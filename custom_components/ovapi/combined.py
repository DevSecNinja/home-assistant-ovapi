"""Stable leaf references and stateless manual board composition."""

import json
from datetime import datetime
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONF_ENTRY_TYPE, CONF_SOURCES, CONF_WALK, DOMAIN, MAX_DEPARTURES

if TYPE_CHECKING:
    from .coordinator import BoardPayload, Status


def is_combined(entry: ConfigEntry) -> bool:
    return entry.data.get(CONF_ENTRY_TYPE) == "combined"


def leaf_entry(hass: HomeAssistant, entry_id: str) -> ConfigEntry | None:
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN or is_combined(entry):
        return None
    return entry


def source_entity(hass: HomeAssistant, entry_id: str) -> er.RegistryEntry | None:
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, entry_id)
    return registry.async_get(entity_id) if entity_id else None


def source_label(hass: HomeAssistant, entry_id: str) -> str:
    entry = leaf_entry(hass, entry_id)
    if entry is None:
        return entry_id
    entity = source_entity(hass, entry_id)
    return f"{entry.title} ({entity.entity_id if entity else entry_id})"


def combined_identity(sources: list[str]) -> str:
    return json.dumps(["combined", *sorted(sources)])


def combine_snapshots(
    entry: ConfigEntry,
    entity_id: str,
    status: Status,
    sources: list[BoardPayload],
) -> BoardPayload:
    """No retained copy: every snapshot borrows the original source deadlines."""
    rows = {
        tuple(sorted(departure.items())): departure
        for source in sources
        for departure in source["departures"]
    }
    return {
        "contract_version": 1,
        "board_id": entry.entry_id,
        "entity_id": entity_id,
        "stop": {"id": entry.entry_id, "name": entry.data["name"]},
        "status": status,
        "fetched_at": min(
            (source["fetched_at"] for source in sources if source["fetched_at"]),
            key=datetime.fromisoformat,
            default=None,
        ),
        "expires_at": min(
            (source["expires_at"] for source in sources if source["expires_at"]),
            key=datetime.fromisoformat,
            default=None,
        ),
        "walking_minutes": entry.options.get(CONF_WALK, 0),
        "departures": sorted(
            rows.values(),
            key=lambda row: datetime.fromisoformat(
                row["expected_at"] or row["scheduled_at"]
            ),
        )[:MAX_DEPARTURES],
    }


def source_ids(entry: ConfigEntry) -> list[str]:
    return list(entry.options[CONF_SOURCES])
