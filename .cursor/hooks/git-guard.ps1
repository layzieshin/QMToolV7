$ErrorActionPreference = "Stop"

function Deny-Command([string]$message) {
    @{
        permission = "deny"
        user_message = $message
        agent_message = $message
    } | ConvertTo-Json -Compress | Write-Output
    exit 0
}

$raw = [Console]::In.ReadToEnd()
$inputData = $raw | ConvertFrom-Json
$command = [string]$inputData.command
$lower = $command.ToLowerInvariant()

# Repository-wide hard denials.
if ($lower -match "\bgit\b[^;`r`n]*\bpush\b[^;`r`n]*(--force(?:-with-lease)?|-f(?:\s|$))") {
    Deny-Command "Force-push is forbidden."
}
if ($lower -match "\bgit\b[^;`r`n]*\b(?:clean|reset|rebase|stash|restore|pull|am|apply|update-ref)\b") {
    Deny-Command "Destructive or history-rewriting Git command is forbidden."
}
if ($lower -match "\bgh\s+pr\s+merge\b[^;`r`n]*(?:--admin|--bypass|--force)") {
    Deny-Command "Branch-protection bypass flags are forbidden."
}

# Classify every Git invocation. Unknown subcommands fail closed.
$gitPattern = '(?i)\bgit(?:\.exe)?(?:\s+-C\s+(?:"[^"]+"|''[^'']+''|\S+))*\s+([a-z][a-z-]*)'
$gitMatches = [regex]::Matches($command, $gitPattern)
$gitInvocationCount = [regex]::Matches($command, '(?i)\bgit(?:\.exe)?(?=\s|$)').Count
if ($gitInvocationCount -ne $gitMatches.Count) {
    Deny-Command "Unclassified Git invocation or global option is denied fail-closed."
}
$readGit = @(
    "status", "diff", "log", "show", "rev-parse", "ls-files", "ls-tree", "name-rev",
    "describe", "merge-base", "blame", "shortlog", "for-each-ref", "count-objects",
    "check-ignore", "help", "version"
)
$writeGit = @("add", "rm", "mv", "commit", "push", "fetch", "merge")
$hasGitWrite = $false

foreach ($match in $gitMatches) {
    $subcommand = $match.Groups[1].Value.ToLowerInvariant()
    if ($subcommand -in $writeGit) {
        $hasGitWrite = $true
        continue
    }
    if ($subcommand -in $readGit) {
        continue
    }
    if ($subcommand -eq "branch") {
        $readOnlyBranch = '^\s*git(?:\.exe)?\s+branch(?:\s+(?:--show-current|--list))?\s*$'
        if ($lower -notmatch $readOnlyBranch) {
            Deny-Command "Only read-only git branch, git branch --show-current, and git branch --list are allowed."
        }
        continue
    }
    if ($subcommand -eq "worktree") {
        if ($lower -notmatch "\bgit\b[^;`r`n]*\bworktree\s+list\b") {
            Deny-Command "Only read-only git worktree list is allowed."
        }
        continue
    }
    if ($subcommand -eq "remote") {
        if ($lower -notmatch "\bgit\b[^;`r`n]*\bremote(?:\s+-v|\s+get-url|\s+show|\s*$)") {
            Deny-Command "Remote configuration mutation is forbidden."
        }
        continue
    }
    if ($subcommand -eq "config") {
        if ($lower -notmatch "\bgit\b[^;`r`n]*\bconfig\b[^;`r`n]*(?:--get|--get-regexp|--list|-l\b|--show-origin)") {
            Deny-Command "Git configuration mutation is forbidden."
        }
        continue
    }
    Deny-Command "Unclassified Git subcommand '$subcommand' is denied fail-closed."
}

# Classify every gh pr invocation. Unknown subcommands fail closed.
$ghMatches = [regex]::Matches($command, '(?i)\bgh\s+pr\s+([a-z][a-z-]*)')
$readGh = @("checks", "view", "status", "list", "diff")
$writeGh = @("create", "edit", "close", "reopen", "comment", "review", "ready", "merge")
$hasGhWrite = $false
foreach ($match in $ghMatches) {
    $subcommand = $match.Groups[1].Value.ToLowerInvariant()
    if ($subcommand -in $writeGh) {
        $hasGhWrite = $true
        continue
    }
    if ($subcommand -in $readGh) {
        continue
    }
    Deny-Command "Unclassified gh pr subcommand '$subcommand' is denied fail-closed."
}

$isWrite = $hasGitWrite -or $hasGhWrite
if (-not $isWrite) {
    @{ permission = "allow" } | ConvertTo-Json -Compress | Write-Output
    exit 0
}
if ($lower -match "\bgit\s+-c\s+") {
    Deny-Command "git -C is forbidden for workflow Git writes; the hook cwd is authoritative."
}

