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

# Owner-validation exit when pytest returns 0 but the final JUnit document is not gate-passing.
$JUNIT_GATE_OWNER_VALIDATION_EXIT = 91

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

    try {
        $attributes = [System.IO.File]::GetAttributes($Path)
    }
    catch [System.IO.FileNotFoundException], [System.IO.DirectoryNotFoundException] {
        return $false
    }
    catch {
        throw "Unable to inspect path attributes for reparse detection: $Path. $($_.Exception.Message)"
    }

    return [bool]($attributes -band [System.IO.FileAttributes]::ReparsePoint)
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

function Get-JUnitSuiteCounter {
    param(
        [System.Xml.XmlElement]$Suite,
        [string]$Name,
        [string]$JUnitPath
    )

    if (-not $Suite.HasAttribute($Name)) {
        Write-Host "JUnit gate FAIL: missing $Name counter on testsuite at $JUnitPath"
        return $null
    }

    $raw = $Suite.GetAttribute($Name)
    if ([string]::IsNullOrWhiteSpace($raw)) {
        Write-Host "JUnit gate FAIL: missing $Name counter on testsuite at $JUnitPath"
        return $null
    }

    $parsed = 0
    if (-not [int]::TryParse(
            $raw,
            [System.Globalization.NumberStyles]::Integer,
            [System.Globalization.CultureInfo]::InvariantCulture,
            [ref]$parsed)) {
        Write-Host "JUnit gate FAIL: invalid $Name counter '$raw' on testsuite at $JUnitPath"
        return $null
    }

    if ($parsed -lt 0) {
        Write-Host "JUnit gate FAIL: negative $Name counter '$raw' on testsuite at $JUnitPath"
        return $null
    }

    return $parsed
}

function Get-JUnitGateExitCode {
    param(
        [string]$JUnitPath,
        [int]$PytestExitCode
    )

    if ($PytestExitCode -ne 0) {
        return $PytestExitCode
    }

    if (-not (Test-Path -LiteralPath $JUnitPath)) {
        Write-Host "JUnit gate FAIL: missing JUnit document at $JUnitPath"
        return $JUNIT_GATE_OWNER_VALIDATION_EXIT
    }

    $junitText = Get-Content -LiteralPath $JUnitPath -Raw -ErrorAction Stop
    if (-not $junitText -or -not $junitText.Trim()) {
        Write-Host "JUnit gate FAIL: empty JUnit document at $JUnitPath"
        return $JUNIT_GATE_OWNER_VALIDATION_EXIT
    }

    try {
        [xml]$document = $junitText
    }
    catch {
        Write-Host "JUnit gate FAIL: malformed JUnit document at $JUnitPath. $($_.Exception.Message)"
        return $JUNIT_GATE_OWNER_VALIDATION_EXIT
    }

    $suites = @($document.SelectNodes("//testsuite"))
    if ($suites.Count -eq 0 -and $document.DocumentElement -and $document.DocumentElement.LocalName -eq "testsuite") {
        $suites = @($document.DocumentElement)
    }

    if ($suites.Count -eq 0) {
        Write-Host "JUnit gate FAIL: JUnit document has no testsuite nodes at $JUnitPath"
        return $JUNIT_GATE_OWNER_VALIDATION_EXIT
    }

    $tests = 0
    $failures = 0
    $errors = 0
    foreach ($suite in $suites) {
        $suiteTests = Get-JUnitSuiteCounter -Suite $suite -Name "tests" -JUnitPath $JUnitPath
        if ($null -eq $suiteTests) {
            return $JUNIT_GATE_OWNER_VALIDATION_EXIT
        }
        $suiteFailures = Get-JUnitSuiteCounter -Suite $suite -Name "failures" -JUnitPath $JUnitPath
        if ($null -eq $suiteFailures) {
            return $JUNIT_GATE_OWNER_VALIDATION_EXIT
        }
        $suiteErrors = Get-JUnitSuiteCounter -Suite $suite -Name "errors" -JUnitPath $JUnitPath
        if ($null -eq $suiteErrors) {
            return $JUNIT_GATE_OWNER_VALIDATION_EXIT
        }

        $tests += $suiteTests
        $failures += $suiteFailures
        $errors += $suiteErrors
    }

    if ($tests -le 0) {
        Write-Host "JUnit gate FAIL: JUnit document reports zero tests at $JUnitPath"
        return $JUNIT_GATE_OWNER_VALIDATION_EXIT
    }
    if ($failures -gt 0 -or $errors -gt 0) {
        Write-Host "JUnit gate FAIL: JUnit document reports failures=$failures errors=$errors at $JUnitPath"
        return $JUNIT_GATE_OWNER_VALIDATION_EXIT
    }

    return 0
}

function Invoke-PytestGate {
    $repoRoot = (& git rev-parse --show-toplevel 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $repoRoot) {
        throw "run-pytest-gate.ps1 must be started inside a Git worktree."
    }
    $repoRoot = [System.IO.Path]::GetFullPath($repoRoot)
    $buildRoot = Join-Path $repoRoot "build"
    Set-Location $repoRoot

    $resolvedPythonPath = $PythonPath
    if (-not [System.IO.Path]::IsPathRooted($resolvedPythonPath)) {
        $resolvedPythonPath = Join-Path $repoRoot $resolvedPythonPath
    }
    $resolvedPythonPath = [System.IO.Path]::GetFullPath($resolvedPythonPath)

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
        if (Test-Path -LiteralPath $resolvedJUnitPath) {
            throw "JUnitPath must not exist before the gate run; choose a fresh target or remove stale evidence: $resolvedJUnitPath"
        }
    }

    $preflight = Join-Path $PSScriptRoot "assert-execution-host.ps1"
    & $preflight -TargetRoot $repoRoot -PythonPath $resolvedPythonPath -RequirePythonTemp
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
        & $resolvedPythonPath @pytestCommand
        $exitCode = $LASTEXITCODE
        if ($resolvedJUnitPath) {
            $exitCode = Get-JUnitGateExitCode -JUnitPath $resolvedJUnitPath -PytestExitCode $exitCode
        }
    }
    finally {
        $env:TEMP = $previousTemp
        $env:TMP = $previousTmp
    }

    exit $exitCode
}

if ($MyInvocation.InvocationName -ne '.') {
    Invoke-PytestGate
}
