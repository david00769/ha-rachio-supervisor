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
- Rachio-app-like yard control: zone photos first, icon badges second, and
  Supervisor state layered on top only when it changes an operator decision

Content plan:
- zone photo grid first
- then weather/skip and next-run posture
- then moisture and flow review
- then raw audit detail

Interaction thesis:
- the first viewport should answer "do I need to do anything now?"
- review bands should collapse when healthy and expand only when a real action
  is available
- schedule detail should stay below the decision rail so the dashboard never
  feels like a spreadsheet first
- zone cards should use photos, icons, compact badges, and short labels instead
  of sentence-heavy explanations

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

The accepted production layout is zone-first, with four follow-on operator
sections. Each section owns one job so the same fact is not repeated in
multiple places.

1. Zones
2. Weather / skips
3. Moisture
4. Flow
5. Audit

Freshness and parity diagnostics still matter, but they should not displace the
operator decision rail in the first viewport. Keep them as follow-on cards or a
small audit appendix.

## Production Dashboard

The accepted plugin-backed surface should be the single production irrigation
dashboard. Do not keep a permanent shadow copy with duplicated supervisor facts;
that creates stale review paths and makes dashboard bugs ambiguous.

For the current live cutover, the production dashboard is:

- sidebar title: `Irrigation`
- dashboard URL path: `/irrigation-dashboard`
- source of truth: stable `sensor.rachio_site_*` entities plus the packaged
  `custom:rachio-supervisor-zone-grid-card`

The old Home-dashboard `Irrigation` view and the temporary
`Irrigation Shadow` dashboard should stay retired after promotion. Keep only a
small audit/diagnostic appendix for raw entity detail inside the production
dashboard.

The intended production relationship is:

- use the zone grid as the first viewport
- use weather, catch-up, moisture, flow, and audit sections below the zone grid
- route write/acknowledge actions through generic Supervisor queue services
- do not show the same schedule recommendation in both a "Moisture review" list
  and a separate "Schedule detail" list unless the second view adds different
  operator value

## First-viewport contract

The first viewport should stay simple:

- zone photos
- `Health`
- `Webhook health`
- active/running count
- rain/skip badge
- moisture badge
- flow-alert badge
- quick-run affordance on each live zone card

Keep lower-value diagnostics such as linked entry titles, raw bookkeeping, and
parity-only duplication below the fold.

## Zone-first layout

The UI should feel closer to the Rachio phone app than to a Home Assistant
diagnostic panel:

- one picture per zone
- one compact zone name
- icon badges for water/skip, Supervisor, and moisture
- next run shown as a short token when HA/Rachio exposes it
- quick run exposed as a confirmation-gated action on real live zone cards
- plant/soil/drip/slope notes kept to one small line or a lower detail panel

The Rachio app model separates Events, Zones, and Schedules. Rachio describes
Events as the place for weather, watering adjustments, and water usage; Zones
as the place for yard images/details; and Schedules as the place for schedule
and upcoming calendar context:

<https://rachio.com/blog/rachio-app-changes>

The Supervisor dashboard uses the same mental model: zones are the primary
surface, weather and schedule evidence explain the zone badges, and raw audit
detail stays below the operator controls.

The integration ships the `rachio-supervisor-zone-grid-card` Lovelace module
for this purpose. Add this dashboard resource:

`/rachio_supervisor/rachio-supervisor-zone-grid-card.js`

Resource type:

`JavaScript module`

Then use:

```yaml
type: custom:rachio-supervisor-zone-grid-card
entity: sensor.rachio_site_zone_overview
title: Zones
```

This card should be the first card in the production `Irrigation` dashboard.
Keep dense audit/status cards below it so the first viewport is the zone photo
surface, not the raw diagnostic appendix.

The card also reads these site-level Supervisor entities by default:

