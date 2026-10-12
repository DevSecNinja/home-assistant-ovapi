"""Favourite setup, options and reconfiguration through Home Assistant."""

import asyncio
import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

import probatio as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_NAME
from homeassistant.core import HassJob, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector
from homeassistant.helpers.event import async_call_later
from homeassistant.util import dt as dt_util

from .client import ApiError, valid_stop
from .const import (
    CONF_DESTINATION,
    CONF_LINES,
    CONF_STOP,
    CONF_TRANSPORTS,
    CONF_WALK,
    DOMAIN,
    RETENTION_SECONDS,
    SUPPORTED_TRANSPORTS,
)
from .coordinator import CachedLookup, get_coordinator, identity
from .discovery import MAX_LOOKUPS, MAX_SEARCH_RESULTS, TimingPoint, search_areas


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
            vol.Optional(
                CONF_TRANSPORTS,
                default=defaults.get(CONF_TRANSPORTS, list(SUPPORTED_TRANSPORTS)),
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=list(SUPPORTED_TRANSPORTS),
                    multiple=True,
                    translation_key="transport",
                    mode=selector.SelectSelectorMode.LIST,
                )
            ),
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
            CONF_TRANSPORTS: sorted(
                set(user_input.get(CONF_TRANSPORTS, SUPPORTED_TRANSPORTS))
            ),
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


def valid_transports(value: Any) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(
            isinstance(mode, str) and mode in SUPPORTED_TRANSPORTS for mode in value
        )
    )


class OvapiConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._key = ""
        self._query = ""
        self._picked_name = ""
        self._lookup_task: asyncio.Task[None] | None = None
        self._lookup_error: str | None = None
        self._expiry_cancel: Callable[[], None] | None = None
        self._expired = False
        self._search_started = False
        self._reserved = False
        self._notify_cancel: Callable[[], None] | None = None
        self._notify_until = 0.0
        self._notify_delay = 1.0
        self._manual_input: dict[str, Any] | None = None
        self._manual_step = "manual"

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OvapiOptionsFlow:
        return OvapiOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return await self._step("user", user_input)
        return self._menu("user")

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return await self._step("reconfigure", user_input)
        return self._menu("reconfigure")

    def _menu(self, step: str) -> ConfigFlowResult:
        if len(self._async_in_progress()) >= MAX_LOOKUPS:
            return self.async_abort(reason="discovery_busy")
        return self.async_show_menu(step_id=step, menu_options=["search", "manual"])

    async def async_step_manual(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._clear_choices()
        return await self._step("manual", user_input)

    async def _load(self) -> None:
        try:
            coordinator = get_coordinator(self.hass)
            if self._manual_input is not None:
                current = (
                    self._get_reconfigure_entry()
                    if self.source == config_entries.SOURCE_RECONFIGURE
                    else None
                )
                await coordinator.async_validate(
                    self._manual_input[CONF_STOP].strip(),
                    reservation_id=self.flow_id,
                    replacing=current.entry_id if current else None,
                    interactive=True,
                )
            else:
                await coordinator.async_lookup(self._key)
        except ApiError as err:
            self._lookup_error = err.code

    async def _progress(self, step: str, next_step: str) -> ConfigFlowResult:
        if self._lookup_task is None:
            self._lookup_error = None
            self._lookup_task = self.hass.async_create_background_task(
                self._load(), "ovapi configuration lookup"
            )
        elif self._lookup_task.done():
            self._lookup_task = None
            lookup = get_coordinator(self.hass).lookup(self._key)
            if lookup is not None and not self._expired and step != "validate":
                self._arm_expiry(lookup)
            self._notify_until = time.monotonic() + RETENTION_SECONDS
            self._notify_delay = 1.0
            self._schedule_progress_notification()
            return self.async_show_progress_done(next_step_id=next_step)
        action, resume_at = get_coordinator(self.hass).lookup_wait()
        return self.async_show_progress(
            step_id=step,
            progress_action=action,
            description_placeholders={
                "resume_at": dt_util.as_local(resume_at).strftime("%Y-%m-%d %H:%M:%S")
            },
            progress_task=self._lookup_task,
        )

    async def async_step_validate(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._progress("validate", "validated")

    async def async_step_validated(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._ack_progress()
        entered = self._manual_input
        self._manual_input = None
        return await self._step(self._manual_step, entered, validated=True)

    async def async_step_directory(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._key = ""
        self._search_started = True
        return await self._progress("directory", "search")

    async def async_step_details(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return await self._progress("details", "point")

    async def async_step_search(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._ack_progress()
        if self._expired:
            return await self.async_step_retry()
        if user_input and user_input.get("manual"):
            return await self.async_step_manual()
        if not self._search_started:
            return await self.async_step_directory()
        lookup = get_coordinator(self.hass).lookup("")
        if user_input is not None:
            self._query = user_input["query"].strip()
            if len(self._query) < 2:
                return self._search_form({"query": "short_query"})
            if lookup is not None:
                return await self.async_step_area()
            return await self.async_step_directory()
        if lookup is None and self._lookup_error is None:
            return await self.async_step_directory()
        errors = {"base": self._lookup_error} if self._lookup_error else {}
        return self._search_form(errors)

    def _search_form(self, errors: dict[str, str]) -> ConfigFlowResult:
        return self.async_show_form(
            step_id="search",
            data_schema=vol.Schema(
                {
                    vol.Optional("query", default=self._query): vol.All(
                        cv.string, vol.Length(max=100)
                    ),
                    vol.Optional("manual", default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_area(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        lookup = get_coordinator(self.hass).lookup("")
        if self._expired or lookup is None:
            self._lookup_error = "selection_expired"
            return await self.async_step_retry()
        if user_input and user_input.get("search_again"):
            return self._search_form({})
        matches = search_areas(lookup.areas, self._query)
        if not matches or len(matches) > MAX_SEARCH_RESULTS:
            return self._search_form(
                {"base": "no_matches" if not matches else "too_many_matches"}
            )
        if user_input is not None:
            chosen = next(
                (area for area in matches if area.code == user_input.get("area")), None
            )
            if chosen is None:
                return self._search_form({"base": "selection_expired"})
            self._key = chosen.code
            self._picked_name = chosen.name
            return await self.async_step_details()
        return self.async_show_form(
            step_id="area",
            data_schema=vol.Schema(
                {
                    vol.Optional("area"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                selector.SelectOptionDict(
                                    value=area.code, label=area.label
                                )
                                for area in matches
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                    vol.Optional("search_again", default=False): bool,
                }
            ),
        )

    async def async_step_point(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._ack_progress()
        lookup = get_coordinator(self.hass).lookup(self._key)
        if self._expired or lookup is None or self._lookup_error:
            return await self.async_step_retry()
        if not lookup.points:
            self._lookup_error = "no_points"
            return await self.async_step_retry()
        if user_input is not None:
            try:
                self._reserved = True
                get_coordinator(self.hass).select_point(
                    self._key,
                    user_input[CONF_STOP],
                    reservation_id=self.flow_id,
                    replacing=self.context.get("entry_id")
                    if self.source == config_entries.SOURCE_RECONFIGURE
                    else None,
                )
            except ApiError as err:
                self._lookup_error = err.code
                return await self.async_step_retry()
        return await self._step("point", user_input, lookup.points)

    async def async_step_retry(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            action = user_input["action"]
            if action == "retry":
                get_coordinator(self.hass).discard_lookup(self._key)
            self._expired = False
            self._lookup_error = None
            if action == "manual":
                return await self.async_step_manual()
            if action == "search":
                return await self.async_step_search()
            return (
                await self.async_step_details()
                if self._key
                else await self.async_step_directory()
            )
        return self.async_show_form(
            step_id="retry",
            data_schema=vol.Schema(
                {
                    vol.Required("action", default="retry"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["retry", "search", "manual"],
                            translation_key="recovery",
                        )
                    ),
                }
            ),
            errors={
                "base": (
                    "selection_expired"
                    if self._expired
                    else self._lookup_error or "selection_expired"
                )
            },
        )

    @callback
    def _schedule_progress_notification(self) -> None:
        # HA subscribes after the HTTP progress response, so fast tasks can race it.
        self._notify_cancel = async_call_later(
            self.hass,
            self._notify_delay,
            HassJob(self._notify_progress, cancel_on_shutdown=True),
        )

    @callback
    def _notify_progress(self, _now: datetime) -> None:
        self._notify_cancel = None
        if time.monotonic() < self._notify_until:
            self.async_notify_flow_changed()
            self._notify_delay = min(30, self._notify_delay * 2)
            self._schedule_progress_notification()

    @callback
    def _ack_progress(self) -> None:
        if self._notify_cancel is not None:
            self._notify_cancel()
            self._notify_cancel = None

    @callback
    def _arm_expiry(self, lookup: CachedLookup) -> None:
        # The first directory deadline also bounds copied selected-area names.
        if self._expiry_cancel is None:
            seconds = min(
                lookup.monotonic_expiry - time.monotonic(),
                (lookup.expires_at - dt_util.utcnow()).total_seconds(),
            )
            self._expiry_cancel = async_call_later(
                self.hass,
                max(0, seconds),
                HassJob(self._expire_choices, cancel_on_shutdown=True),
            )

    @callback
    def _expire_choices(self, _now: datetime) -> None:
        self._clear_choices()
        self._expired = True
        if self._lookup_task is not None and not self._lookup_task.done():
            self._lookup_task.cancel()
        self.async_notify_flow_changed()

    @callback
    def _clear_choices(self) -> None:
        self._ack_progress()
        if self._reserved:
            get_coordinator(self.hass).release_stop(self.flow_id)
            self._reserved = False
        if self._expiry_cancel is not None:
            self._expiry_cancel()
            self._expiry_cancel = None
        self._picked_name = ""
        if self.cur_step is not None:
            self.cur_step.pop("data_schema", None)

    @callback
    def async_remove(self) -> None:
        self._clear_choices()
        if self._lookup_task is not None and not self._lookup_task.done():
            self._lookup_task.cancel()
        self._lookup_task = None
        self._manual_input = None

    async def _step(
        self,
        step: str,
        user_input: dict[str, Any] | None,
        points: dict[str, TimingPoint] | None = None,
        *,
        validated: bool = False,
    ) -> ConfigFlowResult:
        current = (
            self._get_reconfigure_entry()
            if self.source == config_entries.SOURCE_RECONFIGURE
            else None
        )
        defaults = {**current.data, **current.options} if current else {}
        if step == "point" and current is None:
            defaults[CONF_NAME] = self._picked_name[:80]
        errors: dict[str, str] = {}
        if user_input is not None:
            if not user_input[CONF_NAME].strip():
                errors[CONF_NAME] = "invalid_name"
            elif not valid_walk(user_input.get(CONF_WALK, 0)):
                errors[CONF_WALK] = "invalid_walk"
            elif not valid_transports(
                user_input.get(CONF_TRANSPORTS, list(SUPPORTED_TRANSPORTS))
            ):
                errors[CONF_TRANSPORTS] = "invalid_transport"
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
                    if points is None:
                        self._reserved = True
                        coordinator = get_coordinator(self.hass)
                        if validated and self._lookup_error is not None:
                            raise ApiError(self._lookup_error)
                        coordinator.reserve_stop(
                            self.flow_id,
                            data[CONF_STOP],
                            current.entry_id if current else None,
                        )
                        if coordinator.status(data[CONF_STOP]) == "unavailable":
                            self._manual_input = dict(user_input)
                            self._manual_step = step
                            return await self.async_step_validate()
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
                        title=data[CONF_NAME],
                        data=data,
                        options=options,
                        description="default",
                    )
            defaults = user_input
        form_schema = schema(defaults)
        if points is not None:
            fields = dict(form_schema.schema)
            fields.pop(CONF_STOP)
            point_selector = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        selector.SelectOptionDict(value=point.code, label=point.label)
                        for point in points.values()
                    ],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
            form_schema = vol.Schema(
                {vol.Required(CONF_STOP): point_selector, **fields}
            )
        return self.async_show_form(
            step_id=step,
            data_schema=form_schema,
            errors=errors,
            description_placeholders={
                "observed_modes": ", ".join(
                    sorted(
                        {
                            departure.transport
                            for point in points.values()
                            for departure in point.departures
                        }
                    )
                )
                or "-"
                if points is not None
                else "-",
            },
        )


class OvapiOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if not valid_walk(user_input.get(CONF_WALK, 0)) or not valid_transports(
                user_input.get(CONF_TRANSPORTS, list(SUPPORTED_TRANSPORTS))
            ):
                return self._form(
                    (
                        {CONF_WALK: "invalid_walk"}
                        if not valid_walk(user_input.get(CONF_WALK, 0))
                        else {CONF_TRANSPORTS: "invalid_transport"}
                    ),
                    user_input,
                )
            entry = self.config_entry
            options = {
                CONF_TRANSPORTS: sorted(
                    set(user_input.get(CONF_TRANSPORTS, SUPPORTED_TRANSPORTS))
                ),
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
        return self._form(errors, user_input)

    def _form(
        self, errors: dict[str, str], defaults: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_form(
            step_id="init",
            data_schema=schema(
                {**self.config_entry.options, **(defaults or {})}, options=True
            ),
            errors=errors,
            description_placeholders={
                "observed_modes": ", ".join(
                    get_coordinator(self.hass).observed_transports(
                        self.config_entry.data[CONF_STOP]
                    )
                )
                or "-",
            },
        )
