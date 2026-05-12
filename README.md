# ILM Van Nuys Kit-Bash Research Platform

NuHopeTools is a private research workstation for documenting kit-bashed parts used on ILM studio models built in Van Nuys, starting with the 5-foot Millennium Falcon from ANH.

The goal is to make cross-model donor-kit connections visible, keep evidence attached to every interpretation, and preserve researcher attribution.

## Current State

Phase 1 is complete enough to build on. The active project is now a local Flask + SQLite backend plus focused browser workbenches for image evidence, map placements, and entity lookup.

Start with:

- [Current Status](docs/CurrentStatus.md) for the short current-state view
- [Documentation Index](docs/README.md) for the full docs map
- [Roadmap](docs/Roadmap.md) for the longer strategic plan

## Active Tools

Live static tools are served from [nuhopetools1300.github.io](https://nuhopetools1300.github.io).

| Tool | Role |
|------|------|
| [Workbench](workbench.html) | Active image evidence, region linking, claims, and image family workflow |
| [Map Workbench](map_workbench.html) | Active kit-first map placement, position correction, and evidence linking workflow |
| [Entity Browser](entity_browser.html) | Active read-first database visibility with relationship pivots |

Legacy and sidecar tools remain available, but should stay maintenance-only unless a concrete migration or bug fix needs them:

- [Image Annotator](tools/ImageAnnotator.html)
- [Image Timeline](tools/image_timeline.html)
- [Box Art Extractor](tools/box_art_extractor.html)
- [frontend.html](frontend.html)

## Local Setup

```bash
pip install -r requirements.txt
python -m backend.app
```

The backend creates `backend/data/ilm1300.db` on first run and serves the API at `http://localhost:5000`.

Operational notes:

- Keep only one backend process bound to port `5000` during testing.
- If endpoint behavior looks stale, stop existing listeners on `5000` and restart the backend from this workspace.
- Runtime data under `backend/data/` is local state and should not be committed.

## Verification

```powershell
.\tools\verify.ps1
```

The verifier runs Python compile checks plus the current backend smoke tests for placement positions, image regions/claims, import reconciliation, and placement refine/merge.

## Data Import

```bash
python backend/import_spreadsheets.py --kits path/to/PartList_private.xlsx
python backend/import_spreadsheets.py --donors path/to/ANH_donors.xlsx
```

Both imports can be run together:

```bash
python backend/import_spreadsheets.py \
    --kits path/to/PartList_private.xlsx \
    --donors path/to/ANH_donors.xlsx
```

See [Data Model](docs/DataModel.md), [API Reference](docs/API.md), and [Migration Policy](backend/migrations/README.md) for implementation details.

## Documentation

The docs are organized from current operational truth to deeper design history:

- [Documentation Index](docs/README.md)
- [Current Status](docs/CurrentStatus.md)
- [API Reference](docs/API.md)
- [Backend Architecture](docs/BackendArchitecture.md)
- [Data Model](docs/DataModel.md)
- [Deployment Plan](docs/DeploymentPlan.md)
- [Roadmap](docs/Roadmap.md)
- [Product UI Architecture](docs/ProductUIArchitecture.md)
- [Research Architecture](docs/ResearchArchitecture.md)
- [Phase 1 Build Checklist](docs/Phase1BuildChecklist.md)

Generated review artifacts live under `docs/generated/`; they are useful review outputs, not the canonical status source.

## Immediate Build Lane

1. Finish placement-to-evidence flow in `map_workbench.html`.
2. Keep entity-first visibility split between `entity_browser.html` and Datasette.
3. Improve image browsing speed and canvas ergonomics in `workbench.html`.
4. Keep schema changes on the `schema.sql` plus ordered migration path.
5. Keep runtime data, generated imports, backups, uploads, and private archives out of normal source-control churn.
