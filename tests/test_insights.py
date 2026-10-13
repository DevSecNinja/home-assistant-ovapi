"""Passive native diagnostics, exact board identity and request-budget contracts."""

from unittest.mock import patch

import pytest
from homeassistant.const import EntityCategory
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import DATA_DISPATCHER
from homeassistant.setup import async_setup_component

from custom_components.ovapi.combined import source_entity
from custom_components.ovapi.const import SIGNAL_COMBINED_UPDATE
from custom_components.ovapi.coordinator import get_coordinator

from .test_combined import (
    create_combined,
    entity_id,
    saved_combined,
    setup_sources,
)
from .test_coordinator import tick
from .test_init import make_entry, setup_entry
from .test_websocket import subscribe

pytestmark = pytest.mark.freeze_time("2030-01-15T12:00:00+00:00")


@pytest.fixture(autouse=True)
def no_transport_heartbeat():
    with patch("aiohttp.web_ws.WebSocketResponse._reset_heartbeat"):
        yield


def insight_id(hass, entry, key):
    return er.async_get(hass).async_get_entity_id(
        "sensor", "ovapi", f"{entry.entry_id}_{key}"
    )


def insight(hass, entry, key):
    state = hass.states.get(insight_id(hass, entry, key))
    assert state is not None
    return state


def assert_counts(hass, entry, configured, ready):
    assert insight(hass, entry, "configured_sources").state == str(configured)
    assert insight(hass, entry, "ready_sources").state == str(ready)


async def test_native_registry_and_retention_allowlist(hass, api, payload):
    sources = await setup_sources(hass, api, payload)
    group = await create_combined(hass, sources, walking_minutes=7)
    registry = er.async_get(hass)
    for entry in (*sources, group):
        board_id = entity_id(hass, entry)
        board = registry.async_get(board_id)
        assert board.unique_id == entry.entry_id
        assert board_id.endswith("_departure_board")
        state = hass.states.get(board_id)
        assert state.attributes["board_id"] == entry.entry_id
        assert state.attributes["contract_version"] == 1
        keys = ["walking_duration"]
        if entry is group:
            keys += ["configured_sources", "ready_sources"]
        entities = er.async_entries_for_config_entry(registry, entry.entry_id)
        assert len(entities) == 1 + len(keys)
        for key in keys:
            diagnostic_id = insight_id(hass, entry, key)
            diagnostic = registry.async_get(diagnostic_id)
            assert diagnostic.entity_category is EntityCategory.DIAGNOSTIC
            assert diagnostic.disabled_by is None
            assert diagnostic.hidden_by is None
            assert diagnostic.device_id == board.device_id
            assert diagnostic.translation_key == key
            assert diagnostic.capabilities is None
            attributes = insight(hass, entry, key).attributes
            assert set(attributes) <= {
                "friendly_name",
                "icon",
                "device_class",
                "unit_of_measurement",
            }
            assert "state_class" not in attributes
        device = dr.async_get(hass).async_get(board.device_id)
        assert device.name == entry.data["name"]
        assert device.entry_type is dr.DeviceEntryType.SERVICE
    walking = insight(hass, group, "walking_duration")
    assert walking.state == "7"
    assert walking.attributes["unit_of_measurement"] == "min"
    assert walking.attributes["device_class"] == "duration"
    assert insight(hass, sources[0], "walking_duration").state == "9"
    assert insight(hass, sources[1], "walking_duration").state == "0"
    assert_counts(hass, group, 2, 2)
    assert len(group.runtime_data._listeners) == 2
    assert api.call_count == 1


async def test_diagnostics_cannot_subscribe_as_boards(
    hass, api, payload, hass_ws_client
):
    sources = await setup_sources(hass, api, payload)
    group = await create_combined(hass, sources)
    coordinator = get_coordinator(hass)
    listeners = len(coordinator._listeners)
    for entry in (*sources, group):
        keys = ["walking_duration"]
        if entry is group:
            keys += ["configured_sources", "ready_sources"]
        for key in keys:
            client = await hass_ws_client(hass)
            await client.send_json(
                {
                    "id": 1,
                    "type": "ovapi/subscribe",
                    "entity_id": insight_id(hass, entry, key),
                }
            )
            result = await client.receive_json()
            assert result["error"]["code"] == "not_found"
            assert len(coordinator._listeners) == listeners
            await client.close()
    # Identity, not attributes or ready state, still accepts original/legacy boards.
    await hass.config_entries.async_unload(sources[0].entry_id)
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)
    board = await subscribe(client, entity_id(hass, group))
    assert board["status"] == "unavailable"
    assert board["departures"] == []
    assert api.call_count == 1
    await client.close()


