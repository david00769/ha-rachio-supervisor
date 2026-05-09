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

## Evidence split

### Planned intent

Comes from Rachio:

- runs
- skips
- delays
- controller-side watering state

### Observed actuals

Comes from Home Assistant:

- rainfall totals
- optional moisture sensors

This distinction is the center of the product model.

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
- if no moisture candidates are selected, the flow skips the schedule-mapping
  step instead of presenting an empty mapping form

This is a deliberate product choice. The supervisor should be installable
before the operator has finalized every optional evidence source.

### possible future expansion

- optional worker/add-on
- richer policy editing
- Smart Irrigation interop
