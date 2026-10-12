# Research: stop-name picker

Verified 2026-10-12 using documentation and implementation, not live datasets.

## Source shape and coverage

**Decision**: Fetch `/stopareacode/` only on demand; fetch departures for exactly
one selected area. Keep area IDs as strings and encode path segments.
**Rationale**: [StopAreaCode wiki](https://raw.githubusercontent.com/wiki/koch-t/KV78Turbo-OVAPI/StopAreaCode.md)
provides town/name metadata. `/tpc/` supplies only code/count pairs.
**Alternatives considered**: Per-point network expansion rejected as scraping.

The [upstream implementation](https://github.com/koch-t/KV78Turbo-OVAPI/blob/master/kv78turbo-api.py),
`queryStopAreas`, returns a `ServerTime` sibling in an area's timing-point map.
Its nested `Stop` insertion condition can omit stop metadata; `addMeta` supplies
town/name on passes when known. Optional line/destination metadata can be absent.
Unknown areas may be omitted; a valid empty response proves no coverage claim.
Do not derive a platform from a code or a direction from numeric LineDirection.

## Native HA progress, lifecycle and serialization

**Decision**: `async_show_progress(progress_task=...)`, progress-done continuation,
public `async_remove` cleanup and `async_notify_flow_changed` expiry notifications.
**Rationale**: HA 2026.10.1 `data_entry_flow.py` owns cancellation, subscribes a
task callback and removes flows on abort/create. `cur_step` otherwise retains
schemas indefinitely. HTTP GET re-enters the current step.
**Alternatives considered**: Repeated rate-limited forms rejected; custom frontend
rejected. Source datasets in task results or flow fields rejected.

The native frontend's `dialog-data-entry-flow.ts` subscribes to flow-change
events once a progress step appears and keeps the subscription until dialog
close. A brief cached progress step preserves that notification path.
Disconnected/suspended browser memory cannot be forcibly erased by a backend;
server expiry and reconnect/replay must fail closed. No browser storage is added.

HA's `helpers/data_entry_flow.py` serializes probatio schemas with
`cv.custom_serializer`; callable schema normalizers are not supported. It does
not log response bodies. Core data-entry-flow logging handles cleanup exceptions
and invalid progress API usage, not successful forms. Verify enabled debug output
and native WebSocket logging separately before adding any narrowly scoped guard.

## Budget and retention

**Decision**: Extend the existing singleton and deadlines, not a separate client.
Bound directory/detail body sizes and decompression; discard unneeded source
fields such as coordinates/messages. Retain only bounded normalized metadata.
**Rationale**: No published numeric quota or available full GOVI license resolves
the conservative project policy. The user's subsequent speed requirement
supersedes the initial all-request floor: background batches retain 120 seconds,
while an instance-wide rolling allowance permits two immediate discovery calls.
No server failure/Retry-After pause can be bypassed.
**Alternatives considered**: Disk cache, background catalogue polling, resetting
age on selection and unbounded per-flow request allowances all rejected.

## Evidence-driven corrections

- Two floor-spaced, metadata-only live checks emitted only outcomes/counts.
  The first strict parser rejected data; aggregate diagnostics found 4,590 areas,
  valid metadata shapes throughout, and eight codes rejected by an undocumented
  ASCII-leading regex. Printable source strings up to ten characters are now
  encoded as complete path segments; batching/traversal delimiters are rejected.
  Synthetic tests cover punctuation, Unicode, query/fragment escaping and literal
  percent sequences. No live catalogue or departures were persisted.
- Actual native rendering reproduced completed-progress events racing frontend
  subscription. Bounded source-free flow-change notification retries now stop on
  continuation, abort, source expiry or shutdown. Browser tests observe actual
  WebSocket subscription acknowledgments/progress frames, not fixed readiness sleeps.
