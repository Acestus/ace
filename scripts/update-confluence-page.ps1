# Update Confluence Page Content
# Usage: .\update-confluence-page.ps1 -PageId "<PAGE_ID>" -ContentFile "page-content.html" -VersionMessage "Updated from VSCode"

param(
    [Parameter(Mandatory=$true)]
    [string]$PageId,
    
    [Parameter(Mandatory=$false)]
    [string]$ContentFile,
    
    [Parameter(Mandatory=$false)]
    [string]$Content,
    
    [Parameter(Mandatory=$false)]
    [string]$Title,
    
    [Parameter(Mandatory=$false)]
    [string]$VersionMessage = "Updated from VSCode",
    
    [Parameter(Mandatory=$false)]
    [string]$BaseUrl = "https://<YOUR_ATLASSIAN>.atlassian.net/wiki/rest/api"
)

# Load credentials from .env file if it exists
$rootEnvPath = Join-Path $PSScriptRoot "../.env"
$localEnvPath = Join-Path $PSScriptRoot ".env"

if (Test-Path $rootEnvPath) {
    Get-Content $rootEnvPath | ForEach-Object {
        if ($_ -match '^([^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
} elseif (Test-Path $localEnvPath) {
    Get-Content $localEnvPath | ForEach-Object {
        if ($_ -match '^([^=]+)=(.*)$') {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            [System.Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
}

. (Join-Path $PSScriptRoot "lib/ErrorHelpers.ps1")
Require-EnvVar -Names @("CONFLUENCE_EMAIL","WWEEKS_CONFLUENCE_API_TOKEN")

$email = $env:CONFLUENCE_EMAIL
$token = $env:WWEEKS_CONFLUENCE_API_TOKEN

# Create auth header
$base64AuthInfo = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("${email}:${token}"))
$headers = @{
    "Authorization" = "Basic $base64AuthInfo"
    "Accept" = "application/json"
    "Content-Type" = "application/json"
}

# Get current page to retrieve version and title
Write-Host "Fetching current page data..." -ForegroundColor Cyan
$currentPageUri = "$BaseUrl/content/${PageId}?expand=body.storage,version"

try {
    $currentPage = Invoke-RestMethod -Uri $currentPageUri -Headers $headers -Method Get
    
    Write-Host "✓ Current page retrieved" -ForegroundColor Green
    Write-Host "  Current version: $($currentPage.version.number)" -ForegroundColor Gray
    Write-Host "  Current title: $($currentPage.title)" -ForegroundColor Gray
    
    # Determine new version number
    $newVersion = $currentPage.version.number + 1
    
    # Use existing title if not provided
    if (-not $Title) {
        $Title = $currentPage.title
    }
    
    # Get content from file or parameter
    if ($ContentFile) {
        if (-not (Test-Path $ContentFile)) {
            Write-ActionableError -Message "Content file not found: $ContentFile" `
                -Causes @("Path is relative to wrong working directory", "File typo or wrong extension") `
                -Try @("ls -la $(Split-Path $ContentFile -Parent 2>$null)", "Pass an absolute path")
        }
        $Content = Get-Content -Path $ContentFile -Raw
    } elseif (-not $Content) {
        Write-ActionableError -Message "Either -ContentFile or -Content must be provided" `
            -Causes @("Neither flag was passed") `
            -Try @("Re-run with -ContentFile path/to/page.html OR -Content '<p>...</p>'")
    }
    
    # Create update body
    $updateBody = @{
        version = @{
            number = $newVersion
            message = $VersionMessage
        }
        title = $Title
        type = "page"
        body = @{
            storage = @{
                value = $Content
                representation = "storage"
            }
        }
    } | ConvertTo-Json -Depth 10
    
    # Update the page
    Write-Host "`nUpdating page..." -ForegroundColor Cyan
    $updateUri = "$BaseUrl/content/${PageId}"
    
    $response = Invoke-RestMethod -Uri $updateUri -Headers $headers -Method Put -Body $updateBody
    
    Write-Host "✓ Page updated successfully!" -ForegroundColor Green
    Write-Host "  New version: $($response.version.number)" -ForegroundColor Gray
    Write-Host "  Title: $($response.title)" -ForegroundColor Gray
    Write-Host "  URL: $($response._links.base)$($response._links.webui)" -ForegroundColor Cyan
    
    return $response
    
} catch {
    $sc = $null
    try { $sc = [int]$_.Exception.Response.StatusCode } catch {}
    $body = ""
    if ($_.Exception.Response) {
        try {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $reader.BaseStream.Position = 0
            $body = $reader.ReadToEnd()
        } catch {}
    }
    Write-ActionableError -Message "Confluence page update failed for PageId $PageId (HTTP $sc): $($_.Exception.Message)" `
        -Causes @(
            "PageId $PageId does not exist",
            "Version conflict — another editor saved a newer version (HTTP 409)",
            "Account lacks 'Edit' permission on the page",
            "Storage-format XHTML is malformed"
        ) `
        -Try @(
            "Re-fetch page to get latest version: curl -u `"$email`:<token>`" '$BaseUrl/content/$PageId?expand=version'",
            "Open page in browser: https://<YOUR_ATLASSIAN>.atlassian.net/wiki/pages/viewpage.action?pageId=$PageId",
            "Response body: $body"
        ) `
        -Docs "confluence/<ORG_NAME>-Engineering/Confluence-API.md"
}
