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

# Narrow exception: synchronize a clean local main that is only behind origin/main.
$safePull = $command -match '(?i)^\s*git(?:\.exe)?\s+pull\s+--ff-only(?:\s+origin\s+main)?\s*$'
if ($safePull) {
    $cwd = [string]$inputData.cwd
    if (-not $cwd -or -not (Test-Path -LiteralPath $cwd -PathType Container)) {
        Deny-Command "Safe pull denied: command working directory is unavailable."
    }
    $repositoryRoot = [string](& git -C $cwd rev-parse --show-toplevel 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $repositoryRoot) {
        Deny-Command "Safe pull denied: repository root cannot be observed."
    }
    try {
        $resolvedCwd = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $cwd).Path).TrimEnd('\', '/')
        $resolvedRoot = [System.IO.Path]::GetFullPath((Resolve-Path -LiteralPath $repositoryRoot).Path).TrimEnd('\', '/')
    } catch {
        Deny-Command "Safe pull denied: repository path cannot be resolved."
    }
    if ($resolvedCwd -ne $resolvedRoot) {
        Deny-Command "Safe pull denied: command cwd must be the repository root."
    }
    $branch = [string](& git -C $cwd branch --show-current 2>$null)
    if ($LASTEXITCODE -ne 0 -or $branch -ne "main") {
        Deny-Command "Safe pull denied: current branch must be main."
    }
    $upstream = [string](& git -C $cwd rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>$null)
    if ($LASTEXITCODE -ne 0 -or $upstream -ne "origin/main") {
        Deny-Command "Safe pull denied: main upstream must be origin/main."
    }
    $porcelain = @(& git -C $cwd status --porcelain=v1 --untracked-files=all 2>$null)
    if ($LASTEXITCODE -ne 0 -or $porcelain.Count -ne 0) {
        Deny-Command "Safe pull denied: working tree and index must be completely clean."
    }
    $countsRaw = [string](& git -C $cwd rev-list --left-right --count HEAD...origin/main 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $countsRaw) {
        Deny-Command "Safe pull denied: ahead/behind relationship cannot be observed."
    }
    $counts = @($countsRaw.Trim() -split '\s+')
    if ($counts.Count -ne 2) {
        Deny-Command "Safe pull denied: ahead/behind result is invalid."
    }
    $ahead = 0
    $behind = 0
    if (-not [int]::TryParse($counts[0], [ref]$ahead) -or
        -not [int]::TryParse($counts[1], [ref]$behind) -or
        $ahead -ne 0 -or $behind -lt 0) {
        Deny-Command "Safe pull denied: local main is ahead or diverged from origin/main."
    }
    @{ permission = "allow" } | ConvertTo-Json -Compress | Write-Output
    exit 0
}

