# Changelog

## 0.2.8 - 2026-05-14

- Changed moisture badge and review copy from definitive `offline` language to
  `no sample` / `not reporting` language when Home Assistant has no usable
  numeric moisture sample.
- Documented the dashboard contract for a lower-priority 14-day moisture
  history graph below the moisture review surface.

## 0.2.7 - 2026-05-14

- Changed Rachio zone-photo import so large source images can be downloaded up
  to a larger safety cap, resized/compressed into dashboard JPEGs, and cached
  instead of being rejected only because the original file is over 8 MB.
- Kept a hard source cap and explicit rejection states for unsupported,
  undecodable, or still-too-large images.

## 0.2.6 - 2026-05-14

- Clarified the app docs and PRD around HACS update behavior for the packaged
  Lovelace card: use the Home Assistant-served module URL with a version query,
  replace stale inline `data:text/javascript` resources, restart Home Assistant
  after custom-component updates, and refresh open dashboard tabs.
- Reworked the zone-grid Supervisor overlay so first-viewport data warnings use
  operator-readable copy instead of raw internal tokens, and widened status
  badges so icon/text labels do not collide on narrow cards.

## 0.2.5 - 2026-05-14

- Added a first-class observed-rain source mode for Weather Underground / The
  Weather Company PWS stations. Operators can enter a station ID and API key in
  setup/options, and the coordinator resolves the station's current
  `precipTotal` as a daily observed rain total.
- Kept Rachio weather-source/forecast hints diagnostic-only; the station
  override is explicit user configuration, not inferred from Rachio.
- Redacted the Weather Underground API key from diagnostics exports.
- Reworked moisture review payloads and dashboard copy around last check-in,
  last valid moisture, sensor freshness, quality, and write status instead of
  raw implementation tokens.
- Updated the packaged zone grid card so rejected or failed Rachio photo
  imports render as an in-place image error such as `image too large`, not as a
  raw `rejected` pill.

## 0.2.4 - 2026-05-11

- Replaced live Home Assistant dashboard captures with sanitized public product
  screenshots that avoid private hostnames, account UI, property names, and raw
  house data.
- Expanded CI validation to run the deterministic logic suite, YAML sanity
  checks, and Lovelace card syntax checks in addition to Python and JSON
  validation.
- Updated the local test notes and pull request checklist to match the current
  release-readiness bar.
- Added dated moisture evidence handling with freshness, confidence, quality
  notes, runtime caching through temporary sensor dropouts, stricter auto-write
  guards, and compact zone-card moisture observations.
- Added a simple moisture calibration assistant to the packaged zone grid card.
  It can auto-detect or accept explicitly mapped soil-calibration number
  entities, optionally read from an explicitly mapped moisture sensor, calculate
  the next offset from a target reading, and apply it through Home Assistant's
  `number.set_value` service after confirmation when both current values are
  numeric.
- Added a read-only `Heat assist` weather outlook from Rachio forecast data,
  kept forecast precipitation out of actual-rain decisions, made catch-up
  evidence and last catch-up decision states dashboard-readable, and filtered
  Supervisor/helper noise out of observed-rain source candidates.
- Changed zone overview construction to use Rachio schedule rule metadata for
  zone matching, next-run timestamps, and watering-day chips instead of
  schedule-name overlap, and stopped publishing invented plant-note copy when
  no HA/Rachio source reports it.
- Config flow now preselects likely soil-moisture sensor candidates discovered
  from Home Assistant state names and attributes while keeping the final
  per-schedule moisture mapping explicit.
- Controller selection and setup defaults now prefer the discovered linked
  Rachio zone count before falling back to the generic seven-zone default.
- Promoted the live plugin-backed irrigation surface to a single production
  dashboard at `/irrigation-dashboard`, removed the stale Home-dashboard
  irrigation view, and retired the temporary `Irrigation Shadow` dashboard.

## 0.2.3 - 2026-05-11

- Treats `v0.2.3` as the release-candidate cutover build for the cron
  replacement path.
- Added zone-overview photo import diagnostics through `photo_import_counts`
  and `photo_import_summary`.
- Added quiet photo-state badges to the packaged zone grid card: missing
  photos show a muted `No photo` badge, rejected or failed imports show a small
  warning badge, and normal local/imported photos stay quiet.
- Hardened oversized photo handling when Rachio omits or sends an unusable
  `Content-Length`: the importer now reads only up to the hard byte cap and
  rejects only when the cap is exceeded.
- Fixed photo metadata being dropped when schedule snapshots were hydrated with
  moisture context, which caused live zone overview rows to fall back to stale
  `disabled` photo status after successful evidence reconciliation.

## 0.2.2 - 2026-05-11

- Made `evaluate_now` clear cached Rachio evidence before requesting refresh so
  operator-triggered reconciliation always rebuilds the live evidence path.
- Added a runtime note when Rachio zone-photo import is enabled, making live
  cutover diagnostics easier to confirm.

## 0.2.1 - 2026-05-11

- Hardened live photo-import status reporting so enabled imports publish a
  concrete non-fatal state instead of stale `disabled` metadata.
- Added regression coverage for enabled evidence imports with missing Rachio
  images and unavailable HA config paths.

## 0.2.0 - 2026-05-11

- Added optional Rachio-derived zone photo import. Public installs keep the
  feature off by default; when enabled, the integration caches Rachio zone
  photos locally under `/local/rachio-supervisor/imported-zones/<zone-id>.jpg`.
- Preserved safe image resolution order: manual local override first, cached
  Rachio import second, packaged placeholder last.
- Added zone overview photo metadata, including `image_source`,
  `rachio_image_available`, and `photo_import_status`, so dashboards can render
  clean fallbacks without browser 404s.
