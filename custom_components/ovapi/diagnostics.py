"""Never include entry configuration, locations, payloads or raw exceptions."""

from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant

from .const import (
    DISCOVERY_REQUESTS,
    DISCOVERY_WINDOW_SECONDS,
    MAX_STOPS,
    POLL_SECONDS,
    RETENTION_SECONDS,
)

if TYPE_CHECKING:
    from . import OvapiConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OvapiConfigEntry
) -> dict[str, Any]:
    return {
        "contract_version": 1,
        "poll_seconds": POLL_SECONDS,
        "discovery_requests_per_window": DISCOVERY_REQUESTS,
        "discovery_window_seconds": DISCOVERY_WINDOW_SECONDS,
        "retention_seconds": RETENTION_SECONDS,
        "maximum_distinct_stops": MAX_STOPS,
        "configured_distinct_stops": entry.runtime_data.stop_count,
        "request_count": entry.runtime_data.request_count,
        "transport": "unencrypted_http",
        "departure_data": "excluded",
    }
