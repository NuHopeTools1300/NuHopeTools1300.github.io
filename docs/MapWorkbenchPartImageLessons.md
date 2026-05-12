# Map Workbench Part Image Lessons

Date: 2026-05-01

## Root Cause

PartList images were imported correctly, but they entered the system as `part_files.url`
records served by `/api/part_images/<filename>`. The map workbench was built around
two different image surfaces:

- kit thumbnails via `kits.thumbnail_url`
- research/evidence images via the `images` and `image_links` tables

That meant placed/refined part records could be validly linked to a kit and part while
still having no visible image in the map workbench. The missing bridge was API payload
support for `part_files` on placement records and UI rendering for those references.

The follow-up debugging also got noisy because the Flask backend was started as a
foreground verification command. `backend/app.py` is a long-running server entry point,
so running it directly inside an agent turn blocks until interrupted.

## What To Check First

1. Confirm the selected map record has a part-level placement, not only a kit-level
   placement.
2. Confirm that placement's `part_id` has non-empty `part_files.url` rows.
3. Confirm those URLs are image-like, especially `/api/part_images/...`.
4. Confirm `/api/placements/<id>` returns the part file data needed by the UI.
5. Confirm the UI renders from the same image surface the data uses.

## Prevention Checklist

- Treat `images` and `part_files` as separate image sources unless they are explicitly
  normalized.
- When adding imported part images, expose a lightweight placement summary field such
  as `part_reference_url` for list views.
- For detail views, include the full `part_files` array for part-level placements.
- Do not use URL-only dedupe if one image file can legitimately support more than one
  part association; prefer `(part_id, url)`.
- Avoid one-off debug scripts in the repo. Use inline shell/Python probes unless the
  script is intended to stay.
- Never run `python backend/app.py` as a foreground verification step in an agent turn.
  Use a bounded test client check, a hidden/background server with a health timeout, or
  an already-running local server.
- If a UI image is not visible, verify the API payload before changing CSS or layout.

## Known Good Probe

This kind of bounded probe is enough to prove the backend data path without starting a
long-running server:

```powershell
@'
from backend.app import app
with app.test_client() as client:
    res = client.get('/api/placements?map_id=8')
    payload = res.get_json()
    rows = payload.get('data') or []
    print(len([r for r in rows if r.get('part_reference_url')]))
'@ | & 'C:\Users\gunkel\.conda\envs\therpf-scraper\python.exe' -
```
