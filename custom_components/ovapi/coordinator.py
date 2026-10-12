"""One per-instance batch/cache/budget, independent of entities and card viewers."""

import asyncio
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Literal, TypedDict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .client import ApiError, Departure, DeparturePayload, OvapiClient
from .const import (
    CONF_DESTINATION,
    CONF_LINES,
    CONF_STOP,
    CONF_WALK,
    DOMAIN,
    MAX_BACKOFF_SECONDS,
    MAX_DEPARTURES,
    MAX_STOPS,
    POLL_SECONDS,
    RETENTION_SECONDS,
)

_LOGGER = logging.getLogger(__name__)
type Status = Literal["ready", "stale", "unavailable"]


class StopPayload(TypedDict):
    id: str
    name: str


class BoardPayload(TypedDict):
    contract_version: int
    board_id: str
    entity_id: str
    stop: StopPayload
    status: Status
    fetched_at: str | None
    expires_at: str | None
    walking_minutes: int
    departures: list[DeparturePayload]


@dataclass(slots=True)
class CachedBoard:
    departures: tuple[Departure, ...]
    fetched_at: datetime
    expires_at: datetime
    monotonic_expiry: float
    stale: bool = False


def normalized_lines(value: str) -> tuple[str, ...]:
    return tuple(
        sorted({line.strip().casefold() for line in value.split(",") if line.strip()})
    )


def identity(stop: str, options: dict[str, Any]) -> str:
    """Canonical identity excludes presentation-only name and walking duration."""
    lines = ",".join(normalized_lines(options.get(CONF_LINES, "")))
    destination = options.get(CONF_DESTINATION, "").strip().casefold()
    return json.dumps([stop, lines, destination], ensure_ascii=True)


