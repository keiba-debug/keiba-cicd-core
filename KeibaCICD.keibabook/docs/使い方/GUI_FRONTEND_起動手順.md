# GUI フロントエンド 起動手順（Next.js）

## 前提
- 実行環境: Windows / PowerShell
- 依存: API（FastAPI）が `http://localhost:8000` で起動済み

## 起動
```powershell
cd C:\source\git-h.fukuda1207\_keiba\keiba-cicd-core\KeibaCICD.keibabook\gui
npm install
npm run dev
```
- 既定ポート: `http://localhost:3000`

## 接続設定
- APIの接続先を `.env.local` で設定可能:
```
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

## 基本操作
1. 実行フォーム
   - 処理選択（fast_batch/integrator/markdown など）
   - 期間やデータタイプの指定
   - 実行→ジョブID発行
2. ジョブ一覧
   - 5秒間隔で自動更新
   - ステータス確認（running/success/failed）
3. ログビュー
   - 2秒ポーリングで最新ログ取得
   - 自動スクロール/ダウンロード
4. MDプレビュー
   - 日付/競馬場/レース選択→Markdownプレビュー

## トラブルシューティング
- 画面が空白: APIが未起動/ポート競合を確認
- CORSエラー: API側でCORS許可、またはフロントでプロキシ設定
- ログが流れない: `/logs/{jobId}` のレスポンスとジョブ状態を確認
