# Tasks: Local favourite insights

**Input**: Design documents in `specs/005-local-favourite-insights/`
**Prerequisites**: spec, plan, research, data model and entity contract
**Tests**: Explicitly required; real HA public interfaces and native UI.

## Phase 1: Setup

- [x] T001 Resolve actual Spec Kit templates and record feature selection in `.mise.toml` and `specs/005-local-favourite-insights/`.

## Phase 2: Foundational

- [x] T002 Add failing registry/WS diagnostic contract tests in `tests/test_insights.py`.
- [x] T003 Extract shared device info in `custom_components/ovapi/sensor.py` and guard designated board identity in `custom_components/ovapi/websocket.py`.

## Phase 3: User Story 1 - Walking duration (Priority: P1, MVP)

**Goal**: Every favourite shows existing configured walking minutes locally.
**Independent Test**: Default zero, options update and unavailable feed still show
the duration without requests.

- [x] T004 [US1] Test walking values, passive updates, stable suffixes, retention allowlist and lifecycle in `tests/test_insights.py`.
- [x] T005 [US1] Add typed passive walking-duration description/entity in `custom_components/ovapi/sensor.py`, using existing `walking_minutes`, default 0.
- [x] T006 [US1] Add EN/NL labels and native walking icon in `custom_components/ovapi/strings.json`, `translations/en.json`, `translations/nl.json` and `icons.json`.

## Phase 4: User Story 2 - Source health (Priority: P1)

**Goal**: Distinguish selected sources from non-stale ready sources.
**Independent Test**: Three configured, two ready, unavailable combined feed after
one source is lost.

- [x] T007 [US2] Test source loss/stale/expiry/recovery/options and exact source identity in `tests/test_insights.py` and `tests/test_combined.py`.
- [x] T008 [US2] Add configured/ready descriptions only for combinations in `custom_components/ovapi/sensor.py`; no source-data copies.
- [x] T009 [US2] Add explicit configured/ready labels and icons in `custom_components/ovapi/strings.json`, `translations/en.json`, `translations/nl.json` and `icons.json`.

## Phase 5: Cross-cutting verification and delivery

- [x] T010 Test all-leaf-disabled passive listeners, deadline preservation, local manual updates/reloads and cleanup in `tests/test_insights.py`.
- [x] T011 Add real native EN/NL device-page and grouped walking-aware card/picker proof in `tests/ui/test_native_insights.py`, using peer bundle and synthetic three-source data.
- [x] T012 [P] Update `README.md`, `docs/README.nl.md`, `docs/card-contract-v1.md` and `docs/development.md`.
- [x] T013 Run both locked HA suites, per-module coverage, types/lint/package/pre-commit and record exact results in `specs/005-local-favourite-insights/verification.md`.
- [x] T014 Converge artifacts against implementation, create/push focused PR using `.github/PULL_REQUEST_TEMPLATE.md`, report PR/head/evidence to parent and inspect PR CI.

## Dependencies & Execution Order

T001 -> T002 -> T003. Each story then has tests -> implementation -> translations.
Story 2 uses the passive entity foundation from story 1, not its walking value.
T010 follows both stories; T011 follows runtime completion and peer bundle.
T012 can run independently of native proof. T013 follows all changes; T014 follows
validation. Native grouped card target follows the coordinator's narrowed scope,
not a redesigned commute card.

## Parallel Examples

US1/US2 tests share a file and run sequentially. Once runtime implementation is
complete, both locked fixture suites can run in separate virtual environments;
documentation and native proof preparation are independent.

## Implementation Strategy

Land one focused PR: establish identity safety, implement walking as smallest
useful increment, add combination health, then verify passive behavior and native
surfaces. No release, version bump, merge, automatic station work or new agents.

## Phase 6: Native review correction

- [x] T015 Replace the copied URL-prefix guard consistently across `tests/ui/test_native_insights.py`, `test_native_combined.py` and `test_native_picker.py` using the pure parsed-origin policy in `tests/ui/network.py`; prove invalid/non-HTTP/userinfo/lookalike origins fail closed in `tests/test_browser_origin.py` and rerun both native fixture groups for review finding 4256960761.
