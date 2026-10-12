"""Native stop selection through HA public flow and HTTP interfaces."""

import logging

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.ovapi.coordinator import get_coordinator
from custom_components.ovapi.discovery import MAX_LOOKUPS, MAX_SEARCH_RESULTS

from .test_coordinator import tick
from .test_discovery import DIRECTORY
from .test_discovery_coordinator import settle
from .test_init import make_entry


async def start_picker(hass, api):
    api.get("http://v0.ovapi.nl/stopareacode/", json=DIRECTORY)
    result = await hass.config_entries.flow.async_init(
        "ovapi", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "search"}
    )
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    await settle()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["step_id"] == "search"
    return result


async def test_picker_cold_path(hass, api, payload, freezer):
    freezer.move_to("2030-01-15T12:00:00+00:00")
    result = await start_picker(hass, api)
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"query": "synthetisch centraal"}
    )
    assert result["step_id"] == "area"
    api.get("http://v0.ovapi.nl/stopareacode/AbC01/departures", json={"AbC01": payload})
    result = await hass.config_entries.flow.async_configure(flow_id, {"area": "AbC01"})
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    await settle()
    assert api.call_count == 2
    result = await hass.config_entries.flow.async_configure(flow_id)
    assert result["step_id"] == "point"
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"stop_id": "01234567", "name": "My tram"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"name": "My tram", "stop_id": "01234567"}
    assert result["result"].state is ConfigEntryState.LOADED
    assert api.call_count == 2


async def choose_area(hass, result, query="centraal", area="AbC01"):
    flow_id = result["flow_id"]
    result = await hass.config_entries.flow.async_configure(flow_id, {"query": query})
    assert result["step_id"] == "area"
    return await hass.config_entries.flow.async_configure(flow_id, {"area": area})


@pytest.mark.parametrize(
    "query,error",
    [
        ("missing", "no_matches"),
        (" ", "short_query"),
    ],
)
async def test_search_errors_and_manual(hass, api, query, error):
    result = await start_picker(hass, api)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"query": query}
    )
    assert error in result["errors"].values()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"manual": True}
    )
    assert result["step_id"] == "manual"
    assert api.call_count == 1


async def test_search_limits_change_and_invalid_choice(hass, api):
    result = await start_picker(hass, api)
    coordinator = get_coordinator(hass)
    from custom_components.ovapi.discovery import StopArea

    coordinator.lookup("").areas = tuple(
        StopArea(str(i), "Town", "Name") for i in range(MAX_SEARCH_RESULTS + 1)
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"query": "name"}
    )
    assert result["errors"]["base"] == "too_many_matches"
    coordinator.lookup("").areas = (StopArea("A", "Town", "Name"),)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"query": "name"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"search_again": True}
    )
    assert result["step_id"] == "search"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"query": "name"}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["errors"]["base"] == "selection_expired"
    assert api.call_count == 1


async def test_directory_error_recovery(hass, api, freezer):
    api.get("http://v0.ovapi.nl/stopareacode/", status=503)
    result = await hass.config_entries.flow.async_init(
        "ovapi", context={"source": config_entries.SOURCE_USER}
    )
    flow_id = result["flow_id"]
    await hass.config_entries.flow.async_configure(flow_id, {"next_step_id": "search"})
    await settle()
    result = await hass.config_entries.flow.async_configure(flow_id)
    assert result["errors"]["base"] == "cannot_connect"
    # An explicit new search retries directory acquisition after backoff.
    result = await hass.config_entries.flow.async_configure(flow_id, {"query": "town"})
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    await settle()
    api.clear_requests()
    api.get("http://v0.ovapi.nl/stopareacode/", json=DIRECTORY)
    await tick(hass, freezer, 240)
    await settle()
    result = await hass.config_entries.flow.async_configure(flow_id)
    assert result["step_id"] == "search"
    assert not result["errors"]
    hass.config_entries.flow.async_abort(flow_id)
    await settle()
    assert not get_coordinator(hass)._lookup_tasks


