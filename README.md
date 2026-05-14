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

The integration now includes the first cron-replacement runtime path while
still keeping the default install observe-first:

- config flow links to an existing Home Assistant `rachio` entry
- the integration discovers the linked Rachio entity surface from the entity
  registry
- site-level supervisor sensors expose health, linked controller posture,
  actual-rain input status, and discovered zone counts
- the site-level `Zone overview` sensor exposes a visual dashboard payload for
  each discovered zone: resolved image path/source, optional Rachio-import
  status, zone/schedule ids, quick-run minutes, next run if HA exposes one, day
  chips, water/skip badge, rain-skip state, Supervisor badge, moisture band,
  flow-alert state, and plant/detail notes
- the integration serves a lightweight Lovelace custom card at
  `/rachio_supervisor/rachio-supervisor-zone-grid-card.js`; this is the
  recommended zone-first dashboard surface and renders zone photos, compact
  badges, editable Quick Run minutes, and confirmation-gated Quick Run actions
- actual-rain diagnostics now include source status, reporting window,
  confidence, likely Home Assistant rain-source candidates, and a Rachio
  weather-source probe that is diagnostic-only
- the coordinator now reads real Rachio public API event history using the
  linked HA `rachio` API key
- site-level sensors now expose `last run` and `last skip`
- the site-level sensor surface now also carries legacy-parity aliases for
  `last run event` and `last skip decision` so migrations can compare the new
  integration against an existing operator surface without forcing an immediate
  semantic rename
- multi-controller accounts now use site-name-aware controller selection instead
  of zone-count-only matching
- site-level sensors now expose webhook registration health using the linked HA
  Rachio webhook id/url plus the Home Assistant-managed
  `homeassistant.rachio:` webhook prefix
- config flow and options now include a schedule-policy step so individual
  discovered Rachio schedules can be opted into automatic catch-up while the
  default posture stays observe-only
- the coordinator can execute opt-in weather-skip catch-up through Home
  Assistant's built-in `rachio.start_watering` service when observe-first mode
  is disabled; the same safety checks and duplicate lockout back the manual
  `run_catch_up_now` service
- setup/options now also accept candidate moisture sensors, and schedule-level
  sensors now expose moisture mapping, a dated last-valid observation,
  freshness, confidence, quality notes, and the compatible `dry` / `target` /
  `wet` band
- the integration exposes a manual `write_moisture_now` service that writes
  the currently mapped moisture value into one resolved Rachio zone, but only
  when moisture write-back mode is enabled for that entry; this updates
  Rachio's moisture estimate and does not start watering
- the integration exposes a `quick_run_zone` service for confirmation-gated,
  operator-initiated zone runs; this is deliberately separate from Supervisor
  automation and is meant for Rachio-app-style zone cards
- the integration also exposes `write_recommended_moisture_now` and
  `acknowledge_all_recommendations` so the packaged dashboard can use real
  generic actions instead of placeholder per-schedule service data
- the integration also supports opt-in moisture auto-write per schedule; it is
  off by default, requires global moisture write-back mode, writes only the
  fresh non-boundary mapped HA moisture value into the resolved Rachio zone,
  and uses a 24-hour same-value cooldown
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
  `last event`, `last reconciliation`, `observed rain 24h`, read-only `heat
  assist` weather outlook, `catch-up evidence`, `last catch-up decision`, and
  `supervisor mode`
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
  the dashboard during wet conditions; review items now show the proposed write
  contract as `HA sensor -> Rachio zone moisture`, with Rachio's current value
  marked `not_reported` when the public API does not expose it; mapped moisture
  review items also expose last check-in age, last valid observation age,
  freshness, confidence, source state, and quality notes so sleeping MQTT/
  Zigbee probes do not erase useful evidence
- the supervisor now inspects recent Rachio event history for low-flow and
  high-flow alerts across the 7-day inspection window, compares later native calibration events against the prior
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
- optional zone photos can be imported from Rachio or provided as local Home
  Assistant overrides, but the packaged placeholder is always available
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

