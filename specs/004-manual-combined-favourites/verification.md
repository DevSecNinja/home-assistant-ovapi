# Verification: manual combined favourites

Verified locally on 2026-10-13 from main `dc70075218a78a133d645f4e808afe9f4a67668e`.
No automatic-station code, live Home Assistant, upstream capture or provider
download was used.

## Regression-first evidence

The first public HA regression failed because the native user menu did not offer
`combined`. The implemented regression creates two leaf entries in one actual
intercepted batch, then creates the combination through HA's flow manager and
subscribes over authenticated HA WebSocket. The same trip ID with opposite
destinations remains two departures. The actual HTTP count stays at one.

Additional regressions cover full-record overlap deduplication, different trip
IDs, cancellation and unknown facts, the thirty-row cap, source filters and new
services, a valid empty source, oldest fetch/expiry, stale/recovery, expiry while
building the snapshot, disable/unload/removal, entity rename, source stop
reconfiguration, saved restart configuration, options/reload identity, missing
source replacement, 2-12 bounds, nested/self rejection, capacity and cleanup.

Unrelated registry changes and group metadata changes every thirty seconds must
not postpone the ordinary poll: the count reaches two at 121 seconds. Source
notifications, local options, unload and expiry use listener notification rather
than resetting the polling timer. Source-expiry races fail closed over WebSocket.
An additional regression first reproduced a combined viewer keeping polling
alive when all leaf entities were disabled. Passive HA-dispatcher listeners now
leave the count at one through 121 seconds, a public `update_entity` call, and
source expiry. Leaf manual-update behavior is unchanged.

## Local commands

| Command                                | Result                                                                           |
| -------------------------------------- | -------------------------------------------------------------------------------- |
| `mise run check`                       | Passed: all tasks below, using locked tool versions                              |
| `mise run test`                        | HA 2026.10.1 / fixture 0.13.372: 318 passed, 4 optional browser tests deselected |
| `mise run test-minimum`                | HA 2026.10.0 / fixture 0.13.371: 318 passed, 4 optional browser tests deselected |
| `mise run typecheck`                   | Passed: strict mypy, ten source modules                                          |
| `mise run lint`                        | Passed: ruff, formatting, dprint, yamlfmt, actionlint and zizmor                 |
| `mise run package`                     | Passed: 24 integration files validated; local `dist/ovapi.zip` created           |
| `mise exec -- lefthook run pre-commit` | Passed against staged feature files: formatting, Python lint and strict types    |

Both runtimes report config flow **100% statements / 100% branches**. Every
integration module exceeds 95% in both: coordinator 99.79% / 97.47%, all other
modules 100% / 100%. Coverage checks enumerate modules rather than relying on an
aggregate. `uv.lock`, release versions, supported HA floor and CI triggers are
unchanged.

## Actual native browser and card evidence

Both complete native test files passed in both environments:

```sh
OVAPI_CARD_BUNDLE=/absolute/path/to/lovelace-ovapi.js \
OVAPI_UI_ARTIFACTS=.ha-e2e/combined \
mise exec -- uv run --locked --group e2e \
pytest tests/ui -m frontend --no-cov --timeout=60 -q --tb=short

UV_PROJECT_ENVIRONMENT=.venv-minimum \
OVAPI_CARD_BUNDLE=/absolute/path/to/lovelace-ovapi.js \
OVAPI_UI_ARTIFACTS=.ha-e2e/combined-minimum \
mise exec -- uv run --locked --no-default-groups --group minimum --group e2e \
pytest tests/ui -m frontend --no-cov --timeout=60 -q --tb=short
```

Results: **4 passed per runtime** (EN/NL stop picker and EN/NL combination).
After adding splash-removal/font/geometry waits and the grouped-card assertion,
the same commands restricted to `tests/ui/test_native_combined.py` passed again:
**2 passed per runtime**. Screenshots were inspected after those waits.

This is the actual Home Assistant frontend, not a representation of flow objects.
The browser selects native checkboxes, sees the one-source error, submits the
combination, edits options and replaces a source through native reconfiguration.
A named Lovelace storage dashboard then loads the actual current companion
module with just the combined entity. Both default and grouped modes display one
board with two opposite-direction rows. Disabling a source removes every row;
the unchanged real card editor still offers the unavailable combined sensor.
The actual intercepted upstream count remains **one** throughout.

The read-only supplied bundle was copied into each isolated test server:

- Card source commit: `e84e9483cc0a5611fd70dd383701d4fa8ee67f65`.
- Current card main: `eb99055cfa592305012535829250a97af966130c`, same source tree.
- Measured bundle SHA-256:
  `0d12045dac54fcda844ef3c78aebeb4cf8f98cfaed06a2621535d484ba3d224f`.

Retained evidence is under [evidence/](evidence/): native add/error,
phone reconfigure, phone/desktop default board, phone grouped board, and measured
JSON results for each language/runtime. Browser requests outside the local HA
origin were blocked. Browsers and fixture servers stopped at test completion.
The native-form mechanical detector returned no findings.

## Convergence and limits

Checked nine functional requirements, four success criteria, nine acceptance
scenarios, the six bounded design decisions and all five constitution principles.
No feature-code gaps remain. Convergence identified only persistence of this
verification record and pending PR/hosted-CI delivery; these remain explicit tasks.
No extension hooks are configured.

This deliberately does not solve automatic station membership or close issue 5.
It combines 2-12 existing leaf favourites and cannot expand their filters.
Recreated deleted favourites require manual reselection. Any unusable source
makes the entire board unavailable. Payloads remain transient; ordinary entity
cards and Recorder still cannot access departure rows. No version bump, merge,
release, live installation or primary-checkout write was performed.
