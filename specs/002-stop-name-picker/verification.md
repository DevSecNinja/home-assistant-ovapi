# Stop-picker verification

Date: 2026-10-12. New branch `devsecninja-ovapi-stop-name-picker` starts at merged
main `42cc323`; the previous implementation PR is not reopened. No releases,
merges or live Home Assistant modifications are performed.

## Final policy and compatibility

The user's speed correction supersedes the initial all-request 120-second floor.
Normal setup can perform the directory and selected-area request immediately,
including immediately after a board poll. One instance-wide monotonic deque limits
discovery to two starts per rolling 120 seconds, not two per flow. Every request
shares transport serialization, request counting and response-relative
failure/Retry-After backoff. Each discovery start defers ordinary polling; only
extra lookups after the pair can reserve an eligible board refresh for fairness.
Background batches remain at least 120 seconds apart.

Tests assert actual intercepted HTTP counts: the first pair needs no minute-scale
clock advance, selected-stop validation adds no third request, staggered starts
enforce a rolling rather than fixed window, and eviction/cancellation/reopening
cannot reset the allowance. Server backoff blocks unused interactive capacity too.

Original wall/monotonic expiry remains 1740 seconds, with no source-age reset on
selection or replay. Cached lookup tasks return no dataset, active form schemas
discard labels on expiry, and flow abort cancels pending work. Valid empty timing
points remain selectable with no invented transport mode/direction. Known
unsupported-only points are excluded; departures remain bus/tram/metro only.

Manifest/project/User-Agent remain 0.1.0. Configuration schema and card contract
remain version 1. HACS minimum remains 2026.10.0 with exact fixture 0.13.371;
locked development remains HA 2026.10.1 with fixture 0.13.372. No migration needed.

## Executed local checks

| Command                                                                    | Result                                                                                            |
| -------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `mise run test`                                                            | Passed: 246 tests on locked HA 2026.10.1                                                          |
| `mise run test-minimum`                                                    | Passed: the same 246 tests on exact HA 2026.10.0                                                  |
| `mise exec -- uv run --locked pytest tests/test_discovery.py -q --no-cov`  | Passed: 54 tests, including maximum-size cached search under one second                           |
| `mise run test-ui -- -q --tb=short --show-capture=no`                      | Passed: real HA frontend, 1 browser scenario, 7.60 seconds                                        |
| `mise run typecheck`                                                       | Passed: strict mypy, all nine integration modules                                                 |
| `mise run package`                                                         | Passed: 15 integration files, translations and unchanged version guards                           |
| `mise run lint`                                                            | Passed: ruff, dprint, yamlfmt, actionlint and offline zizmor                                      |
| `mise exec -- lefthook run pre-commit`                                     | Passed with the implementation staged: formatting, Python lint and strict types actually executed |
| `mise exec -- gitleaks git --staged --no-banner --redact --log-level warn` | Passed                                                                                            |

Every integration module has 100% statement coverage. Coordinator branches are
97.67%; all other modules, including config flow, have 100% branch coverage.
The normal/minimum suites intentionally deselect the optional browser scenario;
it runs separately with the pinned `e2e` dependency group.

The public-flow suites include real HTTP setup, options and reconfigure forms,
not only probatio form objects. The browser harness observes actual WebSocket
subscription acknowledgments and progressed frames before fake-time advancement;
there are no fixed readiness sleeps and no manual flow-manager advancement in
its browser journey. Only its loopback HA origin is permitted in the browser.

## Actual native frontend evidence

HA 2026.10.1, frontend 20260930.3, Chromium 141 (Playwright 1.56.0). Desktop
1280 x 900 and phone 390 x 844. All data and account state are synthetic.

- [Desktop town/name choices](evidence/desktop-stop-search.png)
- [Phone timing-point selection](evidence/phone-timing-point.png)
- [Phone exhausted-allowance progress](evidence/phone-progress.png)
- [Phone no-match recovery](evidence/phone-search-error.png)
- [Phone automatic expiry/retry](evidence/phone-expired-selection.png)

The first cold setup creates a loaded favourite with two immediate requests.
A second cache-only setup adds none. The native UI continues after actual progress
events, shows a no-match error, recovers, and switches automatically to a
source-free retry form at original expiry. A separate exhausted-allowance case
waits visibly, then continues automatically without weakening production limits.
The HA test clock advances time; this is not a real-network latency benchmark.

