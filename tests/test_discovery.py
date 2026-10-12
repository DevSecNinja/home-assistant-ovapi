"""Synthetic stop metadata, never a captured network directory."""

import asyncio
import gzip
import json
import time
from urllib.parse import quote

import pytest

from custom_components.ovapi.client import ApiError, OvapiClient
from custom_components.ovapi.const import MAX_RESPONSE_BYTES
from custom_components.ovapi.discovery import (
    MAX_AREA_POINTS,
    MAX_AREAS,
    MAX_SEARCH_RESULTS,
    StopArea,
    parse_area,
    parse_directory,
    search_areas,
    valid_area,
)

DIRECTORY = {
    "AbC01": {"TimingPointTown": "Synthetisch", "TimingPointName": "Centràal"},
    "AbC02": {"TimingPointTown": "Andere stad", "TimingPointName": "Centraal"},
}


def test_directory_search_and_duplicates():
    directory = parse_directory(DIRECTORY)
    assert [x.code for x in search_areas(directory, "SYNThetisch centraal")] == [
        "AbC01"
    ]
    assert len(search_areas(directory, "centraal")) == 2
    assert search_areas(directory, "missing") == ()
    assert "Andere stad" in search_areas(directory, "andere")[0].label


@pytest.mark.parametrize(
    "code", ["AbC01", "001", "A-B_c", "halte.1", "'sAbc", "Één", "A B", "A?#", "%2f"]
)
def test_area_codes(code):
    assert valid_area(code)


@pytest.mark.parametrize(
    "code", ["", "../", "a,b", "a/b", "x" * 11, "..", "\\x", " ", "a\nb"]
)
def test_unsafe_area_codes(code):
    assert not valid_area(code)


@pytest.mark.parametrize(
    "value", [[], {"bad": []}, {"bad": {}}, {"bad": {"TimingPointTown": 1}}]
)
def test_invalid_directory(value):
    with pytest.raises(ApiError, match="invalid_data"):
        parse_directory(value)


def test_area_shape(payload):
    result = parse_area({"AbC01": {"ServerTime": "ignored", **payload}}, "AbC01")
    assert list(result) == ["01234567"]
    assert "X1" in result["01234567"].label
    assert "Synthetic destination" in result["01234567"].label
    assert result["01234567"].departures


def test_empty_and_unsupported_area(payload):
    assert parse_area({"AbC01": {}}, "AbC01") == {}
    payload["01234567"]["Passes"]["SYNTHETIC_TRIP"]["TransportType"] = "TRAIN"
    assert parse_area({"AbC01": payload}, "AbC01") == {}
    with pytest.raises(ApiError, match="unknown_area"):
        parse_area({}, "AbC01")


async def test_directory_transport(api):
    raw = gzip.compress(json.dumps(DIRECTORY).encode())
    api.get(
        "http://v0.ovapi.nl/stopareacode/",
        content=raw,
        headers={"Content-Encoding": "gzip"},
    )
    async with api.create_session(asyncio.get_running_loop()) as session:
        assert await OvapiClient(session).fetch_directory() == parse_directory(
            DIRECTORY
        )


async def test_area_transport(api, payload):
    api.get("http://v0.ovapi.nl/stopareacode/AbC01/departures", json={"AbC01": payload})
    async with api.create_session(asyncio.get_running_loop()) as session:
        assert await OvapiClient(session).fetch_area("AbC01") == parse_area(
            {"AbC01": payload}, "AbC01"
        )


@pytest.mark.parametrize(
    "metadata",
    [
        {"TimingPointTown": "Town", "TimingPointName": "x" * 257},
        {"TimingPointTown": "Town", "TimingPointName": "Name", "StopAreaCode": "wrong"},
        {"TimingPointTown": "Town", "TimingPointName": []},
    ],
)
def test_directory_bad_metadata(metadata):
    with pytest.raises(ApiError, match="invalid_data"):
        parse_directory({"AbC01": metadata})


def test_directory_limits():
    with pytest.raises(ApiError, match="invalid_data"):
        parse_directory({str(i): {} for i in range(MAX_AREAS + 1)})
    with pytest.raises(ApiError, match="invalid_data"):
        parse_directory({"../bad": {}})
    areas = parse_directory(
        {
            str(i): {"TimingPointTown": "Town", "TimingPointName": "Name"}
            for i in range(MAX_SEARCH_RESULTS + 10)
        }
    )
    assert len(search_areas(areas, "town")) == MAX_SEARCH_RESULTS + 1


