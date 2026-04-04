"""
ILM Van Nuys Kit-Bash Research Platform
Flask backend — Phase 1
"""

import sqlite3
import os
from flask import Flask, g, jsonify, request

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'data', 'ilm1300.db')
SCHEMA   = os.path.join(BASE_DIR, 'schema.sql')


# ── DATABASE CONNECTION ───────────────────────────────────────────

def get_db():
    """Return a database connection for the current request context."""
    if 'db' not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row      # rows behave like dicts
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(exc=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Create tables from schema.sql if they don't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
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


# ── HEALTH ────────────────────────────────────────────────────────

@app.get('/api/health')
def health():
    db = get_db()
    tables = rows_to_list(db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall())
    return ok(tables=[t['name'] for t in tables])


# ── KITS ─────────────────────────────────────────────────────────

@app.get('/api/kits')
def list_kits():
    db = get_db()
    q  = request.args.get('q', '').strip()
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
    # which models use parts from this kit
    models = rows_to_list(db.execute("""
        SELECT DISTINCT m.id, m.name, m.slug, m.film
        FROM models m
        JOIN placements p ON p.model_id = m.id
        JOIN parts pt     ON pt.id = p.part_id
        WHERE pt.kit_id = ?
        ORDER BY m.name
    """, (kit_id,)).fetchall())
    return ok(kit=dict(kit), parts=parts, used_on_models=models)

@app.post('/api/kits')
def create_kit():
    data = request.json or {}
    required = ('brand', 'name')
    missing  = [f for f in required if not data.get(f)]
    if missing:
        return err(f"Missing required fields: {', '.join(missing)}")
    db = get_db()
    cur = db.execute("""
        INSERT INTO kits
            (coffman_number, coffman_base, coffman_suffix,
             brand, scale, name, serial_number,
             scalemates_url, scans_url, instructions_url,
             confirmed_in_image, notes, attributed_to)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data.get('coffman_number'), data.get('coffman_base'), data.get('coffman_suffix'),
        data['brand'], data.get('scale'), data['name'], data.get('serial_number'),
        data.get('scalemates_url'), data.get('scans_url'), data.get('instructions_url'),
        data.get('confirmed_in_image', 0), data.get('notes'), data.get('attributed_to')
    ))
    db.commit()
    return ok(id=cur.lastrowid), 201


# ── PARTS ─────────────────────────────────────────────────────────

@app.get('/api/parts')
def list_parts():
    db    = get_db()
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
    # kit summary — how many parts from each kit
    kit_summary = rows_to_list(db.execute("""
        SELECT k.id, k.brand, k.name as kit_name, k.scale,
               COUNT(DISTINCT p.id) as part_count,
               SUM(pl.copy_count)   as total_copies
        FROM placements pl
        JOIN parts p ON p.id = pl.part_id
        JOIN kits  k ON k.id = p.kit_id
        WHERE pl.model_id = ?
        GROUP BY k.id
        ORDER BY total_copies DESC
    """, (model['id'],)).fetchall())
    return ok(model=dict(model), maps=maps, kit_summary=kit_summary)

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


# ── PLACEMENTS ────────────────────────────────────────────────────

@app.get('/api/placements')
def list_placements():
    db       = get_db()
    model_id = request.args.get('model_id')
    kit_id   = request.args.get('kit_id')
    map_id   = request.args.get('map_id')

    sql = """
        SELECT pl.*,
               m.name  as model_name,
               mp.name as map_name,
               pt.part_number, pt.part_label,
               k.brand, k.name as kit_name, k.coffman_number,
               ca.name as cast_assembly_name,
               c.handle as attributed_handle
        FROM placements pl
        JOIN models m       ON m.id  = pl.model_id
        LEFT JOIN maps mp   ON mp.id = pl.map_id
        LEFT JOIN parts pt  ON pt.id = pl.part_id
        LEFT JOIN kits k    ON k.id  = pt.kit_id
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
    sql += " ORDER BY m.name, mp.name, k.brand, pt.part_number"

    rows = db.execute(sql, params).fetchall()
    return ok(rows_to_list(rows), count=len(rows))

@app.post('/api/placements')
def create_placement():
    data = request.json or {}
    if not data.get('model_id'):
        return err("model_id is required")
    if not data.get('part_id') and not data.get('cast_assembly_id'):
        return err("Either part_id or cast_assembly_id is required")
    if data.get('part_id') and data.get('cast_assembly_id'):
        return err("Only one of part_id or cast_assembly_id may be set")
    db  = get_db()
    cur = db.execute("""
        INSERT INTO placements
            (model_id, map_id, part_id, cast_assembly_id,
             location_label, copy_count, confidence,
             notes, source_url, attributed_to)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (
        data['model_id'], data.get('map_id'),
        data.get('part_id'), data.get('cast_assembly_id'),
        data.get('location_label'), data.get('copy_count', 1),
        data.get('confidence', 'confirmed'),
        data.get('notes'), data.get('source_url'), data.get('attributed_to')
    ))
    db.commit()
    return ok(id=cur.lastrowid), 201


# ── CROSS-MODEL CONNECTIONS ───────────────────────────────────────
# The key query: which kits/parts appear on more than one model?

@app.get('/api/connections')
def cross_model_connections():
    """
    Return kits that appear on multiple models.
    This is the unique value of the platform.
    """
    db   = get_db()
    rows = rows_to_list(db.execute("""
        SELECT k.id as kit_id, k.brand, k.name as kit_name, k.scale,
               COUNT(DISTINCT pl.model_id) as model_count,
               GROUP_CONCAT(DISTINCT m.name) as appears_on
        FROM placements pl
        JOIN parts p ON p.id = pl.part_id
        JOIN kits  k ON k.id = p.kit_id
        JOIN models m ON m.id = pl.model_id
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
               COUNT(DISTINCT cap.part_id)    as part_count,
               COUNT(DISTINCT pl.model_id)    as used_on_count
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
    parts = rows_to_list(db.execute("""
        SELECT cap.notes as usage_notes,
               pt.part_number, pt.part_label,
               k.brand, k.name as kit_name, k.coffman_number
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
    return ok(cast_assembly=dict(ca), component_parts=parts, used_on=models)


# ── IMAGES ────────────────────────────────────────────────────────

@app.get('/api/images')
def list_images():
    db         = get_db()
    entity_type = request.args.get('entity_type')
    entity_id  = request.args.get('entity_id')
    image_type = request.args.get('image_type')

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
        sql += " ORDER BY date_taken DESC"
        rows = rows_to_list(db.execute(sql, params).fetchall())

    return ok(rows, count=len(rows))

@app.post('/api/images')
def create_image():
    data = request.json or {}
    db   = get_db()
    cur  = db.execute("""
        INSERT INTO images
            (filename, drive_id, url, image_type,
             date_taken, source, tags, notes, attributed_to)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (
        data.get('filename'), data.get('drive_id'), data.get('url'),
        data.get('image_type', 'other'), data.get('date_taken'),
        data.get('source'), data.get('tags'), data.get('notes'),
        data.get('attributed_to')
    ))
    db.commit()
    return ok(id=cur.lastrowid), 201

@app.post('/api/image_links')
def create_image_link():
    data    = request.json or {}
    missing = [f for f in ('image_id', 'entity_type', 'entity_id') if not data.get(f)]
    if missing:
        return err(f"Missing required fields: {', '.join(missing)}")
    db  = get_db()
    cur = db.execute("""
        INSERT OR IGNORE INTO image_links (image_id, entity_type, entity_id, annotation)
        VALUES (?,?,?,?)
    """, (data['image_id'], data['entity_type'], data['entity_id'], data.get('annotation')))
    db.commit()
    return ok(id=cur.lastrowid), 201


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


# ── ENTRY POINT ───────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    print("Starting ILM1300 backend on http://localhost:5000")
    print("API endpoints:")
    print("  GET  /api/health")
    print("  GET  /api/kits          ?q=&brand=")
    print("  GET  /api/kits/<id>")
    print("  GET  /api/parts         ?kit_id=&q=")
    print("  GET  /api/models")
    print("  GET  /api/models/<slug>")
    print("  GET  /api/placements    ?model_id=&kit_id=&map_id=")
    print("  GET  /api/connections   (cross-model)")
    print("  GET  /api/cast_assemblies")
    print("  GET  /api/cast_assemblies/<id>")
    print("  GET  /api/images        ?entity_type=&entity_id=&image_type=")
    print("  GET  /api/contributors")
    app.run(debug=True, port=5000)
