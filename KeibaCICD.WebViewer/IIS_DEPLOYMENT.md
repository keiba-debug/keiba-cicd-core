# IIS Deployment Guide (v1.0)

> **現在のステータス**: 開発中（`:3000`ポートで動作確認済み）
> **更新日**: 2026-02-07

---

## 📋 概要

KeibaCICD.WebViewer (Next.js 16 App Router) のIISデプロイ手順と課題をまとめたドキュメント。

---

## ✅ 完了した作業

### 1. Next.js設定の更新

**[next.config.ts](next.config.ts)**:
```typescript
const nextConfig: NextConfig = {
  output: 'standalone',  // IISデプロイ用
  // ...その他の設定
};
```

### 2. web.config作成

**[web.config](web.config)**:
- iisnodeによるNode.js実行設定
- URL Rewriteルール設定
- デバッグモード有効化

### 3. デプロイスクリプト作成

**[scripts/deploy-iis-fixed.ps1](scripts/deploy-iis-fixed.ps1)**:
- キャッシュクリーン
- ビルド実行
- ファイルコピー
- IIS設定
- 権限設定

### 4. TypeScript修正

以下のビルドエラーを修正：
- ESLint設定の削除（Next.js 16非対応）
- 型定義の統一（LogEntry, IntegratedRaceData, HorseEntry）
- 色関数の修正（getWakuColorRGB）

### 5. IIS環境構築

必要なモジュール：
- iisnode
- URL Rewrite Module

---

## 🔍 判明した課題

### パス問題

以下のパスがハードコードされている：

1. **Pythonスクリプト**:
   ```
   C:\inetpub\KeibaCICD.AI\tools\target_reader.py
   ```
   - 実際: `C:\KEIBA-CICD\_keiba\keiba-cicd-core\KeibaCICD.AI\tools\target_reader.py`

2. **rating_standards.json**:
   ```
   C:\inetpub\wwwroot\KeibaCICD.keibabook\data\rating_standards.json
   ```
   - 実際: `C:\KEIBA-CICD\data2\...`（環境変数 `DATA_ROOT` 配下）

### 影響範囲

管理画面機能の一部：
- Python統合（統計取得、日別サマリー）
- RPCI基準値の読み込み

---

## 🎯 現在の運用方法

### 開発サーバーで直接実行（推奨）

```bash
cd c:\KEIBA-CICD\_keiba\keiba-cicd-core\KeibaCICD.WebViewer
npm run dev
# または
node .next/standalone/server.js
```

アクセス: `http://localhost:3000/`

**メリット**:
- パス問題なし
- デバッグ容易
- 即座に動作

---

## 🚀 今後の対応方針

### Phase 1: パフォーマンス最適化（予定）

以下と合わせてIIS統合を検討：
- ビルド最適化
- キャッシュ戦略
- 画像最適化

### Phase 2: IIS完全統合

必要な修正：
1. **パスの環境変数化**
   - Pythonスクリプトパス → 環境変数
   - データファイルパス → 環境変数

2. **設定ファイルの整理**
   - `config.ts` でパス一元管理
   - `.env.local` での上書き対応

3. **デプロイスクリプト改善**
   - パス検証機能
   - ロールバック機能

---

## 📚 参考情報

### アーキテクチャの違い

**静的エクスポート（`out`）が使えない理由**:
- 40以上のAPI routesが存在
- Pythonスクリプト実行
- ファイルシステムへの書き込み
- リアルタイムデータ処理

→ **Node.jsサーバー必須**（Standalone output）

### 以前のプロジェクトでoutが使えた理由

- バックエンド: C# (ASP.NET Core) - 別サーバー
- フロントエンド: Next.js静的サイト
- Next.jsにはAPIが無い

---

## 🔧 デバッグコマンド

### IIS操作

```powershell
# サイト停止
Stop-Website -Name 'KeibaCICD'

# サイト起動
Start-Website -Name 'KeibaCICD'

# アプリプール再起動
Restart-WebAppPool -Name 'KeibaCICDAppPool'

# ログ確認
Get-Content "C:\inetpub\wwwroot\keiba-cicd\iisnode\*stderr*.txt" -Tail 20
```

### ビルド & デプロイ

```powershell
# デプロイスクリプト実行（管理者権限）
cd c:\KEIBA-CICD\_keiba\keiba-cicd-core\KeibaCICD.WebViewer
.\scripts\deploy-iis-fixed.ps1
```

---

## 📝 メモ

- iisnode経由だとNode.jsサーバーがポート3000で起動（ログ確認済み）
- デバッグモード有効化済み（`debuggingEnabled="true"`）
- 環境変数は `.env.local` で設定済み（`DATA_ROOT`, `JV_DATA_ROOT_DIR`）

---

**作成者**: カカシ
**最終更新**: 2026-02-07
