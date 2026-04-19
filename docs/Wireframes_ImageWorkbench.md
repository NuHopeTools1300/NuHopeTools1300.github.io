# Wireframes: Image Workbench

## Purpose

These are low-fidelity wireframes for the first rebuilt workbench slice:

- `image -> region -> entity -> claim`

They are intentionally bare-bones.

The goal is to define:

- layout
- hierarchy
- selection flow
- action placement
- information grouping

They are not visual design comps.

## Screen 1: Image Workbench Default

Use when:

- an image is selected
- no region is currently selected

```text
+------------------------------------------------------------------------------------------------------+
| Workbench / Images                              [Search] [Filters] [Queue] [Global Actions]          |
+------------------------------------------------------------------------------------------------------+
| Library                               | Canvas                                          | Inspector  |
|---------------------------------------|-------------------------------------------------|------------|
| Images                                | [Image title]                                   | Image      |
| [q: death star turret]                | [source badge] [image type] [date]              |------------|
| [type] [source] [tags] [with regions] |                                                 | Overview   |
|                                       | +---------------------------------------------+ | title      |
| > IMG-001  Workshop still             | |                                             | | code       |
|   12 regions  3 claims                | |                                             | | type       |
|   Propstore   model_shop              | |                 IMAGE CANVAS                 | | date       |
|                                       | |                                             | | dimensions |
|   IMG-002  PPTX crop                  | |      o      □           o                   | |            |
|   5 regions   1 claim                 | |                                             | | Provenance |
|   slide_deck reference                | |                                             | | source     |
|                                       | |                                             | | author     |
|   IMG-003  Auction detail             | |                                             | | storage    |
|   0 regions   0 claims                | |                                             | |            |
|   auction exhibition                  | +---------------------------------------------+ | Regions     |
|                                       | [Zoom] [Fit] [1:1] [Show regions] [Add point] | | 12 total    |
| [saved queue]                         | [Add box] [Compare later]                     | | unlinked 4 |
|                                       |                                                 | linked 8    |
|                                       |                                                 |            |
|                                       |                                                 | Linked      |
|                                       |                                                 | entities    |
|                                       |                                                 | kits 3      |
|                                       |                                                 | parts 5     |
|                                       |                                                 | placements  |
|                                       |                                                 |            |
|                                       |                                                 | Claims      |
|                                       |                                                 | 3 claims    |
+------------------------------------------------------------------------------------------------------+
```

### Key Decisions

- left panel is the working image library, not mere navigation
- center is dominated by the image
- right panel is image-level inspector because nothing on the image is selected yet
- region tools exist, but secondary to the image itself

## Screen 2: Region Selected

Use when:

- a region is selected on the image

```text
+------------------------------------------------------------------------------------------------------+
| Workbench / Images                              [Search] [Filters] [Queue] [Global Actions]          |
+------------------------------------------------------------------------------------------------------+
| Library                               | Canvas                                          | Inspector  |
|---------------------------------------|-------------------------------------------------|------------|
| Images                                | [Image title]                                   | Region     |
| [same list as before]                 | [source badge] [image type] [date]              |------------|
|                                       |                                                 | Overview   |
|                                       | +---------------------------------------------+ | label      |
|                                       | |                                             | | type       |
|                                       | |                                             | | linked?    |
|                                       | |              IMAGE CANVAS                   | | claims     |
|                                       | |                                             | |            |
|                                       | |       o      [SELECTED BOX]     o          | | Geometry   |
|                                       | |                                             | | x/y        |
|                                       | |                                             | | w/h        |
|                                       | |                                             | | pixel pos  |
|                                       | +---------------------------------------------+ |            |
|                                       | [Select] [Add point] [Add box] [Hide others]   | Linked      |
|                                       | [Create claim]                                 | entity      |
|                                       |                                                 |------------|
|                                       |                                                 | none linked |
|                                       |                                                 | [Link]      |
|                                       |                                                 |            |
|                                       |                                                 | Evidence    |
|                                       |                                                 | source      |
|                                       |                                                 | sibling regs|
|                                       |                                                 |            |
|                                       |                                                 | Claims      |
|                                       |                                                 | none yet    |
+------------------------------------------------------------------------------------------------------+
```

