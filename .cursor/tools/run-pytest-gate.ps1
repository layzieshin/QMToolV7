[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern("^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")]
    [string]$GateId,

    [Parameter()]
    [string]$PythonPath = ".venv\Scripts\python.exe",

    [Parameter()]
    [string]$JUnitPath = "",

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"

function Test-DisallowedJUnitAlias {
    param([string]$Argument)

    return (
        $Argument -eq "--junitxml" -or
        $Argument -like "--junitxml=*" -or
        $Argument -eq "--junit-xml" -or
        $Argument -like "--junit-xml=*"
    )
}

function Resolve-RepositoryJUnitPath {
    param(
        [string]$RepoRoot,
        [string]$CandidatePath
    )

    $resolvedPath = $CandidatePath
    if (-not [System.IO.Path]::IsPathRooted($resolvedPath)) {
        $resolvedPath = Join-Path $RepoRoot $resolvedPath
    }
    return [System.IO.Path]::GetFullPath($resolvedPath)
}

function Test-ReparsePointPath {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $false
    }
    $item = Get-Item -LiteralPath $Path -Force
    return [bool]($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)
}

function Assert-NoReparsePointsInBuildPathChain {
    param(
        [string]$BuildRoot,
        [string]$TargetPath
    )

    $normalizedBuildRoot = [System.IO.Path]::GetFullPath($BuildRoot)
    if (Test-ReparsePointPath -Path $normalizedBuildRoot) {
        throw "Build path must not contain a junction or reparse point: $normalizedBuildRoot"
    }

    if (Test-ReparsePointPath -Path $TargetPath) {
        throw "Target path must not be a junction or reparse point: $TargetPath"
    }

    $targetDirectory = Split-Path -Parent $TargetPath
    if (-not $targetDirectory) {
        return
    }

    $normalizedTargetDirectory = [System.IO.Path]::GetFullPath($targetDirectory)
    $buildPrefix = $normalizedBuildRoot.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    $underBuild = (
        $normalizedTargetDirectory.Equals($normalizedBuildRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        $normalizedTargetDirectory.StartsWith($buildPrefix, [System.StringComparison]::OrdinalIgnoreCase)
    )
    if (-not $underBuild) {
        return
    }

    if ($normalizedTargetDirectory.Equals($normalizedBuildRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        return
    }

    $relativePath = $normalizedTargetDirectory.Substring($normalizedBuildRoot.Length).TrimStart('\', '/')
    $currentPath = $normalizedBuildRoot
    if ($relativePath) {
        foreach ($segment in $relativePath.Split([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)) {
            if (-not $segment) {
                continue
            }
            $currentPath = Join-Path $currentPath $segment
            if (Test-ReparsePointPath -Path $currentPath) {
                throw "Build path chain must not contain a junction or reparse point: $currentPath"
            }
        }
    }

}

function Assert-AllowedJUnitPath {
    param(
        [string]$RepoRoot,
        [string]$ResolvedJUnitPath
    )

    if (-not $ResolvedJUnitPath.EndsWith(".xml", [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "JUnitPath must use a .xml file extension: $ResolvedJUnitPath"
    }

    $repoRootPrefix = $RepoRoot.TrimEnd('\', '/')
    if (-not $ResolvedJUnitPath.StartsWith($repoRootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "JUnitPath must resolve inside the repository: $ResolvedJUnitPath"
    }
    $relativePath = $ResolvedJUnitPath.Substring($repoRootPrefix.Length).TrimStart('\', '/').Replace('\', '/')
    $trackedMatch = (& git -C $RepoRoot ls-files -- $relativePath 2>$null | Select-Object -First 1)
    if ($trackedMatch) {
        throw "JUnitPath must not target a tracked repository path: $relativePath"
    }

    $buildRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot "build"))
    $buildPrefix = $buildRoot + [System.IO.Path]::DirectorySeparatorChar
    if (-not ($ResolvedJUnitPath.StartsWith($buildPrefix, [System.StringComparison]::OrdinalIgnoreCase))) {
        throw "JUnitPath must resolve under the repository build directory: $ResolvedJUnitPath"
    }
}

$repoRoot = (& git rev-parse --show-toplevel 2>$null).Trim()
if ($LASTEXITCODE -ne 0 -or -not $repoRoot) {
    throw "run-pytest-gate.ps1 must be started inside a Git worktree."
}
$repoRoot = [System.IO.Path]::GetFullPath($repoRoot)
$buildRoot = Join-Path $repoRoot "build"
Set-Location $repoRoot

if (-not [System.IO.Path]::IsPathRooted($PythonPath)) {
    $PythonPath = Join-Path $repoRoot $PythonPath
}
$PythonPath = [System.IO.Path]::GetFullPath($PythonPath)

foreach ($argument in @($PytestArgs)) {
    if ($argument -eq "--basetemp" -or $argument -like "--basetemp=*") {
        throw "The gate wrapper owns --basetemp; remove it from PytestArgs."
    }
    if (Test-DisallowedJUnitAlias $argument) {
        throw "Use -JUnitPath instead of passing JUnit aliases through PytestArgs."
    }
}

$resolvedJUnitPath = ""
if ($JUnitPath) {
    $resolvedJUnitPath = Resolve-RepositoryJUnitPath -RepoRoot $repoRoot -CandidatePath $JUnitPath
    Assert-AllowedJUnitPath -RepoRoot $repoRoot -ResolvedJUnitPath $resolvedJUnitPath
    Assert-NoReparsePointsInBuildPathChain -BuildRoot $buildRoot -TargetPath $resolvedJUnitPath
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
Assert-NoReparsePointsInBuildPathChain -BuildRoot $buildRoot -TargetPath $baseTemp
New-Item -ItemType Directory -Path (Split-Path -Parent $baseTemp) -Force | Out-Null
Assert-NoReparsePointsInBuildPathChain -BuildRoot $buildRoot -TargetPath $processTemp
New-Item -ItemType Directory -Path $processTemp -Force | Out-Null

$pytestCommand = @("-m", "pytest") + @($PytestArgs) + @(
    "-p", "no:cacheprovider",
    "--basetemp", $baseTemp
)

if ($resolvedJUnitPath) {
    $junitDirectory = Split-Path -Parent $resolvedJUnitPath
    if ($junitDirectory) {
        Assert-NoReparsePointsInBuildPathChain -BuildRoot $buildRoot -TargetPath $resolvedJUnitPath
        New-Item -ItemType Directory -Path $junitDirectory -Force | Out-Null
    }
    $pytestCommand += @("--junitxml", $resolvedJUnitPath)
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