async def test_local_options_reload_and_registry_order(hass, api, payload):
    sources = await setup_sources(hass, api, payload)
    group = await create_combined(hass, sources)
    third = make_entry(hass, lines="X2", name="Third source")
    assert await hass.config_entries.async_setup(third.entry_id)
    registry = er.async_get(hass)
    original_id = entity_id(hass, sources[0])
    registry.async_update_entity(
        insight_id(hass, sources[0], "walking_duration"),
        new_entity_id="sensor.first_diagnostic",
    )
    registry.async_update_entity(original_id, new_entity_id="sensor.renamed_source")
    await hass.async_block_till_done()
    assert source_entity(hass, sources[0].entry_id).entity_id == "sensor.renamed_source"
    original_walk_id = insight_id(hass, group, "walking_duration")
    result = await hass.config_entries.options.async_init(group.entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "source_entry_ids": [entry.entry_id for entry in (*sources, third)],
            "walking_minutes": 12,
        },
    )
    result = await hass.config_entries.options.async_init(sources[0].entry_id)
    await hass.config_entries.options.async_configure(
        result["flow_id"], {"walking_minutes": 0}
    )
    await hass.async_block_till_done()
    assert_counts(hass, group, 3, 3)
    assert insight(hass, group, "walking_duration").state == "12"
    assert hass.states.get("sensor.first_diagnostic").state == "0"
    assert await hass.config_entries.async_reload(group.entry_id)
    await hass.async_block_till_done()
    assert insight_id(hass, group, "walking_duration") == original_walk_id
    assert_counts(hass, group, 3, 3)
    assert api.call_count == 1


@pytest.mark.parametrize(
    "action", ["unload", "remove", "disable_entity", "remove_entity", "disable_entry"]
)
async def test_health_remains_visible_after_source_loss(hass, api, payload, action):
    from homeassistant.config_entries import ConfigEntryDisabler

    sources = await setup_sources(hass, api, payload)
    third = make_entry(hass, name="Third source", lines="X2")
    assert await hass.config_entries.async_setup(third.entry_id)
    group = await create_combined(hass, (*sources, third), walking_minutes=7)
    registry = er.async_get(hass)
    board_id = entity_id(hass, sources[1])
    assert_counts(hass, group, 3, 3)
    if action == "unload":
        await hass.config_entries.async_unload(sources[1].entry_id)
    elif action == "remove":
        await hass.config_entries.async_remove(sources[1].entry_id)
    elif action == "disable_entity":
        registry.async_update_entity(
            board_id, disabled_by=er.RegistryEntryDisabler.USER
        )
    elif action == "remove_entity":
        registry.async_remove(board_id)
    else:
        await hass.config_entries.async_set_disabled_by(
            sources[1].entry_id, ConfigEntryDisabler.USER
        )
    await hass.async_block_till_done()
    assert_counts(hass, group, 3, 2)
    assert insight(hass, group, "walking_duration").state == "7"
    assert hass.states.get(entity_id(hass, group)).state == "unavailable"
    assert hass.states.get(entity_id(hass, group)).attributes["unavailable_sources"]
    if action == "disable_entity":
        # An enabled diagnostic is not a substitute for the disabled board.
        assert insight(hass, sources[1], "walking_duration").state == "0"
        registry.async_update_entity(board_id, disabled_by=None)
        await hass.async_block_till_done()
        assert_counts(hass, group, 3, 3)
    assert api.call_count == 1


