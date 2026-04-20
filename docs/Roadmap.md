# ILM Van Nuys - Kit-Bash Research Platform
### Project Roadmap · NuHopeTools1300 · April 2026

---

## Vision

A research platform and eventual public database documenting the kit-bashed parts used on ILM studio models built in Van Nuys during the original Star Wars movie - starting with the 5-foot Millennium Falcon. The goal is to make the cross-model connections visible, credit the researchers who found them, and gradually shift a fragmented, knowledge-hoarding community toward open sharing.

---

## Strategic approach

- Build the research infrastructure first - tools that make our own work better today.
- Don't ask the community to change behaviour - build something worth pointing at.
- Attribution baked in from day one - every find credits its identifier, permanently.
- The cross-model connection graph is the unique value.
- Define one shared UI language early - current tools can stay sketch-like, but they should converge on a common paradigm before public-facing polish.

---

## Product language

Current interfaces are useful prototypes, not yet a coherent system. The roadmap should treat shared UI thinking as part of the architecture, not as a late polish pass.

- Core layout: library / canvas / inspector.
- Core objects: evidence / entity / link.
- Core modes: browse / inspect / annotate / relate.
- Shared primitives: cards, chips, confidence states, provenance badges, timeline markers, filters, and right-side detail panels.
- Shared intent: every tool should help move from raw evidence to interpreted claim without losing provenance.

This is not a visual cleanup task. It is part of the information architecture.

Reference:

- See [ProductUIArchitecture.md](./ProductUIArchitecture.md) for the target shell, object model, rebuild order, and the explicit decision to stop investing major polish effort into the legacy fragmented UI.
- See [WorkbenchSlice_ImageRegionClaim.md](./WorkbenchSlice_ImageRegionClaim.md) for the first concrete vertical slice to rebuild.
- See [CoreResearchWorkflows.md](./CoreResearchWorkflows.md) for the workflow-level framing that should guide implementation choices.

---

## Phase 1 - Now · Research infrastructure
*Private · you + few enthusiasts*

| # | Step | Description | Tag |
|---|------|-------------|-----|
| 1 | **Flask backend + SQLite database** | Shared persistent store. Imports existing spreadsheets. Replaces localStorage across all tools. Runs locally to start. | Start here |
| 2 | **Image <-> data linking** | The core missing link. Part -> kit scans. Falcon location -> all reference images showing it. Google Drive integration. | Core |
| 3 | **Shared design system + UI paradigm** | Define the common theme, panel grammar, interaction model, and entity presentation across tools. `library / canvas / inspector` is the likely baseline, with consistent treatment of evidence, entities, links, confidence, and provenance. | Foundation |
| 4 | **Connect existing tools to backend** | ImageAnnotator + image timeline all read/write from the shared database. Work already done - just rewired. | Upgrade |
| 5 | **Attribution baked in from day one** | Every find credits its identifier. Permanent, visible, citable. The key to unlocking expert contribution later. | Strategic |

---

## Current stability assessment

The project is on a good track conceptually.

The risk is not imminent collapse.

The risk is continued growth by patching and duplication faster than the implementation is consolidated.

Current positives:

- the product thesis is clear
- the evidence-first schema direction is coherent
- `library / canvas / inspector` is a strong target shell
- the newer workbench and map-correction work are moving in the right direction

Current growth risks:

- schema truth is split across `schema.sql`, runtime bootstrap in `backend/app.py`, and draft migrations
- frontend request, auth, and local state wiring is duplicated across multiple standalone HTML apps
- persistence is still split between backend records and browser-local tool storage
- runtime artifacts and generated data live beside source in the repo
- verification coverage is still light relative to the amount of surface area

Planning implication:

- do not treat the current state as failing
- do treat the next pass as a consolidation pass, not just another feature pass

---

## Immediate stabilization priorities

These items should happen before widening scope much further.

### 1. Freeze the legacy UI surface

- treat `frontend.html` and older one-off tools as maintenance-only surfaces
- keep `workbench.html` and `map_workbench.html` as the active operator shells
- avoid adding major new product concepts to legacy entry points
- do not spend time proactively refactoring legacy surfaces during the current stabilization pass
- touch legacy surfaces only for concrete bug fixes, compatibility shims, or migration support

