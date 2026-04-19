from __future__ import annotations

import csv
import hashlib
import math
import re
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional
import xml.etree.ElementTree as ET


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}

GREEN = "00FF00"
YELLOW = "FFFF00"


def sha1_file(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def ensure_extracted(pptx_path: Path, extract_dir: Path) -> None:
    if extract_dir.exists():
        return
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(pptx_path) as archive:
        archive.extractall(extract_dir)


def slide_number(path: Path) -> int:
    match = re.search(r"(\d+)", path.stem)
    if not match:
        raise ValueError(f"Could not parse slide number from {path}")
    return int(match.group(1))


def crop_fraction(src_rect: Optional[ET.Element]) -> Dict[str, float]:
    if src_rect is None:
        return {"l": 0.0, "r": 0.0, "t": 0.0, "b": 0.0}
    return {
        key: int(src_rect.attrib.get(key, "0")) / 100000.0
        for key in ("l", "r", "t", "b")
    }


def shape_box(xfrm: Optional[ET.Element]) -> Dict[str, int]:
    if xfrm is None:
        return {"x": 0, "y": 0, "cx": 0, "cy": 0}
    off = xfrm.find("./a:off", NS)
    ext = xfrm.find("./a:ext", NS)
    return {
        "x": int(off.attrib["x"]) if off is not None else 0,
        "y": int(off.attrib["y"]) if off is not None else 0,
        "cx": int(ext.attrib["cx"]) if ext is not None else 0,
        "cy": int(ext.attrib["cy"]) if ext is not None else 0,
    }


def normalize_title(raw_title: str) -> str:
    if not raw_title:
        return ""
    return re.sub(r"\s*Date:.*$", "", raw_title).strip()


def label_status_from_line_color(line_color: str) -> str:
    color = (line_color or "").upper()
    if color == GREEN:
        return "identified_in_this_image"
    if color == YELLOW:
        return "identified_elsewhere"
    return "other_or_unstyled"


def load_timeline_manifest(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    rows: Dict[str, Dict[str, str]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = row.get("file") or row.get("filename") or row.get("media_filename")
            if key:
                rows[key] = row
    return rows


def load_hash_crosswalk(media_dir: Path) -> Dict[str, str]:
    crosswalk: Dict[str, str] = {}
    for media_path in media_dir.glob("*"):
        if media_path.is_file():
            crosswalk[sha1_file(media_path)] = media_path.name
    return crosswalk


def read_slide_size(presentation_xml: Path) -> Dict[str, int]:
    root = ET.parse(presentation_xml).getroot()
    size = root.find("./p:sldSz", NS)
    if size is None:
        raise ValueError("presentation.xml has no slide size")
    return {"cx": int(size.attrib["cx"]), "cy": int(size.attrib["cy"])}


def picture_sort_key(picture: Dict[str, object]) -> tuple:
    return (0 if not picture["crop_any"] else 1, -int(picture["area"]))


def choose_base_picture(pictures: List[Dict[str, object]]) -> Optional[Dict[str, object]]:
    if not pictures:
        return None
    groups: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for picture in pictures:
        groups[str(picture["media_name"])].append(picture)
    group_choices = [sorted(group, key=picture_sort_key)[0] for group in groups.values()]
    return max(group_choices, key=lambda item: int(item["area"]))


def assignment_score(label: Dict[str, object], picture: Dict[str, object]) -> tuple:
    center_x = float(label["x"]) + float(label["cx"]) / 2.0
    center_y = float(label["y"]) + float(label["cy"]) / 2.0
    pic_x = float(picture["x"])
    pic_y = float(picture["y"])
    pic_w = float(picture["cx"])
    pic_h = float(picture["cy"])
    inside = pic_x <= center_x <= pic_x + pic_w and pic_y <= center_y <= pic_y + pic_h
    if inside:
        return (0.0, -float(picture["area"]))
    dx = 0.0 if pic_x <= center_x <= pic_x + pic_w else min(
        abs(center_x - pic_x),
        abs(center_x - (pic_x + pic_w)),
    )
    dy = 0.0 if pic_y <= center_y <= pic_y + pic_h else min(
        abs(center_y - pic_y),
        abs(center_y - (pic_y + pic_h)),
    )
    return (math.hypot(dx, dy), -float(picture["area"]))


def mapping_quality(
    assigned_picture: Optional[Dict[str, object]],
    base_picture: Optional[Dict[str, object]],
    unique_media_count: int,
) -> str:
    if not assigned_picture:
        return "unmapped"
    if assigned_picture.get("old_media_name"):
        return "high_exact_reused_image"
    if assigned_picture.get("media_name") == (base_picture or {}).get("media_name"):
        return "medium_base_image_only"
    if unique_media_count == 1:
        return "medium_same_slide_reuse_only"
    return "low_multi_media_slide"


def parse_rel_targets(rel_path: Path) -> Dict[str, str]:
    if not rel_path.exists():
        return {}
    root = ET.parse(rel_path).getroot()
    result: Dict[str, str] = {}
    for rel in root.findall(".//pr:Relationship", NS):
        result[rel.attrib["Id"]] = rel.attrib["Target"]
    return result


def iter_text_shapes(slide_root: ET.Element) -> Iterable[Dict[str, object]]:
    for shape in slide_root.findall(".//p:sp", NS):
        texts = [
            node.text.strip()
            for node in shape.findall(".//a:t", NS)
            if node.text and node.text.strip()
        ]
        if not texts:
            continue
        xfrm = shape.find("./p:spPr/a:xfrm", NS)
        box = shape_box(xfrm)
        line_color = ""
        sppr = shape.find("./p:spPr", NS)
        if sppr is not None:
            line = sppr.find("./a:ln", NS)
            if line is not None:
                solid = line.find("./a:solidFill", NS)
                if solid is not None:
                    srgb = solid.find("./a:srgbClr", NS)
                    scheme = solid.find("./a:schemeClr", NS)
                    if srgb is not None:
                        line_color = srgb.attrib.get("val", "")
                    elif scheme is not None:
                        line_color = f"scheme:{scheme.attrib.get('val', '')}"
        yield {
            "text": " ".join(texts),
            "line_color": line_color,
            **box,
        }


def parse_slide(
    slide_xml: Path,
    kit_media_dir: Path,
    old_hash_crosswalk: Dict[str, str],
    timeline_manifest: Dict[str, Dict[str, str]],
) -> Dict[str, object]:
    slide_root = ET.parse(slide_xml).getroot()
    rel_targets = parse_rel_targets(slide_xml.parent / "_rels" / f"{slide_xml.name}.rels")

    pictures: List[Dict[str, object]] = []
    for index, picture in enumerate(slide_root.findall(".//p:pic", NS), start=1):
        blip = picture.find(".//a:blip", NS)
        rel_id = blip.attrib.get(f"{{{NS['r']}}}embed") if blip is not None else None
        target = rel_targets.get(rel_id or "")
        media_name = Path(target).name if target else ""
        media_path = kit_media_dir / media_name if media_name else None
        old_media_name = ""
        if media_path and media_path.exists():
            old_media_name = old_hash_crosswalk.get(sha1_file(media_path), "")
        manifest_row = timeline_manifest.get(old_media_name, {})
        xfrm = picture.find("./p:spPr/a:xfrm", NS)
        box = shape_box(xfrm)
        crop = crop_fraction(picture.find(".//a:srcRect", NS))
        crop_any = any(value for value in crop.values())
        pictures.append(
            {
                "picture_index": index,
                "media_name": media_name,
                "old_media_name": old_media_name,
                "crop": crop,
                "crop_any": crop_any,
                "area": box["cx"] * box["cy"],
                "visible_subject": manifest_row.get("visible_subject", ""),
                "likely_model_or_scene": manifest_row.get("likely_model_or_scene", ""),
                **box,
            }
        )

    raw_texts = list(iter_text_shapes(slide_root))
    title_shape = next(
        (item for item in raw_texts if "Date:" in str(item["text"]) and "Source:" in str(item["text"])),
        None,
    )
    labels = [
        item
        for item in raw_texts
        if item is not title_shape and not str(item["text"]).startswith("Readme ")
    ]
    base_picture = choose_base_picture(pictures)
    same_media_reuse = len({pic["media_name"] for pic in pictures}) < len(pictures) if pictures else False

    return {
        "slide": slide_number(slide_xml),
        "slide_title": str(title_shape["text"]) if title_shape else "",
        "slide_key": normalize_title(str(title_shape["text"])) if title_shape else "",
        "pictures": pictures,
        "labels": labels,
        "base_picture": base_picture,
        "same_media_reuse": same_media_reuse,
    }


def build_rows(research_dir: Path) -> Dict[str, List[Dict[str, object]]]:
    kit_pptx = research_dir / "Kit_images.pptx"
    old_pptx = research_dir / "ILM75-77_timeline_.pptx"
    kit_extract = research_dir / "_kit_images_extract"
    old_extract = research_dir / "_pptx_extract"
    ensure_extracted(kit_pptx, kit_extract)
    ensure_extracted(old_pptx, old_extract)

    old_hash_crosswalk = load_hash_crosswalk(old_extract / "ppt" / "media")
    timeline_manifest = load_timeline_manifest(research_dir / "anh_pptx_image_manifest.csv")
    slide_size = read_slide_size(kit_extract / "ppt" / "presentation.xml")

    slides = sorted((kit_extract / "ppt" / "slides").glob("slide*.xml"), key=slide_number)
    slide_rows: List[Dict[str, object]] = []
    label_rows: List[Dict[str, object]] = []
    media_rows: Dict[str, Dict[str, object]] = {}

    for slide_xml in slides:
        parsed = parse_slide(slide_xml, kit_extract / "ppt" / "media", old_hash_crosswalk, timeline_manifest)
        base_picture = parsed["base_picture"]
        pictures = parsed["pictures"]
        labels = parsed["labels"]

        status_counts = Counter(label_status_from_line_color(str(label["line_color"])) for label in labels)
        slide_rows.append(
            {
                "slide": parsed["slide"],
                "slide_key": parsed["slide_key"],
                "slide_title": parsed["slide_title"],
                "picture_count": len(pictures),
                "unique_media_count": len({pic["media_name"] for pic in pictures}),
                "same_media_reuse": "yes" if parsed["same_media_reuse"] else "no",
                "exact_timeline_match": "yes" if any(pic["old_media_name"] for pic in pictures) else "no",
                "base_media": base_picture["media_name"] if base_picture else "",
                "base_timeline_media": base_picture["old_media_name"] if base_picture else "",
                "base_subject": base_picture["visible_subject"] if base_picture else "",
                "base_scene": base_picture["likely_model_or_scene"] if base_picture else "",
                "green_labels": status_counts["identified_in_this_image"],
                "yellow_labels": status_counts["identified_elsewhere"],
                "other_labels": status_counts["other_or_unstyled"],
            }
        )

        for picture in pictures:
            row = media_rows.setdefault(
                str(picture["media_name"]),
                {
                    "kit_media": picture["media_name"],
                    "timeline_media": picture["old_media_name"],
                    "timeline_subject": picture["visible_subject"],
                    "timeline_scene": picture["likely_model_or_scene"],
                    "referenced_by_slides": set(),
                    "label_total": 0,
                    "base_slide_count": 0,
                },
            )
            row["referenced_by_slides"].add(parsed["slide"])
            if base_picture and picture["media_name"] == base_picture["media_name"]:
                row["base_slide_count"] += 1

        for label in labels:
            assigned_picture = min(pictures, key=lambda pic: assignment_score(label, pic)) if pictures else None
            center_x = float(label["x"]) + float(label["cx"]) / 2.0
            center_y = float(label["y"]) + float(label["cy"]) / 2.0

            x_norm = ""
            y_norm = ""
            projected_x = ""
            projected_y = ""
            if assigned_picture and assigned_picture["cx"] and assigned_picture["cy"]:
                rel_x = (center_x - float(assigned_picture["x"])) / float(assigned_picture["cx"])
                rel_y = (center_y - float(assigned_picture["y"])) / float(assigned_picture["cy"])
                crop = assigned_picture["crop"]
                proj_x = crop["l"] + rel_x * (1.0 - crop["l"] - crop["r"])
                proj_y = crop["t"] + rel_y * (1.0 - crop["t"] - crop["b"])
                x_norm = f"{rel_x:.4f}"
                y_norm = f"{rel_y:.4f}"
                projected_x = f"{proj_x:.4f}"
                projected_y = f"{proj_y:.4f}"

            if assigned_picture:
                media_rows[str(assigned_picture["media_name"])]["label_total"] += 1

            label_rows.append(
                {
                    "slide": parsed["slide"],
                    "slide_key": parsed["slide_key"],
                    "slide_title": parsed["slide_title"],
                    "label_text": label["text"],
                    "label_status": label_status_from_line_color(str(label["line_color"])),
                    "line_color": label["line_color"],
                    "assigned_picture_index": assigned_picture["picture_index"] if assigned_picture else "",
                    "assigned_media": assigned_picture["media_name"] if assigned_picture else "",
                    "assigned_timeline_media": assigned_picture["old_media_name"] if assigned_picture else "",
                    "base_media": base_picture["media_name"] if base_picture else "",
                    "base_timeline_media": base_picture["old_media_name"] if base_picture else "",
                    "base_subject": base_picture["visible_subject"] if base_picture else "",
                    "base_scene": base_picture["likely_model_or_scene"] if base_picture else "",
                    "slide_same_media_reuse": "yes" if parsed["same_media_reuse"] else "no",
                    "mapping_quality": mapping_quality(
                        assigned_picture,
                        base_picture,
                        len({pic["media_name"] for pic in pictures}),
                    ),
                    "x_norm_in_assigned": x_norm,
                    "y_norm_in_assigned": y_norm,
                    "projected_x_in_original": projected_x,
                    "projected_y_in_original": projected_y,
                    "slide_x_norm": f"{center_x / slide_size['cx']:.4f}",
                    "slide_y_norm": f"{center_y / slide_size['cy']:.4f}",
                }
            )

    media_output: List[Dict[str, object]] = []
    for row in media_rows.values():
        media_output.append(
            {
                "kit_media": row["kit_media"],
                "timeline_media": row["timeline_media"],
                "timeline_subject": row["timeline_subject"],
                "timeline_scene": row["timeline_scene"],
                "referenced_by_slides": ",".join(str(num) for num in sorted(row["referenced_by_slides"])),
                "label_total": row["label_total"],
                "base_slide_count": row["base_slide_count"],
            }
        )

    slide_rows.sort(key=lambda item: int(item["slide"]))
    label_rows.sort(key=lambda item: (int(item["slide"]), str(item["label_text"])))
    media_output.sort(key=lambda item: str(item["kit_media"]))
    return {"slides": slide_rows, "labels": label_rows, "media": media_output}


def write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_report(slide_rows: List[Dict[str, object]], label_rows: List[Dict[str, object]]) -> str:
    exact_slides = sum(1 for row in slide_rows if row["exact_timeline_match"] == "yes")
    reuse_slides = sum(1 for row in slide_rows if row["same_media_reuse"] == "yes")
    green_labels = sum(1 for row in label_rows if row["label_status"] == "identified_in_this_image")
    yellow_labels = sum(1 for row in label_rows if row["label_status"] == "identified_elsewhere")
    high_quality = sum(1 for row in label_rows if row["mapping_quality"] == "high_exact_reused_image")
    unmatched_slides = [row for row in slide_rows if row["exact_timeline_match"] == "no" and int(row["picture_count"]) > 0]
    top_slides = sorted(
        slide_rows,
        key=lambda row: (int(row["green_labels"]) + int(row["yellow_labels"])),
        reverse=True,
    )[:8]

    lines = [
        "# Kit Images Overlay Extraction",
        "",
        "This pass extracts kit-name overlays from `Kit_images.pptx`, keeps the green/yellow label distinction from the deck, and cross-matches reused embedded photos against the earlier `ILM75-77_timeline_.pptx` media set.",
        "",
        "## Summary",
        "",
        f"- Slides parsed: `{len(slide_rows)}`",
        f"- Overlay labels extracted: `{len(label_rows)}`",
        f"- Green labels (`identified_in_this_image`): `{green_labels}`",
        f"- Yellow labels (`identified_elsewhere`): `{yellow_labels}`",
        f"- Slides with an exact reused timeline image: `{exact_slides}` of `{len(slide_rows)}`",
        f"- Slides reusing the same embedded image for full view plus zoom crop: `{reuse_slides}` of `{len(slide_rows)}`",
        f"- Labels mapped with high-confidence exact reused-image linkage: `{high_quality}`",
        "",
        "## Notes",
        "",
        "- Text color was not the useful signal here; the slide shape line color carries the green/yellow meaning.",
        "- `projected_x_in_original` and `projected_y_in_original` are normalized coordinates in the underlying original image space.",
        "- When a slide reuses the same embedded photo for both the main image and a zoom crop, those projected coordinates are especially useful because they land back on the larger original cleanly.",
        "- Some slides contain media that are not exact file matches to the earlier timeline deck. Those remain useful locally, but their cross-deck linkage is lower confidence until image-level matching is added.",
        "",
        "## Top Overlay-Dense Slides",
        "",
    ]

    for row in top_slides:
        lines.append(
            f"- Slide `{row['slide']}` `{row['slide_key'] or row['slide_title']}`: "
            f"`{row['green_labels']}` green, `{row['yellow_labels']}` yellow, "
            f"base media `{row['base_media']}` -> timeline `{row['base_timeline_media'] or 'none'}`"
        )

    lines.extend(["", "## Unmatched Slide Bases", ""])
    for row in unmatched_slides[:12]:
        lines.append(
            f"- Slide `{row['slide']}` `{row['slide_key'] or row['slide_title']}` uses base media `{row['base_media']}` with no exact cross-deck file match yet"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    research_dir = repo_root / "export_text" / "research"
    rows = build_rows(research_dir)

    write_csv(research_dir / "kit_images_slide_manifest.csv", rows["slides"])
    write_csv(research_dir / "kit_images_overlay_labels.csv", rows["labels"])
    write_csv(research_dir / "kit_images_media_crosswalk.csv", rows["media"])
    report = build_report(rows["slides"], rows["labels"])
    (research_dir / "kit_images_overlay_report.md").write_text(report, encoding="utf-8")

    print("Wrote:")
    print(research_dir / "kit_images_slide_manifest.csv")
    print(research_dir / "kit_images_overlay_labels.csv")
    print(research_dir / "kit_images_media_crosswalk.csv")
    print(research_dir / "kit_images_overlay_report.md")


if __name__ == "__main__":
    main()
