# Research Architecture

## Why This Needs A New Layer

The current platform already has a strong donor-part backbone:

- `kits`
- `parts`
- `cast_assemblies`
- `models`
- `maps`
- `placements`
- `images`
- `contributors`

That is enough for "this kit part appears on this model here".

It is not yet enough for the next stage of the project:

- image naming and provenance independent of raw filenames
- forum-post evidence with exact quote or post anchors
- physical miniature lineage separate from the generic model class
- canonical location vocabularies instead of free-text labels
- image-region annotation that can be linked to kits, parts, placements, locations, people, or events
- claim-level research where multiple sources can agree, conflict, or remain unresolved
- a real chronology of build, filming, repaint, transfer, auction, and exhibition events

The current repo is therefore best understood as `phase 1 data spine + tools`, with the next phase becoming an `evidence-backed research platform`.

Current implementation decision:

- `physical_objects`, `locations`, and `events` remain deferred target-shape entities during the current stabilization pass
- the active implementation boundary stays on the existing donor-part backbone plus images, image regions, and claims
- do not treat this document's target schema as an instruction to partially land those entities ahead of a dedicated next-phase start

## The Target Shape

The cleanest model is to separate four layers that currently blur together:

### 1. Reference Layer

These are stable categories and lookup entities.

- `kits`
- `parts`
- `cast_assemblies`
- `models`
- `maps`
- `contributors`

These should remain.

### 2. Physical Layer

This is where actual filmed miniatures, survivor objects, and evolving paint/identity states live.

- `physical_objects`
- `object_states`
- `locations`

Examples:

- One `model` might be `X-Wing`
- A `physical_object` might be `Blue 1 / later Red 2 hero lineage`
- An `object_state` might be `Blue 1 reference state, Dec 1975`
- A `location` might be `starboard upper engine trench`, or `Death Star tile zone 3 upper ridge`

### 3. Evidence Layer

This is the raw or near-raw material that supports research.

- `sources`
- `source_extracts`
- `images`
- `image_regions`
- `evidence_links`

Examples:

- a forum thread transcript
- a single post excerpt from that thread
- a workshop still
- a cropped region on that still
- a link saying that region depicts a specific kit or location

### 4. Interpretation Layer

This is where research assertions and chronology live.

- `placements`
- `claims`
- `events`
- `event_links`

Examples:

- "this region shows an AMT Peterbilt 359"
- "this physical Y-wing object is probably Gold Two"
- "this model state existed by spring 1976"
- "this miniature was filmed during the battle-program photography window"

## Proposed Additions

### Images Need To Become First-Class Records

Raw filenames should stop carrying meaning.

The DB should carry the naming system:

- `images.title`
- `images.image_code`
- `images.caption`
- `images.sha256`
- `images.storage_kind`
- `images.storage_path`
- `images.width`
- `images.height`

Practical effect:

- ugly legacy filenames become harmless
- Drive links, uploads, PPTX extractions, and later ingest batches can coexist
- tools can show human labels while storage stays stable

This still needs one more layer for real-world browsing:

- logical `image families`
- primary image vs duplicate / crop / higher-resolution detail variants
- hidden duplicate handling without deleting provenance

See [ImageFamiliesAndPositionCorrection.md](./ImageFamiliesAndPositionCorrection.md).

### Sources And Extracts

Forum transcripts, auction listings, interviews, magazine scans, and slide decks should all become `sources`.

Then exact post excerpts, quotes, slide notes, or transcript snippets should become `source_extracts`.

This is the missing bridge for text-based research.

It lets us preserve:

- local transcript file path
- post or page anchor
- quote text
- author / handle
- source date

That is much better than burying provenance in freeform notes.

### Physical Objects And States

The current `models` table is too coarse for ANH fighter and Death Star research.

We need to distinguish:

- the canonical subject class: `X-Wing`, `Y-Wing`, `TIE Fighter`
- the physical filmed object: one actual miniature
- the state of that object at a moment in time: paint scheme, role label, damage, rebuild

This is the only clean way to represent:

- `Blue 1 -> Red 2`
- `Red 1 pyro -> Red 3`
- `Red 6 -> Red 10`
- Y-wing survivor identity problems
- Death Star crane vs tile families vs special sections

### Locations As Canonical Spatial Entities

`placements.location_label` is useful, but too loose for serious extraction from text and images.

We need canonical `locations` that can be:

- hierarchical
- attached to a model
- optionally attached to a specific map
- optionally given geometry on a map

Examples:

- `Falcon > port mandible > upper surface > circular dish cluster`
- `X-Wing > port engine > outboard side`
- `Death Star tile family > panel type 3 > raised ridge`

Then forum text, image regions, placements, and map notes can all point at the same location record.

We also need editable positional geometry separate from the conceptual placement itself, so imported map positions can be corrected without overwriting the import record.

That argues for a dedicated position layer such as `placement_positions` or equivalent geometry records.

### Image Regions Instead Of Generic Sightings

The current `ImageAnnotator` is strong as a UI idea, but its data model is still a local generic object/sighting system.