### 2. Extract one shared frontend API/auth layer

- move API base handling, auth headers, request helpers, and error handling into shared frontend code
- stop mixing header-based auth and query-param auth across tools
- reduce each HTML surface to workflow-specific UI rather than infrastructure duplication

### 3. Choose one schema evolution path

- make `schema.sql` plus ordered migrations the source of truth
- treat runtime schema patching in `backend/app.py` as a temporary compatibility bridge, not the long-term mechanism
- avoid introducing new core entities in docs and code through separate parallel tracks

### 4. Clean repo/runtime boundaries

- add a real `.gitignore`
- stop versioning live database files, backups, uploads, caches, and generated bulk artifacts
- keep research corpora and runtime state accessible without making them part of normal source-control churn

### 5. Add a repeatable verification harness

- keep the existing smoke-test mindset, but formalize it
- add a simple local verification script that runs compile checks plus core smoke tests
- expand smoke coverage around image, region, claim, and map-position workflows before major new feature work

### 6. Make an explicit call on the next entity layer

- either wire `physical_objects`, `locations`, and `events` properly in the next active phase
- or mark them as intentionally deferred and stop partial seepage into implementation
- avoid the half-adopted middle state where concepts exist in architecture docs but not in the operating model

---

## Current next-pass UX priorities

The current workbench color scheme and overall `library / canvas / inspector` layout are worth keeping. The immediate focus should be on making browsing and inspection faster, not on rethinking the visual direction again.

- treat `image groups` as stable enough for now and stop polishing them endlessly unless a real research blocker appears
- keep image-group terminology simple in the UI:
  - `Image group`
  - `Default image in list`
  - `Images in group`
- improve image browsing with keyboard navigation, previous / next affordances, and a quick gallery / filmstrip
- collapse duplicates, crops, and alternate resolutions into logical image families rather than exposing every raw file as a top-level row
- add explicit image intake and removal actions in the workbench, with safe wording and guardrails so `add image`, `detach from family`, `delete family`, and `delete image record` are not conflated
- keep primary editing controls close to the selected object instead of forcing everything into the far-right inspector
  - list + compact local editor is often the better pattern
  - right-side panels should lean toward secondary detail, provenance, history, and linked evidence
- treat `add image`, `edit image record`, and `delete image` as the next real lifecycle baseline for evidence handling rather than as afterthought admin functions
- improve canvas ergonomics with cursor-centered zoom, robust two-axis pan, and controls that stay inside the accessible work area
- shorten list-facing image names while keeping fuller research descriptions available in secondary UI
- surface kit suggestions directly from region labels where exact or strong matches exist
- add a lightweight kit browser so users can enter the research space from kits as well as from images
- add batch matching from region labels on map-style images to `kits` in the database
- add OCR as the next extraction layer for images where relevant text is visible but not yet entered as region labels
- add manual position correction for imported map/location geometry instead of destructively editing imported coordinates
- implement a dedicated position-record layer for map correction:
  - `placement` stays conceptual
  - `map` should be treated as one concrete image-backed working surface
  - `placement_positions` stores imported/manual/candidate geometry plus history
  - map correction should become its own surface, not an image-workbench afterthought
- user-facing terminology should likely shift away from `placement` toward `object` + `position`
  - reason: `placement` sounds already located
  - keep backend/schema naming stable for now to avoid churn
  - revisit schema renaming only after the concept fully settles

Reference:

- See [ImageFamiliesAndPositionCorrection.md](./ImageFamiliesAndPositionCorrection.md)
- See [PositionCorrectionImplementation.md](./PositionCorrectionImplementation.md)

---

## Phase 2 - Next · Community database
*Semi-public · trusted contributors*

| # | Step | Description | Tag |
|---|------|-------------|-----|
| 6 | **Cross-model connection explorer** | The unique value prop. "This Tamiya kit also appears on the Star Destroyer and X-Wing." Connections nobody else shows. | Differentiator |
| 7 | **Search + filter interface** | Find by kit, model, part number, location. The public-facing database experience starts here. | Public-facing |
| 8 | **Contribution workflow** | Simple submit form for trusted contributors. Low friction, clearly attributed. No account required to start. | Community |

---

