$ErrorActionPreference = "Stop"

$logPath = if ($env:QMTOOL_RUNTIME_LOG_PATH) {
    $env:QMTOOL_RUNTIME_LOG_PATH
} else {
    Join-Path (Get-Location) ".cursor/runtime/subagent-start.log"
}
$logDirectory = Split-Path -Parent $logPath
if ($logDirectory) {
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
}

function Read-HostHookStdinBytes {
    $stdin = [Console]::OpenStandardInput()
    if ($null -eq $stdin) {
        $fallback = [Console]::In.ReadToEnd()
        if ([string]::IsNullOrEmpty($fallback)) {
            return @()
        }
        return [System.Text.Encoding]::UTF8.GetBytes($fallback)
    }
    $buffer = New-Object byte[] 8192
    $ms = New-Object System.IO.MemoryStream
    try {
        while (($read = $stdin.Read($buffer, 0, $buffer.Length)) -gt 0) {
            $ms.Write($buffer, 0, $read)
        }
        return $ms.ToArray()
    }
    finally {
        $ms.Dispose()
    }
}

function Decode-HostHookStdinText {
    param([byte[]]$Bytes)
    if ($null -eq $Bytes -or $Bytes.Length -eq 0) {
        $fallback = [Console]::In.ReadToEnd()
        if ([string]::IsNullOrWhiteSpace($fallback)) {
            return ""
        }
        return $fallback.Trim()
    }
    $offset = 0
    if ($Bytes.Length -ge 3 -and $Bytes[0] -eq 0xEF -and $Bytes[1] -eq 0xBB -and $Bytes[2] -eq 0xBF) {
        $offset = 3
    }
    elseif ($Bytes.Length -ge 2 -and $Bytes[0] -eq 0xFF -and $Bytes[1] -eq 0xFE) {
        if ($Bytes.Length -ge 4 -and $Bytes[2] -eq 0xFE -and $Bytes[3] -eq 0xFF) {
            return [System.Text.Encoding]::UTF32.GetString($Bytes, 4, $Bytes.Length - 4).Trim()
        }
        return [System.Text.Encoding]::Unicode.GetString($Bytes, 2, $Bytes.Length - 2).Trim()
    }
    return [System.Text.Encoding]::UTF8.GetString($Bytes, $offset, $Bytes.Length - $offset).Trim()
}

function Emit-HostHookParseFailure {
    param([string]$Reason)
    @{
        permission = "deny"
        user_message = $Reason
    } | ConvertTo-Json -Compress | Write-Output
    exit 1
}

function Emit-HostHookEnforcementFailure {
    @{
        permission = "deny"
        user_message = "Subagent enforcement could not be completed safely."
    } | ConvertTo-Json -Compress | Write-Output
    exit 1
}

function Test-IsConvertFromJsonObject {
    param($Value)
    if ($null -eq $Value) {
        return $false
    }
    if ($Value -is [string] -or $Value -is [bool] -or $Value -is [ValueType]) {
        return $false
    }
    if ($Value -is [System.Array] -or $Value -is [System.Collections.ArrayList]) {
        return $false
    }
    return ($Value.PSObject.TypeNames -contains 'System.Management.Automation.PSCustomObject')
}

function Write-HostIngressObservation {
    param(
        $InputData,
        [int]$IngressByteLength,
        [string]$LogPath
    )
    $propertyNames = @($InputData.PSObject.Properties.Name)
    $record = [ordered]@{
        timestamp = [DateTime]::UtcNow.ToString("o")
        observation = "host_payload_decoded"
        ingress_bytes = $IngressByteLength
        top_level_key_count = $propertyNames.Count
        hook_event_name_present = $propertyNames -contains "hook_event_name"
        subagent_type_present = $propertyNames -contains "subagent_type"
        validation_mode_present = $propertyNames -contains "validation_mode"
        task_present = $propertyNames -contains "task"
        subagent_model_present = $propertyNames -contains "subagent_model"
        model_field_present = $propertyNames -contains "model"
        subagent_id_present = $propertyNames -contains "subagent_id"
        tool_call_id_present = $propertyNames -contains "tool_call_id"
        parent_conversation_id_present = $propertyNames -contains "parent_conversation_id"
        is_parallel_worker_present = $propertyNames -contains "is_parallel_worker"
    }
    if ($propertyNames -contains "hook_event_name") {
        $record.hook_event_name = [string]$InputData.hook_event_name
    }
    if ($propertyNames -contains "subagent_type") {
        $record.subagent_type = [string]$InputData.subagent_type
    }
    if ($propertyNames -contains "validation_mode") {
        $record.validation_mode = [string]$InputData.validation_mode
    }
    $record | ConvertTo-Json -Compress | Add-Content -LiteralPath $LogPath -Encoding UTF8
}

$ingressBytes = @(Read-HostHookStdinBytes)
$raw = Decode-HostHookStdinText -Bytes $ingressBytes
if ([string]::IsNullOrWhiteSpace($raw)) {
    Emit-HostHookParseFailure -Reason "Hook payload was empty or unreadable."
}
$ingressByteLength = if ($ingressBytes.Length -gt 0) {
    $ingressBytes.Length
} else {
    [System.Text.Encoding]::UTF8.GetByteCount($raw)
}
try {
    $inputData = $raw | ConvertFrom-Json -ErrorAction Stop
}
catch {
    Emit-HostHookParseFailure -Reason "Hook payload could not be parsed as JSON."
}
if ($null -eq $inputData) {
    Emit-HostHookParseFailure -Reason "Hook payload decoded to null."
}
if (-not (Test-IsConvertFromJsonObject -Value $inputData)) {
    Emit-HostHookParseFailure -Reason "Hook payload must be a JSON object."
}
Write-HostIngressObservation -InputData $inputData -IngressByteLength $ingressByteLength -LogPath $logPath

