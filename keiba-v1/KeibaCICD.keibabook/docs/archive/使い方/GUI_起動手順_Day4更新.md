# KeibaCICD GUI 起動手順（Day4更新版）

## 概要
KeibaCIDCのGUIシステムは、FastAPI（バックエンド）とNext.js（フロントエンド）で構成されています。
Day4でエラーハンドリング機能と運用監視機能が追加されました。

## 起動手順

### 1. API サーバー起動

```bash
cd C:\source\git-h.fukuda1207\_keiba\keiba-cicd-core\KeibaCICD.keibabook\api

# 依存関係インストール（初回のみ）
pip install -r requirements.txt

# サーバー起動
python main.py
```

APIは http://localhost:8000 で起動します。

### 2. フロントエンド起動

別のターミナルで：

```bash
cd C:\source\git-h.fukuda1207\_keiba\keiba-cicd-core\KeibaCICD.keibabook\gui

# 依存関係インストール（初回のみ）
npm install

# 開発サーバー起動
npm run dev
```

GUIは http://localhost:3000 でアクセス可能です。

## 新規追加エンドポイント（Day4）

### エラーハンドリング関連

#### POST `/retry/{jobId}`
失敗したジョブを再試行します。

```bash
curl -X POST http://localhost:8000/retry/{jobId}
```

レスポンス例：
```json
{
  "job_id": "new-job-id",
  "status": "running",
  "created_at": "2025-08-23T14:00:00"
}
```

#### POST `/rerun-partial`
特定のデータ型のみを再取得します。

```bash
curl -X POST http://localhost:8000/rerun-partial \
  -H "Content-Type: application/json" \
  -d '{
    "date": "2025/08/23",
    "data_types": ["paddok", "seiseki"]
  }'
```

利用可能なdata_types:
- `race_info`: レース情報
- `syutubo`: 出馬表
- `odds`: オッズ
- `cyokyo`: 調教
- `danwa`: 談話
- `paddok`: パドック
- `seiseki`: 成績

### 監視・運用関連

#### GET `/health`
システムの詳細なヘルスチェック情報を取得します。

```bash
curl http://localhost:8000/health
```

レスポンス例：
```json
{
  "status": "healthy",
  "timestamp": "2025-08-23T14:00:00",
  "service": "KeibaCICD API",
  "version": "0.1.0",
  "environment": {
    "data_root_path": "Z:/KEIBA-CICD",
    "keiba_project_path": "C:/source/...",
    "data_dir_exists": true,
    "project_dir_exists": true
  },
  "jobs": {
    "total": 10,
    "running": 1,
    "completed": 8,
    "failed": 1,
    "error": 0
  },
  "logs": {
    "directory": "job_logs",
    "total_size_mb": 15.2,
    "retention_days": 7
  },
  "system": {
    "memory_usage_mb": 256.5,
    "cpu_percent": 15.2
  },
  "retry_config": {
    "max_attempts": 3,
    "wait_seconds": 5,
    "backoff_multiplier": 2
  }
}
```

#### GET `/logs/download/{jobId}`
ジョブのログファイルをダウンロードします。

```bash
curl -O http://localhost:8000/logs/download/{jobId}
```

## 環境設定

`.env`ファイルで以下の設定が可能です（`.env.example`を参照）：

```env
# API設定
API_HOST=127.0.0.1
API_PORT=8000

# リトライ設定
MAX_RETRY_ATTEMPTS=3          # 最大リトライ回数
RETRY_WAIT_SECONDS=5          # 初回待機時間（秒）
RETRY_BACKOFF_MULTIPLIER=2    # バックオフ倍率

# ログ設定
LOG_RETENTION_DAYS=7          # ログ保持期間（日）
LOG_MAX_SIZE_MB=100           # ログ最大サイズ（MB）

# パス設定
DATA_ROOT_PATH=Z:/KEIBA-CICD
KEIBA_PROJECT_PATH=C:/source/git-h.fukuda1207/_keiba/keiba-cicd-core/KeibaCICD.keibabook
```

## GUI機能（Day4追加）

### 1. 失敗ジョブの再試行
- ジョブ一覧で失敗したジョブに「再試行」ボタンが表示
- クリックで同一コマンドを新規ジョブとして再実行
- リトライ回数の表示

### 2. ヘルスステータス表示
- ヘッダーにシステム状態を常時表示
- 実行中ジョブ数、メモリ使用量、ログサイズを監視
- 30秒ごとに自動更新

### 3. ログダウンロード
- ログビューアーにダウンロードボタン追加
- 完全なログファイルをローカルに保存可能

## 自動リトライ機能

以下のエラーが検出された場合、自動的にリトライされます：
- タイムアウトエラー
- 接続エラー
- ネットワークエラー
- 502 Bad Gateway
- 503 Service Unavailable
- 504 Gateway Timeout
- 一時的な障害

リトライは指数バックオフで実行されます：
- 1回目: 5秒待機
- 2回目: 10秒待機
- 3回目: 20秒待機

## トラブルシューティング

### APIが起動しない
1. Python環境の確認
2. `pip install -r requirements.txt`で依存関係を再インストール
3. ポート8000が使用されていないか確認

### GUIが表示されない
1. Node.js/npmのバージョン確認
2. `npm install`で依存関係を再インストール
3. ポート3000が使用されていないか確認

### ジョブが失敗する
1. `/health`エンドポイントで環境設定を確認
2. データディレクトリの存在確認
3. ログファイルでエラー詳細を確認

## 運用上の注意

1. **ログローテーション**: 7日以上前のログは自動削除されます
2. **メモリ使用量**: ヘルスステータスで監視し、必要に応じて再起動
3. **同時実行数**: max_workersパラメータで制御（デフォルト8）
4. **エラー時の対処**: 
   - 一時的なエラーは自動リトライ
   - 永続的エラーは手動で再試行ボタンを使用
   - 部分再取得で特定データのみ更新可能