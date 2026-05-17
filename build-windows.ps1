# build-windows.ps1 — Build a self-contained ReadComics Windows distribution.
#
# Requirements (must be installed before running):
#   Python 3.10+ from https://www.python.org/downloads/  (check "Add to PATH")
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File build-windows.ps1
#
# Output:
#   dist\ReadComics\ReadComics.exe   (plus all support files in the same folder)
#
# Distribute by zipping dist\ReadComics\ — no Python or browser install needed.

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ScriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$Version    = (Get-Content "$ScriptDir\VERSION").Trim()
$VenvDir    = "$ScriptDir\venv-win"
$PwBrowsers = "$ScriptDir\win-build\browsers"
$DistDir    = "$ScriptDir\dist\ReadComics"

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  ReadComics v$Version — Windows Build"      -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ── 0. Verify Python ──────────────────────────────────────────────────────────
Write-Host "--> Checking Python..." -ForegroundColor Yellow
try   { $pyver = (python --version 2>&1).ToString().Trim() }
catch { $pyver = "" }
if (-not $pyver) {
    Write-Error "Python not found. Install Python 3.10+ from https://www.python.org/downloads/ and add it to PATH."
    exit 1
}
Write-Host "    Found: $pyver"

# ── 1. Create / reuse virtual environment ────────────────────────────────────
Write-Host "--> Setting up virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path "$VenvDir\Scripts\Activate.ps1")) {
    python -m venv $VenvDir
}
& "$VenvDir\Scripts\Activate.ps1"

# ── 2. Install Python dependencies ───────────────────────────────────────────
Write-Host "--> Installing Python packages..." -ForegroundColor Yellow
pip install --quiet --upgrade pip
pip install --quiet -r "$ScriptDir\requirements.txt"
pip install --quiet pyinstaller

# ── 3. Download Playwright Firefox ────────────────────────────────────────────
Write-Host "--> Installing Playwright Firefox (this may take a few minutes)..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $PwBrowsers | Out-Null
$env:PLAYWRIGHT_BROWSERS_PATH = $PwBrowsers
playwright install firefox

# ── 4. Generate icon ─────────────────────────────────────────────────────────
Write-Host "--> Generating icon..." -ForegroundColor Yellow
python "$ScriptDir\build-icon.py"

# ── 5. Run PyInstaller ────────────────────────────────────────────────────────
Write-Host "--> Running PyInstaller..." -ForegroundColor Yellow
Set-Location $ScriptDir
pyinstaller readcomics.spec --noconfirm

# ── 6. Copy Playwright Firefox into the dist folder ───────────────────────────
Write-Host "--> Copying Firefox browsers into dist..." -ForegroundColor Yellow
$destBrowsers = "$DistDir\browsers"
if (Test-Path $destBrowsers) { Remove-Item -Recurse -Force $destBrowsers }
Copy-Item -Recurse $PwBrowsers $destBrowsers

# ── 7. Copy VERSION ───────────────────────────────────────────────────────────
Copy-Item "$ScriptDir\VERSION" "$DistDir\VERSION" -Force

# ── 8. Report ─────────────────────────────────────────────────────────────────
$sizeMB = [math]::Round(
    (Get-ChildItem $DistDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
)
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Build complete!" -ForegroundColor Green
Write-Host "  EXE : $DistDir\ReadComics.exe" -ForegroundColor Green
Write-Host "  Size: ${sizeMB} MB" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "To distribute: zip the entire dist\ReadComics\ folder." -ForegroundColor Cyan
Write-Host ""
