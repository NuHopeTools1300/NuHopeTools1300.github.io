# Workflow Pivot Table

## Purpose

This is the plain-language companion to the architecture docs.

It answers:

- where does a user start?
- what are they trying to find out?
- which surface should support that?
- which objects are involved?
- what pivots must work cleanly?

This should help keep the product grounded in real use instead of drifting into tool-by-tool design.

## Reading Rule

Each row is a real research starting point.

If the product cannot support that row cleanly, something is missing in the workflow design.

## Pivot Table

| Starting point | User question | Best surface | Main objects involved | Required pivots |
|---|---|---|---|---|
| Image family | What is this image, and what variants belong with it? | `Workbench / Images` | `image_family`, `image`, `source` | image family -> variants -> provenance |
| Image family | What regions already exist on this image? | `Workbench / Images` | `image`, `image_region` | image -> regions |
| Image region | What does this marked area show? | `Workbench / Images` | `image_region`, `kit/part/placement/model`, `claim` | region -> entity -> claim |
| Image region | Is this identification already known or contested? | `Workbench / Images` | `image_region`, `claim` | region -> claims -> evidence |
| Image region | This imported marker is slightly wrong; can I correct it? | `Workbench / Images` | `image_region`, region geometry history | region -> correction history |
| Kit | Where does this kit appear in images? | `Entity Workbench` | `kit`, `image`, `image_region`, `claim` | kit -> linked regions -> images |
| Kit | Which placements use this kit? | `Entity Workbench` | `kit`, `placement`, `model`, `map` | kit -> placements -> maps/models |
| Part | Which images actually support this part identification? | `Entity Workbench` | `part`, `image_region`, `claim`, `source_extract` | part -> evidence |
| Placement | Where is this placement on the model, and what evidence supports it? | `Workbench / Maps` or `Entity Workbench` | `placement`, `map`, `placement_position`, `image_region`, `claim` | placement -> map position -> evidence |
| Map area / location | What other images show this area? | `Workbench / Maps` | `location`, `placement`, `image_region`, `image` | location -> placements -> regions -> images |
| Map area / location | What other objects are linked to this area? | `Workbench / Maps` | `location`, `placement`, `kit`, `part`, `claim` | location -> placements -> entities |
| Source | Does this post/article/auction actually support anything in the database? | `Workbench / Sources` | `source`, `source_extract`, `claim`, `image`, `entity` | source -> extracts -> claims/entities |
| Source extract | Which image, object, or event does this quote relate to? | `Workbench / Sources` | `source_extract`, `image`, `physical_object`, `event`, `claim` | extract -> evidence/claim/entity |
| Physical object | Which images and claims define this lineage or state? | `Entity Workbench` | `physical_object`, `object_state`, `image`, `claim`, `event` | object -> states -> evidence -> events |
| Event | What evidence dates this build, filming, repaint, or transfer event? | `Workbench / Timeline` | `event`, `image`, `source_extract`, `claim`, `object_state` | event -> evidence -> objects |

## Surface Summary

### Workbench / Images

Best for:

- image-family browsing
- image inspection
- region annotation
- region correction
- entity linking
- claim creation from visual evidence

Must support:

- family -> variant switching
- image -> region
- region -> entity
- region -> claim
- entity backlinks out of the inspector

### Workbench / Maps

Best for:

- placement inspection
- location review
- manual position correction
- area-based evidence lookup

Must support:

- map area -> placement
- placement -> evidence
- location -> linked images
- imported position -> corrected position

### Workbench / Sources

Best for:

- transcript/post/article review
- quote extraction
- text evidence linking
- provenance-heavy checking

Must support:

- source -> extract
- extract -> entity
- extract -> claim
- extract -> image/event/object

### Entity Workbench

Best for:

- starting from kits, parts, placements, objects
- following linked evidence outward
- reviewing all known support and conflicts

Must support:

- entity -> linked images
- entity -> linked regions
- entity -> claims
- entity -> neighboring related entities

### Workbench / Timeline

Best for:

- chronology
- build/filming windows
- object states over time

Must support:

- event -> objects
- event -> evidence
- event -> claims

## What This Clarifies

### 1. The Image Workbench Is Important, But Not The Whole Product

It owns a strong cluster of workflows, but not all of them.

### 2. Reverse Lookup Is Core, Not A Nice-To-Have

The user must be able to start from:

- kit
- placement
- location
- object
- event

and fan outward into evidence just as naturally as starting from an image.

### 3. Interoperability Matters More Than Tool Count

The system can have several workbench surfaces.

That is fine.

What matters is that:

- object identity is shared
- pivots are reliable
- the user never feels trapped in one tool

### 4. Duplicate Handling And Position Correction Are Workflow Problems

They are not just data-cleaning chores.

They affect:

- how users browse
- how they trust evidence
- how they revise earlier imports

So they belong in the product model.

## Simple Product Test

Whenever we design a new feature, ask:

1. What is the user starting from?
2. What are they trying to learn or do?
3. Which surface should own that interaction?
4. What pivots need to work before and after that step?

If we cannot answer those four questions clearly, the feature is probably underdefined.
