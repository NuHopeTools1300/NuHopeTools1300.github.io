"""Smoke-test the Flask route surface after blueprint refactors."""

from app import app


EXPECTED_ROUTES = {
    ("DELETE", "/api/claims/<int:claim_id>"),
    ("DELETE", "/api/image_families/<int:family_id>"),
    ("DELETE", "/api/image_families/<int:family_id>/members/<int:member_id>"),
    ("DELETE", "/api/image_links/<int:link_id>"),
    ("DELETE", "/api/image_regions/<int:region_id>"),
    ("DELETE", "/api/images/<int:image_id>"),
    ("DELETE", "/api/images/<int:image_id>/tags/<tag>"),
    ("DELETE", "/api/kits/<int:kit_id>/references/<int:ref_id>"),
    ("DELETE", "/api/parts/<int:part_id>/files/<int:file_id>"),
    ("DELETE", "/api/placement_positions/<int:position_id>"),
    ("DELETE", "/api/placements/<int:pl_id>"),
    ("DELETE", "/api/placements/<int:pl_id>/contributors/<int:contrib_id>"),
    ("GET", "/api/cast_assemblies"),
    ("GET", "/api/cast_assemblies/<int:ca_id>"),
    ("GET", "/api/claims"),
    ("GET", "/api/claims/<int:claim_id>"),
    ("GET", "/api/connections"),
    ("GET", "/api/contributors"),
    ("GET", "/api/entity_search"),
    ("GET", "/api/health"),
    ("GET", "/api/image_families"),
    ("GET", "/api/image_families/<int:family_id>"),
    ("GET", "/api/image_links"),
    ("GET", "/api/image_regions"),
    ("GET", "/api/image_regions/<int:region_id>"),
    ("GET", "/api/images"),
    ("GET", "/api/images/<int:image_id>"),
    ("GET", "/api/kits"),
    ("GET", "/api/kits/<int:kit_id>"),
    ("GET", "/api/kits/<int:kit_id>/history"),
    ("GET", "/api/kits/<int:kit_id>/references"),
    ("GET", "/api/maps"),
    ("GET", "/api/models"),
    ("GET", "/api/models/<slug>"),
    ("GET", "/api/part_images/<path:filename>"),
    ("GET", "/api/parts"),
    ("GET", "/api/parts/<int:part_id>"),
    ("GET", "/api/placement_positions"),
    ("GET", "/api/placement_positions/<int:position_id>"),
    ("GET", "/api/placements"),
    ("GET", "/api/placements/<int:pl_id>"),
    ("GET", "/api/placements/refinement-queue"),
    ("GET", "/api/placements/refinement_queue"),
    ("GET", "/api/search"),
    ("GET", "/api/source_extracts"),
    ("GET", "/api/source_extracts/<int:extract_id>"),
    ("GET", "/api/sources"),
    ("GET", "/api/sources/<int:source_id>"),
    ("GET", "/static/<path:filename>"),
    ("GET", "/uploads/<path:filename>"),
    ("POST", "/api/cast_assemblies"),
    ("POST", "/api/cast_assemblies/<int:ca_id>/parts"),
    ("POST", "/api/claims"),
    ("POST", "/api/contributors"),
    ("POST", "/api/image_families"),
    ("POST", "/api/image_families/<int:family_id>/members"),
    ("POST", "/api/image_links"),
    ("POST", "/api/image_regions"),
    ("POST", "/api/images"),
    ("POST", "/api/images/<int:image_id>/tags"),
    ("POST", "/api/imports/normalize_part_numbers"),
    ("POST", "/api/imports/reconcile_apply"),
    ("POST", "/api/imports/reconciliation_preview"),
    ("POST", "/api/kits"),
    ("POST", "/api/kits/<int:kit_id>/references"),
    ("POST", "/api/maps"),
    ("POST", "/api/models"),
    ("POST", "/api/parts"),
    ("POST", "/api/parts/<int:part_id>/files"),
    ("POST", "/api/placement_positions"),
    ("POST", "/api/placements"),
    ("POST", "/api/placements/<int:pl_id>/contributors"),
    ("POST", "/api/placements/<int:pl_id>/refine"),
    ("POST", "/api/placements/<int:pl_id>/refine_part"),
    ("POST", "/api/placements/merge"),
    ("POST", "/api/source_extracts"),
    ("POST", "/api/sources"),
    ("PUT", "/api/claims/<int:claim_id>"),
    ("PUT", "/api/image_families/<int:family_id>"),
    ("PUT", "/api/image_families/<int:family_id>/members/<int:member_id>"),
    ("PUT", "/api/image_links/<int:link_id>"),
    ("PUT", "/api/image_regions/<int:region_id>"),
    ("PUT", "/api/images/<int:image_id>"),
    ("PUT", "/api/kits/<int:kit_id>"),
    ("PUT", "/api/maps/<int:map_id>"),
    ("PUT", "/api/models/<int:model_id>"),
    ("PUT", "/api/parts/<int:part_id>"),
    ("PUT", "/api/placement_positions/<int:position_id>"),
    ("PUT", "/api/placements/<int:pl_id>"),
    ("PUT", "/api/source_extracts/<int:extract_id>"),
    ("PUT", "/api/sources/<int:source_id>"),
}


def actual_routes():
    routes = set()
    for rule in app.url_map.iter_rules():
        for method in rule.methods - {"HEAD", "OPTIONS"}:
            routes.add((method, str(rule)))
    return routes


def format_routes(routes):
    return "\n".join(f"  {method:6} {rule}" for method, rule in sorted(routes))


def main():
    actual = actual_routes()
    missing = EXPECTED_ROUTES - actual
    extra = actual - EXPECTED_ROUTES

    if missing or extra:
        lines = ["Route contract mismatch."]
        if missing:
            lines.append("\nMissing routes:")
            lines.append(format_routes(missing))
        if extra:
            lines.append("\nUnexpected routes:")
            lines.append(format_routes(extra))
        raise SystemExit("\n".join(lines))

    print(f"route_contract smoke test passed ({len(actual)} routes)")


if __name__ == "__main__":
    main()
