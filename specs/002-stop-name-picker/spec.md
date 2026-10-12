# Feature Specification: Stop-name picker

**Feature Branch**: `devsecninja-ovapi-stop-name-picker`

**Created**: 2026-10-12

**Status**: Accepted

**Input**: "I see I need to provide a timing point code. That's not user friendly,
can't we do a call to the API to request these and just present a list to the user?"
Followed by: "Ok lets implement it".

**User-directed revision, 2026-10-12**: "How long does the initial setup take?
I think 5 minutes to wait to complete the setup is way too long." Normal setup
must not intentionally wait minutes between its two discovery requests.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Find a stop by name (Priority: P1)

A traveller adds a favourite using town and stop names, without researching an
internal identifier. Nearby stop signs/directions are distinguished using only
available source information.

**Why this priority**: External code research blocks ordinary setup.

**Independent Test**: Complete setup using a synthetic town, a matching stop area
and one of its supported timing points.

**Acceptance Scenarios**:

1. **Given** a cold directory, **When** the user searches by town/name, **Then**
   they see cancellable progress followed by labelled choices, without repeated
   submission during the request cooldown.
2. **Given** duplicate names or accented names, **When** the user searches,
   **Then** matching is case/accent insensitive and choices remain distinguishable.
3. **Given** a selected area, **When** its timing points load, **Then** available
   bus/tram/metro direction/line information helps selection; absent facts are
   not fabricated and trains are not offered.

### User Story 2 - Change an existing favourite (Priority: P1)

An existing user changes a timing point using the same picker without replacing
their favourite identity, entity or local options.

**Why this priority**: Installed users must benefit without losing dashboards.

**Independent Test**: Reconfigure a loaded entry and check its entity ID, walking
time, filters and duplicate detection.

**Acceptance Scenarios**:

1. **Given** an existing favourite, **When** the user selects another timing point,
   **Then** the existing favourite is updated and unaffected options are preserved.
2. **Given** an already configured stop/filter combination, **When** it is selected,
   **Then** duplicate handling is unchanged and no redundant validation occurs.

### User Story 3 - Recover or enter a code (Priority: P2)

The user can retry a failed lookup, change their search, cancel, or deliberately
choose advanced manual-code entry.

**Why this priority**: Incomplete upstream data must not strand configuration.

**Independent Test**: Exercise missing/malformed/oversized/failed responses and
manual entry through public configuration interfaces.

**Acceptance Scenarios**:

1. **Given** no matching metadata or no supported candidates, **When** lookup
   finishes, **Then** the explanation does not claim there are no services and
   offers retry/search/manual recovery.
2. **Given** an expired or abandoned selection, **When** its original retention
   deadline passes, **Then** downloaded candidates are discarded and refreshed
   selection is required rather than replaying expired data.

### Edge Cases

- Leading-zero timing points; nonnumeric area codes; unsafe path delimiters.
- Same name in different towns, multiple directions, absent optional metadata.
- Missing area, empty directory, malformed records, oversized compressed data.
- Concurrent flows, cancellation while queued/in flight, clock rollback, backoff.
- Existing polling competing with lookup, maximum distinct stops, stale selection.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Normal setup and reconfiguration MUST offer town/name discovery and
  source-labelled timing-point selection in English and Dutch.
- **FR-002**: The directory MUST load only on demand; searching cached metadata
  MUST NOT make a request per keystroke or expand the whole network's departures.
- **FR-003**: Discovery and detail MUST share one instance-wide allowance of two
  requests per rolling 120 seconds, independent of the background polling
  cooldown. Background batches remain at least 120 seconds apart. All traffic
  shares serialization, observability and response-relative failure/backoff
  deadlines; interactive setup MUST NOT bypass a server pause. Extra lookups must
  remain bounded and neither polling nor discovery may starve indefinitely.
- **FR-004**: Healthy normal cold setup MUST permit its first two discovery
  requests without an intentional minute-scale pause, even immediately after a
  board poll. Exhausted allowance/backoff MUST show cancellable progress and
  continue automatically; warm-cache selection consumes no new allowance.
- **FR-005**: Downloaded data, including pending candidates, MUST remain bounded,
  memory-only and expire within 29 minutes of acquisition on either clock.
  Replay/reconnect MUST NOT renew source age. Only explicitly selected stable
  favourite configuration may persist.
- **FR-006**: Explicit advanced manual entry, honest error/retry paths and
  existing options/duplicate behavior MUST remain available.
- **FR-007**: Supported timing-point selection MUST reuse acquired board data
  instead of requiring a third validation request.
- **FR-008**: Existing favourites, entity IDs, configuration schema, release
  identity and card contract MUST remain compatible; NS rail stays out of scope.
- **FR-009**: Source data MUST NOT leak through logs, diagnostics, restored state
  or Recorder. Source-provided labels MUST NOT be presented as guaranteed coverage.
- **FR-010**: Delivery MUST include real rendered native forms, HTTP serialization,
  public-flow tests on minimum/locked runtimes, per-module coverage above 95% and
  full configuration-flow coverage, plus maintained setup/quality evidence.

### Key Entities

- **Stop area**: Temporary town/name grouping of nearby timing points.
- **Timing-point choice**: Temporary supported stop sign/direction, identified by
  its leading-zero-preserving source code and supplied descriptive information.
- **Favourite**: Existing stable user-selected code, name and local filter/options.
- **Lookup lifetime**: Original acquisition and expiry shared across concurrent
  users; not extended by reading or presenting a result.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: Both adding and reconfiguring a favourite can finish without external
  code research in the synthetic English and Dutch acceptance journeys.
- **SC-002**: A cold directory plus selected-area journey uses two source requests,
  not three; a concurrent identical journey adds no duplicate source requests.
- **SC-003**: Both cold requests complete in tests without advancing minutes,
  including after a recent poll. A third distinct lookup waits for shared capacity;
  server backoff still blocks setup. Background requests stay at least 120 seconds
  apart, and setup defers the next poll to avoid an immediate redundant third call.
  Cached searches finish within one second.
- **SC-004**: No downloaded directory/candidate/board remains after its original
  1740-second expiry in cache, abandoned backend flow state or replay.
- **SC-005**: All existing favourite/option/card contract regressions pass unchanged,
  with rendered phone/desktop evidence and exact supported-runtime checks.

## Assumptions

- This enhances existing native Home Assistant forms, not a custom frontend.
- Coverage depends on source metadata and current supported departures; missing
  information is not proof that a stop has no service.
- The background floor and bounded interactive allowance are project engineering
  choices, not upstream quotas or a guaranteed network-latency SLA.
- Unresolved source-license applicability requires the same strict retention for
  directory metadata as departures; no persistent catalogue is introduced.
- Release automation, publishing, merging and live-user installation are excluded.
