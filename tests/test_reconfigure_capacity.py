"""Replacing a full-capacity favourite must not destroy the working board."""

import asyncio

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import UnknownFlow
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.ovapi.client import ApiError
from custom_components.ovapi.coordinator import get_coordinator

from .test_discovery import DIRECTORY
from .test_discovery_coordinator import settle
from .test_init import make_entry

CODES = [f"{number:08d}" for number in range(10)]
TARGET = "09999999"


async def prepare(hass, api, *, loaded=False, shared=False):
    entries = [
        make_entry(hass, stop=code, name=f"Stop {code}", walking_minutes=5)
        for code in CODES
    ]
    if shared:
        make_entry(hass, stop=CODES[0], lines="X1")
    api.get(
        f"http://v0.ovapi.nl/tpc/{','.join(CODES)}/departures",
        json={code: {"Passes": {}} for code in CODES},
    )
    if loaded:
        assert await async_setup_component(hass, "ovapi", {})
        await hass.async_block_till_done()
    else:
        await get_coordinator(hass).async_refresh()
    return entries[0]


async def picker(hass, api, entry):
    api.get("http://v0.ovapi.nl/stopareacode/", json=DIRECTORY)
    api.get(
        "http://v0.ovapi.nl/stopareacode/AbC01/departures",
        json={"AbC01": {TARGET: {"Passes": {}}}},
    )
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
    await hass.config_entries.flow.async_configure(flow_id)
    await hass.config_entries.flow.async_configure(flow_id, {"query": "centraal"})
    await hass.config_entries.flow.async_configure(flow_id, {"area": "AbC01"})
    await settle()
    result = await hass.config_entries.flow.async_configure(flow_id)
    assert result["step_id"] == "point"
    return flow_id


async def test_picker_replaces_tenth_stop_preserving_identity(hass, api):
    entry = await prepare(hass, api, loaded=True)
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", "ovapi", entry.entry_id
    )
    coordinator = get_coordinator(hass)
    original = coordinator._cache[CODES[0]]
    flow_id = await picker(hass, api, entry)
    assert coordinator._cache[CODES[0]] is original
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"name": "Replacement", "stop_id": TARGET}
    )
    await hass.async_block_till_done()
    assert result.get("reason") == "reconfigure_successful"
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data["stop_id"] == TARGET
    assert entry.options["walking_minutes"] == 5
    assert (
        er.async_get(hass).async_get_entity_id("sensor", "ovapi", entry.entry_id)
        == entity_id
    )
    assert len(coordinator._cache) == coordinator.stop_count == 10
    assert CODES[0] not in coordinator._cache
    assert api.call_count == 3


@pytest.mark.parametrize("manual", [False, True])
async def test_shared_old_point_still_counts(hass, api, manual):
    entry = await prepare(hass, api, shared=True)
    coordinator = get_coordinator(hass)
    original = coordinator._cache[CODES[0]]
    if manual:
        result = await hass.config_entries.flow.async_init(
            "ovapi",
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
            data={"name": "Replacement", "stop_id": TARGET},
        )
        flow_id = result["flow_id"]
    else:
        flow_id = await picker(hass, api, entry)
        result = await hass.config_entries.flow.async_configure(
            flow_id, {"name": "Replacement", "stop_id": TARGET}
        )
    assert result["errors"]["base"] == "too_many_stops"
    assert entry.data["stop_id"] == CODES[0]
    assert coordinator._cache[CODES[0]] is original
    hass.config_entries.flow.async_abort(flow_id)


async def test_aborting_selected_replacement_preserves_old(hass, api):
    entry = await prepare(hass, api)
    coordinator = get_coordinator(hass)
    original = coordinator._cache[CODES[0]]
    flow_id = await picker(hass, api, entry)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"name": " ", "stop_id": TARGET}
    )
    assert result["errors"] == {"name": "invalid_name"}
    assert coordinator._cache[CODES[0]] is original
    assert entry.data["stop_id"] == CODES[0]
    hass.config_entries.flow.async_abort(flow_id)
    assert coordinator._cache[CODES[0]] is original
    assert TARGET not in coordinator._cache
    assert len(coordinator._cache) == 10


@pytest.mark.parametrize("status", [200, 503])
async def test_manual_reconfiguration_capacity_and_failure(hass, api, freezer, status):
    entry = await prepare(hass, api)
    coordinator = get_coordinator(hass)
    original = coordinator._cache[CODES[0]]
    replacement_codes = sorted([*CODES[1:], TARGET])
    api.get(
        f"http://v0.ovapi.nl/tpc/{','.join(replacement_codes)}/departures",
        status=status,
        json={code: {"Passes": {}} for code in replacement_codes},
    )
    freezer.tick(120)
    result = await hass.config_entries.flow.async_init(
        "ovapi",
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
        data={"name": "Manual replacement", "stop_id": TARGET},
    )
    await hass.async_block_till_done()
    if status == 200:
        assert result.get("reason") == "reconfigure_successful"
        assert entry.data["stop_id"] == TARGET
        assert coordinator.status(TARGET) == "ready"
    else:
        assert result["errors"]["base"] == "cannot_connect"
        assert entry.data["stop_id"] == CODES[0]
        assert coordinator._cache[CODES[0]] is original
        hass.config_entries.flow.async_abort(result["flow_id"])
    assert len(coordinator._cache) <= 10
    assert api.call_count == 2