$statePath = if ($env:QMTOOL_WORKFLOW_STATE_PATH) {
    $env:QMTOOL_WORKFLOW_STATE_PATH
} else {
    Join-Path (Get-Location) ".cursor/runtime/workflow-state.json"
}
if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
    Deny-Command "Git write denied: no persisted workflow state is available."
}
$state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
if ([string]$state.status -ne "RUNNING") {
    Deny-Command "Git write denied: workflow status must be RUNNING."
}
if ([bool]$state.human_gate) {
    Deny-Command "Git write denied while a HUMAN_GATE is active."
}

$phase = [string]$state.phase
$baseBranch = [string]$state.base_branch
$stateWorkBranch = [string]$state.work_branch
$cwd = [string]$inputData.cwd
if (-not $cwd -or -not (Test-Path -LiteralPath $cwd -PathType Container)) {
    Deny-Command "Git write denied: command working directory is unavailable."
}
$observedBranch = [string](& git -C $cwd branch --show-current 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $observedBranch) {
    Deny-Command "Git write denied: current branch cannot be observed."
}
if (-not $stateWorkBranch -or $observedBranch -ne $stateWorkBranch) {
    Deny-Command "Git write denied: observed branch '$observedBranch' does not match persisted work branch '$stateWorkBranch'."
}
if ($observedBranch -eq $baseBranch) {
    Deny-Command "Git write denied on the protected base branch."
}

$isCommit = $lower -match "\bgit\b[^;`r`n]*\bcommit\b"
$isPush = $lower -match "\bgit\b[^;`r`n]*\bpush\b"
$isFetch = $lower -match "\bgit\b[^;`r`n]*\bfetch\b"
$isGitMerge = $lower -match "\bgit\b[^;`r`n]*\bmerge\b"
$isIndexWrite = $lower -match "\bgit\b[^;`r`n]*\b(?:add|rm|mv)\b"
$isPrCreateOrUpdate = $lower -match "\bgh\s+pr\s+(?:create|edit|close|reopen|comment|review|ready)\b"
$isPrMerge = $lower -match "\bgh\s+pr\s+merge\b"

if (($isCommit -or $isIndexWrite) -and $phase -notin @("CHECKPOINT_GIT", "FINAL_GIT")) {
    Deny-Command "Commit/index writes are allowed only in CHECKPOINT_GIT or FINAL_GIT."
}
if (($isFetch -or $isGitMerge -or $isPrCreateOrUpdate) -and $phase -ne "FINAL_GIT") {
    Deny-Command "Fetch, merge, and pull-request writes are allowed only in FINAL_GIT."
}

if ($isPush) {
    if ($phase -notin @("CHECKPOINT_GIT", "FINAL_GIT")) {
        Deny-Command "git push is allowed only in CHECKPOINT_GIT or FINAL_GIT."
    }
    $escapedWork = [regex]::Escape($stateWorkBranch.ToLowerInvariant())
    $allowedSource = "(?:head|$escapedWork)"
    $allowedTarget = "(?:refs/heads/)?$escapedWork"
    $gitPrefix = 'git(?:\s+-C\s+(?:"[^"]+"|''[^'']+''|\S+))?'
    $allowedPush = "^\s*$gitPrefix\s+push(?:\s+(?:-u|--set-upstream))?\s+origin\s+$allowedSource(?::$allowedTarget)?\s*$"
    if ($lower -notmatch $allowedPush) {
        Deny-Command "Push must use origin and only HEAD or the persisted work branch as source and target; foreign or delete refspecs are forbidden."
    }
}

if ($isPrMerge) {
    $fullRegression = [bool]$state.gates.full_regression_pass
    $finalAudit = [bool]$state.gates.final_audit_pass
    $ciPass = [bool]$state.gates.ci_pass
    if ($phase -ne "FINAL_GIT" -or -not $fullRegression -or -not $finalAudit -or -not $ciPass) {
        Deny-Command "PR merge denied: FINAL_GIT, full regression PASS, final audit PASS, CI PASS, and no HUMAN_GATE are required."
    }
    $mergeMatch = [regex]::Match($lower, '^\s*gh\s+pr\s+merge\s+(\d+)\s+--squash\s*$')
    if (-not $mergeMatch.Success) {
        Deny-Command "PR merge must use the exact form: gh pr merge <number> --squash."
    }
    $prNumber = $mergeMatch.Groups[1].Value
    $prJson = (& gh pr view $prNumber --json headRefName,baseRefName,state 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $prJson) {
        Deny-Command "PR merge denied: pull-request head/base metadata could not be verified."
    }
    try {
        $pr = $prJson | ConvertFrom-Json
    } catch {
        Deny-Command "PR merge denied: pull-request metadata was invalid."
    }
    if ([string]$pr.headRefName -ne $stateWorkBranch -or
        [string]$pr.baseRefName -ne $baseBranch -or
        [string]$pr.state -ne "OPEN") {
        Deny-Command "PR merge denied: PR must be OPEN with persisted work_branch as head and base_branch as base."
    }
}

@{ permission = "allow" } | ConvertTo-Json -Compress | Write-Output
