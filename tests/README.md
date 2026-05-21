# Test Notes

The repo carries a deterministic logic suite that runs without a full Home
Assistant install by stubbing the narrow import-time API surface used by the
current integration modules.

## Test layers

### Unit / deterministic logic

This is the default local and CI layer. It stubs the Home Assistant import-time
surface and exercises pure coordinator, config-flow, service, entity, photo,
and card-contract behavior without requiring a live Home Assistant install.

Current coverage:

- config flow optional-input behavior
- options flow moisture-mapping behavior
- site-level entity naming and state exposure
- diagnostics payload shape
- catch-up decision safety and duplicate lockout
- manual Quick Run service targeting
- moisture evidence freshness, confidence, cache, and calibration-suspicion
  policy
- manual and automatic moisture write-back guardrails
- zone overview payload and static card contract, including the dashboard
  calibration assistant
- optional Rachio zone-photo import handling
- flow-alert lifecycle classification
- flow-alert clear-review guardrails
- dashboard/docs resource-version consistency for the packaged Lovelace module
- observed rain `24h` `unknown/not_reported` parity
- degraded/healthy reconcile cadence semantics

Run locally with the repo runtime:

```bash
uv run python -m unittest -v tests.test_supervisor_logic
```

### Integration / package sanity

This layer verifies that the checked-in custom component and packaged Lovelace
module are syntactically loadable and that public JSON/YAML artifacts parse.
It is intentionally lightweight so it can run on every push.

Readiness checks:

```bash
uv run python -m py_compile custom_components/rachio_supervisor/*.py
node --check custom_components/rachio_supervisor/www/rachio-supervisor-zone-grid-card.js
git diff --check
```

CI also parses checked-in JSON plus workflow, service, and example dashboard
YAML. Keep that gate aligned with `.github/workflows/validate.yml`.

### End-to-end / Home Assistant visual gate

The public repo does not carry private Home Assistant storage or live property
data, so full dashboard validation remains a manual or local-environment gate.
Before promoting a dashboard-facing change, install or redownload the HACS
custom integration, restart or reload Home Assistant as appropriate, confirm the
Lovelace resource uses the installed version query, and visually inspect the
Irrigation dashboard on desktop and narrow/mobile widths.

Use this gate for:

- packaged card layout changes
- Supervisor overlay copy or warning-state changes
- Rachio photo import behavior
- flow-alert review and clear-review affordances
- moisture calibration/detail drawer changes

The public screenshots under `docs/assets/screenshots/` are sanitized product
captures. Do not replace them with live Home Assistant screenshots that include
private network addresses, account UI, property names, or raw house data.
