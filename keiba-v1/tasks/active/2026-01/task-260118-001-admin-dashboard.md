# Task: 管理画面の実装

## メタデータ
- **ID**: 260118-001
- **作成日**: 2026-01-18
- **更新日**: 2026-01-18 19:00
- **優先度**: 🟡重要
- **ステータス**: 完了
- **進捗**: 100%
- **見積工数**: 4h
- **実績工数**: 1.5h
- **担当**: AI Assistant

## 概要

競馬ブックデータの取得・統合・生成を GUI から実行できる管理画面を `KeibaCICD.WebViewer` に追加する。

## 背景・目的

現在、パドック情報や成績情報の取得はコマンドラインで実行する必要があり、運用が煩雑。
ボタンクリックで実行できる管理画面があると、レース当日のリアルタイム運用が効率化される。

## 要件

- 利用シーン: レース当日リアルタイム + 前日準備
- 同時実行: 不要（順次実行でOK）
- エラー通知: 画面表示のみ
- 実行権限: 確認ダイアログなし

## 依存関係

- 前提: KeibaCICD.WebViewer が動作すること
- 前提: KeibaCICD.keibabook のCLIが動作すること

## 作業内容

### Phase 1: 基本機能 (MVP)

- [ ] 管理画面ページ作成 (`/admin`)
- [ ] 日付選択コンポーネント
- [ ] 単発実行ボタン
  - [ ] スケジュール取得
  - [ ] 基本データ取得
  - [ ] パドック取得
  - [ ] 成績取得
  - [ ] データ統合
  - [ ] MD生成
  - [ ] 馬プロフィール生成
- [ ] API Route でコマンド実行 (`/api/admin/execute`)
- [ ] ログ表示（リアルタイム）
- [ ] 実行状態表示

### Phase 2: 一括実行

- [ ] 前日準備ボタン（一括）
- [ ] レース後更新ボタン（一括）
- [ ] 進捗バー表示

## 進捗ログ

- 2026-01-18 18:00: 設計書作成完了 (`docs/管理画面設計.md`)
- 2026-01-18 18:30: Phase 1 実装完了
  - コマンド定義・設定ファイル作成
  - API Route作成 (`/api/admin/execute`)
  - UIコンポーネント作成
  - 管理画面ページ作成 (`/admin`)
  - ヘッダーにリンク追加
- 2026-01-18 19:00: 動作確認完了

## 技術メモ

### コマンド実行方法

```typescript
import { spawn } from 'child_process';

const process = spawn('python', ['-m', 'src.fast_batch_cli', ...args], {
  cwd: process.env.KEIBABOOK_PATH
});
```

### SSE（Server-Sent Events）でリアルタイムログ

```typescript
// API Route
export async function POST(request: Request) {
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      // プロセスのstdoutをストリームに流す
    }
  });
  
  return new Response(stream, {
    headers: { 'Content-Type': 'text/event-stream' }
  });
}
```

## 関連ファイル

- `KeibaCICD.WebViewer/docs/管理画面設計.md` - 設計書
- `運用サポート.md` - 現在の運用手順

## 作業ログ

<!-- 完了した作業のworklogへのリンク -->
