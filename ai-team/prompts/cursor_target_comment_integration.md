# Cursor相談: TARGETコメント連携機能

## 🎯 目的

TARGETフロントエンド（JRA-VAN Data Lab.ビューア）で管理している馬コメント・レース結果コメントを、KeibaCICD.WebViewerで参照・更新できるようにしたい。

## 📁 データソース

### 1. 馬コメント（UMA_COM）
- **場所**: `E:\TFJV\MY_DATA\UMA_COM`
- **用途**: 馬ごとの永続的なメモ（「左回り苦手」「重馬場得意」など）
- **ファイル形式**: 要調査（おそらくCSVまたは独自形式）

### 2. レース結果コメント（KEK_COM）
- **場所**: `E:\TFJV\MY_DATA\KEK_COM\2026`
- **用途**: レース別・馬別の結果コメント（「前走掛かった」「距離短縮◎」など）
- **ファイル形式**: 要調査

### 3. レース別馬別予想コメント（YOS_COM）
- **場所**: `E:\TFJV\MY_DATA\YOS_COM`
- **用途**: レース別・馬別の予想コメント（レース前に入力する予想メモ）
- **ファイル形式**: 要調査

## 📋 実装要件

### Phase 1: データ構造調査・読み取り機能
1. **データ形式の解析**
   - UMA_COM, KEK_COMのファイル形式を調査
   - エンコーディング確認（Shift-JIS / UTF-8）
   - ファイル命名規則の把握

2. **データリーダー実装**
   - `src/lib/data/target-comment-reader.ts` を新規作成
   - 既存の `baba-reader.ts` パターンを参考に実装
   - 環境変数 `JV_DATA_ROOT_DIR` を使用

3. **UI表示**
   - 馬詳細ページ（horses-v2）にコメント表示エリア追加
   - 出馬表で馬名横にコメントアイコン（ホバーで内容表示）

### Phase 2: 書き込み機能（Phase 1完了後）
1. **更新API実装**
   - Server Actionsまたは API Routes で書き込み
   - TARGETと同じフォーマットで保存

2. **UI編集機能**
   - インライン編集またはモーダル
   - 保存確認・バリデーション

## 🔧 技術的な参考情報

### 既存のデータリーダーパターン
```typescript
// src/lib/data/baba-reader.ts を参考に
export interface TargetComment {
  horseId: string;      // 馬ID（10桁）
  comment: string;      // コメント本文
  updatedAt?: string;   // 更新日時
}

export function getHorseComment(horseId: string): TargetComment | null {
  // UMA_COMから読み取り
}

export function getRaceComment(raceId: string, horseId: string): TargetComment | null {
  // KEK_COMから読み取り
}
```

### 環境変数
```
JV_DATA_ROOT_DIR=E:\TFJV
```

### 注意点
- **ファイルロック**: TARGETと同時使用時の競合に注意
- **エンコーディング**: TARGETはShift-JISの可能性が高い
- **パフォーマンス**: 読み取りは個別ファイルアクセスなので問題なし

## ❓ 相談事項

1. **まずデータ形式を調査してほしい**
   - `E:\TFJV\MY_DATA\UMA_COM` と `E:\TFJV\MY_DATA\KEK_COM\2026` の中身を確認
   - ファイル形式、エンコーディング、構造を報告

2. **読み取り専用で実装開始**
   - 書き込み機能は後回し
   - まずは表示だけできるようにする

3. **既存コードとの整合性**
   - `src/lib/data/` 配下の他のリーダーと同じパターンで実装

## 📂 関連ファイル

- `src/lib/data/baba-reader.ts` - 馬場情報リーダー（参考）
- `src/lib/data/baba-utils.ts` - ユーティリティ関数（参考）
- `src/app/horses-v2/[umacd]/page.tsx` - 馬詳細ページ
- `src/components/race-v2/HorseEntryTable.tsx` - 出馬表コンポーネント

---

## 🚀 進め方

1. まずデータ構造を調査して報告してください
2. 調査結果をもとに実装方針を相談
3. Phase 1（読み取り）から実装開始
