# build-windows.ps1 — Build a self-contained ReadComics Windows distribution.
#
# Requirements (must be installed before running):
#   - Python 3.10+ (https://www.python.org/downloads/) — add to PATH during install
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File build-windows.ps1
#
# Output:
#   dist\ReadComics\ReadComics.exe   (and all support files in the same folder)
#
# The resulting dist\ReadComics\ folder is fully self-contained.
# Zip it and distribute — no Python or browser installation needed.

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
try { $pyver = python --version 2>&1 } catch { $pyver = $null }
if (-not $pyver) {
    Write-Error "Python not found. Install Python 3.10+ from https://www.python.org/downloads/ and add it to PATH."
    exit 1
}
Write-Host "    Found: $pyver"

# ── 1. Create / reuse virtual environment ────────────────────────────────────
Write-Host "--> Setting up virtual environment..." -ForegroundColor Yellow
if (-not (Test-Path "$VenvDir\Scripts\activate.ps1")) {
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

# ── 4. Generate icon (.ico) ───────────────────────────────────────────────────
Write-Host "--> Generating icon..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "$ScriptDir\docs" | Out-Null
python - <<'PYEOF'
try:
    from PIL import Image, ImageDraw
    sizes = [16, 32, 48, 64, 128, 256]
    frames = []
    for size in sizes:
        img = Image.new('RGBA', (size, size), (30, 30, 46, 255))   # Catppuccin base
        d   = ImageDraw.Draw(img)
        m   = max(1, size // 8)
        r   = max(1, size // 6)
        # Comic page background
        d.rounded_rectangle([m, m, size - m, size - m], radius=r, fill=(137, 180, 250, 255))
        # Dark inner area (simulates open book)
        i = size // 4
        d.rectangle([i, i, size - i, size - i + size // 8], fill=(30, 30, 46, 255))
        # Three "text lines"
        lm, lw, lh = size // 3, size // 3, max(1, size // 16)
        for row in range(3):
            y = i + size // 6 + row * (lh + max(1, size // 20))
            d.rectangle([lm, y, lm + lw, y + lh], fill=(137, 180, 250, 200))
        frames.append(img)
    frames[0].save('docs/icon.ico', format='ICO',
                   sizes=[(s, s) for s in sizes],
                   append_images=frames[1:])
    print('    Icon saved: docs/icon.ico')
except Exception as e:
    print(f'    Warning: icon generation failed ({e}) — building without icon')
    # Write an empty placeholder so PyInstaller does not error
    open('docs/icon.ico', 'wb').close()
PYEOF

# ── 5. Run PyInstaller ────────────────────────────────────────────────────────
Write-Host "--> Running PyInstaller..." -ForegroundColor Yellow
Set-Location $ScriptDir
pyinstaller readcomics.spec --noconfirm

# ── 6. Copy Playwright Firefox into the dist folder ───────────────────────────
Write-Host "--> Copying Firefox browsers into dist..." -ForegroundColor Yellow
$destBrowsers = "$DistDir\browsers"
if (Test-Path $destBrowsers) { Remove-Item -Recurse -Force $destBrowsers }
Copy-Item -Recurse $PwBrowsers $destBrowsers

# ── 7. Copy VERSION for display ───────────────────────────────────────────────
Copy-Item "$ScriptDir\VERSION" "$DistDir\VERSION" -Force

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Build complete!" -ForegroundColor Green
Write-Host "  EXE : $DistDir\ReadComics.exe" -ForegroundColor Green
Write-Host "  Size: $([math]::Round((Get-ChildItem $DistDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB)) MB" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "To distribute: zip the entire dist\ReadComics\ folder." -ForegroundColor Cyan
Write-Host ""
