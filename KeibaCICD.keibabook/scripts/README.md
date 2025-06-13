# 競馬ブック データ取得システム v2.0 - スクリプト集

## 📊 概要

競馬ブック データ取得システム v2.0（リファクタリング完了版）の自動化スクリプト集です。

**最終更新**: 2025年2月4日  
**対応システム**: v2.0 統合CLIシステム  
**対応OS**: Windows (PowerShell), Linux/macOS (Bash)

---

## 🗂️ スクリプト一覧

### 📋 v2.0 新システム対応スクリプト

| スクリプト | OS | 用途 | 説明 |
|-----------|----|----|------|
| `daily_batch_v2.ps1` | Windows | 日次バッチ処理 | 新統合CLIシステム対応 |
| `daily_batch_v2.sh` | Linux/macOS | 日次バッチ処理 | 新統合CLIシステム対応 |
| `integration_test_v2.ps1` | Windows | 統合テスト | システム動作確認 |

### 📂 レガシースクリプト（v1.0互換）

| スクリプト | OS | 用途 | 状態 |
|-----------|----|----|------|
| `daily_scraping.ps1` | Windows | 旧バッチ処理 | 🔄 要更新 |
| `daily_scraping.sh` | Linux/macOS | 旧バッチ処理 | 🔄 要更新 |
| `weekly_scraping.ps1` | Windows | 週次処理 | 🔄 要更新 |
| `integration_test.ps1` | Windows | 旧テスト | 🔄 要更新 |

---

## 🚀 推奨使用方法

### 基本的なワークフロー

#### Windows環境
```powershell
# 1. 統合テスト実行
.\scripts\integration_test_v2.ps1

# 2. 日次バッチ処理実行
.\scripts\daily_batch_v2.ps1 -StartDate "2025/02/04"

# 3. 期間データ取得
.\scripts\daily_batch_v2.ps1 -StartDate "2025/02/01" -EndDate "2025/02/07"
```

#### Linux/macOS環境
```bash
# 1. スクリプトに実行権限を付与
chmod +x scripts/daily_batch_v2.sh

# 2. 日次バッチ処理実行
./scripts/daily_batch_v2.sh --start-date "2025/02/04"

# 3. 期間データ取得
./scripts/daily_batch_v2.sh --start-date "2025/02/01" --end-date "2025/02/07"
```

---

## 📋 詳細スクリプト解説

### 🔄 daily_batch_v2.ps1 / daily_batch_v2.sh

#### 概要
新しい統合CLIシステム（`batch_cli.py`）を使用した日次バッチ処理スクリプト。

#### 主要機能
- **全処理実行**: レース日程取得 → データ取得の一括処理
- **個別処理**: 日程のみ、データのみの選択実行
- **エラーハンドリング**: 詳細ログ、通知機能
- **環境チェック**: Python環境・ファイル存在確認

#### Windows版使用例
```powershell
# 基本実行（今日のデータを全処理）
.\scripts\daily_batch_v2.ps1

# 特定日の処理
.\scripts\daily_batch_v2.ps1 -StartDate "2025/02/04"

# 期間指定処理
.\scripts\daily_batch_v2.ps1 -StartDate "2025/02/01" -EndDate "2025/02/07"

# 日程取得のみ
.\scripts\daily_batch_v2.ps1 -StartDate "2025/02/04" -ScheduleOnly

# データ取得のみ
.\scripts\daily_batch_v2.ps1 -StartDate "2025/02/04" -DataOnly

# デバッグモード
.\scripts\daily_batch_v2.ps1 -StartDate "2025/02/04" -Debug

# ドライラン（テスト実行）
.\scripts\daily_batch_v2.ps1 -StartDate "2025/02/04" -DryRun

# カスタム設定
.\scripts\daily_batch_v2.ps1 `
  -StartDate "2025/02/04" `
  -DataTypes "seiseki,shutsuba" `
  -Delay 5 `
  -WaitBetweenPhases 15
```

#### Linux/macOS版使用例
```bash
# 基本実行
./scripts/daily_batch_v2.sh

# 特定日の処理
./scripts/daily_batch_v2.sh --start-date "2025/02/04"

# 期間指定処理
./scripts/daily_batch_v2.sh --start-date "2025/02/01" --end-date "2025/02/07"

# 日程取得のみ
./scripts/daily_batch_v2.sh --start-date "2025/02/04" --schedule-only

# データ取得のみ
./scripts/daily_batch_v2.sh --start-date "2025/02/04" --data-only

# デバッグモード
./scripts/daily_batch_v2.sh --start-date "2025/02/04" --debug

# 環境変数での設定
START_DATE="2025/02/04" DEBUG=true ./scripts/daily_batch_v2.sh
```

