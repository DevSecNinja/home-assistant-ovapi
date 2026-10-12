"""Bounded, pure stop discovery; no locations, raw records or persistence."""

import unicodedata
from dataclasses import dataclass, field
from itertools import islice

from .client import ApiError, Departure, parse_board, valid_stop

MAX_AREAS = 50_000
MAX_AREA_POINTS = 100
MAX_SEARCH_RESULTS = 50
MAX_LOOKUPS = 10
MAX_DIRECTORY_BYTES = 16 * 1024 * 1024
AREA_URL = "http://v0.ovapi.nl/stopareacode"


def valid_area(value: str) -> bool:
    return (
        0 < len(value) <= 10
        and bool(value.strip())
        and value not in (".", "..")
        and value.isprintable()
        and not any(char in value for char in "/\\,")
    )


def search_text(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(char)
    )


def _text(value: object) -> str:
    if value is None:
        return ""
    if not isinstance(value, str) or len(value) > 256:
        raise ApiError("invalid_data")
    return value.strip()


@dataclass(frozen=True, slots=True, repr=False)
class StopArea:
    code: str
    town: str
    name: str
    search_key: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "search_key", search_text(f"{self.town} {self.name}"))

    @property
    def label(self) -> str:
        return f"{self.town} - {self.name} ({self.code})"


@dataclass(frozen=True, slots=True, repr=False)
class TimingPoint:
    code: str
    name: str
    services: tuple[str, ...]
    departures: tuple[Departure, ...]

    @property
    def label(self) -> str:
        parts = [self.name, *self.services, f"({self.code})"]
        return " - ".join(part for part in parts if part)


def parse_directory(value: object) -> tuple[StopArea, ...]:
    if not isinstance(value, dict) or len(value) > MAX_AREAS:
        raise ApiError("invalid_data")
    areas = []
    for code, metadata in value.items():
        if not isinstance(code, str) or not valid_area(code):
            raise ApiError("invalid_data")
        if not isinstance(metadata, dict):
            raise ApiError("invalid_data")
        town = _text(metadata.get("TimingPointTown"))
        name = _text(metadata.get("TimingPointName"))
        if not name or not town or metadata.get("StopAreaCode", code) != code:
            raise ApiError("invalid_data")
        areas.append(StopArea(code, town, name))
    return tuple(sorted(areas, key=lambda area: search_text(area.label)))


def search_areas(areas: tuple[StopArea, ...], query: str) -> tuple[StopArea, ...]:
    words = search_text(query).split()
    return tuple(
        islice(
            (area for area in areas if all(word in area.search_key for word in words)),
            MAX_SEARCH_RESULTS + 1,
        )
    )


def parse_area(value: object, code: str) -> dict[str, TimingPoint]:
    if not isinstance(value, dict):
        raise ApiError("invalid_data")
    if code not in value:
        raise ApiError("unknown_area")
    points = value[code]
    if (
        not isinstance(points, dict)
        or len(points) - ("ServerTime" in points) > MAX_AREA_POINTS
    ):
        raise ApiError("invalid_data")
    result = {}
    for stop, board in points.items():
        if stop == "ServerTime":
            continue
        if not isinstance(stop, str) or not valid_stop(stop):
            raise ApiError("invalid_data")
        departures = parse_board(board)
        passes = board.get("Passes") or {}
        if passes and not any(
            item.get("TransportType") in ("BUS", "TRAM", "METRO")
            for item in passes.values()
        ):
            continue
        metadata = board.get("Stop", {})
        if not isinstance(metadata, dict):
            raise ApiError("invalid_data")
        name = _text(metadata.get("TimingPointName"))
        if not name:
            for record in passes.values():
                if record.get("TransportType") in ("BUS", "TRAM", "METRO"):
                    name = _text(record.get("TimingPointName"))
                    if name:
                        break
        services = tuple(
            sorted({f"{item.line}: {item.destination}" for item in departures})[:3]
        )
        result[stop] = TimingPoint(stop, name, services, departures)
    return result
