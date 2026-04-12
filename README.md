# ILM Van Nuys Kit-Bash Research Platform

A research platform documenting the kit-bashed parts used on ILM studio models built in Van Nuys — starting with the 5-foot Millennium Falcon (ANH). The goal is to make cross-model connections visible, credit the researchers who found them, and gradually shift a fragmented, knowledge-hoarding community toward open sharing.

---

## Tools

Live at [nuhopetools1300.github.io](https://nuhopetools1300.github.io)

| Tool | Description |
|------|-------------|
| [Image Annotator](tools/annotator.html) | Annotate reference images with part locations |
| [Image Timeline](tools/image_timeline.html) | View reference images in chronological order |
| [Box Art Extractor](tools/box_art_extractor.html) | Extract and identify parts from kit box art |

---

## Backend

A local Flask + SQLite backend that provides a shared persistent store for all tools. Replaces the localStorage approach used in earlier versions of the tools.

### Setup

```bash
pip install -r requirements.txt
python backend/app.py
```

The database will be created at `backend/data/ilm1300.db` on first run. The API is then available at `http://localhost:5000`.

### Importing existing spreadsheets

```bash
# Import kit list (PartList_private.xlsx)
python backend/import_spreadsheets.py --kits path/to/PartList_private.xlsx

# Import ANH cross-model donor sheet
python backend/import_spreadsheets.py --donors path/to/ANH_donors.xlsx

# Both at once
python backend/import_spreadsheets.py \
    --kits path/to/PartList_private.xlsx \
    --donors path/to/ANH_donors.xlsx
```

### API endpoints

```
GET  /api/health
GET  /api/kits                  ?q=&brand=&availability=
GET  /api/kits/<id>
POST /api/kits
GET  /api/parts                 ?kit_id=&q=
POST /api/parts
GET  /api/models
GET  /api/models/<slug>
POST /api/models
GET  /api/placements            ?model_id=&kit_id=&map_id=&film_version=
POST /api/placements
GET  /api/connections           cross-model kit appearances
GET  /api/cast_assemblies
GET  /api/cast_assemblies/<id>
GET  /api/images                ?entity_type=&entity_id=&image_type=
POST /api/images
POST /api/image_links
GET  /api/contributors
POST /api/contributors
```

---

## Data model

Nine core tables. Everything connects through `placements` — the join between a kit part and a specific location on a specific model.

| Table | Purpose |
|-------|---------|
| `kits` | Source model kits — brand, scale, name, serial number, Scalemates link, scan links, availability. |
| `kit_references` | External numbering systems for kits (e.g. Coffman numbers). One kit can have references in multiple systems. |
| `parts` | Individual parts within a kit. |
| `part_files` | 3D scan files, CAD models, and STL files associated with a part. |
| `cast_assemblies` | Named physical assemblies: groups of parts cast together and reused across models. |
| `models` | ILM studio models — Falcon, X-Wing, Star Destroyer, etc. |
| `placements` | The heart of the system. Links a part (or cast assembly, or kit) to a location on a model, with copy count, confidence, film version, and modification state. |
| `placement_contributors` | Many-to-many attribution for placements — multiple researchers often identify the same part independently. |
| `placement_history` | Audit trail for corrected identifications. Transparent correction history builds community trust. |
| `maps` | Annotated map images of model sections. |
| `images` | All reference images — model shop, exhibition, kit scans. |
| `image_tags` | Tags for images (proper many-to-many). |
| `image_links` | Connects images to any entity (kit / part / placement / model). One image, many connections. |
| `contributors` | Researcher handles and forum profiles. Attribution target for all tables. |

### Key design decisions

- `placements` is where the magic happens — one part can link to the Falcon, the Star Destroyer, and the X-Wing simultaneously. That's the cross-model query nobody else can run.
- `film_version` on placements handles models that were modified between films (ANH → ESB → ROTJ on the 5-footer). A placement can be flagged as specific to one film version without needing a separate model record.
- `kit_references` replaces hardcoded Coffman number columns. Any numbering system used by any researcher can be stored here without schema changes.
- `placement_contributors` means every researcher who independently identified a part gets permanent, visible credit — not just the first one in the database.
- `placement_history` records corrections. "Not from the Rodney as I originally thought" is a real and regular event in this community. Showing the correction history openly is how trust is built.
- `confidence` on placements captures `confirmed` / `probable` / `speculative` — critical for research integrity.

---

## Docs

- [Roadmap](docs/Roadmap.md) — phased plan from private research tool to public platform
- [COLMAP transform guide](docs/colmap_transform_guide.md) — photogrammetry workflow for digitising parts

---

## Project status

Phase 1 — private research infrastructure. See [Roadmap](docs/Roadmap.md) for the full plan.

---

*NuHopeTools1300 · April 2026*
