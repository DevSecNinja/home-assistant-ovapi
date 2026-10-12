"""Fake-time proofs of actual shared request counts and retention."""

import asyncio
import copy
import time
from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMockResponse,
)

from custom_components.ovapi.client import ApiError
from custom_components.ovapi.coordinator import get_coordinator

from .test_init import make_entry, setup_entry


async def tick(hass, freezer, seconds):
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass, dt_util.utcnow())
    await hass.async_block_till_done()


async def test_concurrent_setup_batches(hass, api, payload, freezer):
    freezer.move_to("2030-01-15T12:00:00+00:00")
    first = make_entry(hass)
    second = make_entry(hass, stop="76543210", name="Amsterdam Centraal")
    payload["76543210"] = {"Passes": {}}
    api.get("http://v0.ovapi.nl/tpc/01234567,76543210/departures", json=payload)
    assert all(
        await asyncio.gather(
            hass.config_entries.async_setup(first.entry_id),
            hass.config_entries.async_setup(second.entry_id),
        )
    )
    await hass.async_block_till_done()
    assert api.call_count == 1
    assert first.runtime_data is second.runtime_data
    for _ in range(10):
        await first.runtime_data.async_validate("01234567")
    assert api.call_count == 1
    await tick(hass, freezer, 119)
    assert api.call_count == 1
    await tick(hass, freezer, 2)
    assert api.call_count == 2


async def test_backoff_expiry_and_recovery(hass, api, payload, freezer):
    freezer.move_to("2030-01-15T12:00:00+00:00")
    entry = await setup_entry(hass, api, payload)
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", "ovapi", entry.entry_id
    )
    original = entry.runtime_data.snapshot(entry, entity_id)
    api.clear_requests()
    api.get(
        "http://v0.ovapi.nl/tpc/01234567/departures",
        status=429,
        headers={"Retry-After": "3600"},
    )
    await tick(hass, freezer, 121)
    assert api.call_count == 1
    assert hass.states.get(entity_id).state == "stale"
    stale = entry.runtime_data.snapshot(entry, entity_id)
    assert stale["expires_at"] == original["expires_at"]
    await tick(hass, freezer, 120)
    assert api.call_count == 1
    await tick(hass, freezer, 1500)
    assert api.call_count == 1
    assert hass.states.get(entity_id).state == "unavailable"
    expired = entry.runtime_data.snapshot(entry, entity_id)
    assert expired["departures"] == []
    assert expired["expires_at"] is None
    api.clear_requests()
    api.get(
        "http://v0.ovapi.nl/tpc/01234567/departures", json={"01234567": {"Passes": {}}}
    )
    await tick(hass, freezer, 3601)
    assert api.call_count == 1
    assert hass.states.get(entity_id).state == "ready"


async def test_concurrent_validation(hass, api, payload, freezer):
    freezer.move_to("2030-01-15T12:00:00+00:00")
    payload["76543210"] = {"Passes": {}}
    api.get("http://v0.ovapi.nl/tpc/01234567,76543210/departures", json=payload)
    coordinator = get_coordinator(hass)
    await asyncio.gather(
        coordinator.async_validate("01234567"),
        coordinator.async_validate("76543210"),
    )
    assert api.call_count == 1
    assert coordinator.status("01234567") == "ready"
    await tick(hass, freezer, 1740)
    assert coordinator.status("01234567") == "unavailable"
    assert api.call_count == 1


async def test_distinct_stop_cap(hass, api):
    for index in range(10):
        make_entry(hass, stop=str(index), name=f"Stop {index}")
    with pytest.raises(ApiError, match="too_many_stops"):
        await get_coordinator(hass).async_validate("11")
    assert api.call_count == 0


async def test_partial_batch_and_unknown_stop(hass, api, payload, freezer):
    freezer.move_to("2030-01-15T12:00:00+00:00")
    entry = await setup_entry(hass, api, payload)
    coordinator = entry.runtime_data
    api.clear_requests()
    api.get("http://v0.ovapi.nl/tpc/01234567/departures", json={})
    await tick(hass, freezer, 121)
    assert coordinator.status("01234567") == "stale"
    assert api.call_count == 1
    # Missing data for a new stop cannot become a fabricated empty board.
    await tick(hass, freezer, 120)
    with pytest.raises(ApiError, match="unknown_stop"):
        await coordinator.async_validate("76543210")
    assert api.call_count == 2


