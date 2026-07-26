#!/usr/bin/env pwsh

# Script to copy files from SMB source to violet media directories
param(
    [Parameter(Mandatory=$false)]
    [string]$SourcePath = "/media/acestus/INFUSE",
    
    [Parameter(Mandatory=$false)]
    [string]$DestinationHost = "violet",
    
    [Parameter(Mandatory=$false)]
    [string]$DestinationPath = "/media/violet/movies01",
    
    [Parameter(Mandatory=$false)]
    [switch]$DryRun,
    
    [Parameter(Mandatory=$false)]
    [switch]$VerboseOutput,
    
    [Parameter(Mandatory=$false)]
    [switch]$DeleteExtra
)

Write-Host "Copy to Violet Script" -ForegroundColor Green
Write-Host "===================" -ForegroundColor Green
Write-Host ""

# Display configuration
Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Source: $SourcePath"
Write-Host "  Destination Host: $DestinationHost"
Write-Host "  Destination Path: $DestinationPath"
Write-Host "  Dry Run: $DryRun"
Write-Host "  Delete Extra Files: $DeleteExtra"
Write-Host ""

# Function to control Samba service on violet
function Manage-SambaService {
    param(
        [string]$Action,  # "stop" or "start"
        [string]$HostName
    )
    
    $actionText = if ($Action -eq "stop") { "Stopping" } else { "Starting" }
    Write-Host "$actionText Samba service on $HostName..." -ForegroundColor Cyan
    
    try {
        $result = ssh $HostName "sudo systemctl $Action smbd"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ Samba service ${Action}ed successfully" -ForegroundColor Green
        } else {
            Write-Host "  ⚠ Warning: Failed to $Action Samba service (exit code: $LASTEXITCODE)" -ForegroundColor Yellow
            Write-Host "  This may not prevent the file transfer from working" -ForegroundColor Gray
        }
    }
    catch {
        Write-Host "  ⚠ Warning: Error managing Samba service: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-Host "  Continuing with file transfer anyway..." -ForegroundColor Gray
    }
    Write-Host ""
}

# Function to execute rsync command
function Invoke-RsyncCopy {
    param(
        [string]$Source,
        [string]$Destination,
        [string]$Category,
        [switch]$DryRun,
        [switch]$VerboseOutput,
        [switch]$DeleteExtra
    )
    
    Write-Host "Copying $Category files..." -ForegroundColor Cyan
    
    # Build rsync command
    $rsyncArgs = @(
        "-rlptvh"       # recursive, links, permissions, times, verbose, human-readable (no -o,-g for ownership)
        "--progress"    # show progress
        "--partial"     # keep partially transferred files
        "--update"      # skip files that are newer on destination
        "--ignore-existing"  # skip updating files that exist on destination
        "--no-owner"    # don't preserve owner
        "--no-group"    # don't preserve group
        "--exclude='.DS_Store'"     # exclude Mac metadata
        "--exclude='Thumbs.db'"     # exclude Windows thumbnails
        "--exclude='desktop.ini'"   # exclude Windows folder settings
        "--exclude='**/*.parts'"    # exclude partial download files
        "--exclude='**/.*parts'"    # exclude hidden partial files
        "--exclude='**/*.tmp'"      # exclude temporary files
        "--exclude='**/*.temp'"     # exclude temporary files
    )
    
    if ($DeleteExtra) {
        $rsyncArgs += "--delete"
        $rsyncArgs += "--delete-excluded"
        Write-Host "  DELETE MODE - Extra files on destination will be removed" -ForegroundColor Red
    }
    
    if ($DryRun) {
        $rsyncArgs += "--dry-run"
        Write-Host "  DRY RUN MODE - No files will be copied" -ForegroundColor Yellow
    }
    
    if ($VerboseOutput) {
        $rsyncArgs += "-v"
    }
    
    # Add source and destination
    $rsyncArgs += $Source
    $rsyncArgs += "${DestinationHost}:$Destination"
    
    # Execute rsync
    Write-Host "  Command: rsync $($rsyncArgs -join ' ')" -ForegroundColor Gray
    Write-Host ""
    
    try {
        & rsync $rsyncArgs
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ✓ $Category copy completed successfully" -ForegroundColor Green
        } elseif ($LASTEXITCODE -eq 23) {
            Write-Host "  ✓ $Category copy completed with minor warnings (exit code: 23)" -ForegroundColor Yellow
            Write-Host "    Files were transferred successfully, but some metadata may not have been preserved" -ForegroundColor Gray
        } else {
            Write-Host "  ✗ $Category copy failed with exit code: $LASTEXITCODE" -ForegroundColor Red
        }
    }
    catch {
        Write-Host "  ✗ Error executing rsync: $($_.Exception.Message)" -ForegroundColor Red
    }
    
    Write-Host ""
}

# Check if rsync is available
if (-not (Get-Command rsync -ErrorAction SilentlyContinue)) {
    Write-Host "Error: rsync is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install rsync to use this script" -ForegroundColor Red
    exit 1
}

