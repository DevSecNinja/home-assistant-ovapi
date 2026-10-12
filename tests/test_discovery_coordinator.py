"""Actual shared HTTP request counts under synthetic time."""

import asyncio
import time
from unittest.mock import patch

import pytest

from custom_components.ovapi.client import ApiError
from custom_components.ovapi.coordinator import get_coordinator
from custom_components.ovapi.discovery import MAX_LOOKUPS

from .test_coordinator import tick
from .test_discovery import DIRECTORY
from .test_init import make_entry


async def settle():
    for _ in range(12):
        await asyncio.sleep(0)


async def test_shared_directory_area_seed(hass, api, payload, freezer):
    freezer.move_to("2030-01-15T12:00:00+00:00")
    api.get("http://v0.ovapi.nl/stopareacode/", json=DIRECTORY)
    api.get("http://v0.ovapi.nl/stopareacode/AbC01/departures", json={"AbC01": payload})
    coordinator = get_coordinator(hass)
    await asyncio.gather(coordinator.async_lookup(""), coordinator.async_lookup(""))
    assert api.call_count == 1
    task = asyncio.create_task(coordinator.async_lookup("AbC01"))
    await settle()
    assert task.done()
    await task
    assert api.call_count == 2
    lookup = coordinator.lookup("AbC01")
    coordinator.select_point("AbC01", "01234567")
    await coordinator.async_validate("01234567")
    assert api.call_count == 2
    assert coordinator._cache["01234567"].expires_at == lookup.expires_at
    api.get("http://v0.ovapi.nl/stopareacode/Next/departures", json={"Next": {}})
    third = asyncio.create_task(coordinator.async_lookup("Next"))
    await settle()
    assert not third.done()
    await tick(hass, freezer, 119)
    assert api.call_count == 2
    await tick(hass, freezer, 1)
    await settle()
    assert third.done()
    await third
    assert api.call_count == 3


async def test_cancel_last_waiter(hass, api):
    api.get("http://v0.ovapi.nl/stopareacode/", json=DIRECTORY)
    coordinator = get_coordinator(hass)
    await coordinator.async_lookup("")
    api.get("http://v0.ovapi.nl/stopareacode/Initial/departures", json={"Initial": {}})
    await coordinator.async_lookup("Initial")
    task = asyncio.create_task(coordinator.async_lookup("AbC01"))
    await settle()
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await settle()
    assert not coordinator._lookup_tasks
    assert api.call_count == 2


async def test_lookup_expiry_replay_and_rollback(hass, api, freezer):
    api.get("http://v0.ovapi.nl/stopareacode/", json=DIRECTORY)
    coordinator = get_coordinator(hass)
    await coordinator.async_lookup("")
    old = coordinator.lookup("")
    original = old.expires_at
    await tick(hass, freezer, 100)
    await coordinator.async_lookup("")
    assert coordinator.lookup("").expires_at == original
    assert api.call_count == 1
    await tick(hass, freezer, 1640)
    assert coordinator.lookup("") is None
    assert old.areas == ()
    await coordinator.async_lookup("")
    result = coordinator.lookup("")
    with patch(
        "custom_components.ovapi.coordinator.time.monotonic",
        return_value=result.monotonic_expiry,
    ):
        assert coordinator.lookup("") is None
    assert result.areas == ()


async def test_polling_fairness(hass, api, payload, freezer):
    make_entry(hass)
    api.get("http://v0.ovapi.nl/stopareacode/", json=DIRECTORY)
    api.get("http://v0.ovapi.nl/tpc/01234567/departures", json=payload)
    api.get("http://v0.ovapi.nl/stopareacode/AbC01/departures", json={"AbC01": payload})
    coordinator = get_coordinator(hass)
    await coordinator.async_lookup("")
    await coordinator.async_lookup("AbC01")
    assert api.call_count == 2
    api.get("http://v0.ovapi.nl/stopareacode/Next/departures", json={"Next": {}})
    task = asyncio.create_task(coordinator.async_lookup("Next"))
    await settle()
    await coordinator.async_refresh()
    assert api.call_count == 2
    await tick(hass, freezer, 120)
    await settle()
    assert api.call_count == 4
    assert str(api.mock_calls[2][1]).endswith("/tpc/01234567/departures")
    assert task.done()
    await task
    assert api.call_count == 4


