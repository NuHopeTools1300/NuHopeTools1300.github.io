"""
Link ScifiKitbash thread 33 first-post map attachments to local map records.

This intentionally targets only the first post of:
  https://scifikitbash.com/showthread.php?tid=33

Dry run:
  python tools/link_scifikitbash_tid33_maps.py --dry-run

Apply:
  python tools/link_scifikitbash_tid33_maps.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import mimetypes
import re
import shutil
import sqlite3
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "data" / "ilm1300.db"
UPLOAD_DIR = ROOT / "backend" / "data" / "uploads"
REPORT_PATH = ROOT / "docs" / "generated" / "ScifiKitbashTid33MapImageMatches.csv"
DEFAULT_MIRROR = Path(r"D:\Manuel\MillenniumFalcon\Websites\scifikitbash_mirror")
THREAD_URL = "https://scifikitbash.com/showthread.php?tid=33"
THREAD_TITLE = "My 5 Foot Millennium Falcon Part Maps"
SOURCE_CODE = "SCIFIKITBASH-TID33"


@dataclass
class Attachment:
    filename: str
    href: str
    local_path: Path
    aid: str | None


def normalize_name(value: str) -> str:
    text = str(value or "").lower()
    text = re.sub(r"\.(jpe?g|png|gif|webp)$", "", text)
    text = re.sub(r"\baid[_-]?\d+\b", " ", text)
    text = re.sub(r"\bcopy\b", " ", text)
    text = text.replace("mandilbe", "mandible")
    text = text.replace("maintenence", "maintenance")
    text = text.replace("turett", "turret")
    text = text.replace("foarward", "forward")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_first_post(html_text: str) -> str:
    start = html_text.find('<div class="post" id="post_38"')
    if start == -1:
        raise RuntimeError("Could not find first post id post_38")
    next_post = html_text.find('<div class="post" id="post_', start + 1)
    if next_post == -1:
        return html_text[start:]
    return html_text[start:next_post]


def parse_attachments(mirror: Path) -> list[Attachment]:
    thread_file = mirror / "threads" / "showthread.php_tid_33.html"
    text = thread_file.read_text(encoding="utf-8", errors="replace")
    first_post = extract_first_post(text)
    attachments: list[Attachment] = []
    seen: set[str] = set()
    pattern = re.compile(
        r'<a\b[^>]*data-caption="(?P<caption>[^"]+)"[^>]*data-type="image"[^>]*href="(?P<href>[^"]+)"',
        re.IGNORECASE,
    )
    for match in pattern.finditer(first_post):
        caption = html.unescape(match.group("caption"))
        href = html.unescape(match.group("href"))
        filename_match = re.search(r"Filename:\s*</b>\s*(.*?)\s*-\s*<b>", caption, re.IGNORECASE)
        if not filename_match:
            filename_match = re.search(r"Filename:\s*(.*?)\s*-\s*Size:", caption, re.IGNORECASE)
        if not filename_match:
            continue
        filename = html.unescape(filename_match.group(1)).strip()
        if filename in seen:
            continue
        seen.add(filename)
        rel = href.replace("../", "")
        local_path = mirror / rel.replace("/", "\\")
        aid_match = re.search(r"_aid_(\d+)", href)
        attachments.append(Attachment(filename=filename, href=href, local_path=local_path, aid=aid_match.group(1) if aid_match else None))
    return attachments


def rows(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
    return list(conn.execute(sql, params).fetchall())


def get_source_id(conn: sqlite3.Connection, apply: bool) -> int | None:
    existing = conn.execute("SELECT id FROM sources WHERE source_code=?", (SOURCE_CODE,)).fetchone()
    if existing:
        return existing["id"]
    if not apply:
        return None
    cur = conn.execute(
        """
        INSERT INTO sources (source_code, source_type, title, author, publisher, source_date, url, local_path, notes)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            SOURCE_CODE,
            "forum_thread",
            THREAD_TITLE,
            None,
            "ScifiKitbash",
            "2022-10-25",
            THREAD_URL,
            str(DEFAULT_MIRROR / "threads" / "showthread.php_tid_33.html"),
            "First post contains the 5-foot Millennium Falcon part map image attachments.",
        ),
    )
    return cur.lastrowid


