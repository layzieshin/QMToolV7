$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "recovery-policy.ps1")

$raw = [Console]::In.ReadToEnd()
$inputData = $raw | ConvertFrom-Json
if ([string]$inputData.status -eq "aborted") {
    $null = Invoke-TechnicalRecoveryPolicy -PersistUserStop
    Write-Output "{}"
    exit 0
}
if ([string]$inputData.status -ne "completed") {
    Write-Output "{}"
    exit 0
}

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
if ($state.status -ne "RUNNING" -or [bool]$state.human_gate -or [bool]$state.technical_recovery.user_stop) {
    Write-Output "{}"
    exit 0
}

if ([string]$state.external_review.bindingRecord.review_need -eq "RECOVERY_DIAGNOSIS" -or
    [bool]$state.external_review.recovery_proposal_bound) {
    $config = Get-Content -LiteralPath (Join-Path (Get-Location) ".cursor/agent-system.json") -Raw -Encoding UTF8 | ConvertFrom-Json
    $recovery = Invoke-TechnicalRecoveryPolicy -Config $config -ConsumeFollowup
    if (-not $recovery.eligible) { Write-Output "{}"; exit 0 }
    @{ followup_message = "Resume reserved technical recovery batch $($recovery.batch_count) from its bound proposal. Run affected gates and fresh independent review; the receipt grants no PASS or Git authority." } | ConvertTo-Json -Compress | Write-Output
    exit 0
}

$message = "Resume the active work package from the persisted workflow state. Read the authoritative package and execution documents, perform next_action, and continue until the next legitimate stop condition."
@{ followup_message = $message } | ConvertTo-Json -Compress | Write-Output
