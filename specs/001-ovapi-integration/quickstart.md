# Backend validation quickstart

1. Install mise, trust this checkout, then `mise install`.
2. `mise run install` creates a local locked Python environment.
3. `mise run test` runs only synthetic offline tests and per-module coverage gates.
   `mise run test-minimum` runs the same suite against the exact HACS-declared HA
   minimum in its separate, locked environment with a compatible fixture release.
4. `mise run lint`, `mise run typecheck`, `mise run package` verify quality/packaging.
5. Use `docs/card-contract-v1.md` and the synthetic fixture for companion-card tests.

Expected outcomes: setup/reconfigure/options/unload tests pass, all integration
modules exceed 95% coverage and config flow reaches 100%; shared request spacing,
backoff and source expiry are asserted with fake time. There are no public API
requests in tests, CI, package checks or card subscriptions.

Installation and isolated HA/card E2E instructions will be included in user docs.
Never run development experiments against the user's live Home Assistant instance.
