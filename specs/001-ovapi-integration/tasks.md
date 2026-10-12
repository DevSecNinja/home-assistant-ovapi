# Tasks: Responsible OVAPI departures

**Input**: `specs/001-ovapi-integration/` specification, plan and design artifacts.
**Tests**: Required; offline synthetic HA public-interface tests and strict gates.

## Phase 1: Setup

- [x] T001 Initialize pinned actual Spec Kit assets in `.specify/` and `.github/skills/`.
- [x] T002 Record constitution/spec/design/contract in `specs/001-ovapi-integration/`.
- [x] T003 Add `.mise.toml`, `pyproject.toml`, `.gitignore` and lock the HA environment.

## Phase 2: Foundation

- [x] T004 Write synthetic parser/network/time/budget acceptance tests in `tests/test_client.py` and `tests/test_coordinator.py`.
- [x] T005 Implement bounded typed client and fixed limits in `custom_components/ovapi/client.py` and `const.py`.
- [x] T006 Implement single global request floor, batching, deduplication, exponential backoff and independent 29-minute expiry in `custom_components/ovapi/coordinator.py`.

## Phase 3: US1 - Favourite configuration

**Goal**: Several validated favourite/filter sets without duplicates or extra polling.
**Independent test**: Exercise public HA config flow, options/reconfigure and unload.

- [x] T007 [US1] Write flow/lifecycle/registry tests in `tests/test_config_flow.py` and `tests/test_init.py`.
- [x] T008 [US1] Implement setup/options/reconfiguration with 1-10 digit stop IDs, 1-80 character names, walking minutes 0-120 and canonical filter identity in `custom_components/ovapi/config_flow.py`.
- [x] T009 [US1] Wire typed runtime data and clean unload in `custom_components/ovapi/__init__.py`.
- [x] T010 [US1] Create status-only sensor/service device and translated UI in `custom_components/ovapi/sensor.py`, `strings.json`, `translations/` and `icons.json`.

## Phase 4: US2 - Ephemeral departure views

**Goal**: Authorized v1 snapshots preserve uncertainty and never extend retention.
**Independent test**: HA WebSocket connection, permissions, reconnect and expiry.

- [x] T011 [US2] Write subscription/permission/retention tests in `tests/test_websocket.py`.
- [x] T012 [US2] Implement `ovapi/subscribe` in `custom_components/ovapi/websocket.py`.
- [x] T013 [US2] Provide synthetic HA setup artifacts and backend instructions in `docs/development.md` to the card sibling.

## Phase 5: US3 - Responsible operation

**Goal**: Diagnose and maintain without source persistence or request multiplication.
**Independent test**: Count actual intercepted network requests with fake time.

- [x] T014 [US3] Test safe diagnostics and absence of source state in `tests/test_diagnostics.py`.
- [x] T015 [US3] Implement operational-only diagnostics in `custom_components/ovapi/diagnostics.py`.
- [x] T016 [US3] Document transport/policy caveats, installation/removal, examples and quality evidence in `README.md`, `docs/` and `custom_components/ovapi/quality_scale.yaml`.

## Phase 6: Cross-cutting verification

- [x] T017 Adopt applicable organization configs and SHA-pinned reusable lint in `.github/workflows/`.
- [x] T018 Add strict per-module >95% / full-flow gates and package checks in `scripts/`.
- [x] T019 Execute `mise run test`, `lint`, `typecheck`, `package`; fix all implementation failures.
- [x] T020 Assess convergence and record exact results/limitations in `specs/001-ovapi-integration/verification.md`.
- [x] T021 Commit and push the implementation branch without merging/publishing.

## Dependencies and execution

T001-T003 precede foundation. T004 precedes T005/T006. All user stories depend on
foundation. US2 also depends on US1 entity identity. US3 diagnostics require
foundation; its docs may be written alongside US1/US2. T017/T018 may be implemented
independently of UI work. Final validation requires all stories and gates.
No additional agents are needed; frontend is independently owned in its repository.

## Implementation strategy

Build parser/budget first, then a configured status entity, then authorized boards.
Run focused tests at each increment, expand edge/branch coverage, and converge
against FR-001 through FR-009 and SC-001 through SC-005 before pushing.

## Phase 7: Convergence

- [x] T022 Verify loaded reconfiguration, shared-stop unload, filtering/cap and clock-change expiry in `tests/test_config_flow.py` and `tests/test_coordinator.py` per FR-001/FR-003/SC-003 (partial).
- [x] T023 Add shared incomplete-source fixture and producer mapping regression in `tests/fixtures/card-source-edge.json` and `tests/test_client.py` per FR-005 and contract nonempty fields (partial).
- [x] T024 Record bounded actual Amsterdam verification and static example IDs in `README.md`, `docs/README.nl.md` and `specs/001-ovapi-integration/research.md` per FR-007 (partial).
- [x] T025 Run official HACS/hassfest review checks and final Spec Kit convergence, recording any external limitations in `specs/001-ovapi-integration/verification.md` per FR-008/FR-009 (partial).

External limitation: initial HACS license validation reads default-branch metadata,
which is null until the first authorized merge. The branch includes MIT LICENSE;
the check is not suppressed, and no merge is performed. See verification.md.