try {
$validationMode = [string]$inputData.validation_mode
$task = [string]$inputData.task
$actual = [string]$inputData.subagent_model

function Get-Config {
    $configPath = Join-Path (Get-Location) ".cursor/agent-system.json"
    return Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Normalize-PathForCompare {
    param([string]$Value)
    if (-not $Value) { return "" }
    $trimmed = $Value.Trim()
    if ($trimmed -match '^/([a-zA-Z]):(/(.*))?$') {
        $drive = $Matches[1].ToUpperInvariant()
        $rest = if ($Matches[3]) { [string]$Matches[3] } else { "" }
        if ($rest) {
            $rest = $rest.Replace('/', '\')
            return [System.IO.Path]::GetFullPath("${drive}:\$rest")
        }
        return [System.IO.Path]::GetFullPath("${drive}:\")
    }
    $normalized = $trimmed.Replace('/', '\')
    return [System.IO.Path]::GetFullPath($normalized)
}

function Test-NormalizedPathEqual {
    param([string]$Left, [string]$Right)
    $leftPath = Normalize-PathForCompare $Left
    $rightPath = Normalize-PathForCompare $Right
    if (-not $leftPath -or -not $rightPath) { return $false }
    return [string]::Equals($leftPath, $rightPath, [System.StringComparison]::OrdinalIgnoreCase)
}

function Get-FileSha256 {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) { return $null }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = $null
    try {
        $stream = [System.IO.File]::OpenRead((Resolve-Path -LiteralPath $Path).Path)
        $bytes = $sha.ComputeHash($stream)
        return ([System.BitConverter]::ToString($bytes)).Replace("-", "")
    }
    finally {
        if ($null -ne $stream) { $stream.Dispose() }
        $sha.Dispose()
    }
}

function Test-NonEmptyString {
    param($Value)
    return ($null -ne $Value) -and ([string]$Value).Trim().Length -gt 0
}

function Get-GitValue {
    param(
        [string[]]$GitArguments,
        [string]$RepoRoot = ""
    )
    if (-not (Test-NonEmptyString $RepoRoot)) {
        $RepoRoot = (Get-Location).Path
    }
    $output = & git -C $RepoRoot @GitArguments 2>$null
    if ($LASTEXITCODE -ne 0) { return $null }
    if ($null -eq $output) { return $null }
    $text = [string]$output
    if ($text.Trim().Length -eq 0) { return $null }
    return $text.Trim()
}

function Resolve-PythonExecutable {
    $candidates = @()
    if ($env:QMTOOL_PYTHON_EXE) { $candidates += $env:QMTOOL_PYTHON_EXE }
    $candidates += @(
        "I:\Projekte\QMToolV7\.venv\Scripts\python.exe",
        "python",
        "py"
    )
    foreach ($candidate in $candidates) {
        if (-not $candidate) { continue }
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($null -ne $command) { return $command.Source }
    }
    return $null
}

function Get-GitPathSet {
    param([string]$RepoRoot, [string[]]$GitArguments)
    $output = & git -C $RepoRoot @GitArguments 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $output) { return @() }
    return @($output -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}

function Format-OutOfScopeDenialReason {
    param([string[]]$Paths)
    $normalized = @($Paths | ForEach-Object { ([string]$_).Replace('\', '/') } | Where-Object { $_ })
    if ($normalized.Count -eq 0) {
        return "out-of-scope repository mutation"
    }
    return "out-of-scope repository mutation: " + ($normalized -join ",")
}

function Invoke-GitCommand {
    param([string]$RepoRoot, [string[]]$GitArguments)
    $stderrCapture = [System.IO.Path]::GetTempFileName()
    $priorEap = $ErrorActionPreference
    try {
        $gitResult = & {
            param($Root, [string[]]$GitArgv, $ErrFile)
            $ErrorActionPreference = 'Continue'
            $stdoutRaw = & git -C $Root @GitArgv 2> $ErrFile
            $exitCode = $LASTEXITCODE
            [pscustomobject]@{
                stdoutRaw = $stdoutRaw
                exitCode = $exitCode
            }
        } -Root $RepoRoot -GitArgv $GitArguments -ErrFile $stderrCapture
        $exitCode = $gitResult.exitCode
        $stdoutRaw = $gitResult.stdoutRaw
        $stdout = ""
        if ($null -ne $stdoutRaw) {
            if ($stdoutRaw -is [System.Array]) {
                # Out-String restores Git's terminal newline; -join "`n" drops it and breaks diff_sha256.
                $stdout = [string]($stdoutRaw | Out-String)
            }
            else {
                $stdout = [string]$stdoutRaw
            }
        }
        $stderr = ""
        if (Test-Path -LiteralPath $stderrCapture) {
            $stderrContent = Get-Content -LiteralPath $stderrCapture -Raw -ErrorAction SilentlyContinue
            if ($stderrContent) {
                $stderr = [string]$stderrContent
            }
        }
        return @{
            ok = ($exitCode -eq 0)
            exit_code = $exitCode
            stdout = $stdout
            stderr = $stderr
        }
    }
    finally {
        $ErrorActionPreference = $priorEap
        if (Test-Path -LiteralPath $stderrCapture) {
            Remove-Item -LiteralPath $stderrCapture -Force -ErrorAction SilentlyContinue
        }
    }
}

function Get-GitPathSetStrict {
    param([string]$RepoRoot, [string[]]$GitArguments, [string]$FailureReason)
    $result = Invoke-GitCommand -RepoRoot $RepoRoot -GitArguments $GitArguments
    if (-not $result.ok) {
        return @{ ok = $false; reason = $FailureReason; paths = @() }
    }
    if ($result.stdout.Trim().Length -eq 0) {
        return @{ ok = $true; paths = @() }
    }
    return @{
        ok = $true
        paths = @($result.stdout -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    }
}

function Get-GitValueStrict {
    param([string]$RepoRoot, [string[]]$GitArguments, [string]$FailureReason)
    $result = Invoke-GitCommand -RepoRoot $RepoRoot -GitArguments $GitArguments
    if (-not $result.ok) {
        return @{ ok = $false; reason = $FailureReason }
    }
    return @{ ok = $true; value = $result.stdout.Trim() }
}

function Get-GitStageEntryStrict {
    param([string]$RepoRoot, [string]$RelativePath)
    $result = Invoke-GitCommand -RepoRoot $RepoRoot -GitArguments @("ls-files", "--stage", "--", $RelativePath)
    if (-not $result.ok) {
        return @{ ok = $false; reason = "git ls-files failed for foreign path: $RelativePath" }
    }
    if ($result.stdout.Trim().Length -eq 0) {
        return @{ ok = $true; indexed = $false; entry = $null }
    }
    return @{ ok = $true; indexed = $true; entry = $result.stdout.Trim() }
}

function Test-PathMatchesAllowlist {
    param([string]$Path, [string[]]$Allowlist)
    $normalized = ($Path -replace '\\', '/').Trim()
    foreach ($rule in $Allowlist) {
        $ruleNorm = ($rule -replace '\\', '/').TrimEnd('/')
        if ($normalized -eq $ruleNorm -or $normalized.StartsWith("$ruleNorm/")) {
            return $true
        }
    }
    return $false
}

function Invoke-WorkspaceSnapshotBinding {
    param($Config, $Policy)
    $allowlist = @($Policy.allowlist)
    $baseRef = [string]$Policy.base_ref
    $repoRoot = Get-GitValue @("rev-parse", "--show-toplevel")
    if (-not $repoRoot) {
        $repoRoot = (Get-Location).Path
    }
    $staged = Get-GitPathSet $repoRoot @("diff", "--cached", "--name-only")
    $unstaged = Get-GitPathSet $repoRoot @("diff", "--name-only")
    $untracked = Get-GitPathSet $repoRoot @("ls-files", "--others", "--exclude-standard")
    $changed = @($staged + $unstaged + $untracked | Select-Object -Unique)
    if ($Policy.scope_mode -eq "dirty") {
        $outOfScope = @($changed | Where-Object { -not (Test-PathMatchesAllowlist $_ $allowlist) })
        if ($outOfScope.Count -gt 0) {
            return @{
                valid = $false
                reason = (Format-OutOfScopeDenialReason @($outOfScope))
                out_of_scope_paths = $outOfScope
            }
        }
    }

    $python = Resolve-PythonExecutable
    if (-not $python) {
        return @{ valid = $false; reason = "workspace snapshot unavailable" }
    }
    $snapshotScript = Join-Path $repoRoot ".cursor/skills/execute-gated-macro/scripts/checkpoint_snapshot.py"
    if (-not (Test-Path -LiteralPath $snapshotScript)) {
        return @{ valid = $false; reason = "workspace snapshot owner missing" }
    }
    $token = [guid]::NewGuid().ToString("n")
    $relativeOutput = "build/pt/hook-snapshot-$token.json"
    $outputPath = Join-Path $repoRoot $relativeOutput
    $outputDir = Split-Path -Parent $outputPath
    if ($outputDir) { New-Item -ItemType Directory -Path $outputDir -Force | Out-Null }
    $checkpoint = if ($Policy.route -eq "critical_final_audit") { "FINAL_AUDIT" } else { "W1" }
    $snapshotArgs = @(
        $snapshotScript,
        "snapshot",
        "--root", $repoRoot,
        "--checkpoint", $checkpoint,
        "--phase", "hook-binding",
        "--output", ($relativeOutput -replace '\\', '/'),
        "--base-ref", $baseRef,
        "--scope-mode", [string]$Policy.scope_mode,
        "--fail-on-out-of-scope",
        "--fail-on-denial"
    )
    foreach ($path in $allowlist) { $snapshotArgs += @("--allow", $path) }
    if ($Policy.route -eq "critical_final_audit") {
        foreach ($foreignPath in (Get-DeclaredForeignRules -Config $Config)) {
            $snapshotArgs += @("--foreign", $foreignPath)
        }
    }
    & $python @snapshotArgs 2>$null | Out-Null
    if (-not (Test-Path -LiteralPath $outputPath)) {
        return @{ valid = $false; reason = "workspace snapshot failed" }
    }
    try {
        $snapshot = Get-Content -LiteralPath $outputPath -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    finally {
        if (Test-Path -LiteralPath $outputPath) { Remove-Item -LiteralPath $outputPath -Force }
    }
    if ($LASTEXITCODE -ne 0) {
        if ($snapshot.denial_reasons -and @($snapshot.denial_reasons).Count -gt 0) {
            return @{
                valid = $false
                reason = ([string]$snapshot.denial_reasons[0])
                denial_reasons = @($snapshot.denial_reasons)
                out_of_scope_paths = @($snapshot.out_of_scope_paths)
            }
        }
        if ($snapshot.out_of_scope_paths -and @($snapshot.out_of_scope_paths).Count -gt 0) {
            return @{
                valid = $false
                reason = (Format-OutOfScopeDenialReason @($snapshot.out_of_scope_paths))
                out_of_scope_paths = @($snapshot.out_of_scope_paths)
            }
        }
        return @{ valid = $false; reason = "workspace snapshot failed" }
    }
    if ($snapshot.denial_reasons -and @($snapshot.denial_reasons).Count -gt 0) {
        return @{
            valid = $false
            reason = ([string]$snapshot.denial_reasons[0])
            denial_reasons = @($snapshot.denial_reasons)
            out_of_scope_paths = @($snapshot.out_of_scope_paths)
        }
    }
    if ($snapshot.out_of_scope_paths -and @($snapshot.out_of_scope_paths).Count -gt 0) {
        return @{
            valid = $false
            reason = (Format-OutOfScopeDenialReason @($snapshot.out_of_scope_paths))
            out_of_scope_paths = @($snapshot.out_of_scope_paths)
        }
    }
    return @{
        valid = $true
        repository_state_sha256 = [string]$snapshot.repository_state_sha256
        out_of_scope_paths = @($snapshot.out_of_scope_paths)
    }
}

function Test-SafeEvidenceAttemptSegment {
    param([string]$Segment)
    if (-not (Test-NonEmptyString $Segment)) { return $false }
    $value = ([string]$Segment).Trim()
    if ($value -eq '.' -or $value -eq '..') { return $false }
    if ($value -match '[/\\]') { return $false }
    if ($value -match '^[a-zA-Z]:') { return $false }
    if ($value.StartsWith('\\')) { return $false }
    if ($value -match '\.\.') { return $false }
    return ($value -match '^[A-Za-z0-9._-]+$')
}

function Get-CanonicalEvidencePaths {
    param([string]$EvidenceAttempt, $Config, $Template = $null)
    if (-not (Test-SafeEvidenceAttemptSegment $EvidenceAttempt)) {
        return @{ valid = $false; reason = "invalid evidence_attempt segment" }
    }
    if ($null -eq $Template) {
        $Template = $Config.external_codex_bound_review.evidence_path_template
    }
    $repoRoot = (Get-Location).Path
    $rootRelative = ([string]$Template.root).Replace('\', '/').TrimEnd('/')
    $contractFile = [string]$Template.contract_file
    $manifestFile = [string]$Template.manifest_file
    $contractRel = "$rootRelative/$EvidenceAttempt/$contractFile"
    $manifestRel = "$rootRelative/$EvidenceAttempt/$manifestFile"
    $canonicalRoot = Normalize-PathForCompare (Join-Path $repoRoot $rootRelative)
    $candidateRoot = Normalize-PathForCompare (Join-Path $repoRoot (Join-Path $rootRelative $EvidenceAttempt))
    $candidateContract = Normalize-PathForCompare (Join-Path $repoRoot ($contractRel -replace '/', '\'))
    $candidateManifest = Normalize-PathForCompare (Join-Path $repoRoot ($manifestRel -replace '/', '\'))
    if (-not $candidateRoot.StartsWith($canonicalRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        return @{ valid = $false; reason = "evidence path escapes canonical root" }
    }
    if (-not $candidateContract.StartsWith($canonicalRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
        -not $candidateManifest.StartsWith($canonicalRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        return @{ valid = $false; reason = "evidence artifact escapes canonical root" }
    }
    return @{
        valid = $true
        contract_path = $contractRel
        manifest_path = $manifestRel
    }
}

function Get-ReviewRouteBindings {
    param($Config)
    return $Config.external_codex_bound_review.review_route_bindings
}

function Test-ExternalReviewRouteBinding {
    param($Handoff, $Config)
    $bindings = Get-ReviewRouteBindings -Config $Config
    $packageId = [string]$Handoff.package_id
    $checkpointId = [string]$Handoff.checkpoint_id
    $reviewNeed = [string]$Handoff.review_need
    if ($null -eq $bindings) {
        return @{ valid = $false; reason = "unknown package review route" }
    }
    $packageBindings = $null
    if ($bindings -is [hashtable]) {
        if (-not $bindings.ContainsKey($packageId)) {
            return @{ valid = $false; reason = "unknown package review route" }
        }
        $packageBindings = $bindings[$packageId]
    }
    elseif ($bindings.PSObject.Properties.Name -contains $packageId) {
        $packageBindings = $bindings.$packageId
    }
    else {
        return @{ valid = $false; reason = "unknown package review route" }
    }
    $escalation = $packageBindings.checkpoint_escalation
    $finalAudit = $packageBindings.critical_final_audit
    if ($null -eq $Handoff.ladder_history) {
        $history = @()
    }
    else {
        $history = @($Handoff.ladder_history)
    }
    $isEscalation = ($checkpointId -eq [string]$escalation.checkpoint_id -and
        $reviewNeed -eq [string]$escalation.review_need)
    $isFinalAudit = ($checkpointId -eq [string]$finalAudit.checkpoint_id -and
        $reviewNeed -eq [string]$finalAudit.review_need)
    if ($isEscalation -and $isFinalAudit) {
        return @{ valid = $false; reason = "ambiguous review route facts" }
    }
    if (-not $isEscalation -and -not $isFinalAudit) {
        return @{ valid = $false; reason = "review_need and checkpoint_id do not match an authorized route" }
    }
    if ($isFinalAudit) {
        if (-not ($finalAudit.direct_external -is [bool]) -or $finalAudit.direct_external -ne $true) {
            return @{ valid = $false; reason = "critical final audit route is not configured as direct external" }
        }
        if (-not ($finalAudit.forbid_ladder_history -is [bool]) -or $finalAudit.forbid_ladder_history -ne $true) {
            return @{ valid = $false; reason = "critical final audit route does not strictly forbid ladder history" }
        }
        if ($history.Count -gt 0) {
            return @{ valid = $false; reason = "critical final audit must not include checkpoint-reviewer ladder history" }
        }
        return @{ valid = $true; route = "critical_final_audit"; ladder_role = $null }
    }
    if (-not ($escalation.require_complete_ladder -is [bool]) -or $escalation.require_complete_ladder -ne $true) {
        return @{ valid = $false; reason = "checkpoint escalation route does not strictly require a complete ladder" }
    }
    $ladderRole = [string]$escalation.ladder_role
    if ([string]::IsNullOrWhiteSpace($ladderRole)) {
        return @{ valid = $false; reason = "checkpoint escalation route is missing ladder_role" }
    }
    $ladderCheck = Test-ExternalCodexLadderPrerequisite -History $Handoff.ladder_history -Role $ladderRole -Config $Config
    if (-not $ladderCheck.valid) {
        return @{ valid = $false; reason = $ladderCheck.reason }
    }
    return @{ valid = $true; route = "checkpoint_escalation"; ladder_role = $ladderRole }
}

function Get-ExternalReviewRoutePolicy {
    param($Handoff, $Config)
    $routeCheck = Test-ExternalReviewRouteBinding -Handoff $Handoff -Config $Config
    if (-not $routeCheck.valid) {
        return @{ valid = $false; reason = $routeCheck.reason }
    }
    $contract = $Config.external_codex_bound_review
    if ($routeCheck.route -eq "critical_final_audit") {
        return @{
            valid = $true
            route = "critical_final_audit"
            allowlist = @($contract.w3_allowlist_paths)
            base_ref = [string]$contract.base_ref
            evidence_template = $contract.final_audit_evidence_path_template
            scope_mode = "committed_final_audit"
        }
    }
    return @{
        valid = $true
        route = "checkpoint_escalation"
        allowlist = @($contract.w1_allowlist_paths)
        base_ref = [string]$contract.base_ref
        evidence_template = $contract.evidence_path_template
        scope_mode = "dirty"
    }
}

function Get-DeclaredForeignRules {
    param($Config)
    return @($Config.external_codex_bound_review.declared_foreign_bindings | ForEach-Object { [string]$_.path })
}

function Get-CanonicalForeignBindingRecords {
    param([string]$RepoRoot, $Config)
    $bindings = @($Config.external_codex_bound_review.declared_foreign_bindings)
    $records = @()
    foreach ($binding in $bindings) {
        $relative = ([string]$binding.path).Replace('\', '/')
        $absolute = Join-Path $RepoRoot ($relative -replace '/', '\')
        $stage = Get-GitStageEntryStrict -RepoRoot $RepoRoot -RelativePath $relative
        if (-not $stage.ok) {
            return @{ valid = $false; reason = $stage.reason }
        }
        $indexState = if ($stage.indexed) { "indexed" } else { "untracked" }
        if (-not (Test-Path -LiteralPath $absolute -PathType Leaf)) {
            return @{ valid = $false; reason = "missing expected foreign binding: $relative" }
        }
        $size = (Get-Item -LiteralPath $absolute).Length
        if ([int]$binding.size -ne [int]$size) {
            return @{ valid = $false; reason = "foreign path size mismatch: $relative" }
        }
        $hash = Get-FileSha256 $absolute
        if ($null -eq $hash) {
            return @{ valid = $false; reason = "foreign path hash unavailable: $relative" }
        }
        if ($hash.ToLowerInvariant() -ne ([string]$binding.sha256).ToLowerInvariant()) {
            return @{ valid = $false; reason = "foreign path hash mismatch: $relative" }
        }
        $records += @{
            path = $relative
            size = [int]$size
            sha256 = $hash.ToLowerInvariant()
            index_state = $indexState
            index_entry = $stage.entry
        }
    }
    return @{ valid = $true; records = $records }
}

function Test-DeclaredForeignBinding {
    param([string]$RepoRoot, $Config)
    $bindings = @($Config.external_codex_bound_review.declared_foreign_bindings)
    if ($bindings.Count -eq 0) {
        return @{ valid = $true }
    }
    $expectedPaths = @($bindings | ForEach-Object { ([string]$_.path).Replace('\', '/') })
    $staged = Get-GitPathSetStrict $RepoRoot @("diff", "--cached", "--name-only") "git diff --cached failed for foreign binding"
    if (-not $staged.ok) { return @{ valid = $false; reason = $staged.reason } }
    $unstaged = Get-GitPathSetStrict $RepoRoot @("diff", "--name-only") "git diff failed for foreign binding"
    if (-not $unstaged.ok) { return @{ valid = $false; reason = $unstaged.reason } }
    $untracked = Get-GitPathSetStrict $RepoRoot @("ls-files", "--others", "--exclude-standard") "git ls-files --others failed for foreign binding"
    if (-not $untracked.ok) { return @{ valid = $false; reason = $untracked.reason } }

    foreach ($expected in $expectedPaths) {
        if ($expected -in @($staged.paths)) {
            return @{ valid = $false; reason = "foreign path staged denied: $expected" }
        }
        if ($expected -in @($unstaged.paths)) {
            return @{ valid = $false; reason = "foreign path mutation denied: $expected" }
        }
    }

    foreach ($path in @($untracked.paths)) {
        $normalized = ($path -replace '\\', '/').Trim()
        if ($normalized -in $expectedPaths) {
            continue
        }
        foreach ($expected in $expectedPaths) {
            if ($normalized.StartsWith("$expected/")) {
                return @{ valid = $false; reason = "foreign child path denied: $normalized" }
            }
        }
        return @{ valid = $false; reason = "foreign binding add denied: $normalized" }
    }

    $canonical = Get-CanonicalForeignBindingRecords -RepoRoot $RepoRoot -Config $Config
    if (-not $canonical.valid) {
        return @{ valid = $false; reason = $canonical.reason }
    }
    foreach ($record in $canonical.records) {
        $relative = [string]$record.path
        if ($record.index_state -ne "untracked") {
            return @{ valid = $false; reason = "foreign path must remain untracked: $relative" }
        }
        if ($relative -notin @($untracked.paths)) {
            return @{ valid = $false; reason = "foreign path must be untracked only: $relative" }
        }
    }
    if (@($canonical.records).Count -ne $bindings.Count) {
        return @{ valid = $false; reason = "foreign binding drop denied" }
    }
    return @{ valid = $true; records = $canonical.records }
}

function Test-HandoffForeignOverrideDenied {
    param($Handoff)
    foreach ($field in @(
        "declared_foreign_bindings",
        "declared_foreign_paths",
        "foreign_bindings",
        "foreign_override",
        "foreign_rules"
    )) {
        if ($Handoff.PSObject.Properties.Name.Contains($field)) {
            return @{ valid = $false; reason = "foreign binding override denied: $field" }
        }
    }
    return @{ valid = $true }
}

function Test-ManifestDeclaredForeignBindings {
    param([string]$RepoRoot, [string]$ManifestRelativePath, $Config)
    $manifestPath = Join-Path $RepoRoot ($ManifestRelativePath -replace '/', '\')
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        return @{ valid = $false; reason = "manifest missing for foreign binding validation" }
    }
    try {
        $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        return @{ valid = $false; reason = "manifest malformed for foreign binding validation" }
    }
    if (-not $manifest.PSObject.Properties.Name.Contains("declared_foreign_bindings")) {
        return @{ valid = $false; reason = "manifest missing declared_foreign_bindings" }
    }
    $canonical = Get-CanonicalForeignBindingRecords -RepoRoot $RepoRoot -Config $Config
    if (-not $canonical.valid) {
        return @{ valid = $false; reason = $canonical.reason }
    }
    $manifestRecords = @($manifest.declared_foreign_bindings)
    $expectedByPath = @{}
    foreach ($record in $canonical.records) {
        $expectedByPath[[string]$record.path] = $record
    }
    $manifestByPath = @{}
    foreach ($actual in $manifestRecords) {
        $actualPath = ([string]$actual.path).Replace('\', '/')
        if ($manifestByPath.ContainsKey($actualPath)) {
            return @{ valid = $false; reason = "manifest foreign binding duplicate denied: $actualPath" }
        }
        $manifestByPath[$actualPath] = $actual
    }
    foreach ($path in $expectedByPath.Keys) {
        if (-not $manifestByPath.ContainsKey($path)) {
            return @{ valid = $false; reason = "manifest foreign binding drop denied: $path" }
        }
    }
    foreach ($path in $manifestByPath.Keys) {
        if (-not $expectedByPath.ContainsKey($path)) {
            return @{ valid = $false; reason = "manifest foreign binding add denied: $path" }
        }
        $expected = $expectedByPath[$path]
        $actual = $manifestByPath[$path]
        foreach ($requiredField in @("path", "size", "sha256", "index_state", "index_entry")) {
            if (-not $actual.PSObject.Properties.Name.Contains($requiredField)) {
                return @{ valid = $false; reason = "manifest foreign binding missing field ${requiredField}: $path" }
            }
        }
        if ($null -eq $actual.path -or [string]::IsNullOrWhiteSpace([string]$actual.path)) {
            return @{ valid = $false; reason = "manifest foreign binding missing field path: $path" }
        }
        if ($null -eq $actual.size) {
            return @{ valid = $false; reason = "manifest foreign binding missing field size: $path" }
        }
        if ($null -eq $actual.sha256 -or [string]::IsNullOrWhiteSpace([string]$actual.sha256)) {
            return @{ valid = $false; reason = "manifest foreign binding missing field sha256: $path" }
        }
        if ($null -eq $actual.index_state -or [string]::IsNullOrWhiteSpace([string]$actual.index_state)) {
            return @{ valid = $false; reason = "manifest foreign binding missing field index_state: $path" }
        }
        if ([int]$actual.size -ne [int]$expected.size) {
            return @{ valid = $false; reason = "manifest foreign binding size mismatch: $path" }
        }
        if ([string]$actual.sha256 -ne [string]$expected.sha256) {
            return @{ valid = $false; reason = "manifest foreign binding hash mismatch: $path" }
        }
        if ([string]$actual.index_state -ne [string]$expected.index_state) {
            return @{ valid = $false; reason = "manifest foreign binding index_state mismatch: $path" }
        }
        $expectedIndexEntry = if ($null -eq $expected.index_entry) { $null } else { [string]$expected.index_entry }
        $actualIndexEntry = if ($actual.PSObject.Properties.Name.Contains("index_entry") -and $null -ne $actual.index_entry) {
            [string]$actual.index_entry
        } else {
            $null
        }
        if ($expectedIndexEntry -ne $actualIndexEntry) {
            return @{ valid = $false; reason = "manifest foreign binding index_entry mismatch: $path" }
        }
    }
    return @{ valid = $true }
}

function Test-StrictBooleanField {
    param($Object, [string]$Name)
    if ($null -eq $Object) { return $false }
    if (-not $Object.PSObject.Properties.Name.Contains($Name)) { return $false }
    return ($Object.$Name -is [bool])
}

function Get-WorkspaceDerivedBindings {
    param($Config, $Policy)
    $allowlist = @($Policy.allowlist)
    $baseRef = [string]$Policy.base_ref
    $cwdRoot = (Get-Location).Path
    $repoRootResult = Get-GitValueStrict -RepoRoot $cwdRoot -GitArguments @("rev-parse", "--show-toplevel") -FailureReason "git rev-parse failed for workspace binding"
    if (-not $repoRootResult.ok) {
        return @{
            target_root = Normalize-PathForCompare $cwdRoot
            snapshot_error = $repoRootResult.reason
        }
    }
    $repoRoot = $repoRootResult.value
    if ($Policy.scope_mode -eq "committed_final_audit") {
        $baseHeadResult = Get-GitValueStrict -RepoRoot $repoRoot -GitArguments @("rev-parse", "--verify", "$baseRef^{commit}") -FailureReason "git rev-parse base failed for final audit binding"
        if (-not $baseHeadResult.ok) {
            return @{
                target_root = Normalize-PathForCompare $repoRoot
                snapshot_error = $baseHeadResult.reason
            }
        }
        $priorEap = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            & git -C $repoRoot merge-base --is-ancestor $baseRef HEAD 2>$null | Out-Null
            $ancestorExit = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $priorEap
        }
        if ($ancestorExit -eq 1) {
            return @{
                target_root = Normalize-PathForCompare $repoRoot
                snapshot_error = "base ref is not an ancestor of HEAD"
            }
        }
        if ($ancestorExit -ne 0) {
            return @{
                target_root = Normalize-PathForCompare $repoRoot
                snapshot_error = "git merge-base failed for final audit binding"
            }
        }
        $diffResult = Invoke-GitCommand -RepoRoot $repoRoot -GitArguments @("diff", $baseRef, "HEAD")
        if (-not $diffResult.ok) {
            return @{
                target_root = Normalize-PathForCompare $repoRoot
                snapshot_error = "git diff failed for final audit binding"
            }
        }
        $diffText = $diffResult.stdout
        $branchResult = Get-GitValueStrict -RepoRoot $repoRoot -GitArguments @("branch", "--show-current") -FailureReason "git branch failed for final audit binding"
        if (-not $branchResult.ok) {
            return @{
                target_root = Normalize-PathForCompare $repoRoot
                snapshot_error = $branchResult.reason
            }
        }
        $reviewedHeadResult = Get-GitValueStrict -RepoRoot $repoRoot -GitArguments @("rev-parse", "HEAD") -FailureReason "git rev-parse HEAD failed for final audit binding"
        if (-not $reviewedHeadResult.ok) {
            return @{
                target_root = Normalize-PathForCompare $repoRoot
                snapshot_error = $reviewedHeadResult.reason
            }
        }
        $branch = $branchResult.value
        $reviewedHead = $reviewedHeadResult.value
        $baseHead = $baseHeadResult.value
    }
    else {
        $diffArgs = @("diff", $baseRef, "--") + $allowlist
        $diffResult = Invoke-GitCommand -RepoRoot $repoRoot -GitArguments $diffArgs
        if (-not $diffResult.ok) {
            return @{
                target_root = Normalize-PathForCompare $repoRoot
                snapshot_error = "git diff failed for checkpoint escalation binding"
            }
        }
        $diffText = $diffResult.stdout
        $branch = Get-GitValue -RepoRoot $repoRoot @("branch", "--show-current")
        $reviewedHead = Get-GitValue -RepoRoot $repoRoot @("rev-parse", "HEAD")
        $baseHead = Get-GitValue -RepoRoot $repoRoot @("rev-parse", $baseRef)
    }
    if ($null -eq $diffText) { $diffText = "" }
    $diffSha = Get-TextSha256 $diffText
    if ($Policy.route -eq "critical_final_audit") {
        $foreignPrecheck = Test-DeclaredForeignBinding -RepoRoot $repoRoot -Config $Config
        if (-not $foreignPrecheck.valid) {
            return @{
                target_root = Normalize-PathForCompare $repoRoot
                branch = $branch
                reviewed_head = $reviewedHead
                base_head = $baseHead
                diff_sha256 = $diffSha
                route = [string]$Policy.route
                scope_mode = [string]$Policy.scope_mode
                snapshot_error = $foreignPrecheck.reason
            }
        }
    }
    $snapshot = Invoke-WorkspaceSnapshotBinding -Config $Config -Policy $Policy
    $binding = @{
        target_root = Normalize-PathForCompare $repoRoot
        branch = $branch
        reviewed_head = $reviewedHead
        base_head = $baseHead
        diff_sha256 = $diffSha
        route = [string]$Policy.route
        scope_mode = [string]$Policy.scope_mode
    }
    if ($snapshot.valid) {
        $binding.repository_state_sha256 = $snapshot.repository_state_sha256
        $binding.out_of_scope_paths = @($snapshot.out_of_scope_paths)
    }
    else {
        $binding.snapshot_error = $snapshot.reason
        if ($snapshot.denial_reasons) {
            $binding.denial_reasons = @($snapshot.denial_reasons)
        }
        if ($snapshot.out_of_scope_paths) {
            $binding.out_of_scope_paths = @($snapshot.out_of_scope_paths)
        }
    }
    return $binding
}

function Get-TextSha256 {
    param([string]$Text)
    $normalized = ($Text -replace "`r`n", "`n")
    $sha = [System.Security.Cryptography.SHA256]::Create()
    try {
        $bytes = [System.Text.Encoding]::UTF8.GetBytes($normalized)
        $hash = $sha.ComputeHash($bytes)
        return ([System.BitConverter]::ToString($hash)).Replace("-", "")
    }
    finally {
        $sha.Dispose()
    }
}

function Test-LadderHistoryForAttempt {
    param(
        [string]$Role,
        $History,
        [int]$Attempt,
        $Config
    )
    if ($Attempt -le 1) {
        if ($null -eq $History) { return @{ valid = $true } }
        if (@($History).Count -gt 0) {
            return @{ valid = $false; reason = "attempt 1 must not include prior ladder history" }
        }
        return @{ valid = $true }
    }
    $requiredPrior = $Attempt - 1
    if ($null -eq $History) {
        return @{ valid = $false; reason = "missing ladder_history for attempt $Attempt" }
    }
    $entries = @($History)
    if ($entries.Count -ne $requiredPrior) {
        return @{ valid = $false; reason = "ladder_history must contain exactly $requiredPrior prior attempts" }
    }
    for ($i = 0; $i -lt $entries.Count; $i++) {
        $entry = $entries[$i]
        $expectedAttempt = $i + 1
        if ([int]$entry.attempt -ne $expectedAttempt) {
            return @{ valid = $false; reason = "ladder_history attempt order mismatch at index $i" }
        }
        if ([string]$entry.role -ne $Role) {
            return @{ valid = $false; reason = "ladder_history role mismatch at attempt $expectedAttempt" }
        }
        if ([string]$entry.result_category -ne "UNAVAILABLE") {
            return @{ valid = $false; reason = "ladder_history attempt $expectedAttempt must be UNAVAILABLE" }
        }
        $expectedRung = (Get-RoleLadderRungs -Role $Role -Config $Config)[$i]
        if ($null -eq $expectedRung) {
            return @{ valid = $false; reason = "ladder_history missing configured rung at attempt $expectedAttempt" }
        }
        if ([string]$entry.requested_model -ne [string]$expectedRung.model) {
            return @{ valid = $false; reason = "ladder_history model mismatch at attempt $expectedAttempt" }
        }
        if (-not (Test-NonEmptyString $entry.requested_model)) {
            return @{ valid = $false; reason = "ladder_history missing requested_model at attempt $expectedAttempt" }
        }
        if (-not (Test-NonEmptyString $entry.agent_id)) {
            return @{ valid = $false; reason = "ladder_history missing agent_id at attempt $expectedAttempt" }
        }
        if (-not (Test-NonEmptyString $entry.signal)) {
            return @{ valid = $false; reason = "ladder_history missing signal at attempt $expectedAttempt" }
        }
    }
    return @{ valid = $true }
}

function Test-ExternalCodexLadderPrerequisite {
    param($History, [string]$Role, $Config)
    $roleProp = $Config.review_model_fallback.roles.PSObject.Properties[$Role]
    if ($null -eq $roleProp) { return @{ valid = $false; reason = "unknown review role" } }
    $rungs = @($roleProp.Value.ladder)
    $gptRung = $rungs | Where-Object { $_.gpt_fallback -eq $true } | Select-Object -First 1
    if ($null -eq $gptRung) { return @{ valid = $false; reason = "missing gpt rung" } }
    if ($null -eq $History) {
        return @{ valid = $false; reason = "missing ladder_history for external codex" }
    }
    $entries = @($History)
    if ($entries.Count -ne [int]$gptRung.attempt) {
        return @{ valid = $false; reason = "ladder_history must contain all attempts through cursor gpt" }
    }
    for ($i = 0; $i -lt $entries.Count; $i++) {
        $entry = $entries[$i]
        $expectedAttempt = $i + 1
        $expectedRung = $rungs[$i]
        if ([int]$entry.attempt -ne $expectedAttempt) {
            return @{ valid = $false; reason = "ladder_history attempt order mismatch at index $i" }
        }
        if ([string]$entry.role -ne $Role) {
            return @{ valid = $false; reason = "ladder_history role mismatch at attempt $expectedAttempt" }
        }
        if ([string]$entry.requested_model -ne [string]$expectedRung.model) {
            return @{ valid = $false; reason = "ladder_history model mismatch at attempt $expectedAttempt" }
        }
        if ([string]$entry.result_category -eq "FAIL_SUBSTANTIVE") {
            return @{ valid = $false; reason = "substantive fail blocks external codex" }
        }
        if ([string]$entry.result_category -ne "UNAVAILABLE") {
            return @{ valid = $false; reason = "ladder_history attempt $expectedAttempt must be UNAVAILABLE" }
        }
        if (-not (Test-NonEmptyString $entry.agent_id)) {
            return @{ valid = $false; reason = "ladder_history missing agent_id at attempt $expectedAttempt" }
        }
        if (-not (Test-NonEmptyString $entry.signal)) {
            return @{ valid = $false; reason = "ladder_history missing signal at attempt $expectedAttempt" }
        }
    }
    return @{ valid = $true }
}

function Invoke-ExternalCodexWorkspaceValidation {
    param($Handoff, $Config, [string]$Mode)
    $contract = $Config.external_codex_bound_review
    $allowedHosts = @("codex-chatgpt-authenticated")
    $requiredFields = if ($Mode -eq "EXTERNAL_CODEX_PRE_HANDOFF") {
        @($contract.pre_handoff_required_fields)
    } else {
        @($contract.bound_review_required_fields)
    }

    function Invalid([string]$Reason) {
        return @{
            permission = "deny"
            validation_mode = $Mode
            handoff = "HANDOFF_INVALID"
            status = "BLOCKED_HUMAN"
            reason = $Reason
            authenticates_origin = $false
            authenticates_serving_model = $false
        }
    }

    if ($null -eq $Handoff) { return Invalid("missing handoff") }
    $foreignOverride = Test-HandoffForeignOverrideDenied -Handoff $Handoff
    if (-not $foreignOverride.valid) { return Invalid($foreignOverride.reason) }
    foreach ($field in $requiredFields) {
        if (-not $Handoff.PSObject.Properties.Name.Contains($field)) {
            return Invalid("missing field $field")
        }
        if ($field -in @("mutation_detected", "separate_context", "read_only", "findings", "ladder_history")) { continue }
        if (-not (Test-NonEmptyString $Handoff.$field)) {
            return Invalid("empty field $field")
        }
    }
    if ($Mode -eq "EXTERNAL_CODEX_PRE_HANDOFF") {
        foreach ($forbidden in @($contract.pre_handoff_forbidden_fields)) {
            if ($Handoff.PSObject.Properties.Name.Contains($forbidden) -and $null -ne $Handoff.$forbidden) {
                return Invalid("pre-handoff includes completed-review field $forbidden")
            }
        }
    }
    if (-not (Test-StrictBooleanField $Handoff "separate_context")) {
        return Invalid("separate_context must be strict boolean")
    }
    if (-not (Test-StrictBooleanField $Handoff "read_only")) {
        return Invalid("read_only must be strict boolean")
    }
    if (-not (Test-StrictBooleanField $Handoff "mutation_detected")) {
        return Invalid("mutation_detected must be strict boolean")
    }
    if ($Handoff.package_id -ne "AGENT-COST-01") { return Invalid("wrong package") }
    if (-not $Handoff.separate_context -or -not $Handoff.read_only) {
        return Invalid("not separate read-only")
    }
    if ($Handoff.mutation_detected) { return Invalid("mutation detected") }
    $author = [string]$Handoff.author_id
    $reviewer = [string]$Handoff.reviewer_id
    $implementer = [string]$Handoff.implementer_id
    if ($author -eq $reviewer -or $implementer -eq $reviewer -or $author -eq $implementer) {
        return Invalid("role separation")
    }
    if ($allowedHosts -notcontains [string]$Handoff.external_host) {
        return Invalid("external host not allowed")
    }
    if ($Mode -eq "EXTERNAL_CODEX_BOUND_REVIEW") {
        if ($Handoff.verdict -notin @("PASS", "FAIL")) { return Invalid("invalid verdict") }
        if ($Handoff.verdict -eq "FAIL") { return Invalid("external FAIL blocks") }
    }
    if ($null -eq $Handoff.findings -and $Mode -eq "EXTERNAL_CODEX_BOUND_REVIEW") {
        return Invalid("missing findings")
    }

    $routeCheck = Test-ExternalReviewRouteBinding -Handoff $Handoff -Config $Config
    if (-not $routeCheck.valid) { return Invalid($routeCheck.reason) }

    $policy = Get-ExternalReviewRoutePolicy -Handoff $Handoff -Config $Config
    if (-not $policy.valid) { return Invalid($policy.reason) }

    $derived = Get-WorkspaceDerivedBindings -Config $Config -Policy $policy
    if ($derived.snapshot_error) { return Invalid($derived.snapshot_error) }
    if ($derived.out_of_scope_paths -and @($derived.out_of_scope_paths).Count -gt 0) {
        return Invalid((Format-OutOfScopeDenialReason @($derived.out_of_scope_paths)))
    }
    if (-not $derived.repository_state_sha256) {
        return Invalid("workspace fingerprint unavailable")
    }
    if ($policy.route -eq "critical_final_audit") {
        $foreignCheck = Test-DeclaredForeignBinding -RepoRoot $derived.target_root -Config $Config
        if (-not $foreignCheck.valid) {
            return Invalid($foreignCheck.reason)
        }
    }
    if ([string]$Handoff.reviewed_head -ne $derived.reviewed_head) { return Invalid("stale head") }
    if ([string]$Handoff.base_head -ne $derived.base_head) { return Invalid("wrong base") }
    if ([string]$Handoff.branch -ne $derived.branch) { return Invalid("wrong branch") }
    if (-not (Test-NormalizedPathEqual ([string]$Handoff.target_root) $derived.target_root)) {
        return Invalid("foreign target")
    }
    if ([string]$Handoff.diff_sha256 -ne $derived.diff_sha256) { return Invalid("stale diff") }
    if ([string]$Handoff.pre_fingerprint -ne $derived.repository_state_sha256) {
        return Invalid("pre fingerprint not workspace-derived")
    }
    if ([string]$Handoff.post_fingerprint -ne $derived.repository_state_sha256) {
        return Invalid("post fingerprint not workspace-derived")
    }
    if ([string]$Handoff.pre_fingerprint -eq "pending_parent_capture" -or
        [string]$Handoff.post_fingerprint -eq "pending_parent_capture") {
        return Invalid("pending parent capture cannot prove immutability")
    }

    $canonical = Get-CanonicalEvidencePaths -EvidenceAttempt ([string]$Handoff.evidence_attempt) -Config $Config -Template $policy.evidence_template
    if ($canonical.valid -ne $true) {
        return Invalid([string]$canonical.reason)
    }
    $claimedContract = ([string]$Handoff.contract_path).Replace('\', '/')
    $claimedManifest = ([string]$Handoff.evidence_manifest_path).Replace('\', '/')
    if ($claimedContract -ne $canonical.contract_path) {
        return Invalid("contract path not canonical")
    }
    if ($claimedManifest -ne $canonical.manifest_path) {
        return Invalid("manifest path not canonical")
    }

    $repoRoot = $derived.target_root
    $contractPath = Join-Path $repoRoot $canonical.contract_path
    $computedContract = Get-FileSha256 $contractPath
    if ($computedContract -ne [string]$Handoff.contract_sha256) {
        return Invalid("contract hash mismatch")
    }

    $manifestPath = Join-Path $repoRoot $canonical.manifest_path
    $computedManifest = Get-FileSha256 $manifestPath
    if ($computedManifest -ne [string]$Handoff.evidence_manifest_sha256) {
        return Invalid("evidence manifest hash mismatch")
    }
    if ($policy.route -eq "critical_final_audit") {
        $manifestForeign = Test-ManifestDeclaredForeignBindings -RepoRoot $repoRoot -ManifestRelativePath $canonical.manifest_path -Config $Config
        if (-not $manifestForeign.valid) {
            return Invalid($manifestForeign.reason)
        }
    }

    if ($Mode -eq "EXTERNAL_CODEX_PRE_HANDOFF") {
        return @{
            permission = "allow"
            validation_mode = $Mode
            handoff = "PRE_HANDOFF_READY"
            status = "READY"
            reason = "workspace-derived pre-handoff binding valid"
            authenticates_origin = $false
            authenticates_serving_model = $false
            derived = $derived
        }
    }

    return @{
        permission = "allow"
        validation_mode = $Mode
        handoff = "HANDOFF_READY"
        status = "CONTINUE"
        reason = "workspace-derived binding valid"
        authenticates_origin = $false
        authenticates_serving_model = $false
        derived = $derived
    }
}

function Get-RoleLadderRungs {
    param([string]$Role, $Config)
    $fallback = $Config.review_model_fallback
    if ($null -eq $fallback) { return @() }
    $roleProp = $fallback.roles.PSObject.Properties[$Role]
    if ($null -eq $roleProp) { return @() }
    return @($roleProp.Value.ladder)
}

function Get-RoleAuthorizedGptModels {
    param([string]$Role, $Config)
    $models = [System.Collections.Generic.List[string]]::new()
    foreach ($rung in Get-RoleLadderRungs -Role $Role -Config $Config) {
        if ($rung.gpt_fallback -eq $true) {
            $models.Add((Normalize-ModelToken ([string]$rung.model)))
        }
    }
    return $models
}

function Normalize-ModelToken {
    param([string]$Value)
    return ([string]$Value).Trim().ToLowerInvariant()
}

function Test-RejectedModelFromConfig {
    param([string]$ActualLower, $Config, [string]$Role)
    if (-not $ActualLower) { return $true }
    foreach ($pattern in @($Config.model_binding.rejected_patterns)) {
        $p = [string]$pattern
        if ($p -eq "fast=true" -and $ActualLower.Contains("fast=true")) { return $true }
        if ($ActualLower -eq (Normalize-ModelToken $p)) { return $true }
        if ($ActualLower.Contains($p)) { return $true }
    }
    if ($ActualLower.Contains("-fast")) { return $true }
    if ($ActualLower.StartsWith("gpt-")) {
        $authorized = Get-RoleAuthorizedGptModels -Role $Role -Config $Config
        if ($authorized -contains $ActualLower) { return $false }
        return $true
    }
    return $false
}

function Test-ComposerEquivalentFromConfig {
    param([string]$ActualLower, $Config)
    foreach ($allowed in @($Config.model_binding.composer_allowed)) {
        if ($ActualLower -eq (Normalize-ModelToken $allowed)) { return $true }
    }
    return $false
}

function Test-LadderGrokModelFromConfig {
    param([string]$ActualLower, $Config)
    foreach ($allowed in @($Config.model_binding.ladder_grok_models)) {
        if ($ActualLower -eq (Normalize-ModelToken $allowed)) { return $true }
    }
    return $false
}

function Test-ModelMatchesExpectedFromConfig {
    param([string]$Expected, [string]$Actual, $Config, [string]$Role)
    $expectedLower = (Normalize-ModelToken $Expected)
    $actualLower = (Normalize-ModelToken $Actual)
    if (Test-RejectedModelFromConfig $actualLower $Config $Role) { return $false }
    if ($expectedLower -like "composer-2.5*") {
        return Test-ComposerEquivalentFromConfig $actualLower $Config
    }
    if ((Get-RoleLadderRungs -Role $Role -Config $Config).Count -gt 0) {
        return $false
    }
    return ($actualLower -eq $expectedLower)
}

function Resolve-RoleModelBinding {
    param([string]$Role, [string]$Actual, $Config, $History)
    $actualLower = (Normalize-ModelToken $Actual)
    if (Test-RejectedModelFromConfig $actualLower $Config $Role) { return $null }
    $rungs = Get-RoleLadderRungs -Role $Role -Config $Config
    if ($rungs.Count -gt 0) {
        foreach ($rung in $rungs) {
            $rungModel = (Normalize-ModelToken ([string]$rung.model))
            if ($actualLower -eq $rungModel) {
                $attempt = [int]$rung.attempt
                $historyCheck = Test-LadderHistoryForAttempt -Role $Role -History $History -Attempt $attempt -Config $Config
                if (-not $historyCheck.valid) {
                    return @{
                        allowed = $false
                        selected_model = $rungModel
                        ladder_attempt = $attempt
                        ladder_rung = [string]$rung.model
                        history_reason = $historyCheck.reason
                    }
                }
                return @{
                    allowed = $true
                    selected_model = $rungModel
                    configured_model = $rungModel
                    ladder_attempt = $attempt
                    ladder_rung = [string]$rung.model
                }
            }
        }
        return @{ allowed = $false; selected_model = $actualLower; ladder_attempt = $null; ladder_rung = $null }
    }
    $roleProp = $Config.roles.PSObject.Properties[$Role]
    if ($null -eq $roleProp) { return $null }
    $expected = [string]$roleProp.Value.model
    if (Test-ModelMatchesExpectedFromConfig -Expected $expected -Actual $Actual -Config $Config -Role $Role) {
        return @{
            allowed = $true
            selected_model = $actualLower
            configured_model = $expected
            ladder_attempt = $null
            ladder_rung = $null
        }
    }
    return @{ allowed = $false; selected_model = $actualLower; configured_model = $expected; ladder_attempt = $null; ladder_rung = $null }
}

function Normalize-ModelParams {
    param($RawParams)
    if ($null -eq $RawParams) {
        return @{ valid = $true; present = $false; normalized = @{} }
    }
    $normalized = @{}
    if ($RawParams -is [System.Array]) {
        foreach ($entry in @($RawParams)) {
            if ($null -eq $entry) {
                return @{ valid = $false; reason = "malformed model_params entry" }
            }
            if (-not $entry.PSObject.Properties.Name.Contains("id") -or
                -not $entry.PSObject.Properties.Name.Contains("value")) {
                return @{ valid = $false; reason = "malformed model_params entry" }
            }
            $id = ([string]$entry.id).Trim()
            if (-not $id) {
                return @{ valid = $false; reason = "malformed model_params entry" }
            }
            if ($normalized.ContainsKey($id)) {
                return @{ valid = $false; reason = "duplicate model_params id" }
            }
            $normalized[$id] = $entry.value
        }
        return @{ valid = $true; present = $true; normalized = $normalized }
    }
    if ($RawParams -is [pscustomobject]) {
        foreach ($prop in $RawParams.PSObject.Properties) {
            if ($normalized.ContainsKey($prop.Name)) {
                return @{ valid = $false; reason = "duplicate model_params id" }
            }
            $normalized[$prop.Name] = $prop.Value
        }
        return @{ valid = $true; present = $true; normalized = $normalized }
    }
    return @{ valid = $false; reason = "unexpected model_params container" }
}

function Get-SelectedLadderRung {
    param([string]$Role, $Config, $Binding)
    if ($null -eq $Binding -or $null -eq $Binding.ladder_attempt) { return $null }
    foreach ($rung in Get-RoleLadderRungs -Role $Role -Config $Config) {
        if ([int]$rung.attempt -eq [int]$Binding.ladder_attempt) { return $rung }
    }
    return $null
}

function Test-ModelParamsBinding {
    param($InputData, [string]$Role, $Config, $Binding)
    $normalize = Normalize-ModelParams $InputData.model_params
    if (-not $normalize.valid) {
        return @{
            bound = $true
            allowed = $false
            model_params = "REJECTED"
            reason = $normalize.reason
        }
    }
    if (-not $normalize.present) {
        return @{ bound = $false; allowed = $true; model_params = "UNKNOWN" }
    }
    $params = $normalize.normalized
    $selectedRung = Get-SelectedLadderRung -Role $Role -Config $Config -Binding $Binding
    if ($params.ContainsKey("fast")) {
        $fast = $params["fast"]
        if ($fast -isnot [bool] -or $fast -ne $false) {
            return @{ bound = $true; allowed = $false; model_params = "REJECTED" }
        }
    }
    if ($params.ContainsKey("effort")) {
        if ($null -eq $selectedRung) {
            return @{ bound = $true; allowed = $false; model_params = "REJECTED" }
        }
        $effort = $params["effort"]
        if ($effort -isnot [string]) {
            return @{ bound = $true; allowed = $false; model_params = "REJECTED" }
        }
        $expected = (Normalize-ModelToken ([string]$selectedRung.runtime_reasoning))
        $actual = (Normalize-ModelToken $effort)
        if ($actual -ne $expected) {
            return @{ bound = $true; allowed = $false; model_params = "REJECTED" }
        }
    }
    return @{ bound = $true; allowed = $true; model_params = "BOUND" }
}

function Test-PreToolUseTaskStructure {
    param($InputData)
    if (-not $InputData.PSObject.Properties.Name.Contains("hook_event_name")) {
        return @{ valid = $true; pretooluse = $false }
    }
    if ([string]$InputData.hook_event_name -ne "preToolUse") {
        return @{ valid = $true; pretooluse = $false }
    }
    if (-not (Test-NonEmptyString $InputData.tool_name) -or [string]$InputData.tool_name -ne "Task") {
        return @{ valid = $false; pretooluse = $true; reason = "unexpected preToolUse tool_name" }
    }
    if (-not $InputData.PSObject.Properties.Name.Contains("tool_input")) {
        return @{ valid = $false; pretooluse = $true; reason = "missing tool_input" }
    }
    if (-not (Test-IsConvertFromJsonObject -Value $InputData.tool_input)) {
        return @{ valid = $false; pretooluse = $true; reason = "tool_input must be a JSON object" }
    }
    $toolInput = $InputData.tool_input
    if (-not $toolInput.PSObject.Properties.Name.Contains("prompt")) {
        return @{ valid = $false; pretooluse = $true; reason = "missing tool_input.prompt" }
    }
    if (-not (Test-NonEmptyString $toolInput.prompt)) {
        return @{ valid = $false; pretooluse = $true; reason = "missing tool_input.prompt" }
    }
    if (-not (Test-NonEmptyString $InputData.tool_use_id)) {
        return @{ valid = $false; pretooluse = $true; reason = "missing tool_use_id" }
    }
    return @{ valid = $true; pretooluse = $true }
}

function Normalize-PreToolUseTaskPayload {
    param($InputData)
    $toolInput = $InputData.tool_input
    $props = @{}
    foreach ($prop in $InputData.PSObject.Properties) {
        $props[$prop.Name] = $prop.Value
    }
    $props["task"] = [string]$toolInput.prompt
    if ($toolInput.PSObject.Properties.Name.Contains("model")) {
        $props["subagent_model"] = [string]$toolInput.model
    }
    else {
        $props["subagent_model"] = ""
    }
    if ($toolInput.PSObject.Properties.Name.Contains("subagent_type")) {
        $props["subagent_type"] = [string]$toolInput.subagent_type
    }
    $props["tool_call_id"] = [string]$InputData.tool_use_id
    $props["task_id"] = [string]$InputData.tool_use_id
    if ($InputData.PSObject.Properties.Name.Contains("conversation_id")) {
        $props["parent_conversation_id"] = [string]$InputData.conversation_id
    }
    return [pscustomobject]$props
}

function Resolve-PreToolUseTaskIdentity {
    param($InputData, [bool]$TaggedRole)
    if (-not $TaggedRole) {
        return @{ valid = $true; native = $false }
    }
    foreach ($field in @("tool_call_id", "parent_conversation_id")) {
        if (-not (Test-NonEmptyString $InputData.$field)) {
            return @{ valid = $false; reason = "missing preToolUse correlation field $field" }
        }
    }
    if (-not (Test-NonEmptyString $InputData.subagent_model)) {
        return @{ valid = $false; reason = "missing tool_input.model" }
    }
    $toolCallId = [string]$InputData.tool_call_id
    return @{
        valid = $true
        native = $false
        task_id = $toolCallId
        child_agent_id = $null
    }
}

function Test-NativeSubagentStartStructure {
    param($InputData)
    if (-not $InputData.PSObject.Properties.Name.Contains("hook_event_name")) {
        return @{ valid = $true; native = $false }
    }
    if ([string]$InputData.hook_event_name -ne "subagentStart") {
        return @{ valid = $true; native = $false }
    }
    foreach ($field in @(
            "task",
            "subagent_type",
            "subagent_id",
            "tool_call_id",
            "parent_conversation_id",
            "subagent_model"
        )) {
        if (-not $InputData.PSObject.Properties.Name.Contains($field)) {
            return @{ valid = $false; native = $true; reason = "missing native structural field $field" }
        }
        if (-not (Test-NonEmptyString $InputData.$field)) {
            return @{ valid = $false; native = $true; reason = "missing native structural field $field" }
        }
    }
    if (-not (Test-StrictBooleanField $InputData "is_parallel_worker")) {
        return @{ valid = $false; native = $true; reason = "missing native structural field is_parallel_worker" }
    }
    return @{ valid = $true; native = $true }
}

function Resolve-NativeSubagentIdentity {
    param($InputData, [bool]$TaggedRole)
    if (-not $TaggedRole) {
        return @{ valid = $true; native = $false }
    }
    foreach ($field in @("subagent_id", "tool_call_id", "parent_conversation_id")) {
        if (-not (Test-NonEmptyString $InputData.$field)) {
            return @{ valid = $false; reason = "missing native identity field $field" }
        }
    }
    if (-not (Test-NonEmptyString $InputData.subagent_model)) {
        return @{ valid = $false; reason = "missing subagent_model" }
    }
    if (-not (Test-StrictBooleanField $InputData "is_parallel_worker")) {
        return @{ valid = $false; reason = "is_parallel_worker must be strict boolean" }
    }
    $nativeChild = [string]$InputData.subagent_id
    $nativeTask = [string]$InputData.tool_call_id
    $aliasChild = [string]$InputData.child_agent_id
    $aliasTask = [string]$InputData.task_id
    if ($aliasChild -and $aliasChild -ne $nativeChild) {
        return @{ valid = $false; reason = "contradictory child_agent_id" }
    }
    if ($aliasTask -and $aliasTask -ne $nativeTask) {
        return @{ valid = $false; reason = "contradictory task_id" }
    }
    return @{
        valid = $true
        native = $true
        child_agent_id = $nativeChild
        task_id = $nativeTask
        parent_conversation_id = [string]$InputData.parent_conversation_id
        is_parallel_worker = [bool]$InputData.is_parallel_worker
    }
}

function Test-SyntheticLadderIdentity {
    param($InputData, [string]$Role, $Config)
    if ((Get-RoleLadderRungs -Role $Role -Config $Config).Count -le 0) {
        return @{ valid = $true }
    }
    $childId = [string]$InputData.child_agent_id
    $taskId = [string]$InputData.task_id
    if (-not $childId -or -not $taskId) {
        return @{ valid = $false; reason = "missing synthetic ladder identity" }
    }
    return @{ valid = $true; child_agent_id = $childId; task_id = $taskId }
}

function Test-WorkspaceMatch {
    param($InputData)
    $repoRoot = Get-GitValue @("rev-parse", "--show-toplevel")
    if (-not $repoRoot) { return $false }
    if ($null -eq $InputData -or -not $InputData.PSObject.Properties.Name.Contains("workspace_roots")) {
        return $true
    }
    $roots = @($InputData.workspace_roots)
    if ($roots.Count -eq 0) { return $true }
    foreach ($root in $roots) {
        if (Test-NormalizedPathEqual ([string]$root) $repoRoot) { return $true }
    }
    return $false
}

function Write-SubagentEventObservation {
    param(
        [string]$EventName,
        [bool]$WorkspaceMatch,
        $Identity,
        [string]$SubagentModel,
        $IsParallelWorker,
        [bool]$Allowed,
        [string]$LogPath
    )
    $record = [ordered]@{
        timestamp = [DateTime]::UtcNow.ToString("o")
        event_name = $EventName
        workspace_match = $WorkspaceMatch
        native_subagent_id_present = [bool](Test-NonEmptyString $Identity.native_subagent_id)
        native_tool_call_id_present = [bool](Test-NonEmptyString $Identity.native_tool_call_id)
        native_parent_conversation_id_present = [bool](Test-NonEmptyString $Identity.native_parent_conversation_id)
        alias_child_agent_id_present = [bool](Test-NonEmptyString $Identity.alias_child_agent_id)
        alias_task_id_present = [bool](Test-NonEmptyString $Identity.alias_task_id)
        subagent_id = if ($Identity.correlation_subagent_id) { [string]$Identity.correlation_subagent_id } else { $null }
        tool_call_id = if ($Identity.correlation_tool_call_id) { [string]$Identity.correlation_tool_call_id } else { $null }
        parent_conversation_id = if ($Identity.correlation_parent_conversation_id) { [string]$Identity.correlation_parent_conversation_id } else { $null }
        subagent_model = $SubagentModel
        is_parallel_worker = $IsParallelWorker
        allowed = $Allowed
        runtime_attested = $false
    }
    $record | ConvertTo-Json -Compress | Add-Content -LiteralPath $LogPath -Encoding UTF8
}

function Test-StrictIntegerField {
    param($Object, [string]$Name)
    if ($null -eq $Object) { return $false }
    if (-not $Object.PSObject.Properties.Name.Contains($Name)) { return $false }
    $value = $Object.$Name
    if ($value -is [int] -or $value -is [long]) { return $true }
    return $false
}

function Invoke-D15ReviewerEvidenceValidation {
    param($Facts, $Config)
    $role = [string]$Facts.role
    if (-not $role) { $role = "checkpoint-reviewer" }

    function Blocked([string]$Reason, $ObservedModel, $ObservedReasoning) {
        return @{
            validation_mode = "D15_REVIEWER_EVIDENCE"
            evidence_profile = "UNVERIFIED"
            gate_e = "BLOCKED"
            reason = $Reason
            observed_runtime_model = if ($ObservedModel -in @($null, "", "UNAVAILABLE")) { "UNAVAILABLE" } else { [string]$ObservedModel }
            observed_reasoning = if ($ObservedReasoning -in @($null, "", "UNAVAILABLE")) { "UNAVAILABLE" } else { [string]$ObservedReasoning }
        }
    }

    $strictBooleanFields = @(
        "agent_instantiated",
        "separate_context",
        "uses_verify_reports_and_plan",
        "readonly",
        "contradictory_metadata",
        "fallback_or_substitution_message",
        "mutation_detected",
        "explicit_ladder_fallback"
    )
    foreach ($field in $strictBooleanFields) {
        if (-not $Facts.PSObject.Properties.Name.Contains($field)) {
            if ($field -eq "mutation_detected") {
                return Blocked("missing mutation proof", $Facts.observed_runtime_model, $Facts.observed_reasoning)
            }
            return Blocked("strict boolean required for $field", $Facts.observed_runtime_model, $Facts.observed_reasoning)
        }
        if (-not (Test-StrictBooleanField $Facts $field)) {
            return Blocked("strict boolean required for $field", $Facts.observed_runtime_model, $Facts.observed_reasoning)
        }
    }

    $roleProp = $Config.roles.PSObject.Properties[$role]
    if ($null -eq $roleProp) { return Blocked("unknown role", $Facts.observed_runtime_model, $Facts.observed_reasoning) }
    $configured = [string]$roleProp.Value.model
    foreach ($modelField in @("configured_model", "requested_model", "selected_model")) {
        if (-not $Facts.PSObject.Properties.Name.Contains($modelField)) {
            return Blocked("missing $modelField", $Facts.observed_runtime_model, $Facts.observed_reasoning)
        }
        if ($Facts.$modelField -isnot [string]) {
            return Blocked("missing $modelField", $Facts.observed_runtime_model, $Facts.observed_reasoning)
        }
        if (-not (Test-NonEmptyString $Facts.$modelField)) {
            return Blocked("missing $modelField", $Facts.observed_runtime_model, $Facts.observed_reasoning)
        }
    }
    $declaredConfigured = [string]$Facts.configured_model
    $requested = [string]$Facts.requested_model
    $selected = [string]$Facts.selected_model
    if ($declaredConfigured -ne $configured) {
        return Blocked("configured_model mismatch", $Facts.observed_runtime_model, $Facts.observed_reasoning)
    }
    if ($requested -ne $selected) {
        return Blocked("requested_model does not match selected_model", $Facts.observed_runtime_model, $Facts.observed_reasoning)
    }
    $observedModel = $Facts.observed_runtime_model
    $observedReasoning = $Facts.observed_reasoning
    $agentId = [string]$Facts.agent_id
    $separateContext = $Facts.separate_context
    $usesVerify = $Facts.uses_verify_reports_and_plan
    $readonly = $Facts.readonly
    $contradictory = $Facts.contradictory_metadata
    $fallbackMsg = $Facts.fallback_or_substitution_message
    $explicitLadder = $Facts.explicit_ladder_fallback
    if (-not $Facts.PSObject.Properties.Name.Contains("ladder_result_category") -or
        -not (Test-NonEmptyString $Facts.ladder_result_category)) {
        return Blocked("missing ladder_result_category", $observedModel, $observedReasoning)
    }
    $ladderResult = [string]$Facts.ladder_result_category
    $instantiated = $Facts.agent_instantiated

    if (-not $instantiated -or -not $agentId -or -not $separateContext) {
        return Blocked("missing agent instantiation, agent_id, or separate context", $observedModel, $observedReasoning)
    }
    $authorized = @()
    foreach ($rung in Get-RoleLadderRungs -Role $role -Config $Config) {
        $authorized += (Normalize-ModelToken ([string]$rung.model))
    }
    if ($authorized -notcontains (Normalize-ModelToken $selected)) {
        return Blocked("selected model not on authorized ladder", $observedModel, $observedReasoning)
    }
    if ($ladderResult -eq "FAIL_SUBSTANTIVE") {
        return Blocked("substantive reviewer failure", $observedModel, $observedReasoning)
    }
    if ($ladderResult -ne "SUCCESS") {
        return Blocked("selected reviewer did not succeed", $observedModel, $observedReasoning)
    }
    if (-not $usesVerify -or -not $readonly) {
        return Blocked("missing verify-reports-and-plan or readonly", $observedModel, $observedReasoning)
    }
    $preRaw = $Facts.pre_fingerprint
    $postRaw = $Facts.post_fingerprint
    if ($preRaw -in @($null, "") -or $postRaw -in @($null, "")) {
        return Blocked("missing mutation proof", $observedModel, $observedReasoning)
    }
    if ($Facts.mutation_detected -eq $true) {
        return Blocked("reviewer mutation detected", $observedModel, $observedReasoning)
    }
    if ([string]$postRaw -eq "pending_parent_capture" -or [string]$preRaw -eq "pending_parent_capture") {
        return Blocked("pending parent capture cannot prove immutability", $observedModel, $observedReasoning)
    }
    if ([string]$preRaw -ne [string]$postRaw) {
        return Blocked("reviewer mutation detected", $observedModel, $observedReasoning)
    }
    if ($contradictory -or ($fallbackMsg -and -not $explicitLadder)) {
        return Blocked("contradictory or fallback/substitution metadata", $observedModel, $observedReasoning)
    }

    $rung = $null
    foreach ($candidate in Get-RoleLadderRungs -Role $role -Config $Config) {
        if ((Normalize-ModelToken ([string]$candidate.model)) -eq (Normalize-ModelToken $selected)) {
            $rung = $candidate
            break
        }
    }
    if ($null -eq $rung) {
        return Blocked("selected model not on authorized ladder", $observedModel, $observedReasoning)
    }
    if (-not (Test-StrictIntegerField $Facts "selected_ladder_rung")) {
        return Blocked("selected_ladder_rung must be a strict integer", $observedModel, $observedReasoning)
    }
    $selectedRung = [int]$Facts.selected_ladder_rung
    if ($selectedRung -ne [int]$rung.attempt) {
        return Blocked("selected_ladder_rung does not match selected model", $observedModel, $observedReasoning)
    }
    if ($selectedRung -eq 1) {
        if ($explicitLadder) {
            return Blocked("rung 1 must not claim ladder fallback", $observedModel, $observedReasoning)
        }
    }
    else {
        if (-not $explicitLadder) {
            return Blocked("later ladder rung requires explicit fallback record", $observedModel, $observedReasoning)
        }
    }
    $requiredReasoning = (Normalize-ModelToken ([string]$rung.runtime_reasoning))
    $modelObserved = $observedModel -notin @($null, "", "UNAVAILABLE")
    $reasoningObserved = $observedReasoning -notin @($null, "", "UNAVAILABLE")
    if ($modelObserved -ne $reasoningObserved) {
        return Blocked("partial runtime metadata", $observedModel, $observedReasoning)
    }
    if ($modelObserved -and $reasoningObserved) {
        $modelOk = (Normalize-ModelToken ([string]$observedModel)) -eq (Normalize-ModelToken $selected)
        $reasoningOk = (Normalize-ModelToken ([string]$observedReasoning)) -eq $requiredReasoning
        if (-not $modelOk -or -not $reasoningOk) {
            return Blocked("observed runtime metadata contradicts selected ladder rung", $observedModel, $observedReasoning)
        }
        return @{
            validation_mode = "D15_REVIEWER_EVIDENCE"
            evidence_profile = "RUNTIME_ATTESTED"
            gate_e = "CONTINUE"
            reason = "observed runtime metadata matches selected ladder rung"
            observed_runtime_model = [string]$observedModel
            observed_reasoning = [string]$observedReasoning
            selected_ladder_rung = $selectedRung
        }
    }
    return @{
        validation_mode = "D15_REVIEWER_EVIDENCE"
        evidence_profile = "CONTROL_PLANE_PINNED"
        gate_e = "CONTINUE"
        reason = "local control-plane pin fully proven; runtime metadata UNAVAILABLE"
        observed_runtime_model = "UNAVAILABLE"
        observed_reasoning = "UNAVAILABLE"
        selected_ladder_rung = $selectedRung
    }
}

$config = Get-Config
if ($validationMode -eq "EXTERNAL_CODEX_PRE_HANDOFF") {
    $result = Invoke-ExternalCodexWorkspaceValidation -Handoff $inputData.handoff -Config $config -Mode $validationMode
    $result | ConvertTo-Json -Compress | Write-Output
    exit 0
}
if ($validationMode -eq "EXTERNAL_CODEX_BOUND_REVIEW") {
    $result = Invoke-ExternalCodexWorkspaceValidation -Handoff $inputData.handoff -Config $config -Mode $validationMode
    $result | ConvertTo-Json -Compress | Write-Output
    exit 0
}
if ($validationMode -eq "D15_REVIEWER_EVIDENCE") {
    $result = Invoke-D15ReviewerEvidenceValidation -Facts $inputData.facts -Config $config
    $result | ConvertTo-Json -Compress | Write-Output
    exit 0
}

$preToolStructure = Test-PreToolUseTaskStructure -InputData $inputData
if ($preToolStructure.pretooluse -and -not $preToolStructure.valid) {
    @{
        permission = "deny"
        user_message = "preToolUse Task payload is missing required structural fields."
    } | ConvertTo-Json -Compress | Write-Output
    exit 2
}
if ($preToolStructure.pretooluse) {
    $inputData = Normalize-PreToolUseTaskPayload -InputData $inputData
    $task = [string]$inputData.task
    $actual = [string]$inputData.subagent_model
}

$nativeStructure = Test-NativeSubagentStartStructure -InputData $inputData
if ($nativeStructure.native -and -not $nativeStructure.valid) {
    @{
        permission = "deny"
        user_message = "Native subagentStart payload is missing required structural fields."
    } | ConvertTo-Json -Compress | Write-Output
    exit 2
}

$trimmedTask = $task.Trim()
$hookEventName = if ($inputData.PSObject.Properties.Name.Contains("hook_event_name")) {
    [string]$inputData.hook_event_name
} else {
    ""
}
$isNativeEvent = ($hookEventName -eq "subagentStart")
$isPreToolUseEvent = ($hookEventName -eq "preToolUse")
$workspaceMatch = Test-WorkspaceMatch -InputData $inputData
$roleMarkerMatches = [regex]::Matches(
    $task,
    '\[role:([^\]]*)\]',
    [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
)
$validRoleMatch = $trimmedTask -cmatch '^\[ROLE:([a-z0-9-]+)\](?:\s|$)'
$matchedRole = if ($validRoleMatch) { [string]$Matches[1] } else { "" }
$roleShapedAttempt = $task -match '\[(?i)role:'

if ($roleShapedAttempt) {
    if ($task -match '(?i)\[role:[^\]]*$') {
        @{
            permission = "deny"
            user_message = "Malformed or unterminated [ROLE:...] marker."
        } | ConvertTo-Json -Compress | Write-Output
        exit 2
    }
    if ($task -match '(?i)\[role:') {
        if (-not ($task -cmatch '\[ROLE:')) {
            @{
                permission = "deny"
                user_message = "Malformed or misplaced [ROLE:...] marker."
            } | ConvertTo-Json -Compress | Write-Output
            exit 2
        }
    }
    foreach ($match in $roleMarkerMatches) {
        $inner = [string]$match.Groups[1].Value
        if ($inner -cmatch '[A-Z]') {
            @{
                permission = "deny"
                user_message = "Malformed or misplaced [ROLE:...] marker."
            } | ConvertTo-Json -Compress | Write-Output
            exit 2
        }
    }
}
if ($roleMarkerMatches.Count -gt 0 -and -not $validRoleMatch) {
    @{
        permission = "deny"
        user_message = "Malformed or misplaced [ROLE:...] marker."
    } | ConvertTo-Json -Compress | Write-Output
    exit 2
}
if ($roleMarkerMatches.Count -gt 1) {
    @{
        permission = "deny"
        user_message = "Multiple [ROLE:...] markers are forbidden."
    } | ConvertTo-Json -Compress | Write-Output
    exit 2
}
if ($task -match '(?m)^\s+\[(?i)role:' -or $task -match '(?m)\S\[(?i)role:') {
    @{
        permission = "deny"
        user_message = "Malformed or misplaced [ROLE:...] marker."
    } | ConvertTo-Json -Compress | Write-Output
    exit 2
}
if ($task -match '\[ROLE[\s\t]+:' -or $task -match '\[ROLE:[\s\t]+') {
    @{
        permission = "deny"
        user_message = "Malformed or misplaced [ROLE:...] marker."
    } | ConvertTo-Json -Compress | Write-Output
    exit 2
}

if (-not $validRoleMatch) {
    @{
        timestamp = [DateTime]::UtcNow.ToString("o")
        role = "UNOBSERVED_INTERNAL_HELPER"
        actual_model = $actual
        observed_cost = "UNKNOWN"
        model_params = "UNKNOWN"
        allowed = $true
        non_authoritative = $true
        gate_budget_authority = $false
        runtime_attested = $false
    } | ConvertTo-Json -Compress | Add-Content -LiteralPath $logPath -Encoding UTF8
    @{
        permission = "allow"
        non_authoritative = $true
        gate_budget_authority = $false
    } | ConvertTo-Json -Compress | Write-Output
    exit 0
}

$role = $matchedRole
$roleProperty = $config.roles.PSObject.Properties[$role]
if ($null -eq $roleProperty) {
    @{
        permission = "deny"
        user_message = "Unknown tagged agent role '$role'."
    } | ConvertTo-Json -Compress | Write-Output
    exit 2
}

$expected = [string]$roleProperty.Value.model
$history = $inputData.ladder_history
$binding = Resolve-RoleModelBinding -Role $role -Actual $actual -Config $config -History $history
$modelMatches = [bool]$binding.allowed
$paramsResult = Test-ModelParamsBinding -InputData $inputData -Role $role -Config $config -Binding $binding

if ($isNativeEvent) {
    $identityResult = Resolve-NativeSubagentIdentity -InputData $inputData -TaggedRole $true
}
elseif ($isPreToolUseEvent) {
    $identityResult = Resolve-PreToolUseTaskIdentity -InputData $inputData -TaggedRole $true
}
else {
    $identityResult = Test-SyntheticLadderIdentity -InputData $inputData -Role $role -Config $config
}
$correlationChildId = if ($identityResult.child_agent_id) { [string]$identityResult.child_agent_id } else { $null }
$correlationTaskId = if ($identityResult.task_id) { [string]$identityResult.task_id } else { $null }
$identityObs = @{
    native_subagent_id = if ($isNativeEvent) { [string]$inputData.subagent_id } else { $null }
    native_tool_call_id = if ($isNativeEvent) { [string]$inputData.tool_call_id } else { $null }
    native_parent_conversation_id = if ($isNativeEvent) { [string]$inputData.parent_conversation_id } else { $null }
    alias_child_agent_id = if ($inputData.PSObject.Properties.Name.Contains("child_agent_id")) { [string]$inputData.child_agent_id } else { $null }
    alias_task_id = if ($inputData.PSObject.Properties.Name.Contains("task_id")) { [string]$inputData.task_id } else { $null }
    correlation_subagent_id = $correlationChildId
    correlation_tool_call_id = $correlationTaskId
    correlation_parent_conversation_id = if ($isNativeEvent -or $isPreToolUseEvent) {
        [string]$inputData.parent_conversation_id
    } else {
        $null
    }
}
$parallelWorker = if ($isNativeEvent) { [bool]$identityResult.is_parallel_worker } else { $null }
$observationAllowed = $identityResult.valid -and $modelMatches -and (-not $paramsResult.bound -or $paramsResult.allowed)
Write-SubagentEventObservation `
    -EventName $(if ($hookEventName) { $hookEventName } else { "subagentStart" }) `
    -WorkspaceMatch $workspaceMatch `
    -Identity $identityObs `
    -SubagentModel $actual `
    -IsParallelWorker $parallelWorker `
    -Allowed $observationAllowed `
    -LogPath $logPath

if (-not $identityResult.valid) {
    @{
        permission = "deny"
        user_message = "Bound model_params or task identity contradict required model binding."
    } | ConvertTo-Json -Compress | Write-Output
    exit 2
}

if ($paramsResult.bound -and -not $paramsResult.allowed) {
    @{
        permission = "deny"
        user_message = "Bound model_params or task identity contradict required model binding."
    } | ConvertTo-Json -Compress | Write-Output
    exit 2
}

if (-not $modelMatches) {
    $reason = if ($binding.history_reason) { $binding.history_reason } else { "model not authorized" }
    $required = if ($binding.configured_model) { [string]$binding.configured_model } else { $expected }
    @{
        permission = "deny"
        user_message = "Role '$role' requires '$required' or an authorized ladder model but Cursor selected '$actual' ($reason). Use the configured fallback ladder without Auto, inherit, Fast, or legacy xhigh routes."
    } | ConvertTo-Json -Compress | Write-Output
    exit 2
}

@{ permission = "allow" } | ConvertTo-Json -Compress | Write-Output
}
catch {
    Emit-HostHookEnforcementFailure
}