For this repo, the persistent unit should become an `image_region`:

- point
- box
- polygon
- optional rotation
- normalized coordinates
- optional note

Then `image_region` can be linked to:

- `kit`
- `part`
- `cast_assembly`
- `placement`
- `model`
- `map`
- `physical_object`
- `object_state`
- `location`
- `event`
- `source_extract`

That means the annotator becomes a serious evidence tool, not just a standalone markup toy.

### Claims As The Unit Of Research

Not every statement should be baked straight into a placement or object record.

Some things stay contested.

`claims` should capture:

- subject
- predicate
- object or text value
- supporting source or image region
- confidence
- status
- attribution

Examples:

- `image region 214 depicts AMT Peterbilt 359`
- `physical object YWC-O2 is Gold Leader`
- `event E-1976-04-battle-program involved physical object XW-O3`

This allows disagreement without data collapse.

## How Existing Research Files Map In

The current research corpus already lines up with the new model surprisingly well.

### Can Seed `images`

- [anh_pptx_image_manifest.csv](/c:/Users/gunkel/git_nht/NuHopeTools1300.github.io/export_text/research/anh_pptx_image_manifest.csv:1)
- [kit_images_media_crosswalk.csv](/c:/Users/gunkel/git_nht/NuHopeTools1300.github.io/export_text/research/kit_images_media_crosswalk.csv:1)

### Can Seed `image_regions` And `evidence_links`

- [kit_images_overlay_labels.csv](/c:/Users/gunkel/git_nht/NuHopeTools1300.github.io/export_text/research/kit_images_overlay_labels.csv:1)

Those rows already carry normalized coordinates and kit labels.

### Can Seed `events`

- [anh_ilm_timeline.csv](/c:/Users/gunkel/git_nht/NuHopeTools1300.github.io/export_text/research/anh_ilm_timeline.csv:1)
- [anh_ilm_model_timeline.csv](/c:/Users/gunkel/git_nht/NuHopeTools1300.github.io/export_text/research/anh_ilm_model_timeline.csv:1)

### Can Seed `physical_objects` And `object_states`

- [anh_fighter_lineages.csv](/c:/Users/gunkel/git_nht/NuHopeTools1300.github.io/export_text/research/anh_fighter_lineages.csv:1)
- [anh_fighter_identity_states.csv](/c:/Users/gunkel/git_nht/NuHopeTools1300.github.io/export_text/research/anh_fighter_identity_states.csv:1)
- [anh_ywing_conflict_matrix.csv](/c:/Users/gunkel/git_nht/NuHopeTools1300.github.io/export_text/research/anh_ywing_conflict_matrix.csv:1)

### Can Seed `locations`

Initially from:

- existing `maps`
- placement `location_label`
- forum-post recurring map terminology
- image annotator regions

### Can Seed `sources` And `source_extracts`

The forum export folder under [export_text](/c:/Users/gunkel/git_nht/NuHopeTools1300.github.io/export_text:1>) can become structured source records rather than just loose text files.

## Extraction Workflow: Forum Posts

The forum-post pipeline should be:

1. Register transcript file as a `source`
2. Split into post-level or quote-level `source_extracts`
3. Tag candidate entities:
   - kits
   - parts
   - people
   - models
   - physical objects
   - locations
   - events
4. Promote reviewed extracts into:
   - `claims`
   - `placements`
   - `events`
   - `location` aliases or notes

Important point:

Do not parse straight into hard facts.
Parse into candidate extracts first, then review into claims.

## Extraction Workflow: Images

The image workflow should be:

1. Register image once in `images`
2. Optionally add image-level metadata:
   - title
   - code
   - source
   - date
   - scene
3. Annotate one or more `image_regions`
4. Link each region through `evidence_links`
5. Promote strong evidence into `claims` or `placements`

This also makes the PPTX overlay work directly useful instead of staying as side research.

## What Should Happen To ImageAnnotator

The current tool is useful, but too generic and too local.

It should move in this direction:

- DB-backed image list instead of browser-only `DB.images`
- DB-backed region records instead of local `sightings`
- selected entities loaded from the backend instead of only local generic objects
- image properties mapped onto real image metadata fields
- export/import kept as optional convenience, not primary persistence

The current class/object system can still be useful as a temporary UI layer, but the long-term persistent model should be:

- `image`
- `image_region`
- linked research entities

## Immediate Refactor Priorities

1. Make image identity stable and human-readable with `title` and `image_code`
2. Introduce `sources` and `source_extracts`
3. Introduce `locations`
4. Introduce `image_regions`
5. Bridge annotator persistence to the backend
6. Introduce `physical_objects` and `object_states`
7. Introduce `events` and `claims`

That order gives the fastest payoff without breaking the existing donor-part backbone.

## Working Principle

The goal is not to replace the current donor-part database.

The goal is to let it grow into a full research system where:

- parts
- images
- quotes
- maps
- locations
- physical miniatures
- chronology
- attribution

all reinforce each other in one place.

For the product-shell implications of this data model, see [ProductUIArchitecture.md](./ProductUIArchitecture.md).
