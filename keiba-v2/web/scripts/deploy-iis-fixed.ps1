# KeibaCICD.WebViewer IIS Deployment Script
# Run PowerShell as Administrator before executing this script

param(
    [string]$SiteName = "KeibaCICD",
    [string]$AppPoolName = "KeibaCICDAppPool",
    [string]$PhysicalPath = "C:\inetpub\wwwroot\keiba-cicd",
    [int]$Port = 80,
    [string]$DataRoot = "C:\KEIBA-CICD\data2",
    [string]$JvDataRoot = "C:\TFJV"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "KeibaCICD.WebViewer IIS Deployment Start" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Step 1: Clean cache and build
Write-Host "`n[1/8] Cleaning Next.js cache..." -ForegroundColor Yellow
Set-Location $PSScriptRoot\..
Remove-Item -Path ".\.next" -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "Cache cleaned" -ForegroundColor Green

Write-Host "`n[2/8] Building Next.js application..." -ForegroundColor Yellow
npm run build

if ($LASTEXITCODE -ne 0) {
    Write-Host "Build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "Build completed successfully" -ForegroundColor Green

# Step 2: Create deployment directory
Write-Host "`n[3/8] Creating deployment directory..." -ForegroundColor Yellow
if (Test-Path $PhysicalPath) {
    Write-Host "Removing existing directory..."
    Remove-Item -Path $PhysicalPath -Recurse -Force
}
New-Item -ItemType Directory -Path $PhysicalPath -Force | Out-Null
Write-Host "Directory created: $PhysicalPath" -ForegroundColor Green

# Step 3: Copy files
Write-Host "`n[4/8] Copying build files..." -ForegroundColor Yellow

# Copy .next/standalone directory contents
Copy-Item -Path ".\.next\standalone\*" -Destination $PhysicalPath -Recurse -Force

# Copy public directory
if (Test-Path ".\public") {
    Copy-Item -Path ".\public" -Destination "$PhysicalPath\public" -Recurse -Force
}

# Copy .next/static directory
Copy-Item -Path ".\.next\static" -Destination "$PhysicalPath\.next\static" -Recurse -Force

# Copy web.config
Copy-Item -Path ".\web.config" -Destination "$PhysicalPath\web.config" -Force

Write-Host "Files copied successfully" -ForegroundColor Green

# Step 4: Create environment file
Write-Host "`n[5/8] Creating environment file..." -ForegroundColor Yellow
$envFilePath = Join-Path $PhysicalPath ".env.local"
$envContent = @"
DATA_ROOT=$DataRoot
JV_DATA_ROOT_DIR=$JvDataRoot
NODE_ENV=production
"@
$envContent | Out-File -FilePath $envFilePath -Encoding UTF8 -Force
Write-Host ".env.local created successfully" -ForegroundColor Green

# Step 5: Create application pool
Write-Host "`n[6/8] Configuring IIS application pool..." -ForegroundColor Yellow

# Remove existing application pool if exists
if (Test-Path "IIS:\AppPools\$AppPoolName") {
    Remove-WebAppPool -Name $AppPoolName
    Write-Host "Removed existing application pool"
}

# Create new application pool
New-WebAppPool -Name $AppPoolName
Set-ItemProperty "IIS:\AppPools\$AppPoolName" -Name "managedRuntimeVersion" -Value ""
Set-ItemProperty "IIS:\AppPools\$AppPoolName" -Name "enable32BitAppOnWin64" -Value $false
Set-ItemProperty "IIS:\AppPools\$AppPoolName" -Name "processModel.identityType" -Value "ApplicationPoolIdentity"
Write-Host "Application pool created: $AppPoolName" -ForegroundColor Green

# Step 6: Create website
Write-Host "`n[7/8] Configuring IIS website..." -ForegroundColor Yellow

# Remove existing website if exists
if (Test-Path "IIS:\Sites\$SiteName") {
    Remove-Website -Name $SiteName
    Write-Host "Removed existing website"
}

# Create new website
New-Website -Name $SiteName `
    -PhysicalPath $PhysicalPath `
    -ApplicationPool $AppPoolName `
    -Port $Port

Write-Host "Website created: $SiteName" -ForegroundColor Green

# Step 7: Set permissions
Write-Host "`n[8/8] Setting directory permissions..." -ForegroundColor Yellow
$acl = Get-Acl $PhysicalPath
$identity = "IIS AppPool\$AppPoolName"
$fileSystemRights = "ReadAndExecute"
$type = "Allow"
$fileSystemAccessRule = New-Object System.Security.AccessControl.FileSystemAccessRule($identity, $fileSystemRights, "ContainerInherit,ObjectInherit", "None", $type)
$acl.SetAccessRule($fileSystemAccessRule)
Set-Acl -Path $PhysicalPath -AclObject $acl
Write-Host "Permissions set successfully" -ForegroundColor Green

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Deployment completed successfully!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "URL: http://localhost:$Port" -ForegroundColor Yellow
Write-Host "Physical path: $PhysicalPath" -ForegroundColor Yellow
Write-Host "`nManage the site with these commands:" -ForegroundColor Cyan
Write-Host "  Start: Start-Website -Name '$SiteName'" -ForegroundColor White
Write-Host "  Stop: Stop-Website -Name '$SiteName'" -ForegroundColor White
Write-Host "  Restart: Restart-WebAppPool -Name '$AppPoolName'" -ForegroundColor White