#### パラメータ一覧

| パラメータ | Windows | Linux/macOS | デフォルト | 説明 |
|-----------|---------|-------------|------------|------|
| 開始日 | `-StartDate` | `--start-date` | 今日 | 取得開始日 (YYYY/MM/DD) |
| 終了日 | `-EndDate` | `--end-date` | 開始日 | 取得終了日 (YYYY/MM/DD) |
| データタイプ | `-DataTypes` | `--data-types` | seiseki,shutsuba | カンマ区切り |
| リクエスト間隔 | `-Delay` | `--delay` | 3 | 秒数 |
| Phase間待機 | `-WaitBetweenPhases` | `--wait-phases` | 10 | 秒数 |
| 日程のみ | `-ScheduleOnly` | `--schedule-only` | false | スイッチ |
| データのみ | `-DataOnly` | `--data-only` | false | スイッチ |
| デバッグ | `-Debug` | `--debug` | false | スイッチ |
| ドライラン | `-DryRun` | `--dry-run` | false | スイッチ |

### 🧪 integration_test_v2.ps1

#### 概要
新しいシステムの動作確認用統合テストスクリプト。

#### テストカテゴリ
1. **システムテスト**: Python環境、ファイル存在確認
2. **統合CLIテスト**: 新batch_cli.pyの動作確認
3. **レガシーテスト**: 従来システムの互換性確認
4. **軽量データテスト**: HTMLパース機能確認

#### 使用例
```powershell
# 基本実行
.\scripts\integration_test_v2.ps1

# 特定カテゴリをスキップ
.\scripts\integration_test_v2.ps1 -SkipLegacyTest

# 詳細ログ付き実行
.\scripts\integration_test_v2.ps1 -Verbose

# ドライラン
.\scripts\integration_test_v2.ps1 -DryRun
```

#### テスト項目例
- Python バージョン確認
- 必須ファイル存在確認
- 統合CLIシステムのインポート
- バッチモジュールの動作確認
- レガシースクレイパーの互換性
- HTMLパース機能

---

## ⚙️ 自動化設定

### Windows タスクスケジューラー

#### 基本設定
```powershell
# タスク作成例
$Action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-File C:\path\to\scripts\daily_batch_v2.ps1"
$Trigger = New-ScheduledTaskTrigger -Daily -At "06:00"
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "KeibaDataDaily" -Action $Action -Trigger $Trigger -Settings $Settings
```

#### 高度な設定
```powershell
# 週末のみ実行（土日）
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Saturday,Sunday -At "06:00"

# 複数回実行（朝・夕）
$Trigger1 = New-ScheduledTaskTrigger -Daily -At "06:00"
$Trigger2 = New-ScheduledTaskTrigger -Daily -At "18:00"
```

### Linux/macOS cron設定

#### 基本設定
```bash
# crontabを編集
crontab -e

# 毎日6時に実行
0 6 * * * /path/to/scripts/daily_batch_v2.sh >> /path/to/logs/cron.log 2>&1

# 平日のみ実行
0 6 * * 1-5 /path/to/scripts/daily_batch_v2.sh

# 週末のみ実行
0 6 * * 6,0 /path/to/scripts/daily_batch_v2.sh
```

#### 高度な設定
```bash
# 環境変数を設定して実行
0 6 * * * START_DATE=$(date +\%Y/\%m/\%d) /path/to/scripts/daily_batch_v2.sh

# 過去データの補完（毎月1日）
0 2 1 * * /path/to/scripts/daily_batch_v2.sh --start-date "$(date -d 'last month' +\%Y/\%m/01)" --end-date "$(date -d 'last day of last month' +\%Y/\%m/\%d)"
```

---

## 🔧 カスタマイズ

### 環境変数設定

#### .env ファイル
```bash
# 認証情報
KEIBABOOK_SESSION=実際のセッション値
KEIBABOOK_TK=実際のtk値
KEIBABOOK_XSRF_TOKEN=実際のXSRF値

# データ保存先
KEIBA_DATA_DIR=./data

# ログレベル
LOG_LEVEL=INFO
```

