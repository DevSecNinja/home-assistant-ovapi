# Implementation Plan: Manual combined favourites

**Branch**: `devsecninja-manual-combined-favourites` | **Date**: 2026-10-12 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-manual-combined-favourites/spec.md`

## Summary

Add a leaf-only manual favourite type. Store config-entry IDs, expose a native
multiselect, and derive a v1 snapshot on demand from the existing coordinator.
No additional provider, polling, source cache, station coverage or card changes.

## Technical Context

**Language/Version**: Python 3.14.8

**Primary Dependencies**: Home Assistant 2026.10.0 minimum / 2026.10.1 locked

**Storage**: HA configuration for name/source IDs/walk only; existing transient cache

**Testing**: Locked pytest HA fixtures, fake time, intercepted HTTP, Playwright

**Target Platform**: Home Assistant custom integration

**Project Type**: Integration with an existing companion-card WebSocket contract

**Performance Goals**: Zero additional HTTP requests or physical-stop reservations

**Constraints**: Original source expiry, no Recorder departures, flow coverage 100%,
every module >95% statement and branch coverage, strict typing

**Scale/Scope**: 2-12 leaf favourite views per combination, existing 30-row output

## Constitution Check

Pass before and after design: shared upstream budget unchanged; native translated
HA flows; offline public-interface regressions first; v1 unchanged; pinned tooling.
No unresolved clarification or constitution exception. No extension hooks configured.

## Project Structure

### Documentation (this feature)

```text
specs/004-manual-combined-favourites/
  spec.md
  plan.md
  research.md
  data-model.md
  contracts/card-v1.md
  quickstart.md
  tasks.md
  verification.md
```

### Source Code (repository root)

```text
custom_components/ovapi/
  combined.py       # bounded source-reference and aggregation helpers
  config_flow.py    # native create/options/reconfigure
  coordinator.py    # derived snapshots, shared lifecycle notifications
  __init__.py       # local-only combined setup/unload
  sensor.py         # capability identity and source health
  strings.json
  translations/
tests/
  test_combined.py
  ui/test_native_combined.py
```

**Structure Decision**: Extend existing entry/coordinator interfaces, with one small
helper module rather than another coordinator, provider or dependency graph.
