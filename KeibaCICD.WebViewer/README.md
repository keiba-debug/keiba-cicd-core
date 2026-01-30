# KEIBA Data Viewer

競馬データをWebブラウザで閲覧するためのローカルアプリケーションです。

## 機能

- 📅 **日付別レース一覧**: 日付を選択してその日のレースを一覧表示
- 🏟️ **競馬場別表示**: 中山・東京・京都・阪神など競馬場ごとにグループ化
- 🕒 **正確な発走時刻**: JRA-VANデータ連携により正確な発走時刻を表示
- 📝 **レース詳細**: MarkdownファイルをHTMLに変換して表示
- 🐴 **馬プロファイル**: 馬の詳細情報を表示
- 🔗 **リンク連携**: 
  - レース⇔馬の相互リンク
  - 外部サイト（競馬ブック、netkeiba、BBS）への直接リンク
- 📰 **表示切替**: カード型 / 新聞風のテーマ切替
- 📺 **JRAビュアー連携**: パドック・レース・パトロール映像へのワンクリックアクセス
- 🖥️ **マルチビュー**: 
  - 複数のJRA映像を並べて同時視聴（スロット数無制限）
  - 馬プロファイルから過去レースを一括で比較視聴
- 📝 **ユーザーメモ**: レース・馬ごとにメモを保存

## 必要条件

- Node.js 18.x 以上
- npm

## セットアップ

```bash
cd keiba-cicd-core/KeibaCICD.WebViewer
npm install
```

## 起動方法

### 開発モード

```bash
npm run dev
```

ブラウザで http://localhost:3000 を開きます。

- **Turbopack FATAL や multi-view のリロードループが出る場合**: Next.js 16 は開発時に Turbopack がデフォルトです。環境によっては `npm run dev:webpack`（webpack で起動）で解消することがあります。詳しくは `keiba-cicd-core/運用サポート.md` を参照してください。

### プロダクションビルド

```bash
npm run build
npm start
```

## データソース

デフォルトでは `Z:/KEIBA-CICD/data2/` フォルダからデータを読み込みます。

```
Z:/KEIBA-CICD/data2/
├── races/
│   └── {YYYY}/{MM}/{DD}/{競馬場}/{レースID}.md
└── horses/
    └── profiles/{馬ID}_{馬名}.md
```

データパスを変更する場合は環境変数 `DATA_ROOT` を設定してください。

```bash
DATA_ROOT="C:/path/to/your/data" npm run dev
```

## 技術スタック

- **フレームワーク**: Next.js 14+ (App Router)
- **スタイリング**: Tailwind CSS v4
- **UIコンポーネント**: shadcn/ui
- **Markdown変換**: remark + remark-gfm
- **データ連携**: Python CLI (fast_batch_cli, parse_jv_race_data)

## 機能拡張状況

- [x] SQLiteによるデータベース化 (一部検討中)
- [x] 全文検索機能 (馬検索実装済み)
- [x] JRA-VAN連携 (KeibaCICD.JraVanSync / KeibaCICD.TARGET)
  - 発走時刻の取得 (DRファイル解析)
- [x] **馬過去レースマルチビュー**: 1頭の馬の過去レースを複数選択して並べて確認
  - 実装完了: 馬プロファイルページから複数レースを選択してマルチビューに追加可能

## ディレクトリ構成

```
src/
├── app/                    # Next.js App Router
│   ├── page.tsx           # トップ（日付選択・レース一覧）
│   ├── races/[date]/[track]/[id]/
│   │   └── page.tsx       # レース詳細
│   ├── horses/
│   │   ├── page.tsx       # 馬検索
│   │   └── [id]/page.tsx  # 馬プロファイル
│   ├── multi-view/
│   │   └── page.tsx       # マルチビュー（JRA映像並列表示）
│   ├── admin/
│   │   └── page.tsx       # 管理画面（データ取得・更新）
│   └── api/
│       ├── horses/search/route.ts  # 検索API
│       ├── notes/route.ts          # レースメモAPI
│       ├── horse-memo/route.ts     # 馬メモAPI
│       └── race-lookup/route.ts    # レース情報検索API
├── components/
│   ├── ui/                    # shadcn/ui コンポーネント
│   ├── header.tsx             # ヘッダー
│   ├── providers.tsx          # Context Provider
│   ├── jra-viewer-links.tsx   # JRAビュアーリンク
│   ├── jra-viewer-mini-links.tsx  # JRAビュアー小リンク
│   ├── race-memo-editor.tsx   # レースメモエディタ
│   ├── horse-profile-memo-editor.tsx  # 馬メモエディタ
│   ├── horse-race-selector.tsx # 過去レース選択コンポーネント
│   └── race-fetch-actions.tsx # データ取得アクション
├── lib/
│   ├── config.ts              # 設定
│   ├── jra-viewer-url.ts      # JRAビュアーURL生成
│   ├── data/                  # データ読込層
│   │   ├── race-reader.ts
│   │   ├── horse-reader.ts
│   │   ├── race-lookup.ts     # レース検索ロジック
│   │   └── ...
│   └── admin/                 # 管理画面ロジック
└── types/
    └── index.ts               # 型定義

docs/
├── 管理画面設計.md
└── 馬過去レースマルチビュー計画.md
```
