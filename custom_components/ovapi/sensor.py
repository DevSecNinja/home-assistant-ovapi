"""Recorder-safe operational status; departure boards are deliberately not state."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .combined import is_combined, source_ids, source_label
from .const import COMBINED_CONTEXT, CONF_STOP, CONF_WALK, DOMAIN
from .coordinator import OvapiCoordinator

if TYPE_CHECKING:
    from . import OvapiConfigEntry

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class OvapiInsightDescription(SensorEntityDescription):
    value_fn: Callable[[OvapiConfigEntry], int]


WALKING_DURATION = OvapiInsightDescription(
    key="walking_duration",
    translation_key="walking_duration",
    device_class=SensorDeviceClass.DURATION,
    native_unit_of_measurement=UnitOfTime.MINUTES,
    value_fn=lambda entry: entry.options.get(CONF_WALK, 0),
)
COMBINED_INSIGHTS = (
    OvapiInsightDescription(
        key="configured_sources",
        translation_key="configured_sources",
        value_fn=lambda entry: len(source_ids(entry)),
    ),
    OvapiInsightDescription(
        key="ready_sources",
        translation_key="ready_sources",
        value_fn=lambda entry: sum(
            status == "ready"
            for status in entry.runtime_data.source_statuses(entry).values()
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OvapiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    descriptions = (
        (WALKING_DURATION, *COMBINED_INSIGHTS)
        if is_combined(entry)
        else (WALKING_DURATION,)
    )
    async_add_entities(
        [
            OvapiStatusSensor(entry),
            *(OvapiInsightSensor(entry, description) for description in descriptions),
        ]
    )


def device_info(entry: OvapiConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.data["name"],
        entry_type=DeviceEntryType.SERVICE,
        manufacturer="OVAPI",
        model=(
            "Manual combination"
            if is_combined(entry)
            else f"Timing point {entry.data[CONF_STOP]}"
        ),
        configuration_url=(
            "https://github.com/DevSecNinja/home-assistant-ovapi#status-and-data"
        ),
    )


class OvapiInsightSensor(CoordinatorEntity[OvapiCoordinator], SensorEntity):
    """Read-only local values, without polling ownership or board capabilities."""

    entity_description: OvapiInsightDescription
    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, entry: OvapiConfigEntry, description: OvapiInsightDescription
    ) -> None:
        super().__init__(entry.runtime_data, COMBINED_CONTEXT)
        self._entry = entry
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = device_info(entry)

    @property
    def available(self) -> bool:
        """Configuration and source health remain useful during feed outages."""
        return True

    @property
    def native_value(self) -> int:
        return self.entity_description.value_fn(self._entry)

    async def async_update(self) -> None:
        self._handle_coordinator_update()


class OvapiStatusSensor(CoordinatorEntity[OvapiCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "board"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["ready", "stale"]

    def __init__(self, entry: OvapiConfigEntry) -> None:
        super().__init__(
            entry.runtime_data, COMBINED_CONTEXT if is_combined(entry) else None
        )
        self._entry = entry
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = device_info(entry)

    @property
    def capability_attributes(self) -> dict[str, Any]:
        attributes = {
            **(super().capability_attributes or {}),
            "contract_version": 1,
            "board_id": self._entry.entry_id,
        }
        if is_combined(self._entry):
            statuses = self.coordinator.source_statuses(self._entry)
            attributes.update(
                source_entry_ids=source_ids(self._entry),
                source_count=len(statuses),
                unavailable_sources=[
                    source_label(self.hass, source)
                    for source, status in statuses.items()
                    if status == "unavailable"
                ],
            )
        return attributes

    @property
    def suggested_object_id(self) -> str:
        """Keep the original entity-ID suffix while clarifying the visible name."""
        return "departure_board"

    @property
    def available(self) -> bool:
        return self.coordinator.entry_status(self._entry) != "unavailable"

    @property
    def native_value(self) -> str:
        return self.coordinator.entry_status(self._entry)

    async def async_update(self) -> None:
        if is_combined(self._entry):
            self._handle_coordinator_update()
        else:
            await super().async_update()
