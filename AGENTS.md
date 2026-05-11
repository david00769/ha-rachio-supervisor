# Project Agent Notes

This repository is the public upstream seed for `Rachio Supervisor for Home Assistant`.

Repository rules:
- Keep this repo publishable. Do not add house-specific secrets, screenshots with private addresses, exported Home Assistant storage, or raw property data.
- The product is a HACS custom integration first. Do not pivot it into an add-on-first runtime without updating `PRD.md`.
- Treat `PRD.md` as the decision contract for public-facing scope.
- Keep the docs site polished and restrained. The public docs should match the actual integration surface and example dashboard package.
- Do not claim runtime behavior that is not implemented. If scaffolding exists ahead of functionality, say so plainly in docs and release notes.
- Keep `rachio_supervisor.evaluate_now` as a forced fresh Rachio evidence reconciliation, not only a coordinator refresh. Photo import, webhook cutover checks, and operator debugging depend on live evidence.
