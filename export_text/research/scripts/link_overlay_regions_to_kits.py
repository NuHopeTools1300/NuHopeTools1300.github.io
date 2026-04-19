from __future__ import annotations

import csv
import json
import re
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "backend" / "data" / "ilm1300.db"
REPORT_PATH = ROOT / "export_text" / "research" / "phase1_region_kit_links.csv"


def normalize(value: str | None) -> str:
    text = (value or "").lower()
    text = text.replace("’", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text


def snapshot_row(row: sqlite3.Row) -> str:
    payload = {key: row[key] for key in row.keys()}
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    kit_index: dict[str, list[sqlite3.Row]] = {}
    for kit in conn.execute("SELECT id, brand, name FROM kits ORDER BY id").fetchall():
        key = normalize(f"{kit['brand']} {kit['name']}")
        kit_index.setdefault(key, []).append(kit)

    linked_rows: list[dict[str, object]] = []
    skipped_rows: list[dict[str, object]] = []

    regions = conn.execute(
        """
        SELECT r.*, i.title AS image_title
        FROM image_regions r
        JOIN images i ON i.id = r.image_id
        WHERE r.label IS NOT NULL AND TRIM(r.label) <> ''
        ORDER BY r.id
        """
    ).fetchall()

    updated = 0
    for region in regions:
        key = normalize(region["label"])
        matches = kit_index.get(key, [])
        if len(matches) != 1:
            skipped_rows.append(
                {
                    "region_id": region["id"],
                    "image_id": region["image_id"],
                    "image_title": region["image_title"],
                    "label": region["label"],
                    "status": "no_exact_match" if not matches else "ambiguous_exact_match",
                    "match_count": len(matches),
                    "kit_id": "",
                    "kit_brand": "",
                    "kit_name": "",
                }
            )
            continue

        kit = matches[0]
        already_linked = region["entity_type"] == "kit" and region["entity_id"] == kit["id"]
        if not already_linked:
            conn.execute(
                """
                UPDATE image_regions
                SET entity_type = 'kit',
                    entity_id = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (kit["id"], region["id"]),
            )
            conn.execute(
                """
                INSERT INTO image_region_history (region_id, action, snapshot_json, reason)
                VALUES (?, 'update', ?, ?)
                """,
                (
                    region["id"],
                    snapshot_row(region),
                    f"Phase 1 exact overlay-to-kit link: {kit['brand']} {kit['name']}",
                ),
            )
            updated += 1

        linked_rows.append(
            {
                "region_id": region["id"],
                "image_id": region["image_id"],
                "image_title": region["image_title"],
                "label": region["label"],
                "status": "linked" if not already_linked else "already_linked",
                "match_count": 1,
                "kit_id": kit["id"],
                "kit_brand": kit["brand"],
                "kit_name": kit["name"],
            }
        )

    conn.commit()

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "region_id",
            "image_id",
            "image_title",
            "label",
            "status",
            "match_count",
            "kit_id",
            "kit_brand",
            "kit_name",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in linked_rows + skipped_rows:
            writer.writerow(row)

    print(f"Regions scanned: {len(regions)}")
    print(f"Regions linked this run: {updated}")
    print(f"Exact-match rows recorded: {len(linked_rows)}")
    print(f"Skipped rows recorded: {len(skipped_rows)}")
    print(f"Report written to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
