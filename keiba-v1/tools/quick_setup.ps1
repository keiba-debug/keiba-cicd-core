# Quick Setup Script for Keiba-CICD-Core
# Run this script to set up the system quickly

Write-Host "=== Keiba-CICD-Core Quick Setup ===" -ForegroundColor Green

# Check Python
Write-Host "Checking Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python not found. Please install Python 3.8+" -ForegroundColor Red
    exit 1
}

# Install dependencies
Write-Host "Installing dependencies..." -ForegroundColor Yellow
try {
    pip install -r src/keibabook/requirements.txt
    Write-Host "✓ Dependencies installed successfully" -ForegroundColor Green
} catch {
    Write-Host "✗ Failed to install dependencies" -ForegroundColor Red
    exit 1
}

# Create directories
Write-Host "Creating directories..." -ForegroundColor Yellow
$directories = @(
    "data\keibabook\seiseki",
    "data\debug",
    "data\analysis",
    "logs"
)

foreach ($dir in $directories) {
    if (!(Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "✓ Created: $dir" -ForegroundColor Green
    } else {
        Write-Host "✓ Exists: $dir" -ForegroundColor Green
    }
}

# Create .env file if not exists
Write-Host "Setting up environment file..." -ForegroundColor Yellow
if (!(Test-Path ".env")) {
    @"
# Keiba Book Authentication Cookies
KEIBABOOK_SESSION=your_session_cookie_here
KEIBABOOK_TK=your_tk_cookie_here
KEIBABOOK_XSRF_TOKEN=your_xsrf_token_here

# Application Settings
DEBUG=false
HEADLESS=true
LOG_LEVEL=INFO

# Scraping Settings
DEFAULT_TIMEOUT=10
DEFAULT_SLEEP_TIME=2.0
MAX_RETRY_COUNT=3
"@ | Out-File -FilePath ".env" -Encoding UTF8
    Write-Host "✓ Created .env file template" -ForegroundColor Green
} else {
    Write-Host "✓ .env file already exists" -ForegroundColor Green
}

# Test basic functionality
Write-Host "Testing basic functionality..." -ForegroundColor Yellow
$testFiles = Get-ChildItem -Path "data\debug\" -Filter "*.html" -ErrorAction SilentlyContinue
if ($testFiles) {
    $testFile = $testFiles[0]
    Write-Host "Using test file: $($testFile.Name)" -ForegroundColor Cyan
    
    try {
        $result = python src/keibabook/main.py --mode parse_only --html-file $testFile.FullName --race-id test 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ Basic parsing test passed" -ForegroundColor Green
        } else {
            Write-Host "⚠ Basic parsing test had warnings (check logs)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "✗ Basic parsing test failed" -ForegroundColor Red
    }
} else {
    Write-Host "⚠ No test HTML files found - skipping functionality test" -ForegroundColor Yellow
}

# Show next steps
Write-Host "`n=== Setup Complete ===" -ForegroundColor Green
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Edit .env file with your actual cookies from keibabook.co.jp" -ForegroundColor White
Write-Host "2. Test with: python src/keibabook/main.py --test" -ForegroundColor White
Write-Host "3. Run analysis with: python tools\data_analyzer.py" -ForegroundColor White
Write-Host "4. For daily scraping: .\scripts\daily_scraping.ps1 -TestMode -DryRun" -ForegroundColor White

Write-Host "`nAvailable commands:" -ForegroundColor Cyan
Write-Host "• python src/keibabook/main.py --help" -ForegroundColor White
Write-Host "• python tools\data_analyzer.py --help" -ForegroundColor White
Write-Host "• .\scripts\daily_scraping.ps1 -TestMode" -ForegroundColor White

Write-Host "`nFor help, check:" -ForegroundColor Cyan
Write-Host "• docs\setup_guide.md" -ForegroundColor White
Write-Host "• docs\setup_troubleshooting.md" -ForegroundColor White

Write-Host "`n🎉 Setup completed successfully!" -ForegroundColor Green 