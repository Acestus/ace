# scripts/lib/ErrorHelpers.ps1
#
# Shared PowerShell helpers for actionable error messages.
# Dot-source from any script:
#   . (Join-Path $PSScriptRoot "lib/ErrorHelpers.ps1")
#
# See .github/instructions/error-messaging.instructions.md for the convention.

function Write-ActionableError {
    <#
    .SYNOPSIS
        Prints an actionable error block (causes + try + docs) and throws.
    .EXAMPLE
        Write-ActionableError -Message "Confluence API rejected request (401)" `
            -Causes @(
                "WWEEKS_CONFLUENCE_API_TOKEN is expired or revoked",
                "CONFLUENCE_EMAIL does not match the token owner"
            ) `
            -Try @(
                "Rotate token: https://id.atlassian.com/manage-profile/security/api-tokens",
                "grep CONFLUENCE_ .env"
            ) `
            -Docs "confluence/<ORG_NAME>-Engineering/Jira-API-Setup.md"
    #>
    param(
        [Parameter(Mandatory=$true)][string]$Message,
        [string[]]$Causes = @(),
        [string[]]$Try = @(),
        [string]$Docs = $null,
        [int]$ExitCode = 1,
        [switch]$NoThrow
    )

    Write-Host ""
    Write-Host "❌ $Message" -ForegroundColor Red
    if ($Causes.Count -gt 0) {
        Write-Host "   Likely causes:" -ForegroundColor Yellow
        foreach ($c in $Causes) { Write-Host "     • $c" -ForegroundColor Yellow }
    }
    if ($Try.Count -gt 0) {
        Write-Host "   Try:" -ForegroundColor Cyan
        foreach ($t in $Try) { Write-Host "     • $t" -ForegroundColor Cyan }
    }
    if ($Docs) { Write-Host "   Docs: $Docs" -ForegroundColor Gray }
    Write-Host ""

    if ($NoThrow) { return }
    exit $ExitCode
}

function Require-EnvVar {
    <#
    .SYNOPSIS
        Asserts one or more env vars are set. Fails with actionable error if any are missing.
    .EXAMPLE
        Require-EnvVar -Names @("CONFLUENCE_EMAIL","WWEEKS_CONFLUENCE_API_TOKEN") `
            -Hint "Load .env: . scripts/load-env.ps1"
    #>
    param(
        [Parameter(Mandatory=$true)][string[]]$Names,
        [string]$Hint = $null
    )
    $missing = @()
    foreach ($n in $Names) {
        if (-not [Environment]::GetEnvironmentVariable($n)) { $missing += $n }
    }
    if ($missing.Count -eq 0) { return }

    $tryList = @(
        "Check .env: grep -E '^($($missing -join '|'))=' .env"
    )
    if ($Hint) { $tryList += $Hint }

    Write-ActionableError -Message "Missing required environment variable(s): $($missing -join ', ')" `
        -Causes @(
            ".env file was not loaded into this session",
            "Variable name typo (check exact casing)",
            "Running outside the project root"
        ) `
        -Try $tryList
}

function Invoke-WithActionableError {
    <#
    .SYNOPSIS
        Wraps a script block. On error, prints actionable block and re-throws.
    .EXAMPLE
        Invoke-WithActionableError -Operation "Connect-MgGraph" `
            -ApiName "Microsoft Graph" `
            -CommonCauses @{
                401 = @("Token expired", "Scopes insufficient");
                403 = @("App needs admin consent");
            } `
            -ScriptBlock { Connect-MgGraph -Scopes "Sites.ReadWrite.All" -NoWelcome }
    #>
    param(
        [Parameter(Mandatory=$true)][scriptblock]$ScriptBlock,
        [Parameter(Mandatory=$true)][string]$Operation,
        [string]$ApiName = "the API",
        [hashtable]$CommonCauses = @{},
        [string[]]$ExtraTry = @()
    )

    try {
        & $ScriptBlock
    } catch {
        $err = $_
        $statusCode = $null
        if ($err.Exception.Response) {
            try { $statusCode = [int]$err.Exception.Response.StatusCode } catch {}
        }

        $causes = @()
        $tryList = @()
        if ($statusCode -and $CommonCauses.ContainsKey($statusCode)) {
            $causes = $CommonCauses[$statusCode]
        }
        if ($ExtraTry.Count -gt 0) { $tryList += $ExtraTry }
        $tryList += "Replay with -Verbose for full request/response detail"

        $msg = "$Operation failed against $ApiName"
        if ($statusCode) { $msg += " (HTTP $statusCode)" }
        $msg += ": $($err.Exception.Message)"

        Write-ActionableError -Message $msg -Causes $causes -Try $tryList -NoThrow
        throw
    }
}

# Common-cause dictionaries — keyed by HTTP status code

$Script:GRAPH_COMMON_CAUSES = @{
    401 = @(
        "Graph access token expired (typical lifetime: 60-90 min)",
        "Connect-MgGraph not yet called in this session",
        "Required scope missing from -Scopes parameter"
    )
    403 = @(
        "App registration lacks admin consent for the requested scope",
        "Signed-in user lacks permission on the target site/drive/item",
        "Conditional Access blocking the request"
    )
    404 = @(
        "Site, drive, file, or user ID does not exist",
        "Site URL path is wrong (check :/sites/<name> casing)",
        "Item was deleted or moved"
    )
    429 = @(
        "Graph throttling — back off and retry (use Retry-After header)"
    )
}

$Script:CONFLUENCE_COMMON_CAUSES = @{
    401 = @(
        "WWEEKS_CONFLUENCE_API_TOKEN expired or revoked",
        "CONFLUENCE_EMAIL does not match the token owner",
        "Basic auth header not constructed as 'email:token'"
    )
    403 = @(
        "Account lacks 'Space admin' or page edit permission",
        "Page is restricted to a specific group"
    )
    404 = @(
        "Page ID does not exist (or wrong space key)",
        "Confluence Cloud vs Server endpoint mismatch"
    )
}
