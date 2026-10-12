"""Test setup/unload and entity registry behavior through Home Assistant."""

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ovapi.coordinator import identity


def make_entry(hass, stop="01234567", name="Amsterdam Amstel", **options):
    entry = MockConfigEntry(
        domain="ovapi",
        title=name,
        unique_id=identity(stop, options),
        data={"stop_id": stop, "name": name},
        options=options,
    )
    entry.add_to_hass(hass)
    return entry


async def setup_entry(hass, api, payload, **options):
    entry = make_entry(hass, **options)
    api.get("http://v0.ovapi.nl/tpc/01234567/departures", json=payload)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_unload(hass, api, payload, freezer):
    freezer.move_to("2030-01-15T12:00:00+00:00")
    entry = await setup_entry(hass, api, payload)
    assert entry.state is ConfigEntryState.LOADED
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", "ovapi", entry.entry_id)
    state = hass.states.get(entity_id)
    assert state.state == "ready"
    assert state.attributes["board_id"] == entry.entry_id
    assert "departures" not in state.attributes
    device = dr.async_get(hass).async_get_device_by_identifier(
        ("ovapi", entry.entry_id), entry.entry_id
    )
    assert device.name == "Amsterdam Amstel"
    assert api.call_count == 1
    coordinator = entry.runtime_data
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert coordinator.snapshot(entry, entity_id)["departures"] == []


async def test_setup_error(hass, api):
    entry = make_entry(hass)
    api.get("http://v0.ovapi.nl/tpc/01234567/departures", status=503)
    assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert api.call_count == 1


async def test_unload_failure_preserves_runtime(hass, api, payload):
    entry = await setup_entry(hass, api, payload)
    coordinator = entry.runtime_data
    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ):
        assert not await hass.config_entries.async_unload(entry.entry_id)
    assert coordinator.status("01234567") == "ready"
