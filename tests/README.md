# Test Notes

The repo carries a deterministic logic suite that runs without a full Home
Assistant install by stubbing the narrow import-time API surface used by the
current integration modules.

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
- observed rain `24h` `unknown/not_reported` parity
- degraded/healthy reconcile cadence semantics

Run locally with the repo runtime:

```bash
uv run python -m unittest -v tests.test_supervisor_logic
```

Readiness checks:

```bash
uv run python -m py_compile custom_components/rachio_supervisor/*.py
node --check custom_components/rachio_supervisor/www/rachio-supervisor-zone-grid-card.js
git diff --check
```

The public screenshots under `docs/assets/screenshots/` are sanitized product
captures. Do not replace them with live Home Assistant screenshots that include
private network addresses, account UI, property names, or raw house data.