## Phase 3 - Later · Public platform
*Open · community gravity*

| # | Step | Description | Tag |
|---|------|-------------|-----|
| 9 | **Visual connection graph** | Interactive web of models, kits and shared parts. The 'big picture' made visible to everyone. | Showcase |
| 10 | **Open contribution + moderation** | Community submissions with review. The culture shift toward open sharing happens here - if the platform earned it. | Long game |

---

---

## Hosting & Deployment

High-level hosting plan for the project (integrated with roadmap phases):

- **Source & CI**: keep code on GitHub (frontend + backend). Use GitHub Actions for linting, tests, and deployment pipelines. Keep secrets in GitHub Secrets or a dedicated secret manager.
- **Frontend (static)**: publish the built static site to GitHub Pages, Cloudflare Pages, or S3 + CloudFront. The frontend should be buildable as static assets and read the API base URL from a small config or environment variable injected at deploy time.
- **Backend (API)**: run the Flask API in a container (Docker) on a managed host (Render, Fly, or a VPS). Serve with a production WSGI server behind HTTPS; use environment variables for configuration and credentials.
- **Database**: SQLite for local/dev; migrate to a managed Postgres (Supabase, Render Postgres, AWS RDS) in production for reliability, backups, and migrations.
- **Images / storage**: store image files in cloud object storage (S3/GCS) with CDN in front for performance. If Google Drive is required for private content, store Drive IDs in the DB and proxy access through the backend using a service account to avoid public-sharing problems.
- **Image linking**: use the existing `images` + `image_links` tables to store metadata and relationships; backend endpoints should return signed URLs or proxied bytes as required.
- **Backups & monitoring**: schedule automated DB backups to object storage, add a health endpoint (already `/api/health`), and wire basic log/alerting for errors and uptime.

**Minimal recommended stack:** GitHub repo -> GitHub Actions -> Docker image -> Render/Fly (Flask + Postgres) -> Cloudflare Pages / GitHub Pages (static frontend) -> Images on S3/GCS + CDN.

---

### Integrated hosting plan (from hosting-plan.md)

## NuHopeTools - Hosting Plan

### Architecture overview

| Part | Service | Notes |
|---|---|---|
| Frontend | GitHub Pages | Already in repo, free, zero config |
| Backend (Flask) | Railway or Render | Persistent container, supports SQLite |
| Images | Google Drive | Shared folder, direct link URLs |
| Access control | Google Sheets + Apps Script | Private sheet, no external auth service |
| Data import | Local script | `import_spreadsheets.py` run manually or on deploy |

**Free tier is viable for all services** at low/internal traffic levels.

---

### Frontend - GitHub Pages

- Serve `index.html` and `tools/*.html` directly from the repo
- Already set up at `NuHopeTools1300.github.io`
- No changes needed - just keep pushing to `main`

---

### Backend - Railway or Render

Both support Python/Flask with persistent disk storage (important for the SQLite `.db` file).

**Railway** is the easier starting point:
1. Connect your GitHub repo
2. Set start command: `flask run --host=0.0.0.0 --port=8080`
3. Add environment variables (e.g. `FLASK_ENV=production`)
4. Persistent volume for `/data/ilm1300.db`

**Render** is similar but has a clearer free-tier dashboard.

> Warning: free tiers on both services spin down after about 15 minutes of inactivity. The first request after idle takes a few seconds. A paid plan keeps it always on.

---

### Image storage - Google Drive

- Create a shared folder for box art, timeline images, etc.
- Set sharing to "Anyone with the link can view"
- Reference images by their direct Drive URL in the database
- No bandwidth costs at internal-use scale

---

### Access control - Google Sheets + Apps Script

#### The Sheet (private)

Keep a Google Sheet with one row per user:

| email | token | active | role |
|---|---|---|---|
| user@example.com | abc123xyz | TRUE | viewer |
| admin@example.com | def456uvw | TRUE | admin |

To revoke access: set `active` to `FALSE`. To add someone: paste a new row. No code changes needed.

#### The Apps Script (Web App)

Publish as a Web App with access set to **"Anyone"** (the URL is useless without a valid token).

