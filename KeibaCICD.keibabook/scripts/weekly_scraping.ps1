# Windows PowerShell Weekly Scraping Script
# Usage: .\scripts\weekly_scraping.ps1 [start_date] [end_date]
# Example: .\scripts\weekly_scraping.ps1 20250201 20250207

param(
    [string]$StartDate = "",
    [string]$EndDate = "",
    [switch]$TestMode = $false,
    [switch]$DryRun = $false,
    [switch]$WeekendsOnly = $true
)

# Move to project root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

# Setup logging
$LogDir = "logs"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = "$LogDir\weekly_scraping_$Timestamp.log"

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

function Get-DateRange {
    param(
        [string]$Start,
        [string]$End
    )
    
    if ([string]::IsNullOrEmpty($Start)) {
        # Default: Last Sunday
        $LastSunday = (Get-Date).AddDays(-(Get-Date).DayOfWeek.value__)
        $Start = $LastSunday.ToString("yyyyMMdd")
    }
    
    if ([string]::IsNullOrEmpty($End)) {
        # Default: Next Saturday
        $NextSaturday = (Get-Date).AddDays(6 - (Get-Date).DayOfWeek.value__)
        $End = $NextSaturday.ToString("yyyyMMdd")
    }
    
    return @($Start, $End)
}

function Get-ProcessDates {
    param(
        [string]$StartDate,
        [string]$EndDate,
        [bool]$WeekendsOnly
    )
    
    $ProcessDates = @()
    $CurrentDate = [DateTime]::ParseExact($StartDate, "yyyyMMdd", $null)
    $EndDateTime = [DateTime]::ParseExact($EndDate, "yyyyMMdd", $null)
    
    while ($CurrentDate -le $EndDateTime) {
        if ($WeekendsOnly) {
            # Saturday (6) or Sunday (0)
            if ($CurrentDate.DayOfWeek -eq [DayOfWeek]::Saturday -or $CurrentDate.DayOfWeek -eq [DayOfWeek]::Sunday) {
                $ProcessDates += $CurrentDate.ToString("yyyyMMdd")
            }
        } else {
            $ProcessDates += $CurrentDate.ToString("yyyyMMdd")
        }
        $CurrentDate = $CurrentDate.AddDays(1)
    }
    
    return $ProcessDates
}

Write-Log "=== Weekly Racing Data Scraping Started ==="

# Determine date range
$DateRange = Get-DateRange -Start $StartDate -End $EndDate
$ProcessStartDate = $DateRange[0]
$ProcessEndDate = $DateRange[1]

Write-Log "Processing Period: $ProcessStartDate to $ProcessEndDate"

if ($TestMode) { Write-Log "Test Mode: Enabled" }
if ($DryRun) { Write-Log "Dry Run Mode: Enabled" }
if ($WeekendsOnly) { Write-Log "Weekends Only: Enabled" }

# Major racecourse codes
# 01:Sapporo, 02:Hakodate, 03:Fukushima, 04:Niigata, 05:Tokyo, 06:Nakayama
# 07:Chukyo, 08:Kyoto, 09:Hanshin, 10:Kokura
$RaceCourses = @(
    "05",  # Tokyo
    "06",  # Nakayama
    "09",  # Hanshin
    "08",  # Kyoto
    "07",  # Chukyo
    "10"   # Kokura
)

if ($TestMode) {
    # Limit to major courses for testing
    $RaceCourses = @("05", "06")  # Tokyo and Nakayama only
    Write-Log "Test Mode: Limited to Tokyo and Nakayama"
}

# Get processing dates
$ProcessDates = Get-ProcessDates -StartDate $ProcessStartDate -EndDate $ProcessEndDate -WeekendsOnly $WeekendsOnly
Write-Log "Processing Dates: $($ProcessDates -join ', ')"
Write-Log "Race Courses: $($RaceCourses -join ', ')"

# Counters
$TotalSuccess = 0
$TotalFailure = 0
$TotalRaces = 0
$StartTime = Get-Date

