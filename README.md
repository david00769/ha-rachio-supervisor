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
- the site-level sensor surface now also carries legacy-parity aliases for
  `last run event` and `last skip decision` so a shadow dashboard can compare
  the new integration against an existing operator surface without forcing an
  immediate semantic rename
- multi-controller accounts now use site-name-aware controller selection instead
  of zone-count-only matching
- site-level sensors now expose webhook registration health using the linked HA
  Rachio webhook id/url plus the Home Assistant-managed
  `homeassistant.rachio:` webhook prefix
- config flow and options now include a schedule-policy step so individual
  discovered Rachio schedules can be opted into automatic catch-up while the
  default posture stays observe-only
- setup/options now also accept candidate moisture sensors, and schedule-level
  sensors now expose moisture mapping plus a simple `dry` / `target` / `wet`
  band derived from the mapped sensor value
- the integration now exposes a manual `write_moisture_now` service that writes
  the currently mapped moisture value into one resolved Rachio zone, but only
  when moisture write-back mode is enabled for that entry
- moisture support now uses an explicit per-schedule mapping step in config and
  options instead of guessing by name overlap at runtime
- the write path now prefers a stable `schedule_entity_id` target and records
  the last manual moisture-write result as supervisor state
- the site-level entity model now exposes which schedules are ready for manual
  moisture write-back through `Ready moisture writes` and `Moisture write queue`
- the site-level entity model now also exposes which schedules are actually
  recommended for manual moisture write-back through `Recommended moisture
  writes` and `Recommended moisture queue`
- the operator surface now also exposes which recommendations are still pending
  review versus already acknowledged in the current runtime session through
  `Active recommendations`, `Active recommendation queue`, `Acknowledged
  recommendations`, and `Acknowledged recommendation queue`
- the integration now also exposes parity-oriented supervisor surfaces for
  `last event`, `last reconciliation`, `observed rain 24h`, `catch-up
  evidence`, `last catch-up decision`, and `supervisor mode`
- site-level supervisor sensors now set explicit names in the entity model so
  a fresh shadow install gets stable, readable entity ids instead of generic
  registry fallbacks
- `Health` now reflects runtime integrity only; optional rain/moisture gaps are
  exposed as data-completeness warnings instead of top-level degradation
- `Webhook health` remains a narrower signal than `Health`; it only reports
  whether the Home Assistant-managed Rachio webhook registration still looks
  valid
- site-level moisture review now stays visible even when recommended writes are
  `0`, so mapped schedules still expose `dry` / `target` / `wet` posture in
  the dashboard during wet conditions
- the supervisor now inspects recent Rachio event history for low-flow and
  high-flow alerts, compares later native calibration events against the prior
  baseline when both are present, and clears the Supervisor-side review queue
  when the post-alert baseline remains stable
- schedule policy now distinguishes between:
  - automatic catch-up after weather skip
  - automatic missed-run recovery
- schedule-level sensors now expose:
  - status
  - reason
  - policy
  - moisture
  - write-back
  - recommendation
  - review
  - catch-up candidate
- site-level diagnostics now also expose:
  - last moisture write
  - ready moisture writes
  - moisture write queue
  - recommended moisture writes
  - recommended moisture queue
  - active recommendations
  - active recommendation queue
  - acknowledged recommendations
  - acknowledged recommendation queue
  - active flow alerts
  - flow alert queue
  - last flow alert decision

The deeper irrigation logic is still pending:

- richer missed-run recurrence handling beyond the current conservative model
- deeper webhook-quality reasoning beyond registration health
- more polished dashboard/action workflow for operator execution
- native flow calibration execution through Rachio is not implemented because
  Rachio's public API does not currently expose the native calibration command
  or calibrated-flow fields; the Supervisor can verify and clear its own review
  state after a calibration event appears in Rachio history

## Local verification bar

The current local verification work now includes deterministic coverage for:

- config flow with optional rain inputs and no moisture sensors
- options flow moisture-mapping behavior
- site-level entity naming and state exposure
- runtime-only health evaluation and cached-evidence freshness handling
- site-level moisture review payload exposure even when recommendation counts
  are zero
- diagnostics payload shape
- observed-rain `unknown / not_reported` semantics
- degraded/healthy cadence transitions
- flow-alert lifecycle and clear-review restrictions

The current deterministic suite lives in:

- [`tests/test_supervisor_logic.py`](./tests/test_supervisor_logic.py)

This is still not the full cutover gate. The real release gate remains a
7-day live shadow comparison against the old Codex-published Sugarloaf
supervisor.

## Flow alert review contract

Flow alert handling is intentionally conservative.

The Supervisor treats low-flow and high-flow alerts as a review workflow with a
specific gate:

