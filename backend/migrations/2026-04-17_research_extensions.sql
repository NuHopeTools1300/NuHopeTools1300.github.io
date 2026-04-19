-- Research extensions for the ILM Van Nuys platform
-- Draft migration: additive foundation for image identity, evidence,
-- physical objects, locations, events, and claims.
--
-- Notes:
-- - This is intended as a one-time migration draft, not yet wired into init_db().
-- - Existing image_links remains in place for backward compatibility.
-- - evidence_links is the wider successor for images, image regions, and text extracts.

PRAGMA foreign_keys = ON;

-- Image metadata upgrades.
ALTER TABLE images ADD COLUMN title TEXT;
ALTER TABLE images ADD COLUMN image_code TEXT;
ALTER TABLE images ADD COLUMN caption TEXT;
ALTER TABLE images ADD COLUMN storage_kind TEXT;
ALTER TABLE images ADD COLUMN storage_path TEXT;
ALTER TABLE images ADD COLUMN sha256 TEXT;
ALTER TABLE images ADD COLUMN width INTEGER;
ALTER TABLE images ADD COLUMN height INTEGER;

-- Canonical source records for forum threads, auction listings, interviews,
-- slide decks, spreadsheets, magazine articles, videos, etc.
CREATE TABLE IF NOT EXISTS sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_code     TEXT UNIQUE,
    source_type     TEXT NOT NULL,
    title           TEXT NOT NULL,
    author          TEXT,
    publisher       TEXT,
    source_date     DATE,
    url             TEXT,
    local_path      TEXT,
    parent_source_id INTEGER REFERENCES sources(id),
    notes           TEXT,
    attributed_to   INTEGER REFERENCES contributors(id),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Extracted post-level or quote-level evidence from a source.
CREATE TABLE IF NOT EXISTS source_extracts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id       INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    extract_type    TEXT NOT NULL,      -- forum_post, quote, transcript, slide_note, caption
    locator         TEXT,               -- line range, post number, page, slide, timecode
    author_handle   TEXT,
    extract_date    DATE,
    content         TEXT NOT NULL,
    notes           TEXT,
    attributed_to   INTEGER REFERENCES contributors(id),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Actual physical miniatures or sections, distinct from the canonical model class.
