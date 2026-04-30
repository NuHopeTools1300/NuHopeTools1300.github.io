#!/usr/bin/env python
"""Fetch Scalemates kit images into the local upload cache.

The script reads kits.scalemates_url, finds the best product/box-art image on
the Scalemates page, downloads it into backend/data/uploads/kit_thumbnails, and
updates kits.thumbnail_url plus kits.thumbnail_source_url.
"""

from __future__ import annotations

import argparse
import hashlib
import mimetypes
import re
import shutil
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "backend" / "data" / "ilm1300.db"
THUMB_DIR = ROOT / "backend" / "data" / "uploads" / "kit_thumbnails"
BACKUP_PATH = DB_PATH.with_name(f"{DB_PATH.name}.bak.scalemates_thumbnails")
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

SKIP_URL_WORDS = (
    "logo",
    "banner",
    "advert",
    "ads",
    "sprite",
    "icon",
    "favicon",
    "profile",
    "avatar",
    "facebook",
    "twitter",
    "instagram",
    "sockelshop",
)


@dataclass
class ImageCandidate:
    url: str
    score: int
    reason: str


class ScalematesImageParser(HTMLParser):
    def __init__(self, base_url: str, kit_words: set[str]):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.kit_words = kit_words
        self.candidates: list[ImageCandidate] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = {name.lower(): (value or "") for name, value in attrs}
        tag = tag.lower()
        if tag == "meta":
            key = (attrs_dict.get("property") or attrs_dict.get("name") or "").lower()
            if key in {"og:image", "og:image:url", "twitter:image", "twitter:image:src"}:
                self.add(attrs_dict.get("content", ""), 35, key)
            return
        if tag != "img":
            return
        alt = attrs_dict.get("alt", "")
        title = attrs_dict.get("title", "")
        for attr in ("src", "data-src", "data-original", "data-lazy-src"):
            self.add(attrs_dict.get(attr, ""), 20, f"img {attr}", alt, title)
        for attr in ("srcset", "data-srcset"):
            first = first_srcset_url(attrs_dict.get(attr, ""))
            self.add(first, 20, f"img {attr}", alt, title)

    def add(self, raw_url: str, base_score: int, reason: str, alt: str = "", title: str = "") -> None:
        if not raw_url:
            return
        url = urljoin(self.base_url, raw_url.strip())
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            return
        haystack = " ".join([url, alt, title]).lower()
        if any(word in haystack for word in SKIP_URL_WORDS):
            return
        score = base_score
        if "products/img" in haystack:
            score += 80
        if "/products/" in haystack:
            score += 45
        if "product" in haystack:
            score += 20
        if any(word and word in haystack for word in self.kit_words):
            score += 25
        if "preview" in haystack or "box" in haystack or "cover" in haystack:
            score += 12
        if re.search(r"\.(jpe?g|png|webp)(?:[?#]|$)", url, re.I):
            score += 8
        self.candidates.append(ImageCandidate(url=url, score=score, reason=reason))


def first_srcset_url(value: str) -> str:
    if not value:
        return ""
    first = value.split(",", 1)[0].strip()
    return first.split(" ", 1)[0].strip()


def important_words(*values: object) -> set[str]:
    text = " ".join(str(value or "") for value in values).lower()
    words = {word for word in re.split(r"[^a-z0-9]+", text) if len(word) >= 3}
    return {word for word in words if word not in {"the", "and", "kit", "model"}}


def fetch_bytes(url: str, timeout: int) -> tuple[bytes, str]:
    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,de;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "")
        return response.read(), content_type


def candidate_images(page_url: str, html: str, kit: sqlite3.Row) -> list[ImageCandidate]:
    parser = ScalematesImageParser(
        page_url,
        important_words(kit["brand"], kit["name"], kit["serial_number"], kit["scale"]),
    )
    parser.feed(html)
    deduped: dict[str, ImageCandidate] = {}
    for candidate in parser.candidates:
        current = deduped.get(candidate.url)
        if current is None or candidate.score > current.score:
            deduped[candidate.url] = candidate
    return sorted(deduped.values(), key=lambda item: item.score, reverse=True)


def extension_for(content_type: str, source_url: str) -> str:
    parsed_ext = Path(urlparse(source_url).path).suffix.lower()
    if parsed_ext in {".jpg", ".jpeg", ".png", ".webp"}:
        return ".jpg" if parsed_ext == ".jpeg" else parsed_ext
    guessed = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
    if guessed in {".jpg", ".jpeg", ".png", ".webp"}:
        return ".jpg" if guessed == ".jpeg" else guessed
    return ".jpg"


def safe_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:80] or "kit"


