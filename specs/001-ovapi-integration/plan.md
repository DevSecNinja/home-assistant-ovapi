# Implementation Plan: Responsible OVAPI departures

**Branch**: `devsecninja-ovapi-ha-integration` | **Date**: 2026-10-12
**Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-ovapi-integration/spec.md`.

## Summary

Build a typed async HACS integration with one shared HA coordinator/request budget.
Separate transient departure boards from Recorder-safe operational status entities.
Use authenticated WebSocket snapshots for companion cards, strict expiry and honest
upstream/quality limitations.

## Technical Context

**Language/Version**: Python 3.14.8, minimum HA 2026.10.
**Primary Dependencies**: HA 2026.10.1, HA-managed aiohttp, voluptuous; no new runtime
packages outside HA. Client logic is isolated for possible later external extraction.
**Storage**: Configuration only; source data exclusively bounded memory.
**Testing**: pytest-homeassistant-custom-component 0.13.372, public HA fixture APIs,
freezer, intercepted aiohttp responses, branch coverage and strict mypy/ruff.
**Target Platform**: Home Assistant supported Python environment; macOS local tests.
**Project Type**: HACS custom integration, no claimed official quality tier.
**Performance Goals**: One batched request per >=120 seconds per HA instance.
**Constraints**: No live tests, source retention <=29 minutes, up to ten unique stops,
maximum 2 MiB decoded response, maximum 30 displayed departures per board.
**Scale/Scope**: Several favourites; no systemwide discovery, rail, history or analytics.

## Constitution Check

All five principles pass at design stage. Explicit constraints:

- The shared coordinator owns the only network client. Configuration validation,
  entry startup and manual entity refresh all obey the same minimum request spacing.
  Concurrent validations coalesce; cache validation causes no request. New stops
  during cooldown report an actionable retry-later error rather than bypassing it.
- All existing enabled entries are included in startup batching. A pending request
  cannot repopulate removed/expired data. Unload clears boards not used elsewhere.
- Per-board expiry timer purges memory independent of poll/backoff/listeners.
- Coordinator `data` contains only operational states, not departure lists.
- WebSockets check entity permissions and fetch the current registry ID; diagnostics
  return only safe operational counts/settings, never raw exceptions or entry data.
- ISO offsets are normalized to UTC. Ambiguous/nonexistent naive Europe/Amsterdam
  timestamps are rejected, not guessed. Missing mandatory schedule records are
  skipped with safe aggregate warnings; unknown predictions remain null.
- No official legal, Gold/Platinum or verified Amsterdam coverage claims.

Post-design check: no unapproved exceptions to the constitution.

## Project Structure

```text
custom_components/ovapi/
  __init__.py             # Shared coordinator lifecycle, typed runtime data
  const.py                # Conservative fixed limits
  client.py               # Async bounded HTTP and pure typed parsing
  coordinator.py          # Global budget, batch/cache/backoff/expiry
  config_flow.py          # UI setup/options/reconfiguration
  sensor.py               # Status-only entity/device
  websocket.py            # Authorized ephemeral snapshots
  diagnostics.py          # Safe operational metadata
  strings.json, translations/{en,nl}.json, icons.json
  manifest.json, quality_scale.yaml
tests/
  fixtures/               # Synthetic only
  test_client.py, test_coordinator.py, test_config_flow.py
  test_init.py, test_sensor.py, test_websocket.py, test_diagnostics.py
scripts/
  check_coverage.py, check_package.py
docs/
  card-contract-v1.md, policy.md, quality.md, README.nl.md
```

Feature documents also include research, data model, contract pointer, quickstart,
tasks and final verification evidence. Upstream Spec Kit 1.1.3 installed assets are
preserved; feature directory selection is independent of the app-managed branch.

## Complexity Tracking

| Deliberate tradeoff                            | Why necessary                                                        | Alternative rejected                                                   |
| ---------------------------------------------- | -------------------------------------------------------------------- | ---------------------------------------------------------------------- |
| WebSocket boards rather than departure sensors | Enforce source retention without relying on user Recorder exclusions | Persistent state attributes leak licensed data into history            |
| Fixed global minimum/cooldown                  | Protect upstream during setup/retry storms                           | Per-entry or card polling multiplies load                              |
| Bundled isolated client for HACS               | No package publication is authorized                                 | Publishing a new library now exceeds scope; Core extraction documented |
