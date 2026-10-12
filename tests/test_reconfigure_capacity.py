"""Replacing a full-capacity favourite must not destroy the working board."""

import asyncio

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from custom_components.ovapi.client import ApiError
from custom_components.ovapi.coordinator import get_coordinator

from .test_config_flow import finish_progress
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
    result = await finish_progress(hass, result)
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


@pytest.mark.parametrize("add_first", [False, True])
async def test_same_target_add_cannot_borrow_replacement_slot(hass, api, add_first):
    entry = await prepare(hass, api)
    coordinator = get_coordinator(hass)
    if add_first:
        with pytest.raises(ApiError, match="too_many_stops"):
            coordinator.reserve_stop("add", TARGET)
    coordinator.reserve_stop("replace", TARGET, entry.entry_id)
    with pytest.raises(ApiError, match="too_many_stops"):
        coordinator.reserve_stop("add", TARGET)
    coordinator.release_stop("replace")
    assert not coordinator._reservations
    assert coordinator.stop_count == 10


@pytest.mark.parametrize("expire", [False, True])
async def test_same_target_add_after_aborted_picker_keeps_ten_stops(
    hass, api, freezer, expire
):
    from .test_coordinator import tick

    entry = await prepare(hass, api)
    coordinator = get_coordinator(hass)
    original = coordinator._cache[CODES[0]]
    flow_id = await picker(hass, api, entry)
    result = await hass.config_entries.flow.async_configure(
        flow_id, {"name": " ", "stop_id": TARGET}
    )
    assert result["errors"] == {"name": "invalid_name"}
    add_result = await hass.config_entries.flow.async_init(
        "ovapi",
        context={"source": config_entries.SOURCE_USER},
        data={"name": "Concurrent add", "stop_id": TARGET},
    )
    assert add_result["errors"]["base"] == "too_many_stops"
    if expire:
        await tick(hass, freezer, 1740)
    else:
        hass.config_entries.flow.async_abort(flow_id)
        assert coordinator._cache[CODES[0]] is original
    assert TARGET not in coordinator._cache
    assert (
        coordinator.stop_count == len(hass.config_entries.async_entries("ovapi")) == 10
    )
    hass.config_entries.flow.async_abort(add_result["flow_id"])
    if expire:
        hass.config_entries.flow.async_abort(flow_id)
    assert not coordinator._reservations
    assert api.call_count == 3


async def test_same_target_shared_old_claim_cannot_borrow_credit(hass, api):
    entry = await prepare(hass, api)
    other = hass.config_entries.async_entries("ovapi")[1]
    make_entry(hass, stop=other.data["stop_id"], lines="X1")
    coordinator = get_coordinator(hass)
    coordinator.reserve_stop("unique", TARGET, entry.entry_id)
    with pytest.raises(ApiError, match="too_many_stops"):
        coordinator.reserve_stop("shared", TARGET, other.entry_id)
    coordinator.release_stop("unique")
    assert not coordinator._reservations


@pytest.mark.parametrize("add_first", [False, True])
async def test_same_target_with_real_spare_capacity_survives_abort(
    hass, api, add_first
):
    entries = [make_entry(hass, stop=code) for code in CODES[:9]]
    coordinator = get_coordinator(hass)
    if add_first:
        coordinator.reserve_stop("add", TARGET)
    coordinator.reserve_stop("replace", TARGET, entries[0].entry_id)
    if not add_first:
        coordinator.reserve_stop("add", TARGET)
    with pytest.raises(ApiError, match="too_many_stops"):
        coordinator.reserve_stop("another_add", "08888888")
    coordinator.release_stop("replace")
    coordinator.reserve_stop("add", TARGET)
    coordinator.release_stop("add")
    assert not coordinator._reservations
    assert coordinator.stop_count == 9


async def test_concurrent_manual_replacements_batch_at_capacity(hass, api, freezer):
    first = await prepare(hass, api)
    second = hass.config_entries.async_entries("ovapi")[1]
    targets = [TARGET, "08888888"]
    codes = sorted([*CODES[2:], *targets])
    api.get(
        f"http://v0.ovapi.nl/tpc/{','.join(codes)}/departures",
        json={code: {"Passes": {}} for code in codes},
    )
    flows = []
    for entry in (first, second):
        result = await hass.config_entries.flow.async_init(
            "ovapi",
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "manual"}
        )
        flows.append(result["flow_id"])
    freezer.tick(120)
    results = await asyncio.gather(
        *(
            hass.config_entries.flow.async_configure(
                flow_id, {"name": "Replacement", "stop_id": target}
            )
            for flow_id, target in zip(flows, targets, strict=True)
        )
    )
    results = await asyncio.gather(
        *(finish_progress(hass, result) for result in results)
    )
    await hass.async_block_till_done()
    assert all(result.get("reason") == "reconfigure_successful" for result in results)
    coordinator = get_coordinator(hass)
    assert not coordinator._reservations
    assert len(coordinator._cache) == coordinator.stop_count == 10
    assert api.call_count == 2


@pytest.mark.parametrize("abort", [False, True])
async def test_abort_inflight_manual_replacement_cannot_restore_target(
    hass, api, freezer, abort
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
            method,
            url,
            status=200 if abort else 503,
            json={code: {"Passes": {}} for code in codes},
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
    with pytest.raises(ApiError, match="too_many_stops"):
        coordinator.reserve_stop("concurrent_add", TARGET)
    if abort:
        hass.config_entries.flow.async_abort(flow_id)
    finish.set()
    progress = await task
    if abort:
        assert progress["type"] is FlowResultType.SHOW_PROGRESS
    else:
        assert (await finish_progress(hass, progress))["errors"][
            "base"
        ] == "cannot_connect"
        hass.config_entries.flow.async_abort(flow_id)
    await settle()
    assert entry.data["stop_id"] == CODES[0]
    assert coordinator._cache[CODES[0]] is original
    assert TARGET not in coordinator._cache
    assert not coordinator._reservations
    assert len(coordinator._cache) == 10