CREATE TABLE IF NOT EXISTS physical_objects (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    object_code     TEXT NOT NULL UNIQUE,
    model_id        INTEGER REFERENCES models(id),
    object_class    TEXT,               -- fighter, tile, hero_ship, special_section, pyro, survivor
    display_name    TEXT NOT NULL,
    shop_label      TEXT,
    build_status    TEXT,               -- reference, hero, pyro, test, survivor, uncertain
    notes           TEXT,
    attributed_to   INTEGER REFERENCES contributors(id),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- A physical object can exist in multiple known states over time.
CREATE TABLE IF NOT EXISTS object_states (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    object_id       INTEGER NOT NULL REFERENCES physical_objects(id) ON DELETE CASCADE,
    state_code      TEXT NOT NULL UNIQUE,
    display_name    TEXT NOT NULL,
    identity_label  TEXT,               -- e.g. Blue 1, Red 2, Gold Leader
    film_version    TEXT,
    date_start      DATE,
    date_end        DATE,
    notes           TEXT,
    attributed_to   INTEGER REFERENCES contributors(id),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Canonical spatial locations on a model or map.
CREATE TABLE IF NOT EXISTS locations (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id            INTEGER REFERENCES models(id),
    map_id              INTEGER REFERENCES maps(id),
    parent_location_id  INTEGER REFERENCES locations(id),
    slug                TEXT NOT NULL UNIQUE,
    display_name        TEXT NOT NULL,
    location_type       TEXT,           -- area, panel, trench, turret, tile, ridge, cockpit, engine
    geometry_json       TEXT,           -- normalized geometry on a map, if available
    notes               TEXT,
    attributed_to       INTEGER REFERENCES contributors(id),
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Chronology for build, filming, repaint, transfer, exhibition, publication, etc.
CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_code      TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    event_type      TEXT NOT NULL,      -- build, filming, repaint, shipment, interview, publication, exhibition
    date_start      DATE,
    date_end        DATE,
    date_note       TEXT,               -- spring 1976, late 1975, etc.
    place_name      TEXT,
    summary         TEXT,
    confidence      TEXT DEFAULT 'probable'
                        CHECK(confidence IN ('confirmed','probable','speculative')),
    attributed_to   INTEGER REFERENCES contributors(id),
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Generic event linkage to existing or new entities.
CREATE TABLE IF NOT EXISTS event_links (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        INTEGER NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    entity_type     TEXT NOT NULL,      -- model, physical_object, object_state, image, source, location, placement
    entity_id       INTEGER NOT NULL,
    relation_type   TEXT DEFAULT 'involves',
    notes           TEXT,
    UNIQUE(event_id, entity_type, entity_id, relation_type)
);

-- Persistent image annotations or extracted overlay markers.
CREATE TABLE IF NOT EXISTS image_regions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id          INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
    region_type       TEXT NOT NULL,    -- point, box, polygon
    x_norm            REAL,
    y_norm            REAL,
    width_norm        REAL,
    height_norm       REAL,
    pixel_x           REAL,
    pixel_y           REAL,
    pixel_width       REAL,
    pixel_height      REAL,
    points_json       TEXT,
    rotation_deg      REAL,
    label             TEXT,
    notes             TEXT,
    object_name       TEXT,
    object_class      TEXT,
    color             TEXT,
    properties_json   TEXT,
    entity_type       TEXT,
    entity_id         INTEGER,
    source_extract_id INTEGER REFERENCES source_extracts(id),
    attributed_to     INTEGER REFERENCES contributors(id),
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Generalized evidence linking.
CREATE TABLE IF NOT EXISTS evidence_links (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    evidence_type   TEXT NOT NULL,      -- image, image_region, source, source_extract
    evidence_id     INTEGER NOT NULL,
    entity_type     TEXT NOT NULL,      -- kit, part, cast_assembly, placement, model, map, physical_object, object_state, location, event
    entity_id       INTEGER NOT NULL,
    relation_type   TEXT DEFAULT 'depicts',
    annotation      TEXT,
    UNIQUE(evidence_type, evidence_id, entity_type, entity_id, relation_type)
);

-- Claim-level research, including unresolved or conflicting statements.
CREATE TABLE IF NOT EXISTS claims (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_code          TEXT UNIQUE,
    subject_type        TEXT NOT NULL,
    subject_id          INTEGER,
    predicate           TEXT NOT NULL,
    object_type         TEXT,
    object_id           INTEGER,
    value_text          TEXT,
    source_id           INTEGER REFERENCES sources(id),
    source_extract_id   INTEGER REFERENCES source_extracts(id),
    image_region_id     INTEGER REFERENCES image_regions(id),
    confidence          TEXT DEFAULT 'probable'
                            CHECK(confidence IN ('confirmed','probable','speculative')),
    status              TEXT DEFAULT 'active'
                            CHECK(status IN ('active','contested','deprecated','superseded')),
    attributed_to       INTEGER REFERENCES contributors(id),
    notes               TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_images_code              ON images(image_code);
CREATE INDEX IF NOT EXISTS idx_images_title             ON images(title);
CREATE INDEX IF NOT EXISTS idx_sources_type             ON sources(source_type);
CREATE INDEX IF NOT EXISTS idx_sources_date             ON sources(source_date);
CREATE INDEX IF NOT EXISTS idx_source_extracts_source   ON source_extracts(source_id);
CREATE INDEX IF NOT EXISTS idx_physical_objects_model   ON physical_objects(model_id);
CREATE INDEX IF NOT EXISTS idx_object_states_object     ON object_states(object_id);
CREATE INDEX IF NOT EXISTS idx_locations_model          ON locations(model_id);
CREATE INDEX IF NOT EXISTS idx_locations_map            ON locations(map_id);
CREATE INDEX IF NOT EXISTS idx_events_dates             ON events(date_start, date_end);
CREATE INDEX IF NOT EXISTS idx_event_links_event        ON event_links(event_id);
CREATE INDEX IF NOT EXISTS idx_event_links_entity       ON event_links(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_image_regions_image      ON image_regions(image_id);
CREATE INDEX IF NOT EXISTS idx_image_regions_entity     ON image_regions(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_image_regions_extract    ON image_regions(source_extract_id);
CREATE INDEX IF NOT EXISTS idx_evidence_links_ev        ON evidence_links(evidence_type, evidence_id);
CREATE INDEX IF NOT EXISTS idx_evidence_links_entity    ON evidence_links(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_claims_subject           ON claims(subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_claims_object            ON claims(object_type, object_id);
CREATE INDEX IF NOT EXISTS idx_claims_source            ON claims(source_id, source_extract_id);
