# API Reference

Updated: May 3, 2026

Source of truth: route decorators in `backend/app.py` and `backend/blueprints/`.

Base URL for local development:

```text
http://localhost:5000
```

## Conventions

Most responses use the backend envelope:

```json
{
  "ok": true,
  "data": {}
}
```

Some detail endpoints return named payloads such as `image`, `position`, `family`, or `claim`.

Write routes are admin-protected. If `ADMIN_API_KEY` is set, send:

```text
X-API-Key: <key>
```

For local operator work, the backend also accepts:

```text
X-Admin-Local: 1
```

when the request is local or `ALLOW_LOCAL_ADMIN=1` is set.

## Health And Static Files

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/health` | Backend health check |
| GET | `/uploads/<filename>` | Uploaded image/file bytes |
| GET | `/api/part_images/<filename>` | Imported part-list image bytes |

## Imports And Admin Operations

| Method | Path | Notes |
|--------|------|-------|
| POST | `/api/imports/reconciliation_preview` | Preview spreadsheet/import reconciliation |
| POST | `/api/imports/reconcile_apply` | Apply reconciliation actions |
| POST | `/api/imports/normalize_part_numbers` | Normalize imported part numbers |

## Kits

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/kits` | Query kits with `q`, `brand`, `availability`, `category_family` |
| GET | `/api/kits/<id>` | Kit detail with references, parts, placements, images |
| POST | `/api/kits` | Create kit |
| PUT | `/api/kits/<id>` | Update kit |
| GET | `/api/kits/<id>/history` | Kit change history |
| GET | `/api/kits/<id>/references` | External kit reference list |
| POST | `/api/kits/<id>/references` | Add external kit reference |
| DELETE | `/api/kits/<id>/references/<reference_id>` | Delete external kit reference |

## Parts

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/parts` | Query parts with `kit_id`, `q` |
| GET | `/api/parts/<id>` | Part detail with kit and placement context |
| POST | `/api/parts` | Create part |
| PUT | `/api/parts/<id>` | Update part |
| POST | `/api/parts/<id>/files` | Add part file/asset link |
| DELETE | `/api/parts/<id>/files/<file_id>` | Delete part file/asset link |

## Models And Maps

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/models` | List studio model records |
| GET | `/api/models/<slug>` | Model detail by slug |
| POST | `/api/models` | Create model |
| PUT | `/api/models/<id>` | Update model |
| GET | `/api/maps` | Query maps with `model_id` |
| POST | `/api/maps` | Create map |
| PUT | `/api/maps/<id>` | Update map |

## Placements

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/placements` | Query placements with `model_id`, `kit_id`, `map_id`, `film_version`, `confidence` |
| GET | `/api/placements/<id>` | Placement detail with positions and related evidence |
| POST | `/api/placements` | Create placement |
| PUT | `/api/placements/<id>` | Update placement |
| DELETE | `/api/placements/<id>` | Delete placement |
| GET | `/api/placements/refinement_queue` | Part-refinement queue |
| GET | `/api/placements/refinement-queue` | Alias for refinement queue |
| POST | `/api/placements/<id>/refine_part` | Refine kit-level placement to a part |
| POST | `/api/placements/<id>/refine` | Alias for part refinement |
| POST | `/api/placements/merge` | Merge duplicate placements |
| POST | `/api/placements/<id>/contributors` | Add placement contributor |
| DELETE | `/api/placements/<id>/contributors/<contributor_id>` | Remove placement contributor |
| GET | `/api/connections` | Cross-model kit appearance query |

## Placement Positions

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/placement_positions` | Query map geometry records with `placement_id`, `map_id`, `status` |
| GET | `/api/placement_positions/<id>` | Position detail |
| POST | `/api/placement_positions` | Create position record |
| PUT | `/api/placement_positions/<id>` | Update position; can mark current |
| DELETE | `/api/placement_positions/<id>` | Delete eligible position |

## Cast Assemblies

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/cast_assemblies` | List cast assemblies |
| GET | `/api/cast_assemblies/<id>` | Cast assembly detail |
| POST | `/api/cast_assemblies` | Create cast assembly |
| POST | `/api/cast_assemblies/<id>/parts` | Add part to cast assembly |

## Sources And Extracts

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/sources` | Query sources with `q`, `source_type` |
| GET | `/api/sources/<id>` | Source detail |
| POST | `/api/sources` | Create source |
| PUT | `/api/sources/<id>` | Update source |
| GET | `/api/source_extracts` | Query extracts with `source_id`, `extract_type`, `author_handle`, `q` |
| GET | `/api/source_extracts/<id>` | Extract detail |
| POST | `/api/source_extracts` | Create extract |
| PUT | `/api/source_extracts/<id>` | Update extract |

## Image Families

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/image_families` | Query families with `image_id`, `q` |
| GET | `/api/image_families/<id>` | Family detail with members |
| POST | `/api/image_families` | Create family |
| PUT | `/api/image_families/<id>` | Update family |
| DELETE | `/api/image_families/<id>` | Delete family |
| POST | `/api/image_families/<id>/members` | Add family member |
| PUT | `/api/image_families/<id>/members/<member_id>` | Update family member |
| DELETE | `/api/image_families/<id>/members/<member_id>` | Remove family member |

## Images, Regions, Links, And Tags

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/images` | Query images with `entity_type`, `entity_id`, `image_type`, `source_id`, `family_id`, `collapse_family`, `tag`, `q` |
| GET | `/api/images/<id>` | Image detail with links, tags, regions, source, claims, family |
| POST | `/api/images` | Create image metadata or upload file |
| PUT | `/api/images/<id>` | Update image metadata and tags |
| DELETE | `/api/images/<id>` | Delete image record and unreferenced uploaded file |
| GET | `/api/image_regions` | Query regions with `image_id`, `entity_type`, `entity_id`, `source_extract_id` |
| GET | `/api/image_regions/<id>` | Region detail with links, claims, history |
| POST | `/api/image_regions` | Create region |
| PUT | `/api/image_regions/<id>` | Update region |
| DELETE | `/api/image_regions/<id>` | Delete region |
| GET | `/api/image_links` | Query image links with `image_id` or `entity_type` plus `entity_id` |
| POST | `/api/image_links` | Create image link |
| PUT | `/api/image_links/<id>` | Update image link |
| DELETE | `/api/image_links/<id>` | Delete image link |
| POST | `/api/images/<id>/tags` | Add image tag |
| DELETE | `/api/images/<id>/tags/<tag>` | Remove image tag |

## Contributors, Search, And Claims

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/contributors` | List contributors |
| POST | `/api/contributors` | Create contributor |
| GET | `/api/entity_search` | Normalized picker search across entity types |
| GET | `/api/search` | Lightweight cross-entity search |
| GET | `/api/claims` | Query claims with subject/evidence filters |
| GET | `/api/claims/<id>` | Claim detail with evidence labels |
| POST | `/api/claims` | Create claim |
| PUT | `/api/claims/<id>` | Update claim and evidence links |
| DELETE | `/api/claims/<id>` | Delete claim |

## Maintenance Note

When routes change, update this file in the same pass as the backend change. A future cleanup should replace this hand-maintained list with a tiny route-dump script.
