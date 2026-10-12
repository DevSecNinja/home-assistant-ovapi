"""Async transport and pure parsing; no Home Assistant dependency or persistence."""

import json
import logging
import re
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Literal, TypedDict
from urllib.parse import quote
from zoneinfo import ZoneInfo

import aiohttp

from .const import API_URL, MAX_RESPONSE_BYTES, MAX_STOPS, USER_AGENT

if TYPE_CHECKING:
    from .discovery import StopArea, TimingPoint

_LOGGER = logging.getLogger(__name__)
_DUTCH_TZ = ZoneInfo("Europe/Amsterdam")
_STOP_PATTERN = re.compile(r"[0-9]{1,10}")
type Transport = Literal["bus", "tram", "metro", "unknown"]


class DeparturePayload(TypedDict):
    """Public v1 departure schema."""

    id: str
    line: str
    destination: str
    transport: Transport
    scheduled_at: str
    expected_at: str | None
    cancelled: bool | None
    delay_seconds: int | None


@dataclass(frozen=True, slots=True)
class Departure:
    """Immutable normalized source record."""

    id: str
    line: str
    destination: str
    transport: Transport
    scheduled_at: datetime
    expected_at: datetime | None
    cancelled: bool | None

    @property
    def departure_at(self) -> datetime:
        return self.expected_at or self.scheduled_at

    @property
    def delay_seconds(self) -> int | None:
        if self.expected_at is None:
            return None
        return int((self.expected_at - self.scheduled_at).total_seconds())

    def as_payload(self) -> DeparturePayload:
        return {
            "id": self.id,
            "line": self.line,
            "destination": self.destination,
            "transport": self.transport,
            "scheduled_at": self.scheduled_at.isoformat(),
            "expected_at": self.expected_at.isoformat() if self.expected_at else None,
            "cancelled": self.cancelled,
            "delay_seconds": self.delay_seconds,
        }


class ApiError(Exception):
    """Safe error codes only: never keep URLs, response data or source exceptions."""

    def __init__(self, code: str, retry_after: float = 0) -> None:
        super().__init__(code)
        self.code = code
        self.retry_after = retry_after


def valid_stop(value: str) -> bool:
    return _STOP_PATTERN.fullmatch(value) is not None


def parse_time(value: object) -> datetime:
    """Reject nonexistent/ambiguous local instants rather than guessing a DST fold."""
    if not isinstance(value, str):
        raise ValueError("invalid_time")
    result = datetime.fromisoformat(value)
    if result.year < 2000:
        raise ValueError("invalid_time")
    if result.tzinfo is None:
        first = result.replace(tzinfo=_DUTCH_TZ, fold=0)
        second = result.replace(tzinfo=_DUTCH_TZ, fold=1)
        if first.utcoffset() != second.utcoffset():
            raise ValueError("ambiguous_or_nonexistent_time")
        result = first
    return result.astimezone(UTC)


def parse_board(value: object) -> tuple[Departure, ...]:
    """Normalize supported departures; optional static timetable data can be absent."""
    if not isinstance(value, dict):
        raise ApiError("invalid_data")
    passes = value.get("Passes")
    if passes is None and isinstance(value.get("Stop"), dict):
        return ()
    if not isinstance(passes, dict):
        raise ApiError("invalid_data")
    departures: list[Departure] = []
    skipped = 0
    for journey_id, record in passes.items():
        if not isinstance(record, dict):
            raise ApiError("invalid_data")
        transport = record.get("TransportType")
        mode: Transport
        if transport == "BUS":
            mode = "bus"
        elif transport == "TRAM":
            mode = "tram"
        elif transport == "METRO":
            mode = "metro"
        else:
            continue
        status = record.get("TripStopStatus")
        if record.get("JourneyStopType") == "LAST" or status == "PASSED":
            continue
        if not record.get("TargetDepartureTime"):
            skipped += 1
            continue
        try:
            scheduled = parse_time(record["TargetDepartureTime"])
            expected_value = record.get("ExpectedDepartureTime")
            expected = parse_time(expected_value) if expected_value else None
        except ValueError:
            raise ApiError("invalid_data") from None
        line = record.get("LinePublicNumber", "")
        destination = record.get("DestinationName50", "")
        if (
            not isinstance(line, str)
            or not isinstance(destination, str)
            or not isinstance(journey_id, str)
            or not journey_id
            or max(len(journey_id), len(line), len(destination)) > 512
        ):
            raise ApiError("invalid_data")
        if not line.strip() or not destination.strip():
            skipped += 1
            continue
        cancelled: bool | None = None
        if status in ("CANCEL", "LINESTOPCANCEL"):
            cancelled = True
        elif status in ("DRIVING", "PLANNED", "ARRIVED"):
            cancelled = False
        departures.append(
            Departure(
                str(journey_id), line, destination, mode, scheduled, expected, cancelled
            )
        )
    if skipped:
        _LOGGER.debug(
            "Omitted %d departures with incomplete timetable metadata", skipped
        )
    return tuple(sorted(departures, key=lambda departure: departure.departure_at))


