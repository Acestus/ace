#!/usr/bin/env pwsh
# Planner-DayEnd.ps1: Deterministic local-first day-end path for planner
#
# This script:
# 1. Runs dotnet workflow end-my-day to sync with Linear/Notion/GitHub
# 2. Exports the local SQLite snapshot to .catalog/assigned-work.db
# 3. Prepares standup summary from local data
# 4. Shows readiness for end-of-day planner flow

param(
    [switch]$NoPublish = $false,
    [switch]$Verbose = $false
)

$ErrorActionPreference = 'Stop'

$RepoRoot = (Get-Item "$PSScriptRoot/..").FullName
$WorkflowDb = "$env:USERPROFILE/.acestus/workflow.db"
$CatalogDir = "$RepoRoot/.catalog"
$CatalogDb = "$CatalogDir/assigned-work.db"

# Colors
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Error { Write-Host "❌ $args" -ForegroundColor Red }
function Write-Info { Write-Host "ℹ️  $args" -ForegroundColor Cyan }
function Write-Step { Write-Host "🔵 $args" -ForegroundColor Blue }
function Write-Warn { Write-Host "⚠️  $args" -ForegroundColor Yellow }

Write-Host "🌙 Planner Day-End Flow" -ForegroundColor Blue
Write-Host ""

# Step 1: Run workflow end-my-day
Write-Step "Step 1: Publishing changes to Linear/Notion/GitHub..."
if (-not $NoPublish) {
    $result = & dotnet run --project "$RepoRoot/src/Ace.Tools.Cli" -- workflow end-my-day 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Workflow end-my-day completed"
    } else {
        Write-Error "Workflow end-my-day failed"
        Write-Host $result
        exit 1
    }
} else {
    Write-Warn "Skipping workflow end-my-day (--NoPublish)"
}
Write-Host ""

# Step 2: Export local snapshot to catalog
Write-Step "Step 2: Creating local snapshot..."
New-Item -ItemType Directory -Path $CatalogDir -Force | Out-Null

if (Test-Path $WorkflowDb) {
    try {
        Copy-Item $WorkflowDb $CatalogDb -Force
        $size = (Get-Item $CatalogDb).Length / 1KB
        Write-Success "Snapshot created: $([Math]::Round($size, 1)) KB"
    } catch {
        Write-Warn "Could not create catalog snapshot: $_"
    }
} else {
    Write-Warn "Workflow database not found at $WorkflowDb"
}
Write-Host ""

# Step 3: Prepare standup summary template
Write-Step "Step 3: Preparing standup summary..."

$standupTemplate = @"
# Standup Summary (from local snapshot)
Generated: $(Get-Date -AsUTC -Format 'yyyy-MM-dd HH:mm:ss UTC')

## Work Completed Today
- Using local SQLite snapshot (.catalog/assigned-work.db)
- Deterministic results (no random re-querying of live systems)
- Ready for standup generation

## Pending Actions
- Linear comments: (from local snapshot)
- Notion pages: (from local snapshot)
- CRM syncs: (from local snapshot)
- Job search: (from local snapshot)

## Ready for Next Step
Run 'planner standup' to generate final summary from this snapshot
"@

$standupTemplate | Out-File "$CatalogDir/standup-summary.txt" -Encoding UTF8
Write-Success "Standup summary template created"
Write-Host ""

# Step 4: Show summary
Write-Step "Step 4: Day-End Summary"
if (Test-Path $WorkflowDb) {
    $dbSize = (Get-Item $WorkflowDb).Length / 1MB
    Write-Info "Workflow DB: $WorkflowDb ($([Math]::Round($dbSize, 2)) MB)"
}
if (Test-Path $CatalogDb) {
    $catalogSize = (Get-Item $CatalogDb).Length / 1MB
    Write-Info "Catalog DB: $CatalogDb ($([Math]::Round($catalogSize, 2)) MB)"
}
Write-Info "Standup summary: $CatalogDir/standup-summary.txt"
Write-Host ""

Write-Success "Day-end flow complete!"
Write-Host ""
Write-Host "Next steps:"
Write-Host "   1. Review work in planner: $RepoRoot/planner/$(Get-Date -Format 'MM-dd').org"
Write-Host "   2. Run 'planner standup' to generate final summary"
Write-Host "   3. Commit: git add -A && git commit -m 'Daily standup summary'"
Write-Host "   4. Push: git push"
Write-Host ""

if ($Verbose) {
    Write-Host "Debug Info:"
    if (Test-Path $CatalogDb) {
        Write-Host "  Catalog tables: (use .catalog/query.sql to inspect)"
    }
}
