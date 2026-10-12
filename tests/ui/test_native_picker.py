"""Actual HA frontend with synthetic upstream data; no live user's instance."""

import asyncio
import copy
import json
import os
import time
from datetime import timedelta
from pathlib import Path

import pytest
from aiohttp.web_log import AccessLogger
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.ovapi.coordinator import get_coordinator
from tests.test_coordinator import tick
from tests.test_discovery import DIRECTORY
from tests.test_discovery_coordinator import settle

pytestmark = [pytest.mark.frontend, pytest.mark.enable_socket]

LABELS = {
    "en": {
        "find": "Find a stop by name",
        "find_other": "Find a different stop by name",
        "directory": "Loading stop names",
        "search_title": "Find a stop",
        "search": "Search",
        "area": "Choose a stop",
        "continue": "Continue",
        "point": "Choose your stop sign",
        "no_matches": "No matching stop metadata was found.",
        "retry": "Stop lookup needs attention",
        "details": "Loading stop directions",
        "reconfigure": "Change the favourite",
    },
    "nl": {
        "find": "Halte zoeken op naam",
        "find_other": "Andere halte zoeken op naam",
        "directory": "Haltenamen laden",
        "search_title": "Halte zoeken",
        "search": "Zoeken",
        "area": "Halte kiezen",
        "continue": "Doorgaan",
        "point": "Kies je haltebord",
        "no_matches": "Geen passende haltegegevens gevonden.",
        "retry": "Halte zoeken vraagt aandacht",
        "details": "Halterichtingen laden",
        "reconfigure": "Favoriet wijzigen",
    },
}


