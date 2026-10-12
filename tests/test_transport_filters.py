"""Mode filtering remains local and follows new lines without changing card v1."""

from copy import deepcopy

import pytest
from homeassistant import config_entries

from custom_components.ovapi.coordinator import get_coordinator, identity

from .test_config_flow import INPUT, finish_progress
from .test_coordinator import tick
from .test_init import make_entry


@pytest.mark.parametrize("value", ["metro", ["rail"], [1], None, []])
async def test_invalid_modes_rejected_in_both_flows(hass, api, value):
    result = await hass.config_entries.flow.async_init(
        "ovapi",
        context={"source": config_entries.SOURCE_USER},
        data={**INPUT, "transport_types": value},
    )
    assert result["errors"] == {"transport_types": "invalid_transport"}
    entry = make_entry(hass)
    result = await hass.config_entries.options.async_init(
        entry.entry_id, data={"transport_types": value}
    )
    assert result["errors"] == {"transport_types": "invalid_transport"}
    assert api.call_count == 0


def test_mode_identity_preserves_legacy_and_canonicalizes():
    original = identity("001", {})
    assert original == '["001", "", ""]'
    for modes in (["bus", "tram", "metro"], ["metro", "tram", "bus"]):
        assert identity("001", {"transport_types": modes}) == original
    assert identity("001", {"transport_types": ["metro"]}) != original
    assert identity("001", {"transport_types": ["bus", "metro"]}) == identity(
        "001", {"transport_types": ["metro", "bus"]}
    )


async def test_metro_filter_follows_new_service_and_options_are_local(
    hass, api, payload, freezer
):
    freezer.move_to("2030-01-15T12:00:00+00:00")
    passes = payload["01234567"]["Passes"]
    record = passes["SYNTHETIC_TRIP"]
    passes["BUS"] = {**record, "TransportType": "BUS"}
    passes["METRO"] = {
        **record,
        "TransportType": "METRO",
        "LinePublicNumber": "50",
        "DestinationName50": "Synthetic North",
    }
    api.get("http://v0.ovapi.nl/tpc/01234567/departures", json=payload)
    result = await hass.config_entries.flow.async_init(
        "ovapi",
        context={"source": config_entries.SOURCE_USER},
        data={**INPUT, "transport_types": ["metro"]},
    )
    result = await finish_progress(hass, result)
    entry = result["result"]
    coordinator = get_coordinator(hass)
    before = coordinator.snapshot(entry, "sensor.test")
    assert before["contract_version"] == 1
    assert [item["line"] for item in before["departures"]] == ["50"]
    assert coordinator.observed_transports("01234567") == ("bus", "metro", "tram")
    assert coordinator.observed_transports("missing") == ()
    changed = deepcopy(payload)
    changed["01234567"]["Passes"]["METRO"].update(
        LinePublicNumber="53", DestinationName50="Synthetic South"
    )
    assert api.call_count == 1
    api.clear_requests()
    api.get("http://v0.ovapi.nl/tpc/01234567/departures", json=changed)
    await tick(hass, freezer, 120)
    await coordinator.async_refresh()
    after = coordinator.snapshot(entry, "sensor.test")
    assert after["board_id"] == before["board_id"]
    assert [item["destination"] for item in after["departures"]] == ["Synthetic South"]
    assert api.call_count == 1
    for options, expected in (
        ({"transport_types": ["bus", "tram", "metro"]}, 3),
        ({"transport_types": ["metro"], "lines": "M53"}, 0),
        (
            {"transport_types": ["metro"], "lines": "53", "destination": "South,North"},
            0,
        ),
        ({"transport_types": ["metro"], "lines": "53", "destination": "south"}, 1),
    ):
        await hass.config_entries.options.async_init(entry.entry_id, data=options)
        assert len(coordinator.snapshot(entry, "sensor.test")["departures"]) == expected
    assert api.call_count == 1


async def test_explicit_all_modes_duplicates_legacy_entry(hass, api):
    make_entry(hass)
    result = await hass.config_entries.flow.async_init(
        "ovapi",
        context={"source": config_entries.SOURCE_USER},
        data={**INPUT, "transport_types": ["bus", "tram", "metro"]},
    )
    assert result["reason"] == "already_configured"
    assert api.call_count == 0


async def test_empty_reconfigure_keeps_entry_and_missing_defaults_mean_all(hass, api):
    entry = make_entry(hass)
    result = await hass.config_entries.flow.async_init(
        "ovapi",
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
        data={**INPUT, "stop_id": "76543210", "transport_types": []},
    )
    assert result["errors"] == {"transport_types": "invalid_transport"}
    assert entry.data["stop_id"] == "01234567"
    for key in result["data_schema"].schema:
        if key == "transport_types":
            assert key.default() == []
    form = await hass.config_entries.options.async_init(entry.entry_id)
    for key in form["data_schema"].schema:
        if key == "transport_types":
            assert set(key.default()) == {"bus", "tram", "metro"}
    assert api.call_count == 0


async def test_persisted_empty_selection_is_not_silently_all(
    hass, api, payload, freezer
):
    freezer.move_to("2030-01-15T12:00:00+00:00")
    entry = make_entry(hass)
    api.get("http://v0.ovapi.nl/tpc/01234567/departures", json=payload)
    coordinator = get_coordinator(hass)
    await coordinator.async_refresh()
    assert len(coordinator.snapshot(entry, "sensor.test")["departures"]) == 1
    hass.config_entries.async_update_entry(entry, options={"transport_types": []})
    assert coordinator.snapshot(entry, "sensor.test")["departures"] == []
    result = await hass.config_entries.options.async_init(
        entry.entry_id, data={"transport_types": [], "walking_minutes": 9}
    )
    assert result["errors"] == {"transport_types": "invalid_transport"}
    assert result["description_placeholders"]["observed_modes"] == "tram"
    assert api.call_count == 1
