-- ILM Van Nuys Kit-Bash Research Database
-- Revised schema — April 2026
-- Enable foreign key enforcement
PRAGMA foreign_keys = ON;

-- ── CONTRIBUTORS ─────────────────────────────────────────────────
-- Researchers who identified parts. Attribution target for all other tables.
CREATE TABLE IF NOT EXISTS contributors (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    handle       TEXT NOT NULL UNIQUE,   -- forum username / known alias
    display_name TEXT,
    forum        TEXT,                   -- e.g. 'RPF', 'SSM', 'Facebook'
    profile_url  TEXT,
    notes        TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── KITS ─────────────────────────────────────────────────────────
-- Commercial model kits used as donor parts by ILM.
-- Removed: coffman_number, coffman_base, coffman_suffix → see kit_references
-- Removed: confirmed_in_image → derivable from image_links (entity_type='kit')
CREATE TABLE IF NOT EXISTS kits (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    brand            TEXT NOT NULL,
    scale            TEXT,               -- e.g. '1/72', '1/35'
    name             TEXT NOT NULL,
    serial_number    TEXT,               -- manufacturer part number
    scalemates_url   TEXT,
    scans_url        TEXT,
    instructions_url TEXT,
    availability     TEXT DEFAULT 'unknown'
                         CHECK(availability IN ('available','rare','oop','unknown')),
                         -- oop = out of production
    notes            TEXT,
    attributed_to    INTEGER REFERENCES contributors(id),
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── KIT REFERENCES ───────────────────────────────────────────────
-- External / researcher-specific numbering systems for kits.
-- Replaces coffman_number / coffman_base / coffman_suffix on kits.
-- Supports any numbering system — Coffman for the Falcon, others as they emerge.
-- value stores the full reference as a string (e.g. '47a', '12', '144').
CREATE TABLE IF NOT EXISTS kit_references (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    kit_id  INTEGER NOT NULL REFERENCES kits(id) ON DELETE CASCADE,
    system  TEXT NOT NULL,               -- e.g. 'coffman', 'spruebrothers', 'internal'
    value   TEXT NOT NULL,               -- the actual reference string
    notes   TEXT,
    UNIQUE(kit_id, system)
);

-- ── PARTS ────────────────────────────────────────────────────────
-- Individual parts within a kit.
CREATE TABLE IF NOT EXISTS parts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    kit_id        INTEGER NOT NULL REFERENCES kits(id),
    part_number   TEXT NOT NULL,         -- e.g. '42', 'A3', 'npn_001'
    part_label    TEXT,                  -- optional description
    notes         TEXT,
    attributed_to INTEGER REFERENCES contributors(id),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── PART FILES ───────────────────────────────────────────────────
-- 3D scan files and digital assets associated with a part.
-- 3D printing / digitisation is now mainstream in the studio scale hobby.
CREATE TABLE IF NOT EXISTS part_files (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    part_id     INTEGER NOT NULL REFERENCES parts(id) ON DELETE CASCADE,
    file_type   TEXT NOT NULL CHECK(file_type IN ('scan','cad','stl','step','reference','other')),
    url         TEXT NOT NULL,           -- GrabCAD, Drive, Shapeways, etc.
    source      TEXT,                    -- e.g. 'Maruska', 'YAFF', 'personal scan'
    notes       TEXT,
    attributed_to INTEGER REFERENCES contributors(id),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── CAST ASSEMBLIES ──────────────────────────────────────────────
-- Named physical assemblies: groups of parts cast together and reused
-- across models. May be one part or many, from one kit or several.
CREATE TABLE IF NOT EXISTS cast_assemblies (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,         -- e.g. '8Rad plate', 'Matilda assembly'
    notes         TEXT,
    attributed_to INTEGER REFERENCES contributors(id),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Which parts make up each cast assembly (many-to-many)
CREATE TABLE IF NOT EXISTS cast_assembly_parts (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    cast_assembly_id INTEGER NOT NULL REFERENCES cast_assemblies(id),
    part_id          INTEGER NOT NULL REFERENCES parts(id),
    notes            TEXT,               -- e.g. 'cut', 'modified', 'partial'
    UNIQUE(cast_assembly_id, part_id)
);

-- ── MODELS ───────────────────────────────────────────────────────
-- ILM studio models.
CREATE TABLE IF NOT EXISTS models (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,          -- e.g. 'Millennium Falcon (5ft)'
    slug         TEXT NOT NULL UNIQUE,   -- e.g. 'falcon-5ft', 'star-destroyer'
    film         TEXT,                   -- primary film: 'ANH', 'ESB', 'ROTJ'
    scale_approx TEXT,
    notes        TEXT
);

-- ── MAPS ─────────────────────────────────────────────────────────
-- Named sections / annotated map images of a model.
CREATE TABLE IF NOT EXISTS maps (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id      INTEGER NOT NULL REFERENCES models(id),
    name          TEXT NOT NULL,         -- e.g. 'cockpit', 'bottom center', '8Rad'
    version       TEXT,                  -- e.g. 'Version 1.2 July 4, 2024'
    url           TEXT,
    map_date      DATE,
    attributed_to INTEGER REFERENCES contributors(id),
    notes         TEXT
);

-- ── PLACEMENTS ───────────────────────────────────────────────────
-- The heart of the system.
-- Links a part (or cast assembly) to a specific location on a specific model.
--
-- Three valid cases (enforced by CHECK):
--   1. part_id only              — known part, no cast assembly
--   2. cast_assembly_id only     — known cast assembly
--   3. kit_id only               — kit confirmed present but part not yet identified
--      (replaces the old '?' placeholder part hack from the importer)
--
-- film_version overrides model.film for placements specific to one film version
-- of a model that spanned multiple films (e.g. 5ft Falcon ANH vs ESB vs ROTJ).
--
-- modification captures how the part was prepared before placement.
-- Multi-contributor attribution is handled by placement_contributors below.
CREATE TABLE IF NOT EXISTS placements (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id         INTEGER NOT NULL REFERENCES models(id),
    map_id           INTEGER REFERENCES maps(id),
    part_id          INTEGER REFERENCES parts(id),
    cast_assembly_id INTEGER REFERENCES cast_assemblies(id),
    kit_id           INTEGER REFERENCES kits(id),   -- kit-level only, when part unknown
    film_version     TEXT,               -- e.g. 'ANH', 'ESB' — overrides model.film
    location_label   TEXT,
    copy_count       INTEGER DEFAULT 1,
    confidence       TEXT DEFAULT 'confirmed'
                         CHECK(confidence IN ('confirmed','probable','speculative')),
    modification     TEXT DEFAULT 'none'
                         CHECK(modification IN
                             ('none','cut','sanded','combined','painted_over','reversed','other')),
    notes            TEXT,
    source_url       TEXT,               -- forum post or thread where identified
    attributed_to    INTEGER REFERENCES contributors(id),
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- exactly one of part_id, cast_assembly_id, or kit_id must be set
    CHECK (
        (part_id IS NOT NULL AND cast_assembly_id IS NULL AND kit_id IS NULL) OR
        (part_id IS NULL AND cast_assembly_id IS NOT NULL AND kit_id IS NULL) OR
        (part_id IS NULL AND cast_assembly_id IS NULL AND kit_id IS NOT NULL)
    )
);

-- ── PLACEMENT CONTRIBUTORS ───────────────────────────────────────
-- Multiple researchers often independently identify the same part.
-- This replaces the single attributed_to FK for placements with a proper
-- many-to-many so every finder gets permanent, visible credit.
-- attributed_to on placements remains as the primary / first identifier;
-- co-identifiers go here.
CREATE TABLE IF NOT EXISTS placement_contributors (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    placement_id   INTEGER NOT NULL REFERENCES placements(id) ON DELETE CASCADE,
    contributor_id INTEGER NOT NULL REFERENCES contributors(id),
    role           TEXT DEFAULT 'identifier'
                       CHECK(role IN ('identifier','verifier','challenger','corrector')),
    notes          TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(placement_id, contributor_id)
);

-- ── PLACEMENT HISTORY ────────────────────────────────────────────
-- Audit trail for identification corrections.
-- "Not from the Rodney as I originally thought" is a real event.
-- Showing corrections transparently builds community trust.
CREATE TABLE IF NOT EXISTS placement_history (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    placement_id     INTEGER NOT NULL REFERENCES placements(id) ON DELETE CASCADE,
    changed_by       INTEGER REFERENCES contributors(id),
    changed_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    prev_part_id     INTEGER REFERENCES parts(id),
    prev_kit_id      INTEGER REFERENCES kits(id),
    prev_confidence  TEXT,
    prev_notes       TEXT,
    reason           TEXT                -- why the identification was revised
);

-- ── IMAGES ───────────────────────────────────────────────────────
-- All reference images: model shop, exhibition, kit scans, etc.
-- Removed: tags (comma-separated) → see image_tags below
CREATE TABLE IF NOT EXISTS images (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    filename      TEXT,
    drive_id      TEXT,                  -- Google Drive file ID
    url           TEXT,
    image_type    TEXT CHECK(image_type IN (
                      'model_shop','exhibition','kit_scan',
                      'box_art','reference','other'
                  )),
    date_taken    DATE,
    source        TEXT,                  -- e.g. 'Prop Store auction', 'RPF thread'
    notes         TEXT,
    attributed_to INTEGER REFERENCES contributors(id),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── IMAGE TAGS ───────────────────────────────────────────────────
-- Replaces comma-separated tags column on images.
-- Proper many-to-many makes tag filtering a simple join.
CREATE TABLE IF NOT EXISTS image_tags (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    tag      TEXT NOT NULL,
    UNIQUE(image_id, tag)
);

-- ── IMAGE LINKS ──────────────────────────────────────────────────
-- Connects an image to any entity in the database.
-- One image can link to a kit, a part, a placement, a model — all at once.
CREATE TABLE IF NOT EXISTS image_links (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id    INTEGER NOT NULL REFERENCES images(id),
    entity_type TEXT NOT NULL CHECK(entity_type IN (
                    'kit','part','cast_assembly','placement','model','map'
                )),
    entity_id   INTEGER NOT NULL,
    annotation  TEXT,
    UNIQUE(image_id, entity_type, entity_id)
);

-- ── INDEXES ──────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_parts_kit           ON parts(kit_id);
CREATE INDEX IF NOT EXISTS idx_placements_model    ON placements(model_id);
CREATE INDEX IF NOT EXISTS idx_placements_part     ON placements(part_id);
CREATE INDEX IF NOT EXISTS idx_placements_cast     ON placements(cast_assembly_id);
CREATE INDEX IF NOT EXISTS idx_placements_kit      ON placements(kit_id);
CREATE INDEX IF NOT EXISTS idx_placements_film     ON placements(film_version);
CREATE INDEX IF NOT EXISTS idx_image_links_img     ON image_links(image_id);
CREATE INDEX IF NOT EXISTS idx_image_links_ent     ON image_links(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_maps_model          ON maps(model_id);
CREATE INDEX IF NOT EXISTS idx_cap_assembly        ON cast_assembly_parts(cast_assembly_id);
CREATE INDEX IF NOT EXISTS idx_cap_part            ON cast_assembly_parts(part_id);
CREATE INDEX IF NOT EXISTS idx_kit_references_kit  ON kit_references(kit_id);
CREATE INDEX IF NOT EXISTS idx_kit_references_sys  ON kit_references(system, value);
CREATE INDEX IF NOT EXISTS idx_placement_contrib   ON placement_contributors(placement_id);
CREATE INDEX IF NOT EXISTS idx_placement_history   ON placement_history(placement_id);
CREATE INDEX IF NOT EXISTS idx_part_files_part     ON part_files(part_id);
CREATE INDEX IF NOT EXISTS idx_image_tags          ON image_tags(image_id);
CREATE INDEX IF NOT EXISTS idx_image_tags_tag      ON image_tags(tag);