# Home Assistant quality evidence

This is a **custom** integration. It has not been reviewed, rated or endorsed by
Home Assistant, and must not display an official Gold/Platinum claim. We track
every currently published rule in
[`quality_scale.yaml`](../custom_components/ovapi/quality_scale.yaml).

## Evidence

| Concern                                    | Implementation and verification                                                                        |
| ------------------------------------------ | ------------------------------------------------------------------------------------------------------ |
| UI setup, reconfigure, options, duplicates | `config_flow.py`; full public-flow tests and 100% coverage gate                                        |
| Setup/unload/retry, typed runtime data     | `__init__.py`; real HA entry states and registry lifecycle tests                                       |
| Shared async polling                       | `coordinator.py`, injected HA-managed session; fake-time actual-request count tests                    |
| Unknown/stale/unavailable/recovery         | Explicit snapshot/status state machine and expiry timer tests                                          |
| Retention and diagnostics                  | No source state attributes, pure operational diagnostics, DEBUG-enabled WebSocket redaction tests      |
| Device/entity identity                     | Service devices, stable entry-based unique IDs, translated names and icons, rename tests               |
| Type and test rigor                        | Strict mypy; each integration module >95% statement and branch coverage; config flow 100%              |
| Packaging                                  | HACS manifest, offline archive/translation checks, official HACS/hassfest PR jobs                      |
| User docs                                  | English/Dutch setup, all settings, removal, examples, update behavior, limitations and troubleshooting |
| Reproducibility                            | Repository-local mise, frozen uv lock, actual pinned Spec Kit, shared org CI                           |

## Stop-picker evidence

The [stop-picker verification](../specs/002-stop-name-picker/verification.md)
records exact minimum/locked-runtime commands and rendered native UI evidence.
`test_picker_flow.py` exercises public setup/reconfigure/options and real HTTP
serialization. `test_discovery_coordinator.py` measures shared request counts,
fairness, cancellation, original-age cache expiry and no third validation request.
`tests/ui/test_native_picker.py` drives actual HA forms in Chromium, including a
new cache-only dialog and a delayed-budget path; native events, not test calls to
the flow manager, continue the browser.

HA can emit completed-progress events before its frontend subscribes. Source-free
notifications are retried with 1-to-30-second backoff only until continuation,
abort, expiry or shutdown (at most 29 minutes). This is not upstream polling.
The browser test reproduced the stuck spinner before this fix. Directory labels
are cleared from backend schemas at original expiry and the active native dialog
switches to a source-free retry form. Missing/empty stop information remains
honest, including valid empty timing points whose transport mode is unknown.

## Honest external gaps

Branding is now bundled locally, supported since HA 2026.3. Original 256/512-square
icons and light/dark wordmarks ship in the validated archive. `test_brand.py`
extracts that archive and checks every PNG through the real authenticated HA
brands API on both supported runtimes, with no CDN request. The current HACS
validator accepts local `brand/icon.png`, so its former exception is removed.
Package/release publication and a Core PR remain outside this delivery.

The [favourite-onboarding evidence](../specs/003-station-favourites/verification.md)
covers manual interactive waiting, source-pause deadlines, cancellation, local
transport preferences, translated empty-selection errors and native card handoff.
Automatic station grouping is explicitly unbuilt in
[#5](https://github.com/DevSecNinja/home-assistant-ovapi/issues/5); a bus-only area
is not presented as full metro-station coverage.

The client is fully asynchronous, typed and isolated in `client.py`, accepting
an injected session, but is bundled for HACS. HA Core submission would require
maintaining/extracting the API library as an independent package and reviewing
the transient WebSocket/log-redaction design. This is a future compatibility goal,
not a claim that the integration is already Core-ready.

Policy verification is also incomplete externally: the wiki's GOVI license link
is unavailable and no numerical rate allowance is published. Conservative
implementation choices cannot substitute for upstream permission. See [policy](policy.md).

## Product-specific exemptions

There is no authentication credential upstream, so reauthentication is not
applicable. There are no controllable devices, firmware updates, custom service
actions/triggers/conditions, or network discovery. Users explicitly add/remove
favourites, rather than discover a changing device fleet. No real physical-device
health/firmware lifecycle is modeled.

There is one primary status entity per favourite, enabled by default, with enum
device class. Additional default-visible diagnostic entities expose configured
walking duration and, for combinations, configured/ready source-favourite counts.
They reuse passive listeners and cannot be subscribed to as boards.
Departure lists cannot be stored as ordinary sensor attributes without
breaking retention. Therefore historic departure statistics, standard departure
automations, and entity-only departure cards are intentionally unsupported.

Transient failures recover automatically. An unknown timing point is surfaced
through translated setup errors and can be reconfigured; no persistent hardware
repair or credentials need intervention. Current repair behavior is documented in
the rule checklist rather than implying an interactive repairs wizard.