# Process each date
foreach ($ProcessDate in $ProcessDates) {
    Write-Log "=== Processing Date: $ProcessDate ==="
    
    $DaySuccess = 0
    $DayFailure = 0
    $DayRaces = 0
    
    # Process each racecourse
    foreach ($Venue in $RaceCourses) {
        Write-Log "Processing Racecourse: $Venue on $ProcessDate"
        
        # Process each race (1R-12R)
        $RaceNumbers = if ($TestMode) { 11..13 } else { 11..22 }  # 11-22 = 1R-12R
        
        foreach ($RaceNum in $RaceNumbers) {
            $RaceId = "${ProcessDate}${Venue}${RaceNum}"
            
            Write-Log "Processing Race: $RaceId"
            $DayRaces++
            $TotalRaces++
            
            if ($DryRun) {
                Write-Log "Dry Run: python src/keibabook/main.py --race-id $RaceId --mode scrape_and_parse"
                $DaySuccess++
                $TotalSuccess++
                Start-Sleep -Seconds 1
                continue
            }
            
            # Execute main processing with timeout
            try {
                $Process = Start-Process -FilePath "python" -ArgumentList "src/keibabook/main.py --race-id $RaceId --mode scrape_and_parse" -Wait -PassThru -NoNewWindow
                
                if ($Process.ExitCode -eq 0) {
                    Write-Log "✅ Race $RaceId completed successfully"
                    $DaySuccess++
                    $TotalSuccess++
                } else {
                    Write-Log "❌ Race $RaceId failed with exit code $($Process.ExitCode)"
                    $DayFailure++
                    $TotalFailure++
                }
            }
            catch {
                Write-Log "❌ Race $RaceId failed with exception: $($_.Exception.Message)"
                $DayFailure++
                $TotalFailure++
            }
            
            # Wait between races (load reduction)
            if ($RaceNum -lt $RaceNumbers[-1] -or $Venue -ne $RaceCourses[-1]) {
                $WaitTime = if ($TestMode) { 3 } else { 15 }
                Start-Sleep -Seconds $WaitTime
            }
        }
        
        # Wait between racecourses
        if ($Venue -ne $RaceCourses[-1]) {
            $VenueWaitTime = if ($TestMode) { 5 } else { 60 }
            Write-Log "Racecourse $Venue completed. Waiting $VenueWaitTime seconds..."
            Start-Sleep -Seconds $VenueWaitTime
        }
    }
    
    # Daily summary
    Write-Log "=== Daily Summary for $ProcessDate ==="
    Write-Log "Total Races: $DayRaces"
    Write-Log "Success: $DaySuccess"
    Write-Log "Failed: $DayFailure"
    
    $DaySuccessRate = if ($DayRaces -gt 0) { [math]::Round($DaySuccess * 100 / $DayRaces, 1) } else { 0 }
    Write-Log "Success Rate: $DaySuccessRate%"
    
    # Wait between dates
    if ($ProcessDate -ne $ProcessDates[-1]) {
        $DateWaitTime = if ($TestMode) { 10 } else { 120 }
        Write-Log "Waiting $DateWaitTime seconds before next date..."
        Start-Sleep -Seconds $DateWaitTime
    }
}

# Calculate total duration
$EndTime = Get-Date
$Duration = $EndTime - $StartTime
$DurationMinutes = [math]::Round($Duration.TotalMinutes, 1)

# Weekly summary
Write-Log "=== Weekly Processing Summary ==="
Write-Log "Processing Period: $ProcessStartDate - $ProcessEndDate"
Write-Log "Total Races: $TotalRaces"
Write-Log "Success: $TotalSuccess"
Write-Log "Failed: $TotalFailure"

$OverallSuccessRate = if ($TotalRaces -gt 0) { [math]::Round($TotalSuccess * 100 / $TotalRaces, 1) } else { 0 }
Write-Log "Overall Success Rate: $OverallSuccessRate%"
Write-Log "Total Processing Time: $DurationMinutes minutes"

# Generated files statistics
Write-Log "=== Generated Files Statistics ==="
foreach ($ProcessDate in $ProcessDates) {
    $Pattern = "seiseki_${ProcessDate}*.json"
    $DateFiles = Get-ChildItem -Path "data\keibabook\seiseki\" -Filter $Pattern -ErrorAction SilentlyContinue
    $FileCount = if ($DateFiles) { $DateFiles.Count } else { 0 }
    Write-Log "$ProcessDate : $FileCount files"
}

# Total data files
$AllDataFiles = Get-ChildItem -Path "data\keibabook\seiseki\" -Filter "seiseki_*.json" -ErrorAction SilentlyContinue
$TotalFiles = if ($AllDataFiles) { $AllDataFiles.Count } else { 0 }
Write-Log "Total Data Files: $TotalFiles"

# Recent files list (max 10)
Write-Log "=== Recent Generated Files (Max 10) ==="
if ($AllDataFiles) {
    $RecentFiles = $AllDataFiles | Sort-Object LastWriteTime -Descending | Select-Object -First 10
    foreach ($File in $RecentFiles) {
        $SizeKB = [math]::Round($File.Length / 1KB, 1)
        $LastModified = $File.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss")
        Write-Log "  $($File.Name) ($LastModified, $SizeKB KB)"
    }
} else {
    Write-Log "No data files found"
}

# Performance statistics
if ($TotalSuccess -gt 0) {
    $AvgTimePerRace = $Duration.TotalMinutes / $TotalSuccess
    Write-Log "=== Performance Statistics ==="
    Write-Log "Average time per race: $([math]::Round($AvgTimePerRace, 2)) minutes"
    
    if ($TotalRaces -gt 0) {
        $EstimatedFullWeekTime = ($TotalRaces * $AvgTimePerRace) / $TotalRaces * 144  # Estimated for all courses/races
        Write-Log "Estimated full week processing time: $([math]::Round($EstimatedFullWeekTime, 1)) minutes"
    }
}

# Error analysis and final status
if ($TotalFailure -gt 0) {
    $ErrorRate = [math]::Round($TotalFailure * 100 / $TotalRaces, 1)
    Write-Log "⚠️  Some races failed (Error Rate: $ErrorRate%)"
    
    if ($ErrorRate -gt 50) {
        Write-Log "🚨 Error rate exceeds 50% ($ErrorRate%). Please check system status"
    }
    
    Write-Log "=== Error Analysis ==="
    Write-Log "For detailed error logs, check: $LogFile"
    Write-Log "Search for errors with: Select-String '❌|ERROR|Failed' $LogFile"
    
    exit 1
} else {
    Write-Log "✅ All races processed successfully"
    Write-Log "Log file saved: $LogFile"
    
    # Success post-processing suggestions
    Write-Log "=== Suggested Next Steps ==="
    Write-Log "1. Run data analysis: python tools\data_analyzer.py --date-start $($ProcessDates[0].Substring(0,4))-$($ProcessDates[0].Substring(4,2))-$($ProcessDates[0].Substring(6,2))"
    Write-Log "2. Generate weekly report"
    Write-Log "3. Backup data files if needed"
    
    exit 0
} 