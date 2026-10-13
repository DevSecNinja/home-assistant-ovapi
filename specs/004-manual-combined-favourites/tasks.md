# Tasks: Manual combined favourites

**Input**: Design documents from `/specs/004-manual-combined-favourites/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Required, public HA interfaces and intercepted HTTP.

## Phase 1: Setup

- [x] T001 Record bounded specification and resolved design in specs/004-manual-combined-favourites/spec.md and plan.md.

## Phase 2: Foundational

- [x] T002 Write failing public-flow and two-source WebSocket regressions in tests/test_combined.py.

## Phase 3: User Story 1 - One board (Priority: P1)

**Goal**: One filtered, chronological feed without extra upstream work.

**Independent Test**: Two loaded leaf favourites become one thirty-row-limited v1
board, exact duplicates only removed, actual HTTP count unchanged.

- [x] T003 [US1] Add leaf-only source validation and native create form (2-12 unique IDs, walk integer 0-120/default 0) in custom_components/ovapi/config_flow.py and combined.py.
- [x] T004 [US1] Derive filtered, sorted and fully equal-event-deduplicated snapshots in custom_components/ovapi/coordinator.py; skip upstream setup and capacity registration in `custom_components/ovapi/__init__.py`.

## Phase 4: User Story 2 - Honest availability (Priority: P1)

**Goal**: No silent partial board or extended data lifetime.

**Independent Test**: Fake-time expiry, stale/recovery and source loss clear/update
the live subscription and actual HA state with no copied persistent data.

- [x] T005 [US2] Add stale/empty/unknown/cancelled/expiry/loss tests in tests/test_combined.py.
- [x] T006 [US2] Add bounded lifecycle notifications and capability identity/source health in custom_components/ovapi/coordinator.py and sensor.py, including unsubscribe cleanup.

## Phase 5: User Story 3 - Maintain the group (Priority: P2)

**Goal**: Stable identity and removable missing references.

**Independent Test**: Public options/reconfigure, renamed/reconfigured sources,
reload and persisted restart configuration preserve identity and age.

- [x] T007 [US3] Add options/reconfigure/restart/cycle/capacity regressions in tests/test_combined.py.
- [x] T008 [US3] Wire group editing and English/Dutch forms in custom_components/ovapi/config_flow.py, strings.json and translations/.
- [x] T009 [US3] Exercise native add/reconfigure and current card rendering in tests/ui/test_native_combined.py.

## Phase 6: Polish & Cross-Cutting Concerns

- [x] T010 Document manual setup, limitations and retention in README.md and specs/004-manual-combined-favourites/verification.md.
- [x] T011 Run both HA suites, strict coverage, type/lint/package/native browser gates and converge specs/004-manual-combined-favourites/tasks.md.
- [x] T012 Commit/push focused branch, create template-based PR and verify hosted CI using .github/PULL_REQUEST_TEMPLATE.md.

## Dependencies & Execution Order

T001 -> T002 -> T003 -> T004. T005 -> T006 requires T004.
T007 -> T008 requires T004. T009 requires T006/T008.
T010 follows implementation; T011 requires T009/T010; T012 requires T011.
All three stories are required for this safe interim solution.

## Parallel Opportunities

No additional agents or sessions. Independent regression scenarios can run in one
pytest invocation; the two HA environments and static checks may run independently.
US1 snapshot and filter cases, US2 loss and expiry cases, and US3 options and
reconfigure cases are independent tests within their story.

## Implementation Strategy

Test first, implement one bounded leaf-only path, validate each story, then run
cross-cutting gates. Do not add a dependency graph or station discovery. No
extension hooks configured. All twelve tasks use checklist IDs and explicit paths.

## Phase 7: Convergence

- [x] T013 Finish review delivery and hosted CI verification per T012 and Constitution V (partial), using .github/PULL_REQUEST_TEMPLATE.md.
- [x] T014 Persist measured native-screen and command evidence in specs/004-manual-combined-favourites/verification.md per T010 and SC-004 (missing).