def select_downloadable_image(candidates: Iterable[ImageCandidate], timeout: int) -> tuple[ImageCandidate, bytes, str]:
    errors: list[str] = []
    for candidate in candidates:
        try:
            data, content_type = fetch_bytes(candidate.url, timeout)
        except Exception as error:  # noqa: BLE001 - report and try next candidate
            errors.append(f"{candidate.url}: {error}")
            continue
        if not content_type.lower().startswith("image/"):
            errors.append(f"{candidate.url}: not an image ({content_type})")
            continue
        if len(data) < 1024:
            errors.append(f"{candidate.url}: image too small")
            continue
        return candidate, data, content_type
    raise RuntimeError("; ".join(errors[:5]) or "no downloadable image candidates")


def ensure_columns(db: sqlite3.Connection) -> None:
    existing = {row[1] for row in db.execute("PRAGMA table_info(kits)").fetchall()}
    for name, ddl in {
        "thumbnail_url": "TEXT",
        "thumbnail_source_url": "TEXT",
        "thumbnail_fetched_at": "TEXT",
    }.items():
        if name not in existing:
            db.execute(f"ALTER TABLE kits ADD COLUMN {name} {ddl}")


def existing_kit_columns(db: sqlite3.Connection) -> set[str]:
    return {row[1] for row in db.execute("PRAGMA table_info(kits)").fetchall()}


def kit_rows(db: sqlite3.Connection, kit_id: int | None, force: bool) -> list[sqlite3.Row]:
    columns = existing_kit_columns(db)
    thumbnail_expr = "thumbnail_url" if "thumbnail_url" in columns else "NULL AS thumbnail_url"
    sql = """
        SELECT id, brand, scale, name, serial_number, scalemates_url, {thumbnail_expr}
        FROM kits
        WHERE scalemates_url IS NOT NULL
          AND trim(scalemates_url) != ''
    """.format(thumbnail_expr=thumbnail_expr)
    params: list[object] = []
    if kit_id:
        sql += " AND id=?"
        params.append(kit_id)
    if not force and "thumbnail_url" in columns:
        sql += " AND (thumbnail_url IS NULL OR trim(thumbnail_url) = '')"
    sql += " ORDER BY brand, name"
    return list(db.execute(sql, params))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kit-id", type=int, help="fetch one kit only")
    parser.add_argument("--limit", type=int, help="maximum kits to process")
    parser.add_argument("--force", action="store_true", help="refresh kits that already have thumbnails")
    parser.add_argument("--dry-run", action="store_true", help="show work without downloading images or writing")
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--sleep", type=float, default=0.5, help="pause between Scalemates page requests")
    args = parser.parse_args()

    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    THUMB_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    try:
        if not args.dry_run:
            if not BACKUP_PATH.exists():
                shutil.copy2(DB_PATH, BACKUP_PATH)
                print(f"Backup written: {BACKUP_PATH}")
            ensure_columns(db)
            db.commit()
        rows = kit_rows(db, args.kit_id, args.force)
        if args.limit:
            rows = rows[: args.limit]
        print(f"Kits to process: {len(rows)}")
        if args.dry_run:
            missing = {"thumbnail_url", "thumbnail_source_url", "thumbnail_fetched_at"} - existing_kit_columns(db)
            if missing:
                print(f"Dry run: would add kit columns: {', '.join(sorted(missing))}")
            for kit in rows[:25]:
                print(f"  {kit['id']}: {kit['brand']} {kit['scale'] or ''} {kit['name']} -> {kit['scalemates_url']}")
            return 0

        updated = 0
        failed = 0
        for index, kit in enumerate(rows, start=1):
            label = f"{kit['brand']} {kit['scale'] or ''} {kit['name']}".strip()
            page_url = kit["scalemates_url"]
            print(f"[{index}/{len(rows)}] {kit['id']} {label}")
            try:
                html_bytes, _ = fetch_bytes(page_url, args.timeout)
                html = html_bytes.decode("utf-8", errors="replace")
                candidates = candidate_images(page_url, html, kit)
                if not candidates:
                    raise RuntimeError("no image candidates found")
                candidate, image_bytes, content_type = select_downloadable_image(candidates, args.timeout)
                digest = hashlib.sha256(image_bytes).hexdigest()[:16]
                ext = extension_for(content_type, candidate.url)
                filename = f"kit_{kit['id']}_{safe_slug(label)}_{digest}{ext}"
                target = THUMB_DIR / filename
                target.write_bytes(image_bytes)
                local_url = f"/uploads/kit_thumbnails/{filename}"
                fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
                db.execute(
                    """
                    UPDATE kits
                    SET thumbnail_url=?, thumbnail_source_url=?, thumbnail_fetched_at=?
                    WHERE id=?
                    """,
                    (local_url, candidate.url, fetched_at, kit["id"]),
                )
                db.commit()
                updated += 1
                print(f"  saved {local_url} ({candidate.reason}, score {candidate.score})")
            except Exception as error:  # noqa: BLE001 - keep batch moving
                failed += 1
                print(f"  FAILED: {error}")
            if args.sleep and index < len(rows):
                time.sleep(args.sleep)

        print(f"Updated: {updated}; failed: {failed}")
        return 0 if failed == 0 else 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