class OvapiCoordinator(DataUpdateCoordinator[dict[str, Status]]):
    """Keep departure objects out of HA coordinator data and persistent surfaces."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            config_entry=None,
            update_interval=timedelta(seconds=POLL_SECONDS),
        )
        self.client = OvapiClient(async_get_clientsession(hass))
        self.entries: dict[str, str] = {
            entry.entry_id: entry.data[CONF_STOP]
            for entry in hass.config_entries.async_entries(DOMAIN)
            if entry.disabled_by is None
        }
        self._cache: dict[str, CachedBoard] = {}
        self._pending: set[str] = set()
        self._inflight: asyncio.Task[None] | None = None
        self._expiry_cancel: Callable[[], None] | None = None
        self._next_request = 0.0
        self._failures = 0
        self._error: str | None = None
        self.request_count = 0
        self.data = {}

    @property
    def stop_count(self) -> int:
        return len(self._configured_stops())

    def _configured_stops(self) -> set[str]:
        return set(self.entries.values())

    @callback
    def register(self, entry: ConfigEntry) -> None:
        self.entries[entry.entry_id] = entry.data[CONF_STOP]

    @callback
    def unregister(self, entry: ConfigEntry) -> None:
        stop = self.entries.pop(entry.entry_id, None)
        if stop is not None and stop not in self._configured_stops():
            self._cache.pop(stop, None)
        self._schedule_expiry()
        self.async_set_updated_data(self.statuses())

    def statuses(self) -> dict[str, Status]:
        return {stop: self.status(stop) for stop in self._configured_stops()}

    def status(self, stop: str) -> Status:
        board = self._get_board(stop)
        if board is None:
            return "unavailable"
        return "stale" if board.stale else "ready"

    def _get_board(self, stop: str) -> CachedBoard | None:
        board = self._cache.get(stop)
        if board is not None and (
            dt_util.utcnow() >= board.expires_at
            or time.monotonic() >= board.monotonic_expiry
        ):
            self._cache.pop(stop)
            return None
        return board

    async def async_validate(self, stop: str) -> None:
        """Validate through the same cache/budget, never a second client."""
        if self._get_board(stop) is not None:
            return
        if len(self._configured_stops() | self._pending | {stop}) > MAX_STOPS:
            raise ApiError("too_many_stops")
        self._pending.add(stop)
        try:
            await self._refresh()
            if self._get_board(stop) is None:
                raise ApiError(self._error or "rate_limited")
        finally:
            self._pending.discard(stop)

    async def _async_update_data(self) -> dict[str, Status]:
        await self._refresh()
        return self.statuses()

    async def _refresh(self) -> None:
        if self._inflight is None:
            self._inflight = self.hass.async_create_task(
                self._fetch_batch(), "ovapi batched refresh"
            )
        task = self._inflight
        try:
            await asyncio.shield(task)
        finally:
            if task.done() and self._inflight is task:
                self._inflight = None

    async def _fetch_batch(self) -> None:
        # Yield once so simultaneous startup/flow calls contribute to one batch.
        await asyncio.sleep(0)
        stops = self._configured_stops() | self._pending
        if not stops or time.monotonic() < self._next_request:
            return
        started = time.monotonic()
        self._next_request = started + POLL_SECONDS
        self.request_count += 1
        previous_error = self._error
        try:
            result = await self.client.fetch(stops)
        except ApiError as err:
            self._failures += 1
            self._next_request = started + max(
                min(POLL_SECONDS * 2 ** min(self._failures, 5), MAX_BACKOFF_SECONDS),
                err.retry_after,
            )
            self._error = err.code
            for board in self._cache.values():
                board.stale = True
        else:
            self._failures = 0
            self._error = None
            now = dt_util.utcnow()
            wanted = self._configured_stops() | self._pending
            for stop, departures in result.items():
                if stop not in wanted:
                    continue
                if departures is None:
                    self._error = "unknown_stop"
                    if stop in self._cache:
                        self._cache[stop].stale = True
                    continue
                self._cache[stop] = CachedBoard(
                    departures,
                    now,
                    now + timedelta(seconds=RETENTION_SECONDS),
                    time.monotonic() + RETENTION_SECONDS,
                )
        if self._error is not None and previous_error is None:
            _LOGGER.warning("OVAPI refresh unavailable (%s)", self._error)
        elif self._error is None and previous_error is not None:
            _LOGGER.info("OVAPI connection recovered")
        self._schedule_expiry()
        self.async_set_updated_data(self.statuses())

    @callback
    def _schedule_expiry(self) -> None:
        if self._expiry_cancel is not None:
            self._expiry_cancel()
            self._expiry_cancel = None
        if self._cache:
            seconds = min(
                min(
                    board.monotonic_expiry - time.monotonic(),
                    (board.expires_at - dt_util.utcnow()).total_seconds(),
                )
                for board in self._cache.values()
            )
            self._expiry_cancel = async_call_later(
                self.hass, max(0, seconds), self._expire
            )

    @callback
    def _expire(self, _now: datetime) -> None:
        self._expiry_cancel = None
        for stop in list(self._cache):
            self._get_board(stop)
        self.async_set_updated_data(self.statuses())
        self._schedule_expiry()

    def snapshot(self, entry: ConfigEntry, entity_id: str) -> BoardPayload:
        stop: str = entry.data[CONF_STOP]
        board = self._get_board(stop) if entry.entry_id in self.entries else None
        lines = normalized_lines(entry.options.get(CONF_LINES, ""))
        destination = entry.options.get(CONF_DESTINATION, "").strip().casefold()
        now = dt_util.utcnow()
        departures = (
            [
                departure.as_payload()
                for departure in board.departures
                if departure.departure_at >= now
                and (not lines or departure.line.casefold() in lines)
                and destination in departure.destination.casefold()
            ][:MAX_DEPARTURES]
            if board
            else []
        )
        return {
            "contract_version": 1,
            "board_id": entry.entry_id,
            "entity_id": entity_id,
            "stop": {"id": stop, "name": entry.data["name"]},
            "status": ("stale" if board.stale else "ready") if board else "unavailable",
            "fetched_at": board.fetched_at.isoformat() if board else None,
            "expires_at": board.expires_at.isoformat() if board else None,
            "walking_minutes": entry.options.get(CONF_WALK, 0),
            "departures": departures,
        }

    async def async_shutdown(self) -> None:
        await super().async_shutdown()
        if self._inflight is not None:
            self._inflight.cancel()
        if self._expiry_cancel is not None:
            self._expiry_cancel()
            self._expiry_cancel = None
        self._cache.clear()


@callback
def get_coordinator(hass: HomeAssistant) -> OvapiCoordinator:
    """A runtime-only singleton; preserve the budget across entry reloads."""
    coordinator = hass.data.get(DOMAIN)
    if isinstance(coordinator, OvapiCoordinator):
        return coordinator
    coordinator = OvapiCoordinator(hass)
    hass.data[DOMAIN] = coordinator
    hass.async_create_task(coordinator.async_register_shutdown())
    return coordinator
