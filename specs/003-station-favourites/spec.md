# Feature Specification: Station-wide favourites

**Feature Branch**: `devsecninja-station-wide-ovapi-favourites`

**Created**: 2026-10-12

**Status**: Independent scope approved; station grouping deferred to
[#5](https://github.com/DevSecNinja/home-assistant-ovapi/issues/5).

**Delivery decision (2026-10-12)**: After bounded source research, the coordinator
directed delivery of manual interactive waiting, transport filters for existing
timing points, bundled branding and card onboarding. Story 1 and the station-only
parts of Story 2/FR-001..004/SC-001 remain unfulfilled in #5, not claimed complete.
The original intent below is retained to prevent losing the station requirement.

**Input**: Add a whole station that follows changing stops, lines and directions;
optionally show only bus, tram or metro; provide recognizable integration branding
and explain how to display departures after setup. Preserve individual favourites.

## User Scenarios & Testing _(mandatory)_

### User Story 1 - Follow a whole station (Priority: P1)

A resident selects their station once, without choosing each platform or line.
Their existing departure card follows current station services, including temporary
weekend lines and changed directions.

**Why this priority**: Selecting today's lines or one platform misses tomorrow's
temporary services, which is the main problem reported by the user.

**Independent Test**: Configure a fictional station with bus platforms and metro
platforms missing from the basic stop-area directory. Change its reported members
and services, then observe the same favourite and board.

**Acceptance Scenarios**:

1. **Given** a station with bus and orphan metro platforms, **When** selected as a
   whole station, **Then** both supported modes are discoverable without guessing
   identifiers, and incomplete coverage is not presented as a complete station.
2. **Given** an existing station favourite, **When** members, lines or destinations
   change, **Then** the same board follows the new data without reconfiguration.
3. **Given** an existing individual-stop favourite and card, **When** this feature
   is installed, **Then** its identity, settings and departure display still work.
4. **Given** overlapping station and individual favourites, **When** refreshed,
   **Then** source work is shared and each board contains no duplicate departures.

---

### User Story 2 - Select transport rather than today's lines (Priority: P1)

A traveller can retain metro and omit buses without enumerating metro lines.
Defaults include all supported transport and do not filter lines or destinations.

**Why this priority**: A metro-only station board must still discover temporary
metro replacements instead of freezing the initial service selection.

**Independent Test**: Filter a mixed station to metro; replace its metro services
and confirm the new services appear and buses remain hidden.

**Acceptance Scenarios**:

1. **Given** current bus and metro observations, **When** editing a favourite,
   **Then** observed modes are distinguished from unknown or absent observations.
2. **Given** a metro-only selection, **When** new metro lines/directions appear,
   **Then** they appear automatically without additional filter-driven requests.
3. **Given** blank line and destination filters, **When** a board is shown,
   **Then** every otherwise eligible service appears. Line filters match exact
   public numbers; the destination filter is one substring, not a comma list.

---

### User Story 3 - Reach the departure display (Priority: P2)

Users recognize OVAPI in integration setup and understand that its status entity
reports feed health, while the companion card displays upcoming departures.
Users entering a known code can wait automatically for a shared request slot.

**Why this priority**: A successful setup that only says "Ready", or a third add
that appears rejected, hides the integration's value.

**Independent Test**: Complete English and Dutch setup with a third uncached
manual code, observe automatic waiting, and follow the card installation guidance.

**Acceptance Scenarios**:

1. **Given** a fresh installation, **When** opening integration setup, **Then**
   recognizable original artwork is available locally in light and dark themes.
2. **Given** a successful favourite setup, **When** viewing its status,
   **Then** users see its station/stop identity and can find instructions and a
   direct companion-card installation link without exposing departure history.
3. **Given** a third uncached lookup, **When** the shared allowance is exhausted,
   **Then** entered settings remain intact and setup continues automatically at
   the eligible deadline rather than requiring resubmission.
4. **Given** a server pause longer than two minutes, **When** setup is waiting,
   **Then** the explanation distinguishes that pause from a local allowance and
   does not promise an incorrect fixed two-minute wait.

### Edge Cases

- Empty overnight platforms remain valid; absent data does not prove no service.
- Malformed, missing, partial and offline responses stay distinct from successful
  empty boards; expired data is not displayed or retained as history.
- Station discovery does not infer metro from a station name, guess nearby codes,
  or repeatedly download the entire departure network.
- Membership replacement removes obsolete members without changing board identity.
- Simultaneous setup, reconfiguration, options edits, cards and background updates
  share one bounded budget; cancellation and unload clean up pending work.
- Cached selections require no redundant validation; local filters never fetch.
- Unsupported rail services are excluded without inventing replacement modes.

## Requirements _(mandatory)_

### Functional Requirements

- **FR-001**: Offer station-wide and individual-stop favourites.
- **FR-002**: Discover orphan station platforms through defensible source metadata;
  explicitly disclose missing or uncertain coverage rather than silently omitting it.
- **FR-003**: Refresh station membership and services dynamically, keeping one
  stable aggregate board per favourite.
- **FR-004**: Preserve existing favourite/entity identifiers and current cards.
- **FR-005**: Offer optional bus/tram/metro selection, with all supported modes
  enabled initially and no default line/destination restriction. Reject an
  explicit empty transport selection with a translated error; missing legacy
  preferences still mean all modes.
- **FR-006**: Distinguish observed modes from no-current-data and unknown modes.
- **FR-007**: Apply filters locally; explain exact public line numbers and the
  single destination substring in English and Dutch.
- **FR-008**: Share deduplicated bounded requests across all consumers; keep
  background requests at least 120 seconds apart and interactive requests within
  two starts per rolling 120 seconds, respecting longer upstream pauses.
- **FR-009**: Disclose any slower per-board cadence required for mixed targets.
- **FR-010**: Erase transient departures within 29 minutes using elapsed-time and
  wall-clock deadlines; exclude them from state history, logs and diagnostics.
- **FR-011**: Bundle original recognizable transit branding; avoid impersonating
  transit operators or Home Assistant and avoid artwork downloads during UI use.
- **FR-012**: Clarify operational status and provide a direct card-installation
  handoff without adding raw-departure sensors or recreating the photographed card.
- **FR-013**: Preserve manual input while waiting automatically, including
  reconfiguration; cached validation is immediate and cancellation stops unneeded work.
- **FR-014**: Distinguish local waiting from an upstream pause using the actual
  remaining deadline; do not add automatic repeat-request loops or raise quotas.

### Key Entities _(include if feature involves data)_

- **Favourite**: Stable user-selected station or individual stop with a name,
  transport/line/destination preferences and walking duration.
- **Station**: Source-defined grouping whose current platform membership can change.
- **Platform**: A source-addressable boarding point, including orphan points
  absent from the basic station directory.
- **Board**: Ephemeral ordered departures plus operational availability and expiry.
- **Lookup**: Shared bounded discovery or validation work that can be cached,
  queued, cancelled or blocked by an upstream pause.

## Success Criteria _(mandatory)_

### Measurable Outcomes

- **SC-001**: Synthetic orphan-metro stations include all verified members and
  follow member addition/removal and weekend service changes without user edits.
- **SC-002**: Metro-only boards show new metro services and zero bus departures.
- **SC-003**: Existing individual favourites retain their identifiers and current
  card functionality with no user migration.
- **SC-004**: Concurrent consumers never exceed the stated shared request limits;
  filter and walking-time edits cause zero upstream requests.
- **SC-005**: Third uncached manual setup resumes automatically at the eligible
  deadline in both supported languages, preserving every entered field.
- **SC-006**: No expired departure survives 29 minutes, including failures and unload.
- **SC-007**: Minimum and current supported installations display packaged branding
  and provide a usable card-installation handoff in English and Dutch.

## Assumptions

- The photographed station board is a future card reference, not a request for a
  frontend replacement or reproduction of the physical housing.
- NS/other rail remains outside scope; source coverage is not a service guarantee.
- Users keep the existing companion cards; any necessary contract change must be
  explicit rather than silently rejected by strict consumers.
- Supplemental static metadata is acceptable only after source, namespace,
  licensing, bounded retrieval and cache policy are established.
- Delivery is an independent reviewed feature branch from merged main, not a
  stacked change. No merge, release or installation on the user's live system.
