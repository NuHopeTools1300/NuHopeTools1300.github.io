# Product UI Architecture

## Purpose

This document defines the target product shell for NuHopeTools as it grows from a set of historically-grown research utilities into a coherent evidence-backed research workstation.

It is not a visual polish brief.

It is a structural decision about:

- what the product fundamentally is
- how users move through it
- how research entities are presented
- how evidence turns into interpretation
- which current tools should be preserved, absorbed, or retired

Companion workflow reference:

- See [CoreResearchWorkflows.md](./CoreResearchWorkflows.md)
- See [WorkflowPivotTable.md](./WorkflowPivotTable.md) for the same workflow model expressed from the user's starting questions
- See [WorkflowSystemMap.md](./WorkflowSystemMap.md) for the compact visual-text system sketch

## Current Reality

The current UI layer is fragmented by history, not by design.

What exists today:

- a kit/placement browser in `frontend.html`
- a standalone `ImageAnnotator`
- standalone timeline views
- separate research HTML artifacts
- several one-off operators for import, extraction, and inspection

This is useful for private work, but it is not a sustainable product surface.

Problems:

- different tools use different interaction models
- object identity is inconsistent across surfaces
- evidence and interpretation are often mixed in the same panel
- too much local tool state leaks into the user experience
- users must mentally translate between kits, parts, placements, images, locations, and claims
- adding features to the current UI tends to increase entropy rather than reduce it

Conclusion:

The current UI should be treated as temporary operator tooling, not the foundation of the long-term product.

The same is true conceptually:

- current tools should be treated as partial workflow supports, not as the conceptual structure of the product

Immediate implementation implication:

- freeze the legacy surfaces instead of continuing to widen them
- extract shared frontend infrastructure rather than re-solving API/auth/state per HTML file
- stop allowing schema and product concepts to drift across runtime bootstrap, draft migrations, and docs
- prefer consolidation passes when entropy starts rising faster than capability

For the current stabilization phase, "freeze" does not mean "clean up all old files now."

- legacy surfaces do not need proactive refactoring just to make them prettier or more consistent
- leave them alone unless a concrete bug, migration need, or compatibility requirement makes a touch necessary

This is how the project keeps the current prototype energy without letting the temporary layer become the accidental architecture.

## Product Thesis

NuHopeTools should become a research workstation for miniature archaeology.

The product is not "a database page plus some tools".

It is a single environment for:

- collecting evidence
- annotating and linking evidence
- comparing candidate interpretations
- preserving provenance
- moving from raw material to structured claims

The product should feel like one system with multiple canvases, not a bag of separate mini-apps.

## Core Interaction Model

The base shell should be:

- `Library`
- `Canvas`
- `Inspector`

### Library

The library is where users browse, search, filter, queue, and compare.

Typical content:

- images
- sources
- extracts
- kits
- parts
- placements
- locations
- physical objects
- events
- claims

The library is not just a left nav. It is a first-class working surface.

### Canvas

The canvas is where the primary evidence or spatial/temporal material is viewed.

Examples:

- image canvas
- map canvas
- timeline canvas
- transcript canvas
- graph canvas

The canvas is the main reading/inspection surface.

### Inspector

The inspector is the structured side panel for the selected thing.

Typical inspector sections:

- summary
- provenance
- linked entities
- evidence
- claims
- history
- notes

The inspector should be consistent across canvases.

But consistency should not mean pushing every edit action into the far-right panel.

For object-focused workflows, the better split is often:

- left: list plus compact selected-object controls
- center: canvas
- right: deeper detail, provenance, history, linked evidence, and advanced metadata

That keeps high-frequency editing close to the thing the user just selected instead of forcing a
wide left/right mental jump.

## Core Object Model

The UI should revolve around a stable set of entity types.

### Evidence Objects

- `source`
- `source_extract`
- `image`
- `image_region`

### Reference Objects

- `kit`
- `part`
- `cast_assembly`
- `model`
- `map`
- `location`

### Physical Objects

- `physical_object`
- `object_state`

### Interpretation Objects

- `placement`
- `claim`
- `event`

Every surface should use these same objects, labels, badges, and relationship semantics.

## Core User Modes

The product should support four main modes.

### Browse

Find things, filter them, sort them, compare them.

### Inspect

Read a selected thing in detail and understand its links and provenance.

### Annotate

Create regions, notes, links, and candidate identifications on evidence.

### Relate

Connect entities to each other and move evidence into structured interpretation.

These modes should exist everywhere, even if the active canvas differs.

They should be understood as cross-cutting modes layered across the concrete research workflows described in [CoreResearchWorkflows.md](./CoreResearchWorkflows.md), not as standalone tool silos.

## Design Principles

### 1. Evidence First

The UI should always make it clear what the evidence is and what the interpretation is.

Bad:

- a freeform note that silently behaves like a fact

Good:

- a source extract
- an image region
- a claim attached to those records

### 2. Provenance Visible Everywhere

Every important view should surface:

- source
- attribution
- confidence
- status
- history

Users should never have to guess where a statement came from.

### 3. One Thing, One Identity

A kit, image, placement, or claim should present consistently everywhere.

That means:

- same title logic
- same badges
- same provenance treatment
- same related-object sections

### 4. Spatial And Temporal Work Should Feel Native