def test_maximum_cached_search_under_one_second():
    areas = tuple(
        StopArea(str(i), "Synthetic town", "Synthetic stop") for i in range(MAX_AREAS)
    )
    started = time.perf_counter()
    assert search_areas(areas, "absent destination") == ()
    assert time.perf_counter() - started < 1


@pytest.mark.parametrize(
    "value",
    [
        [],
        {"AbC01": []},
        {"AbC01": {"invalid": {}}},
        {"AbC01": {str(i): {} for i in range(MAX_AREA_POINTS + 2)}},
        {"AbC01": {"01234567": {"Passes": {"bad": []}}}},
    ],
)
def test_area_malformed(value):
    with pytest.raises(ApiError, match="invalid_data"):
        parse_area(value, "AbC01")


def test_metadata_empty_and_optional_labels(payload):
    assert (
        parse_area(
            {
                "AbC01": {
                    "01234567": {"Stop": {"TimingPointName": "Synthetic night stop"}}
                }
            },
            "AbC01",
        )["01234567"].label
        == "Synthetic night stop - (01234567)"
    )
    board = payload["01234567"]
    board["Stop"] = {"TimingPointName": "Source platform B"}
    assert (
        "Source platform B" in parse_area({"AbC01": payload}, "AbC01")["01234567"].label
    )
    board["Stop"] = []
    with pytest.raises(ApiError, match="invalid_data"):
        parse_area({"AbC01": payload}, "AbC01")
    board.pop("Stop")
    board["Passes"]["SYNTHETIC_TRIP"]["TimingPointName"] = "Name from pass"
    assert "Name from pass" in parse_area({"AbC01": payload}, "AbC01")["01234567"].label
    board["Passes"] = {
        "rail": {"TransportType": "TRAIN"},
        "missing": {"TransportType": "BUS"},
        **board["Passes"],
    }
    assert parse_area({"AbC01": payload}, "AbC01")["01234567"].departures


@pytest.mark.parametrize(
    "board",
    [
        {"Stop": {}},
        {"Stop": {}, "Passes": None},
        {"Passes": {}},
    ],
)
def test_empty_board_without_optional_name(board):
    point = parse_area({"AbC01": {"01234567": board}}, "AbC01")["01234567"]
    assert point.label == "(01234567)"
    assert point.departures == ()


@pytest.mark.parametrize("code", ["'sAbc", "Één", "A B", "A?#", "%2f"])
async def test_encoded_area_path(api, code):
    api.get(
        f"http://v0.ovapi.nl/stopareacode/{quote(code, safe='')}/departures",
        json={code: {}},
    )
    async with api.create_session(asyncio.get_running_loop()) as session:
        assert await OvapiClient(session).fetch_area(code) == {}
    assert api.call_count == 1
    assert api.mock_calls[0][1].host == "v0.ovapi.nl"
    assert not api.mock_calls[0][1].query_string
    assert not api.mock_calls[0][1].fragment


@pytest.mark.parametrize(
    "code,status,error",
    [
        ("../", 200, "invalid_area"),
        ("AbC01", 404, "unknown_area"),
        ("AbC01", 503, "cannot_connect"),
    ],
)
async def test_area_transport_errors(api, code, status, error):
    api.get("http://v0.ovapi.nl/stopareacode/AbC01/departures", status=status)
    async with api.create_session(asyncio.get_running_loop()) as session:
        with pytest.raises(ApiError, match=error):
            await OvapiClient(session).fetch_area(code)
    assert api.call_count == (0 if code == "../" else 1)


@pytest.mark.parametrize(
    "encoding,body,error",
    [
        ("br", b"not accepted", "invalid_data"),
        ("gzip", b"broken", "invalid_data"),
        ("gzip", gzip.compress(b"{}")[:-3], "invalid_data"),
        ("gzip", gzip.compress(b"{}") + b"trailing", "invalid_data"),
        ("gzip", gzip.compress(b"x" * (MAX_RESPONSE_BYTES + 1)), "response_too_large"),
    ],
)
async def test_bounded_decompression(api, encoding, body, error):
    api.get(
        "http://v0.ovapi.nl/stopareacode/AbC01/departures",
        content=body,
        headers={"Content-Encoding": encoding},
    )
    async with api.create_session(asyncio.get_running_loop()) as session:
        with pytest.raises(ApiError, match=error):
            await OvapiClient(session).fetch_area("AbC01")
