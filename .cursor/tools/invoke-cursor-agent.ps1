[CmdletBinding(DefaultParameterSetName = "Inline")]
param(
    [Parameter(Mandatory = $true)]
    [string]$TargetRoot,

    [Parameter(Mandatory = $true, ParameterSetName = "Inline")]
    [string]$Prompt,

    [Parameter(Mandatory = $true, ParameterSetName = "File")]
    [string]$PromptPath,

    [string]$WorkPackage,
    [string]$ExpectedBranch,
    [string]$ExpectedHead,

    [switch]$Force,
    [switch]$AutoReview,
    [switch]$Interactive,
    [string]$ResumeSession
)

$ErrorActionPreference = "Stop"

$freshEntryRedirectEnvVars = @(
    "QMTOOL_WORKFLOW_STATE_PATH",
    "QMTOOL_RUNTIME_LOG_PATH",
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_INDEX_FILE"
)

function Invoke-TargetGit {
    param(
        [string]$RepositoryRoot,
        [string[]]$Arguments
    )

    $previousErrorAction = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    $output = & git -C $RepositoryRoot @Arguments 2>&1
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorAction
    if ($exitCode -ne 0) {
        $joined = $Arguments -join " "
        $detail = ($output | Out-String).Trim()
        if ($detail) {
            throw "Git command failed: git -C $RepositoryRoot $joined ($detail)"
        }
        throw "Git command failed: git -C $RepositoryRoot $joined"
    }
    return ($output | Out-String).Trim()
}

function Assert-FreshEntryRedirectedOwnersAbsent {
    foreach ($name in $freshEntryRedirectEnvVars) {
        $value = [Environment]::GetEnvironmentVariable($name, "Process")
        if ($value -and $value.Trim()) {
            throw "Fresh package entry cannot run with redirected owner variable ${name}."
        }
    }
}

