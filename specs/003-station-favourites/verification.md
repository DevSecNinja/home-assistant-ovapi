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
| `mise run test`                                                                                                                 | Passed: 283 tests, HA 2026.10.1 / fixture 0.13.372                    |
| `mise run test-minimum`                                                                                                         | Passed: 283 tests, HA 2026.10.0 / fixture 0.13.371                    |
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
only. The parent session owns posting/resolving the review thread after its
checks. Nothing is merged, released or installed on a live HA.