async def test_unload_during_fetch_does_not_repopulate(hass, api, payload, freezer):
    freezer.move_to("2030-01-15T12:00:00+00:00")
    entry = await setup_entry(hass, api, payload)
    coordinator = entry.runtime_data
    entered = asyncio.Event()
    release = asyncio.Event()

    async def response(method, url, data):
        entered.set()
        await release.wait()
        return AiohttpClientMockResponse(method, url, json=payload)

    api.clear_requests()
    api.get("http://v0.ovapi.nl/tpc/01234567/departures", side_effect=response)
    freezer.tick(timedelta(seconds=121))
    refresh = asyncio.create_task(coordinator.async_request_refresh())
    await entered.wait()
    assert await hass.config_entries.async_unload(entry.entry_id)
    release.set()
    await refresh
    assert coordinator.status("01234567") == "unavailable"
    assert api.call_count == 1


async def test_shutdown_cancels_inflight_and_expiry(hass, api, payload):
    coordinator = get_coordinator(hass)
    api.get("http://v0.ovapi.nl/tpc/01234567/departures", json=payload)
    await coordinator.async_validate("01234567")
    assert coordinator.status("01234567") == "ready"
    await coordinator.async_shutdown()
    assert coordinator.status("01234567") == "unavailable"

    entered = asyncio.Event()

    async def blocked(method, url, data):
        entered.set()
        await asyncio.Future()

    other = make_entry(hass, stop="76543210")
    coordinator.register(other)
    api.get("http://v0.ovapi.nl/tpc/76543210/departures", side_effect=blocked)
    # A fresh coordinator here models an independent HA instance, not a reload.
    from custom_components.ovapi.coordinator import OvapiCoordinator

    fresh = OvapiCoordinator(hass)
    task = asyncio.create_task(fresh.async_validate("76543210"))
    await entered.wait()
    await fresh.async_shutdown()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_shared_stop_unload_preserves_other_favourite(
    hass, api, payload, freezer
):
    freezer.move_to("2030-01-15T12:00:00+00:00")
    first = await setup_entry(hass, api, payload)
    second = make_entry(hass, lines="X1")
    assert await hass.config_entries.async_setup(second.entry_id)
    coordinator = first.runtime_data
    assert api.call_count == 1
    assert await hass.config_entries.async_unload(first.entry_id)
    assert coordinator.status("01234567") == "ready"
    await tick(hass, freezer, 121)
    assert api.call_count == 2


async def test_wall_clock_rollback_does_not_extend_expiry(hass, api, payload, freezer):
    freezer.move_to("2030-01-15T12:00:00+00:00")
    entry = await setup_entry(hass, api, payload)
    monotonic = time.monotonic()
    coordinator = entry.runtime_data
    fetched = coordinator.snapshot(entry, "sensor.test")
    freezer.move_to("2030-01-15T11:00:00+00:00")
    with patch(
        "custom_components.ovapi.coordinator.time.monotonic",
        return_value=monotonic + 1740,
    ):
        expired = coordinator.snapshot(entry, "sensor.test")
    assert fetched["expires_at"] == "2030-01-15T12:29:00+00:00"
    assert expired["status"] == "unavailable"
    assert expired["departures"] == []
    assert api.call_count == 1


async def test_filtering_and_display_cap(hass, api, payload, freezer):
    freezer.move_to("2030-01-15T12:00:00+00:00")
    record = payload["01234567"]["Passes"]["SYNTHETIC_TRIP"]
    payload["01234567"]["Passes"] = {
        f"SYNTHETIC_{index}": copy.deepcopy(record) for index in range(45)
    }
    entry = await setup_entry(
        hass, api, payload, lines=" x1, X1 ", destination="DESTINATION"
    )
    coordinator = entry.runtime_data
    assert len(coordinator.snapshot(entry, "sensor.test")["departures"]) == 30
    hass.config_entries.async_update_entry(entry, options={"lines": "X2"})
    await hass.async_block_till_done()
    assert coordinator.snapshot(entry, "sensor.test")["departures"] == []
    hass.config_entries.async_update_entry(
        entry, options={"destination": "not present"}
    )
    await hass.async_block_till_done()
    assert coordinator.snapshot(entry, "sensor.test")["departures"] == []
    assert api.call_count == 1


async def test_retry_after_starts_at_response_receipt(hass, api, payload, freezer):
    freezer.move_to("2030-01-15T12:00:00+00:00")
    entry = await setup_entry(hass, api, payload)
    coordinator = entry.runtime_data
    api.clear_requests()

    async def slow_limit(method, url, data):
        freezer.tick(19)
        return AiohttpClientMockResponse(
            method, url, status=429, headers={"Retry-After": "600"}
        )

    api.get("http://v0.ovapi.nl/tpc/01234567/departures", side_effect=slow_limit)
    freezer.tick(121)
    await coordinator.async_refresh()
    assert api.call_count == 1
    freezer.tick(599)
    await coordinator.async_refresh()
    assert api.call_count == 1
    freezer.tick(2)
    await coordinator.async_refresh()
    assert api.call_count == 2
