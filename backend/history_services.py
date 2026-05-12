"""Audit/history write helpers."""

import json


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
