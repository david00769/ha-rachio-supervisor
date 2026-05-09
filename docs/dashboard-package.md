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
- site-level moisture-write queue and recommendation sensors
- per-schedule status / reason / policy entities
- per-schedule moisture / write-back / recommendation entities

The example YAML should now be treated as a near-term operator contract built
around the shipped entity model, not around a future generic zone abstraction.