@pytest.mark.parametrize("kind", ["empty", "error", "expired"])
async def test_detail_recovery(hass, api, freezer, kind):
    result = await start_picker(hass, api)
    flow_id = result["flow_id"]
    if kind == "error":
        api.get("http://v0.ovapi.nl/stopareacode/AbC01/departures", status=404)
    else:
        api.get("http://v0.ovapi.nl/stopareacode/AbC01/departures", json={"AbC01": {}})
    await choose_area(hass, result)
    await settle()
    await tick(hass, freezer, 120)
    await settle()
    if kind == "expired":
        get_coordinator(hass).discard_lookup("AbC01")
    result = await hass.config_entries.flow.async_configure(flow_id)
    assert result["step_id"] == "retry"
    assert (
        result["errors"]["base"]
        == {
            "empty": "no_points",
            "error": "unknown_area",
            "expired": "selection_expired",
        }[kind]
    )
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"action": "retry"}
    )
    assert result["step_id"] == "details"
    hass.config_entries.flow.async_abort(flow_id)
    await settle()


@pytest.mark.parametrize("step", ["search", "area", "point"])
async def test_expired_labels_removed_and_replay(hass, api, payload, freezer, step):
    result = await start_picker(hass, api)
    flow_id = result["flow_id"]
    if step in ("area", "point"):
        result = await hass.config_entries.flow.async_configure(
            flow_id, {"query": "centraal"}
        )
    if step == "point":
        api.get(
            "http://v0.ovapi.nl/stopareacode/AbC01/departures", json={"AbC01": payload}
        )
        await hass.config_entries.flow.async_configure(flow_id, {"area": "AbC01"})
        await settle()
        await tick(hass, freezer, 120)
        await settle()
        result = await hass.config_entries.flow.async_configure(flow_id)
    flow = hass.config_entries.flow._progress[flow_id]
    await tick(hass, freezer, 1740)
    assert not flow._picked_name
    assert "data_schema" not in flow.cur_step
    result = await hass.config_entries.flow.async_configure(flow_id)
    assert result["step_id"] == "retry"
    assert result["errors"]["base"] == "selection_expired"
    result = await hass.config_entries.flow.async_configure(
        flow_id,
        {"action": {"search": "retry", "area": "search", "point": "manual"}[step]},
    )
    if step == "point":
        assert result["step_id"] == "manual"
    else:
        assert result["type"] is FlowResultType.SHOW_PROGRESS
    hass.config_entries.flow.async_abort(flow_id)
    await settle()


async def test_empty_stop_can_be_selected(hass, api, freezer):
    result = await start_picker(hass, api)
    api.get(
        "http://v0.ovapi.nl/stopareacode/AbC01/departures",
        json={
            "AbC01": {
                "01234567": {"Stop": {"TimingPointName": "Night stop"}, "Passes": {}}
            }
        },
    )
    await choose_area(hass, result)
    await settle()
    await tick(hass, freezer, 120)
    await settle()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Night stop", "stop_id": "01234567"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert api.call_count == 2


async def test_reconfigure_picker_preserves_registry_and_options(
    hass, api, payload, freezer
):
    entry = make_entry(hass, walking_minutes=7, lines="X1")
    api.get("http://v0.ovapi.nl/tpc/01234567/departures", json=payload)
    api.get("http://v0.ovapi.nl/stopareacode/", json=DIRECTORY)
    # Warm caches before the flow; the flow still emits native progress once.
    coordinator = get_coordinator(hass)
    await coordinator.async_lookup("")
    api.get(
        "http://v0.ovapi.nl/stopareacode/AbC01/departures",
        json={"AbC01": {"76543210": {"Passes": {}}}},
    )
    task = hass.async_create_background_task(
        coordinator.async_lookup("AbC01"), "test lookup"
    )
    await settle()
    await tick(hass, freezer, 120)
    await settle()
    await tick(hass, freezer, 120)
    await settle()
    await task
    assert await hass.config_entries.async_setup(entry.entry_id)
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", "ovapi", entry.entry_id
    )
    before = api.call_count
    result = await hass.config_entries.flow.async_init(
        "ovapi",
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    flow_id = result["flow_id"]
    await hass.config_entries.flow.async_configure(flow_id, {"next_step_id": "search"})
    await settle()
    result = await hass.config_entries.flow.async_configure(flow_id)
    await choose_area(hass, result)
    await settle()
    result = await hass.config_entries.flow.async_configure(flow_id)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"name": "Changed stop", "stop_id": "76543210"}
    )
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert entry.options["walking_minutes"] == 7
    assert entry.options["lines"] == "X1"
    assert (
        er.async_get(hass).async_get_entity_id("sensor", "ovapi", entry.entry_id)
        == entity_id
    )
    assert api.call_count == before


