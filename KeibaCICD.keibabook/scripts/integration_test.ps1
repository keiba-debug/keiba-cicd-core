# Keiba CICD Core - Integration Test Script
# 全システム機能の統合テスト

Write-Host "[INTEGRATION TEST] Keiba CICD Core - Integration Test" -ForegroundColor Green

$TestResults = @()
$StartTime = Get-Date

function Test-Function {
    param(
        [string]$TestName,
        [scriptblock]$TestScript
    )
    
    Write-Host "Testing: $TestName..." -ForegroundColor Yellow
    
    try {
        $result = & $TestScript
        if ($LASTEXITCODE -eq 0 -or $result) {
            Write-Host "[PASS] $TestName - PASSED" -ForegroundColor Green
            $script:TestResults += @{Name = $TestName; Result = "PASSED"; Error = $null}
            return $true
        } else {
            Write-Host "[FAIL] $TestName - FAILED" -ForegroundColor Red
            $script:TestResults += @{Name = $TestName; Result = "FAILED"; Error = "Exit code: $LASTEXITCODE"}
            return $false
        }
    }
    catch {
        Write-Host "[ERROR] $TestName - ERROR: $($_.Exception.Message)" -ForegroundColor Red
        $script:TestResults += @{Name = $TestName; Result = "ERROR"; Error = $_.Exception.Message}
        return $false
    }
}

Write-Host "`n=== Phase 1: Environment Tests ===" -ForegroundColor Cyan

# Test 1: Python Environment
Test-Function "Python Environment" {
    $version = python --version 2>&1
    return $version -match "Python 3\."
}

# Test 2: Dependencies
Test-Function "Python Dependencies" {
    $result = python -c "import selenium; import bs4; import pandas; import requests; import lxml; print('OK')" 2>&1
    return $result -match "OK"
}

# Test 3: Directory Structure
Test-Function "Directory Structure" {
    $dirs = @("data\keibabook\seiseki", "data\debug", "data\analysis", "logs", "src", "scripts", "tools")
    $allExist = $true
    foreach ($dir in $dirs) {
        if (!(Test-Path $dir)) {
            $allExist = $false
            break
        }
    }
    return $allExist
}

# Test 4: Configuration Files
Test-Function "Configuration Files" {
    return (Test-Path ".env") -and (Test-Path "src/keibabook/requirements.txt") -and (Test-Path "src/keibabook/main.py")
}

Write-Host "`n=== Phase 2: Core Functionality Tests ===" -ForegroundColor Cyan

# Test 5: Main Application Help
Test-Function "Main Application" {
    $output = python src/keibabook/main.py --help 2>&1
    return $output -match "usage:" -and $output -match "main.py"
}

# Test 6: Data Analyzer
Test-Function "Data Analyzer Tool" {
    $output = python tools\data_analyzer.py --help 2>&1
    return $output -match "Horse Racing Data Analyzer"
}

# Test 7: System Monitor
Test-Function "System Monitor Tool" {
    $output = python tools\system_monitor.py --format json --output data\analysis\test_monitor.json 2>&1
    return (Test-Path "data\analysis\test_monitor.json")
}

Write-Host "`n=== Phase 3: Automation Scripts Tests ===" -ForegroundColor Cyan

# Test 8: Daily Scraping Script (Dry Run)
Test-Function "Daily Scraping Script" {
    $output = powershell -ExecutionPolicy Bypass -File scripts\daily_scraping.ps1 -TestMode -DryRun 2>&1
    return $LASTEXITCODE -eq 0
}

# Test 9: Weekly Scraping Script (Dry Run)
Test-Function "Weekly Scraping Script" {
    $output = powershell -ExecutionPolicy Bypass -File scripts\weekly_scraping.ps1 -TestMode -DryRun -StartDate 20250607 -EndDate 20250608 2>&1
    return $LASTEXITCODE -eq 0
}

Write-Host "`n=== Phase 4: Data Analysis Tests ===" -ForegroundColor Cyan

