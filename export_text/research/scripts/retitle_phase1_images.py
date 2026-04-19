from __future__ import annotations

import csv
import json
import re
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "backend" / "data" / "ilm1300.db"
REPORT_PATH = ROOT / "export_text" / "research" / "phase1_image_retitles.csv"


GENERIC_TITLES = {"n/a", "open"}


def is_generic_title(value: str | None) -> bool:
    if not value:
        return True
    text = value.strip().lower()
    return text in GENERIC_TITLES or bool(re.fullmatch(r"image\d+\.(jpg|jpeg|png|gif|webp)", text))


def parse_notes(text: str | None) -> dict[str, str]:
    data: dict[str, str] = {}
    for raw_line in (text or "").splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def normalize_candidate(value: str | None) -> str | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if text.lower() in {"none", "n/a", "open", "unknown"}:
        return None
    return text


def humanize_slide_key(value: str | None) -> str | None:
    text = normalize_candidate(value)
    if not text:
        return None
    text = text.replace("_", " ").replace("-", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def choose_title(conn: sqlite3.Connection, image_id: int, image_title: str | None, notes: str | None, image_code: str | None) -> tuple[str, str | None]:
    note_map = parse_notes(notes)
    for key in ("likely_model_or_scene",):
        candidate = normalize_candidate(note_map.get(key))
        if candidate:
            return candidate, None

    region_rows = conn.execute(
        """
        SELECT label, properties_json
        FROM image_regions
        WHERE image_id = ?
        ORDER BY id
        """,
        (image_id,),
    ).fetchall()

    region_props = []
    labels = []
    for row in region_rows:
        if row["label"]:
            labels.append(row["label"])
        if row["properties_json"]:
            try:
                region_props.append(json.loads(row["properties_json"]))
            except json.JSONDecodeError:
                pass

    for props in region_props:
        for key in ("base_scene", "base_subject"):
            candidate = normalize_candidate(props.get(key))
            if candidate:
                return candidate, None

    if labels:
        first_labels = []
        seen = set()
        for label in labels:
            if label in seen:
                continue
            seen.add(label)
            first_labels.append(label)
            if len(first_labels) == 3:
                break
        if first_labels:
            return f"Overlay reference: {' / '.join(first_labels)}", None

    for props in region_props:
        slide_key = humanize_slide_key(props.get("slide_key"))
        if slide_key:
            return f"{slide_key} overlay reference", None

    slide_key = humanize_slide_key(note_map.get("slide_key"))
    if slide_key:
        return f"{slide_key} reference image", None

    if image_title and image_title.strip().lower() == "n/a":
        return f"Malformed PPTX extract {image_code or image_id}", "file is malformed or not yet decodable"
    if image_title and image_title.strip().lower() == "open":
        return f"Unreviewed PPTX extract {image_code or image_id}", "not yet visually reviewed"

    return f"PPTX extract {image_code or image_id}", None


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    updates = []
    rows = conn.execute(
        """
        SELECT id, title, caption, notes, image_code
        FROM images
        ORDER BY id
        """
    ).fetchall()

    for row in rows:
        if not is_generic_title(row["title"]):
            continue
        new_title, fallback_caption = choose_title(conn, row["id"], row["title"], row["notes"], row["image_code"])
        new_caption = row["caption"] or fallback_caption
        if new_title == row["title"] and new_caption == row["caption"]:
            continue
        conn.execute(
            """
            UPDATE images
            SET title = ?,
                caption = ?
            WHERE id = ?
            """,
            (new_title, new_caption, row["id"]),
        )
        updates.append(
            {
                "image_id": row["id"],
                "old_title": row["title"],
                "new_title": new_title,
                "caption": new_caption or "",
            }
        )

    conn.commit()

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["image_id", "old_title", "new_title", "caption"])
        writer.writeheader()
        writer.writerows(updates)

    print(f"Images retitled: {len(updates)}")
    print(f"Report written to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
