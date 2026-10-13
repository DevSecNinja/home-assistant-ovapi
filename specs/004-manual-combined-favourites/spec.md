# Feature Specification: Manual combined favourites

**Feature Branch**: `devsecninja-manual-combined-favourites`

**Created**: 2026-10-12

**Status**: Accepted

**Input**: "As an intermediate solution, what if we make it such that the user can just select multiple entities to combine into one sensor? Would it be possible for me to just combine the Diemen Zuid data manually?"

## User Scenarios & Testing _(mandatory)_

### User Story 1 - One board from existing favourites (Priority: P1)

A traveller selects two or more existing favourites, gives the combination a name
and walking duration, and selects the resulting entity in one companion card.

**Why this priority**: Allows manually combining Diemen Zuid directions now,
without waiting for automatic station membership.

**Independent Test**: Combine two synthetic favourites in native setup and verify
one chronological board without any additional upstream requests.

**Acceptance Scenarios**:

1. **Given** two ready favourites, **When** combined, **Then** one board contains
   their departures in time order, removing only fully identical events.
2. **Given** source filters, **When** combined, **Then** those filters still apply;
   unrestricted sources include new lines and destinations automatically.
3. **Given** empty, cancelled or unknown source facts, **When** combined, **Then**
   those facts retain their meaning.

### User Story 2 - Honest source availability (Priority: P1)

A traveller sees when a source needs attention instead of trusting a partial board.

**Why this priority**: Missing a direction must not look like complete live data.

**Independent Test**: Disable, unload, remove, stale and expire a source while
watching the combined board and its status entity.

**Acceptance Scenarios**:

1. **Given** any missing or unusable source, **When** the combination is displayed,
   **Then** it is unavailable with no departures or live dates, and Home Assistant
   identifies the affected source.
2. **Given** all sources usable and one stale, **When** combined, **Then** the board
   is stale, not actionable as a current commute.
3. **Given** source expiry, **When** the combination is replayed, edited or reloaded,
   **Then** the oldest source deadline is never extended.

### User Story 3 - Maintain the manual group (Priority: P2)

A traveller changes selected favourites or walking time without recreating the board.

**Why this priority**: Direction choices and personal travel preferences change.

**Independent Test**: Edit a group in native preferences and reconfigure, rename a
source entity, then reload and restart using the saved configuration.

**Acceptance Scenarios**:

1. **Given** renamed or reconfigured sources, **When** updated, **Then** the group
   follows the same logical favourites.
2. **Given** a removed source, **When** editing, **Then** its saved reference is
   visible and removable, and another existing favourite can replace it.
3. **Given** a combined favourite, **When** selecting sources, **Then** self and
   other combined favourites are rejected.

### Edge Cases

- Two to twelve distinct source favourites; physical-stop capacity is unchanged.
- Same trip identifier with different directions, times or cancellation facts is
  not sufficient evidence for deduplication.
- A ready source with no matching future departures remains usable.
- Disabled and unloaded existing sources remain selectable, but not live.
- Oldest source timestamps govern the whole group; no derived persistent cache.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Users MUST be able to create a named combination of 2-12 existing
  non-combined OVAPI favourites with its own walking duration, default zero.
- **FR-002**: Setup, editing, viewing and reloading a combination MUST add zero
  upstream requests and consume no additional physical-stop capacity.
- **FR-003**: The board MUST respect source filters, sort by expected time or
  scheduled time when unknown, preserve distinct events, and retain the existing
  thirty-departure output limit.
- **FR-004**: Any unusable source MUST make the whole combination unavailable;
  affected sources MUST be identifiable in Home Assistant. Otherwise any stale
  source MUST make the combination stale.
- **FR-005**: Source age MUST never be renewed by combining data. Departure data
  MUST remain transient and absent from entity history and diagnostics.
- **FR-006**: Source references and board identity MUST survive entity renames,
  source reconfiguration, reloads and restarts.
- **FR-007**: Setup, preferences and reconfiguration MUST support native English
  and Dutch forms, including removal/replacement of missing source references.
- **FR-008**: The combination MUST be selectable as one entity in existing cards,
  including while unavailable, without changing their feed contract.
- **FR-009**: Existing single-favourite configuration, identity and request-budget
  behavior MUST remain unchanged.

### Key Entities

- **Source favourite**: Existing single-stop favourite with its own filters and
  independently managed availability.
- **Combined favourite**: User-named selection of stable source references and a
  walking duration; one status entity and one transient departure board.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: Two selected directions appear on one board with zero extra source
  requests during creation, viewing, editing and reload.
- **SC-002**: Every tested source loss clears the combination; every tested source
  recovery restores it without recreating the group.
- **SC-003**: No copied departure survives the oldest selected source's deadline.
- **SC-004**: Users can add and change the group through actual English and Dutch
  native screens; the existing card displays both directions as one board.

## Assumptions

- This is an interim manual group, not automatic station coverage or membership.
- Source favourites must already exist; filters cannot be expanded by the group.
- Two to twelve leaf favourites bounds the manual selection. Multiple filtered
  favourites may share a physical stop; the ten-stop instance limit stays intact.
- NS trains, provider metadata downloads, releases and live user installations
  are outside scope.
