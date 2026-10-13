# Verification: Local favourite insights

Verified 2026-10-13 from merged baseline `a1edd74d26f52e64c6b185440a4c0360c6146298`.
No live Home Assistant or OVAPI endpoint was contacted. All schedule evidence
uses dynamically dated synthetic X1/X2 data intercepted at the HTTP boundary.

## Runtime and tooling

| Exact command           | Result                                                                            |
| ----------------------- | --------------------------------------------------------------------------------- |
| `mise run test`         | PASS: 332 tests, HA 2026.10.1 / fixture 0.13.372; per-module coverage gate passes |
| `mise run test-minimum` | PASS: 332 tests, HA 2026.10.0 / fixture 0.13.371; per-module coverage gate passes |
| `mise run typecheck`    | PASS: all 10 integration modules                                                  |
| `mise run lint`         | PASS: ruff, Python formatting, dprint, yamlfmt, actionlint, offline zizmor        |
| `mise run package`      | PASS: 24 integration files; release identity unchanged at 0.1.0                   |

Config flow, sensor and WebSocket modules have **100% statements and branches**.
All modules exceed 95% in each dimension; coordinator is 99.79% statements and
97.47% branches. The first new entity-registry test failed on the unchanged
baseline before implementation because no diagnostics existed.

`tests/test_insights.py` adds 14 real-HA scenarios covering default/zero/changed
walking duration, native registry/device metadata, scalar state allowlist,
configured and ready counts, stale/empty/expired/recovered sources, removal,
disable and unload, options and reload, exact renamed source identity,
WebSocket rejection, ordinary deadline preservation, and dispatcher cleanup.
Both initially disabled and subsequently disabled leaf boards are exercised,
with and without a combination. Enabled diagnostics do not own polling,
request data through `update_entity`, reset ordinary deadlines, or retain a
copied departure cache. Existing board permissions/legacy/unavailable behavior
continue through `tests/test_websocket.py` and `tests/test_combined.py`.

## Native device page and joint card proof

The new external card bundle is the immutable production build from
`DevSecNinja/lovelace-ovapi` source
`989266688e788863db64be3d923ed9a57f9be589`:

```text
SHA256 299636dd37b6e8ea673d2b56fe9d85d5a6aa8cc00867b166454776b74aac442a
```

It was copied read-only into `.ha-e2e/bundles/leave-card.js`. No card code or
contract-version change is included here. Current-main card
`eb99055cfa592305012535829250a97af966130c` (SHA256
`0d12045dac54fcda844ef3c78aebeb4cf8f98cfaed06a2621535d484ba3d224f`)
also passed an initial strict-picker/diagnostic-subscription check; only the new
bundle is used for the final walking-aware evidence below.

```sh
OVAPI_CARD_BUNDLE="$PWD/.ha-e2e/bundles/leave-card.js" \
OVAPI_UI_ARTIFACTS=.ha-e2e/insights \
  mise exec -- uv run --locked --group e2e \
  pytest tests/ui/test_native_insights.py -m frontend --no-cov --timeout=120 -q --tb=short
```

**PASS: 4 tests**, English/Dutch native device pages and actual Lovelace
dashboard/editor on HA 2026.10.1.

```sh
UV_PROJECT_ENVIRONMENT=.venv-minimum \
OVAPI_CARD_BUNDLE="$PWD/.ha-e2e/bundles/leave-card.js" \
OVAPI_UI_ARTIFACTS=.ha-e2e/minimum-insights \
  mise exec -- uv run --locked --no-default-groups --group minimum --group e2e \
  pytest tests/ui/test_native_insights.py -m frontend --no-cov --timeout=120 -q --tb=short
```

**PASS: 4 tests**, the same scenarios on HA 2026.10.0 with its compatible fixture.
No dependency overrides, incompatible fixture reuse or altered production timing.

The actual native page (not a custom page) shows the default-visible Diagnostic
section with configured walk **7**, configured sources **3**, and ready sources
**3**. Disabling one source changes ready sources to **2** while the combined
board is unavailable. The remaining diagnostics stay visible; leaf devices show
only their configured walking duration in addition to feed status.

The real grouped departures card uses one combined status entity, `time_mode:
leave`, and three routes: two opposite metro directions and a tram destination.
Each route has four vehicles. A 4-minute vehicle is unreachable with the group's
7-minute walk; the primary becomes the 12-minute vehicle, with two following
walking-adjusted alternatives. Exact datetime arithmetic is asserted, not merely
row appearance. Separate source walking values (9, 3, 11) are never inherited.

Native dashboard Edit / card Edit / Save / fresh-page Reopen verifies **omitted
override -> 2 -> cleared -> explicit 0**, with effective walking values **7, 2,
7, 0**. The group's configured diagnostic remains **7** throughout. Fresh
navigation reads actual persisted Lovelace configuration, not an injected editor
model or retained dialog. After source disable the board fails closed and remains
in the native picker; all six diagnostics are excluded, and all six explicit
diagnostic WebSocket subscriptions return `not_found`.

Each scenario makes exactly **one batched synthetic HTTP request**, unchanged by
native pages, card subscriptions, editor previews, saves/reopens and source
disable. Both HA fixtures and all browsers close after completion. Browser
requests outside the isolated loopback origin are blocked.

Screenshots wait for `#ha-launch-screen` removal, fonts and stable geometry after
navigation/resize. Geometry reacquires the target because HA replaces native rows
at responsive breakpoints. The HA instance language is set before entity creation
so native names, not just client-side controls, are genuinely translated.
English/Dutch desktop and phone screenshots were visually inspected.

## Evidence

- [English native device, ready](evidence/en/desktop-device-ready.png)
- [Dutch native device, ready](evidence/nl/desktop-device-ready.png)
- [English phone, source disabled](evidence/en/phone-device-source-disabled.png)
- [Dutch phone, source disabled](evidence/nl/phone-device-source-disabled.png)
- [English grouped leave choices](evidence/en/desktop-grouped-leave.png)
- [Dutch phone grouped leave choices](evidence/nl/phone-grouped-leave.png)
- [Native walking override and preview](evidence/en/desktop-native-walking-override.png)
- [Native Dutch board-only picker](evidence/nl/phone-native-board-picker.png)
- Machine-readable device/card/minimum-card results in each language's evidence directory.

No source schedule, fetched/expiry time, destination, line or vehicle-derived
count is added to HA states. Screenshots/logs here contain synthetic data only.

## Delivery

`mise exec -- lefthook run pre-commit` **PASS** with changes staged: formatting,
ruff and types all ran (not skipped). Spec Kit convergence checked all nine
functional requirements, five success criteria, both user stories and all five
constitution principles; no implementation gaps or extra tasks were found.
Hosted PR checks are pending PR creation. No merge, release,
version bump, automatic-station work, HACS store-icon change or main-branch CI
trigger is part of this delivery.