### Key Decisions

- selecting a region does not navigate away from the image
- the inspector changes mode, the page does not
- `Create claim` becomes available directly in the canvas action row
- entity linking is visible as the most important next step if unlinked

## Screen 3: Link Entity Flow

Use when:

- a region is selected
- the user chooses `Link entity`

```text
+------------------------------------------------------------------------------------------------------+
| Workbench / Images                              [Search] [Filters] [Queue] [Global Actions]          |
+------------------------------------------------------------------------------------------------------+
| Library                               | Canvas                                          | Inspector  |
|---------------------------------------|-------------------------------------------------|------------|
| Images                                | [Image remains visible]                         | Region     |
| [same list]                           | +---------------------------------------------+ |------------|
|                                       | |                                             | Linked      |
|                                       | |         selected region stays visible        | entity      |
|                                       | |                                             |------------|
|                                       | +---------------------------------------------+ | [type tabs] |
|                                       |                                                 | All | Kit   |
|                                       |                                                 | Part| Place |
|                                       |                                                 |------------|
|                                       |                                                 | [search box]|
|                                       |                                                 |             |
|                                       |                                                 | Results     |
|                                       |                                                 |-------------|
|                                       |                                                 | Kit         |
|                                       |                                                 | AMT 57 Chevy|
|                                       |                                                 | car / id 27 |
|                                       |                                                 | [Select]    |
|                                       |                                                 |             |
|                                       |                                                 | Part        |
|                                       |                                                 | pt-194      |
|                                       |                                                 | kit 27      |
|                                       |                                                 | [Select]    |
|                                       |                                                 |             |
|                                       |                                                 | Placement   |
|                                       |                                                 | Falcon port |
|                                       |                                                 | probable    |
|                                       |                                                 | [Select]    |
+------------------------------------------------------------------------------------------------------+
```

### Key Decisions

- linking happens in the inspector, not in a detached modal
- the image remains visible the whole time
- entity type tabs reduce picker overload
- results must be rich enough to prevent mistaken linking

## Screen 4: Claim Draft

Use when:

- a region is selected
- optionally an entity is already linked
- the user clicks `Create claim`

```text
+------------------------------------------------------------------------------------------------------+
| Workbench / Images                              [Search] [Filters] [Queue] [Global Actions]          |
+------------------------------------------------------------------------------------------------------+
| Library                               | Canvas                                          | Inspector  |
|---------------------------------------|-------------------------------------------------|------------|
| Images                                | [Image remains visible with selected region]    | Claim Draft|
| [same list]                           | +---------------------------------------------+ |------------|
|                                       | |                                             | Evidence    |
|                                       | |         selected region stays visible        | | image id   |
|                                       | |                                             | | region id  |
|                                       | +---------------------------------------------+ | source     |
|                                       |                                                 | linked ent  |
|                                       |                                                 |            |
|                                       |                                                 | Claim type  |
|                                       |                                                 | [preset ▼]  |
|                                       |                                                 |            |
|                                       |                                                 | Subject     |
|                                       |                                                 | [entity/text]|
|                                       |                                                 | Predicate   |
|                                       |                                                 | [depicts ▼] |
|                                       |                                                 | Object      |
|                                       |                                                 | [entity/text]|
|                                       |                                                 |            |
|                                       |                                                 | Confidence  |
|                                       |                                                 | confirmed   |
|                                       |                                                 | probable    |
|                                       |                                                 | uncertain   |
|                                       |                                                 |            |
|                                       |                                                 | Rationale   |
|                                       |                                                 | [textarea]  |
|                                       |                                                 |            |
|                                       |                                                 | [Cancel]    |
|                                       |                                                 | [Save claim]|
+------------------------------------------------------------------------------------------------------+
```

