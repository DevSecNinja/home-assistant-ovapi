"""OVAPI departures with a shared request budget and transient source data."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .client import ApiError
from .const import CONF_STOP, DOMAIN
from .coordinator import OvapiCoordinator, get_coordinator
from .websocket import async_register_websocket

type OvapiConfigEntry = ConfigEntry[OvapiCoordinator]
PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register connection-local subscription commands once, without fetching."""
    async_register_websocket(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: OvapiConfigEntry) -> bool:
    coordinator = get_coordinator(hass)
    coordinator.register(entry)
    try:
        await coordinator.async_validate(entry.data[CONF_STOP])
    except ApiError as err:
        raise ConfigEntryNotReady(
            translation_domain="ovapi", translation_key=err.code
        ) from None
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OvapiConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    entry.runtime_data.unregister(entry)
    return True


async def async_update_options(hass: HomeAssistant, entry: OvapiConfigEntry) -> None:
    """Filters and walking time change locally; preserve source age and budget."""
    coordinator = entry.runtime_data
    coordinator.async_set_updated_data(coordinator.statuses())
