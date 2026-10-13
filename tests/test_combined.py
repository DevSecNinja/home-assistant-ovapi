"""Manual leaf combinations through HA flows, state and transient subscriptions."""

from copy import deepcopy
from unittest.mock import patch

import probatio
import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ovapi.client import ApiError
from custom_components.ovapi.combined import combined_identity
from custom_components.ovapi.coordinator import get_coordinator
from custom_components.ovapi.diagnostics import async_get_config_entry_diagnostics

from .test_coordinator import tick
from .test_init import make_entry
from .test_websocket import subscribe

pytestmark = pytest.mark.freeze_time("2030-01-15T12:00:00+00:00")


@pytest.fixture(autouse=True)
def no_transport_heartbeat():
    with patch("aiohttp.web_ws.WebSocketResponse._reset_heartbeat"):
        yield


async def setup_sources(hass, api, payload):
    first = make_entry(hass, name="Synthetic east", walking_minutes=9)
    second = make_entry(hass, stop="76543210", name="Synthetic west")
    west = deepcopy(payload["01234567"])
    west["Passes"]["SYNTHETIC_TRIP"]["DestinationName50"] = "Opposite direction"
    west["Passes"]["SYNTHETIC_TRIP"]["ExpectedDepartureTime"] = None
    api.get(
        "http://v0.ovapi.nl/tpc/01234567,76543210/departures",
        json={**payload, "76543210": west},
    )
    assert await hass.config_entries.async_setup(first.entry_id)
    await hass.async_block_till_done()
    assert second.state is ConfigEntryState.LOADED
    assert api.call_count == 1
    return first, second


async def create_combined(hass, sources, **values):
    result = await hass.config_entries.flow.async_init(
        "ovapi", context={"source": config_entries.SOURCE_USER}
    )
    assert "combined" in result["menu_options"]
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "combined"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "Synthetic combined",
            "source_entry_ids": [entry.entry_id for entry in sources],
            **values,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY, result
    return result["result"]


def entity_id(hass, entry):
    return er.async_get(hass).async_get_entity_id("sensor", "ovapi", entry.entry_id)


async def test_two_leaves_one_board_no_requests(hass, api, payload, hass_ws_client):
    first, second = await setup_sources(hass, api, payload)
    combined = await create_combined(hass, (first, second))
    client = await hass_ws_client(hass)
    board = await subscribe(client, entity_id(hass, combined))
    assert board["board_id"] == combined.entry_id
    assert board["stop"] == {"id": combined.entry_id, "name": "Synthetic combined"}
    assert board["walking_minutes"] == 0
    assert board["status"] == "ready"
    assert [row["destination"] for row in board["departures"]] == [
        "Opposite direction",
        "Synthetic destination",
    ]
    assert "coverage" not in board
    state = hass.states.get(entity_id(hass, combined))
    assert state.state == "ready"
    assert state.attributes["contract_version"] == 1
    assert "departures" not in state.attributes
    assert first.runtime_data.stop_count == 2
    assert api.call_count == 1
    await client.close()


def saved_combined(hass, sources, name="Saved group"):
    ids = [entry.entry_id for entry in sources]
    entry = MockConfigEntry(
        domain="ovapi",
        title=name,
        data={"entry_type": "combined", "name": name},
        options={"source_entry_ids": ids, "walking_minutes": 0},
        unique_id=combined_identity(ids),
    )
    entry.add_to_hass(hass)
    return entry


async def new_form(hass):
    result = await hass.config_entries.flow.async_init(
        "ovapi", context={"source": config_entries.SOURCE_USER}
    )
    return await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "combined"}
    )


async def received_status(client, expected):
    for _ in range(30):
        event = (await client.receive_json())["event"]
        if event["status"] == expected:
            return event
    pytest.fail(f"No {expected} update")


def assert_unavailable(board):
    assert board["status"] == "unavailable"
    assert board["departures"] == []
    assert board["fetched_at"] is None
    assert board["expires_at"] is None


