"""Actual HA service-device diagnostics and the externally built companion card."""

import hashlib
import json
import os
import shutil
import time
from datetime import timedelta
from pathlib import Path

import pytest
from aiohttp.web_log import AccessLogger
from homeassistant.components.http import StaticPathConfig
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.test_combined import create_combined, entity_id
from tests.test_init import make_entry
from tests.test_insights import assert_counts, insight, insight_id

pytestmark = [pytest.mark.frontend, pytest.mark.enable_socket]

LABELS = {
    "en": {
        "walking": "Configured walking time",
        "configured": "Configured source favourites",
        "ready": "Source favourites with ready feed",
    },
    "nl": {
        "walking": "Ingestelde looptijd",
        "configured": "Ingestelde bronfavorieten",
        "ready": "Bronfavorieten met actuele gegevens",
    },
}


async def capture(page, artifacts, filename, target):
    await page.locator("#ha-launch-screen").wait_for(state="detached")
    await page.evaluate("document.fonts.ready")
    await target.wait_for()
    last, stable = None, 0
    # HA can replace the entity row when a responsive breakpoint changes.
    for _ in range(120):
        box = await target.bounding_box()
        stable = stable + 1 if box and box == last else 0
        if stable >= 3:
            break
        last = box
        await page.evaluate("() => new Promise(requestAnimationFrame)")
    else:
        pytest.fail("Unstable screenshot geometry")
    await page.screenshot(
        path=str(artifacts / filename), animations="disabled", full_page=True
    )


