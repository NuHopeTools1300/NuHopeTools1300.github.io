#!/usr/bin/env python3
"""
Inventory, deduplicate, and classify local reference-image corpora without
touching the originals.

This script is designed for large, messy local reference folders. It:
  - walks configured roots
  - excludes configured subtrees
  - keeps image files only
  - computes exact duplicate groups by sha256
  - extracts width/height from image headers when possible
  - infers likely source/origin from path and filename clues
  - infers subject / model scope
  - emits DB-prep manifests and a summary report

Outputs:
  - corpus_all_images.csv
  - corpus_canonical_images.csv
  - corpus_duplicate_groups.csv
  - corpus_db_prep.csv
  - corpus_summary.md
  - corpus_summary.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import struct
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "export_text" / "research" / "local_reference_corpus"

SOURCE_ROOTS = [
    ("mf_references", Path(r"D:\Documents\privat\MillenniumFalcon\mf\References"), "Millennium Falcon"),
    ("y_wing", Path(r"D:\Documents\privat\MillenniumFalcon\y-wing"), "Y-Wing"),
]

EXCLUDE_DIRS = {
    Path(r"D:\Documents\privat\MillenniumFalcon\mf\References\exhibition_photo_sets"),
    Path(r"D:\Documents\privat\MillenniumFalcon\mf\References\other_ANH_models\ISD"),
    Path(r"D:\Documents\privat\MillenniumFalcon\y-wing\GoldLeader"),
    Path(r"D:\Documents\privat\MillenniumFalcon\mf\References\FrankWire"),
    Path(r"D:\Documents\privat\MillenniumFalcon\mf\References\DrMaul"),
    Path(r"D:\Documents\privat\MillenniumFalcon\mf\References\Bandai_Perfect_Grade"),
    Path(r"D:\Documents\privat\MillenniumFalcon\mf\References\historical\chronicles_book"),
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".gif", ".webp", ".bmp"}
HASHLIKE_NAME_RE = re.compile(r"^[0-9a-f]{20,}(?:-[0-9a-z]+)?$", re.IGNORECASE)
FACEBOOK_NAME_RE = re.compile(r"(?:^|_)\d{6,}_[0-9]{6,}_[0-9]{6,}_[no](?:\.[a-z0-9]+)?$", re.IGNORECASE)
FACEBOOK_SIMPLE_RE = re.compile(r"_[0-9]{8,}_[0-9]{8,}_[0-9]{8,}_[no]\b", re.IGNORECASE)

PERSON_SOURCES = {
    "chriscasady": "Chris Casady",
    "davejones": "Dave Jones",
    "daveg": "Dave G",
    "drmaul": "DrMaul",
    "frankwire": "Frank Wire",
    "monsieurtox": "monsieurtox",
    "crudecasts": "CrudeCasts",
    "nicen_redjammer": "NiceN / RedJammer",
    "nice n_redjammer": "NiceN / RedJammer",
    "goldleader": "Gold Leader collection",
    "redjammer": "Red Jammer collection",
}

SUBJECT_HINTS = [
    ("blockade runner", "Blockade Runner"),
    ("tantive", "Blockade Runner"),
    ("x wing", "X-Wing"),
    ("x-wing", "X-Wing"),
    ("y wing", "Y-Wing"),
    ("y-wing", "Y-Wing"),
    ("tie fighter", "TIE Fighter"),
    ("tie-fighter", "TIE Fighter"),
    ("tie advanced", "TIE Advanced"),
    ("tie-advanced", "TIE Advanced"),
    ("star destroyer", "Star Destroyer"),
    ("isd", "Star Destroyer"),
    ("death star", "Death Star"),
    ("sandcrawler", "Sandcrawler"),
    ("landspeeder", "Landspeeder"),
    ("escape pod", "Escape Pod"),
    ("training remote", "Training Remote"),
    ("gold leader", "Y-Wing Gold Leader"),
    ("red jammer", "Y-Wing Red Jammer"),
    ("cantwell", "Y-Wing Cantwell"),
    ("pyro", "Pyro miniature"),
]


@dataclass
class ImageRecord:
    root_key: str
    root_path: Path
    default_subject: str
    abs_path: Path
    rel_path: Path
    filename: str
    ext: str
    size_bytes: int
    modified_ts: float
    sha256: str
    width: int | None
    height: int | None
    source_platform: str
    source_collection: str
    source_creator: str
    source_confidence: str
    subject: str
    subject_detail: str
    content_kind: str
    is_hidden: bool
    is_hashlike_name: bool


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inventory and classify local reference image corpora.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help=f"Directory for manifests and reports (default: {DEFAULT_OUTPUT_DIR})")
    return parser.parse_args()


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = value.lower().replace("_", " ").replace("-", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def should_skip(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        return True
    for exclude in EXCLUDE_DIRS:
        try:
            if resolved == exclude.resolve() or exclude.resolve() in resolved.parents:
                return True
        except OSError:
            continue
    return False


def iter_image_files(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        dirnames[:] = [d for d in dirnames if not should_skip(current / d)]
        for filename in filenames:
            path = current / filename
            if should_skip(path):
                continue
            if path.suffix.lower() in IMAGE_EXTENSIONS:
                yield path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def parse_png_size(handle) -> tuple[int, int] | tuple[None, None]:
    sig = handle.read(24)
    if len(sig) >= 24 and sig[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", sig[16:24])
    return None, None


def parse_gif_size(handle) -> tuple[int, int] | tuple[None, None]:
    header = handle.read(10)
    if len(header) >= 10 and header[:6] in (b"GIF87a", b"GIF89a"):
        return struct.unpack("<HH", header[6:10])
    return None, None


def parse_bmp_size(handle) -> tuple[int, int] | tuple[None, None]:
    header = handle.read(26)
    if len(header) >= 26 and header[:2] == b"BM":
        return struct.unpack("<II", header[18:26])
    return None, None


def parse_webp_size(handle) -> tuple[int, int] | tuple[None, None]:
    data = handle.read(64)
    if len(data) < 30 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None, None
    chunk = data[12:16]
    if chunk == b"VP8 " and len(data) >= 30:
        return struct.unpack("<HH", data[26:30])
    if chunk == b"VP8L" and len(data) >= 25:
        b0, b1, b2, b3 = data[21:25]
        width = 1 + (((b1 & 0x3F) << 8) | b0)
        height = 1 + (((b3 & 0x0F) << 10) | (b2 << 2) | ((b1 & 0xC0) >> 6))
        return width, height
    if chunk == b"VP8X" and len(data) >= 30:
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return width, height
    return None, None


def parse_tiff_size(handle) -> tuple[int, int] | tuple[None, None]:
    header = handle.read(8)
    if len(header) < 8:
        return None, None
    if header[:2] == b"II":
        endian = "<"
    elif header[:2] == b"MM":
        endian = ">"
    else:
        return None, None
    if struct.unpack(endian + "H", header[2:4])[0] != 42:
        return None, None
    ifd_offset = struct.unpack(endian + "I", header[4:8])[0]
    handle.seek(ifd_offset)
    entry_count_data = handle.read(2)
    if len(entry_count_data) < 2:
        return None, None
    entry_count = struct.unpack(endian + "H", entry_count_data)[0]
    width = height = None
    for _ in range(entry_count):
        entry = handle.read(12)
        if len(entry) < 12:
            break
        tag, type_id, count, value = struct.unpack(endian + "HHII", entry)
        if tag == 256:
            width = value
        elif tag == 257:
            height = value
        if width and height:
            return width, height
    return width, height


def parse_jpeg_size(handle) -> tuple[int, int] | tuple[None, None]:
    if handle.read(2) != b"\xff\xd8":
        return None, None
    while True:
        marker_prefix = handle.read(1)
        if not marker_prefix:
            return None, None
        if marker_prefix != b"\xff":
            continue
        marker = handle.read(1)
        while marker == b"\xff":
            marker = handle.read(1)
        if not marker or marker in {b"\xd8", b"\xd9"}:
            continue
        if marker in {b"\x01"} or 0xD0 <= marker[0] <= 0xD7:
            continue
        length_data = handle.read(2)
        if len(length_data) != 2:
            return None, None
        seg_len = struct.unpack(">H", length_data)[0]
        if seg_len < 2:
            return None, None
        if marker[0] in {
            0xC0, 0xC1, 0xC2, 0xC3,
            0xC5, 0xC6, 0xC7,
            0xC9, 0xCA, 0xCB,
            0xCD, 0xCE, 0xCF,
        }:
            data = handle.read(5)
            if len(data) != 5:
                return None, None
            _, height, width = struct.unpack(">BHH", data)
            return width, height
        handle.seek(seg_len - 2, os.SEEK_CUR)


def image_size(path: Path) -> tuple[int | None, int | None]:
    try:
        with path.open("rb") as handle:
            ext = path.suffix.lower()
            if ext == ".png":
                return parse_png_size(handle)
            if ext in {".gif"}:
                return parse_gif_size(handle)
            if ext in {".bmp"}:
                return parse_bmp_size(handle)
            if ext in {".webp"}:
                return parse_webp_size(handle)
            if ext in {".tif", ".tiff"}:
                return parse_tiff_size(handle)
            if ext in {".jpg", ".jpeg"}:
                return parse_jpeg_size(handle)
    except Exception:
        return None, None
    return None, None


def descriptive_filename_score(filename: str) -> int:
    stem = Path(filename).stem
    score = 0
    if not HASHLIKE_NAME_RE.match(stem):
        score += 2
    if "youtube" in filename.lower():
        score += 1
    if "propstore" in filename.lower():
        score += 1
    if "rpf" in filename.lower() or "therpf" in filename.lower():
        score += 1
    if len(stem) > 12:
        score += 1
    return score


def infer_source(path_parts: list[str], filename: str) -> tuple[str, str, str, str]:
    parts_norm = [normalize_text(p) for p in path_parts]
    filename_norm = normalize_text(filename)
    combined = " | ".join(parts_norm + [filename_norm])

    for part in parts_norm:
        key = part.replace(" ", "")
        if key in PERSON_SOURCES:
            return "personal_archive", part, PERSON_SOURCES[key], "high"

    if "propstoreauctions" in combined or "propstore" in combined:
        return "auction", "Propstore", "Propstore", "high"
    if "therpf" in combined or "rpf costume and prop maker community" in combined:
        return "forum", "theRPF", "theRPF", "high"
    if "youtube" in combined:
        return "video", "YouTube", "YouTube", "high"
    if "fb" in parts_norm or "facebook" in combined or FACEBOOK_NAME_RE.search(filename) or FACEBOOK_SIMPLE_RE.search(filename):
        return "social", "Facebook", "Facebook", "medium"
    if "historical" in parts_norm:
        return "historical", "historical", "local historical compilation", "medium"
    if "internet sources" in parts_norm or "internet source" in combined:
        return "web", "internet_sources", "local internet compilation", "medium"
    if "bandai perfect grade" in combined:
        return "kit_reference", "Bandai Perfect Grade", "kit reference set", "medium"
    if "goldleader" in combined:
        return "collection", "GoldLeader", "Gold Leader collection", "medium"
    if "redjammer" in combined:
        return "collection", "RedJammer", "Red Jammer collection", "medium"

    return "unknown", "", "", "low"


def infer_subject(root_key: str, default_subject: str, rel_parts: list[str], filename: str) -> tuple[str, str]:
    filename_norm = normalize_text(filename)
    parts_norm = [normalize_text(p) for p in rel_parts]
    combined = " | ".join(parts_norm + [filename_norm])

    if root_key == "mf_references" and parts_norm:
        if parts_norm[0] == "other anh models":
            if len(parts_norm) > 1:
                sub = parts_norm[1]
                for hint, subject in SUBJECT_HINTS:
                    if hint in sub:
                        return subject, rel_parts[1]
            return "Other ANH models", rel_parts[1] if len(rel_parts) > 1 else ""

    for hint, subject in SUBJECT_HINTS:
        if hint in combined:
            return subject, rel_parts[0] if rel_parts else ""

    if root_key == "y_wing":
        if parts_norm and parts_norm[0] == "goldleader":
            return "Y-Wing Gold Leader", rel_parts[0]
        if parts_norm and parts_norm[0] == "redjammer":
            return "Y-Wing Red Jammer", rel_parts[0]
        return "Y-Wing", rel_parts[0] if rel_parts else ""

    return default_subject, rel_parts[0] if rel_parts else ""


def infer_content_kind(rel_parts: list[str], filename: str, source_platform: str) -> str:
    parts_norm = [normalize_text(p) for p in rel_parts]
    filename_norm = normalize_text(filename)
    combined = " | ".join(parts_norm + [filename_norm])

    if "map" in combined:
        return "map_or_markup"
    if source_platform == "auction":
        return "auction_photo"
    if source_platform == "forum":
        return "forum_capture"
    if source_platform == "video":
        return "video_screencap"
    if source_platform == "social":
        return "social_media_image"
    if "historical" in parts_norm:
        return "historical_reference"
    if "blender" in parts_norm or filename.lower().endswith(".webp"):
        return "render_or_cg"
    if "bandai perfect grade" in combined:
        return "kit_reference"
    return "reference_image"


def preferred_record(records: list[ImageRecord]) -> ImageRecord:
    def key(record: ImageRecord):
        return (
            record.is_hidden,
            -record.size_bytes,
            -(record.width or 0) * (record.height or 0),
            -descriptive_filename_score(record.filename),
            len(str(record.rel_path)),
            str(record.rel_path).lower(),
        )

    return sorted(records, key=key)[0]


def collect_records() -> list[ImageRecord]:
    records: list[ImageRecord] = []
    for root_key, root_path, default_subject in SOURCE_ROOTS:
        for abs_path in iter_image_files(root_path):
            rel_path = abs_path.relative_to(root_path)
            rel_parts = list(rel_path.parts[:-1])
            source_platform, source_collection, source_creator, source_confidence = infer_source(rel_parts, abs_path.name)
            subject, subject_detail = infer_subject(root_key, default_subject, rel_parts, abs_path.name)
            content_kind = infer_content_kind(rel_parts, abs_path.name, source_platform)
            width, height = image_size(abs_path)
            stat = abs_path.stat()
            records.append(
                ImageRecord(
                    root_key=root_key,
                    root_path=root_path,
                    default_subject=default_subject,
                    abs_path=abs_path,
                    rel_path=rel_path,
                    filename=abs_path.name,
                    ext=abs_path.suffix.lower(),
                    size_bytes=stat.st_size,
                    modified_ts=stat.st_mtime,
                    sha256=sha256_file(abs_path),
                    width=width,
                    height=height,
                    source_platform=source_platform,
                    source_collection=source_collection,
                    source_creator=source_creator,
                    source_confidence=source_confidence,
                    subject=subject,
                    subject_detail=subject_detail,
                    content_kind=content_kind,
                    is_hidden=abs_path.name.startswith("."),
                    is_hashlike_name=bool(HASHLIKE_NAME_RE.match(abs_path.stem)),
                )
            )
    return records


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]):
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def summarize(records: list[ImageRecord], groups: dict[str, list[ImageRecord]], canonical_by_hash: dict[str, ImageRecord]) -> tuple[dict, str]:
    total = len(records)
    unique = len(canonical_by_hash)
    duplicate_files = total - unique
    duplicate_groups = sum(1 for g in groups.values() if len(g) > 1)

    by_root = Counter(r.root_key for r in records)
    by_subject = Counter(r.subject for r in records)
    by_source = Counter((r.source_platform or "unknown", r.source_collection or "") for r in records)
    by_kind = Counter(r.content_kind for r in records)

    summary = {
        "total_image_files": total,
        "unique_exact_images": unique,
        "duplicate_files": duplicate_files,
        "duplicate_groups": duplicate_groups,
        "by_root": dict(by_root.most_common()),
        "by_subject": dict(by_subject.most_common()),
        "by_source": {f"{plat}:{coll}".rstrip(":"): count for (plat, coll), count in by_source.most_common()},
        "by_content_kind": dict(by_kind.most_common()),
    }

    lines = [
        "# Local Reference Corpus Summary",
        "",
        "## Overview",
        "",
        f"- Total image files scanned: `{total}`",
        f"- Unique exact-image hashes: `{unique}`",
        f"- Duplicate files beyond canonical copies: `{duplicate_files}`",
        f"- Duplicate groups: `{duplicate_groups}`",
        "",
        "## By Root",
        "",
    ]
    for key, count in by_root.most_common():
        lines.append(f"- `{key}`: `{count}`")

    lines.extend(["", "## By Subject", ""])
    for key, count in by_subject.most_common(20):
        lines.append(f"- `{key}`: `{count}`")

    lines.extend(["", "## By Source", ""])
    for (platform, collection), count in by_source.most_common(20):
        label = f"{platform}:{collection}".rstrip(":")
        lines.append(f"- `{label}`: `{count}`")

    lines.extend(["", "## By Content Kind", ""])
    for key, count in by_kind.most_common():
        lines.append(f"- `{key}`: `{count}`")

    return summary, "\n".join(lines) + "\n"


def main():
    args = parse_args()
    output_dir = args.output_dir
    ensure_dir(output_dir)

    records = collect_records()
    groups: dict[str, list[ImageRecord]] = defaultdict(list)
    for record in records:
        groups[record.sha256].append(record)

    canonical_by_hash: dict[str, ImageRecord] = {}
    all_rows: list[dict] = []
    canonical_rows: list[dict] = []
    duplicate_rows: list[dict] = []
    db_rows: list[dict] = []

    for sha, group in groups.items():
        canonical = preferred_record(group)
        canonical_by_hash[sha] = canonical
        dup_count = len(group)

        suggested_title = canonical.subject
        if canonical.source_collection:
            suggested_title += f" - {canonical.source_collection}"
        if canonical.subject_detail:
            suggested_title += f" - {canonical.subject_detail}"

        canonical_row = {
            "sha256": sha,
            "canonical_abs_path": str(canonical.abs_path),
            "canonical_rel_path": str(canonical.rel_path),
            "filename": canonical.filename,
            "ext": canonical.ext,
            "size_bytes": canonical.size_bytes,
            "width": canonical.width or "",
            "height": canonical.height or "",
            "root_key": canonical.root_key,
            "subject": canonical.subject,
            "subject_detail": canonical.subject_detail,
            "source_platform": canonical.source_platform,
            "source_collection": canonical.source_collection,
            "source_creator": canonical.source_creator,
            "source_confidence": canonical.source_confidence,
            "content_kind": canonical.content_kind,
            "duplicate_count": dup_count,
            "suggested_title": suggested_title,
            "suggested_image_code": f"REF-{sha[:12].upper()}",
            "db_ready": "yes",
        }
        canonical_rows.append(canonical_row)
        db_rows.append(canonical_row.copy())

        if dup_count > 1:
            for record in sorted(group, key=lambda r: str(r.abs_path).lower()):
                duplicate_rows.append(
                    {
                        "sha256": sha,
                        "canonical_abs_path": str(canonical.abs_path),
                        "duplicate_abs_path": str(record.abs_path),
                        "duplicate_rel_path": str(record.rel_path),
                        "root_key": record.root_key,
                        "filename": record.filename,
                        "size_bytes": record.size_bytes,
                        "is_canonical": "yes" if record.abs_path == canonical.abs_path else "no",
                    }
                )

        for record in group:
            all_rows.append(
                {
                    "sha256": sha,
                    "abs_path": str(record.abs_path),
                    "rel_path": str(record.rel_path),
                    "root_key": record.root_key,
                    "filename": record.filename,
                    "ext": record.ext,
                    "size_bytes": record.size_bytes,
                    "width": record.width or "",
                    "height": record.height or "",
                    "subject": record.subject,
                    "subject_detail": record.subject_detail,
                    "source_platform": record.source_platform,
                    "source_collection": record.source_collection,
                    "source_creator": record.source_creator,
                    "source_confidence": record.source_confidence,
                    "content_kind": record.content_kind,
                    "is_hidden": "yes" if record.is_hidden else "no",
                    "is_hashlike_name": "yes" if record.is_hashlike_name else "no",
                    "duplicate_count": dup_count,
                    "is_canonical": "yes" if record.abs_path == canonical.abs_path else "no",
                    "canonical_abs_path": str(canonical.abs_path),
                }
            )

    all_rows.sort(key=lambda row: (row["root_key"], row["subject"], row["source_platform"], row["rel_path"].lower()))
    canonical_rows.sort(key=lambda row: (row["subject"], row["source_platform"], row["filename"].lower()))
    duplicate_rows.sort(key=lambda row: (row["sha256"], row["is_canonical"] != "yes", row["duplicate_abs_path"].lower()))
    db_rows.sort(key=lambda row: (row["subject"], row["source_platform"], row["filename"].lower()))

    write_csv(
        output_dir / "corpus_all_images.csv",
        all_rows,
        [
            "sha256", "abs_path", "rel_path", "root_key", "filename", "ext", "size_bytes",
            "width", "height", "subject", "subject_detail", "source_platform", "source_collection",
            "source_creator", "source_confidence", "content_kind", "is_hidden",
            "is_hashlike_name", "duplicate_count", "is_canonical", "canonical_abs_path",
        ],
    )
    write_csv(
        output_dir / "corpus_canonical_images.csv",
        canonical_rows,
        [
            "sha256", "canonical_abs_path", "canonical_rel_path", "filename", "ext", "size_bytes",
            "width", "height", "root_key", "subject", "subject_detail", "source_platform",
            "source_collection", "source_creator", "source_confidence", "content_kind",
            "duplicate_count", "suggested_title", "suggested_image_code", "db_ready",
        ],
    )
    write_csv(
        output_dir / "corpus_duplicate_groups.csv",
        duplicate_rows,
        [
            "sha256", "canonical_abs_path", "duplicate_abs_path", "duplicate_rel_path",
            "root_key", "filename", "size_bytes", "is_canonical",
        ],
    )
    write_csv(
        output_dir / "corpus_db_prep.csv",
        db_rows,
        [
            "sha256", "canonical_abs_path", "canonical_rel_path", "filename", "ext", "size_bytes",
            "width", "height", "root_key", "subject", "subject_detail", "source_platform",
            "source_collection", "source_creator", "source_confidence", "content_kind",
            "duplicate_count", "suggested_title", "suggested_image_code", "db_ready",
        ],
    )

    summary_json, summary_md = summarize(records, groups, canonical_by_hash)
    (output_dir / "corpus_summary.json").write_text(json.dumps(summary_json, indent=2), encoding="utf-8")
    (output_dir / "corpus_summary.md").write_text(summary_md, encoding="utf-8")
    print(json.dumps(summary_json, indent=2))


if __name__ == "__main__":
    main()
