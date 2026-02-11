# Windows PowerShell Daily Scraping Script
# Usage: .\scripts\daily_scraping.ps1 [date]
# Example: .\scripts\daily_scraping.ps1 20250204

param(
    [string]$TargetDate = (Get-Date -Format "yyyyMMdd"),
    [switch]$TestMode = $false,
    [switch]$DryRun = $false
)

# Move to project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

# Setup logging
$LogDir = "logs"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = "$LogDir\daily_scraping_$Timestamp.log"

if (!(Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force
}

function Write-Log {
    param([string]$Message)
    $Time = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $LogEntry = "$Time : $Message"
    Write-Host $LogEntry
    Add-Content -Path $LogFile -Value $LogEntry
}

Write-Log "=== Daily Scraping Started ==="
Write-Log "Target Date: $TargetDate"

if ($TestMode) { Write-Log "Test Mode: Enabled" }
if ($DryRun) { Write-Log "Dry Run Mode: Enabled" }

# Define race IDs (Tokyo track only for simplicity)
$RaceIds = @(
    "${TargetDate}0511",
    "${TargetDate}0512",
    "${TargetDate}0513"
)

if ($TestMode) {
    Write-Log "Test Mode: Processing limited races"
} else {
    # Add more races for production
    $RaceIds += @(
        "${TargetDate}0514",
        "${TargetDate}0515",
        "${TargetDate}0516",
        "${TargetDate}0517",
        "${TargetDate}0518",
        "${TargetDate}0519",
        "${TargetDate}0520",
        "${TargetDate}0521",
        "${TargetDate}0522"
    )
}

Write-Log "Total races to process: $($RaceIds.Count)"

# Counters
$SuccessCount = 0
$FailureCount = 0
$StartTime = Get-Date

# Process each race
for ($i = 0; $i -lt $RaceIds.Count; $i++) {
    $RaceId = $RaceIds[$i]
    $Progress = [math]::Round(($i + 1) / $RaceIds.Count * 100, 1)
    
    Write-Log "Processing race: $RaceId ($($i + 1)/$($RaceIds.Count) - $Progress percent)"
    
    if ($DryRun) {
        Write-Log "Dry Run: python src/keibabook/main.py --race-id $RaceId --mode scrape_and_parse"
        $SuccessCount++
        Start-Sleep -Seconds 2
        continue
    }
    
    # Execute main processing
    try {
        $Process = Start-Process -FilePath "python" -ArgumentList "src/keibabook/main.py --race-id $RaceId --mode scrape_and_parse" -Wait -PassThru -NoNewWindow
        
        if ($Process.ExitCode -eq 0) {
            Write-Log "Success: Race $RaceId completed"
            $SuccessCount++
        } else {
            Write-Log "Error: Race $RaceId failed with exit code $($Process.ExitCode)"
            $FailureCount++
        }
    }
    catch {
        Write-Log "Exception: Race $RaceId failed with error: $($_.Exception.Message)"
        $FailureCount++
    }
    
    # Wait between requests (except for last race)
    if ($i -lt ($RaceIds.Count - 1)) {
        $WaitTime = if ($TestMode) { 5 } else { 30 }
        Write-Log "Waiting $WaitTime seconds..."
        Start-Sleep -Seconds $WaitTime
    }
}

# Calculate duration
$EndTime = Get-Date
$Duration = $EndTime - $StartTime
$DurationMinutes = [math]::Round($Duration.TotalMinutes, 1)

# Results summary
Write-Log "=== Results Summary ==="
Write-Log "Total races: $($RaceIds.Count)"
Write-Log "Success: $SuccessCount"
Write-Log "Failed: $FailureCount"

$SuccessRate = if ($RaceIds.Count -gt 0) { [math]::Round($SuccessCount * 100 / $RaceIds.Count, 1) } else { 0 }
Write-Log "Success rate: $SuccessRate percent"
Write-Log "Processing time: $DurationMinutes minutes"

# Check generated files
Write-Log "=== Generated Files ==="
if ($SuccessCount -gt 0) {
    $Pattern = "seiseki_${TargetDate}*.json"
    $DataFiles = Get-ChildItem -Path "data\keibabook\seiseki\" -Filter $Pattern -ErrorAction SilentlyContinue
    
    if ($DataFiles) {
        foreach ($File in $DataFiles) {
            $SizeKB = [math]::Round($File.Length / 1KB, 1)
            Write-Log "  $($File.Name) ($SizeKB KB)"
        }
        Write-Log "Total files: $($DataFiles.Count)"
    } else {
        Write-Log "No data files found for date $TargetDate"
    }
} else {
    Write-Log "No files generated"
}

# Final status
if ($FailureCount -gt 0) {
    Write-Log "Warning: $FailureCount out of $($RaceIds.Count) races failed"
    Write-Log "Log file: $LogFile"
    exit 1
} else {
    Write-Log "Success: All races processed successfully"
    Write-Log "Log file: $LogFile"
    exit 0
} 