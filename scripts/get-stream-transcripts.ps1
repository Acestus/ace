#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Downloads VTT transcripts of your Microsoft Stream videos.

.DESCRIPTION
    Authenticates via device code flow (browser sign-in), searches Microsoft Graph
    for video files you created across OneDrive and SharePoint, downloads any
    available transcripts as .vtt files, and saves them to the output directory.

    Uses the Microsoft Graph beta API for media transcriptions.

.PARAMETER OutputDir
    Directory to save transcripts. Created if it doesn't exist.
    Default: ./transcripts

.PARAMETER TenantId
    Entra ID tenant ID or domain. Defaults to 'organizations' (any work/school account).
    Set this to your tenant ID if you get consent errors.

.EXAMPLE
    ./get-stream-transcripts.ps1
    ./get-stream-transcripts.ps1 -OutputDir ./docs/transcripts
    ./get-stream-transcripts.ps1 -TenantId contoso.onmicrosoft.com
#>

[CmdletBinding()]
param(
    [string]$OutputDir = "./transcripts",
    [string]$TenantId  = "organizations"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

. (Join-Path $PSScriptRoot "lib/ErrorHelpers.ps1")

# ── Constants ────────────────────────────────────────────────────────

$GraphBase = "https://graph.microsoft.com"

# Microsoft Graph Command Line Tools — first-party public client app
# Supports device code flow without requiring your own app registration
$ClientId  = "14d82eec-204b-4c2f-b7e8-296a70dab67e"
$Authority = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0"

$VideoExtensions = @("mp4", "webm", "mov", "avi", "mkv", "m4v")
$Scopes = "Files.Read.All Sites.Read.All openid profile offline_access"

# Token cache — persists refresh token between runs
$TokenCachePath = Join-Path $PSScriptRoot ".graph-token-cache.json"

# ── Token Management ─────────────────────────────────────────────────

function Save-TokenCache {
    param($TokenResponse)
    $cache = @{
        access_token  = $TokenResponse.access_token
        refresh_token = $TokenResponse.refresh_token
        expires_at    = [DateTimeOffset]::UtcNow.AddSeconds([int]$TokenResponse.expires_in - 60).ToUnixTimeSeconds()
    }
    $cache | ConvertTo-Json | Set-Content -Path $TokenCachePath -Encoding UTF8
}

function Get-CachedToken {
    if (-not (Test-Path $TokenCachePath)) { return $null }

    try {
        $cache = Get-Content $TokenCachePath -Raw | ConvertFrom-Json
    } catch {
        return $null
    }

    $now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()

    # Token still valid — use it directly
    if ($cache.expires_at -gt $now -and $cache.access_token) {
        Write-Host "🔑 Using cached token" -ForegroundColor Cyan
        return $cache.access_token
    }

    # Token expired but we have a refresh token — try to refresh
    if ($cache.refresh_token) {
        Write-Host "🔄 Refreshing token..." -ForegroundColor Cyan
        try {
            $refreshResp = Invoke-RestMethod -Uri "$Authority/token" -Method POST -Body @{
                client_id     = $ClientId
                grant_type    = "refresh_token"
                refresh_token = $cache.refresh_token
                scope         = $Scopes
            } -ContentType "application/x-www-form-urlencoded"

            Save-TokenCache $refreshResp
            Write-Host "✅ Token refreshed" -ForegroundColor Green
            return $refreshResp.access_token
        } catch {
            Write-Host "⚠️  Refresh failed — will re-authenticate" -ForegroundColor Yellow
        }
    }

    return $null
}

# ── Authenticate ─────────────────────────────────────────────────────

$accessToken = Get-CachedToken

if (-not $accessToken) {
    Write-Host "🔑 Requesting device code..." -ForegroundColor Cyan

    $deviceCodeResp = Invoke-RestMethod -Uri "$Authority/devicecode" -Method POST -Body @{
        client_id = $ClientId
        scope     = $Scopes
    } -ContentType "application/x-www-form-urlencoded"

    Write-Host ""
    Write-Host "  $($deviceCodeResp.message)" -ForegroundColor Yellow
    Write-Host ""

    $tokenBody = @{
        client_id   = $ClientId
        grant_type  = "urn:ietf:params:oauth:grant-type:device_code"
        device_code = $deviceCodeResp.device_code
    }

    while (-not $accessToken) {
        Start-Sleep -Seconds ([Math]::Max($deviceCodeResp.interval, 5))
        try {
            $tokenResp = Invoke-RestMethod -Uri "$Authority/token" -Method POST `
                -Body $tokenBody -ContentType "application/x-www-form-urlencoded"
            Save-TokenCache $tokenResp
            $accessToken = $tokenResp.access_token
        } catch {
            $errBody = $null
            try { $errBody = $_.ErrorDetails.Message | ConvertFrom-Json } catch {}
            if ($errBody.error -eq "authorization_pending") { continue }
            if ($errBody.error -eq "slow_down") { Start-Sleep -Seconds 5; continue }
            $msg = $errBody.error_description ?? $_.Exception.Message
            Write-ActionableError -Message "Device-code auth flow failed: $msg" `
                -Causes @(
                    "User did not complete the browser sign-in within the time window",
                    "Tenant ID '$TenantId' does not allow this public client app",
                    "Conditional Access blocked device-code flow (admin-restricted)"
                ) `
                -Try @(
                    "Re-run and complete sign-in promptly: pwsh scripts/get-stream-transcripts.ps1",
                    "Pin to your tenant: -TenantId <org_short>fg.onmicrosoft.com",
                    "Ask admin to allow public client device-code flow for your account"
                )
        }
    }
}

$headers = @{
    Authorization = "Bearer $accessToken"
    Accept        = "application/json"
}

Write-Host "✅ Authenticated" -ForegroundColor Green

# ── Helpers ──────────────────────────────────────────────────────────

function Invoke-Graph {
    param(
        [string]$Uri,
        [string]$Method = "GET",
        [object]$Body
    )
    $params = @{
        Uri         = $Uri
        Headers     = $headers
        Method      = $Method
        ContentType = "application/json"
    }
    if ($Body) { $params.Body = ($Body | ConvertTo-Json -Depth 10) }
    Invoke-RestMethod @params
}

function Get-SafeFileName {
    param([string]$Name)
    $invalid = [System.IO.Path]::GetInvalidFileNameChars()
    $safe = $Name
    foreach ($c in $invalid) { $safe = $safe.Replace([string]$c, '_') }
    return $safe
}

# ── Get current user ─────────────────────────────────────────────────

$me = Invoke-Graph "$GraphBase/v1.0/me?`$select=id,displayName,mail,userPrincipalName"
$myId = $me.id
Write-Host "👤 $($me.displayName) ($($me.mail ?? $me.userPrincipalName))" -ForegroundColor Gray

# ── Search for video files ───────────────────────────────────────────

Write-Host "`n🔍 Searching for your video files..." -ForegroundColor Cyan

$videos = [System.Collections.Generic.List[object]]::new()
$seen   = [System.Collections.Generic.HashSet[string]]::new()

function Add-Video {
    param($Item)
    $driveId = $null; $itemId = $null
    try { $driveId = $Item.parentReference.driveId } catch {}
    try { $itemId  = $Item.id } catch {}
    if (-not $driveId -or -not $itemId) { return }

    $key = "$driveId|$itemId"
    if (-not $seen.Add($key)) { return }

    $ext = [System.IO.Path]::GetExtension($Item.name).TrimStart('.').ToLower()
    if ($ext -notin $VideoExtensions) { return }

    $videos.Add(@{
        Name    = $Item.name
        DriveId = $driveId
        ItemId  = $itemId
        WebUrl  = $Item.webUrl
        Created = $Item.createdDateTime
    })
}

# ── Target: <org_short>fg.sharepoint.com/sites/Infrastructure ─────────────

$SiteHost = "<org_short>fg.sharepoint.com"
$SitePath = "/sites/Infrastructure"

Write-Host "  Site: $SiteHost$SitePath" -ForegroundColor Gray

# Resolve site → all drives → search each library root for videos
try {
    $site = Invoke-Graph "$GraphBase/v1.0/sites/${SiteHost}:${SitePath}"
} catch {
    Write-ActionableError -Message "Could not resolve SharePoint site $SiteHost$SitePath — $($_.Exception.Message)" `
        -Causes @(
            "Account has no access to the Infrastructure site",
            "Site path typo (check casing: /sites/Infrastructure)",
            "Site was renamed or archived"
        ) `
        -Try @(
            "Open https://$SiteHost$SitePath in a browser to verify access",
            "Search for the site: Invoke-Graph '$GraphBase/v1.0/sites?search=Infrastructure'",
            "Re-auth with --TenantId <org_short>fg.onmicrosoft.com"
        )
}

Write-Host "  📍 Site ID: $($site.id)" -ForegroundColor DarkGray

$drives = (Invoke-Graph "$GraphBase/v1.0/sites/$($site.id)/drives?`$select=id,name").value
Write-Host "  📚 Found $($drives.Count) document library/libraries" -ForegroundColor DarkGray

foreach ($drive in $drives) {
    Write-Host "  📂 $($drive.name)" -ForegroundColor DarkGray -NoNewline
    $libCount = 0

    # Search the entire library for video files
    foreach ($ext in $VideoExtensions) {
        $nextLink = "$GraphBase/v1.0/drives/$($drive.id)/root/search(q='.$ext')"
        while ($nextLink) {
            try {
                $results = Invoke-Graph $nextLink
                foreach ($item in $results.value) {
                    $before = $videos.Count
                    Add-Video $item
                    if ($videos.Count -gt $before) { $libCount++ }
                }
                $nextLink = $null
                try { $nextLink = $results.'@odata.nextLink' } catch {}
            } catch {
                $nextLink = $null
            }
        }
    }
    Write-Host " → $libCount video(s)" -ForegroundColor $(if ($libCount) { "Green" } else { "DarkGray" })
}

if ($videos.Count -eq 0) {
    Write-Host "⚠️  No video files found for your account." -ForegroundColor Yellow
    exit 0
}

Write-Host "📹 Found $($videos.Count) video(s)" -ForegroundColor Green

# ── Create output directory ──────────────────────────────────────────

if (-not (Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
    Write-Host "📁 Created $OutputDir" -ForegroundColor Gray
}

# ── Download transcripts ─────────────────────────────────────────────

# Stream-on-SharePoint stores transcripts internally via the media API.
# We try multiple endpoints in order:
#   1. Graph beta site-scoped: /beta/sites/{siteId}/drives/…/media/transcriptions
#   2. SharePoint REST v2.1:   https://{host}/_api/v2.1/drives/…/media/transcriptions
#   3. Graph beta drive-scoped: /beta/drives/…/media/transcriptions

$siteId = $site.id

# Get a SharePoint-audience token via refresh grant for SP REST fallback
$spToken = $null
$cachePath = Join-Path $PSScriptRoot ".graph-token-cache.json"
if (Test-Path $cachePath) {
    try {
        $cache = Get-Content $cachePath -Raw | ConvertFrom-Json
        if ($cache.refresh_token) {
            $spResp = Invoke-RestMethod -Uri "$Authority/token" -Method POST -Body @{
                client_id     = $ClientId
                grant_type    = "refresh_token"
                refresh_token = $cache.refresh_token
                scope         = "https://$SiteHost/.default"
            } -ContentType "application/x-www-form-urlencoded"
            $spToken = $spResp.access_token
            Write-Host "🔑 SharePoint token acquired" -ForegroundColor DarkGray
        }
    } catch {
        Write-Host "⚠️  Could not get SharePoint token — SP REST fallback disabled" -ForegroundColor Yellow
    }
}

Write-Host "`n📥 Downloading transcripts...`n" -ForegroundColor Cyan

$downloaded    = 0
$noTranscript  = 0
$errorCount    = 0

# ── Probe the first video to find which endpoint works ───────────────

$probe = $videos[0]
$probeDriveId = $probe.DriveId
$probeItemId  = $probe.ItemId
Write-Host "🔬 Probing endpoints with: $($probe.Name)" -ForegroundColor Cyan

$graphH = @{ Authorization = "Bearer $accessToken"; Accept = "application/json" }
$spH    = if ($spToken) { @{ Authorization = "Bearer $spToken"; Accept = "application/json" } } else { $null }

# ── Phase 1: Dump the full /media property to find transcript info ────

Write-Host "`n📋 Full /media dump for first video:" -ForegroundColor Cyan
try {
    $mediaResp = Invoke-RestMethod -Uri "$GraphBase/beta/drives/$probeDriveId/items/${probeItemId}?`$select=id,name,media" `
        -Headers $graphH -Method GET
    $mediaResp.media | ConvertTo-Json -Depth 10 | Write-Host -ForegroundColor DarkGray
} catch {
    Write-Host "  /media dump failed: $($_.Exception.Message)" -ForegroundColor Red
}

# ── Phase 2: Probe transcript endpoints ──────────────────────────────

$probeEndpoints = @(
    # "transcripts" (not "transcriptions") — the correct Graph beta segment name
    @{ Label = "Graph beta /media/transcripts";          Tag = "transcripts";
       Uri   = "$GraphBase/beta/drives/$probeDriveId/items/$probeItemId/media/transcripts";
       H     = $graphH }
    @{ Label = "SP v2.1 /media/transcripts";             Tag = "transcripts";
       Uri   = "https://$SiteHost/_api/v2.1/drives/$probeDriveId/items/$probeItemId/media/transcripts";
       H     = $spH }
    @{ Label = "Graph beta site /media/transcripts";     Tag = "transcripts";
       Uri   = "$GraphBase/beta/sites/$siteId/drives/$probeDriveId/items/$probeItemId/media/transcripts";
       H     = $graphH }
    # subtitles — sometimes transcripts are stored as subtitles
    @{ Label = "Graph beta /media/subtitles";            Tag = "subtitles";
       Uri   = "$GraphBase/beta/drives/$probeDriveId/items/$probeItemId/media/subtitles";
       H     = $graphH }
    @{ Label = "SP v2.1 /media/subtitles";               Tag = "subtitles";
       Uri   = "https://$SiteHost/_api/v2.1/drives/$probeDriveId/items/$probeItemId/media/subtitles";
       H     = $spH }
    # original "transcriptions" attempts for completeness
    @{ Label = "Graph beta /media/transcriptions";       Tag = "transcriptions";
       Uri   = "$GraphBase/beta/drives/$probeDriveId/items/$probeItemId/media/transcriptions";
       H     = $graphH }
    @{ Label = "SP v2.1 /media/transcriptions";          Tag = "transcriptions";
       Uri   = "https://$SiteHost/_api/v2.1/drives/$probeDriveId/items/$probeItemId/media/transcriptions";
       H     = $spH }
)

$workingEndpoint = $null

foreach ($ep in $probeEndpoints) {
    if (-not $ep.H) {
        Write-Host "  ⏭️  $($ep.Label) — skipped (no token)" -ForegroundColor DarkGray
        continue
    }
    Write-Host "  🔎 $($ep.Label)" -ForegroundColor DarkGray -NoNewline
    try {
        $probeResp = Invoke-WebRequest -Uri $ep.Uri -Headers $ep.H -Method GET -ErrorAction Stop
        $statusCode = $probeResp.StatusCode
        $bodyLen = $probeResp.Content.Length
        $bodyPreview = $probeResp.Content.Substring(0, [Math]::Min(500, $bodyLen))
        Write-Host " → $statusCode ($bodyLen bytes)" -ForegroundColor Green
        Write-Host "     $bodyPreview" -ForegroundColor DarkGray
        # Only accept endpoints that have transcript/subtitle data (value array)
        $check = $null; try { $check = $probeResp.Content | ConvertFrom-Json } catch {}
        if ($check -and $check.value -and $check.value.Count -gt 0) {
            if (-not $workingEndpoint) { $workingEndpoint = $ep }
            Write-Host "     ✅ Found $($check.value.Count) transcript(s)!" -ForegroundColor Green
        }
    } catch {
        $errStatus = $null
        try { $errStatus = $_.Exception.Response.StatusCode.value__ } catch {}
        $errBody = $null
        try { $errBody = $_.ErrorDetails.Message.Substring(0, [Math]::Min(200, $_.ErrorDetails.Message.Length)) } catch {}
        $errBody = $errBody ?? $_.Exception.Message
        Write-Host " → $errStatus $errBody" -ForegroundColor Red
    }
}

Write-Host ""

if (-not $workingEndpoint) {
    Write-ActionableError -Message "No working transcript endpoint found for the discovered videos." `
        -Causes @(
            "None of the videos have an auto-generated transcript yet (transcription is async after upload)",
            "Account lacks media-transcription read scope (need Files.Read.All for transcript bytes)",
            "Microsoft Stream beta endpoint changed (this script uses beta APIs)"
        ) `
        -Try @(
            "Open one video in Stream UI to verify a transcript is visible there first",
            "Re-run with -Verbose to see exact endpoint responses",
            "Check Graph changelog: https://learn.microsoft.com/en-us/graph/changelog"
        )
}

Write-Host "✅ Using: $($workingEndpoint.Label)`n" -ForegroundColor Green

# ── Download transcripts using the working endpoint ──────────────────

# Helper: Convert Stream JSON transcript to VTT format
function Convert-JsonToVtt {
    param([string]$JsonContent)
    $entries = $JsonContent | ConvertFrom-Json
    $sb = [System.Text.StringBuilder]::new()
    [void]$sb.AppendLine("WEBVTT")
    [void]$sb.AppendLine()
    $idx = 0
    foreach ($e in $entries) {
        $startMs  = [long]$e.startTime
        $endMs    = [long]$e.endTime
        $speaker  = $e.speakerName
        $text     = $e.text
        $startTS  = [TimeSpan]::FromMilliseconds($startMs).ToString("hh\:mm\:ss\.fff")
        $endTS    = [TimeSpan]::FromMilliseconds($endMs).ToString("hh\:mm\:ss\.fff")
        [void]$sb.AppendLine("$idx")
        [void]$sb.AppendLine("$startTS --> $endTS")
        if ($speaker) {
            [void]$sb.AppendLine("<v $speaker>$text</v>")
        } else {
            [void]$sb.AppendLine($text)
        }
        [void]$sb.AppendLine()
        $idx++
    }
    return $sb.ToString()
}

# Probe the first video's transcript to find the best download method
$probeVideo = $videos[0]
$probeDlUri = $workingEndpoint.Uri `
    -replace [regex]::Escape($probeDriveId), $probeVideo.DriveId `
    -replace [regex]::Escape($probeItemId),  $probeVideo.ItemId
$probeListResp = Invoke-RestMethod -Uri $probeDlUri -Headers $workingEndpoint.H -Method GET
$probeTx = $probeListResp.value[0]
$probeTxId = $probeTx.id
$probeTempUrl = $null; try { $probeTempUrl = $probeTx.temporaryDownloadUrl } catch {}

Write-Host "`n🔬 Probing download methods for transcript '$($probeTx.displayName)':" -ForegroundColor Cyan

$downloadMethod = $null  # "tempUrl", "contentVtt", "contentRaw"

# Method 1: temporaryDownloadUrl (pre-signed, no auth needed)
if ($probeTempUrl) {
    Write-Host "  🔎 temporaryDownloadUrl" -ForegroundColor DarkGray -NoNewline
    try {
        $dlResp = Invoke-WebRequest -Uri $probeTempUrl -Method GET -ErrorAction Stop
        $preview = ""
        if ($dlResp.Content -is [byte[]]) {
            $preview = [System.Text.Encoding]::UTF8.GetString($dlResp.Content, 0, [Math]::Min(300, $dlResp.Content.Length))
        } else {
            $preview = $dlResp.Content.Substring(0, [Math]::Min(300, $dlResp.Content.Length))
        }
        Write-Host " → $($dlResp.StatusCode) ($($dlResp.Content.Length) bytes)" -ForegroundColor Green
        Write-Host "     $preview" -ForegroundColor DarkGray
        $downloadMethod = "tempUrl"
    } catch {
        $st = $null; try { $st = $_.Exception.Response.StatusCode.value__ } catch {}
        Write-Host " → $st $($_.Exception.Message)" -ForegroundColor Red
    }
}

# Method 2: /{txId}/content?format=vtt (SP token)
Write-Host "  🔎 /{txId}/content?format=vtt" -ForegroundColor DarkGray -NoNewline
try {
    $contentVttUri = "$probeDlUri/$probeTxId/content?format=vtt"
    $dlResp = Invoke-WebRequest -Uri $contentVttUri -Headers $workingEndpoint.H -Method GET -ErrorAction Stop
    $preview = ""
    if ($dlResp.Content -is [byte[]]) {
        $preview = [System.Text.Encoding]::UTF8.GetString($dlResp.Content, 0, [Math]::Min(300, $dlResp.Content.Length))
    } else {
        $preview = $dlResp.Content.Substring(0, [Math]::Min(300, $dlResp.Content.Length))
    }
    Write-Host " → $($dlResp.StatusCode) ($($dlResp.Content.Length) bytes)" -ForegroundColor Green
    Write-Host "     $preview" -ForegroundColor DarkGray
    if (-not $downloadMethod -or $preview -match "^WEBVTT") { $downloadMethod = "contentVtt" }
} catch {
    $st = $null; try { $st = $_.Exception.Response.StatusCode.value__ } catch {}
    $errMsg = $null; try { $errMsg = $_.ErrorDetails.Message.Substring(0, [Math]::Min(200, $_.ErrorDetails.Message.Length)) } catch {}
    Write-Host " → $st $($errMsg ?? $_.Exception.Message)" -ForegroundColor Red
}

# Method 3: /{txId}/content (no format param, SP token)
Write-Host "  🔎 /{txId}/content" -ForegroundColor DarkGray -NoNewline
try {
    $contentUri = "$probeDlUri/$probeTxId/content"
    $dlResp = Invoke-WebRequest -Uri $contentUri -Headers $workingEndpoint.H -Method GET -ErrorAction Stop
    $preview = ""
    if ($dlResp.Content -is [byte[]]) {
        $preview = [System.Text.Encoding]::UTF8.GetString($dlResp.Content, 0, [Math]::Min(300, $dlResp.Content.Length))
    } else {
        $preview = $dlResp.Content.Substring(0, [Math]::Min(300, $dlResp.Content.Length))
    }
    Write-Host " → $($dlResp.StatusCode) ($($dlResp.Content.Length) bytes)" -ForegroundColor Green
    Write-Host "     $preview" -ForegroundColor DarkGray
    if (-not $downloadMethod) { $downloadMethod = "contentRaw" }
} catch {
    $st = $null; try { $st = $_.Exception.Response.StatusCode.value__ } catch {}
    $errMsg = $null; try { $errMsg = $_.ErrorDetails.Message.Substring(0, [Math]::Min(200, $_.ErrorDetails.Message.Length)) } catch {}
    Write-Host " → $st $($errMsg ?? $_.Exception.Message)" -ForegroundColor Red
}

if (-not $downloadMethod) {
    Write-ActionableError -Message "No transcript download method succeeded against the discovered endpoint." `
        -Causes @(
            "Endpoint returned 401/403 — token lacks the right scope for transcript content",
            "Endpoint returned 404 — the test video has no transcript content (may be in progress)",
            "Beta API contract changed (download URL format or auth scheme)"
        ) `
        -Try @(
            "Re-run with -Verbose to capture each tried method's exact response",
            "Inspect headers: Invoke-WebRequest with -SkipHttpErrorCheck on the endpoint URL",
            "Check Graph changelog and beta docs"
        )
}

Write-Host "`n✅ Download method: $downloadMethod`n" -ForegroundColor Green

# ── Main download loop ───────────────────────────────────────────────

foreach ($video in $videos) {
    $baseName = [System.IO.Path]::GetFileNameWithoutExtension($video.Name)
    $safeName = Get-SafeFileName $baseName
    Write-Host "  🎬 $baseName" -ForegroundColor White -NoNewline

    $found = $false

    # Build the transcript list URI for this video
    $listUri = $workingEndpoint.Uri `
        -replace [regex]::Escape($probeDriveId), $video.DriveId `
        -replace [regex]::Escape($probeItemId),  $video.ItemId

    try {
        $listResp = Invoke-RestMethod -Uri $listUri -Headers $workingEndpoint.H -Method GET -ErrorAction Stop
        if (-not $listResp.value -or $listResp.value.Count -eq 0) {
            Write-Host " — no transcript" -ForegroundColor DarkGray
            $noTranscript++; continue
        }

        foreach ($tx in $listResp.value) {
            $txId  = $tx.id
            $lang  = $null; try { $lang = $tx.languageTag } catch {}
            $suffix = if ($listResp.value.Count -gt 1) { ".$(${lang} ?? 'en')" } else { "" }
            $outFile = "$safeName$suffix.vtt"
            $outPath = Join-Path $OutputDir $outFile

            $rawContent = $null

            switch ($downloadMethod) {
                "tempUrl" {
                    $tempUrl = $null; try { $tempUrl = $tx.temporaryDownloadUrl } catch {}
                    if ($tempUrl) {
                        $dlResp = Invoke-WebRequest -Uri $tempUrl -Method GET -ErrorAction Stop
                        $rawContent = if ($dlResp.Content -is [byte[]]) {
                            [System.Text.Encoding]::UTF8.GetString($dlResp.Content)
                        } else { $dlResp.Content }
                    }
                }
                "contentVtt" {
                    $uri = "$listUri/$txId/content?format=vtt"
                    $dlResp = Invoke-WebRequest -Uri $uri -Headers $workingEndpoint.H -Method GET -ErrorAction Stop
                    $rawContent = if ($dlResp.Content -is [byte[]]) {
                        [System.Text.Encoding]::UTF8.GetString($dlResp.Content)
                    } else { $dlResp.Content }
                }
                "contentRaw" {
                    $uri = "$listUri/$txId/content"
                    $dlResp = Invoke-WebRequest -Uri $uri -Headers $workingEndpoint.H -Method GET -ErrorAction Stop
                    $rawContent = if ($dlResp.Content -is [byte[]]) {
                        [System.Text.Encoding]::UTF8.GetString($dlResp.Content)
                    } else { $dlResp.Content }
                }
            }

            if ($rawContent) {
                # Strip UTF-8 BOM if present
                $rawContent = $rawContent -replace "^\xEF\xBB\xBF", "" -replace "^\uFEFF", ""
                # If already VTT, save directly; otherwise convert from JSON
                if ($rawContent -match "^\s*WEBVTT") {
                    $vttContent = $rawContent
                } else {
                    # Assume JSON transcript array
                    try {
                        $vttContent = Convert-JsonToVtt $rawContent
                    } catch {
                        Write-Host " ❌ JSON→VTT conversion failed" -ForegroundColor Red
                        $errorCount++; continue
                    }
                }
                Set-Content -Path $outPath -Value $vttContent -Encoding UTF8 -NoNewline
                Write-Host " ✓ $outFile" -ForegroundColor Green
                $downloaded++; $found = $true
            }
        }
    } catch {
        $statusCode = $null
        try { $statusCode = $_.Exception.Response.StatusCode.value__ } catch {}
        if ($statusCode -eq 404) {
            Write-Host " — no transcript" -ForegroundColor DarkGray
        } else {
            Write-Host " ❌ $statusCode $($_.Exception.Message)" -ForegroundColor Red
            $errorCount++
        }
    }

    if (-not $found) { $noTranscript++ }
}

# ── Summary ──────────────────────────────────────────────────────────

Write-Host "`n──────────────────────────────────" -ForegroundColor DarkGray
Write-Host "📊 Videos found:           $($videos.Count)"
Write-Host "   Transcripts downloaded: $downloaded" -ForegroundColor Green
Write-Host "   No transcript:         $noTranscript" -ForegroundColor DarkGray
if ($errorCount -gt 0) {
    Write-Host "   Errors:                $errorCount" -ForegroundColor Red
}
Write-Host "   Output:                $(Resolve-Path $OutputDir -ErrorAction SilentlyContinue ?? $OutputDir)"