def choose_match(attachment: Attachment, maps: list[sqlite3.Row]) -> tuple[sqlite3.Row | None, str, float]:
    att_norm = normalize_name(attachment.filename)
    exact = [m for m in maps if normalize_name(m["name"]) == att_norm]
    if len(exact) == 1:
        return exact[0], "exact", 1.0
    # A few map records intentionally collapse paired first-post files.
    if att_norm in {"top back 05", "top back left 07"}:
        candidates = [m for m in maps if normalize_name(m["name"]) == "top back 05 07"]
        if candidates:
            return candidates[0], "collapsed-top-back", 0.92
    if att_norm == "ventral rear numbers":
        candidates = [m for m in maps if normalize_name(m["name"]) == "ventral rear numbers close"]
        if candidates:
            return candidates[0], "collapsed-ventral-rear", 0.9
    if att_norm == "ventral rear close":
        candidates = [m for m in maps if normalize_name(m["name"]) == "ventral rear numbers close"]
        if candidates:
            return candidates[0], "collapsed-ventral-rear", 0.9
    if att_norm == "radar front":
        candidates = [m for m in maps if normalize_name(m["name"]) == "complete radar"]
        if candidates:
            return candidates[0], "detail-of-complete-radar", 0.88
    if att_norm == "ventral rear":
        candidates = [m for m in maps if normalize_name(m["name"]) == "ventral rear numbers close"]
        if candidates:
            return candidates[0], "near-duplicate-ventral-rear", 0.86
    contains = [m for m in maps if att_norm and (att_norm in normalize_name(m["name"]) or normalize_name(m["name"]) in att_norm)]
    if len(contains) == 1:
        return contains[0], "contains", 0.82
    return None, "unmatched" if not contains else "ambiguous", 0.0


def file_ext(attachment: Attachment, raw: bytes) -> str:
    ext = Path(attachment.filename).suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        return ".jpg" if ext == ".jpeg" else ext
    guessed = mimetypes.guess_extension(mimetypes.guess_type(attachment.filename)[0] or "")
    return guessed or ".jpg"


def image_dimensions(path: Path) -> tuple[int | None, int | None]:
    try:
        from PIL import Image

        with Image.open(path) as img:
            return img.size
    except Exception:
        return None, None


def upsert_image(conn: sqlite3.Connection, attachment: Attachment, source_id: int | None, apply: bool) -> tuple[int | None, str | None]:
    if not attachment.local_path.exists():
        return None, "missing-local-file"
    raw = attachment.local_path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    existing = conn.execute("SELECT id FROM images WHERE sha256=?", (digest,)).fetchone()
    if existing:
        return existing["id"], "existing"
    if not apply:
        return None, "would-create"
    ext = file_ext(attachment, raw)
    upload_name = f"{digest[:16]}{ext}"
    dest = UPLOAD_DIR / upload_name
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        shutil.copyfile(attachment.local_path, dest)
    width, height = image_dimensions(dest)
    cur = conn.execute(
        """
        INSERT INTO images
            (filename, title, image_code, caption, url, storage_kind, storage_path, sha256,
             width, height, image_type, source, source_id, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            upload_name,
            Path(attachment.filename).stem,
            f"SCIFIKITBASH-TID33-AID-{attachment.aid}" if attachment.aid else None,
            attachment.filename,
            f"/uploads/{upload_name}",
            "upload",
            str(dest),
            digest,
            width,
            height,
            "map",
            "ScifiKitbash thread 33 first post",
            source_id,
            f"Imported from {THREAD_URL} first post attachment {attachment.href}",
        ),
    )
    return cur.lastrowid, "created"


def ensure_image_family(conn: sqlite3.Connection, map_row: sqlite3.Row, primary_image_id: int, apply: bool) -> int | None:
    existing = conn.execute(
        "SELECT family_id FROM image_family_members WHERE image_id=?",
        (primary_image_id,),
    ).fetchone()
    if existing:
        return existing["family_id"]
    if not apply:
        return None
    cur = conn.execute(
        """
        INSERT INTO image_families (title, family_type, primary_image_id, notes)
        VALUES (?,?,?,?)
        """,
        (
            f"Map image family - {map_row['name']}",
            "detail_set",
            primary_image_id,
            f"Created while linking ScifiKitbash thread 33 first-post map attachments to map {map_row['id']}.",
        ),
    )
    family_id = cur.lastrowid
    conn.execute(
        """
        INSERT INTO image_family_members
            (family_id, image_id, relation_type, sort_order, is_primary, is_hidden_in_library, coverage_role, notes)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (family_id, primary_image_id, "primary", 0, 1, 0, "full_frame", "Primary map image."),
    )
    return family_id


