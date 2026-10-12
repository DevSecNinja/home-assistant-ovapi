"""Pure parsing and bounded transport tests."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import aiohttp
import pytest

from custom_components.ovapi.client import (
    ApiError,
    OvapiClient,
    parse_board,
    parse_time,
    retry_after_seconds,
    valid_stop,
)
from custom_components.ovapi.const import MAX_RESPONSE_BYTES


def test_parse_board(payload):
    """Source times are Dutch local time, not HA's configured timezone."""
    departures = parse_board(payload["01234567"])
    assert departures[0].scheduled_at == datetime(2030, 1, 15, 12, 10, tzinfo=UTC)
    assert departures[0].delay_seconds == 120
    assert departures[0].cancelled is False


@pytest.mark.parametrize(
    "value",
    ["2030-03-31T02:30:00", "2030-10-27T02:30:00", "invalid", "1970-01-01T00:00:00"],
)
def test_invalid_or_ambiguous_time(value):
    with pytest.raises(ValueError):
        parse_time(value)


async def test_batched_client(api, payload):
    api.get("http://v0.ovapi.nl/tpc/01234567,76543210/departures", json=payload)
    async with api.create_session(asyncio.get_running_loop()) as session:
        result = await OvapiClient(session).fetch({"76543210", "01234567"})
    assert result["01234567"][0].line == "X1"
    assert result["76543210"] is None
    assert api.call_count == 1


async def test_http_error(api):
    api.get(
        "http://v0.ovapi.nl/tpc/01234567/departures",
        status=429,
        headers={"Retry-After": "600"},
    )
    async with api.create_session(asyncio.get_running_loop()) as session:
        with pytest.raises(ApiError) as error:
            await OvapiClient(session).fetch({"01234567"})
    assert error.value.code == "rate_limited"
    assert error.value.retry_after == 600


@pytest.mark.parametrize(
    "value,expected",
    [
        ("2030-01-15T13:00:00+01:00", "2030-01-15T12:00:00+00:00"),
        ("2030-07-15T13:00:00", "2030-07-15T11:00:00+00:00"),
        ("2030-01-16T00:05:00", "2030-01-15T23:05:00+00:00"),
        ("2030-10-27T02:30:00+02:00", "2030-10-27T00:30:00+00:00"),
        ("2030-10-27T02:30:00+01:00", "2030-10-27T01:30:00+00:00"),
    ],
)
def test_time_instants(value, expected):
    assert parse_time(value).isoformat() == expected


def test_invalid_time_type():
    with pytest.raises(ValueError):
        parse_time(None)


@pytest.mark.parametrize("value", [[], {}, {"Passes": []}, {"Passes": {"trip": []}}])
def test_malformed_board(value):
    with pytest.raises(ApiError, match="invalid_data"):
        parse_board(value)


def test_empty_and_metadata_only_board():
    assert parse_board({"Passes": {}}) == ()
    assert parse_board({"Stop": {}}) == ()


@pytest.mark.parametrize(
    "mode,expected", [("BUS", "bus"), ("TRAM", "tram"), ("METRO", "metro")]
)
@pytest.mark.parametrize(
    "status,cancelled",
    [("CANCEL", True), ("LINESTOPCANCEL", True), ("PLANNED", False), ("UNKNOWN", None)],
)
def test_modes_predictions_and_cancellations(
    payload, mode, expected, status, cancelled
):
    record = payload["01234567"]["Passes"]["SYNTHETIC_TRIP"]
    record.update(
        {"TransportType": mode, "TripStopStatus": status, "ExpectedDepartureTime": None}
    )
    departure = parse_board(payload["01234567"])[0]
    serialized = departure.as_payload()
    assert serialized["transport"] == expected
    assert serialized["cancelled"] is cancelled
    assert serialized["expected_at"] is None
    assert serialized["delay_seconds"] is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("TransportType", "TRAIN"),
        ("TransportType", "FERRY"),
        ("TransportType", None),
        ("JourneyStopType", "LAST"),
        ("TripStopStatus", "PASSED"),
        ("TargetDepartureTime", None),
        ("LinePublicNumber", ""),
        ("DestinationName50", ""),
    ],
)
def test_skip_unsupported_or_incomplete(payload, field, value):
    payload["01234567"]["Passes"]["SYNTHETIC_TRIP"][field] = value
    assert parse_board(payload["01234567"]) == ()


@pytest.mark.parametrize(
    "field,value",
    [
        ("TargetDepartureTime", "broken"),
        ("ExpectedDepartureTime", "broken"),
        ("LinePublicNumber", 12),
        ("DestinationName50", []),
        ("LinePublicNumber", "X" * 513),
    ],
)
def test_malformed_record(payload, field, value):
    payload["01234567"]["Passes"]["SYNTHETIC_TRIP"][field] = value
    with pytest.raises(ApiError, match="invalid_data"):
        parse_board(payload["01234567"])


@pytest.mark.parametrize(
    "stop,expected",
    [
        ("01234567", True),
        ("0", True),
        ("12345678901", False),
        ("../", False),
        ("１", False),
    ],
)
def test_stop_validation(stop, expected):
    assert valid_stop(stop) is expected


@pytest.mark.parametrize(
    "value,expected", [(None, 0), ("12", 12), ("invalid", 0), ("-3", 0)]
)
def test_retry_after(value, expected):
    assert retry_after_seconds(value) == expected


def test_retry_after_http_date(freezer):
    freezer.move_to("2030-01-15T12:00:00+00:00")
    assert retry_after_seconds("Tue, 15 Jan 2030 12:05:00 GMT") == 300
    assert retry_after_seconds("Tue, 15 Jan 2030 11:00:00 GMT") == 0


@pytest.mark.parametrize("stops", [set(), {"bad/stop"}, {str(i) for i in range(11)}])
async def test_invalid_stops_no_requests(api, stops):
    async with api.create_session(asyncio.get_running_loop()) as session:
        with pytest.raises(ApiError, match="invalid_stop"):
            await OvapiClient(session).fetch(stops)
    assert api.call_count == 0


@pytest.mark.parametrize(
    "body", [b"not json", b"[]", b"\xff", b"x" * (MAX_RESPONSE_BYTES + 1)]
)
async def test_invalid_network_body(api, body):
    api.get("http://v0.ovapi.nl/tpc/01234567/departures", content=body)
    async with api.create_session(asyncio.get_running_loop()) as session:
        with pytest.raises(ApiError):
            await OvapiClient(session).fetch({"01234567"})


@pytest.mark.parametrize("error", [aiohttp.ClientConnectionError(), TimeoutError()])
async def test_network_failure_is_safe(api, error):
    api.get("http://v0.ovapi.nl/tpc/01234567/departures", exc=error)
    async with api.create_session(asyncio.get_running_loop()) as session:
        with pytest.raises(ApiError, match="cannot_connect"):
            await OvapiClient(session).fetch({"01234567"})


def test_shared_contract_edge_fixture():
    source = json.loads(Path("tests/fixtures/card-source-edge.json").read_text())
    normalized = [item.as_payload() for item in parse_board(source["01234567"])]
    assert len(normalized) == 1
    assert normalized[0]["id"] == "SYNTHETIC_VALID"
    for item in normalized:
        assert all(
            0 < len(item[field]) <= 512 for field in ("id", "line", "destination")
        )
        assert item["expected_at"] is None
        assert item["cancelled"] is None
        assert item["delay_seconds"] is None
