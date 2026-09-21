[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern("^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")]
    [string]$GateId,

    [string]$PythonPath = ".venv\Scripts\python.exe",

    [string]$JUnitPath = "",

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"

$repoRoot = (& git rev-parse --show-toplevel 2>$null).Trim()
if ($LASTEXITCODE -ne 0 -or -not $repoRoot) {
    throw "run-pytest-gate.ps1 must be started inside a Git worktree."
}
$repoRoot = [System.IO.Path]::GetFullPath($repoRoot)
Set-Location $repoRoot

if (-not [System.IO.Path]::IsPathRooted($PythonPath)) {
    $PythonPath = Join-Path $repoRoot $PythonPath
}
$PythonPath = [System.IO.Path]::GetFullPath($PythonPath)

foreach ($argument in @($PytestArgs)) {
    if ($argument -eq "--basetemp" -or $argument -like "--basetemp=*") {
        throw "The gate wrapper owns --basetemp; remove it from PytestArgs."
    }
    if ($argument -eq "--junitxml" -or $argument -like "--junitxml=*") {
        throw "Use -JUnitPath instead of passing --junitxml through PytestArgs."
    }
}

$preflight = Join-Path $PSScriptRoot "assert-execution-host.ps1"
& $preflight -TargetRoot $repoRoot -PythonPath $PythonPath -RequirePythonTemp
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssfffZ")
$token = [guid]::NewGuid().ToString("N").Substring(0, 8)
$baseTemp = Join-Path $repoRoot ("build\pt\{0}-{1}-{2}" -f $GateId, $stamp, $token)
$processTemp = Join-Path $repoRoot ("build\ptmp\{0}-{1}" -f $PID, $token)
if (Test-Path -LiteralPath $baseTemp) {
    throw "Generated basetemp already exists: $baseTemp"
}
New-Item -ItemType Directory -Path (Split-Path -Parent $baseTemp) -Force | Out-Null
New-Item -ItemType Directory -Path $processTemp -Force | Out-Null

$pytestCommand = @("-m", "pytest") + @($PytestArgs) + @(
    "-p", "no:cacheprovider",
    "--basetemp", $baseTemp
)

if ($JUnitPath) {
    if (-not [System.IO.Path]::IsPathRooted($JUnitPath)) {
        $JUnitPath = Join-Path $repoRoot $JUnitPath
    }
    $JUnitPath = [System.IO.Path]::GetFullPath($JUnitPath)
    $junitDirectory = Split-Path -Parent $JUnitPath
    if ($junitDirectory) {
        New-Item -ItemType Directory -Path $junitDirectory -Force | Out-Null
    }
    $pytestCommand += @("--junitxml", $JUnitPath)
}

$previousTemp = $env:TEMP
$previousTmp = $env:TMP
$env:TEMP = $processTemp
$env:TMP = $processTemp

try {
    Write-Host "QMTOOL_PYTEST_BASETEMP=$baseTemp"
    Write-Host "QMTOOL_PYTEST_PROCESS_TEMP=$processTemp"
    & $PythonPath @pytestCommand
    $exitCode = $LASTEXITCODE
}
finally {
    $env:TEMP = $previousTemp
    $env:TMP = $previousTmp
}

exit $exitCode