@pytest.mark.parametrize("language", ["en", "nl"])
async def test_native_picker(
    hass,
    hass_client,
    hass_admin_user,
    hass_storage,
    api,
    payload,
    freezer,
    tmp_path,
    monkeypatch,
    language,
):
    from playwright.async_api import async_playwright

    # Freezegun's localtime omits tm_gmtoff; keep access logging functional.
    monkeypatch.setattr(AccessLogger, "_get_local_time", staticmethod(dt_util.utcnow))

    hass_storage["onboarding"] = {
        "version": 4,
        "key": "onboarding",
        "data": {"done": ["user", "core_config", "integration", "analytics"]},
    }
    assert await async_setup_component(hass, "frontend", {})
    assert await async_setup_component(hass, "ovapi", {})
    client = await hass_client()
    url = str(client.make_url("/")).rstrip("/")
    refresh_token = await hass.auth.async_create_refresh_token(
        hass_admin_user, client_id=url + "/", access_token_expiration=timedelta(days=1)
    )
    labels = LABELS[language]
    artifacts = Path(os.environ.get("OVAPI_UI_ARTIFACTS", str(tmp_path))) / language
    await hass.async_add_executor_job(
        lambda: artifacts.mkdir(parents=True, exist_ok=True)
    )
    api.get("http://v0.ovapi.nl/stopareacode/", json=DIRECTORY)
    target_board = copy.deepcopy(payload["01234567"])
    target_board["Passes"]["SYNTHETIC_TRIP"].update(
        {
            "LinePublicNumber": "X2",
            "DestinationName50": "Synthetic opposite direction",
        }
    )
    api.get(
        "http://v0.ovapi.nl/stopareacode/AbC01/departures",
        json={"AbC01": {**payload, "76543210": target_board}},
    )
    api.get("http://v0.ovapi.nl/tpc/01234567/departures", json=payload)
    api.get(
        "http://v0.ovapi.nl/tpc/76543210/departures", json={"76543210": target_board}
    )
    tokens = {
        "hassUrl": url,
        "clientId": url + "/",
        "access_token": hass.auth.async_create_access_token(refresh_token),
        "refresh_token": refresh_token.token,
        "token_type": "Bearer",
        "expires_in": 86400,
        "expires": (time.time() + 86400) * 1000,
    }
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900}, locale=language
        )
        await context.add_init_script(
            f"localStorage.setItem('hassTokens', {json.dumps(json.dumps(tokens))});"
            "localStorage.setItem('selectedLanguage', "
            f"{json.dumps(json.dumps(language))});"
        )
        # Only HA itself is allowed; tests must not contact source/CDN services.
        await context.route(
            "**/*",
            lambda route: (
                route.continue_()
                if route.request.url.startswith(url)
                else route.abort()
            ),
        )
        page = await context.new_page()

        async def localized(key):
            await page.wait_for_function(
                """({key, language}) => {
                    const hass = document.querySelector('home-assistant')?.hass;
                    return hass?.locale?.language === language && hass.localize(key);
                }""",
                arg={"key": key, "language": language},
            )
            value = await page.evaluate(
                "(key) => document.querySelector('home-assistant').hass.localize(key)",
                key,
            )
            assert value
            return value

        progress_subscribed = asyncio.Event()
        progress_changed = asyncio.Event()

        def observe_socket(socket):
            subscription_ids = set()

            def sent(frame):
                messages = json.loads(frame)
                for message in messages if isinstance(messages, list) else [messages]:
                    if (
                        isinstance(message, dict)
                        and message.get("type") == "subscribe_events"
                        and message.get("event_type") == "data_entry_flow_progressed"
                    ):
                        subscription_ids.add(message["id"])

            def received(frame):
                messages = json.loads(frame)
                for message in messages if isinstance(messages, list) else [messages]:
                    if not isinstance(message, dict):
                        continue
                    event = message.get("event")
                    if (
                        message.get("type") == "event"
                        and isinstance(event, dict)
                        and event.get("event_type") == "data_entry_flow_progressed"
                    ):
                        progress_changed.set()
                    if (
                        message.get("type") == "result"
                        and message.get("id") in subscription_ids
                        and message.get("success")
                    ):
                        subscription_ids.discard(message["id"])
                        progress_subscribed.set()

            socket.on("framesent", sent)
            socket.on("framereceived", received)

        page.on("websocket", observe_socket)
        try:
            await page.goto(url + "/config/integrations/dashboard")
            await page.wait_for_function(
                "document.querySelector('home-assistant')?.hass?.connected",
                timeout=30000,
            )
            await page.wait_for_function(
                """(language) =>
                    document.querySelector('home-assistant').hass.locale.language
                    === language""",
                arg=language,
            )
            await page.get_by_role(
                "button",
                name=await localized("ui.panel.config.integrations.add_integration"),
                exact=True,
            ).last.click()
            await page.locator("dialog-add-integration input").fill("OVAPI")
            await (
                page.locator("dialog-add-integration")
                .get_by_text("OVAPI", exact=True)
                .click()
            )
            await page.get_by_text(labels["find"], exact=True).click()
            await page.get_by_text(labels["directory"], exact=True).wait_for()
            await asyncio.wait_for(progress_subscribed.wait(), timeout=5)
            await tick(hass, freezer, 1)
            await page.get_by_text(labels["search_title"], exact=True).wait_for()
            await page.locator("ha-form input").first.fill("centraal")
            await page.get_by_role("button", name=labels["search"], exact=True).click()
            await page.get_by_text(labels["area"], exact=True).wait_for()
            await page.locator("ha-selector-select ha-select").click()
            await page.get_by_text(
                "Synthetisch - Centràal (AbC01)", exact=True
            ).wait_for()
            await page.screenshot(path=str(artifacts / "desktop-stop-search.png"))
            await page.get_by_text("Synthetisch - Centràal (AbC01)", exact=True).click()
            progress_changed.clear()
            await page.get_by_role(
                "button", name=labels["continue"], exact=True
            ).click()
            await asyncio.wait_for(progress_changed.wait(), timeout=5)
            await page.set_viewport_size({"width": 390, "height": 844})
            assert api.call_count == 2
            await tick(hass, freezer, 1)
            await settle()
            # No click or manual GET: native progress events advance the dialog.
            await page.get_by_text(labels["point"], exact=True).wait_for()
            await page.screenshot(path=str(artifacts / "phone-timing-point.png"))
            assert api.call_count == 2
            await page.locator("ha-selector-select ha-select").click()
            await (
                page.get_by_role("menuitem")
                .get_by_text("X1: Synthetic destination - (01234567)", exact=True)
                .click()
            )
            await page.locator("ha-form input").first.fill("Synthetic tram")
            await page.locator("ha-form-string input").nth(1).fill("X1")
            await page.locator("ha-selector-number input").fill("5")
            submit = await localized("ui.panel.config.integrations.config_flow.submit")
            await page.get_by_role("button", name=submit, exact=True).click()
            await page.locator("step-flow-create-entry").wait_for()
            await page.get_by_role(
                "button",
                name=await localized(
                    "ui.panel.config.integrations.config_flow.finish_skip"
                ),
                exact=True,
            ).click()
            assert len(hass.config_entries.async_entries("ovapi")) == 1
            assert api.call_count == 2
            entry = hass.config_entries.async_entries("ovapi")[0]
            entity_id = er.async_get(hass).async_get_entity_id(
                "sensor", "ovapi", entry.entry_id
            )
            assert entry.state is ConfigEntryState.LOADED
            assert entry.options["walking_minutes"] == 5
            assert entry.options["lines"] == "X1"

            # Reconfigure through the actual translated native entry menu.
            progress_subscribed.clear()
            await page.goto(url + "/config/integrations/integration/ovapi")
            await page.locator(
                "ha-config-entry-row ha-dropdown[slot=end] > "
                "ha-icon-button[slot=trigger]"
            ).first.click()
            await page.locator(
                "ha-config-entry-row ha-dropdown-item[value=reconfigure]"
            ).click()
            await page.get_by_text(labels["reconfigure"], exact=True).wait_for()
            await page.get_by_text(labels["find_other"], exact=True).click()
            await page.get_by_text(labels["directory"], exact=True).wait_for()
            await asyncio.wait_for(progress_subscribed.wait(), timeout=5)
            await tick(hass, freezer, 1)
            await page.get_by_text(labels["search_title"], exact=True).wait_for()
            await page.locator("ha-form input").first.fill("centraal")
            await page.get_by_role("button", name=labels["search"], exact=True).click()
            await page.get_by_text(labels["area"], exact=True).wait_for()
            await page.locator("ha-selector-select ha-select").click()
            await page.get_by_text("Synthetisch - Centràal (AbC01)", exact=True).click()
            progress_changed.clear()
            await page.get_by_role(
                "button", name=labels["continue"], exact=True
            ).click()
            await asyncio.wait_for(progress_changed.wait(), timeout=5)
            await tick(hass, freezer, 1)
            await page.get_by_text(labels["point"], exact=True).wait_for()
            await page.locator("ha-selector-select ha-select").click()
            await (
                page.get_by_role("menuitem")
                .get_by_text(
                    "X2: Synthetic opposite direction - (76543210)", exact=True
                )
                .click()
            )
            await page.locator("ha-form input").first.fill("Updated synthetic")
            await (
                page.get_by_role("menuitem")
                .get_by_text(
                    "X2: Synthetic opposite direction - (76543210)", exact=True
                )
                .wait_for(state="hidden")
            )
            await page.screenshot(path=str(artifacts / "phone-reconfigure.png"))
            await page.get_by_role("button", name=submit, exact=True).click()
            await page.locator("step-flow-abort").wait_for()
            await page.get_by_text(
                await localized(
                    "component.homeassistant.config.abort.reconfigure_successful"
                ),
                exact=False,
            ).wait_for()
            await hass.async_block_till_done()
            assert entry.state is ConfigEntryState.LOADED
            assert entry.data["stop_id"] == "76543210"
            assert entry.options["walking_minutes"] == 5
            assert entry.options["lines"] == "X1"
            assert (
                er.async_get(hass).async_get_entity_id(
                    "sensor", "ovapi", entry.entry_id
                )
                == entity_id
            )
            assert api.call_count == 2

            # A second, instant-cache flow must also advance without a manual GET.
            progress_subscribed.clear()
            await page.goto(url + "/config/integrations/dashboard")
            await page.get_by_role(
                "button",
                name=await localized("ui.panel.config.integrations.add_integration"),
                exact=True,
            ).last.click()
            await page.locator("dialog-add-integration input").fill("OVAPI")
            await (
                page.locator("dialog-add-integration")
                .get_by_text("OVAPI", exact=True)
                .click()
            )
            await page.get_by_text(labels["find"], exact=True).click()
            await page.get_by_text(labels["directory"], exact=True).wait_for()
            await asyncio.wait_for(progress_subscribed.wait(), timeout=5)
            await tick(hass, freezer, 1)
            await page.get_by_text(labels["search_title"], exact=True).wait_for()
            await page.locator("ha-form input").first.fill("no such synthetic stop")
            await page.get_by_role("button", name=labels["search"], exact=True).click()
            await page.get_by_text(labels["no_matches"], exact=False).wait_for()
            await page.screenshot(path=str(artifacts / "phone-search-error.png"))
            assert api.call_count == 2
            await page.locator("ha-form input").first.fill("centraal")
            await page.get_by_role("button", name=labels["search"], exact=True).click()
            await page.get_by_text(labels["area"], exact=True).wait_for()
            await page.locator("ha-selector-select ha-select").click()
            await page.get_by_text("Synthetisch - Centràal (AbC01)", exact=True).click()
            progress_changed.clear()
            await page.get_by_role(
                "button", name=labels["continue"], exact=True
            ).click()
            await asyncio.wait_for(progress_changed.wait(), timeout=5)
            await tick(hass, freezer, 1)
            await page.get_by_text(labels["point"], exact=True).wait_for()
            assert api.call_count == 2
            # Original-source expiry clears the active native dialog automatically.
            await tick(hass, freezer, 1740)
            await page.get_by_text(labels["retry"], exact=True).wait_for()
            await page.get_by_role("button", name=submit, exact=True).wait_for()
            await page.screenshot(path=str(artifacts / "phone-expired-selection.png"))
            # Other interactive work can exhaust the shared allowance; no bypass.
            coordinator = get_coordinator(hass)
            for key in ("BusyA", "BusyB"):
                api.get(
                    f"http://v0.ovapi.nl/stopareacode/{key}/departures", json={key: {}}
                )
                await coordinator.async_lookup(key)
            before = api.call_count
            await page.get_by_role("button", name=submit, exact=True).click()
            await page.get_by_text(labels["details"], exact=True).wait_for()
            await page.screenshot(path=str(artifacts / "phone-progress.png"))
            assert api.call_count == before
            await tick(hass, freezer, 120)
            await page.get_by_text(labels["point"], exact=True).wait_for()
            assert api.call_count == before + 2
        except BaseException:
            await page.screenshot(path=str(artifacts / "failure.png"))
            raise
        finally:
            await context.close()
            await browser.close()