@pytest.mark.parametrize("kind", ["options", "reconfigure"])
async def test_edit_group_preserves_age_identity(
    hass, api, payload, kind, hass_ws_client
):
    sources = await setup_sources(hass, api, payload)
    group = await create_combined(hass, sources)
    third = make_entry(hass, name="Another view", lines="X1")
    assert await hass.config_entries.async_setup(third.entry_id)
    old_id = entity_id(hass, group)
    client = await hass_ws_client(hass)
    original = await subscribe(client, old_id)
    values = {
        "source_entry_ids": [sources[0].entry_id, third.entry_id],
        "walking_minutes": 7,
    }
    if kind == "options":
        manager = hass.config_entries.options
        result = await manager.async_init(group.entry_id)
    else:
        manager = hass.config_entries.flow
        result = await manager.async_init(
            "ovapi", context={"source": "reconfigure", "entry_id": group.entry_id}
        )
        values["name"] = "Renamed combination"
    fields = probatio.to_field_list(
        result["data_schema"], custom_serializer=cv.custom_serializer
    )
    assert next(field for field in fields if field["name"] == "source_entry_ids")[
        "selector"
    ]["select"]["multiple"]
    result = await manager.async_configure(result["flow_id"], values)
    await hass.async_block_till_done()
    assert result["type"] in (FlowResultType.CREATE_ENTRY, FlowResultType.ABORT)
    assert entity_id(hass, group) == old_id
    board = get_coordinator(hass).snapshot(group, old_id)
    assert board["fetched_at"] == original["fetched_at"]
    assert board["expires_at"] == original["expires_at"]
    assert board["walking_minutes"] == 7
    assert len(board["departures"]) == 1
    if kind == "reconfigure":
        assert board["stop"]["name"] == "Renamed combination"
    assert await hass.config_entries.async_reload(group.entry_id)
    await hass.async_block_till_done()
    assert get_coordinator(hass).snapshot(group, old_id) == board
    assert api.call_count == 1
    await client.close()


@pytest.mark.parametrize(
    "values,error",
    [
        ({"name": " "}, {"name": "invalid_name"}),
        ({"walking_minutes": 1.5}, {"walking_minutes": "invalid_walk"}),
        ({"source_entry_ids": []}, {"source_entry_ids": "invalid_sources"}),
        (
            {"source_entry_ids": ["missing", "absent"]},
            {"source_entry_ids": "invalid_sources"},
        ),
        ({"source_entry_ids": "invalid"}, {"source_entry_ids": "invalid_sources"}),
        ({"source_entry_ids": [1, 2]}, {"source_entry_ids": "invalid_sources"}),
        (
            {"source_entry_ids": ["same", "same"]},
            {"source_entry_ids": "invalid_sources"},
        ),
        (
            {"source_entry_ids": [str(i) for i in range(13)]},
            {"source_entry_ids": "invalid_sources"},
        ),
    ],
)
async def test_invalid_combined_form(hass, api, values, error):
    result = await new_form(hass)
    fields = probatio.to_field_list(
        result["data_schema"], custom_serializer=cv.custom_serializer
    )
    assert fields
    if values.get("source_entry_ids"):
        with pytest.raises(InvalidData):
            await hass.config_entries.flow.async_configure(
                result["flow_id"], {"name": "Group", "source_entry_ids": [], **values}
            )
    else:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"name": "Group", "source_entry_ids": [], **values}
        )
        assert result["errors"] == error
    assert api.call_count == 0


@pytest.mark.parametrize("kind", ["create", "options", "reconfigure"])
async def test_reject_nested_and_duplicate_group(hass, api, payload, kind):
    first, second = await setup_sources(hass, api, payload)
    group = await create_combined(hass, (first, second))
    if kind == "create":
        result = await new_form(hass)
        manager = hass.config_entries.flow
    elif kind == "options":
        manager = hass.config_entries.options
        result = await manager.async_init(group.entry_id)
    else:
        manager = hass.config_entries.flow
        result = await manager.async_init(
            "ovapi", context={"source": "reconfigure", "entry_id": group.entry_id}
        )
    values = {"source_entry_ids": [first.entry_id, group.entry_id]}
    if kind != "options":
        values["name"] = "Group"
    with pytest.raises(InvalidData):
        await manager.async_configure(result["flow_id"], values)
    if kind == "create":
        result = await manager.async_configure(
            result["flow_id"],
            {
                "name": "Duplicate",
                "source_entry_ids": [second.entry_id, first.entry_id],
            },
        )
        assert result["errors"] == {"base": "already_configured"}
    assert api.call_count == 1


