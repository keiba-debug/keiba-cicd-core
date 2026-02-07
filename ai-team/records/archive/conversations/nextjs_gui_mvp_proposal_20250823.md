# 提案: データ取得/MD新聞確認の簡易GUI（Next.js MVP）（2025-08-23）

## 目的
- 週末運用の反復作業（取得→統合→生成→確認）をGUIでワンクリック化し、人的負荷を削減
- 実行ログ/結果確認/再実行を一画面で完結

## MVP機能
1. 実行パネル
   - 期間指定: 単日/範囲
   - 処理選択: `fast_batch_cli` / `integrator_cli` / `markdown_cli` / `organizer_cli`
   - 実行ボタン + 進捗/ログストリーム
2. 生成物ブラウズ
   - 日付/競馬場/レース選択
   - MD新聞プレビュー（Markdownレンダ）
   - 統合JSON表示（開発者向け）
3. 再実行ショートカット
   - 欠損タイプのみ再取得
   - 単レース再生成

## 技術構成（推奨）
- フロント: Next.js 14 App Router + TypeScript + shadcn/ui（簡素）
- バックエンドAPI: FastAPI（Python）で既存CLIを非同期実行（subprocess）
  - 理由: 既存Python資産を直接活かしつつ、プロセス/非同期制御/ログ配信が容易
- 通信: REST + Server-Sent Events（ログ配信）
- ホスト: ローカル内向け（同一PC、ポート固定）

## API方式（詳細）
- POST /run
  - body: `{ command: 'fast_batch', args: {...} }`
  - 振る舞い: 非同期ジョブ起動→jobId返却
- GET /logs/{jobId}
  - SSEでリアルタイム配信
- GET /artifacts?date=YYYY-MM-DD
  - organized配下を列挙
- GET /markdown/{raceId}
  - MDを返却（またはHTML変換後）

## 画面構成
- /
  - 実行カード（期間/処理/ボタン/進捗）
  - 最近のジョブ一覧（状態/リンク）
- /newspaper
  - 日付/場/レース選択
  - プレビュー（MD）/JSONタブ

## 運用
- 環境: ローカル専用。秘密情報なし
- 権限: 起動ユーザのみアクセス（ポートローカル）
- ログ: FastAPI側でjobId単位に保存

## リスク/対応
- セキュリティ: ローカル専用に限定、外部公開不可
- 同時実行: キュー/同時数制限（1〜2）
- CLI破壊的変更: APIハンドラでバージョン吸収

## ロードマップ
- Phase 0: PoC（FastAPIでCLI 1本起動+SSEログ） 0.5d
- Phase 1: MVP（実行/プレビュー/再実行） 2d
- Phase 2: 予約実行/タスク履歴/権限 2d

## 次アクション
- PoC: FastAPI雛形 + `/run` `/logs/{jobId}` 実装
- Next.js: 実行フォームとログビュー実装
- 統合: organized列挙→MDプレビュー
