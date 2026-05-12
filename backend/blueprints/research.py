"""Research, source, contributor, claim, and search API routes."""

import sqlite3

from flask import Blueprint, request

try:
    from ..api_utils import err, ok, rows_to_list, to_int
    from ..auth import require_admin
    from ..db import get_db
    from ..entity_services import enrich_claim_rows
except ImportError:
    from api_utils import err, ok, rows_to_list, to_int
    from auth import require_admin
    from db import get_db
    from entity_services import enrich_claim_rows


research_bp = Blueprint('research', __name__)


@research_bp.get('/api/cast_assemblies')
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

@research_bp.get('/api/cast_assemblies/<int:ca_id>')
def get_cast_assembly(ca_id):
    db = get_db()
    ca = db.execute("SELECT * FROM cast_assemblies WHERE id=?", (ca_id,)).fetchone()
    if not ca:
        return err('Cast assembly not found', 404)
    # The current kits schema no longer carries the old coffman_number column.
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

@research_bp.post('/api/cast_assemblies')
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

@research_bp.post('/api/cast_assemblies/<int:ca_id>/parts')
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


# Sources and research query routes.

@research_bp.get('/api/sources')
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


@research_bp.get('/api/sources/<int:source_id>')
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


@research_bp.post('/api/sources')
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


@research_bp.put('/api/sources/<int:source_id>')
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


@research_bp.get('/api/source_extracts')
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


@research_bp.get('/api/source_extracts/<int:extract_id>')
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


@research_bp.post('/api/source_extracts')
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


@research_bp.put('/api/source_extracts/<int:extract_id>')
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


@research_bp.get('/api/contributors')
def list_contributors():
    db   = get_db()
    rows = rows_to_list(db.execute(
        "SELECT * FROM contributors ORDER BY handle"
    ).fetchall())
    return ok(rows)

@research_bp.post('/api/contributors')
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

@research_bp.get('/api/entity_search')
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
            SELECT id, brand, name, scale, serial_number, category_family, category_subject,
                   thumbnail_url, thumbnail_source_url, thumbnail_fetched_at
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
                'badges': [v for v in [row.get('category_family'), row.get('category_subject')] if v],
                'thumbnail_url': row.get('thumbnail_url'),
                'thumbnail_source_url': row.get('thumbnail_source_url'),
                'thumbnail_fetched_at': row.get('thumbnail_fetched_at')
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


@research_bp.get('/api/claims')
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


@research_bp.get('/api/claims/<int:claim_id>')
def get_claim(claim_id):
    db = get_db()
    row = db.execute("SELECT * FROM claims WHERE id=?", (claim_id,)).fetchone()
    if not row:
        return err('Claim not found', 404)
    claims = enrich_claim_rows([row], db)
    return ok(claim=claims[0])


@research_bp.post('/api/claims')
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


@research_bp.put('/api/claims/<int:claim_id>')
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


@research_bp.delete('/api/claims/<int:claim_id>')
@require_admin
def delete_claim(claim_id):
    db = get_db()
    db.execute("DELETE FROM claims WHERE id=?", (claim_id,))
    db.commit()
    return ok()


@research_bp.get('/api/search')
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

