# Implementation Plan: Stop-name picker

**Branch**: `devsecninja-ovapi-stop-name-picker` | **Date**: 2026-10-12
**Spec**: [spec.md](spec.md)

## Summary

Extend native configuration with search/manual navigation, locally searched
on-demand stop-area metadata and selected-area timing points. Use native progress
tasks for shared-budget waits. Reuse selected-area boards for entry validation.

## Technical Context

**Language/Version**: Python 3.14.8.
**Primary Dependencies**: Locked HA 2026.10.1 / fixture 0.13.372; minimum HA
2026.10.0 / fixture 0.13.371; HA-managed aiohttp and probatio selectors.
**Storage**: Runtime-only source cache, original wall/monotonic deadlines.
**Testing**: Synthetic pytest HA public interfaces, actual HTTP forms, isolated
rendered frontend; existing per-module statement/branch gates.
**Target Platform**: Native Home Assistant, English/Dutch, phone/desktop.
**Project Type**: Existing custom integration; no new frontend package.
**Performance Goals**: Cached search under one second; no per-keystroke HTTP.
**Constraints**: Background batches at least 120 seconds apart, two interactive
requests per rolling 120 seconds instance-wide, shared response-relative backoff,
1740-second retention, bounded compressed/uncompressed response sizes.
**Scale/Scope**: Ten configured timing points, one directory, bounded area cache,
at most 50 displayed search results and bounded queued lookups.

## Constitution Check

Before and after design: all five principles satisfied by planned mechanisms.
Source data is runtime-only; card/config/release versions are unchanged; real
public HA interfaces and original-source expiry are explicit acceptance gates.
No hooks registered. Research was performed directly without extra agents.

## Project Structure

```text
custom_components/ovapi/
  client.py          # shared bounded HTTP reader
  discovery.py       # pure metadata/area parsing and local search
  coordinator.py     # shared scheduler, lookup lifetime, board seeding
  config_flow.py     # native search/progress/select/manual/reconfigure
  strings.json
  translations/
tests/
  test_discovery.py
  test_discovery_coordinator.py
  test_picker_flow.py
  test_config_flow.py
docs/
specs/002-stop-name-picker/
```

**Structure Decision**: One small pure discovery module, extending the existing
client/coordinator rather than a second transport or independent budget.

## Implementation Decisions

- Menu entry points offer search and explicit advanced manual entry. Existing
  reconfigure/manual input and options continue through existing save logic.
- A native search form submits a bounded query against shared metadata, then
  shows at most 50 town/name/code-labelled choices in a native dropdown.
- Directory/detail progress tasks return no dataset; flows keep only lookup keys,
  selected IDs and local preferences. Cache eviction/expiry invalidates choices.
- Brief progress is shown even for cache hits so the native frontend subscribes
  to flow-change notifications. Bounded source-free retries handle completion
  before that subscription. Expiry clears backend schemas and notifies the
  frontend to reload a source-free retry form.
- A FIFO request lock serializes transport. A two-element monotonic request deque
  enforces the rolling interactive allowance independently of the background
  deadline. Each lookup defers the next ordinary poll by 120 seconds. Only extra
  lookups after the initial pair reserve an eligible polling slot, so sustained
  setup traffic cannot starve existing boards. Source backoff applies to both lanes.
- Same-key waiters share a task; cancelling the last waiter cancels queued work.
  Normal polling retains its existing nonblocking cooldown behavior.
- Known unsupported-only points are excluded. Valid empty points remain selectable
  with unknown mode/direction, preserving existing empty-board setup behavior.
  Missing metadata uses available pass metadata and the code, never guessed facts.
- Detail boards are copied into the selected stop's normal cache with the original
  acquisition/deadline; selection never resets their age.
- No broad logging suppression: inspect/test core serialization and protect only
  source-bearing OVAPI flow frames if an actual logging path exists.

## Complexity Tracking

No constitution exceptions. The scheduler and expiry callbacks are necessary to
preserve existing budget/retention guarantees across native asynchronous forms.
The user-directed speed revision explicitly replaces the initial all-request
120-second floor; it does not remove bounded traffic or shared server backoff.
