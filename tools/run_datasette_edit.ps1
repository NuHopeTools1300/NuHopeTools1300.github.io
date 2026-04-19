<#
tools/run_datasette_edit.ps1

Backup the SQLite DB, ensure Datasette and the edit plugin are installed,
and run Datasette in the current active Python environment.

Usage (PowerShell):
  conda activate therpf-scraper
  .\tools\run_datasette_edit.ps1

#>

param(
  [string]$DbPath = "backend/data/ilm1300.db",
  [string]$BindHost = '127.0.0.1',
  [int]$Port = 8001
)

if (-not (Test-Path $DbPath)) {
  Write-Error "Database not found: $DbPath"
  exit 1
}

$ts = Get-Date -Format "yyyyMMddHHmmss"
$bak = "$DbPath.bak.$ts"
Copy-Item $DbPath $bak -Force
Write-Host "Backup created: $bak"

Write-Host "Ensuring datasette and datasette-edit-rows are installed in the active Python environment..."
python -m pip install --upgrade datasette datasette-edit-rows

Write-Host "Starting Datasette. Stop the Flask app first to avoid SQLite WAL conflicts."
Write-Host "Open http://$BindHost`:$Port in your browser. Ctrl+C to stop." -ForegroundColor Cyan

python -m datasette serve "$DbPath" --host $BindHost --port $Port --reload
