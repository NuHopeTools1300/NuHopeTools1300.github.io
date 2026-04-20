# Phase 1 Build Checklist

## Purpose

This checklist translates the first real product slice into concrete implementation work.

Scope for Phase 1:

- browse images
- annotate regions
- link regions to entities
- create claims
- review provenance

This is the smallest coherent version of the future workbench.

## Definition Of Done

Phase 1 is done when a researcher can:

1. open the workbench
2. find an image
3. inspect the image on a proper canvas
4. create or select a region
5. link that region to a real entity
6. create a claim from that evidence
7. revisit the image later and still understand source, attribution, confidence, and history

## Workstream 1: Backend

### 1. Images API Hardening

- [x] Confirm `GET /api/images` returns the fields needed for library rows
- [x] Add or normalize display fields:
  - `title`
  - `image_code`
  - `image_type`
  - `date_taken`
  - `source_id`
  - region count
  - claim count later
- [x] Add filters needed by the workbench:
  - `q`
  - `image_type`
  - `source_id`
  - `tag`
- [x] Ensure image list responses are consistent enough that the frontend does not need custom reconstruction logic

### 2. Image Regions API Completion

- [x] Confirm `GET /api/images/<id>` includes regions
- [x] Confirm `GET /api/image_regions?image_id=...` is stable and sufficient
- [x] Support create/update/delete for:
  - point regions
  - box regions
- [x] Ensure normalized coordinates are the canonical storage
- [x] Keep pixel coordinates optional but supported for audit/debug
- [x] Add basic validation for malformed region payloads

### 3. Entity Picker Search

- [x] Create one backend search endpoint suitable for linking regions to entities
- [x] Support at minimum:
  - `kit`
  - `part`
  - `placement`
  - `model`
- [x] Return normalized picker rows:
  - `entity_type`
  - `entity_id`
  - `title`
  - `subtitle`
  - `badges`
  - optional confidence/status summary
- [x] Make results useful enough to reduce mis-linking

### 4. Claims Layer

- [x] Add `claims` table
- [x] Define minimal fields:
  - `subject_type`
  - `subject_id`
  - `predicate`
  - `object_type`
  - `object_id`
  - `text_value`
  - `confidence`
  - `status`
  - `rationale`
  - `attributed_to`
  - timestamps
- [x] Add evidence-link mechanism for claims
- [x] At minimum, support linking a claim to:
  - `image_region`
  - optionally `source_extract`
- [x] Create endpoints:
  - list claims by region
  - create claim
  - update claim
  - view claim

### 5. Provenance And History

- [x] Add or confirm history tracking for `image_regions`
- [x] Keep placement history intact and visible for later work
- [x] Ensure claim records capture attribution and timestamps
- [x] Ensure image/source provenance can be surfaced without custom parsing

### 6. Response Shape Cleanup

- [x] Standardize API envelopes where needed
- [x] Ensure all core workbench endpoints return stable display-ready fields
- [x] Reduce frontend need for special-case joins

## Workstream 2: Frontend

### 1. New Workbench Shell

- [x] Create a new workbench entry point
- [x] Do not extend the legacy `frontend.html` as the long-term shell
- [x] Implement the basic layout:
  - library panel
  - canvas panel
  - inspector panel
- [x] Add top-level workbench state:
  - current image
  - current region
  - inspector mode
  - active filters

### 2. Image Library

- [x] Build image result list
- [x] Support search and basic filters
- [x] Show useful metadata in result rows:
  - title
  - source
  - image type
  - date
  - region count
- [x] Add good loading / empty / error states

### 3. Image Canvas

- [x] Render selected image
- [x] Add zoom and pan
- [x] Add fit and reset controls
- [x] Render existing regions
- [x] Make selection visually clear
- [x] Ensure image remains the center of attention

### 4. Region Interaction

- [x] Select region from canvas
- [x] Create point region
- [x] Create box region
- [x] Edit region label/notes if needed
- [x] Delete region safely
- [x] Visually distinguish:
  - selected region
  - unlinked region
  - linked region

### 5. Inspector

- [x] Implement image inspector mode
- [x] Implement region inspector mode
- [x] Keep the section structure stable:
  - overview
  - provenance
  - links
  - claims
  - history
  - notes
- [x] Avoid modal-heavy flows where inspector interaction works better

### 6. Entity Linking Flow

- [x] Add `Link entity` action in region inspector
- [x] Build searchable entity picker
- [x] Allow filtering by entity type
- [x] Display selected linked entity as a proper card
- [x] Support replace and unlink actions

### 7. Claim Draft Flow

- [x] Add `Create claim` from selected region
- [x] Build claim draft form in inspector
- [x] Prefill region/evidence context
- [x] Support at least simple templates:
  - region depicts part
  - region depicts kit
  - region supports placement
- [x] After save, show claims as cards in region inspector

### 8. State And Navigation Rules

- [x] Keep library selection, canvas selection, and inspector mode synchronized
- [x] Make it obvious what is currently selected
- [x] Preserve context after save where possible
- [x] Avoid page-jump behavior for region actions

## Workstream 3: Data Preparation

### 1. Seed Images

- [x] Ensure a useful initial image corpus exists in DB
- [x] Prefer images with real provenance and stable metadata
- [x] Ensure titles are readable and not filename junk

### 2. Seed Sources

- [x] Ensure image records point to usable `source` or `source_id`
- [x] Normalize major source types:
  - forum thread
  - auction
  - slide deck
  - article
  - interview

