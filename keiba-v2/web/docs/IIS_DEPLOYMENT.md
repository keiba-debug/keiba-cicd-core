# KeibaCICD.WebViewer IISデプロイガイド

> Next.js 16アプリケーションをIISで実行するための完全ガイド

---

## 📋 前提条件

### 必須ソフトウェア

1. **Windows Server 2019+** または **Windows 10/11 Pro**
2. **IIS 10+** （Internet Information Services）
3. **Node.js 20.9.0+**
4. **iisnode** （Node.jsアプリケーションをIISで実行するモジュール）
5. **URL Rewrite Module** （IIS拡張機能）

---

## 🚀 クイックスタート

### 1. 必要なコンポーネントのインストール

#### IISのインストール（未インストールの場合）

```powershell
# PowerShellを管理者権限で実行
Enable-WindowsOptionalFeature -Online -FeatureName IIS-WebServerRole
Enable-WindowsOptionalFeature -Online -FeatureName IIS-WebServer
Enable-WindowsOptionalFeature -Online -FeatureName IIS-CommonHttpFeatures
Enable-WindowsOptionalFeature -Online -FeatureName IIS-HttpErrors
Enable-WindowsOptionalFeature -Online -FeatureName IIS-ApplicationDevelopment
Enable-WindowsOptionalFeature -Online -FeatureName IIS-NetFxExtensibility45
Enable-WindowsOptionalFeature -Online -FeatureName IIS-ISAPIExtensions
Enable-WindowsOptionalFeature -Online -FeatureName IIS-ISAPIFilter
```

#### Node.jsのインストール

