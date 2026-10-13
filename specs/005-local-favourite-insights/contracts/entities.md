# Native entities and unchanged board contract

- Original board registry identity remains `sensor/ovapi/<entry_id>` and original
  object-ID suffix remains `departure_board`.
- Only original boards advertise `contract_version: 1` and `board_id`; those
  attributes remain present even when unavailable.
- Added diagnostic entities expose only their scalar value and standard HA
  entity metadata. No fetched/expiry timestamps, departures, destination, lines
  or vehicle-derived counters.
- `ovapi/subscribe` explicitly addressed to a diagnostic returns `not_found`,
  creates no listener and causes no upstream request. Actual board permissions,
  rename and unavailable/reconnect behavior remain unchanged.
- Source-reference resolution selects the original board by exact unique ID,
  never sensor order, friendly name, diagnostic enablement or ready state.
- Existing v1 payloads and configuration schema do not change.
