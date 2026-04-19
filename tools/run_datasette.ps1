#!/usr/bin/env pwsh
# Run Datasette against the local SQLite DB (PowerShell script)
# Usage: open PowerShell, then: ./tools/run_datasette.ps1

param()

Write-Host "Activating conda environment 'therpf-scraper' (if available)..."
try {
  & conda activate therpf-scraper
} catch {
  Write-Host "(conda activate failed or not available - ensure you run this in the intended env)" -ForegroundColor Yellow
}

Write-Host "Installing or upgrading Datasette (pip)..."
python -m pip install --upgrade datasette | Out-Null

$dbPath = Join-Path -Path "$PSScriptRoot\..\backend\data" -ChildPath "ilm1300.db"
if (-not (Test-Path $dbPath)) {
  Write-Host "Database not found at $dbPath" -ForegroundColor Red
  exit 1
}

Write-Host "Starting Datasette serving $dbPath on http://127.0.0.1:8001"
Write-Host "Press Ctrl+C to stop."

datasette serve $dbPath --host 127.0.0.1 --port 8001
