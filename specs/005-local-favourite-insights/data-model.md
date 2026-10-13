# Data model

| Entity key           | Scope           | Value                                                | Unique ID                       |
| -------------------- | --------------- | ---------------------------------------------------- | ------------------------------- |
| `walking_duration`   | Every favourite | Existing `walking_minutes`, default 0, minutes       | `<entry_id>_walking_duration`   |
| `configured_sources` | Combination     | Number of saved source references, including missing | `<entry_id>_configured_sources` |
| `ready_sources`      | Combination     | Count of source statuses exactly `ready`             | `<entry_id>_ready_sources`      |

All diagnostics share `(ovapi, entry_id)` service-device identity. All are
default-enabled diagnostics without state class or board capability attributes.
Their availability is independent of feed availability while the entity is
loaded. Unload uses normal HA unavailable/removal behavior, not restored values.

Source status transitions use the existing coordinator: ready -> stale on failed
refresh; ready/stale -> unavailable on disable/remove/unload/expiry; unavailable
or stale -> ready on recovery (including successful empty data). The configured
count changes only when source preferences change. No source-health history or
copied departures are maintained by the integration.