- `sensor.rachio_site_health`
- `sensor.rachio_site_webhook_health`
- `sensor.rachio_site_catch_up_evidence`
- `sensor.rachio_site_recommended_moisture_writes`
- `sensor.rachio_site_active_flow_alerts`

If a site uses different entity ids, override them with `health_entity`,
`webhook_entity`, `catch_up_entity`, `moisture_entity`, and `flow_entity`.

The Weather section should also include `sensor.rachio_site_heat_assist`. It is
a read-only Rachio forecast outlook for heat/top-up review, not an implemented
heat top-up automation.

The card can also expose a simple moisture calibration assistant in each zone
detail drawer. When a mapped soil-calibration `number` entity is available, the
operator enters the target moisture reading for the current field condition and
the card calculates the next offset as:

`current offset + (target moisture - current moisture)`

Applying the offset calls Home Assistant's `number.set_value` service after an
explicit confirmation. This is a sensor-offset assistant only; it does not run
watering, write moisture to Rachio, update firmware, or claim volumetric soil
accuracy. Apply stays disabled until both the moisture sensor and calibration
number report numeric states, so a sleepy Zigbee probe cannot be calibrated
from an unknown current offset.

Common Zigbee2MQTT-style `Soil calibration` number entities are auto-detected
from the mapped moisture sensor name. Keep the moisture-to-schedule mapping in
the integration options so the dashboard reads `moisture_entity_id` from the
zone overview payload. If auto-detection is ambiguous, use
`calibration_entities` as a narrow override by the mapped moisture entity:

```yaml
type: custom:rachio-supervisor-zone-grid-card
entity: sensor.rachio_site_zone_overview
title: Zones
calibration_entities:
  sensor.example_moisture:
    moisture: sensor.example_moisture
    soil: number.example_soil_calibration
```

The card reads `sensor.rachio_site_zone_overview`. Its `zones` attribute
includes:

- `zone_name`
- `schedule_entity_id`
- `zone_entity_id`
- `image_path`
- `image_source`
- `suggested_image_path`
- `fallback_image_path`
- `rachio_image_available`
- `photo_import_status`
- `photo_import_reason`
- `quick_run_minutes`
- `next_run`
- `watering_days`
- `last_run_at`
- `last_skip_at`
- `rain_skip_state`
- `water_badge`
- `supervisor_badge`
- `moisture_band`
- `moisture_observed_value`
- `moisture_observed_at`
- `moisture_age_label`
- `moisture_freshness`
- `moisture_confidence`
- `moisture_quality_note`
- `moisture_source_state`
- `moisture_entity_id`
- `flow_alert_state`
- `plant_note`
- `detail_note`

`image_path` always points at a loadable image: a local override, an imported
Rachio photo, or the packaged placeholder. `image_source` records which one is
active. `suggested_image_path` shows the filename convention to use for manual
local overrides without causing browser 404s on a fresh install.

Manual local overrides win over imported photos. Upload overrides to:

`/local/rachio-supervisor/zones/<zone-slug>.jpg`

If `import_rachio_zone_photos` is enabled, the integration caches available
Rachio zone photos under:

`/local/rachio-supervisor/imported-zones/<zone-id>.jpg`

The packaged placeholder remains the final fallback.

The zone overview sensor also exposes `photo_import_counts` and
`photo_import_summary`. Those attributes summarize disabled, cached, imported,
missing, rejected, and failed photo states across the full zone overview so
operators can confirm import behavior without inspecting each zone item.

Known photo limits:

- Rachio `imageUrl` may be absent for some zones.
- Very large Rachio originals are rejected rather than hotlinked.
- Photo import is opt-in and read-only.
- Manual local overrides always win.
- Unresolved zones use `/rachio_supervisor/zone-placeholder.svg`.

The packaged card uses the real `zone_entity_id` or `schedule_entity_id` from
the overview payload when it calls `rachio_supervisor.quick_run_zone`.
Quick Run is manual only, editable per click, and confirmation-gated. It calls
Home Assistant's existing Rachio watering service through the Supervisor
service; it does not enable catch-up, moisture auto-write, or any broader
autonomous watering policy.

