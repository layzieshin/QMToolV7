param(
    [switch]$Clean = $true,
    [switch]$Console = $false,
    # Build work/dist on local disk (recommended on UNC/network shares: avoids WinError 225 / AV on BeginUpdateResource).
    [switch]$InProjectBuild = $false
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SpecFile = Join-Path $ProjectRoot "qm_tool_pyqt.spec"

if (-not (Test-Path $SpecFile)) { throw "spec file not found: $SpecFile" }

$LocalRoot = Join-Path $env:LOCALAPPDATA "QmToolPyQtBuild"
$LocalWork = Join-Path $LocalRoot "build"
$LocalDist = Join-Path $LocalRoot "dist"

if ($InProjectBuild) {
    $WorkPath = Join-Path $ProjectRoot "build"
    $DistPath = Join-Path $ProjectRoot "dist"
} else {
    $WorkPath = $LocalWork
    $DistPath = $LocalDist
}

if ($Clean) {
    if (Test-Path $LocalRoot) { Remove-Item $LocalRoot -Recurse -Force }
    $projBuild = Join-Path $ProjectRoot "build"
    $projDist = Join-Path $ProjectRoot "dist"
    if (Test-Path $projBuild) { Remove-Item $projBuild -Recurse -Force }
    if (Test-Path $projDist) { Remove-Item $projDist -Recurse -Force }
}

python -m pip install -q pyinstaller
if ($LASTEXITCODE -ne 0) { throw "pyinstaller installation failed with exit code $LASTEXITCODE" }

python -m pip install -q -r (Join-Path $ProjectRoot "requirements.txt") -r (Join-Path $ProjectRoot "requirements-pyqt.txt")
if ($LASTEXITCODE -ne 0) { throw "dependency installation failed with exit code $LASTEXITCODE" }

New-Item -ItemType Directory -Force -Path $WorkPath | Out-Null
New-Item -ItemType Directory -Force -Path $DistPath | Out-Null

# Run PyInstaller outside project cwd to avoid stdlib shadowing by local package names.
Push-Location $env:TEMP
try {
    $env:QMTOOL_PROJECT_ROOT = $ProjectRoot
    if ($Console) { $env:QMTOOL_PYQT_EXE_CONSOLE = "1" }
    python -m PyInstaller --noconfirm --distpath $DistPath --workpath $WorkPath "$SpecFile"
    if ($LASTEXITCODE -ne 0) { throw "pyinstaller build failed with exit code $LASTEXITCODE" }
}
finally {
    Remove-Item Env:\QMTOOL_PROJECT_ROOT -ErrorAction SilentlyContinue
    Remove-Item Env:\QMTOOL_PYQT_EXE_CONSOLE -ErrorAction SilentlyContinue
    Pop-Location
}

$BuiltExe = Join-Path $DistPath "QmToolPyQt.exe"
if (-not (Test-Path $BuiltExe)) { throw "build finished but exe not found: $BuiltExe" }

if (-not $InProjectBuild) {
    $OutDir = Join-Path $ProjectRoot "dist"
    New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
    Copy-Item $BuiltExe (Join-Path $OutDir "QmToolPyQt.exe") -Force
}

Write-Host ""
Write-Host "Build finished."
$ExePath = Join-Path $ProjectRoot "dist\QmToolPyQt.exe"
Write-Host "EXE: $ExePath"
if (-not (Test-Path $ExePath)) { throw "exe not copied to project dist: $ExePath" }
