# OVAPI for Home Assistant

Public-transport departure boards with one shared, conservative request budget.
Configure favourite timing points, line/destination filters and walking duration,
then use the [companion Lovelace cards](https://github.com/DevSecNinja/lovelace-ovapi)
for upcoming departures and local "leave in" countdowns.

**Custom integration, not an officially rated Gold/Platinum integration.**
Home Assistant 2026.10 or newer is required. This repository is HACS-ready; the
initial implementation is delivered on a review branch, with no release published.
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
  A **120-second global minimum** is our conservative engineering choice, not an
  official permission or guarantee. See [policy and retention](docs/policy.md).
- Departure data is ephemeral: **not a normal departure sensor attribute** and not
  available for historical automations, Recorder, statistics or restored state.
  The only sensor is operational board status. This is an intentional retention
  boundary, not equivalent to full native departure-sensor support.

## Installation

### HACS

Once the implementation is on the repository's default branch:

1. In HACS, open **Custom repositories**.
2. Add `https://github.com/DevSecNinja/home-assistant-ovapi`, category **Integration**.
3. Download OVAPI and restart Home Assistant.
4. Open **Settings > Devices & services > Add integration > OVAPI**.
5. Add a favourite as described below. Install the companion cards separately.

No package or release publication is performed by the repository's CI.
Brand submission to the HA brands repository is still external follow-up; the
HACS branding check alone is explicitly excluded.

### Manual / review branch

Download the desired branch archive from GitHub. Copy **only**
`custom_components/ovapi` into your Home Assistant configuration's
`custom_components/ovapi` directory, restart, and add OVAPI in Devices & services.
Do not copy the development virtual environment, tests or Spec Kit assets.
`mise run package` also creates a locally validated `dist/ovapi.zip`; extract it
into a configuration directory only when intentionally installing.

## Favourite configuration

Each favourite creates a service device and one status sensor.

| Setting              | Description                                                                                                              |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------ |
| Favourite name       | Your label, 1-80 characters; for example Amsterdam Amstel.                                                               |
| Timing-point code    | 1-10 digits, retaining leading zeros. A timing point is generally one stop sign/platform/direction, not a whole station. |
| Lines                | Optional comma-separated public line numbers, matched exactly and case-insensitively.                                    |
| Destination contains | Optional case-insensitive substring filter.                                                                              |
| Walking time         | 0-120 whole minutes; used by the cards, not sent to OVAPI.                                                               |

Obtain the correct timing-point code from the stop/operator's published information.
We do not download/scrape a complete stop directory. Do not assume a station name
or national stop identifier is interchangeable with an OVAPI timing-point code.
Up to ten **distinct timing points** are supported per HA instance. Add multiple
favourites for one timing point if their filters differ; identical stop/filter
combinations are rejected even when the display names differ.

New stops are validated through the same shared budget as polling. Adding a stop
immediately after another request may ask you to retry after at least two minutes.
This deliberate throttle also applies to reload/startup retries and manual updates.
Polling is always on while an enabled board entity or card subscription is active;
there are no travel windows, interval fields, or timing settings to configure.

Use **Configure** to change walking time/filters locally, with no network request
or interruption. Use **Reconfigure** to change the timing point or configured name.
Reconfiguration/reload may briefly wait for the shared request budget.
Removing/renaming the entity in HA's registry is supported; update card YAML if you
change its entity ID.

## Status and data

| Status      | Meaning                                                                     |
| ----------- | --------------------------------------------------------------------------- |
| Ready       | Latest refresh succeeded, including a valid empty board.                    |
| Stale       | Refresh failed; last successful data is retained until its original expiry. |
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

**No card data:** use the companion cards, select an OVAPI sensor and check the HA
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
There is no departure-history database or restore file to clean up.

## Development and quality

See [development](docs/development.md), [quality evidence](docs/quality.md), and
[Spec Kit artifacts](specs/001-ovapi-integration/). Tooling is repository-local mise,
locked Python dependencies, real HA fixtures, offline synthetic tests, strict typing
and coverage gates for **every module**, with 100% config-flow coverage.

Code is MIT licensed. This license does **not** cover upstream transport data or
override OVAPI/GOVI terms. The wiki's linked GOVI license was unavailable during
verification; [policy.md](docs/policy.md) records the unresolved limitation.
