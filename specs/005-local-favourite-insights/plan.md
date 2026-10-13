# Implementation Plan: Local favourite insights

**Branch**: `devsecninja-local-favourite-insights` | **Date**: 2026-10-13
**Spec**: [spec.md](spec.md)

**Input**: `specs/005-local-favourite-insights/spec.md`

## Summary

Add native read-only walking duration for every favourite and configured/ready
source counts for combinations. Share device metadata and typed HA sensor
descriptions, but not board capabilities. Reuse the existing passive dispatcher
context for all diagnostics. Guard WebSocket subscription by the original board's
unique ID, not merely its platform/domain.

## Technical Context

**Language/Version**: Python 3.14.8
**Primary Dependencies**: HA 2026.10.0/2026.10.1 and matching locked fixture groups
**Storage**: Existing configuration plus safe diagnostic states; no new cache
**Testing**: pytest HA public APIs, intercepted HTTP, fake time, native Playwright
**Target Platform**: Home Assistant native service-device page, EN/NL
**Project Type**: Custom integration
**Performance Goals**: Zero added upstream requests, listeners do not own polls
**Constraints**: Existing 120-second floor and 29-minute expiry unchanged
**Scale/Scope**: One additional sensor per leaf, three per combination

## Constitution Check

Pre-design and post-design: pass. No network path, source data persistence,
protocol migration, new dependency, poller or graph. Diagnostic state is safe
configuration/operational metadata. Public-state tests cover registry identity,
subscription permissions and lifecycle. Both compatibility profiles and strict
per-module coverage remain release gates. Native screenshots use synthetic data
only. No agents, live HA, upstream queries, merges or releases.

## Project Structure

### Documentation (this feature)

```text
specs/005-local-favourite-insights/
  spec.md
  plan.md
  research.md
  data-model.md
  contracts/entities.md
  quickstart.md
  tasks.md
  verification.md
```

### Source Code (repository root)

```text
custom_components/ovapi/
  sensor.py
  websocket.py
  coordinator.py        # existing passive dispatcher, reused unchanged
  combined.py           # existing exact board-identity lookup, reused unchanged
  strings.json
  translations/{en,nl}.json
  icons.json
tests/
  test_insights.py
  test_combined.py
  test_websocket.py
  ui/test_native_insights.py
docs/
  README.nl.md
  card-contract-v1.md
  development.md
```

**Structure Decision**: Keep implementation in the current sensor platform; add
no new integration module. Extract only shared device metadata. Use description
value callbacks rather than keyed fallbacks, and make diagnostic availability
independent of departure availability. HA entity removal controls unload state.

## Complexity Tracking

No constitution violations or added architectural layers.
