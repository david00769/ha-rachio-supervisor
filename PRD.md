# Product Requirements Document

## Project

`Rachio Supervisor for Home Assistant`

Standalone repo target:

`ha-rachio-supervisor`

## Product Summary

Rachio Supervisor is a **Rachio-first Home Assistant custom integration** that
adds policy, verification, and operator trust on top of the existing Rachio
controller and Home Assistant `rachio` integration.

It is built for advanced homeowners and Home Assistant power users who want
better irrigation visibility and control without replacing Rachio as the
controller of record.

The product solves for:

- skip and delay explainability
- actual-rain-aware catch-up reasoning
- webhook/API health visibility
- per-zone moisture-aware policy
- safe, opt-in automatic actions
- a calm operator UI that explains what happened and what should happen next

## Problem Statement

Rachio is good at controller-level scheduling and hardware execution, but it is
weak at operator-grade transparency. In practice:

- Flex behavior can feel opaque and hard to trust
- skip logic is difficult to audit after the fact
- actual local rainfall is not the same thing as forecast intent
- Home Assistant users often build fragile one-off automations around incomplete
  evidence
- moisture sensors are available in HA, but the integration path from moisture
  data to trustworthy zone decisions is weak

Existing adjacent tools, including Smart Irrigation, are useful for calculation
and scheduling support, but they do not solve the Rachio-specific supervision
problem well:

- Rachio supervision and explainability
- catch-up reasoning from actual rain
- zone-level moisture-aware policy
- webhook/API health visibility
- operator trust and auditability

## Primary User

Advanced homeowner / Home Assistant power user.

Traits:

- comfortable with entities, integrations, and dashboards
- willing to map zones, weather inputs, and optional moisture sensors
- wants stronger operator trust than vendor apps usually provide
- prefers calm, information-dense UI over marketing UX

## Goals

1. Keep Rachio as the watering actuator and schedule authority.
2. Make Home Assistant the supervision, evidence, and decision layer.
3. Ship a native Home Assistant setup experience via config flow.
4. Keep the default install safe: observe-first, no surprise watering.
5. Support actual-rain-aware catch-up reasoning.
6. Support generic Home Assistant moisture sensors without vendor lock-in.
7. Support optional moisture write-back into Rachio when explicitly enabled.
8. Ship a recommended operator dashboard package and polished public docs.

## Non-Goals

- replacing Rachio with a full standalone irrigation engine
- generic ET scheduling for arbitrary irrigation platforms
- automatic dashboard generation
- add-on-first architecture
- Home Assistant Core inclusion as the first delivery target
- calibration-heavy soil science and agronomy in v1
- vendor firmware management for moisture sensors

## Product Positioning

### What it is

- a Rachio-specific supervisor
- a Home Assistant custom integration
- a policy and evidence layer
- an operator-facing product with clear reasons and action posture

### What it is not

- a clone of the stock `rachio` integration
- a generic irrigation automation toolkit
- a calculation-only engine
- a custom dashboard framework

## Functional Scope

### Control model

Primary v1 mode:

- **supervisor-first schedules**

This means:

- Rachio schedules remain primary
- Rachio remains the schedule and valve authority
- the supervisor verifies, interprets, and optionally acts around the schedule

Allowed automatic action classes in v1:

- catch-up watering after verified inadequate watering / skip conditions
- optional write-back of moisture state into Rachio

Allowed manual action classes in v1:

- per-zone Quick Run with explicit operator confirmation and bounded duration

Explicitly not in v1:

- broad autonomous watering independent of Rachio schedule posture
- a generalized top-up engine that replaces schedule ownership
- treating forecast-only weather conditions as observed rainfall
- treating Rachio forecast payloads as actual rainfall unless the API returns a
  clearly observed historical rainfall total

### Safety model

Default posture:

- observe-first
- per-zone opt-in
- manual-first defaults

Rules:

- every zone starts in observe mode
- automatic actions must be enabled explicitly per zone
- action posture must be visible in the UI
- no automatic action should happen because a sensor merely exists

