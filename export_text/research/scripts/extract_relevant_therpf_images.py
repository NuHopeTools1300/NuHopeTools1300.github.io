#!/usr/bin/env python3
"""
Extract a selective, deduplicated set of relevant therpf mirror images and
link them back to mirrored thread text exports.

This is intentionally conservative: it prefers ANH / Star Wars studio-scale
research threads and known model-research titles over "everything Star Wars".

Outputs under the chosen output directory:
  - thread_manifest.csv
  - image_manifest.csv
  - image_links.csv
  - summary.json
  - index.html
  - thread_pages/*.html
  - thread_texts/*.txt
  - images/<sha-prefix>/<sha>.<ext>

Typical usage:
    python extract_relevant_therpf_images.py
    python extract_relevant_therpf_images.py --tier all
    python extract_relevant_therpf_images.py --summary-only
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_WEBSITES_ROOT = Path(r"D:\Manuel\MillenniumFalcon\Websites")
DEFAULT_MIRROR_ROOT = DEFAULT_WEBSITES_ROOT / "therpf_mirror"
DEFAULT_TEXT_ROOT = DEFAULT_WEBSITES_ROOT / "export_text"
DEFAULT_DB_PATH = REPO_ROOT / "backend" / "data" / "ilm1300.db"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "export_text" / "research" / "therpf_relevant_images"
BASE_URL = "https://www.therpf.com"

GLOBAL_RESOURCE_KEYWORDS = {
    "kit scan",
    "kit scans",
    "parts map",
    "parts maps",
    "donor",
}

SPECIFIC_RESEARCH_KEYWORDS = {
    "a new hope",
    "episode iv",
    "episode 4",
    "anh",
    "photos of models built for star wars",
    "blue one",
    "blue 1",
    "red leader",
    "red five",
    "red 5",
    "gold leader",
    "gold two",
    "gold 2",
    "pyro",
    "cantwell",
    "5 foot",
    "five foot",
    "32 inch",
}

MODEL_KEYWORDS = {
    "millennium falcon",
    "falcon",
    "x wing",
    "x-wing",
    "y wing",
    "y-wing",
    "tie fighter",
    "tie-fighter",
    "tie advanced",
    "tie-advanced",
    "star destroyer",
    "blockade runner",
    "tantive",
    "corellian corvette",
    "death star",
    "turbo laser",
    "turbolaser",
    "escape pod",
    "sandcrawler",
    "landspeeder",
    "training remote",
    "crane",
    "silo",
    "hangar",
    "docking bay",
}

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tif", ".tiff"}
THREAD_ID_RE = re.compile(r"/forums/threads/[^/]+\.(\d+)/?$")
SAFE_TEXT_RE = re.compile(r'[\\/:*?"<>|]')
THREAD_PAGE_RE = re.compile(r"_(page-\d+|latest)$")


@dataclass
class ThreadRecord:
    thread_id: str
    url: str
    title: str
    safe_title: str
    tier: str
    score: int
    reasons: list[str]
    html_files: list[Path] = field(default_factory=list)
    text_source_path: Path | None = None
    text_copy_path: Path | None = None
    page_path: Path | None = None
    image_link_count: int = 0
    unique_image_count: int = 0
    missing_image_count: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract relevant therpf mirror images into a browsable, deduplicated corpus.")
    parser.add_argument("--websites-root", type=Path, default=DEFAULT_WEBSITES_ROOT, help=f"Root folder containing mirror scripts and exports (default: {DEFAULT_WEBSITES_ROOT})")
    parser.add_argument("--mirror-root", type=Path, default=DEFAULT_MIRROR_ROOT, help=f"Mirror root containing threads/images/index (default: {DEFAULT_MIRROR_ROOT})")
    parser.add_argument("--text-root", type=Path, default=DEFAULT_TEXT_ROOT, help=f"Folder containing per-thread exported text files (default: {DEFAULT_TEXT_ROOT})")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH, help=f"SQLite database used to seed model keywords (default: {DEFAULT_DB_PATH})")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help=f"Output folder for manifests, copied text, copied images, and gallery pages (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--tier", choices=("strong", "candidate", "all"), default="strong", help="Which relevance tier to extract. strong is the safest default.")
    parser.add_argument("--summary-only", action="store_true", help="Analyze and report counts without copying files or writing the gallery.")
    parser.add_argument("--limit", type=int, default=0, help="Optional cap on number of selected threads, for testing.")
    return parser.parse_args()


def load_external_module(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = value.lower()
    value = value.replace("_", " ").replace("-", " ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def keyword_matches(keyword: str, normalized_text: str) -> bool:
    normalized_keyword = normalize_text(keyword)
    if not normalized_keyword:
        return False
    pattern = rf"(?<![a-z0-9]){re.escape(normalized_keyword)}(?![a-z0-9])"
    return re.search(pattern, normalized_text) is not None


def safe_title_filename(title: str) -> str:
    cleaned = SAFE_TEXT_RE.sub("_", title)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = cleaned[:180] or "thread"
    return f"{cleaned}.txt"


def build_text_index(text_root: Path) -> dict[str, Path]:
    index: dict[str, Path] = {}
    with os.scandir(text_root) as it:
        for entry in it:
            if not entry.is_file() or not entry.name.lower().endswith(".txt"):
                continue
            stem = Path(entry.name).stem
            key = normalize_text(stem)
            index.setdefault(key, Path(entry.path))
    return index


def resolve_text_export_path(title: str, text_root: Path, text_index: dict[str, Path]) -> Path | None:
    direct = text_root / safe_title_filename(title)
    if direct.exists():
        return direct
    return text_index.get(normalize_text(title))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def load_model_keywords(db_path: Path) -> set[str]:
    keywords = set(MODEL_KEYWORDS)
    if not db_path.exists():
        return keywords

    con = sqlite3.connect(str(db_path))
    try:
        cur = con.cursor()
        for (name,) in cur.execute("SELECT name FROM models ORDER BY name"):
            if not name:
                continue
            lowered = normalize_text(re.sub(r"\([^)]*\)", "", name))
            if lowered:
                keywords.add(lowered)
                keywords.add(lowered.replace(" tie ", " tie-"))
                keywords.add(lowered.replace(" x wing", " x-wing"))
                keywords.add(lowered.replace(" y wing", " y-wing"))
        return {kw.strip() for kw in keywords if kw.strip()}
    finally:
        con.close()


def resolve_title(url: str, stored_title: str, threads_dir: Path, title_from_html, slug_from_url, safe_filename) -> str:
    if stored_title and stored_title.strip():
        return stored_title.strip()

    html_path = threads_dir / safe_filename(url)
    if html_path.exists():
        recovered = title_from_html(str(html_path))
        if recovered:
            return recovered

    return slug_from_url(url)


def thread_id_from_url(url: str) -> str:
    match = THREAD_ID_RE.search(url)
    return match.group(1) if match else ""


def score_thread(title: str, is_star_wars_relevant, model_keywords: set[str]) -> tuple[str, int, list[str]]:
    title_norm = normalize_text(title)
    reasons: list[str] = []
    score = 0

    sw_relevant = bool(is_star_wars_relevant(title))
    model_hits = sorted({kw for kw in model_keywords if keyword_matches(kw, title_norm)})
    global_resource_hits = sorted({kw for kw in GLOBAL_RESOURCE_KEYWORDS if keyword_matches(kw, title_norm)})
    specific_hits = sorted({kw for kw in SPECIFIC_RESEARCH_KEYWORDS if keyword_matches(kw, title_norm)})

    if sw_relevant:
        score += 2
        reasons.append("sw_filter")
    if model_hits:
        score += 3
        reasons.append(f"model:{model_hits[0]}")
    if global_resource_hits:
        score += 2
        reasons.append(f"resource:{global_resource_hits[0]}")
    if specific_hits and (sw_relevant or model_hits):
        score += 2
        reasons.append(f"research:{specific_hits[0]}")

    if model_hits or global_resource_hits or (specific_hits and (sw_relevant or model_hits)):
        return "strong", score, reasons
    if sw_relevant:
        return "candidate", score, reasons
    return "exclude", score, reasons


def choose_threads(progress_data: dict[str, Any], threads_dir: Path, tier_filter: str, limit: int, is_star_wars_relevant, model_keywords: set[str], title_from_html, slug_from_url, safe_filename) -> list[ThreadRecord]:
    selected: list[ThreadRecord] = []
    thread_urls = progress_data.get("thread_urls", [])

    for item in thread_urls:
        if isinstance(item, str):
            url = item
            stored_title = ""
        else:
            url = item[0]
            stored_title = item[1] if len(item) > 1 else ""

        title = resolve_title(url, stored_title, threads_dir, title_from_html, slug_from_url, safe_filename)
        tier, score, reasons = score_thread(title, is_star_wars_relevant, model_keywords)
        if tier == "exclude":
            continue
        if tier_filter != "all" and tier != tier_filter:
            continue

        thread_id = thread_id_from_url(url) or "unknown"
        selected.append(
            ThreadRecord(
                thread_id=thread_id,
                url=url,
                title=title,
                safe_title=safe_title_filename(title).rsplit(".", 1)[0],
                tier=tier,
                score=score,
                reasons=reasons,
            )
        )
        if limit and len(selected) >= limit:
            break

    selected.sort(key=lambda record: (-record.score, record.title.lower(), record.thread_id))
    return selected


def thread_page_sort_key(path: Path) -> tuple[int, int, str]:
    name = path.name
    if name.endswith("_latest.html"):
        return (2, 0, name)
    match = re.search(r"_page-(\d+)\.html$", name)
    if match:
        return (1, int(match.group(1)), name)
    return (0, 1, name)


def build_thread_html_index(threads_dir: Path) -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = defaultdict(list)
    with os.scandir(threads_dir) as it:
        for entry in it:
            if not entry.is_file() or not entry.name.endswith(".html"):
                continue
            base_stem = THREAD_PAGE_RE.sub("", Path(entry.name).stem)
            index[base_stem].append(Path(entry.path))

    for paths in index.values():
        paths.sort(key=thread_page_sort_key)
    return dict(index)


def files_for_thread(url: str, safe_filename, html_index: dict[str, list[Path]]) -> list[Path]:
    base_stem = Path(safe_filename(url)).stem
    return list(html_index.get(base_stem, []))


def extract_post_images(html_path: Path, image_local_path) -> list[dict[str, Any]]:
    with html_path.open("r", encoding="utf-8", errors="replace") as handle:
        soup = BeautifulSoup(handle.read(), "html.parser")

    records: list[dict[str, Any]] = []
    for article in soup.select("article[data-content]"):
        post_id = article.get("data-content", "")
        num_el = article.select_one(".message-attribution-opposite a[href*='post-']")
        post_num = num_el.get_text(strip=True) if num_el else ""
        author_el = article.select_one(".message-name .username, .message-name a")
        author = author_el.get_text(strip=True) if author_el else "Unknown"
        time_el = article.select_one("time.u-dt, time[datetime]")
        post_date = ""
        if time_el:
            post_date = time_el.get("title") or time_el.get("datetime") or time_el.get_text(strip=True)

        body_el = article.select_one(".message-body .bbWrapper, .message-userContent")
        if body_el is None:
            continue

        seen_srcs: set[str] = set()
        image_index = 0
        for img in body_el.select("img"):
            src = (img.get("data-src") or img.get("src") or "").strip()
            if not src or src.startswith("data:"):
                continue
            try:
                src = urljoin(BASE_URL, src)
            except ValueError:
                continue
            ext = Path(src.split("?", 1)[0]).suffix.lower()
            if ext and ext not in IMAGE_EXTENSIONS:
                continue
            if src in seen_srcs:
                continue
            seen_srcs.add(src)
            image_index += 1
            local_path = Path(image_local_path(src, str(html_path.parents[1] / "images")))
            records.append(
                {
                    "page_file": html_path.name,
                    "post_id": post_id,
                    "post_num": post_num,
                    "author": author,
                    "date": post_date,
                    "image_index": image_index,
                    "image_url": src,
                    "image_local_path": local_path,
                }
            )
    return records


def ensure_clean_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def copy_text_export(source_path: Path, destination_dir: Path) -> Path:
    ensure_clean_dir(destination_dir)
    destination_path = destination_dir / source_path.name
    if not destination_path.exists():
        shutil.copy2(source_path, destination_path)
    return destination_path


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]):
    ensure_clean_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def build_thread_page(thread: ThreadRecord, link_rows: list[dict[str, Any]], output_dir: Path) -> Path:
    pages_dir = output_dir / "thread_pages"
    ensure_clean_dir(pages_dir)
    page_name = f"{thread.thread_id}_{thread.safe_title[:80]}.html"
    page_path = pages_dir / page_name

    image_cards: list[str] = []
    for row in link_rows:
        image_href = html.escape(row["copied_image_rel"])
        label = html.escape(row["image_label"])
        meta = f"Post {html.escape(row['post_num'] or row['post_id'] or '?')} · {html.escape(row['author'] or 'Unknown')}"
        if row["date"]:
            meta += f" · {html.escape(row['date'])}"
        image_cards.append(
            f"""
            <figure class="card">
              <a href="../{image_href}"><img loading="lazy" src="../{image_href}" alt="{label}"></a>
              <figcaption>
                <div class="label">{label}</div>
                <div class="meta">{meta}</div>
              </figcaption>
            </figure>
            """
        )

    text_link = ""
    if thread.text_copy_path is not None:
        text_rel = thread.text_copy_path.relative_to(output_dir).as_posix()
        text_link = f'<a class="pill" href="../{html.escape(text_rel)}">Thread text</a>'

    page_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(thread.title)}</title>
  <style>
    :root {{
      --bg: #0f1720;
      --panel: #1b2633;
      --panel-2: #263447;
      --line: #3e536c;
      --text: #e6edf5;
      --muted: #adc0d4;
      --accent: #f0c75e;
      --accent-2: #8bb8ff;
    }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background: radial-gradient(circle at top, #213348 0, var(--bg) 58%);
      color: var(--text);
    }}
    main {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 28px;
    }}
    .top {{
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      align-items: center;
      margin-bottom: 18px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 2rem;
      line-height: 1.1;
    }}
    .meta {{
      color: var(--muted);
      margin-bottom: 18px;
    }}
    .pill {{
      display: inline-block;
      padding: 8px 12px;
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--text);
      text-decoration: none;
      background: rgba(255,255,255,0.04);
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: 16px;
    }}
    .card {{
      margin: 0;
      background: rgba(255,255,255,0.04);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 18px;
      overflow: hidden;
    }}
    .card img {{
      width: 100%;
      height: 220px;
      object-fit: cover;
      display: block;
      background: #0a1118;
    }}
    .card figcaption {{
      padding: 12px;
    }}
    .label {{
      color: var(--accent);
      font-size: 0.95rem;
      margin-bottom: 4px;
    }}
    .meta {{
      color: var(--muted);
      font-size: 0.88rem;
    }}
    a {{
      color: var(--accent-2);
    }}
  </style>
</head>
<body>
  <main>
    <div class="top">
      <a class="pill" href="../index.html">Back to index</a>
      {text_link}
      <a class="pill" href="{html.escape(thread.url)}">Original thread URL</a>
    </div>
    <h1>{html.escape(thread.title)}</h1>
    <div class="meta">Tier: {html.escape(thread.tier)} · Score: {thread.score} · Reasons: {html.escape(", ".join(thread.reasons))}</div>
    <div class="grid">
      {''.join(image_cards) if image_cards else '<p>No mirrored images were available for this thread.</p>'}
    </div>
  </main>
</body>
</html>
"""

    page_path.write_text(page_html, encoding="utf-8")
    return page_path


