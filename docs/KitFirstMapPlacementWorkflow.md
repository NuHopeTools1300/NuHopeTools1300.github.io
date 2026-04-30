# Kit-First Map Placement Workflow

## Rule

Map placement work should happen in two passes.

In plain language:

- a map location gets a kit tag first
- later, that same location gets a part tag from that kit when the exact part is known

Current schema mapping:

- the "location" is represented by a `placement` plus its `placement_positions`
- the first-pass kit tag is `placements.kit_id` with `part_id` empty
- the later part tag is a refined placement using `part_id`
- kit tag views may also be derived from existing part placements, because a part placement implies its parent kit

Do not add a separate canonical `locations` table for this slice.

Part numbers are integer identifiers when numeric. Store and display `8`, not
`8.0`; decimal-looking numeric cells from spreadsheets should be normalized at
import time unless the identifier is genuinely alphanumeric or compound.

## Pass 1 - Kit-Level Placement

Place the kit on the map first.

This is intentionally rough:

- use the map number, label, or visible kit ID when available
- create a `placement` with `kit_id`
- leave `part_id` empty
- place the marker or box on the map
- use `confidence='probable'` unless the map/source makes it certain
- treat this as useful working data, not a final part identification

This pass answers:

- which kits appear on this map?
- roughly where are they?
- which maps still need coverage?
- which kits need a later part-refinement pass?

If exact part placements already exist, do not duplicate them with separate kit-only placements just to make the kit visible. The kit is already derivable from the part.

## Pass 2 - Part Refinement

Later, revisit kit-level placements and identify the exact part.

This pass can be entered from:

- a map
- a kit in the Entity Browser
- an image/region
- a review queue of kit-level placements without parts

The refinement should convert or supersede the kit-level placement with an exact `part_id` only when the part is actually known.

## Why

Trying to identify every exact part while mapping creates too much friction.

The useful first milestone is coverage:

- maps have visible kit markers
- the database can answer kit/map questions
- later refinement becomes a focused cleanup queue instead of a blocker

## UI Implication

`map_workbench.html` should default to kit-level placement.

Part-level placement is a refinement mode, not the default path.
