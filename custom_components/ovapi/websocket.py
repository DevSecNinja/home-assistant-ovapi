"""Authenticated, entity-authorized transient board subscriptions."""

import logging
from typing import Any

import probatio as vol
from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components import websocket_api
from homeassistant.components.websocket_api.connection import ActiveConnection
from homeassistant.components.websocket_api.decorators import websocket_command
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .coordinator import get_coordinator


class BoardLogFilter(logging.Filter):
    """Core logs outgoing/queued frames, including coalesced batches, at debug."""

    def filter(self, record: logging.LogRecord) -> bool:
        text = record.getMessage()
        if '"board_id"' in text and '"departures"' in text:
            record.msg = "OVAPI departure payload omitted by retention policy"
            record.args = ()
            record.exc_info = None
            record.exc_text = None
        return True


@callback
def async_register_websocket(hass: HomeAssistant) -> None:
    logger = logging.getLogger("homeassistant.components.websocket_api.http.connection")
    if not any(isinstance(item, BoardLogFilter) for item in logger.filters):
        # Keep the guard for the process lifetime, including already queued frames.
        logger.addFilter(BoardLogFilter())
    websocket_api.async_register_command(hass, websocket_subscribe)


@websocket_command(
    {vol.Required("type"): "ovapi/subscribe", vol.Required("entity_id"): cv.entity_id}
)
@callback
def websocket_subscribe(
    hass: HomeAssistant,
    connection: ActiveConnection,
    msg: dict[str, Any],
) -> None:
    registry = er.async_get(hass)
    entity = registry.async_get(msg["entity_id"])
    if (
        entity is None
        or entity.platform != DOMAIN
        or entity.domain != "sensor"
        or entity.disabled
        or entity.config_entry_id is None
    ):
        connection.send_error(msg["id"], "not_found", "OVAPI board not found")
        return
    if not connection.user.permissions.check_entity(entity.entity_id, POLICY_READ):
        connection.send_error(msg["id"], "unauthorized", "Not authorized")
        return
    entry = hass.config_entries.async_get_entry(entity.config_entry_id)
    if entry is None:
        connection.send_error(msg["id"], "not_found", "OVAPI entry not found")
        return
    coordinator = get_coordinator(hass)
    entity_registry_id = entity.id

    @callback
    def send_snapshot() -> None:
        current = registry.async_get(entity_registry_id)
        if current is None or current.disabled:
            connection.subscriptions.pop(msg["id"])()
            connection.send_error(msg["id"], "not_found", "OVAPI board removed")
            return
        if not connection.user.permissions.check_entity(current.entity_id, POLICY_READ):
            connection.subscriptions.pop(msg["id"])()
            connection.send_error(msg["id"], "unauthorized", "Not authorized")
            return
        connection.send_event(msg["id"], coordinator.snapshot(entry, current.entity_id))

    connection.subscriptions[msg["id"]] = coordinator.async_add_listener(send_snapshot)
    connection.send_result(msg["id"])
    send_snapshot()
