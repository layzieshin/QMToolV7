[CmdletBinding(DefaultParameterSetName = "Inline")]
param(
    [Parameter(Mandatory = $true)]
    [string]$TargetRoot,

    [Parameter(Mandatory = $true, ParameterSetName = "Inline")]
    [string]$Prompt,

    [Parameter(Mandatory = $true, ParameterSetName = "File")]
    [string]$PromptPath,

    [switch]$Force,
    [switch]$Interactive,
    [string]$ResumeSession
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
    return $process.ExitCode
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
    "--model", "composer-2.5"
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
$argumentList += "--"
$argumentList += $promptText

Write-Host "Starting Cursor synchronously in: $resolvedTarget"
exit (Invoke-CursorAgentProcess -Executable $cursor.Source -ArgumentList $argumentList -WorkingDirectory $resolvedTarget)
