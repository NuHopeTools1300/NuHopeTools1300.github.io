"""Placement, placement-position, and connection API routes."""

import sqlite3

from flask import Blueprint, request

try:
    from ..api_utils import err, json_text, ok, rows_to_list, to_float, to_int
    from ..auth import require_admin
    from ..db import get_db
    from ..entity_services import enrich_claim_rows
    from ..placement_services import (
        attach_part_file_summaries,
        ensure_single_current_position_per_map,
        placement_identity_kind,
        rows_for_placement_positions,
        set_current_position,
    )
except ImportError:
    from api_utils import err, json_text, ok, rows_to_list, to_float, to_int
    from auth import require_admin
    from db import get_db
    from entity_services import enrich_claim_rows
    from placement_services import (
        attach_part_file_summaries,
        ensure_single_current_position_per_map,
        placement_identity_kind,
        rows_for_placement_positions,
        set_current_position,
    )


placements_bp = Blueprint('placements', __name__)


@placements_bp.get('/api/placements')
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
               k.id as resolved_kit_id,
               k.brand, k.name as kit_name,
               k.thumbnail_url,
               k.thumbnail_source_url,
               k.thumbnail_fetched_at,
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
    attach_part_file_summaries(db, rows)
    return ok(rows, count=len(rows))

@placements_bp.get('/api/placements/<int:pl_id>')
def get_placement(pl_id):
    db = get_db()
    pl = db.execute("""
        SELECT pl.*,
               m.name  as model_name,
               mp.name as map_name,
               pt.part_number, pt.part_label,
               k.id as resolved_kit_id,
               k.brand, k.name as kit_name,
               k.thumbnail_url,
               k.thumbnail_source_url,
               k.thumbnail_fetched_at,
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
        SELECT i.*, il.id AS image_link_id, il.annotation
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
    claim_rows = rows_to_list(db.execute("""
        SELECT DISTINCT c.*
        FROM claims c
        WHERE (c.subject_type='placement' AND c.subject_id=?)
           OR (c.object_type='placement' AND c.object_id=?)
        ORDER BY c.updated_at DESC, c.id DESC
    """, (pl_id, pl_id)).fetchall())
    claims = enrich_claim_rows(claim_rows, db)
    positions = rows_for_placement_positions(db, placement_id=pl_id)
    placement = dict(pl)
    attach_part_file_summaries(db, [placement])
    part_files = []
    part_id = pl['part_id']
    part_number = str(pl['part_number'] or '').strip() if 'part_number' in pl.keys() else ''
    if part_id:
        part_files = rows_to_list(db.execute("""
            SELECT *
            FROM part_files
            WHERE part_id=?
              AND TRIM(COALESCE(url, '')) <> ''
            ORDER BY
              CASE WHEN url LIKE '/api/part_images/%' THEN 0 ELSE 1 END,
              file_type, source, id
        """, (part_id,)).fetchall())
        if not part_files and part_number:
            part_files = rows_to_list(db.execute("""
                SELECT pf.*
                FROM part_files pf
                JOIN parts p ON p.id = pf.part_id
                WHERE p.part_number=?
                  AND TRIM(COALESCE(pf.url, '')) <> ''
                ORDER BY
                  CASE WHEN pf.url LIKE '/api/part_images/%' THEN 0 ELSE 1 END,
                  pf.file_type, pf.source, pf.id
            """, (part_number,)).fetchall())
    return ok(placement=placement, contributors=contributors,
              images=images, part_files=part_files,
              history=history, claims=claims, positions=positions,
              current_position=next((row for row in positions if row.get('is_current')), None))

@placements_bp.post('/api/placements')
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

@placements_bp.put('/api/placements/<int:pl_id>')
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

@placements_bp.delete('/api/placements/<int:pl_id>')
@require_admin
def delete_placement(pl_id):
    db = get_db()
    db.execute("DELETE FROM placements WHERE id=?", (pl_id,))
    db.commit()
    return ok()


@placements_bp.get('/api/placements/refinement_queue')
@placements_bp.get('/api/placements/refinement-queue')
def list_refinement_queue():
    db = get_db()
    model_id = to_int(request.args.get('model_id'))
    map_id = to_int(request.args.get('map_id'))
    q = request.args.get('q', '').strip()

    sql = """
        SELECT pl.*,
               m.name AS model_name,
               mp.name AS map_name,
               k.id AS resolved_kit_id,
               k.brand,
               k.name AS kit_name,
               k.thumbnail_url,
               k.thumbnail_source_url,
               k.thumbnail_fetched_at
        FROM placements pl
        JOIN models m ON m.id = pl.model_id
        LEFT JOIN maps mp ON mp.id = pl.map_id
        LEFT JOIN kits k ON k.id = pl.kit_id
        WHERE pl.part_id IS NULL
          AND pl.cast_assembly_id IS NULL
          AND pl.kit_id IS NOT NULL
    """
    params = []
    if model_id:
        sql += " AND pl.model_id=?"
        params.append(model_id)
    if map_id:
        sql += " AND pl.map_id=?"
        params.append(map_id)
    if q:
        sql += " AND (COALESCE(pl.location_label,'') LIKE ? OR COALESCE(k.brand,'') LIKE ? OR COALESCE(k.name,'') LIKE ?)"
        like = f'%{q}%'
        params.extend([like, like, like])
    sql += " ORDER BY m.name, mp.name, k.brand, k.name, pl.id"

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


@placements_bp.post('/api/placements/<int:pl_id>/refine_part')
@placements_bp.post('/api/placements/<int:pl_id>/refine')
@require_admin
def refine_placement_to_part(pl_id):
    data = request.json or {}
    part_id = to_int(data.get('part_id'))
    if not part_id:
        return err('part_id is required')

    db = get_db()
    placement = db.execute("SELECT * FROM placements WHERE id=?", (pl_id,)).fetchone()
    if not placement:
        return err('Placement not found', 404)
    if placement_identity_kind(placement) != 'kit':
        return err('Only kit-level placements can be refined with this endpoint', 409)

    part = db.execute("SELECT id, kit_id, part_number, part_label FROM parts WHERE id=?", (part_id,)).fetchone()
    if not part:
        return err('Part not found', 404)
    if placement['kit_id'] and part['kit_id'] != placement['kit_id']:
        return err('part_id must belong to the same kit as the kit-level placement', 409)

    change_reason = data.get('change_reason') or data.get('reason')

    db.execute("""
        INSERT INTO placement_history
            (placement_id, changed_by, prev_part_id, prev_kit_id, prev_confidence, prev_notes, reason)
        VALUES (?,?,?,?,?,?,?)
    """, (
        pl_id,
        to_int(data.get('changed_by')),
        placement['part_id'],
        placement['kit_id'],
        placement['confidence'],
        placement['notes'],
        change_reason or f"Refined kit-level placement to part {part['part_number']}"
    ))

    next_confidence = data.get('confidence', placement['confidence'])
    notes_append = (data.get('notes_append') or '').strip()
    if notes_append:
        current_notes = (placement['notes'] or '').strip()
        next_notes = f"{current_notes}\n{notes_append}".strip() if current_notes else notes_append
    else:
        next_notes = placement['notes']

    db.execute("""
        UPDATE placements
        SET part_id=?, kit_id=NULL, cast_assembly_id=NULL, confidence=?, notes=?
        WHERE id=?
    """, (part_id, next_confidence, next_notes, pl_id))
    db.commit()

    return ok(
        id=pl_id,
        part_id=part_id,
        message='Placement refined from kit-level to part-level.'
    )


@placements_bp.post('/api/placements/merge')
@require_admin
def merge_placements():
    data = request.json or {}
    canonical_id = to_int(data.get('canonical_id')) or to_int(data.get('primary_id'))
    duplicate_values = data.get('duplicate_ids')
    if duplicate_values is None:
        duplicate_values = data.get('merge_ids') or []
    duplicate_ids = [to_int(v) for v in duplicate_values if to_int(v)]
    reason = (data.get('reason') or '').strip() or 'Merged duplicate placement records.'
    changed_by = to_int(data.get('changed_by'))

    if not canonical_id:
        return err('canonical_id is required')
    duplicate_ids = [pid for pid in duplicate_ids if pid and pid != canonical_id]
    if not duplicate_ids:
        return err('duplicate_ids must include at least one placement id distinct from canonical_id')

    db = get_db()
    canonical = db.execute("SELECT * FROM placements WHERE id=?", (canonical_id,)).fetchone()
    if not canonical:
        return err('Canonical placement not found', 404)

    rows = rows_to_list(db.execute(
        f"SELECT * FROM placements WHERE id IN ({','.join('?' for _ in duplicate_ids)})",
        duplicate_ids
    ).fetchall())
    if len(rows) != len(duplicate_ids):
        return err('One or more duplicate placement ids were not found', 404)

    canonical_kind = placement_identity_kind(canonical)
    moved_positions = 0
    moved_claim_refs = 0
    moved_image_links = 0
    moved_contributors = 0

    for duplicate in rows:
        if duplicate['model_id'] != canonical['model_id']:
            return err('All merged placements must belong to the same model as canonical placement', 409)
        if canonical_kind != 'unknown' and placement_identity_kind(duplicate) != canonical_kind:
            return err('Only placements of the same identity kind can be merged', 409)

    for duplicate in rows:
        duplicate_id = duplicate['id']

        db.execute("""
            INSERT OR IGNORE INTO image_links (image_id, entity_type, entity_id, annotation)
            SELECT image_id, entity_type, ?, annotation
            FROM image_links
            WHERE entity_type='placement' AND entity_id=?
        """, (canonical_id, duplicate_id))
        moved_image_links += db.execute(
            "SELECT changes() AS c"
        ).fetchone()['c']
        db.execute("DELETE FROM image_links WHERE entity_type='placement' AND entity_id=?", (duplicate_id,))

        db.execute("""
            INSERT OR IGNORE INTO placement_contributors (placement_id, contributor_id, role, notes)
            SELECT ?, contributor_id, role, notes
            FROM placement_contributors
            WHERE placement_id=?
        """, (canonical_id, duplicate_id))
        moved_contributors += db.execute(
            "SELECT changes() AS c"
        ).fetchone()['c']
        db.execute("DELETE FROM placement_contributors WHERE placement_id=?", (duplicate_id,))

        db.execute(
            "UPDATE claims SET subject_id=? WHERE subject_type='placement' AND subject_id=?",
            (canonical_id, duplicate_id)
        )
        moved_claim_refs += db.execute("SELECT changes() AS c").fetchone()['c']
        db.execute(
            "UPDATE claims SET object_id=? WHERE object_type='placement' AND object_id=?",
            (canonical_id, duplicate_id)
        )
        moved_claim_refs += db.execute("SELECT changes() AS c").fetchone()['c']

        db.execute(
            "UPDATE placement_positions SET placement_id=? WHERE placement_id=?",
            (canonical_id, duplicate_id)
        )
        moved_positions += db.execute("SELECT changes() AS c").fetchone()['c']

        db.execute("""
            INSERT INTO placement_history
                (placement_id, changed_by, prev_part_id, prev_kit_id, prev_confidence, prev_notes, reason)
            VALUES (?,?,?,?,?,?,?)
        """, (
            canonical_id,
            changed_by,
            duplicate.get('part_id'),
            duplicate.get('kit_id'),
            duplicate.get('confidence'),
            duplicate.get('notes'),
            f"Merged placement #{duplicate_id} into #{canonical_id}. {reason}"
        ))

        db.execute("DELETE FROM placements WHERE id=?", (duplicate_id,))

    ensure_single_current_position_per_map(db, canonical_id)
    db.commit()

    return ok(
        canonical_id=canonical_id,
        merged_count=len(rows),
        moved_positions=moved_positions,
        moved_claim_refs=moved_claim_refs,
        moved_image_links=moved_image_links,
        moved_contributors=moved_contributors
    )


@placements_bp.get('/api/placement_positions')
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


@placements_bp.get('/api/placement_positions/<int:position_id>')
def get_placement_position(position_id):
    db = get_db()
    rows = rows_for_placement_positions(db, position_id=position_id)
    if not rows:
        return err('Placement position not found', 404)
    return ok(position=rows[0])


@placements_bp.post('/api/placement_positions')
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


@placements_bp.put('/api/placement_positions/<int:position_id>')
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


@placements_bp.delete('/api/placement_positions/<int:position_id>')
@require_admin
def delete_placement_position(position_id):
    db = get_db()
    old = db.execute("SELECT * FROM placement_positions WHERE id=?", (position_id,)).fetchone()
    if not old:
        return err('Placement position not found', 404)
    if old['source_kind'] not in ('manual', 'candidate') and old['status'] != 'candidate':
        return err('Only manual or candidate position records can be deleted', 409)
    # Preserve the supersedes chain so deleting one record does not violate FK constraints.
    db.execute(
        "UPDATE placement_positions SET supersedes_id=? WHERE supersedes_id=?",
        (old['supersedes_id'], position_id)
    )
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

@placements_bp.post('/api/placements/<int:pl_id>/contributors')
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

@placements_bp.delete('/api/placements/<int:pl_id>/contributors/<int:contrib_id>')
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

@placements_bp.get('/api/connections')
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

