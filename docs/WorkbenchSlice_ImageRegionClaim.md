# Workbench Slice: Image -> Region -> Entity -> Claim

## Purpose

This document specifies the first real rebuilt product slice for NuHopeTools.

It takes the high-level direction from [ProductUIArchitecture.md](./ProductUIArchitecture.md) and turns it into a buildable interaction spec.

Companion references:

- [UIPrinciples.md](./UIPrinciples.md)
- [Wireframes_ImageWorkbench.md](./Wireframes_ImageWorkbench.md)
- [CoreResearchWorkflows.md](./CoreResearchWorkflows.md)

The slice is:

- `image -> region -> entity -> claim`

This is the first end-to-end workflow where a user should be able to:

1. find an image
2. inspect it on a proper canvas
3. select or create a region
4. connect that region to a real entity
5. promote that evidence into a structured claim

Within the larger workflow model, this slice primarily serves:

- `Image evidence inspection`
- `Annotation and geometry correction`
- `Entity linking`
- `Claim formation and review`

It is not intended to cover the full product by itself.

## Why This Slice First

This slice is the right place to begin because it exercises the core product idea:

- evidence is first-class
- provenance stays visible
- annotation becomes structured data
- interpretation grows out of evidence, not freeform notes

It also fits the current data model best:

- `images`
- `sources`
- `source_extracts`
- `image_regions`
- linked entities such as `kits`, `parts`, `placements`

And it directly absorbs the strongest current prototype:

- `tools/ImageAnnotator.html`

## User Goal

The primary user goal is:

> "I have a reference image. I want to mark a specific visible area, link it to the most relevant research object, and record what I think it shows without losing where that idea came from."

## Primary Personas

### Research Operator

Deeply familiar with the subject matter. Wants speed, density, and low-friction linking.

### Reviewer

Less concerned with annotation speed. More concerned with checking provenance, confidence, and whether a claim is justified.

### Explorer

Browsing existing evidence to understand what is already known.

## Page Type

This slice should live in the future `Workbench`, not as a standalone tool.

Recommended route concept:

- `/workbench/images`
- optionally `/workbench/images/:id`

## Overall Layout

Use the standard shell:

- `Library`
- `Canvas`
- `Inspector`

### Left: Library

Purpose:

- search and filter images
- browse image results
- switch current image
- save short working queues

### Center: Canvas

Purpose:

- display the selected image
- show regions
- create/select/edit regions

### Right: Inspector

Purpose:

- inspect selected image or selected region
- view provenance and linked entities
- create or review claims

## Information Hierarchy

### Default Selection State

When an image is selected but no region is selected:

- the canvas centers on the image
- all visible regions are shown
- the inspector shows image-level information

### Region Selection State

When a region is selected:

- the canvas highlights that region
- other regions remain visible but secondary
- the inspector switches to region detail

### Claim Draft State

When creating a claim from a region:

- the region stays selected
- the inspector enters claim-draft mode
- evidence context stays visible above the claim form

## Library Specification

### Library Header

Contains:

- query input
- source filter
- image type filter
- tags filter
- "only with regions" toggle
- "only linked" toggle

Short-term additions:

- quick gallery / filmstrip toggle
- current-image navigation affordances

### Result Rows

Each image row should show:

- short display title
- image code
- source badge
- image type badge
- date if known
- region count
- claim count
- linked entity count

Rule:

- optimize the first line for fast scanning
- move fuller or more speculative wording into subtitle or inspector detail

### Result Grouping

Useful grouping options:

- by source
- by image type
- by related model
- by ingest batch

### Library Actions

At minimum:

- open image
- previous / next image
- open in new compare slot later
- quick flag
- add to work queue

Near-term additions:

- keyboard navigation between images
- quick browse gallery / filmstrip

## Canvas Specification

### Core Canvas Behavior

The canvas should support:

- zoom
- pan
- fit-to-screen
- 1:1 zoom
- region visibility toggles
- region hover
- region selection

Interaction requirements:

- zoom should anchor to cursor or viewport center
- the visible image area should remain inside the usable work area
- panning must behave well in both axes

### Region Display

Each region should visually encode:

- selection state
- linked / unlinked state
- claim count
- confidence or review status if available

Suggested rules:

- selected region gets strong outline
- unlinked region gets neutral warning style
- linked region gets entity-colored accent
- contested region gets striped or mixed-state marker

### Region Creation

Supported region types in the first slice:

- point
- box

Polygon can stay phase-two if needed.

### Canvas Action Bar

Recommended actions:

- select
- pan
- add point
- add box
- hide/show all regions
- filter visible regions by entity type
- create claim from selected region

Immediate usability corrections for this slice:

- previous / next image via keyboard and optional edge-click zones
- quick gallery / filmstrip for visual scanning
- calmer default region labeling
- more direct kit access from the same workbench

## Inspector Specification

The inspector has two primary modes.

### Image Inspector

Sections:

- `Overview`
- `Provenance`
- `Regions`
- `Linked entities`
- `Claims using this image`
- `Notes`

#### Overview

Show:

- title
- image code
- image type
- dimensions
- date

#### Provenance

Show:

- source record
- source type
- source date
- attribution
- storage kind

If a source extract is linked later, it should be surfaced here too.

#### Regions

Show:

- region count
- list of regions
- region status summaries