Normal states should be quiet. The card intentionally shortens healthy labels
such as `rain`, `flow`, and `ok`, while abnormal states use stronger words such
as `skip`, `review`, `alert`, `moisture`, or `catch-up`. Full details remain in
the badge title, detail drawer, and Audit section.

The Supervisor overlay follows the same rule. It is a thin strip above the zone
grid, not a replacement for the zone UI. Healthy state renders as a quiet
single-line status. The detailed status pills appear only when the overlay has
something to explain, and only the relevant pills are shown. It becomes
visually stronger only for:

- runtime health or webhook degradation
- active catch-up/top-up review
- recommended moisture writes
- active flow alert review
- data warnings such as missing optional rain or moisture inputs

A built-in-only Markdown fallback can still be built from the same entity
payload, but it is visually inferior and should not be treated as the canonical
upstream dashboard.

Rain evidence should keep two labels distinct:

- `Observed rain, 24h` is the Rachio skip-event evidence parsed from event
  history
- `Actual rain` is the selected Home Assistant observed-rain source, with
  `window` and `confidence` attributes explaining whether the number is rolling
  24h, today, since 9am, or another source-specific total
- `Catch-up evidence` should display the dated Rachio skip/rain amount when one
  is driving review, with the machine status kept in the `status` attribute

If the selected source is a forecast-only weather entity, the dashboard should
show a data warning instead of silently treating forecast precipitation as rain
that already fell.

## Accepted Live Layout

The repository example should match the accepted live production dashboard, not
a future-looking abstraction. Today that means:

- the primary entity surface is `sensor.rachio_site_*`
- the dashboard is a dedicated `Irrigation` view
- the layout is zone-led through the packaged custom card, with Supervisor
  diagnostics pushed below the visual operating surface
- moisture stays review-oriented, with manual actions visible and auto-write
  requiring explicit per-schedule opt-in
- mapped moisture state is visible even when recommended write count is zero
- manual moisture write actions are confirmation-gated and do not start watering
- packaged manual actions use generic services (`write_recommended_moisture_now`
  and `acknowledge_all_recommendations`) so the upstream example is usable
  without fake schedule-name placeholders
- opt-in moisture auto-write is shown as schedule policy and status; it updates
  Rachio moisture estimates only and never starts watering
- flow alerts remain visibly gated until explicitly cleared
- raw decision strings live in `Audit`, not in the first scan path
- the primary surface is photo-led and icon-led; explanatory text belongs in
  zone detail drawers or Audit, not in the tile body

The public docs screenshot is a sanitized product capture. It should show the
accepted layout and entity contract without live Home Assistant chrome, private
network addresses, account details, property names, or raw house data.

- [docs/assets/screenshots/production-dashboard-desktop.png](./assets/screenshots/production-dashboard-desktop.png)

## Frontend-skill critique

Using the frontend-skill lens against the accepted live dashboard:

Strengths:

- the first viewport now answers the key operator questions quickly
- moisture is presented as drift and review, not a raw telemetry wall
- flow alerts have a dedicated review band with explicit clear gating
- Rear Protea Shade Bed is framed conservatively instead of as a routine
  top-up candidate

Remaining issues:

- raw `Recent decisions` entities were too dense for first-scan use when values
  were long, so the accepted contract now uses card-owned summaries fed by
  compact `subject` / `brief` / `at_local` attributes
- moisture recommendations used to show only a count; the accepted contract now
  shows `HA sensor -> Rachio zone moisture` before any write action
- the decision rail should stay self-contained inside the four operator cards
  rather than becoming a scattered card mosaic
- queue and audit context should stay below the posture rail unless non-zero
- parity comparison should be a shadow-only appendix, not a permanent operator
  surface
- repeated schedule summaries create confusion; the accepted pattern keeps one
  moisture review list and removes the duplicate schedule-detail list unless a
  specific drill-down is needed

