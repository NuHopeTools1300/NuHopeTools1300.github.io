"""
Import part reference images from PartList_private.zip into the DB.

Usage (dry run):
    python tools/import_partlist_images.py --dry-run

Usage (import):
    python tools/import_partlist_images.py

Reads PartList_private.zip from the repo root.
Extracts matched images to backend/data/part_images/.
Inserts part_files records with url='/api/part_images/<filename>',
file_type='photo', source='PartList_private'.

Only imports where BOTH kit AND part are matched in the DB.
Skips rows already present (idempotent by url).
"""

import argparse
import re
import sqlite3
import sys
import zipfile
from html.parser import HTMLParser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ZIP_PATH  = REPO_ROOT / 'PartList_private.zip'
DB_PATH   = REPO_ROOT / 'backend' / 'data' / 'ilm1300.db'
IMG_DIR   = REPO_ROOT / 'backend' / 'data' / 'part_images'
FILE_TYPE = 'reference'
SOURCE    = 'PartList_private'


# ── HTML parser ───────────────────────────────────────────────────────────────

class PartListParser(HTMLParser):
    """Parses PartList HTML into sections of {heading, parts:[{label, imgs}]}."""

    def __init__(self):
        super().__init__()
        self._in_h = False
        self._buf = ''
        self.sections = []
        self._cur_section = None
        self._cur_part = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('h5', 'h4'):
            self._in_h = True
            self._buf = ''
        elif tag == 'img':
            src = attrs.get('src', '')
            if src:
                if self._cur_part is not None:
                    self._cur_part['imgs'].append(src)
                elif self._cur_section and self._cur_section['parts']:
                    self._cur_section['parts'][-1]['imgs'].append(src)

    def handle_endtag(self, tag):
        if tag in ('h5', 'h4'):
            self._in_h = False
            heading = self._buf.strip()
            if heading:
                self._cur_section = {'heading': heading, 'parts': []}
                self.sections.append(self._cur_section)
                self._cur_part = None

    def handle_data(self, data):
        if self._in_h:
            self._buf += data
        else:
            t = data.strip()
            if self._cur_section and re.match(r'^[\w\-\.]+:$', t) and len(t) < 30:
                self._cur_part = {'label': t, 'imgs': []}
                self._cur_section['parts'].append(self._cur_part)


# ── Matching helpers ──────────────────────────────────────────────────────────

def _clean(s):
    return re.sub(r'\s+', ' ', s.replace('\xa0', ' ')).strip()

def _norm(s):
    return re.sub(r'[\s\-_/\.]', '', str(s)).lower()

_HDG = re.compile(r'^([\w\-\.]+)\s+(.+?)\s+(1/[\w\.]+)\s+(.+?)(?:\s+([\w\-/\.]+))?$')


def build_kit_indexes(db):
    serial_idx = {}
    name_idx = {}
    for row in db.execute("SELECT id, brand, scale, name, serial_number FROM kits"):
        k = dict(row)
        if k['serial_number']:
            serial_idx[_norm(k['serial_number'])] = k
        name_idx[(_norm(k['brand']), _norm(k['scale']), _norm(k['name']))] = k
    return serial_idx, name_idx


def match_kit(heading, serial_idx, name_idx):
    h = _clean(heading)
    m = _HDG.match(h)
    if not m:
        return None
    brand, scale, name_serial = m.group(2), m.group(3), m.group(4)
    serial = m.group(5)
    if serial and _norm(serial) in serial_idx:
        return serial_idx[_norm(serial)]
    tokens = name_serial.split()
    if tokens and _norm(tokens[-1]) in serial_idx:
        return serial_idx[_norm(tokens[-1])]
    name_part = ' '.join(tokens) if not serial else name_serial
    key = (_norm(brand), _norm(scale), _norm(name_part))
    return name_idx.get(key)


def get_parts_index(db, kit_id):
    idx = {}
    for row in db.execute("SELECT id, part_number FROM parts WHERE kit_id=?", (kit_id,)):
        pn = str(row['part_number']).strip()
        idx[pn] = row['id']
        idx[_norm(pn)] = row['id']
    return idx


# ── Import plan ───────────────────────────────────────────────────────────────

