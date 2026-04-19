from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "backend" / "data" / "ilm1300.db"


def ensure_claim(
    conn: sqlite3.Connection,
    *,
    subject_type: str,
    subject_id: int,
    predicate: str,
    object_type: str | None,
    object_id: int | None,
    text_value: str | None,
    confidence: str,
    status: str,
    rationale: str,
) -> tuple[int, bool]:
    row = conn.execute(
        """
        SELECT id
        FROM claims
        WHERE subject_type = ?
          AND subject_id = ?
          AND predicate = ?
          AND COALESCE(object_type, '') = COALESCE(?, '')
          AND COALESCE(object_id, -1) = COALESCE(?, -1)
          AND COALESCE(text_value, '') = COALESCE(?, '')
        LIMIT 1
        """,
        (subject_type, subject_id, predicate, object_type, object_id, text_value),
    ).fetchone()
    if row:
        claim_id = row[0]
        conn.execute(
            """
            UPDATE claims
            SET confidence = ?,
                status = ?,
                rationale = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (confidence, status, rationale, claim_id),
        )
        return claim_id, False

    cur = conn.execute(
        """
        INSERT INTO claims
            (subject_type, subject_id, predicate, object_type, object_id,
             text_value, confidence, status, rationale)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            subject_type,
            subject_id,
            predicate,
            object_type,
            object_id,
            text_value,
            confidence,
            status,
            rationale,
        ),
    )
    return cur.lastrowid, True


def attach_region_evidence(conn: sqlite3.Connection, claim_id: int, region_id: int, annotation: str) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO claim_evidence (claim_id, evidence_type, evidence_id, annotation)
        VALUES (?, 'image_region', ?, ?)
        """,
        (claim_id, region_id, annotation),
    )


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    seeded = 0

    clean_region = conn.execute(
        """
        SELECT id, label, entity_id
        FROM image_regions
        WHERE label = 'Airfix Focke Wulf 189'
          AND entity_type = 'kit'
          AND entity_id IS NOT NULL
        ORDER BY id
        LIMIT 1
        """
    ).fetchone()
    if clean_region:
        claim_id, created = ensure_claim(
            conn,
            subject_type="image_region",
            subject_id=clean_region["id"],
            predicate="depicts",
            object_type="kit",
            object_id=clean_region["entity_id"],
            text_value=None,
            confidence="confirmed",
            status="active",
            rationale="Phase 1 seed: exact overlay label matches a single kit record.",
        )
        attach_region_evidence(conn, claim_id, clean_region["id"], "Seed clean identification example.")
        seeded += int(created)

    conflict_region = conn.execute(
        """
        SELECT id
        FROM image_regions
        WHERE label = 'Bandai Hummel'
        ORDER BY id
        LIMIT 1
        """
    ).fetchone()
    if conflict_region:
        claim_id, created = ensure_claim(
            conn,
            subject_type="image_region",
            subject_id=conflict_region["id"],
            predicate="depicts",
            object_type=None,
            object_id=None,
            text_value="Bandai Hummel family component",
            confidence="probable",
            status="active",
            rationale="Phase 1 seed: preserves the imported overlay identification as a working interpretation.",
        )
        attach_region_evidence(conn, claim_id, conflict_region["id"], "Seed conflict case A.")
        seeded += int(created)

        alt_claim_id, created = ensure_claim(
            conn,
            subject_type="image_region",
            subject_id=conflict_region["id"],
            predicate="depicts",
            object_type=None,
            object_id=None,
            text_value="Bandai Panzer IV / F2 family component",
            confidence="speculative",
            status="contested",
            rationale="Phase 1 seed: alternate reading kept explicit so conflict handling can be tested.",
        )
        attach_region_evidence(conn, alt_claim_id, conflict_region["id"], "Seed conflict case B.")
        seeded += int(created)

    empty_region = conn.execute(
        """
        SELECT id
        FROM image_regions
        WHERE (entity_type IS NULL OR entity_id IS NULL)
          AND label IS NOT NULL
          AND label NOT IN ('Bandai Hummel')
        ORDER BY id
        LIMIT 1
        """
    ).fetchone()

    conn.commit()

    print("Phase 1 claim seed complete.")
    print(f"Claims inserted this run: {seeded}")
    print(f"Clean linked region: {clean_region['id'] if clean_region else 'missing'}")
    print(f"Conflict region: {conflict_region['id'] if conflict_region else 'missing'}")
    print(f"Unlinked/no-claim region available: {empty_region['id'] if empty_region else 'missing'}")


if __name__ == "__main__":
    main()