1. [Node.js公式サイト](https://nodejs.org/)から最新LTS版（20.x）をダウンロード
2. インストーラーを実行し、デフォルト設定でインストール

#### iisnodeのインストール

1. [iisnode公式リリース](https://github.com/Azure/iisnode/releases)から最新版をダウンロード
   - 64bit版: `iisnode-full-v0.2.21-x64.msi`
2. インストーラーを実行

#### URL Rewrite Moduleのインストール

1. [Microsoft公式ページ](https://www.iis.net/downloads/microsoft/url-rewrite)からダウンロード
2. インストーラーを実行

---

## 📦 デプロイ手順

### 方法A: 自動デプロイスクリプト（推奨）

```powershell
# PowerShellを管理者権限で実行
cd C:\KEIBA-CICD\_keiba\keiba-cicd-core\KeibaCICD.WebViewer

# デプロイ実行
.\scripts\deploy-iis.ps1 `
  -SiteName "KeibaCICD" `
  -AppPoolName "KeibaCICDAppPool" `
  -PhysicalPath "C:\inetpub\wwwroot\keiba-cicd" `
  -Port 80 `
  -DataRoot "C:\KEIBA-CICD\data2" `
  -JvDataRoot "C:\TFJV"
```

**完了！** ブラウザで `http://localhost` を開いてください。

---

### 方法B: 手動デプロイ

#### ステップ1: ビルド

```powershell
cd C:\KEIBA-CICD\_keiba\keiba-cicd-core\KeibaCICD.WebViewer

# 依存関係インストール
npm install

# 本番ビルド
npm run build
```

#### ステップ2: ファイルのコピー

```powershell
# デプロイディレクトリ作成
$deployPath = "C:\inetpub\wwwroot\keiba-cicd"
New-Item -ItemType Directory -Path $deployPath -Force

# .next/standalone の内容をコピー
Copy-Item -Path ".\.next\standalone\*" -Destination $deployPath -Recurse -Force

# public ディレクトリをコピー
Copy-Item -Path ".\public" -Destination "$deployPath\public" -Recurse -Force

# .next/static をコピー
Copy-Item -Path ".\.next\static" -Destination "$deployPath\.next\static" -Recurse -Force

# web.config をコピー
Copy-Item -Path ".\web.config" -Destination "$deployPath\web.config" -Force
```

#### ステップ3: 環境変数設定

`C:\inetpub\wwwroot\keiba-cicd\.env.local` を作成:

```ini
DATA_ROOT=C:/KEIBA-CICD/data2
JV_DATA_ROOT_DIR=C:/TFJV
NODE_ENV=production
```

#### ステップ4: IIS設定

```powershell
# アプリケーションプール作成
New-WebAppPool -Name "KeibaCICDAppPool"
Set-ItemProperty "IIS:\AppPools\KeibaCICDAppPool" -Name "managedRuntimeVersion" -Value ""

# Webサイト作成
New-Website -Name "KeibaCICD" `
  -PhysicalPath "C:\inetpub\wwwroot\keiba-cicd" `
  -ApplicationPool "KeibaCICDAppPool" `
  -Port 80

# 権限設定
$acl = Get-Acl "C:\inetpub\wwwroot\keiba-cicd"
$identity = "IIS AppPool\KeibaCICDAppPool"
$fileSystemRights = "ReadAndExecute"
$type = "Allow"
$rule = New-Object System.Security.AccessControl.FileSystemAccessRule($identity, $fileSystemRights, "ContainerInherit,ObjectInherit", "None", $type)
$acl.SetAccessRule($rule)
Set-Acl -Path "C:\inetpub\wwwroot\keiba-cicd" -AclObject $acl
```

---

## 🔧 トラブルシューティング

### エラー1: HTTP 500エラー

**原因**: Node.jsがIISから見えない、または権限不足

**解決策**:
```powershell
# Node.jsのパスを確認
where.exe node

# IISアプリケーションプールのidentityにNode.jsへのアクセス権を付与
icacls "C:\Program Files\nodejs" /grant "IIS AppPool\KeibaCICDAppPool:(OI)(CI)RX" /T
```

### エラー2: 502.2 Bad Gateway

**原因**: iisnodeが正しくインストールされていない

**解決策**:
1. iisnodeを再インストール
2. IISをリセット: `iisreset`

### エラー3: 静的ファイル（CSS/JS）が404

**原因**: URL Rewriteルールが正しく設定されていない

**解決策**:
1. URL Rewrite Moduleがインストールされているか確認
2. web.configのrewriteルールを確認

### エラー4: データが表示されない

**原因**: 環境変数が正しく設定されていない

**解決策**:
```powershell
# .env.localを確認
Get-Content C:\inetpub\wwwroot\keiba-cicd\.env.local

# パスが正しいか確認
Test-Path "C:\KEIBA-CICD\data2"
Test-Path "C:\TFJV"
```

### ログの確認

```powershell
# iisnodeログディレクトリ
Get-ChildItem "C:\inetpub\wwwroot\keiba-cicd\iisnode" -Recurse

# 最新のログを表示
Get-Content "C:\inetpub\wwwroot\keiba-cicd\iisnode\*.log" -Tail 50
```

---

## 🛡️ セキュリティ設定

### HTTPSの有効化（推奨）

```powershell
# 自己署名証明書の作成（開発環境）
New-SelfSignedCertificate -DnsName "localhost" -CertStoreLocation "cert:\LocalMachine\My"

# HTTPSバインディング追加
New-WebBinding -Name "KeibaCICD" -Protocol "https" -Port 443 -IPAddress "*"

# 証明書をバインディングに割り当て（IISマネージャーから手動で設定）
```

### ファイアウォール設定

```powershell
# HTTP (80) を許可
New-NetFirewallRule -DisplayName "KeibaCICD HTTP" -Direction Inbound -Protocol TCP -LocalPort 80 -Action Allow

# HTTPS (443) を許可
New-NetFirewallRule -DisplayName "KeibaCICD HTTPS" -Direction Inbound -Protocol TCP -LocalPort 443 -Action Allow
```

---

## 📊 パフォーマンス最適化

### 1. 圧縮の有効化

web.configで既に設定済み:
```xml
<urlCompression doStaticCompression="true" doDynamicCompression="true" />
```

### 2. キャッシュの設定

```xml
<staticContent>
  <clientCache cacheControlMode="UseMaxAge" cacheControlMaxAge="365.00:00:00" />
</staticContent>
```

### 3. アプリケーションプールの最適化

```powershell
# リサイクル設定
Set-ItemProperty "IIS:\AppPools\KeibaCICDAppPool" -Name "recycling.periodicRestart.time" -Value "00:00:00"
Set-ItemProperty "IIS:\AppPools\KeibaCICDAppPool" -Name "recycling.periodicRestart.memory" -Value 2097152  # 2GB

# 常時実行モード
Set-ItemProperty "IIS:\AppPools\KeibaCICDAppPool" -Name "startMode" -Value "AlwaysRunning"
```

---

## 🔄 更新手順

```powershell
# 1. アプリケーションプール停止
Stop-WebAppPool -Name "KeibaCICDAppPool"

# 2. 最新ビルドをデプロイ
.\scripts\deploy-iis.ps1

# 3. アプリケーションプール開始
Start-WebAppPool -Name "KeibaCICDAppPool"

# または、自動デプロイスクリプトが自動的に再起動します
```

---

## 🧪 動作確認

```powershell
# サイトのステータス確認
Get-Website -Name "KeibaCICD"

# アプリケーションプールのステータス確認
Get-WebAppPoolState -Name "KeibaCICDAppPool"

# HTTPレスポンス確認
Invoke-WebRequest -Uri "http://localhost" -UseBasicParsing
```

---

## 📚 参考資料

- [iisnode GitHub](https://github.com/Azure/iisnode)
- [Next.js Deployment](https://nextjs.org/docs/deployment)
- [IIS Configuration Reference](https://docs.microsoft.com/en-us/iis/configuration/)

---

**プロジェクトオーナー**: ふくだ君
**最終更新**: 2026-02-07
