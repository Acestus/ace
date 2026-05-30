# Test Confluence API Connection
# Usage: .\test-connection.ps1

param(
    [Parameter(Mandatory=$false)]
    [string]$BaseUrl = "https://<YOUR_ATLASSIAN>.atlassian.net/wiki/rest/api"
)

# Try to load from root .env file first, then local
$rootEnvPath = Join-Path $PSScriptRoot "../.env"
$localEnvPath = Join-Path $PSScriptRoot ".env"

if (Test-Path $rootEnvPath) {
    Write-Host "Loading credentials from root .env file..." -ForegroundColor Cyan
    Get-Content $rootEnvPath | ForEach-Object {
        if ($_ -match '^([^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
} elseif (Test-Path $localEnvPath) {
    Write-Host "Loading credentials from local .env file..." -ForegroundColor Cyan
    Get-Content $localEnvPath | ForEach-Object {
        if ($_ -match '^([^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

$email = $env:CONFLUENCE_EMAIL
$token = $env:WWEEKS_CONFLUENCE_API_TOKEN

. (Join-Path $PSScriptRoot "lib/ErrorHelpers.ps1")
Require-EnvVar -Names @("CONFLUENCE_EMAIL","WWEEKS_CONFLUENCE_API_TOKEN") `
    -Hint "Load env: . scripts/load-env.ps1 (or 'export `$(grep -v ^# .env | xargs)' in bash before invoking pwsh)"

Write-Host "✓ Email found: $email" -ForegroundColor Green
Write-Host "✓ Token found: $($token.Substring(0, 4))...$($token.Substring($token.Length - 4))" -ForegroundColor Green

# Create auth header
$base64AuthInfo = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${email}:${token}"))
$headers = @{
    "Authorization" = "Basic $base64AuthInfo"
    "Accept" = "application/json"
}

# Test 1: Get current user
Write-Host "`n=== Test 1: Getting current user ===" -ForegroundColor Cyan
try {
    $userUri = "$BaseUrl/user/current"
    $user = Invoke-RestMethod -Uri $userUri -Headers $headers -Method Get
    Write-Host "✓ Authentication successful!" -ForegroundColor Green
    Write-Host "  User: $($user.displayName)" -ForegroundColor Gray
    Write-Host "  Account ID: $($user.accountId)" -ForegroundColor Gray
    Write-Host "  Email: $($user.email)" -ForegroundColor Gray
} catch {
    $sc = $null
    try { $sc = [int]$_.Exception.Response.StatusCode } catch {}
    Write-ActionableError -Message "Confluence /user/current call failed (HTTP $sc): $($_.Exception.Message)" `
        -Causes @(
            "WWEEKS_CONFLUENCE_API_TOKEN expired or revoked",
            "CONFLUENCE_EMAIL ($email) does not match the token owner",
            "Base URL wrong — should be https://<site>.atlassian.net/wiki/rest/api"
        ) `
        -Try @(
            "Rotate token: https://id.atlassian.com/manage-profile/security/api-tokens",
            "Verify with curl: curl -u `"$email`:<token>`" $BaseUrl/user/current",
            "Confirm BaseUrl: $BaseUrl"
        ) `
        -Docs "confluence/<ORG_NAME>-Engineering/Jira-API-Setup.md"
}

# Test 2: Get IPM space
Write-Host "`n=== Test 2: Accessing IPM space ===" -ForegroundColor Cyan
try {
    $spaceUri = "$BaseUrl/space/IPM"
    $space = Invoke-RestMethod -Uri $spaceUri -Headers $headers -Method Get
    Write-Host "✓ IPM space accessible!" -ForegroundColor Green
    Write-Host "  Space Name: $($space.name)" -ForegroundColor Gray
    Write-Host "  Space Key: $($space.key)" -ForegroundColor Gray
    Write-Host "  Space ID: $($space.id)" -ForegroundColor Gray
} catch {
    Write-ActionableError -Message "Cannot access Confluence space 'IPM': $($_.Exception.Message)" `
        -Causes @(
            "IPM space was renamed/deleted",
            "Account lacks 'View' permission on the IPM space",
            "Space key is case-sensitive — should be all caps"
        ) `
        -Try @(
            "List spaces you can see: curl -u `"$email`:<token>`" '$BaseUrl/space?limit=50'",
            "Ask a Confluence admin to grant 'View' on IPM"
        )
}

# Test 3: List recent pages
Write-Host "`n=== Test 3: Listing recent pages ===" -ForegroundColor Cyan
try {
    $pagesUri = "$BaseUrl/content?spaceKey=IPM&limit=5&expand=version,space"
    $pages = Invoke-RestMethod -Uri $pagesUri -Headers $headers -Method Get
    Write-Host "✓ Found $($pages.size) pages (showing first 5):" -ForegroundColor Green
    foreach ($page in $pages.results) {
        Write-Host "  • $($page.title) (ID: $($page.id), v$($page.version.number))" -ForegroundColor Gray
    }
} catch {
    Write-ActionableError -Message "Cannot list pages in IPM space: $($_.Exception.Message)" `
        -Causes @(
            "Account lacks page-read permission",
            "Confluence Cloud rate limit hit (try again in a minute)"
        ) `
        -Try @(
            "Retry after 60 seconds",
            "Check rate limit headers in the response"
        )
}

Write-Host "`n🎉 All tests passed! Your Confluence API connection is working." -ForegroundColor Green
Write-Host "`nYou can now use the other scripts:" -ForegroundColor Yellow
Write-Host "  .\get-confluence-page.ps1 -PageId '<PAGE_ID>'" -ForegroundColor Cyan
Write-Host "  .\update-confluence-page.ps1 -PageId '<PAGE_ID>' -Content '<p>Test</p>'" -ForegroundColor Cyan
Write-Host "  .\create-confluence-page.ps1 -SpaceKey 'IPM' -Title 'Test Page' -Content '<p>Hello</p>'" -ForegroundColor Cyan
