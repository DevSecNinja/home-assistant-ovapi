"""Real HA WebSocket contract, lifecycle, permissions and log-retention checks."""

import json
import logging
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er

from .test_coordinator import tick
from .test_init import setup_entry

pytestmark = pytest.mark.freeze_time("2030-01-15T12:00:00+00:00")


@pytest.fixture(autouse=True)
def no_transport_heartbeat():
    """Transport heartbeat timing is outside source expiry fake-time tests."""
    with patch("aiohttp.web_ws.WebSocketResponse._reset_heartbeat"):
        yield


async def subscribe(client, entity_id, message_id=1):
    await client.send_json(
        {"id": message_id, "type": "ovapi/subscribe", "entity_id": entity_id}
    )
    result = await client.receive_json()
    assert result["success"], result
    return (await client.receive_json())["event"]


async def test_contract_local_options_and_rename(
    hass, api, payload, freezer, hass_ws_client
):
    freezer.move_to("2030-01-15T12:00:00+00:00")
    entry = await setup_entry(hass, api, payload, walking_minutes=5)
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", "ovapi", entry.entry_id)
    client = await hass_ws_client(hass)
    board = await subscribe(client, entity_id)
    assert board["contract_version"] == 1
    assert board["status"] == "ready"
    assert board["departures"][0]["delay_seconds"] == 120
    assert board["walking_minutes"] == 5
    assert api.call_count == 1
    # Ten additional subscribers do not cause an upstream request.
    for message_id in range(2, 12):
        assert (await subscribe(client, entity_id, message_id))["expires_at"] == board[
            "expires_at"
        ]
    assert api.call_count == 1
    await client.send_json({"id": 12, "type": "unsubscribe_events", "subscription": 1})
    assert (await client.receive_json())["success"]
    await client.close()

    client = await hass_ws_client(hass)
    replay = await subscribe(client, entity_id)
    assert replay["fetched_at"] == board["fetched_at"]
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"walking_minutes": 9}
    )
    await hass.async_block_till_done()
    updated = (await client.receive_json())["event"]
    assert updated["walking_minutes"] == 9
    assert updated["expires_at"] == board["expires_at"]
    assert hass.states.get(entity_id).state == "ready"
    assert api.call_count == 1

    registry.async_update_entity(entity_id, new_entity_id="sensor.renamed_board")
    await hass.async_block_till_done()
    await entry.runtime_data.async_request_refresh()
    renamed = (await client.receive_json())["event"]
    assert renamed["entity_id"] == "sensor.renamed_board"
    assert api.call_count == 1
    await client.close()


async def test_unload_clears_subscription(hass, api, payload, freezer, hass_ws_client):
    freezer.move_to("2030-01-15T12:00:00+00:00")
    entry = await setup_entry(hass, api, payload)
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", "ovapi", entry.entry_id
    )
    client = await hass_ws_client(hass)
    await subscribe(client, entity_id)
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    unavailable = (await client.receive_json())["event"]
    assert unavailable["status"] == "unavailable"
    assert unavailable["departures"] == []
    assert unavailable["fetched_at"] is None
    await client.close()


async def test_expiry_event(hass, api, payload, freezer, hass_ws_client):
    freezer.move_to("2030-01-15T12:00:00+00:00")
    entry = await setup_entry(hass, api, payload)
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", "ovapi", entry.entry_id
    )
    client = await hass_ws_client(hass)
    await subscribe(client, entity_id)
    api.clear_requests()
    api.get(
        "http://v0.ovapi.nl/tpc/01234567/departures",
        status=503,
        headers={"Retry-After": "3600"},
    )
    await tick(hass, freezer, 121)
    stale = (await client.receive_json())["event"]
    assert stale["status"] == "stale"
    await tick(hass, freezer, 1620)
    # A scheduled cooldown notification can precede the independent expiry event.
    while (event := (await client.receive_json())["event"])["status"] != "unavailable":
        assert event["status"] == "stale"
    assert event["departures"] == []
    assert api.call_count == 1
    await client.close()


async def test_invalid_entity_and_permission(
    hass, api, payload, hass_ws_client, hass_admin_user
):
    entry = await setup_entry(hass, api, payload)
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", "ovapi", entry.entry_id
    )
    client = await hass_ws_client(hass)
    await client.send_json(
        {"id": 1, "type": "ovapi/subscribe", "entity_id": "sensor.missing"}
    )
    assert (await client.receive_json())["error"]["code"] == "not_found"
    with patch.object(
        type(hass_admin_user.permissions), "check_entity", return_value=False
    ):
        await client.send_json(
            {"id": 2, "type": "ovapi/subscribe", "entity_id": entity_id}
        )
        assert (await client.receive_json())["error"]["code"] == "unauthorized"
    await client.close()


async def test_debug_logs_redact_payload(
    hass, api, payload, freezer, hass_ws_client, caplog
):
    freezer.move_to("2030-01-15T12:00:00+00:00")
    entry = await setup_entry(hass, api, payload)
    logger_name = "homeassistant.components.websocket_api.http.connection"
    caplog.set_level(logging.DEBUG, logger=logger_name)
    client = await hass_ws_client(hass)
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", "ovapi", entry.entry_id
    )
    await subscribe(client, entity_id)
    await hass.async_block_till_done()
    assert "SYNTHETIC_TRIP" not in caplog.text
    assert "Synthetic destination" not in caplog.text
    assert "payload omitted" in caplog.text
    # Also cover coalesced frames and slow-client error logging.
    logging.getLogger(logger_name).error(
        "Last message was %s",
        json.dumps([{"event": {"board_id": "x", "departures": ["secret"]}}]).encode(),
    )
    assert "secret" not in caplog.text
    await client.close()


async def test_removed_registry_entry_ends_subscription(
    hass, api, payload, hass_ws_client
):
    entry = await setup_entry(hass, api, payload)
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", "ovapi", entry.entry_id)
    client = await hass_ws_client(hass)
    await subscribe(client, entity_id)
    registry.async_remove(entity_id)
    await hass.async_block_till_done()
    await entry.runtime_data.async_request_refresh()
    assert (await client.receive_json())["error"]["code"] == "not_found"
    await client.close()


async def test_revoked_permission_ends_subscription(
    hass, api, payload, hass_ws_client, hass_admin_user
):
    entry = await setup_entry(hass, api, payload)
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", "ovapi", entry.entry_id
    )
    client = await hass_ws_client(hass)
    await subscribe(client, entity_id)
    with patch.object(
        type(hass_admin_user.permissions), "check_entity", return_value=False
    ):
        await entry.runtime_data.async_request_refresh()
        assert (await client.receive_json())["error"]["code"] == "unauthorized"
    await client.close()


async def test_missing_config_entry(hass, api, payload, hass_ws_client):
    entry = await setup_entry(hass, api, payload)
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", "ovapi", entry.entry_id
    )
    client = await hass_ws_client(hass)
    with patch.object(hass.config_entries, "async_get_entry", return_value=None):
        await client.send_json(
            {"id": 1, "type": "ovapi/subscribe", "entity_id": entity_id}
        )
        assert (await client.receive_json())["error"]["code"] == "not_found"
    await client.close()
