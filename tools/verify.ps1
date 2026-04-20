<#
tools/verify.ps1

Run the local verification checks for this repo:
- Python syntax compilation
- placement_positions smoke test

The script prefers an explicitly provided interpreter, then the active `python`,
then falls back to the resolved interpreter inside `therpf-scraper` if available.

Examples:
  .\tools\verify.ps1
  .\tools\verify.ps1 -PythonExe "C:\path\to\python.exe"
  .\tools\verify.ps1 -SkipSmoke
#>

param(
  [string]$PythonExe = "",
  [string]$CondaEnv = "therpf-scraper",
  [switch]$SkipSmoke
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $ProjectRoot "backend"
$DbPath = Join-Path $BackendDir "data\ilm1300.db"
$DbWalPath = "$DbPath-wal"
$DbShmPath = "$DbPath-shm"
$CompileTargets = @(
  (Join-Path $BackendDir "app.py"),
  (Join-Path $BackendDir "import_spreadsheets.py"),
  (Join-Path $BackendDir "classify_kits.py"),
  (Join-Path $BackendDir "smoke_test_placement_positions.py")
)

$script:PythonPrefix = @()
$script:PythonLabel = ""
$script:SelectedPythonExitCode = 0

function Invoke-SelectedPython {
  param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PythonArgs
  )

  if (-not $script:PythonPrefix -or $script:PythonPrefix.Count -eq 0) {
    throw "Python interpreter not configured."
  }

  if ($script:PythonPrefix.Count -gt 1) {
    & $script:PythonPrefix[0] @($script:PythonPrefix[1..($script:PythonPrefix.Count - 1)]) @PythonArgs
  } else {
    & $script:PythonPrefix[0] @PythonArgs
  }

  $script:SelectedPythonExitCode = $LASTEXITCODE
}

function Test-PythonCandidate {
  param(
    [string[]]$Prefix,
    [string]$Label
  )

  $previousPrefix = $script:PythonPrefix
  $previousLabel = $script:PythonLabel

  try {
    $script:PythonPrefix = $Prefix
    $script:PythonLabel = $Label
    Invoke-SelectedPython "-c" "import flask, openpyxl" *> $null
    return ($script:SelectedPythonExitCode -eq 0)
  } catch {
    return $false
  } finally {
    $script:PythonPrefix = $previousPrefix
    $script:PythonLabel = $previousLabel
  }
}

function Resolve-CondaPython {
  $condaCmd = Get-Command conda -ErrorAction SilentlyContinue
  if (-not $condaCmd) {
    return $null
  }

  try {
    $resolved = & conda run -n $CondaEnv python -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -ne 0) {
      return $null
    }
    $candidate = ($resolved | Select-Object -Last 1).Trim()
    if ($candidate -and (Test-Path $candidate)) {
      return $candidate
    }
  } catch {
    return $null
  }

  return $null
}

function Select-Python {
  if ($PythonExe) {
    if (-not (Test-Path $PythonExe)) {
      throw "Specified Python interpreter not found: $PythonExe"
    }
    if (-not (Test-PythonCandidate -Prefix @($PythonExe) -Label $PythonExe)) {
      throw "Specified Python interpreter does not have the required dependencies: $PythonExe"
    }
    $script:PythonPrefix = @($PythonExe)
    $script:PythonLabel = $PythonExe
    return
  }

  $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
  if ($pythonCmd -and (Test-PythonCandidate -Prefix @("python") -Label "python")) {
    $script:PythonPrefix = @("python")
    $script:PythonLabel = "python"
    return
  }

  $condaPython = Resolve-CondaPython
  if ($condaPython -and (Test-PythonCandidate -Prefix @($condaPython) -Label $condaPython)) {
    $script:PythonPrefix = @($condaPython)
    $script:PythonLabel = $condaPython
    return
  }

  throw "No suitable Python interpreter found. Use -PythonExe or activate/install an environment with Flask and openpyxl."
}

Write-Host "Selecting Python interpreter..."
Select-Python
Write-Host "Using $script:PythonLabel" -ForegroundColor Cyan

Write-Host ""
Write-Host "Compiling Python files..."
$compileHelperPath = Join-Path ([System.IO.Path]::GetTempPath()) ("nuhope_compile_{0}.py" -f ([System.Guid]::NewGuid().ToString("N")))
$compileSnippet = @"
import sys
import tokenize

for path in sys.argv[1:]:
    with tokenize.open(path) as handle:
        source = handle.read()
    compile(source, path, "exec")
"@

try {
  Set-Content -LiteralPath $compileHelperPath -Value $compileSnippet -Encoding UTF8
  Invoke-SelectedPython $compileHelperPath @CompileTargets
  if ($script:SelectedPythonExitCode -ne 0) {
    Write-Host "Compile checks failed." -ForegroundColor Red
    exit $script:SelectedPythonExitCode
  }
} finally {
  if (Test-Path $compileHelperPath) {
    Remove-Item -LiteralPath $compileHelperPath -Force
  }
}
Write-Host "Compile checks passed." -ForegroundColor Green

if ($SkipSmoke) {
  Write-Host ""
  Write-Host "Smoke tests skipped." -ForegroundColor Yellow
  exit 0
}

Write-Host ""
Write-Host "Running placement_positions smoke test..."
$dbBackupPath = $null
if (Test-Path $DbPath) {
  $dbBackupPath = Join-Path ([System.IO.Path]::GetTempPath()) ("ilm1300.verify.{0}.db" -f ([System.Guid]::NewGuid().ToString("N")))
  Copy-Item $DbPath $dbBackupPath -Force
}

try {
  Invoke-SelectedPython (Join-Path $BackendDir "smoke_test_placement_positions.py")
  if ($script:SelectedPythonExitCode -ne 0) {
    Write-Host "Smoke test failed." -ForegroundColor Red
    exit $script:SelectedPythonExitCode
  }
} finally {
  foreach ($sidecar in @($DbWalPath, $DbShmPath)) {
    if (Test-Path $sidecar) {
      Remove-Item -LiteralPath $sidecar -Force
    }
  }
  if ($dbBackupPath -and (Test-Path $dbBackupPath)) {
    Copy-Item $dbBackupPath $DbPath -Force
    Remove-Item -LiteralPath $dbBackupPath -Force
  }
}

Write-Host "Smoke test passed." -ForegroundColor Green
