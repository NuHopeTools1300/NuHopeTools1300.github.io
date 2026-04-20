"""
ILM Van Nuys Kit-Bash Research Platform
Flask backend — Phase 1
"""

import sqlite3
import os
import hashlib
from flask import Flask, g, jsonify, request, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from functools import wraps
import json

app = Flask(__name__)
CORS(app)   # allow GitHub Pages (or any origin) to call this API


@app.after_request
def add_local_browser_cors_headers(response):
    # Browsers may preflight localhost/private-network requests from file:// or
    # other non-standard local origins and require this explicit opt-in.
    if request.headers.get('Access-Control-Request-Private-Network') == 'true':
        response.headers['Access-Control-Allow-Private-Network'] = 'true'
    return response

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
DB_PATH     = os.path.join(BASE_DIR, 'data', 'ilm1300.db')
SCHEMA      = os.path.join(BASE_DIR, 'schema.sql')
UPLOAD_DIR  = os.path.join(BASE_DIR, 'data', 'uploads')
ALLOWED_EXT = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'tif', 'tiff'}

app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100 MB


# ── DATABASE CONNECTION ───────────────────────────────────────────

def get_db():
    """Return a database connection for the current request context."""
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row      # rows behave like dicts
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA journal_mode = WAL")
    return g.db

@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


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


def to_int(value):
    if value in (None, ''):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def to_float(value):
    if value in (None, ''):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def json_text(value):
    if value in (None, ''):
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value

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


# ── HELPERS ───────────────────────────────────────────────────────

def rows_to_list(rows):
    return [dict(r) for r in rows]

def ok(data=None, **kwargs):
    payload = {'ok': True}
    if data is not None:
        payload['data'] = data
    payload.update(kwargs)
    return jsonify(payload)

def err(message, status=400):
    return jsonify({'ok': False, 'error': message}), status

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXT


# Simple admin API key decorator. If ADMIN_API_KEY env var is set,
# requests that modify data must provide the same key in `X-API-Key` header
ADMIN_API_KEY = os.environ.get('ADMIN_API_KEY')
def require_admin(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if ADMIN_API_KEY:
            # allow explicit API key
            key = request.headers.get('X-API-Key') or request.args.get('api_key')
            if key == ADMIN_API_KEY:
                return f(*args, **kwargs)
            # allow local admin header if request comes from localhost or ALLOW_LOCAL_ADMIN env var is set
            local_override = request.headers.get('X-Admin-Local') == '1' or request.args.get('admin_local') == '1'
            remote = request.remote_addr or ''
            if local_override and (remote.startswith('127.') or remote == '::1' or os.environ.get('ALLOW_LOCAL_ADMIN') == '1'):
                return f(*args, **kwargs)
            return err('Unauthorized', 401)
        return f(*args, **kwargs)
    return wrapper


def record_kit_history(db, kit_id, change_type, prev_values=None, new_values=None, changed_by=None, reason=None):
    db.execute("""
        INSERT INTO kit_history (kit_id, changed_by, change_type, prev_values, new_values, reason)
        VALUES (?,?,?,?,?,?)
    """, (
        kit_id, changed_by, change_type,
        json.dumps(prev_values) if prev_values is not None else None,
        json.dumps(new_values) if new_values is not None else None,
        reason
    ))
    db.commit()


def record_image_region_history(db, region_id, action, snapshot=None, changed_by=None, reason=None):
    db.execute("""
        INSERT INTO image_region_history (region_id, action, snapshot_json, changed_by, reason)
        VALUES (?,?,?,?,?)
    """, (
        region_id,
        action,
        json.dumps(snapshot, ensure_ascii=False) if snapshot is not None else None,
        changed_by,
        reason
    ))
    db.commit()


def rows_for_placement_positions(db, placement_id=None, map_id=None, status=None, position_id=None):
    sql = """
        SELECT pp.*,
               mp.name AS map_name,
               mp.version AS map_version,
               c.handle AS attributed_handle
        FROM placement_positions pp
        JOIN maps mp ON mp.id = pp.map_id
        LEFT JOIN contributors c ON c.id = pp.attributed_to
        WHERE 1=1
    """
    params = []
    if position_id is not None:
        sql += " AND pp.id=?"
        params.append(position_id)
    if placement_id is not None:
        sql += " AND pp.placement_id=?"
        params.append(placement_id)
    if map_id is not None:
        sql += " AND pp.map_id=?"
        params.append(map_id)
    if status:
        sql += " AND pp.status=?"
        params.append(status)
    sql += " ORDER BY pp.is_current DESC, pp.created_at DESC, pp.id DESC"
    return rows_to_list(db.execute(sql, params).fetchall())


def set_current_position(db, placement_id, map_id, position_id):
    db.execute(
        "UPDATE placement_positions SET is_current=0 WHERE placement_id=? AND map_id=? AND id<>?",
        (placement_id, map_id, position_id)
    )
    db.execute(
        "UPDATE placement_positions SET is_current=1, status='active' WHERE id=?",
        (position_id,)
    )


def normalize_tags(tags):
    if isinstance(tags, str):
        return [t.strip() for t in tags.split(',') if t.strip()]
    return tags or []


def to_bool_int(value, default=0):
    if value in (None, ''):
        return default
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if int(value) else 0
    text = str(value).strip().lower()
    if text in ('1', 'true', 'yes', 'y', 'on'):
        return 1
    if text in ('0', 'false', 'no', 'n', 'off'):
        return 0
    return default


def set_family_primary_image(db, family_id, image_id):
    db.execute(
        "UPDATE image_families SET primary_image_id=? WHERE id=?",
        (image_id, family_id)
    )
    db.execute(
        "UPDATE image_family_members SET is_primary=CASE WHEN image_id=? THEN 1 ELSE 0 END WHERE family_id=?",
        (image_id, family_id)
    )
    db.execute(
        """
        UPDATE image_family_members
        SET relation_type=CASE
            WHEN image_id=? AND relation_type='variant' THEN 'primary'
            WHEN image_id!=? AND relation_type='primary' THEN 'variant'
            ELSE relation_type
        END
        WHERE family_id=?
        """,
        (image_id, image_id, family_id)
    )


def ensure_family_member(db, family_id, image_id, relation_type='variant', sort_order=0,
                         is_primary=0, is_hidden_in_library=0, coverage_role=None, notes=None):
    existing = db.execute(
        "SELECT * FROM image_family_members WHERE family_id=? AND image_id=?",
        (family_id, image_id)
    ).fetchone()
    if existing:
        return dict(existing)
    cur = db.execute("""
        INSERT INTO image_family_members
            (family_id, image_id, relation_type, sort_order, is_primary, is_hidden_in_library, coverage_role, notes)
        VALUES (?,?,?,?,?,?,?,?)
    """, (
        family_id, image_id, relation_type, sort_order, is_primary,
        is_hidden_in_library, coverage_role, notes
    ))
    row = db.execute("SELECT * FROM image_family_members WHERE id=?", (cur.lastrowid,)).fetchone()
    return dict(row) if row else None


def detach_image_from_family(db, image_id):
    existing = db.execute(
        "SELECT * FROM image_family_members WHERE image_id=?",
        (image_id,)
    ).fetchone()
    if not existing:
        return
    family_id = existing['family_id']
    was_primary = bool(existing['is_primary'])
    db.execute("DELETE FROM image_family_members WHERE id=?", (existing['id'],))
    remaining = rows_to_list(db.execute(
        "SELECT * FROM image_family_members WHERE family_id=? ORDER BY is_primary DESC, sort_order ASC, id ASC",
        (family_id,)
    ).fetchall())
    if not remaining:
        db.execute("UPDATE image_families SET primary_image_id=NULL WHERE id=?", (family_id,))
    elif was_primary:
        set_family_primary_image(db, family_id, remaining[0]['image_id'])


def get_image_family_membership(db, image_id):
    row = db.execute(
        "SELECT * FROM image_family_members WHERE image_id=?",
        (image_id,)
    ).fetchone()
    return dict(row) if row else None


def get_image_family_map(db, image_ids):
    ids = [to_int(v) for v in image_ids if to_int(v) is not None]
    if not ids:
        return {}
    placeholders = ','.join('?' for _ in ids)
    family_rows = rows_to_list(db.execute(f"""
        SELECT
            m.image_id,
            m.id AS family_member_id,
            m.family_id,
            m.relation_type,
            m.sort_order,
            m.is_primary,
            m.is_hidden_in_library,
            m.coverage_role,
            m.notes AS family_member_notes,
            f.title AS family_title,
            f.family_type,
            f.primary_image_id,
            (
                SELECT COUNT(*)
                FROM image_family_members fm2
                WHERE fm2.family_id = f.id
            ) AS family_variant_count
        FROM image_family_members m
        JOIN image_families f ON f.id = m.family_id
        WHERE m.image_id IN ({placeholders})
    """, ids).fetchall())
    return {row['image_id']: row for row in family_rows}


def get_image_family_payload(db, family_id):
    family = db.execute(
        "SELECT * FROM image_families WHERE id=?",
        (family_id,)
    ).fetchone()
    if not family:
        return None
    members = rows_to_list(db.execute("""
        SELECT
            m.*,
            i.title,
            i.image_code,
            i.filename,
            i.url,
            i.storage_path,
            i.image_type,
            i.date_taken,
            i.source,
            i.source_id,
            s.title AS source_title
        FROM image_family_members m
        JOIN images i ON i.id = m.image_id
        LEFT JOIN sources s ON s.id = i.source_id
        WHERE m.family_id=?
        ORDER BY m.is_primary DESC, m.sort_order ASC, m.id ASC
    """, (family_id,)).fetchall())
    payload = dict(family)
    payload['members'] = members
    payload['variant_count'] = len(members)
    return payload


def create_image_v2(db):
    """Richer image creation with stable metadata and source linkage."""
    if request.content_type and 'multipart/form-data' in request.content_type:
        f = request.files.get('file')
        if not f or not allowed_file(f.filename):
            return err("No valid image file provided")
        data = request.form
        raw = f.read()
        ext = f.filename.rsplit('.', 1)[1].lower()
        digest_full = hashlib.sha256(raw).hexdigest()
        digest = digest_full[:16]
        filename = f"{digest}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(filepath):
            with open(filepath, 'wb') as out:
                out.write(raw)
        url = f"/uploads/{filename}"
        title = data.get('title') or f.filename
        storage_kind = data.get('storage_kind') or 'upload'
        storage_path = data.get('storage_path') or filepath
        sha256 = data.get('sha256') or digest_full
    else:
        data = request.json or {}
        filename = data.get('filename', '')
        url = data.get('url', '')
        title = data.get('title') or filename or url
        storage_kind = data.get('storage_kind') or ('drive' if data.get('drive_id') else ('url' if url else 'other'))
        storage_path = data.get('storage_path')
        sha256 = data.get('sha256')

    cur = db.execute("""
        INSERT INTO images
            (filename, title, image_code, caption, drive_id, url,
             storage_kind, storage_path, sha256, width, height,
             image_type, date_taken, source, source_id, notes, attributed_to)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        filename, title, data.get('image_code'), data.get('caption'),
        data.get('drive_id'), url,
        storage_kind, storage_path, sha256, to_int(data.get('width')), to_int(data.get('height')),
        data.get('image_type', 'other'),
        data.get('date_taken'), data.get('source'), to_int(data.get('source_id')),
        data.get('notes'), data.get('attributed_to')
    ))
    image_id = cur.lastrowid

    for tag in normalize_tags(data.get('tags', '')):
        db.execute("INSERT OR IGNORE INTO image_tags (image_id, tag) VALUES (?,?)",
                   (image_id, tag))

    family_id = to_int(data.get('family_id'))
    if family_id:
        ensure_family_member(
            db,
            family_id,
            image_id,
            relation_type=data.get('relation_type') or ('primary' if to_bool_int(data.get('is_primary')) else 'variant'),
            sort_order=to_int(data.get('sort_order')) or 0,
            is_primary=to_bool_int(data.get('is_primary')),
            is_hidden_in_library=to_bool_int(data.get('is_hidden_in_library')),
            coverage_role=data.get('coverage_role'),
            notes=data.get('family_member_notes')
        )
        if to_bool_int(data.get('is_primary')):
            set_family_primary_image(db, family_id, image_id)

    db.commit()
    return ok(id=image_id, url=url), 201


def update_image_v2(db, image_id):
    """Update richer image metadata and tags."""
    data = request.json or {}
    db.execute("""
        UPDATE images SET
            title=?, image_code=?, caption=?, image_type=?, date_taken=?, source=?,
            source_id=?, drive_id=?, url=?, storage_kind=?, storage_path=?, sha256=?,
            width=?, height=?, notes=?
        WHERE id=?
    """, (
        data.get('title'), data.get('image_code'), data.get('caption'),
        data.get('image_type'), data.get('date_taken'), data.get('source'),
        to_int(data.get('source_id')), data.get('drive_id'), data.get('url'),
        data.get('storage_kind'), data.get('storage_path'), data.get('sha256'),
        to_int(data.get('width')), to_int(data.get('height')), data.get('notes'),
        image_id
    ))
    if 'tags' in data:
        db.execute("DELETE FROM image_tags WHERE image_id=?", (image_id,))
        for tag in normalize_tags(data.get('tags', '')):
            db.execute("INSERT OR IGNORE INTO image_tags (image_id, tag) VALUES (?,?)",
                       (image_id, tag))
    if 'family_id' in data:
        family_id = to_int(data.get('family_id'))
        existing = db.execute(
            "SELECT * FROM image_family_members WHERE image_id=?",
            (image_id,)
        ).fetchone()
        if family_id is None:
            detach_image_from_family(db, image_id)
        else:
            if existing and existing['family_id'] != family_id:
                detach_image_from_family(db, image_id)
                existing = None
            if not existing:
                ensure_family_member(
                    db,
                    family_id,
                    image_id,
                    relation_type=data.get('relation_type') or ('primary' if to_bool_int(data.get('is_primary')) else 'variant'),
                    sort_order=to_int(data.get('sort_order')) or 0,
                    is_primary=to_bool_int(data.get('is_primary')),
                    is_hidden_in_library=to_bool_int(data.get('is_hidden_in_library')),
                    coverage_role=data.get('coverage_role'),
                    notes=data.get('family_member_notes')
                )
            else:
                db.execute("""
                    UPDATE image_family_members SET
                        relation_type=?,
                        sort_order=?,
                        is_primary=?,
                        is_hidden_in_library=?,
                        coverage_role=?,
                        notes=?
                    WHERE id=?
                """, (
                    data.get('relation_type') or existing['relation_type'],
                    to_int(data.get('sort_order')) if 'sort_order' in data else existing['sort_order'],
                    to_bool_int(data.get('is_primary'), existing['is_primary']) if 'is_primary' in data else existing['is_primary'],
                    to_bool_int(data.get('is_hidden_in_library'), existing['is_hidden_in_library']) if 'is_hidden_in_library' in data else existing['is_hidden_in_library'],
                    data.get('coverage_role') if 'coverage_role' in data else existing['coverage_role'],
                    data.get('family_member_notes') if 'family_member_notes' in data else existing['notes'],
                    existing['id']
                ))
            if to_bool_int(data.get('is_primary')) or data.get('relation_type') == 'primary':
                set_family_primary_image(db, family_id, image_id)
    db.commit()
    return ok()


# ── STATIC FILES ─────────────────────────────────────────────────
# Serve uploaded images. The tools themselves are served by GitHub Pages
# (or directly as files); this only covers locally-uploaded images.

@app.get('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


# ── HEALTH ────────────────────────────────────────────────────────

@app.get('/api/health')
def health():
    db = get_db()
    tables = rows_to_list(db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall())
    counts = {}
    for t in tables:
        n = t['name']
        counts[n] = db.execute(f"SELECT COUNT(*) as c FROM {n}").fetchone()['c']
    return ok(tables=[t['name'] for t in tables], counts=counts)


# ── KITS ─────────────────────────────────────────────────────────

@app.get('/api/kits')
def list_kits():
    db    = get_db()
    q     = request.args.get('q', '').strip()
    brand = request.args.get('brand', '').strip()
    family = request.args.get('category_family', '').strip()
    subject = request.args.get('category_subject', '').strip()

    sql    = "SELECT * FROM kits WHERE 1=1"
    params = []
    if q:
        sql += " AND (name LIKE ? OR brand LIKE ? OR serial_number LIKE ? OR category_family LIKE ? OR category_subject LIKE ?)"
        params += [f'%{q}%', f'%{q}%', f'%{q}%', f'%{q}%', f'%{q}%']
    if brand:
        sql += " AND brand = ?"
        params.append(brand)
    if family:
        sql += " AND category_family = ?"
        params.append(family)
    if subject:
        sql += " AND category_subject = ?"
        params.append(subject)
    sql += " ORDER BY brand, name"

    rows = db.execute(sql, params).fetchall()
    return ok(rows_to_list(rows), count=len(rows))

@app.get('/api/kits/<int:kit_id>')
def get_kit(kit_id):
    db  = get_db()
    kit = db.execute("SELECT * FROM kits WHERE id=?", (kit_id,)).fetchone()
    if not kit:
        return err('Kit not found', 404)
    parts = rows_to_list(db.execute(
        "SELECT * FROM parts WHERE kit_id=? ORDER BY part_number", (kit_id,)
    ).fetchall())
    # external reference numbers (Coffman etc.)
    references = rows_to_list(db.execute(
        "SELECT * FROM kit_references WHERE kit_id=? ORDER BY system", (kit_id,)
    ).fetchall())
    # which models use parts from this kit
    models = rows_to_list(db.execute("""
        SELECT DISTINCT m.id, m.name, m.slug, m.film
        FROM models m
        JOIN placements p ON p.model_id = m.id
        JOIN parts pt     ON pt.id = p.part_id
        WHERE pt.kit_id = ?
        ORDER BY m.name
    """, (kit_id,)).fetchall())
    # images linked to this kit
    images = rows_to_list(db.execute("""
        SELECT i.*, il.annotation
        FROM images i
        JOIN image_links il ON il.image_id = i.id
        WHERE il.entity_type = 'kit' AND il.entity_id = ?
        ORDER BY i.date_taken
    """, (kit_id,)).fetchall())
    return ok(kit=dict(kit), parts=parts, references=references,
              used_on_models=models, images=images)

@app.post('/api/kits')
@require_admin
def create_kit():
    # BUG FIX: removed coffman_number/base/suffix and confirmed_in_image
    # (columns removed from schema — now handled by kit_references table)
    data    = request.json or {}
    missing = [f for f in ('brand', 'name') if not data.get(f)]
    if missing:
        return err(f"Missing required fields: {', '.join(missing)}")
    db  = get_db()
    cur = db.execute("""
        INSERT INTO kits
            (brand, scale, name, serial_number, category_family, category_subject,
             scalemates_url, scans_url, instructions_url,
             availability, notes, attributed_to)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data['brand'], data.get('scale'), data['name'], data.get('serial_number'),
        data.get('category_family'), data.get('category_subject'),
        data.get('scalemates_url'), data.get('scans_url'), data.get('instructions_url'),
        data.get('availability', 'unknown'), data.get('notes'), data.get('attributed_to')
    ))
    db.commit()
    # record history for creation
    try:
        record_kit_history(db, cur.lastrowid, 'create', prev_values=None, new_values=data, changed_by=data.get('changed_by'))
    except Exception:
        pass
    return ok(id=cur.lastrowid), 201