function Assert-FreshEntryCanonicalOwnerPathLiteral {
    param(
        [string]$RepositoryRoot,
        [string]$Path,
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Target canonical $Label is missing."
    }

    $targetRootResolved = [System.IO.Path]::GetFullPath($RepositoryRoot)
    $leafFullPath = [System.IO.Path]::GetFullPath(
        $(if ([System.IO.Path]::IsPathRooted($Path)) { $Path } else { Join-Path $RepositoryRoot $Path })
    )
    if (-not $leafFullPath.StartsWith($targetRootResolved, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Fresh package entry canonical $Label must resolve inside the target root."
    }

    $rootItem = Get-Item -LiteralPath $targetRootResolved -Force
    if (($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "Fresh package entry cannot use a reparse-point redirected canonical $Label."
    }

    $relative = $leafFullPath.Substring($targetRootResolved.Length).TrimStart([char]'\', [char]'/')
    $segments = @()
    if ($relative) {
        $segments = $relative -split '[\\/]'
    }

    $cursor = $targetRootResolved
    foreach ($segment in $segments) {
        if (-not $segment) {
            continue
        }
        $cursor = Join-Path $cursor $segment
        $item = Get-Item -LiteralPath $cursor -Force
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Fresh package entry cannot use a reparse-point redirected canonical $Label."
        }
    }

    return $leafFullPath
}

function Assert-FreshEntryWorkflowState {
    param(
        [string]$WorkflowStatePath
    )

    if (-not (Test-Path -LiteralPath $WorkflowStatePath -PathType Leaf)) {
        throw "Fresh package entry requires workflow-state.json."
    }
    try {
        $workflowStateJson = Get-Content -LiteralPath $WorkflowStatePath -Raw -Encoding UTF8
        # Windows PowerShell can unwrap a one-element JSON array during pipeline assignment.
        if ($workflowStateJson -notmatch '^\s*\{') { throw "workflow state is not an object" }
        $workflowState = $workflowStateJson | ConvertFrom-Json
    }
    catch {
        throw "Fresh package entry requires valid workflow-state.json as a JSON object."
    }
    # The existing runtime README/template owns this contract. Validate its required shape here,
    # before interpreting ownership; missing guards must never behave like false/null defaults.
    $stateGroups = @(
        @{ value = $workflowState; label = "workflow-state"; fields = [ordered]@{
            status = "string"; human_gate = "bool"; work_package = "nullable-string";
            base_branch = "string"; work_branch = "nullable-string"; phase = "string";
            checkpoint = "nullable-string"; rework_count = "counter"; final_rework_count = "counter";
            escalation_used = "bool"; last_green_commit = "nullable-string"; next_action = "nullable-string";
            updated_at = "string"; work_package_path = "nullable-string";
            execution_journal_path = "nullable-string"; final_report_path = "nullable-string"
        } },
        @{ value = $workflowState.external_review; label = "external_review"; fields = [ordered]@{
            status = "string"; round = "counter"; reviewed_head = "nullable-string";
            blocking_findings = "array"; last_checked_at = "nullable-string";
            bindingRecord = "nullable-object"; recovery_proposal_bound = "bool"
        } },
        @{ value = $workflowState.gates; label = "gates"; fields = [ordered]@{
            full_regression_pass = "bool"; final_audit_pass = "bool"; ci_pass = "bool"
        } }
    )
    # Recovery is a newer optional extension; existing states need no migration at entry.
    if ($workflowState.PSObject.Properties.Name -contains "technical_recovery") {
        $stateGroups += @{ value = $workflowState.technical_recovery; label = "technical_recovery";
            fields = [ordered]@{ enabled = "bool"; user_stop = "bool" } }
    }
    foreach ($group in $stateGroups) {
        if ($group.value -isnot [pscustomobject]) {
            throw "Fresh package entry requires workflow-state.json object $($group.label)."
        }
        foreach ($field in $group.fields.Keys) {
            if ($group.value.PSObject.Properties.Name -notcontains $field) {
                throw "Fresh package entry requires workflow-state.json field $($group.label).$field."
            }
            $value = $group.value.$field
            $validType = switch ($group.fields[$field]) {
                "string" { $value -is [string] }
                "nullable-string" { $null -eq $value -or $value -is [string] }
                "bool" { $value -is [bool] }
                "counter" { ($value -is [int] -or $value -is [long]) -and $value -ge 0 }
                "array" { $value -is [array] }
                "nullable-object" { $null -eq $value -or $value -is [pscustomobject] }
            }
            if (-not $validType) {
                throw "Fresh package entry requires workflow-state.json field $($group.label).$field of type $($group.fields[$field])."
            }
        }
    }
    $status = $workflowState.status
    if ($status -notin @("IDLE", "DONE")) {
        throw "Fresh package entry blocked by workflow status: $status"
    }
    if ($workflowState.human_gate) {
        throw "Fresh package entry blocked by human_gate."
    }
    if ($workflowState.technical_recovery.user_stop) {
        throw "Fresh package entry blocked by technical_recovery.user_stop."
    }
    if ($status -eq "IDLE" -and $null -ne $workflowState.work_package -and $workflowState.work_package.Trim()) {
        throw "Fresh package entry blocked by conflicting work_package ownership while IDLE."
    }
}

$resolvedTarget = (Resolve-Path -LiteralPath $TargetRoot).Path
if ($PSCmdlet.ParameterSetName -eq "File") {
    $resolvedPrompt = (Resolve-Path -LiteralPath $PromptPath -ErrorAction Stop).Path
    $promptText = Get-Content -LiteralPath $resolvedPrompt -Raw -Encoding UTF8
}
else {
    $promptText = $Prompt
}

if (-not $promptText.Trim()) {
    throw "Cursor prompt must not be empty."
}

if ($Force -and $AutoReview) {
    throw "AutoReview cannot be combined with Force."
}

$bindingKeys = @("WorkPackage", "ExpectedBranch", "ExpectedHead")
$providedBinding = @($bindingKeys | Where-Object { $PSBoundParameters.ContainsKey($_) })
if ($providedBinding.Count -gt 0 -and $providedBinding.Count -lt $bindingKeys.Count) {
    throw "WorkPackage, ExpectedBranch and ExpectedHead must be supplied together."
}
$hasFreshEntry = $providedBinding.Count -eq $bindingKeys.Count

if ($hasFreshEntry -and $PSBoundParameters.ContainsKey("ResumeSession")) {
    throw "Fresh package entry cannot be combined with ResumeSession."
}

$journalPath = $null
$launchCorrelationId = $null
$journalStartWritten = $false

if ($hasFreshEntry) {
    if (-not $WorkPackage.Trim()) {
        throw "WorkPackage must not be blank."
    }
    if (-not $ExpectedBranch.Trim()) {
        throw "ExpectedBranch must not be blank."
    }
    if ($ExpectedHead -notmatch '^[0-9a-fA-F]{40}$') {
        throw "ExpectedHead must be a full 40-character commit SHA."
    }
    if ($ExpectedBranch -match "^(?i)(main|master)$") {
        throw "Fresh package entry cannot target protected branch: $ExpectedBranch"
    }

    Assert-FreshEntryRedirectedOwnersAbsent

    $canonicalLauncher = Join-Path $resolvedTarget ".cursor\tools\invoke-cursor-agent.ps1"
    $canonicalLauncherResolved = Assert-FreshEntryCanonicalOwnerPathLiteral `
        -RepositoryRoot $resolvedTarget `
        -Path $canonicalLauncher `
        -Label "invoke-cursor-agent.ps1"
    $thisScriptResolved = (Resolve-Path -LiteralPath $PSCommandPath).Path
    if (-not $canonicalLauncherResolved.Equals($thisScriptResolved, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Launcher must be the target canonical invoke-cursor-agent.ps1."
    }

    $canonicalAgentSystem = Join-Path $resolvedTarget ".cursor\agent-system.json"
    $canonicalWorkflowState = Join-Path $resolvedTarget ".cursor\runtime\workflow-state.json"
}

$preflight = Join-Path $PSScriptRoot "assert-execution-host.ps1"
& $preflight -TargetRoot $TargetRoot -RequireGitWrite -RequireCursorCli
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$agentSystemPath = Join-Path $resolvedTarget ".cursor\agent-system.json"
if (-not (Test-Path -LiteralPath $agentSystemPath -PathType Leaf)) {
    throw "Target agent-system.json is missing."
}
$agentConfig = Get-Content -LiteralPath $agentSystemPath -Raw -Encoding UTF8 | ConvertFrom-Json
$coordinatorModel = [string]$agentConfig.routing.coordinator_model
if (-not $coordinatorModel) {
    throw "Target agent-system.json does not define routing.coordinator_model."
}

if ($hasFreshEntry) {
    $canonicalAgentSystemResolved = Assert-FreshEntryCanonicalOwnerPathLiteral `
        -RepositoryRoot $resolvedTarget `
        -Path $canonicalAgentSystem `
        -Label "agent-system.json"
    $loadedAgentSystemResolved = (Resolve-Path -LiteralPath $agentSystemPath).Path
    if (-not $canonicalAgentSystemResolved.Equals($loadedAgentSystemResolved, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Target agent-system.json must be loaded from the canonical target path."
    }
    $canonicalWorkflowStateResolved = Assert-FreshEntryCanonicalOwnerPathLiteral `
        -RepositoryRoot $resolvedTarget `
        -Path $canonicalWorkflowState `
        -Label "workflow-state.json"

    $actualBranch = Invoke-TargetGit -RepositoryRoot $resolvedTarget -Arguments @("branch", "--show-current")
    if (-not $actualBranch) {
        throw "Fresh package entry requires an attached branch."
    }
    if ($actualBranch -ne $ExpectedBranch) {
        throw "ExpectedBranch mismatch: expected '$ExpectedBranch', actual '$actualBranch'."
    }

    $actualHead = Invoke-TargetGit -RepositoryRoot $resolvedTarget -Arguments @("rev-parse", "HEAD")
    Invoke-TargetGit -RepositoryRoot $resolvedTarget -Arguments @("cat-file", "-e", "${ExpectedHead}^{commit}")
    if ($ExpectedHead.ToLowerInvariant() -ne $actualHead.ToLowerInvariant()) {
        throw "ExpectedHead mismatch: expected '$ExpectedHead', actual '$actualHead'."
    }

    Assert-FreshEntryWorkflowState -WorkflowStatePath $canonicalWorkflowStateResolved

    $dirtyStatus = Invoke-TargetGit -RepositoryRoot $resolvedTarget -Arguments @("status", "--porcelain")
    if ($dirtyStatus) {
        throw "Fresh package entry requires a clean worktree."
    }

    $launchCorrelationId = [guid]::NewGuid().ToString("N")
    $journalDir = Join-Path $resolvedTarget ("build\codex-cursor-entry\" + ($WorkPackage -replace '[^A-Za-z0-9._-]', '_'))
    New-Item -ItemType Directory -Path $journalDir -Force | Out-Null
    $journalPath = Join-Path $journalDir "execution-journal.md"
    $startUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $startEntry = @(
        "## ENTRY_START $startUtc",
        "- launch_correlation_id: $launchCorrelationId (launcher-generated; not a native Cursor task/session id)",
        "- work_package: $WorkPackage",
        "- expected_branch: $ExpectedBranch",
        "- expected_head: $ExpectedHead",
        "- target_root: $resolvedTarget",
        "- requested_model: $coordinatorModel",
        "- launcher: $canonicalLauncherResolved",
        "- workflow_state: $canonicalWorkflowStateResolved",
        "- agent_system: $canonicalAgentSystemResolved",
        "- note: child exit 0 does not mean package DONE, reviewer PASS, or runtime model attestation",
        ""
    ) -join "`n"
    Add-Content -LiteralPath $journalPath -Value $startEntry -Encoding UTF8
    $journalStartWritten = $true

    $bindingPreamble = @(
        "CODEX_ENTRY_BINDING (verify before any edit):",
        "- WorkPackage: $WorkPackage",
        "- ExpectedBranch: $ExpectedBranch",
        "- ExpectedHead: $ExpectedHead",
        "- TargetRoot: $resolvedTarget",
        "- LaunchCorrelationId: $launchCorrelationId (launcher-generated; not a native Cursor task/session id)",
        "Recheck identity and ownership against this binding immediately. Do not recurse through invoke-cursor-agent.ps1.",
        "The supplied task prompt below carries the original approved scope. WorkPackage is a binding label only, not an implicit /execute-work-package command or broader Git authorization.",
        ""
    ) -join "`n"
    $promptText = $bindingPreamble + $promptText
}

function Format-NativeCommandArgument {
    param([string]$Value)
    if ($null -eq $Value) { return '""' }
    if ($Value -notmatch '[\s"]') { return $Value }
    $quoted = '"'
    $backslashCount = 0
    foreach ($ch in $Value.ToCharArray()) {
        if ($ch -eq '\') {
            $backslashCount++
        }
        elseif ($ch -eq '"') {
            $quoted += ('\' * (($backslashCount * 2) + 1))
            $quoted += '"'
            $backslashCount = 0
        }
        else {
            if ($backslashCount -gt 0) {
                $quoted += ('\' * $backslashCount)
                $backslashCount = 0
            }
            $quoted += $ch
        }
    }
    if ($backslashCount -gt 0) {
        $quoted += ('\' * ($backslashCount * 2))
    }
    $quoted += '"'
    return $quoted
}

function Invoke-CursorAgentProcess {
    param(
        [string]$Executable,
        [string[]]$ArgumentList,
        [string]$WorkingDirectory
    )
    $fileName = $Executable
    $argsToUse = $ArgumentList
    if ($Executable -like '*.ps1') {
        $fileName = (Get-Command powershell.exe -ErrorAction Stop).Source
        $argsToUse = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $Executable) + $ArgumentList
    }
    $startInfo = New-Object System.Diagnostics.ProcessStartInfo
    $startInfo.FileName = $fileName
    $startInfo.UseShellExecute = $false
    $startInfo.WorkingDirectory = $WorkingDirectory
    if ($startInfo.PSObject.Properties.Name -contains 'ArgumentList') {
        foreach ($arg in $argsToUse) {
            [void]$startInfo.ArgumentList.Add([string]$arg)
        }
    }
    else {
        $startInfo.Arguments = ($argsToUse | ForEach-Object { Format-NativeCommandArgument $_ }) -join " "
    }
    $process = [System.Diagnostics.Process]::Start($startInfo)
    if ($null -eq $process) {
        throw "Failed to start cursor-agent."
    }
    $process.WaitForExit()
    return [pscustomobject]@{
        ExitCode = $process.ExitCode
        Executable = $fileName
        WorkingDirectory = $WorkingDirectory
        ProcessId = $process.Id
    }
}

function Write-FreshEntryJournalResult {
    param(
        [string]$JournalPath,
        [string]$CorrelationId,
        [string]$Outcome,
        [int]$ExitCode = -1,
        [string]$Executable = "",
        [string]$WorkingDirectory = "",
        [int]$ProcessId = -1,
        [string]$Detail = ""
    )

    $endUtc = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
    $lines = @(
        "## ENTRY_RESULT $endUtc",
        "- launch_correlation_id: $CorrelationId (launcher-generated; not a native Cursor task/session id)",
        "- outcome: $Outcome",
        "- child_exit_code: $ExitCode",
        "- child_executable: $Executable",
        "- child_working_directory: $WorkingDirectory",
        "- child_process_id: $ProcessId",
        "- native_cursor_task_session: unknown",
        "- package_result: unverified",
        ""
    )
    if ($Detail) {
        $lines = @(
            $lines[0],
            $lines[1],
            "- detail: $Detail"
        ) + $lines[2..($lines.Length - 1)]
    }
    Add-Content -LiteralPath $JournalPath -Value ($lines -join "`n") -Encoding UTF8
}

$cursor = Get-Command cursor-agent -ErrorAction Stop
$argumentList = @()
if (-not $Interactive) {
    $argumentList += @(
        "--print",
        "--output-format", "text"
    )
}
$argumentList += @(
    "--workspace", $resolvedTarget,
    "--model", $coordinatorModel
)
if ($PSBoundParameters.ContainsKey('ResumeSession')) {
    $argumentList += "--resume"
    if ($ResumeSession) {
        $argumentList += $ResumeSession
    }
}
if ($Force) {
    $argumentList += "--force"
}
if ($AutoReview) {
    $argumentList += "--auto-review"
}
$argumentList += "--"
$argumentList += $promptText

Write-Host "Starting Cursor synchronously in: $resolvedTarget"
$childResult = $null
try {
    $childResult = Invoke-CursorAgentProcess -Executable $cursor.Source -ArgumentList $argumentList -WorkingDirectory $resolvedTarget
}
catch {
    if ($journalStartWritten -and $journalPath -and $launchCorrelationId) {
        Write-FreshEntryJournalResult `
            -JournalPath $journalPath `
            -CorrelationId $launchCorrelationId `
            -Outcome "child_start_failure" `
            -Detail $_.Exception.Message
    }
    throw
}

if ($journalStartWritten -and $journalPath -and $launchCorrelationId -and $childResult) {
    Write-FreshEntryJournalResult `
        -JournalPath $journalPath `
        -CorrelationId $launchCorrelationId `
        -Outcome "child_exit" `
        -ExitCode $childResult.ExitCode `
        -Executable $childResult.Executable `
        -WorkingDirectory $childResult.WorkingDirectory `
        -ProcessId $childResult.ProcessId
}

exit $childResult.ExitCode
