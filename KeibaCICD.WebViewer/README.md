# KeibaCICD.WebViewer

> 競馬データ可視化・Web UIモジュール

レース情報・馬プロファイルのWeb表示、JRA映像マルチビューを提供します。

---

## 🎯 主要機能

- 📅 **日付別レース一覧**: 日付を選択してその日のレースを一覧表示
- 🏟️ **競馬場別表示**: 中山・東京・京都・阪神など競馬場ごとにグループ化
- 📝 **レース詳細**: Markdownファイルを解析してHTML表示
- 🐴 **馬プロファイル**: 馬の詳細情報・過去レース成績
- 📺 **JRA映像マルチビュー**: 複数JRA映像を並べて同時視聴
- 📝 **メモ機能**: レース・馬ごとにローカルメモ保存
- 💰 **資金管理**: 予算管理・収支記録

---

## 🚀 クイックスタート

### 1. セットアップ

```bash
cd KeibaCICD.WebViewer
npm install
```

### 2. 環境変数設定

`.env.local` ファイルを作成：
```ini
DATA_ROOT=C:/KEIBA-CICD/data2
JV_DATA_ROOT_DIR=C:/TFJV
```

### 3. 開発サーバー起動

```bash
npm run dev
```

ブラウザで `http://localhost:3000` を開きます。

---

## 📦 技術スタック

- **フレームワーク**: Next.js 16.1 (App Router)
- **UI**: React 19, shadcn/ui (Radix UI), Tailwind CSS 4.0
- **Markdown**: remark + remark-gfm
- **その他**: Mermaid 11.12, date-fns 4.1

---

## 📁 主要ページ

### トップページ

- **パス**: `/`
- **機能**: 日付選択・レース一覧表示

### レース詳細

- **パス**: `/races-v2/[date]/[track]/[id]`
- **機能**: 出走表・調教情報・予想・レース結果・メモ

### 馬プロファイル

- **パス**: `/horses-v2/[id]`
- **機能**: 基本情報・過去レース成績・ユーザーメモ

### マルチビュー

- **パス**: `/multi-view`
- **機能**: 複数JRA映像の並列表示

### 管理画面

- **パス**: `/admin`
- **機能**: データ取得・キャッシュクリア

---

## 🗂️ ディレクトリ構成

```
KeibaCICD.WebViewer/
├── src/
│   ├── app/                    # Next.js App Router
│   │   ├── page.tsx            # トップ
│   │   ├── races-v2/[...]/     # レース詳細
│   │   ├── horses-v2/[id]/     # 馬プロファイル
│   │   ├── multi-view/         # マルチビュー
│   │   ├── admin/              # 管理画面
│   │   └── api/                # REST API
│   ├── components/
│   │   ├── ui/                 # shadcn/ui
│   │   ├── race-v2/            # レース表示
│   │   ├── horse-v2/           # 馬プロファイル
│   │   └── bankroll/           # 資金管理
│   ├── lib/
│   │   ├── data/               # データ読込
│   │   └── config.ts           # 設定
│   └── types/
│       └── index.ts            # 型定義
└── user-data/                  # ローカル永続化
    ├── notes/                  # レースメモ
    └── horse-memo/             # 馬メモ
```

---

## 📚 ドキュメント

### はじめに読むドキュメント

- **[MODULE_OVERVIEW.md](../../ai-team/knowledge/MODULE_OVERVIEW.md)** - WebViewerモジュール詳細
- **[SETUP_GUIDE.md](../../ai-team/knowledge/SETUP_GUIDE.md)** - 環境構築手順
- **[ARCHITECTURE.md](../../ai-team/knowledge/ARCHITECTURE.md)** - システム全体構成

### その他ドキュメント

- **[管理画面設計.md](./docs/管理画面設計.md)** - 管理画面仕様
- **[馬過去レースマルチビュー計画.md](./docs/馬過去レースマルチビュー計画.md)** - マルチビュー仕様

---

## 🔧 コマンド

```bash
# 開発サーバー起動
npm run dev

# 本番ビルド
npm run build

# 本番サーバー起動
npm start
```

---

## ⚠️ トラブルシューティング

### Turbopack FATAL エラー

Next.js 16はTurbopackがデフォルトです。環境によっては以下で解消：

```bash
npm run dev:webpack
```

### データが表示されない

1. `DATA_ROOT` 環境変数が正しく設定されているか確認
2. keibabook でデータ収集が完了しているか確認
3. Next.jsサーバーを再起動

---

## 🔗 関連モジュール

- **[KeibaCICD.keibabook](../KeibaCICD.keibabook/)** - データ収集モジュール
- **[KeibaCICD.TARGET](../KeibaCICD.TARGET/)** - データ分析モジュール

---

**プロジェクトオーナー**: ふくだ君
**最終更新**: 2026-02-06
