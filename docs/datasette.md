# Datasette - Database Browser Sidecar

Datasette is the current recommended sidecar for browsing the live SQLite database.

Role in this project:

- use it for raw operator visibility into the database before building custom CRUD UI
- browse `kits`, `parts`, `models`, `maps`, `placements`, `images`, `image_regions`, and `claims`
- run quick SQL to answer cleanup and reverse-lookup questions
- inspect relationships while keeping `workbench.html` and `map_workbench.html` focused on evidence and map workflows
- treat it as a private/local operator tool, not the public community interface

## Read-Only Browsing

From the workspace root, run the helper script:

```powershell
./tools/run_datasette.ps1
```

Open http://127.0.0.1:8001 in your browser.

Use this first when the question is "what is in the database?" or "how are these records connected?"

## Controlled Local Editing

For careful admin cleanup, use the editing helper:

```powershell
./tools/run_datasette_edit.ps1
```

This path is intentionally separate from normal browsing. It should create a backup before serving the editable database and should be used only for controlled local cleanup.

Editing rule:

- prefer repeatable cleanup scripts for known transformations
- use editable Datasette only when manual inspection is the safest way to decide
- do not use Datasette editing as the hidden source of truth for major schema or import changes

## Why Not Build This From Scratch Now?

The project needs database visibility immediately, but generic table browsing is not the unique product value.

Borrow Datasette for the commodity layer. Spend custom development effort on the project-specific layer:

- evidence-to-entity links
- placement/map pivots
- image region review
- provenance and confidence
- cross-model kit/part connections

Notes:

- `tools/run_datasette.ps1` installs/updates `datasette` via `pip` in the active Python environment.
- `tools/run_datasette_edit.ps1` also installs `datasette-edit-rows`.
- If you prefer a virtualenv/conda workflow, activate that environment first.
- For production or remote access, run Datasette with TLS and proper access controls. The current helper scripts are local-operator conveniences.