### Moisture model

Inputs:

- generic Home Assistant entities chosen by the user
- one optional moisture entity per zone in v1

Interpretation:

- thresholds + trends
- simple sensor-offset calibration before write-back
- not calibration-heavy agronomy, soil science, or vendor firmware management

Per-zone thresholds:

- dry band
- target band
- wet band

Trend context:

- recent direction of change
- last meaningful change window
- stale or noisy sensor warning state

Moisture write-back:

- optional
- manual write service available when write-back mode is enabled
- schedule-level opt-in for automatic write-back
- not the primary control model
- updates Rachio's moisture estimate only; it does not start watering

Dashboard stance:

- moisture is shown as a schedule-linked review signal
- moisture is expressed through bands and recommendations before raw telemetry
- simple calibration is exposed as an operator assistant for mapped sensors; it
  may calculate and apply Home Assistant number-entity offsets, but it must not
  imply universal volumetric soil-moisture accuracy
- manual write-back to Rachio comes before any automatic moisture-assisted
  action
- no automatic top-up watering is implied by the mere existence of a moisture
  sensor
- opt-in auto-write may write the mapped HA moisture percentage into Rachio for
  selected schedules, with audit history and cooldowns

### Rain / evidence model

Authority split:

- Rachio is authoritative for planned intent:
  - schedules
  - skips
  - delays
  - event history
- Home Assistant rain entities are authoritative for observed actuals:
  - actual rainfall totals
  - catch-up reasoning based on what truly fell

Accepted v1 actual-rain source:

- any numeric Home Assistant observed-rain entity chosen by the user
- a Home Assistant weather entity only when it exposes a numeric observed
  rainfall or precipitation total
- a configured Weather Underground / The Weather Company PWS station override
  when the user provides a station ID and API key; this is treated as a
  user-selected observed-rain source, not as data inferred from Rachio

Forecast integrations are not the core story in v1. The important distinction
is:

- Rachio planned intent
- Home Assistant observed actuals

## Public User Interfaces

### Config flow

The integration must support setup through the Home Assistant UI.

Target flow shape:

1. choose an existing Rachio integration / controller context
2. choose or confirm a site label
3. choose actual-rain entity or entities
4. select operating mode
5. optionally map one moisture sensor per zone
6. set per-zone thresholds and action posture

The initial public scaffold may implement a reduced flow first, but the
complete intended flow is the contract.

### Entities

Planned first-class entities:

- supervisor health
- webhook/API freshness
- actual rain window totals
- last run
- last skip
- last reconciliation
- active flow alerts
- flow alert review queue
- last flow alert decision
- per-zone status
- per-zone reason/explanation
- per-zone moisture band
- per-zone catch-up candidate / decision state

### Operator UI thesis

The operator surface should answer a small number of questions quickly instead
of exposing every entity equally.

Primary operator questions:

1. Are we watering, skipping, or waiting right now?
2. Do we owe a catch-up or top-up decision because conditions have diverged
   from schedule intent?
3. Is measured soil moisture drifting enough from Rachio's estimate that we
   should write moisture back into Rachio?
4. Is a flow alert still a real issue, or has calibration shown it was a false
   alarm?

Frontend-skill direction:

- visual thesis: calm yard-control surface with zone photography as the
  dominant UI and Supervisor state layered on as compact badges
- content plan: zones first, then weather/skip, moisture, flow, and audit
- interaction thesis: tap or open zone detail for deeper context, edit Quick
  Run minutes inline, and confirmation-gate watering/write actions

The dashboard should stay simple enough that:

- first viewport = zone photos, next-run/skip/moisture/flow badges, and manual
  Quick Run affordances
- second layer = evidence
- lower layer = full schedule detail

It should not feel like a generic card wall, a zone spreadsheet, or a text
audit surface first.

The current operator model is a zone-first dashboard with four follow-on
sections:

