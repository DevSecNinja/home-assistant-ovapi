# Unchanged v1 board contract

`ovapi/subscribe` accepts the combined sensor entity exactly like a leaf.
`contract_version` remains 1; no `coverage` is emitted.

- `board_id` and `stop.id`: combined config-entry ID.
- `stop.name`: user-supplied combined name.
- `walking_minutes`: combined setting, never an arbitrary source's walking time.
- `departures`: union of source favourite views, fully equal v1 events deduplicated,
  stable expected-or-scheduled instant order, maximum thirty.
- `fetched_at` / `expires_at`: oldest source instants, null when unavailable.
- `status`: conservative all-source availability and any-source staleness.

Entity capability attributes retain `board_id` and `contract_version`, including
unavailable state. Safe source references/health can be shown in HA attributes;
departures and live dates remain exclusively in transient WebSocket messages.
