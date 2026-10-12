# Validation quickstart

Use only this worktree and synthetic fixtures, never a live Home Assistant.

```sh
mise trust
mise run test
mise run test-minimum
mise run typecheck
mise run lint
mise run package
mise run test-ui
```

Minimum runtime frontend:

```sh
UV_PROJECT_ENVIRONMENT=.venv-minimum OVAPI_UI_ARTIFACTS=.ha-e2e/minimum-evidence \
  mise exec -- uv run --locked --no-default-groups --group minimum --group e2e \
  pytest tests/ui/test_native_picker.py -m frontend --no-cov --timeout=60
```

Expected: shared exact-deadline manual waiting, late/concurrent calls, cancellation,
real server pause and preserved form values; local mode filtering/new metro lines;
legacy identity/contract; authenticated PNG serving from an extracted package.
English/Dutch browser checks use native progress events, keyboard-accessible mode
selection and the real setup-success card link.

`scripts/render_brand.py` regenerates original artwork without asset/font downloads.
Station aggregation is not a validation claim of this delivery; see #5 and
[research](research.md).