async def test_unavailable_sources_selectable_and_missing_removable(hass, api, payload):
    first, second = await setup_sources(hass, api, payload)
    group = await create_combined(hass, (first, second))
    old_source = second.entry_id
    assert await hass.config_entries.async_remove(second.entry_id)
    third = make_entry(hass, name="Unloaded replacement", lines="X2")
    result = await hass.config_entries.options.async_init(group.entry_id)
    fields = probatio.to_field_list(
        result["data_schema"], custom_serializer=cv.custom_serializer
    )
    choices = next(f for f in fields if f["name"] == "source_entry_ids")["selector"][
        "select"
    ]["options"]
    assert {"value": old_source, "label": old_source} in choices
    assert any(choice["value"] == third.entry_id for choice in choices)
    # A saved missing reference can be kept while editing walk.
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"source_entry_ids": [first.entry_id, old_source], "walking_minutes": 2},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    result = await hass.config_entries.options.async_init(group.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"source_entry_ids": [first.entry_id, third.entry_id]},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert old_source not in group.options["source_entry_ids"]
    assert hass.states.get(entity_id(hass, group)).state == "unavailable"
    assert api.call_count == 1


async def test_source_filters_and_new_services(
    hass, api, payload, freezer, hass_ws_client
):
    passes = payload["01234567"]["Passes"]
    base = passes["SYNTHETIC_TRIP"]
    for key, values in {
        "cancelled": {"TripStopStatus": "CANCEL"},
        "unknown": {"TripStopStatus": "UNKNOWN", "ExpectedDepartureTime": None},
        "other_line": {"LinePublicNumber": "X2"},
        "metro": {"TransportType": "METRO"},
    }.items():
        passes[key] = {**base, **values}
    sources = await setup_sources(hass, api, payload)
    group = await create_combined(hass, sources)
    client = await hass_ws_client(hass)
    await subscribe(client, entity_id(hass, group))
    for source in sources:
        result = await hass.config_entries.options.async_init(source.entry_id)
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            {"lines": "X1", "destination": "Synthetic", "transport_types": ["tram"]},
        )
    await hass.async_block_till_done()
    board = get_coordinator(hass).snapshot(group, entity_id(hass, group))
    assert {row["id"] for row in board["departures"]} == {
        "SYNTHETIC_TRIP",
        "cancelled",
        "unknown",
    }
    assert (
        next(row for row in board["departures"] if row["id"] == "cancelled")[
            "cancelled"
        ]
        is True
    )
    unknown = next(row for row in board["departures"] if row["id"] == "unknown")
    assert (
        unknown["cancelled"]
        is unknown["expected_at"]
        is unknown["delay_seconds"]
        is None
    )
    for source in sources:
        result = await hass.config_entries.options.async_init(source.entry_id)
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                "lines": "",
                "destination": "",
                "transport_types": ["bus", "tram", "metro"],
            },
        )
    api.clear_requests()
    base["LinePublicNumber"] = "NEW"
    base["DestinationName50"] = "New destination"
    api.get(
        "http://v0.ovapi.nl/tpc/01234567,76543210/departures",
        json={**payload, "76543210": {"Passes": {}}},
    )
    await tick(hass, freezer, 121)
    board = get_coordinator(hass).snapshot(group, entity_id(hass, group))
    assert any(row["line"] == "NEW" for row in board["departures"])
    assert api.call_count == 1
    await client.close()


async def test_overlap_dedup_all_fields_and_limit(hass, api, payload):
    passes = payload["01234567"]["Passes"]
    base = passes["SYNTHETIC_TRIP"]
    passes.update({f"trip{i:02}": {**base} for i in range(40)})
    first, second = await setup_sources(hass, api, payload)
    overlap = make_entry(hass, name="Overlapping view", lines="X1")
    assert await hass.config_entries.async_setup(overlap.entry_id)
    group = await create_combined(hass, (first, second, overlap))
    board = get_coordinator(hass).snapshot(group, entity_id(hass, group))
    assert len(board["departures"]) == 30
    assert board["departures"][0]["destination"] == "Opposite direction"
    assert len({tuple(row.items()) for row in board["departures"]}) == 30
    assert api.call_count == 1


