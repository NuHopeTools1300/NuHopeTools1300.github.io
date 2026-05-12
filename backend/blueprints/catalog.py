"""Catalog API routes for kits, parts, models, and maps."""

import sqlite3

from flask import Blueprint, request

try:
    from ..api_utils import err, ok, rows_to_list, to_int
    from ..auth import require_admin
    from ..db import get_db
    from ..history_services import record_kit_history
except ImportError:
    from api_utils import err, ok, rows_to_list, to_int
    from auth import require_admin
    from db import get_db
    from history_services import record_kit_history


catalog_bp = Blueprint('catalog', __name__, url_prefix='/api')


@catalog_bp.get('/kits')
def list_kits():
    db = get_db()
    q = request.args.get('q', '').strip()
    brand = request.args.get('brand', '').strip()
    family = request.args.get('category_family', '').strip()
    subject = request.args.get('category_subject', '').strip()

    sql = "SELECT * FROM kits WHERE 1=1"
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


@catalog_bp.get('/kits/<int:kit_id>')
def get_kit(kit_id):
    db = get_db()
    kit = db.execute("SELECT * FROM kits WHERE id=?", (kit_id,)).fetchone()
    if not kit:
        return err('Kit not found', 404)
    parts = rows_to_list(db.execute(
        "SELECT * FROM parts WHERE kit_id=? ORDER BY part_number", (kit_id,)
    ).fetchall())
    references = rows_to_list(db.execute(
        "SELECT * FROM kit_references WHERE kit_id=? ORDER BY system", (kit_id,)
    ).fetchall())
    models = rows_to_list(db.execute("""
        SELECT DISTINCT m.id, m.name, m.slug, m.film
        FROM models m
        JOIN placements p ON p.model_id = m.id
        JOIN parts pt     ON pt.id = p.part_id
        WHERE pt.kit_id = ?
        ORDER BY m.name
    """, (kit_id,)).fetchall())
    images = rows_to_list(db.execute("""
        SELECT i.*, il.annotation
        FROM images i
        JOIN image_links il ON il.image_id = i.id
        WHERE il.entity_type = 'kit' AND il.entity_id = ?
        ORDER BY i.date_taken
    """, (kit_id,)).fetchall())
    return ok(kit=dict(kit), parts=parts, references=references,
              used_on_models=models, images=images)


@catalog_bp.post('/kits')
@require_admin
def create_kit():
    data = request.json or {}
    missing = [f for f in ('brand', 'name') if not data.get(f)]
    if missing:
        return err(f"Missing required fields: {', '.join(missing)}")
    db = get_db()
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
    try:
        record_kit_history(db, cur.lastrowid, 'create', prev_values=None, new_values=data, changed_by=data.get('changed_by'))
    except Exception:
        pass
    return ok(id=cur.lastrowid), 201


@catalog_bp.put('/kits/<int:kit_id>')
@require_admin
def update_kit(kit_id):
    data = request.json or {}
    db = get_db()
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
        new = db.execute("SELECT * FROM kits WHERE id=?", (kit_id,)).fetchone()
        new_dict = dict(new) if new else None
        record_kit_history(db, kit_id, 'update', prev_values=prev_dict, new_values=new_dict, changed_by=data.get('changed_by'), reason=data.get('reason'))
    except Exception:
        pass
    return ok()


@catalog_bp.get('/kits/<int:kit_id>/references')
def list_kit_references(kit_id):
    db = get_db()
    rows = db.execute(
        "SELECT * FROM kit_references WHERE kit_id=? ORDER BY system", (kit_id,)
    ).fetchall()
    return ok(rows_to_list(rows))


