# OPTIONAL Compose helper (not an M3 prerequisite). Requires
# QMTOOL_PG_TEST_ADMIN_PASSWORD in the environment when used.
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("start", "status", "stop")]
    [string]$Action
)

$ErrorActionPreference = "Stop"
$compose = Join-Path $PSScriptRoot "compose.yaml"

if (-not $env:QMTOOL_PG_TEST_ADMIN_PASSWORD) {
    throw "QMTOOL_PG_TEST_ADMIN_PASSWORD is required (no default)."
}

switch ($Action) {
    "start" {
        docker compose -f $compose up -d
        docker compose -f $compose ps
    }
    "status" {
        docker compose -f $compose ps
    }
    "stop" {
        docker compose -f $compose stop
    }
}
