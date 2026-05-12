"""
ILM Van Nuys Kit-Bash Research Platform
Flask backend — Phase 1
"""

from flask import Flask, request, send_from_directory
from flask_cors import CORS
try:
    from .api_utils import ok, rows_to_list
    from .blueprints.catalog import catalog_bp
    from .blueprints.evidence import evidence_bp
    from .blueprints.imports import imports_bp
    from .blueprints.placements import placements_bp
    from .blueprints.research import research_bp
    from .config import DB_PATH, MAX_CONTENT_LENGTH, PART_IMAGES_DIR, UPLOAD_DIR
    from .db import close_db, get_db
    from .schema_bootstrap import init_db
except ImportError:
    from api_utils import ok, rows_to_list
    from blueprints.catalog import catalog_bp
    from blueprints.evidence import evidence_bp
    from blueprints.imports import imports_bp
    from blueprints.placements import placements_bp
    from blueprints.research import research_bp
    from config import DB_PATH, MAX_CONTENT_LENGTH, PART_IMAGES_DIR, UPLOAD_DIR
    from db import close_db, get_db
    from schema_bootstrap import init_db

app = Flask(__name__)
CORS(app)   # allow GitHub Pages (or any origin) to call this API


@app.after_request
def add_local_browser_cors_headers(response):
    # Browsers may preflight localhost/private-network requests from file:// or
    # other non-standard local origins and require this explicit opt-in.
    if request.headers.get('Access-Control-Request-Private-Network') == 'true':
        response.headers['Access-Control-Allow-Private-Network'] = 'true'
    return response

app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.teardown_appcontext(close_db)
app.register_blueprint(catalog_bp)
app.register_blueprint(evidence_bp)
app.register_blueprint(imports_bp)
app.register_blueprint(placements_bp)
app.register_blueprint(research_bp)


# ── STATIC FILES ─────────────────────────────────────────────────
# Serve uploaded images. The tools themselves are served by GitHub Pages
# (or directly as files); this only covers locally-uploaded images.

@app.get('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.get('/api/part_images/<path:filename>')
def part_image_file(filename):
    """Serve images imported from PartList_private.zip."""
    return send_from_directory(PART_IMAGES_DIR, filename)


# ── HEALTH ────────────────────────────────────────────────────────

@app.get('/api/health')
def health():
    db = get_db()
    tables = rows_to_list(db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall())
    counts = {}
    for t in tables:
        n = t['name']
        counts[n] = db.execute(f"SELECT COUNT(*) as c FROM {n}").fetchone()['c']
    return ok(tables=[t['name'] for t in tables], counts=counts)





if __name__ == '__main__':
    init_db()
    print("\n  ILM Van Nuys Research Platform")
    print("  ================================")
    print(f"  API:  http://localhost:5000/api/health")
    print()
    print("  Endpoints:")
    print("    GET  /api/health")
    print("    GET  /api/kits                ?q=  &brand=")
    print("    GET  /api/kits/<id>")
    print("    POST /api/kits")
    print("    PUT  /api/kits/<id>")
    print("    GET/POST/DELETE /api/kits/<id>/references")
    print("    GET  /api/parts               ?kit_id=  &q=")
    print("    GET  /api/parts/<id>")
    print("    POST /api/parts")
    print("    PUT  /api/parts/<id>")
    print("    POST/DELETE /api/parts/<id>/files")
    print("    GET  /api/models")
    print("    GET  /api/models/<slug>")
    print("    POST /api/models")
    print("    GET/POST /api/maps            ?model_id=")
    print("    GET  /api/placements          ?model_id=  &kit_id=  &map_id=  &confidence=")
    print("    GET  /api/placements/<id>")
    print("    POST /api/placements")
    print("    PUT  /api/placements/<id>")
    print("    DELETE /api/placements/<id>")
    print("    POST/DELETE /api/placements/<id>/contributors")
    print("    GET  /api/connections         (cross-model)")
    print("    GET  /api/cast_assemblies")
    print("    GET  /api/cast_assemblies/<id>")
    print("    POST /api/cast_assemblies")
    print("    POST /api/cast_assemblies/<id>/parts")
    print("    GET  /api/sources             ?q=  &source_type=")
    print("    GET  /api/sources/<id>")
    print("    POST /api/sources")
    print("    PUT  /api/sources/<id>")
    print("    GET  /api/source_extracts     ?source_id=  &extract_type=  &author_handle=  &q=")
    print("    GET  /api/source_extracts/<id>")
    print("    POST /api/source_extracts")
    print("    PUT  /api/source_extracts/<id>")
    print("    GET  /api/image_families      ?image_id=  &q=")
    print("    GET  /api/image_families/<id>")
    print("    POST /api/image_families")
    print("    PUT  /api/image_families/<id>")
    print("    DELETE /api/image_families/<id>")
    print("    POST /api/image_families/<id>/members")
    print("    PUT  /api/image_families/<id>/members/<member_id>")
    print("    DELETE /api/image_families/<id>/members/<member_id>")
    print("    GET  /api/images              ?entity_type=  &entity_id=  &image_type=  &source_id=  &family_id=  &collapse_family=1  &tag=  &q=")
    print("    GET  /api/images/<id>")
    print("    POST /api/images              (JSON body or multipart file upload)")
    print("    PUT  /api/images/<id>")
    print("    DELETE /api/images/<id>")
    print("    GET  /api/image_regions       ?image_id=  &entity_type=  &entity_id=  &source_extract_id=")
    print("    GET  /api/image_regions/<id>")
    print("    POST /api/image_regions")
    print("    PUT  /api/image_regions/<id>")
    print("    DELETE /api/image_regions/<id>")
    print("    GET  /api/image_links         ?image_id=  OR  ?entity_type=&entity_id=")
    print("    POST /api/image_links")
    print("    PUT  /api/image_links/<id>")
    print("    DELETE /api/image_links/<id>")
    print("    POST/DELETE /api/images/<id>/tags")
    print("    GET  /api/contributors")
    print("    POST /api/contributors")
    print("    GET  /api/search              ?q=")
    print()
    # Disable the auto-reloader: frequent DB writes (SQLite WAL) can
    # trigger the reloader repeatedly. Keep debug=True for helpful
    # error pages but avoid use_reloader to stop continuous restarts.
    app.run(debug=True, use_reloader=False, port=5000)
