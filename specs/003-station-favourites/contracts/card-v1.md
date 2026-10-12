# Card v1 remains unchanged

The authenticated `ovapi/subscribe` payload retains exactly the existing contract:
version, board/entity IDs, stop identity, operational status, fetched/expiry
timestamps, walking minutes and normalized departures.

Mode, exact-line and destination-substring filtering happens before serializing
the existing departure array. No new required keys, station object, transport
configuration echo or duplicate departure records are introduced. Existing board
IDs, registry entity IDs and the legacy ID suffix are preserved.

Only the visible entity name/state translation becomes clearer: this is feed
status, not the departure list. Companion cards still discover the same enum
sensor with `contract_version`/`board_id` attributes.

Future station aggregation must resolve membership and per-platform journey
deduplication in #5 before extending the model; this document does not authorize
silently changing strict card consumers.
