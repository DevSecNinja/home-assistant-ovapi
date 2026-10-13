# Validation guide

Use the repository-local mise environment and synthetic HTTP fixtures only.

```sh
mise exec -- uv run --locked pytest tests/test_combined.py
mise run test test-minimum typecheck lint package
OVAPI_CARD_BUNDLE=/absolute/path/to/lovelace-ovapi.js mise exec -- uv run --locked --group e2e pytest tests/ui/test_native_combined.py -m frontend --no-cov --timeout=60
mise exec -- lefthook run pre-commit
```

Native browser scenario: create two leaf favourites, add OVAPI > Combine existing
favourites, select both, name the group and set walking time. Select just its
entity in the current companion card. Both directions must render as one board.
Repeat add/reconfigure in English and Dutch. Source loss must clear the feed and
preserve card discovery. Check actual intercepted HTTP counts before/after.

No live Home Assistant, provider downloads, release or merge is part of validation.
