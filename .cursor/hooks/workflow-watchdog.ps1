$ErrorActionPreference = "Stop"

$raw = [Console]::In.ReadToEnd()
$inputData = $raw | ConvertFrom-Json
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
if ($state.status -ne "RUNNING" -or [bool]$state.human_gate) {
    Write-Output "{}"
    exit 0
}

$message = "Resume the active work package from the persisted workflow state. Read the authoritative package and execution documents, perform next_action, and continue until the next legitimate stop condition."
@{ followup_message = $message } | ConvertTo-Json -Compress | Write-Output
