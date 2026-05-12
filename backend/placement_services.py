"""Placement and placement-position helper logic."""

import sqlite3

try:
    from .api_utils import rows_to_list
except ImportError:
    from api_utils import rows_to_list


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


def attach_part_file_summaries(db, rows):
    part_ids = sorted({
        row.get('part_id')
        for row in rows
        if row.get('part_id')
    })
    if not part_ids:
        return rows

    placeholders = ','.join('?' for _ in part_ids)
    files = rows_to_list(db.execute(f"""
        SELECT part_id, url, file_type, source
        FROM part_files
        WHERE part_id IN ({placeholders})
          AND TRIM(COALESCE(url, '')) <> ''
        ORDER BY
          CASE WHEN url LIKE '/api/part_images/%' THEN 0 ELSE 1 END,
          file_type, source, id
    """, part_ids).fetchall())
    by_part = {}
    for file_row in files:
        summary = by_part.setdefault(file_row['part_id'], {
            'part_reference_url': file_row['url'],
            'part_reference_type': file_row['file_type'],
            'part_reference_source': file_row['source'],
            'part_reference_count': 0
        })
        summary['part_reference_count'] += 1

    missing_part_numbers = sorted({
        str(row.get('part_number')).strip()
        for row in rows
        if row.get('part_id') and not by_part.get(row.get('part_id')) and str(row.get('part_number') or '').strip()
    })
    by_part_number = {}
    if missing_part_numbers:
        placeholders = ','.join('?' for _ in missing_part_numbers)
        fallback_files = rows_to_list(db.execute(f"""
            SELECT p.part_number, pf.url, pf.file_type, pf.source
            FROM part_files pf
            JOIN parts p ON p.id = pf.part_id
            WHERE p.part_number IN ({placeholders})
              AND TRIM(COALESCE(pf.url, '')) <> ''
            ORDER BY
              p.part_number,
              CASE WHEN pf.url LIKE '/api/part_images/%' THEN 0 ELSE 1 END,
              pf.file_type, pf.source, pf.id
        """, missing_part_numbers).fetchall())
        for file_row in fallback_files:
            pn = str(file_row.get('part_number') or '').strip()
            if not pn:
                continue
            summary = by_part_number.setdefault(pn, {
                'part_reference_url': file_row['url'],
                'part_reference_type': file_row['file_type'],
                'part_reference_source': file_row['source'],
                'part_reference_count': 0
            })
            summary['part_reference_count'] += 1

    for row in rows:
        summary = by_part.get(row.get('part_id'))
        if not summary:
            pn = str(row.get('part_number') or '').strip()
            summary = by_part_number.get(pn) if pn else None
        if summary:
            row.update(summary)
        else:
            row['part_reference_url'] = None
            row['part_reference_type'] = None
            row['part_reference_source'] = None
            row['part_reference_count'] = 0
    return rows


def set_current_position(db, placement_id, map_id, position_id):
    db.execute(
        "UPDATE placement_positions SET is_current=0 WHERE placement_id=? AND map_id=? AND id<>?",
        (placement_id, map_id, position_id)
    )
    db.execute(
        "UPDATE placement_positions SET is_current=1, status='active' WHERE id=?",
        (position_id,)
    )


def placement_identity_kind(placement_row):
    row = dict(placement_row) if isinstance(placement_row, sqlite3.Row) else dict(placement_row or {})
    if row.get('part_id'):
        return 'part'
    if row.get('cast_assembly_id'):
        return 'cast_assembly'
    if row.get('kit_id'):
        return 'kit'
    return 'unknown'


def ensure_single_current_position_per_map(db, placement_id):
    map_rows = rows_to_list(db.execute(
        "SELECT DISTINCT map_id FROM placement_positions WHERE placement_id=?",
        (placement_id,)
    ).fetchall())
    for map_row in map_rows:
        map_id = map_row['map_id']
        positions = rows_to_list(db.execute("""
            SELECT id, is_current, status
            FROM placement_positions
            WHERE placement_id=? AND map_id=?
            ORDER BY is_current DESC, created_at DESC, id DESC
        """, (placement_id, map_id)).fetchall())
        if not positions:
            continue
        preferred = next((p for p in positions if p['is_current'] and p['status'] == 'active'), None)
        if not preferred:
            preferred = next((p for p in positions if p['status'] == 'active'), None)
        if not preferred:
            preferred = positions[0]
        db.execute(
            "UPDATE placement_positions SET is_current=0 WHERE placement_id=? AND map_id=?",
            (placement_id, map_id)
        )
        db.execute(
            "UPDATE placement_positions SET is_current=1, status='active' WHERE id=?",
            (preferred['id'],)
        )
