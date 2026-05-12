"""Entity display labels and claim enrichment helpers."""

try:
    from .api_utils import rows_to_list
except ImportError:
    from api_utils import rows_to_list


def entity_label(entity_type, entity_id, db):
    """Return a short human-readable string for display next to a link."""
    try:
        if entity_type == 'kit':
            r = db.execute("SELECT brand, name FROM kits WHERE id=?", (entity_id,)).fetchone()
            return f"{r['brand']} — {r['name']}" if r else str(entity_id)
        elif entity_type == 'part':
            r = db.execute("""
                SELECT p.part_number, p.part_label, k.name as kit_name
                FROM parts p JOIN kits k ON k.id = p.kit_id WHERE p.id=?
            """, (entity_id,)).fetchone()
            if r:
                label = r['part_label'] or ''
                return f"{r['kit_name']} #{r['part_number']} {label}".strip()
        elif entity_type == 'cast_assembly':
            r = db.execute("SELECT name FROM cast_assemblies WHERE id=?", (entity_id,)).fetchone()
            return r['name'] if r else str(entity_id)
        elif entity_type == 'placement':
            r = db.execute("""
                SELECT pl.location_label, pt.part_number, k.brand, k.name as kit_name,
                       m.name as model_name
                FROM placements pl
                JOIN models m ON m.id = pl.model_id
                LEFT JOIN parts pt ON pt.id = pl.part_id
                LEFT JOIN kits k   ON k.id  = COALESCE(pt.kit_id, pl.kit_id)
                WHERE pl.id=?
            """, (entity_id,)).fetchone()
            if r:
                part_str = f"{r['brand']} {r['kit_name']} #{r['part_number']}" if r['part_number'] else ''
                loc = r['location_label'] or ''
                return f"{r['model_name']} — {part_str} {loc}".strip(' —')
        elif entity_type == 'model':
            r = db.execute("SELECT name FROM models WHERE id=?", (entity_id,)).fetchone()
            return r['name'] if r else str(entity_id)
        elif entity_type == 'map':
            r = db.execute("SELECT name FROM maps WHERE id=?", (entity_id,)).fetchone()
            return r['name'] if r else str(entity_id)
        elif entity_type == 'image':
            r = db.execute("SELECT title, image_code, filename FROM images WHERE id=?", (entity_id,)).fetchone()
            if r:
                return r['title'] or r['image_code'] or r['filename'] or f"Image {entity_id}"
        elif entity_type == 'image_region':
            r = db.execute("SELECT label, image_id FROM image_regions WHERE id=?", (entity_id,)).fetchone()
            if r:
                return r['label'] or f"Region {entity_id} on image {r['image_id']}"
    except Exception:
        pass
    return str(entity_id)


def enrich_claim_rows(rows, db):
    enriched = []
    for row in rows:
        claim = dict(row)
        if claim.get('subject_type') and claim.get('subject_id') is not None:
            claim['subject_label'] = entity_label(claim['subject_type'], claim['subject_id'], db)
        else:
            claim['subject_label'] = None
        if claim.get('object_type') and claim.get('object_id') is not None:
            claim['object_label'] = entity_label(claim['object_type'], claim['object_id'], db)
        else:
            claim['object_label'] = None
        evidence = rows_to_list(db.execute("""
            SELECT * FROM claim_evidence
            WHERE claim_id=?
            ORDER BY evidence_type, evidence_id
        """, (claim['id'],)).fetchall())
        for item in evidence:
            if item.get('evidence_type') == 'image_region':
                reg = db.execute("SELECT label, image_id FROM image_regions WHERE id=?", (item['evidence_id'],)).fetchone()
                if reg:
                    item['evidence_label'] = reg['label'] or f"Region {item['evidence_id']}"
                    item['image_id'] = reg['image_id']
                else:
                    item['evidence_label'] = f"Region {item['evidence_id']}"
            elif item.get('evidence_type') == 'source_extract':
                ext = db.execute("SELECT locator, content FROM source_extracts WHERE id=?", (item['evidence_id'],)).fetchone()
                if ext:
                    item['evidence_label'] = ext['locator'] or (ext['content'][:80] + '...' if ext['content'] and len(ext['content']) > 80 else ext['content'])
                else:
                    item['evidence_label'] = f"Source extract {item['evidence_id']}"
            elif item.get('evidence_type') == 'image':
                img = db.execute("SELECT title, image_code, filename FROM images WHERE id=?", (item['evidence_id'],)).fetchone()
                if img:
                    item['evidence_label'] = img['title'] or img['image_code'] or img['filename'] or f"Image {item['evidence_id']}"
                else:
                    item['evidence_label'] = f"Image {item['evidence_id']}"
        claim['evidence'] = evidence
        enriched.append(claim)
    return enriched
