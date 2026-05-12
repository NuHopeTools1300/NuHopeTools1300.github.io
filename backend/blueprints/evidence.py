"""Image evidence API routes."""

import os

from flask import Blueprint, request

try:
    from ..api_utils import err, json_text, ok, rows_to_list, to_bool_int, to_float, to_int
    from ..auth import require_admin
    from ..config import UPLOAD_DIR
    from ..db import get_db
    from ..entity_services import enrich_claim_rows, entity_label as _entity_label
    from ..history_services import record_image_region_history
    from ..image_family_services import (
        detach_image_from_family,
        ensure_family_member,
        get_image_family_map,
        get_image_family_membership,
        get_image_family_payload,
        set_family_primary_image,
    )
    from ..image_services import create_image_v2, update_image_v2
except ImportError:
    from api_utils import err, json_text, ok, rows_to_list, to_bool_int, to_float, to_int
    from auth import require_admin
    from config import UPLOAD_DIR
    from db import get_db
    from entity_services import enrich_claim_rows, entity_label as _entity_label
    from history_services import record_image_region_history
    from image_family_services import (
        detach_image_from_family,
        ensure_family_member,
        get_image_family_map,
        get_image_family_membership,
        get_image_family_payload,
        set_family_primary_image,
    )
    from image_services import create_image_v2, update_image_v2


evidence_bp = Blueprint('evidence', __name__)


@evidence_bp.get('/api/image_families')
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


@evidence_bp.get('/api/image_families/<int:family_id>')
def get_image_family(family_id):
    db = get_db()
    payload = get_image_family_payload(db, family_id)
    if not payload:
        return err('Image family not found', 404)
    return ok(family=payload)


@evidence_bp.post('/api/image_families')
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


@evidence_bp.put('/api/image_families/<int:family_id>')
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


@evidence_bp.delete('/api/image_families/<int:family_id>')
@require_admin
def delete_image_family(family_id):
    db = get_db()
    existing = db.execute("SELECT * FROM image_families WHERE id=?", (family_id,)).fetchone()
    if not existing:
        return err('Image family not found', 404)
    db.execute("DELETE FROM image_families WHERE id=?", (family_id,))
    db.commit()
    return ok()


@evidence_bp.post('/api/image_families/<int:family_id>/members')
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


@evidence_bp.put('/api/image_families/<int:family_id>/members/<int:member_id>')
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


@evidence_bp.delete('/api/image_families/<int:family_id>/members/<int:member_id>')
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


@evidence_bp.get('/api/images')
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

@evidence_bp.get('/api/images/<int:image_id>')
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


@evidence_bp.post('/api/images')
@require_admin
def create_image():
    # BUG FIX: removed 'tags' column (replaced by image_tags table)
    # Handles both JSON body (URL/Drive registration) and multipart file upload
    db = get_db()
    return create_image_v2(db)

@evidence_bp.put('/api/images/<int:image_id>')
@require_admin
def update_image(image_id):
    """Update image metadata and tags."""
    db   = get_db()
    return update_image_v2(db, image_id)

@evidence_bp.delete('/api/images/<int:image_id>')
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


@evidence_bp.get('/api/image_regions')
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


@evidence_bp.get('/api/image_regions/<int:region_id>')
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


@evidence_bp.post('/api/image_regions')
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


@evidence_bp.put('/api/image_regions/<int:region_id>')
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


@evidence_bp.delete('/api/image_regions/<int:region_id>')
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

@evidence_bp.get('/api/image_links')
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

@evidence_bp.post('/api/image_links')
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

@evidence_bp.put('/api/image_links/<int:link_id>')
def update_image_link(link_id):
    data = request.json or {}
    db   = get_db()
    db.execute("UPDATE image_links SET annotation=? WHERE id=?",
               (data.get('annotation'), link_id))
    db.commit()
    return ok()

@evidence_bp.delete('/api/image_links/<int:link_id>')
def delete_image_link(link_id):
    db = get_db()
    db.execute("DELETE FROM image_links WHERE id=?", (link_id,))
    db.commit()
    return ok()


# ── IMAGE TAGS ────────────────────────────────────────────────────

@evidence_bp.post('/api/images/<int:image_id>/tags')
def add_image_tag(image_id):
    data = request.json or {}
    if not data.get('tag'):
        return err("tag is required")
    db = get_db()
    db.execute("INSERT OR IGNORE INTO image_tags (image_id, tag) VALUES (?,?)",
               (image_id, data['tag'].strip()))
    db.commit()
    return ok()

@evidence_bp.delete('/api/images/<int:image_id>/tags/<tag>')
def remove_image_tag(image_id, tag):
    db = get_db()
    db.execute("DELETE FROM image_tags WHERE image_id=? AND tag=?", (image_id, tag))
    db.commit()
    return ok()


# ── CONTRIBUTORS ─────────────────────────────────────────────────

