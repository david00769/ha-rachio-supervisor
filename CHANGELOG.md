# Changelog

## 0.1.0 - 2026-05-09

- Seeded the public repo.
- Added the formal PRD, public docs site, recommended dashboard package, and HACS custom integration scaffold.
- Documented the product boundary: Rachio-first, supervisor-first, observe-first, with opt-in catch-up and optional moisture write-back.
- Added the first runtime milestone: config flow now links to an existing HA `rachio` entry, the coordinator discovers the linked entity surface, and site-level evidence sensors now reflect real HA state instead of placeholder scaffold values.
- Added the second runtime milestone: the coordinator now reuses the linked HA `rachio` API key to read real Rachio event history, expose `last run` / `last skip`, and publish schedule-level status, reason, and catch-up-candidate sensors for active schedules.
- Added the third runtime milestone: the coordinator now exposes webhook registration health, uses site-name-aware controller selection for multi-controller Rachio accounts, and publishes webhook match context through the site-level diagnostic surface.
- Added the fourth runtime milestone: setup/options now include schedule-level catch-up policy selection, schedule snapshots now expose explicit `policy` state, and catch-up candidacy now distinguishes default review-only schedules from auto-eligible opt-in schedules.
- Added the fifth runtime milestone: setup/options now accept candidate moisture sensors, schedule snapshots expose mapped moisture context and coarse `dry` / `target` / `wet` banding, and diagnostics now flag when configured moisture sensors do not match any discovered schedules.
- Added the sixth runtime milestone: manual `write_moisture_now` service support now resolves one schedule to a controller zone, reuses the linked HA `rachio` API key, and writes the mapped moisture value into Rachio only when moisture write-back mode is enabled.
