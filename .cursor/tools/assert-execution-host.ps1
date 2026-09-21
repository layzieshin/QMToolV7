[CmdletBinding()]
param(
    [string]$TargetRoot = ".",

    [string]$PythonPath = "",

    [switch]$RequireGitWrite,

    [switch]$RequirePythonTemp,

    [switch]$RequireCursorCli,

    [switch]$Json
)

$ErrorActionPreference = "Stop"

$checks = [ordered]@{}
$failures = [System.Collections.Generic.List[object]]::new()

function Add-HostFailure {
    param(
        [string]$Code,
        [string]$Message
    )

    $failures.Add([ordered]@{ code = $Code; message = $Message })
}

function Set-HostCheck {
    param(
        [string]$Name,
        [bool]$Passed
    )

    $checks[$Name] = if ($Passed) { "PASS" } else { "FAIL" }
}

function Resolve-GitPath {
    param(
        [string]$RepositoryRoot,
        [string]$GitPath
    )

    if ([System.IO.Path]::IsPathRooted($GitPath)) {
        return [System.IO.Path]::GetFullPath($GitPath)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $RepositoryRoot $GitPath))
}

$resolvedTarget = $null
$branch = $null
$head = $null

try {
    $resolvedTarget = (Resolve-Path -LiteralPath $TargetRoot -ErrorAction Stop).Path
}
catch {
    Add-HostFailure "TARGET_ROOT_MISSING" "Target root does not exist: $TargetRoot"
}

if ($resolvedTarget) {
    $repoRoot = (& git -C $resolvedTarget rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $repoRoot) {
        Add-HostFailure "NOT_A_GIT_WORKTREE" "Target root is not a Git worktree: $resolvedTarget"
    }
    else {
        $repoRoot = [System.IO.Path]::GetFullPath($repoRoot.Trim())
        $resolvedTarget = [System.IO.Path]::GetFullPath($resolvedTarget)
        $sameRoot = $repoRoot.Equals($resolvedTarget, [System.StringComparison]::OrdinalIgnoreCase)
        Set-HostCheck "target_is_repository_root" $sameRoot
        if (-not $sameRoot) {
            Add-HostFailure "TARGET_ROOT_MISMATCH" "Target must be the opened repository root, not a parent or child path."
        }

        $registeredRoots = @(
            & git -C $resolvedTarget worktree list --porcelain 2>$null |
                Where-Object { $_ -like "worktree *" } |
                ForEach-Object {
                    [System.IO.Path]::GetFullPath($_.Substring("worktree ".Length))
                }
        )
        $registered = $registeredRoots | Where-Object {
            $_.Equals($resolvedTarget, [System.StringComparison]::OrdinalIgnoreCase)
        }
        Set-HostCheck "registered_worktree" ([bool]$registered)
        if (-not $registered) {
            Add-HostFailure "UNREGISTERED_WORKTREE" "Target root is not present in git worktree list."
        }

        $branch = (& git -C $resolvedTarget branch --show-current 2>$null).Trim()
        $head = (& git -C $resolvedTarget rev-parse HEAD 2>$null).Trim()
        $hasBranch = [bool]$branch
        Set-HostCheck "attached_branch" $hasBranch
        if (-not $hasBranch) {
            Add-HostFailure "DETACHED_HEAD" "Target worktree must be attached to its package branch."
        }

        if ($RequireGitWrite) {
            $gitProbe = $null
            try {
                $indexPath = (& git -C $resolvedTarget rev-parse --git-path index 2>$null).Trim()
                if ($LASTEXITCODE -ne 0 -or -not $indexPath) {
                    throw "git rev-parse --git-path index failed"
                }
                $indexPath = Resolve-GitPath $resolvedTarget $indexPath
                $indexLock = "$indexPath.lock"
                if (Test-Path -LiteralPath $indexLock) {
                    Set-HostCheck "git_worktree_metadata_writable" $false
                    Add-HostFailure "GIT_INDEX_LOCKED" "The target worktree already has an index.lock; preserve it and stop competing writers."
                    throw "Git index is locked by another or interrupted writer."
                }
                $adminRoot = Split-Path -Parent $indexPath
                $gitProbe = Join-Path $adminRoot ("qmtool-write-probe-{0}.tmp" -f [guid]::NewGuid().ToString("N"))
                $stream = [System.IO.File]::Open(
                    $gitProbe,
                    [System.IO.FileMode]::CreateNew,
                    [System.IO.FileAccess]::Write,
                    [System.IO.FileShare]::None
                )
                $stream.Dispose()
                Remove-Item -LiteralPath $gitProbe -Force
                $gitProbe = $null
                Set-HostCheck "git_worktree_metadata_writable" $true
            }
            catch {
                if (-not $checks.Contains("git_worktree_metadata_writable")) {
                    Set-HostCheck "git_worktree_metadata_writable" $false
                    Add-HostFailure "GIT_METADATA_NOT_WRITABLE" "Git worktree metadata is not writable from this execution host."
                }
            }
            finally {
                if ($gitProbe -and (Test-Path -LiteralPath $gitProbe)) {
                    Remove-Item -LiteralPath $gitProbe -Force -ErrorAction SilentlyContinue
                }
            }
        }

        if ($RequirePythonTemp) {
            $python = $PythonPath
            if (-not $python) {
                $python = Join-Path $resolvedTarget ".venv\Scripts\python.exe"
            }
            if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
                Set-HostCheck "python_temp_roundtrip" $false
                Add-HostFailure "PYTHON_NOT_FOUND" "Python executable not found for the temp-path probe."
            }
            else {
                $probeParent = Join-Path $resolvedTarget "build\agent-host-probe"
                $probePath = Join-Path $probeParent ([guid]::NewGuid().ToString("N"))
                New-Item -ItemType Directory -Path $probeParent -Force | Out-Null
                $probeCode = @"
from pathlib import Path
import sys
p = Path(sys.argv[1])
p.mkdir(parents=True, exist_ok=False)
f = p / 'probe.txt'
f.write_text('ok', encoding='utf-8')
assert [item.name for item in p.iterdir()] == ['probe.txt']
f.unlink()
p.rmdir()
"@
                try {
                    & $python -c $probeCode $probePath 2>$null
                    if ($LASTEXITCODE -ne 0) {
                        throw "Python child could not complete the temp-path roundtrip."
                    }
                    Set-HostCheck "python_temp_roundtrip" $true
                }
                catch {
                    Set-HostCheck "python_temp_roundtrip" $false
                    Add-HostFailure "PYTHON_TEMP_NOT_WRITABLE" "A Python child cannot create, enumerate and remove files below the repository build directory."
                }
                finally {
                    if (Test-Path -LiteralPath $probePath) {
                        Remove-Item -LiteralPath $probePath -Recurse -Force -ErrorAction SilentlyContinue
                    }
                }
            }
        }
    }
}

