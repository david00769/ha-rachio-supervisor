# Test notes

The repo now carries a first deterministic logic suite that runs without a full
Home Assistant install by stubbing the narrow import-time API surface used by
the current integration modules.

Current coverage:

- flow-alert lifecycle classification
- flow-alert clear-review guardrails
- observed rain `24h` `unknown/not_reported` parity
- degraded/healthy reconcile cadence semantics

Run locally with the bundled runtime:

```bash
/Users/davidsiroky/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m unittest -v tests.test_supervisor_logic
```

Still missing:

- config flow tests
- options flow tests
- entity naming and state tests
- diagnostics tests
- catch-up decision tests
- moisture write-back tests
- shadow dashboard screenshot verification