That critique should drive future dashboard iterations against the production
dashboard, rather than reviving retired shadow views.

## Decision rail design

The key operator rail should be four self-contained cards, not a large card
grid:

- `Catch-up / top-up` owns rain skip, heat/top-up posture, last run/skip, and
  catch-up actions
- `Moisture drift` owns mapped moisture state, `HA sensor -> Rachio` write
  summaries, manual write buttons, and auto-write status
- `Flow review` owns the 7-day flow alert queue, calibration evidence, baseline
  deltas, and clear-review actions
- `Rachio Supervisor` owns runtime health, webhook health, data warnings, and
  the compact running log

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
- current implementation boundary: show the Rachio forecast as `Heat assist`
  context, but do not claim any autonomous heat top-up action
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
- last check-in age
- last valid observation age
- freshness
- confidence
- quality note
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
- `Auto` = schedule is off, watching, eligible, or blocked for auto-write
- `Written` / `Rejected` / `Auto written` / `Auto skipped` = audit trail from
  the last write attempt
- `Stale - no write`, `Calibrate sensor`, and `Sensor offline` = context only,
  not write-back candidates

Do not treat moisture drift as automatic top-up watering in v1.

Opt-in moisture auto-write is allowed in v1, but it is deliberately narrower
than watering automation:

- off by default
- enabled per schedule
- requires global moisture write-back mode
- writes only fresh, non-boundary mapped HA moisture evidence into Rachio
- uses a same-value cooldown
- records the last write result for audit

The UI must show what changes before exposing a write action:

- `HA sensor 13% -> Rachio not reported`
- `Sensor 13% -> Rachio zone moisture`
- `last check-in: 4h ago - fresh - high confidence`
- `last valid: 2d ago - stale - blocked`

If the Rachio public API does not expose the current zone moisture estimate,
the dashboard must say `not reported` instead of inventing a comparison.

Do not overstate sensor accuracy. CS-201Z-style sensors can sleep or report
intermittently, so Rachio Supervisor uses the last valid dated observation
instead of treating transient `unknown` as data loss. Repeated `0%` or `100%`
readings should show as calibration-suspicious until corrected or explicitly
accepted by the operator.

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

The dashboard package should stay useful even when:

- no moisture sensors are mapped yet
- no actual-rain entity is selected yet
- automatic catch-up remains disabled for every schedule, or is enabled only for
  specific schedules selected during cutover

## Retired Shadow Posture

Shadow dashboards are temporary acceptance surfaces only. Once production is
promoted, delete the shadow dashboard and remove stale Home-dashboard irrigation
views so operators review one source of truth.

During a future migration shadow period:

- keep the comparison band explicit
- keep all destructive or externally visible actions gated
- prefer one comparison entities card over many duplicated tiles during the
  shadow period only
- show parity drift clearly before introducing polished operator-only sections
- when the plugin-backed sections prove out, move those sections into the
  production irrigation dashboard and retire the old-script cards

## Cron cutover checklist

When replacing an old cron-published supervisor, use the dashboard as a cutover
gate before pausing the cron runner:

1. Reload the custom integration and confirm `Health`, `Webhook health`, `Last
   reconciliation`, `Catch-up evidence`, and `Last catch-up decision` are fresh.
2. Confirm the zone grid card loads from
   `/rachio_supervisor/rachio-supervisor-zone-grid-card.js`.
3. Select only reviewed schedules for automatic catch-up.
4. Disable `observe_first` only after the selected schedules resolve to the
   intended zone entities.
5. Run `rachio_supervisor.evaluate_now` to force fresh Rachio evidence,
   including webhook and optional photo-import evidence.
6. Pause the old cron automation once the plugin-backed integration is healthy
   and publishing catch-up decision state.

## Legacy Shadow Comparison Note

This is historical cutover guidance for future migrations, not the current
production posture.

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