async def test_ready_excludes_stale_and_expired_includes_empty(
    hass, api, payload, freezer
):
    sources = await setup_sources(hass, api, payload)
    group = await create_combined(hass, sources)
    api.clear_requests()
    api.get("http://v0.ovapi.nl/tpc/01234567,76543210/departures", json=payload)
    await tick(hass, freezer, 121)
    assert_counts(hass, group, 2, 1)
    assert hass.states.get(entity_id(hass, group)).state == "stale"
    api.clear_requests()
    api.get(
        "http://v0.ovapi.nl/tpc/01234567,76543210/departures",
        status=503,
        headers={"Retry-After": "3600"},
    )
    await tick(hass, freezer, 121)
    assert_counts(hass, group, 2, 0)
    await tick(hass, freezer, 1740)
    assert_counts(hass, group, 2, 0)
    assert hass.states.get(entity_id(hass, group)).state == "unavailable"
    assert insight(hass, sources[0], "walking_duration").state == "9"
    assert api.call_count == 1
    api.clear_requests()
    api.get(
        "http://v0.ovapi.nl/tpc/01234567,76543210/departures",
        json={
            "01234567": {"Passes": {}},
            "76543210": {"Passes": {}},
        },
    )
    await tick(hass, freezer, 3601)
    assert_counts(hass, group, 2, 2)
    assert api.call_count == 1


@pytest.mark.parametrize("with_group", [False, True])
@pytest.mark.parametrize("disable_after_setup", [False, True])
async def test_all_leaf_boards_disabled_diagnostics_never_poll(
    hass, api, payload, freezer, with_group, disable_after_setup
):
    assert await async_setup_component(hass, "homeassistant", {})
    sources = [make_entry(hass), make_entry(hass, lines="X1", name="Second")]
    registry = er.async_get(hass)
    for source in sources:
        registry.async_get_or_create(
            "sensor",
            "ovapi",
            source.entry_id,
            config_entry=source,
            disabled_by=(
                None if disable_after_setup else er.RegistryEntryDisabler.USER
            ),
        )
    group = saved_combined(hass, sources) if with_group else None
    api.get("http://v0.ovapi.nl/tpc/01234567/departures", json=payload)
    assert await async_setup_component(hass, "ovapi", {})
    await hass.async_block_till_done()
    coordinator = get_coordinator(hass)
    if disable_after_setup:
        assert len(coordinator._listeners) == 2
        for source in sources:
            registry.async_update_entity(
                entity_id(hass, source),
                disabled_by=er.RegistryEntryDisabler.USER,
            )
        await hass.async_block_till_done()
    assert not coordinator._listeners
    if group:
        assert_counts(hass, group, 2, 0)
    await tick(hass, freezer, 121)
    entries = [*sources, *([group] if group else [])]
    ids = [
        entity.entity_id
        for entry in entries
        for entity in er.async_entries_for_config_entry(registry, entry.entry_id)
        if not entity.disabled
    ]
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": ids}, blocking=True
    )
    for entry in entries:
        result = await hass.config_entries.options.async_init(entry.entry_id)
        values = {"walking_minutes": 7}
        if entry is group:
            values["source_entry_ids"] = [source.entry_id for source in sources]
        await hass.config_entries.options.async_configure(result["flow_id"], values)
        await hass.async_block_till_done()
        assert insight(hass, entry, "walking_duration").state == "7"
        assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert not coordinator._listeners
    assert api.call_count == 1
    await tick(hass, freezer, 1740)
    assert not coordinator._cache
    assert api.call_count == 1
    await hass.services.async_call(
        "homeassistant", "update_entity", {"entity_id": ids}, blocking=True
    )
    assert api.call_count == 1
    for entry in entries:
        await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not coordinator._listeners
    assert not coordinator._source_unsubs
    assert not hass.data[DATA_DISPATCHER].get(SIGNAL_COMBINED_UPDATE)
    assert coordinator._expiry_cancel is None
    # Removed entities must not retain a dispatcher callback that writes state.
    before = {key: hass.states.get(key) for key in ids}
    coordinator.async_update_listeners()
    await hass.async_block_till_done()
    assert {key: hass.states.get(key) for key in ids} == before


async def test_manual_diagnostics_and_options_do_not_postpone_poll(
    hass, api, payload, freezer
):
    assert await async_setup_component(hass, "homeassistant", {})
    entry = await setup_entry(hass, api, payload)
    for walking in range(1, 5):
        await tick(hass, freezer, 30)
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {"entity_id": insight_id(hass, entry, "walking_duration")},
            blocking=True,
        )
        result = await hass.config_entries.options.async_init(entry.entry_id)
        await hass.config_entries.options.async_configure(
            result["flow_id"], {"walking_minutes": walking}
        )
        await hass.async_block_till_done()
        assert insight(hass, entry, "walking_duration").state == str(walking)
    await tick(hass, freezer, 1)
    assert api.call_count == 2