async def test_reservations_cannot_double_spend_replacement_capacity(hass, api):
    entry = await prepare(hass, api)
    coordinator = get_coordinator(hass)
    other = hass.config_entries.async_entries("ovapi")[1]
    coordinator.reserve_stop("first", TARGET, entry.entry_id)
    with pytest.raises(ApiError, match="reconfigure_in_progress"):
        coordinator.reserve_stop("second", "08888888", entry.entry_id)
    with pytest.raises(ApiError, match="too_many_stops"):
        coordinator.reserve_stop("add_old", CODES[0])
    coordinator.reserve_stop("other", "08888888", other.entry_id)
    coordinator.release_stop("first")
    with pytest.raises(ApiError, match="too_many_stops"):
        coordinator.reserve_stop("add_target", TARGET)
    coordinator.release_stop("other")
    assert not coordinator._reservations
    assert len(coordinator._cache) == coordinator.stop_count == 10
    assert entry.data["stop_id"] == CODES[0]
    assert api.call_count == 1


async def test_uncommitted_shrinking_edits_do_not_free_capacity(hass, api):
    first = await prepare(hass, api)
    second = hass.config_entries.async_entries("ovapi")[1]
    coordinator = get_coordinator(hass)
    coordinator.reserve_stop("shrink", CODES[1], first.entry_id)
    with pytest.raises(ApiError, match="too_many_stops"):
        coordinator.reserve_stop("add", TARGET)
    coordinator.release_stop("shrink")
    coordinator.reserve_stop("first", TARGET, first.entry_id)
    coordinator.reserve_stop("same_target", TARGET, second.entry_id)
    with pytest.raises(ApiError, match="too_many_stops"):
        coordinator.reserve_stop("add", "08888888")
    coordinator.release_stop("first")
    coordinator.release_stop("same_target")
    assert len(coordinator._cache) == coordinator.stop_count == 10


async def test_concurrent_manual_replacements_batch_at_capacity(hass, api, freezer):
    first = await prepare(hass, api)
    second = hass.config_entries.async_entries("ovapi")[1]
    targets = [TARGET, "08888888"]
    codes = sorted([*CODES[2:], *targets])
    api.get(
        f"http://v0.ovapi.nl/tpc/{','.join(codes)}/departures",
        json={code: {"Passes": {}} for code in codes},
    )
    freezer.tick(120)
    results = await asyncio.gather(
        *(
            hass.config_entries.flow.async_init(
                "ovapi",
                context={
                    "source": config_entries.SOURCE_RECONFIGURE,
                    "entry_id": entry.entry_id,
                },
                data={"name": "Replacement", "stop_id": target},
            )
            for entry, target in zip((first, second), targets, strict=True)
        )
    )
    await hass.async_block_till_done()
    assert all(result.get("reason") == "reconfigure_successful" for result in results)
    coordinator = get_coordinator(hass)
    assert not coordinator._reservations
    assert len(coordinator._cache) == coordinator.stop_count == 10
    assert api.call_count == 2


async def test_abort_inflight_manual_replacement_cannot_restore_target(
    hass, api, freezer
):
    from pytest_homeassistant_custom_component.test_util.aiohttp import (
        AiohttpClientMockResponse,
    )

    entry = await prepare(hass, api)
    coordinator = get_coordinator(hass)
    original = coordinator._cache[CODES[0]]
    started, finish = asyncio.Event(), asyncio.Event()
    codes = sorted([*CODES[1:], TARGET])

    async def response(method, url, data):
        started.set()
        await finish.wait()
        return AiohttpClientMockResponse(
            method, url, json={code: {"Passes": {}} for code in codes}
        )

    api.get(
        f"http://v0.ovapi.nl/tpc/{','.join(codes)}/departures", side_effect=response
    )
    result = await hass.config_entries.flow.async_init(
        "ovapi",
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    flow_id = result["flow_id"]
    await hass.config_entries.flow.async_configure(flow_id, {"next_step_id": "manual"})
    freezer.tick(120)
    task = asyncio.create_task(
        hass.config_entries.flow.async_configure(
            flow_id, {"name": "Replacement", "stop_id": TARGET}
        )
    )
    await started.wait()
    hass.config_entries.flow.async_abort(flow_id)
    finish.set()
    with pytest.raises(UnknownFlow):
        await task
    assert entry.data["stop_id"] == CODES[0]
    assert coordinator._cache[CODES[0]] is original
    assert TARGET not in coordinator._cache
    assert not coordinator._reservations
    assert len(coordinator._cache) == 10
