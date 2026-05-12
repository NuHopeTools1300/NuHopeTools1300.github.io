"""Spreadsheet import orchestration helpers."""

import os

try:
    from . import import_spreadsheets as spreadsheet_importer
    from .config import BASE_DIR
except ImportError:
    import import_spreadsheets as spreadsheet_importer
    from config import BASE_DIR


def resolve_spreadsheet_path(path_value):
    raw = str(path_value or '').strip()
    if not raw:
        return None
    if os.path.isabs(raw):
        return os.path.abspath(raw)
    repo_root = os.path.dirname(BASE_DIR)
    return os.path.abspath(os.path.join(repo_root, raw))


def run_spreadsheet_import_pipeline(db, kits_path=None, donors_path=None, dry_run=False):
    report = {}
    preview = {
        'kits': {},
        'donors': {}
    }

    if kits_path:
        preview['kits']['kits_imported'] = spreadsheet_importer.import_kits(kits_path, db)
        preview['kits']['maps_imported_or_updated'] = spreadsheet_importer.import_maps(kits_path, db)
        preview['kits']['parts_imported'] = spreadsheet_importer.import_parts(
            kits_path,
            db,
            dry_run=dry_run,
            report=report
        )
        preview['kits']['part_files_imported'] = spreadsheet_importer.import_3d_parts(kits_path, db)

    if donors_path:
        preview['donors']['placements_recorded'] = spreadsheet_importer.import_donors(
            donors_path,
            db,
            dry_run=dry_run,
            report=report
        )

    return preview, report
