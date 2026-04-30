import os
import sqlite3
import uuid

from app import DB_PATH, init_db
from import_spreadsheets import (
    classify_part_placement_action,
    classify_cross_model_kit_action,
    clean_part_number,
)


def main():
    init_db()

    suffix = uuid.uuid4().hex[:8]
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")

    model_id = None
    map_id = None
    kit_id = None
    part_id = None
    kit_level_placement_id = None
    part_level_placement_id = None

    try:
        model_cur = db.execute(
            "INSERT INTO models (name, slug, film) VALUES (?,?,?)",
            (f"Import smoke model {suffix}", f"import-smoke-model-{suffix}", "ANH"),
        )
        model_id = model_cur.lastrowid

        map_cur = db.execute(
            "INSERT INTO maps (model_id, name, version) VALUES (?,?,?)",
            (model_id, f"Import smoke map {suffix}", "v1"),
        )
        map_id = map_cur.lastrowid

        kit_cur = db.execute(
            "INSERT INTO kits (brand, name, scale) VALUES (?,?,?)",
            ("ImportSmoke", f"Kit {suffix}", "1/72"),
        )
        kit_id = kit_cur.lastrowid

        part_cur = db.execute(
            "INSERT INTO parts (kit_id, part_number, part_label) VALUES (?,?,?)",
            (kit_id, "42", "Smoke Part"),
        )
        part_id = part_cur.lastrowid

        kit_level_cur = db.execute(
            """
            INSERT INTO placements (model_id, map_id, kit_id, location_label, confidence)
            VALUES (?,?,?,?,?)
            """,
            (model_id, map_id, kit_id, "smoke import location", "probable"),
        )
        kit_level_placement_id = kit_level_cur.lastrowid

        db.commit()

        action, target_id = classify_part_placement_action(db, model_id, map_id, kit_id, part_id)
        assert action == "refine_existing_kit"
        assert target_id == kit_level_placement_id

        db.execute(
            "UPDATE placements SET part_id=?, kit_id=NULL WHERE id=?",
            (part_id, kit_level_placement_id),
        )
        db.commit()

        action_2, target_id_2 = classify_part_placement_action(db, model_id, map_id, kit_id, part_id)
        assert action_2 == "duplicate_part"
        assert target_id_2 == kit_level_placement_id

        action_3, _ = classify_cross_model_kit_action(db, model_id, kit_id)
        assert action_3 == "implied_by_part"

        db.execute(
            """
            INSERT INTO placements (model_id, kit_id, confidence, location_label)
            VALUES (?,?,?,?)
            """,
            (model_id, kit_id, "probable", "explicit kit-level"),
        )
        part_level_placement_id = db.execute("SELECT MAX(id) AS id FROM placements").fetchone()["id"]
        db.commit()

        action_4, target_id_4 = classify_cross_model_kit_action(db, model_id, kit_id)
        assert action_4 == "duplicate_kit_level"
        assert target_id_4 == part_level_placement_id

        assert clean_part_number("8.0") == "8"
        assert clean_part_number("A3") == "A3"

        print("import_reconciliation smoke test passed")
    finally:
        cleanup = sqlite3.connect(DB_PATH)
        cleanup.execute("PRAGMA foreign_keys = ON")
        if model_id is not None:
            cleanup.execute("DELETE FROM placement_history WHERE placement_id IN (SELECT id FROM placements WHERE model_id=?)", (model_id,))
            cleanup.execute("DELETE FROM placement_positions WHERE placement_id IN (SELECT id FROM placements WHERE model_id=?)", (model_id,))
            cleanup.execute("DELETE FROM placements WHERE model_id=?", (model_id,))
        if part_id is not None:
            cleanup.execute("DELETE FROM parts WHERE id=?", (part_id,))
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
