# GUI API 起動手順（FastAPI）

## 前提
- OS: Windows（PowerShell）
- ルート: C:\source\git-h.fukuda1207\_keiba\keiba-cicd-core\KeibaCICD.keibabook
- Python: 3.10+

## 1. セットアップ
```powershell
cd C:\source\git-h.fukuda1207\_keiba\keiba-cicd-core\KeibaCICD.keibabook
pip install -r api/requirements.txt
```

必要に応じて .env（任意）:
```
API_HOST=127.0.0.1
API_PORT=8000
DATA_ROOT_PATH=Z:/KEIBA-CICD
KEIBA_PROJECT_PATH=C:/source/git-h.fukuda1207/_keiba/keiba-cicd-core/KeibaCICD.keibabook
```

## 2. 起動
```powershell
python api/main.py
```
- 既定ポート: http://localhost:8000

起動確認:
```powershell
curl http://localhost:8000/health
```

## 3. 主要エンドポイント
- POST /run（CLI非同期実行）
- GET /jobs（ジョブ一覧）
- GET /logs/{jobId}（ジョブログ）
- GET /logs/download/{jobId}（ログDL）
- GET /artifacts?date=YYYY-MM-DD（生成物一覧）
- GET /markdown/{raceId}（MD本文）
- GET /health（ヘルスチェック）

例:
```powershell
# ジョブ一覧
curl http://localhost:8000/jobs

# ログ取得
curl http://localhost:8000/logs/{jobId}
```

## 4. トラブルシューティング
- 起動しない: Python環境と `pip install -r api/requirements.txt` を再実行
- ポート競合: 8000を使用中のプロセス停止 or .envで変更
- CORS/接続不可（フロント連携）: フロントの NEXT_PUBLIC_API_BASE を確認
- 権限: PowerShellを管理者で実行

## 5. 補足
- フロント手順: docs/使い方/GUI_FRONTEND_起動手順.md
- 一体型手順: docs/使い方/GUI_起動手順.md
```

PowerShellでの自動作成（任意・2行実行）:
```powershell
$path="C:\source\git-h.fukuda1207\_keiba\keiba-cicd-core\KeibaCICD.keibabook\docs\使い方\GUI_API_起動手順.md"
Set-Content -Path $path -Value @'
[上記Markdown本文を貼り付け]
'@ -Encoding UTF8