def build_index_page(threads: list[ThreadRecord], output_dir: Path):
    rows: list[str] = []
    for thread in threads:
        page_rel = thread.page_path.relative_to(output_dir).as_posix() if thread.page_path else ""
        text_rel = thread.text_copy_path.relative_to(output_dir).as_posix() if thread.text_copy_path else ""
        text_link = f'<a href="{html.escape(text_rel)}">text</a>' if text_rel else "missing"
        rows.append(
            f"""
            <tr>
              <td><a href="{html.escape(page_rel)}">{html.escape(thread.title)}</a></td>
              <td>{html.escape(thread.thread_id)}</td>
              <td>{html.escape(thread.tier)}</td>
              <td>{thread.score}</td>
              <td>{thread.image_link_count}</td>
              <td>{thread.unique_image_count}</td>
              <td>{thread.missing_image_count}</td>
              <td>{html.escape(", ".join(thread.reasons))}</td>
              <td>{text_link}</td>
            </tr>
            """
        )

    page_html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Relevant therpf images</title>
  <style>
    :root {{
      --bg: #0b1118;
      --panel: #162230;
      --line: #30465f;
      --text: #e7edf4;
      --muted: #acc0d4;
      --accent: #f0c75e;
      --accent-2: #8cb5ff;
    }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background: linear-gradient(180deg, #152131 0, var(--bg) 320px);
      color: var(--text);
    }}
    main {{
      max-width: 1400px;
      margin: 0 auto;
      padding: 28px;
    }}
    h1 {{
      margin: 0 0 10px;
      font-size: 2.2rem;
    }}
    p {{
      color: var(--muted);
      max-width: 950px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 20px;
      background: rgba(255,255,255,0.03);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 18px;
      overflow: hidden;
    }}
    th, td {{
      padding: 12px 14px;
      border-bottom: 1px solid rgba(255,255,255,0.08);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--accent);
      font-weight: 600;
      background: rgba(255,255,255,0.03);
    }}
    tr:hover {{
      background: rgba(255,255,255,0.03);
    }}
    a {{
      color: var(--accent-2);
    }}
  </style>
