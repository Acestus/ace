# Create New Confluence Page
# Usage: .\create-confluence-page.ps1 -SpaceKey "IPM" -Title "My New Page" -Content "<p>Hello World</p>" -ParentId "<PAGE_ID>"

param(
    [Parameter(Mandatory=$true)]
    [string]$SpaceKey,
    
    [Parameter(Mandatory=$true)]
    [string]$Title,
    
    [Parameter(Mandatory=$false)]
    [string]$ContentFile,
    
    [Parameter(Mandatory=$false)]
    [string]$Content = "<p>Page created from VSCode</p>",
    
    [Parameter(Mandatory=$false)]
    [string]$ParentId,
    
    [Parameter(Mandatory=$false)]
    [switch]$IsLiveDoc,
    
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

# Get content from file or parameter
if ($ContentFile) {
    if (-not (Test-Path $ContentFile)) {
        Write-ActionableError -Message "Content file not found: $ContentFile" `
            -Causes @(
                "Path is relative to wrong working directory",
                "File typo or wrong extension"
            ) `
            -Try @(
                "ls -la $(Split-Path $ContentFile -Parent 2>$null)",
                "Pass an absolute path"
            )
    }
    $Content = Get-Content -Path $ContentFile -Raw
}

# Create page body
$pageBody = @{
    type = "page"
    title = $Title
    space = @{
        key = $SpaceKey
    }
    body = @{
        storage = @{
            value = $Content
            representation = "storage"
        }
    }
}

# Add parent if provided
if ($ParentId) {
    $pageBody.ancestors = @(
        @{
            id = $ParentId
        }
    )
}

$jsonBody = $pageBody | ConvertTo-Json -Depth 10

# Create the page
Write-Host "Creating new page..." -ForegroundColor Cyan
Write-Host "  Space: $SpaceKey" -ForegroundColor Gray
Write-Host "  Title: $Title" -ForegroundColor Gray
if ($ParentId) {
    Write-Host "  Parent ID: $ParentId" -ForegroundColor Gray
}

try {
    $uri = "$BaseUrl/content"
    $response = Invoke-RestMethod -Uri $uri -Headers $headers -Method Post -Body $jsonBody
    
    Write-Host "`n✓ Page created successfully!" -ForegroundColor Green
    Write-Host "  Page ID: $($response.id)" -ForegroundColor Gray
    Write-Host "  Title: $($response.title)" -ForegroundColor Gray
    Write-Host "  URL: https://<YOUR_ATLASSIAN>.atlassian.net$($response._links.webui)" -ForegroundColor Cyan
    
    # If IsLiveDoc flag is set, we would need to use a different API endpoint or method
    if ($IsLiveDoc) {
        Write-Warning "Live doc creation may require additional API calls or Confluence UI configuration"
    }
    
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
    Write-ActionableError -Message "Confluence page creation failed (HTTP $sc): $($_.Exception.Message)" `
        -Causes @(
            "Page with this title already exists in space '$SpaceKey' (Confluence rejects duplicate titles in same space)",
            "ParentId '$ParentId' does not exist or is in a different space",
            "Account lacks 'Add Page' permission in space '$SpaceKey'",
            "Storage-format XHTML is malformed (unclosed tags, bad CDATA)"
        ) `
        -Try @(
            "Search for existing page: curl -u `"$email`:<token>`" '$BaseUrl/content?spaceKey=$SpaceKey&title=$([uri]::EscapeDataString($Title))'",
            "Verify parent: curl -u `"$email`:<token>`" '$BaseUrl/content/$ParentId'",
            "Validate storage format with the macro storage-format converter in Confluence UI",
            "Response body: $body"
        ) `
        -Docs "confluence/<ORG_NAME>-Engineering/Confluence-API.md"
}
