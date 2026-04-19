## Datasette — quick setup

Datasette provides an instant web UI for exploring SQLite databases.

1) From the workspace root, run the helper script (PowerShell):

```powershell
./tools/run_datasette.ps1
```

2) Open http://127.0.0.1:8001 in your browser.

Notes:
- The script installs/updates `datasette` via `pip` in the active Python environment.
- If you prefer a virtualenv/conda workflow, activate that environment first.
- For production or remote access, run `datasette` with TLS and proper access controls.
