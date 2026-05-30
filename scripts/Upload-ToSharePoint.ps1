param(
    [Parameter(Mandatory=$true)]
    [string]$FilePath,
    [string]$TargetFolder = "docs",
    [string]$SiteRelPath  = "/sites/Infrastructure",
    [string]$LibraryName  = "FS - Infrastructure"
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "lib/ErrorHelpers.ps1")

try {
    Import-Module Microsoft.Graph.Authentication -ErrorAction Stop
} catch {
    Write-ActionableError -Message "Cannot load module 'Microsoft.Graph.Authentication'" `
        -Causes @(
            "Microsoft.Graph PowerShell SDK not installed",
            "PowerShell module path doesn't include the install location"
        ) `
        -Try @(
            "Install-Module Microsoft.Graph -Scope CurrentUser",
            "Get-Module -ListAvailable Microsoft.Graph*"
        )
}

Write-Host "Connecting to Microsoft Graph (delegated)..." -ForegroundColor Cyan
try {
    Connect-MgGraph -Scopes "Sites.ReadWrite.All","Files.ReadWrite.All" -NoWelcome
} catch {
    Write-ActionableError -Message "Connect-MgGraph failed: $($_.Exception.Message)" `
        -Causes @(
            "Browser auth window was closed or denied",
            "Tenant does not allow delegated Sites.ReadWrite.All scope",
            "Conditional Access blocking the device"
        ) `
        -Try @(
            "Disconnect-MgGraph; Connect-MgGraph -Scopes ... again",
            "Sign in via az login first to prime tenant cookies"
        )
}

if (-not (Test-Path $FilePath)) {
    Write-ActionableError -Message "Source file not found: $FilePath" `
        -Causes @(
            "Path is relative to wrong working directory",
            "File was deleted or never created"
        ) `
        -Try @(
            "ls -la $(Split-Path $FilePath -Parent)",
            "Pass an absolute path with -FilePath"
        )
}

$fileName  = [System.IO.Path]::GetFileName($FilePath)
$fileBytes = [System.IO.File]::ReadAllBytes($FilePath)
$fileSize  = (Get-Item $FilePath).Length

Write-Host "File: $fileName ($fileSize bytes)" -ForegroundColor White
Write-Host "Target: https://<org_short>fg.sharepoint.com$SiteRelPath/$LibraryName/$TargetFolder/$fileName" -ForegroundColor White

Write-Host "  -> Resolving site..." -ForegroundColor Gray
try {
    $site = Invoke-MgGraphRequest -Method GET -Uri "https://graph.microsoft.com/v1.0/sites/<org_short>fg.sharepoint.com:$SiteRelPath"
} catch {
    Write-ActionableError -Message "Failed to resolve SharePoint site '$SiteRelPath': $($_.Exception.Message)" `
        -Causes @(
            "Site relative path is wrong (check casing: /sites/Infrastructure)",
            "Signed-in user has no access to this site",
            "Site URL changed or site was deleted"
        ) `
        -Try @(
            "Open https://<org_short>fg.sharepoint.com$SiteRelPath in a browser to verify access",
            "List sites you can see: Invoke-MgGraphRequest GET 'https://graph.microsoft.com/v1.0/sites?search=Infrastructure'"
        )
}
$siteId = $site.id
Write-Host "  OK Site: $($site.displayName) ($siteId)" -ForegroundColor Green

Write-Host "  -> Finding '$LibraryName' drive..." -ForegroundColor Gray
$drivesResp = Invoke-MgGraphRequest -Method GET -Uri "https://graph.microsoft.com/v1.0/sites/$siteId/drives"
$drive      = $drivesResp.value | Where-Object { $_.name -eq $LibraryName }

if (-not $drive) {
    $available = ($drivesResp.value | ForEach-Object { $_.name }) -join ", "
    Write-ActionableError -Message "Document library '$LibraryName' not found on site $SiteRelPath" `
        -Causes @(
            "Library name typo or wrong casing",
            "Library was renamed in SharePoint admin",
            "Wrong site — library lives elsewhere"
        ) `
        -Try @(
            "Pass -LibraryName with one of: $available",
            "Verify library in SharePoint admin: https://<org_short>fg.sharepoint.com$SiteRelPath"
        )
}
Write-Host "  OK Drive: $($drive.name) ($($drive.id))" -ForegroundColor Green

$uploadUri = "https://graph.microsoft.com/v1.0/drives/$($drive.id)/root:/$TargetFolder/$($fileName):/content"
Write-Host "  -> Uploading..." -ForegroundColor Gray
try {
    $result = Invoke-MgGraphRequest -Method PUT -Uri $uploadUri -Body $fileBytes -ContentType "text/html; charset=utf-8"
} catch {
    Write-ActionableError -Message "Upload to SharePoint failed: $($_.Exception.Message)" `
        -Causes @(
            "File exceeds 4MB simple-upload limit (use upload session for larger)",
            "Target folder '$TargetFolder' is checked out by another user",
            "Library requires check-in with metadata fields"
        ) `
        -Try @(
            "Check folder is writable: Invoke-MgGraphRequest GET 'https://graph.microsoft.com/v1.0/drives/$($drive.id)/root:/$TargetFolder'",
            "For files > 4MB use createUploadSession API"
        )
}
Write-Host "  OK Uploaded: $($result.webUrl)" -ForegroundColor Green
Write-Host ""
Write-Host "Done! File is live at:" -ForegroundColor Cyan
Write-Host "   $($result.webUrl)" -ForegroundColor White