if ($RequireCursorCli) {
    $deadProxyNames = [System.Collections.Generic.List[string]]::new()
    foreach ($name in @("ALL_PROXY", "HTTP_PROXY", "HTTPS_PROXY", "GIT_HTTP_PROXY", "GIT_HTTPS_PROXY")) {
        $value = [Environment]::GetEnvironmentVariable($name, "Process")
        if ($value -and $value -match "(?i)^https?://(127\.0\.0\.1|localhost|\[::1\]):9/?$") {
            $deadProxyNames.Add($name)
        }
    }
    $proxyReady = $deadProxyNames.Count -eq 0
    Set-HostCheck "cursor_network_environment" $proxyReady
    if (-not $proxyReady) {
        Add-HostFailure "CURSOR_NETWORK_BLOCKED" ("Cursor CLI is routed through a disabled local proxy in: " + ($deadProxyNames -join ", "))
    }

    $cursorCommand = Get-Command cursor-agent -ErrorAction SilentlyContinue
    Set-HostCheck "cursor_agent_available" ([bool]$cursorCommand)
    if (-not $cursorCommand) {
        Add-HostFailure "CURSOR_AGENT_NOT_FOUND" "cursor-agent is not available on PATH."
    }

    $cursorProbe = $null
    try {
        if (-not $env:USERPROFILE) {
            throw "USERPROFILE is unset"
        }
        $chatRoot = Join-Path $env:USERPROFILE ".cursor\chats"
        New-Item -ItemType Directory -Path $chatRoot -Force | Out-Null
        $cursorProbe = Join-Path $chatRoot ("qmtool-write-probe-{0}" -f [guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Path $cursorProbe -ErrorAction Stop | Out-Null
        Remove-Item -LiteralPath $cursorProbe -Force
        $cursorProbe = $null
        Set-HostCheck "cursor_session_store_writable" $true
    }
    catch {
        Set-HostCheck "cursor_session_store_writable" $false
        Add-HostFailure "CURSOR_SESSION_STORE_NOT_WRITABLE" "Cursor cannot write its session store under USERPROFILE from this execution host."
    }
    finally {
        if ($cursorProbe -and (Test-Path -LiteralPath $cursorProbe)) {
            Remove-Item -LiteralPath $cursorProbe -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
}

$result = [ordered]@{
    status = if ($failures.Count -eq 0) { "READY" } else { "EXECUTION_HOST_REQUIRED" }
    target_root = $resolvedTarget
    branch = $branch
    head = $head
    checks = $checks
    failures = @($failures)
}

if ($Json) {
    $result | ConvertTo-Json -Depth 6
}
else {
    Write-Host ("Execution host: {0}" -f $result.status)
    if ($resolvedTarget) {
        Write-Host ("Target: {0}" -f $resolvedTarget)
    }
    foreach ($entry in $checks.GetEnumerator()) {
        Write-Host ("{0}: {1}" -f $entry.Key, $entry.Value)
    }
    foreach ($failure in $failures) {
        Write-Host ("{0}: {1}" -f $failure.code, $failure.message)
    }
}

if ($failures.Count -ne 0) {
    exit 3
}
