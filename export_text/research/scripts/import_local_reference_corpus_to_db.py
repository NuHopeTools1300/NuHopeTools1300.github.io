from __future__ import annotations

import csv
import json
import re
import sqlite3
from pathlib import Path

from import_pptx_research_to_db import (
    DB_PATH,
    REPO_ROOT,
    SCHEMA_PATH,
    UPLOAD_DIR,
    clean,
    column_exists,
    ensure_column,
    ensure_schema,
    ensure_source,
    ensure_upload_copy,
    existing_image_by_sha,
    merge_notes,
    merge_tags,
)


SCRIPT_DIR = Path(__file__).resolve().parent
RESEARCH_DIR = SCRIPT_DIR.parent
CORPUS_DIR = RESEARCH_DIR / "local_reference_corpus"
SAFE_CSV = CORPUS_DIR / "corpus_safe_to_stage.csv"

PARENT_SOURCE_CODE = "LOCALREF-CORPUS-SAFE"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def relative_or_abs(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def slugify(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "-", (value or "").strip()).strip("-")
    return text.upper() or "UNKNOWN"


def image_code_for_digest(digest: str) -> str:
    return f"LOCREF-{digest[:8].upper()}"


def ensure_parent_source(db: sqlite3.Connection) -> int:
    return ensure_source(
        db,
        source_code=PARENT_SOURCE_CODE,
        title="Local reference corpus safe bucket",
        source_type="local_corpus",
        local_path=relative_or_abs(SAFE_CSV),
        notes="Imported from corpus_safe_to_stage.csv in export_text/research/local_reference_corpus.",
    )


def ensure_collection_source(
    db: sqlite3.Connection,
    *,
    parent_source_id: int,
    source_platform: str,
    source_collection: str,
    source_creator: str,
) -> int:
    platform = clean(source_platform) or "unknown"
    collection = clean(source_collection) or "unknown"
    creator = clean(source_creator)

    code = f"LOCALREF-{slugify(platform)}-{slugify(collection)}"
    title = f"Local reference corpus - {collection}"
    notes = merge_notes(
        None,
        [
            f"parent_source_code={PARENT_SOURCE_CODE}",
            f"source_platform={platform}",
            f"source_collection={collection}",
            f"source_creator={creator or ''}",
            "Imported from the safe-to-stage bucket of the local reference corpus.",
        ],
    )

    row = db.execute("SELECT id FROM sources WHERE source_code=?", (code,)).fetchone()
    if row:
        db.execute(
            """
            UPDATE sources
            SET title=?, source_type=?, author=?, local_path=?, parent_source_id=?, notes=?
            WHERE id=?
            """,
            (
                title,
                platform,
                creator,
                relative_or_abs(SAFE_CSV),
                parent_source_id,
                notes,
                row["id"],
            ),
        )
        return int(row["id"])

    cur = db.execute(
        """
        INSERT INTO sources
            (source_code, source_type, title, author, local_path, parent_source_id, notes)
        VALUES (?,?,?,?,?,?,?)
        """,
        (
            code,
            platform,
            title,
            creator,
            relative_or_abs(SAFE_CSV),
            parent_source_id,
            notes,
        ),
    )
    return int(cur.lastrowid)


def build_tags(row: dict[str, str]) -> list[str]:
    return [
        "local-reference-corpus",
        "safe-to-stage",
        clean(row.get("root_key")),
        clean(row.get("subject")),
        clean(row.get("subject_detail")),
        clean(row.get("source_platform")),
        clean(row.get("source_collection")),
        clean(row.get("content_kind")),
    ]


def build_note_lines(row: dict[str, str], source_code: str) -> list[str]:
    return [
        "import_batch=local_reference_corpus_safe",
        f"bucket={clean(row.get('bucket')) or 'safe_to_stage'}",
        f"bucket_reason={clean(row.get('bucket_reason')) or 'attributed_and_nonhistorical'}",
        f"source_code={source_code}",
        f"original_local_path={clean(row.get('canonical_abs_path')) or ''}",
        f"original_rel_path={clean(row.get('canonical_rel_path')) or ''}",
        f"root_key={clean(row.get('root_key')) or ''}",
        f"source_platform={clean(row.get('source_platform')) or ''}",
        f"source_collection={clean(row.get('source_collection')) or ''}",
        f"source_creator={clean(row.get('source_creator')) or ''}",
        f"source_confidence={clean(row.get('source_confidence')) or ''}",
        f"content_kind={clean(row.get('content_kind')) or ''}",
        f"duplicate_count={clean(row.get('duplicate_count')) or ''}",
    ]


def import_row(
    db: sqlite3.Connection,
    row: dict[str, str],
    source_id: int,
    source_code: str,
) -> tuple[str, int]:
    source_path = Path(row["canonical_abs_path"])
    digest = row["sha256"]
    upload_name, upload_storage_path = ensure_upload_copy(source_path, digest)
    title = clean(row.get("suggested_title")) or source_path.name
    caption = clean(row.get("subject"))
    width = int(row["width"]) if clean(row.get("width")) else None
    height = int(row["height"]) if clean(row.get("height")) else None
    tags = build_tags(row)
    note_lines = build_note_lines(row, source_code)
    display_source = clean(row.get("source_collection")) or clean(row.get("source_platform")) or "local reference corpus"

    existing = existing_image_by_sha(db, digest)
    if existing:
        db.execute(
            """
            UPDATE images
            SET title=COALESCE(NULLIF(title, ''), ?),
                image_code=COALESCE(NULLIF(image_code, ''), ?),
                caption=COALESCE(NULLIF(caption, ''), ?),
                filename=COALESCE(NULLIF(filename, ''), ?),
                url=COALESCE(NULLIF(url, ''), ?),
                storage_kind=COALESCE(NULLIF(storage_kind, ''), 'upload'),
                storage_path=COALESCE(NULLIF(storage_path, ''), ?),
                width=COALESCE(width, ?),
                height=COALESCE(height, ?),
                image_type=COALESCE(NULLIF(image_type, ''), 'reference'),
                source=COALESCE(NULLIF(source, ''), ?),
                source_id=COALESCE(source_id, ?),
                notes=?
            WHERE id=?
            """,
            (
                title,
                image_code_for_digest(digest),
                caption,
                upload_name,
                f"/uploads/{upload_name}",
                upload_storage_path,
                width,
                height,
                display_source,
                source_id,
                merge_notes(existing["notes"], note_lines),
                existing["id"],
            ),
        )
        image_id = int(existing["id"])
        merge_tags(db, image_id, tags)
        return "updated_existing", image_id

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
            image_code_for_digest(digest),
            caption,
            f"/uploads/{upload_name}",
            "upload",
            upload_storage_path,
            digest,
            width,
            height,
            "reference",
            display_source,
            source_id,
            merge_notes(None, note_lines),
        ),
    )
    image_id = int(cur.lastrowid)
    merge_tags(db, image_id, tags)
    return "inserted", image_id


