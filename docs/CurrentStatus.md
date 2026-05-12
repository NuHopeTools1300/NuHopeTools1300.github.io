# Current Status

Updated: May 3, 2026

## Short Version

NuHopeTools is in a private Phase 1 workstation state.

The donor-part backbone is usable, the active workbench surfaces are live, and the next work should be consolidation plus focused workflow completion rather than broad feature expansion.

Documentation entry points:

- [Documentation Index](README.md)
- [API Reference](API.md)
- [Backend Architecture](BackendArchitecture.md)
- [Data Model](DataModel.md)
- [Deployment Plan](DeploymentPlan.md)

## Active Surfaces

- `workbench.html` - image evidence, regions, entity linking, claims, image families
- `map_workbench.html` - kit-first map placement, placement positions, refinement, map evidence links
- `entity_browser.html` - read-first entity visibility and relationship pivots
- Datasette sidecar - raw SQLite inspection and controlled local admin review

Legacy/sidecar tools still exist, but should stay maintenance-only unless a concrete migration or bug fix needs them:

- `frontend.html`
- `tools/ImageAnnotator.html`
- `tools/image_timeline.html`
- `tools/box_art_extractor.html`

## Current Data Shape

Snapshot from the local SQLite database during the May 1 cleanup baseline:

- `449` kits
- `1,797` parts
- `2,845` placements
- `420` images
- `533` image regions
- `5` claims
- `5` sources
- `0` source extracts

Interpretation:

- part/kit placement data is the strongest layer
- image-region linking is active but still being populated
- claims and source extracts exist structurally, but are early in actual use
- the map-position layer exists and works, but only covers a small part of the placement set so far

## Verification

Run:

```powershell
.\tools\verify.ps1
```

The verifier now covers:

- recursive Python syntax compilation for backend modules, blueprints, and tool scripts
- route contract smoke test
- placement position smoke test
- image region / claim smoke test
- import reconciliation smoke test
- placement refine / merge smoke test

## Immediate Build Lane

1. Checkpoint the backend modularization pass; all current non-static API domains now live in Blueprints with URLs unchanged.
2. Finish placement-to-evidence flow in `map_workbench.html`.
3. Keep entity-first visibility split between `entity_browser.html` and Datasette.
4. Improve image browsing speed and canvas ergonomics in `workbench.html`.
5. Continue verification hardening around route payloads and high-value workflows before larger feature work.
6. Keep schema changes on the `schema.sql` plus ordered migration path.
7. Keep runtime data, generated imports, backups, uploads, and private archives out of normal source-control churn.

## Documentation Ownership

- README is the short project front door.
- This file is the current operational status source.
- [API Reference](API.md) owns route inventory.
- [Backend Architecture](BackendArchitecture.md) owns backend module boundaries.
- [Data Model](DataModel.md) owns readable schema summary.
- [Deployment Plan](DeploymentPlan.md) owns current hosting/storage/access-control direction.
- [Roadmap](Roadmap.md) owns strategic direction and longer-term phases.
- [Phase 1 Build Checklist](Phase1BuildChecklist.md) is a completed implementation record, not the live task list.

## Deferred On Purpose

Do not widen the active implementation into these until the current workstation core is more settled:

- canonical `locations`
- `physical_objects`
- `object_states`
- `events`
- public/community graph and contribution workflows