def build_plan(sections, db, serial_idx, name_idx, create_parts=False):
    """
    Returns (plan, missing_parts) where:
      plan          – list of image-to-part link dicts ready for part_files insertion
      missing_parts – list of {kit_id, kit_name, part_number} for parts not yet in DB

    When create_parts=True, missing parts are inserted into the DB before building
    their image links, so they appear in plan rather than missing_parts.
    """
    plan = []
    missing_parts = []
    for sec in sections:
        kit = match_kit(sec['heading'], serial_idx, name_idx)
        if not kit:
            continue
        parts_idx = get_parts_index(db, kit['id'])
        for pt in sec['parts']:
            lbl = pt['label'].rstrip(':').strip()
            part_id = parts_idx.get(lbl) or parts_idx.get(_norm(lbl))
            if not part_id:
                if create_parts and pt['imgs']:
                    # Insert missing part and refresh index entry
                    cur = db.execute(
                        "INSERT INTO parts (kit_id, part_number) VALUES (?,?)",
                        (kit['id'], lbl)
                    )
                    part_id = cur.lastrowid
                    parts_idx[lbl] = part_id
                    parts_idx[_norm(lbl)] = part_id
                else:
                    if pt['imgs']:
                        missing_parts.append({
                            'kit_id': kit['id'],
                            'kit_name': kit['name'],
                            'part_number': lbl,
                            'imgs': len(pt['imgs']),
                        })
                    continue
            for img_src in pt['imgs']:
                filename = Path(img_src).name  # e.g. image801.png
                plan.append({
                    'kit_id': kit['id'],
                    'kit_name': kit['name'],
                    'part_id': part_id,
                    'part_number': lbl,
                    'img_src': img_src,
                    'filename': filename,
                    'url': f'/api/part_images/{filename}',
                })
    return plan, missing_parts


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--dry-run', action='store_true', help='Print plan without writing anything')
    parser.add_argument('--create-parts', action='store_true',
                        help='Create missing part rows in DB before linking images')
    parser.add_argument('--zip', default=str(ZIP_PATH), help='Path to PartList_private.zip')
    parser.add_argument('--db', default=str(DB_PATH), help='Path to SQLite DB')
    args = parser.parse_args()

    zip_path = Path(args.zip)
    db_path = Path(args.db)

    if not zip_path.exists():
        sys.exit(f'ERROR: ZIP not found: {zip_path}')
    if not db_path.exists():
        sys.exit(f'ERROR: DB not found: {db_path}')

    print(f'ZIP:  {zip_path}')
    print(f'DB:   {db_path}')
    print(f'IMGS: {IMG_DIR}')

    # Parse HTML
    with zipfile.ZipFile(zip_path) as zf:
        html = zf.read('PartList_private.html').decode('utf-8', 'ignore')
        zip_names = set(zf.namelist())

    p = PartListParser()
    p.feed(html)
    print(f'Parsed {len(p.sections)} kit sections')

    # Build plan
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    serial_idx, name_idx = build_kit_indexes(db)

    # When dry-running with --create-parts, we don't actually write to DB yet,
    # so pass create_parts=False and show what would be created.
    plan, missing_parts = build_plan(
        p.sections, db, serial_idx, name_idx,
        create_parts=(args.create_parts and not args.dry_run)
    )
    if args.create_parts and not args.dry_run:
        db.commit()  # commit any newly inserted parts
        # Re-build plan now that parts exist (avoids double-counting after commit)
        # plan already contains the new rows from create_parts=True pass above
    print(f'Importable image-part links: {len(plan)}')

    # Deduplicate against existing
    existing_urls = {row['url'] for row in db.execute(
        "SELECT url FROM part_files WHERE url LIKE '/api/part_images/%'"
    )}
    new_plan = [x for x in plan if x['url'] not in existing_urls]
    print(f'Already present: {len(plan) - len(new_plan)}')
    print(f'Net new to import: {len(new_plan)}')

    if missing_parts and not args.create_parts:
        from collections import defaultdict
        by_kit = defaultdict(list)
        for mp in missing_parts:
            by_kit[(mp['kit_id'], mp['kit_name'])].append((mp['part_number'], mp['imgs']))
        print(f'\nPart-level misses (kit matched, part not in DB): {len(missing_parts)} parts, '
              f'{sum(mp["imgs"] for mp in missing_parts)} imgs skipped')
        print('  Use --create-parts to create these parts and import their images.')

    if args.dry_run:
        print('\n--- DRY RUN sample (first 20) ---')
        for r in new_plan[:20]:
            print(f"  kit={r['kit_id']:3d} part={r['part_id']:5d} pn={r['part_number']:10s} img={r['img_src']}")
        kits = {}
        for r in new_plan:
            kits.setdefault(r['kit_id'], r['kit_name'])
        print(f'\nAffected kits: {len(kits)}')
        for kid, kname in sorted(kits.items()):
            cnt = sum(1 for r in new_plan if r['kit_id'] == kid)
            print(f"  kit={kid:3d} {kname[:50]:50s} imgs={cnt}")
        if args.create_parts and missing_parts:
            from collections import defaultdict
            by_kit = defaultdict(list)
            for mp in missing_parts:
                by_kit[(mp['kit_id'], mp['kit_name'])].append((mp['part_number'], mp['imgs']))
            print(f'\nWould also CREATE {len(missing_parts)} missing parts:')
            for (kid, kname), pts in sorted(by_kit.items()):
                print(f"  kit={kid:3d} {kname[:50]:50s}")
                for pn, nimgs in pts:
                    print(f"         pn={pn:15s} imgs={nimgs}")
        return

    if not new_plan:
        print('Nothing to import.')
        return

    # Extract images
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    needed_srcs = {r['img_src'] for r in new_plan}
    extracted = 0
    skipped = 0
    with zipfile.ZipFile(zip_path) as zf:
        for src in needed_srcs:
            dest = IMG_DIR / Path(src).name
            if dest.exists():
                skipped += 1
                continue
            if src not in zip_names:
                print(f'  WARN: {src} not in ZIP, skipping')
                continue
            dest.write_bytes(zf.read(src))
            extracted += 1
    print(f'Images: {extracted} extracted, {skipped} already on disk')

    # Insert part_files rows
    inserted = 0
    with db:
        for r in new_plan:
            db.execute(
                "INSERT INTO part_files (part_id, file_type, url, source) VALUES (?,?,?,?)",
                (r['part_id'], FILE_TYPE, r['url'], SOURCE)
            )
            inserted += 1
    print(f'Inserted {inserted} part_files rows')
    db.close()
    print('Done.')


if __name__ == '__main__':
    main()
