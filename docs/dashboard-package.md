# Recommended Dashboard Package

The product ships one recommended Lovelace irrigation workspace.

It is not a dashboard builder.

## Design intent

- operator-first
- scanable on phone and tablet
- calm hierarchy
- minimal chrome
- no card mosaic

Using the frontend-skill standard:

Visual thesis:
- quiet control-room utility with one dominant decision rail, muted diagnostic
  context, and a single accent color reserved for states that need human
  action

Content plan:
- current watering posture first
- then the next operator decision
- then the evidence that explains that decision
- then deeper schedule detail

Interaction thesis:
- the first viewport should answer "do I need to do anything now?"
- review bands should collapse when healthy and expand only when a real action
  is available
- schedule detail should stay below the decision rail so the dashboard never
  feels like a spreadsheet first

Health contract:
- `Health` is runtime integrity only
- missing rain or moisture inputs are warnings, not top-level degradation
- the dashboard should render `supervisor_reason` and any `missing_inputs`
  directly below the posture rail so the operator does not need Developer Tools
- `Webhook health` is narrower than `Health`; it only answers whether the HA-
  managed Rachio webhook registration still looks valid

## Primary operator questions

The dashboard should be designed around these questions, in this order:

1. Are we watering, skipping, or waiting right now?
2. Do we owe a catch-up or top-up decision because rain or heat invalidated the
   original schedule intent?
3. Is measured soil moisture drifting enough from Rachio's estimate that we
   should write moisture back into Rachio?
4. Is a flow alert still a real problem, or has calibration shown it was a
   false alarm?

If the first viewport does not answer those four questions quickly, the
dashboard is carrying too much low-value detail.

## Recommended sections

The accepted live shadow layout is intentionally short:

1. Watering posture
2. Moisture drift
3. Catch-up / top-up outlook
4. Flow alert review
5. Schedule review

Freshness and parity diagnostics still matter, but they should not displace the
operator decision rail in the first viewport. Keep them as follow-on cards or a
shadow-only appendix during the 7-day comparison window.

## First-viewport contract

The first viewport should stay simple:

- `Health`
- `Webhook health`
- `Observed rain, 24h`
- `Catch-up evidence`
- `Last catch-up decision`
- `Active flow alerts`
- `Recommended moisture writes`
- one compact moisture review card below the posture rail

Keep lower-value diagnostics such as linked entry titles, raw bookkeeping, and
parity-only duplication below the fold.

## Accepted live shadow layout

The repository example should match the accepted live shadow view, not a
future-looking abstraction. Today that means:

- the primary entity surface is `sensor.rachio_site_*`
- the dashboard is a dedicated `Shadow` view
- the layout is section-led, not card-mosaic-led
- moisture stays review-oriented and manual-first
- flow alerts remain visibly gated until explicitly cleared

The current accepted screenshot lives at:

- [docs/assets/screenshots/shadow-dashboard-desktop.png](./assets/screenshots/shadow-dashboard-desktop.png)

## Frontend-skill critique

Using the frontend-skill lens against the current live shadow dashboard:

Strengths:

- the first viewport now answers the key operator questions quickly
- moisture is presented as drift and review, not a raw telemetry wall
- flow alerts have a dedicated review band with explicit clear gating
- Rear Protea Shade Bed is framed conservatively instead of as a routine
  top-up candidate

Remaining issues:

- raw `Recent decisions` entities were too dense for first-scan use when values
  were long, so the accepted contract now uses a templated markdown summary
  fed by compact `subject` / `brief` / `at_local` attributes
- the decision rail is split across too many adjacent cards for a narrow screen
- queue and audit context should stay below the posture rail unless non-zero
- parity comparison should be a shadow-only appendix, not a permanent operator
  surface

That critique should drive future dashboard iterations before the production
cutover, rather than treating the first live shadow view as finished.

## Decision rail design

The key operator rail should be a small set of decision tiles, not a large card
grid:

- `Catch-up evidence`
- `Last catch-up decision`
- `Recommended moisture writes`
- `Recommended moisture queue`
- `Active flow alerts`
- `Last flow alert decision`

This rail is where future optional alerting should anchor. Alerts should follow
the same priorities:

- first: flow alerts that still need human review
- second: catch-up or missed-run decisions that would otherwise be lost
- third: moisture-estimate drift only when write-back is enabled or review is
  explicitly requested

## Heatwave top-up stance

Heatwave top-up is a valid operator concept, but it should not be presented as
an always-on autonomous engine in the current public product.

For v1 dashboard design, treat heatwave top-up as a future extension of the
same decision rail:

- current product term: `Catch-up / top-up outlook`
- current implementation boundary: only show recommendation space where the
  runtime truly has supporting evidence
- future policy: high-heat, low-rain, fast-drying conditions may justify a
  supervised top-up recommendation

That keeps the UI stable even before the runtime grows into a fuller top-up
policy.

## Moisture drift design

Moisture sensors are not a standalone dashboard category.

They are a schedule-linked review signal.

The moisture section should focus on drift between:

- measured moisture from the mapped HA sensor
- Rachio's current watering posture / inferred estimate

The operator does not need another generic moisture dashboard. The useful
question is:

- is this close enough to trust, or far enough to justify a write-back?

So the moisture band should present:

- schedule name
- mapped sensor
- current band
- recommendation state
- write-back readiness
- last write result
- queue membership

Avoid showing every raw moisture number as a primary tile unless it is directly
useful to the write decision.

The operator contract should stay explicit:

- `Recommended` = review this schedule now
- `Ready` = a manual write can be issued now
- `Written` / `Rejected` = audit trail from the last manual write attempt

Do not treat moisture drift as automatic top-up watering in v1.

Even when recommended writes are `0`, the dashboard should still show the
mapped review list with:

- schedule name
- mapped sensor
- current band
- posture note
- write-back readiness

That is the only way to make wet-condition reviews legible after substantial
rain without inventing noisy or misleading recommendations.

### Conservative watch zones

Some zones should remain watch-oriented even after moisture sensors are mapped.

Example:

- mixed Protea / azalea / clivia shade beds should present as:
  - `Moisture watch`
  - `No default boost`
  - `Avoid saturation`

That kind of zone is not a generic top-up candidate. The UI should reinforce
that by showing a conservative posture note in schedule detail rather than
promoting it into the main action rail.

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

## Shadow dashboard posture

The shadow dashboard should be a separate view, not a modification of the
production irrigation dashboard.

Its job is to make old-versus-new comparison easy, not to look finished for the
end user on day one. That means:

- keep the comparison band explicit
- keep all destructive or externally visible actions gated
- prefer one comparison entities card over many duplicated tiles
- show parity drift clearly before introducing polished operator-only sections

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
