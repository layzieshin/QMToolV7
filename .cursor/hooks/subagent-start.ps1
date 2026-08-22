$ErrorActionPreference = "Stop"

$raw = [Console]::In.ReadToEnd()
$inputData = $raw | ConvertFrom-Json
$task = [string]$inputData.task
$actual = [string]$inputData.subagent_model
$logPath = if ($env:QMTOOL_RUNTIME_LOG_PATH) {
    $env:QMTOOL_RUNTIME_LOG_PATH
} else {
    Join-Path (Get-Location) ".cursor/runtime/subagent-start.log"
}
$logDirectory = Split-Path -Parent $logPath
if ($logDirectory) {
    New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
}
$taskShort = ($task -replace '[\r\n]+', ' ').Trim()
if ($taskShort.Length -gt 160) {
    $taskShort = $taskShort.Substring(0, 160)
}

if ($task -notmatch "^\[ROLE:([a-z0-9-]+)\]") {
    @{
        timestamp = [DateTime]::UtcNow.ToString("o")
        role = "UNTAGGED"
        actual_model = $actual
        task_short = $taskShort
        allowed = $true
    } | ConvertTo-Json -Compress | Add-Content -LiteralPath $logPath -Encoding UTF8
    @{ permission = "allow" } | ConvertTo-Json -Compress | Write-Output
    exit 0
}

$role = $Matches[1]
$configPath = Join-Path (Get-Location) ".cursor/agent-system.json"
$config = Get-Content -LiteralPath $configPath -Raw -Encoding UTF8 | ConvertFrom-Json
$roleProperty = $config.roles.PSObject.Properties[$role]
if ($null -eq $roleProperty) {
    @{
        permission = "deny"
        user_message = "Unknown tagged agent role '$role'."
    } | ConvertTo-Json -Compress | Write-Output
    exit 0
}

$expected = [string]$roleProperty.Value.model
$expectedLower = $expected.ToLowerInvariant()
$actualLower = $actual.ToLowerInvariant()

if ($expectedLower -eq "composer-2.5[]") {
    $modelMatches = $actualLower -in @("composer-2.5[]", "composer-2.5[fast=false]", "composer-2.5")
} else {
    $modelMatches = ($actualLower -eq $expectedLower) -or
        ($actualLower.StartsWith("$expectedLower[") -and -not $actualLower.Contains("fast=true"))
}

@{
    timestamp = [DateTime]::UtcNow.ToString("o")
    role = $role
    actual_model = $actual
    expected_model = $expected
    task_short = $taskShort
    allowed = $modelMatches
} | ConvertTo-Json -Compress | Add-Content -LiteralPath $logPath -Encoding UTF8

if (-not $modelMatches) {
    @{
        permission = "deny"
        user_message = "Role '$role' requires '$expected' but Cursor selected '$actual'. Restart the defined custom subagent with its configured model."
    } | ConvertTo-Json -Compress | Write-Output
    exit 0
}

@{ permission = "allow" } | ConvertTo-Json -Compress | Write-Output
