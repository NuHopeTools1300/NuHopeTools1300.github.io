# Placement Refinement Workflow

## Overview

The placement refinement workflow supports a practical two-pass approach:

1. **Kit-first pass**: Place kits quickly on the map without part-level identity.
2. **Refinement pass**: Convert kit-level placements to part-level placements when part identity is known, or merge duplicates.

This keeps the initial mapping fast while preserving evidence and enabling cleanup of existing placements.

---

## Operator Workflow

### Phase 1: Kit Placement (Fast Coverage)

1. Open **Map Workbench** (`map_workbench.html`).
2. Filter by **Class** = "Kit" to show kit-only placements.
3. Add new placements with kit identity only (no part number).
4. Mark locations quickly on the map.

### Phase 2: Refinement (Targeted Detail)

1. Open **Refinement Queue** in the map workbench (filter icon or menu).
2. The queue shows all kit-level placements on the current model.
3. For each placement in the queue:
   - **Refine**: If you identify the specific part, click **Refine** to convert the placement from kit-level to part-level.
   - **Merge**: If you find duplicates or conflicting records, click **Merge** to combine them into a single canonical placement.
4. Use **Map Workbench Inspector** to view linked images, evidence, and history while deciding.

### Existing Placements

The same refine/merge tools work on existing placements:

- Select a placement in the list or inspector.
- Use **Refine** to upgrade kit-level records.
- Use **Merge** to deduplicate records from multiple import sources.

---

## API Endpoints

### GET `/api/placements/refinement-queue`

List all kit-level placements (eligible for refinement) for a given model.

**Query Parameters:**
- `model_id` (integer, required): The model ID to filter by.

**Response:**
```json
{
  "status": "ok",
  "data": [
    {
      "id": 123,
      "kit_id": 456,
      "kit_name": "Airfix Bismarck",
      "part_id": null,
      "model_id": 1,
      "map_id": 55,
      "location_label": "Starboard walkway top",
      "confidence": "high",
      "notes": "Kit placement pending part identification",
      "current_position": {
        "x_norm": 0.42,
        "y_norm": 0.58,
        "map_name": "Starboard walkway top",
        "source": "manual_map_click"
      }
    }
  ]
}
```

### POST `/api/placements/<id>/refine`

Convert a kit-level placement to a part-level placement.

**Request Body:**
```json
{
  "part_id": 789,
  "reason": "Identified part from donor kit documentation"
}
```

**Response:**
```json
{
  "status": "ok",
  "data": {
    "id": 123,
    "kit_id": 456,
    "part_id": 789,
    "part_number": "12-A",
    "model_id": 1,
    "message": "Placement refined from kit to part"
  }
}
```

**Error Responses:**
- `400 Bad Request`: Missing or invalid `part_id`.
- `404 Not Found`: Placement or part not found.
- `409 Conflict`: Placement is already at part level or is not a direct kit placement.

---

### POST `/api/placements/merge`

Merge multiple placements into a single canonical placement, preserving history and linked evidence.

**Request Body:**
```json
{
  "primary_id": 123,
  "merge_ids": [124, 125],
  "reason": "Duplicate records from import; consolidating into primary"
}
```

**Response:**
```json
{
  "status": "ok",
  "data": {
    "id": 123,
    "merged_count": 2,
    "message": "Merged 2 placements into primary placement 123",
    "history": [
      {
        "placement_id": 123,
        "action": "merge",
        "reason": "Duplicate records from import; consolidating into primary"
      }
    ]
  }
}
```

**Error Responses:**
- `400 Bad Request`: Missing required fields or empty `merge_ids`.
- `404 Not Found`: Primary or merge placement not found.
- `409 Conflict`: Cannot merge placements on different models or maps.

---

## Import Reconciliation

When importing placements from spreadsheets or external sources, the importer now classifies rows into:

- **Create**: New placement (no conflict).
- **Refine**: Existing kit-level placement; upgrade to part level.
- **Merge candidate**: Duplicate of existing placement; offer merge.
- **Unresolved**: Cannot determine action automatically; review in queue.

**Dry-run import report** includes these classifications and counts, allowing you to review before committing.

---

## History & Evidence

All refinement and merge operations are recorded in `placement_history` with:

- `action`: "refine" or "merge"
- `reason`: Operator-provided rationale
- `changed_at`: Timestamp
- `snapshot_json`: Previous state (for audit/recovery)

Linked images, regions, and claims are preserved across refinement/merge operations to maintain evidence chains.

---

## Best Practices

1. **Kit-first default**: Always place the kit first, even if part identity is uncertain. Refine later when information is available.
2. **Single source of truth**: Merge duplicates from multiple imports into one canonical record.
3. **Document reason**: Always include a reason when refining or merging (e.g., "Identified part from donor kit docs", "Consolidated duplicate from source X").
4. **Review before import**: Use the import dry-run reconciliation report to catch conflicts before committing.
5. **Use Datasette for audit**: Open `http://127.0.0.1:8001` and browse `placement_history` and `placements` tables to verify merge/refine operations.