async def test_flow_limit(hass):
    flows = []
    for _ in range(MAX_LOOKUPS):
        result = await hass.config_entries.flow.async_init(
            "ovapi", context={"source": config_entries.SOURCE_USER}
        )
        flows.append(result["flow_id"])
    result = await hass.config_entries.flow.async_init(
        "ovapi", context={"source": config_entries.SOURCE_USER}
    )
    assert result["reason"] == "discovery_busy"
    for flow_id in flows:
        hass.config_entries.flow.async_abort(flow_id)


async def test_expiry_cancels_budget_wait(hass, api, freezer):
    result = await start_picker(hass, api)
    coordinator = get_coordinator(hass)
    # A server-directed pause may outlast the directory's remaining lifetime.
    coordinator._backoff_until = coordinator._next_request + 3600
    await choose_area(hass, result)
    await settle()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    await tick(hass, freezer, 1740)
    await settle()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["step_id"] == "retry"
    assert not coordinator._lookup_tasks
    assert api.call_count == 1
    hass.config_entries.flow.async_abort(result["flow_id"])


@pytest.mark.parametrize("outcome", ["limit", "duplicate", "invalid_name"])
async def test_point_save_errors(hass, api, payload, freezer, outcome):
    result = await start_picker(hass, api)
    api.get("http://v0.ovapi.nl/stopareacode/AbC01/departures", json={"AbC01": payload})
    await choose_area(hass, result)
    await settle()
    await tick(hass, freezer, 120)
    await settle()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    if outcome == "limit":
        get_coordinator(hass).entries = {str(i): str(i) for i in range(10)}
    elif outcome == "duplicate":
        make_entry(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": " " if outcome == "invalid_name" else "Favourite",
            "stop_id": "01234567",
        },
    )
    if outcome == "duplicate":
        assert result["reason"] == "already_configured"
    else:
        assert ("too_many_stops" if outcome == "limit" else "invalid_name") in (
            result["errors"].values()
        )
        hass.config_entries.flow.async_abort(result["flow_id"])
    assert api.call_count == 2


async def test_completed_progress_retries_notification_until_ack(hass, api, freezer):
    from homeassistant.data_entry_flow import EVENT_DATA_ENTRY_FLOW_PROGRESSED

    events = []

    @callback
    def record(event):
        events.append(event.data)

    hass.bus.async_listen(EVENT_DATA_ENTRY_FLOW_PROGRESSED, record)
    api.get("http://v0.ovapi.nl/stopareacode/", json=DIRECTORY)
    result = await hass.config_entries.flow.async_init(
        "ovapi", context={"source": config_entries.SOURCE_USER}
    )
    flow_id = result["flow_id"]
    await hass.config_entries.flow.async_configure(flow_id, {"next_step_id": "search"})
    await settle()
    flow = hass.config_entries.flow._progress[flow_id]
    assert flow.cur_step["type"] is FlowResultType.SHOW_PROGRESS_DONE
    events.clear()
    await tick(hass, freezer, 1)
    assert len(events) == 1
    assert events[0] == {"handler": "ovapi", "flow_id": flow_id, "refresh": True}
    assert api.call_count == 1
    await hass.config_entries.flow.async_configure(flow_id)
    assert flow._notify_cancel is None
    events.clear()
    await tick(hass, freezer, 5)
    assert not events
    hass.config_entries.flow.async_abort(flow_id)
    assert flow._expiry_cancel is None


async def test_failed_unattended_progress_notifications_are_bounded(hass, api, freezer):
    api.get("http://v0.ovapi.nl/stopareacode/", status=503)
    result = await hass.config_entries.flow.async_init(
        "ovapi", context={"source": config_entries.SOURCE_USER}
    )
    await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "search"}
    )
    await settle()
    flow = hass.config_entries.flow._progress[result["flow_id"]]
    await tick(hass, freezer, 1740)
    assert flow._notify_cancel is None
    assert api.call_count == 1
    hass.config_entries.flow.async_abort(result["flow_id"])


