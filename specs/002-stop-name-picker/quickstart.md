# Validation quickstart

Use this worktree only; no releases or live Home Assistant changes.

1. `mise run install` restores locked dependencies.
2. `mise run test` runs the locked runtime and per-module coverage gate.
3. `mise run test-minimum` runs the exact supported minimum in isolation.
4. `mise run typecheck`, `mise run lint`, `mise run package` check production code
   and integration packaging.
5. Run the synthetic isolated frontend harness documented in verification.md;
   inspect phone/desktop search, progress, candidate selection, errors and
   reconfiguration. Stop the temporary server afterwards.

Expected: two lookup requests on a cold unconfigured instance, no third selected
stop validation, shared same-key concurrency, original-age expiry, and preserved
IDs/options. Hosted CI additionally runs official hassfest and HACS validation.
