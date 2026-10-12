"""Diagnostics contain operational metadata, not source or user locations."""

import json

from custom_components.ovapi.diagnostics import async_get_config_entry_diagnostics

from .test_init import setup_entry


async def test_diagnostics(hass, api, payload, freezer):
    freezer.move_to("2030-01-15T12:00:00+00:00")
    entry = await setup_entry(hass, api, payload, lines="X1")
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["request_count"] == 1
    assert diagnostics["configured_distinct_stops"] == 1
    assert diagnostics["retention_seconds"] == 1740
    serialized = json.dumps(diagnostics)
    for excluded in ("01234567", "Amsterdam", "X1", "Synthetic", entry.entry_id):
        assert excluded not in serialized