def retry_after_seconds(value: str | None) -> float:
    """Honor delta-seconds and HTTP dates without retaining the header."""
    if value is None:
        return 0
    if value.isdigit() and len(value) <= 9:
        return float(value)
    try:
        date = parsedate_to_datetime(value)
        return max(0.0, (date - datetime.now(UTC)).total_seconds())
    except ValueError, TypeError, OverflowError:
        return 0


class OvapiClient:
    """Fixed public HTTP origin; no redirects, TLS bypass, auth or storage."""

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def fetch(self, stops: set[str]) -> dict[str, tuple[Departure, ...] | None]:
        if (
            not stops
            or len(stops) > MAX_STOPS
            or any(not valid_stop(stop) for stop in stops)
        ):
            raise ApiError("invalid_stop")
        url = f"{API_URL}/{','.join(sorted(stops))}/departures"
        payload = await self._request(url)
        return {
            stop: parse_board(payload[stop]) if stop in payload else None
            for stop in stops
        }

    async def fetch_directory(self) -> tuple[StopArea, ...]:
        from .discovery import AREA_URL, MAX_DIRECTORY_BYTES, parse_directory

        return parse_directory(await self._request(f"{AREA_URL}/", MAX_DIRECTORY_BYTES))

    async def fetch_area(self, area: str) -> dict[str, TimingPoint]:
        from .discovery import AREA_URL, parse_area, valid_area

        if not valid_area(area):
            raise ApiError("invalid_area")
        try:
            payload = await self._request(
                f"{AREA_URL}/{quote(area, safe='')}/departures"
            )
        except ApiError as err:
            if err.code == "unknown_stop":
                raise ApiError("unknown_area", err.retry_after) from None
            raise
        return parse_area(payload, area)

    async def _request(
        self, url: str, limit: int = MAX_RESPONSE_BYTES
    ) -> dict[str, object]:
        try:
            async with self._session.get(
                url,
                headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip"},
                timeout=aiohttp.ClientTimeout(total=20),
                allow_redirects=False,
                auto_decompress=False,
            ) as response:
                if response.status != 200:
                    code = {
                        404: "unknown_stop",
                        429: "rate_limited",
                    }.get(response.status, "cannot_connect")
                    raise ApiError(
                        code, retry_after_seconds(response.headers.get("Retry-After"))
                    )
                encoding = response.headers.get("Content-Encoding", "identity")
                if encoding not in ("identity", "gzip"):
                    raise ApiError("invalid_data")
                decoder = (
                    zlib.decompressobj(16 + zlib.MAX_WBITS)
                    if encoding == "gzip"
                    else None
                )
                body = bytearray()
                received = 0
                async for chunk in response.content.iter_chunked(64 * 1024):
                    received += len(chunk)
                    if received > limit:
                        raise ApiError("response_too_large")
                    body.extend(
                        decoder.decompress(chunk, limit - len(body) + 1)
                        if decoder
                        else chunk
                    )
                    if len(body) > limit:
                        raise ApiError("response_too_large")
                if decoder and (not decoder.eof or decoder.unused_data):
                    raise ApiError("invalid_data")
                try:
                    payload = json.loads(body)
                except ValueError, UnicodeDecodeError:
                    raise ApiError("invalid_data") from None
                if not isinstance(payload, dict):
                    raise ApiError("invalid_data")
                return payload
        except zlib.error:
            raise ApiError("invalid_data") from None
        except aiohttp.ClientError, TimeoutError:
            raise ApiError("cannot_connect") from None
