from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
RESEARCH_DIR = SCRIPT_DIR.parent
REPO_ROOT = RESEARCH_DIR.parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
DB_PATH = BACKEND_DIR / "data" / "ilm1300.db"
SCHEMA_PATH = BACKEND_DIR / "schema.sql"
UPLOAD_DIR = BACKEND_DIR / "data" / "uploads"

TIMELINE_PPTX = RESEARCH_DIR / "ILM75-77_timeline_.pptx"
KIT_PPTX = RESEARCH_DIR / "Kit_images.pptx"
TIMELINE_MANIFEST = RESEARCH_DIR / "anh_pptx_image_manifest.csv"
OVERLAY_CSV = RESEARCH_DIR / "kit_images_overlay_labels.csv"
KIT_CROSSWALK = RESEARCH_DIR / "kit_images_media_crosswalk.csv"
TIMELINE_MEDIA_DIR = RESEARCH_DIR / "_pptx_extract" / "ppt" / "media"
KIT_MEDIA_DIR = RESEARCH_DIR / "_kit_images_extract" / "ppt" / "media"

TIMELINE_SOURCE_CODE = "PPTX-ILM75-77"
KIT_SOURCE_CODE = "PPTX-KIT-IMAGES"

STATUS_COLOR = {
    "identified_in_this_image": "#34d399",
    "identified_elsewhere": "#fbbf24",
    "other_or_unstyled": "#94a3b8",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def clean(value: object) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def maybe_float(value: object) -> Optional[float]:
    text = clean(value)
    if text is None or text.lower() == "n/a":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_str(path: Path) -> str:
    return path.resolve().relative_to(REPO_ROOT).as_posix()


def column_exists(db: sqlite3.Connection, table_name: str, column_name: str) -> bool:
    rows = db.execute(f"PRAGMA table_info({table_name})").fetchall()
    return any(row[1] == column_name for row in rows)


def ensure_column(db: sqlite3.Connection, table_name: str, column_name: str, ddl: str) -> None:
    if not column_exists(db, table_name, column_name):
        db.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")


def ensure_schema(db: sqlite3.Connection) -> None:
    db.execute("PRAGMA foreign_keys = ON")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with SCHEMA_PATH.open(encoding="utf-8") as handle:
        db.executescript(handle.read())
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS sources (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            source_code      TEXT UNIQUE,
            source_type      TEXT NOT NULL,
            title            TEXT NOT NULL,
            author           TEXT,
            publisher        TEXT,
            source_date      DATE,
            url              TEXT,
            local_path       TEXT,
            parent_source_id INTEGER REFERENCES sources(id),
            notes            TEXT,
            attributed_to    INTEGER REFERENCES contributors(id),
            created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS source_extracts (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            source_id      INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            extract_type   TEXT NOT NULL,
            locator        TEXT,
            author_handle  TEXT,
            extract_date   DATE,
            content        TEXT NOT NULL,
            notes          TEXT,
            attributed_to  INTEGER REFERENCES contributors(id),
            created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS image_regions (
            id                INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id          INTEGER NOT NULL REFERENCES images(id) ON DELETE CASCADE,
            region_type       TEXT NOT NULL DEFAULT 'point',
            x_norm            REAL,
            y_norm            REAL,
            width_norm        REAL,
            height_norm       REAL,
            pixel_x           REAL,
            pixel_y           REAL,
            pixel_width       REAL,
            pixel_height      REAL,
            points_json       TEXT,
            rotation_deg      REAL,
            label             TEXT,
            notes             TEXT,
            object_name       TEXT,
            object_class      TEXT,
            color             TEXT,
            properties_json   TEXT,
            entity_type       TEXT,
            entity_id         INTEGER,
            source_extract_id INTEGER REFERENCES source_extracts(id),
            attributed_to     INTEGER REFERENCES contributors(id),
            created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    ensure_column(db, "images", "title", "TEXT")
    ensure_column(db, "images", "image_code", "TEXT")
    ensure_column(db, "images", "caption", "TEXT")
    ensure_column(db, "images", "storage_kind", "TEXT")
    ensure_column(db, "images", "storage_path", "TEXT")
    ensure_column(db, "images", "sha256", "TEXT")
    ensure_column(db, "images", "width", "INTEGER")
    ensure_column(db, "images", "height", "INTEGER")
    ensure_column(db, "images", "source_id", "INTEGER REFERENCES sources(id)")
    ensure_column(db, "image_regions", "pixel_x", "REAL")
    ensure_column(db, "image_regions", "pixel_y", "REAL")
    ensure_column(db, "image_regions", "pixel_width", "REAL")
    ensure_column(db, "image_regions", "pixel_height", "REAL")
    ensure_column(db, "image_regions", "object_name", "TEXT")
    ensure_column(db, "image_regions", "object_class", "TEXT")
    ensure_column(db, "image_regions", "color", "TEXT")
    ensure_column(db, "image_regions", "properties_json", "TEXT")
    ensure_column(db, "image_regions", "entity_type", "TEXT")
    ensure_column(db, "image_regions", "entity_id", "INTEGER")
    ensure_column(db, "image_regions", "source_extract_id", "INTEGER REFERENCES source_extracts(id)")
    ensure_column(db, "image_regions", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    db.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_sources_type        ON sources(source_type);
        CREATE INDEX IF NOT EXISTS idx_sources_date        ON sources(source_date);
        CREATE INDEX IF NOT EXISTS idx_source_extracts_src ON source_extracts(source_id);
        CREATE INDEX IF NOT EXISTS idx_images_code         ON images(image_code);
        CREATE INDEX IF NOT EXISTS idx_images_title        ON images(title);
        CREATE INDEX IF NOT EXISTS idx_images_source_id    ON images(source_id);
        CREATE INDEX IF NOT EXISTS idx_image_regions_image   ON image_regions(image_id);
        CREATE INDEX IF NOT EXISTS idx_image_regions_entity  ON image_regions(entity_type, entity_id);
        CREATE INDEX IF NOT EXISTS idx_image_regions_extract ON image_regions(source_extract_id);
        """
    )
    db.commit()


def ensure_source(
    db: sqlite3.Connection,
    *,
    source_code: str,
    title: str,
    source_type: str,
    local_path: str,
    notes: str,
) -> int:
    row = db.execute("SELECT id FROM sources WHERE source_code=?", (source_code,)).fetchone()
    if row:
        db.execute(
            """
            UPDATE sources
            SET title=?, source_type=?, local_path=?, notes=?
            WHERE id=?
            """,
            (title, source_type, local_path, notes, row["id"]),
        )
        return int(row["id"])

    cur = db.execute(
        """
        INSERT INTO sources (source_code, source_type, title, local_path, notes)
        VALUES (?,?,?,?,?)
        """,
        (source_code, source_type, title, local_path, notes),
    )
    return int(cur.lastrowid)


def ensure_upload_copy(source_path: Path, digest: str) -> Tuple[str, str]:
    ext = source_path.suffix.lower() or ".bin"
    upload_name = f"{digest[:16]}{ext}"
    upload_path = UPLOAD_DIR / upload_name
    if not upload_path.exists():
        shutil.copyfile(source_path, upload_path)
    return upload_name, str(upload_path)


def merge_notes(existing_notes: Optional[str], extra_lines: Iterable[str]) -> str:
    lines = []
    seen = set()
    if existing_notes:
        for line in str(existing_notes).splitlines():
            line = line.strip()
            if line and line not in seen:
                lines.append(line)
                seen.add(line)
    for raw in extra_lines:
        line = clean(raw)
        if line and line not in seen:
            lines.append(line)
            seen.add(line)
    return "\n".join(lines)


def merge_tags(db: sqlite3.Connection, image_id: int, tags: Iterable[str]) -> None:
    for raw in tags:
        tag = clean(raw)
        if tag:
            db.execute("INSERT OR IGNORE INTO image_tags (image_id, tag) VALUES (?,?)", (image_id, tag.lower().replace(" ", "-")))


def existing_image_by_sha(db: sqlite3.Connection, sha256: str) -> Optional[sqlite3.Row]:
    return db.execute("SELECT * FROM images WHERE sha256=? ORDER BY id LIMIT 1", (sha256,)).fetchone()


def existing_images_by_original_path(db: sqlite3.Connection, rel_path: str) -> list[sqlite3.Row]:
    return db.execute(
        "SELECT * FROM images WHERE notes LIKE ? ORDER BY id",
        (f"%original_media_path={rel_path}%",),
    ).fetchall()


def choose_title(metadata: dict[str, str], fallback: str) -> str:
    return (
        clean(metadata.get("likely_model_or_scene"))
        or clean(metadata.get("visible_subject"))
        or fallback
    )


def image_code_for_digest(digest: str) -> str:
    return f"PPTXIMG-{digest[:8].upper()}"


def enrich_existing_image(
    db: sqlite3.Connection,
    *,
    image_id: int,
    primary_source_id: int,
    title: Optional[str],
    caption: Optional[str],
    note_lines: Iterable[str],
    tags: Iterable[str],
) -> None:
    row = db.execute("SELECT * FROM images WHERE id=?", (image_id,)).fetchone()
    if not row:
        return
    db.execute(
        """
        UPDATE images
        SET title=COALESCE(title, ?),
            caption=COALESCE(caption, ?),
            source=COALESCE(source, ?),
            source_id=COALESCE(source_id, ?),
            notes=?
        WHERE id=?
        """,
        (
            title,
            caption,
            "pptx extract",
            primary_source_id,
            merge_notes(row["notes"], note_lines),
            image_id,
        ),
    )
    merge_tags(db, image_id, tags)


def delete_image_if_orphaned(db: sqlite3.Connection, image_id: int) -> None:
    region_count = db.execute("SELECT COUNT(*) FROM image_regions WHERE image_id=?", (image_id,)).fetchone()[0]
    link_count = db.execute("SELECT COUNT(*) FROM image_links WHERE image_id=?", (image_id,)).fetchone()[0]
    if region_count or link_count:
        return
    db.execute("DELETE FROM images WHERE id=?", (image_id,))


def import_image_record(
    db: sqlite3.Connection,
    *,
    source_path: Path,
    primary_source_id: int,
    metadata: dict[str, str],
    tags: Iterable[str],
    note_lines: Iterable[str],
) -> int:
    digest = sha256_file(source_path)
    upload_name, upload_storage_path = ensure_upload_copy(source_path, digest)
    title = choose_title(metadata, source_path.name)
    caption = clean(metadata.get("visible_subject"))
    width = None
    height = None
    image_code = image_code_for_digest(digest)
    row = existing_image_by_sha(db, digest)

    merged_note_lines = list(note_lines)
    merged_note_lines.append(f"original_media_path={relative_str(source_path)}")

    if row:
        db.execute(
            """
            UPDATE images
            SET title=COALESCE(title, ?),
                image_code=COALESCE(image_code, ?),
                caption=COALESCE(caption, ?),
                filename=COALESCE(filename, ?),
                url=COALESCE(url, ?),
                storage_kind=COALESCE(storage_kind, 'upload'),
                storage_path=COALESCE(storage_path, ?),
                width=COALESCE(width, ?),
                height=COALESCE(height, ?),
                source=COALESCE(source, ?),
                source_id=COALESCE(source_id, ?),
                notes=?
            WHERE id=?
            """,
            (
                title,
                image_code,
                caption,
                upload_name,
                f"/uploads/{upload_name}",
                upload_storage_path,
                width,
                height,
                "pptx extract",
                primary_source_id,
                merge_notes(row["notes"], merged_note_lines),
                row["id"],
            ),
        )
        image_id = int(row["id"])
    else:
        cur = db.execute(
            """
            INSERT INTO images
                (filename, title, image_code, caption, url, storage_kind, storage_path,
                 sha256, width, height, image_type, source, source_id, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                upload_name,
                title,
                image_code,
                caption,
                f"/uploads/{upload_name}",
                "upload",
                upload_storage_path,
                digest,
                width,
                height,
                "reference",
                "pptx extract",
                primary_source_id,
                merge_notes(None, merged_note_lines),
            ),
        )
        image_id = int(cur.lastrowid)

    merge_tags(db, image_id, tags)
    return image_id


def region_signature(
    *,
    image_id: int,
    label_text: str,
    label_status: str,
    x_norm: Optional[float],
    y_norm: Optional[float],
) -> tuple[object, ...]:
    return (
        image_id,
        clean(label_text) or "",
        clean(label_status) or "",
        round(x_norm or 0.0, 6),
        round(y_norm or 0.0, 6),
    )


def load_existing_region_signatures(db: sqlite3.Connection) -> set[tuple[object, ...]]:
    signatures: set[tuple[object, ...]] = set()
    rows = db.execute(
        "SELECT image_id, label, object_name, x_norm, y_norm, properties_json FROM image_regions"
    ).fetchall()
    for row in rows:
        props = {}
        if row["properties_json"]:
            try:
                props = json.loads(row["properties_json"])
            except json.JSONDecodeError:
                props = {}
        signatures.add(
            region_signature(
                image_id=int(row["image_id"]),
                label_text=clean(row["object_name"]) or clean(row["label"]) or "",
                label_status=clean(props.get("label_status")) or "",
                x_norm=row["x_norm"],
                y_norm=row["y_norm"],
            )
        )
    return signatures


def clear_imported_overlay_regions(db: sqlite3.Connection) -> int:
    count = db.execute(
        """
        SELECT COUNT(*) FROM image_regions
        WHERE properties_json LIKE '%"import_source": "Kit_images.pptx"%'
        """
    ).fetchone()[0]
    if count:
        db.execute(
            """
            DELETE FROM image_regions
            WHERE properties_json LIKE '%"import_source": "Kit_images.pptx"%'
            """
        )
    return int(count)


def main() -> None:
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    ensure_schema(db)

    timeline_source_id = ensure_source(
        db,
        source_code=TIMELINE_SOURCE_CODE,
        title="ILM75-77 timeline deck extract",
        source_type="slide_deck",
        local_path=relative_str(TIMELINE_PPTX),
        notes="Imported extracted media from the ILM75-77 timeline PPTX.",
    )
    kit_source_id = ensure_source(
        db,
        source_code=KIT_SOURCE_CODE,
        title="Kit images deck extract",
        source_type="slide_deck",
        local_path=relative_str(KIT_PPTX),
        notes="Imported extracted media and overlay labels from the Kit_images PPTX.",
    )

    timeline_rows = read_csv(TIMELINE_MANIFEST)
    overlay_rows = read_csv(OVERLAY_CSV)
    crosswalk_rows = read_csv(KIT_CROSSWALK)

    timeline_manifest_by_file = {row["file"]: row for row in timeline_rows if row.get("file")}
    kit_crosswalk_by_media = {row["kit_media"]: row for row in crosswalk_rows if row.get("kit_media")}

    image_ids_by_path: Dict[str, int] = {}
    image_ids_by_timeline_media: Dict[str, int] = {}
    image_ids_by_kit_media: Dict[str, int] = {}

    timeline_imported = 0
    kit_imported = 0
    image_seen_ids: set[int] = set()

    for source_path in sorted(TIMELINE_MEDIA_DIR.iterdir()):
        if not source_path.is_file():
            continue
        file_name = source_path.name
        row = timeline_manifest_by_file.get(file_name, {})
        if "malformed" in (row.get("notes") or "").lower():
            continue
        tags = [
            "pptx-extract",
            "timeline-deck",
            row.get("likely_program"),
            row.get("likely_model_or_scene"),
            row.get("confidence"),
        ]
        notes = [
            f"nearest_slide_anchor={row.get('nearest_slide_anchor')}",
            f"likely_program={row.get('likely_program')}",
            f"likely_model_or_scene={row.get('likely_model_or_scene')}",
            f"likely_date_window={row.get('likely_date_window')}",
            f"confidence={row.get('confidence')}",
            row.get("notes"),
        ]
        image_id = import_image_record(
            db,
            source_path=source_path,
            primary_source_id=timeline_source_id,
            metadata=row,
            tags=tags,
            note_lines=notes,
        )
        image_ids_by_path[relative_str(source_path)] = image_id
        image_ids_by_timeline_media[file_name] = image_id
        if image_id not in image_seen_ids:
            image_seen_ids.add(image_id)
            timeline_imported += 1

    for row in crosswalk_rows:
        kit_media = clean(row.get("kit_media"))
        if not kit_media:
            continue
        source_path = KIT_MEDIA_DIR / kit_media
        if not source_path.exists():
            continue
        timeline_media = clean(row.get("timeline_media"))
        linked_timeline_id = image_ids_by_timeline_media.get(timeline_media or "")
        source_rel = relative_str(source_path)
        existing_for_path = existing_images_by_original_path(db, source_rel)
        tags = [
            "pptx-extract",
            "kit-deck",
            clean(row.get("timeline_scene")),
            clean(row.get("timeline_subject")),
        ]
        notes = [
            f"crosswalk_timeline_media={timeline_media or 'none'}",
            f"base_slide_count={row.get('base_slide_count')}",
            f"label_total={row.get('label_total')}",
            clean(row.get("timeline_subject")),
            clean(row.get("timeline_scene")),
        ]
        metadata = {"likely_model_or_scene": row.get("timeline_scene"), "visible_subject": row.get("timeline_subject")}
        if linked_timeline_id:
            enrich_existing_image(
                db,
                image_id=linked_timeline_id,
                primary_source_id=timeline_source_id,
                title=choose_title(metadata, source_path.name),
                caption=clean(metadata.get("visible_subject")),
                note_lines=[*notes, f"original_media_path={source_rel}"],
                tags=tags,
            )
            for dup in existing_for_path:
                if int(dup["id"]) == linked_timeline_id:
                    continue
                duplicate_tags = [
                    tag_row["tag"]
                    for tag_row in db.execute("SELECT tag FROM image_tags WHERE image_id=?", (dup["id"],)).fetchall()
                ]
                enrich_existing_image(
                    db,
                    image_id=linked_timeline_id,
                    primary_source_id=timeline_source_id,
                    title=clean(dup["title"]),
                    caption=clean(dup["caption"]),
                    note_lines=[clean(dup["notes"])],
                    tags=duplicate_tags,
                )
                delete_image_if_orphaned(db, int(dup["id"]))
            image_id = linked_timeline_id
        else:
            image_id = import_image_record(
                db,
                source_path=source_path,
                primary_source_id=kit_source_id,
                metadata=metadata,
                tags=tags,
                note_lines=notes,
            )
        image_ids_by_path[relative_str(source_path)] = image_id
        image_ids_by_kit_media[kit_media] = image_id
        if linked_timeline_id and linked_timeline_id != image_id:
            image_ids_by_timeline_media[timeline_media or ""] = linked_timeline_id
        if image_id not in image_seen_ids:
            image_seen_ids.add(image_id)
            kit_imported += 1

    cleared_regions = clear_imported_overlay_regions(db)
    existing_region_keys = load_existing_region_signatures(db)
    regions_added = 0
    regions_skipped = 0

    for row in overlay_rows:
        timeline_media = clean(row.get("assigned_timeline_media")) or clean(row.get("base_timeline_media"))
        kit_media = clean(row.get("assigned_media")) or clean(row.get("base_media"))
        image_id = None
        use_projected = False

        if timeline_media and timeline_media in image_ids_by_timeline_media:
            image_id = image_ids_by_timeline_media[timeline_media]
            use_projected = True
        elif kit_media and kit_media in image_ids_by_kit_media:
            image_id = image_ids_by_kit_media[kit_media]
            use_projected = False

        if image_id is None:
            regions_skipped += 1
            continue

        x_norm = maybe_float(row.get("projected_x_in_original")) if use_projected else None
        y_norm = maybe_float(row.get("projected_y_in_original")) if use_projected else None
        if x_norm is None:
            x_norm = maybe_float(row.get("x_norm_in_assigned"))
        if y_norm is None:
            y_norm = maybe_float(row.get("y_norm_in_assigned"))
        if x_norm is None or y_norm is None:
            regions_skipped += 1
            continue

        sig = region_signature(
            image_id=image_id,
            label_text=row.get("label_text", ""),
            label_status=row.get("label_status", ""),
            x_norm=x_norm,
            y_norm=y_norm,
        )
        if sig in existing_region_keys:
            regions_skipped += 1
            continue

        props = {
            "import_source": "Kit_images.pptx",
            "slide": clean(row.get("slide")),
            "slide_key": clean(row.get("slide_key")),
            "slide_title": clean(row.get("slide_title")),
            "label_status": clean(row.get("label_status")),
            "line_color": clean(row.get("line_color")),
            "mapping_quality": clean(row.get("mapping_quality")),
            "assigned_media": clean(row.get("assigned_media")),
            "assigned_timeline_media": clean(row.get("assigned_timeline_media")),
            "base_media": clean(row.get("base_media")),
            "base_timeline_media": clean(row.get("base_timeline_media")),
            "base_subject": clean(row.get("base_subject")),
            "base_scene": clean(row.get("base_scene")),
            "slide_same_media_reuse": clean(row.get("slide_same_media_reuse")),
        }
        notes = merge_notes(
            None,
            [
                f"slide={row.get('slide')}",
                f"slide_key={row.get('slide_key')}",
                f"label_status={row.get('label_status')}",
                f"mapping_quality={row.get('mapping_quality')}",
            ],
        )
        db.execute(
            """
            INSERT INTO image_regions
                (image_id, region_type, x_norm, y_norm, label, notes,
                 object_name, object_class, color, properties_json)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                image_id,
                "point",
                x_norm,
                y_norm,
                clean(row.get("label_text")),
                notes,
                clean(row.get("label_text")),
                "Kit",
                STATUS_COLOR.get(clean(row.get("label_status")) or "", STATUS_COLOR["other_or_unstyled"]),
                json.dumps(props, ensure_ascii=False, sort_keys=True),
            ),
        )
        existing_region_keys.add(sig)
        regions_added += 1

    db.commit()
    total_images = db.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    total_regions = db.execute("SELECT COUNT(*) FROM image_regions").fetchone()[0]
    print(f"Timeline unique images imported/merged: {timeline_imported}")
    print(f"Kit-deck unique images imported/merged: {kit_imported}")
    print(f"Overlay regions refreshed (deleted before reimport): {cleared_regions}")
    print(f"Regions added: {regions_added}")
    print(f"Regions skipped as duplicates/unmappable: {regions_skipped}")
    print(f"Database totals -> images: {total_images}, image_regions: {total_regions}")


if __name__ == "__main__":
    main()
