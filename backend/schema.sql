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
    category_family  TEXT,               -- e.g. 'aircraft', 'military_ground', 'naval'
    category_subject TEXT,               -- e.g. 'military_aircraft', 'afv', 'carrier'
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
    url         TEXT,                    -- GrabCAD, Drive, Shapeways, etc. (NULL = source known but no URL yet)
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
    image_id      INTEGER REFERENCES images(id),
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

-- ── PLACEMENT POSITIONS ──────────────────────────────────────────
-- Versioned geometric records for where a placement is drawn on a map.
-- This keeps conceptual placement identity separate from imported/manual geometry.
CREATE TABLE IF NOT EXISTS placement_positions (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    placement_id  INTEGER NOT NULL REFERENCES placements(id) ON DELETE CASCADE,
    map_id        INTEGER NOT NULL REFERENCES maps(id) ON DELETE CASCADE,
    position_type TEXT NOT NULL DEFAULT 'point'
                  CHECK(position_type IN ('point','box','polygon')),
    x_norm        REAL,
    y_norm        REAL,
    width_norm    REAL,
    height_norm   REAL,
    polygon_json  TEXT,
    source_kind   TEXT NOT NULL DEFAULT 'manual'
                  CHECK(source_kind IN ('imported','manual','candidate','derived')),
    status        TEXT NOT NULL DEFAULT 'active'
                  CHECK(status IN ('active','superseded','rejected')),
    is_current    INTEGER NOT NULL DEFAULT 1 CHECK(is_current IN (0,1)),
    supersedes_id INTEGER REFERENCES placement_positions(id),
    confidence    TEXT DEFAULT 'probable'
                  CHECK(confidence IN ('confirmed','probable','speculative')),
    notes         TEXT,
    attributed_to INTEGER REFERENCES contributors(id),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Canonical source records for forum threads, auction listings, interviews,
-- slide decks, spreadsheets, magazine articles, videos, etc.
CREATE TABLE IF NOT EXISTS sources (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    source_code      TEXT UNIQUE,
    source_type      TEXT NOT NULL,      -- forum_thread, article, auction, interview, slide_deck, spreadsheet, video
    title            TEXT NOT NULL,
    author           TEXT,
    publisher        TEXT,
    source_date      DATE,
    url              TEXT,
    local_path       TEXT,
    parent_source_id INTEGER REFERENCES sources(id),
    notes            TEXT,
    attributed_to    INTEGER REFERENCES contributors(id),
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Extracted post-level or quote-level evidence from a source.
CREATE TABLE IF NOT EXISTS source_extracts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id      INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    extract_type   TEXT NOT NULL,        -- forum_post, quote, transcript, slide_note, caption
    locator        TEXT,                 -- line range, post number, page, slide, timecode
    author_handle  TEXT,
    extract_date   DATE,
    content        TEXT NOT NULL,
    notes          TEXT,
    attributed_to  INTEGER REFERENCES contributors(id),
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ── IMAGES ───────────────────────────────────────────────────────
-- All reference images: model shop, exhibition, kit scans, etc.
-- Removed: tags (comma-separated) → see image_tags below
CREATE TABLE IF NOT EXISTS images (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    filename      TEXT,
    title         TEXT,                  -- human-friendly display title
    image_code    TEXT,                  -- stable human-readable identifier
    caption       TEXT,
    drive_id      TEXT,                  -- Google Drive file ID
    url           TEXT,
    storage_kind  TEXT,                  -- upload, drive, url, generated, extracted, other
    storage_path  TEXT,                  -- local or logical storage path
    sha256        TEXT,                  -- binary identity for dedupe / crosswalk
    width         INTEGER,
    height        INTEGER,
    image_type    TEXT CHECK(image_type IN (
                      'model_shop','exhibition','kit_scan',
                      'box_art','reference','map','other'
                  )),
    date_taken    DATE,
    source        TEXT,                  -- e.g. 'Prop Store auction', 'RPF thread'
    source_id     INTEGER REFERENCES sources(id),
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
-- Logical image families for duplicates, crops, overlays, and other related variants.
CREATE TABLE IF NOT EXISTS image_families (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    title            TEXT NOT NULL,
    family_type      TEXT DEFAULT 'reference_set'
                        CHECK(family_type IN ('reference_set','duplicate_group','detail_set','overlay_set','mixed')),
    primary_image_id INTEGER REFERENCES images(id) ON DELETE SET NULL,
    notes            TEXT,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS image_family_members (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    family_id            INTEGER NOT NULL REFERENCES image_families(id) ON DELETE CASCADE,
    image_id             INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    relation_type        TEXT NOT NULL DEFAULT 'variant'
                           CHECK(relation_type IN (
                               'primary','variant','duplicate','near_duplicate',
                               'crop','detail','overlay','higher_resolution',
                               'lower_resolution','alternate_scan','derived'
                           )),
    sort_order           INTEGER DEFAULT 0,
    is_primary           INTEGER NOT NULL DEFAULT 0 CHECK(is_primary IN (0,1)),
    is_hidden_in_library INTEGER NOT NULL DEFAULT 0 CHECK(is_hidden_in_library IN (0,1)),
    coverage_role        TEXT
                           CHECK(coverage_role IN (
                               'full_frame','detail_crop','annotation_overlay','comparison_variant'
                           )),
    notes                TEXT,
    UNIQUE(family_id, image_id)
);

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

-- Persistent image annotations / regions for point, box, or polygon evidence.
-- Can optionally carry a linked entity reference plus object snapshot metadata
-- from the annotator until a fuller evidence-link layer lands.
CREATE TABLE IF NOT EXISTS image_regions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id         INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    region_type      TEXT NOT NULL DEFAULT 'point'
                         CHECK(region_type IN ('point','box','polygon')),
    x_norm           REAL,
    y_norm           REAL,
    width_norm       REAL,
    height_norm      REAL,
    pixel_x          REAL,
    pixel_y          REAL,
    pixel_width      REAL,
    pixel_height     REAL,
    points_json      TEXT,
    rotation_deg     REAL,
    label            TEXT,
    notes            TEXT,
    object_name      TEXT,
    object_class     TEXT,
    color            TEXT,
    properties_json  TEXT,
    entity_type      TEXT,
    entity_id        INTEGER,
    source_extract_id INTEGER REFERENCES source_extracts(id),
    attributed_to    INTEGER REFERENCES contributors(id),
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Region-level history for annotation changes.
CREATE TABLE IF NOT EXISTS image_region_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    region_id     INTEGER NOT NULL,
    action        TEXT NOT NULL,         -- create, update, delete
    snapshot_json TEXT,
    changed_by    INTEGER REFERENCES contributors(id),
    reason        TEXT,
    changed_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Structured interpretations derived from evidence.
CREATE TABLE IF NOT EXISTS claims (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_type  TEXT NOT NULL,
    subject_id    INTEGER,
    predicate     TEXT NOT NULL,
    object_type   TEXT,
    object_id     INTEGER,
    text_value    TEXT,
    confidence    TEXT NOT NULL DEFAULT 'probable'
                   CHECK(confidence IN ('confirmed','probable','uncertain','speculative')),
    status        TEXT NOT NULL DEFAULT 'active'
                   CHECK(status IN ('draft','active','contested','retracted','superseded')),
    rationale     TEXT,
    attributed_to INTEGER REFERENCES contributors(id),
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Links a claim back to the evidence that supports it.
CREATE TABLE IF NOT EXISTS claim_evidence (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_id      INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    evidence_type TEXT NOT NULL CHECK(evidence_type IN ('image_region','source_extract','image')),
    evidence_id   INTEGER NOT NULL,
    annotation    TEXT,
    UNIQUE(claim_id, evidence_type, evidence_id)
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
CREATE INDEX IF NOT EXISTS idx_kits_category_family ON kits(category_family);
CREATE INDEX IF NOT EXISTS idx_kits_category_subject ON kits(category_subject);
CREATE INDEX IF NOT EXISTS idx_placement_contrib   ON placement_contributors(placement_id);
CREATE INDEX IF NOT EXISTS idx_placement_history   ON placement_history(placement_id);
CREATE INDEX IF NOT EXISTS idx_placement_positions_placement ON placement_positions(placement_id);
CREATE INDEX IF NOT EXISTS idx_placement_positions_map ON placement_positions(map_id);
CREATE INDEX IF NOT EXISTS idx_placement_positions_current ON placement_positions(placement_id, map_id, is_current);
CREATE INDEX IF NOT EXISTS idx_part_files_part     ON part_files(part_id);
CREATE INDEX IF NOT EXISTS idx_image_tags          ON image_tags(image_id);
CREATE INDEX IF NOT EXISTS idx_image_tags_tag      ON image_tags(tag);
CREATE INDEX IF NOT EXISTS idx_image_families_primary ON image_families(primary_image_id);
CREATE INDEX IF NOT EXISTS idx_image_family_members_family ON image_family_members(family_id);
CREATE INDEX IF NOT EXISTS idx_image_family_members_image ON image_family_members(image_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_image_family_members_image_unique ON image_family_members(image_id);
CREATE INDEX IF NOT EXISTS idx_sources_type        ON sources(source_type);
CREATE INDEX IF NOT EXISTS idx_sources_date        ON sources(source_date);
CREATE INDEX IF NOT EXISTS idx_source_extracts_src ON source_extracts(source_id);
CREATE INDEX IF NOT EXISTS idx_images_code         ON images(image_code);
CREATE INDEX IF NOT EXISTS idx_images_title        ON images(title);
CREATE INDEX IF NOT EXISTS idx_images_source_id    ON images(source_id);
CREATE INDEX IF NOT EXISTS idx_image_regions_image ON image_regions(image_id);
CREATE INDEX IF NOT EXISTS idx_image_regions_entity ON image_regions(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_image_regions_extract ON image_regions(source_extract_id);
CREATE INDEX IF NOT EXISTS idx_image_region_history_region ON image_region_history(region_id);
CREATE INDEX IF NOT EXISTS idx_claims_subject      ON claims(subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_claims_status       ON claims(status);
CREATE INDEX IF NOT EXISTS idx_claim_evidence_claim ON claim_evidence(claim_id);
CREATE INDEX IF NOT EXISTS idx_claim_evidence_target ON claim_evidence(evidence_type, evidence_id);
