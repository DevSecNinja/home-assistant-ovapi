# Tasks: Favourite filters and onboarding

**Input**: Design documents from `specs/003-station-favourites/`.
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/.
**Tests**: Required synthetic unit/integration/native browser evidence.
**Organization**: Independent delivered stories; station grouping moved to #5.

## Phase 1: Setup

- [x] T001 Verify merged-main baseline and pinned tools in `.mise.toml`.
- [x] T002 Resolve Spec Kit 1.1.3 templates and record specification/design in `specs/003-station-favourites/`.
- [x] T003 Record bounded source/licensing investigations and approved partial-delivery decision in `specs/003-station-favourites/research.md`.

## Phase 2: Foundational

- [x] T004 Integrate reviewed replacement capacity fixes, including every-claimant credit from 62473ca, in `custom_components/ovapi/coordinator.py` and `tests/test_reconfigure_capacity.py`.
- [x] T005 Preserve the unchanged card contract in `specs/003-station-favourites/contracts/card-v1.md` and legacy unique-ID behavior.

## Phase 3: User Story 1 - Whole station (deferred)

**Goal**: Preserve the unmet requirement without shipping incomplete coverage.
**Independent Test**: A future station implementation must include orphan metro,
not merely area `09542`'s buses.

- [x] T006 [US1] Explicitly defer runtime grouping to [#5](https://github.com/DevSecNinja/home-assistant-ovapi/issues/5) in `specs/003-station-favourites/spec.md`; add no guessed-ID or spatial fallback.

The original station implementation remains unbuilt. T006 records the approved
scope decision, not completion of the station feature.

## Phase 4: User Story 2 - Transport filters

**Goal**: Include new services of selected modes without configuring their lines.
**Independent Test**: New synthetic metro line/destination appears while bus is
excluded, with unchanged board/card identity and zero filter-generated requests.

- [x] T007 [US2] Cover missing legacy preferences, explicit empty rejection, exact lines and single destination substring in `tests/test_transport_filters.py`.
- [x] T008 [US2] Add a nonempty selection of `bus`, `tram`, `metro` in `custom_components/ovapi/config_flow.py`, defaulting absent preferences to all and retaining legacy canonical identity in `coordinator.py`.
- [x] T009 [US2] Translate selection help and distinguish source observations from coverage in `custom_components/ovapi/strings.json` and `translations/{en,nl}.json`.

## Phase 5: User Story 3 - Onboarding and automatic waiting

**Goal**: Manual setup waits without losing input, and successful setup explains
where departures appear rather than only exposing "Ready".
**Independent Test**: EN/NL native UI continues after local cooldown and a longer
server pause; the extracted package serves authenticated local artwork.

- [x] T010 [US3] Route manual validation through the existing two-per-120-second interactive allowance in `custom_components/ovapi/coordinator.py` and native progress in `config_flow.py`.
- [x] T011 [US3] Cover cancellation, late/concurrent callers, true backoff deadlines, no automatic source-failure loops and cache reuse in `tests/test_manual_progress.py`.
- [x] T012 [P] [US3] Generate original PNG artwork with `scripts/render_brand.py`, ship it through `scripts/check_package.py`, and verify real authenticated serving in `tests/test_brand.py`.
- [x] T013 [US3] Clarify feed-status names without changing entity-ID suffixes in `custom_components/ovapi/sensor.py` and add the native setup-success HACS card link in translations.
- [x] T014 [US3] Finish native EN/NL selection, empty-selection recovery, manual cooldown/server-pause and handoff verification on both supported HA runtimes in `tests/ui/test_native_picker.py`.

## Phase 6: Polish and cross-cutting concerns

- [x] T015 Update `README.md`, `docs/README.nl.md`, `docs/policy.md`, `docs/quality.md` and `docs/development.md` for delivered behavior and deferred #5.
- [x] T016 Run final minimum/current suites, per-module coverage, typing/lint/package and record exact results in `specs/003-station-favourites/verification.md`.
- [x] T017 Commit/push the independent actual-scope PR using `.github/PULL_REQUEST_TEMPLATE.md`; coordinate native Copilot review and record addressed feedback in verification evidence.

## Dependencies and execution order

T001 -> T002/T003 -> T004/T005. US2 and US3 require T004/T005; their source files
overlap, so implementation is serialized. T012's artwork/package work is independent
of flow changes. T014 requires T009..T013. T015 requires the final source/UX decision.
T016 follows T014/T015. T017 follows T016. US1's unbuilt runtime work is tracked in
#5 and is not a prerequisite to the approved narrower delivery.

## Parallel opportunities

Mode tests and packaging tests can run independently once implementation is stable.
Current and minimum HA verification use separate virtual environments; PNG test
archives use separate temporary paths. Native checks do not contact external APIs.
No subagents or additional worktrees are needed.

## Implementation strategy

Keep the original intent traceable, fail the station source gate honestly, and
deliver the independently useful mode/onboarding changes with unchanged v1 and
retention. Validate each behavior through existing public HA interfaces, then
converge and obtain native review before handing back the PR.

## Phase 7: Convergence

- [x] T018 Include the calendar date in native pause deadlines in `custom_components/ovapi/config_flow.py` and verify a Retry-After longer than 24 hours in `tests/test_manual_progress.py` per FR-014 (partial).

## Phase 8: Parent visual verification

- [x] T019 Start the real HA brands component in `tests/ui/test_native_picker.py`; reproduce the missing-image failure, assert the native local image request/HTTP 200/decode/natural width, and recapture EN/NL handoff on both supported HA runtimes per SC-007.
