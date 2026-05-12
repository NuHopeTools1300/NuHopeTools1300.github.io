# Data Model

Updated: May 3, 2026

Canonical schema file: `backend/schema.sql`.

This document is a readable summary only. If this summary conflicts with `backend/schema.sql`, the schema file wins.

## Schema Evolution Rule

New accepted schema changes should land in three places:

1. `backend/schema.sql` for fresh databases.
2. A new ordered SQL file in `backend/migrations/` for existing databases.
3. A minimal compatibility bridge in `backend/schema_bootstrap.py` only when older local databases would otherwise break.

See [Migration Policy](../backend/migrations/README.md).

## Core Layers

### Reference Layer

Stable records used across the workstation.

| Table | Purpose |
|-------|---------|
| `contributors` | Researcher handles and attribution targets |
| `kits` | Commercial donor kits: brand, scale, name, serial, category, Scalemates, thumbnail, availability |
| `kit_references` | External numbering systems such as Coffman references |
| `parts` | Individual parts within a kit |
| `part_files` | Scan/CAD/STL/reference file links for parts |
| `cast_assemblies` | Named reused assemblies made from one or more parts |
| `cast_assembly_parts` | Parts included in a cast assembly |
| `models` | Studio model subjects such as Falcon, X-Wing, Star Destroyer |
| `maps` | Annotated map images/sections for a model |

### Placement Layer

This is the donor-part backbone.

| Table | Purpose |
|-------|---------|
| `placements` | Links one part, cast assembly, or kit-level unknown to a model/map location |
| `placement_contributors` | Many-to-many contributor attribution for placements |
| `placement_history` | Identification correction history |
| `placement_positions` | Versioned map geometry for placement position correction |

Important placement rule:

- A placement has exactly one identity target: `part_id`, `cast_assembly_id`, or kit-level `kit_id`.
- Kit-level placements are valid when the donor kit is known but the exact part is not.
- Map geometry belongs in `placement_positions`, not directly in conceptual placement identity.

### Evidence Layer

Raw or near-raw evidence.

| Table | Purpose |
|-------|---------|
| `sources` | Canonical forum thread, auction, slide deck, spreadsheet, article, interview, or video source records |
| `source_extracts` | Post-level, quote-level, caption, slide note, or transcript extracts |
| `images` | Image metadata for uploads, Drive records, extracted images, kit scans, maps, and references |
| `image_tags` | Normalized image tags |
| `image_families` | Logical groups for duplicates, crops, details, overlays, and variants |
| `image_family_members` | Images included in a family, with role/visibility metadata |
| `image_links` | Direct image-to-entity links |
| `image_regions` | Persistent image annotations with normalized geometry and optional entity link |
| `image_region_history` | Region-level change history |

### Interpretation Layer

Structured research assertions.

| Table | Purpose |
|-------|---------|
| `claims` | Structured assertion with subject, predicate, object/text value, confidence, status, rationale |
| `claim_evidence` | Evidence links supporting a claim |

Current workflow simplification:

- Direct image links and region links should be the normal workflow.
- Claims are for contested, explanatory, or review-heavy interpretation.
- Ordinary evidence linking should not force claim creation.

## Active Implementation Boundary

In scope now:

- kits
- parts
- models
- maps
- placements
- placement positions
- images
- image families
- image regions
- image links
- claims
- sources and extracts

Deferred on purpose:

- canonical `locations`
- `physical_objects`
- `object_states`
- `events`
- public/community graph and contribution layers

Those deferred entities appear in architecture docs as target-shape concepts, but should not be partially introduced into active schema/API/UI until a dedicated phase begins.

## Current Local Data Snapshot

From the May 1 cleanup pass:

| Table | Count |
|-------|------:|
| `kits` | 449 |
| `parts` | 1,797 |
| `models` | 13 |
| `maps` | 59 |
| `placements` | 2,845 |
| `placement_positions` | 33 |
| `images` | 420 |
| `image_families` | 64 |
| `image_regions` | 533 |
| `image_links` | 340 |
| `claims` | 5 |
| `sources` | 5 |
| `source_extracts` | 0 |
| `contributors` | 0 |

Interpretation:

- donor kit / part / placement records are the strongest populated layer
- image regions and links are active but still being expanded
- claims and source extracts exist structurally but are early in actual use
- placement positions work, but currently cover only a small part of the placement set