- Changed `rachio_supervisor.evaluate_now` to force a fresh Rachio evidence
  reconciliation instead of only refreshing cached coordinator data. This keeps
  photo import, webhook cutover checks, and operator debugging tied to live
  evidence.
- Hardened options-flow defaults so stale saved schedule or moisture selector
  values are ignored in forms instead of producing a generic Home Assistant
  options error.

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
- Added the seventh runtime milestone: setup/options now use an explicit per-schedule moisture-mapping step, and runtime moisture context now resolves only from that stored mapping instead of fuzzy name matching.
- Added the eighth runtime milestone: the manual moisture-write path now prefers stable `schedule_entity_id` targeting, records rejected/successful write outcomes in coordinator state, and exposes a site-level `last moisture write` diagnostic sensor.
- Added the ninth runtime milestone: the site-level entity model now exposes `ready moisture writes` and `moisture write queue`, and schedule-level sensors now include explicit `write-back` readiness so the operator can see which schedules are actionable before calling the manual write service.
- Added the tenth runtime milestone: the entity model now exposes `recommended moisture writes` and `recommended moisture queue`, and schedule-level sensors now include explicit `recommendation` state so the operator can distinguish merely ready schedules from schedules that are currently recommended for manual write-back.
- Added the eleventh runtime milestone: the operator surface now exposes active versus acknowledged recommendation queues, schedule-level sensors now include explicit `review` state, and manual services can acknowledge or clear one recommendation for the current runtime session without enabling autonomous action.
- Added the twelfth runtime milestone: the supervisor now exposes generic parity surfaces for `last event`, `last reconciliation`, `observed rain 24h`, `catch-up evidence`, `last catch-up decision`, and `supervisor mode`; policy configuration now distinguishes automatic weather-skip catch-up from missed-run recovery; and the coordinator now keeps a narrow supervision loop with health transitions, notification support, and opt-in catch-up execution.
- Added the thirteenth runtime milestone: the setup/options flow now supports a cleaner shadow-install path by treating rain actuals and moisture candidates as optional inputs, skipping the moisture-mapping step when no candidates were selected, avoiding invalid empty rain defaults, and linking the built-in `rachio` entry through either entity-registry `config_entry_ids` or legacy `config_entry_id` rows.
- Added the fourteenth runtime milestone: the supervisor now detects recent low-flow/high-flow alert events, compares later native calibration baselines against the prior baseline when available, exposes flow-alert review sensors, and adds a `clear_flow_alert_review` service for Supervisor-side review cleanup. Native Rachio calibration execution remains outside the public API boundary.
- Tightened the flow-alert review gate: `normal_after_calibration` no longer auto-clears. The Supervisor now requires an explicit clear step, and that clear step is only allowed after a stable post-alert calibration comparison.
- Fixed a shadow-install naming bug where site-level diagnostic sensors could be registered without names and end up with generic entity ids such as `sensor.sugarloaf_8`.
- Expanded the deterministic test harness so local coverage now includes config-flow optional-input behavior, options-flow moisture mapping, site-level entity naming/state exposure, and diagnostics payload shape.
- Replaced the stale dashboard example with the accepted live irrigation layout using stable `sensor.rachio_site_*` entities.
- Added screenshot assets for the current live shadow dashboard and documented a frontend-skill critique of the current operator surface, including the remaining `Recent decisions` density issue on narrow widths.
- Tightened shadow-runtime health semantics so `Health` now reflects runtime integrity only, while optional rain/moisture gaps surface through data-completeness warnings and explicit `missing_inputs` attributes.
- Added site-level compact moisture review payloads so mapped schedules remain visible in the dashboard even when recommended moisture writes are `0`.
- Added compact decision attributes (`subject`, `brief`, `at_local`) for recent-decision dashboard rendering and updated the recommended Lovelace example to use built-in markdown cards instead of raw long-string entities in the first viewport.
- Fixed the per-schedule moisture-mapping step so the active schedule name is visible directly in the mapping field label instead of relying on hidden description copy.
- Added the fifteenth runtime milestone: moisture review items now show the proposed write contract (`HA sensor -> Rachio zone moisture`), rain actuals reject forecast-only weather entities with plain-English data warnings, flow review uses a 7-day inspection window, and schedule-level opt-in moisture auto-write can update Rachio moisture estimates without starting watering.
- Redesigned the recommended irrigation dashboard around the new 4+1 card model: Rachio Supervisor, Catch-up / top-up, Moisture drift, Flow review, and Audit.
- Added observed-rain source discovery and richer rain-source metadata: configured actual-rain sources now expose status, reason, reporting window, confidence, likely HA rain-source candidates, and diagnostic-only Rachio weather/forecast hints.
- Added generic dashboard-safe services for `write_recommended_moisture_now` and `acknowledge_all_recommendations`, and removed fake schedule-name placeholders from the packaged Lovelace example.
- Reworked the recommended dashboard toward a Rachio-app-style zone-first UI: zone photos, compact icon badges, and visual weather/moisture/flow sections instead of text-heavy Supervisor cards.
- Added a `Zone overview` sensor payload plus a confirmation-gated `quick_run_zone` service so the dashboard can attach real per-zone Quick Run buttons from stable entity ids.
- Added the packaged `rachio-supervisor-zone-grid-card` Lovelace module, served by the integration, for photo-first zone cards with day chips, compact rain/moisture/flow/Supervisor badges, editable Quick Run minutes, and a low-noise detail drawer.
- Added the cron-cutover runtime path: automatic weather-skip catch-up now uses
  Home Assistant's `rachio.start_watering` service with an integer minute
  duration, and `rachio_supervisor.run_catch_up_now` can execute the current
  confirmed catch-up candidate as an explicit operator action using the same
  safety checks and duplicate lockout.
