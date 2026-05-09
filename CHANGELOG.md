# Changelog

## 0.1.0 - 2026-05-09

- Seeded the public repo.
- Added the formal PRD, public docs site, recommended dashboard package, and HACS custom integration scaffold.
- Documented the product boundary: Rachio-first, supervisor-first, observe-first, with opt-in catch-up and optional moisture write-back.
- Added the first runtime milestone: config flow now links to an existing HA `rachio` entry, the coordinator discovers the linked entity surface, and site-level evidence sensors now reflect real HA state instead of placeholder scaffold values.
- Added the second runtime milestone: the coordinator now reuses the linked HA `rachio` API key to read real Rachio event history, expose `last run` / `last skip`, and publish schedule-level status, reason, and catch-up-candidate sensors for active schedules.
