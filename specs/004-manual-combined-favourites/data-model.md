# Data model

- Existing leaf entry data/options and unique IDs remain unchanged.
- Combined entry data: `entry_type: combined`, `name`.
- Combined options: `source_entry_ids` (2-12 unique leaf config-entry IDs),
  `walking_minutes` (integer 0-120, default 0).
- Combined unique ID: canonical sorted source IDs in a disjoint combined namespace.
  Presentation edits do not change board/entity identity.
- Loaded combined IDs are tracked separately from physical stop registrations.
- Derived board: ready if every source ready, stale if any usable source stale,
  unavailable if any source missing, disabled, unloaded, removed or expired.
- No departures, timestamps or runtime objects are persisted for the combination.
- Source diagnostics contain static entry/entity IDs and operational status only.