async def test_lookup_backoff_shared_with_polling(hass, api, freezer):
    make_entry(hass)
    api.get(
        "http://v0.ovapi.nl/stopareacode/", status=429, headers={"Retry-After": "600"}
    )
    coordinator = get_coordinator(hass)
    with pytest.raises(ApiError, match="rate_limited"):
        await coordinator.async_lookup("")
    assert coordinator._next_request == time.monotonic() + 600
    await coordinator.async_refresh()
    assert api.call_count == 1
    await tick(hass, freezer, 599)
    await coordinator.async_refresh()
    assert api.call_count == 1


async def test_same_key_waiter_cancellation_and_queue_limit(hass, api, freezer):
    api.get("http://v0.ovapi.nl/stopareacode/", json=DIRECTORY)
    api.get("http://v0.ovapi.nl/stopareacode/AbC01/departures", json={"AbC01": {}})
    coordinator = get_coordinator(hass)
    await coordinator.async_lookup("")
    api.get("http://v0.ovapi.nl/stopareacode/Initial/departures", json={"Initial": {}})
    await coordinator.async_lookup("Initial")
    first = asyncio.create_task(coordinator.async_lookup("AbC01"))
    second = asyncio.create_task(coordinator.async_lookup("AbC01"))
    await settle()
    first.cancel()
    await asyncio.gather(first, return_exceptions=True)
    assert not second.done()
    await tick(hass, freezer, 120)
    await settle()
    await second
    assert api.call_count == 3
    api.get("http://v0.ovapi.nl/stopareacode/Ready/departures", json={"Ready": {}})
    await coordinator.async_lookup("Ready")
    tasks = [
        asyncio.create_task(coordinator.async_lookup(f"A{i}"))
        for i in range(MAX_LOOKUPS)
    ]
    await settle()
    with pytest.raises(ApiError, match="discovery_busy"):
        await coordinator.async_lookup("overflow")
    await coordinator.async_shutdown()
    await asyncio.gather(*tasks, return_exceptions=True)
    assert not coordinator._lookup_tasks


async def test_cold_pair_after_recent_board_poll(hass, api, payload, freezer):
    make_entry(hass)
    api.get("http://v0.ovapi.nl/tpc/01234567/departures", json=payload)
    api.get("http://v0.ovapi.nl/stopareacode/", json=DIRECTORY)
    api.get("http://v0.ovapi.nl/stopareacode/AbC01/departures", json={"AbC01": payload})
    coordinator = get_coordinator(hass)
    await coordinator.async_refresh()
    await coordinator.async_lookup("")
    await coordinator.async_lookup("AbC01")
    assert api.call_count == 3
    coordinator.select_point("AbC01", "01234567")
    await coordinator.async_validate("01234567")
    await coordinator.async_refresh()
    assert api.call_count == 3
    await tick(hass, freezer, 119)
    await coordinator.async_refresh()
    assert api.call_count == 3
    await tick(hass, freezer, 1)
    await coordinator.async_refresh()
    assert api.call_count == 4


async def test_shared_response_relative_backoff_blocks_interactive_pair(
    hass, api, freezer
):
    from pytest_homeassistant_custom_component.test_util.aiohttp import (
        AiohttpClientMockResponse,
    )

    async def slow_limit(method, url, data):
        freezer.tick(19)
        return AiohttpClientMockResponse(
            method, url, status=429, headers={"Retry-After": "600"}
        )

    api.get("http://v0.ovapi.nl/stopareacode/", side_effect=slow_limit)
    coordinator = get_coordinator(hass)
    with pytest.raises(ApiError, match="rate_limited"):
        await coordinator.async_lookup("")
    assert coordinator._backoff_until == time.monotonic() + 600
    api.clear_requests()
    api.get("http://v0.ovapi.nl/stopareacode/", json=DIRECTORY)
    task = asyncio.create_task(coordinator.async_lookup(""))
    await settle()
    await tick(hass, freezer, 599)
    assert api.call_count == 0
    await tick(hass, freezer, 1)
    await settle()
    assert task.done()
    await task
    assert api.call_count == 1


