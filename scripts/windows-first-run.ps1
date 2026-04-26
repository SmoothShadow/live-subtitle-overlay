param(
    [switch]$SkipDiagnostics,
    [switch]$SkipDeviceChooser,
    [switch]$DiagnosticsOnly
)

$ErrorActionPreference = "Stop"

if (-not $IsWindows) {
    throw "This script is intended to run on Windows."
}

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    throw "Virtual environment not found at .venv. Create it first with: python -m venv .venv"
}

$envPath = Join-Path $repoRoot ".env"
if (-not (Test-Path $envPath)) {
    throw ".env not found. Create it from .env.example before running this script."
}

Push-Location $repoRoot
try {
    if (-not $SkipDiagnostics) {
        Write-Host "== Running startup diagnostics ==" -ForegroundColor Cyan
        & $venvPython -m live_subtitle_overlay --diagnostics
        if ($LASTEXITCODE -ne 0) {
            throw "Startup diagnostics failed. Fix the reported errors before launching the app."
        }
    }

    if ($DiagnosticsOnly) {
        exit 0
    }

    if (-not $SkipDeviceChooser) {
        Write-Host "== Opening loopback device chooser ==" -ForegroundColor Cyan
        & $venvPython -m live_subtitle_overlay --choose-device
        if ($LASTEXITCODE -ne 0) {
            throw "Device chooser failed."
        }
    }

    Write-Host "== Launching overlay ==" -ForegroundColor Cyan
    & $venvPython -m live_subtitle_overlay
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
