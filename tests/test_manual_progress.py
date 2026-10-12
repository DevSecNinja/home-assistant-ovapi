"""Manual setup waits through the same bounded allowance as stop discovery."""

import asyncio
from datetime import timedelta

import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMockResponse,
)

from custom_components.ovapi.client import ApiError
from custom_components.ovapi.coordinator import get_coordinator

from .test_config_flow import finish_progress
from .test_coordinator import tick
from .test_discovery import DIRECTORY
from .test_discovery_coordinator import settle

pytestmark = pytest.mark.freeze_time("2030-01-15T12:00:00+00:00")


def route(api, *codes, status=200, headers=None):
    api.get(
        f"http://v0.ovapi.nl/tpc/{','.join(sorted(codes))}/departures",
        json={code: {"Passes": {}} for code in codes},
        status=status,
        headers=headers,
    )


async def begin(hass, code, **options):
    return await hass.config_entries.flow.async_init(
        "ovapi",
        context={"source": config_entries.SOURCE_USER},
        data={"name": f"Board {code}", "stop_id": code, **options},
    )


async def test_third_manual_waits_and_preserves_every_field(hass, api, freezer):
    route(api, "001")
    first = await finish_progress(hass, await begin(hass, "001"))
    route(api, "001", "002")
    await finish_progress(hass, await begin(hass, "002"))
    route(api, "001", "002", "003")
    third = await begin(
        hass,
        "003",
        transport_types=["metro"],
        lines="",
        destination="North",
        walking_minutes=8,
    )
    assert third["progress_action"] == "budget_wait"
    assert third["description_placeholders"]["resume_at"] == dt_util.as_local(
        dt_util.utcnow() + timedelta(seconds=120)
    ).strftime("%Y-%m-%d %H:%M:%S")
    await settle()
    assert api.call_count == 2
    await tick(hass, freezer, 119)
    assert api.call_count == 2
    # An options change is local even while another setup is waiting.
    options = await hass.config_entries.options.async_init(
        first["result"].entry_id, data={"walking_minutes": 3}
    )
    assert options["type"] is FlowResultType.CREATE_ENTRY
    assert api.call_count == 2
    await tick(hass, freezer, 1)
    third = await finish_progress(hass, third)
    assert third["data"] == {"name": "Board 003", "stop_id": "003"}
    assert third["options"] == {
        "transport_types": ["metro"],
        "lines": "",
        "destination": "North",
        "walking_minutes": 8,
    }
    assert api.call_count == 3
    assert not get_coordinator(hass)._reservations


async def test_cached_manual_and_reopened_flow_do_not_reset_budget(hass, api):
    route(api, "001")
    await finish_progress(hass, await begin(hass, "001"))
    route(api, "001", "002")
    await finish_progress(hass, await begin(hass, "002"))
    cached = await begin(hass, "001", lines="X1")
    assert cached["type"] is FlowResultType.CREATE_ENTRY
    assert api.call_count == 2
    coordinator = get_coordinator(hass)
    starts = tuple(coordinator._lookup_starts)
    for _ in range(2):
        pending = await begin(hass, "003")
        await settle()
        flow = hass.config_entries.flow._progress[pending["flow_id"]]
        hass.config_entries.flow.async_abort(pending["flow_id"])
        await settle()
        assert flow._manual_input is None
        assert coordinator._validation_task is None
        assert not coordinator._pending
        assert not coordinator._reservations
        assert tuple(coordinator._lookup_starts) == starts
    assert api.call_count == 2


async def test_manual_and_search_share_one_allowance(hass, api, freezer):
    coordinator = get_coordinator(hass)
    api.get("http://v0.ovapi.nl/stopareacode/", json=DIRECTORY)
    await coordinator.async_lookup("")
    route(api, "001")
    await finish_progress(hass, await begin(hass, "001"))
    api.get("http://v0.ovapi.nl/stopareacode/Next/departures", json={"Next": {}})
    task = asyncio.create_task(coordinator.async_lookup("Next"))
    await settle()
    assert api.call_count == 2
    await tick(hass, freezer, 119)
    assert not task.done()
    await tick(hass, freezer, 1)
    await settle()
    await task
    assert api.call_count == 4  # One fair background batch, then area discovery.
    assert str(api.mock_calls[-1][1]).endswith("/stopareacode/Next/departures")


