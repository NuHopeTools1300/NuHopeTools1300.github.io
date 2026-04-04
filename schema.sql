-- ILM Van Nuys Kit-Bash Research Database
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
-- Commercial model kits used as donor parts by ILM
CREATE TABLE IF NOT EXISTS kits (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    coffman_number      INTEGER,         -- Coffman kit# for Falcon, NULL for others
    coffman_base        INTEGER,         -- base number (without suffix)
    coffman_suffix      INTEGER,         -- suffix (variant)
    brand               TEXT NOT NULL,
    scale               TEXT,            -- e.g. '1/72', '1/35'
    name                TEXT NOT NULL,
    serial_number       TEXT,            -- manufacturer part number
    scalemates_url      TEXT,
    scans_url           TEXT,
    instructions_url    TEXT,
    confirmed_in_image  BOOLEAN DEFAULT 0,
    notes               TEXT,
    attributed_to       INTEGER REFERENCES contributors(id),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── PARTS ────────────────────────────────────────────────────────
-- Individual parts within a kit
CREATE TABLE IF NOT EXISTS parts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    kit_id          INTEGER NOT NULL REFERENCES kits(id),
    part_number     TEXT NOT NULL,       -- e.g. '42', 'A3', 'npn_001'
    part_label      TEXT,                -- optional description
    notes           TEXT,
    attributed_to   INTEGER REFERENCES contributors(id),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── CAST ASSEMBLIES ──────────────────────────────────────────────
-- Named physical assemblies: groups of parts cast together and reused
-- across models. May be one part or many, from one kit or several.
CREATE TABLE IF NOT EXISTS cast_assemblies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,           -- e.g. '8Rad plate', 'Matilda assembly'
    notes       TEXT,
    attributed_to INTEGER REFERENCES contributors(id),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Which parts make up each cast assembly (many-to-many)
CREATE TABLE IF NOT EXISTS cast_assembly_parts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    cast_assembly_id    INTEGER NOT NULL REFERENCES cast_assemblies(id),
    part_id             INTEGER NOT NULL REFERENCES parts(id),
    notes               TEXT,            -- e.g. 'cut', 'modified', 'partial'
    UNIQUE(cast_assembly_id, part_id)
);

-- ── MODELS ───────────────────────────────────────────────────────
-- ILM studio models
CREATE TABLE IF NOT EXISTS models (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,          -- e.g. 'Millennium Falcon (5ft)'
    slug         TEXT NOT NULL UNIQUE,   -- e.g. 'falcon-5ft', 'star-destroyer'
    film         TEXT,                   -- e.g. 'ANH', 'ESB', 'ROTJ'
    scale_approx TEXT,                   -- approximate scale if known
    notes        TEXT
);

-- ── MAPS ─────────────────────────────────────────────────────────
-- Named sections / annotated map images of a model
CREATE TABLE IF NOT EXISTS maps (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id      INTEGER NOT NULL REFERENCES models(id),
    name          TEXT NOT NULL,         -- e.g. 'cockpit', 'bottom center', '8Rad'
    version       TEXT,                  -- e.g. 'Version 1.2 July 4, 2024'
    url           TEXT,                  -- link to the annotated map image
    map_date      DATE,
    attributed_to INTEGER REFERENCES contributors(id),
    notes         TEXT
);

-- ── PLACEMENTS ───────────────────────────────────────────────────
-- The heart of the system.
-- Links a part (or cast assembly) to a specific location on a specific model.
-- Either part_id OR cast_assembly_id must be set — enforced by CHECK constraint.
CREATE TABLE IF NOT EXISTS placements (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id            INTEGER NOT NULL REFERENCES models(id),
    map_id              INTEGER REFERENCES maps(id),
    part_id             INTEGER REFERENCES parts(id),
    cast_assembly_id    INTEGER REFERENCES cast_assemblies(id),
    location_label      TEXT,            -- free text location description
    copy_count          INTEGER DEFAULT 1,
    confidence          TEXT DEFAULT 'confirmed'
                            CHECK(confidence IN ('confirmed','probable','speculative')),
    notes               TEXT,
    source_url          TEXT,            -- forum post or thread where identified
    attributed_to       INTEGER REFERENCES contributors(id),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- exactly one of part_id or cast_assembly_id must be set
    CHECK (
        (part_id IS NOT NULL AND cast_assembly_id IS NULL) OR
        (part_id IS NULL AND cast_assembly_id IS NOT NULL)
    )
);

-- ── IMAGES ───────────────────────────────────────────────────────
-- All reference images: model shop, exhibition, kit scans, etc.
CREATE TABLE IF NOT EXISTS images (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    filename      TEXT,
    drive_id      TEXT,                  -- Google Drive file ID
    url           TEXT,                  -- fallback / direct URL
    image_type    TEXT CHECK(image_type IN (
                      'model_shop','exhibition','kit_scan',
                      'box_art','reference','other'
                  )),
    date_taken    DATE,
    source        TEXT,                  -- e.g. 'Prop Store auction', 'RPF thread'
    tags          TEXT,                  -- comma-separated free tags
    notes         TEXT,
    attributed_to INTEGER REFERENCES contributors(id),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    annotation  TEXT,                    -- what's visible / relevant in this image
    UNIQUE(image_id, entity_type, entity_id)
);

-- ── INDEXES ──────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_parts_kit        ON parts(kit_id);
CREATE INDEX IF NOT EXISTS idx_placements_model ON placements(model_id);
CREATE INDEX IF NOT EXISTS idx_placements_part  ON placements(part_id);
CREATE INDEX IF NOT EXISTS idx_placements_cast  ON placements(cast_assembly_id);
CREATE INDEX IF NOT EXISTS idx_image_links_img  ON image_links(image_id);
CREATE INDEX IF NOT EXISTS idx_image_links_ent  ON image_links(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_maps_model       ON maps(model_id);
CREATE INDEX IF NOT EXISTS idx_cap_assembly     ON cast_assembly_parts(cast_assembly_id);
CREATE INDEX IF NOT EXISTS idx_cap_part         ON cast_assembly_parts(part_id);