The same actual-browser scenario also passed on **minimum HA 2026.10.0** with
fixture 0.13.371 in **8.79 seconds**:

```sh
UV_PROJECT_ENVIRONMENT=.venv-minimum OVAPI_UI_ARTIFACTS=.ha-e2e/evidence-minimum mise exec -- uv run --locked --no-default-groups --group minimum --group e2e pytest tests/ui/test_native_picker.py -m frontend --no-cov -q --timeout=60 --tb=short --show-capture=no
```

Minimum-runtime screenshots remain in `.ha-e2e/evidence-minimum/`; the
[minimum-runtime phone timing-point view](evidence/phone-timing-point-minimum.png)
is also committed. No dependency overrides or mixed incompatible fixture groups
were used.

An early browser run reproduced a genuine lost fast-progress event: HA emits it
before the frontend subscribes. The fix retries only source-free flow-change
notifications at 1-to-30-second intervals until continuation, abort, expiry or
shutdown, with a 29-minute ceiling. It neither delays an upstream request nor
adds a polling endpoint. Both cold and cache-only browser paths exercise it.

Screenshots are committed under `specs/002-stop-name-picker/evidence/`.
Original harness outputs remain at `.ha-e2e/evidence/` in this worktree.
The browser and temporary HA server are stopped by fixture cleanup.

## Bounded live source verification

Three metadata-only requests were made, each spaced beyond the original
120-second floor. The first exposed an over-restrictive ASCII-leading area-code
regex. Aggregate diagnostics found 4,590 records, valid town/name metadata
throughout, and eight five-/six-character codes rejected by that regex.

After accepting printable source codes up to ten characters, rejecting
traversal/batching delimiters and encoding complete URL segments, the actual
production `OvapiClient.fetch_directory()` **passed with 4,590 parsed areas**.
Only outcomes/counts were emitted. No live catalogue, coordinates, departures or
response bodies were saved. Punctuation/Unicode/URL-encoding regressions use
synthetic fixtures. No live selected-area departures were needed for this check.

## HACS installation links and remaining boundaries

The user's additional request adds the official My Home Assistant HACS repository
badge to English/Dutch backend installation docs, with owner/repository/category
verified against the live redirect page. It opens HACS repository confirmation,
requires HACS already installed, and does not silently install anything. Manual
instructions remain. The companion-card badge is coordinated separately.

HTTP transport, incomplete/variable coverage, unknown mode at empty points, the
unavailable linked full GOVI license and lack of a published numeric quota remain
explicit limitations. Suspended/disconnected browsers cannot be forcibly erased;
active dialogs update, backend data expires and replay fails closed. Full companion
card E2E is not rerun because the wire contract is unchanged.

## Hosted checks

