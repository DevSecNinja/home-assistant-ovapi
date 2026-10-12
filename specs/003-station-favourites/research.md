# Research and decisions

Research date: 2026-10-12. No live departure payload, coordinates or real journey
fixtures were retained. No full GTFS feed or national departure sweep was downloaded.

## Station discovery: deferred, not partially claimed

**Decision**: Do not ship station-wide grouping until
[#5](https://github.com/DevSecNinja/home-assistant-ovapi/issues/5) is resolved.

**Rationale**: OVAPI area `09542` reports bus points `30000250`/`30000251`;
independently verified metro points `30009542`/`30009543` have no StopAreaCode.
The basic directory alone cannot fulfil the user's Diemen Zuid requirement.

**Alternatives considered**:

- Parent-provided v0 directory/line/TPC research: area directory lacks orphan
  membership, TPC catalogue has counts without names, narrow metro line metadata
  did not expose traversable membership. Do not repeat or expand these probes.
- [Current OVAPI GTFS](https://gtfs.ovapi.nl/README): first-party reuse permission
  exists, with identification/compression and conservative update guidance.
  HTTP 206 ranges retrieved a 64 KiB ZIP directory and only the 1,562,512-byte
  compressed `stops.txt` (5,893,577 decoded bytes). Its 78,537 rows group four
  Diemen platforms under `stoparea:615121`, but contain no TPC mapping and blank
  platform `stop_code` values. Internal IDs are not timing-point IDs.
- The narrower same-provider current GOVI GTFS `stops.txt` was 251,272 compressed
  bytes/1,080,819 decoded bytes with 16,436 rows; it had no matching Diemen Zuid.
- [CHB exports](https://data.ndovloket.nl/haltes/): listing advertises approximately
  13 MB compressed physical-stop data and 1 MB assignments. Assignment HEAD
  reports 1,031,761 bytes. Neither export was downloaded. BISON schema documents
  NL:Q quays, but current first-party reuse terms were not established.
- [Old OpenOV stop metadata](http://data.openov.nl/haltes/) is explicitly linked
  as CC0 by [OpenOV](https://www.openov.nl/), but files date to 2021 and cannot
  serve as current membership authority.
- [OSM licensing](https://www.openstreetmap.org/copyright) permits reuse under ODbL
  with attribution/share-alike obligations. One bounded 10,251-byte selected-area
  relation query found train/subway/bus groups. Bus platforms had explicit
  `NL:Q:30000250`/`30000251`; subway stop positions and platform had no `ref:IFOPT`.
  No spatial or numeric-prefix guesses were made. Additionally,
  [Overpass operator guidance](https://dev.overpass-api.de/overpass-doc/en/preface/commons.html)
  discourages using public instances as a third-party application's backend.

A separately licensed, bounded static cache could be appropriate in a future
design, but public accessibility does not prove licensing. No supplemental
metadata endpoint or persistent static registry is added in this delivery.

## Manual waiting and filters

**Decision**: Manual setup/reconfiguration uses the same interactive allowance as
directory/details. Existing cached boards complete immediately. Preserve entered
fields through native progress and show the actual next eligible local deadline.

**Rationale**: The old manual flow called ordinary `_refresh`, returned
`rate_limited` for local cooldown and made the user resubmit. A third lookup is
not a two-sensor capacity limit.

**Alternatives considered**: Raising quotas, arbitrary two-minute error copy and
automatic repeated retries were rejected. A real failed request returns an
explicit preserved form; user resubmission waits automatically for the shared
backoff. Late callers can join a later eligible batch, not a completed request.

Transport options default to all supported modes when absent for backward
compatibility. Explicit empty selection is rejected, rather than silently
reenabling all modes. Observations describe current normalized source data,
not guaranteed operator coverage. All filtering remains local.

## Branding and onboarding

**Decision**: Bundle eight original PNGs in `brand/`, with 256/512-square icons
and corresponding light/dark wordmarks. Render them reproducibly using the
existing locked Pillow dependency. Include them in the installation archive.

**Evidence**: [HA's February 2026 announcement](https://developers.home-assistant.io/blog/2026/02/24/brands-proxy-api/)
and [brands guidance](https://github.com/home-assistant/brands/blob/master/README.md)
document local branding since HA 2026.3. Both supported runtimes contain the
authenticated `/api/brands/integration/{domain}/{image}` API.
Current HACS validator `adb7d83e33d24325535fb43b8226572405143757` accepts a local
`custom_components/ovapi/brand/icon.png` before consulting the CDN. Its exact
validation method was executed against this tree successfully; remove the
obsolete `ignore: brands` rather than request an external brands PR.

Use incumbent native HA forms and controls. Clarify the status entity's visible
name while preserving the legacy ID suffix, show static timing-point identity on
its service device, and link device help/setup success to card instructions/HACS.
Do not populate Recorder with departures or rebuild the companion frontend.