@app.put('/api/kits/<int:kit_id>')
@require_admin
def update_kit(kit_id):
    data = request.json or {}
    db   = get_db()
    # capture previous values for audit
    prev = db.execute("SELECT * FROM kits WHERE id=?", (kit_id,)).fetchone()
    prev_dict = dict(prev) if prev else None
    db.execute("""
        UPDATE kits SET
            brand=?, scale=?, name=?, serial_number=?, category_family=?, category_subject=?,
            scalemates_url=?, scans_url=?, instructions_url=?,
            availability=?, notes=?, attributed_to=?
        WHERE id=?
    """, (
        data.get('brand'), data.get('scale'), data.get('name'), data.get('serial_number'),
        data.get('category_family'), data.get('category_subject'),
        data.get('scalemates_url'), data.get('scans_url'), data.get('instructions_url'),
        data.get('availability', 'unknown'), data.get('notes'), data.get('attributed_to'),
        kit_id
    ))
    db.commit()
    try:
        # new values snapshot
        new = db.execute("SELECT * FROM kits WHERE id=?", (kit_id,)).fetchone()
        new_dict = dict(new) if new else None
        record_kit_history(db, kit_id, 'update', prev_values=prev_dict, new_values=new_dict, changed_by=data.get('changed_by'), reason=data.get('reason'))
    except Exception:
        pass
    return ok()


# ── KIT REFERENCES ────────────────────────────────────────────────
# Coffman numbers and any other external numbering systems.

@app.get('/api/kits/<int:kit_id>/references')
def list_kit_references(kit_id):
    db   = get_db()
    rows = db.execute(
        "SELECT * FROM kit_references WHERE kit_id=? ORDER BY system", (kit_id,)
    ).fetchall()
    return ok(rows_to_list(rows))

@app.post('/api/kits/<int:kit_id>/references')
def create_kit_reference(kit_id):
    data    = request.json or {}
    missing = [f for f in ('system', 'value') if not data.get(f)]
    if missing:
        return err(f"Missing required fields: {', '.join(missing)}")
    db  = get_db()
    try:
        cur = db.execute("""
            INSERT INTO kit_references (kit_id, system, value, notes)
            VALUES (?,?,?,?)
        """, (kit_id, data['system'], data['value'], data.get('notes')))
        db.commit()
        return ok(id=cur.lastrowid), 201
    except sqlite3.IntegrityError:
        return err(f"Reference for system '{data['system']}' already exists on this kit")


@app.delete('/api/kits/<int:kit_id>/references/<int:ref_id>')
def delete_kit_reference(kit_id, ref_id):
    db = get_db()
    db.execute("DELETE FROM kit_references WHERE id=? AND kit_id=?", (ref_id, kit_id))
    db.commit()
    return ok()


# ── PARTS ─────────────────────────────────────────────────────────

@app.get('/api/parts')
def list_parts():
    db     = get_db()
    kit_id = request.args.get('kit_id')
    q      = request.args.get('q', '').strip()

    sql    = "SELECT p.*, k.brand, k.name as kit_name FROM parts p JOIN kits k ON k.id=p.kit_id WHERE 1=1"
    params = []
    if kit_id:
        sql += " AND p.kit_id=?"
        params.append(kit_id)
    if q:
        sql += " AND (p.part_number LIKE ? OR p.part_label LIKE ?)"
        params += [f'%{q}%', f'%{q}%']
    sql += " ORDER BY k.brand, k.name, p.part_number"

    rows = db.execute(sql, params).fetchall()
    return ok(rows_to_list(rows), count=len(rows))

@app.get('/api/parts/<int:part_id>')
def get_part(part_id):
    db   = get_db()
    part = db.execute("""
        SELECT p.*, k.brand, k.name as kit_name
        FROM parts p JOIN kits k ON k.id = p.kit_id
        WHERE p.id=?
    """, (part_id,)).fetchone()
    if not part:
        return err('Part not found', 404)
    placements = rows_to_list(db.execute("""
        SELECT pl.*, m.name as model_name, m.slug as model_slug
        FROM placements pl JOIN models m ON m.id = pl.model_id
        WHERE pl.part_id = ?
    """, (part_id,)).fetchall())
    images = rows_to_list(db.execute("""
        SELECT i.*, il.annotation
        FROM images i
        JOIN image_links il ON il.image_id = i.id
        WHERE il.entity_type = 'part' AND il.entity_id = ?
        ORDER BY i.date_taken
    """, (part_id,)).fetchall())
    files = rows_to_list(db.execute(
        "SELECT * FROM part_files WHERE part_id=? ORDER BY file_type", (part_id,)
    ).fetchall())
    return ok(part=dict(part), placements=placements, images=images, files=files)

@app.post('/api/parts')
@require_admin
def create_part():
    data    = request.json or {}
    missing = [f for f in ('kit_id', 'part_number') if not data.get(f)]
    if missing:
        return err(f"Missing required fields: {', '.join(missing)}")
    db  = get_db()
    cur = db.execute("""
        INSERT INTO parts (kit_id, part_number, part_label, notes, attributed_to)
        VALUES (?,?,?,?,?)
    """, (data['kit_id'], data['part_number'],
          data.get('part_label'), data.get('notes'), data.get('attributed_to')))
    db.commit()
    return ok(id=cur.lastrowid), 201

@app.put('/api/parts/<int:part_id>')
@require_admin
def update_part(part_id):
    data = request.json or {}
    db   = get_db()
    db.execute("""
        UPDATE parts SET part_number=?, part_label=?, notes=?, attributed_to=?
        WHERE id=?
    """, (data.get('part_number'), data.get('part_label'),
          data.get('notes'), data.get('attributed_to'), part_id))
    db.commit()
    return ok()


# ── PART FILES ────────────────────────────────────────────────────

@app.post('/api/parts/<int:part_id>/files')
@require_admin
def create_part_file(part_id):
    data    = request.json or {}
    missing = [f for f in ('file_type', 'url') if not data.get(f)]
    if missing:
        return err(f"Missing required fields: {', '.join(missing)}")
    db  = get_db()
    cur = db.execute("""
        INSERT INTO part_files (part_id, file_type, url, source, notes, attributed_to)
        VALUES (?,?,?,?,?,?)
    """, (part_id, data['file_type'], data['url'],
          data.get('source'), data.get('notes'), data.get('attributed_to')))
    db.commit()
    return ok(id=cur.lastrowid), 201

