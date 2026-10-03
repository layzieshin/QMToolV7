# Shared policy for the existing workflow-state owner; dot-source only.
# A recovery receipt reserves a bounded repair batch, never PASS or Git authority.
function Get-TechnicalRecoveryStatePath {
    if ($env:QMTOOL_WORKFLOW_STATE_PATH) { return $env:QMTOOL_WORKFLOW_STATE_PATH }
    return Join-Path (Get-Location) ".cursor/runtime/workflow-state.json"
}

function Get-RecoveryFileHash([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose(); $stream.Dispose() }
}

function Get-RecoveryCounterFields($State) {
    # Existing W3 states retain their historical counters. New states use the canonical rework_count.
    if ($State.PSObject.Properties.Name -contains 'regular_rework_count') {
        return @('regular_rework_count', 'exceptional_count', 'final_rework_count')
    }
    return @('rework_count', 'final_rework_count')
}

function Get-RecoveryPreservedCounterFields($State) {
    return @('rework_count', 'regular_rework_count', 'exceptional_count', 'final_rework_count') |
        Where-Object { $State.PSObject.Properties.Name -contains $_ }
}

function Test-RecoveryInteger($Value) {
    return (($Value -is [int] -or $Value -is [long]) -and $Value -ge 0)
}

function Get-RecoveryArtifactPath([string]$Root, [string]$Relative) {
    if ([string]::IsNullOrWhiteSpace($Relative) -or [IO.Path]::IsPathRooted($Relative) -or
        $Relative -match '(^|[\\/])\.\.?([\\/]|$)') { throw "invalid recovery artifact path" }
    $base = [IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
    $path = [IO.Path]::GetFullPath((Join-Path $base $Relative))
    if (-not $path.StartsWith($base + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw "recovery artifact escapes target"
    }
    $cursor = $path
    while ($cursor) {
        if ((Test-Path -LiteralPath $cursor) -and
            ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "recovery artifact reparse point denied"
        }
        $cursor = Split-Path -Parent $cursor
    }
    return $path
}

function Read-RecoveryArtifact([string]$Root, [string]$Relative, [string]$Sha256) {
    if ($Sha256 -notmatch '^[a-fA-F0-9]{64}$') { throw "missing recovery artifact hash" }
    $path = Get-RecoveryArtifactPath $Root $Relative
    if (-not (Test-Path -LiteralPath $path -PathType Leaf) -or
        (Get-RecoveryFileHash $path) -ne $Sha256) {
        throw "recovery artifact hash mismatch: $Relative"
    }
    return Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function Get-RecoveryObjectHash($Object) {
    $bytes = [Text.Encoding]::UTF8.GetBytes(($Object | ConvertTo-Json -Compress -Depth 30))
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
}

function Write-TechnicalRecoveryState($StatePath, $State) {
    # Caller holds the existing per-state mutex for reservation, continuation or manual stop.
    $temporary = "$StatePath.recovery-$PID-$([guid]::NewGuid().ToString('N')).tmp"
    $backup = "$StatePath.recovery-backup-$PID-$([guid]::NewGuid().ToString('N')).tmp"
    try {
        [IO.File]::WriteAllText($temporary, ($State | ConvertTo-Json -Depth 40), [Text.UTF8Encoding]::new($false))
        [IO.File]::Replace($temporary, $StatePath, $backup)
        $readback = Get-Content -LiteralPath $StatePath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ((Get-RecoveryObjectHash $readback) -ne (Get-RecoveryObjectHash $State)) { throw "recovery state readback mismatch" }
    } finally {
        if (Test-Path -LiteralPath $temporary) { Remove-Item -LiteralPath $temporary -Force }
        if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force }
    }
}

function Invoke-TechnicalRecoveryPolicy {
    param($Config, $BindingRecord = $null, [string]$ProposalPath = "", [string]$ProposalSha256 = "",
        [switch]$Reserve, [switch]$ConsumeFollowup, [switch]$PersistUserStop)
    $statePath = Get-TechnicalRecoveryStatePath
    $mutex = $null
    $locked = $false
    try {
        # All reservation/followup/stop updates serialize against this exact runtime state.
        if ($Reserve -or $ConsumeFollowup -or $PersistUserStop) {
            $stateKey = Get-RecoveryObjectHash ([IO.Path]::GetFullPath($statePath).ToLowerInvariant())
            $mutex = New-Object Threading.Mutex($false, "Local\QMToolRecovery-$stateKey")
            $locked = $mutex.WaitOne($(if ($PersistUserStop) { 5000 } else { 0 }))
            if (-not $locked) { throw "recovery state is busy" }
        }
        $state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
        $recovery = $state.technical_recovery
        if ($null -eq $recovery -or $recovery.enabled -isnot [bool] -or -not $recovery.enabled) {
            throw "technical recovery is not commissioned"
        }
        if ($PersistUserStop) {
            # Stopping grants no authority and must survive stale diagnostic artifacts.
            if ($state.status -ne 'RUNNING') { throw "no running commissioned recovery to stop" }
            if ($recovery.user_stop -isnot [bool]) { throw "invalid recovery user_stop" }
            if (-not $recovery.user_stop) {
                $recovery.user_stop = $true
                Write-TechnicalRecoveryState -StatePath $statePath -State $state
            }
            return @{ eligible = $false; reason = 'manual stop persisted'; recovery_action = 'STOPPED';
                review_pass = $false; git_authorized = $false }
        }
        if ($state.status -ne 'RUNNING' -or $state.human_gate -isnot [bool] -or $state.human_gate -or
            $recovery.user_stop -isnot [bool] -or $recovery.user_stop) { throw "recovery stopped or human decision active" }
        $limit = $Config.defaults.max_technical_recovery_batches
        $followupLimit = $Config.defaults.stop_hook_loop_limit
        if (-not (Test-RecoveryInteger $limit) -or $limit -le 0 -or
            -not (Test-RecoveryInteger $followupLimit) -or $followupLimit -le 0) { throw "invalid configured recovery budget" }
        $root = [IO.Path]::GetFullPath((Get-Location).Path).TrimEnd('\', '/')
        $commission = Read-RecoveryArtifact $root $recovery.commission_path $recovery.commission_sha256
        if ($commission.kind -ne 'AUTONOMOUS_TECHNICAL_RECOVERY' -or
            [string]::IsNullOrWhiteSpace([string]$commission.user_authorization) -or
            $commission.allow_technical_repair -isnot [bool] -or -not $commission.allow_technical_repair) {
            throw "invalid immutable user commission"
        }
        $record = $state.external_review.bindingRecord
        if ($null -eq $record -or $record.review_need -ne 'RECOVERY_DIAGNOSIS') { throw "missing recovery bindingRecord" }
        if ($null -ne $BindingRecord -and (Get-RecoveryObjectHash $BindingRecord) -ne (Get-RecoveryObjectHash $record)) {
            throw "recovery binding changed during reservation"
        }
        foreach ($pair in @(@('package_id', 'work_package'), @('checkpoint_id', 'checkpoint'), @('branch', 'work_branch'))) {
            if ([string]::IsNullOrWhiteSpace([string]$commission.($pair[0])) -or
                [string]$commission.($pair[0]) -ne [string]$state.($pair[1]) -or
                [string]$record.($pair[0]) -ne [string]$commission.($pair[0])) { throw "recovery commission identity mismatch" }
        }
        if ([IO.Path]::GetFullPath([string]$commission.target_root).TrimEnd('\', '/') -ne $root -or
            [IO.Path]::GetFullPath([string]$record.target_root).TrimEnd('\', '/') -ne $root -or
            $commission.contract_sha256 -ne $record.contract_sha256) { throw "recovery commission contract/target mismatch" }
        $branch = [string](& git rev-parse --abbrev-ref HEAD 2>$null)
        if ($LASTEXITCODE -ne 0 -or $branch -ne $record.branch) { throw "recovery branch changed" }
        $head = [string](& git rev-parse HEAD 2>$null)
        if ($LASTEXITCODE -ne 0 -or $head -ne $record.reviewed_head) { throw "recovery HEAD changed" }
        $contractPath = Get-RecoveryArtifactPath $root $record.contract_path
        if ((Get-RecoveryFileHash $contractPath) -ne $record.contract_sha256) {
            throw "recovery contract changed"
        }
        $manifest = Read-RecoveryArtifact $root $record.manifest_path $record.manifest_sha256
        $counterFields = @(@(Get-RecoveryPreservedCounterFields $state) + @(Get-RecoveryPreservedCounterFields $commission.counter_floor) | Select-Object -Unique)
        if ('rework_count' -notin $counterFields -or 'final_rework_count' -notin $counterFields) { throw "missing canonical recovery counters" }
        foreach ($field in $counterFields) {
            if (-not (Test-RecoveryInteger $state.$field) -or
                -not (Test-RecoveryInteger $commission.counter_floor.$field) -or
                $state.$field -lt $commission.counter_floor.$field) { throw "recovery counter regression: $field" }
        }
        if ($recovery.batches -isnot [array]) { throw "missing recovery batch history" }
        $batches = @($recovery.batches)
        if ($batches.Count -gt $limit) { throw "recovery batch budget exceeded" }
        $seen = @{}
        foreach ($batch in $batches) {
            if ($batch.commission_sha256 -ne $recovery.commission_sha256 -or
                [string]::IsNullOrWhiteSpace([string]$batch.id) -or $seen.ContainsKey([string]$batch.id)) {
                throw "recovery history commission or identity mismatch"
            }
            $seen[[string]$batch.id] = $true
            foreach ($field in @(Get-RecoveryPreservedCounterFields $state)) {
                if (-not (Test-RecoveryInteger $batch.counters.$field) -or $state.$field -lt $batch.counters.$field) {
                    throw "recovery history counter regression: $field"
                }
            }
        }
        if (-not $Reserve) {
            if ($batches.Count -eq 0) { throw "no reserved recovery batch" }
            $active = $batches[-1]
            if ($recovery.active_batch_id -ne $active.id) { throw "recovery active batch mismatch" }
            $ProposalPath = [string]$active.proposal_path
            $ProposalSha256 = [string]$active.proposal_sha256
        }
        $proposal = Read-RecoveryArtifact $root $ProposalPath $ProposalSha256
        if ($proposal.kind -ne 'TECHNICAL_RECOVERY_PROPOSAL' -or
            $proposal.decision -ne 'REPAIR_WITHIN_COMMISSION' -or
            $proposal.diagnosis_complete -isnot [bool] -or -not $proposal.diagnosis_complete -or
            $proposal.requires_user_decision -isnot [bool] -or $proposal.requires_user_decision -or
            $proposal.changes_security_or_permissions -isnot [bool] -or $proposal.changes_security_or_permissions -or
            $proposal.material_amendment -isnot [bool] -or $proposal.material_amendment) {
            throw "recovery proposal requires diagnosis or human decision"
        }
        foreach ($field in @('package_id', 'checkpoint_id', 'contract_sha256', 'manifest_sha256', 'diff_sha256')) {
            if ([string]::IsNullOrWhiteSpace([string]$proposal.$field) -or
                [string]$proposal.$field -ne [string]$record.$field) { throw "recovery proposal binding mismatch: $field" }
        }
        if ($proposal.findings -isnot [array] -or $proposal.findings.Count -eq 0 -or
            $proposal.repair_paths -isnot [array] -or $proposal.repair_paths.Count -eq 0 -or
            $proposal.verification_commands -isnot [array] -or $proposal.verification_commands.Count -eq 0) {
            throw "recovery proposal inventory/repair/verification missing"
        }
        foreach ($finding in $proposal.findings) {
            if ([string]::IsNullOrWhiteSpace([string]$finding.id) -or [string]::IsNullOrWhiteSpace([string]$finding.cause) -or
                [string]::IsNullOrWhiteSpace([string]$finding.repair)) { throw "incomplete recovery finding" }
            $key = [string]$finding.evidence_key
            if ([string]::IsNullOrWhiteSpace($key) -or $null -eq $manifest.evidence_paths.$key) { throw "recovery finding evidence missing" }
            $evidence = Get-RecoveryArtifactPath $root ([string]$manifest.evidence_paths.$key)
            if ((Get-RecoveryFileHash $evidence) -ne [string]$manifest.evidence_sha256.$key) {
                throw "recovery finding evidence changed"
            }
        }
        foreach ($path in $proposal.repair_paths) {
            $null = Get-RecoveryArtifactPath $root ([string]$path)
            if ([string]$path -notin @($commission.repair_allowlist) -or [string]$path -notin @($manifest.allowlist)) {
                throw "recovery repair outside commissioned scope"
            }
        }
        foreach ($command in $proposal.verification_commands) {
            if ([string]::IsNullOrWhiteSpace([string]$command) -or [string]$command -notin @($record.verification_commands)) {
                throw "recovery verification outside bound gate commands"
            }
        }
        $batchId = Get-RecoveryObjectHash ([ordered]@{ commission = [string]$recovery.commission_sha256;
            proposal = $ProposalSha256.ToLowerInvariant(); binding = $record })
        $replay = $false
        if ($Reserve) {
            if ($seen.ContainsKey($batchId)) {
                if ($batches[-1].id -ne $batchId -or $recovery.active_batch_id -ne $batchId) { throw "stale recovery receipt replay" }
                $active = $batches[-1]
                $replay = $true
            } else {
                if ($batches.Count -ge $limit) { throw "technical recovery batch budget exhausted" }
                if ($batches.Count -gt 0 -and $batches[-1].outcome -ne "FAILED") {
                    throw "complete current recovery batch before another proposal"
                }
                $counters = [ordered]@{}
                foreach ($field in @(Get-RecoveryPreservedCounterFields $state)) { $counters[$field] = $state.$field }
                $active = [pscustomobject][ordered]@{ id = $batchId; commission_sha256 = $recovery.commission_sha256;
                    proposal_path = $ProposalPath; proposal_sha256 = $ProposalSha256; bindingRecord = $record;
                    counters = $counters; followup_count = 0; outcome = "IN_PROGRESS" }
                $recovery.batches = @($batches) + @($active)
                $recovery.active_batch_id = $batchId
            }
        } elseif ((Get-RecoveryObjectHash $active.bindingRecord) -ne (Get-RecoveryObjectHash $record) -or $active.id -ne $batchId) {
            throw "recovery batch context changed"
        }
        if ($active.outcome -ne "IN_PROGRESS") { throw "recovery batch is closed; fresh proposal/reservation required" }
        if (-not (Test-RecoveryInteger $active.followup_count)) { throw "invalid recovery followup count" }
        if ($ConsumeFollowup) {
            if ($active.followup_count -ge $followupLimit) { throw "recovery continuation budget exhausted; reassess impasse" }
            $active.followup_count++
        }
        if ($Reserve -and -not $replay) {
            $state.phase = "REWORK"
            $state.next_action = "Execute the reserved technical recovery proposal, then gates and independent review."
            $state.updated_at = [DateTime]::UtcNow.ToString("o")
        }
        if ($Reserve -or $ConsumeFollowup) {
            Write-TechnicalRecoveryState -StatePath $statePath -State $state
        }
        return @{ eligible = $true; reason = 'bound technical repair batch'; batch_id = $batchId;
            batch_count = @($recovery.batches).Count; replay = $replay; recovery_action = 'REWORK';
            review_pass = $false; git_authorized = $false }
    } catch {
        return @{ eligible = $false; reason = $_.Exception.Message; recovery_action = 'DIAGNOSE_ONLY';
            review_pass = $false; git_authorized = $false }
    } finally {
        if ($locked) { $mutex.ReleaseMutex() }
        if ($null -ne $mutex) { $mutex.Dispose() }
    }
}
