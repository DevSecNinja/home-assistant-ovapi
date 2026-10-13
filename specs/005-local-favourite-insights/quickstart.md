# Validation quickstart

Use the locked repository-local environments, synthetic HTTP and disposable HA
fixtures only. See [development](../../docs/development.md) for tooling setup.

```sh
mise run test
mise run test-minimum
mise run typecheck
mise run lint
mise run package
mise exec -- lefthook run pre-commit
```

Targeted runtime scenarios live in `tests/test_insights.py`: public states and
registry, scalar retention allowlist, options, source health, board authorization,
all-leaf-disabled behavior, manual updates, reload, deadlines and cleanup.

For joint native proof, provide the peer's built card bundle:

```sh
OVAPI_CARD_BUNDLE=/absolute/path/to/lovelace-ovapi.js \
OVAPI_UI_ARTIFACTS=.ha-e2e/insights \
  mise exec -- uv run --locked --group e2e \
  pytest tests/ui/test_native_insights.py -m frontend --no-cov --timeout=120
```

Expected: native English/Dutch walking duration and configured/ready counts,
three distinct grouped walking-aware departure routes with following vehicles, strict board-only
picker, unavailable board plus useful diagnostics after source disable, unchanged
synthetic upstream count. Screenshots wait for launch-screen removal, fonts and
stable geometry on phone/desktop. Repeat using isolated minimum fixture flags
documented in `docs/development.md`. Never use a real HA token or live schedules.