@pytest.mark.parametrize(
    "action", ["unload", "remove", "disable_entity", "remove_entity", "disable_entry"]
)
async def test_source_loss_clears_live_feed(hass, api, payload, hass_ws_client, action):
    first, second = await setup_sources(hass, api, payload)
    group = await create_combined(hass, (first, second))
    client = await hass_ws_client(hass)
    group_id = entity_id(hass, group)
    await subscribe(client, group_id)
    registry = er.async_get(hass)
    source_id = entity_id(hass, second)
    if action == "unload":
        assert await hass.config_entries.async_unload(second.entry_id)
    elif action == "remove":
        assert await hass.config_entries.async_remove(second.entry_id)
    elif action == "disable_entity":
        registry.async_update_entity(
            source_id, disabled_by=er.RegistryEntryDisabler.USER
        )
    elif action == "remove_entity":
        registry.async_remove(source_id)
    else:
        await hass.config_entries.async_set_disabled_by(
            second.entry_id, config_entries.ConfigEntryDisabler.USER
        )
    await hass.async_block_till_done()
    assert_unavailable(await received_status(client, "unavailable"))
    state = hass.states.get(group_id)
    assert state.state == "unavailable"
    assert state.attributes["contract_version"] == 1
    assert state.attributes["board_id"] == group.entry_id
    assert state.attributes["source_count"] == 2
    assert state.attributes["unavailable_sources"]
    assert "departures" not in state.attributes
    assert "fetched_at" not in state.attributes
    assert api.call_count == 1
    if action == "disable_entity":
        registry.async_update_entity(source_id, disabled_by=None)
        await hass.async_block_till_done()
        assert (await received_status(client, "ready"))["departures"]
    await client.close()


async def test_rename_and_source_reconfigure(hass, api, payload):
    first, second = await setup_sources(hass, api, payload)
    group = await create_combined(hass, (first, second))
    registry = er.async_get(hass)
    registry.async_update_entity(
        entity_id(hass, second), new_entity_id="sensor.renamed_leaf"
    )
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_init(
        "ovapi",
        context={"source": "reconfigure", "entry_id": second.entry_id},
        data={"name": "Changed source", "stop_id": "01234567", "lines": "X1"},
    )
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    board = get_coordinator(hass).snapshot(group, entity_id(hass, group))
    assert board["status"] == "ready"
    assert len(board["departures"]) == 1
    assert second.entry_id in group.options["source_entry_ids"]
    assert entity_id(hass, second) == "sensor.renamed_leaf"
    assert api.call_count == 1


async def test_oldest_expiry_stale_and_recovery(
    hass, api, payload, freezer, hass_ws_client
):
    first, second = await setup_sources(hass, api, payload)
    group = await create_combined(hass, (first, second))
    client = await hass_ws_client(hass)
    group_id = entity_id(hass, group)
    original = await subscribe(client, group_id)
    api.clear_requests()
    # Missing source retains its old cache as stale; other source gets newer data.
    api.get("http://v0.ovapi.nl/tpc/01234567,76543210/departures", json=payload)
    await tick(hass, freezer, 121)
    stale = await received_status(client, "stale")
    assert stale["fetched_at"] == original["fetched_at"]
    assert stale["expires_at"] == original["expires_at"]
    assert api.call_count == 1
    api.clear_requests()
    api.get(
        "http://v0.ovapi.nl/tpc/01234567,76543210/departures",
        status=503,
        headers={"Retry-After": "3600"},
    )
    await tick(hass, freezer, 121)
    await tick(hass, freezer, 1497)
    assert get_coordinator(hass).snapshot(group, group_id)["status"] == "stale"
    await tick(hass, freezer, 1)
    assert_unavailable(await received_status(client, "unavailable"))
    assert hass.states.get(group_id).state == "unavailable"
    assert hass.states.get(group_id).attributes["board_id"] == group.entry_id
    assert api.call_count == 1
    await client.close()
    client = await hass_ws_client(hass)
    assert_unavailable(await subscribe(client, group_id))
    assert await hass.config_entries.async_reload(group.entry_id)
    await hass.async_block_till_done()
    assert_unavailable(get_coordinator(hass).snapshot(group, group_id))
    assert api.call_count == 1
    api.clear_requests()
    api.get(
        "http://v0.ovapi.nl/tpc/01234567,76543210/departures",
        json={"01234567": {"Passes": {}}, "76543210": {"Passes": {}}},
    )
    await tick(hass, freezer, 3601)
    ready = await received_status(client, "ready")
    assert ready["departures"] == []
    assert api.call_count == 1
    await client.close()


