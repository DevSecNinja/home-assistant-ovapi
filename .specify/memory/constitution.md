# Home Assistant OVAPI Constitution

## Core Principles

### I. Respect the upstream service and its data

All entry points MUST share one per-HA-instance request budget and deduplicated
batched cache. Cards MUST never contact upstream. Polling MUST be conservative,
bounded, compressed, identifiable and backed off on failures. No numerical limit
may be described as officially permitted without a published source.
Source data MUST remain transient and be erased before 30 minutes, including
outages, unload, diagnostics, Recorder and browser storage.

### II. Honest Home Assistant behavior

Use supported asynchronous HA interfaces, managed sessions, UI configuration,
runtime data, entity/device registries, lifecycle cleanup and translations.
Unknown, stale, empty and cancelled MUST remain distinct. NS rail is outside
scope. Gold/Platinum rules guide engineering; this custom integration MUST NOT
claim an official tier. Every exemption or unmet external rule needs evidence.

### III. Deterministic evidence before delivery

Tests MUST be offline and synthetic. HA integration tests MUST exercise public
interfaces. Every integration module MUST exceed 95% measured coverage; config
flow MUST reach 100%. Fake-time tests MUST assert actual network counts, batching,
cache, backoff and retention rather than merely mocking a coordinator result.
Typing, lint, packaging and lifecycle checks are release gates.

### IV. Versioned, minimal interfaces

The card contract MUST be agreed before implementation and versioned on breaking
changes. Timestamps represent instants; unknown predictions MUST NOT be invented.
Departure boards MUST NOT be stored in state attributes. This limitation on
ordinary cards/automations and potential Core submission MUST be explicit.

### V. Reproducible, reviewable delivery

Use actual pinned GitHub Spec Kit artifacts through constitution, specification,
plan, tasks, implementation and convergence. Use repository-local mise and
locked dependencies. Commit/push review branches, but do not merge, publish
packages/releases or modify a live Home Assistant installation.

## Scope and Constraints

HACS-first, multiple favourite stops with line/destination filtering and walking
duration. Always-on polling, no travel windows or user-facing timing settings.
English/Dutch copy and synthetic Amsterdam Centraal/Amstel examples must not
imply unverified operator coverage. No upstream scraping or email outreach.

## Development Workflow

Resolve official Spec Kit templates, preserve implementation decisions and source
evidence, write acceptance tests, implement, then converge against the recorded
intent. Quality exemptions must explain product or upstream constraints, never
hide failing checks. Maintenance changes must update affected tests and docs.

## Governance

This constitution governs all feature artifacts. Amendments require a rationale,
updated version/date and review of affected requirements/tests. Breaking principle
changes increment major, new principles minor, clarifications patch. Reviewers
must examine retention and actual request-budget evidence on every network change.

**Version**: 1.0.0 | **Ratified**: 2026-10-12 | **Last Amended**: 2026-10-12
