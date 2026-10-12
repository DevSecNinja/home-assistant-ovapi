"""One per-instance batch/cache/budget, independent of entities and card viewers."""

import asyncio
import json
import logging
import time
from collections import Counter, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Literal, TypedDict
from uuid import uuid4

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
    CONF_TRANSPORTS,
    CONF_WALK,
    DISCOVERY_REQUESTS,
    DISCOVERY_WINDOW_SECONDS,
    DOMAIN,
    MAX_BACKOFF_SECONDS,
    MAX_DEPARTURES,
    MAX_STOPS,
    POLL_SECONDS,
    RETENTION_SECONDS,
    SUPPORTED_TRANSPORTS,
)
from .discovery import MAX_LOOKUPS, StopArea, TimingPoint

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


@dataclass(slots=True, repr=False)
class CachedLookup:
    fetched_at: datetime
    expires_at: datetime
    monotonic_expiry: float
    areas: tuple[StopArea, ...] = ()
    points: dict[str, TimingPoint] = field(default_factory=dict)

    def clear(self) -> None:
        self.areas = ()
        self.points.clear()


@dataclass(frozen=True, slots=True, repr=False)
class StopReservation:
    stop: str
    replacing: str | None


def normalized_lines(value: str) -> tuple[str, ...]:
    return tuple(
        sorted({line.strip().casefold() for line in value.split(",") if line.strip()})
    )