#### スクリプト固有の環境変数
```bash
# Bashスクリプト用
export START_DATE="2025/02/04"
export DATA_TYPES="seiseki,shutsuba"
export DELAY="5"
export DEBUG="true"
```

### 通知設定（将来実装予定）

#### Slack通知
```powershell
# 成功時
Send-SlackMessage -Channel "#keiba-data" -Message "✅ 日次バッチ処理が完了しました"

# 失敗時
Send-SlackMessage -Channel "#keiba-alerts" -Message "❌ 日次バッチ処理でエラーが発生しました"
```

#### Email通知
```bash
# 成功時
echo "日次バッチ処理が完了しました" | mail -s "Keiba Batch Success" admin@example.com

# 失敗時
echo "日次バッチ処理でエラーが発生しました" | mail -s "Keiba Batch Error" admin@example.com
```

---

## 🔍 トラブルシューティング

### よくある問題

#### 1. スクリプト実行エラー
```powershell
# Windows: 実行ポリシーエラー
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Linux/macOS: 実行権限エラー
chmod +x scripts/daily_batch_v2.sh
```

#### 2. Python環境エラー
```bash
# Pythonパスの確認
which python
python --version

# モジュールインポートテスト
python -c "import src.keibabook.batch_cli"
```

#### 3. 認証エラー
```bash
# .envファイルの確認
cat .env

# Cookie値の更新が必要
# ブラウザで競馬ブックに再ログイン後、新しいCookie取得
```

### デバッグ方法

#### 詳細ログ付き実行
```powershell
# Windows
.\scripts\daily_batch_v2.ps1 -StartDate "2025/02/04" -Debug

# Linux/macOS
./scripts/daily_batch_v2.sh --start-date "2025/02/04" --debug
```

#### ドライラン実行
```powershell
# Windows
.\scripts\daily_batch_v2.ps1 -StartDate "2025/02/04" -DryRun

# Linux/macOS
./scripts/daily_batch_v2.sh --start-date "2025/02/04" --dry-run
```

#### ログファイル確認
```bash
# 最新のログを確認
tail -f logs/daily_batch_*.log

# エラーログのみ確認
grep "ERROR" logs/daily_batch_*.log
```

---

## 📈 パフォーマンス最適化

### 推奨設定

| 項目 | 推奨値 | 理由 |
|------|--------|------|
| リクエスト間隔 | 3-5秒 | サーバー負荷軽減 |
| Phase間待機 | 10-15秒 | 処理安定性確保 |
| 実行時間帯 | 早朝（6-8時） | サーバー負荷が軽い |
| 同時実行 | 1プロセスのみ | リソース競合回避 |

### システムリソース監視
```bash
# CPU・メモリ使用量確認
top -p $(pgrep -f batch_cli)

# ディスク容量確認
du -sh data/keibabook/*/

# ログファイルサイズ確認
du -sh logs/
```

---

## 🔄 マイグレーション（v1.0 → v2.0）

### 旧スクリプトから新スクリプトへの移行

#### 旧システム（v1.0）
```powershell
# 旧: 複数ステップが必要
.\scripts\daily_scraping.ps1 -StartDate "2025/02/04"
```

#### 新システム（v2.0）
```powershell
# 新: 一括実行
.\scripts\daily_batch_v2.ps1 -StartDate "2025/02/04"
```

### 移行チェックリスト
- [ ] 新スクリプトの動作確認（integration_test_v2.ps1）
- [ ] タスクスケジューラー/cronの更新
- [ ] ログファイル保存先の確認
- [ ] 通知設定の移行
- [ ] 旧スクリプトの無効化

---

## 📞 サポート・リファレンス

### 関連ドキュメント
- [workflow_guide.md](../docs/workflow_guide.md) - 完全ワークフロー
- [api_reference.md](../docs/api_reference.md) - APIリファレンス
- [troubleshooting.md](../docs/troubleshooting.md) - トラブルシューティング

### バージョン履歴
- **v2.0** (2025-02-04): 統合CLIシステム対応、新スクリプト作成
- **v1.0** (初期版): 旧システム対応スクリプト

---

**最終更新**: 2025年2月4日  
**対応システム**: v2.0 統合CLIシステム  
**スクリプト状態**: 本格運用可能