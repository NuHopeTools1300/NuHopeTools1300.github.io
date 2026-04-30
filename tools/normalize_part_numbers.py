#!/usr/bin/env python
"""Normalize safe decimal-zero part numbers in the local SQLite database.

Part numbers are identifiers, not measurements. This script only changes exact
integer-looking decimal values such as "8.0" or "236.00" to "8" and "236".
Alphanumeric and compound identifiers are left untouched.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "data" / "ilm1300.db"
BACKUP_PATH = DB_PATH.with_name(f"{DB_PATH.name}.bak.normalize_part_numbers")
SAFE_DECIMAL_RE = re.compile(r"^(\d+)\.0+$")


def normalized_part_number(value: object) -> str | None:
    text = "" if value is None else str(value).strip()
    match = SAFE_DECIMAL_RE.fullmatch(text)
    return match.group(1) if match else None


def collect_updates(db: sqlite3.Connection) -> list[tuple[str, int, str]]:
    rows = db.execute("SELECT id, part_number FROM parts ORDER BY id").fetchall()
    updates: list[tuple[str, int, str]] = []
    for part_id, part_number in rows:
        normalized = normalized_part_number(part_number)
        if normalized and normalized != str(part_number):
            updates.append((normalized, part_id, str(part_number)))
    return updates


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="report changes without writing")
    args = parser.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    db = sqlite3.connect(DB_PATH)
    try:
        updates = collect_updates(db)
        print(f"Safe decimal-zero part numbers found: {len(updates)}")
        for normalized, part_id, original in updates[:20]:
            print(f"  part {part_id}: {original} -> {normalized}")
        if len(updates) > 20:
            print(f"  ... {len(updates) - 20} more")

        if args.dry_run or not updates:
            return 0

        if not BACKUP_PATH.exists():
            shutil.copy2(DB_PATH, BACKUP_PATH)
            print(f"Backup written: {BACKUP_PATH}")
        else:
            print(f"Backup already exists: {BACKUP_PATH}")

        db.executemany(
            "UPDATE parts SET part_number=? WHERE id=?",
            [(normalized, part_id) for normalized, part_id, _ in updates],
        )
        db.commit()
        print(f"Normalized part numbers: {len(updates)}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
