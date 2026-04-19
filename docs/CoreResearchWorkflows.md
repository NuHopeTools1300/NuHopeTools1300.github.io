# Core Research Workflows

## Purpose

This document reframes NuHopeTools around research workflows rather than around legacy tools.

That is the right level of thinking now.

We are not really rebuilding:

- `ImageAnnotator.html`
- `frontend.html`
- timeline pages

We are rebuilding the workflows those tools only partially supported.

The practical question should no longer be:

> "How do we redesign the annotator?"

It should be:

> "What are the core research workflows, and what surfaces do they need?"

## Product Thesis

NuHopeTools is a research workbench for miniature archaeology.

Its job is to let a researcher move from:

- raw evidence
- to structured observation
- to linked entity
- to explicit interpretation
- without losing provenance, uncertainty, or revision history

That work happens through a small number of recurring workflows.

Those workflows, not the old tools, should define the product.

## Workflow Inventory

There are seven core workflows that matter most right now.

These are not strictly one-way pipelines.

The product must support both:

- `evidence-first` work, where the user starts from an image, source, or extract
- `entity-first` work, where the user starts from a kit, part, placement, map area, or object and asks where else it appears

That second direction is just as important.

Many serious research questions sound like:

- `I have this kit. Where is it visible in images?`
- `I have this placement or map area. What other images show it?`
- `What other objects or models link to this area?`
- `What other evidence supports or contests this identification?`

So every major workflow should be thought of as reversible where possible.

### 1. Image Intake And Grouping

Goal:

- bring images into the system
- classify them
- deduplicate them
- group them into logical image families
- choose a primary image
- keep useful variants attached

Typical inputs:

- PPTX extracts
- local archive folders
- auction images
- forum-saved images
- scans
- derived overlays

Typical outputs:

- image records
- source linkage
- image family
- duplicate/detail/crop classification
- primary image assignment
- editable image record metadata:
  - title
  - code
  - type
  - date
  - source label
  - notes
- explicit disposition state for each image:
  - keep as active evidence
  - hide behind a family
  - detach from family
  - delete the image record entirely when appropriate

Why it matters:

- otherwise every later workflow starts in noise

Main UI needs:

- intake/review queue
- family manager
- duplicate resolution tools
- source/provenance editor
- safe destructive-action design so `remove from family` and `delete image` are clearly separated
- explicit image lifecycle controls:
  - add image
  - edit image record
  - delete image
- simple user-facing language that keeps the concept clear:
  - `Image group`
  - `Default image in list`
  - `Images in group`

### 2. Image Evidence Inspection

Goal:

- open a logical image
- inspect it on a stable canvas
- compare variants within that image family
- review existing regions, links, and claims

Typical outputs:

- understanding of what evidence already exists
- decision to annotate, compare, relink, or claim
- extracted visible text when relevant
- candidate entity matches derived from that text

Why it matters:

- this is the everyday reading workflow

Main UI needs:

- library row per image family
- canvas with primary image
- filmstrip for variants
- inspector with provenance, links, claims, history
- support for map-style images where the text printed on the image itself is part of the evidence
- OCR later for images where labels are visible but not yet structured

### 3. Annotation And Geometry Correction

Goal:

- create or refine `image_regions`
- correct imported region positions when needed
- preserve manual corrections without losing the import trail

Typical outputs:

- new region
- revised region
- better geometry
- history of adjustment

Why it matters:

- evidence is rarely ready-made

Main UI needs:

- direct region editing on canvas
- point/box/polygon tools later
- save-as-correction behavior
- visible imported vs manual geometry provenance

### 4. Entity Linking

Goal:

- connect an evidence unit to the most relevant entity

Typical targets:

- `kit`
- `part`
- `cast_assembly`
- `placement`
- `model`
- later `location`, `physical_object`, `event`

Typical outputs:

- explicit evidence-to-entity relationship
- searchable connection for later review
- quick `label -> kit` linking for map-style images when visible text strongly matches DB records

Why it matters:

- this is the bridge from observation to structure

Main UI needs:

- fast entity picker
- direct kit suggestions from labels
- batch matching from region labels to kits for images that already carry structured label regions
- browse-from-entity entry points
- reversible linking

Reverse lookup needs:

- from any entity, show linked images
- from any entity, show linked regions
- from any entity, show related claims
- from any entity, show neighboring related entities

### 5. Claim Formation And Review

Goal:

- turn linked evidence into an explicit interpretation
- preserve confidence, attribution, and rationale
- allow competing claims

Typical outputs:

- `claim`
- claim evidence links
- contested or confirmed interpretations

Why it matters:

- without claims, conclusions stay hidden in notes

Main UI needs:

- lightweight claim drafting
- readable claim cards
- confidence/status display
- multi-claim comparison on the same evidence

### 6. Spatial Placement And Location Correction

Goal:

