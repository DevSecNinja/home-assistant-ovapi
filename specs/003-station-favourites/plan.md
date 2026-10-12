# Implementation Plan: Favourite filters and onboarding

**Branch**: `devsecninja-station-wide-ovapi-favourites` | **Date**: 2026-10-12
**Spec**: [spec.md](spec.md)

## Summary

Deliver the independent transport filters, manual waiting, local branding and
card handoff. Station-wide aggregation is explicitly deferred to
[#5](https://github.com/DevSecNinja/home-assistant-ovapi/issues/5): bounded research
did not establish a licensed current station-to-TPC registry covering orphan metro.
The coordinating session approved this narrower delivery rather than an
incorrect bus-only "whole station".

## Technical Context

**Language/Version**: Python 3.14.8; repository-local mise/uv lock.
**Primary Dependencies**: HA 2026.10.0/fixture 0.13.371 minimum;
HA 2026.10.1/fixture 0.13.372 development. No new runtime dependency.
**Storage**: Existing config-entry preferences; transient 29-minute departure cache.
**Testing**: Real HA pytest fixtures, HTTP/WebSockets, fake-time actual request
counts, EN/NL Chromium frontend; per-module >95%, flows 100%.
**Target Platform**: Home Assistant custom integration, HACS installation.
**Project Type**: Async Python integration with native HA configuration surfaces.
**Performance Goals**: No requests from filters/cards; two interactive request
starts per rolling 120 seconds, ordinary requests at least 120 seconds apart.
**Constraints**: Shared serialization/backoff, unchanged retention and card v1.
**Scale/Scope**: Ten distinct timing points, concurrent replacement reservations,
eight bundled PNG assets, no station grouping or companion-card implementation.

## Constitution Check

- Shared request budgets, bounded bodies, no departure persistence: retained.
- Truthful unknown/empty/stale, native HA and EN/NL: retained and clarified.
- Per-module coverage and real public-interface evidence: release gates retained.
- Card v1 keys, values and existing registry identifiers: unchanged.
- Actual Spec Kit 1.1.3 template resolution/setup scripts: executed in this worktree.
- Source gate failed for station grouping; that work is deferred, not disguised
  as a completed requirement. No supplemental provider/cache is introduced.
- Parent-directed latest capacity correction from PR #4 is integrated before
  validation, not independently reimplemented.

## Project Structure

### Documentation (this feature)

```text
specs/003-station-favourites/
  spec.md
  plan.md
  research.md
  data-model.md
  quickstart.md
  contracts/card-v1.md
  checklists/requirements.md
  tasks.md
  verification.md
```

### Source Code (repository root)

```text
custom_components/ovapi/
  config_flow.py
  coordinator.py
  const.py
  sensor.py
  brand/*.png
  strings.json
  translations/{en,nl}.json
scripts/{render_brand,check_package}.py
tests/test_{manual_progress,transport_filters,brand,reconfigure_capacity}.py
tests/ui/test_native_picker.py
```

**Structure Decision**: Extend existing native flow/coordinator, preserving the
capacity reservation API. Manual checks contribute to a shared interactive batch;
late callers join the next eligible batch, never retry source failures in a loop.
Use original generated artwork and HA's native brands endpoint, not a frontend
asset server. Missing transport preference means all for legacy entries; an
explicit empty selection is a translated validation error.

## Complexity Tracking

No constitutional exceptions for delivered behavior. Static-metadata persistence,
station scheduling and aggregate identity remain unimplemented pending #5.