1. `Zones` for photos, zone names, day chips, next run, compact status badges,
   plant notes, detail drawers, confirmation-gated Quick Run, and mapped sensor
   calibration assistance
2. `Weather` for rain skip, actual observed rain, read-only heat/weather
   outlook, and catch-up/top-up posture
3. `Moisture` for mapped sensor state, `HA sensor -> Rachio` write summaries,
   manual write, and auto-write status
4. `Flow` for the 7-day flow alert queue, calibration evidence, baseline delta,
   and clear-review action
5. `Audit` for health, webhook state, raw strings, queues, parity detail, and
   full evidence

For moisture specifically:

- first viewport should only surface moisture when drift has become actionable
- the main moisture section should answer whether measured soil moisture is far
  enough from Rachio's posture to justify a write-back
- zone detail should only show mapped sensor, current band, and a short posture
  note, with calibration controls kept in the detail layer
- conservative watch zones should remain visibly non-autonomous

### Alerting and action posture

The dashboard and notification model should follow the same priority order:

1. flow alert review that still needs a real operator decision
2. catch-up or missed-run decisions that would otherwise be lost
3. moisture-estimate drift when write-back is enabled or explicitly reviewed

Heatwave top-up should be treated as a future extension of the same
`catch-up / top-up outlook` surface, not as a separate always-on automation
concept in the initial public product.

### Services

Planned first-class services:

- evaluate now
- run catch-up now
- write moisture now
- acknowledge recommendation
- dismiss recommendation
- clear flow alert review after a normal post-alert calibration
- pause zone policy

### Diagnostics

Planned diagnostics surface:

- mapped Rachio inputs
- mapped moisture inputs
- mapped rain inputs
- flow alert review queue and post-calibration baseline comparison
- policy mode per zone
- latest supervisor evidence snapshot
- stale webhook/API warnings

### Flow alert supervision

Flow alert handling is a first-class supervision workflow, not a generic note.

The product must treat low-flow and high-flow alerts conservatively because
operators may see vendor alerts that are not actually actionable faults.

Required v1 lifecycle:

1. detect recent low-flow / high-flow alert events from Rachio history
2. require a later native Rachio calibration event for the affected zone before
   any clear is possible
3. compare the post-alert baseline against the most recent pre-alert baseline
   when both are available
4. only mark the alert as eligible to clear when the post-alert baseline is
   within the configured stable-baseline tolerance
5. keep the alert in review when:
   - calibration has not happened yet
   - no earlier comparable baseline exists
   - the new baseline moved materially from the prior baseline

Important boundary:

- the product may clear the **Supervisor review item**
- it does not claim to clear the native vendor alert in Rachio unless the public
  API supports that in the future
- zone association and baseline association may need to be inferred from Rachio
  event text, so the product should prefer false-negative review retention over
  false-positive auto-clear

Required statuses:

- `calibration_required`
- `calibrated_needs_review`
- `normal_after_calibration`
- `problem_suspected`

Required actions:

- `run_native_calibration`
- `review_baseline`
- `clear_review`
- `inspect_zone`

## UX Direction

### Home Assistant operator UX

The in-HA experience should feel quiet, technical, and trustworthy.

Design direction:

- calm surface hierarchy
- dense but readable information
- minimal chrome
- no dashboard-card mosaic
- no decorative gradients or ornamental status blocks

The first irrigation workspace should help an operator answer:

- is the controller healthy?
- what watered?
- what skipped?
- did enough rain actually fall?
- which zones are dry?
- which zones are candidates for catch-up or review?

### Recommended dashboard package

v1 ships with:

- one recommended Lovelace dashboard package
- one lightweight custom Lovelace card, `rachio-supervisor-zone-grid-card`,
  served by the integration for the photo-led zone grid

v1 does not ship:

- a custom dashboard builder
- dashboard generation

The dashboard package should include:

- photo-led zone grid with compact badges
- editable, confirmation-gated per-zone Quick Run
- current site status in Audit and as zone/weather/moisture/flow badges
- moisture + rain context
- simple dashboard-assisted moisture sensor calibration
- review queue / actions