async def test_rolling_allowance_not_fixed_window(hass, api, freezer):
    coordinator = get_coordinator(hass)
    for key in ("A", "B", "C", "D"):
        api.get(f"http://v0.ovapi.nl/stopareacode/{key}/departures", json={key: {}})
    await coordinator.async_lookup("A")
    await tick(hass, freezer, 20)
    await coordinator.async_lookup("B")
    third = asyncio.create_task(coordinator.async_lookup("C"))
    fourth = asyncio.create_task(coordinator.async_lookup("D"))
    await settle()
    await tick(hass, freezer, 99)
    assert api.call_count == 2
    await tick(hass, freezer, 1)
    await settle()
    assert third.done() and not fourth.done()
    assert api.call_count == 3
    await tick(hass, freezer, 19)
    assert api.call_count == 3
    await tick(hass, freezer, 1)
    await settle()
    await asyncio.gather(third, fourth)
    assert api.call_count == 4


async def test_cache_eviction_and_cancel_do_not_reset_allowance(hass, api):
    api.get("http://v0.ovapi.nl/stopareacode/", json=DIRECTORY)
    api.get("http://v0.ovapi.nl/stopareacode/A/departures", json={"A": {}})
    coordinator = get_coordinator(hass)
    await coordinator.async_lookup("")
    await coordinator.async_lookup("A")
    starts = list(coordinator._lookup_starts)
    coordinator.discard_lookup("")
    assert get_coordinator(hass) is coordinator
    for _ in range(2):
        task = asyncio.create_task(coordinator.async_lookup(""))
        await settle()
        assert not task.done()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert list(coordinator._lookup_starts) == starts
    assert api.call_count == 2


async def test_board_failure_blocks_unused_interactive_allowance(hass, api, freezer):
    make_entry(hass)
    api.get(
        "http://v0.ovapi.nl/tpc/01234567/departures",
        status=429,
        headers={"Retry-After": "600"},
    )
    api.get("http://v0.ovapi.nl/stopareacode/", json=DIRECTORY)
    coordinator = get_coordinator(hass)
    await coordinator.async_refresh()
    task = asyncio.create_task(coordinator.async_lookup(""))
    await settle()
    await tick(hass, freezer, 599)
    assert api.call_count == 1
    await tick(hass, freezer, 1)
    await settle()
    await task
    assert api.call_count == 2


async def test_lookup_eviction_and_selection_validation(hass, api, payload, freezer):
    api.get("http://v0.ovapi.nl/stopareacode/", json=DIRECTORY)
    coordinator = get_coordinator(hass)
    await coordinator.async_lookup("")
    directory = coordinator.lookup("")
    for i in range(MAX_LOOKUPS):
        key = f"A{i}"
        api.get(
            f"http://v0.ovapi.nl/stopareacode/{key}/departures", json={key: payload}
        )
        await tick(hass, freezer, 120)
        await coordinator.async_lookup(key)
    assert len(coordinator._lookups) == MAX_LOOKUPS
    assert directory.areas == ()
    with pytest.raises(ApiError, match="selection_expired"):
        coordinator.select_point("missing", "01234567")
    with pytest.raises(ApiError, match="selection_expired"):
        coordinator.select_point("A9", "999")
    coordinator.select_point("A9", "01234567")
    board = coordinator._cache["01234567"]
    coordinator.select_point("A9", "01234567")
    assert coordinator._cache["01234567"] is board
    coordinator.entries = {str(i): str(i) for i in range(10)}
    with pytest.raises(ApiError, match="too_many_stops"):
        coordinator.select_point("A9", "01234567")
    coordinator.entries.clear()
    coordinator._cache = {str(i): board for i in range(10)}
    coordinator.select_point("A9", "01234567")
    assert len(coordinator._cache) == 10
    coordinator.discard_lookup("A9")
    coordinator.discard_lookup("missing")
    assert coordinator.lookup("A9") is None