@app.delete('/api/parts/<int:part_id>/files/<int:file_id>')
@require_admin
def delete_part_file(part_id, file_id):
    db = get_db()
    db.execute("DELETE FROM part_files WHERE id=? AND part_id=?", (file_id, part_id))
    db.commit()
    return ok()


# ── MODELS ────────────────────────────────────────────────────────

@app.get('/api/models')
def list_models():
    db   = get_db()
    rows = db.execute("SELECT * FROM models ORDER BY film, name").fetchall()
    return ok(rows_to_list(rows))

@app.get('/api/models/<slug>')
def get_model(slug):
    db    = get_db()
    model = db.execute("SELECT * FROM models WHERE slug=?", (slug,)).fetchone()
    if not model:
        return err('Model not found', 404)
    maps = rows_to_list(db.execute(
        "SELECT * FROM maps WHERE model_id=? ORDER BY name", (model['id'],)
    ).fetchall())
    kit_summary = rows_to_list(db.execute("""
        SELECT k.id, k.brand, k.name as kit_name, k.scale,
               COUNT(DISTINCT pt.id) as part_count,
               SUM(pl.copy_count)    as total_copies
        FROM placements pl
        JOIN parts pt ON pt.id = pl.part_id
        JOIN kits  k  ON k.id  = pt.kit_id
        WHERE pl.model_id = ?
        GROUP BY k.id
        ORDER BY total_copies DESC
    """, (model['id'],)).fetchall())
    images = rows_to_list(db.execute("""
        SELECT i.*, il.annotation
        FROM images i
        JOIN image_links il ON il.image_id = i.id
        WHERE il.entity_type = 'model' AND il.entity_id = ?
        ORDER BY i.date_taken
    """, (model['id'],)).fetchall())
    return ok(model=dict(model), maps=maps, kit_summary=kit_summary, images=images)

@app.post('/api/models')
def create_model():
    data    = request.json or {}
    missing = [f for f in ('name', 'slug') if not data.get(f)]
    if missing:
        return err(f"Missing required fields: {', '.join(missing)}")
    db  = get_db()
    cur = db.execute("""
        INSERT INTO models (name, slug, film, scale_approx, notes)
        VALUES (?,?,?,?,?)
    """, (data['name'], data['slug'], data.get('film'),
          data.get('scale_approx'), data.get('notes')))
    db.commit()
    return ok(id=cur.lastrowid), 201


# ── MAPS ──────────────────────────────────────────────────────────

def map_select_sql():
    return """
        SELECT mp.*,
               i.title AS image_title,
               i.image_code AS image_code,
               i.url AS image_url,
               i.storage_path AS image_storage_path,
               i.storage_kind AS image_storage_kind,
               i.filename AS image_filename,
               i.width AS image_width,
               i.height AS image_height,
               i.image_type AS image_type
        FROM maps mp
        LEFT JOIN images i ON i.id = mp.image_id
    """

@app.get('/api/maps')
def list_maps():
    db       = get_db()
    model_id = request.args.get('model_id')
    if model_id:
        rows = db.execute(
            f"{map_select_sql()} WHERE mp.model_id=? ORDER BY mp.name", (model_id,)
        ).fetchall()
    else:
        rows = db.execute(f"{map_select_sql()} ORDER BY mp.name").fetchall()
    return ok(rows_to_list(rows))

@app.post('/api/maps')
def create_map():
    data    = request.json or {}
    missing = [f for f in ('model_id', 'name') if not data.get(f)]
    if missing:
        return err(f"Missing required fields: {', '.join(missing)}")
    db  = get_db()
    cur = db.execute("""
        INSERT INTO maps (model_id, name, version, image_id, url, map_date, attributed_to, notes)
        VALUES (?,?,?,?,?,?,?,?)
    """, (data['model_id'], data['name'], data.get('version'),
          to_int(data.get('image_id')),
          data.get('url'), data.get('map_date'),
          data.get('attributed_to'), data.get('notes')))
    db.commit()
    return ok(id=cur.lastrowid), 201


@app.put('/api/maps/<int:map_id>')
@require_admin
def update_map(map_id):
    data = request.json or {}
    db = get_db()
    old = db.execute("SELECT * FROM maps WHERE id=?", (map_id,)).fetchone()
    if not old:
        return err('Map not found', 404)
    merged = {
        'model_id': to_int(data.get('model_id')) if 'model_id' in data else old['model_id'],
        'name': data.get('name', old['name']),
        'version': data.get('version', old['version']),
        'image_id': to_int(data.get('image_id')) if 'image_id' in data else old['image_id'],
        'url': data.get('url', old['url']),
        'map_date': data.get('map_date', old['map_date']),
        'attributed_to': to_int(data.get('attributed_to')) if 'attributed_to' in data else old['attributed_to'],
        'notes': data.get('notes', old['notes'])
    }
    if not merged['model_id']:
        return err('model_id is required')
    if not merged['name']:
        return err('name is required')
    db.execute("""
        UPDATE maps SET
            model_id=?, name=?, version=?, image_id=?, url=?, map_date=?, attributed_to=?, notes=?
        WHERE id=?
    """, (
        merged['model_id'], merged['name'], merged['version'], merged['image_id'],
        merged['url'], merged['map_date'], merged['attributed_to'], merged['notes'],
        map_id
    ))
    db.commit()
    return ok()


@app.get('/api/kits/<int:kit_id>/history')
def get_kit_history(kit_id):
    db = get_db()
    rows = db.execute("SELECT * FROM kit_history WHERE kit_id=? ORDER BY changed_at DESC", (kit_id,)).fetchall()
    return ok(rows_to_list(rows))


# ── PLACEMENTS ────────────────────────────────────────────────────

@app.get('/api/placements')
def list_placements():
    db       = get_db()
    model_id = request.args.get('model_id')
    kit_id   = request.args.get('kit_id')
    map_id   = request.args.get('map_id')
    conf     = request.args.get('confidence')

    sql = """
        SELECT pl.*,
               m.name  as model_name,
               mp.name as map_name,
               pt.part_number, pt.part_label,
               k.brand, k.name as kit_name,
               ca.name as cast_assembly_name,
               c.handle as attributed_handle
        FROM placements pl
        JOIN models m            ON m.id  = pl.model_id
        LEFT JOIN maps mp        ON mp.id = pl.map_id
        LEFT JOIN parts pt       ON pt.id = pl.part_id
        LEFT JOIN kits k         ON k.id  = COALESCE(pt.kit_id, pl.kit_id)
        LEFT JOIN cast_assemblies ca ON ca.id = pl.cast_assembly_id
        LEFT JOIN contributors c     ON c.id  = pl.attributed_to
        WHERE 1=1
    """
    params = []
    if model_id:
        sql += " AND pl.model_id=?"
        params.append(model_id)
    if kit_id:
        sql += " AND k.id=?"
        params.append(kit_id)
    if map_id:
        sql += " AND pl.map_id=?"
        params.append(map_id)
    if conf:
        sql += " AND pl.confidence=?"
        params.append(conf)
    sql += " ORDER BY m.name, mp.name, k.brand, pt.part_number"

    rows = rows_to_list(db.execute(sql, params).fetchall())
    if rows:
        placement_ids = [row['id'] for row in rows]
        current_positions = rows_to_list(db.execute(f"""
            SELECT pp.*,
                   mp.name AS map_name,
                   mp.version AS map_version
            FROM placement_positions pp
            JOIN maps mp ON mp.id = pp.map_id
            WHERE pp.is_current=1
              AND pp.placement_id IN ({','.join('?' for _ in placement_ids)})
            ORDER BY pp.created_at DESC, pp.id DESC
        """, placement_ids).fetchall())
        current_by_placement = {}
        for pos in current_positions:
            current_by_placement.setdefault(pos['placement_id'], pos)
        for row in rows:
            row['current_position'] = current_by_placement.get(row['id'])
    return ok(rows, count=len(rows))

@app.get('/api/placements/<int:pl_id>')
def get_placement(pl_id):
    db = get_db()
    pl = db.execute("""
        SELECT pl.*,
               m.name  as model_name,
               mp.name as map_name,
               pt.part_number, pt.part_label,
               k.brand, k.name as kit_name,
               ca.name as cast_assembly_name,
               c.handle as attributed_handle
        FROM placements pl
        JOIN models m            ON m.id  = pl.model_id
        LEFT JOIN maps mp        ON mp.id = pl.map_id
        LEFT JOIN parts pt       ON pt.id = pl.part_id
        LEFT JOIN kits k         ON k.id  = COALESCE(pt.kit_id, pl.kit_id)
        LEFT JOIN cast_assemblies ca ON ca.id = pl.cast_assembly_id
        LEFT JOIN contributors c     ON c.id  = pl.attributed_to
        WHERE pl.id=?
    """, (pl_id,)).fetchone()
    if not pl:
        return err('Placement not found', 404)
    # co-contributors
    contributors = rows_to_list(db.execute("""
        SELECT pc.*, c.handle, c.display_name, c.forum
        FROM placement_contributors pc
        JOIN contributors c ON c.id = pc.contributor_id
        WHERE pc.placement_id=?
    """, (pl_id,)).fetchall())
    # images
    images = rows_to_list(db.execute("""
        SELECT i.*, il.annotation
        FROM images i
        JOIN image_links il ON il.image_id = i.id
        WHERE il.entity_type = 'placement' AND il.entity_id = ?
        ORDER BY i.date_taken
    """, (pl_id,)).fetchall())
    # history
    history = rows_to_list(db.execute("""
        SELECT ph.*, c.handle as changed_by_handle
        FROM placement_history ph
        LEFT JOIN contributors c ON c.id = ph.changed_by
        WHERE ph.placement_id=?
        ORDER BY ph.changed_at DESC
    """, (pl_id,)).fetchall())
    positions = rows_for_placement_positions(db, placement_id=pl_id)
    return ok(placement=dict(pl), contributors=contributors,
              images=images, history=history, positions=positions,
              current_position=next((row for row in positions if row.get('is_current')), None))

@app.post('/api/placements')
@require_admin
def create_placement():
    data = request.json or {}
    if not data.get('model_id'):
        return err("model_id is required")
    # must have exactly one of part_id, cast_assembly_id, kit_id
    set_fields = [f for f in ('part_id', 'cast_assembly_id', 'kit_id') if data.get(f)]
    if len(set_fields) == 0:
        return err("One of part_id, cast_assembly_id, or kit_id is required")
    if len(set_fields) > 1:
        return err("Only one of part_id, cast_assembly_id, or kit_id may be set")
    db  = get_db()
    cur = db.execute("""
        INSERT INTO placements
            (model_id, map_id, part_id, cast_assembly_id, kit_id,
             film_version, location_label, copy_count, confidence,
             modification, notes, source_url, attributed_to)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data['model_id'], data.get('map_id'),
        data.get('part_id'), data.get('cast_assembly_id'), data.get('kit_id'),
        data.get('film_version'),
        data.get('location_label'), data.get('copy_count', 1),
        data.get('confidence', 'confirmed'),
        data.get('modification', 'none'),
        data.get('notes'), data.get('source_url'), data.get('attributed_to')
    ))
    db.commit()
    return ok(id=cur.lastrowid), 201

@app.put('/api/placements/<int:pl_id>')
@require_admin
def update_placement(pl_id):
    data = request.json or {}
    db   = get_db()
    old = db.execute("SELECT * FROM placements WHERE id=?", (pl_id,)).fetchone()
    if not old:
        return err('Placement not found', 404)
    values = {}
    for field in (
        'model_id', 'map_id', 'part_id', 'cast_assembly_id', 'kit_id',
        'film_version', 'location_label', 'copy_count', 'confidence',
        'modification', 'notes', 'source_url', 'attributed_to'
    ):
        if field in data:
            values[field] = data.get(field)
        else:
            values[field] = old[field]

    if not values['model_id']:
        return err("model_id is required")

    if (values['part_id'] != old['part_id'] or
            values['kit_id'] != old['kit_id'] or
            values['confidence'] != old['confidence']):
        db.execute("""
            INSERT INTO placement_history
                (placement_id, changed_by, prev_part_id, prev_kit_id,
                 prev_confidence, prev_notes, reason)
            VALUES (?,?,?,?,?,?,?)
        """, (pl_id, data.get('changed_by'),
              old['part_id'], old['kit_id'],
              old['confidence'], old['notes'],
              data.get('change_reason')))

    set_fields = [f for f in ('part_id', 'cast_assembly_id', 'kit_id') if values.get(f)]
    if len(set_fields) == 0:
        return err("One of part_id, cast_assembly_id, or kit_id is required")
    if len(set_fields) > 1:
        return err("Only one of part_id, cast_assembly_id, or kit_id may be set")

    db.execute("""
        UPDATE placements SET
            model_id=?, map_id=?, part_id=?, cast_assembly_id=?, kit_id=?,
            film_version=?, location_label=?, copy_count=?,
            confidence=?, modification=?, notes=?, source_url=?, attributed_to=?
        WHERE id=?
    """, (
        values['model_id'], values['map_id'], values['part_id'],
        values['cast_assembly_id'], values['kit_id'],
        values['film_version'], values['location_label'],
        values.get('copy_count', 1),
        values.get('confidence', 'confirmed'),
        values.get('modification', 'none'),
        values['notes'], values['source_url'], values['attributed_to'],
        pl_id
    ))
    db.commit()
    return ok()

@app.delete('/api/placements/<int:pl_id>')
@require_admin
def delete_placement(pl_id):
    db = get_db()
    db.execute("DELETE FROM placements WHERE id=?", (pl_id,))
    db.commit()
    return ok()


@app.get('/api/placement_positions')
def list_placement_positions():
    db = get_db()
    placement_id = request.args.get('placement_id')
    map_id = request.args.get('map_id')
    status = request.args.get('status', '').strip() or None
    rows = rows_for_placement_positions(
        db,
        placement_id=to_int(placement_id),
        map_id=to_int(map_id),
        status=status
    )
    return ok(rows, count=len(rows))


@app.get('/api/placement_positions/<int:position_id>')
def get_placement_position(position_id):
    db = get_db()
    rows = rows_for_placement_positions(db, position_id=position_id)
    if not rows:
        return err('Placement position not found', 404)
    return ok(position=rows[0])


@app.post('/api/placement_positions')
@require_admin
def create_placement_position():
    data = request.json or {}
    placement_id = to_int(data.get('placement_id'))
    map_id = to_int(data.get('map_id'))
    if not placement_id:
        return err('placement_id is required')
    if not map_id:
        return err('map_id is required')
    db = get_db()
    placement = db.execute("SELECT id, map_id FROM placements WHERE id=?", (placement_id,)).fetchone()
    if not placement:
        return err('Placement not found', 404)
    if placement['map_id'] and placement['map_id'] != map_id:
        return err('map_id must match the placement map_id when placement.map_id is set')

    cur = db.execute("""
        INSERT INTO placement_positions
            (placement_id, map_id, position_type, x_norm, y_norm, width_norm, height_norm,
             polygon_json, source_kind, status, is_current, supersedes_id,
             confidence, notes, attributed_to)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        placement_id, map_id,
        data.get('position_type', 'point'),
        to_float(data.get('x_norm')), to_float(data.get('y_norm')),
        to_float(data.get('width_norm')), to_float(data.get('height_norm')),
        json_text(data.get('polygon_json')),
        data.get('source_kind', 'manual'),
        data.get('status', 'active'),
        1 if str(data.get('is_current', '1')).lower() not in ('0', 'false', 'no') else 0,
        to_int(data.get('supersedes_id')),
        data.get('confidence', 'probable'),
        data.get('notes'),
        to_int(data.get('attributed_to'))
    ))
    position_id = cur.lastrowid
    if str(data.get('is_current', '1')).lower() not in ('0', 'false', 'no'):
        set_current_position(db, placement_id, map_id, position_id)
        supersedes_id = to_int(data.get('supersedes_id'))
        if supersedes_id:
            db.execute(
                "UPDATE placement_positions SET status='superseded', is_current=0 WHERE id=?",
                (supersedes_id,)
            )
    db.commit()
    return ok(id=position_id), 201


