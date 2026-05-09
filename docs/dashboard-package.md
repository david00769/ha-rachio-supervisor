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
3. Flow alert review
4. Moisture recommendations
5. Schedule review table
6. Review queue / actions

## Entity expectations

The current public runtime now provides:

- site-level health and freshness sensors
- site-level last-run / last-skip sensors
- legacy-parity aliases for `last run event` and `last skip decision`
- site-level last-event / last-reconciliation / observed-rain sensors
- site-level moisture-write queue and recommendation sensors
- site-level active-review and acknowledged-review queue sensors
- site-level active flow-alert count, queue, and last-decision sensors
- per-schedule status / reason / policy entities
- per-schedule moisture / write-back / recommendation / review entities

## Flow alert UI evaluation

Using the frontend-skill standard, the current operator surface should treat
flow alerts as a narrow review rail, not as a loud alarm wall.

Visual thesis:
- quiet control-room utility with one accented review rail for items that still
  need a real operator decision

Content plan:
- status first
- then one dedicated flow-alert review band
- then moisture and schedule detail below

Interaction thesis:
- the alert queue should collapse to a terse healthy state when empty
- one tap should reveal baseline-before, baseline-after, delta, calibration
  time, and recommended action
- clear actions should feel gated and deliberate, not like casual dismiss chips

UI rules for flow-alert handling:

- `calibration_required`, `calibrated_needs_review`, and `problem_suspected`
  should remain visually active in the review rail
- `normal_after_calibration` should present as **eligible to clear**, not as
  already resolved
- the UI should show the baseline comparison explicitly before any clear action
- the clear action copy should say `Clear review`, not imply that the native
  Rachio alert itself is being dismissed

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

## Shadow comparison note

For a real cutover, do not jump directly from the old Codex-published sensors to
the new generic site-level tiles.

Start with a parallel shadow view that places these old and new surfaces next to
each other:

- old `sensor.sugarloaf_rachio_supervisor_webhook_health` vs new `Webhook health`
- old `sensor.sugarloaf_rachio_supervisor_last_event` vs new `Last event`
- old `sensor.sugarloaf_rachio_supervisor_last_run_event` vs new `Last run event`
- old `sensor.sugarloaf_rachio_supervisor_last_skip_decision` vs new `Last skip decision`
- old `sensor.sugarloaf_rachio_supervisor_last_reconciliation` vs new `Last reconciliation`
- old `sensor.sugarloaf_rachio_observed_rain_24h` vs new `Observed rain, 24h`
- old `sensor.sugarloaf_rachio_supervisor_catch_up_evidence` vs new `Catch-up evidence`
- old `sensor.sugarloaf_rachio_supervisor_last_catch_up_decision` vs new `Last catch-up decision`

That shadow view is the acceptance surface for production cutover. Once those
pairs agree in live use, replace the old cards instead of preserving both.
