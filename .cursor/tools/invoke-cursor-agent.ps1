[CmdletBinding(DefaultParameterSetName = "Inline")]
param(
    [Parameter(Mandatory = $true)]
    [string]$TargetRoot,

    [Parameter(Mandatory = $true, ParameterSetName = "Inline")]
    [string]$Prompt,

    [Parameter(Mandatory = $true, ParameterSetName = "File")]
    [string]$PromptPath,

    [switch]$Force
)

$ErrorActionPreference = "Stop"

$preflight = Join-Path $PSScriptRoot "assert-execution-host.ps1"
& $preflight -TargetRoot $TargetRoot -RequireGitWrite -RequireCursorCli
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
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

$cursor = Get-Command cursor-agent -ErrorAction Stop
$arguments = @("--print", "--output-format", "text", "--workspace", $resolvedTarget)
if ($Force) {
    $arguments += "--force"
}
$arguments += $promptText

Write-Host "Starting Cursor synchronously in: $resolvedTarget"
& $cursor.Source @arguments
exit $LASTEXITCODE