### Public docs site

The repo must include a polished public docs / landing experience.

Use the frontend-skill explicitly:

- visual thesis: quiet, technical, weather-aware, premium utility rather than
  hobbyist gadget UI
- content plan: hero, problem/fit, workflow, operator UI, install/CTA
- interaction thesis:
  - restrained entrance sequence
  - scroll-linked product framing
  - clear screenshot / mock reveal behavior

## Technical Shape

### Architecture choice

v1 architecture:

- **integration-first suite**

Primary delivery mechanism:

- Home Assistant custom integration
- HACS distribution

Optional future runtime:

- add-on or worker process only if needed later for background execution or
  heavy reconciliation

### Repo contents

The upstream repo should include:

- `custom_components/rachio_supervisor/`
- `docs/`
- `examples/`
- `PRD.md`
- `README.md`
- `CHANGELOG.md`
- `.github/`
- screenshots or product visuals

## Success Metrics

Initial success should be judged by:

1. clean HACS-ready repo structure
2. decision-complete PRD
3. polished public docs and clear product positioning
4. native Home Assistant integration scaffold in place
5. recommended dashboard package that matches the documented entity model
6. a public repo strong enough to implement against without reopening product
   scope

## Test Scenarios

### Product behavior

- scheduled zone runs normally and is reflected cleanly in supervisor state
- Rachio skips watering and actual rainfall is sufficient, so no catch-up is
  recommended
- Rachio skips watering and actual rainfall is inadequate, so catch-up is
  recommended
- moisture sensor shows dry band, but no automatic action occurs while the zone
  is still advisory-only
- a zone is promoted from observe-only to auto mode and only that zone may act
  automatically
- webhook/API data goes stale and degraded health is visible immediately
- moisture write-back is enabled and writes to Rachio without broader autonomous
  control
- moisture auto-write is off by default, runs only for explicitly enabled
  schedules, and records written/skipped/rejected results
- forecast-only weather entities are rejected as observed-rain sources with a
  data warning
- observed-rain diagnostics expose reporting window and confidence, so sources
  such as local 24h gauges, daily totals, `rain_since_9am`, and Weather
  Underground-style `precipTotal` are not misrepresented as the same kind of
  measurement
- Weather Underground station overrides expose the configured station ID and
  observed timestamp in diagnostics; the station-specific `precipTotal` is a
  daily observed total unless the provider/source explicitly says otherwise
- Rachio weather-source/forecast hints are collected for diagnostics only and
  do not drive actual-rain decisions
- heat assist is a read-only weather outlook in v1; it must not show
  unevaluated placeholder text and must not imply autonomous heat top-up
  watering before that policy exists
- dashboard package actions call real generic services for writing current
  recommendations and acknowledging current recommendations; packaged examples
  do not ship fake schedule-name placeholders
- zone overview payload exposes image paths, zone ids, compact badges, quick-run
  defaults, and next-run hints so dashboards can be visual and zone-first
- per-zone Quick Run calls the existing Home Assistant Rachio watering service
  only after an explicit operator action
- missing or noisy moisture entities degrade gracefully
- the dashboard package renders cleanly on phone and tablet

### Distribution and docs

- clean HACS install
- successful config-flow setup from an existing Rachio integration context
- public docs explain setup without forum archaeology
- dashboard example matches the shipped public entity contract

## Launch Deliverables

The first public implementation milestone should include:

- this PRD
- public repo
- HACS integration scaffold
- issue templates and CI
- docs landing page
- architecture notes
- dashboard package example

The first real functional milestone should add:

- live data coordinator
- entity model
- diagnostic payloads
- service registration
- catch-up evaluation path
- cron-replacement cutover path with opt-in catch-up execution
- moisture write-back wiring

## Future Roadmap

- optional Smart Irrigation interoperability
- optional worker/add-on runtime if needed
- broader operator analytics
- richer zone policy editing
- possible future Home Assistant Core path once the product proves stable and
  generally useful
