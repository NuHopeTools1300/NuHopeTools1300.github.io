"""Import and import-cleanup API routes."""

import os
import re
import sqlite3

from flask import Blueprint, request

try:
    from ..api_utils import err, ok, rows_to_list
    from ..auth import require_admin
    from ..config import DB_PATH
    from ..db import get_db
    from ..import_services import resolve_spreadsheet_path, run_spreadsheet_import_pipeline
except ImportError:
    from api_utils import err, ok, rows_to_list
    from auth import require_admin
    from config import DB_PATH
    from db import get_db
    from import_services import resolve_spreadsheet_path, run_spreadsheet_import_pipeline


imports_bp = Blueprint('imports', __name__, url_prefix='/api/imports')


@imports_bp.post('/reconciliation_preview')
@require_admin
def import_reconciliation_preview():
    data = request.json or {}
    kits_path = resolve_spreadsheet_path(data.get('kits_path'))
    donors_path = resolve_spreadsheet_path(data.get('donors_path'))

    if not kits_path and not donors_path:
        return err('Provide kits_path and/or donors_path')
    if kits_path and not os.path.exists(kits_path):
        return err(f'kits_path not found: {kits_path}', 404)
    if donors_path and not os.path.exists(donors_path):
        return err(f'donors_path not found: {donors_path}', 404)

    db_preview = sqlite3.connect(':memory:')
    db_preview.row_factory = sqlite3.Row
    db_preview.execute('PRAGMA foreign_keys = ON')
    db_source = sqlite3.connect(DB_PATH)
    try:
        db_source.backup(db_preview)
        preview, report = run_spreadsheet_import_pipeline(
            db_preview,
            kits_path=kits_path,
            donors_path=donors_path,
            dry_run=True
        )
        db_preview.rollback()
    finally:
        db_source.close()
        db_preview.close()

    return ok(
        preview=preview,
        reconciliation_report=report,
        resolved_paths={
            'kits_path': kits_path,
            'donors_path': donors_path
        }
    )


@imports_bp.post('/reconcile_apply')
@require_admin
def import_reconcile_apply():
    data = request.json or {}
    kits_path = resolve_spreadsheet_path(data.get('kits_path'))
    donors_path = resolve_spreadsheet_path(data.get('donors_path'))

    if not kits_path and not donors_path:
        return err('Provide kits_path and/or donors_path')
    if kits_path and not os.path.exists(kits_path):
        return err(f'kits_path not found: {kits_path}', 404)
    if donors_path and not os.path.exists(donors_path):
        return err(f'donors_path not found: {donors_path}', 404)

    db = get_db()
    preview, report = run_spreadsheet_import_pipeline(
        db,
        kits_path=kits_path,
        donors_path=donors_path,
        dry_run=False
    )

    return ok(
        applied=True,
        preview=preview,
        reconciliation_report=report,
        resolved_paths={
            'kits_path': kits_path,
            'donors_path': donors_path
        }
    )


@imports_bp.post('/normalize_part_numbers')
@require_admin
def normalize_part_numbers_import_endpoint():
    data = request.json or {}
    apply_updates = bool(data.get('apply'))
    db = get_db()

    rows = rows_to_list(db.execute("SELECT id, part_number FROM parts ORDER BY id").fetchall())
    updates = []
    for row in rows:
        value = str(row.get('part_number') or '').strip()
        match = re.fullmatch(r'(\d+)\.0+', value)
        if match and value != match.group(1):
            updates.append({
                'id': row['id'],
                'from': value,
                'to': match.group(1)
            })

    if apply_updates and updates:
        db.executemany(
            "UPDATE parts SET part_number=? WHERE id=?",
            [(item['to'], item['id']) for item in updates]
        )
        db.commit()

    return ok(
        applied=apply_updates,
        update_count=len(updates),
        updates=updates[:100]
    )
