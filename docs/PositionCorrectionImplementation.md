# Position Correction Implementation

## Purpose

This is the next concrete structural step after the image workbench and image-group workflow.

The goal is to move from:

- `placement` as a conceptual link between part/kit and model/map

to:

- `placement` plus a real editable geometry/history layer

without destroying imported coordinates or confusing conceptual identity with drawn map position.

## Current State

What already exists:

- `placements` in [backend/schema.sql](../backend/schema.sql)
- `maps`
- image evidence linking to `placement`
- claim formation on top of image regions

What is missing:

- a dedicated position record layer
- imported vs manual vs candidate position history
- a correction workflow that does not overwrite imported geometry
- a dedicated map/location surface
- a first-class `location` entity later

## Design Principle

Keep these separate:

- `placement`
  what is present on the model

- `map`
  one concrete image-backed map surface used for work

- `position`
  where that placement is drawn on one specific map surface

- `location`
  a later canonical named area or location concept that can survive map replacement

Do not collapse them into one row.

## Terminology Note

For now, the backend/data model may keep using `placement` because that is already established in
the schema and API.

But in the user-facing map workbench, clearer language is likely:

- `object`
  the thing being tracked
- `position`
  where that object is drawn on one specific map

Reason:

- `placement` sounds like the thing already has a location
- `object` + `position` reads more naturally during map-side creation and editing

So the recommended direction is:

- keep backend naming stable for now
- evolve the UI language first
- only consider schema renaming later if the concept fully settles

## Map Model Clarification

For this project, the cleanest working rule is:

- one map record = one concrete image-backed working surface

That means:

- a forum-published map image is one map
- a revised redraw is another map
- an annotated overlay export is another map if it is used as an actual working surface

What we should avoid is a vague abstract `map` concept with no concrete image behind it.

That creates clutter and makes geometry hard to reason about.

So the practical model is:

- `placement` stays stable
- `map` is replaceable
- `placement_position` belongs to one map
- `location` later can outlive any individual map image

## Minimum Recommended Schema

Add a new table:

- `placement_positions`

Suggested fields:

- `id`
- `placement_id`
- `map_id`
- `position_type`
- `x_norm`
- `y_norm`
- `width_norm`
- `height_norm`
- `polygon_json`
- `source_kind`
- `status`
- `is_current`
- `supersedes_id`
- `confidence`
- `notes`
- `attributed_to`
- `created_at`

Suggested semantics:

- `placement_id`
  the conceptual placement this position belongs to

- `map_id`
  the map revision or map image this geometry is drawn on

- `position_type`
  `point`, `box`, `polygon`

- `source_kind`
  `imported`, `manual`, `candidate`, `derived`

- `status`
  `active`, `superseded`, `rejected`

- `is_current`
  whether this is the currently preferred position for that placement on that map

- `supersedes_id`
  if a manual correction replaces an imported record, preserve the chain

- `confidence`
  `confirmed`, `probable`, `speculative`

## Why This Layer Matters

It solves the current modeling problem cleanly:

- imported geometry can remain preserved
- manual correction becomes additive, not destructive
- multiple candidate positions can coexist
- provenance and disagreement remain visible
- map correction can become a real workflow instead of a hidden edit
- map images can be replaced later without destroying placement identity

## Recommended API Shape

Add:

- `GET /api/placement_positions?placement_id=&map_id=&status=`
- `GET /api/placement_positions/<id>`
- `POST /api/placement_positions`
- `PUT /api/placement_positions/<id>`
- `DELETE /api/placement_positions/<id>`

Useful companion behavior:

- `GET /api/placements/<id>` should include positions grouped by map
- `GET /api/maps/<id>` later should include active placement positions for fast map rendering

## Creation Rules

Recommended behavior:

- imported loader creates `source_kind=imported`, `status=active`, `is_current=1`
- manual correction creates a new row:
  - `source_kind=manual`
  - `status=active`
  - `is_current=1`
  - `supersedes_id=<old_position_id>`
- previous current row becomes:
  - `status=superseded`
  - `is_current=0`

Candidate behavior:

- candidate positions may exist with:
  - `source_kind=candidate`
  - `status=active`
  - `is_current=0`

This keeps uncertainty visible without making the map unreadable.

## First UI Surface

This should not be forced into the image workbench.

Build a dedicated map workbench with the same shell grammar:

- left: map / placement library
- center: map canvas
- right: inspector

The first map correction slice should support:

- open one map
- show active positions
- select a placement
- inspect current and superseded positions
- create a manual correction
- mark a position as current
- remove only a manual/candidate position

## Inspector Model

The placement inspector should show:

- placement identity
- linked kit / part / model
- map name
- current active position
- previous imported/manual chain
- linked image evidence
- linked claims

This is where image and map workflows start to connect properly.

## What Not To Build Yet

Do not add yet:

- full canonical `location` entity editing
- object lineage/state modeling
- automatic geometric propagation across map revisions
- image-family alignment transforms

Those are good later layers, but not required for the first correction workflow.

## Immediate Implementation Order

1. Add `placement_positions` schema and migration support.
2. Add CRUD endpoints for position records.
3. Return active/current position summaries in placement responses.
4. Build a minimal map correction surface.
5. Add reverse lookup from placement to linked images and claims in that surface.

## Map Replacement Behavior

Replacing a map should be simple:

- keep the `placement`
- keep the later `location` concept
- keep old `placement_positions` on the old map as history
- create new `placement_positions` for the new map image

What should not be assumed:

- exact coordinates automatically carry over across map replacements

What should carry over:

- placement identity
- linked kit / part / cast assembly
- claims
- provenance

So replacement is safe as long as geometry is attached to a map-specific position layer instead of being stored as a permanent property of the placement row.

## Relationship To Later Work

After this layer exists, the next natural additions become much cleaner:

- canonical `location` entities
- object / physical miniature entities
- object states over time
- map-to-image cross-evidence workflows
- aligned variant layers for cropped map or overlay images

## In One Sentence

The next serious step is to treat placement geometry as its own versioned evidence layer rather than as a destructive property of the placement row itself.
