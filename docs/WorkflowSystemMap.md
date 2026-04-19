# Workflow System Map

## Purpose

This is the compact visual-text map of the product.

It is meant to show the system at one glance:

- main surfaces
- shared objects
- core workflow directions
- important pivots

Use this as the quick orientation sheet.

For the fuller prose model, see:

- [CoreResearchWorkflows.md](./CoreResearchWorkflows.md)
- [WorkflowPivotTable.md](./WorkflowPivotTable.md)
- [ProductUIArchitecture.md](./ProductUIArchitecture.md)

## System Sketch

```text
                               NUHOPETOOLS RESEARCH WORKBENCH

    ┌──────────────────────┐
    │   IMAGE INTAKE       │
    │  grouping / dedupe   │
    │  family management   │
    └──────────┬───────────┘
               │ creates / organizes
               v
    ┌──────────────────────────────────────── SHARED OBJECT MODEL ─────────────────────────────────────────┐
    │                                                                                                      │
    │  Evidence                         Reference / Spatial                    Interpretation / Time       │
    │  ─────────                        ───────────────────                    ─────────────────────       │
    │  source                           kit                                   claim                       │
    │  source_extract                   part                                  event                       │
    │  image_family                     cast_assembly                         physical_object             │
    │  image                            model                                 object_state                │
    │  image_region                     map                                   placement                   │
    │                                   location                              placement_position          │
    │                                                                                                      │
    └──────────┬──────────────────────────────┬───────────────────────────────┬───────────────────────────┘
               │                              │                               │
               │ evidence-first               │ entity-first                  │ time/state-first
               │                              │                               │
               v                              v                               v
  ┌──────────────────────────┐   ┌──────────────────────────┐   ┌──────────────────────────┐
  │   WORKBENCH / IMAGES     │   │    ENTITY WORKBENCH      │   │   WORKBENCH / TIMELINE   │
  │                          │   │                          │   │                          │
  │  inspect image families  │   │  start from kit / part   │   │  start from event /      │
  │  compare variants        │   │  placement / object      │   │  chronology / state      │
  │  annotate regions        │   │  fan outward to evidence │   │  fan outward to evidence │
  │  correct region geometry │   │  review all support      │   │  date build / filming /  │
  │  link region to entity   │   │  and conflicts           │   │  repaint / transfer      │
  │  form claims             │   │                          │   │                          │
  └──────────┬───────────────┘   └──────────┬───────────────┘   └──────────┬───────────────┘
             │                               │                               │
             │ pivots                        │ pivots                        │ pivots
             v                               v                               v
  ┌──────────────────────────┐   ┌──────────────────────────┐   ┌──────────────────────────┐
  │    WORKBENCH / MAPS      │   │   WORKBENCH / SOURCES    │   │  CROSS-MODEL / GRAPH     │
  │                          │   │                          │   │      later surface        │
  │  inspect map areas       │   │  inspect source records  │   │                          │
  │  place entities on maps  │   │  extract quotes/posts    │   │  model <-> kit <-> part  │
  │  correct imported        │   │  link text evidence      │   │  object <-> claim <->    │
  │  positions manually      │   │  to images / objects /   │   │  evidence exploration    │
  │  pivot area -> evidence  │   │  events / claims         │   │                          │
  └──────────────────────────┘   └──────────────────────────┘   └──────────────────────────┘


  Primary forward path:
    image_family -> image -> image_region -> entity -> claim

  Primary reverse path:
    kit / placement / location / object -> linked regions -> linked images -> linked claims

  Map path:
    map / location -> placement -> placement_position -> image_region / claim / source_extract

  Source path:
    source -> source_extract -> image / object / event / claim
```

## Surface Ownership

| Surface | Owns best |
|---|---|
| `Workbench / Images` | image-family browsing, region annotation, geometry correction, entity linking, visual claim creation |
| `Entity Workbench` | reverse lookup from kits, parts, placements, objects into linked evidence and claims |
| `Workbench / Maps` | placement review, location review, manual position correction, area-to-evidence pivots |
| `Workbench / Sources` | transcript/post/article extraction, provenance-heavy review, quote-to-entity linking |
| `Workbench / Timeline` | chronology, event evidence, object-state sequencing |

## Pivots That Must Always Work

- image -> regions
- region -> entity
- region -> claims
- entity -> linked regions
- entity -> linked images
- placement -> map position
- location -> linked evidence
- source extract -> claims
- event -> evidence

## Simple Rule

If a user can get into the system from one side but cannot pivot back out through the linked objects, the surface is incomplete.
