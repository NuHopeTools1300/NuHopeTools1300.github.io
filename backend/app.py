"""
ILM Van Nuys Kit-Bash Research Platform
Flask backend — Phase 1
"""

import sqlite3
import os
import hashlib
from flask import Flask, g, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)

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

def init_db():
    """Create tables from schema.sql if they don't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    with open(SCHEMA) as f:
        db.executescript(f.read())
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

    sql    = "SELECT * FROM kits WHERE 1=1"
    params = []
    if q:
        sql += " AND (name LIKE ? OR brand LIKE ? OR serial_number LIKE ?)"
        params += [f'%{q}%', f'%{q}%', f'%{q}%']
    if brand:
        sql += " AND brand = ?"
        params.append(brand)
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
            (brand, scale, name, serial_number,
             scalemates_url, scans_url, instructions_url,
             availability, notes, attributed_to)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        data['brand'], data.get('scale'), data['name'], data.get('serial_number'),
        data.get('scalemates_url'), data.get('scans_url'), data.get('instructions_url'),
        data.get('availability', 'unknown'), data.get('notes'), data.get('attributed_to')
    ))
    db.commit()
    return ok(id=cur.lastrowid), 201

@app.put('/api/kits/<int:kit_id>')
def update_kit(kit_id):
    data = request.json or {}
    db   = get_db()
    db.execute("""
        UPDATE kits SET
            brand=?, scale=?, name=?, serial_number=?,
            scalemates_url=?, scans_url=?, instructions_url=?,
            availability=?, notes=?, attributed_to=?
        WHERE id=?
    """, (
        data.get('brand'), data.get('scale'), data.get('name'), data.get('serial_number'),
        data.get('scalemates_url'), data.get('scans_url'), data.get('instructions_url'),
        data.get('availability', 'unknown'), data.get('notes'), data.get('attributed_to'),
        kit_id
    ))
    db.commit()
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

@app.get('/api/maps')
def list_maps():
    db       = get_db()
    model_id = request.args.get('model_id')
    if model_id:
        rows = db.execute(
            "SELECT * FROM maps WHERE model_id=? ORDER BY name", (model_id,)
        ).fetchall()
    else:
        rows = db.execute("SELECT * FROM maps ORDER BY name").fetchall()
    return ok(rows_to_list(rows))

@app.post('/api/maps')
def create_map():
    data    = request.json or {}
    missing = [f for f in ('model_id', 'name') if not data.get(f)]
    if missing:
        return err(f"Missing required fields: {', '.join(missing)}")
    db  = get_db()
    cur = db.execute("""
        INSERT INTO maps (model_id, name, version, url, map_date, attributed_to, notes)
        VALUES (?,?,?,?,?,?,?)
    """, (data['model_id'], data['name'], data.get('version'),
          data.get('url'), data.get('map_date'),
          data.get('attributed_to'), data.get('notes')))
    db.commit()
    return ok(id=cur.lastrowid), 201


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

    rows = db.execute(sql, params).fetchall()
    return ok(rows_to_list(rows), count=len(rows))

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
    return ok(placement=dict(pl), contributors=contributors,
              images=images, history=history)

@app.post('/api/placements')
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
def update_placement(pl_id):
    data = request.json or {}
    db   = get_db()
    # record history before updating
    old = db.execute("SELECT * FROM placements WHERE id=?", (pl_id,)).fetchone()
    if old and (data.get('part_id') != old['part_id'] or
                data.get('kit_id') != old['kit_id'] or
                data.get('confidence') != old['confidence']):
        db.execute("""
            INSERT INTO placement_history
                (placement_id, changed_by, prev_part_id, prev_kit_id,
                 prev_confidence, prev_notes, reason)
            VALUES (?,?,?,?,?,?,?)
        """, (pl_id, data.get('changed_by'),
              old['part_id'], old['kit_id'],
              old['confidence'], old['notes'],
              data.get('change_reason')))
    db.execute("""
        UPDATE placements SET
            map_id=?, film_version=?, location_label=?, copy_count=?,
            confidence=?, modification=?, notes=?, source_url=?, attributed_to=?
        WHERE id=?
    """, (
        data.get('map_id'), data.get('film_version'),
        data.get('location_label'), data.get('copy_count', 1),
        data.get('confidence', 'confirmed'), data.get('modification', 'none'),
        data.get('notes'), data.get('source_url'), data.get('attributed_to'),
        pl_id
    ))
    db.commit()
    return ok()

@app.delete('/api/placements/<int:pl_id>')
def delete_placement(pl_id):
    db = get_db()
    db.execute("DELETE FROM placements WHERE id=?", (pl_id,))
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
    db   = get_db()
    rows = rows_to_list(db.execute("""
        SELECT k.id as kit_id, k.brand, k.name as kit_name, k.scale,
               COUNT(DISTINCT pl.model_id) as model_count,
               GROUP_CONCAT(DISTINCT m.name) as appears_on
        FROM placements pl
        JOIN parts p  ON p.id  = pl.part_id
        JOIN kits  k  ON k.id  = p.kit_id
        JOIN models m ON m.id  = pl.model_id
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

