"""Local SQLite schema initialization and compatibility bridges."""

import os
import sqlite3

try:
    from .config import DB_PATH, SCHEMA, UPLOAD_DIR
except ImportError:
    from config import DB_PATH, SCHEMA, UPLOAD_DIR


def column_exists(db, table_name, column_name):
    rows = db.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_column(db, table_name, column_name, ddl):
    if not column_exists(db, table_name, column_name):
        db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")


def ensure_images_support_map_type(db):
    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='images'"
    ).fetchone()
    if not row:
        sql = ''
    elif isinstance(row, sqlite3.Row):
        sql = row['sql'] or ''
    else:
        sql = row[0] or ''
    if "'map'" in sql:
        return
    db.execute("PRAGMA foreign_keys = OFF")
    db.execute("ALTER TABLE images RENAME TO images_old_maptype")
    db.executescript("""
    CREATE TABLE images (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        filename      TEXT,
        title         TEXT,
        image_code    TEXT,
        caption       TEXT,
        drive_id      TEXT,
        url           TEXT,
        storage_kind  TEXT,
        storage_path  TEXT,
        sha256        TEXT,
        width         INTEGER,
        height        INTEGER,
        image_type    TEXT CHECK(image_type IN (
                          'model_shop','exhibition','kit_scan',
                          'box_art','reference','map','other'
                      )),
        date_taken    DATE,
        source        TEXT,
        source_id     INTEGER REFERENCES sources(id),
        notes         TEXT,
        attributed_to INTEGER REFERENCES contributors(id),
        created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    INSERT INTO images (
        id, filename, title, image_code, caption, drive_id, url, storage_kind, storage_path,
        sha256, width, height, image_type, date_taken, source, source_id, notes, attributed_to, created_at
    )
    SELECT
        id, filename, title, image_code, caption, drive_id, url, storage_kind, storage_path,
        sha256, width, height, image_type, date_taken, source, source_id, notes, attributed_to, created_at
    FROM images_old_maptype;
    DROP TABLE images_old_maptype;
    """)
    db.execute("PRAGMA foreign_keys = ON")


def table_sql_contains(db, table_name, needle):
    row = db.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    ).fetchone()
    if not row:
        return False
    sql = row['sql'] if isinstance(row, sqlite3.Row) else row[0]
    return needle in (sql or '')


def rebuild_table(db, table_name, create_sql, columns):
    temp_name = f"{table_name}__repair"
    column_csv = ", ".join(columns)
    db.execute(f"DROP TABLE IF EXISTS {temp_name}")
    db.execute(create_sql.replace("__TABLE__", temp_name))
    db.execute(f"""
        INSERT INTO {temp_name} ({column_csv})
        SELECT {column_csv}
        FROM {table_name}
    """)
    db.execute(f"DROP TABLE {table_name}")
    db.execute(f"ALTER TABLE {temp_name} RENAME TO {table_name}")