### 3. Seed Regions

- [x] Reuse existing imported PPTX regions where appropriate
- [x] Confirm imported regions display correctly in the future workbench
- [x] Separate overlay-derived regions from hand-reviewed regions if useful

### 4. Seed Entity Targets

- [x] Ensure `kits` are searchable and display cleanly
- [x] Ensure `parts` have stable labels
- [x] Ensure `placements` have useful titles/subtitles for picker use
- [x] Keep categories available for filtering later

### 5. Claim Test Data

- [x] Create a small starter set of claims for UX validation
- [x] Include:
  - one clean agreed identification
  - one unlinked region
  - one region with multiple competing claims

## Workstream 4: UX Validation

### 1. Test The Core Happy Path

- [x] Open image
- [x] create region
- [x] link entity
- [x] create claim
- [x] reload and verify persistence

### 2. Test Empty States

- [x] image with no regions
- [x] region with no linked entity
- [x] region with no claims

### 3. Test Conflict Cases

- [x] multiple claims on one region
- [x] low-confidence claim
- [x] relinked region

### 4. Test Research Readability

- [x] can a user understand provenance quickly?
- [x] can a user distinguish evidence from interpretation?
- [x] can a user tell what is selected?

## Build Order

### Step 1: Shell

- [x] new workbench shell
- [x] library/canvas/inspector layout

### Step 2: Images

- [x] image library
- [x] image inspector
- [x] image canvas display

### Step 3: Regions

- [x] load regions
- [x] select regions
- [x] create/edit/delete point and box regions

### Step 4: Linking

- [x] entity search endpoint
- [x] entity picker UI
- [x] region-to-entity linking

### Step 5: Claims

- [x] claims schema
- [x] claims API
- [x] claim draft UI
- [x] claim card display

### Step 6: Review Pass

- [x] provenance visibility
- [x] history visibility
- [x] empty states
- [x] workflow friction cleanup

## What Not To Do In Phase 1

- [ ] do not rebuild the whole public site
- [ ] do not redesign graph and timeline at the same time
- [ ] do not over-expand into physical object tools yet
- [ ] do not fold transcript annotation into the first slice
- [ ] do not spend major effort beautifying legacy UI surfaces

## Recommended Immediate Next Task

Phase 1 is complete enough to use.

Before widening scope further, the next pass should be a stabilization pass focused on consolidation:

- freeze legacy UI surfaces
- extract shared frontend request/auth/config code
- clean up schema evolution workflow
- add repo hygiene and repeatable verification

After that, continue with browse speed, canvas ergonomics, and direct access to kits.

Clarification:

- the stabilization pass does not require proactive cleanup of legacy HTML surfaces
- legacy files can stay untouched unless there is a concrete bug fix, migration step, or compatibility reason

## Next Pass Priorities

### Priority 0: Stabilization Pass

- [ ] treat `frontend.html` and older one-off tools as maintenance-only rather than active growth surfaces
- [ ] do not proactively refactor legacy surfaces unless a concrete need appears
- [ ] keep `workbench.html` and `map_workbench.html` as the main active operator shells
- [ ] extract one shared frontend API/auth/config layer for workbench surfaces
- [ ] stop mixing query-param auth and header auth across tools
- [ ] choose one schema evolution path:
  - `schema.sql` + ordered migrations as the source of truth
  - runtime schema patching only as a compatibility bridge while transitioning
- [ ] add `.gitignore` coverage for:
  - live DB files
  - DB backups
  - uploads
  - `__pycache__`
  - editor state
  - generated bulk outputs
- [ ] add one repeatable local verification command or script that runs:
  - Python compile checks
  - core smoke tests
- [ ] add at least one more smoke test around image/region/claim workflows
- [ ] decide whether `physical_objects`, `locations`, and `events` are:
  - active next-phase implementation work
  - or explicitly deferred to avoid half-adopted architecture

Stabilization exit criteria:

- new workflow work lands in the active workbench surfaces rather than the legacy HTML shells
- legacy surfaces remain untouched unless there was a specific bug or migration reason to change them
- frontend infrastructure is shared instead of reimplemented
- schema changes have one visible path
- local verification is cheap enough to run constantly

### Pass 1: Faster Image Browsing

- add keyboard navigation:
  - `up/down` moves through the image list
  - `left/right` moves previous / next image
- add optional previous / next active areas on the canvas edges
- add a quick gallery or filmstrip for rapid image scanning
- keep the active image visible in the list while navigating

### Pass 2: Better Canvas Ergonomics

- zoom should anchor to cursor or viewport center, not the image top-left
- canvas controls should remain accessible while the image stays in the visible work area
- panning should feel solid in both axes and not fight selection / box creation
- preserve zoom and scroll position when staying on the same image

### Pass 3: Smarter Library Titles

- shorten primary list-facing image names for quick scanning
- keep ambiguous or longer research wording in secondary metadata or inspector detail
- separate `display title` from fuller research title if needed

### Pass 4: Kit Access And Suggestions

- surface direct kit suggestions when region labels exactly match or strongly suggest a kit
- add a lightweight kit browser so kit exploration is not only possible from region selection
- keep region-driven linking, but do not make it the only path into kit data

### Pass 5: Batch And Expert Workflow

- add batch actions for overlay-derived regions:
  - accept exact kit links
  - mark as needs review
  - hide imported labels
- reduce redundant round-trips when linking multiple nearby regions
- make repeated inspector actions cheap enough for expert use