def identity(stop: str, options: dict[str, Any]) -> str:
    """Canonical identity excludes presentation-only name and walking duration."""
    lines = ",".join(normalized_lines(options.get(CONF_LINES, "")))
    destination = options.get(CONF_DESTINATION, "").strip().casefold()
    modes = sorted(options.get(CONF_TRANSPORTS, SUPPORTED_TRANSPORTS))
    parts = [stop, lines, destination]
    if set(modes) != set(SUPPORTED_TRANSPORTS):
        parts.append(",".join(modes))
    return json.dumps(parts, ensure_ascii=True)


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
        self._lookups: dict[str, CachedLookup] = {}
        self._lookup_tasks: dict[str, asyncio.Task[None]] = {}
        self._lookup_waiters: dict[str, int] = {}
        self._request_lock = asyncio.Lock()
        self._lookup_starts: deque[float] = deque(maxlen=DISCOVERY_REQUESTS)
        self._lookups_since_poll = 0
        self._backoff_until = 0.0
        self._pending: set[str] = set()
        self._pending_counts: Counter[str] = Counter()
        self._reservations: dict[str, StopReservation] = {}
        self._inflight: asyncio.Task[dict[str, str]] | None = None
        self._validation_task: asyncio.Task[dict[str, str]] | None = None
        self._validation_waiters: dict[asyncio.Task[dict[str, str]], int] = {}
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
        return set(self._registered_entries().values())

    def _registered_entries(self) -> dict[str, str]:
        return {
            entry_id: entry.data[CONF_STOP]
            if (entry := self.hass.config_entries.async_get_entry(entry_id))
            else stop
            for entry_id, stop in self.entries.items()
        }

    def _capacity_entries(self) -> dict[str, str]:
        return {
            **self.entries,
            **{
                entry.entry_id: entry.data[CONF_STOP]
                for entry in self.hass.config_entries.async_entries(DOMAIN)
                if entry.disabled_by is None
            },
        }

    def reserve_stop(self, token: str, stop: str, replacing: str | None = None) -> None:
        """Reserve the prospective configuration, without changing active boards."""
        if replacing is not None and any(
            key != token and item.replacing == replacing
            for key, item in self._reservations.items()
        ):
            raise ApiError("reconfigure_in_progress")
        entries = self._capacity_entries()
        reservations = {**self._reservations, token: StopReservation(stop, replacing)}
        counts = Counter(entries.values())
        targets = {item.stop for item in reservations.values()}
        released: set[str] = set()
        # Only one unique old point can back each new point. A shrinking edit
        # cannot lend its future free slot to another flow before it commits.
        for target in targets - counts.keys():
            backing = [
                (entries.get(item.replacing) if item.replacing is not None else None)
                for item in reservations.values()
                if item.stop == target
            ]
            # Every claimant must carry its own replacement credit, including
            # whichever claimant remains after the others abort.
            if any(
                old is None or counts[old] != 1 or old in targets for old in backing
            ):
                continue
            released.update(old for old in backing[:1] if old is not None)
        prospective = (
            (set(counts) - released) | targets | (self._pending - set(entries.values()))
        )
        if len(prospective) > MAX_STOPS:
            raise ApiError("too_many_stops")
        self._reservations[token] = reservations[token]

    def release_stop(self, token: str, *, discard_unconfigured: bool = True) -> None:
        reservation = self._reservations.pop(token, None)
        if reservation is None:
            return
        remaining = {item.stop for item in self._reservations.values()}
        if reservation.stop not in remaining:
            self._pending.discard(reservation.stop)
        protected = set(self._capacity_entries().values()) | self._pending | remaining
        if discard_unconfigured and reservation.stop not in protected:
            self._cache.pop(reservation.stop, None)
        for stop in list(self._cache):
            if len(self._cache) > MAX_STOPS and stop not in protected:
                self._cache.pop(stop)
        self._schedule_expiry()

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

    async def async_validate(
        self,
        stop: str,
        *,
        reservation_id: str | None = None,
        replacing: str | None = None,
        interactive: bool = False,
    ) -> None:
        """Validate through the same cache/budget, never a second client."""
        token = None
        reservation = None
        if reservation_id is not None or stop not in self._capacity_entries().values():
            token = reservation_id or uuid4().hex
            self.reserve_stop(token, stop, replacing)
            reservation = self._reservations[token]
        success = False
        pending = False
        try:
            if self._get_board(stop) is None:
                pending = True
                self._pending_counts[stop] += 1
                self._pending.add(stop)
                errors = (
                    await self._validate_interactively(stop)
                    if interactive
                    else await self._refresh()
                )
                if reservation_id is not None and (
                    self._reservations.get(reservation_id) is not reservation
                ):
                    raise ApiError("selection_expired")
                if self._get_board(stop) is None:
                    raise ApiError(errors.get(stop, "rate_limited"))
            success = True
        finally:
            if pending:
                self._pending_counts[stop] -= 1
                if not self._pending_counts[stop]:
                    self._pending_counts.pop(stop)
                    self._pending.discard(stop)
            if (
                token is not None
                and (reservation_id is None or not success)
                and self._reservations.get(token) is reservation
            ):
                self.release_stop(
                    token, discard_unconfigured=not success or replacing is not None
                )

    async def _async_update_data(self) -> dict[str, Status]:
        await self._refresh()
        return self.statuses()

    async def _validate_interactively(self, stop: str) -> dict[str, str]:
        while True:
            if self._validation_task is None or self._validation_task.done():
                self._validation_task = self.hass.async_create_background_task(
                    self._fetch_validation(), "ovapi interactive validation"
                )
            task = self._validation_task
            self._validation_waiters[task] = self._validation_waiters.get(task, 0) + 1
            try:
                errors = await asyncio.shield(task)
            finally:
                self._validation_waiters[task] -= 1
                if not self._validation_waiters[task]:
                    self._validation_waiters.pop(task)
                    if self._validation_task is task:
                        self._validation_task = None
                    if not task.done():
                        task.cancel()
            if (
                stop in errors
                or self._get_board(stop) is not None
                or stop not in self._pending
            ):
                return errors
            # A caller arriving after dispatch joins the next eligible batch.
            # Failed requests return above; this never retries a source failure.

    async def _fetch_validation(self) -> dict[str, str]:
        await asyncio.sleep(0)
        async with self._request_lock:
            await self._wait_for_budget()
            if (
                self._lookups_since_poll == DISCOVERY_REQUESTS
                and self._configured_stops()
            ):
                # The fair ordinary batch also satisfies pending manual validation.
                return await self._perform_batch()
            return await self._perform_batch(interactive=True)

    async def _refresh(self) -> dict[str, str]:
        if self._inflight is None:
            self._inflight = self.hass.async_create_task(
                self._fetch_batch(), "ovapi batched refresh"
            )
        task = self._inflight
        try:
            return await asyncio.shield(task)
        finally:
            if task.done() and self._inflight is task:
                self._inflight = None

    async def _fetch_batch(self) -> dict[str, str]:
        # Yield once so simultaneous startup/flow calls contribute to one batch.
        await asyncio.sleep(0)
        if self._request_lock.locked():
            return {}
        async with self._request_lock:
            return await self._perform_batch()

    async def _perform_batch(self, *, interactive: bool = False) -> dict[str, str]:
        stops = self._configured_stops() | self._pending
        if len(stops) > MAX_STOPS:
            replacing = {
                item.replacing
                for item in self._reservations.values()
                if item.stop in self._pending
            }
            retained = {
                stop
                for entry_id, stop in self._registered_entries().items()
                if entry_id not in replacing
            }
            # Keep the old board cached, but validate its replacement in this batch.
            stops = retained | self._pending
        if not stops or (not interactive and time.monotonic() < self._next_request):
            return {}
        started = time.monotonic()
        self._next_request = started + POLL_SECONDS
        if interactive:
            self._record_lookup(started)
        else:
            self._lookups_since_poll = 0
        self.request_count += 1
        previous_error = self._error
        errors: dict[str, str] = {}
        try:
            result = await self.client.fetch(stops)
        except ApiError as err:
            self._back_off(err)
            self._error = err.code
            errors = dict.fromkeys(stops, err.code)
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
                    errors[stop] = "unknown_stop"
                    if stop in self._cache:
                        self._cache[stop].stale = True
                    continue
                self._remember_board(
                    stop,
                    CachedBoard(
                        departures,
                        now,
                        now + timedelta(seconds=RETENTION_SECONDS),
                        time.monotonic() + RETENTION_SECONDS,
                    ),
                )
        if self._error is not None and previous_error is None:
            _LOGGER.warning("OVAPI refresh unavailable (%s)", self._error)
        elif self._error is None and previous_error is not None:
            _LOGGER.info("OVAPI connection recovered")
        self._schedule_expiry()
        self.async_set_updated_data(self.statuses())
        return errors

    def lookup(self, key: str) -> CachedLookup | None:
        result = self._lookups.get(key)
        if result is not None and (
            dt_util.utcnow() >= result.expires_at
            or time.monotonic() >= result.monotonic_expiry
        ):
            self._lookups.pop(key).clear()
            return None
        return result

    def discard_lookup(self, key: str) -> None:
        if (lookup := self._lookups.pop(key, None)) is not None:
            lookup.clear()
        self._schedule_expiry()

    async def async_lookup(self, key: str) -> None:
        """Share work but not task-result datasets; last cancellation stops work."""
        if self.lookup(key) is not None:
            return
        if key not in self._lookup_tasks:
            if len(self._lookup_tasks) >= MAX_LOOKUPS:
                raise ApiError("discovery_busy")
            self._lookup_tasks[key] = self.hass.async_create_background_task(
                self._fetch_lookup(key), "ovapi stop lookup"
            )
        task = self._lookup_tasks[key]
        self._lookup_waiters[key] = self._lookup_waiters.get(key, 0) + 1
        try:
            await asyncio.shield(task)
        finally:
            self._lookup_waiters[key] -= 1
            if not self._lookup_waiters[key]:
                self._lookup_waiters.pop(key)
                self._lookup_tasks.pop(key)
                if not task.done():
                    task.cancel()

    def _back_off(self, error: ApiError) -> None:
        self._failures += 1
        self._backoff_until = time.monotonic() + max(
            min(POLL_SECONDS * 2 ** min(self._failures, 5), MAX_BACKOFF_SECONDS),
            error.retry_after,
        )
        self._next_request = max(self._next_request, self._backoff_until)

    def _lookup_ready_at(self) -> float:
        now = time.monotonic()
        while self._lookup_starts and (
            now - self._lookup_starts[0] >= DISCOVERY_WINDOW_SECONDS
        ):
            self._lookup_starts.popleft()
        ready = self._backoff_until
        if len(self._lookup_starts) == DISCOVERY_REQUESTS:
            ready = max(ready, self._lookup_starts[0] + DISCOVERY_WINDOW_SECONDS)
        if self._lookups_since_poll == DISCOVERY_REQUESTS and self._configured_stops():
            ready = max(ready, self._next_request)
        return ready

    def lookup_wait(self) -> tuple[str, datetime]:
        now = time.monotonic()
        ready = self._lookup_ready_at()
        action = (
            "server_pause"
            if self._backoff_until > now
            else "budget_wait"
            if ready > now
            else "lookup"
        )
        return action, dt_util.utcnow() + timedelta(seconds=max(0, ready - now))

    def _record_lookup(self, started: float) -> None:
        self._lookup_starts.append(started)
        self._lookups_since_poll = min(DISCOVERY_REQUESTS, self._lookups_since_poll + 1)

    async def _wait_for_budget(self) -> None:
        while (remaining := self._lookup_ready_at() - time.monotonic()) > 0:
            ready: asyncio.Future[None] = asyncio.get_running_loop().create_future()

            @callback
            def wake(_now: datetime, future: asyncio.Future[None] = ready) -> None:
                if not future.done():
                    future.set_result(None)

            cancel = async_call_later(self.hass, remaining, wake)
            try:
                await ready
            finally:
                cancel()

    async def _fetch_lookup(self, key: str) -> None:
        async with self._request_lock:
            await self._wait_for_budget()
            # Only extra lookups wait for a polling slot; never split the setup pair.
            if (
                self._lookups_since_poll == DISCOVERY_REQUESTS
                and self._configured_stops()
            ):
                await self._perform_batch()
                await self._wait_for_budget()
            started = time.monotonic()
            self._record_lookup(started)
            self._next_request = max(self._next_request, started + POLL_SECONDS)
            self.request_count += 1
            try:
                areas = await self.client.fetch_directory() if not key else ()
                points = await self.client.fetch_area(key) if key else {}
            except ApiError as err:
                self._back_off(err)
                _LOGGER.warning("OVAPI stop lookup unavailable (%s)", err.code)
                raise ApiError(err.code) from None
            self._failures = 0
            now = dt_util.utcnow()
            if len(self._lookups) >= MAX_LOOKUPS:
                oldest = next(iter(self._lookups))
                self._lookups.pop(oldest).clear()
            self._lookups[key] = CachedLookup(
                now,
                now + timedelta(seconds=RETENTION_SECONDS),
                time.monotonic() + RETENTION_SECONDS,
                areas,
                points,
            )
            self._schedule_expiry()

    def select_point(
        self,
        area: str,
        stop: str,
        *,
        reservation_id: str | None = None,
        replacing: str | None = None,
    ) -> None:
        lookup = self.lookup(area)
        if lookup is None or stop not in lookup.points:
            raise ApiError("selection_expired")
        token = reservation_id or uuid4().hex
        self.reserve_stop(token, stop, replacing)
        existing = self._get_board(stop)
        if existing is None or existing.fetched_at < lookup.fetched_at:
            self._remember_board(
                stop,
                CachedBoard(
                    lookup.points[stop].departures,
                    lookup.fetched_at,
                    lookup.expires_at,
                    lookup.monotonic_expiry,
                ),
            )
        if reservation_id is None:
            self.release_stop(token, discard_unconfigured=False)
        self._schedule_expiry()

    def _remember_board(self, stop: str, board: CachedBoard) -> None:
        if len(self._cache) >= MAX_STOPS and stop not in self._cache:
            unused = next(
                (
                    key
                    for key in self._cache
                    if key
                    not in (
                        self._configured_stops()
                        | self._pending
                        | {item.stop for item in self._reservations.values()}
                    )
                ),
                None,
            )
            if unused is not None:
                self._cache.pop(unused)
        self._cache[stop] = board

    @callback
    def _schedule_expiry(self) -> None:
        if self._expiry_cancel is not None:
            self._expiry_cancel()
            self._expiry_cancel = None
        cached: list[CachedBoard | CachedLookup] = [
            *self._cache.values(),
            *self._lookups.values(),
        ]
        if cached:
            seconds = min(
                min(
                    board.monotonic_expiry - time.monotonic(),
                    (board.expires_at - dt_util.utcnow()).total_seconds(),
                )
                for board in cached
            )
            self._expiry_cancel = async_call_later(
                self.hass, max(0, seconds), self._expire
            )

    @callback
    def _expire(self, _now: datetime) -> None:
        self._expiry_cancel = None
        for stop in list(self._cache):
            self._get_board(stop)
        for key in list(self._lookups):
            self.lookup(key)
        self.async_set_updated_data(self.statuses())
        self._schedule_expiry()

    def snapshot(self, entry: ConfigEntry, entity_id: str) -> BoardPayload:
        stop: str = entry.data[CONF_STOP]
        board = self._get_board(stop) if entry.entry_id in self.entries else None
        lines = normalized_lines(entry.options.get(CONF_LINES, ""))
        destination = entry.options.get(CONF_DESTINATION, "").strip().casefold()
        modes = entry.options.get(CONF_TRANSPORTS, SUPPORTED_TRANSPORTS)
        now = dt_util.utcnow()
        departures = (
            [
                departure.as_payload()
                for departure in board.departures
                if departure.departure_at >= now
                and departure.transport in modes
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

    def observed_transports(self, stop: str) -> tuple[str, ...]:
        board = self._get_board(stop)
        return (
            tuple(sorted({departure.transport for departure in board.departures}))
            if board
            else ()
        )

    async def async_shutdown(self) -> None:
        await super().async_shutdown()
        if self._inflight is not None:
            self._inflight.cancel()
        if self._validation_task is not None:
            self._validation_task.cancel()
        for task in self._lookup_tasks.values():
            task.cancel()
        if self._expiry_cancel is not None:
            self._expiry_cancel()
            self._expiry_cancel = None
        self._cache.clear()
        for lookup in self._lookups.values():
            lookup.clear()
        self._lookups.clear()
        self._reservations.clear()


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