</head>
<body>
  <main>
    <h1>Relevant therpf image corpus</h1>
    <p>This view is a selective extraction from the mirrored therpf Studio Scale archive. It keeps the relevant thread text nearby, deduplicates mirrored images by content hash, and groups the results by thread so the corpus stays browsable without dragging in the whole mirror.</p>
    <table>
      <thead>
        <tr>
          <th>Thread</th>
          <th>ID</th>
          <th>Tier</th>
          <th>Score</th>
          <th>Image links</th>
          <th>Unique images</th>
          <th>Missing</th>
          <th>Reasons</th>
          <th>Text</th>
        </tr>
      </thead>
      <tbody>
        {''.join(rows)}
      </tbody>
    </table>
  </main>
</body>
</html>
"""
    (output_dir / "index.html").write_text(page_html, encoding="utf-8")


def main():
    args = parse_args()
    websites_root = args.websites_root
    mirror_root = args.mirror_root
    text_root = args.text_root
    output_dir = args.output_dir

    mirror_utils = load_external_module("therpf_mirror_utils", websites_root / "mirror_utils.py")
    sw_filter = load_external_module("therpf_sw_filter", websites_root / "sw_filter.py")

    progress_path = mirror_root / "progress.json"
    threads_dir = mirror_root / "threads"
    images_dir = mirror_root / "images"
    if not progress_path.exists():
        raise FileNotFoundError(f"Missing progress file: {progress_path}")

    with progress_path.open("r", encoding="utf-8") as handle:
        progress_data = json.load(handle)

    model_keywords = load_model_keywords(args.db_path)
    html_index = build_thread_html_index(threads_dir)
    text_index = build_text_index(text_root)
    threads = choose_threads(
        progress_data=progress_data,
        threads_dir=threads_dir,
        tier_filter=args.tier,
        limit=args.limit,
        is_star_wars_relevant=sw_filter.is_star_wars_relevant,
        model_keywords=model_keywords,
        title_from_html=mirror_utils.title_from_html,
        slug_from_url=mirror_utils.slug_from_url,
        safe_filename=mirror_utils.safe_filename,
    )

    summary = {
        "websites_root": str(websites_root),
        "mirror_root": str(mirror_root),
        "text_root": str(text_root),
        "output_dir": str(output_dir),
        "tier": args.tier,
        "summary_only": args.summary_only,
        "selected_threads": len(threads),
    }

    if args.summary_only:
        print(json.dumps(summary, indent=2))
        return

    ensure_clean_dir(output_dir)
    ensure_clean_dir(output_dir / "images")
    ensure_clean_dir(output_dir / "thread_pages")
    ensure_clean_dir(output_dir / "thread_texts")

    image_manifest_rows: list[dict[str, Any]] = []
    image_link_rows: list[dict[str, Any]] = []
    thread_manifest_rows: list[dict[str, Any]] = []
    copied_by_hash: dict[str, dict[str, Any]] = {}
    thread_links_for_pages: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for thread in threads:
        thread.html_files = files_for_thread(thread.url, mirror_utils.safe_filename, html_index)
        resolved_text_path = resolve_text_export_path(thread.title, text_root, text_index)
        if resolved_text_path is not None and resolved_text_path.exists():
            thread.text_source_path = resolved_text_path
            thread.text_copy_path = copy_text_export(resolved_text_path, output_dir / "thread_texts")

        thread_unique_hashes: set[str] = set()
        for html_file in thread.html_files:
            for image_record in extract_post_images(html_file, mirror_utils.image_local_path):
                local_path: Path = image_record["image_local_path"]
                row_base = {
                    "thread_id": thread.thread_id,
                    "thread_title": thread.title,
                    "thread_url": thread.url,
                    "thread_tier": thread.tier,
                    "thread_score": thread.score,
                    "page_file": image_record["page_file"],
                    "post_id": image_record["post_id"],
                    "post_num": image_record["post_num"],
                    "author": image_record["author"],
                    "date": image_record["date"],
                    "image_index": image_record["image_index"],
                    "image_url": image_record["image_url"],
                    "mirror_local_path": str(local_path),
                    "mirror_local_exists": local_path.exists(),
                }

                if not local_path.exists():
                    thread.missing_image_count += 1
                    image_link_rows.append(
                        row_base
                        | {
                            "image_hash": "",
                            "copied_image_rel": "",
                            "image_label": Path(image_record["image_url"].split("?", 1)[0]).name,
                            "status": "missing",
                        }
                    )
                    continue

                image_hash = sha256_file(local_path)
                thread_unique_hashes.add(image_hash)
                suffix = local_path.suffix.lower() if local_path.suffix else ".jpg"
                copied_rel = Path("images") / image_hash[:2] / f"{image_hash}{suffix}"
                copied_abs = output_dir / copied_rel
                ensure_clean_dir(copied_abs.parent)
                if image_hash not in copied_by_hash:
                    if not copied_abs.exists():
                        shutil.copy2(local_path, copied_abs)
                    copied_by_hash[image_hash] = {
                        "image_hash": image_hash,
                        "original_filename": local_path.name,
                        "mirror_local_path": str(local_path),
                        "copied_image_rel": copied_rel.as_posix(),
                        "size_bytes": local_path.stat().st_size,
                        "suffix": suffix,
                        "first_image_url": image_record["image_url"],
                    }
                    image_manifest_rows.append(copied_by_hash[image_hash])

                link_row = row_base | {
                    "image_hash": image_hash,
                    "copied_image_rel": copied_rel.as_posix(),
                    "image_label": local_path.name,
                    "status": "copied",
                }
                image_link_rows.append(link_row)
                thread_links_for_pages[thread.thread_id].append(link_row)

        thread.image_link_count = sum(1 for row in image_link_rows if row["thread_id"] == thread.thread_id and row["status"] == "copied")
        thread.unique_image_count = len(thread_unique_hashes)
        thread.page_path = build_thread_page(thread, thread_links_for_pages[thread.thread_id], output_dir)
        thread_manifest_rows.append(
            {
                "thread_id": thread.thread_id,
                "thread_title": thread.title,
                "thread_url": thread.url,
                "tier": thread.tier,
                "score": thread.score,
                "reasons": "; ".join(thread.reasons),
                "html_file_count": len(thread.html_files),
                "image_link_count": thread.image_link_count,
                "unique_image_count": thread.unique_image_count,
                "missing_image_count": thread.missing_image_count,
                "text_source_path": str(thread.text_source_path) if thread.text_source_path else "",
                "text_copy_rel": thread.text_copy_path.relative_to(output_dir).as_posix() if thread.text_copy_path else "",
                "page_rel": thread.page_path.relative_to(output_dir).as_posix() if thread.page_path else "",
            }
        )

    build_index_page(threads, output_dir)

    write_csv(
        output_dir / "thread_manifest.csv",
        thread_manifest_rows,
        [
            "thread_id",
            "thread_title",
            "thread_url",
            "tier",
            "score",
            "reasons",
            "html_file_count",
            "image_link_count",
            "unique_image_count",
            "missing_image_count",
            "text_source_path",
            "text_copy_rel",
            "page_rel",
        ],
    )
    write_csv(
        output_dir / "image_manifest.csv",
        image_manifest_rows,
        [
            "image_hash",
            "original_filename",
            "mirror_local_path",
            "copied_image_rel",
            "size_bytes",
            "suffix",
            "first_image_url",
        ],
    )
    write_csv(
        output_dir / "image_links.csv",
        image_link_rows,
        [
            "thread_id",
            "thread_title",
            "thread_url",
            "thread_tier",
            "thread_score",
            "page_file",
            "post_id",
            "post_num",
            "author",
            "date",
            "image_index",
            "image_url",
            "mirror_local_path",
            "mirror_local_exists",
            "image_hash",
            "copied_image_rel",
            "image_label",
            "status",
        ],
    )

    summary = {
        **summary,
        "copied_unique_images": len(image_manifest_rows),
        "linked_images": sum(1 for row in image_link_rows if row["status"] == "copied"),
        "missing_images": sum(1 for row in image_link_rows if row["status"] == "missing"),
        "threads_with_text_copies": sum(1 for thread in threads if thread.text_copy_path is not None),
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