@app.put('/api/placement_positions/<int:position_id>')
@require_admin
def update_placement_position(position_id):
    data = request.json or {}
    db = get_db()
    old = db.execute("SELECT * FROM placement_positions WHERE id=?", (position_id,)).fetchone()
    if not old:
        return err('Placement position not found', 404)
    current = dict(old)
    merged = {
        'placement_id': to_int(data.get('placement_id')) if 'placement_id' in data else current['placement_id'],
        'map_id': to_int(data.get('map_id')) if 'map_id' in data else current['map_id'],
        'position_type': data.get('position_type', current['position_type']),
        'x_norm': to_float(data.get('x_norm')) if 'x_norm' in data else current['x_norm'],
        'y_norm': to_float(data.get('y_norm')) if 'y_norm' in data else current['y_norm'],
        'width_norm': to_float(data.get('width_norm')) if 'width_norm' in data else current['width_norm'],
        'height_norm': to_float(data.get('height_norm')) if 'height_norm' in data else current['height_norm'],
        'polygon_json': json_text(data.get('polygon_json')) if 'polygon_json' in data else current['polygon_json'],
        'source_kind': data.get('source_kind', current['source_kind']),
        'status': data.get('status', current['status']),
        'is_current': 1 if str(data.get('is_current', current['is_current'])).lower() not in ('0', 'false', 'no') else 0,
        'supersedes_id': to_int(data.get('supersedes_id')) if 'supersedes_id' in data else current['supersedes_id'],
        'confidence': data.get('confidence', current['confidence']),
        'notes': data.get('notes', current['notes']),
        'attributed_to': to_int(data.get('attributed_to')) if 'attributed_to' in data else current['attributed_to'],
    }
    placement = db.execute("SELECT id, map_id FROM placements WHERE id=?", (merged['placement_id'],)).fetchone()
    if not placement:
        return err('Placement not found', 404)
    if placement['map_id'] and placement['map_id'] != merged['map_id']:
        return err('map_id must match the placement map_id when placement.map_id is set')

    db.execute("""
        UPDATE placement_positions SET
            placement_id=?, map_id=?, position_type=?, x_norm=?, y_norm=?, width_norm=?, height_norm=?,
            polygon_json=?, source_kind=?, status=?, is_current=?, supersedes_id=?, confidence=?, notes=?, attributed_to=?
        WHERE id=?
    """, (
        merged['placement_id'], merged['map_id'], merged['position_type'],
        merged['x_norm'], merged['y_norm'], merged['width_norm'], merged['height_norm'],
        merged['polygon_json'], merged['source_kind'], merged['status'], merged['is_current'],
        merged['supersedes_id'], merged['confidence'], merged['notes'], merged['attributed_to'],
        position_id
    ))
    if merged['is_current']:
        set_current_position(db, merged['placement_id'], merged['map_id'], position_id)
    db.commit()
    return ok()


@app.delete('/api/placement_positions/<int:position_id>')
@require_admin
def delete_placement_position(position_id):
    db = get_db()
    old = db.execute("SELECT * FROM placement_positions WHERE id=?", (position_id,)).fetchone()
    if not old:
        return err('Placement position not found', 404)
    if old['is_current']:
        replacement = db.execute("""
            SELECT id
            FROM placement_positions
            WHERE placement_id=? AND map_id=? AND id<>? AND status='active'
            ORDER BY created_at DESC, id DESC
            LIMIT 1
        """, (old['placement_id'], old['map_id'], position_id)).fetchone()
        if replacement:
            set_current_position(db, old['placement_id'], old['map_id'], replacement['id'])
    db.execute("DELETE FROM placement_positions WHERE id=?", (position_id,))
    db.commit()
    return ok()


# ── PLACEMENT CONTRIBUTORS ────────────────────────────────────────

@app.post('/api/placements/<int:pl_id>/contributors')
def add_placement_contributor(pl_id):
    data    = request.json or {}
    missing = [f for f in ('contributor_id',) if not data.get(f)]
    if missing:
        return err("contributor_id is required")
    db  = get_db()
    try:
        cur = db.execute("""
            INSERT INTO placement_contributors
                (placement_id, contributor_id, role, notes)
            VALUES (?,?,?,?)
        """, (pl_id, data['contributor_id'],
              data.get('role', 'identifier'), data.get('notes')))
        db.commit()
        return ok(id=cur.lastrowid), 201
    except sqlite3.IntegrityError:
        return err("This contributor is already credited on this placement")

@app.delete('/api/placements/<int:pl_id>/contributors/<int:contrib_id>')
def remove_placement_contributor(pl_id, contrib_id):
    db = get_db()
    db.execute("""
        DELETE FROM placement_contributors
        WHERE placement_id=? AND contributor_id=?
    """, (pl_id, contrib_id))
    db.commit()
    return ok()


# ── CROSS-MODEL CONNECTIONS ───────────────────────────────────────
# The key query: which kits/parts appear on more than one model?

@app.get('/api/connections')
def cross_model_connections():
    """
    Kits (or parts from kits) that appear on more than one model.
    Covers both:
      - part-level placements (part_id → kit via parts table)
      - kit-level placements  (kit_id directly, part not yet identified)
    """
    db   = get_db()
    rows = rows_to_list(db.execute("""
        SELECT k.id as kit_id, k.brand, k.name as kit_name, k.scale,
               COUNT(DISTINCT pl.model_id) as model_count,
               GROUP_CONCAT(DISTINCT m.name ORDER BY m.name) as appears_on
        FROM placements pl
        JOIN kits  k  ON k.id  = COALESCE(
                            (SELECT kit_id FROM parts WHERE id = pl.part_id),
                            pl.kit_id
                         )
        JOIN models m ON m.id  = pl.model_id
        WHERE k.id IS NOT NULL
        GROUP BY k.id
        HAVING model_count > 1
        ORDER BY model_count DESC, k.brand, k.name
    """).fetchall())
    return ok(rows, count=len(rows))


# ── CAST ASSEMBLIES ───────────────────────────────────────────────

@app.get('/api/cast_assemblies')
def list_cast_assemblies():
    db   = get_db()
    rows = rows_to_list(db.execute("""
        SELECT ca.*,
               COUNT(DISTINCT cap.part_id)  as part_count,
               COUNT(DISTINCT pl.model_id)  as used_on_count
        FROM cast_assemblies ca
        LEFT JOIN cast_assembly_parts cap ON cap.cast_assembly_id = ca.id
        LEFT JOIN placements pl           ON pl.cast_assembly_id  = ca.id
        GROUP BY ca.id
        ORDER BY ca.name
    """).fetchall())
    return ok(rows)

@app.get('/api/cast_assemblies/<int:ca_id>')
def get_cast_assembly(ca_id):
    db = get_db()
    ca = db.execute("SELECT * FROM cast_assemblies WHERE id=?", (ca_id,)).fetchone()
    if not ca:
        return err('Cast assembly not found', 404)
    # BUG FIX: removed k.coffman_number (column removed from kits table)
    parts = rows_to_list(db.execute("""
        SELECT cap.notes as usage_notes,
               pt.id as part_id, pt.part_number, pt.part_label,
               k.id as kit_id, k.brand, k.name as kit_name
        FROM cast_assembly_parts cap
        JOIN parts pt ON pt.id = cap.part_id
        JOIN kits  k  ON k.id  = pt.kit_id
        ORDER BY k.brand, pt.part_number
    """, (ca_id,)).fetchall())
    models = rows_to_list(db.execute("""
        SELECT DISTINCT m.name, m.slug, m.film,
               pl.location_label, pl.copy_count, pl.confidence
        FROM placements pl
        JOIN models m ON m.id = pl.model_id
        WHERE pl.cast_assembly_id = ?
    """, (ca_id,)).fetchall())
    images = rows_to_list(db.execute("""
        SELECT i.*, il.annotation
        FROM images i
        JOIN image_links il ON il.image_id = i.id
        WHERE il.entity_type = 'cast_assembly' AND il.entity_id = ?
        ORDER BY i.date_taken
    """, (ca_id,)).fetchall())
    return ok(cast_assembly=dict(ca), component_parts=parts,
              used_on=models, images=images)

@app.post('/api/cast_assemblies')
def create_cast_assembly():
    data = request.json or {}
    if not data.get('name'):
        return err("name is required")
    db  = get_db()
    cur = db.execute("""
        INSERT INTO cast_assemblies (name, notes, attributed_to)
        VALUES (?,?,?)
    """, (data['name'], data.get('notes'), data.get('attributed_to')))
    db.commit()
    return ok(id=cur.lastrowid), 201

@app.post('/api/cast_assemblies/<int:ca_id>/parts')
def add_cast_assembly_part(ca_id):
    data = request.json or {}
    if not data.get('part_id'):
        return err("part_id is required")
    db  = get_db()
    try:
        cur = db.execute("""
            INSERT INTO cast_assembly_parts (cast_assembly_id, part_id, notes)
            VALUES (?,?,?)
        """, (ca_id, data['part_id'], data.get('notes')))
        db.commit()
        return ok(id=cur.lastrowid), 201
    except sqlite3.IntegrityError:
        return err("This part is already in this assembly")


# ── IMAGES ────────────────────────────────────────────────────────

@app.get('/api/sources')
def list_sources():
    db          = get_db()
    q           = request.args.get('q', '').strip()
    source_type = request.args.get('source_type', '').strip()

    sql = """
        SELECT s.*,
               (SELECT COUNT(*) FROM source_extracts se WHERE se.source_id = s.id) AS extract_count
        FROM sources s
        WHERE 1=1
    """
    params = []
    if source_type:
        sql += " AND s.source_type=?"
        params.append(source_type)
    if q:
        sql += " AND (s.title LIKE ? OR s.author LIKE ? OR s.publisher LIKE ? OR s.source_code LIKE ? OR s.url LIKE ? OR s.local_path LIKE ? OR s.notes LIKE ?)"
        params.extend([f'%{q}%'] * 7)
    sql += " ORDER BY s.source_date DESC, s.title"
    rows = rows_to_list(db.execute(sql, params).fetchall())
    return ok(rows, count=len(rows))


