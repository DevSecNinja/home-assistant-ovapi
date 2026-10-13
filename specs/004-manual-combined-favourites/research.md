# Bounded design decisions

- **Decision**: Persist config-entry IDs and resolve current entity registry records.
  **Rationale**: IDs survive rename and source stop/filter reconfiguration.
  **Alternatives**: Entity names are fragile; nested groups require cycle handling.
- **Decision**: Native multiselect with current names/entity IDs and saved missing IDs.
  **Rationale**: HA serializes and translates native forms; missing references stay
  removable without an upstream lookup. Disabled sources are still choices.
  **Alternatives**: A live-only picker hides the entries that need repair.
- **Decision**: Reuse source snapshots; deduplicate only equal full v1 records,
  and sort timestamp instants. Keep the oldest fetched/expiry times.
  **Rationale**: Honors filters, never guesses trip equivalence, never renews age.
  **Alternatives**: ID-only deduplication loses opposing directions.
- **Decision**: No combined cache; shared-coordinator notifications plus HA registry
  and config-entry changes while groups are loaded.
  **Rationale**: Source loss/recovery is immediate without polling multiplication.
  Combined entity/card listeners use HA's dispatcher passively; unlike ordinary
  coordinator listeners they cannot start or retain polling without leaf viewers.
  **Alternatives**: Per-source brokers or a dependency graph add unnecessary state.
- **Decision**: Capability attributes carry board identity and safe source health.
  **Rationale**: HA `Entity._async_write_ha_state` omits extra attributes when
  unavailable; cards still need discovery and users need affected-source IDs.
  **Alternatives**: Weakening the card selector would hide the backend defect.

Evidence: current `coordinator.snapshot`, `websocket_subscribe`, HA's locked
`config_entries.SIGNAL_CONFIG_ENTRY_CHANGED` and entity capability handling.
No provider research or automatic-station artifacts reused.
