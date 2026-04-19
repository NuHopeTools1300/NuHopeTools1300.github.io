# Image Families And Position Correction

## Why This Matters

Two real issues are showing up at once:

- the workbench now exposes both a list and a thumbnail strip, but they currently compete instead of complementing each other
- the image corpus contains duplicates, near-duplicates, crops, and mixed-resolution variants that should not all appear as first-class rows
- some imported spatial positions are only approximately correct and need a clean manual correction path

These are not edge cases.

They are normal for this project.

The product needs to treat them as first-class research realities rather than cleanup chores.

## Product Goal

The user should browse one logical evidence item at a time, not one raw file at a time.

That means:

- one visible library row for a logical image family
- one designated primary image for that family
- zero or more associated variants
- the ability to switch between variants when useful
- the ability to mark duplicates as hidden behind the primary item
- the ability to preserve cropped or higher-resolution detail variants without flooding the library

Likewise, spatial records should distinguish:

- imported positions
- manually corrected positions
- multiple candidate positions when uncertainty remains

## Recommended UX Model

### 1. Give The List And The Gallery Different Jobs

Do not keep both as parallel full result views.

Instead:

- `Library list`: one row per logical image family, optimized for search, metadata, provenance, and selection
- `Filmstrip/gallery`: visual variant browser for the selected family or the current short result window

This makes the two surfaces complementary rather than redundant.

### 2. Library Rows Should Represent Image Families

A row should represent the logical unit a researcher thinks in:

- `1976 shop still with Y-wing buck`
- `PPTX overlay reference image`
- `auction hero shot of Gold Leader`

Not:

- `image12.jpg`
- `image12_crop3.jpg`
- `image12_resized.jpg`

Each family row should show:

- compact title
- source / date / type
- family size badge, for example `4 variants`
- duplicate / crop status badges where relevant
- a small primary thumbnail

### 3. Filmstrip Should Show Variants, Not Duplicate The List

When an image family is selected, the filmstrip should switch from "all visible search results" to "variants within this family".

That gives the filmstrip a strong purpose:

- quick swap between `primary`, `crop`, `high-res detail`, `overlay`, `duplicate`, `alternate scan`

If no family grouping exists yet, the filmstrip can temporarily fall back to result browsing.

### 4. Duplicates Should Usually Collapse

Exact duplicates and visually equivalent low-value repeats should not all remain visible in the main library.

Recommended behavior:

- one `primary` image is shown in the library
- duplicates are hidden under `Show associated images`
- duplicates remain in the database for provenance and audit reasons
- a duplicate can be promoted to primary later if the user changes their mind

### 5. Crops And High-Resolution Details Should Stay Associated

These are not the same as duplicates.

Typical case:

- low-resolution full image gives context
- high-resolution crop gives usable detail

Recommended behavior:

- both belong to the same family
- primary is usually the full contextual image
- crops are attached as `detail variants`
- canvas should let the user swap between them

This avoids flooding the library while preserving meaningful evidence.

## Recommended Data Model

### Image Families

Add an explicit image-family layer.

Suggested tables:

- `image_families`
- `image_family_members`

Possible shape:

- `image_families`
  - `id`
  - `title`
  - `family_type`
  - `primary_image_id`
  - `notes`

- `image_family_members`
  - `id`
  - `family_id`
  - `image_id`
  - `relation_type`
  - `sort_order`
  - `is_primary`
  - `is_hidden_in_library`
  - `coverage_role`
  - `notes`

Suggested `relation_type` values:

- `duplicate`
- `near_duplicate`
- `crop`
- `detail`
- `overlay`
- `higher_resolution`
- `lower_resolution`
- `alternate_scan`
- `derived`

Suggested `coverage_role` values:

- `full_frame`
- `detail_crop`
- `annotation_overlay`
- `comparison_variant`

### Why A Family Layer Is Better Than Reusing `image_links`

`image_links` currently links images to entities like kits, parts, placements, and models.

That is not the same as image-to-image structure.

Trying to encode family logic inside `image_links` would blur:

- evidence relationships
- entity relationships
- file/variant relationships

The image-family layer should stay explicit.

## Recommended Spatial Correction Model

### Current Weakness

`placements` currently have:

- `map_id`
- `location_label`

But they do not have canonical editable geometry on the map.

That means imported location placements cannot be corrected in a structured way.

### Needed Capability

We need a persistent map-position layer that supports:

- imported geometry
- manual correction
- multiple candidate positions
- history
- provenance

Suggested table:

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

Suggested `source_kind` values:

- `imported`
- `manual`
- `derived`

Suggested `status` values:

- `active`
- `superseded`
- `candidate`
- `rejected`

### Why This Should Be Separate From `placements`

The placement record is the identification claim:

- what part / kit / cast assembly is placed where conceptually

The position record is the geometric interpretation:

- where on the map we currently think that placement sits

Those should not be the same field.

Otherwise every correction becomes destructive and history-poor.

## Workbench / UI Suggestions

### Image Workbench

Recommended near-term behavior:

- left library shows one row per image family
- selecting a row loads the primary image
- filmstrip shows associated images for that family
- inspector has a `Variants` section with:
  - set primary
  - hide from library
  - mark duplicate
  - mark crop/detail
  - show hidden associated images

### Variant Actions

Each associated image should support:

- `Make primary`
- `Mark duplicate`
- `Mark detail crop`
- `Keep visible in library`
- `Hide in library`
- `Detach from family`

### Map / Placement Workbench

When a placement is selected on a map:

- show current active position
- show original imported position if one exists
- allow drag or point/box correction
- save as a new manual position record
- preserve the imported record in history

This should feel like:

- `import said this`
- `manual correction now says this`

not:

- `the old data vanished`

## Concrete Product Rules

### Rule 1

Raw files should not define the visible browsing unit.

### Rule 2

One logical evidence family gets one library entry by default.

### Rule 3

Duplicates are preserved in the database but hidden in normal browsing unless requested.

### Rule 4

Crops and higher-resolution detail variants stay attached to the same family unless they are genuinely independent evidence objects.

### Rule 5

Imported geometry should never be overwritten silently; manual correction should create a new current position and preserve the previous one.

## Suggested Implementation Order

### Step 1

Add image-family schema and API.

### Step 2

Update workbench library to browse image families instead of raw images.

### Step 3

Retarget the filmstrip to family variants.

### Step 4

Add family-management controls in the inspector.

### Step 5

Add `placement_positions` schema and API.

### Step 6

Build a map correction tool that writes manual position overrides instead of mutating imports directly.

## Honest Assessment

This is worth doing before the image corpus grows much further.

Without an image-family layer, the workbench will become noisier every time we import a serious batch.

Without a position-override layer, spatial corrections will remain fragile and under-documented.

Both are structural improvements, not polish.