@app.get('/api/sources/<int:source_id>')
def get_source(source_id):
    db = get_db()
    source = db.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
    if not source:
        return err('Source not found', 404)
    extracts = rows_to_list(db.execute("""
        SELECT id, source_id, extract_type, locator, author_handle, extract_date, content, notes, attributed_to, created_at
        FROM source_extracts
        WHERE source_id=?
        ORDER BY extract_date, id
    """, (source_id,)).fetchall())
    images = rows_to_list(db.execute("""
        SELECT * FROM images
        WHERE source_id=?
        ORDER BY date_taken, id
    """, (source_id,)).fetchall())
    return ok(source=dict(source), extracts=extracts, images=images)


@app.post('/api/sources')
@require_admin
def create_source():
    data = request.json or {}
    missing = [f for f in ('source_type', 'title') if not data.get(f)]
    if missing:
        return err(f"Missing required fields: {', '.join(missing)}")
    db = get_db()
    cur = db.execute("""
        INSERT INTO sources
            (source_code, source_type, title, author, publisher,
             source_date, url, local_path, parent_source_id, notes, attributed_to)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data.get('source_code'), data['source_type'], data['title'],
        data.get('author'), data.get('publisher'),
        data.get('source_date'), data.get('url'), data.get('local_path'),
        to_int(data.get('parent_source_id')), data.get('notes'), data.get('attributed_to')
    ))
    db.commit()
    return ok(id=cur.lastrowid), 201


@app.put('/api/sources/<int:source_id>')
@require_admin
def update_source(source_id):
    data = request.json or {}
    db = get_db()
    db.execute("""
        UPDATE sources SET
            source_code=?, source_type=?, title=?, author=?, publisher=?,
            source_date=?, url=?, local_path=?, parent_source_id=?, notes=?, attributed_to=?
        WHERE id=?
    """, (
        data.get('source_code'), data.get('source_type'), data.get('title'),
        data.get('author'), data.get('publisher'),
        data.get('source_date'), data.get('url'), data.get('local_path'),
        to_int(data.get('parent_source_id')), data.get('notes'), data.get('attributed_to'),
        source_id
    ))
    db.commit()
    return ok()


@app.get('/api/source_extracts')
def list_source_extracts():
    db           = get_db()
    source_id    = request.args.get('source_id')
    extract_type = request.args.get('extract_type', '').strip()
    author       = request.args.get('author_handle', '').strip()
    q            = request.args.get('q', '').strip()

    sql = """
        SELECT se.*, s.title AS source_title, s.source_code
        FROM source_extracts se
        JOIN sources s ON s.id = se.source_id
        WHERE 1=1
    """
    params = []
    if source_id:
        sql += " AND se.source_id=?"
        params.append(source_id)
    if extract_type:
        sql += " AND se.extract_type=?"
        params.append(extract_type)
    if author:
        sql += " AND se.author_handle LIKE ?"
        params.append(f'%{author}%')
    if q:
        sql += " AND (se.content LIKE ? OR se.locator LIKE ? OR se.notes LIKE ?)"
        params.extend([f'%{q}%'] * 3)
    sql += " ORDER BY se.extract_date, se.id"
    rows = rows_to_list(db.execute(sql, params).fetchall())
    return ok(rows, count=len(rows))


@app.get('/api/source_extracts/<int:extract_id>')
def get_source_extract(extract_id):
    db = get_db()
    extract = db.execute("""
        SELECT se.*, s.title AS source_title, s.source_code
        FROM source_extracts se
        JOIN sources s ON s.id = se.source_id
        WHERE se.id=?
    """, (extract_id,)).fetchone()
    if not extract:
        return err('Source extract not found', 404)
    return ok(extract=dict(extract))


@app.post('/api/source_extracts')
@require_admin
def create_source_extract():
    data = request.json or {}
    missing = [f for f in ('source_id', 'extract_type', 'content') if not data.get(f)]
    if missing:
        return err(f"Missing required fields: {', '.join(missing)}")
    db = get_db()
    cur = db.execute("""
        INSERT INTO source_extracts
            (source_id, extract_type, locator, author_handle, extract_date,
             content, notes, attributed_to)
        VALUES (?,?,?,?,?,?,?,?)
    """, (
        to_int(data.get('source_id')), data['extract_type'], data.get('locator'),
        data.get('author_handle'), data.get('extract_date'),
        data['content'], data.get('notes'), data.get('attributed_to')
    ))
    db.commit()
    return ok(id=cur.lastrowid), 201


@app.put('/api/source_extracts/<int:extract_id>')
@require_admin
def update_source_extract(extract_id):
    data = request.json or {}
    db = get_db()
    db.execute("""
        UPDATE source_extracts SET
            source_id=?, extract_type=?, locator=?, author_handle=?,
            extract_date=?, content=?, notes=?, attributed_to=?
        WHERE id=?
    """, (
        to_int(data.get('source_id')), data.get('extract_type'),
        data.get('locator'), data.get('author_handle'),
        data.get('extract_date'), data.get('content'),
        data.get('notes'), data.get('attributed_to'),
        extract_id
    ))
    db.commit()
    return ok()


@app.get('/api/image_families')
def list_image_families():
    db = get_db()
    image_id = request.args.get('image_id')
    q = request.args.get('q', '').strip()
    sql = """
        SELECT
            f.*,
            (
                SELECT COUNT(*)
                FROM image_family_members m
                WHERE m.family_id = f.id
            ) AS variant_count
        FROM image_families f
        WHERE 1=1
    """
    params = []
    if image_id:
        sql += " AND f.id IN (SELECT family_id FROM image_family_members WHERE image_id=?)"
        params.append(image_id)
    if q:
        sql += " AND (COALESCE(f.title,'') LIKE ? OR COALESCE(f.notes,'') LIKE ?)"
        params.extend([f'%{q}%', f'%{q}%'])
    sql += " ORDER BY f.id DESC"
    rows = rows_to_list(db.execute(sql, params).fetchall())
    return ok(rows, count=len(rows))


@app.get('/api/image_families/<int:family_id>')
def get_image_family(family_id):
    db = get_db()
    payload = get_image_family_payload(db, family_id)
    if not payload:
        return err('Image family not found', 404)
    return ok(family=payload)


@app.post('/api/image_families')
@require_admin
def create_image_family():
    data = request.json or {}
    if not data.get('title'):
        return err('title is required')
    db = get_db()
    member_image_ids = [to_int(member.get('image_id')) for member in (data.get('members') or [])]
    primary_image_id = to_int(data.get('primary_image_id'))
    candidate_ids = [image_id for image_id in [*member_image_ids, primary_image_id] if image_id]
    checked = set()
    for image_id in candidate_ids:
        if image_id in checked:
            continue
        checked.add(image_id)
        existing_membership = get_image_family_membership(db, image_id)
        if existing_membership:
            return err(f'Image {image_id} already belongs to family {existing_membership["family_id"]}', 409)
    cur = db.execute("""
        INSERT INTO image_families
            (title, family_type, primary_image_id, notes)
        VALUES (?,?,?,?)
    """, (
        data['title'],
        data.get('family_type', 'reference_set'),
        to_int(data.get('primary_image_id')),
        data.get('notes')
    ))
    family_id = cur.lastrowid
    for member in data.get('members') or []:
        ensure_family_member(
            db,
            family_id,
            to_int(member.get('image_id')),
            relation_type=member.get('relation_type') or ('primary' if to_bool_int(member.get('is_primary')) else 'variant'),
            sort_order=to_int(member.get('sort_order')) or 0,
            is_primary=to_bool_int(member.get('is_primary')),
            is_hidden_in_library=to_bool_int(member.get('is_hidden_in_library')),
            coverage_role=member.get('coverage_role'),
            notes=member.get('notes')
        )
    if not primary_image_id and data.get('members'):
        primary = next((m for m in data['members'] if to_bool_int(m.get('is_primary'))), None)
        if primary:
            primary_image_id = to_int(primary.get('image_id'))
    if primary_image_id:
        ensure_family_member(db, family_id, primary_image_id, relation_type='primary', is_primary=1)
        set_family_primary_image(db, family_id, primary_image_id)
    db.commit()
    return ok(id=family_id), 201


@app.put('/api/image_families/<int:family_id>')
@require_admin
def update_image_family(family_id):
    data = request.json or {}
    db = get_db()
    existing = db.execute("SELECT * FROM image_families WHERE id=?", (family_id,)).fetchone()
    if not existing:
        return err('Image family not found', 404)
    merged = {
        'title': data.get('title', existing['title']),
        'family_type': data.get('family_type', existing['family_type']),
        'primary_image_id': to_int(data.get('primary_image_id')) if 'primary_image_id' in data else existing['primary_image_id'],
        'notes': data.get('notes', existing['notes'])
    }
    db.execute("""
        UPDATE image_families SET
            title=?, family_type=?, primary_image_id=?, notes=?
        WHERE id=?
    """, (
        merged['title'],
        merged['family_type'],
        merged['primary_image_id'],
        merged['notes'],
        family_id
    ))
    if merged['primary_image_id']:
        ensure_family_member(db, family_id, merged['primary_image_id'], relation_type='primary', is_primary=1)
        set_family_primary_image(db, family_id, merged['primary_image_id'])
    db.commit()
    return ok()


@app.delete('/api/image_families/<int:family_id>')
@require_admin
def delete_image_family(family_id):
    db = get_db()
    existing = db.execute("SELECT * FROM image_families WHERE id=?", (family_id,)).fetchone()
    if not existing:
        return err('Image family not found', 404)
    db.execute("DELETE FROM image_families WHERE id=?", (family_id,))
    db.commit()
    return ok()


@app.post('/api/image_families/<int:family_id>/members')
@require_admin
def create_image_family_member(family_id):
    data = request.json or {}
    image_id = to_int(data.get('image_id'))
    if not image_id:
        return err('image_id is required')
    db = get_db()
    family = db.execute("SELECT * FROM image_families WHERE id=?", (family_id,)).fetchone()
    if not family:
        return err('Image family not found', 404)
    existing_membership = get_image_family_membership(db, image_id)
    if existing_membership:
        if existing_membership['family_id'] != family_id:
            return err(f'Image already belongs to family {existing_membership["family_id"]}', 409)
        return ok(id=existing_membership['id']), 200
    member = ensure_family_member(
        db,
        family_id,
        image_id,
        relation_type=data.get('relation_type') or ('primary' if to_bool_int(data.get('is_primary')) else 'variant'),
        sort_order=to_int(data.get('sort_order')) or 0,
        is_primary=to_bool_int(data.get('is_primary')),
        is_hidden_in_library=to_bool_int(data.get('is_hidden_in_library')),
        coverage_role=data.get('coverage_role'),
        notes=data.get('notes')
    )
    if to_bool_int(data.get('is_primary')) or data.get('relation_type') == 'primary':
        set_family_primary_image(db, family_id, image_id)
    db.commit()
    return ok(id=member['id'] if member else None), 201


@app.put('/api/image_families/<int:family_id>/members/<int:member_id>')
@require_admin
def update_image_family_member(family_id, member_id):
    data = request.json or {}
    db = get_db()
    existing = db.execute(
        "SELECT * FROM image_family_members WHERE id=? AND family_id=?",
        (member_id, family_id)
    ).fetchone()
    if not existing:
        return err('Image family member not found', 404)
    merged = {
        'relation_type': data.get('relation_type', existing['relation_type']),
        'sort_order': to_int(data.get('sort_order')) if 'sort_order' in data else existing['sort_order'],
        'is_primary': to_bool_int(data.get('is_primary'), existing['is_primary']) if 'is_primary' in data else existing['is_primary'],
        'is_hidden_in_library': to_bool_int(data.get('is_hidden_in_library'), existing['is_hidden_in_library']) if 'is_hidden_in_library' in data else existing['is_hidden_in_library'],
        'coverage_role': data.get('coverage_role', existing['coverage_role']),
        'notes': data.get('notes', existing['notes'])
    }
    db.execute("""
        UPDATE image_family_members SET
            relation_type=?, sort_order=?, is_primary=?, is_hidden_in_library=?, coverage_role=?, notes=?
        WHERE id=?
    """, (
        merged['relation_type'],
        merged['sort_order'],
        merged['is_primary'],
        merged['is_hidden_in_library'],
        merged['coverage_role'],
        merged['notes'],
        member_id
    ))
    if merged['is_primary'] or merged['relation_type'] == 'primary':
        set_family_primary_image(db, family_id, existing['image_id'])
    db.commit()
    return ok()


@app.delete('/api/image_families/<int:family_id>/members/<int:member_id>')
@require_admin
def delete_image_family_member(family_id, member_id):
    db = get_db()
    existing = db.execute(
        "SELECT * FROM image_family_members WHERE id=? AND family_id=?",
        (member_id, family_id)
    ).fetchone()
    if not existing:
        return err('Image family member not found', 404)
    db.execute("DELETE FROM image_family_members WHERE id=?", (member_id,))
    remaining = rows_to_list(db.execute(
        "SELECT * FROM image_family_members WHERE family_id=? ORDER BY is_primary DESC, sort_order ASC, id ASC",
        (family_id,)
    ).fetchall())
    if not remaining:
        db.execute("UPDATE image_families SET primary_image_id=NULL WHERE id=?", (family_id,))
    elif existing['is_primary']:
        set_family_primary_image(db, family_id, remaining[0]['image_id'])
    db.commit()
    return ok()


@app.get('/api/images')
def list_images():
    db          = get_db()
    entity_type = request.args.get('entity_type')
    entity_id   = request.args.get('entity_id')
    image_type  = request.args.get('image_type')
    tag         = request.args.get('tag')
    source_id   = request.args.get('source_id')
    family_id   = request.args.get('family_id')
    collapse_family = request.args.get('collapse_family') in ('1', 'true', 'yes')
    q           = request.args.get('q', '').strip()

    if entity_type and entity_id:
        rows = rows_to_list(db.execute("""
            SELECT i.*, il.annotation,
                   s.title AS source_title,
                   (SELECT COUNT(*) FROM image_regions r WHERE r.image_id = i.id) AS region_count,
                   (SELECT COUNT(DISTINCT ce.claim_id)
                    FROM claim_evidence ce
                    JOIN image_regions r ON r.id = ce.evidence_id
                    WHERE ce.evidence_type = 'image_region' AND r.image_id = i.id) AS claim_count
            FROM images i
            JOIN image_links il ON il.image_id = i.id
            LEFT JOIN sources s ON s.id = i.source_id
            WHERE il.entity_type=? AND il.entity_id=?
            ORDER BY i.date_taken
        """, (entity_type, entity_id)).fetchall())
    else:
        sql = """
            SELECT i.*, s.title AS source_title,
                   (SELECT COUNT(*) FROM image_regions r WHERE r.image_id = i.id) AS region_count,
                   (SELECT COUNT(DISTINCT ce.claim_id)
                    FROM claim_evidence ce
                    JOIN image_regions r ON r.id = ce.evidence_id
                    WHERE ce.evidence_type = 'image_region' AND r.image_id = i.id) AS claim_count
            FROM images i
            LEFT JOIN sources s ON s.id = i.source_id
            WHERE 1=1
        """
        params = []
        if image_type:
            sql += " AND i.image_type=?"
            params.append(image_type)
        if source_id:
            sql += " AND i.source_id=?"
            params.append(source_id)
        if family_id:
            sql += " AND i.id IN (SELECT image_id FROM image_family_members WHERE family_id=?)"
            params.append(family_id)
        if tag:
            sql += " AND i.id IN (SELECT image_id FROM image_tags WHERE tag=?)"
            params.append(tag)
        if q:
            sql += " AND (COALESCE(i.title,'') LIKE ? OR COALESCE(i.caption,'') LIKE ? OR COALESCE(i.image_code,'') LIKE ? OR COALESCE(i.filename,'') LIKE ? OR COALESCE(i.source,'') LIKE ? OR COALESCE(i.notes,'') LIKE ? OR COALESCE(s.title,'') LIKE ?)"
            params.extend([f'%{q}%'] * 7)
        sql += " ORDER BY i.date_taken DESC, i.id DESC"
        rows = rows_to_list(db.execute(sql, params).fetchall())

    family_map = get_image_family_map(db, [row['id'] for row in rows])
    for row in rows:
        family = family_map.get(row['id'])
        row['family'] = family
        if family:
            row['family_id'] = family['family_id']
            row['family_title'] = family['family_title']
            row['family_type'] = family['family_type']
            row['family_variant_count'] = family['family_variant_count']
            row['is_family_primary'] = family['is_primary']
            row['is_hidden_in_library'] = family['is_hidden_in_library']
        else:
            row['family_id'] = None
            row['family_title'] = None
            row['family_type'] = None
            row['family_variant_count'] = None
            row['is_family_primary'] = 0
            row['is_hidden_in_library'] = 0

    if collapse_family:
        rows = [
            row for row in rows
            if not row.get('family_id')
            or row.get('is_family_primary')
            or not row.get('is_hidden_in_library')
        ]

    return ok(rows, count=len(rows))

@app.get('/api/images/<int:image_id>')
def get_image(image_id):
    db  = get_db()
    img = db.execute("SELECT * FROM images WHERE id=?", (image_id,)).fetchone()
    if not img:
        return err('Image not found', 404)
    links = rows_to_list(db.execute(
        "SELECT * FROM image_links WHERE image_id=? ORDER BY entity_type, entity_id",
        (image_id,)
    ).fetchall())
    # resolve human-readable labels for each link
    for link in links:
        link['entity_label'] = _entity_label(link['entity_type'], link['entity_id'], db)
    tags = [r['tag'] for r in db.execute(
        "SELECT tag FROM image_tags WHERE image_id=? ORDER BY tag", (image_id,)
    ).fetchall()]
    regions = rows_to_list(db.execute(
        "SELECT * FROM image_regions WHERE image_id=? ORDER BY id",
        (image_id,)
    ).fetchall())
    region_claim_counts = {
        row['evidence_id']: row['c']
        for row in db.execute("""
            SELECT evidence_id, COUNT(DISTINCT claim_id) AS c
            FROM claim_evidence
            WHERE evidence_type='image_region'
              AND evidence_id IN (SELECT id FROM image_regions WHERE image_id=?)
            GROUP BY evidence_id
        """, (image_id,)).fetchall()
    }
    for region in regions:
        if region.get('entity_type') and region.get('entity_id') is not None:
            region['entity_label'] = _entity_label(region['entity_type'], region['entity_id'], db)
        region['claim_count'] = region_claim_counts.get(region['id'], 0)
    source_record = None
    if img['source_id']:
        src = db.execute("SELECT * FROM sources WHERE id=?", (img['source_id'],)).fetchone()
        if src:
            source_record = dict(src)
    claim_count = db.execute("""
        SELECT COUNT(DISTINCT ce.claim_id) AS c
        FROM claim_evidence ce
        JOIN image_regions r ON r.id = ce.evidence_id
        WHERE ce.evidence_type='image_region' AND r.image_id=?
    """, (image_id,)).fetchone()['c']
    family_row = get_image_family_map(db, [image_id]).get(image_id)
    family = get_image_family_payload(db, family_row['family_id']) if family_row else None
    return ok(
        image=dict(img),
        links=links,
        tags=tags,
        regions=regions,
        source_record=source_record,
        claim_count=claim_count,
        family=family,
        family_member=family_row
    )

def _entity_label(entity_type, entity_id, db):
    """Return a short human-readable string for display next to a link."""
    try:
        if entity_type == 'kit':
            r = db.execute("SELECT brand, name FROM kits WHERE id=?", (entity_id,)).fetchone()
            return f"{r['brand']} — {r['name']}" if r else str(entity_id)
        elif entity_type == 'part':
            r = db.execute("""
                SELECT p.part_number, p.part_label, k.name as kit_name
                FROM parts p JOIN kits k ON k.id = p.kit_id WHERE p.id=?
            """, (entity_id,)).fetchone()
            if r:
                label = r['part_label'] or ''
                return f"{r['kit_name']} #{r['part_number']} {label}".strip()
        elif entity_type == 'cast_assembly':
            r = db.execute("SELECT name FROM cast_assemblies WHERE id=?", (entity_id,)).fetchone()
            return r['name'] if r else str(entity_id)
        elif entity_type == 'placement':
            r = db.execute("""
                SELECT pl.location_label, pt.part_number, k.brand, k.name as kit_name,
                       m.name as model_name
                FROM placements pl
                JOIN models m ON m.id = pl.model_id
                LEFT JOIN parts pt ON pt.id = pl.part_id
                LEFT JOIN kits k   ON k.id  = COALESCE(pt.kit_id, pl.kit_id)
                WHERE pl.id=?
            """, (entity_id,)).fetchone()
            if r:
                part_str = f"{r['brand']} {r['kit_name']} #{r['part_number']}" if r['part_number'] else ''
                loc = r['location_label'] or ''
                return f"{r['model_name']} — {part_str} {loc}".strip(' —')
        elif entity_type == 'model':
            r = db.execute("SELECT name FROM models WHERE id=?", (entity_id,)).fetchone()
            return r['name'] if r else str(entity_id)
        elif entity_type == 'map':
            r = db.execute("SELECT name FROM maps WHERE id=?", (entity_id,)).fetchone()
            return r['name'] if r else str(entity_id)
    except Exception:
        pass
    return str(entity_id)


def enrich_claim_rows(rows, db):
    enriched = []
    for row in rows:
        claim = dict(row)
        if claim.get('subject_type') and claim.get('subject_id') is not None:
            claim['subject_label'] = _entity_label(claim['subject_type'], claim['subject_id'], db)
        else:
            claim['subject_label'] = None
        if claim.get('object_type') and claim.get('object_id') is not None:
            claim['object_label'] = _entity_label(claim['object_type'], claim['object_id'], db)
        else:
            claim['object_label'] = None
        evidence = rows_to_list(db.execute("""
            SELECT * FROM claim_evidence
            WHERE claim_id=?
            ORDER BY evidence_type, evidence_id
        """, (claim['id'],)).fetchall())
        for item in evidence:
            if item.get('evidence_type') == 'image_region':
                reg = db.execute("SELECT label, image_id FROM image_regions WHERE id=?", (item['evidence_id'],)).fetchone()
                if reg:
                    item['evidence_label'] = reg['label'] or f"Region {item['evidence_id']}"
                    item['image_id'] = reg['image_id']
                else:
                    item['evidence_label'] = f"Region {item['evidence_id']}"
            elif item.get('evidence_type') == 'source_extract':
                ext = db.execute("SELECT locator, content FROM source_extracts WHERE id=?", (item['evidence_id'],)).fetchone()
                if ext:
                    item['evidence_label'] = ext['locator'] or (ext['content'][:80] + '...' if ext['content'] and len(ext['content']) > 80 else ext['content'])
                else:
                    item['evidence_label'] = f"Source extract {item['evidence_id']}"
            elif item.get('evidence_type') == 'image':
                img = db.execute("SELECT title, image_code, filename FROM images WHERE id=?", (item['evidence_id'],)).fetchone()
                if img:
                    item['evidence_label'] = img['title'] or img['image_code'] or img['filename'] or f"Image {item['evidence_id']}"
                else:
                    item['evidence_label'] = f"Image {item['evidence_id']}"
        claim['evidence'] = evidence
        enriched.append(claim)
    return enriched

@app.post('/api/images')
@require_admin
def create_image():
    # BUG FIX: removed 'tags' column (replaced by image_tags table)
    # Handles both JSON body (URL/Drive registration) and multipart file upload
    db = get_db()
    return create_image_v2(db)

@app.put('/api/images/<int:image_id>')
@require_admin
def update_image(image_id):
    """Update image metadata and tags."""
    db   = get_db()
    return update_image_v2(db, image_id)

@app.delete('/api/images/<int:image_id>')
@require_admin
def delete_image(image_id):
    db  = get_db()
    img = db.execute("SELECT filename FROM images WHERE id=?", (image_id,)).fetchone()
    detach_image_from_family(db, image_id)
    db.execute("UPDATE image_families SET primary_image_id=NULL WHERE primary_image_id=?", (image_id,))
    if img and img['filename']:
        # Only delete file if no other image record references it
        others = db.execute(
            "SELECT COUNT(*) as c FROM images WHERE filename=? AND id!=?",
            (img['filename'], image_id)
        ).fetchone()['c']
        if others == 0:
            path = os.path.join(UPLOAD_DIR, img['filename'])
            if os.path.exists(path):
                os.remove(path)
    db.execute("DELETE FROM images WHERE id=?", (image_id,))
    db.commit()
    return ok()


@app.get('/api/image_regions')
def list_image_regions():
    db = get_db()
    image_id = request.args.get('image_id')
    entity_type = request.args.get('entity_type', '').strip()
    entity_id = request.args.get('entity_id')
    source_extract_id = request.args.get('source_extract_id')

    sql = "SELECT * FROM image_regions WHERE 1=1"
    params = []
    if image_id:
        sql += " AND image_id=?"
        params.append(image_id)
    if entity_type:
        sql += " AND entity_type=?"
        params.append(entity_type)
    if entity_id:
        sql += " AND entity_id=?"
        params.append(entity_id)
    if source_extract_id:
        sql += " AND source_extract_id=?"
        params.append(source_extract_id)
    sql += " ORDER BY image_id, id"
    rows = rows_to_list(db.execute(sql, params).fetchall())
    for row in rows:
        if row.get('entity_type') and row.get('entity_id') is not None:
            row['entity_label'] = _entity_label(row['entity_type'], row['entity_id'], db)
    return ok(rows, count=len(rows))


@app.get('/api/image_regions/<int:region_id>')
def get_image_region(region_id):
    db = get_db()
    row = db.execute("SELECT * FROM image_regions WHERE id=?", (region_id,)).fetchone()
    if not row:
        return err('Image region not found', 404)
    region = dict(row)
    if region.get('entity_type') and region.get('entity_id') is not None:
        region['entity_label'] = _entity_label(region['entity_type'], region['entity_id'], db)
    history = rows_to_list(db.execute("""
        SELECT * FROM image_region_history
        WHERE region_id=?
        ORDER BY changed_at DESC, id DESC
    """, (region_id,)).fetchall())
    claim_rows = rows_to_list(db.execute("""
        SELECT c.*
        FROM claims c
        JOIN claim_evidence ce ON ce.claim_id = c.id
        WHERE ce.evidence_type='image_region' AND ce.evidence_id=?
        ORDER BY c.updated_at DESC, c.id DESC
    """, (region_id,)).fetchall())
    claims = enrich_claim_rows(claim_rows, db)
    region['history'] = history
    region['claims'] = claims
    return ok(region=region, history=history, claims=claims)


@app.post('/api/image_regions')
@require_admin
def create_image_region():
    data = request.json or {}
    missing = [f for f in ('image_id',) if not data.get(f)]
    if missing:
        return err(f"Missing required fields: {', '.join(missing)}")
    db = get_db()
    cur = db.execute("""
        INSERT INTO image_regions
            (image_id, region_type, x_norm, y_norm, width_norm, height_norm,
             pixel_x, pixel_y, pixel_width, pixel_height, points_json, rotation_deg,
             label, notes, object_name, object_class, color, properties_json,
             entity_type, entity_id, source_extract_id, attributed_to)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        to_int(data.get('image_id')), data.get('region_type', 'point'),
        to_float(data.get('x_norm')), to_float(data.get('y_norm')),
        to_float(data.get('width_norm')), to_float(data.get('height_norm')),
        to_float(data.get('pixel_x')), to_float(data.get('pixel_y')),
        to_float(data.get('pixel_width')), to_float(data.get('pixel_height')),
        json_text(data.get('points_json') if 'points_json' in data else data.get('points')),
        to_float(data.get('rotation_deg')),
        data.get('label'), data.get('notes'), data.get('object_name'),
        data.get('object_class'), data.get('color'),
        json_text(data.get('properties_json') if 'properties_json' in data else data.get('properties')),
        data.get('entity_type'), to_int(data.get('entity_id')),
        to_int(data.get('source_extract_id')), data.get('attributed_to')
    ))
    db.commit()
    created = db.execute("SELECT * FROM image_regions WHERE id=?", (cur.lastrowid,)).fetchone()
    record_image_region_history(db, cur.lastrowid, 'create', snapshot=dict(created), changed_by=data.get('attributed_to'), reason=data.get('reason'))
    return ok(id=cur.lastrowid), 201


