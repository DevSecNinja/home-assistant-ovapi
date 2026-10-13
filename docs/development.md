# Development and isolated verification

## Toolchain

Use repository-local [mise](https://mise.jdx.dev/), not global tool settings:

```sh
mise trust
mise install
mise run install
mise run test
mise run test-minimum
mise run typecheck
mise run lint
mise run package
mise exec -- lefthook run pre-commit
```

Python 3.14.8 and uv 0.12.20 are pinned in `.mise.toml`; `uv.lock` pins both
test environments: development HA 2026.10.1 / pytest-homeassistant-custom-component
0.13.372, and declared minimum HA 2026.10.0 / fixture 0.13.371. Commands use
`--locked`: dependency drift fails instead of silently updating the lock.
Both test tasks fail unless every integration
module exceeds 95% statement **and** branch coverage; config flow requires 100%
in both. There is no aggregate-only escape hatch.

Keep `.mise.toml`'s `min_version` and both CI installation pins (`mise-version`
and the mise action's `version`) aligned. Each pin's immediately preceding Renovate
annotation lets the inherited manager update them together. Compatibility tests
reject stale or unannotated CI pins while allowing coherent version bumps.
The Python pin is the development/CI interpreter, not the HA support floor.
Python 3.15 resolves both HA profiles and passes the proposed Linux CI, but the
native macOS installation is not ready: locked `pycares==5.1.0` builds bundled
c-ares from source and fails on `pipe2` availability with the current macOS SDK,
even with CMake installed. Renovate temporarily allows Python `<3.15` for both
mise and `requires-python`; Python 3.14 patch updates remain managed. Revisit this
constraint when the locked dependencies install normally on macOS, then rerun both
HA suites and native browser checks. Do not patch dependencies, suppress compiler
errors, or raise the HA floor to force the interpreter upgrade.

### Home Assistant compatibility and version changes

`hacs.json`'s `homeassistant` field is the **supported HA minimum authority**.
`scripts/check_compatibility.py` reads it, accepts only stable `YYYY.M.P`
versions (real month, no prerelease/range/prefix), and compares numeric versions
against the **installed** HA distribution before tests and packaging. A declared
minimum newer than the tested runtime fails.

CI runs two real integration-suite jobs: `backend (locked)` and `backend (minimum)`.
The latter requires installed HA to **equal** the declared minimum, not merely
exceed it. The `minimum` dependency group's fixture release must genuinely require
that HA version. The guard verifies the installed fixture matches the group's
exact pin and that its dependency metadata requires the installed HA exactly.
No `--no-deps`, dependency overrides or incompatible fixture reuse are permitted.

`mise run test-minimum` uses `.venv-minimum`, `.coverage-minimum` and
`coverage-minimum.json`, separate from development. The mutually exclusive groups
share one committed `uv.lock`. Both full suites and per-module gates run in
`mise run check`; neither job is path-filtered or skipped for draft PRs.

To deliberately change the supported floor, edit `hacs.json`, select a compatible
fixture release for the `minimum` group, run `mise exec -- uv lock`, and run
`mise run check`. Updating just the HACS field or just the minimum fixture fails
the exact-runtime check. Routine development-fixture/Renovate updates must **not**
automatically raise the minimum; keep the minimum profile intact and test both.
Renovate therefore excludes only this fixture in the `minimum` dependency group;
the development fixture remains managed. Fixture 0.13.372 requires HA 2026.10.1
and cannot replace minimum fixture 0.13.371 while the supported floor is 2026.10.0.
There is no arbitrary maximum HA version or runtime rejection of manual installs.

### Integration release identity

`custom_components/ovapi/manifest.json`'s `version` is the **integration release
authority**, independent of the HA minimum. For a release bump, update that field,
`const.py`'s literal `VERSION`, and `pyproject.toml`'s `project.version` together,
then refresh `uv.lock` and run `mise run check`. The package guard parses the
constant statically (no HA imports/runtime file I/O) and fails with the mismatched
file named. Versions must use canonical three-part PEP 440 syntax, such as `0.2.0`
or `0.2.0rc1`, without epoch or local suffix.

The real async-client request test derives its expected release from the manifest
and verifies `const.VERSION`, `USER_AGENT`, and the outgoing `User-Agent` header.
Coherent version bumps pass; tests are not frozen to `0.1.0`.
Do **not** synchronize `ConfigFlow.VERSION` (persisted config schema),
`contract_version` (card wire protocol), or `v0` in `API_URL` (upstream protocol)
with the integration release or supported HA minimum.

HA now uses **probatio** schemas; do not blindly copy older voluptuous flow
examples. Tests use real config-entry managers, registries, state machines,
coordinator timers and authenticated HA WebSockets. The HTTP client is intercepted
with HA's `aioclient_mock`, not replaced with a canned coordinator result.
`aioresponses` was evaluated but removed because its current constructor is
incompatible with HA's aiohttp 3.14; no production compatibility patch was added.

## Synthetic integration/card E2E

### Native stop-picker browser check

```sh
mise exec -- uv sync --locked --group e2e
mise exec -- uv run --locked --group e2e playwright install chromium
mise run test-ui
```

The optional locked `e2e` group provides HA's matching frontend and Playwright.
The normal/minimum suites exclude the `frontend` marker; they still exercise real
HTTP config/options/reconfigure serialization. `test-ui` launches an isolated HA
fixture on loopback and a browser, intercepts upstream HTTP with synthetic data,
and blocks browser requests outside that test origin. It closes the browser and
server on completion. No user's HA, real token, directory or schedule is used.

Screenshots are written to ignored `.ha-e2e/evidence/`; set `OVAPI_UI_ARTIFACTS`
when invoking pytest directly to retain them elsewhere. Phone/desktop checks
cover cold setup, actual native progress events, cache-only setup, no-match error
recovery and automatic expiry. Time is advanced by the HA test clock, not by
manually advancing configuration steps or reducing production request limits.

The same EN/NL scenarios cover mode selection, explicit empty-selection recovery,
the HACS card handoff, manual-code local waiting and a real synthetic 600-second
server pause. A failed request returns a preserved form; resubmission waits
automatically. Checkboxes are exercised through native keyboard/label interaction,
not injected application state.

Run the same browser checks on the declared minimum without mixing fixture groups:

```sh
UV_PROJECT_ENVIRONMENT=.venv-minimum OVAPI_UI_ARTIFACTS=.ha-e2e/minimum-evidence \
  mise exec -- uv run --locked --no-default-groups --group minimum --group e2e \
  pytest tests/ui/test_native_picker.py -m frontend --no-cov --timeout=60
```

`tests/test_brand.py` builds an isolated installation archive for each runtime,
uses native HA integration discovery on its extracted files, and serves all eight
PNGs through authenticated brands HTTP requests. No CDN fallback is allowed.
The browser harness also starts the real `brands` component: normal HA bootstrap
includes it independently, but starting `frontend` alone does not. Before
capturing setup success, it asserts the actual image uses the local brands
endpoint, receives HTTP 200, decodes successfully and has positive natural width.
`mise exec -- uv run --locked python scripts/render_brand.py` regenerates the
original transit-sign artwork; no network assets or installed fonts are needed.

### Companion-card E2E

For native combined-favourite setup/options/reconfigure and one actual Lovelace
board, supply an already built current card bundle (read-only source). The harness
copies only that bundle to its isolated temporary server:

```sh
OVAPI_CARD_BUNDLE=/absolute/path/to/lovelace-ovapi.js \
OVAPI_UI_ARTIFACTS=.ha-e2e/combined \
  mise exec -- uv run --locked --group e2e \
  pytest tests/ui/test_native_combined.py -m frontend --no-cov --timeout=60
```

This checks both languages, keyboard selection, an invalid one-source submission,
local preferences, source replacement, one two-direction board, source loss and
the unchanged card selector with an unavailable combined entity. The artifact
records the bundle SHA-256 and actual upstream count (one batched request, unchanged
by combining, editing or card rendering). Without `OVAPI_CARD_BUNDLE`, only this
optional browser test skips. Use the minimum environment/group flags above to
repeat against HA 2026.10.0. The current frontend's default overview uses its own
strategy, so this harness creates a separate named storage dashboard.

For local diagnostic device-page proof and the peer's grouped walking-aware
departures card, use the same bundle/environment flags with
`pytest tests/ui/test_native_insights.py -m frontend --no-cov --timeout=120`.
This checks native EN/NL phone/desktop device pages, three source favourites,
configured versus ready counts after source disable, strict board-only selection
and diagnostic WebSocket rejection. The dashboard override never changes the
configured walking diagnostic. Artifact JSON records the exact bundle hash,
public entity values and unchanged synthetic HTTP count.

All three native browser fixtures share `tests/ui/network.py`'s parsed exact-origin
predicate. Only credential-free HTTP(S) URLs with the fixture's scheme, host and
port are allowed; invalid/non-HTTP URLs fail closed. `tests/test_browser_origin.py`
exercises credential-style URLs, prefix-lookalike hosts/ports and malformed
origins as pure strings with sockets disabled, never by following those URLs.

Do not point development tests at a live HA installation or public OVAPI.
The companion repository owns the combined browser/HA scenario. To reproduce its
backend side:

1. Create a separate disposable HA configuration and copy only this repository's
   `custom_components/ovapi` into it.
2. Use the pinned HA runtime plus its matching frontend package; the pytest
   environment intentionally does not install the full frontend.
3. Bind HTTP to **127.0.0.1 only**, use a fresh local test user and choose an unused
   port. Never reuse a real HA token or configuration directory.
4. Before HA initialization, replace `OvapiClient.fetch` in the **test harness**
   with synthetic `parse_board` results, dynamically dated relative to UTC now.
   This is not a production option and must not be installed on a live instance.
5. Initialize HA's loader before bootstrap, load HTTP/auth/frontend/config/Lovelace
   as needed, and use the real UI config flow to add `01234567` labelled
   "Amsterdam Amstel", walking time 5.
6. Install the built companion-card JavaScript as a local Lovelace module and
   select the created `sensor.amsterdam_amstel_departure_board`.
7. Exercise ready, cancellation, stale/expiry, local walking-time edits, reconnect,
   multiple cards and removal. Confirm synthetic source-call count does not rise
   with card count. Stop the bounded server and delete only its disposable
   configuration/artifacts after the check.

For smaller repeatable backend tests, use `tests/test_init.py`,
`tests/test_coordinator.py` and `tests/test_websocket.py` as examples.
`tests/fixtures/card-v1.json` is a standalone synthetic contract snapshot.
No fixture was captured from the public API.

## Spec Kit provenance and workflow

This repository was actually initialized with **specify-cli 1.1.3**, using the
official Copilot integration in default skills mode. Installed skills, templates,
scripts and workflow are preserved under `.github/skills/` and `.specify/`.
Current names are `/speckit-constitution`, `/speckit-specify`, `/speckit-plan`,
`/speckit-tasks`, `/speckit-implement`, `/speckit-converge`; they are agent skills,
not executable terminal slash commands.

The implementation agent read and followed these installed skills directly,
resolved official templates, ran `setup-plan.sh`, `setup-tasks.sh` and
`check-prerequisites.sh`, and executed their successive artifact/implementation
phases without spawning additional agents. `.specify/feature.json` selects the
feature independently of the app-managed Git branch and is upstream-defined local
state (ignored by Git). The repository-local mise environment sets
`SPECIFY_FEATURE_DIRECTORY=specs/005-local-favourite-insights` so fresh checkouts reproduce
feature resolution. Constitution, specification,
plan, research, data model, contract, tasks and verification live in
`specs/001-ovapi-integration/`, `specs/002-stop-name-picker/`,
`specs/003-station-favourites/`, `specs/004-manual-combined-favourites/`,
`specs/005-local-favourite-insights/` and
`.specify/memory/constitution.md`.

Run `mise run specify -- --help` for the pinned CLI. Never replace these artifacts
with similarly named documents while omitting actual toolkit initialization.

## Organization conventions

Reviewed DevSecNinja/.github at `9170d8c24e95a27dca91e1b7904f1f70a94dd1b0` and
repo-starter at `970ad82787165d0f8673815c08614a13a498a74a`. CI reuses the shared
lint workflow v3.2.0 by full SHA and enables failure gating (its default is false).
HA pytest, ruff, types, packaging, HACS and hassfest are repository-specific jobs.
All run on pull requests, including drafts, and on pushes to `main`, without
path-filtered checks. Pushes to other branches do not duplicate PR runs.
Repository-owned jobs use GitHub-hosted `ubuntu-26.04`; the reusable workflow's
runner remains upstream-owned. Actionlint 1.7.12 predates that hosted label, so
`.github/actionlint.yaml` adds only that exact label through its documented
`self-hosted-runner.labels` extension setting. This does not provision or select
a self-hosted runner, use a wildcard, or suppress lint errors. Remove the entry
when the pinned actionlint supports Ubuntu 26.04 natively. Compatibility tests run
the real linter and require unknown runner labels to keep failing.
The pinned reusable lint workflow declares `security-events: write` on nested
checkov/trivy jobs even when those jobs and SARIF upload are disabled. GitHub
validates that declaration before evaluating job conditions, so the caller grants
that permission **only to the shared-lint job**. Other jobs remain contents-read.
The first hosted run demonstrated this static permission requirement; it is a
documented central-workflow limitation, not an enabled publication/upload action.

On the initial PR, HACS's license check reads GitHub repository metadata, which
still reflects the bootstrap default branch without a license. The review branch
includes the MIT `LICENSE`, but HACS reports that metadata check as failed until
an authorized merge updates the default branch. Do not suppress the license check
or modify `main` just to make the initial check green. That initial metadata gap
was resolved by the reviewed merge. Current HACS branding validation accepts
bundled `brand/icon.png`, and the former `brands` exception is removed.

Canonical EditorConfig, dprint, yamlfmt, gitleaks and Renovate settings are adopted.
Documented deviations: Python uses four-space indentation; generated Spec Kit
assets and the virtual environment are excluded from project formatting; redundant
yamllint and unrelated Go/shell/IaC scanners are disabled. All authored Actions
are checked by actionlint/zizmor. Generated Spec Kit shell files remain upstream
assets rather than being reformatted locally.

Commits and PR titles use Conventional Commits. No workflow publishes packages,
releases or merges code. No global mise defaults or central repositories are changed.
