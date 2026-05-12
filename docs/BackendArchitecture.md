# Backend Architecture

Updated: May 3, 2026

The backend is a Flask application with the app shell in `backend/app.py`, API route domains in `backend/blueprints/`, and shared behavior in focused service/helper modules.

## Current Module Map

| Module | Owns |
|--------|------|
| `backend/app.py` | Flask app setup, CORS/local browser headers, blueprint registration, static file routes, health check, and local entrypoint |
| `backend/blueprints/catalog.py` | Kit, part, model, map, kit reference, kit history, and part-file routes |
| `backend/blueprints/evidence.py` | Image, image-family, image-region, image-link, and image-tag routes |
| `backend/blueprints/imports.py` | Import and import-cleanup API routes under `/api/imports` |
| `backend/blueprints/placements.py` | Placement, refinement, merge, placement-position, contributor, and cross-model connection routes |
| `backend/blueprints/research.py` | Cast assembly, source, source extract, contributor, entity search, claim, and global search routes |
| `backend/config.py` | Local paths, upload directories, allowed image extensions, request-size limit |
| `backend/db.py` | SQLite connection lifecycle for Flask request contexts |
| `backend/schema_bootstrap.py` | Local database initialization and temporary compatibility bridges |
| `backend/api_utils.py` | API response wrappers, row conversion, numeric/JSON parsing, tag/bool helpers |
| `backend/auth.py` | Admin API-key and local-admin decorator |
| `backend/import_services.py` | Spreadsheet path resolution and import pipeline orchestration |
| `backend/history_services.py` | Kit and image-region history writes |
| `backend/placement_services.py` | Placement-position queries, part-file summaries, merge/refine helpers |
| `backend/image_family_services.py` | Image-family membership and primary-image helpers |
| `backend/image_services.py` | Image create/update flows, including upload handling and tag/family updates |
| `backend/entity_services.py` | Entity display labels and claim enrichment |

## Current Boundary

This pass keeps public URLs and payloads unchanged. The immediate goal is to reduce the `app.py` monolith without changing operator workflows.

Blueprint splitting is complete for the current non-static API domains. The remaining routes in `app.py` are app-shell concerns: uploaded file serving, part image serving, and `/api/health`.

## Next Modularization Pass

Recommended order:

1. Expand route-level smoke coverage from route presence into payload checks for the highest-value workflows.
2. Consider an app-factory split once tests need isolated Flask app instances.
3. Review auth boundaries route-by-route and document which write/admin endpoints intentionally allow local-admin access.

Keep route URLs identical during each cleanup slice and run `.\tools\verify.ps1` after each change.