async def test_expiry_during_snapshot_fails_closed(
    hass, api, payload, freezer, hass_ws_client
):
    sources = await setup_sources(hass, api, payload)
    group = await create_combined(hass, sources)
    coordinator = get_coordinator(hass)
    original = coordinator._get_board
    calls = 0

    def expire_during_read(stop):
        nonlocal calls
        calls += 1
        if calls == 3:
            freezer.tick(1740)
        return original(stop)

    client = await hass_ws_client(hass)
    with patch.object(coordinator, "_get_board", side_effect=expire_during_read):
        assert_unavailable(await subscribe(client, entity_id(hass, group)))
    await client.close()


async def test_registry_churn_does_not_postpone_poll(hass, api, payload, freezer):
    sources = await setup_sources(hass, api, payload)
    group = await create_combined(hass, sources)
    registry = er.async_get(hass)
    unrelated = MockConfigEntry(domain="other", data={})
    unrelated.add_to_hass(hass)
    for index in range(4):
        await tick(hass, freezer, 30)
        entity = registry.async_get_or_create("sensor", "other", f"other{index}")
        registry.async_remove(entity.entity_id)
        hass.config_entries.async_update_entry(unrelated, title=f"Other {index}")
        hass.config_entries.async_update_entry(group, title=f"Group {index}")
        await hass.async_block_till_done()
    await tick(hass, freezer, 1)
    assert api.call_count == 2


async def test_saved_restart_order_and_cleanup(hass, api, payload, hass_ws_client):
    first = make_entry(hass, name="First")
    second = make_entry(hass, name="Second", lines="X1")
    group = saved_combined(hass, (first, second))
    coordinator = get_coordinator(hass)
    assert coordinator.stop_count == 1
    api.get("http://v0.ovapi.nl/tpc/01234567/departures", json=payload)
    assert await async_setup_component(hass, "ovapi", {})
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)
    board = await subscribe(client, entity_id(hass, group))
    assert board["status"] == "ready"
    assert len(board["departures"]) == 1
    assert api.call_count == 1
    diagnostics = await async_get_config_entry_diagnostics(hass, group)
    assert diagnostics["configured_distinct_stops"] == 1
    assert "SYNTHETIC_TRIP" not in str(diagnostics)
    assert coordinator._source_unsubs
    assert await hass.config_entries.async_unload(group.entry_id)
    await hass.async_block_till_done()
    assert_unavailable(await received_status(client, "unavailable"))
    assert coordinator._source_unsubs == []
    assert not coordinator._combined
    await client.close()
    assert len(coordinator._listeners) == 2
    assert await hass.config_entries.async_unload(first.entry_id)
    assert await hass.config_entries.async_unload(second.entry_id)
    assert not coordinator._listeners
    assert not coordinator._cache
    assert coordinator._expiry_cancel is None


async def test_combined_does_not_consume_stop_capacity(hass, api):
    sources = [make_entry(hass, stop=str(i), name=f"Leaf {i}") for i in range(10)]
    group = saved_combined(hass, sources)
    coordinator = get_coordinator(hass)
    assert coordinator.stop_count == 10
    coordinator.register(group)
    coordinator.reserve_stop("existing", "0")
    coordinator.release_stop("existing")
    with pytest.raises(ApiError, match="too_many_stops"):
        coordinator.reserve_stop("overflow", "10")
    assert api.call_count == 0
    coordinator.unregister(group)