```javascript
// Google Apps Script - Tools > Script editor, then Deploy > Web App
function doGet(e) {
	const token = e.parameter.token;
	const sheet = SpreadsheetApp.getActiveSpreadsheet()
									.getSheetByName("users");
	const data = sheet.getDataRange().getValues();

	for (let i = 1; i < data.length; i++) {
		if (data[i][1] === token && data[i][2] === true) {
			return ContentService.createTextOutput(
				JSON.stringify({ ok: true, role: data[i][3] })
			).setMimeType(ContentService.MimeType.JSON);
		}
	}
	return ContentService.createTextOutput(
		JSON.stringify({ ok: false })
	).setMimeType(ContentService.MimeType.JSON);
}
```

#### Flask integration

Add a `require_auth` decorator that checks every protected route:

```python
import functools
import requests
from flask import jsonify, request

SCRIPT_URL = "https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec"

def require_auth(f):
	@functools.wraps(f)
	def wrapper(*args, **kwargs):
		token = request.headers.get("X-Token")
		r = requests.get(SCRIPT_URL, params={"token": token}, timeout=3)
		if not r.ok or not r.json().get("ok"):
			return jsonify({"error": "unauthorized"}), 401
		return f(*args, **kwargs)
	return wrapper

@app.route("/api/data")
@require_auth
def get_data():
	...
```

#### Frontend

Store the user's token in `localStorage` and send it with every API request:

```javascript
const token = localStorage.getItem("nuHopeToken");

fetch("https://your-backend.railway.app/api/data", {
	headers: { "X-Token": token }
});
```

Users receive their token from you directly (e.g. via email). No login page required initially.

---

### Optional: magic link login

If you want email-based login instead of pre-shared tokens, extend the Apps Script to:
1. Accept an email address
2. Generate a time-limited token, write it to the Sheet
3. Send it to the user via `MailApp.sendEmail()`

The Flask side stays the same - it just checks the token.

---

### Summary checklist

- [ ] Push frontend to GitHub Pages (already done)
- [ ] Deploy Flask app to Railway or Render with persistent volume
- [ ] Move `ilm1300.db` to persistent mount path
- [ ] Create Google Drive folder for images, update DB references
- [ ] Create Google Sheet with user list
- [ ] Paste Apps Script, deploy as Web App, copy script URL
- [ ] Add `SCRIPT_URL` as environment variable in Railway/Render
- [ ] Add `require_auth` decorator to protected Flask routes
- [ ] Distribute tokens to initial users

---

## Data model

Seven core tables. Everything connects through `placements` - the join between a kit part and a specific location on a specific model.

| Table | Purpose |
|-------|---------|
| `kits` | Source model kits - brand, scale, name, serial number, Scalemates link, scan links. |
| `parts` | Individual parts within a kit. Self-referencing FK for cast/recast relationships. |
| `models` | ILM studio models - Falcon, X-Wing, Star Destroyer, etc. |
| `placements` | The heart of the system. Links a part to a location on a model, with copy count and confidence level. |
| `maps` | Annotated map images of model sections. Each map links to a model. |
| `images` | All reference images - model shop, exhibition, kit scans. Tagged, dated, sourced. |
| `image_links` | Connects images to any entity (kit / part / placement / model). One image, many connections. |
| `contributors` | Researcher handles and forum profiles. Attribution FK target. |

### Key design decisions

- **`placements`** is where the magic happens - one part can link to the Falcon, the Star Destroyer, and the X-Wing simultaneously. That's the cross-model query nobody else can run.
- **`image_links`** solves the core missing link - one exhibition photo can simultaneously relate to a model, specific placements visible in it, and the kit parts identified there.
- **`cast_source_part_id`** is a self-referencing FK on `parts` - captures the cast/recast relationships between parts shared across models.
- **`confidence`** on placements captures `confirmed` / `probable` / `speculative` - critical for research integrity.

---

## Saved for later - not forgotten

**Box art extractor** - a deep archaeology tool for identifying which vintage kit boxes ILM purchased. Useful for the 'which kits were originally used' historical research, but low community value and not on the critical path. Revisit after Phase 1 is solid.

---

## North star

> Build so well it becomes the obvious place to share *to* - don't ask people to change their habits, give them a destination worth pointing at.

---

*NuHopeTools1300 · Working document · April 2026*
