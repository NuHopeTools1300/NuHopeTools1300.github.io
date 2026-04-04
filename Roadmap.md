# ILM Van Nuys - Kit-Bash Research Platform
### Project Roadmap · NuHopeTools1300 · April 2026

---

## Vision

A research platform and eventual public database documenting the kit-bashed parts used on ILM studio models built in Van Nuys during the original Star Wars movie - starting with the 5-foot Millennium Falcon. The goal is to make the cross-model connections visible, credit the researchers who found them, and gradually shift a fragmented, knowledge-hoarding community toward open sharing.

---

## Strategic approach

- Build the research infrastructure first - tools that make our own work better today.
- Don't ask the community to change behaviour - build something worth pointing at.
- Attribution baked in from day one - every find credits its identifier, permanently.
- The cross-model connection graph is the unique value.

---

## Phase 1 - Now · Research infrastructure
*Private · you + few enthusiasts*

| # | Step | Description | Tag |
|---|------|-------------|-----|
| 1 | **Flask backend + SQLite database** | Shared persistent store. Imports existing spreadsheets. Replaces localStorage across all tools. Runs locally to start. | Start here |
| 2 | **Image ↔ data linking** | The core missing link. Part → kit scans. Falcon location → all reference images showing it. Google Drive integration. | Core |
| 3 | **Connect existing tools to backend** | ImageAnnotator + image timeline all read/write from the shared database. Work already done — just rewired. | Upgrade |
| 4 | **Attribution baked in from day one** | Every find credits its identifier. Permanent, visible, citable. The key to unlocking expert contribution later. | Strategic |

---

## Phase 2 - Next · Community database
*Semi-public · trusted contributors*

| # | Step | Description | Tag |
|---|------|-------------|-----|
| 5 | **Cross-model connection explorer** | The unique value prop. "This Tamiya kit also appears on the Star Destroyer and X-Wing." Connections nobody else shows. | Differentiator |
| 6 | **Search + filter interface** | Find by kit, model, part number, location. The public-facing database experience starts here. | Public-facing |
| 7 | **Contribution workflow** | Simple submit form for trusted contributors. Low friction, clearly attributed. No account required to start. | Community |

---

## Phase 3 - Later · Public platform
*Open · community gravity*

| # | Step | Description | Tag |
|---|------|-------------|-----|
| 8 | **Visual connection graph** | Interactive web of models, kits and shared parts. The 'big picture' made visible to everyone. | Showcase |
| 9 | **Open contribution + moderation** | Community submissions with review. The culture shift toward open sharing happens here - if the platform earned it. | Long game |

---

## Data model

Seven core tables. Everything connects through `placements` - the join between a kit part and a specific location on a specific model.

| Table | Purpose |
|-------|---------|
| `kits` | Source model kits — brand, scale, name, serial number, Scalemates link, scan links. |
| `parts` | Individual parts within a kit. Self-referencing FK for cast/recast relationships. |
| `models` | ILM studio models — Falcon, X-Wing, Star Destroyer, etc. |
| `placements` | The heart of the system. Links a part to a location on a model, with copy count and confidence level. |
| `maps` | Annotated map images of model sections. Each map links to a model. |
| `images` | All reference images — model shop, exhibition, kit scans. Tagged, dated, sourced. |
| `image_links` | Connects images to any entity (kit / part / placement / model). One image, many connections. |
| `contributors` | Researcher handles and forum profiles. Attribution FK target. |

### Key design decisions

- **`placements`** is where the magic happens — one part can link to the Falcon, the Star Destroyer, and the X-Wing simultaneously. That's the cross-model query nobody else can run.
- **`image_links`** solves the core missing link — one exhibition photo can simultaneously relate to a model, specific placements visible in it, and the kit parts identified there.
- **`cast_source_part_id`** is a self-referencing FK on `parts` — captures the cast/recast relationships between parts shared across models.
- **`confidence`** on placements captures `confirmed` / `probable` / `speculative` — critical for research integrity.

---

## Saved for later - not forgotten

**Box art extractor** — a deep archaeology tool for identifying which vintage kit boxes ILM purchased. Useful for the 'which kits were originally used' historical research, but low community value and not on the critical path. Revisit after Phase 1 is solid.

---

## North star

> Build so well it becomes the obvious place to share *to* - don't ask people to change their habits, give them a destination worth pointing at.

---

*NuHopeTools1300 · Working document · April 2026*