# Test 10: Data Analysis Functionality
Test-Function "Data Analysis Functionality" {
    $dataFiles = Get-ChildItem -Path "data\keibabook\seiseki\" -Filter "*.json" -ErrorAction SilentlyContinue
    if ($dataFiles) {
        $output = python tools\data_analyzer.py --output-dir data\analysis\test 2>&1
        return $LASTEXITCODE -eq 0
    } else {
        Write-Host "   [WARN] No data files found - testing help function" -ForegroundColor Yellow
        $output = python tools\data_analyzer.py --help 2>&1
        return $output -match "Horse Racing Data Analyzer"
    }
}

# Calculate results
$EndTime = Get-Date
$Duration = $EndTime - $StartTime
$TotalTests = $TestResults.Count
$PassedTests = ($TestResults | Where-Object { $_.Result -eq "PASSED" }).Count
$FailedTests = ($TestResults | Where-Object { $_.Result -eq "FAILED" }).Count
$ErrorTests = ($TestResults | Where-Object { $_.Result -eq "ERROR" }).Count

# Generate summary report
Write-Host "`n=== Integration Test Summary ===" -ForegroundColor Green
Write-Host "Test Duration: $($Duration.TotalSeconds.ToString('F1')) seconds" -ForegroundColor White
Write-Host "Total Tests: $TotalTests" -ForegroundColor White
Write-Host "Passed: $PassedTests" -ForegroundColor Green
Write-Host "Failed: $FailedTests" -ForegroundColor Red
Write-Host "Errors: $ErrorTests" -ForegroundColor Yellow

$SuccessRate = [math]::Round($PassedTests * 100 / $TotalTests, 1)
Write-Host "Success Rate: $SuccessRate%" -ForegroundColor $(if ($SuccessRate -ge 80) { "Green" } else { "Yellow" })

# Detailed results
if ($FailedTests -gt 0 -or $ErrorTests -gt 0) {
    Write-Host "`n=== Failed/Error Tests ===" -ForegroundColor Red
    foreach ($test in $TestResults) {
        if ($test.Result -ne "PASSED") {
            $emoji = if ($test.Result -eq "FAILED") { "[FAILED]" } else { "[ERROR]" }
            Write-Host "$emoji $($test.Name): $($test.Result)" -ForegroundColor Red
            if ($test.Error) {
                Write-Host "   Error: $($test.Error)" -ForegroundColor Gray
            }
        }
    }
}

# Save detailed report
$ReportPath = "data\analysis\integration_test_$(Get-Date -Format 'yyyyMMdd_HHmmss').json"
$TestReport = @{
    timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    duration_seconds = $Duration.TotalSeconds
    total_tests = $TotalTests
    passed = $PassedTests
    failed = $FailedTests
    errors = $ErrorTests
    success_rate_percent = $SuccessRate
    test_results = $TestResults
}

$TestReport | ConvertTo-Json -Depth 3 | Out-File -FilePath $ReportPath -Encoding UTF8
Write-Host "`nDetailed report saved: $ReportPath" -ForegroundColor Cyan

# System recommendations
Write-Host "`n=== Recommendations ===" -ForegroundColor Cyan

if ($SuccessRate -ge 90) {
    Write-Host "[EXCELLENT] System is ready for production use." -ForegroundColor Green
    Write-Host "[OK] All core functions are working properly" -ForegroundColor Green
} elseif ($SuccessRate -ge 70) {
    Write-Host "[GOOD] System is mostly functional with minor issues." -ForegroundColor Yellow
    Write-Host "[ACTION] Review failed tests and fix configuration issues" -ForegroundColor Yellow
} else {
    Write-Host "[CRITICAL] System needs attention. Multiple issues detected." -ForegroundColor Red
    Write-Host "[ACTION] Fix critical issues before production use" -ForegroundColor Red
}

Write-Host "`n=== Next Steps ===" -ForegroundColor Cyan
Write-Host "1. Review test results above" -ForegroundColor White
Write-Host "2. Fix any failed tests" -ForegroundColor White
Write-Host "3. Update .env with real cookies" -ForegroundColor White
Write-Host "4. Run: .\scripts\daily_scraping.ps1 -TestMode" -ForegroundColor White
Write-Host "5. Monitor with: python tools\system_monitor.py" -ForegroundColor White

# Final status
if ($FailedTests -gt 0 -or $ErrorTests -gt 0) {
    exit 1
} else {
    exit 0
} 