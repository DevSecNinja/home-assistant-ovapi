"""Favourite setup, options and reconfiguration through Home Assistant."""

from typing import Any

import probatio as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector

from .client import ApiError, valid_stop
from .const import CONF_DESTINATION, CONF_LINES, CONF_STOP, CONF_WALK, DOMAIN
from .coordinator import get_coordinator, identity


def schema(defaults: dict[str, Any], *, options: bool = False) -> vol.Schema:
    fields: dict[Any, Any] = {}
    if not options:
        fields = {
            vol.Required(CONF_NAME, default=defaults.get(CONF_NAME, "")): vol.All(
                cv.string, vol.Length(min=1, max=80)
            ),
            vol.Required(CONF_STOP, default=defaults.get(CONF_STOP, "")): vol.All(
                cv.string, vol.Match(r"^[0-9]{1,10}$")
            ),
        }
    fields.update(
        {
            vol.Optional(CONF_LINES, default=defaults.get(CONF_LINES, "")): vol.All(
                cv.string, vol.Length(max=160)
            ),
            vol.Optional(
                CONF_DESTINATION, default=defaults.get(CONF_DESTINATION, "")
            ): vol.All(cv.string, vol.Length(max=120)),
            vol.Optional(CONF_WALK, default=defaults.get(CONF_WALK, 0)): (
                selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=120, step=1, mode=selector.NumberSelectorMode.BOX
                    )
                )
            ),
        }
    )
    return vol.Schema(fields)


def split_input(user_input: dict[str, Any]) -> tuple[dict[str, str], dict[str, Any]]:
    return (
        {
            CONF_NAME: user_input[CONF_NAME].strip(),
            CONF_STOP: user_input[CONF_STOP].strip(),
        },
        {
            CONF_LINES: user_input.get(CONF_LINES, "").strip(),
            CONF_DESTINATION: user_input.get(CONF_DESTINATION, "").strip(),
            CONF_WALK: int(user_input.get(CONF_WALK, 0)),
        },
    )


def valid_walk(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0 <= value <= 120
        and value == int(value)
    )


class OvapiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OvapiOptionsFlow:
        return OvapiOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._step("user", user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._step("reconfigure", user_input)

    async def _step(
        self, step: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        current = self._get_reconfigure_entry() if step == "reconfigure" else None
        defaults = {**current.data, **current.options} if current else {}
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input[CONF_NAME].strip():
                errors[CONF_NAME] = "invalid_name"
            elif not valid_walk(user_input.get(CONF_WALK, 0)):
                errors[CONF_WALK] = "invalid_walk"
            elif not valid_stop(user_input[CONF_STOP].strip()):
                errors[CONF_STOP] = "invalid_stop"
            else:
                data, options = split_input(user_input)
                unique_id = identity(data[CONF_STOP], options)
                await self.async_set_unique_id(unique_id)
                for entry in self._async_current_entries():
                    if entry.unique_id == unique_id and entry is not current:
                        return self.async_abort(reason="already_configured")
                try:
                    await get_coordinator(self.hass).async_validate(data[CONF_STOP])
                except ApiError as err:
                    errors["base"] = err.code
                else:
                    if current is not None:
                        self.hass.config_entries.async_update_entry(
                            current, unique_id=unique_id, title=data[CONF_NAME]
                        )
                        return self.async_update_reload_and_abort(
                            current, data=data, options=options
                        )
                    return self.async_create_entry(
                        title=data[CONF_NAME], data=data, options=options
                    )
            defaults = user_input
        return self.async_show_form(
            step_id=step, data_schema=schema(defaults), errors=errors
        )


class OvapiOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not valid_walk(user_input.get(CONF_WALK, 0)):
                return self.async_show_form(
                    step_id="init",
                    data_schema=schema(dict(self.config_entry.options), options=True),
                    errors={CONF_WALK: "invalid_walk"},
                )
            entry = self.config_entry
            options = {
                CONF_LINES: user_input.get(CONF_LINES, "").strip(),
                CONF_DESTINATION: user_input.get(CONF_DESTINATION, "").strip(),
                CONF_WALK: int(user_input.get(CONF_WALK, 0)),
            }
            unique_id = identity(entry.data[CONF_STOP], options)
            if any(
                other.entry_id != entry.entry_id and other.unique_id == unique_id
                for other in self.hass.config_entries.async_entries(DOMAIN)
            ):
                errors["base"] = "already_configured"
            else:
                self.hass.config_entries.async_update_entry(entry, unique_id=unique_id)
                return self.async_create_entry(data=options)
        return self.async_show_form(
            step_id="init",
            data_schema=schema(dict(self.config_entry.options), options=True),
            errors=errors,
        )
