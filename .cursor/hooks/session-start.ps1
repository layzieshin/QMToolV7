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

$context = @(
    "Active Cursor work package workflow:"
    "Work Package: $($state.work_package)"
    "Phase: $($state.phase)"
    "Checkpoint: $($state.checkpoint)"
    "Rework Count: $($state.rework_count)"
    "Human Gate: $($state.human_gate)"
    "Work Package Path: $($state.work_package_path)"
    "Execution Journal Path: $($state.execution_journal_path)"
    "Next Action: $($state.next_action)"
    "Resume the persisted workflow. Read the referenced authoritative documents. Do not restart already completed planning or checkpoints."
)
if ([string]$state.phase -eq "FINAL_GIT" -and $null -ne $state.external_review) {
    $context += "External Review: $($state.external_review.status) (round $($state.external_review.round))"
}
$context = $context -join "`n"

@{ additional_context = $context } | ConvertTo-Json -Compress | Write-Output
