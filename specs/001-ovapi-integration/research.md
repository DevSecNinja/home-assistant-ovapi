# Research and decisions

Verified 2026-10-12 with bounded documentation and HEAD requests, no full dataset
downloads, source fixture capture, or email outreach.

## Actual Spec Kit

Official [README](https://github.com/github/spec-kit) and release `v1.1.3` use
`specify init --integration copilot` and hyphenated `speckit-*` agent skills.
Executed `mise exec uv@0.11.25 -- uvx --from specify-cli==1.1.3 specify init
--here --integration copilot --script sh --force --non-interactive
--ignore-agent-tools`. The bootstrap uv was subsequently aligned to the shared
organization pin in `.mise.toml`. Templates/skills/workflow were installed by the
CLI, not imitated. Resolved constitution/spec templates and ran `setup-plan.sh`.
The installed skills are read and executed directly by this agent; they are not
shell commands. No git extension or branch-creation hook was enabled.

## Upstream policy and transport

- [Wiki home](https://github.com/koch-t/KV78Turbo-OVAPI/wiki): batch comma-separated
  objects, gzip, identifying user-agent, avoid large amounts/small intervals.
- [Timing points](https://github.com/koch-t/KV78Turbo-OVAPI/wiki/TimingPointCode):
  `/tpc/{ids}/departures`, optional timetable metadata, 404 for unknown stops.
  Codes are strings preserving leading zeros; the prose says ten characters but
  its examples have variable lengths. Accept one to ten numeric digits.
- Source `kv78turbo-api.py` confirms `Passes`, `TripStopStatus: CANCEL`,
  `LINESTOPCANCEL` normalization, optional `Stop`, and naive local time serialization.
  Terminal (`JourneyStopType: LAST`) records are not departures.
- HTTPS HEAD `https://v0.ovapi.nl/tpc/30000001` failed certificate hostname validation.
  Documented HTTP HEAD `/tpc/57330620` returned 200 JSON. Use explicit fixed HTTP;
  never disable TLS, silently downgrade, follow redirects or transmit credentials.
- Original and HTTPS GOVI license URLs return 404:
  `http://openov.nl/license/GOVI-1.0-TravelInfo`. The wiki says no storage >30 minutes
  and names historic operator exceptions. We cannot independently verify current
  full license terms/applicability. Apply the stricter 29-minute ceiling uniformly
  and disclose the unresolved source, rather than claiming legal clearance.
- No numerical published request allowance was found. Fixed 120-second global
  minimum is a conservative engineering choice, not upstream permission.

## Home Assistant

Sources: [quality scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/),
[checklist](https://developers.home-assistant.io/docs/core/integration-quality-scale/checklist/),
[testing](https://developers.home-assistant.io/docs/development_testing/).
Use public-interface tests, explicit exemptions, per-module >95% coverage and full
config flow coverage. No custom integration can self-award an official tier.

Decision: transient WebSocket departure feed plus status-only sensor.
Alternative: normal timestamp/departure entities. Rejected because Recorder/state
history cannot reliably enforce source retention without installation-wide changes.
Tradeoff: ordinary departure automations/cards are not supported and Core submission
will require architectural discussion and an independently maintained async library.

## Organization conventions

Coordinator inspected DevSecNinja/.github at
`9170d8c24e95a27dca91e1b7904f1f70a94dd1b0` and repo-starter at
`970ad82787165d0f8673815c08614a13a498a74a`. Use repo-local mise, canonical shared
configs, SHA-pinned reusable lint v3.2.0, PR-only CI, no draft/path exclusions,
least privilege and Conventional Commits. Repo-specific HA checks stay local.
Avoid unrelated Go/container/release scaffolding and global tool changes.

## Bounded Amsterdam verification

Historical public reference:
`Geonovum/sospilot` commit `86fc0737585f053abee2f87f035113874027f4d5`,
`src/fiware/openov/GVB_51_1.json` lists Centraal Station timing point `30009501`
and Amstelstation `30009514`. On 2026-10-12 a single identified gzip-enabled GET
to `/tpc/30009501,30009514/departures` returned HTTP 200, both named locations
matched and both contained supported-mode records. Data was processed only in
memory, discarded immediately, and no departures were logged or persisted.
These examples are narrow points, not all platforms or a blanket operator claim.
The exact no-trailing-slash production path worked, contradicting an unverified
third-party claim that a trailing slash is mandatory.
