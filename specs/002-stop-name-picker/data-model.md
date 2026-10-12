# Discovery data model

- `StopArea`: string code (up to ten characters, safe single path segment), name,
  town; no coordinates. Search compares Unicode-normalized, accent-insensitive
  casefolded town/name tokens. Duplicate display names include their area code.
- `TimingPoint`: numeric string code retaining leading zeros; source name and
  bounded supported line/destination descriptions; normalized board.
- `CachedLookup`: metadata or timing-point collection, original fetched wall
  time, wall expiry, monotonic expiry. Shared across all flows. Expiry or capacity
  eviction discards data; accesses do not renew it.
- `Flow`: lookup key, query, selected ID and user preferences only; temporary
  schema choices share the lookup's deadline and are cleared on remove/expiry.
- `Favourite`: unchanged `{name, stop_id}` plus existing options, unique identity
  and entity registry IDs. Selected board cache inherits lookup timestamps.

Transitions: menu -> directory progress -> search -> area choice -> area progress
-> timing point -> favourite -> existing create/reconfigure. Errors return visible
retry/search/manual controls. Expiry transitions to a source-free retry form.
