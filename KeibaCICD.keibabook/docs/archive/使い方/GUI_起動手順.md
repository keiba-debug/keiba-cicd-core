# GUI 起動手順（FastAPI + Next.js）

## 前提
- OS: Windows（PowerShell）
- ルート: `C:\source\git-h.fukuda1207\_keiba\keiba-cicd-core\KeibaCICD.keibabook`
- Python 3.10+ / Node.js 18+

---

## 1. API（FastAPI）

### セットアップ
```powershell
cd C:\source\git-h.fukuda1207\_keiba\keiba-cicd-core\KeibaCICD.keibabook
pip install -r api/requirements.txt
```

### 起動
```powershell
python api/main.py
```
- 既定ポート: `http://localhost:8000`

### 主要エンドポイント
- POST `/run`（CLI非同期実行）
- GET `/jobs`（ジョブ一覧）
- GET `/logs/{jobId}`（ジョブログ）
- GET `/artifacts?date=YYYY-MM-DD`（生成物一覧）
- GET `/markdown/{raceId}`（MD本文）

---

## 2. フロント（Next.js）

### セットアップ/起動
```powershell
cd C:\source\git-h.fukuda1207\_keiba\keiba-cicd-core\KeibaCICD.keibabook\gui
npm install
npm run dev
```
- 既定ポート: `http://localhost:3000`

### 接続設定
- `.env.local`
```
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

### 基本操作
1) 実行フォームで処理・期間を指定し実行
2) ジョブ一覧で状態を確認（5秒更新）
3) ログビューで経過を確認（2秒ポーリング）
4) 日付/場/レース選択でMDプレビュー

---

## 3. よくあるトラブル
- ポート競合: 8000/3000 を使用中のプロセス停止 or 変更
- CORS: APIで許可ヘッダ設定 or フロントでプロキシ
- 権限: PowerShellを管理者で実行
- パス: `KEIBA_DATA_ROOT_DIR` 未設定時は既定パスを使用

---

## 4. 参考
- 実装詳細/MVP構成: `ai-team/conversations/nextjs_gui_mvp_proposal_20250823.md`
