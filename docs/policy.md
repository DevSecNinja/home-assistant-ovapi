# Upstream policy, transport and retention

Verified 2026-10-12. Sources:
[OVAPI wiki](https://github.com/koch-t/KV78Turbo-OVAPI/wiki),
[timing-point documentation](https://github.com/koch-t/KV78Turbo-OVAPI/wiki/TimingPointCode),
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

- Minimum 120 seconds between request starts, including config validation,
  retries, concurrent entry setup and manual refresh. This is our conservative
  assumption, **not a published permitted numerical rate**.
- Up to ten distinct timing-point IDs are deduplicated, sorted and batched in one
  `/tpc/{comma-separated-ids}/departures` request. No directory/full-network scrape.
- `Accept-Encoding: gzip`, identifying project/version user-agent, 20-second
  timeout and 2 MiB decompressed-body safety cap.
- Failures back off exponentially (four minutes initially, maximum one hour);
  server `Retry-After` delta-seconds or HTTP date can impose a longer pause.
- Empty success is valid. Partial responses affect missing stops, not invented
  cancellation status. Cache reads, card subscriptions and countdowns do not poll.
- Polling stops when no entity/subscription needs it. Memory expiry remains active.
- The floor survives entry reloads, not a complete HA process restart, and is not
  shared between separate HA installations or other applications on the same IP.

## Retention boundary

Source boards exist only in bounded runtime memory. Their source fetch instant and
absolute expiry (29 minutes later) never change during replay, filtering, reconnect
or failures. Expiry is checked against wall-clock **and** monotonic time and an
independent timer erases expired cache even during long backoff. Unload discards a
stop board when no other favourite uses it; in-flight responses cannot resurrect
removed stops. New-stop validation caches expire too.

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
HA loopback WebSocket fixtures are the only socket exception. Live research used
documentation, two bounded endpoint HEAD attempts (one TLS failure, one HTTP
success), and a small Amsterdam timing-point batch check. Runtime payloads were
parsed in memory, then discarded; only verification outcomes and static example
identifiers were retained. No API response capture or full-network download.
