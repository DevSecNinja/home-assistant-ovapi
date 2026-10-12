"""Recorder-safe operational status; departure boards are deliberately not state."""

from typing import TYPE_CHECKING

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_STOP, DOMAIN
from .coordinator import OvapiCoordinator

if TYPE_CHECKING:
    from . import OvapiConfigEntry

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OvapiConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities([OvapiStatusSensor(entry)])


class OvapiStatusSensor(CoordinatorEntity[OvapiCoordinator], SensorEntity):
    _attr_has_entity_name = True
    _attr_translation_key = "board"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["ready", "stale"]

    def __init__(self, entry: OvapiConfigEntry) -> None:
        super().__init__(entry.runtime_data)
        self._stop = entry.data[CONF_STOP]
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data["name"],
            entry_type=DeviceEntryType.SERVICE,
            manufacturer="OVAPI",
            model=f"Timing point {self._stop}",
            configuration_url=(
                "https://github.com/DevSecNinja/home-assistant-ovapi#status-and-data"
            ),
        )
        self._attr_extra_state_attributes = {
            "contract_version": 1,
            "board_id": entry.entry_id,
        }

    @property
    def suggested_object_id(self) -> str:
        """Keep the original entity-ID suffix while clarifying the visible name."""
        return "departure_board"

    @property
    def available(self) -> bool:
        return self.coordinator.status(self._stop) != "unavailable"

    @property
    def native_value(self) -> str:
        return self.coordinator.status(self._stop)