### Key Decisions

- claim creation happens in context
- evidence summary stays visible at the top of the inspector
- the form is structured, but not overbuilt
- claim presets reduce writing friction

## Screen 5: Region With Multiple Claims

Use when:

- a region already has more than one claim
- claims may agree or conflict

```text
+------------------------------------------------------------------------------------------------------+
| Workbench / Images                              [Search] [Filters] [Queue] [Global Actions]          |
+------------------------------------------------------------------------------------------------------+
| Library                               | Canvas                                          | Inspector  |
|---------------------------------------|-------------------------------------------------|------------|
| Images                                | [Image with selected region]                    | Region     |
| [same list]                           | +---------------------------------------------+ |------------|
|                                       | |                                             | Linked ent  |
|                                       | |         selected region stays visible        | | AMT kit 27 |
|                                       | |                                             |            |
|                                       | +---------------------------------------------+ | Claims      |
|                                       |                                                 |------------|
|                                       |                                                 | Claim A     |
|                                       |                                                 | depicts kit |
|                                       |                                                 | probable    |
|                                       |                                                 | source x    |
|                                       |                                                 | [Open]      |
|                                       |                                                 |            |
|                                       |                                                 | Claim B     |
|                                       |                                                 | supports pt |
|                                       |                                                 | uncertain   |
|                                       |                                                 | source y    |
|                                       |                                                 | [Open]      |
|                                       |                                                 |            |
|                                       |                                                 | Claim C     |
|                                       |                                                 | contested   |
|                                       |                                                 | speculative |
|                                       |                                                 | [Open]      |
|                                       |                                                 |            |
|                                       |                                                 | [New claim] |
+------------------------------------------------------------------------------------------------------+
```

### Key Decisions

- conflict is represented, not hidden
- one region can support multiple interpretations
- claim cards are readable and comparable at a glance

## Screen 6: No Regions Yet

Use when:

- an image exists
- no regions have been created for it

```text
+------------------------------------------------------------------------------------------------------+
| Workbench / Images                              [Search] [Filters] [Queue] [Global Actions]          |
+------------------------------------------------------------------------------------------------------+
| Library                               | Canvas                                          | Inspector  |
|---------------------------------------|-------------------------------------------------|------------|
| Images                                | [Image title]                                   | Image      |
| [same list]                           | +---------------------------------------------+ |------------|
|                                       | |                                             | Overview   |
|                                       | |                  IMAGE CANVAS                | | image meta |
|                                       | |                                             |            |
|                                       | |         No regions marked on this image      | | Regions     |
|                                       | |                                             | | none yet    |
|                                       | |    [Add first point]   [Add first box]       | |            |
|                                       | |                                             | | Suggested   |
|                                       | +---------------------------------------------+ | next steps  |
|                                       |                                                 | - add region |
|                                       |                                                 | - link source|
|                                       |                                                 | - review img |
+------------------------------------------------------------------------------------------------------+
```

### Key Decisions

- blank state stays useful
- the canvas itself invites action
- the inspector offers structured next steps

## Notes On Behavior

### Selection Rules

- library selection chooses the current image
- canvas selection chooses the current region
- inspector always reflects current selection

### Inspector Rules

- image selected, no region selected -> image inspector
- region selected -> region inspector
- claim draft active -> claim-draft inspector

### Region Rendering Rules

- selected region: strong stroke
- unlinked region: neutral warning style
- linked region: linked accent
- contested region: distinct conflict accent

## Build Implications

These wireframes assume:

- no floating detached mini-tools
- no modal-heavy annotation workflow
- no hard context switch between browsing and annotating

They are meant to validate the future shell, not the legacy UI.

## Next Step

If these wireframes feel directionally right, the next artifact should be:

- an implementation plan mapping each screen area to components, endpoints, and missing backend requirements

That would be the bridge from product design into actual build work.

That implementation bridge now lives in:

- [Phase1BuildChecklist.md](./Phase1BuildChecklist.md)
