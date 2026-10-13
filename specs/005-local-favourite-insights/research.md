# Research: Local favourite insights

## Passive lifecycle

**Decision**: Reuse `COMBINED_CONTEXT` in `OvapiCoordinator.async_add_listener`
for diagnostics on leaves and combinations; manual update only writes local state.

**Rationale**: Existing dispatcher fans out expiry, source changes and preferences
without registering a polling listener or resetting deadlines. HA's normal
`CoordinatorEntity.async_update` requests a refresh, so diagnostics must override it.

**Alternatives considered**: Regular coordinator listeners would keep polling
alive after leaf boards were disabled. A separate polling/graph coordinator adds
unnecessary lifecycle and cache ownership. Neither is appropriate.

## Identity and availability

**Decision**: Keep original status unique ID exactly equal to config-entry ID,
object-ID suffix `departure_board`, and v1 capabilities. Diagnostic unique IDs use
explicit suffixes; no v1 capabilities. Reject subscription if registry unique ID
does not equal config-entry ID. Keep permission checks for actual boards intact.

**Rationale**: `combined.source_entity` already uses exact registry lookup and is
safe with multiple sensors. `websocket_subscribe` previously accepted every OVAPI
sensor; new diagnostics must not impersonate boards. Registry identity works
while boards are unavailable and with legacy entries lacking new metadata.

**Alternatives considered**: Requiring ready state or state attributes would
break unavailable/legacy subscriptions; selecting the first registry sensor would
break rename and source health.

## Native presentation

**Decision**: Default-visible diagnostic category, duration device class with
minutes but no state class, source counts without units or state class. Labels
explicitly distinguish configured sources from sources with ready feeds.

**Rationale**: The native page owns layout; these are not controls, measurements,
passenger schedules or fabricated Activity events. Configuration stays useful
through outages. Ready count excludes stale feeds and includes valid empty feeds.

**Alternatives considered**: Hidden diagnostics would not address the empty
page; a number control duplicates existing preferences; departure counts violate
the retention boundary.

No unresolved research questions. Findings come from current repository and
installed HA 2026.10.1 `helpers/update_coordinator.py`; no upstream requests.