Implementation commit `335f5d5` is reviewed in
[PR #3](https://github.com/DevSecNinja/home-assistant-ovapi/pull/3).
[Hosted run 38238395735](https://github.com/DevSecNinja/home-assistant-ovapi/actions/runs/38238395735)
passed both Linux runtime lanes, official HACS, hassfest and all enabled shared
organization lint jobs. Unlike the old pre-merge implementation PR, HACS's
repository-license check now passes against merged main.

`gh pr checks 3 --repo DevSecNinja/home-assistant-ovapi --watch --interval 15`
completed successfully. User-requested GitHub Copilot review is coordinated by
the parent; processing its feedback remains a separate tracked delivery gate.

## Convergence assessment

All 10 functional requirements, 5 success criteria, 7 acceptance scenarios,
9 plan decisions and 5 governing principles were assessed. No production-code
gap remained. The native search/progress description was aligned with the actual
rendered controls and local/hosted evidence is recorded. GitHub Copilot review
feedback is the remaining tracked delivery gate.

## Post-merge Copilot review follow-up

The user merged PR #3 before the six review comments were resolved. The fix
commit was preserved locally without pushing that merged branch, then
cherry-picked onto a new `devsecninja-picker-review-fixes` branch from merged main
`696a326`. No station-wide feature, manual interactive-budget redesign, branding
or transport-mode filtering is included in this follow-up.

| Original review comment                                 | Correction and evidence                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| ------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `4247197172` - replacement at ten-stop capacity         | Flow-owned prospective reservations allow replacement of an unshared old point while retaining the working entry/board until success. Shared old points still count, concurrent replacements cannot double-spend capacity, shrinking edits cannot lend future capacity, and aborted in-flight validation cannot commit or restore a target. `tests/test_reconfigure_capacity.py` covers picker/manual paths, failure, abort, identity/options and concurrency. |
| `4247197237` - bilingual add/reconfigure evidence       | Actual browser scenario now runs in English and Dutch using HA's selected language and translated native entry menus; both addition and reconfiguration preserve entity ID and options. Both minimum and locked HA runs pass.                                                                                                                                                                                                                                  |
| `4247197298`, `4247197336` - English empty-list wording | Canonical strings and English translation now say an empty departure list does not mean that no services operate.                                                                                                                                                                                                                                                                                                                                              |
| `4247197388` - Dutch empty-list wording                 | Natural singular wording: "Een lege vertreklijst betekent niet dat er geen diensten rijden."                                                                                                                                                                                                                                                                                                                                                                   |
| `4247197419` - HACS prerequisite spelling               | Corrected "geïnstalleerd" in the Dutch installation instructions.                                                                                                                                                                                                                                                                                                                                                                                              |

Red/green evidence: four initial full-capacity regressions failed before the fix;
additional uncommitted-capacity and abort-in-flight regressions also failed
before their corrections. The original active board remains available until
successful configuration update, rather than being deleted to make space.
Temporary new boards are bounded by active flow reservations and retain their
original source-age deadlines; ordinary ten-point batches and request budgets
are unchanged.

| Final follow-up command                                                                                                                                                                                                                                                 | Result                                                                                                                  |
| ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `mise run test`                                                                                                                                                                                                                                                         | Passed: 256 tests on HA 2026.10.1 / fixture 0.13.372; two optional browser cases deselected                             |
| `mise run test-minimum`                                                                                                                                                                                                                                                 | Passed: 256 tests on exact HA 2026.10.0 / fixture 0.13.371                                                              |
| `mise run test-ui -- -q --tb=short --show-capture=no`                                                                                                                                                                                                                   | Passed: English and Dutch native add/reconfigure/cache/error/expiry/exhausted-budget journeys, 2 tests in 19.63 seconds |
| `UV_PROJECT_ENVIRONMENT=.venv-minimum OVAPI_UI_ARTIFACTS=.ha-e2e/evidence-minimum mise exec -- uv run --locked --no-default-groups --group minimum --group e2e pytest tests/ui/test_native_picker.py -m frontend --no-cov -q --timeout=60 --tb=short --show-capture=no` | Passed: the same two native bilingual journeys on minimum HA, 18.41 seconds                                             |
| `mise run typecheck`                                                                                                                                                                                                                                                    | Passed: strict mypy for all nine integration modules                                                                    |
| `mise run package`                                                                                                                                                                                                                                                      | Passed: all 15 integration files, translation parity and unchanged version guards                                       |
| `mise run lint`                                                                                                                                                                                                                                                         | Passed: ruff, dprint, yamlfmt, actionlint and offline zizmor                                                            |

Per-module statements are 100%; coordinator branches are 98.25%, all other
modules including config flow have 100% branches. This supersedes the original
implementation's test totals and coverage above.

Fresh, synthetic screenshots are committed in `evidence/review-fixes/`:

- [English reconfigure](evidence/review-fixes/en/phone-reconfigure.png) and
  [Dutch reconfigure](evidence/review-fixes/nl/phone-reconfigure.png).
- [Minimum HA English reconfigure](evidence/review-fixes/en/phone-reconfigure-minimum.png)
  and [minimum HA Dutch reconfigure](evidence/review-fixes/nl/phone-reconfigure-minimum.png).
- [English desktop search](evidence/review-fixes/en/desktop-stop-search.png) and
  [Dutch desktop search](evidence/review-fixes/nl/desktop-stop-search.png).
- [Dutch exhausted-budget progress](evidence/review-fixes/nl/phone-progress.png)
  and [Dutch expired-choice recovery](evidence/review-fixes/nl/phone-expired-selection.png).

The original six threads remain owned by the coordinator for replies/resolution
after verifying the new PR. Hosted and follow-up review results will be recorded
after that PR is opened.
