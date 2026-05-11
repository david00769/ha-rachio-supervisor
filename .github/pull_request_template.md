## Summary

- 

## Validation

- [ ] `python3 -m py_compile $(find custom_components -name '*.py')`
- [ ] `python3 -m unittest -v tests.test_supervisor_logic`
- [ ] `node --check custom_components/rachio_supervisor/www/rachio-supervisor-zone-grid-card.js`
- [ ] JSON/YAML sanity checked
- [ ] Reviewed docs / README changes
- [ ] No private house data or credentials added

## Scope check

- [ ] Matches `PRD.md`
- [ ] Keeps the product Rachio-first
- [ ] Does not claim runtime behavior that is not implemented
