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

The full irrigation runtime is not complete in this initial seed. The current
goal of the repo is to lock product scope, public interfaces, UX direction, and
the integration structure before the full supervisor logic is implemented.

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

## HACS status

The repository is structured as a single custom integration repo for HACS.
Initial HACS packaging is in place via:

- `hacs.json`
- `custom_components/rachio_supervisor/manifest.json`

No release has been cut yet. The first release should happen only after the
runtime behavior matches the documented public surface.

