# Layered Canvas — Design Verdict & Minimal Layers

Saved: 2026-05-12
Source: conversation notes

## Verdict

Layered canvas is an appropriate, practical choice — it preserves data safety and provenance while delivering the single-surface UX you want. Done correctly it’s an enabler, not a roadblock.

## Benefits

- Clarity of intent: layers separate concerns visually (Image Regions vs Map Positions) without forcing mental context switches.
- Safety: keeps backend semantics (image_regions vs placement_positions) intact so edits remain auditable.
- Single workflow: unified library / canvas / inspector reduces navigation cost for users.
- Flexible annotation classes: layering makes it natural to support multiple annotation types per image.
- Incremental rollout: UI-only changes can be prototyped without risky DB migrations.

## Risks / Roadblocks

- UI complexity: poor visual hierarchy or mode handling can confuse users (too many toggles/modes).
- Accidental edits: mixing position-editing affordances with region-editing can cause destructive changes if not gated.
- Performance: rendering many overlays (placements + regions) can slow older machines unless optimized.
- Verification burden: combined UI increases the number of route/interaction permutations to test.

## Design / UX Patterns to Use

- Layer toggle + opacity slider: obvious controls to show/hide Image Regions, Placements, and auxiliary layers.
- Annotation-class palette: pick class (region, placement, candidate, note) before drawing; show active class clearly.
- Mode lock & safety: require explicit “Edit positions” mode for placement edits; use a “Preview → Commit (promote)” flow for manual position changes.
- Visual hierarchy: use color/weight to distinguish imported (read-only) vs manual (editable) overlays; show provenance badges on hover.
- Inspector pivot: single right-side inspector that shows either region or placement details and cross-links between them.
- Non-destructive edits: create new placement_positions rows for manual corrections (preserve imported rows).
- Undo & confirm: quick undo + a small confirmation for replacing current position.
- Progressive disclosure: hide advanced controls behind a “More” panel to keep the UI sleek.

## Implementation / Engineering Guidance

- Keep backend separation: do not collapse `placement_positions` into `image_regions`. Surface both through the UI.
- Incremental prototype: update `workbench.html` to add a Map/Position layer toggle and render placement overlays (read-only) first. Then add explicit edit mode to create/promote positions.
- Performance: virtualize lists, batch overlay drawing (Canvas or requestAnimationFrame), and collapse low-confidence markers at zoomed-out scales.
- Testing: add smoke tests covering: display toggles, create/promote position, region → placement pivot, and permission/flag behavior.
- Design polish: prioritize minimal chrome, generous canvas space, filmstrip for variants, and micro-animations for state changes.

## Visual / Interaction Examples (short)

- Left: library/filters; Center: layered canvas with “Layers” pill (Regions | Positions | Grid) and class picker; Right: inspector with tabs (Details / History / Evidence).
- When user enables “Edit Positions”: UI shows orange manual handles, a small persistent banner “You are in Position Edit mode — changes create manual positions.”

## Minimal Image Classes (recommended)

Start with a small, pragmatic set that covers the workbench and map workflows:

- **Map** — backing map images used for placements (maps + map images). Critical for map_workbench workflows.
- **Reference** — general reference photos (group `model_shop`, `exhibition`, `box_art`, `other` under this during rollout).
- **Kit scan** — scanned kit images used to match parts.

Rationale: these three cover the two distinct UX domains in the repo — image evidence/regions (workbench) vs. map-based placement correction (map workbench) and kit-matching.

## Minimal Layers (implement in order)

1. **Base image** — underlying raster the user views (DOM present in `workbench.html` and `map_workbench.html`).
2. **Image Regions** — persistent annotations (`image_regions` table). Render read-only first; enable selection/inspector linking.
3. **Placements / Position Layer** — placement markers derived from `placements` + `placement_positions` (versioned geometry). Render separate overlay; read-only initially.
4. **Draft/Edit Layer** — transient drawing layer for creating/moving boxes/points (`draft-box` exists in UIs). Edits should create new `placement_positions` rows with `source_kind='manual'` to preserve provenance.
5. **Labels & UI controls** — layer toggle, opacity slider, label size/theme controls (already present in the UI). Hide advanced controls behind progressive disclosure.

Concise rationale: the codebase already separates evidence (`image_regions`) from conceptual placement identity + versioned geometry (`placement_positions`). Surface both overlays but gate edits behind an explicit edit mode that writes new `placement_positions` rows.

## Data & Code References

- DB: `image_regions` and `placement_positions` definitions in `backend/schema.sql`.
- APIs: image regions — `backend/blueprints/evidence.py` (`/api/image_regions`); placement positions — `backend/blueprints/placements.py` (`/api/placement_positions`).
- UIs: region layer — `workbench.html` (`#region-layer`); position layer — `map_workbench.html` (`#position-layer`).

## Next step (recommended)

Prototype a minimal toggle in `workbench.html`: show placement overlays (read-only) and add an “Enable Position Edit” button that opens a guarded edit flow. Run quick usability tests with 3 users and measure accidental edits, task completion time, and clarity.

---

(End of saved notes.)
