$ErrorActionPreference = "Stop"

$null = [Console]::In.ReadToEnd()
$statePath = if ($env:QMTOOL_WORKFLOW_STATE_PATH) {
    $env:QMTOOL_WORKFLOW_STATE_PATH
} else {
    Join-Path (Get-Location) ".cursor/runtime/workflow-state.json"
}

if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
    Write-Output "{}"
    exit 0
}

$state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($state.status -in @("IDLE", "DONE")) {
    Write-Output "{}"
    exit 0
}

$recoveryProposalBound = $false
$recoveryDiagnosisBound = $false
if ($null -ne $state.external_review) {
    if ($state.external_review.PSObject.Properties.Name.Contains("recovery_proposal_bound") -and
        $state.external_review.recovery_proposal_bound -eq $true) {
        $recoveryProposalBound = $true
    }
    if ($state.external_review.PSObject.Properties.Name.Contains("bindingRecord") -and
        $null -ne $state.external_review.bindingRecord -and
        $state.external_review.bindingRecord.PSObject.Properties.Name.Contains("review_need") -and
        [string]$state.external_review.bindingRecord.review_need -eq "RECOVERY_DIAGNOSIS") {
        $recoveryDiagnosisBound = $true
    }
}

$context = @(
    "Active Cursor work package workflow:"
    "Work Package: $($state.work_package)"
    "Phase: $($state.phase)"
    "Checkpoint: $($state.checkpoint)"
    "Rework Count: $($state.rework_count)"
    "Human Gate: $($state.human_gate)"
    "Work Package Path: $($state.work_package_path)"
    "Execution Journal Path: $($state.execution_journal_path)"
)

if ($recoveryProposalBound) {
    $context += "Recovery diagnosis receipt: RECOVERY_PROPOSAL_BOUND"
    $context += "Do not issue Resume, Implement, or Commit instructions from this receipt."
    $context += "Missing explicit coordinator commission blocks further automation."
    $context += "Status remains BLOCKED_HUMAN until human gate or new valid commission."
}
elseif ($recoveryDiagnosisBound) {
    $context += "Recovery diagnosis pre-handoff: RECOVERY_DIAGNOSIS_READY"
    $context += "Do not issue Resume, Implement, or Commit instructions while recovery diagnosis binding is active."
    $context += "Missing explicit coordinator commission blocks further automation."
    $context += "Status remains BLOCKED_HUMAN until human gate or new valid commission."
}
else {
    $context += "Next Action: $($state.next_action)"
    $context += "Resume the persisted workflow. Read the referenced authoritative documents. Do not restart already completed planning or checkpoints."
}

if ([string]$state.phase -eq "FINAL_GIT" -and $null -ne $state.external_review) {
    $context += "External Review: $($state.external_review.status) (round $($state.external_review.round))"
}
$context = $context -join "`n"

@{ additional_context = $context } | ConvertTo-Json -Compress | Write-Output
