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
3. Zone table with reasons
4. Moisture context
5. Review queue / actions

## Entity expectations

The example dashboard assumes the integration eventually provides:

- site-level health and freshness sensors
- site-level last-run / last-skip / last-reconcile sensors
- per-zone status / reason entities
- per-zone moisture-band entities
- recommendation state entities

The initial scaffold in this repo does not yet expose the full zone-level model.
The YAML package is the target operator contract, not the current runtime limit.

