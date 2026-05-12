"""Image family membership helpers."""

try:
    from .api_utils import rows_to_list, to_int
except ImportError:
    from api_utils import rows_to_list, to_int


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