@app.put('/api/image_regions/<int:region_id>')
@require_admin
def update_image_region(region_id):
    data = request.json or {}
    db = get_db()
    old = db.execute("SELECT * FROM image_regions WHERE id=?", (region_id,)).fetchone()
    if not old:
        return err('Image region not found', 404)
    current = dict(old)
    merged = {
        'image_id': to_int(data.get('image_id')) if 'image_id' in data else current['image_id'],
        'region_type': data.get('region_type', current['region_type']),
        'x_norm': to_float(data.get('x_norm')) if 'x_norm' in data else current['x_norm'],
        'y_norm': to_float(data.get('y_norm')) if 'y_norm' in data else current['y_norm'],
        'width_norm': to_float(data.get('width_norm')) if 'width_norm' in data else current['width_norm'],
        'height_norm': to_float(data.get('height_norm')) if 'height_norm' in data else current['height_norm'],
        'pixel_x': to_float(data.get('pixel_x')) if 'pixel_x' in data else current['pixel_x'],
        'pixel_y': to_float(data.get('pixel_y')) if 'pixel_y' in data else current['pixel_y'],
        'pixel_width': to_float(data.get('pixel_width')) if 'pixel_width' in data else current['pixel_width'],
        'pixel_height': to_float(data.get('pixel_height')) if 'pixel_height' in data else current['pixel_height'],
        'points_json': json_text(data.get('points_json') if 'points_json' in data else data.get('points')) if ('points_json' in data or 'points' in data) else current['points_json'],
        'rotation_deg': to_float(data.get('rotation_deg')) if 'rotation_deg' in data else current['rotation_deg'],
        'label': data.get('label') if 'label' in data else current['label'],
        'notes': data.get('notes') if 'notes' in data else current['notes'],
        'object_name': data.get('object_name') if 'object_name' in data else current['object_name'],
        'object_class': data.get('object_class') if 'object_class' in data else current['object_class'],
        'color': data.get('color') if 'color' in data else current['color'],
        'properties_json': json_text(data.get('properties_json') if 'properties_json' in data else data.get('properties')) if ('properties_json' in data or 'properties' in data) else current['properties_json'],
        'entity_type': data.get('entity_type') if 'entity_type' in data else current['entity_type'],
        'entity_id': to_int(data.get('entity_id')) if 'entity_id' in data else current['entity_id'],
        'source_extract_id': to_int(data.get('source_extract_id')) if 'source_extract_id' in data else current['source_extract_id'],
        'attributed_to': data.get('attributed_to') if 'attributed_to' in data else current['attributed_to'],
    }
    if merged['image_id'] is None:
        return err('image_id is required')
    db.execute("""
        UPDATE image_regions SET
            image_id=?, region_type=?, x_norm=?, y_norm=?, width_norm=?, height_norm=?,
            pixel_x=?, pixel_y=?, pixel_width=?, pixel_height=?, points_json=?, rotation_deg=?,
            label=?, notes=?, object_name=?, object_class=?, color=?, properties_json=?,
            entity_type=?, entity_id=?, source_extract_id=?, attributed_to=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (
        merged['image_id'], merged['region_type'],
        merged['x_norm'], merged['y_norm'],
        merged['width_norm'], merged['height_norm'],
        merged['pixel_x'], merged['pixel_y'],
        merged['pixel_width'], merged['pixel_height'],
        merged['points_json'], merged['rotation_deg'],
        merged['label'], merged['notes'], merged['object_name'],
        merged['object_class'], merged['color'],
        merged['properties_json'],
        merged['entity_type'], merged['entity_id'],
        merged['source_extract_id'], merged['attributed_to'],
        region_id
    ))
    db.commit()
    updated = db.execute("SELECT * FROM image_regions WHERE id=?", (region_id,)).fetchone()
    record_image_region_history(db, region_id, 'update', snapshot=dict(updated), changed_by=data.get('attributed_to'), reason=data.get('reason'))
    return ok()


@app.delete('/api/image_regions/<int:region_id>')
@require_admin
def delete_image_region(region_id):
    db = get_db()
    old = db.execute("SELECT * FROM image_regions WHERE id=?", (region_id,)).fetchone()
    if not old:
        return err('Image region not found', 404)
    record_image_region_history(db, region_id, 'delete', snapshot=dict(old), changed_by=request.args.get('changed_by'), reason=request.args.get('reason'))
    db.execute("DELETE FROM image_regions WHERE id=?", (region_id,))
    db.commit()
    return ok()


# ── IMAGE LINKS ───────────────────────────────────────────────────

@app.get('/api/image_links')
def list_image_links():
    """
    List links filtered by image or entity.
    ?image_id=N  → all entities linked to this image
    ?entity_type=kit&entity_id=N  → all images linked to this entity
    """
    db          = get_db()
    image_id    = request.args.get('image_id')
    entity_type = request.args.get('entity_type')
    entity_id   = request.args.get('entity_id')

    if image_id:
        rows = rows_to_list(db.execute(
            "SELECT * FROM image_links WHERE image_id=? ORDER BY entity_type, entity_id",
            (image_id,)
        ).fetchall())
        for r in rows:
            r['entity_label'] = _entity_label(r['entity_type'], r['entity_id'], db)
    elif entity_type and entity_id:
        rows = rows_to_list(db.execute(
            "SELECT * FROM image_links WHERE entity_type=? AND entity_id=?",
            (entity_type, entity_id)
        ).fetchall())
    else:
        return err("Provide image_id or entity_type+entity_id")

    return ok(rows, count=len(rows))

@app.post('/api/image_links')
def create_image_link():
    data    = request.json or {}
    missing = [f for f in ('image_id', 'entity_type', 'entity_id') if not data.get(f)]
    if missing:
        return err(f"Missing required fields: {', '.join(missing)}")
    valid_types = {'kit', 'part', 'cast_assembly', 'placement', 'model', 'map'}
    if data['entity_type'] not in valid_types:
        return err(f"entity_type must be one of: {', '.join(sorted(valid_types))}")
    db  = get_db()
    cur = db.execute("""
        INSERT OR IGNORE INTO image_links (image_id, entity_type, entity_id, annotation)
        VALUES (?,?,?,?)
    """, (data['image_id'], data['entity_type'], data['entity_id'], data.get('annotation')))
    db.commit()
    return ok(id=cur.lastrowid), 201

@app.put('/api/image_links/<int:link_id>')
def update_image_link(link_id):
    data = request.json or {}
    db   = get_db()
    db.execute("UPDATE image_links SET annotation=? WHERE id=?",
               (data.get('annotation'), link_id))
    db.commit()
    return ok()

@app.delete('/api/image_links/<int:link_id>')
def delete_image_link(link_id):
    db = get_db()
    db.execute("DELETE FROM image_links WHERE id=?", (link_id,))
    db.commit()
    return ok()


# ── IMAGE TAGS ────────────────────────────────────────────────────

@app.post('/api/images/<int:image_id>/tags')
def add_image_tag(image_id):
    data = request.json or {}
    if not data.get('tag'):
        return err("tag is required")
    db = get_db()
    db.execute("INSERT OR IGNORE INTO image_tags (image_id, tag) VALUES (?,?)",
               (image_id, data['tag'].strip()))
    db.commit()
    return ok()

@app.delete('/api/images/<int:image_id>/tags/<tag>')
def remove_image_tag(image_id, tag):
    db = get_db()
    db.execute("DELETE FROM image_tags WHERE image_id=? AND tag=?", (image_id, tag))
    db.commit()
    return ok()


# ── CONTRIBUTORS ─────────────────────────────────────────────────

@app.get('/api/contributors')
def list_contributors():
    db   = get_db()
    rows = rows_to_list(db.execute(
        "SELECT * FROM contributors ORDER BY handle"
    ).fetchall())
    return ok(rows)

@app.post('/api/contributors')
def create_contributor():
    data = request.json or {}
    if not data.get('handle'):
        return err("handle is required")
    db  = get_db()
    cur = db.execute("""
        INSERT OR IGNORE INTO contributors
            (handle, display_name, forum, profile_url, notes)
        VALUES (?,?,?,?,?)
    """, (data['handle'], data.get('display_name'),
          data.get('forum'), data.get('profile_url'), data.get('notes')))
    db.commit()
    return ok(id=cur.lastrowid), 201


# ── SEARCH ────────────────────────────────────────────────────────

@app.get('/api/entity_search')
def entity_search():
    q = request.args.get('q', '').strip()
    types_raw = request.args.get('types', '').strip()
    limit = min(max(to_int(request.args.get('limit')) or 24, 1), 100)
    if len(q) < 2:
        return err("Query must be at least 2 characters")
    allowed_types = {'kit', 'part', 'placement', 'model', 'map'}
    types = [t.strip() for t in types_raw.split(',') if t.strip()] if types_raw else ['kit', 'part', 'placement', 'model']
    types = [t for t in types if t in allowed_types]
    if not types:
        types = ['kit', 'part', 'placement', 'model']

    db = get_db()
    like = f'%{q}%'
    results = []

    if 'kit' in types:
        rows = rows_to_list(db.execute("""
            SELECT id, brand, name, scale, serial_number, category_family, category_subject
            FROM kits
            WHERE brand LIKE ? OR name LIKE ? OR serial_number LIKE ?
            ORDER BY brand, name
            LIMIT ?
        """, (like, like, like, limit)).fetchall())
        for row in rows:
            results.append({
                'entity_type': 'kit',
                'entity_id': row['id'],
                'title': f"{row['brand']} - {row['name']}",
                'subtitle': " / ".join([v for v in [row.get('scale'), row.get('serial_number')] if v]),
                'badges': [v for v in [row.get('category_family'), row.get('category_subject')] if v]
            })

    if 'part' in types:
        rows = rows_to_list(db.execute("""
            SELECT p.id, p.part_number, p.part_label, k.brand, k.name AS kit_name, k.category_family, k.category_subject
            FROM parts p
            JOIN kits k ON k.id = p.kit_id
            WHERE p.part_number LIKE ? OR p.part_label LIKE ? OR k.name LIKE ? OR k.brand LIKE ?
            ORDER BY k.brand, k.name, p.part_number
            LIMIT ?
        """, (like, like, like, like, limit)).fetchall())
        for row in rows:
            label = row['part_label'] or ''
            title = f"{row['brand']} / {row['kit_name']} #{row['part_number']}"
            if label:
                title += f" {label}"
            results.append({
                'entity_type': 'part',
                'entity_id': row['id'],
                'title': title,
                'subtitle': row['part_label'] or '',
                'badges': [v for v in [row.get('category_family'), row.get('category_subject')] if v]
            })

    if 'placement' in types:
        rows = rows_to_list(db.execute("""
            SELECT pl.id, pl.location_label, pl.confidence,
                   m.name AS model_name,
                   pt.part_number,
                   k.brand, k.name AS kit_name
            FROM placements pl
            JOIN models m ON m.id = pl.model_id
            LEFT JOIN parts pt ON pt.id = pl.part_id
            LEFT JOIN kits k ON k.id = COALESCE((SELECT kit_id FROM parts WHERE id = pl.part_id), pl.kit_id)
            WHERE m.name LIKE ? OR pl.location_label LIKE ? OR pt.part_number LIKE ? OR k.name LIKE ? OR k.brand LIKE ?
            ORDER BY m.name, pl.id
            LIMIT ?
        """, (like, like, like, like, like, limit)).fetchall())
        for row in rows:
            title = row['model_name']
            if row.get('location_label'):
                title += f" - {row['location_label']}"
            subtitle_bits = []
            if row.get('brand') or row.get('kit_name'):
                subtitle_bits.append(" ".join([v for v in [row.get('brand'), row.get('kit_name')] if v]))
            if row.get('part_number'):
                subtitle_bits.append(f"#{row['part_number']}")
            results.append({
                'entity_type': 'placement',
                'entity_id': row['id'],
                'title': title,
                'subtitle': " / ".join(subtitle_bits),
                'badges': [row.get('confidence')] if row.get('confidence') else []
            })

    if 'model' in types:
        rows = rows_to_list(db.execute("""
            SELECT id, name, film, scale_approx
            FROM models
            WHERE name LIKE ? OR film LIKE ?
            ORDER BY name
            LIMIT ?
        """, (like, like, limit)).fetchall())
        for row in rows:
            results.append({
                'entity_type': 'model',
                'entity_id': row['id'],
                'title': row['name'],
                'subtitle': " / ".join([v for v in [row.get('film'), row.get('scale_approx')] if v]),
                'badges': []
            })

    if 'map' in types:
        rows = rows_to_list(db.execute("""
            SELECT mp.id, mp.name, m.name AS model_name
            FROM maps mp
            JOIN models m ON m.id = mp.model_id
            WHERE mp.name LIKE ? OR m.name LIKE ?
            ORDER BY m.name, mp.name
            LIMIT ?
        """, (like, like, limit)).fetchall())
        for row in rows:
            results.append({
                'entity_type': 'map',
                'entity_id': row['id'],
                'title': row['name'],
                'subtitle': row['model_name'],
                'badges': []
            })

    return ok(results[:limit], count=len(results[:limit]), query=q)


@app.get('/api/claims')
def list_claims():
    db = get_db()
    subject_type = request.args.get('subject_type', '').strip()
    subject_id = request.args.get('subject_id')
    evidence_type = request.args.get('evidence_type', '').strip()
    evidence_id = request.args.get('evidence_id')
    status = request.args.get('status', '').strip()

    sql = "SELECT DISTINCT c.* FROM claims c"
    params = []
    if evidence_type and evidence_id:
        sql += " JOIN claim_evidence ce ON ce.claim_id = c.id"
    sql += " WHERE 1=1"
    if subject_type:
        sql += " AND c.subject_type=?"
        params.append(subject_type)
    if subject_id:
        sql += " AND c.subject_id=?"
        params.append(subject_id)
    if evidence_type and evidence_id:
        sql += " AND ce.evidence_type=? AND ce.evidence_id=?"
        params.extend([evidence_type, evidence_id])
    if status:
        sql += " AND c.status=?"
        params.append(status)
    sql += " ORDER BY c.updated_at DESC, c.id DESC"
    rows = rows_to_list(db.execute(sql, params).fetchall())
    return ok(enrich_claim_rows(rows, db), count=len(rows))


@app.get('/api/claims/<int:claim_id>')
def get_claim(claim_id):
    db = get_db()
    row = db.execute("SELECT * FROM claims WHERE id=?", (claim_id,)).fetchone()
    if not row:
        return err('Claim not found', 404)
    claims = enrich_claim_rows([row], db)
    return ok(claim=claims[0])


@app.post('/api/claims')
@require_admin
def create_claim():
    data = request.json or {}
    missing = [f for f in ('subject_type', 'predicate') if not data.get(f)]
    if missing:
        return err(f"Missing required fields: {', '.join(missing)}")
    if not data.get('object_type') and not data.get('text_value'):
        return err("Either object_type/object_id or text_value is required")

    db = get_db()
    cur = db.execute("""
        INSERT INTO claims
            (subject_type, subject_id, predicate, object_type, object_id,
             text_value, confidence, status, rationale, attributed_to)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        data.get('subject_type'), to_int(data.get('subject_id')), data.get('predicate'),
        data.get('object_type'), to_int(data.get('object_id')),
        data.get('text_value'), data.get('confidence', 'probable'),
        data.get('status', 'active'), data.get('rationale'),
        data.get('attributed_to')
    ))
    claim_id = cur.lastrowid
    for item in (data.get('evidence') or []):
        if not item.get('evidence_type') or item.get('evidence_id') in (None, ''):
            continue
        db.execute("""
            INSERT OR IGNORE INTO claim_evidence (claim_id, evidence_type, evidence_id, annotation)
            VALUES (?,?,?,?)
        """, (
            claim_id, item.get('evidence_type'), to_int(item.get('evidence_id')), item.get('annotation')
        ))
    db.commit()
    return ok(id=claim_id), 201


