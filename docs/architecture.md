# Architecture

## Runtime boundary

The product is intentionally **integration-first**.

Why:

- Home Assistant config flow is the right setup surface.
- entities, services, and diagnostics are the right public contract.
- the operator experience belongs inside Home Assistant.
- an add-on would be useful only if later runtime demands exceed what the
  integration can comfortably handle.

## System roles

### Rachio

- schedule authority
- controller event history
- watering execution
- optional moisture-state recipient

### Home Assistant core `rachio` integration

- controller connection layer
- existing HA-side Rachio entities/actions

### Rachio Supervisor

- policy layer
- evidence correlation
- actual-rain reasoning
- moisture interpretation
- catch-up recommendations
- opt-in automatic actions
- operator diagnostics
- visual zone-overview payload for the Home Assistant dashboard

## Evidence split

### Planned intent

Comes from Rachio:

- runs
- skips
- delays
- controller-side watering state

### Observed actuals

Comes from Home Assistant:

- rainfall totals from numeric observed-rain sensors/helpers, or weather
  entities that expose a numeric observed precipitation total
- optional moisture sensors

This distinction is the center of the product model.

Forecast-only weather entities are not treated as observed rainfall. They stay
visible as data-completeness warnings so the operator knows why actual-rain
reasoning is incomplete.

The preferred rain source is a real local gauge already present in Home
Assistant. That can come from core or custom integrations such as Ecowitt,
WeatherFlow/Tempest, Netatmo, Ambient Weather, MQTT, ESPHome, or any other
integration that exposes a numeric observed rainfall total.

When no local gauge is available, the runtime remains international by design:
operators can map any numeric observed-rain source. The resolver accepts common
daily and regional fields such as `rain_today`, `rain_since_9am`,
`precipTotal`, `precipitation_today`, and `observed_precipitation`. Australian
installations can use a BOM/WillyWeather-derived custom integration if it
publishes observational rainfall sensors. The source window is exposed
separately as `24h`, `today`, `since_9am`, `last_hour`, or another explicit
window so the dashboard does not pretend every source is rolling 24h.

Rachio weather data is handled separately. The public forecast endpoint is
queried only to expose source/provider hints in diagnostics. Rachio forecast
payloads are not used as actual rainfall because forecast precipitation and
observed rainfall are different evidence classes.

## Moisture write boundary

Moisture write-back updates Rachio's zone moisture estimate. It never starts
watering.

The runtime supports two write paths:

- manual `write_moisture_now`, confirmation-gated in dashboard examples
- bulk manual `write_recommended_moisture_now`, which writes only schedules
  that are both recommended and ready in the current snapshot
- opt-in per-schedule auto-write, off by default and guarded by global
  write-back mode, resolved zone identity, numeric mapped sensor value, and a
  same-value cooldown
- `acknowledge_all_recommendations`, which marks current pending schedule
  recommendations reviewed without changing Rachio

## Manual quick-run boundary

The integration also exposes `quick_run_zone` so a dashboard can mimic the
Rachio app's per-zone Quick Run affordance. This is not Supervisor automation.
It is an explicit operator action that calls Home Assistant's existing
`rachio.start_watering` service for a resolved zone entity and bounded duration.
The Home Assistant Rachio action expects `duration` as minutes directly:

<https://www.home-assistant.io/integrations/rachio/#action-rachio-start_watering>

The recommended UI shape is:

- zone photo
- compact zone name
- watering day chips
- next-run / skip / moisture / flow badges
- confirmation-gated Quick Run button with editable minutes

The integration serves this as a lightweight Lovelace module:

`/rachio_supervisor/rachio-supervisor-zone-grid-card.js`

The module reads `sensor.rachio_site_zone_overview` and does not require a
build step or an external custom-card dependency. Built-in Lovelace cards can
still consume the same entity payload as a fallback, but the packaged custom
card is the canonical public dashboard surface.

Automatic catch-up and moisture write-back remain separate policy paths.

Automatic catch-up is only for schedules explicitly selected in the schedule
policy step. While `observe_first` is enabled, the supervisor publishes the
confirmed decision but does not start watering. Once `observe_first` is disabled
for a reviewed install, the coordinator can call `rachio.start_watering` for the
resolved zone entity with `duration` as a plain minute integer. The manual
`run_catch_up_now` service uses the same current-decision check and duplicate
lockout for an explicit operator-triggered run.

Because the Rachio public API does not expose every current zone moisture
estimate, the dashboard contract is explicit: show `Rachio not reported` when
the comparison value is unavailable, and still show the proposed write value.

## Delivery shape

### v1 repo

- HACS custom integration
- docs landing page
- recommended Lovelace dashboard package

## Setup model

The current install path is intentionally compatible with shadow-mode rollout in
an existing Home Assistant system.

- the config flow binds to an existing built-in `rachio` config entry
- linked Rachio entities are discovered through the Home Assistant entity
  registry rather than by asking the user to re-enter controller identity
- actual-rain input is optional at setup time
- moisture candidates are optional at setup time
- moisture auto-write schedules are optional and remain off unless selected in
  schedule policy
- if no moisture candidates are selected, the flow skips the schedule-mapping
  step instead of presenting an empty mapping form

This is a deliberate product choice. The supervisor should be installable
before the operator has finalized every optional evidence source.

### possible future expansion

- optional worker/add-on
- richer policy editing
- Smart Irrigation interop
