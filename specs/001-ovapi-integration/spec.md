# Feature Specification: Responsible OVAPI departures

**Feature Branch**: `devsecninja-ovapi-ha-integration`

**Created**: 2026-10-12

**Status**: Accepted for implementation

**Input**: Develop a Home Assistant integration for v0.ovapi.nl using GitHub
Spec Kit, aligned with Gold/Platinum principles, conservative fair use and solid
tests. NS trains are out of scope; a sibling repository owns modern cards.

## User Scenarios & Testing

### User Story 1 - Configure favourite stops (Priority: P1)

As a resident I can configure several favourite stops, display names, line and
destination filters, and walking duration without managing polling schedules.

**Why this priority**: Favourites are the usable starting point for departure views.

**Independent Test**: Configure, update, reconfigure and remove synthetic favourites.

**Acceptance Scenarios**:

1. **Given** a valid stop, **When** I add it, **Then** it is validated and creates
   one correctly named board entity/device.
2. **Given** the same stop/filter favourite, **When** I add it again, **Then**
   configuration rejects the duplicate without an extra upstream request.
3. **Given** multiple favourites, **When** I update/unload one, **Then** others
   remain active, while removed data/listeners are released.

### User Story 2 - Understand departures and uncertainty (Priority: P1)

As a traveller I can see upcoming supported bus/tram/metro departures, known
delays/cancellations and walking-adjusted leave times through the companion cards.

**Why this priority**: Useful decisions require distinguishing predictions from facts.

**Independent Test**: Deliver synthetic ready/stale/empty/unavailable snapshots.

**Acceptance Scenarios**:

1. **Given** predictions and cancellations, **When** a board is delivered, **Then**
   it preserves known/unknown values and absolute instants across midnight/DST.
2. **Given** an outage, **When** a refresh fails, **Then** the previous board is
   explicitly stale until its original expiry, then unavailable with no departures.
3. **Given** a new card or reconnect, **When** it subscribes, **Then** it receives
   cached data without extra upstream work or extended retention.

### User Story 3 - Operate responsibly (Priority: P2)

As an administrator I can install, troubleshoot and remove the integration while
understanding its data policy, request volume, limitations and quality evidence.

**Why this priority**: Shared infrastructure must stay usable for others.

**Independent Test**: Advance fake time, inspect diagnostics/state storage and package.

**Acceptance Scenarios**:

1. **Given** many entities/cards, **When** time advances, **Then** source request
   volume depends only on the shared scheduler, not the number of viewers.
2. **Given** throttling or network failure, **When** retries occur, **Then** the
   integration backs off and never exceeds its shared request budget.
3. **Given** retained source data, **When** 29 minutes pass or it is unloaded,
   **Then** data disappears and cannot appear in state history or diagnostics.

### Edge Cases

Unknown/leading-zero stop IDs; empty boards; missing optional timetable fields;
malformed responses; oversized responses; HTML error pages; 404/429/5xx;
partial batched responses; repeated user validation; concurrent configuration;
entity registry rename/disable; reconnect; unload during a request; clock changes;
ambiguous/nonexistent Dutch local times; terminal stops; NS/other rail records.

## Requirements

### Functional Requirements

- **FR-001**: Support UI setup/options/reconfiguration, canonical duplicate checks,
  up to ten distinct timing points, and independent favourites with distinct filters.
- **FR-002**: Share one conservative global request floor/cache, batch and deduplicate
  all configured stops, and back off on errors without per-card polling.
- **FR-003**: Keep upstream data transient for at most 29 minutes, including errors,
  reconnects and unload; exclude it from states, history, logs and diagnostics.
- **FR-004**: Preserve explicit ready/stale/unavailable and empty-board semantics.
- **FR-005**: Provide a versioned authenticated/authorized departure feed containing
  instants, line/destination, transport, nullable prediction/cancellation/delay and
  configured walking duration.
- **FR-006**: Exclude NS and other rail services; explain complementary native NS use.
- **FR-007**: Provide English/Dutch setup text, installation/removal/troubleshooting,
  synthetic Amsterdam examples and transparent quality-scale evidence.
- **FR-008**: Deliver deterministic offline tests, per-module coverage above 95%,
  full flow coverage, strict types, lint, packaging and reproducible CI/tooling.
- **FR-009**: Preserve actual Spec Kit methodology and verification artifacts.

### Key Entities

- **Favourite**: User-chosen stop, label, filters and walking duration.
- **Board**: A time-limited source snapshot shared by all favourites for a stop.
- **Departure**: Supported transport with source facts and explicitly unknown fields.
- **Operational status**: Recorder-safe indication of board availability, not a
  native departure sensor suitable for historic departure automations.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All accepted favourites can be created, changed and removed offline
  with synthetic data; duplicates are refused.
- **SC-002**: At most one request starts per 120 seconds per HA instance, including
  setup, user retries and refresh actions; concurrent stops batch into one request.
- **SC-003**: No unexpired source payload survives 29 minutes without a new successful
  fetch; no source departure data reaches persistent HA surfaces.
- **SC-004**: Adding ten viewers introduces zero additional source requests.
- **SC-005**: Every module exceeds 95% coverage, flows reach 100%, and all documented
  backend validation commands pass without public API access.

## Assumptions

- The upstream wiki's conservative retention rule is applied to all operators,
  without relying on its historic exceptions. The linked license is currently
  unavailable; this is not a claim of legal clearance or official polling approval.
- HTTP is the documented working transport; HTTPS currently has an invalid hostname
  certificate. Users must understand this public-data transport limitation.
- Stop IDs are explicitly supplied rather than discovered via a full-data download.
- The shared budget is per Home Assistant instance, not a global public quota.
- HACS custom status only; branding/Core/library publication remain external work.
