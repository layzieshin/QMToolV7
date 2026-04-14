param(
    [switch]$Clean = $true,
    [switch]$RunSmoke = $false
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SpecFile = Join-Path $ProjectRoot "ui_mvp.spec"
$GuiEntry = Join-Path $ProjectRoot "interfaces/gui/main.py"

if (-not (Test-Path $SpecFile)) { throw "spec file not found: $SpecFile" }
if (-not (Test-Path $GuiEntry)) { throw "gui entry file not found: $GuiEntry" }

if ($Clean) {
    if (Test-Path (Join-Path $ProjectRoot "build")) { Remove-Item (Join-Path $ProjectRoot "build") -Recurse -Force }
    if (Test-Path (Join-Path $ProjectRoot "dist")) { Remove-Item (Join-Path $ProjectRoot "dist") -Recurse -Force }
}

python -m pip install pyinstaller
if ($LASTEXITCODE -ne 0) { throw "pyinstaller installation failed with exit code $LASTEXITCODE" }

# Run PyInstaller outside project cwd to avoid stdlib shadowing by local package names.
Push-Location $env:TEMP
try {
    $env:QMTOOL_PROJECT_ROOT = $ProjectRoot
    python -m PyInstaller --noconfirm --distpath (Join-Path $ProjectRoot "dist") --workpath (Join-Path $ProjectRoot "build") "$SpecFile"
    if ($LASTEXITCODE -ne 0) { throw "pyinstaller build failed with exit code $LASTEXITCODE" }
}
finally {
    Remove-Item Env:\QMTOOL_PROJECT_ROOT -ErrorAction SilentlyContinue
    Pop-Location
}

Write-Host ""
Write-Host "Build finished."
$ExePath = Join-Path $ProjectRoot "dist/QmToolUiMvp.exe"
Write-Host "EXE: $ExePath"
if (-not (Test-Path $ExePath)) { throw "build finished but exe not found: $ExePath" }

if ($RunSmoke) {
    Write-Host "Running EXE smoke test..."
    & $ExePath --smoke-test
    if ($LASTEXITCODE -ne 0) { throw "exe smoke test failed with exit code $LASTEXITCODE" }
}
