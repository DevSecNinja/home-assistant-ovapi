"""Actual HA frontend with synthetic upstream data; no live user's instance."""

import asyncio
import json
import os
import time
from datetime import timedelta
from pathlib import Path

import pytest
from aiohttp.web_log import AccessLogger
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.ovapi.coordinator import get_coordinator
from tests.test_coordinator import tick
from tests.test_discovery import DIRECTORY
from tests.test_discovery_coordinator import settle

pytestmark = [pytest.mark.frontend, pytest.mark.enable_socket]


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
    artifacts = Path(os.environ.get("OVAPI_UI_ARTIFACTS", str(tmp_path)))
    await hass.async_add_executor_job(
        lambda: artifacts.mkdir(parents=True, exist_ok=True)
    )
    api.get("http://v0.ovapi.nl/stopareacode/", json=DIRECTORY)
    api.get("http://v0.ovapi.nl/stopareacode/AbC01/departures", json={"AbC01": payload})
    api.get("http://v0.ovapi.nl/tpc/01234567/departures", json=payload)
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
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        await context.add_init_script(
            f"localStorage.setItem('hassTokens', {json.dumps(json.dumps(tokens))});"
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
            await page.get_by_role(
                "button", name="Add integration", exact=True
            ).last.click()
            await page.get_by_placeholder("Search for a brand name").fill("OVAPI")
            await (
                page.locator("dialog-add-integration")
                .get_by_text("OVAPI", exact=True)
                .click()
            )
            await page.get_by_text("Find a stop by name", exact=True).click()
            await page.get_by_text("Loading stop names", exact=True).wait_for()
            await asyncio.wait_for(progress_subscribed.wait(), timeout=5)
            await tick(hass, freezer, 1)
            await page.get_by_text("Find a stop", exact=True).wait_for()
            await page.locator("ha-form input").first.fill("centraal")
            await page.get_by_role("button", name="Search", exact=True).click()
            await page.get_by_text("Choose a stop", exact=True).wait_for()
            await page.locator("ha-selector-select ha-select").click()
            await page.get_by_text(
                "Synthetisch - Centràal (AbC01)", exact=True
            ).wait_for()
            await page.screenshot(path=str(artifacts / "desktop-stop-search.png"))
            await page.get_by_text("Synthetisch - Centràal (AbC01)", exact=True).click()
            progress_changed.clear()
            await page.get_by_role("button", name="Continue", exact=True).click()
            await asyncio.wait_for(progress_changed.wait(), timeout=5)
            await page.set_viewport_size({"width": 390, "height": 844})
            assert api.call_count == 2
            await tick(hass, freezer, 1)
            await settle()
            # No click or manual GET: native progress events advance the dialog.
            await page.get_by_text("Choose your stop sign", exact=True).wait_for()
            await page.screenshot(path=str(artifacts / "phone-timing-point.png"))
            assert api.call_count == 2
            await page.locator("ha-selector-select ha-select").click()
            await (
                page.get_by_role("menuitem")
                .get_by_text("X1: Synthetic destination - (01234567)", exact=True)
                .click()
            )
            await page.locator("ha-form input").first.fill("Synthetic tram")
            await page.get_by_role("button", name="Submit", exact=True).click()
            await page.get_by_text("Name and assign", exact=True).wait_for()
            await page.get_by_role("button", name="Skip and finish", exact=True).click()
            assert len(hass.config_entries.async_entries("ovapi")) == 1
            assert api.call_count == 2

            # A second, instant-cache flow must also advance without a manual GET.
            progress_subscribed.clear()
            await page.goto(url + "/config/integrations/dashboard")
            await page.get_by_role(
                "button", name="Add integration", exact=True
            ).last.click()
            await page.get_by_placeholder("Search for a brand name").fill("OVAPI")
            await (
                page.locator("dialog-add-integration")
                .get_by_text("OVAPI", exact=True)
                .click()
            )
            await page.get_by_text("Find a stop by name", exact=True).click()
            await page.get_by_text("Loading stop names", exact=True).wait_for()
            await asyncio.wait_for(progress_subscribed.wait(), timeout=5)
            await tick(hass, freezer, 1)
            await page.get_by_text("Find a stop", exact=True).wait_for()
            await page.locator("ha-form input").first.fill("no such synthetic stop")
            await page.get_by_role("button", name="Search", exact=True).click()
            await page.get_by_text(
                "No matching stop metadata was found.", exact=False
            ).wait_for()
            await page.screenshot(path=str(artifacts / "phone-search-error.png"))
            assert api.call_count == 2
            await page.locator("ha-form input").first.fill("centraal")
            await page.get_by_role("button", name="Search", exact=True).click()
            await page.get_by_text("Choose a stop", exact=True).wait_for()
            await page.locator("ha-selector-select ha-select").click()
            await page.get_by_text("Synthetisch - Centràal (AbC01)", exact=True).click()
            progress_changed.clear()
            await page.get_by_role("button", name="Continue", exact=True).click()
            await asyncio.wait_for(progress_changed.wait(), timeout=5)
            await tick(hass, freezer, 1)
            await page.get_by_text("Choose your stop sign", exact=True).wait_for()
            assert api.call_count == 2
            # Original-source expiry clears the active native dialog automatically.
            await tick(hass, freezer, 1740)
            await page.get_by_text("Stop lookup needs attention", exact=True).wait_for()
            await page.get_by_role("button", name="Submit", exact=True).wait_for()
            await page.screenshot(path=str(artifacts / "phone-expired-selection.png"))
            # Other interactive work can exhaust the shared allowance; no bypass.
            coordinator = get_coordinator(hass)
            for key in ("BusyA", "BusyB"):
                api.get(
                    f"http://v0.ovapi.nl/stopareacode/{key}/departures", json={key: {}}
                )
                await coordinator.async_lookup(key)
            before = api.call_count
            await page.get_by_role("button", name="Submit", exact=True).click()
            await page.get_by_text("Loading stop directions", exact=True).wait_for()
            await page.screenshot(path=str(artifacts / "phone-progress.png"))
            assert api.call_count == before
            await tick(hass, freezer, 120)
            await page.get_by_text("Choose your stop sign", exact=True).wait_for()
            assert api.call_count == before + 2
        except BaseException:
            await page.screenshot(path=str(artifacts / "failure.png"))
            raise
        finally:
            await context.close()
            await browser.close()