@pytest.mark.parametrize("pause", [600, 90000])
async def test_server_pause_uses_actual_deadline_without_repeat_loop(
    hass, api, freezer, pause
):
    route(api, "001", status=429, headers={"Retry-After": str(pause)})
    result = await finish_progress(hass, await begin(hass, "001", walking_minutes=9))
    assert result["errors"] == {"base": "rate_limited"}
    coordinator = get_coordinator(hass)
    deadline = dt_util.utcnow() + timedelta(seconds=pause)
    await tick(hass, freezer, 90)
    assert api.call_count == 1  # Failure does not automatically repeat a request.
    api.clear_requests()
    route(api, "001")
    waiting = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Board 001", "stop_id": "001", "walking_minutes": 9}
    )
    assert waiting["progress_action"] == "server_pause"
    assert coordinator.lookup_wait() == ("server_pause", deadline)
    assert waiting["description_placeholders"]["resume_at"] == dt_util.as_local(
        deadline
    ).strftime("%Y-%m-%d %H:%M:%S")
    await settle()
    await tick(hass, freezer, pause - 91)
    assert api.call_count == 0
    await tick(hass, freezer, 1)
    complete = await finish_progress(hass, waiting)
    assert complete["options"]["walking_minutes"] == 9
    assert api.call_count == 1


async def test_late_joining_manual_waits_for_its_own_batch(hass, api, freezer):
    coordinator = get_coordinator(hass)
    api.get("http://v0.ovapi.nl/stopareacode/", json=DIRECTORY)
    await coordinator.async_lookup("")
    started, finish = asyncio.Event(), asyncio.Event()

    async def response(method, url, data):
        started.set()
        await finish.wait()
        return AiohttpClientMockResponse(method, url, json={"001": {"Passes": {}}})

    api.get("http://v0.ovapi.nl/tpc/001/departures", side_effect=response)
    first = await begin(hass, "001")
    await started.wait()
    late = await begin(hass, "002")
    await settle()
    assert api.call_count == 2
    route(api, "001", "002")
    finish.set()
    await finish_progress(hass, first)
    await settle()
    assert coordinator.status("001") == "ready"
    assert coordinator.status("002") == "unavailable"
    assert api.call_count == 2
    await tick(hass, freezer, 120)
    completed = await finish_progress(hass, late)
    assert completed["data"]["stop_id"] == "002"
    assert api.call_count == 3
    assert not coordinator._pending_counts


async def test_cancelling_one_validation_waiter_keeps_shared_work(hass, api, freezer):
    coordinator = get_coordinator(hass)
    api.get("http://v0.ovapi.nl/stopareacode/", json=DIRECTORY)
    await coordinator.async_lookup("")
    api.get("http://v0.ovapi.nl/stopareacode/A/departures", json={"A": {}})
    await coordinator.async_lookup("A")
    first = await begin(hass, "001", lines="X1")
    second = await begin(hass, "001", lines="X2")
    await settle()
    hass.config_entries.flow.async_abort(first["flow_id"])
    await settle()
    assert coordinator._validation_task is not None
    route(api, "001")
    await tick(hass, freezer, 120)
    result = await finish_progress(hass, second)
    assert result["options"]["lines"] == "X2"
    assert api.call_count == 3


async def test_shutdown_cancels_waiting_manual_work(hass, api):
    coordinator = get_coordinator(hass)
    route(api, "001", status=429, headers={"Retry-After": "600"})
    with pytest.raises(ApiError):
        await coordinator.async_validate("001", interactive=True)
    task = asyncio.create_task(coordinator.async_validate("002", interactive=True))
    await settle()
    await coordinator.async_shutdown()
    await asyncio.gather(task, return_exceptions=True)
    assert coordinator._validation_task is None
    assert api.call_count == 1
