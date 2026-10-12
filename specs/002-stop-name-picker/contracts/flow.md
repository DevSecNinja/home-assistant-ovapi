# Native configuration contract

The initial menu offers name search and advanced manual code entry. Reconfigure
offers the same picker plus editing existing configuration. Name search uses a
local query followed by searchable `town - stop name (area code)` choices.
Timing-point choices append source-provided lines/destinations and the internal
code to distinguish otherwise identical labels.

Progress is cancellable using the native close button and resumes automatically
when loading completes or capacity becomes available. Normal cold setup has no
intentional minute-scale wait: its directory and detail requests use a shared
two-request allowance per rolling 120 seconds. Extra uncached lookups or server
backoff can wait; cached paths consume no allowance. No per-keystroke requests.
Errors and expiry provide explicit retry/search/manual recovery; no hidden switch
to manual mode and no claim that empty source data means no services.

Options and [card contract v1](../../../docs/card-contract-v1.md) do not change.
Configuration version 1 and release 0.1.0 remain independent and unchanged.
