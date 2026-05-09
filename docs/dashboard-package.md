# Recommended Dashboard Package

The product ships one recommended Lovelace irrigation workspace.

It is not a dashboard builder.

## Design intent

- operator-first
- scanable on phone and tablet
- calm hierarchy
- minimal chrome
- no card mosaic

## Recommended sections

1. Site status
2. Actual rain and freshness
3. Moisture recommendations
4. Schedule review table
5. Review queue / actions

## Entity expectations

The current public runtime now provides:

- site-level health and freshness sensors
- site-level last-run / last-skip sensors
- site-level last-event / last-reconciliation / observed-rain sensors
- site-level moisture-write queue and recommendation sensors
- site-level active-review and acknowledged-review queue sensors
- per-schedule status / reason / policy entities
- per-schedule moisture / write-back / recommendation / review entities

The example YAML should now be treated as a near-term operator contract built
around the shipped entity model, not around a future generic zone abstraction.

Current review acknowledgement behavior is runtime-only. The dashboard should
not imply those acknowledgements survive an integration reload until the product
implements durable review state explicitly.

The dashboard package should also assume a shadow-first rollout. It should stay
useful even when:

- no moisture sensors are mapped yet
- no actual-rain entity is selected yet
- automatic catch-up remains disabled for every schedule