def add_family_member(
    conn: sqlite3.Connection,
    map_row: sqlite3.Row,
    image_id: int,
    match_kind: str,
    attachment: Attachment,
    apply: bool,
) -> str:
    primary_image_id = map_row["image_id"]
    if not primary_image_id or primary_image_id == image_id:
        return "not-needed"
    relation_type = "variant"
    coverage_role = "comparison_variant"
    hidden = 0
    if match_kind == "detail-of-complete-radar":
        relation_type = "detail"
        coverage_role = "detail_crop"
    elif match_kind == "near-duplicate-ventral-rear":
        relation_type = "near_duplicate"
        coverage_role = "comparison_variant"
        hidden = 1
    family_id = ensure_image_family(conn, map_row, primary_image_id, apply)
    if not family_id:
        return "would-add-family-member"
    if not apply:
        return "would-add-family-member"
    existing = conn.execute(
        "SELECT id FROM image_family_members WHERE image_id=?",
        (image_id,),
    ).fetchone()
    if existing:
        return "already-in-family"
    conn.execute(
        """
        INSERT INTO image_family_members
            (family_id, image_id, relation_type, sort_order, is_primary, is_hidden_in_library, coverage_role, notes)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (
            family_id,
            image_id,
            relation_type,
            10,
            0,
            hidden,
            coverage_role,
            f"{attachment.filename} from ScifiKitbash thread 33; {match_kind}.",
        ),
    )
    return f"family-member-{relation_type}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mirror", type=Path, default=DEFAULT_MIRROR)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    apply = not args.dry_run

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    attachments = parse_attachments(args.mirror)
    maps = rows(conn, "SELECT * FROM maps WHERE model_id=1 ORDER BY name")
    source_id = get_source_id(conn, apply)

    report_rows = []
    primary_links = 0
    map_image_links = 0
    created_images = 0
    existing_images = 0
    skipped_existing_map_image = 0

    if apply:
        backup = DB_PATH.with_name(f"{DB_PATH.name}.bak.scifikitbash_tid33_maps")
        if not backup.exists():
            shutil.copyfile(DB_PATH, backup)

    for attachment in attachments:
        matched_map, match_kind, confidence = choose_match(attachment, maps)
        image_id = None
        image_status = None
        update_status = "no-match"
        family_status = ""
        if matched_map:
            image_id, image_status = upsert_image(conn, attachment, source_id, apply)
            if image_status == "created":
                created_images += 1
            elif image_status == "existing":
                existing_images += 1
            if image_id and apply:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO image_links (image_id, entity_type, entity_id, annotation)
                    VALUES (?,?,?,?)
                    """,
                    (
                        image_id,
                        "map",
                        matched_map["id"],
                        f"ScifiKitbash thread 33 first-post attachment: {attachment.filename}",
                    ),
                )
                map_image_links += 1
                family_status = add_family_member(conn, matched_map, image_id, match_kind, attachment, apply)
            if matched_map["image_id"] and matched_map["image_id"] != image_id:
                update_status = "map-image-link-added-primary-unchanged" if image_id and apply else "map-already-has-different-image"
                skipped_existing_map_image += 1
            elif image_id and apply:
                conn.execute("UPDATE maps SET image_id=? WHERE id=?", (image_id, matched_map["id"]))
                update_status = "primary-linked"
                primary_links += 1
            elif image_id:
                update_status = "would-link-existing-image"
            elif image_status == "would-create":
                update_status = "would-create-image-and-link"
            else:
                update_status = image_status or "not-linked"
        report_rows.append(
            {
                "attachment_filename": attachment.filename,
                "attachment_href": attachment.href,
                "local_path": str(attachment.local_path),
                "exists": attachment.local_path.exists(),
                "aid": attachment.aid or "",
                "normalized_attachment": normalize_name(attachment.filename),
                "match_kind": match_kind,
                "confidence": confidence,
                "map_id": matched_map["id"] if matched_map else "",
                "map_name": matched_map["name"] if matched_map else "",
                "previous_map_image_id": matched_map["image_id"] if matched_map else "",
                "image_id": image_id or "",
                "image_status": image_status or "",
                "update_status": update_status,
                "family_status": family_status,
            }
        )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPORT_PATH.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(report_rows[0].keys()))
        writer.writeheader()
        writer.writerows(report_rows)

    if apply:
        conn.commit()

    matched = sum(1 for row in report_rows if row["map_id"])
    missing_files = sum(1 for row in report_rows if not row["exists"])
    print(f"attachments: {len(attachments)}")
    print(f"matched maps: {matched}")
    print(f"missing local files: {missing_files}")
    print(f"created images: {created_images}")
    print(f"existing images: {existing_images}")
    print(f"primary map images linked: {primary_links}")
    print(f"map image_links inserted/confirmed: {map_image_links}")
    print(f"skipped maps with existing different image: {skipped_existing_map_image}")
    print(f"report: {REPORT_PATH}")
    if args.dry_run:
        print("dry run only; no database changes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
