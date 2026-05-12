#!/usr/bin/env python
"""Dry-run matcher for manually collected kit box/side images.

The script groups files from the external Kit_box_images folder, infers a kit
candidate from each filename prefix, and writes a review CSV. It does not import
images or mutate the database unless a future explicit import mode is added.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import shutil
import sqlite3
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "data" / "ilm1300.db"
DEFAULT_IMAGE_ROOT = Path(
    r"G:\.shortcut-targets-by-id\1wUGCO3uhQSoFWdir3gPoj7y93BV_zUjW"
    r"\Millennium Falcon 5'\SW-ANH-donors\SW-ANH-donors_public\Kit_box_images"
)
DEFAULT_REPORT = ROOT / "docs" / "generated" / "KitBoxImageMatchDryRun.csv"
UPLOAD_ROOT = ROOT / "backend" / "data" / "uploads"
KIT_BOX_UPLOAD_DIR = UPLOAD_ROOT / "kit_box_images"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIEW_ALIASES = {
    "front": "front",
    "frot": "front",
    "back": "back",
    "backjpg": "back",
    "back (1)": "back",
    "left": "left",
    "right": "right",
    "top": "top",
    "topo": "top",
    "bottom": "bottom",
}
NOISE_SUFFIXES = {"placeholder", "paceholder"}
TOKEN_SYNONYMS = {
    "af": "airfix",
    "amt": "amt",
    "satv": "apollo saturn v",
    "b727": "boeing 727",
    "dc": "dc",
    "tranatl": "transatlantic",
    "clipper": "clipper",
    "msutang": "mustang",
    "p51d": "p 51d mustang",
    "p": "p",
    "51d": "51d mustang",
    "messerschmitt": "messerschmitt bf109e",
    "hawkerharrier": "hawker harrier",
    "hawkerhurricane": "hawker hurricane",
    "grafspee": "graf spee",
    "arkroyal": "ark royal",
    "devonshire": "devonshire",
    "mauretania": "mauretania",
    "belfast": "belfast",
    "bismarck": "bismarck tirpitz",
    "tirpitz": "tirpitz bismarck",
    "nelson": "nelson",
    "hood": "hood",
}
CONFIRMED_GROUP_KIT_IDS = {
    # User-confirmed from ANH donor sheet/source review.
    "AF144-Trident": 171,
}


@dataclass
class Kit:
    id: int
    brand: str
    scale: str
    name: str
    serial_number: str


@dataclass
class Group:
    key: str
    files: list[Path]
    views: list[str]
    notes: list[str]


def ascii_fold(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value or "")
    return folded.encode("ascii", "ignore").decode("ascii")


def normalize_text(value: str) -> str:
    value = ascii_fold(value).lower()
    value = value.replace("&", " and ")
    value = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
    value = re.sub(r"\bb\s*727\b", "boeing 727", value)
    value = re.sub(r"\bsat\s*v\b", "apollo saturn v", value)
    value = re.sub(r"\bp\s*51\s*d\b", "p 51d mustang", value)
    value = re.sub(r"\bdc\s*9\s*30\b", "dc 9 30", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    words: list[str] = []
    for token in value.split():
        replacement = TOKEN_SYNONYMS.get(token)
        if replacement:
            words.extend(replacement.split())
        else:
            words.append(token)
    return " ".join(words)


def tokens(value: str) -> set[str]:
    return {word for word in normalize_text(value).split() if len(word) > 1 or word.isdigit()}


def slug(value: str, max_length: int = 96) -> str:
    value = ascii_fold(value).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    value = re.sub(r"-+", "-", value)
    return (value or "item")[:max_length].strip("-") or "item"


def split_camelish(value: str) -> str:
    value = re.sub(r"([a-z])([A-Z])", r"\1 \2", value)
    value = re.sub(r"([A-Za-z])(\d)", r"\1 \2", value)
    value = re.sub(r"(\d)([A-Za-z])", r"\1 \2", value)
    return value


def parse_file_name(path: Path) -> tuple[str, str, list[str]]:
    stem = path.stem
    parts = stem.split("_")
    notes: list[str] = []
    while parts and parts[-1].lower() in NOISE_SUFFIXES:
        notes.append(parts.pop())
    view = ""
    if parts:
        raw_view = parts[-1].lower()
        view = VIEW_ALIASES.get(raw_view, "")
        if view:
            if raw_view != view:
                notes.append(f"view typo: {raw_view}->{view}")
            parts.pop()
    if not parts:
        return stem, view or "unknown", notes
    return "_".join(parts), view or "unknown", notes


def group_files(root: Path) -> list[Group]:
    grouped: dict[str, list[tuple[Path, str, list[str]]]] = defaultdict(list)
    for path in sorted(root.iterdir()):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        key, view, notes = parse_file_name(path)
        grouped[key].append((path, view, notes))
    groups = []
    for key, values in grouped.items():
        files = [item[0] for item in values]
        views = sorted({item[1] for item in values})
        notes = sorted({note for item in values for note in item[2]})
        groups.append(Group(key=key, files=files, views=views, notes=notes))
    return sorted(groups, key=lambda group: group.key.lower())


def parse_group_key(key: str) -> tuple[str, str, str, list[str]]:
    notes: list[str] = []
    brand = ""
    scale = ""
    subject = key

    airfix = re.match(r"^AF(\d+)[_-](.+)$", key, flags=re.I)
    if airfix:
        brand = "Airfix"
        scale = f"1/{airfix.group(1)}"
        subject = airfix.group(2)
    else:
        amt = re.match(r"^AMT_1-(\d+)_(.+)$", key, flags=re.I)
        if amt:
            brand = "AMT"
            scale = f"1/{amt.group(1)}"
            subject = amt.group(2)

    subject = re.sub(r"_(0?\d+)([A-Za-z]*)$", r" \2", subject).strip()
    subject = re.sub(r"-(0?\d+)([A-Za-z]*)$", r" \2", subject).strip()
    subject = subject.replace("_", " ").replace("-", " ")
    subject = split_camelish(subject)
    if "MPC" in key.upper():
        notes.append("filename mentions MPC/rebox")
    if "CM" in key.upper():
        notes.append("filename mentions CM")
    return brand, scale, " ".join(subject.split()), notes


def load_kits(db_path: Path) -> list[Kit]:
    con = sqlite3.connect(db_path)
    rows = con.execute(
        "SELECT id, brand, scale, name, serial_number FROM kits ORDER BY brand, scale, name"
    ).fetchall()
    return [Kit(*[value or "" for value in row]) for row in rows]


def score_group(brand: str, scale: str, subject: str, kit: Kit) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0
    if brand and kit.brand.lower() == brand.lower():
        score += 25
        reasons.append("brand")
    elif brand and brand.lower() in kit.brand.lower():
        score += 15
        reasons.append("brand-ish")
    if scale and kit.scale == scale:
        score += 25
        reasons.append("scale")

    subject_norm = normalize_text(subject)
    kit_norm = normalize_text(kit.name)
    subject_tokens = tokens(subject)
    kit_tokens = tokens(kit.name)
    serial_tokens = tokens(kit.serial_number)
    overlap = len(subject_tokens & kit_tokens)
    union = len(subject_tokens | kit_tokens) or 1
    jaccard = overlap / union
    ratio = SequenceMatcher(None, subject_norm, kit_norm).ratio()
    score += jaccard * 38
    score += ratio * 24
    serial_overlap = len(subject_tokens & serial_tokens)
    if serial_overlap:
        score += min(8, serial_overlap * 3)
        reasons.append(f"{serial_overlap} serial overlap")
    if overlap:
        reasons.append(f"{overlap} token overlap")
    if ratio >= 0.72:
        reasons.append("name ratio")
    return round(score, 2), reasons


def confidence(score: float, top_score: float, second_score: float) -> str:
    gap = top_score - second_score
    if score >= 82 and gap >= 6:
        return "high"
    if score >= 68 and gap >= 3:
        return "medium"
    if score >= 55:
        return "low"
    return "unmatched"


def candidate_label(item: tuple[float, Kit, list[str]] | None) -> str:
    if not item:
        return ""
    score, kit, reasons = item
    return f"{kit.id}: {kit.brand} {kit.scale} {kit.name} ({score}; {', '.join(reasons)})"


def build_rows(groups: list[Group], kits: list[Kit]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for group in groups:
        brand, scale, subject, parse_notes = parse_group_key(group.key)
        filtered = [
            kit for kit in kits
            if (not brand or kit.brand.lower() == brand.lower() or brand.lower() in kit.brand.lower())
            and (not scale or kit.scale == scale)
        ]
        pool = filtered or kits
        scored = []
        for kit in pool:
            score, reasons = score_group(brand, scale, subject, kit)
            scored.append((score, kit, reasons))
        top = sorted(scored, key=lambda item: item[0], reverse=True)[:3]
        best = top[0] if top else None
        second = top[1][0] if len(top) > 1 else 0.0
        status = confidence(best[0], best[0], second) if best else "unmatched"
        lexical_match = bool(best and any(
            reason.endswith("token overlap") or reason == "name ratio" or reason.endswith("serial overlap")
            for reason in best[2]
        ))
        if best and (best[0] < 55 or (not lexical_match and best[0] < 68)):
            status = "unmatched"
        alternate = None
        if brand and scale and status == "unmatched":
            alternate_pool = [kit for kit in kits if kit.brand.lower() == brand.lower()]
            alternate_scores = []
            for kit in alternate_pool:
                alt_score, alt_reasons = score_group(brand, "", subject, kit)
                alternate_scores.append((alt_score, kit, alt_reasons))
            alternate = max(alternate_scores, key=lambda item: item[0], default=None)
        notes = sorted(set(group.notes + parse_notes))
        confirmed_kit_id = CONFIRMED_GROUP_KIT_IDS.get(group.key)
        if confirmed_kit_id:
            confirmed = next((kit for kit in kits if kit.id == confirmed_kit_id), None)
            if confirmed:
                confirmed_score, confirmed_reasons = score_group(brand, scale, subject, confirmed)
                best = (confirmed_score, confirmed, confirmed_reasons + ["user-confirmed"])
                status = "high"
                notes = sorted(set(notes + ["user-confirmed match"]))
        rows.append({
            "group_key": group.key,
            "parsed_brand": brand,
            "parsed_scale": scale,
            "parsed_subject": subject,
            "file_count": str(len(group.files)),
            "views": "; ".join(group.views),
            "confidence": status,
            "best_kit_id": str(best[1].id) if best and status != "unmatched" else "",
            "best_brand": best[1].brand if best and status != "unmatched" else "",
            "best_scale": best[1].scale if best and status != "unmatched" else "",
            "best_name": best[1].name if best and status != "unmatched" else "",
            "best_score": str(best[0]) if best else "",
            "match_reasons": "; ".join(best[2]) if best else "",
            "candidate_2": candidate_label(top[1] if len(top) > 1 else None),
            "candidate_3": candidate_label(top[2] if len(top) > 2 else None),
            "alternate_any_scale": candidate_label(alternate),
            "notes": "; ".join(notes),
            "files": "; ".join(path.name for path in group.files),
        })
    return rows


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "group_key", "parsed_brand", "parsed_scale", "parsed_subject",
        "file_count", "views", "confidence",
        "best_kit_id", "best_brand", "best_scale", "best_name", "best_score",
        "match_reasons", "candidate_2", "candidate_3", "alternate_any_scale",
        "notes", "files",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def view_sort_key(path: Path) -> tuple[int, str]:
    _, view, _ = parse_file_name(path)
    order = {
        "front": 0,
        "back": 1,
        "left": 2,
        "right": 3,
        "top": 4,
        "bottom": 5,
        "unknown": 9,
    }
    return order.get(view, 8), path.name.lower()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_image_family(db: sqlite3.Connection, title: str, notes: str) -> int:
    existing = db.execute(
        "SELECT id FROM image_families WHERE title=?",
        (title,)
    ).fetchone()
    if existing:
        db.execute(
            "UPDATE image_families SET family_type='reference_set', notes=? WHERE id=?",
            (notes, existing["id"])
        )
        return int(existing["id"])
    cur = db.execute("""
        INSERT INTO image_families (title, family_type, notes)
        VALUES (?, 'reference_set', ?)
    """, (title, notes))
    return int(cur.lastrowid)


def ensure_image_record(
    db: sqlite3.Connection,
    *,
    source_path: Path,
    group: Group,
    kit: Kit,
    sha256: str,
    view: str,
    dest_rel: str,
    image_code: str,
) -> tuple[int, bool]:
    title = f"{kit.brand} {kit.scale} {kit.name} - {view} box view"
    notes = (
        f"Imported from Kit_box_images group {group.key}. "
        f"Original filename: {source_path.name}. Matched to kit {kit.id} by match_kit_box_images.py."
    )
    existing = db.execute("SELECT id FROM images WHERE image_code=?", (image_code,)).fetchone()
    if existing:
        image_id = int(existing["id"])
        db.execute("""
            UPDATE images
            SET filename=?, title=?, image_code=?, caption=?, url=?, storage_kind=?,
                storage_path=?, sha256=?, image_type=?, source=?, notes=?
            WHERE id=?
        """, (
            dest_rel,
            title,
            image_code,
            f"{view} view from manually collected kit box image set.",
            f"/uploads/{dest_rel}",
            "upload",
            str((UPLOAD_ROOT / dest_rel).resolve()),
            sha256,
            "box_art",
            "Kit_box_images",
            notes,
            image_id,
        ))
        return image_id, False
    cur = db.execute("""
        INSERT INTO images (
            filename, title, image_code, caption, url, storage_kind, storage_path,
            sha256, image_type, source, notes
        )
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        dest_rel,
        title,
        image_code,
        f"{view} view from manually collected kit box image set.",
        f"/uploads/{dest_rel}",
        "upload",
        str((UPLOAD_ROOT / dest_rel).resolve()),
        sha256,
        "box_art",
        "Kit_box_images",
        notes,
    ))
    return int(cur.lastrowid), True


