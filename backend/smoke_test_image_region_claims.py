import os
import sqlite3
import uuid

os.environ['ALLOW_LOCAL_ADMIN'] = '1'

from app import app, DB_PATH, init_db  # noqa: E402


def main():
    init_db()

    suffix = uuid.uuid4().hex[:8]
    model_id = None
    image_id = None
    region_id = None
    claim_id = None

    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    try:
        model_cur = db.execute(
            """
            INSERT INTO models (name, slug, film, notes)
            VALUES (?,?,?,?)
            """,
            (
                f"Smoke test model {suffix}",
                f"smoke-test-model-{suffix}",
                "ANH",
                "temporary smoke test model for image-region-claim flow",
            ),
        )
        model_id = model_cur.lastrowid
        db.commit()
    finally:
        db.close()

    client = app.test_client()
    admin_headers = {"X-Admin-Local": "1"}
    region_label = "Smoke test detail"

    try:
        image_res = client.post(
            "/api/images",
            headers=admin_headers,
            json={
                "title": f"Smoke test image {suffix}",
                "image_code": f"SMOKE-IMG-{suffix}",
                "image_type": "reference",
                "url": f"https://example.invalid/smoke-test-{suffix}.jpg",
                "width": 1600,
                "height": 900,
                "notes": "temporary smoke test image",
                "tags": "smoke-test, region-claim",
            },
        )
        assert image_res.status_code == 201, image_res.get_data(as_text=True)
        image_id = image_res.get_json()["id"]

        region_res = client.post(
            "/api/image_regions",
            headers=admin_headers,
            json={
                "image_id": image_id,
                "region_type": "box",
                "x_norm": 0.21,
                "y_norm": 0.34,
                "width_norm": 0.18,
                "height_norm": 0.12,
                "label": region_label,
                "notes": "temporary smoke test region",
                "object_name": "test greeblie",
                "color": "#ff6600",
                "properties": {"source": "smoke-test"},
            },
        )
        assert region_res.status_code == 201, region_res.get_data(as_text=True)
        region_id = region_res.get_json()["id"]

        claim_res = client.post(
            "/api/claims",
            headers=admin_headers,
            json={
                "subject_type": "model",
                "subject_id": model_id,
                "predicate": "shows_detail",
                "text_value": "smoke test region detail",
                "confidence": "probable",
                "status": "active",
                "rationale": "temporary smoke test claim",
                "evidence": [
                    {
                        "evidence_type": "image_region",
                        "evidence_id": region_id,
                        "annotation": "boxed smoke test evidence",
                    }
                ],
            },
        )
        assert claim_res.status_code == 201, claim_res.get_data(as_text=True)
        claim_id = claim_res.get_json()["id"]

        image_get_res = client.get(f"/api/images/{image_id}")
        assert image_get_res.status_code == 200, image_get_res.get_data(as_text=True)
        image_payload = image_get_res.get_json()
        assert image_payload["image"]["id"] == image_id
        assert image_payload["claim_count"] == 1
        assert image_payload["tags"] == ["region-claim", "smoke-test"]
        assert len(image_payload["regions"]) == 1
        region_summary = image_payload["regions"][0]
        assert region_summary["id"] == region_id
        assert region_summary["label"] == region_label
        assert region_summary["claim_count"] == 1

        region_list_res = client.get(f"/api/image_regions?image_id={image_id}")
        assert region_list_res.status_code == 200, region_list_res.get_data(as_text=True)
        listed_regions = region_list_res.get_json()["data"]
        assert len(listed_regions) == 1
        assert listed_regions[0]["id"] == region_id

        region_get_res = client.get(f"/api/image_regions/{region_id}")
        assert region_get_res.status_code == 200, region_get_res.get_data(as_text=True)
        region_payload = region_get_res.get_json()
        assert region_payload["region"]["id"] == region_id
        assert any(entry["action"] == "create" for entry in region_payload["history"])
        assert len(region_payload["claims"]) == 1
        assert region_payload["claims"][0]["id"] == claim_id

        claim_list_res = client.get(f"/api/claims?evidence_type=image_region&evidence_id={region_id}")
        assert claim_list_res.status_code == 200, claim_list_res.get_data(as_text=True)
        listed_claims = claim_list_res.get_json()["data"]
        assert len(listed_claims) == 1
        assert listed_claims[0]["id"] == claim_id

        claim_get_res = client.get(f"/api/claims/{claim_id}")
        assert claim_get_res.status_code == 200, claim_get_res.get_data(as_text=True)
        claim_payload = claim_get_res.get_json()["claim"]
        assert claim_payload["id"] == claim_id
        assert claim_payload["subject_type"] == "model"
        assert claim_payload["subject_id"] == model_id
        assert claim_payload["text_value"] == "smoke test region detail"
        assert len(claim_payload["evidence"]) == 1
        evidence = claim_payload["evidence"][0]
        assert evidence["evidence_type"] == "image_region"
        assert evidence["evidence_id"] == region_id
        assert evidence["image_id"] == image_id
        assert evidence["annotation"] == "boxed smoke test evidence"

        print("image_region_claims smoke test passed")
    finally:
        cleanup = sqlite3.connect(DB_PATH)
        cleanup.execute("PRAGMA foreign_keys = ON")
        if claim_id is not None:
            cleanup.execute("DELETE FROM claims WHERE id=?", (claim_id,))
        if region_id is not None:
            cleanup.execute("DELETE FROM image_region_history WHERE region_id=?", (region_id,))
            cleanup.execute("DELETE FROM image_regions WHERE id=?", (region_id,))
        if image_id is not None:
            cleanup.execute("DELETE FROM image_tags WHERE image_id=?", (image_id,))
            cleanup.execute("DELETE FROM image_links WHERE image_id=?", (image_id,))
            cleanup.execute("DELETE FROM image_family_members WHERE image_id=?", (image_id,))
            cleanup.execute("UPDATE image_families SET primary_image_id=NULL WHERE primary_image_id=?", (image_id,))
            cleanup.execute("DELETE FROM images WHERE id=?", (image_id,))
        if model_id is not None:
            cleanup.execute("DELETE FROM models WHERE id=?", (model_id,))
        cleanup.commit()
        cleanup.close()


if __name__ == "__main__":
    main()
