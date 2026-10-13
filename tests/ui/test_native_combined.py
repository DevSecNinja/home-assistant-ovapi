"""Native translated group forms and the real, externally built companion card."""

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

from tests.test_combined import entity_id, setup_sources
from tests.test_init import make_entry
from tests.ui.network import is_test_origin

pytestmark = [pytest.mark.frontend, pytest.mark.enable_socket]

LABELS = {
    "en": {
        "combine": "Combine existing favourites",
        "preferences": "Combined favourite preferences",
        "configure": "Configure",
        "invalid": "Select 2-12 different single-stop OVAPI favourites.",
    },
    "nl": {
        "combine": "Bestaande favorieten combineren",
        "preferences": "Voorkeuren gecombineerde favoriet",
        "configure": "Configureren",
        "invalid": "Kies 2-12 verschillende OVAPI-favorieten voor losse haltes.",
    },
}


@pytest.mark.parametrize("language", ["en", "nl"])
async def test_native_combined(
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
    from playwright.async_api import async_playwright, expect

    bundle = os.environ.get("OVAPI_CARD_BUNDLE")
    if not bundle:
        pytest.skip("Set OVAPI_CARD_BUNDLE to a built current companion-card module")
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
    source = payload["01234567"]["Passes"]["SYNTHETIC_TRIP"]
    source["TargetDepartureTime"] = (
        dt_util.utcnow() + timedelta(minutes=10)
    ).isoformat()
    source["ExpectedDepartureTime"] = (
        dt_util.utcnow() + timedelta(minutes=12)
    ).isoformat()
    first, second = await setup_sources(hass, api, payload)
    third = make_entry(hass, name="Synthetic replacement", lines="X1")
    assert await hass.config_entries.async_setup(third.entry_id)
    await hass.async_block_till_done()
    assert api.call_count == 1
    copied = tmp_path / "lovelace-ovapi.js"
    await hass.async_add_executor_job(shutil.copyfile, bundle, copied)
    await hass.http.async_register_static_paths(
        [StaticPathConfig("/combined-test-card.js", str(copied), False)]
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
    labels = LABELS[language]
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
        await context.route(
            "**/*",
            lambda route: (
                route.continue_()
                if is_test_origin(route.request.url, url)
                else route.abort()
            ),
        )
        page = await context.new_page()
        page.set_default_timeout(10000)

        async def localized(key):
            await page.wait_for_function(
                "key => document.querySelector('home-assistant')?.hass?.localize(key)",
                arg=key,
            )
            return await page.evaluate(
                "key => document.querySelector('home-assistant').hass.localize(key)",
                key,
            )

        async def finish():
            await page.get_by_role(
                "button",
                name=await localized(
                    "ui.panel.config.integrations.config_flow.finish_skip"
                ),
                exact=True,
            ).click()

        async def capture(filename, target):
            await page.locator("#ha-launch-screen").wait_for(state="detached")
            await page.evaluate("document.fonts.ready")
            await target.wait_for()
            await target.evaluate("""element => new Promise((resolve, reject) => {
                let last, stable = 0, frames = 0;
                function check() {
                    const r = element.getBoundingClientRect();
                    const value = [r.x, r.y, r.width, r.height].join(",");
                    stable = value === last && r.width > 0 && r.height > 0
                        ? stable + 1 : 0;
                    last = value;
                    if (stable >= 3) return resolve();
                    if (++frames > 120) return reject(Error("Unstable geometry"));
                    requestAnimationFrame(check);
                }
                requestAnimationFrame(check);
            })""")
            await page.screenshot(path=str(artifacts / filename), animations="disabled")

        try:
            await page.goto(url + "/config/integrations/dashboard")
            await page.wait_for_function(
                "language => document.querySelector('home-assistant')"
                "?.hass?.locale?.language === language",
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
            await page.get_by_text(labels["combine"], exact=True).click()
            await page.locator("ha-form-string input").fill("Synthetic combined")
            east = page.get_by_role(
                "checkbox",
                name=f"Synthetic east ({entity_id(hass, first)})",
                exact=True,
            )
            west = page.get_by_role(
                "checkbox",
                name=f"Synthetic west ({entity_id(hass, second)})",
                exact=True,
            )
            await east.press("Space")
            submit = await localized("ui.panel.config.integrations.config_flow.submit")
            await page.get_by_role("button", name=submit, exact=True).click()
            await page.get_by_text(labels["invalid"], exact=False).wait_for()
            await expect(east).to_be_checked()
            await capture("desktop-combine.png", page.locator("ha-form"))
            await west.press("Space")
            await page.locator("ha-selector-number input").fill("4")
            await page.get_by_role("button", name=submit, exact=True).click()
            await page.locator("step-flow-create-entry").wait_for()
            await finish()
            await hass.async_block_till_done()
            group = next(
                entry
                for entry in hass.config_entries.async_entries("ovapi")
                if entry.data.get("entry_type") == "combined"
            )
            group_id = entity_id(hass, group)
            assert group.options["walking_minutes"] == 4
            assert api.call_count == 1

            # Native options retain checked source choices and change only local walk.
            await page.goto(url + "/config/integrations/integration/ovapi")
            row = page.locator("ha-config-entry-row").filter(
                has_text="Synthetic combined"
            )
            await row.wait_for()
            await row.get_by_role("button", name=labels["configure"], exact=True).press(
                "Enter"
            )
            await page.get_by_text(labels["preferences"], exact=True).wait_for()
            await expect(
                page.get_by_role(
                    "checkbox",
                    name=f"Synthetic east ({entity_id(hass, first)})",
                    exact=True,
                )
            ).to_be_checked()
            await page.locator("ha-selector-number input").fill("5")
            await page.get_by_role("button", name=submit, exact=True).click()
            await page.get_by_text(labels["preferences"], exact=True).wait_for(
                state="hidden"
            )
            await hass.async_block_till_done()
            assert group.options["walking_minutes"] == 5

            # Native reconfigure replaces one source, retaining group/entity identity.
            await page.goto(url + "/config/integrations/integration/ovapi")
            row = page.locator("ha-config-entry-row").filter(
                has_text="Synthetic combined"
            )
            await row.locator(
                "ha-dropdown[slot=end] > ha-icon-button[slot=trigger]"
            ).first.click()
            await row.locator("ha-dropdown-item[value=reconfigure]").click()
            await page.get_by_text(labels["combine"], exact=True).wait_for()
            await page.get_by_role(
                "checkbox",
                name=f"Synthetic east ({entity_id(hass, first)})",
                exact=True,
            ).press("Space")
            await page.get_by_role(
                "checkbox",
                name=f"Synthetic replacement ({entity_id(hass, third)})",
                exact=True,
            ).press("Space")
            await page.locator("ha-form-string input").fill("Combined directions")
            await page.set_viewport_size({"width": 390, "height": 844})
            await capture("phone-reconfigure-combined.png", page.locator("ha-form"))
            await page.get_by_role("button", name=submit, exact=True).click()
            await page.locator("step-flow-abort").wait_for()
            await hass.async_block_till_done()
            assert group.options["source_entry_ids"] == sorted(
                [second.entry_id, third.entry_id]
            )
            assert entity_id(hass, group) == group_id
            assert api.call_count == 1

            # Real Lovelace dashboard with just the group's entity and current card.
            await page.evaluate(
                """async entity => {
                const hass = document.querySelector('home-assistant').hass;
                await hass.callWS({type: "lovelace/resources/create",
                    res_type: "module", url: "/combined-test-card.js"});
                await hass.callWS({type: "lovelace/dashboards/create",
                    url_path: "combined-verification", title: "Combined verification",
                    show_in_sidebar: true, require_admin: false});
                await hass.callWS({type: "lovelace/config/save",
                    url_path: "combined-verification", config: {
                    title: "Combined verification", views: [{title: "Manual",
                        cards: [{type: "custom:ovapi-departures-card",
                            entities: [entity]}]}]}});
            }""",
                group_id,
            )
            await page.goto(url + "/combined-verification/0")
            await page.wait_for_function(
                "document.querySelector('home-assistant')?.hass?.connected"
            )
            card = page.locator("ovapi-departures-card")
            await expect(card).to_have_count(1)
            await expect(card.locator("section")).to_have_count(1)
            await card.get_by_text("Synthetic destination", exact=True).wait_for()
            await card.get_by_text("Opposite direction", exact=True).wait_for()
            await expect(card.locator("li.departure")).to_have_count(2)
            assert api.call_count == 1
            await capture("phone-one-board.png", card)
            await page.set_viewport_size({"width": 1280, "height": 900})
            await capture("desktop-one-board.png", card)
            await page.evaluate("""async () => {
                const hass = document.querySelector("home-assistant").hass;
                const config = await hass.callWS({
                    type: "lovelace/config", url_path: "combined-verification"});
                config.views[0].cards[0].display_mode = "grouped";
                await hass.callWS({type: "lovelace/config/save",
                    url_path: "combined-verification", config});
            }""")
            await page.goto(url + "/combined-verification/0")
            await card.get_by_text("Synthetic destination", exact=True).wait_for()
            await card.get_by_text("Opposite direction", exact=True).wait_for()
            await expect(card.locator("section")).to_have_count(1)
            await expect(card.locator("li.departure")).to_have_count(2)
            assert api.call_count == 1
            await page.set_viewport_size({"width": 390, "height": 844})
            await capture("phone-grouped-board.png", card)

            er.async_get(hass).async_update_entity(
                entity_id(hass, second), disabled_by=er.RegistryEntryDisabler.USER
            )
            await hass.async_block_till_done()
            await expect(card.locator("li.departure")).to_have_count(0)
            state = hass.states.get(group_id)
            assert state.state == "unavailable"
            assert state.attributes["contract_version"] == 1
            # Exercise the unchanged real card editor's capability-based selector.
            await page.evaluate(
                """async entity => {
                const editor = document.createElement("ovapi-card-editor");
                editor.hass = document.querySelector("home-assistant").hass;
                editor.setConfig({type: "custom:ovapi-departures-card", entities: []});
                document.body.append(editor);
                await editor.updateComplete;
            }""",
                group_id,
            )
            await page.locator(
                f'ovapi-card-editor input[value="{group_id}"]'
            ).wait_for()
            assert api.call_count == 1
            evidence = {
                "language": language,
                "requests": api.call_count,
                "card_sha256": await hass.async_add_executor_job(
                    lambda: hashlib.sha256(copied.read_bytes()).hexdigest()
                ),
                "boards": 1,
                "departures": 2,
                "grouped_routes": 2,
                "unavailable_capability_selector": True,
            }
            await hass.async_add_executor_job(
                lambda: (artifacts / "combined-results.json").write_text(
                    json.dumps(evidence, indent=2)
                )
            )
        finally:
            await context.close()
            await browser.close()