- place identified parts or objects on maps
- correct imported positions
- distinguish conceptual placement from geometric position
- prefer clearer user-facing map-workbench language like `object` + `position`
  - keep `placement` as the backend/data-model term for now

Typical outputs:

- placement records
- canonical locations later
- imported vs manual position records

Why it matters:

- map work is one of the strongest differentiators of the project

Main UI needs:

- map canvas
- placement inspector
- position history
- override/correction workflow
- explicit separation of conceptual `placement` from editable geometric `position`
- treat each working `map` as one concrete image-backed surface, not as a vague abstract placeholder

Reverse lookup needs:

- start from a map or location
- find all linked placements
- find all linked image regions
- find all linked claims and evidence extracts

Implementation note:

- See [PositionCorrectionImplementation.md](./PositionCorrectionImplementation.md) for the minimum schema/API/surface proposal for this workflow.

### 7. Source Extraction And Evidence Mining

Goal:

- move from forum posts, transcripts, auctions, and articles into structured evidence

Typical outputs:

- source records
- source extracts
- quotes linked to images, placements, objects, or events
- OCR-assisted text extraction from images later, when useful text is visible but not already present as structured labels

Why it matters:

- text research is too important to remain outside the system

Main UI needs:

- source browser
- extract review interface
- quote-to-entity linking
- provenance-first display

## Secondary Workflows

These are strong, but not the first foundation layer.

### 8. Comparison And Review

- compare image variants
- compare two candidate claims
- compare two object states
- compare map interpretations

### 9. Timeline And Event Construction

- build dated events
- connect objects, images, and extracts to chronology

### 10. Cross-Model Exploration

- start from a kit or part
- see all placements, images, and claims across models

## Workflow Dependencies

Not all workflows should be built at once.

The real dependency chain is:

1. image intake and grouping
2. image evidence inspection
3. annotation and geometry correction
4. entity linking
5. claim formation and review
6. spatial placement and location correction
7. source extraction and evidence mining

That means the current workbench is only one slice of a larger chain.

It is best understood as:

- mostly workflow `2`
- part of workflow `3`
- part of workflow `4`
- part of workflow `5`

It is not the whole product.

## Surface Mapping

This is the most important practical reframing.

### Workbench / Images

Supports:

- image evidence inspection
- annotation and geometry correction
- entity linking
- claim formation

This is where the old annotator gets absorbed.

### Workbench / Maps

Supports:

- spatial placement
- location correction
- map-specific evidence review

This should not be forced into the image workbench.

### Workbench / Sources

Supports:

- source browsing
- extract mining
- quote linking
- provenance review

### Workbench / Timeline

Supports:

- event building
- chronology review
- object state sequencing

### Entity Workbench

Supports:

- kit/part/placement/object inspection
- cross-linked evidence review
- relationship browsing

This surface is where the reverse direction becomes first-class.

Typical starting points:

- `show me every image that supports this kit`
- `show me all placements linked to this location`
- `show me all evidence touching this object lineage`

It should not feel secondary or bolted on.

## What This Means For The Old Annotator

The old annotator was not wrong.

It was just too narrow as a product frame.

What it really provided was:

- region drawing
- region editing
- local object marking

Those capabilities still matter.

But they belong inside:

- annotation and geometry correction

They do not define the whole workbench.

So the right question is not:

- "Do we rebuild the annotator?"

It is:

- "Which workflows need direct geometry editing, and how should that feel inside the workbench?"

## Immediate Product Consequences

### Consequence 1

The image workbench should not be designed as a general-purpose replacement for every future surface.

It should be optimized for:

- image-family browsing
- inspection
- annotation
- linking
- claims

### Consequence 2

Map correction should become its own workflow and likely its own canvas, even if it shares shell, inspector grammar, and entity logic.

### Consequence 3

Image families are not just a media-management feature.

They are part of workflow `1`, which sits upstream of nearly everything else.

### Consequence 4

Manual geometry correction should be treated as a normal workflow step, not as an exceptional admin action.

### Consequence 5

Any new UI decision should now be tested against:

- which workflow does this belong to?
- what is the real user goal in that workflow?
- is this a primary canvas action, a library action, or an inspector action?

### Consequence 6

Every important object should support both directions:

- `from evidence to entity`
- `from entity back out to evidence`

If a surface only supports one direction, it is probably incomplete.

## Recommended Build Focus Now

The next build phase should not try to expand the image workbench in every direction.

It should tighten the workflow sequence:

1. finish workflow `1` enough to handle image families well
2. keep improving workflows `2-5` in the image workbench
3. then start workflow `6` as a dedicated map/location surface

That is cleaner than trying to make the image workbench silently absorb map correction and source mining too early.

## In One Sentence

NuHopeTools should be designed as a set of connected research workflows sharing one shell and one object model, not as a collection of redesigned legacy tools.

Companion plain-language reference:

- See [WorkflowPivotTable.md](./WorkflowPivotTable.md)
- See [WorkflowSystemMap.md](./WorkflowSystemMap.md)
