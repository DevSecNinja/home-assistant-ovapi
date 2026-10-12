# Implementation verification and convergence

Date: 2026-10-12. Environment: macOS arm64, Python 3.14.8, HA 2026.10.1,
pytest-homeassistant-custom-component 0.13.372; all dependencies in `uv.lock`.

## Executed evidence

- `mise run check`: passes. Includes pytest, strict mypy, ruff lint/format,
  dprint, yamlfmt, actionlint, offline zizmor and installation archive checks.
- `mise run test`: **106 passed**, entirely synthetic/offline. Every integration
  module has **100% statement coverage**. Coordinator branch coverage is **97.73%**;
  all other modules including config flow are **100%**. The separate gate checks
  every module's statements and branches, not only an aggregate.
- `mise run typecheck`: strict mypy passes for all eight integration modules.
- `mise run package`: validates fourteen integration files, matching EN/NL string
  keys, manifest, HACS minimum version, YAML and Python syntax; creates and reopens
  `dist/ovapi.zip`. Archive is ignored and not published.
- `mise exec -- gitleaks dir . --no-banner --redact --log-level warn`: passes.
- Official Spec Kit `check-prerequisites.sh --require-spec --require-tasks
  --include-tasks`: resolves the completed feature artifacts.

## Acceptance mapping

| Requirement                     | Evidence                                                                                                                                                                     |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| FR-001 / SC-001 favourites      | Real user/options/reconfigure flows, duplicate checks, loaded reconfigure, registry device/entity, reload floor, unload and failure tests                                    |
| FR-002 / SC-002 / SC-004 budget | Actual intercepted HTTP call counts, simultaneous entry/flow batching, cached validation, ten subscriptions, 119/121-second boundaries, 429 Retry-After and recovery         |
| FR-003 / SC-003 retention       | 1740-second independent expiry, stale replay unchanged, unload/in-flight race, monotonic expiry under wall-clock rollback, status-only state and diagnostics                 |
| FR-004 status                   | Ready empty, stale failure, unavailable expiry and recovery through HA state machine and WebSocket events                                                                    |
| FR-005 contract                 | Real authenticated HA WS, entity permission denial/revocation, rename/removal, null facts, cancellation, synthetic incomplete metadata fixture, filters and 30-departure cap |
| FR-006 scope                    | Parser rejects rail/unknown modes/terminal/passed records; native NS link                                                                                                    |
| FR-007 user docs                | EN/NL setup, removal, all parameters, known limitations, verified narrow Amsterdam examples and quality-rule ledger                                                          |
| FR-008 / SC-005 engineering     | Per-module thresholds, full-flow and frontend-schema serialization, strict types, locked mise tooling, shared org CI, package gate                                           |
| FR-009 actual Spec Kit          | Pinned CLI initialization, installed skills/templates/workflow, resolved template scripts, constitution/spec/plan/tasks/implement/convergence artifacts                      |

## Bugs found and corrected during convergence

- Current HA uses probatio rather than legacy voluptuous; typed schemas updated.
- Full HTTP config-flow serialization rejected `str.strip` in schema validators.
  Removed callable normalization from schemas, retained normalization at input
  handling, and added frontend field serialization tests for all three forms.
  Sibling confirmed actual HTTP create-entry success after the correction.
- Ordinary options reload erased source cache while the global budget was cooling
  down. Options now update locally without reload, source-age reset or HTTP.
- Runtime tracking now preserves the original stop ID during loaded reconfiguration,
  allowing old-stop eviction without erasing the newly validated target.
- HA WebSocket debug/coalescing/slow-client logs can contain full source frames.
  Added narrowly targeted logging redaction and real DEBUG-enabled WS tests.
- Missing source line/destination metadata would violate strict card schema.
  Such records are omitted, with synthetic producer/consumer edge evidence.
- No test teardown leaks: global coordinator shutdown cancels expiry/in-flight work;
  explicit unload clears the last-user stop cache.

## Bounded live verification

One small, identified, gzip-enabled Amsterdam batch returned HTTP 200; candidate
timing points `30009501` and `30009514` matched the expected location names and both
contained supported-mode records. No live response, schedule or route was logged
or stored. This is not a coverage guarantee for every service/platform.

## External checks and limitations

Official HACS/hassfest PR jobs and combined actual HA/Lovelace browser verification
are tracked separately until their outcomes are available. Local archive checks
are not represented as a substitute for those official checks.

HA brand submission, independent API-library extraction/Core review, license-link
restoration/upstream numeric quota confirmation, and releases remain external
follow-up, not hidden completed work. The integration remains custom; no official
Gold/Platinum claim. HTTP and transient-only automation limitations are explicit.

## Convergence status

Buildable backend requirements and the appended convergence edge tasks pass locally.
Final convergence/delivery awaits official PR check outcomes and the sibling's
combined E2E report. No package/release publication or live-user installation occurs.