# Repository-wide hard denials.
if ($lower -match "\bgit\b[^;`r`n]*\bpush\b[^;`r`n]*(--force(?:-with-lease)?|-f(?:\s|$))") {
    Deny-Command "Force-push is forbidden."
}
if ($lower -match "\bgh(?:\.exe)?\s+pr\s+merge\b[^;`r`n]*(?:--admin|--bypass|--force)") {
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
$destructiveGit = @(
    "clean", "reset", "rebase", "stash", "restore", "pull", "am", "apply", "update-ref"
)
$hasGitWrite = $false

foreach ($match in $gitMatches) {
    $subcommand = $match.Groups[1].Value.ToLowerInvariant()
    if ($subcommand -in $destructiveGit) {
        Deny-Command "Destructive or history-rewriting Git command is forbidden."
    }
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

# Classify every GitHub CLI invocation. Unknown or mutating API forms fail closed.
$ghVersionOnly = $lower -match '^\s*gh(?:\.exe)?\s+--version\s*$'
$ghTopMatches = [regex]::Matches($command, '(?i)\bgh(?:\.exe)?\s+([a-z][a-z-]*)')
$ghInvocationCount = [regex]::Matches($command, '(?i)\bgh(?:\.exe)?(?=\s|$)').Count
if (-not $ghVersionOnly -and $ghInvocationCount -ne $ghTopMatches.Count) {
    Deny-Command "Unclassified GitHub CLI invocation or global option is denied fail-closed."
}

foreach ($match in $ghTopMatches) {
    $topCommand = $match.Groups[1].Value.ToLowerInvariant()
    if ($topCommand -eq "pr") {
        continue
    }
    if ($topCommand -eq "api") {
        if ($lower -match "(?:--method|-x)\s+(?:post|put|patch|delete)\b" -or
            $lower -match "(?:^|\s)(?:-f|-F|--field|--raw-field|--input)(?:\s|=)") {
            Deny-Command "Mutating gh api requests are forbidden; use a gated first-class gh pr command."
        }
        if ($lower -match "(?:--method|-x)\s+\S+" -and
            $lower -notmatch "(?:--method|-x)\s+get\b") {
            Deny-Command "Only read-only GET requests are allowed through gh api."
        }
        continue
    }
    if ($topCommand -eq "auth" -and $lower -match '^\s*gh(?:\.exe)?\s+auth\s+status\s*$') {
        continue
    }
    if ($topCommand -eq "repo" -and $lower -match '^\s*gh(?:\.exe)?\s+repo\s+view\b') {
        continue
    }
    if ($topCommand -eq "run" -and $lower -match '^\s*gh(?:\.exe)?\s+run\s+(?:list|view|watch)\b') {
        continue
    }
    if ($topCommand -eq "version") {
        continue
    }
    Deny-Command "Unclassified GitHub CLI command '$topCommand' is denied fail-closed."
}

# Classify every gh pr invocation.
$ghMatches = [regex]::Matches($command, '(?i)\bgh(?:\.exe)?\s+pr\s+([a-z][a-z-]*)')
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
if ($command -match '(?i)\bgit\s+-C\s+') {
    Deny-Command "git -C is forbidden for workflow Git writes; the hook cwd is authoritative."
}
if ($lower -match "\b(?:set-location|push-location|pop-location|chdir|cd|sl)\b") {
    Deny-Command "Inline directory changes are forbidden for workflow Git/GitHub writes; the hook cwd is authoritative."
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
$repositoryRoot = [string](& git -C $cwd rev-parse --show-toplevel 2>$null)
if ($LASTEXITCODE -ne 0 -or -not $repositoryRoot) {
    Deny-Command "Git write denied: repository root cannot be observed."
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
$configPath = Join-Path $repositoryRoot ".cursor/agent-system.json"
if (-not (Test-Path -LiteralPath $configPath -PathType Leaf)) {
    Deny-Command "Git write denied: agent-system config is unavailable."
}
try {
    $config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
} catch {
    Deny-Command "Git write denied: agent-system config is invalid."
}

$isCommit = $lower -match "\bgit\b[^;`r`n]*\bcommit\b"
$isPush = $lower -match "\bgit\b[^;`r`n]*\bpush\b"
$isFetch = $lower -match "\bgit\b[^;`r`n]*\bfetch\b"
$isGitMerge = $lower -match "\bgit\b[^;`r`n]*\bmerge\b"
$isIndexWrite = $lower -match "\bgit\b[^;`r`n]*\b(?:add|rm|mv)\b"
$isPrCreateOrUpdate = $lower -match "\bgh(?:\.exe)?\s+pr\s+(?:create|edit|close|reopen|comment|review|ready)\b"
$isPrComment = $lower -match "\bgh(?:\.exe)?\s+pr\s+comment\b"
$isPrMerge = $lower -match "\bgh(?:\.exe)?\s+pr\s+merge\b"

if (($isCommit -or $isIndexWrite) -and $phase -notin @("CHECKPOINT_GIT", "FINAL_GIT")) {
    Deny-Command "Commit/index writes are allowed only in CHECKPOINT_GIT or FINAL_GIT."
}
if (($isFetch -or $isGitMerge -or $isPrCreateOrUpdate) -and $phase -ne "FINAL_GIT") {
    Deny-Command "Fetch, merge, and pull-request writes are allowed only in FINAL_GIT."
}

if ($isPrComment) {
    $codexReviewRequest = [regex]::Match(
        $lower,
        '^\s*gh(?:\.exe)?\s+pr\s+comment\s+(\d+)\s+--body\s+(?:"@codex review"|''@codex review'')\s*$'
    )
    if (-not $codexReviewRequest.Success) {
        Deny-Command "PR comments are limited to the exact bounded @codex review request."
    }
    if (-not [bool]$config.external_review.enabled) {
        Deny-Command "Codex review request denied: external review is disabled."
    }
    $externalState = $state.external_review
    if ($null -eq $externalState) {
        Deny-Command "Codex review request denied: external-review state is missing."
    }
    $externalStatus = [string]$externalState.status
    if ($externalStatus -notin @("NOT_REQUESTED", "STALE")) {
        Deny-Command "Codex review request denied: state must be NOT_REQUESTED or STALE."
    }
    $round = [int]$externalState.round
    $maxRounds = [int]$config.external_review.max_review_rounds
    if ($round -lt 0 -or $round -ge $maxRounds) {
        Deny-Command "Codex review request denied: configured external-review round budget is exhausted."
    }
    $reviewPrNumber = $codexReviewRequest.Groups[1].Value
    $reviewPrJson = (& gh pr view $reviewPrNumber --json headRefName,headRefOid,baseRefName,state 2>$null)
    if ($LASTEXITCODE -ne 0 -or -not $reviewPrJson) {
        Deny-Command "Codex review request denied: pull-request metadata could not be verified."
    }
    try {
        $reviewPr = $reviewPrJson | ConvertFrom-Json
    } catch {
        Deny-Command "Codex review request denied: pull-request metadata is invalid."
    }
    if ([string]$reviewPr.headRefName -ne $stateWorkBranch -or
        [string]$reviewPr.baseRefName -ne $baseBranch -or
        [string]$reviewPr.state -ne "OPEN") {
        Deny-Command "Codex review request denied: PR must be OPEN with persisted work_branch as head and base_branch as base."
    }
    $normalizedStatePath = [System.IO.Path]::GetFullPath($statePath).ToLowerInvariant()
    $hashProvider = [System.Security.Cryptography.SHA256]::Create()
    try {
        $statePathHash = [System.BitConverter]::ToString(
            $hashProvider.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($normalizedStatePath))
        ).Replace("-", "")
    } finally {
        $hashProvider.Dispose()
    }
    $reservationMutex = [System.Threading.Mutex]::new(
        $false,
        "Local\QMToolCursorReview-$statePathHash"
    )
    $mutexHeld = $false
    $reservationFailed = $false
    $temporaryStatePath = $null
    $backupStatePath = $null
    try {
        try {
            $mutexHeld = $reservationMutex.WaitOne(0)
        } catch [System.Threading.AbandonedMutexException] {
            $mutexHeld = $true
        }
        if (-not $mutexHeld) {
            throw "Another review-request reservation is in progress."
        }
        $reservationState = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
        $reservationExternal = $reservationState.external_review
        $reservationRound = [int]$reservationExternal.round
        if ([string]$reservationState.status -ne "RUNNING" -or
            [bool]$reservationState.human_gate -or
            [string]$reservationState.phase -ne "FINAL_GIT" -or
            [string]$reservationState.work_branch -ne $observedBranch -or
            [string]$reservationState.base_branch -ne $baseBranch -or
            $null -eq $reservationExternal -or
            [string]$reservationExternal.status -notin @("NOT_REQUESTED", "STALE") -or
            $reservationRound -lt 0 -or
            $reservationRound -ge $maxRounds) {
            throw "The review-request state is no longer eligible."
        }
        $reservedAt = [DateTime]::UtcNow.ToString("o")
        $reservationExternal.status = "PENDING"
        $reservationExternal.round = $reservationRound + 1
        $reservationExternal.reviewed_head = $null
        $reservationExternal.blocking_findings = @()
        $reservationExternal.last_checked_at = $reservedAt
        $reservationState.updated_at = $reservedAt
        $reservationState.next_action = "Await the reserved Codex review request; do not resend this round."
        $temporaryStatePath = "$statePath.request-$PID-$([Guid]::NewGuid().ToString('N')).tmp"
        $backupStatePath = "$statePath.backup-$PID-$([Guid]::NewGuid().ToString('N')).tmp"
        $serializedState = $reservationState | ConvertTo-Json -Depth 10
        [System.IO.File]::WriteAllText($temporaryStatePath, $serializedState, [System.Text.UTF8Encoding]::new($false))
        [System.IO.File]::Replace($temporaryStatePath, $statePath, $backupStatePath)
        $temporaryStatePath = $null
        Remove-Item -LiteralPath $backupStatePath -Force -ErrorAction SilentlyContinue
        $backupStatePath = $null
    } catch {
        $reservationFailed = $true
    } finally {
        if ($temporaryStatePath -and (Test-Path -LiteralPath $temporaryStatePath -PathType Leaf)) {
            Remove-Item -LiteralPath $temporaryStatePath -Force -ErrorAction SilentlyContinue
        }
        if ($backupStatePath -and (Test-Path -LiteralPath $backupStatePath -PathType Leaf)) {
            Remove-Item -LiteralPath $backupStatePath -Force -ErrorAction SilentlyContinue
        }
        if ($mutexHeld) {
            $reservationMutex.ReleaseMutex()
        }
        $reservationMutex.Dispose()
    }
    if ($reservationFailed) {
        Deny-Command "Codex review request denied: atomic reservation failed or state is no longer requestable."
    }
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
    $mergeMatch = [regex]::Match($lower, '^\s*gh(?:\.exe)?\s+pr\s+merge\s+(\d+)\s+--squash\s*$')
    if (-not $mergeMatch.Success) {
        Deny-Command "PR merge must use the exact form: gh pr merge <number> --squash."
    }
    $prNumber = $mergeMatch.Groups[1].Value
    $prJson = (& gh pr view $prNumber --json headRefName,headRefOid,baseRefName,state 2>$null)
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
    if ([bool]$config.external_review.enabled) {
        $externalState = $state.external_review
        if ($null -eq $externalState) {
            Deny-Command "PR merge denied: external-review state is missing."
        }
        $externalStatus = [string]$externalState.status
        $mergeableExternal = @("PASS", "BOUNDED_COMPLETE", "UNAVAILABLE", "LIMIT_REACHED", "DISABLED")
        if ($externalStatus -notin $mergeableExternal) {
            Deny-Command "PR merge denied: external review is not in a mergeable state."
        }
        if ($externalStatus -eq "PASS" -and
            ([string]$externalState.reviewed_head -ne [string]$pr.headRefOid)) {
            Deny-Command "PR merge denied: external PASS does not match the current PR head."
        }
        if ($externalStatus -eq "PASS" -and
            @($externalState.blocking_findings).Count -ne 0) {
            Deny-Command "PR merge denied: external PASS still contains blocking findings."
        }
        if ($externalStatus -eq "BOUNDED_COMPLETE" -and
            ([int]$externalState.round -ne [int]$config.external_review.max_review_rounds -or
             [string]$externalState.reviewed_head -or
             @($externalState.blocking_findings).Count -ne 0)) {
            Deny-Command "PR merge denied: BOUNDED_COMPLETE requires exhausted rounds, no reviewed head, and no open findings."
        }
        if ($externalStatus -in @("UNAVAILABLE", "LIMIT_REACHED") -and
            [bool]$config.external_review.unavailability_blocks_merge) {
            Deny-Command "PR merge denied: configured external-review unavailability policy blocks merge."
        }
    }
}

@{ permission = "allow" } | ConvertTo-Json -Compress | Write-Output