Images, maps, and timelines are not extras. They are primary canvases for this domain.

The shell should support them directly instead of treating them as bolt-on tools.

### 5. Operator Power Without UI Chaos

Advanced researcher actions matter, but they should live in the inspector or structured action menus, not in scattered one-off controls.

## Shared UI Grammar

The future design system should standardize:

- page shell
- panel spacing
- inspector sections
- chips and badges
- confidence styling
- provenance rows
- linked-entity lists
- action bars
- filter controls
- empty/loading/error states

### Standard Badges

- confidence
- provenance/source type
- attribution
- category
- object state
- review status

### Standard Cards

- evidence card
- entity card
- claim card
- event card

### Standard Inspector Sections

- `Overview`
- `Evidence`
- `Links`
- `Claims`
- `History`
- `Notes`

## Recommended Navigation Model

Top-level navigation should be domain-oriented, not tool-oriented.

Recommended sections:

- `Workbench`
- `Evidence`
- `Entities`
- `Timeline`
- `Graph`
- `Admin`

### Workbench

The default working environment.

This is where the `library / canvas / inspector` shell lives.

Refinement:

- primary editing should stay near the selection source where possible
- the far-right inspector should hold secondary detail rather than all working controls by default

### Evidence

Focused entry points for:

- images
- sources
- extracts
- image regions

### Entities

Focused entry points for:

- kits
- parts
- placements
- locations
- physical objects
- claims

### Timeline

Chronology workspace for:

- events
- object states
- production windows
- filming windows

### Graph

Cross-model relationship exploration.

### Admin

Imports, audits, taxonomy, merge tools, data maintenance.

## Current Tool Disposition

### `frontend.html`

Status:

- keep as temporary operator UI
- do not invest in major visual cleanup
- only fix workflows or data bugs that block research

Long-term:

- replaced by the new workbench shell

### `ImageAnnotator.html`

Status:

- keep as a functional prototype for region workflows
- continue bridging it to backend data only where that directly helps research

Long-term:

- absorbed into the workbench as the image canvas

### Timeline HTML prototypes

Status:

- useful as research outputs
- not a sustainable application surface

Long-term:

- absorbed into a timeline canvas inside the workbench

### Research HTML artifacts

Status:

- keep as generated research deliverables

Long-term:

- coexist with the product, but not define it

## First Real Product Slice

The first rebuilt vertical slice should be:

- `image -> region -> entity -> claim`

Why:

- strongest bridge between current work and future platform
- evidence-rich
- visually concrete
- already partially supported by schema and annotator work
- forces the shell, inspector, provenance model, and linking model to be designed properly

### Slice Requirements

- library view of images
- image canvas with regions
- inspector for selected image or region
- linked entity picker
- claim creation from region evidence
- provenance and confidence display

Detailed first-slice specification:

- See [WorkbenchSlice_ImageRegionClaim.md](./WorkbenchSlice_ImageRegionClaim.md)
- See [Phase1BuildChecklist.md](./Phase1BuildChecklist.md)
- See [ImageFamiliesAndPositionCorrection.md](./ImageFamiliesAndPositionCorrection.md) for the next structural extension around duplicate/crop image families and editable position correction

If this slice feels coherent, the rest of the product has a real foundation.

## Rebuild Sequence

### Phase A: Define The Shell

- page shell
- navigation
- panel system
- inspector patterns
- shared badges and cards

### Phase B: Build The First Slice

- image library
- image canvas
- region inspector
- claim workflow

### Phase C: Expand To Locations And Maps

- map canvas
- canonical locations
- placement/location inspection

### Phase D: Add Timeline

- event library
- event inspector
- timeline canvas
- object state chronology

### Phase E: Add Graph

- model-kit-part-claim graph views
- cross-model exploration

## What To Avoid

- polishing the legacy UI into permanence
- rebuilding screen by screen without a shell
- mixing evidence and claims into one generic note field
- inventing different interaction patterns for each object type
- overfitting the UI to the current private workflow alone
- treating images, timelines, and maps as separate apps

## Design Suggestions For Visual Direction

The visual language should feel archival, technical, and cinematic without becoming themed novelty UI.

Recommended direction:

- restrained dark-ink-on-warm-surface palette or warm-dark archival palette
- clear separation between neutral structure and highlighted evidence state
- typography that supports dense research reading rather than marketing flair
- visual hierarchy built from panels, chips, and metadata rows
- occasional accent colors reserved for confidence, provenance, and selection

Avoid:

- toy sci-fi styling
- franchise cosplay UI
- dashboard gloss
- decorative "Star Wars" skins

The product should feel like a serious research instrument.

Interaction and screen-structure guidance:

- See [UIPrinciples.md](./UIPrinciples.md)
- See [Wireframes_ImageWorkbench.md](./Wireframes_ImageWorkbench.md)

## Success Criteria

The redesign is working if:

- a user can move from raw image to structured claim without confusion
- provenance is always visible
- all major objects feel like members of one system
- adding a new domain object does not require inventing a new UI language
- evidence, interpretation, and chronology reinforce each other instead of fragmenting

## Working Rule

Do not spend major effort beautifying the current fragmented UI.

Use the current tools to keep research moving.

Put real design effort into the replacement shell and the first coherent vertical slice.