def main():
    rows = read_csv(SAFE_CSV)
    if not rows:
        raise SystemExit("No rows found in corpus_safe_to_stage.csv")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        ensure_schema(db)

        parent_source_id = ensure_parent_source(db)
        source_ids: dict[tuple[str, str, str], tuple[int, str]] = {}
        inserted = 0
        updated = 0
        touched_source_ids = {parent_source_id}

        for row in rows:
            key = (
                clean(row.get("source_platform")) or "unknown",
                clean(row.get("source_collection")) or "unknown",
                clean(row.get("source_creator")) or "",
            )
            if key not in source_ids:
                source_id = ensure_collection_source(
                    db,
                    parent_source_id=parent_source_id,
                    source_platform=key[0],
                    source_collection=key[1],
                    source_creator=key[2],
                )
                source_code = f"LOCALREF-{slugify(key[0])}-{slugify(key[1])}"
                source_ids[key] = (source_id, source_code)
            source_id, source_code = source_ids[key]
            touched_source_ids.add(source_id)
            status, _ = import_row(db, row, source_id, source_code)
            if status == "inserted":
                inserted += 1
            else:
                updated += 1

        db.commit()

        summary = {
            "safe_rows": len(rows),
            "inserted": inserted,
            "updated_existing": updated,
            "sources_touched": len(touched_source_ids),
            "source_records_created_or_updated": len(source_ids) + 1,
            "image_count_total": db.execute("SELECT COUNT(*) FROM images").fetchone()[0],
            "source_count_total": db.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
            "tag_count_total": db.execute("SELECT COUNT(*) FROM image_tags").fetchone()[0],
        }
        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
