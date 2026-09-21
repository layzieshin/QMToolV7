$ErrorActionPreference = "Stop"

$preflight = Join-Path $PSScriptRoot "tools\assert-execution-host.ps1"
& $preflight -TargetRoot (Get-Location).Path -RequireGitWrite
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if (-not (Test-Path ".venv\Scripts\python.exe" -PathType Leaf)) {
    py -3.14 -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install `
    -c constraints-py314.txt `
    -r requirements.txt `
    -r requirements-pyqt.txt `
    -r requirements-dev.txt

& $preflight `
    -TargetRoot (Get-Location).Path `
    -PythonPath ".venv\Scripts\python.exe" `
    -RequireGitWrite `
    -RequirePythonTemp
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

if (-not (Test-Path ".cursor\runtime\workflow-state.json" -PathType Leaf)) {
    Copy-Item ".cursor\runtime\workflow-state.template.json" ".cursor\runtime\workflow-state.json"
}
