from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "data" / "ilm1300.db"


def row_dict(row: sqlite3.Row) -> dict:
    return {key: row[key] for key in row.keys()}


def load_review(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def selected_mappings(rows: list[dict]) -> dict[str, int]:
    mappings: dict[str, int] = {}
    for row in rows:
        decision = (row.get("decision") or "").strip().lower()
        selected = str(row.get("selected_kit_id") or "").strip()
        if not selected or decision in {"decline", "skip"}:
            continue
        mappings[row["label_text"]] = int(selected)
    return mappings


def pptx_regions_for_label(db: sqlite3.Connection, label: str) -> list[sqlite3.Row]:
    return db.execute(
        """
        SELECT *
        FROM image_regions
        WHERE (label=? OR object_name=?)
          AND (
            properties_json LIKE '%"import_source": "Kit_images.pptx"%'
            OR notes LIKE '%label_status=%'
          )
        ORDER BY id
        """,
        (label, label),
    ).fetchall()


def apply_review(db: sqlite3.Connection, review_rows: list[dict], dry_run: bool) -> dict:
    mappings = selected_mappings(review_rows)
    summary = {
        "selected_labels": len(mappings),
        "updated_regions": 0,
        "already_linked_regions": 0,
        "missing_kits": [],
        "labels_without_regions": [],
    }
    reason = "Applied exported PPTX label kit-review decision."

    for label, kit_id in mappings.items():
        kit = db.execute("SELECT id FROM kits WHERE id=?", (kit_id,)).fetchone()
        if not kit:
            summary["missing_kits"].append({"label": label, "kit_id": kit_id})
            continue

        regions = pptx_regions_for_label(db, label)
        if not regions:
            summary["labels_without_regions"].append(label)
            continue

        for region in regions:
            if region["entity_type"] == "kit" and region["entity_id"] == kit_id:
                summary["already_linked_regions"] += 1
                continue
            if not dry_run:
                snapshot = row_dict(region)
                db.execute(
                    """
                    INSERT INTO image_region_history (region_id, action, snapshot_json, reason)
                    VALUES (?, 'update', ?, ?)
                    """,
                    (region["id"], json.dumps(snapshot, ensure_ascii=False, sort_keys=True), reason),
                )
                db.execute(
                    """
                    UPDATE image_regions
                    SET entity_type='kit',
                        entity_id=?,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE id=?
                    """,
                    (kit_id, region["id"]),
                )
            summary["updated_regions"] += 1

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply exported PPTX label review decisions to image_regions.")
    parser.add_argument("review_json", type=Path, help="Path to PptxLabelKitReviewDecisions.json")
    parser.add_argument("--dry-run", action="store_true", help="Report what would change without writing")
    args = parser.parse_args()

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        rows = load_review(args.review_json)
        summary = apply_review(db, rows, args.dry_run)
        if summary["missing_kits"] or summary["labels_without_regions"]:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            return 1
        if args.dry_run:
            db.rollback()
        else:
            db.commit()
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
