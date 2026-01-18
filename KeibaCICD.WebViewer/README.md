# KEIBA Data Viewer

競馬データをWebブラウザで閲覧するためのローカルアプリケーションです。

## 機能

- 📅 **日付別レース一覧**: 日付を選択してその日のレースを一覧表示
- 🏟️ **競馬場別表示**: 中山・東京・京都・阪神など競馬場ごとにグループ化
- 📝 **レース詳細**: MarkdownファイルをHTMLに変換して表示
- 🐴 **馬プロファイル**: 馬の詳細情報を表示
- 🔗 **リンク連携**: レース⇔馬の相互リンク
- 📰 **表示切替**: カード型 / 新聞風のテーマ切替
- 📺 **JRAビュアー連携**: パドック・レース・パトロール映像へのワンクリックアクセス
- 🖥️ **マルチビュー**: 複数のJRA映像を並べて同時視聴（2画面/4画面対応）
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

## 将来の拡張予定

- [ ] SQLiteによるデータベース化
- [ ] 全文検索機能
- [ ] JRA-VAN連携 (KeibaCICD.JraVanSync)
- [ ] **馬過去レースマルチビュー**: 1頭の馬の過去レースを複数選択して並べて確認
  - 詳細: [docs/馬過去レースマルチビュー計画.md](docs/馬過去レースマルチビュー計画.md)

## 🔧 既知の課題・改善検討事項

### パフォーマンス
- [ ] **スケジュールデータのキャッシュ化**: 現在は毎回ファイルシステムをスキャンして日付一覧を取得しているため、データ量が増えるとパフォーマンスに影響する可能性がある。キャッシュ機構（メモリキャッシュ or ファイルキャッシュ）の導入を検討。

### UI/UX
- [ ] 404エラーページのカスタマイズ
- [ ] モバイル対応の強化

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
│   ├── demo/course/
│   │   └── page.tsx       # コース情報デモ
│   └── api/
│       ├── horses/search/route.ts  # 検索API
│       ├── notes/route.ts          # レースメモAPI
│       └── horse-memo/route.ts     # 馬メモAPI
├── components/
│   ├── ui/                    # shadcn/ui コンポーネント
│   ├── header.tsx             # ヘッダー
│   ├── providers.tsx          # Context Provider
│   ├── view-mode-toggle.tsx   # テーマ切替
│   ├── jra-viewer-links.tsx   # JRAビュアーリンク
│   ├── jra-viewer-mini-links.tsx  # JRAビュアー小リンク
│   ├── race-memo-editor.tsx   # レースメモエディタ
│   ├── horse-profile-memo-editor.tsx  # 馬メモエディタ
│   └── mermaid-renderer.tsx   # Mermaid図表示
├── lib/
│   ├── config.ts              # 設定
│   ├── jra-viewer-url.ts      # JRAビュアーURL生成
│   ├── data/                  # データ読込層
│   │   ├── race-reader.ts
│   │   ├── horse-reader.ts
│   │   ├── user-notes.ts      # ユーザーメモ管理
│   │   └── horse-memo.ts      # 馬メモ管理
│   └── view-mode-context.tsx
└── types/
    └── index.ts               # 型定義

docs/
└── 馬過去レースマルチビュー計画.md  # 開発計画
```