async def test_group_options_errors_and_boundaries(hass, api, payload):
    first, second = await setup_sources(hass, api, payload)
    group = await create_combined(hass, (first, second))
    manager = hass.config_entries.options
    result = await manager.async_init(group.entry_id)
    result = await manager.async_configure(
        result["flow_id"],
        {"source_entry_ids": [first.entry_id, second.entry_id], "walking_minutes": 0.5},
    )
    assert result["errors"] == {"walking_minutes": "invalid_walk"}
    extra = [make_entry(hass, lines=f"X{i}", name=f"View {i}") for i in range(11)]
    ids = [first.entry_id, *(entry.entry_id for entry in extra)]
    form = await new_form(hass)
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"], {"name": "Twelve", "source_entry_ids": ids}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert get_coordinator(hass).stop_count == 2
    form = await new_form(hass)
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"],
        {"name": "Thirteen", "source_entry_ids": [*ids, second.entry_id]},
    )
    assert result["errors"] == {"source_entry_ids": "invalid_sources"}
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"], {"name": "Repeated", "source_entry_ids": [first.entry_id] * 2}
    )
    assert result["errors"] == {"source_entry_ids": "invalid_sources"}
    form = await manager.async_init(group.entry_id)
    result = await manager.async_configure(form["flow_id"], {"source_entry_ids": ids})
    assert result["errors"] == {"base": "already_configured"}
    assert api.call_count == 1


@pytest.mark.parametrize("change", ["removed", "nested", "foreign"])
async def test_source_changes_while_form_open(hass, api, payload, change):
    first, second = await setup_sources(hass, api, payload)
    form = await new_form(hass)
    if change == "removed":
        assert await hass.config_entries.async_remove(second.entry_id)
    elif change == "nested":
        assert await hass.config_entries.async_unload(second.entry_id)
        hass.config_entries.async_update_entry(
            second,
            data={"name": "Now a group", "entry_type": "combined"},
            options={"source_entry_ids": [first.entry_id, "missing"]},
        )
    else:
        # Persisted references must not cross integration boundaries.
        assert await hass.config_entries.async_remove(second.entry_id)
        other = MockConfigEntry(domain="other", entry_id=second.entry_id, data={})
        other.add_to_hass(hass)
    result = await hass.config_entries.flow.async_configure(
        form["flow_id"],
        {"name": "Group", "source_entry_ids": [first.entry_id, second.entry_id]},
    )
    assert result["errors"] == {"source_entry_ids": "invalid_sources"}
    assert api.call_count == 1


async def test_passive_group_cannot_start_polling(
    hass, api, payload, freezer, hass_ws_client
):
    assert await async_setup_component(hass, "homeassistant", {})
    first = make_entry(hass)
    second = make_entry(hass, lines="X1")
    registry = er.async_get(hass)
    for source in (first, second):
        registry.async_get_or_create(
            "sensor",
            "ovapi",
            source.entry_id,
            config_entry=source,
            disabled_by=er.RegistryEntryDisabler.USER,
        )
    group = saved_combined(hass, (first, second))
    api.get("http://v0.ovapi.nl/tpc/01234567/departures", json=payload)
    assert await async_setup_component(hass, "ovapi", {})
    await hass.async_block_till_done()
    client = await hass_ws_client(hass)
    assert_unavailable(await subscribe(client, entity_id(hass, group)))
    assert api.call_count == 1
    await tick(hass, freezer, 121)
    assert api.call_count == 1
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": entity_id(hass, group)},
        blocking=True,
    )
    assert api.call_count == 1
    await tick(hass, freezer, 1620)
    assert_unavailable(await received_status(client, "unavailable"))
    assert api.call_count == 1
    assert not get_coordinator(hass)._cache
    await client.close()
    assert await hass.config_entries.async_unload(group.entry_id)
    assert not get_coordinator(hass)._listeners


async def test_manual_update_keeps_leaf_behavior(hass, api, payload):
    assert await async_setup_component(hass, "homeassistant", {})
    sources = await setup_sources(hass, api, payload)
    group = await create_combined(hass, sources)
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": [entity_id(hass, sources[0]), entity_id(hass, group)]},
        blocking=True,
    )
    assert api.call_count == 1
    assert hass.states.get(entity_id(hass, group)).state == "ready"
