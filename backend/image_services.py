"""Image create/update service helpers used by Flask routes."""

import hashlib
import os

from flask import request

try:
    from .api_utils import (
        allowed_file,
        err,
        normalize_tags,
        ok,
        to_bool_int,
        to_int,
    )
    from .config import UPLOAD_DIR
    from .image_family_services import (
        detach_image_from_family,
        ensure_family_member,
        set_family_primary_image,
    )
except ImportError:
    from api_utils import (
        allowed_file,
        err,
        normalize_tags,
        ok,
        to_bool_int,
        to_int,
    )
    from config import UPLOAD_DIR
    from image_family_services import (
        detach_image_from_family,
        ensure_family_member,
        set_family_primary_image,
    )


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
