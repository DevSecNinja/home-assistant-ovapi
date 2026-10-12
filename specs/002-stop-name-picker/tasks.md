# Tasks: Stop-name picker

**Input**: Design documents in `specs/002-stop-name-picker/`.
**Prerequisites**: spec, plan, research, data model and native flow contract.
**Tests**: Required synthetic/public HA and rendered frontend evidence.

## Phase 1: Setup

- [x] T001 Verify merged-main baseline, local mise and Spec Kit 1.1.3; select new feature in .mise.toml and .specify/feature.json.

## Phase 2: Foundation

- [x] T002 Add failing bounded parser/transport tests in tests/test_discovery.py.
- [x] T003 Implement "string code (up to ten characters, safe single path segment)" metadata, accent-insensitive search, supported timing points and bounded decompression in custom_components/ovapi/discovery.py and client.py.
- [x] T004 Add request-count, FIFO/dedup/cancellation, bounded immediate interactive pair, background floor, shared backoff, expiry and board-seeding tests in tests/test_discovery_coordinator.py.
- [x] T005 Extend the singleton scheduler and original wall/monotonic cache deadlines in custom_components/ovapi/coordinator.py.

## Phase 3: US1 - Find a stop by name (P1)

**Goal**: Setup without external code research.
**Independent test**: Complete cold and cached synthetic public/HTTP journeys.

- [x] T006 [P] [US1] Add public/HTTP search-progress-area-timing-point tests in tests/test_picker_flow.py.
- [x] T007 [US1] Add native menus, bounded search selectors and automatic progress to custom_components/ovapi/config_flow.py.
- [x] T008 [US1] Add English/Dutch labels and honest wait/coverage descriptions to custom_components/ovapi/strings.json and translations/.

## Phase 4: US2 - Reconfigure a favourite (P1)

**Goal**: Preserve identity, entities and options while replacing the timing point.
**Independent test**: Reconfigure a loaded entry; assert existing entity ID/options.

- [x] T009 [US2] Add reconfigure/duplicate/no-third-request regressions in tests/test_picker_flow.py and tests/test_config_flow.py.
- [x] T010 [US2] Connect the picker to existing save/options/reconfigure behavior in custom_components/ovapi/config_flow.py.

## Phase 5: US3 - Recovery and manual fallback (P2)

**Goal**: Honest errors, safe expiry/abort and deliberate advanced entry.
**Independent test**: Fail, retry, expire, abort and manually configure through HA.

- [x] T011 [US3] Add malformed/empty/oversize, stalled-flow/abort/cache-age and HTTP recovery tests in tests/test_picker_flow.py.
- [x] T012 [US3] Implement source-free error/retry paths, flow cleanup and expiry notifications in custom_components/ovapi/config_flow.py.

## Phase 6: Cross-cutting evidence and delivery

- [x] T013 Update README.md, docs/README.nl.md, docs/policy.md and docs/quality.md with setup, retention and quality evidence.
- [x] T014 Run both locked runtime suites, full-flow/per-module coverage, types/lint/package; record exact results in specs/002-stop-name-picker/verification.md.
- [x] T015 Exercise rendered actual HA phone/desktop configuration, progress and errors with synthetic data; record evidence in specs/002-stop-name-picker/verification.md.
- [x] T016 Converge spec/plan/tasks, commit/push new branch, create template-based PR and verify hosted checks; record results in specs/002-stop-name-picker/verification.md.

## Dependencies & Execution Order

T001 -> T002 -> T003 -> T004 -> T005. US1 follows foundation (T006 -> T007
-> T008). US2 builds on shared picker (T009 -> T010). US3 recovery tests may be
written alongside US1; implementation follows picker (T011 -> T012).
T013-T015 require complete stories; T016 requires all preceding evidence.

## Parallel Opportunities

US1 HTTP tests and translation preparation touch separate files; US2 fixture
preparation and US3 error cases can be prepared separately. Runtime environments
must be installed/validated sequentially due to disk limits. No extra agents.

## Implementation Strategy

Build and test shared transport/scheduling first, then one complete name-selection
journey, then reconfiguration and failure/lifecycle cases. Do not deliver the MVP
alone: all three approved stories and required evidence are delivery gates.

## User-directed speed revision

- [x] T017 Replace the uniform floor with two instance-wide discovery requests per rolling 120 seconds, preserving shared backoff and ordinary polling, in custom_components/ovapi/coordinator.py.
- [x] T018 Prove immediate cold setup after a recent poll, third-request throttling, shared Retry-After and native exhausted-budget UI in tests/test_discovery_coordinator.py and tests/ui/test_native_picker.py.
- [x] T019 Update policy, translated wait copy and Spec Kit evidence for the revised allowance in README.md, docs/ and specs/002-stop-name-picker/.

## User-directed HACS convenience link

- [x] T020 Add official repository-opening badges with installation prerequisites and manual fallback to README.md and docs/README.nl.md; companion-repository change is coordinated separately.

## Phase 7: Convergence

- [x] T021 Align the plan's search-widget/progress wording with the verified native query form, dropdown and bounded notification retries in specs/002-stop-name-picker/plan.md per plan: native UI decisions (partial).
- [x] T022 Finish final dual-runtime/performance, staged pre-commit and hosted PR evidence in specs/002-stop-name-picker/verification.md per FR-010, T014 and T016 (partial).

## User-directed GitHub Copilot review

- [ ] T023 Process GitHub Copilot review feedback and verify any follow-up changes; the coordinator owns the reviewer request and thread replies, with outcomes recorded in specs/002-stop-name-picker/verification.md.

## Phase 8: Post-merge review fixes

PR #3 was merged by the user before review follow-up delivery. These fixes are
carried on a new branch from merged main, not pushed to or reopening that PR.

- [x] T024 Fix full-capacity picker/manual reconfiguration using bounded flow-owned replacement reservations, with failure/abort/concurrency regressions in tests/test_reconfigure_capacity.py.
- [x] T025 Exercise native English and Dutch add-and-reconfigure journeys on both supported HA versions in tests/ui/test_native_picker.py, preserving entity identity and options.
- [x] T026 Correct empty-departure wording in strings.json and translations/en.json/translations/nl.json and the HACS prerequisite spelling in docs/README.nl.md.
- [ ] T027 Preserve updated bilingual screenshots and reservation/validation evidence, then open the new review-fix PR and verify hosted checks; coordinator owns review requests and replies.