def ensure_image_link(db: sqlite3.Connection, image_id: int, kit_id: int, annotation: str) -> bool:
    existing = db.execute("""
        SELECT id FROM image_links
        WHERE image_id=? AND entity_type='kit' AND entity_id=?
    """, (image_id, kit_id)).fetchone()
    if existing:
        db.execute("UPDATE image_links SET annotation=? WHERE id=?", (annotation, existing["id"]))
        return False
    db.execute("""
        INSERT INTO image_links (image_id, entity_type, entity_id, annotation)
        VALUES (?, 'kit', ?, ?)
    """, (image_id, kit_id, annotation))
    return True


def ensure_family_member(
    db: sqlite3.Connection,
    family_id: int,
    image_id: int,
    *,
    relation_type: str,
    sort_order: int,
    is_primary: int,
    notes: str,
) -> bool:
    existing = db.execute(
        "SELECT id, family_id FROM image_family_members WHERE image_id=?",
        (image_id,)
    ).fetchone()
    if existing:
        db.execute("""
            UPDATE image_family_members
            SET relation_type=?, sort_order=?, is_primary=?, is_hidden_in_library=0,
                coverage_role='full_frame', notes=?
            WHERE id=?
        """, (relation_type, sort_order, is_primary, notes, existing["id"]))
        return False
    db.execute("""
        INSERT INTO image_family_members (
            family_id, image_id, relation_type, sort_order, is_primary,
            is_hidden_in_library, coverage_role, notes
        )
        VALUES (?,?,?,?,?,0,'full_frame',?)
    """, (family_id, image_id, relation_type, sort_order, is_primary, notes))
    return True


