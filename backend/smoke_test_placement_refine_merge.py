import os
import sqlite3
import uuid

os.environ['ALLOW_LOCAL_ADMIN'] = '1'

from app import app, DB_PATH, init_db  # noqa: E402


def main():
    init_db()

    suffix = uuid.uuid4().hex[:8]
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    model_id = None
    map_id = None
    kit_id = None
    part_a_id = None
    part_b_id = None
    canonical_id = None
    duplicate_id = None
    image_id = None
    claim_id = None

    try:
        model_cur = db.execute(
            """
            INSERT INTO models (name, slug, film, notes)
            VALUES (?,?,?,?)
            """,
            (
                f"Smoke refine model {suffix}",
                f"smoke-refine-model-{suffix}",
                "ANH",
                "temporary smoke test model for refine/merge",
            ),
        )
        model_id = model_cur.lastrowid

        map_cur = db.execute(
            """
            INSERT INTO maps (model_id, name, version, notes)
            VALUES (?,?,?,?)
            """,
            (
                model_id,
                f"Smoke refine map {suffix}",
                "v1",
                "temporary smoke test map",
            ),
        )
        map_id = map_cur.lastrowid

        kit_cur = db.execute(
            """
            INSERT INTO kits (brand, name, scale, notes)
            VALUES (?,?,?,?)
            """,
            ("SmokeBrand", f"SmokeKit {suffix}", "1/72", "temporary smoke test kit"),
        )
        kit_id = kit_cur.lastrowid

        part_a_cur = db.execute(
            "INSERT INTO parts (kit_id, part_number, part_label) VALUES (?,?,?)",
            (kit_id, "8", "A part"),
        )
        part_a_id = part_a_cur.lastrowid
        part_b_cur = db.execute(
            "INSERT INTO parts (kit_id, part_number, part_label) VALUES (?,?,?)",
            (kit_id, "9", "B part"),
        )
        part_b_id = part_b_cur.lastrowid

        canonical_cur = db.execute(
            """
            INSERT INTO placements
                (model_id, map_id, kit_id, location_label, confidence, notes)
            VALUES (?,?,?,?,?,?)
            """,
            (model_id, map_id, kit_id, "left panel", "probable", "canonical placement"),
        )
        canonical_id = canonical_cur.lastrowid

        duplicate_cur = db.execute(
            """
            INSERT INTO placements
                (model_id, map_id, kit_id, location_label, confidence, notes)
            VALUES (?,?,?,?,?,?)
            """,
            (model_id, map_id, kit_id, "left panel duplicate", "probable", "duplicate placement"),
        )
        duplicate_id = duplicate_cur.lastrowid

        db.commit()
    finally:
        db.close()

    client = app.test_client()
    admin_suffix = "?admin_local=1"

    try:
        refine_canonical_res = client.post(
            f"/api/placements/{canonical_id}/refine_part{admin_suffix}",
            json={"part_id": part_a_id, "change_reason": "smoke refine canonical"},
        )
        assert refine_canonical_res.status_code == 200, refine_canonical_res.get_data(as_text=True)

        refine_duplicate_res = client.post(
            f"/api/placements/{duplicate_id}/refine_part{admin_suffix}",
            json={"part_id": part_b_id, "change_reason": "smoke refine duplicate"},
        )
        assert refine_duplicate_res.status_code == 200, refine_duplicate_res.get_data(as_text=True)

        pos_a_res = client.post(
            f"/api/placement_positions{admin_suffix}",
            json={
                "placement_id": canonical_id,
                "map_id": map_id,
                "position_type": "point",
                "x_norm": 0.2,
                "y_norm": 0.3,
                "source_kind": "manual",
                "is_current": 1,
                "confidence": "confirmed",
            },
        )
        assert pos_a_res.status_code == 201, pos_a_res.get_data(as_text=True)

        pos_b_res = client.post(
            f"/api/placement_positions{admin_suffix}",
            json={
                "placement_id": duplicate_id,
                "map_id": map_id,
                "position_type": "point",
                "x_norm": 0.5,
                "y_norm": 0.6,
                "source_kind": "manual",
                "is_current": 1,
                "confidence": "probable",
            },
        )
        assert pos_b_res.status_code == 201, pos_b_res.get_data(as_text=True)

        image_res = client.post(
            "/api/images",
            headers={"X-Admin-Local": "1"},
            json={
                "title": f"Smoke merge image {suffix}",
                "image_code": f"SMOKE-MERGE-{suffix}",
                "image_type": "reference",
                "url": f"https://example.invalid/smoke-merge-{suffix}.jpg",
                "notes": "temporary smoke merge image",
            },
        )
        assert image_res.status_code == 201, image_res.get_data(as_text=True)
        image_id = image_res.get_json()["id"]

        link_res = client.post(
            "/api/image_links",
            json={
                "image_id": image_id,
                "entity_type": "placement",
                "entity_id": duplicate_id,
                "annotation": "duplicate evidence",
            },
        )
        assert link_res.status_code in (200, 201), link_res.get_data(as_text=True)

        claim_res = client.post(
            f"/api/claims{admin_suffix}",
            json={
                "subject_type": "model",
                "subject_id": model_id,
                "predicate": "shows",
                "object_type": "placement",
                "object_id": duplicate_id,
                "confidence": "probable",
                "status": "active",
                "rationale": "duplicate placement evidence",
            },
        )
        assert claim_res.status_code == 201, claim_res.get_data(as_text=True)
        claim_id = claim_res.get_json()["id"]

        merge_res = client.post(
            f"/api/placements/merge{admin_suffix}",
            json={
                "canonical_id": canonical_id,
                "duplicate_ids": [duplicate_id],
                "reason": "smoke test merge",
            },
        )
        assert merge_res.status_code == 200, merge_res.get_data(as_text=True)

        dup_after = client.get(f"/api/placements/{duplicate_id}")
        assert dup_after.status_code == 404, dup_after.get_data(as_text=True)

        canonical_after = client.get(f"/api/placements/{canonical_id}")
        assert canonical_after.status_code == 200, canonical_after.get_data(as_text=True)
        payload = canonical_after.get_json()
        assert payload["placement"]["part_id"] == part_a_id
        assert len(payload["positions"]) >= 2
        current_positions = [p for p in payload["positions"] if p.get("is_current")]
        assert len(current_positions) == 1

        claim_after = client.get(f"/api/claims/{claim_id}")
        assert claim_after.status_code == 200, claim_after.get_data(as_text=True)
        claim_payload = claim_after.get_json()["claim"]
        assert claim_payload["object_type"] == "placement"
        assert claim_payload["object_id"] == canonical_id

        link_after = client.get(f"/api/image_links?entity_type=placement&entity_id={canonical_id}")
        assert link_after.status_code == 200, link_after.get_data(as_text=True)
        links = link_after.get_json()["data"]
        assert any(int(row["image_id"]) == int(image_id) for row in links)

        print("placement_refine_merge smoke test passed")
    finally:
        cleanup = sqlite3.connect(DB_PATH)
        cleanup.execute("PRAGMA foreign_keys = ON")
        if claim_id is not None:
            cleanup.execute("DELETE FROM claims WHERE id=?", (claim_id,))
        if image_id is not None:
            cleanup.execute("DELETE FROM image_links WHERE image_id=?", (image_id,))
            cleanup.execute("DELETE FROM image_tags WHERE image_id=?", (image_id,))
            cleanup.execute("DELETE FROM images WHERE id=?", (image_id,))
        if canonical_id is not None:
            cleanup.execute("DELETE FROM placement_positions WHERE placement_id=?", (canonical_id,))
            cleanup.execute("DELETE FROM placement_contributors WHERE placement_id=?", (canonical_id,))
            cleanup.execute("DELETE FROM placement_history WHERE placement_id=?", (canonical_id,))
            cleanup.execute("DELETE FROM placements WHERE id=?", (canonical_id,))
        if duplicate_id is not None:
            cleanup.execute("DELETE FROM placement_positions WHERE placement_id=?", (duplicate_id,))
            cleanup.execute("DELETE FROM placement_contributors WHERE placement_id=?", (duplicate_id,))
            cleanup.execute("DELETE FROM placement_history WHERE placement_id=?", (duplicate_id,))
            cleanup.execute("DELETE FROM placements WHERE id=?", (duplicate_id,))
        if part_a_id is not None:
            cleanup.execute("DELETE FROM parts WHERE id=?", (part_a_id,))
        if part_b_id is not None:
            cleanup.execute("DELETE FROM parts WHERE id=?", (part_b_id,))
        if kit_id is not None:
            cleanup.execute("DELETE FROM kits WHERE id=?", (kit_id,))
        if map_id is not None:
            cleanup.execute("DELETE FROM maps WHERE id=?", (map_id,))
        if model_id is not None:
            cleanup.execute("DELETE FROM models WHERE id=?", (model_id,))
        cleanup.commit()
        cleanup.close()


if __name__ == "__main__":
    main()
