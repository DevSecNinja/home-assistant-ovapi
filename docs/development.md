# Development and isolated verification

## Toolchain

Use repository-local [mise](https://mise.jdx.dev/), not global tool settings:

```sh
mise trust
mise install
mise run install
mise run test
mise run typecheck
mise run lint
mise run package
mise exec -- lefthook run pre-commit
```

Python 3.14.8 and uv 0.12.19 are pinned in `.mise.toml`; `uv.lock` pins the entire
test environment, including HA 2026.10.1 and pytest-homeassistant-custom-component
0.13.372. Installation is frozen. `mise run test` fails unless every integration
module exceeds 95% statement **and** branch coverage; config flow requires 100%
in both. There is no aggregate-only escape hatch.

HA now uses **probatio** schemas; do not blindly copy older voluptuous flow
examples. Tests use real config-entry managers, registries, state machines,
coordinator timers and authenticated HA WebSockets. The HTTP client is intercepted
with HA's `aioclient_mock`, not replaced with a canned coordinator result.
`aioresponses` was evaluated but removed because its current constructor is
incompatible with HA's aiohttp 3.14; no production compatibility patch was added.

## Synthetic integration/card E2E

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
`SPECIFY_FEATURE_DIRECTORY=specs/001-ovapi-integration` so fresh checkouts reproduce
feature resolution. Constitution, specification,
plan, research, data model, contract, tasks and verification live in
`specs/001-ovapi-integration/` and `.specify/memory/constitution.md`.

Run `mise run specify -- --help` for the pinned CLI. Never replace these artifacts
with similarly named documents while omitting actual toolkit initialization.

## Organization conventions

Reviewed DevSecNinja/.github at `9170d8c24e95a27dca91e1b7904f1f70a94dd1b0` and
repo-starter at `970ad82787165d0f8673815c08614a13a498a74a`. CI reuses the shared
lint workflow v3.2.0 by full SHA and enables failure gating (its default is false).
HA pytest, ruff, types, packaging, HACS and hassfest are repository-specific jobs.
All run on pull requests, including drafts, without path-filtered required checks.
The pinned reusable lint workflow declares `security-events: write` on nested
checkov/trivy jobs even when those jobs and SARIF upload are disabled. GitHub
validates that declaration before evaluating job conditions, so the caller grants
that permission **only to the shared-lint job**. Other jobs remain contents-read.
The first hosted run demonstrated this static permission requirement; it is a
documented central-workflow limitation, not an enabled publication/upload action.

Canonical EditorConfig, dprint, yamlfmt, gitleaks and Renovate settings are adopted.
Documented deviations: Python uses four-space indentation; generated Spec Kit
assets and the virtual environment are excluded from project formatting; redundant
yamllint and unrelated Go/shell/IaC scanners are disabled. All authored Actions
are checked by actionlint/zizmor. Generated Spec Kit shell files remain upstream
assets rather than being reformatted locally.

Commits and PR titles use Conventional Commits. No workflow publishes packages,
releases or merges code. No global mise defaults or central repositories are changed.
