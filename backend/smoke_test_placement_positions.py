import os
import sqlite3

os.environ['ALLOW_LOCAL_ADMIN'] = '1'

from app import app, DB_PATH, init_db  # noqa: E402


def main():
    init_db()
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    model = db.execute("SELECT id FROM models ORDER BY id LIMIT 1").fetchone()
    kit = db.execute("SELECT id FROM kits ORDER BY id LIMIT 1").fetchone()
    if not model or not kit:
        raise SystemExit("Need at least one model and one kit in the database for the smoke test.")

    map_cur = db.execute(
        """
        INSERT INTO maps (model_id, name, version, notes)
        VALUES (?,?,?,?)
        """,
        (model["id"], "Smoke test map", "position-test", "temporary smoke test map"),
    )
    map_id = map_cur.lastrowid

    placement_cur = db.execute(
        """
        INSERT INTO placements
            (model_id, map_id, kit_id, location_label, confidence, modification, notes)
        VALUES (?,?,?,?,?,?,?)
        """,
        (model["id"], map_id, kit["id"], "smoke-test-location", "probable", "none", "temporary smoke test placement"),
    )
    placement_id = placement_cur.lastrowid
    db.commit()
    db.close()

    client = app.test_client()
    auth_suffix = "?admin_local=1"

    try:
        create_res = client.post(
            f"/api/placement_positions{auth_suffix}",
            json={
                "placement_id": placement_id,
                "map_id": map_id,
                "position_type": "box",
                "x_norm": 0.12,
                "y_norm": 0.34,
                "width_norm": 0.2,
                "height_norm": 0.15,
                "source_kind": "manual",
                "status": "active",
                "is_current": 1,
                "confidence": "probable",
                "notes": "smoke test current position",
            },
        )
        assert create_res.status_code == 201, create_res.get_data(as_text=True)
        created_id = create_res.get_json()["id"]

        get_res = client.get(f"/api/placement_positions/{created_id}")
        assert get_res.status_code == 200, get_res.get_data(as_text=True)
        assert get_res.get_json()["position"]["placement_id"] == placement_id

        create_res_2 = client.post(
            f"/api/placement_positions{auth_suffix}",
            json={
                "placement_id": placement_id,
                "map_id": map_id,
                "position_type": "point",
                "x_norm": 0.55,
                "y_norm": 0.66,
                "source_kind": "candidate",
                "status": "active",
                "is_current": 0,
                "confidence": "speculative",
                "notes": "smoke test candidate position",
            },
        )
        assert create_res_2.status_code == 201, create_res_2.get_data(as_text=True)
        created_id_2 = create_res_2.get_json()["id"]

        list_res = client.get(f"/api/placement_positions?placement_id={placement_id}")
        assert list_res.status_code == 200, list_res.get_data(as_text=True)
        listed = list_res.get_json()["data"]
        assert len(listed) >= 2

        update_res = client.put(
            f"/api/placement_positions/{created_id_2}{auth_suffix}",
            json={
                "is_current": 1,
                "supersedes_id": created_id,
                "source_kind": "manual",
                "confidence": "confirmed",
            },
        )
        assert update_res.status_code == 200, update_res.get_data(as_text=True)

        placement_res = client.get(f"/api/placements/{placement_id}")
        assert placement_res.status_code == 200, placement_res.get_data(as_text=True)
        placement_payload = placement_res.get_json()
        assert placement_payload["current_position"]["id"] == created_id_2
        assert any(row["id"] == created_id for row in placement_payload["positions"])

        delete_res = client.delete(f"/api/placement_positions/{created_id_2}{auth_suffix}")
        assert delete_res.status_code == 200, delete_res.get_data(as_text=True)

        placement_res_after = client.get(f"/api/placements/{placement_id}")
        assert placement_res_after.status_code == 200, placement_res_after.get_data(as_text=True)
        restored_payload = placement_res_after.get_json()
        assert restored_payload["current_position"]["id"] == created_id

        print("placement_positions smoke test passed")
    finally:
        cleanup = sqlite3.connect(DB_PATH)
        cleanup.execute("PRAGMA foreign_keys = ON")
        cleanup.execute("DELETE FROM placement_positions WHERE placement_id=?", (placement_id,))
        cleanup.execute("DELETE FROM placements WHERE id=?", (placement_id,))
        cleanup.execute("DELETE FROM maps WHERE id=?", (map_id,))
        cleanup.commit()
        cleanup.close()


if __name__ == "__main__":
    main()
