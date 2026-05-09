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

Explicitly not in v1:

- broad autonomous watering independent of Rachio schedule posture
- a generalized top-up engine that replaces schedule ownership

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
- not calibration-heavy agronomy

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
- zone-level opt-in
- not the primary control model

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

- any Home Assistant rainfall entity chosen by the user

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
- per-zone status
- per-zone reason/explanation
- per-zone moisture band
- per-zone catch-up candidate / decision state

### Services

Planned first-class services:

- evaluate now
- run catch-up now
- write moisture now
- acknowledge recommendation
- dismiss recommendation
- pause zone policy

### Diagnostics

Planned diagnostics surface:

- mapped Rachio inputs
- mapped moisture inputs
- mapped rain inputs
- policy mode per zone
- latest supervisor evidence snapshot
- stale webhook/API warnings

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

v1 does not ship:

- a custom dashboard builder
- dashboard generation

The dashboard package should include:

- current site status
- zone list with reasons
- moisture + rain context
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
- moisture write-back wiring

## Future Roadmap

- optional Smart Irrigation interoperability
- optional worker/add-on runtime if needed
- broader operator analytics
- richer zone policy editing
- possible future Home Assistant Core path once the product proves stable and
  generally useful

