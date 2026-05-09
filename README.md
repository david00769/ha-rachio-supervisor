# Rachio Supervisor for Home Assistant

Rachio Supervisor is a Rachio-first irrigation supervision layer for Home Assistant.

It is designed for operators who want better answers to the questions Rachio
does not answer well on its own:

- Why did a zone water, skip, or get delayed?
- Did enough rain actually fall to justify the skip?
- Which zones are dry, stable, or trending wet?
- Which zones are catch-up candidates, and why?
- Is the Rachio + Home Assistant evidence chain healthy?

This repository is the initial public seed:

- formal product requirements document
- public docs / landing page
- HACS custom integration scaffold
- recommended Lovelace dashboard package

The full irrigation runtime is not complete yet. The repo now includes the
first real runtime milestones:

- config flow links to an existing Home Assistant `rachio` entry
- the integration discovers the linked Rachio entity surface from the entity
  registry
- site-level supervisor sensors expose health, linked controller posture,
  actual-rain input status, and discovered zone counts
- the coordinator now reads real Rachio public API event history using the
  linked HA `rachio` API key
- site-level sensors now expose `last run` and `last skip`
- multi-controller accounts now use site-name-aware controller selection instead
  of zone-count-only matching
- site-level sensors now expose webhook registration health using the linked HA
  Rachio webhook id/url plus the Home Assistant-managed
  `homeassistant.rachio:` webhook prefix
- schedule-level sensors now expose:
  - status
  - reason
  - catch-up candidate

The deeper irrigation logic is still pending:

- richer catch-up decision engine
- moisture write-back flows
- deeper webhook-quality reasoning beyond registration health

## Product stance

- `Rachio` remains the actuator and schedule authority.
- `Rachio Supervisor` becomes the policy, verification, and audit layer.
- v1 defaults to `observe-first`.
- automatic behavior is `per-zone opt-in`.
- moisture support is `generic Home Assistant sensor input`.
- actual rainfall comes from `user-selected Home Assistant rainfall entities`.

## Why this exists

This project is intentionally not a generic ET engine.

It is aimed at the operational gap between:

- the stock Home Assistant `rachio` integration
- Smart Irrigation-style calculation helpers
- real-world operator needs around skip visibility, actual rain, catch-up
  reasoning, webhook health, and per-zone trust

## Repository map

- [PRD.md](./PRD.md) - decision-complete product requirements
- [docs/index.html](./docs/index.html) - polished public landing page
- [docs/architecture.md](./docs/architecture.md) - integration and runtime shape
- [docs/dashboard-package.md](./docs/dashboard-package.md) - recommended Lovelace surface
- [examples/lovelace-irrigation-dashboard.yaml](./examples/lovelace-irrigation-dashboard.yaml) - operator dashboard example
- [`custom_components/rachio_supervisor/`](./custom_components/rachio_supervisor) - custom integration scaffold

## Planned v1 capabilities

- native Home Assistant config flow
- Rachio-specific status and audit entities
- webhook/API freshness visibility
- actual-rain aware catch-up reasoning
- optional moisture write-back to Rachio
- recommended irrigation workspace dashboard

## Current runtime milestone

Today the custom integration provides a narrow but real runtime:

- config flow selects an existing Home Assistant `rachio` entry
- actual rainfall is mapped from a selected sensor entity
- the coordinator inspects the linked Rachio entry and Rachio public API and publishes:
  - health
  - webhook health
  - linked Rachio entry
  - operating mode
  - action posture
  - actual rain, 24h
  - last run
  - last skip
  - active-zone count
  - configured-zone count
  - last refresh
- schedule-level sensors for each active Rachio schedule:
  - status
  - reason
  - catch-up candidate

This milestone is still intentionally narrow. It does not yet execute catch-up
actions or moisture write-back, and its webhook reasoning currently stops at
registration/match health rather than full event-freshness enforcement.

## HACS status

The repository is structured as a single custom integration repo for HACS.
Initial HACS packaging is in place via:

- `hacs.json`
- `custom_components/rachio_supervisor/manifest.json`

No release has been cut yet. The first release should happen only after the
runtime behavior matches the documented public surface.
