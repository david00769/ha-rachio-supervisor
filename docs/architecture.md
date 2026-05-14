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

Weather Underground / The Weather Company PWS data fits this model when it is
first exposed as a Home Assistant sensor, for example by a REST or custom
integration. The supervisor consumes the resulting observed-rain entity; it
does not ship a bundled Weather Underground API key. If Home Assistant owns the
REST/custom sensor, the key should stay in Home Assistant secrets and the
supervisor should consume only the resulting numeric observed-rain entity.

The supervisor can also own a user-configured Weather Underground PWS override:
the operator selects the PWS source mode, enters a station ID and API key, and
the coordinator polls the station's current `precipTotal` directly. Station
`precipTotal` values are daily totals unless the source explicitly publishes a
rolling 24h total. This is intentionally a user-selected override, not data
inferred from the Rachio controller.

Rachio weather data is handled separately. The public forecast endpoint is
queried to expose source/provider hints and a read-only `Heat assist` weather
outlook. Rachio forecast payloads are not used as actual rainfall because
forecast precipitation and observed rainfall are different evidence classes.

## Moisture write boundary

Moisture write-back updates Rachio's zone moisture estimate. It never starts
watering.

Mapped moisture sensors are resolved as dated observations before they are used
for review or write-back. The coordinator keeps a runtime cache of the last
valid numeric sample per mapped entity so temporary `unknown` or `unavailable`
states from sleeping MQTT/Zigbee probes do not erase useful evidence. Current
numeric state always wins over the cache.

Freshness is explicit:

- `fresh`: last valid numeric sample is 6 hours old or less
- `recent`: more than 6 hours and 30 hours old or less
- `stale`: more than 30 hours and 72 hours old or less
- `expired`: older than 72 hours or no valid numeric sample

Manual review may use fresh or recent evidence. Bulk recommended writes use
fresh or recent non-boundary-suspicious evidence. Auto-write is stricter: it
requires fresh, non-boundary-suspicious evidence and still respects the
same-value cooldown. Stale and expired moisture are display context only.

CS-201Z-style sensors can report intermittently and may expose companion
entities such as `soil_sampling`, `battery`, `linkquality`,
`soil_calibration`, and `soil_warning`. Those companions improve confidence
when present, but the resolver remains generic for any Home Assistant moisture
sensor. Repeated `0%` or `100%` values are calibration-suspicious until the
operator calibrates or manually accepts them.

The dashboard card may expose a simple calibration assistant when a mapped or
explicitly configured soil-calibration number entity is available. It computes
an offset from the current Home Assistant moisture reading and an operator
target, then calls `number.set_value` after confirmation. The action is disabled
unless both the moisture reading and current calibration offset are numeric. It
does not update sensor firmware, run watering, or write to Rachio.

The runtime supports these write and review paths:

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
card is the canonical public dashboard surface. Zone images use a safe
resolution order: optional local override, optional cached Rachio import, then
the packaged placeholder. Rachio photo import is read-only and opt-in.

Automatic catch-up and moisture write-back remain separate policy paths.

## Lovelace resource boundary

The packaged zone grid card is part of the integration distribution. The
dashboard should load it through a Lovelace JavaScript module resource that
points at the Home Assistant-served static file, preferably with the installed
integration version as a query string:

`/rachio_supervisor/rachio-supervisor-zone-grid-card.js?v=0.2.10`

The query string is a cache-busting contract for HACS upgrades. Updating the
custom integration package alone does not guarantee an already-open Lovelace
session has reloaded the card module. Upgrade guidance should therefore include
the normal sequence:

1. update or redownload the custom integration in HACS
2. restart Home Assistant so the new Python and static assets are served
3. ensure the Lovelace resource points at the packaged module URL with the
   installed version query
4. refresh any already-open dashboard tab

Inline `data:text/javascript` Lovelace resources are not a supported production
path. They bypass the packaged static asset and can leave the dashboard pinned
to old card behavior even when the integration itself has updated.

## Automatic action boundary

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