@app.put('/api/claims/<int:claim_id>')
@require_admin
def update_claim(claim_id):
    data = request.json or {}
    db = get_db()
    existing = db.execute("SELECT * FROM claims WHERE id=?", (claim_id,)).fetchone()
    if not existing:
        return err('Claim not found', 404)
    db.execute("""
        UPDATE claims SET
            subject_type=?, subject_id=?, predicate=?, object_type=?, object_id=?,
            text_value=?, confidence=?, status=?, rationale=?, attributed_to=?,
            updated_at=CURRENT_TIMESTAMP
        WHERE id=?
    """, (
        data.get('subject_type', existing['subject_type']),
        to_int(data.get('subject_id')) if 'subject_id' in data else existing['subject_id'],
        data.get('predicate', existing['predicate']),
        data.get('object_type', existing['object_type']),
        to_int(data.get('object_id')) if 'object_id' in data else existing['object_id'],
        data.get('text_value', existing['text_value']),
        data.get('confidence', existing['confidence']),
        data.get('status', existing['status']),
        data.get('rationale', existing['rationale']),
        data.get('attributed_to', existing['attributed_to']),
        claim_id
    ))
    if 'evidence' in data:
        db.execute("DELETE FROM claim_evidence WHERE claim_id=?", (claim_id,))
        for item in (data.get('evidence') or []):
            if not item.get('evidence_type') or item.get('evidence_id') in (None, ''):
                continue
            db.execute("""
                INSERT OR IGNORE INTO claim_evidence (claim_id, evidence_type, evidence_id, annotation)
                VALUES (?,?,?,?)
            """, (
                claim_id, item.get('evidence_type'), to_int(item.get('evidence_id')), item.get('annotation')
            ))
    db.commit()
    return ok()