### Region Inspector

Sections:

- `Overview`
- `Geometry`
- `Linked entity`
- `Evidence`
- `Claims`
- `History`
- `Notes`

#### Overview

Show:

- region label
- region type
- created by
- linked / unlinked state
- claim count

#### Geometry

Show:

- normalized coordinates
- pixel coordinates if known
- image-relative placement

This is mainly for operator trust and debugging.

#### Linked Entity

Show:

- currently linked entity card
- entity type
- entity title
- quick jump to entity detail
- replace / unlink action

#### Evidence

Show:

- source
- related source extract if any
- sibling regions from same image
- other evidence already linked to the same entity

This section is important because it prevents isolated annotation decisions.

#### Claims

Show:

- claims derived from this region
- confidence
- status
- attribution

#### History

Show:

- region edits
- link changes
- claim creation events

## Entity Linking Workflow

### Goal

The user should be able to connect a region to a real entity without navigating away from the canvas.

### Link Flow

1. Select region
2. Click `Link entity`
3. Open structured picker
4. Search by name, code, part number, placement location, or category
5. Choose entity type:
   - `kit`
   - `part`
   - `cast_assembly`
   - `placement`
   - `model`
   - `map`
6. Confirm link

### Picker Requirements

The picker must:

- show entity type
- show title
- show supporting metadata
- show confidence if the entity is itself uncertain
- allow searching across multiple types or within one type

Near-term addition:

- surface exact or strong kit suggestions directly from region labels before generic search results

### Important Rule

Linking a region to an entity is not the same as making a claim.

The UI must make that distinction explicit.

Possible interpretation:

- entity link = "this region is related to this thing"
- claim = "this region depicts this thing in this specific way"

## Claim Creation Workflow

### Goal

Move from linked evidence to structured interpretation.

### Entry Point

The easiest path is:

- selected region
- optional linked entity already chosen
- click `Create claim`

Important boundary:

- claim creation should stay lightweight
- kit browsing should also be possible independently of claim creation or region selection

### Claim Draft Form

Initial claim fields:

- subject
- predicate
- object or text value
- confidence
- status
- rationale
- attribution

### Pre-filled Defaults

If the region is linked to an entity, the form should prefill:

- evidence reference
- probable subject or object
- claim context

### Example Claim Templates

Useful presets:

- `Region depicts part`
- `Region depicts kit`
- `Region supports placement`
- `Region supports location`
- `Region is possible match only`

### Claim Review Mode

After creation, the region inspector should show claims as cards, not raw JSON-like fields.

Each claim card should show:

- main statement
- confidence
- status
- linked evidence
- attribution

## Empty And Edge States

### No Images

The page should explain:

- no image records exist yet
- where to ingest or create them

### Image With No Regions

Canvas shows image only.

Inspector prompts:

- add first point
- add first box

### Region With No Link

Inspector should not feel broken.

It should say:

- this region is unlinked
- you can link it to an entity
- or create a note-only region

### Region With Link But No Claim

This is valid.

Show:

- linked entity
- no claim yet
- create first claim

### Multiple Conflicting Claims

This is a core research case, not an error.

The UI should support:

- several claim cards
- visible disagreement
- per-claim confidence and status

## Compare Support

Not required in the very first build, but the slice should be designed to grow into:

- compare two images
- compare two regions
- compare evidence for the same entity across images

This should influence data structures and state design even if the first shipped version is single-canvas.

## Data Dependencies

### Already Present Or Close

- `images`
- `sources`
- `source_extracts`
- `image_regions`
- entity tables such as `kits`, `parts`, `placements`

### Needed For The Full Slice

- `claims`
- claim-to-evidence linking
- region edit history
- entity search endpoint suitable for picker use

### Nice To Have

- work queues / saved selections
- region review status
- batch operations

## API Needs

### Must Have

- list images with filters
- get image by id
- list regions by image
- create region
- update region
- delete region
- search entities across multiple types
- create claim
- list claims by region

### Recommended Response Shape

The UI will be much easier to build if list endpoints return:

- normalized display title
- badges / summary fields
- counts
- provenance summary

so the frontend does not need to reconstruct identity every time.

## Build Sequence

### Step 1

Create the new workbench shell only.

Deliverables:

- library panel
- image canvas area
- inspector shell

No full claim workflow yet.

### Step 2

Load real images and regions into the shell.

Deliverables:

- image browse
- region display
- region selection

### Step 3

Add region creation/edit.

Deliverables:

- point creation
- box creation
- save/update/delete

### Step 4

Add entity linking.

Deliverables:

- entity picker
- link/unlink
- entity card in inspector

### Step 5

Add claims.

Deliverables:

- create claim
- view claim cards
- support multiple claims per region

## Success Criteria

This slice is successful if a researcher can:

1. locate an image quickly
2. mark the relevant area
3. connect it to a real research object
4. create a claim with visible provenance
5. return later and still understand exactly why that claim exists

## Out Of Scope For Slice One

To keep this slice focused, do not include yet:

- graph exploration
- full timeline editing
- physical object lineage tools
- transcript annotation canvas
- complex moderation workflows
- public-facing visitor UX

Those should come later after the first workbench slice proves the core interaction model.

Implementation checklist:

- See [Phase1BuildChecklist.md](./Phase1BuildChecklist.md)
