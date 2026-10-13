# OVAPI for Home Assistant

Public-transport departure boards with one shared, conservative request budget.
Find favourite stops by town/name, select bus/tram/metro, optionally filter
line/destination and set walking duration,
then use the [companion Lovelace cards](https://github.com/DevSecNinja/lovelace-ovapi)
for upcoming departures and local "leave in" countdowns.

**Custom integration, not an officially rated Gold/Platinum integration.**
Home Assistant 2026.10 or newer is required. This repository is HACS-ready; the
integration has no release publication automation yet.
[Nederlands](docs/README.nl.md).

## Important boundaries

- Bus, tram and metro records are shown **only when OVAPI supplies them**. Coverage
  varies by operator and timing point; an empty board is not proof of no service.
- NS and other trains are excluded. Use Home Assistant's native
  [Nederlandse Spoorwegen integration](https://www.home-assistant.io/integrations/nederlandse_spoorwegen/)
  alongside this one; it is not a dependency.
- OVAPI's documented endpoint is **unencrypted HTTP**. Its HTTPS certificate failed
  hostname validation during verification on 2026-10-12. We neither disable TLS
  checks nor silently downgrade a request. No credentials are sent upstream.
- The wiki discourages small-interval scraping but publishes no numeric allowance.
  Background batches stay at least **120 seconds apart**; interactive discovery
  has a shared allowance of **two requests per rolling 120 seconds**. These are
  engineering choices, not official quotas. See [policy and retention](docs/policy.md).
- Departure data is ephemeral: **not a normal departure sensor attribute** and not
  available for historical automations, Recorder, statistics or restored state.
  Sensors expose operational board status and local configuration/source health.
  This is an intentional retention
  boundary, not equivalent to full native departure-sensor support.

## Installation

### HACS

[![Open OVAPI in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=DevSecNinja&repository=home-assistant-ovapi&category=integration)

With HACS already installed, use the button to open this repository in your Home
Assistant instance, confirm adding it if prompted, and download OVAPI. Restart
Home Assistant afterwards. If the link does not open your instance, use these
manual steps:

1. In HACS, open **Custom repositories**.
2. Add `https://github.com/DevSecNinja/home-assistant-ovapi`, category **Integration**.
3. Download OVAPI and restart Home Assistant.
4. Open **Settings > Devices & services > Add integration > OVAPI**.
5. Add a favourite as described below. Install the companion cards separately.

No package or release publication is performed by the repository's CI.
Original light/dark icons and logos are bundled with the integration and served
locally by Home Assistant. No separate brands submission or UI asset download is
needed on supported HA versions.

### Manual / review branch

Download the desired branch archive from GitHub. Copy **only**
`custom_components/ovapi` into your Home Assistant configuration's
`custom_components/ovapi` directory, restart, and add OVAPI in Devices & services.
Do not copy the development virtual environment, tests or Spec Kit assets.
`mise run package` also creates a locally validated `dist/ovapi.zip`; extract it
into a configuration directory only when intentionally installing.

## Favourite configuration

Each favourite creates a service device, one status sensor and read-only local
diagnostics.

Choose **Find a stop by name**, enter a town and part of the stop name, and select
the matching **town - stop name**. Then choose your stop sign/direction from the
source-provided names, lines and destination examples. Codes distinguish otherwise
identical choices; you do not need to find them externally. Search ignores case
and accents; narrow searches with more than 50 matches.

**Normal cold setup has no deliberate two-minute wait.** Its directory and
selected-area request can run immediately, even after a board refresh. Completion
depends on network latency and your selection, not a guaranteed wall-time SLA.
All flows share two discovery requests per rolling 120 seconds; a third uncached
lookup must wait. Closing/reopening setup or reloading the integration does not
reset that allowance. Cached searches are local and consume no requests.

Progress continues automatically; close the dialog to cancel. Server failures and
`Retry-After` pauses apply to setup too and can require longer waits. Each lookup
defers the next ordinary poll, avoiding a redundant immediate request. Only extra
lookups after a pair can wait for an eligible board refresh to keep polling fair.

| Setting              | Description                                                                                                                       |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------- |
| Favourite name       | Your label, 1-80 characters; for example Amsterdam Amstel.                                                                        |
| Timing-point code    | 1-10 digits, retaining leading zeros. A timing point is generally one stop sign/platform/direction, not a whole station.          |
| Transport to include | Bus, tram and metro are selected initially. Keep at least one selected. A metro-only board follows new metro lines automatically. |
| Line numbers         | Blank = all. Optional comma-separated actual public numbers, matched exactly and case-insensitively; do not invent an `M` prefix. |
| Destination contains | Blank = all. One case-insensitive text fragment, not a comma-separated list.                                                      |
| Walking time         | 0-120 whole minutes; used by the cards, not sent to OVAPI.                                                                        |

**Enter a timing-point code (advanced)** remains available for known codes.
Do not assume a national stop identifier is interchangeable with an OVAPI code.
The on-demand directory contains metadata only; departure details are requested
only for the selected area, never expanded across the whole network.
Line/destination examples are not complete coverage or a permanent direction.
Valid empty timing points remain selectable, but without current information the
transport mode or direction may be unknown. Known unsupported-only points are
omitted. Empty results do not prove that there are no services.
Up to ten **distinct timing points** are supported per HA instance. Add multiple
favourites for one timing point if their filters differ; identical stop/filter
combinations are rejected even when the display names differ.

Selecting a timing point reuses its acquired board and original expiry, without a
third validation request. Advanced manual checks wait automatically through the
interactive allowance. Reload/startup retries and manual entity updates keep
the ordinary background floor.
Polling is always on while an enabled single-stop board entity or its card subscription is active;
there are no travel windows, interval fields, or timing settings to configure.

Use **Configure** to change walking time/filters locally, with no network request
or interruption. Use **Reconfigure** to change the timing point or configured name.
Reconfiguration offers the same name picker and interactive allowance, preserving favourite/entity IDs
and existing options. Lookup choices expire within 29 minutes; an expired dialog
asks you to load fresh choices. Only your selected name/code and preferences are
stored, not the directory, candidates or downloaded departures.
Removing/renaming the entity in HA's registry is supported; update card YAML if you
change its entity ID.

Transport choices describe what you want to include, not a guarantee that every
mode serves a stop. Setup/preferences show current source observations separately.
No current observations means unknown, not no service. Older favourites without a
transport setting continue to include all supported modes.

### Manual codes wait automatically too

Manual add/reconfigure shares the same two-request rolling allowance as name
discovery. Cached stops complete immediately. Uncached checks preserve your
entered settings and continue through native progress at the eligible deadline;
closing the dialog cancels unneeded work. There is no two-favourite limit.

The progress text distinguishes a local allowance from a server pause and uses
the actual deadline, including longer `Retry-After` pauses. If a request itself
fails, the preserved form shows the error: submit again to wait automatically
before another attempt. Failures are not retried in an automatic request loop.
Background startup/reload retries retain their ordinary polling floor.

### Combine existing favourites into one board

Add your individual stop/direction favourites first. Then choose **Add integration >
OVAPI > Combine existing favourites**, select **2-12 source favourites**, give the
combination a name (for example **Diemen Zuid**) and set its own walking time
(default **0**). Select **only the combined entity** in the companion card to get
one board, rather than selecting the source entities as separate boards.

The combination reuses each favourite's filtered feed: it makes **no extra OVAPI
requests**, reserves no timing points and adds no departure cache. The ten distinct
timing-point limit is unchanged. Sources must be single-stop favourites, not other
combinations. Departures are sorted by expected time, or scheduled time if unknown,
with only fully identical records deduplicated and the existing thirty-row limit.
Opposite directions and different vehicles remain distinct.

Combined sensors and subscriptions are passive: they do not keep polling alive
if all source viewers are disabled or unloaded, and manually updating a combined
entity only rereads cached data.

Source line, destination and transport filters still apply. Leave source line and
destination filters blank, with the desired transport types selected, to include
new services automatically. Combining cannot recover departures a source filters
out. A valid empty source is still ready. If any source is stale, the whole board
is stale; if any source is missing, disabled, unloaded or expired, the whole board
is **unavailable**, not a silently incomplete subset. The combined sensor's
`unavailable_sources` attribute identifies affected favourites (removed entries
appear by their saved ID). The card keeps the original sources' **oldest** fetch
and expiry times; reconnecting, editing or reloading never extends them.

Use **Configure** to replace sources or change walking time. **Reconfigure** also
changes the group name. Saved missing references remain listed by ID so you can
deselect them and choose replacements. Source references follow entity renames,
source reconfiguration and restarts; recreating a deleted favourite is a new
reference and must be selected explicitly. Only names, stable source references,
walking time and safe source-health attributes persist, never departure payloads.

### Whole-station discovery is not included yet

Each source favourite still represents one timing point. Manual combinations do
not discover or certify every platform in a station. OVAPI stop areas can omit
working metro platforms: Diemen Zuid's area currently exposes buses while its
known metro timing points exist separately. This update does **not** label that
bus-only group a complete station or freeze today's lines as station membership.
Automatic station grouping is tracked in
[#5](https://github.com/DevSecNinja/home-assistant-ovapi/issues/5), pending a verified
current station-to-timing-point metadata source. No guessed codes or supplementary
metadata provider is used.

## Status and data

The device shows the configured timing-point identity (or manual combination) and **Departure feed
status**. **Feed ready** means the source check succeeded; it is not a departure
time. Existing entity IDs and their `departure_board` suffix remain unchanged.

The native device page also shows these default-enabled **Diagnostic** sensors:

| Insight                           | Meaning                                                                                     |
| --------------------------------- | ------------------------------------------------------------------------------------------- |
| Configured walking time           | This favourite's configured duration in minutes, including zero.                            |
| Configured source favourites      | For combinations: all selected source references, including missing/disabled ones.          |
| Source favourites with ready feed | For combinations: sources with a ready, non-stale feed. A valid empty feed counts as ready. |

For example, one disabled source in a three-source combination leaves **3
configured** and **2 ready** visible while the departure board is **unavailable**.
The existing feed status and `unavailable_sources` explain source loss.
These values remain useful during outages and update locally from existing
configuration and runtime health. They add **no OVAPI requests**, do not keep
polling alive when all ordinary leaf boards/viewers are disabled, and manual
updates only reread local values.

Walking time is display-only here; change it through existing **Configure**
preferences. A combination uses its **own** configured walking duration, never
the sum of or an inherited duration from its sources. A card's optional override
takes precedence on that card only; clearing it returns to the selected
favourite's duration, and an explicit zero means no walking time. Per-card
overrides do not change this diagnostic.

[Open the companion cards in HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=DevSecNinja&repository=lovelace-ovapi&category=plugin),
install them, then add an OVAPI card to your dashboard and select this favourite's
**Departure feed status** entity. Diagnostics are not departure boards and do not
appear in the card's board picker. The setup-success screen includes this handoff.
Ordinary entity cards show only status/configuration/source health; departures
remain on the transient card feed.

| Status      | Meaning                                                                     |
| ----------- | --------------------------------------------------------------------------- |
| Feed ready  | Latest refresh succeeded, including a valid empty board.                    |
| Feed stale  | Refresh failed; last successful data is retained until its original expiry. |
| Unavailable | No usable source data, entry unloaded, or cached data expired.              |

Cards use expected departure time when available, otherwise the scheduled time,
and subtract walking duration for leave time. Missing prediction/cancellation
information stays unknown; we do not manufacture an on-time result. Cancelled
departures do not produce actionable leave countdowns.

At most 30 upcoming departures are delivered per favourite. Rail, terminal stops,
passed services and records without usable scheduled time/line/destination are
omitted. Ambiguous/nonexistent Dutch local times or malformed responses fail
visibly rather than guessing a daylight-saving-time offset.
The API does not guarantee platform, accessibility or cancellation information;
v1 does not advertise those absent capabilities.

The authenticated [card contract](docs/card-contract-v1.md) is a transient WebSocket
feed, not state attributes. Cards never fetch upstream and advance countdowns locally.

## Examples

Two narrow timing-point examples were verified on **2026-10-12**:

| Favourite label    | Timing-point code | Bounded live check                                                     |
| ------------------ | ----------------- | ---------------------------------------------------------------------- |
| Amsterdam Centraal | `30009501`        | API location matched Centraal Station; supported-mode records present. |
| Amsterdam Amstel   | `30009514`        | API location matched Amstelstation; supported-mode records present.    |

These are individual timing points, **not every platform/direction or all bus,
tram and metro services at either station**. Codes came from a
[public historical reference](https://github.com/Geonovum/sospilot/blob/86fc0737585f053abee2f87f035113874027f4d5/src/fiware/openov/GVB_51_1.json)
and were checked using one small comma-separated request. No real departure
payloads were saved. Availability can change; check your intended direction.
Committed fixtures still use fictional X1/X2 services, not captured journeys.

After adding a favourite and installing the companion card, select the resulting
board entity in that card's editor. See the card repository for its current YAML
and layout examples.

A status-only automation can notify you of prolonged loss of source data:

```yaml
alias: OVAPI board unavailable
triggers:
  - trigger: state
    entity_id: sensor.amsterdam_amstel_departure_board
    to: unavailable
    for: "00:10:00"
actions:
  - action: persistent_notification.create
    data:
      title: OVAPI unavailable
      message: Check OVAPI connectivity or the configured timing-point code.
```

Replace the example entity ID with your own. There are no custom actions,
triggers or conditions; only standard HA state automations are supported.
Do not try to persist the transient WebSocket departures via custom automation.

## Troubleshooting and removal

**Cannot connect / stale:** check outbound access to the documented HTTP endpoint.
Do not repeatedly reload or add cards to force refreshes; retries share the budget.
Failures back off from four minutes up to one hour; longer server `Retry-After`
values are respected. A successful refresh recovers automatically.

**Unknown stop:** check the timing-point code, direction and leading zeros.
OVAPI can omit stops; a historic code may no longer be served.

**No departures:** remove filters temporarily and check operator coverage; empty
or incomplete source data is not necessarily a transport disruption.

**No card data:** use the companion cards, select the OVAPI feed-status sensor and check the HA
user's entity read permission. Ordinary entity-only cards cannot read the board.

Download integration diagnostics for request count and safe operational limits.
Diagnostics exclude configured locations, filters and source payloads. Logs report
network failures/recovery without source details. A narrowly scoped guard also
redacts our departure frames from HA's WebSocket debug/slow-client logs.
Do not capture network traces or browser payload dumps containing real departures.

To remove, delete the favourite in **Settings > Devices & services**. Remove
associated dashboard cards, then remove the integration in HACS (or delete only
the installed `custom_components/ovapi` directory) and restart HA if uninstalling
the code. Unloading/removing the last favourite for a stop clears its live cache.
There is no departure-history database, directory cache file or restore file to clean up.

## Development and quality

See [development](docs/development.md), [quality evidence](docs/quality.md), and
[Spec Kit artifacts](specs/001-ovapi-integration/). Tooling is repository-local mise,
locked Python dependencies, real HA fixtures, offline synthetic tests, strict typing
and coverage gates for **every module**, with 100% config-flow coverage.
CI exercises both the declared `hacs.json` minimum and the locked development HA
runtime using matching fixture dependencies. Release-version checks keep the
integration manifest, Python metadata and outgoing user-agent identity aligned.

Code is MIT licensed. This license does **not** cover upstream transport data or
override OVAPI/GOVI terms. The wiki's linked GOVI license was unavailable during
verification; [policy.md](docs/policy.md) records the unresolved limitation.
