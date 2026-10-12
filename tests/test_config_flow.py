"""Configuration via HA's public flow managers."""

import probatio
import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_validation as cv

from custom_components.ovapi.config_flow import schema

from .test_coordinator import tick
from .test_init import make_entry, setup_entry

INPUT = {"name": "Amsterdam Amstel", "stop_id": "01234567", "walking_minutes": 5}


@pytest.mark.parametrize(
    "defaults,options", [({}, False), (INPUT, False), (INPUT, True)]
)
def test_form_schema_serializes_for_frontend(defaults, options):
    fields = probatio.to_field_list(
        schema(defaults, options=options), custom_serializer=cv.custom_serializer
    )
    assert fields


async def test_user_flow(hass, api, payload):
    api.get("http://v0.ovapi.nl/tpc/01234567/departures", json=payload)
    result = await hass.config_entries.flow.async_init(
        "ovapi", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], INPUT)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {"name": "Amsterdam Amstel", "stop_id": "01234567"}
    assert result["options"]["walking_minutes"] == 5
    assert api.call_count == 1


async def test_duplicate_without_request(hass, api):
    make_entry(hass)
    result = await hass.config_entries.flow.async_init(
        "ovapi", context={"source": config_entries.SOURCE_USER}, data=INPUT
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert api.call_count == 0


async def test_invalid_stop_without_request(hass, api):
    result = await hass.config_entries.flow.async_init(
        "ovapi",
        context={"source": config_entries.SOURCE_USER},
        data={**INPUT, "stop_id": "../bad"},
    )
    assert result["errors"] == {"stop_id": "invalid_stop"}
    assert api.call_count == 0


@pytest.mark.parametrize(
    "data,errors",
    [
        ({"name": "  "}, {"name": "invalid_name"}),
        ({"walking_minutes": 2.5}, {"walking_minutes": "invalid_walk"}),
        ({"walking_minutes": -1}, {"walking_minutes": "invalid_walk"}),
        ({"walking_minutes": 121}, {"walking_minutes": "invalid_walk"}),
        ({"walking_minutes": "x"}, {"walking_minutes": "invalid_walk"}),
        ({"walking_minutes": True}, {"walking_minutes": "invalid_walk"}),
    ],
)
async def test_invalid_input(hass, api, data, errors):
    result = await hass.config_entries.flow.async_init(
        "ovapi", context={"source": config_entries.SOURCE_USER}, data={**INPUT, **data}
    )
    assert result["errors"] == errors
    assert api.call_count == 0


async def test_options_invalid_walk(hass):
    entry = make_entry(hass)
    result = await hass.config_entries.options.async_init(
        entry.entry_id, data={"walking_minutes": 1.5}
    )
    assert result["errors"] == {"walking_minutes": "invalid_walk"}


@pytest.mark.parametrize(
    "status,error",
    [(503, "cannot_connect"), (404, "unknown_stop"), (429, "rate_limited")],
)
async def test_errors(hass, api, status, error):
    api.get("http://v0.ovapi.nl/tpc/01234567/departures", status=status)
    result = await hass.config_entries.flow.async_init(
        "ovapi", context={"source": config_entries.SOURCE_USER}, data=INPUT
    )
    assert result["errors"] == {"base": error}
    assert api.call_count == 1


async def test_options(hass):
    entry = make_entry(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"lines": " X1 ", "walking_minutes": 7}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["lines"] == "X1"
    assert entry.options["walking_minutes"] == 7


async def test_options_duplicate(hass):
    first = make_entry(hass)
    second = make_entry(hass, lines="X1")
    result = await hass.config_entries.options.async_init(second.entry_id, data={})
    assert result["errors"] == {"base": "already_configured"}
    assert first.unique_id != second.unique_id


async def test_reconfigure(hass, api, payload):
    entry = make_entry(hass)
    api.get(
        "http://v0.ovapi.nl/tpc/76543210/departures", json={"76543210": {"Passes": {}}}
    )
    # Validation also batches the existing configured stop.
    api.get(
        "http://v0.ovapi.nl/tpc/01234567,76543210/departures",
        json={**payload, "76543210": {"Passes": {}}},
    )
    result = await hass.config_entries.flow.async_init(
        "ovapi",
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**INPUT, "stop_id": "76543210", "name": "Centraal"}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data["stop_id"] == "76543210"
    assert entry.title == "Centraal"


async def test_reconfigure_loaded_to_cached_target(hass, api, payload, freezer):
    freezer.move_to("2030-01-15T12:00:00+00:00")
    entry = await setup_entry(hass, api, payload)
    original_coordinator = entry.runtime_data
    # After the request floor, validate target in the same batch as the old stop.
    freezer.tick(121)
    api.get(
        "http://v0.ovapi.nl/tpc/01234567,76543210/departures",
        json={**payload, "76543210": {"Passes": {}}},
    )
    result = await hass.config_entries.flow.async_init(
        "ovapi",
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
        data={**INPUT, "stop_id": "76543210"},
    )
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data is original_coordinator
    assert api.call_count == 2
    assert original_coordinator.status("01234567") == "unavailable"
    assert original_coordinator.status("76543210") == "ready"


async def test_reload_preserves_floor_not_source(hass, api, payload, freezer):
    freezer.move_to("2030-01-15T12:00:00+00:00")
    entry = await setup_entry(hass, api, payload)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert api.call_count == 1
    await tick(hass, freezer, 121)
    assert entry.state is ConfigEntryState.LOADED
    assert api.call_count == 2