@pytest.fixture
async def native_insights(
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

    freezer.move_to(dt_util.utcnow().replace(microsecond=0))
    await hass.config.async_update(language=language, time_zone="Europe/Amsterdam")
    monkeypatch.setattr(AccessLogger, "_get_local_time", staticmethod(dt_util.utcnow))
    hass_storage["onboarding"] = {
        "version": 4,
        "key": "onboarding",
        "data": {"done": ["user", "core_config", "integration", "analytics"]},
    }
    for component in (
        "persistent_notification",
        "labs",
        "logger",
        "brands",
        "frontend",
        "lovelace",
    ):
        assert await async_setup_component(hass, component, {})
    template = payload["01234567"]["Passes"]["SYNTHETIC_TRIP"]
    definitions = [
        ("01234567", "Metro east", "METRO", "X1", "Synthetic east", 9),
        ("76543210", "Metro west", "METRO", "X1", "Synthetic west", 3),
        ("87654321", "Tram centre", "TRAM", "X2", "Synthetic centre", 11),
    ]
    sources = []
    response = {}
    for stop, name, mode, line, destination, walking in definitions:
        sources.append(make_entry(hass, stop=stop, name=name, walking_minutes=walking))
        response[stop] = {
            "Passes": {
                f"{stop}_vehicle_{index}": {
                    **template,
                    "TransportType": mode,
                    "LinePublicNumber": line,
                    "DestinationName50": destination,
                    "TargetDepartureTime": (
                        dt_util.utcnow() + timedelta(minutes=minutes)
                    ).isoformat(),
                    "ExpectedDepartureTime": (
                        dt_util.utcnow() + timedelta(minutes=minutes)
                    ).isoformat(),
                }
                for index, minutes in enumerate((4, 12, 20, 28))
            }
        }
    api.get(
        "http://v0.ovapi.nl/tpc/01234567,76543210,87654321/departures", json=response
    )
    assert await hass.config_entries.async_setup(sources[0].entry_id)
    await hass.async_block_till_done()
    group = await create_combined(
        hass, sources, name="Diemen Zuid (synthetic)", walking_minutes=7
    )
    assert_counts(hass, group, 3, 3)
    assert api.call_count == 1
    await hass.http.async_register_static_paths(
        [StaticPathConfig("/insights-test", str(tmp_path), False)]
    )
    client = await hass_client()
    url = str(client.make_url("/")).rstrip("/")
    token = await hass.auth.async_create_refresh_token(
        hass_admin_user, client_id=url + "/", access_token_expiration=timedelta(days=1)
    )
    tokens = {
        "hassUrl": url,
        "clientId": url + "/",
        "access_token": hass.auth.async_create_access_token(token),
        "refresh_token": token.token,
        "token_type": "Bearer",
        "expires_in": 86400,
        "expires": (time.time() + 86400) * 1000,
    }
    artifacts = Path(os.environ.get("OVAPI_UI_ARTIFACTS", str(tmp_path))) / language
    await hass.async_add_executor_job(
        lambda: artifacts.mkdir(parents=True, exist_ok=True)
    )
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context(
            viewport={"width": 1440, "height": 1000}, locale=language
        )
        await context.add_init_script(
            f"localStorage.setItem('hassTokens', {json.dumps(json.dumps(tokens))});"
            "localStorage.setItem('selectedLanguage', "
            f"{json.dumps(json.dumps(language))});"
        )
        await context.route(
            "**/*",
            lambda route: (
                route.continue_()
                if route.request.url.startswith(url)
                else route.abort()
            ),
        )
        page = await context.new_page()
        page.set_default_timeout(10000)
        try:
            yield {
                "page": page,
                "url": url,
                "group": group,
                "sources": sources,
                "artifacts": artifacts,
                "tmp_path": tmp_path,
            }
        finally:
            await context.close()
            await browser.close()


@pytest.mark.parametrize("language", ["en", "nl"])
async def test_native_device_insights(hass, api, native_insights, language):
    from playwright.async_api import expect

    env = native_insights
    page, group = env["page"], env["group"]
    labels = LABELS[language]
    registry = er.async_get(hass)
    group_device = registry.async_get(entity_id(hass, group)).device_id
    await page.goto(env["url"] + f"/config/devices/device/{group_device}")
    await page.wait_for_function(
        "language => document.querySelector('home-assistant')?.hass?.locale?.language"
        " === language",
        arg=language,
    )
    for label in labels.values():
        await expect(page.get_by_text(label, exact=True)).to_be_visible()
    walking = page.get_by_text(labels["walking"], exact=True)
    for width, height, size in [(1440, 1000, "desktop"), (390, 844, "phone")]:
        await page.set_viewport_size({"width": width, "height": height})
        await capture(page, env["artifacts"], f"{size}-device-ready.png", walking)
    source_device = registry.async_get(entity_id(hass, env["sources"][0])).device_id
    await page.goto(env["url"] + f"/config/devices/device/{source_device}")
    await expect(walking).to_be_visible()
    await expect(page.get_by_text(labels["configured"], exact=True)).to_have_count(0)
    await capture(page, env["artifacts"], "phone-leaf-device.png", walking)
    registry.async_update_entity(
        entity_id(hass, env["sources"][1]), disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    assert_counts(hass, group, 3, 2)
    assert hass.states.get(entity_id(hass, group)).state == "unavailable"
    assert insight(hass, group, "walking_duration").state == "7"
    await page.goto(env["url"] + f"/config/devices/device/{group_device}")
    for label in labels.values():
        await expect(page.get_by_text(label, exact=True)).to_be_visible()
    for width, height, size in [(390, 844, "phone"), (1440, 1000, "desktop")]:
        await page.set_viewport_size({"width": width, "height": height})
        await capture(
            page, env["artifacts"], f"{size}-device-source-disabled.png", walking
        )
    public_states = await page.evaluate("""() => {
        const hass = document.querySelector("home-assistant").hass;
        return hass.callWS({type: "get_states"});
    }""")
    for key, value in (
        ("walking_duration", "7"),
        ("configured_sources", "3"),
        ("ready_sources", "2"),
    ):
        state = next(
            s for s in public_states if s["entity_id"] == insight_id(hass, group, key)
        )
        assert state["state"] == value
        assert "board_id" not in state["attributes"]
        assert "contract_version" not in state["attributes"]
    assert api.call_count == 1
    evidence = {
        "language": language,
        "requests": api.call_count,
        "surface": "native device page",
        "walking_minutes": 7,
        "configured_sources": 3,
        "ready_after_disable": 2,
        "combined_feed_after_disable": "unavailable",
    }
    await hass.async_add_executor_job(
        lambda: (env["artifacts"] / "device-results.json").write_text(
            json.dumps(evidence, indent=2)
        )
    )


@pytest.mark.parametrize("language", ["en", "nl"])
async def test_native_insights_card(hass, api, native_insights, language):
    from playwright.async_api import expect

    bundle = os.environ.get("OVAPI_CARD_BUNDLE")
    if not bundle:
        pytest.skip("Set OVAPI_CARD_BUNDLE to the built walking-aware departures card")
    env = native_insights
    page, group = env["page"], env["group"]
    group_id = entity_id(hass, group)
    copied = env["tmp_path"] / "lovelace-ovapi.js"
    await hass.async_add_executor_job(shutil.copyfile, bundle, copied)
    await page.goto(env["url"] + "/config/integrations/dashboard")
    await page.wait_for_function(
        "document.querySelector('home-assistant')?.hass?.connected"
    )
    await page.evaluate(
        """async entity => {
        const hass = document.querySelector("home-assistant").hass;
        await hass.callWS({type: "lovelace/resources/create",
            res_type: "module", url: "/insights-test/lovelace-ovapi.js"});
        await hass.callWS({type: "lovelace/dashboards/create",
            url_path: "insights-verification", title: "Local insights",
            show_in_sidebar: true, require_admin: false});
        await hass.callWS({type: "lovelace/config/save",
            url_path: "insights-verification", config: {
                title: "Local insights", views: [{title: "Walking choices", cards: [{
                    type: "custom:ovapi-departures-card", entities: [entity],
                    display_mode: "grouped", time_mode: "leave", max_routes: 5,
                }]}]}});
    }""",
        group_id,
    )
    await page.goto(env["url"] + "/insights-verification/0")
    card = page.locator("hui-masonry-view ovapi-departures-card")
    await expect(card.locator("section")).to_have_count(1)
    await expect(card.locator("li.departure")).to_have_count(3)
    for destination in ("Synthetic east", "Synthetic west", "Synthetic centre"):
        await expect(card.get_by_text(destination, exact=True)).to_be_visible()
    await expect(card.locator(".departure.leave-mode")).to_have_count(3)
    await expect(card.locator(".following time")).to_have_count(6)
    following = await card.locator(".following time").evaluate_all(
        "items => items.map(item => item.getAttribute('datetime'))"
    )
    assert sorted(dt_util.parse_datetime(value) for value in following) == sorted(
        dt_util.utcnow() + timedelta(minutes=minutes)
        for minutes in (13, 21, 13, 21, 13, 21)
    )
    leave = await card.locator(".leave-time").first.get_attribute("datetime")
    vehicle = await card.locator(".departure-clock time").first.get_attribute(
        "datetime"
    )
    assert dt_util.parse_datetime(vehicle) - dt_util.parse_datetime(leave) == timedelta(
        minutes=7
    )
    # The 4-minute vehicle cannot be reached with the group's configured 7-minute walk.
    assert dt_util.parse_datetime(vehicle) == dt_util.utcnow() + timedelta(minutes=12)
    for width, height, size in [(1440, 1000, "desktop"), (390, 844, "phone")]:
        await page.set_viewport_size({"width": width, "height": height})
        await capture(page, env["artifacts"], f"{size}-grouped-leave.png", card)
    await page.set_viewport_size({"width": 1440, "height": 1000})
    edit_dashboard = "Edit dashboard" if language == "en" else "Dashboard bewerken"
    edit = "Edit" if language == "en" else "Bewerken"
    save = "Save" if language == "en" else "Opslaan"
    dialog = page.locator("hui-dialog-edit-card")
    editor = dialog.locator("ovapi-card-editor")

    async def open_editor():
        # Reload from persisted Lovelace config, not the retained dialog instance.
        await page.goto(env["url"] + "/insights-verification/0")
        await page.locator("#ha-launch-screen").wait_for(state="detached")
        await page.get_by_role("button", name=edit_dashboard, exact=True).press("Enter")
        await (
            page.locator("hui-card-options")
            .get_by_role("button", name=edit, exact=True)
            .press("Enter")
        )
        await editor.locator("#walking").wait_for()
        await expect(editor.locator("#time-mode")).to_have_value("leave")
        await expect(editor.locator("#display-mode")).to_have_value("grouped")

    previous = ""
    roundtrips = []
    for value, expected_walk in [("", 7), ("2", 2), ("", 7), ("0", 0)]:
        await open_editor()
        await expect(editor.locator("#walking")).to_have_value(previous)
        await editor.locator("#walking").fill(value)
        await editor.locator("#walking").press("Tab")
        await dialog.get_by_role("button", name=save, exact=True).press("Enter")
        await dialog.wait_for(state="hidden")
        expected_override = int(value) if value else None
        await page.wait_for_function(
            """async expected => {
                const hass = document.querySelector("home-assistant").hass;
                const config = await hass.callWS({
                    type: "lovelace/config", url_path: "insights-verification"});
                const card = config.views[0].cards[0];
                return expected === null ? !("walking_minutes" in card)
                    : card.walking_minutes === expected;
            }""",
            arg=expected_override,
        )
        await expect(card.locator(".departure.leave-mode")).to_have_count(3)
        leave = await card.locator(".leave-time").first.get_attribute("datetime")
        vehicle = await card.locator(".departure-clock time").first.get_attribute(
            "datetime"
        )
        assert dt_util.parse_datetime(vehicle) - dt_util.parse_datetime(
            leave
        ) == timedelta(minutes=expected_walk)
        assert insight(hass, group, "walking_duration").state == "7"
        assert api.call_count == 1
        roundtrips.append(
            {"override": expected_override, "effective_walk": expected_walk}
        )
        previous = value
    await open_editor()
    await expect(editor.locator("#walking")).to_have_value("0")
    await capture(page, env["artifacts"], "desktop-native-card-editor.png", editor)
    await editor.locator("#walking").scroll_into_view_if_needed()
    await capture(
        page,
        env["artifacts"],
        "desktop-native-walking-override.png",
        editor.locator("#walking"),
    )
    cancel = "Cancel" if language == "en" else "Annuleren"
    await dialog.get_by_role("button", name=cancel, exact=True).press("Enter")
    await dialog.wait_for(state="hidden")
    diagnostic_ids = [
        item.entity_id
        for item in er.async_get(hass).entities.values()
        if item.platform == "ovapi" and item.unique_id != item.config_entry_id
    ]
    rejected = await page.evaluate(
        """async ids => {
        const hass = document.querySelector("home-assistant").hass;
        return Promise.all(ids.map(async entity_id => {
            try {
                await hass.callWS({type: "ovapi/subscribe", entity_id});
                return "accepted";
            } catch (error) { return error.code; }
        }));
    }""",
        diagnostic_ids,
    )
    assert rejected == ["not_found"] * len(diagnostic_ids)
    assert api.call_count == 1
    er.async_get(hass).async_update_entity(
        entity_id(hass, env["sources"][1]), disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    await expect(card.locator("li.departure")).to_have_count(0)
    assert_counts(hass, group, 3, 2)
    assert insight(hass, group, "walking_duration").state == "7"
    # Reopen the actual native editor with the original board now unavailable.
    await open_editor()
    await editor.locator(f'input[value="{group_id}"]').wait_for()
    candidates = await editor.locator('input[type="checkbox"]').evaluate_all(
        "inputs => inputs.map(input => input.value)"
    )
    assert set(candidates).isdisjoint(diagnostic_ids)
    assert group_id in candidates
    assert set(candidates) <= {
        entity_id(hass, entry) for entry in (*env["sources"], group)
    }
    await page.set_viewport_size({"width": 390, "height": 844})
    await capture(page, env["artifacts"], "phone-native-board-picker.png", editor)
    assert api.call_count == 1
    evidence = {
        "language": language,
        "requests": api.call_count,
        "card_sha256": await hass.async_add_executor_job(
            lambda: hashlib.sha256(copied.read_bytes()).hexdigest()
        ),
        "sources": 3,
        "grouped_routes": 3,
        "diagnostic_ws_rejections": len(rejected),
        "diagnostics_excluded_from_picker": True,
        "unavailable_board_in_picker": True,
        "native_walking_roundtrips": roundtrips,
        "configured_walking_unchanged": 7,
    }
    await hass.async_add_executor_job(
        lambda: (env["artifacts"] / "card-results.json").write_text(
            json.dumps(evidence, indent=2)
        )
    )
