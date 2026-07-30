[CmdletBinding()]
param(
    [ValidateSet("Economy", "Standard", "Sensitive", "Deep")]
    [string]$ReviewTier = "Standard",

    [string]$Module = "",

    [string]$WorkPackage = "",

    [string]$PromptPath = ".cursor\reviews\qmtool-work-package-review.md",

    [string]$OutputPath = "docs\reviews\codex_latest_review.md"
)

$ErrorActionPreference = "Stop"

function Resolve-ReviewConfiguration {
    param([string]$Tier)

    switch ($Tier) {
        "Economy" {
            return @{ Model = "gpt-5.4-mini"; Reasoning = "medium" }
        }
        "Standard" {
            return @{ Model = "gpt-5.6-luna"; Reasoning = "medium" }
        }
        "Sensitive" {
            return @{ Model = "gpt-5.6-terra"; Reasoning = "medium" }
        }
        "Deep" {
            return @{ Model = "gpt-5.6-sol"; Reasoning = "high" }
        }
        default {
            throw "Unbekanntes ReviewTier: $Tier"
        }
    }
}

if (-not (Get-Command codex -ErrorAction SilentlyContinue)) {
    throw "Die Codex CLI wurde nicht gefunden. Installiere bzw. aktualisiere Codex und melde dich einmal interaktiv an."
}

$repoRoot = (& git rev-parse --show-toplevel 2>$null).Trim()
if (-not $repoRoot) {
    throw "Der Review muss innerhalb eines Git-Repositories gestartet werden."
}

$repoRoot = (Resolve-Path $repoRoot).Path
Set-Location $repoRoot

$resolvedPromptPath = Join-Path $repoRoot $PromptPath
if (-not (Test-Path -LiteralPath $resolvedPromptPath -PathType Leaf)) {
    throw "Review-Prompt nicht gefunden: $resolvedPromptPath"
}

$resolvedOutputPath = Join-Path $repoRoot $OutputPath
$outputDirectory = Split-Path -Parent $resolvedOutputPath
if ($outputDirectory) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$config = Resolve-ReviewConfiguration -Tier $ReviewTier
$basePrompt = Get-Content -LiteralPath $resolvedPromptPath -Raw -Encoding UTF8

$runtimeContext = @"

## Laufkontext

- Review-Tier: $ReviewTier
- Modell: $($config.Model)
- Reasoning: $($config.Reasoning)
- Modul: $(if ($Module) { $Module } else { "aus Git-Diff und Planungsdateien bestimmen" })
- Arbeitspaket: $(if ($WorkPackage) { $WorkPackage } else { "aus Git-Diff und Entwicklungsstatus bestimmen" })
- Repository-Root: $repoRoot

Prüfe nur dieses Arbeitspaket und angrenzende Stellen, die für seine Korrektheit zwingend relevant sind.
"@

$prompt = $basePrompt + $runtimeContext
$configOverride = 'model_reasoning_effort="' + $config.Reasoning + '"'

# UTF-8 für die Übergabe an den nativen Prozess sicherstellen.
$previousOutputEncoding = $OutputEncoding
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

try {
    # --ask-for-approval und --sandbox sind globale Codex-Optionen und
    # muessen deshalb vor dem Unterbefehl `exec` stehen.
    $globalArgs = @(
        "--ask-for-approval", "never",
        "--model", $config.Model,
        "--sandbox", "read-only"
    )

    $execArgs = @(
        "exec",
        "--cd", $repoRoot,
        "--config", $configOverride,
        "--ephemeral",
        "--color", "never",
        "--output-last-message", $resolvedOutputPath,
        "-"
    )

    $prompt | & codex @globalArgs @execArgs

    if ($LASTEXITCODE -ne 0) {
        throw "Codex-Review fehlgeschlagen. Exit-Code: $LASTEXITCODE"
    }
}
finally {
    $OutputEncoding = $previousOutputEncoding
}

if (-not (Test-Path -LiteralPath $resolvedOutputPath -PathType Leaf)) {
    throw "Codex wurde beendet, aber der erwartete Prüfbericht wurde nicht erzeugt: $resolvedOutputPath"
}

Write-Host "Codex-Review abgeschlossen."
Write-Host "Tier: $ReviewTier | Modell: $($config.Model) | Reasoning: $($config.Reasoning)"
Write-Host "Bericht: $resolvedOutputPath"
