# Upstream policy, transport and retention

Verified 2026-10-12. Sources:
[OVAPI wiki](https://github.com/koch-t/KV78Turbo-OVAPI/wiki),
[timing-point documentation](https://github.com/koch-t/KV78Turbo-OVAPI/wiki/TimingPointCode),
[stop-area documentation](https://github.com/koch-t/KV78Turbo-OVAPI/wiki/StopAreaCode),
and upstream `kv78turbo-api.py`.

## What is known, and what is not

The wiki requests comma-separated batching, gzip and an identifying user-agent.
It discourages large downloads and automatic scraping at a small interval.
It links a GOVI data license, forbids storing data more than 30 minutes and names
historic GVB/HTM/Veolia Haaglanden exceptions. Both HTTP and HTTPS variants of the
linked license returned 404 during research, so current complete legal terms and
the exceptions' applicability **could not be independently verified**.

We apply the stricter retention rule uniformly and do not rely on those exceptions.
This implementation is not a legal clearance, an upstream license grant, or an
operator-performance analysis tool. No external email was sent. Users needing
higher volume or analysis should follow the wiki's advice to arrange their own
licensed feed/service with OpenOV.

The fixed HTTP API works. HTTPS hostname verification failed; the client uses the
documented HTTP URL explicitly, sends no credentials, follows no redirects and
does not disable certificate checks. Network observers can see requested stop IDs
and public departures. Treat results as travel information, not a safety guarantee.

## Request budget

One per-HA-instance coordinator owns all upstream access:

- Ordinary board batches (including advanced manual validation) have at least
  120 seconds between starts. Interactive directory/detail discovery has a separate
  **two-request rolling 120-second allowance**, shared by all setup/reconfigure
  flows in this instance. The healthy first pair has no deliberate cooldown even
  immediately after an ordinary poll. These are bounded engineering choices,
  **not published upstream quotas**.
- Up to ten distinct timing-point IDs are deduplicated, sorted and batched in one
  `/tpc/{comma-separated-ids}/departures` request.
- Stop discovery loads `/stopareacode/` metadata on demand, then departures only
  for the selected area. No full-network departure expansion or catalogue polling.
  Identical concurrent lookups share work and cached results consume no allowance.
  A FIFO lock serializes transport. Each lookup defers the next ordinary poll
  by at least 120 seconds. After two lookups, extra queued work can reserve an
  eligible board-polling slot before proceeding; the initial pair is never split
  by a mandatory poll. There are at most two discovery starts plus one ordinary
  batch start in any rolling 120-second window.
- `Accept-Encoding: gzip`, identifying project/version user-agent, 20-second
  timeout, 2 MiB detail/board and 16 MiB directory caps, applied to both received
  and incrementally decompressed bytes. Automatic unbounded decompression is off.
- Both lanes share one failure deadline: errors back off exponentially (four minutes initially, maximum one hour);
  server `Retry-After` delta-seconds or HTTP date can impose a longer pause.
- Empty success is valid. Partial responses affect missing stops, not invented
  cancellation status. Cache reads, card subscriptions and countdowns do not poll.
- Polling stops when no entity/subscription needs it. Memory expiry remains active.
- Both budgets and shared backoff survive flow restart, cache eviction and entry
  reloads, but not a complete HA process restart, and are not
  shared between separate HA installations or other applications on the same IP.

## Retention boundary

Source boards and discovery metadata exist only in bounded runtime memory. Their source fetch instant and
absolute expiry (29 minutes later) never change during replay, filtering, reconnect
or failures. Expiry is checked against wall-clock **and** monotonic time and an
independent timer erases expired cache even during long backoff. Unload discards a
stop board when no other favourite uses it; in-flight responses cannot resurrect
removed stops. New-stop validation caches expire too.
An on-demand area lookup may still hold a normalized copy until its own original
expiry; unload never renews that lifetime.
The directory is capped at 50,000 areas; a detail result at 100 timing points.
At most ten lookup results/tasks and ten interactive setup/reconfigure flows are
admitted, with at most 50 displayed name matches. Coordinates, general messages
and raw records are discarded. Completed tasks return no source dataset.
Cancelling the last waiter cancels queued/in-flight lookup work. Selected boards
inherit the detail result's original timestamps; selection never renews expiry.

Replacing a favourite at the ten-stop limit reserves its prospective timing point
against that favourite's old point only when the old point is unshared. The
working entry and old board are retained until a successful configuration update.
Temporary replacement boards may therefore coexist with the ten configured
boards, bounded by the admitted flows and their original retention deadlines.
Abort, expiry and failed validation release reservations and discard unconfigured
replacement boards; completing the update trims the old unshared board.
Uncommitted changes that would reduce the stop count do not lend capacity to
another flow. Two windows cannot reserve different replacements for one entry,
and an aborted in-flight validation cannot later commit or restore its target.
Manual replacement validation batches at most ten points, omitting the replaced
unshared old point from that request without discarding its cached board.

Native picker schemas are also transient: expiry clears their candidate labels,
notifies an active frontend to reload a source-free retry form, and replay rejects
expired choices. A brief native progress step also establishes this subscription
on cached paths. Flow removal clears labels and cancels pending progress.
Only explicitly selected stable favourite name/code/options are persisted.

HA state attributes contain only contract version and configuration entry ID, with
an operational status state. No departure timestamps, routes, destination lists,
operator data, raw responses or error bodies go to Recorder, restore state,
diagnostics, logs or files. Consequently, there are no historical departure
sensors/statistics or native departure-time automations.

HA 2026.10's WebSocket writer can log outgoing/coalesced frames at DEBUG and pending
frames during slow-client errors. The integration adds a narrow logging filter to
`homeassistant.components.websocket_api.http.connection`, replacing only records
containing our board/departure payload keys. It does not alter log levels, disable
other logging or remove payloads from the actual authorized connection. Tests
exercise real DEBUG-enabled HA WebSockets and coalesced/slow-client log records.
This source-verified compatibility guard must be rechecked on HA upgrades.
The HA 2026.10 HTTP configuration view does not log response bodies, and its
flow-subscription WebSocket excludes user/reconfigure flows. Real HTTP tests with
the relevant core loggers at DEBUG verify that synthetic directory/route labels
are absent. No additional broad logging filter is installed for discovery.

Authenticated card clients receive transient copies, must enforce the unchanged
expiry themselves, and must erase them on expiry/disconnect/unsubscribe. The
companion cards also clear hidden-page state. They must not use localStorage,
sessionStorage, service-worker caches or payload logs.

No application can guarantee timely memory erasure while the operating system,
browser or event loop is suspended, nor prevent an authorized user from deliberately
recording network traffic. Expired data is rejected when execution resumes.
Administrator-installed tracing/third-party clients are outside this implementation's
control; do not use them to persist these payloads.

## Testing

All committed fixtures are synthetic. Routine tests/CI disable external sockets;
HA loopback HTTP/WebSocket fixtures are the only socket exception. The optional
frontend browser test allows only its isolated HA origin. Live research used
documentation, two bounded endpoint HEAD attempts (one TLS failure, one HTTP
success), and a small Amsterdam timing-point batch check. Runtime payloads were
parsed in memory, then discarded; only verification outcomes and static example
identifiers were retained. No API response capture or full-network download.