@catalog_bp.post('/kits/<int:kit_id>/references')
def create_kit_reference(kit_id):
    data = request.json or {}
    missing = [f for f in ('system', 'value') if not data.get(f)]
    if missing:
        return err(f"Missing required fields: {', '.join(missing)}")
    db = get_db()
    try:
        cur = db.execute("""
            INSERT INTO kit_references (kit_id, system, value, notes)
            VALUES (?,?,?,?)
        """, (kit_id, data['system'], data['value'], data.get('notes')))
        db.commit()
        return ok(id=cur.lastrowid), 201
    except sqlite3.IntegrityError:
        return err(f"Reference for system '{data['system']}' already exists on this kit")


@catalog_bp.delete('/kits/<int:kit_id>/references/<int:ref_id>')
def delete_kit_reference(kit_id, ref_id):
    db = get_db()
    db.execute("DELETE FROM kit_references WHERE id=? AND kit_id=?", (ref_id, kit_id))
    db.commit()
    return ok()


@catalog_bp.get('/kits/<int:kit_id>/history')
def get_kit_history(kit_id):
    db = get_db()
    rows = db.execute("SELECT * FROM kit_history WHERE kit_id=? ORDER BY changed_at DESC", (kit_id,)).fetchall()
    return ok(rows_to_list(rows))


@catalog_bp.get('/parts')
def list_parts():
    db = get_db()
    kit_id = request.args.get('kit_id')
    q = request.args.get('q', '').strip()

    sql = """
        SELECT p.*, k.brand, k.name as kit_name,
               COALESCE(
                   (
                       SELECT pf.url
                       FROM part_files pf
                       WHERE pf.part_id = p.id
                         AND pf.url IS NOT NULL
                         AND TRIM(pf.url) != ''
                       ORDER BY
                         CASE WHEN pf.url LIKE '/api/part_images/%' THEN 0 ELSE 1 END,
                         pf.file_type, pf.id
                       LIMIT 1
                   ),
                   (
                       SELECT COALESCE(i.url, CASE WHEN i.filename IS NOT NULL AND i.filename != '' THEN '/uploads/' || i.filename ELSE NULL END)
                       FROM image_links il
                       JOIN images i ON i.id = il.image_id
                       WHERE il.entity_type = 'part'
                         AND il.entity_id = p.id
                       ORDER BY i.date_taken, i.id
                       LIMIT 1
                   )
               ) AS thumbnail_url,
               (SELECT COUNT(*) FROM part_files pf WHERE pf.part_id = p.id) AS file_count,
               (
                   SELECT COUNT(*)
                   FROM image_links il
                   WHERE il.entity_type = 'part'
                     AND il.entity_id = p.id
               ) AS image_count
        FROM parts p
        JOIN kits k ON k.id=p.kit_id
        WHERE 1=1
    """
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


@catalog_bp.get('/parts/<int:part_id>')
def get_part(part_id):
    db = get_db()
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


@catalog_bp.post('/parts')
@require_admin
def create_part():
    data = request.json or {}
    missing = [f for f in ('kit_id', 'part_number') if not data.get(f)]
    if missing:
        return err(f"Missing required fields: {', '.join(missing)}")
    db = get_db()
    cur = db.execute("""
        INSERT INTO parts (kit_id, part_number, part_label, notes, attributed_to)
        VALUES (?,?,?,?,?)
    """, (data['kit_id'], data['part_number'],
          data.get('part_label'), data.get('notes'), data.get('attributed_to')))
    db.commit()
    return ok(id=cur.lastrowid), 201


@catalog_bp.put('/parts/<int:part_id>')
@require_admin
def update_part(part_id):
    data = request.json or {}
    db = get_db()
    db.execute("""
        UPDATE parts SET part_number=?, part_label=?, notes=?, attributed_to=?
        WHERE id=?
    """, (data.get('part_number'), data.get('part_label'),
          data.get('notes'), data.get('attributed_to'), part_id))
    db.commit()
    return ok()