# Check SSH connectivity to destination
Write-Host "Testing SSH connectivity to $DestinationHost..." -ForegroundColor Cyan
try {
    $sshTest = ssh -o ConnectTimeout=10 -o BatchMode=yes $DestinationHost "echo 'SSH connection successful'"
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ SSH connection to $DestinationHost successful" -ForegroundColor Green
    } else {
        Write-Host "  ✗ SSH connection to $DestinationHost failed" -ForegroundColor Red
        Write-Host "  Please ensure SSH key authentication is set up" -ForegroundColor Yellow
        exit 1
    }
}
catch {
    Write-Host "  ✗ SSH test failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
Write-Host ""

# Mount SMB source if needed (this depends on your local setup)
Write-Host "Note: Ensure SMB source '$SourcePath' is accessible" -ForegroundColor Yellow
Write-Host "Mount commands (if needed):" -ForegroundColor Yellow
Write-Host 'ssh violet "sudo umount /media/violet/movies01"'
Write-Host 'ssh violet "sudo mount -o rw,uid=1000,gid=1000,fmask=0022,dmask=0022 /dev/sda1 /media/violet/movies01"'
Write-Host 'ssh violet "mount | grep /media/violet/movies01"'
Write-Host 'ssh violet "ls -la /media/violet/movies01/ | head -5"'


# Stop Samba service before transfer
Manage-SambaService -Action "stop" -HostName $DestinationHost

# Check destination accessibility
Write-Host "Checking destination accessibility..." -ForegroundColor Cyan
try {
    # Check if destination directories exist and are accessible
    $adultCheck = ssh $DestinationHost "test -d '$DestinationPath/adult' && echo 'exists' || echo 'missing'"
    $infuseCheck = ssh $DestinationHost "test -d '$DestinationPath/infuse01' && echo 'exists' || echo 'missing'"
    
    Write-Host "  Adult directory: $adultCheck" -ForegroundColor Gray
    Write-Host "  Infuse01 directory: $infuseCheck" -ForegroundColor Gray
    
    # Check filesystem mount status
    $mountCheck = ssh $DestinationHost "mount | grep '$DestinationPath'"
    Write-Host "  Current mount: $mountCheck" -ForegroundColor Gray
    
    # Check if filesystem appears to be read-only
    if ($mountCheck -match '\(ro[,)]') {
        Write-Host "  ⚠ Warning: Filesystem appears to be mounted read-only" -ForegroundColor Yellow
        $remountChoice = Read-Host "Would you like to remount as read-write? (y/N)"
        if ($remountChoice -eq 'y' -or $remountChoice -eq 'Y') {
            $remountResult = ssh $DestinationHost "sudo mount -o remount,rw '$DestinationPath'"
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  ✓ Filesystem remounted as read-write" -ForegroundColor Green
            } else {
                Write-Host "  ✗ Failed to remount filesystem" -ForegroundColor Red
            }
        }
    } elseif ($mountCheck -match 'type exfat') {
        Write-Host "  ✓ Filesystem appears to be writable" -ForegroundColor Green
        Write-Host "  📁 Detected exfat filesystem - using rsync options optimized for exfat" -ForegroundColor Cyan
        
        # Check if mount has proper ownership settings
        if ($mountCheck -notmatch 'uid=' -and $mountCheck -notmatch 'gid=') {
            Write-Host "  ⚠ Notice: exfat mount doesn't specify uid/gid - files will be owned by root" -ForegroundColor Yellow
            Write-Host "    Consider remounting with: sudo mount -o remount,rw,uid=1000,gid=1000,fmask=0022,dmask=0022 '$DestinationPath'" -ForegroundColor Gray
        }
    } else {
        Write-Host "  ✓ Filesystem appears to be writable" -ForegroundColor Green
    }
    
} catch {
    Write-Host "  ⚠ Warning: Error checking destination: $($_.Exception.Message)" -ForegroundColor Yellow
}
Write-Host ""

# Copy all files from movies-backup to movies01
Write-Host "Copying only adult and infuse01 folders (excluding trash)..." -ForegroundColor Magenta

# Copy adult folder
Write-Host "Copying adult movies..." -ForegroundColor Cyan
Invoke-RsyncCopy -Source "$SourcePath/adult/" -Destination "$DestinationPath/adult/" -Category "Adult Movies" -DryRun:$DryRun -VerboseOutput:$VerboseOutput -DeleteExtra:$DeleteExtra

# Copy infuse01 folder
Write-Host "Copying family movies..." -ForegroundColor Cyan
Invoke-RsyncCopy -Source "$SourcePath/infuse01/" -Destination "$DestinationPath/infuse01/" -Category "Family Movies" -DryRun:$DryRun -VerboseOutput:$VerboseOutput -DeleteExtra:$DeleteExtra

# Restart Samba service after transfer
Manage-SambaService -Action "start" -HostName $DestinationHost

Write-Host "Script completed." -ForegroundColor Green