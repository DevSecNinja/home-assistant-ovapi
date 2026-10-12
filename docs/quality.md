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

## Honest external gaps

Brand assets have **not** been submitted to Home Assistant's separate brands
repository. The `brands` rule remains `todo`; only the HACS branding check is
ignored. Package/release publication and a Core PR are outside this delivery.

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

There is only one useful status entity per favourite, enabled by default, with
enum device class. It is the primary integration output, not a diagnostic-only
extra. Departure lists cannot be stored as ordinary sensor attributes without
breaking retention. Therefore historic departure statistics, standard departure
automations, and entity-only departure cards are intentionally unsupported.

Transient failures recover automatically. An unknown timing point is surfaced
through translated setup errors and can be reconfigured; no persistent hardware
repair or credentials need intervention. Current repair behavior is documented in
the rule checklist rather than implying an interactive repairs wizard.
