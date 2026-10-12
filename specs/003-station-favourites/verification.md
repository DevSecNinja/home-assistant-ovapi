# Verification: filters, branding and onboarding

Verified 2026-10-12 on this independent branch from merged main `696a326`.
This is **not** completion of automatic whole-station discovery; that requirement
remains open in [#5](https://github.com/DevSecNinja/home-assistant-ovapi/issues/5).

## Delivered behavior

- Manual add/reconfigure uses the same two-per-rolling-120-second allowance as
  discovery. Cache hits are immediate; pending work waits automatically, preserves
  every form field and distinguishes local cooldown from shared source backoff.
- A request returning an error leaves the preserved form for explicit resubmission.
  Resubmission waits automatically for the actual eligible deadline. There is no
  automatic repeated source-failure loop.
- Local bus/tram/metro filtering defaults missing legacy settings to all. Explicit
  empty input is rejected in setup/options/reconfigure, with EN/NL recovery.
  New metro services appear without listing their lines or causing filter requests.
- Original light/dark 256/512 icons and wordmarks ship in the archive; native HA
  brands APIs serve every image without network fallback.
- Feed-status wording and static timing-point device identity are clearer.
  Native success links to HACS companion cards. Card v1 and existing entity IDs
  remain unchanged, including the `departure_board` suffix.
- Reviewed capacity corrections from PR #4 (`fdb19c9`, `62473ca`) are integrated.
  Concurrent/late/cancelled replacements retain working boards and cannot share
  another claimant's uncommitted capacity.

## Exact local validation

| Command                                                                                                                         | Result                                                                |
| ------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `mise run test`                                                                                                                 | Passed: 284 tests, HA 2026.10.1 / fixture 0.13.372                    |
| `mise run test-minimum`                                                                                                         | Passed: 284 tests, HA 2026.10.0 / fixture 0.13.371                    |
| `mise run lint`                                                                                                                 | Passed: ruff, format, dprint, yamlfmt, actionlint, offline zizmor     |
| `mise run typecheck`                                                                                                            | Passed: strict mypy, 9 integration modules                            |
| `mise run package`                                                                                                              | Passed: 23 integration files, including all 8 validated PNGs          |
| `mise exec -- uv run --locked pytest tests/test_brand.py --no-cov -q`                                                           | Passed: extracted archive through authenticated current-HA brands API |
| `UV_PROJECT_ENVIRONMENT=.venv-minimum mise exec -- uv run --locked --only-group minimum pytest tests/test_brand.py --no-cov -q` | Passed: extracted archive through authenticated minimum-HA brands API |
| `git diff --check`                                                                                                              | Passed                                                                |

Every integration module exceeds 95% statements and branches. Config flow has
100% statements and branches. Coordinator: 99.75% statements, 97.01% branches.

Actual browser commands:

```sh
OVAPI_UI_ARTIFACTS=.ha-e2e/evidence mise exec -- uv run --locked --group e2e \
  pytest tests/ui/test_native_picker.py -m frontend --no-cov --timeout=60 \
  --tb=short --show-capture=no
```

**Passed: English and Dutch**, on locked HA 2026.10.1.

```sh
UV_PROJECT_ENVIRONMENT=.venv-minimum OVAPI_UI_ARTIFACTS=.ha-e2e/minimum-evidence \
  mise exec -- uv run --locked --no-default-groups --group minimum --group e2e \
  pytest tests/ui/test_native_picker.py -m frontend --no-cov --timeout=60 \
  --tb=short --show-capture=no
```

**Passed: English and Dutch**, on minimum HA 2026.10.0.

The native browser checks cover desktop/phone setup, reconfigure, cache, expiry,
empty-mode error and correction, local-budget waiting, an actual synthetic 429
with 600-second Retry-After, preserved input, resubmission/automatic continuation
and the HACS link. Source counts remain bounded. Only the isolated HA origin is
allowed in the browser; no live user instance or real departure data is involved.
PNG screenshots remain under ignored `.ha-e2e/`.

Final parent visual inspection caught a broken icon in the earlier handoff
capture. The isolated browser fixture had initialized `frontend` without
`brands`, which normal HA bootstrap includes independently in
`DEFAULT_INTEGRATIONS`. The missing brands/token setup left the native image
source empty. A new local-image assertion reproduced that failure.

Starting the real `brands` component in the browser fixture fixed it without
changing production integration code, assets or authentication. Both complete
EN/NL browser runs passed again on minimum/current HA. Before handoff capture,
the actual image must use `/api/brands/integration/ovapi/...`, receive HTTP 200,
complete `HTMLImageElement.decode()` and have `naturalWidth > 0`. All four
recaptured `phone-card-handoff.png` images were visually inspected with the
original icon visible. The separate extracted-package API tests remain in place.

Initial browser harness failures came from clicking the checkbox's covered native
input and keyboard toggling after rerender. Tests now use native label activation
for error recovery and assert the resulting checked state, without forced clicks
or injected application state. The minimum package check was corrected to use
its exact runtime profile, not the development fixture pin. No production version
guard was bypassed.

## Branding/tool evidence

The exact HACS brands validation method at
`adb7d83e33d24325535fb43b8226572405143757` accepted the local `brand/icon.png` path
without CDN lookup. The obsolete HACS exception was removed; no CI trigger or
branch-protection change was made. The normal hosted HACS action remains enabled.

Impeccable context/playbook guidance was applied to native onboarding rather than
replacing HA's visual system. Original artwork was inspected in light/dark
variants. Its mechanical detector returned no findings for the changed native
UI definitions; this does not substitute for the real HA browser evidence above.

## Source limitation and provenance

See [research.md](research.md) for bounded GTFS/CHB/OSM checks. No supplemental
metadata source was adopted, no 247 MB feed downloaded, no guessed `300` prefix
or spatial station membership used. Runtime source retention/backoff is unchanged.

Pinned Spec Kit 1.1.3 specification/plan/task templates were actually resolved,
and setup-plan/setup-tasks/check-prerequisites scripts executed in this worktree.
No extension hooks are registered. This artifact set explicitly preserves the
original unmet station scope rather than representing it as implemented.

## Review handoff

The first hosted run (`38250051535`) caught literal URLs in translated setup
success text. Those now use HA description placeholders backed by constants;
the package guard and public-flow assertion prevent recurrence. Both real native
EN/NL browser scenarios and both 283-test HA suites passed again with the
placeholder-rendered HACS link. The same hosted run's locked backend failed
before tests because the Python release download returned HTTP 504 repeatedly;
no version pin, dependency guard or CI policy was changed to mask that outage.

Convergence checked 32 requirement/acceptance items, eight design decisions and
five constitution principles. One partial FR-014 gap was appended as T018:
time-only pause labels were ambiguous for multi-day Retry-After. A regression
failed before the fix, then passed with date-aware labels for 600- and
90,000-second pauses. The current code satisfies the approved delivered scope;
the original station discovery obligation remains explicitly deferred to #5.

The focused [PR #6](https://github.com/DevSecNinja/home-assistant-ovapi/pull/6)
received native GitHub Copilot review (run `38250041961`, completed successfully).
Its one specific LOW finding identified a checked whole-feature outcome in
`checklists/requirements.md` despite unfulfilled SC-001. The
[review correction](https://github.com/DevSecNinja/home-assistant-ovapi/pull/6#discussion_r4248111743)
leaves that original whole-feature criterion unchecked, links #5, and records
the verified delivered subset separately. T006 records deferral, not station
implementation. The original user goal has not been rewritten or marked complete.

The review reported no other specific code finding and recommended closer human
inspection of scheduler/capacity interactions. The public-interface, concurrency,
late-arrival, cancellation, capacity and request-count evidence remains available
above; passing tests are not a claim of human approval.

Hosted CI `38250613802` passed on `c56f47a483102c936259e1a23cc8848c98b415e5`:
both backend runtimes, HACS with branding enabled, hassfest, actionlint, gitleaks,
dprint, zizmor and yamlfmt. The follow-up checklist correction is documentation
only, and its CI `38250916124` passed on
`59dba47d0e9e97ff3d9f9c8f07bf3199b1aaab44`. The parent confirmed reply
`4248161331` exists and the native review thread is resolved. The subsequent
browser-branding correction changes the harness/evidence only, not production
behavior. This session has not merged any pull request, published a release or
modified a live HA installation.

## Reconciliation with merged main

After PR #4 merged, the user requested resolving PR #6 against
`origin/main` at `2442d3941ccc60622e282e9bfa47b526f70036d6`. A non-rewriting merge
was performed in this PR's existing worktree; this does not merge PR #6 itself.
The initial worktree was clean.

Seven files conflicted:

| Paths                                                                                  | Resolution                                                                                                                                                                                                                                                            |
| -------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `custom_components/ovapi/config_flow.py`, `custom_components/ovapi/coordinator.py`     | Keep final main replacement-credit/reservation safeguards together with the already reviewed interactive queue and pending-waiter accounting. These files remain byte-identical to the pre-merge PR head.                                                             |
| `custom_components/ovapi/strings.json`, `translations/en.json`, `translations/nl.json` | Preserve mode-filter labels/observations and explicitly retain main's EN/NL warning that an empty departure list does not prove no service.                                                                                                                           |
| `tests/test_reconfigure_capacity.py`                                                   | Retain every incoming regression, including the main-only event-gated late-arrival scenario. Adapt that scenario to assert automatic budget waiting, retained old board, ten-stop capacity and successful continuation instead of the superseded hard cooldown error. |
| `tests/ui/test_native_picker.py`                                                       | Retain main's dropdown-dismissal assertion, bilingual reconfiguration and this PR's native branding/image decoding, transport selection and manual-progress coverage.                                                                                                 |

The incoming final `reserve_stop`, `release_stop`, `_capacity_entries` and
`_remember_board` methods were compared structurally during reconciliation.
Incoming policy/specification evidence was preserved rather than selecting an
entire branch wholesale. No versions, entity IDs, runtime request limits,
retention rules, station #5 status or CI triggers changed.

Post-reconciliation validation:

- `mise exec -- uv run --locked pytest tests/test_reconfigure_capacity.py tests/test_manual_progress.py tests/test_transport_filters.py tests/test_config_flow.py --no-cov -q --tb=short --show-capture=no` — passed, 58 targeted tests.
- Both full runtime suites and coverage gates in the table above — passed, 284 tests each.
- `mise run typecheck`, `mise run lint`, `mise run package` — passed.
- Both exact EN/NL native-browser commands above — passed again, including actual local brand HTTP 200, successful image decoding and positive natural width.
- `git diff --check` and conflict-marker scan — passed; no unresolved paths remain.