For production cutover from an old cron-based supervisor, the integration must
be installed/reloaded in Home Assistant, its health/webhook/reconciliation and
catch-up sensors must be fresh, selected schedules must be explicitly opted into
automatic catch-up, and `observe_first` must be disabled only after that review.
The old cron runner can then be paused; deleting old scripts or state files is a
separate cleanup step.

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
- `Observed rain source` can be left unconfigured, mapped to a Home Assistant
  observed-rain entity, or set to a Weather Underground PWS station override
- `rain_actuals_entity` may be a numeric observed-rain sensor/helper, or a
  weather entity only when that weather entity exposes a numeric observed
  precipitation total; forecast-only weather entities are reported as data
  warnings instead of being treated as valid actual rain
- local gauge entities are preferred when present, including gauges delivered
  through Ecowitt, WeatherFlow/Tempest, Netatmo, Ambient Weather, MQTT,
  ESPHome, or similar Home Assistant integrations
- international or regional integrations can be used when they expose a numeric
  observed total; the resolver understands common attribute names such as
  `rain_today`, `rain_since_9am`, `precipTotal`,
  `precipitation_today`, and `observed_precipitation`
- Australian users without a local gauge can use a BOM/WillyWeather-derived
  custom integration if it exposes a numeric observed rainfall sensor; the
  dashboard labels the source window honestly, such as `since_9am` or `today`,
  instead of pretending every source is rolling 24h
- Weather Underground / The Weather Company PWS stations can be used when Home
  Assistant exposes the station's observed total through a REST or custom
  sensor. A station `precipTotal` value is treated as a daily observed total
  unless the HA entity or attribute clearly says it is rolling 24h. If Home
  Assistant owns the REST/custom sensor, keep API keys in Home Assistant
  secrets and select the resulting sensor as
  `rain_actuals_entity`; do not map a forecast-only WU/weather entity as
  observed rain.
- Alternatively, choose the Weather Underground PWS source mode in the
  integration options, enter the station ID and API key, and the supervisor will
  poll the station's current `precipTotal` directly. Diagnostics redact the
  saved key. This is a station-specific observed-rain override and is not
  discovered from the Rachio controller.
- Rachio's public forecast endpoint is used for source/provider hints and the
  read-only `Heat assist` outlook. Forecast precipitation is not treated as
  observed rainfall unless a future API payload exposes a clearly observed
  historical total
- rain-source discovery filters out Supervisor bookkeeping entities and old
  helper/automation state so the candidate list stays focused on actual
  sensor or weather entities
- candidate moisture sensors are optional during initial setup and options edits
- if no moisture sensors are selected, the flow skips the schedule moisture
  mapping step entirely and stores an empty explicit mapping instead of showing
  an empty form
- when moisture mapping is required, the form uses one stable
  `moisture_sensor_entity` field and a separate ignored `schedule_name` display
  field; this keeps the current schedule visible without using dynamic human
  schedule names as submitted field keys
- saving options reloads the integration entry so the dashboard immediately
  rebuilds coordinator state from the new schedule-to-moisture mapping
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
- [docs/assets/screenshots/production-dashboard-desktop.png](./docs/assets/screenshots/production-dashboard-desktop.png) - sanitized product screenshot used for public docs
- [`custom_components/rachio_supervisor/`](./custom_components/rachio_supervisor) - custom integration scaffold

## Dashboard resource

The recommended dashboard uses the packaged zone grid custom card. Add this
Lovelace resource after installing the integration:

- URL: `/rachio_supervisor/rachio-supervisor-zone-grid-card.js`
- type: `JavaScript module`

The example dashboard then uses:

```yaml
type: custom:rachio-supervisor-zone-grid-card
entity: sensor.rachio_site_zone_overview
title: Zones
auto_detect_calibration_entities: true
```

The card includes a thin Supervisor overlay above the zone grid. It stays quiet
when the runtime is healthy and only adds weight for degraded health, webhook
issues, catch-up review, recommended moisture writes, flow alerts, or data
warnings.

Zone photos are optional. The card always has a packaged placeholder. If
`import_rachio_zone_photos` is enabled, the integration caches available Rachio
zone photos under:

`/local/rachio-supervisor/imported-zones/<zone-id>.jpg`

Manual local overrides win over imported photos. Upload overrides to:

`/local/rachio-supervisor/zones/<zone-slug>.jpg`

The zone overview sensor also publishes `photo_import_counts` and
`photo_import_summary` so users can see how many zones are cached, imported,
missing, rejected, failed, or disabled without opening Developer Tools for each
zone row.
Rejected or failed Rachio photo imports are not shown as status pills on the
zone image. The card hides the unusable image and shows an in-place error such
as `image too large`.

Quick Run from the card is manual, editable, and confirmation-gated. It starts
the selected Rachio zone only for the chosen duration and does not enable
Supervisor catch-up or moisture automation.

The packaged card also includes a narrow moisture calibration assistant in each
zone detail drawer when a mapped soil-calibration `number` entity is available.
It compares the current mapped moisture reading with an operator-entered target,
calculates the next offset, and applies that offset through Home Assistant's
`number.set_value` service after confirmation. Apply stays disabled until both
the moisture sensor and the calibration number have numeric states. It does not
run watering, write to Rachio, update firmware, or model soil science.

By default the card tries to auto-detect common Zigbee2MQTT-style calibration
entities from the mapped moisture sensor name. Prefer configuring moisture
sensors through the integration options so the zone overview payload carries
the mapped `moisture_entity_id`. The `calibration_entities` card option is an
override for unusual entity names or temporary migration work, not the primary
source of operational truth:

```yaml
type: custom:rachio-supervisor-zone-grid-card
entity: sensor.rachio_site_zone_overview
title: Zones
calibration_entities:
  sensor.example_moisture:
    moisture: sensor.example_moisture
    soil: number.example_soil_calibration
```

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
  - heat assist weather outlook
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

This milestone is still intentionally narrow. It does not execute automatic
moisture-assisted watering. Moisture support currently means candidate sensor
selection, explicit per-schedule mapping, dated moisture evidence with
freshness and confidence guards, coarse moisture-band state, a runtime review
queue, manual write-back, opt-in moisture estimate auto-write, and review
acknowledgement services. CS-201Z-style probes can sleep or report
intermittently; repeated `0%` or `100%` readings should be calibrated or
manually accepted rather than treated as proof of extreme soil condition.
Review acknowledgements are not persisted yet; they reset when the integration
reloads. Automatic watering remains opt-in and narrow: weather-skip catch-up
can only execute for explicitly selected schedules, and missed-run recovery is
still conservative.

## Cron cutover checklist

Use this sequence when replacing a local cron supervisor:

1. Install or reload the custom integration in Home Assistant.
2. Verify fresh core sensors: `Health`, `Webhook health`, `Last reconciliation`,
   `Catch-up evidence`, and `Last catch-up decision`.
3. Configure only the schedules allowed to run automatic catch-up.
4. Set `observe_first` to `false` only after the selected schedules and zone
   entities are correct.
5. Call `rachio_supervisor.evaluate_now` once. This forces fresh Rachio
   evidence, including webhook and optional photo-import evidence, then confirm
   the dashboard card still loads from
   `/rachio_supervisor/rachio-supervisor-zone-grid-card.js`.
6. Pause the old cron automation after the integration is healthy and publishing
   catch-up decision state.

## HACS status

The repository is structured as a single custom integration repo for HACS.
Initial HACS packaging is in place via:

- `hacs.json`
- `custom_components/rachio_supervisor/manifest.json`

Use `v0.2.5` or newer for HACS installs. That build includes the production
dashboard cutover fixes, heat-assist outlook, stricter actual-rain source
handling, schedule-rule zone matching, forced fresh evidence on
`evaluate_now`, options-flow hardening,
packaged placeholder fallback, and photo import diagnostics.
It also includes the explicit Weather Underground PWS station override for
observed-rain sourcing.

## Known limitations

- Rachio `imageUrl` may be absent for some zones or accounts.
- Very large Rachio original images are rejected instead of hotlinked.
- The card hides rejected images and shows the operator-facing reason in the
  image area, such as `image too large`.
- Photo import is opt-in and read-only.
- Manual local photo overrides always win over imported Rachio photos.
- Unresolved Rachio zones fall back to the packaged placeholder.
