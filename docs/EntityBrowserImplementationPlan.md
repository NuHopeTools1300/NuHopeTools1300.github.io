# Entity Browser Implementation Plan

## Purpose

Give operators a clear browser interface for seeing the database without turning the evidence workbench into a generic CRUD admin panel.

This is the integrated browser-side companion to Datasette:

- Datasette answers: "show me the raw database / let me inspect SQL."
- Entity Browser answers: "show me this kit, placement, image, or region and everything connected to it."

## Implementation Status (May 2026)

Delivered in the current slice:

- `entity_browser.html` exists and is in active use
- tabbed browsing across the primary entity records: kits, parts, models, maps, images
- placements, image regions, and claims remain reachable as related/detail objects rather than primary tabs
- counts load for the primary entity tabs on startup
- search plus faceted filtering in-browser
- linked detail panels and pivots into map/image workbenches
- compatibility fixes for placement-kind faceting and kit badge rendering
- part rows show thumbnails when part reference images exist
- part detail shows available part reference images
- safe create/edit forms exist for the primary entity records

Remaining for the next focused pass:

- formalize an overview endpoint only if repeated client join logic grows again
- preserve read-mostly posture and keep destructive operations out of scope
- add focused review queues for placements, regions, and claims where they are more useful than top-level browsing

## Product Boundary

Build:

- read-first entity browsing
- fast search and filtering
- record detail inspection
- reverse lookups into linked evidence
- small, safe edits for high-value fields
- pivots into `workbench.html` and `map_workbench.html`

Do not build yet:

- arbitrary table editing
- schema editing
- bulk destructive operations
- public contribution workflow
- a replacement for Datasette, NocoDB, or Baserow

## Recommended UI Shape

Create a new browser surface:

- file: `entity_browser.html`
- shell: same shared API/auth layer as `workbench.html` and `map_workbench.html`
- layout: `entity type tabs / result list / detail inspector`

Primary tabs:

- Kits
- Parts
- Models
- Maps
- Images

Relationship and review objects:

- Placements
- Regions
- Claims

These should be exposed through linked detail sections, workbench pivots, or saved review queues rather than as default primary tabs.

Keep the first version visually plain and information-dense. This is a research console, not a public showcase.

## Milestone 1 - Read-Only Browser

Goal: make the database visible in the browser quickly.

Status: implemented as first slice in `entity_browser.html`.

Frontend:

- [x] add entity type tabs
- [x] add shared search box
- [x] show result rows with compact metadata
- [x] select a row and show detail
- [x] support direct URL state such as `entity_browser.html?type=kits&id=123`
- [x] add "Open in Image Workbench" links for images and regions
- [x] add "Open in Map Workbench" links for placements and maps
- [x] add "Open raw in Datasette" link where useful

Backend reuse:

- `GET /api/kits`
- `GET /api/kits/<id>`
- `GET /api/parts`
- `GET /api/parts/<id>`
- `GET /api/placements`
- `GET /api/placements/<id>`
- `GET /api/images`
- `GET /api/images/<id>`
- `GET /api/image_regions`
- `GET /api/image_regions/<id>`
- `GET /api/claims`
- `GET /api/claims/<id>`
- `GET /api/entity_search`

Acceptance check:

- an operator can search for a kit, open it, and see its parts, placements, linked images, and linked regions without writing SQL
- an operator can pivot from a kit, part, map, or image into related placements/regions/claims without making those relationship objects primary tabs
- an operator can search for an image, open it, and see its regions and linked entities

## Milestone 2 - Entity Overview Endpoint

Goal: reduce frontend join logic and make reverse lookups consistent.

Add one normalized endpoint:

```text
GET /api/entities/<entity_type>/<entity_id>/overview
```

Supported `entity_type` values for the first pass:

- `kit`
- `part`
- `placement`
- `model`
- `map`
- `image`
- `image_region`
- `claim`

Response shape:

```json
{
  "entity": {},
  "display": {
    "title": "",
    "subtitle": "",
    "badges": []
  },
  "sections": {
    "relations": [],
    "images": [],
    "regions": [],
    "placements": [],
    "claims": [],
    "history": []
  },
  "actions": {
    "open_in_workbench": "",
    "open_in_map_workbench": "",
    "open_in_datasette": ""
  }
}
```

Implementation rule:

- keep this endpoint read-only
- compose from existing tables and helper functions
- do not introduce new schema for this milestone
- keep missing sections as empty arrays rather than changing response shape

## Milestone 3 - Safe Light Editing

Goal: allow common cleanup without exposing the whole database as editable.

Enable edit forms only for fields that are safe and already supported by APIs.

Kit fields:

- brand
- scale
- name
- serial number
- category family / subject
- Scalemates URL
- notes

Image fields:

- title
- image type
- date taken
- source
- caption / notes

Part fields:

- kit id
- part number
- part label
- notes

Model/map fields:

- name / slug / film / scale / notes
- map model id / version / image id / URL / date / notes

Rules:

- admin/local-admin required for every edit
- keep forms field-limited and backed by existing API validation
- keep existing history/audit mechanisms active where those mechanisms already exist
- never allow delete in the first integrated Entity Browser version
- bulk edit stays out of scope

## Milestone 4 - Review Queues

Goal: turn database mess into actionable queues.

Add saved views in the Entity Browser:

- unlinked regions
- imported PPTX labels still unresolved
- kits with no linked regions/images
- placements with no current position
- placements with no linked evidence
- images with many regions but no linked entities
- claims with low confidence or review status

These should be implemented as named filters first. If they become stable, add backend endpoints or saved SQL notes.

## Milestone 5 - Decide Whether To Adopt More Tooling

After using the Entity Browser and Datasette together, reassess:

- If raw browsing is enough: stay with Datasette + Entity Browser.
- If spreadsheet-like multi-row editing is needed: evaluate `NocoDB` or `Baserow`.
- If custom table UX becomes necessary: use `TanStack Table`, `Tabulator`, or `AG Grid Community`.
- If image/map interaction remains the bottleneck: evaluate `OpenSeadragon`, `Annotorious`, or Leaflet-style viewport patterns.

Do not make this decision before Milestones 1-3 have been used on real cleanup work.

## Build Order

1. Create `entity_browser.html` with shared API/auth and read-only tab/list/detail shell.
2. Reuse existing list/detail endpoints for `kits`, `parts`, `models`, `maps`, `images`, and related placements/regions/claims.
3. Add direct pivots into image and map workbenches.
4. Add `/api/entities/<type>/<id>/overview` once repeated frontend lookup logic appears.
5. Add safe light editing for kits, parts, models, maps, and images.
6. Add review queues for unresolved/unlinked records.
7. Reassess whether Datasette plus this browser is enough before adopting heavier admin tooling.

## Non-Goals

- no legacy `frontend.html` expansion
- no public/community editing
- no destructive cleanup UI
- no new `physical_objects`, `locations`, or `events` work in this slice
- no migration away from SQLite in this slice