def repair_broken_image_foreign_keys(db):
    repair_specs = [
        (
            'image_families',
            """
            CREATE TABLE __TABLE__ (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                title            TEXT NOT NULL,
                family_type      TEXT DEFAULT 'reference_set'
                                    CHECK(family_type IN ('reference_set','duplicate_group','detail_set','overlay_set','mixed')),
                primary_image_id INTEGER REFERENCES images(id) ON DELETE SET NULL,
                notes            TEXT,
                created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            ['id', 'title', 'family_type', 'primary_image_id', 'notes', 'created_at']
        ),
        (
            'image_tags',
            """
            CREATE TABLE __TABLE__ (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                image_id INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
                tag      TEXT NOT NULL,
                UNIQUE(image_id, tag)
            )
            """,
            ['id', 'image_id', 'tag']
        ),
        (
            'image_links',
            """
            CREATE TABLE __TABLE__ (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                image_id    INTEGER NOT NULL REFERENCES images(id),
                entity_type TEXT NOT NULL CHECK(entity_type IN (
                                'kit','part','cast_assembly','placement','model','map'
                            )),
                entity_id   INTEGER NOT NULL,
                annotation  TEXT,
                UNIQUE(image_id, entity_type, entity_id)
            )
            """,
            ['id', 'image_id', 'entity_type', 'entity_id', 'annotation']
        ),
        (
            'image_regions',
            """
            CREATE TABLE __TABLE__ (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                image_id          INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
                region_type       TEXT NOT NULL DEFAULT 'point'
                                 CHECK(region_type IN ('point','box','polygon')),
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
            )
            """,
            [
                'id', 'image_id', 'region_type', 'x_norm', 'y_norm', 'width_norm', 'height_norm',
                'pixel_x', 'pixel_y', 'pixel_width', 'pixel_height', 'points_json', 'rotation_deg',
                'label', 'notes', 'object_name', 'object_class', 'color', 'properties_json',
                'entity_type', 'entity_id', 'source_extract_id', 'attributed_to', 'created_at',
                'updated_at'
            ]
        ),
        (
            'image_family_members',
            """
            CREATE TABLE __TABLE__ (
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
            )
            """,
            [
                'id', 'family_id', 'image_id', 'relation_type', 'sort_order', 'is_primary',
                'is_hidden_in_library', 'coverage_role', 'notes'
            ]
        ),
    ]

    if not any(table_sql_contains(db, table_name, 'images_old_maptype') for table_name, _, _ in repair_specs):
        return

    db.execute("PRAGMA foreign_keys = OFF")
    try:
        for table_name, create_sql, columns in repair_specs:
            if table_sql_contains(db, table_name, 'images_old_maptype'):
                rebuild_table(db, table_name, create_sql, columns)
    finally:
        db.execute("PRAGMA foreign_keys = ON")
    db.commit()


def ensure_research_bootstrap(db):
    """Compatibility bridge for older local databases during schema transition.

    New schema work should land in schema.sql plus ordered migrations first.
    Keep this bootstrap layer focused on backward-compatible repairs/backfills.
    """
    db.executescript("""
    CREATE TABLE IF NOT EXISTS sources (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        source_code      TEXT UNIQUE,
        source_type      TEXT NOT NULL,
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

    CREATE TABLE IF NOT EXISTS source_extracts (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id      INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
        extract_type   TEXT NOT NULL,
        locator        TEXT,
        author_handle  TEXT,
        extract_date   DATE,
        content        TEXT NOT NULL,
        notes          TEXT,
        attributed_to  INTEGER REFERENCES contributors(id),
        created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS image_families (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        title            TEXT NOT NULL,
        family_type      TEXT DEFAULT 'reference_set',
        primary_image_id INTEGER REFERENCES images(id) ON DELETE SET NULL,
        notes            TEXT,
        created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS image_family_members (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        family_id            INTEGER NOT NULL REFERENCES image_families(id) ON DELETE CASCADE,
        image_id             INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
        relation_type        TEXT NOT NULL DEFAULT 'variant',
        sort_order           INTEGER DEFAULT 0,
        is_primary           INTEGER NOT NULL DEFAULT 0,
        is_hidden_in_library INTEGER NOT NULL DEFAULT 0,
        coverage_role        TEXT,
        notes                TEXT,
        UNIQUE(family_id, image_id)
    );

    CREATE TABLE IF NOT EXISTS image_regions (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        image_id          INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
        region_type       TEXT NOT NULL DEFAULT 'point',
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

    CREATE TABLE IF NOT EXISTS image_region_history (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        region_id     INTEGER NOT NULL,
        action        TEXT NOT NULL,
        snapshot_json TEXT,
        changed_by    INTEGER REFERENCES contributors(id),
        reason        TEXT,
        changed_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS claims (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_type  TEXT NOT NULL,
        subject_id    INTEGER,
        predicate     TEXT NOT NULL,
        object_type   TEXT,
        object_id     INTEGER,
        text_value    TEXT,
        confidence    TEXT NOT NULL DEFAULT 'probable',
        status        TEXT NOT NULL DEFAULT 'active',
        rationale     TEXT,
        attributed_to INTEGER REFERENCES contributors(id),
        created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS claim_evidence (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        claim_id      INTEGER NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
        evidence_type TEXT NOT NULL,
        evidence_id   INTEGER NOT NULL,
        annotation    TEXT,
        UNIQUE(claim_id, evidence_type, evidence_id)
    );

    CREATE TABLE IF NOT EXISTS placement_positions (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        placement_id  INTEGER NOT NULL REFERENCES placements(id) ON DELETE CASCADE,
        map_id        INTEGER NOT NULL REFERENCES maps(id) ON DELETE CASCADE,
        position_type TEXT NOT NULL DEFAULT 'point',
        x_norm        REAL,
        y_norm        REAL,
        width_norm    REAL,
        height_norm   REAL,
        polygon_json  TEXT,
        source_kind   TEXT NOT NULL DEFAULT 'manual',
        status        TEXT NOT NULL DEFAULT 'active',
        is_current    INTEGER NOT NULL DEFAULT 1,
        supersedes_id INTEGER REFERENCES placement_positions(id),
        confidence    TEXT DEFAULT 'probable',
        notes         TEXT,
        attributed_to INTEGER REFERENCES contributors(id),
        created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    ensure_column(db, 'images', 'title', 'TEXT')
    ensure_column(db, 'images', 'image_code', 'TEXT')
    ensure_column(db, 'images', 'caption', 'TEXT')
    ensure_column(db, 'images', 'storage_kind', 'TEXT')
    ensure_column(db, 'images', 'storage_path', 'TEXT')
    ensure_column(db, 'images', 'sha256', 'TEXT')
    ensure_column(db, 'images', 'width', 'INTEGER')
    ensure_column(db, 'images', 'height', 'INTEGER')
    ensure_column(db, 'images', 'source_id', 'INTEGER REFERENCES sources(id)')
    ensure_images_support_map_type(db)
    ensure_column(db, 'maps', 'image_id', 'INTEGER REFERENCES images(id)')
    ensure_column(db, 'kits', 'category_family', 'TEXT')
    ensure_column(db, 'kits', 'category_subject', 'TEXT')
    ensure_column(db, 'kits', 'thumbnail_url', 'TEXT')
    ensure_column(db, 'kits', 'thumbnail_source_url', 'TEXT')
    ensure_column(db, 'kits', 'thumbnail_fetched_at', 'TEXT')
    ensure_column(db, 'image_regions', 'pixel_x', 'REAL')
    ensure_column(db, 'image_regions', 'pixel_y', 'REAL')
    ensure_column(db, 'image_regions', 'pixel_width', 'REAL')
    ensure_column(db, 'image_regions', 'pixel_height', 'REAL')
    ensure_column(db, 'image_regions', 'object_name', 'TEXT')
    ensure_column(db, 'image_regions', 'object_class', 'TEXT')
    ensure_column(db, 'image_regions', 'color', 'TEXT')
    ensure_column(db, 'image_regions', 'properties_json', 'TEXT')
    ensure_column(db, 'image_regions', 'entity_type', 'TEXT')
    ensure_column(db, 'image_regions', 'entity_id', 'INTEGER')
    ensure_column(db, 'image_regions', 'source_extract_id', 'INTEGER REFERENCES source_extracts(id)')
    ensure_column(db, 'image_regions', 'updated_at', 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
    repair_broken_image_foreign_keys(db)
    db.executescript("""
    CREATE INDEX IF NOT EXISTS idx_sources_type        ON sources(source_type);
    CREATE INDEX IF NOT EXISTS idx_sources_date        ON sources(source_date);
    CREATE INDEX IF NOT EXISTS idx_source_extracts_src ON source_extracts(source_id);
    CREATE INDEX IF NOT EXISTS idx_kits_category_family ON kits(category_family);
    CREATE INDEX IF NOT EXISTS idx_kits_category_subject ON kits(category_subject);
    CREATE INDEX IF NOT EXISTS idx_images_code         ON images(image_code);
    CREATE INDEX IF NOT EXISTS idx_images_title        ON images(title);
    CREATE INDEX IF NOT EXISTS idx_images_source_id    ON images(source_id);
    CREATE INDEX IF NOT EXISTS idx_image_families_primary ON image_families(primary_image_id);
    CREATE INDEX IF NOT EXISTS idx_image_family_members_family ON image_family_members(family_id);
    CREATE INDEX IF NOT EXISTS idx_image_family_members_image ON image_family_members(image_id);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_image_family_members_image_unique ON image_family_members(image_id);
    CREATE INDEX IF NOT EXISTS idx_image_regions_image   ON image_regions(image_id);
    CREATE INDEX IF NOT EXISTS idx_image_regions_entity  ON image_regions(entity_type, entity_id);
    CREATE INDEX IF NOT EXISTS idx_image_regions_extract ON image_regions(source_extract_id);
    CREATE INDEX IF NOT EXISTS idx_image_region_history_region ON image_region_history(region_id);
    CREATE INDEX IF NOT EXISTS idx_claims_subject      ON claims(subject_type, subject_id);
    CREATE INDEX IF NOT EXISTS idx_claims_status       ON claims(status);
    CREATE INDEX IF NOT EXISTS idx_claim_evidence_claim ON claim_evidence(claim_id);
    CREATE INDEX IF NOT EXISTS idx_claim_evidence_target ON claim_evidence(evidence_type, evidence_id);
    CREATE INDEX IF NOT EXISTS idx_placement_positions_placement ON placement_positions(placement_id);
    CREATE INDEX IF NOT EXISTS idx_placement_positions_map ON placement_positions(map_id);
    CREATE INDEX IF NOT EXISTS idx_placement_positions_current ON placement_positions(placement_id, map_id, is_current);
    """)


def init_db():
    """Create a working local database from schema.sql, then apply compatibility bridges."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    with open(SCHEMA) as f:
        db.executescript(f.read())
    ensure_research_bootstrap(db)
    db.executescript('''
    CREATE TABLE IF NOT EXISTS kit_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kit_id INTEGER NOT NULL,
        changed_at TEXT NOT NULL DEFAULT (datetime('now')),
        changed_by TEXT,
        change_type TEXT,
        prev_values TEXT,
        new_values TEXT,
        reason TEXT
    );
    ''')
    db.commit()
    db.close()
    print(f"Database ready at {DB_PATH}")
