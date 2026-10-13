# Feature Specification: Local favourite insights

**Feature Branch**: `devsecninja-local-favourite-insights`

**Created**: 2026-10-13

**Status**: Accepted

**Input**: "Also the integration page looks quite empty. Can we add some useful
sensors/insights there without having to query the backend?"

## User Scenarios & Testing

### User Story 1 - See configured walking duration (Priority: P1)

Every favourite's native device page shows its configured walking duration without
opening preferences or contacting the transport service.

**Why this priority**: Useful context for both single-stop and combined favourites.

**Independent Test**: Open a favourite, change walking duration in existing
preferences, and observe the read-only insight change locally.

**Acceptance Scenarios**:

1. **Given** any favourite, **When** its device page opens, **Then** configured
   walking duration is visible in minutes, including zero.
2. **Given** an unavailable departure feed, **When** the device page opens,
   **Then** the configured duration remains visible.

### User Story 2 - Diagnose combined source health (Priority: P1)

A combination shows separately how many source favourites are selected and how
many have ready, non-stale feeds, even while the combined board is unavailable.

**Why this priority**: Distinguishes partial source loss from complete loss without
misrepresenting an incomplete board as usable.

**Independent Test**: Disable one of three sources and observe two ready sources,
three configured sources, and an unavailable combined board.

**Acceptance Scenarios**:

1. **Given** three ready sources, **When** one is disabled, removed, unloaded or
   expires, **Then** configured count stays three, ready count becomes two, and
   existing feed status explains that the board is unavailable.
2. **Given** a stale source, **When** health is displayed, **Then** that source
   is not counted as ready; a successful empty response does count as ready.
3. **Given** changed source selection, **When** preferences are saved, **Then**
   counts reflect the selection without fetching or extending cached data.

### Edge Cases

- Missing saved sources count as configured, not ready.
- Disabled departure boards must not be treated as ready because their diagnostics
  remain enabled. Renames and source reconfiguration keep the correct identity.
- All ordinary leaf boards/viewers disabled: diagnostics remain useful without
  sustaining or starting transport-service polling.
- Reload and manual updates do not add requests or postpone ordinary deadlines.
- Unloading a favourite removes its diagnostic subscriptions and live states.

## Requirements

### Functional Requirements

- **FR-001**: Show configured walking duration for every favourite using existing
  preferences only; do not introduce another configuration control.
- **FR-002**: Show configured source-favourite count and ready source-favourite
  count for manual combinations only.
- **FR-003**: Keep diagnostics visible by default on the native device page in
  English and Dutch, with configuration distinct from operational readiness.
- **FR-004**: Diagnostics MUST remain available when the feed is unavailable,
  provided their own favourite is loaded.
- **FR-005**: Creation, viewing, manual updates and local edits MUST add no
  transport requests, polling ownership, deadline resets or departure copies.
- **FR-006**: Preserve the existing board's identity, card eligibility, source
  references and permissions; diagnostic entities MUST NOT act as boards.
- **FR-007**: Persist no departure records, travel times, source timestamps,
  destinations, lines or vehicle-derived counts in diagnostic states.
- **FR-008**: Reflect source loss, staleness, expiry, recovery and preferences
  locally and release listeners on unload.
- **FR-009**: Do not add fabricated Activity events, automatic station discovery,
  config-flow changes or a new card protocol.

### Key Entities

- **Favourite**: Configured name, walking duration and existing departure board.
- **Combination**: Favourite referencing a selected set of single-stop favourites.
- **Diagnostic insight**: Read-only configuration or current operational value,
  not a passenger schedule or new data source.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Every loaded favourite shows one walking-duration insight; every
  loaded combination also shows exactly two source-count insights.
- **SC-002**: Three selected sources with one lost feed visibly show three
  configured and two ready while the combined board is unavailable.
- **SC-003**: Added insights cause zero additional transport requests through
  creation, viewing, edits and manual refresh; all-leaf-disabled polling stays off.
- **SC-004**: English/Dutch phone and desktop native pages display accurate values,
  and companion-card selection contains only actual departure boards.
- **SC-005**: Departure records and source timestamps never enter the new states,
  and source recovery updates health without recreating favourites.

## Assumptions

- Manual combinations from merged PR #7 are the baseline.
- "Without querying the backend" means using configuration and existing runtime
  health, never an additional transport-service request.
- Default-visible diagnostic categorization uses Home Assistant's native layout.
- The companion session owns walking-aware departures-card improvements; this feature supplies
  joint synthetic native-page/card proof without taking over that implementation.
