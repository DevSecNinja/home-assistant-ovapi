# OVAPI card contract v1

Departure data lives only in backend memory and authenticated WebSocket events,
never in HA states/attributes, Recorder, diagnostics, logs, restored state, files,
or browser persistent storage. Source boards expire 29 minutes after a successful
fetch. Reads, filtering, reconnects and failures never extend expiry.

Subscribe through the existing Home Assistant connection:

```json
{"id": 42, "type": "ovapi/subscribe", "entity_id": "sensor.amsterdam_departures"}
```

HA acknowledges the subscription, then emits an immediate snapshot and subsequent
full replacements as standard event envelopes (`id`, `type: event`, `event`).
Use standard `unsubscribe_events` to unsubscribe. Entity read permissions apply.
Subscriptions never initiate upstream requests.

The operational sensor has state `ready`, `stale`, or HA `unavailable`, and static
capability attributes `contract_version: 1`, `board_id` (configuration entry ID),
including while unavailable. Departure
lists are not state attributes. Display names are user-configured.

## Snapshot

See `tests/fixtures/card-v1.json`, which is entirely synthetic, not real service
coverage. Fields:

| Field                      | Meaning                                           |
| -------------------------- | ------------------------------------------------- |
| `contract_version`         | Integer 1; reject unsupported versions visibly.   |
| `board_id`, `entity_id`    | Configuration entry ID and current entity ID.     |
| `stop.id`, `stop.name`     | Configured timing-point ID and display name.      |
| `status`                   | `ready`, `stale`, or `unavailable`.               |
| `fetched_at`, `expires_at` | UTC ISO instants, nullable when unavailable.      |
| `walking_minutes`          | Configured nonnegative integer walking duration.  |
| `departures`               | Array, including for empty/unavailable snapshots. |

Each departure has nonempty strings `id`, `line`, `destination` (maximum 512
characters each). Records with missing schedule/line/destination metadata are
omitted, not replaced with invented source data. `transport` is `bus`,
`tram`, `metro`, or `unknown`; `scheduled_at` is an offset-qualified instant;
`expected_at` is an offset-qualified instant or null; `cancelled` is bool or null;
`delay_seconds` is int or null. Null preserves unknown source information.
Rail services are excluded. No platform field is defined in v1.

`ready` means the last refresh succeeded, including an empty board. `stale`
means a refresh failed but retained data has not expired. `unavailable` requires
empty departures and null fetch/expiry times. None of these board statuses implies
cancellation or absence of service. A null departure field means that information
is unknown.

## Countdown and retention

Departure time is `expected_at` when present, else `scheduled_at`. Leave time is
departure time minus `walking_minutes`. Cards tick locally, hide elapsed
departures, and never show actionable leave countdowns for cancelled departures.
Use HA's configured locale/time zone; instants remain safe across midnight/DST.

Cards must explicitly label stale data and independently erase source data at
`expires_at`, even without a backend event. Disconnect and unsubscribe also erase
payloads. No localStorage/sessionStorage, client logs, or persisted payloads.
The backend actively erases expired boards and emits unavailable snapshots.

Breaking changes require a new version and coordination with lovelace-ovapi.
Additive optional fields may be introduced within v1.

## Manual combined favourites

A manual combination is another v1 sensor/feed; select it alone for one card
board. Its `stop.id` equals its stable configuration-entry ID and `stop.name` is
the user's combined name. `walking_minutes` belongs to the combination.
Source favourite filters apply before merging, sorting and limiting to thirty
departures. Only equality of all v1 departure fields permits deduplication.

All selected leaf sources must be usable. A missing/disabled/unloaded/expired
source makes the combination unavailable, with no departures and null dates.
Otherwise any stale source makes the combination stale. Fetch and expiry dates
are the oldest selected source instants, never the combination/replay time.
No `coverage` field is emitted: selected favourites are not verified platforms.

Safe combined entity attributes `source_entry_ids`, `source_count` and
`unavailable_sources` help repair configuration. They contain references and
user-configured labels, not departure data or live timestamps.