async def test_actual_http_serialization(
    hass, hass_client, api, payload, freezer, caplog
):
    assert await async_setup_component(hass, "config", {})
    assert await async_setup_component(hass, "websocket_api", {})
    client = await hass_client()
    for name in (
        "homeassistant.data_entry_flow",
        "homeassistant.helpers.data_entry_flow",
        "homeassistant.components.config.config_entries",
        "homeassistant.components.websocket_api.http.connection",
        "custom_components.ovapi",
    ):
        caplog.set_level(logging.DEBUG, logger=name)
    api.get("http://v0.ovapi.nl/stopareacode/", json=DIRECTORY)
    response = await client.post(
        "/api/config/config_entries/flow", json={"handler": "ovapi"}
    )
    assert response.status == 200
    result = await response.json()
    url = f"/api/config/config_entries/flow/{result['flow_id']}"
    response = await client.post(url, json={"next_step_id": "search"})
    assert response.status == 200
    assert (await response.json())["type"] == "progress"
    await settle()
    response = await client.get(url)
    assert response.status == 200
    result = await response.json()
    assert result["step_id"] == "search"
    response = await client.post(url, json={"query": "centraal"})
    assert response.status == 200
    result = await response.json()
    options = result["data_schema"][0]["selector"]["select"]["options"]
    assert len(options) == 2
    assert any("Centràal" in option["label"] for option in options)
    api.get("http://v0.ovapi.nl/stopareacode/AbC01/departures", json={"AbC01": payload})
    response = await client.post(url, json={"area": "AbC01"})
    assert response.status == 200
    assert (await response.json())["type"] == "progress"
    await settle()
    await tick(hass, freezer, 120)
    await settle()
    response = await client.get(url)
    assert response.status == 200
    assert (await response.json())["step_id"] == "point"
    response = await client.post(url, json={"stop_id": "01234567", "name": "Favourite"})
    assert response.status == 200
    result = await response.json()
    assert result["type"] == "create_entry"
    assert api.call_count == 2
    assert "Synthetisch" not in caplog.text
    assert "Synthetic destination" not in caplog.text
    assert "Centràal" not in caplog.text


async def test_http_manual_options_and_reconfigure(hass, hass_client, api, payload):
    assert await async_setup_component(hass, "config", {})
    assert await async_setup_component(hass, "websocket_api", {})
    client = await hass_client()
    api.get("http://v0.ovapi.nl/tpc/01234567/departures", json=payload)
    response = await client.post(
        "/api/config/config_entries/flow", json={"handler": "ovapi"}
    )
    result = await response.json()
    url = f"/api/config/config_entries/flow/{result['flow_id']}"
    response = await client.post(url, json={"next_step_id": "manual"})
    assert response.status == 200
    assert (await response.json())["step_id"] == "manual"
    response = await client.post(url, json={"name": "Favourite", "stop_id": "01234567"})
    assert response.status == 200
    assert (await response.json())["type"] == "create_entry"
    entry = hass.config_entries.async_entries("ovapi")[0]
    response = await client.post(
        "/api/config/config_entries/options/flow", json={"handler": entry.entry_id}
    )
    assert response.status == 200
    result = await response.json()
    response = await client.post(
        f"/api/config/config_entries/options/flow/{result['flow_id']}",
        json={"walking_minutes": 9},
    )
    assert response.status == 200
    assert entry.options["walking_minutes"] == 9
    response = await client.post(
        "/api/config/config_entries/flow",
        json={
            "handler": "ovapi",
            "entry_id": entry.entry_id,
        },
    )
    assert response.status == 200
    result = await response.json()
    assert result["step_id"] == "reconfigure"
    url = f"/api/config/config_entries/flow/{result['flow_id']}"
    response = await client.post(url, json={"next_step_id": "manual"})
    assert response.status == 200
    response = await client.post(
        url,
        json={
            "name": "New favourite name",
            "stop_id": "01234567",
        },
    )
    assert response.status == 200
    assert (await response.json())["reason"] == "reconfigure_successful"
    assert entry.data["name"] == "New favourite name"
    assert entry.options["walking_minutes"] == 9
    assert api.call_count == 1