@app.delete('/api/claims/<int:claim_id>')
@require_admin
def delete_claim(claim_id):
    db = get_db()
    db.execute("DELETE FROM claims WHERE id=?", (claim_id,))
    db.commit()
    return ok()


@app.get('/api/search')
def search():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return err("Query must be at least 2 characters")
    db   = get_db()
    like = f'%{q}%'
    results = []
    for row in db.execute(
        "SELECT id, 'kit' as type, brand||' — '||name as label FROM kits WHERE brand LIKE ? OR name LIKE ? OR serial_number LIKE ? LIMIT 5",
        (like, like, like)
    ).fetchall():
        results.append(dict(row))
    for row in db.execute(
        "SELECT p.id, 'part' as type, k.brand||' / '||k.name||' #'||p.part_number as label FROM parts p JOIN kits k ON k.id=p.kit_id WHERE p.part_number LIKE ? OR p.part_label LIKE ? LIMIT 5",
        (like, like)
    ).fetchall():
        results.append(dict(row))
    for row in db.execute(
        "SELECT id, 'model' as type, name as label FROM models WHERE name LIKE ? LIMIT 5",
        (like,)
    ).fetchall():
        results.append(dict(row))
    for row in db.execute(
        "SELECT id, 'image' as type, COALESCE(title, image_code, filename, url, 'untitled') as label FROM images WHERE title LIKE ? OR image_code LIKE ? OR filename LIKE ? OR source LIKE ? OR notes LIKE ? LIMIT 5",
        (like, like, like, like, like)
    ).fetchall():
        results.append(dict(row))
    for row in db.execute(
        "SELECT id, 'source' as type, COALESCE(source_code || ' â€” ', '') || title as label FROM sources WHERE title LIKE ? OR author LIKE ? OR publisher LIKE ? OR source_code LIKE ? OR notes LIKE ? LIMIT 5",
        (like, like, like, like, like)
    ).fetchall():
        results.append(dict(row))
    return ok(results, count=len(results), query=q)


# ── ENTRY POINT ───────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    print("\n  ILM Van Nuys Research Platform")
    print("  ================================")
    print(f"  API:  http://localhost:5000/api/health")
    print()
    print("  Endpoints:")
    print("    GET  /api/health")
    print("    GET  /api/kits                ?q=  &brand=")
    print("    GET  /api/kits/<id>")
    print("    POST /api/kits")
    print("    PUT  /api/kits/<id>")
    print("    GET/POST/DELETE /api/kits/<id>/references")
    print("    GET  /api/parts               ?kit_id=  &q=")
    print("    GET  /api/parts/<id>")
    print("    POST /api/parts")
    print("    PUT  /api/parts/<id>")
    print("    POST/DELETE /api/parts/<id>/files")
    print("    GET  /api/models")
    print("    GET  /api/models/<slug>")
    print("    POST /api/models")
    print("    GET/POST /api/maps            ?model_id=")
    print("    GET  /api/placements          ?model_id=  &kit_id=  &map_id=  &confidence=")
    print("    GET  /api/placements/<id>")
    print("    POST /api/placements")
    print("    PUT  /api/placements/<id>")
    print("    DELETE /api/placements/<id>")
    print("    POST/DELETE /api/placements/<id>/contributors")
    print("    GET  /api/connections         (cross-model)")
    print("    GET  /api/cast_assemblies")
    print("    GET  /api/cast_assemblies/<id>")
    print("    POST /api/cast_assemblies")
    print("    POST /api/cast_assemblies/<id>/parts")
    print("    GET  /api/sources             ?q=  &source_type=")
    print("    GET  /api/sources/<id>")
    print("    POST /api/sources")
    print("    PUT  /api/sources/<id>")
    print("    GET  /api/source_extracts     ?source_id=  &extract_type=  &author_handle=  &q=")
    print("    GET  /api/source_extracts/<id>")
    print("    POST /api/source_extracts")
    print("    PUT  /api/source_extracts/<id>")
    print("    GET  /api/image_families      ?image_id=  &q=")
    print("    GET  /api/image_families/<id>")
    print("    POST /api/image_families")
    print("    PUT  /api/image_families/<id>")
    print("    DELETE /api/image_families/<id>")
    print("    POST /api/image_families/<id>/members")
    print("    PUT  /api/image_families/<id>/members/<member_id>")
    print("    DELETE /api/image_families/<id>/members/<member_id>")
    print("    GET  /api/images              ?entity_type=  &entity_id=  &image_type=  &source_id=  &family_id=  &collapse_family=1  &tag=  &q=")
    print("    GET  /api/images/<id>")
    print("    POST /api/images              (JSON body or multipart file upload)")
    print("    PUT  /api/images/<id>")
    print("    DELETE /api/images/<id>")
    print("    GET  /api/image_regions       ?image_id=  &entity_type=  &entity_id=  &source_extract_id=")
    print("    GET  /api/image_regions/<id>")
    print("    POST /api/image_regions")
    print("    PUT  /api/image_regions/<id>")
    print("    DELETE /api/image_regions/<id>")
    print("    GET  /api/image_links         ?image_id=  OR  ?entity_type=&entity_id=")
    print("    POST /api/image_links")
    print("    PUT  /api/image_links/<id>")
    print("    DELETE /api/image_links/<id>")
    print("    POST/DELETE /api/images/<id>/tags")
    print("    GET  /api/contributors")
    print("    POST /api/contributors")
    print("    GET  /api/search              ?q=")
    print()
    # Disable the auto-reloader: frequent DB writes (SQLite WAL) can
    # trigger the reloader repeatedly. Keep debug=True for helpful
    # error pages but avoid use_reloader to stop continuous restarts.
    app.run(debug=True, use_reloader=False, port=5000)
