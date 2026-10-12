# Data model

- **Favourite configuration**: `stop_id` (1-10 digits, preserve leading zero),
  `name` (1-80 characters); options `lines` (canonical comma-separated exact line
  numbers), `destination` (case-insensitive substring), `walking_minutes` (0-120).
  Canonical identity is stop + normalized filters, excluding label/walking duration.
- **Departure**: immutable source-normalized record matching contract v1; mandatory
  scheduled instant, optional expected instant/cancellation/delay. Only supported
  bus/tram/metro; unknown modes and rail are discarded, rather than inventing coverage.
- **Cached board**: tuple of departures, successful fetch UTC instant, absolute
  expiry 29 minutes later, monotonic expiry deadline, last-refresh-failed flag.
  Memory only; filters do not duplicate cache or reset clocks.
- **Shared coordinator**: one client and serialized in-flight request per HA;
  next-allowed monotonic instant, failure count, pending validation stop IDs,
  cache, cleanup timer, status listeners. No payload state restore.
- **Entity**: stable unique ID based on config entry ID, device of entry type service.
  Registry renames are respected by WebSocket lookup.

Transitions: no data -> ready on success; ready -> stale on failure; stale -> ready
on success; any cached state -> unavailable at expiry/removal. An empty successful
source board is ready. Missing batched stop entries are failures only for that stop.
