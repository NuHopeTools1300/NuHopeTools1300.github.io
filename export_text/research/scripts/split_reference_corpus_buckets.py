#!/usr/bin/env python3
"""
Split the canonical local reference corpus into staging buckets.

Current policy:
  - safe_to_stage:
      source platform is known
      source confidence is high or medium
      content kind is not historical_reference
      content kind is not render_or_cg
  - needs_review:
      anything else

This keeps well-attributed auction/forum/social/personal-archive material easy
to stage while pushing historical compilations and unknown-origin material into
review for better source attribution before DB ingest.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CORPUS_DIR = REPO_ROOT / "export_text" / "research" / "local_reference_corpus"
INPUT_CSV = CORPUS_DIR / "corpus_canonical_images.csv"
SAFE_CSV = CORPUS_DIR / "corpus_safe_to_stage.csv"
REVIEW_CSV = CORPUS_DIR / "corpus_needs_review.csv"
SUMMARY_JSON = CORPUS_DIR / "corpus_bucket_summary.json"
SUMMARY_MD = CORPUS_DIR / "corpus_bucket_summary.md"


def bucket_for_row(row: dict[str, str]) -> tuple[str, str]:
    source_platform = row.get("source_platform", "")
    source_confidence = row.get("source_confidence", "")
    content_kind = row.get("content_kind", "")

    if source_platform in {"", "unknown"}:
        return "needs_review", "unknown_source_platform"
    if source_confidence not in {"high", "medium"}:
        return "needs_review", "low_source_confidence"
    if content_kind == "historical_reference":
        return "needs_review", "historical_compilation"
    if content_kind == "render_or_cg":
        return "needs_review", "render_or_cg"
    return "safe_to_stage", "attributed_and_nonhistorical"


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main():
    rows = list(csv.DictReader(INPUT_CSV.open("r", encoding="utf-8", newline="")))
    if not rows:
        raise SystemExit("No rows found in corpus_canonical_images.csv")

    fieldnames = list(rows[0].keys()) + ["bucket", "bucket_reason"]
    safe_rows: list[dict[str, str]] = []
    review_rows: list[dict[str, str]] = []
    reasons = Counter()
    source_by_bucket: dict[str, Counter[str]] = {
        "safe_to_stage": Counter(),
        "needs_review": Counter(),
    }

    for row in rows:
        bucket, reason = bucket_for_row(row)
        enriched = dict(row)
        enriched["bucket"] = bucket
        enriched["bucket_reason"] = reason
        reasons[(bucket, reason)] += 1
        source_label = f"{row.get('source_platform','')}:{row.get('source_collection','')}".rstrip(":")
        source_by_bucket[bucket][source_label or "unknown"] += 1
        if bucket == "safe_to_stage":
            safe_rows.append(enriched)
        else:
            review_rows.append(enriched)

    safe_rows.sort(key=lambda r: (r["subject"], r["source_platform"], r["filename"].lower()))
    review_rows.sort(key=lambda r: (r["bucket_reason"], r["subject"], r["source_platform"], r["filename"].lower()))

    write_csv(SAFE_CSV, safe_rows, fieldnames)
    write_csv(REVIEW_CSV, review_rows, fieldnames)

    summary = {
        "safe_to_stage": len(safe_rows),
        "needs_review": len(review_rows),
        "reasons": {f"{bucket}:{reason}": count for (bucket, reason), count in reasons.items()},
        "top_safe_sources": dict(source_by_bucket["safe_to_stage"].most_common(20)),
        "top_review_sources": dict(source_by_bucket["needs_review"].most_common(20)),
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md_lines = [
        "# Corpus Bucket Summary",
        "",
        "## Counts",
        "",
        f"- `safe_to_stage`: `{len(safe_rows)}`",
        f"- `needs_review`: `{len(review_rows)}`",
        "",
        "## Reasons",
        "",
    ]
    for (bucket, reason), count in reasons.most_common():
        md_lines.append(f"- `{bucket}` / `{reason}`: `{count}`")

    md_lines.extend(["", "## Top Safe Sources", ""])
    for label, count in source_by_bucket["safe_to_stage"].most_common(20):
        md_lines.append(f"- `{label}`: `{count}`")

    md_lines.extend(["", "## Top Review Sources", ""])
    for label, count in source_by_bucket["needs_review"].most_common(20):
        md_lines.append(f"- `{label}`: `{count}`")

    SUMMARY_MD.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