def apply_import(db_path: Path, rows: list[dict[str, str]], groups: list[Group], kits: list[Kit]) -> dict[str, int]:
    kit_by_id = {str(kit.id): kit for kit in kits}
    group_by_key = {group.key: group for group in groups}
    stats = defaultdict(int)
    KIT_BOX_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    try:
        for row in rows:
            if row["confidence"] != "high":
                stats["skipped_not_high"] += 1
                continue
            kit = kit_by_id.get(row["best_kit_id"])
            group = group_by_key.get(row["group_key"])
            if not kit or not group:
                stats["skipped_missing_match"] += 1
                continue
            family_title = f"Kit box views: {kit.brand} {kit.scale} {kit.name} [{group.key}]"
            family_notes = (
                "Imported from SW-ANH-donors_public/Kit_box_images. "
                f"Matched group {group.key} to kit {kit.id}."
            )
            family_id = ensure_image_family(db, family_title, family_notes)
            stats["families_seen"] += 1

            primary_image_id = None
            files = sorted(group.files, key=view_sort_key)
            for index, source_path in enumerate(files):
                _, view, notes = parse_file_name(source_path)
                sha256 = file_sha256(source_path)
                dest_name = (
                    f"{kit.id}_{slug(group.key, 64)}_{slug(source_path.stem, 70)}_"
                    f"{sha256[:12]}{source_path.suffix.lower()}"
                )
                dest_rel = f"kit_box_images/{dest_name}"
                dest_abs = UPLOAD_ROOT / dest_rel
                if not dest_abs.exists():
                    shutil.copy2(source_path, dest_abs)
                    stats["files_copied"] += 1
                else:
                    stats["files_existing"] += 1
                image_code = f"KITBOX-{slug(group.key, 48).upper()}-{slug(source_path.stem, 48).upper()}-{sha256[:8].upper()}"
                image_id, created = ensure_image_record(
                    db,
                    source_path=source_path,
                    group=group,
                    kit=kit,
                    sha256=sha256,
                    view=view,
                    dest_rel=dest_rel,
                    image_code=image_code,
                )
                stats["images_created" if created else "images_updated"] += 1
                linked = ensure_image_link(
                    db,
                    image_id,
                    kit.id,
                    f"Kit box image {view}; source group {group.key}."
                )
                stats["links_created" if linked else "links_existing"] += 1
                is_primary = 1 if view == "front" and primary_image_id is None else 0
                relation_type = "primary" if is_primary else "variant"
                member_created = ensure_family_member(
                    db,
                    family_id,
                    image_id,
                    relation_type=relation_type,
                    sort_order=index,
                    is_primary=is_primary,
                    notes="; ".join(notes) if notes else f"{view} view",
                )
                stats["family_members_created" if member_created else "family_members_updated"] += 1
                if is_primary:
                    primary_image_id = image_id
            if primary_image_id is None and files:
                first = db.execute("""
                    SELECT image_id FROM image_family_members
                    WHERE family_id=?
                    ORDER BY sort_order, id
                    LIMIT 1
                """, (family_id,)).fetchone()
                primary_image_id = int(first["image_id"]) if first else None
            if primary_image_id:
                db.execute(
                    "UPDATE image_families SET primary_image_id=? WHERE id=?",
                    (primary_image_id, family_id)
                )
                db.execute(
                    "UPDATE image_family_members SET is_primary=CASE WHEN image_id=? THEN 1 ELSE 0 END WHERE family_id=?",
                    (primary_image_id, family_id)
                )
                db.execute("""
                    UPDATE image_family_members
                    SET relation_type=CASE
                        WHEN image_id=? THEN 'primary'
                        WHEN relation_type='primary' THEN 'variant'
                        ELSE relation_type
                    END
                    WHERE family_id=?
                """, (primary_image_id, family_id))
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return dict(stats)


def main() -> int:
    parser = argparse.ArgumentParser(description="Dry-run match kit box image filenames to kits.")
    parser.add_argument("--image-root", type=Path, default=DEFAULT_IMAGE_ROOT)
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--out", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--apply", action="store_true", help="import high-confidence matches into images/image_links")
    args = parser.parse_args()

    if not args.image_root.exists():
        raise SystemExit(f"Image folder not found: {args.image_root}")
    if not args.db.exists():
        raise SystemExit(f"Database not found: {args.db}")

    groups = group_files(args.image_root)
    kits = load_kits(args.db)
    rows = build_rows(groups, kits)
    write_csv(rows, args.out)

    counts = defaultdict(int)
    for row in rows:
        counts[row["confidence"]] += 1
    print(f"Image files: {sum(int(row['file_count']) for row in rows)}")
    print(f"Groups: {len(rows)}")
    print("Confidence:")
    for key in ("high", "medium", "low", "unmatched"):
        print(f"  {key}: {counts[key]}")
    print(f"Report: {args.out}")
    if args.apply:
        stats = apply_import(args.db, rows, groups, kits)
        print("Applied import:")
        for key in sorted(stats):
            print(f"  {key}: {stats[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