1. alert observed in Rachio history
2. later native Rachio calibration observed for the same zone
3. post-alert baseline compared to the most recent pre-alert baseline
4. Supervisor review may only be cleared when the new baseline remains within
   the configured stable-baseline tolerance

That means:

- `calibration_required` stays active until a later calibration appears
- `calibrated_needs_review` stays active when there is no earlier comparable
  baseline
- `problem_suspected` stays active when the new baseline moved materially
- only `normal_after_calibration` is eligible for `clear_flow_alert_review`

The current product only clears the Supervisor-side review item. It does not
claim to dismiss or repair the native Rachio alert itself.

Zone and baseline matching are still inferred from Rachio event text. The
runtime should therefore stay conservative: if the evidence chain is ambiguous,
keep the review item active instead of pretending the alert is safely cleared.

## Setup compatibility notes

The current runtime is now shaped to support a practical shadow install in a
real Home Assistant instance without forcing optional inputs too early.

- the config flow links to an existing Home Assistant `rachio` entry using the
  entity registry, and it now works against registry rows that expose either
  `config_entry_ids` or the older single `config_entry_id`
- `rain_actuals_entity` is optional during initial setup and options edits
- candidate moisture sensors are optional during initial setup and options edits
- if no moisture sensors are selected, the flow skips the schedule moisture
  mapping step entirely and stores an empty explicit mapping instead of showing
  an empty form
- when moisture mapping is required, the form uses one stable
  `moisture_sensor_entity` field and shows the live schedule name in the step
  description; this avoids Home Assistant options-flow handoff failures caused
  by dynamic human schedule names as field keys
- the optional rain selector no longer injects an invalid blank entity id as a
  default

That setup posture is deliberate. It keeps the integration installable in
observe-first shadow mode before a property has finalized rain-source or
moisture-sensor choices.

## Product stance

- `Rachio` remains the actuator and schedule authority.
- `Rachio Supervisor` becomes the policy, verification, and audit layer.
- v1 defaults to `observe-first`.
- automatic behavior is `per-zone opt-in`.
- moisture support is `generic Home Assistant sensor input`.
- actual rainfall comes from `user-selected Home Assistant rainfall entities`.
- Rachio-observed rain from skip events is also surfaced separately because it
  is often the most useful parity signal for irrigation review.

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
- [docs/assets/screenshots/shadow-dashboard-desktop.png](./docs/assets/screenshots/shadow-dashboard-desktop.png) - current live shadow dashboard capture used for frontend critique
- [`custom_components/rachio_supervisor/`](./custom_components/rachio_supervisor) - custom integration scaffold

## Planned v1 capabilities

- native Home Assistant config flow
- Rachio-specific status and audit entities
- webhook/API freshness visibility
- actual-rain aware catch-up reasoning
- Rachio-observed rain review
- optional moisture write-back to Rachio
- recommended irrigation workspace dashboard

## Current runtime milestone

Today the custom integration provides a narrow but real runtime:

- config flow selects an existing Home Assistant `rachio` entry
- actual rainfall can be mapped from a selected sensor entity, but that input is
  optional at setup time
- the coordinator inspects the linked Rachio entry and Rachio public API and publishes:
  - health
  - supervisor mode
  - webhook health
  - linked Rachio entry
  - operating mode
  - action posture
  - actual rain, 24h
  - observed rain, 24h
  - last event
  - last run
  - last run event
  - last skip
  - last skip decision
  - last reconciliation
  - catch-up evidence
  - last catch-up decision
  - active-zone count
  - configured-zone count
  - last refresh
  - recommended moisture writes
  - recommended moisture queue
  - ready moisture writes
  - moisture write queue
  - last moisture write
  - active recommendations
  - active recommendation queue
  - acknowledged recommendations
  - acknowledged recommendation queue
- schedule-level sensors for each active Rachio schedule:
  - status
  - reason
  - policy
  - moisture
  - write-back
  - recommendation
  - review
  - catch-up candidate

This milestone is still intentionally narrow. It does not yet execute automatic
moisture-assisted watering. Moisture support currently means candidate sensor
selection, explicit per-schedule mapping, coarse moisture-band state, a runtime
review queue, plus manual write-back and review acknowledgement services.
Review acknowledgements are not persisted yet; they reset when the integration
reloads. Automatic watering remains opt-in and narrow: weather-skip catch-up
can only execute for explicitly selected schedules, and missed-run recovery is
still conservative.

## HACS status

The repository is structured as a single custom integration repo for HACS.
Initial HACS packaging is in place via:

- `hacs.json`
- `custom_components/rachio_supervisor/manifest.json`

No release has been cut yet. The first release should happen only after the
runtime behavior matches the documented public surface.