@app.get('/api/images')
def list_images():
    db          = get_db()
    entity_type = request.args.get('entity_type')
    entity_id   = request.args.get('entity_id')
    image_type  = request.args.get('image_type')
    tag         = request.args.get('tag')

    if entity_type and entity_id:
        rows = rows_to_list(db.execute("""
            SELECT i.*, il.annotation
            FROM images i
            JOIN image_links il ON il.image_id = i.id
            WHERE il.entity_type=? AND il.entity_id=?
            ORDER BY i.date_taken
        """, (entity_type, entity_id)).fetchall())
    else:
        sql    = "SELECT * FROM images WHERE 1=1"
        params = []
        if image_type:
            sql += " AND image_type=?"
            params.append(image_type)
        if tag:
            sql += " AND id IN (SELECT image_id FROM image_tags WHERE tag=?)"
            params.append(tag)
        sql += " ORDER BY date_taken DESC"
        rows = rows_to_list(db.execute(sql, params).fetchall())

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
    return ok(image=dict(img), links=links, tags=tags)

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

@app.post('/api/images')
def create_image():
    # BUG FIX: removed 'tags' column (replaced by image_tags table)
    # Handles both JSON body (URL/Drive registration) and multipart file upload
    db = get_db()

    if request.content_type and 'multipart/form-data' in request.content_type:
        # ── File upload path ──────────────────────────────────────
        f = request.files.get('file')
        if not f or not allowed_file(f.filename):
            return err("No valid image file provided")
        data = request.form
        raw  = f.read()
        ext  = f.filename.rsplit('.', 1)[1].lower()
        # Content-addressed: same bytes → same filename, no duplicates
        digest   = hashlib.sha256(raw).hexdigest()[:16]
        filename = f"{digest}.{ext}"
        filepath = os.path.join(UPLOAD_DIR, filename)
        if not os.path.exists(filepath):
            with open(filepath, 'wb') as out:
                out.write(raw)
        url = f"/uploads/{filename}"
    else:
        # ── JSON path (Drive URL or external URL) ─────────────────
        data     = request.json or {}
        filename = data.get('filename', '')
        url      = data.get('url', '')

    cur = db.execute("""
        INSERT INTO images
            (filename, drive_id, url, image_type,
             date_taken, source, notes, attributed_to)
        VALUES (?,?,?,?,?,?,?,?)
    """, (
        filename,
        data.get('drive_id'), url,
        data.get('image_type', 'other'),
        data.get('date_taken'), data.get('source'),
        data.get('notes'), data.get('attributed_to')
    ))
    image_id = cur.lastrowid

    # Handle tags if provided (comma-separated string or JSON array)
    tags = data.get('tags', '')
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(',') if t.strip()]
    for tag in tags:
        db.execute("INSERT OR IGNORE INTO image_tags (image_id, tag) VALUES (?,?)",
                   (image_id, tag))

    db.commit()
    return ok(id=image_id, url=url), 201

@app.put('/api/images/<int:image_id>')
def update_image(image_id):
    """Update image metadata and tags."""
    data = request.json or {}
    db   = get_db()
    db.execute("""
        UPDATE images SET
            image_type=?, date_taken=?, source=?, drive_id=?, url=?, notes=?
        WHERE id=?
    """, (
        data.get('image_type'), data.get('date_taken'), data.get('source'),
        data.get('drive_id'), data.get('url'), data.get('notes'),
        image_id
    ))
    # Replace tags if provided
    if 'tags' in data:
        db.execute("DELETE FROM image_tags WHERE image_id=?", (image_id,))
        tags = data['tags']
        if isinstance(tags, str):
            tags = [t.strip() for t in tags.split(',') if t.strip()]
        for tag in tags:
            db.execute("INSERT OR IGNORE INTO image_tags (image_id, tag) VALUES (?,?)",
                       (image_id, tag))
    db.commit()
    return ok()

@app.delete('/api/images/<int:image_id>')
def delete_image(image_id):
    db  = get_db()
    img = db.execute("SELECT filename FROM images WHERE id=?", (image_id,)).fetchone()
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
        "SELECT id, 'image' as type, COALESCE(filename, url, 'untitled') as label FROM images WHERE source LIKE ? OR notes LIKE ? LIMIT 5",
        (like, like)
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
    print("    GET  /api/images              ?entity_type=  &entity_id=  &image_type=  &tag=")
    print("    GET  /api/images/<id>")
    print("    POST /api/images              (JSON body or multipart file upload)")
    print("    PUT  /api/images/<id>")
    print("    DELETE /api/images/<id>")
    print("    GET  /api/image_links         ?image_id=  OR  ?entity_type=&entity_id=")
    print("    POST /api/image_links")
    print("    PUT  /api/image_links/<id>")
    print("    DELETE /api/image_links/<id>")
    print("    POST/DELETE /api/images/<id>/tags")
    print("    GET  /api/contributors")
    print("    POST /api/contributors")
    print("    GET  /api/search              ?q=")
    print()
    app.run(debug=True, port=5000)