@catalog_bp.post('/parts/<int:part_id>/files')
@require_admin
def create_part_file(part_id):
    data = request.json or {}
    missing = [f for f in ('file_type', 'url') if not data.get(f)]
    if missing:
        return err(f"Missing required fields: {', '.join(missing)}")
    db = get_db()
    cur = db.execute("""
        INSERT INTO part_files (part_id, file_type, url, source, notes, attributed_to)
        VALUES (?,?,?,?,?,?)
    """, (part_id, data['file_type'], data['url'],
          data.get('source'), data.get('notes'), data.get('attributed_to')))
    db.commit()
    return ok(id=cur.lastrowid), 201


@catalog_bp.delete('/parts/<int:part_id>/files/<int:file_id>')
@require_admin
def delete_part_file(part_id, file_id):
    db = get_db()
    db.execute("DELETE FROM part_files WHERE id=? AND part_id=?", (file_id, part_id))
    db.commit()
    return ok()


@catalog_bp.get('/models')
def list_models():
    db = get_db()
    rows = db.execute("SELECT * FROM models ORDER BY film, name").fetchall()
    return ok(rows_to_list(rows))


@catalog_bp.get('/models/<slug>')
def get_model(slug):
    db = get_db()
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


@catalog_bp.post('/models')
def create_model():
    data = request.json or {}
    missing = [f for f in ('name', 'slug') if not data.get(f)]
    if missing:
        return err(f"Missing required fields: {', '.join(missing)}")
    db = get_db()
    cur = db.execute("""
        INSERT INTO models (name, slug, film, scale_approx, notes)
        VALUES (?,?,?,?,?)
    """, (data['name'], data['slug'], data.get('film'),
          data.get('scale_approx'), data.get('notes')))
    db.commit()
    return ok(id=cur.lastrowid), 201


@catalog_bp.put('/models/<int:model_id>')
@require_admin
def update_model(model_id):
    data = request.json or {}
    db = get_db()
    old = db.execute("SELECT * FROM models WHERE id=?", (model_id,)).fetchone()
    if not old:
        return err('Model not found', 404)
    merged = {
        'name': data.get('name', old['name']),
        'slug': data.get('slug', old['slug']),
        'film': data.get('film', old['film']),
        'scale_approx': data.get('scale_approx', old['scale_approx']),
        'notes': data.get('notes', old['notes'])
    }
    if not merged['name']:
        return err('name is required')
    if not merged['slug']:
        return err('slug is required')
    try:
        db.execute("""
            UPDATE models SET name=?, slug=?, film=?, scale_approx=?, notes=?
            WHERE id=?
        """, (
            merged['name'], merged['slug'], merged['film'],
            merged['scale_approx'], merged['notes'], model_id
        ))
        db.commit()
    except sqlite3.IntegrityError as exc:
        return err(str(exc), 409)
    return ok()


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


@catalog_bp.get('/maps')
def list_maps():
    db = get_db()
    model_id = request.args.get('model_id')
    if model_id:
        rows = db.execute(
            f"{map_select_sql()} WHERE mp.model_id=? ORDER BY mp.name", (model_id,)
        ).fetchall()
    else:
        rows = db.execute(f"{map_select_sql()} ORDER BY mp.name").fetchall()
    return ok(rows_to_list(rows))


@catalog_bp.post('/maps')
def create_map():
    data = request.json or {}
    missing = [f for f in ('model_id', 'name') if not data.get(f)]
    if missing:
        return err(f"Missing required fields: {', '.join(missing)}")
    db = get_db()
    cur = db.execute("""
        INSERT INTO maps (model_id, name, version, image_id, url, map_date, attributed_to, notes)
        VALUES (?,?,?,?,?,?,?,?)
    """, (data['model_id'], data['name'], data.get('version'),
          to_int(data.get('image_id')),
          data.get('url'), data.get('map_date'),
          data.get('attributed_to'), data.get('notes')))
    db.commit()
    return ok(id=cur.lastrowid), 201


@catalog_bp.put('/maps/<int:map_id>')
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
