# KeibaCICD.WebViewer IISデプロイスクリプト
# 実行前に管理者権限でPowerShellを起動してください

param(
    [Parameter(Mandatory=$true)]
    [string]$SiteName = "KeibaCICD",

    [Parameter(Mandatory=$true)]
    [string]$AppPoolName = "KeibaCICDAppPool",

    [string]$PhysicalPath = "C:\inetpub\wwwroot\keiba-cicd",

    [int]$Port = 80,

    [string]$DataRoot = "C:\KEIBA-CICD\data2",

    [string]$JvDataRoot = "C:\TFJV"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "KeibaCICD.WebViewer IISデプロイ開始" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 1. ビルド
Write-Host "`n[1/7] Next.jsアプリケーションをビルド中..." -ForegroundColor Yellow
Set-Location $PSScriptRoot\..
npm run build

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ ビルドに失敗しました" -ForegroundColor Red
    exit 1
}
Write-Host "✓ ビルド完了" -ForegroundColor Green

# 2. デプロイディレクトリ作成
Write-Host "`n[2/7] デプロイディレクトリを作成中..." -ForegroundColor Yellow
if (Test-Path $PhysicalPath) {
    Write-Host "既存のディレクトリを削除中..."
    Remove-Item -Path $PhysicalPath -Recurse -Force
}
New-Item -ItemType Directory -Path $PhysicalPath -Force | Out-Null
Write-Host "✓ ディレクトリ作成完了: $PhysicalPath" -ForegroundColor Green

# 3. ファイルコピー
Write-Host "`n[3/7] ビルドファイルをコピー中..." -ForegroundColor Yellow

# .next/standalone ディレクトリの内容をコピー
Copy-Item -Path ".\.next\standalone\*" -Destination $PhysicalPath -Recurse -Force

# public ディレクトリをコピー
if (Test-Path ".\public") {
    Copy-Item -Path ".\public" -Destination "$PhysicalPath\public" -Recurse -Force
}

# .next/static ディレクトリをコピー
Copy-Item -Path ".\.next\static" -Destination "$PhysicalPath\.next\static" -Recurse -Force

# web.config をコピー
Copy-Item -Path ".\web.config" -Destination "$PhysicalPath\web.config" -Force

Write-Host "✓ ファイルコピー完了" -ForegroundColor Green

# 4. 環境変数ファイル作成
Write-Host "`n[4/7] 環境変数ファイルを作成中..." -ForegroundColor Yellow
$envContent = @"
DATA_ROOT=$DataRoot
JV_DATA_ROOT_DIR=$JvDataRoot
NODE_ENV=production
"@
$envContent | Out-File -FilePath "$PhysicalPath\.env.local" -Encoding UTF8
Write-Host "✓ .env.local 作成完了" -ForegroundColor Green

# 5. アプリケーションプール作成
Write-Host "`n[5/7] IISアプリケーションプールを設定中..." -ForegroundColor Yellow

# 既存のアプリケーションプールを削除
if (Test-Path "IIS:\AppPools\$AppPoolName") {
    Remove-WebAppPool -Name $AppPoolName
    Write-Host "既存のアプリケーションプールを削除しました"
}

# 新しいアプリケーションプールを作成
New-WebAppPool -Name $AppPoolName
Set-ItemProperty "IIS:\AppPools\$AppPoolName" -Name "managedRuntimeVersion" -Value ""
Set-ItemProperty "IIS:\AppPools\$AppPoolName" -Name "enable32BitAppOnWin64" -Value $false
Set-ItemProperty "IIS:\AppPools\$AppPoolName" -Name "processModel.identityType" -Value "ApplicationPoolIdentity"
Write-Host "✓ アプリケーションプール作成完了: $AppPoolName" -ForegroundColor Green

# 6. Webサイト作成
Write-Host "`n[6/7] IIS Webサイトを設定中..." -ForegroundColor Yellow

# 既存のサイトを削除
if (Test-Path "IIS:\Sites\$SiteName") {
    Remove-Website -Name $SiteName
    Write-Host "既存のWebサイトを削除しました"
}

# 新しいサイトを作成
New-Website -Name $SiteName `
    -PhysicalPath $PhysicalPath `
    -ApplicationPool $AppPoolName `
    -Port $Port

Write-Host "✓ Webサイト作成完了: $SiteName" -ForegroundColor Green

# 7. 権限設定
Write-Host "`n[7/7] ディレクトリ権限を設定中..." -ForegroundColor Yellow
$acl = Get-Acl $PhysicalPath
$identity = "IIS AppPool\$AppPoolName"
$fileSystemRights = "ReadAndExecute"
$type = "Allow"
$fileSystemAccessRule = New-Object System.Security.AccessControl.FileSystemAccessRule($identity, $fileSystemRights, "ContainerInherit,ObjectInherit", "None", $type)
$acl.SetAccessRule($fileSystemAccessRule)
Set-Acl -Path $PhysicalPath -AclObject $acl
Write-Host "✓ 権限設定完了" -ForegroundColor Green

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "✅ デプロイ完了！" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "URL: http://localhost:$Port" -ForegroundColor Yellow
Write-Host "物理パス: $PhysicalPath" -ForegroundColor Yellow
Write-Host "`n次のコマンドでサイトを管理できます:" -ForegroundColor Cyan
Write-Host "  開始: Start-Website -Name '$SiteName'" -ForegroundColor White
Write-Host "  停止: Stop-Website -Name '$SiteName'" -ForegroundColor White
Write-Host "  再起動: Restart-WebAppPool -Name '$AppPoolName'" -ForegroundColor White
