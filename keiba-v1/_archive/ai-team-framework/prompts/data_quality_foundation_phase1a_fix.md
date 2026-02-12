# データ品質基盤 Phase 1a - 検証ロジック修正指示

**作成日**: 2026-02-01
**対象ファイル**: `src/app/api/data/validation/route.ts`
**修正理由**: 未開催レースで不要な警告が出る問題を修正

---

## 🐛 問題の詳細

### 現状の動作

**テストケース**: 2026-01-31（未開催レース）
- `race_info.json` あり
- 競馬場ディレクトリなし
- MDファイルなし

**現在の出力**:
```json
{
  "issues": [
    {
      "level": "warning",
      "message": "race_info.json が存在しますが、競馬場ディレクトリがありません"
    },
    {
      "level": "info",
      "message": "race_info.json のみ存在（未開催レース）"
    }
  ]
}
```

### 問題点

**未開催レースは正常な状態**なのに `warning` が出ている。

- `warning` と `info` の両方が出る → 論理的に矛盾
- 未開催レースでは競馬場ディレクトリがないのが正しい状態

### 期待される動作

```json
{
  "issues": [
    {
      "level": "info",
      "message": "race_info.json のみ存在（未開催レース）"
    }
  ]
}
```

未開催レースの場合は `info` のみ出して、`warning` は出さない。

---

## 🔧 修正内容

### ファイル: `src/app/api/data/validation/route.ts`

**修正箇所**: `validateDate` 関数内の「検証ルール適用」セクション

### 現在のコード（約260行目から）

```typescript
  // 検証ルール適用

  // Critical: 競馬場ディレクトリがあるのに race_info.json がない
  if (checks.trackDirectories && !checks.raceInfoExists) {
    issues.push({
      level: 'critical',
      type: 'missing_file',
      message: '競馬場ディレクトリが存在しますが、race_info.json がありません',
    });
  }

  // Critical: 競馬場ディレクトリがあるのに MDファイルも race_info.json もない
  if (checks.trackDirectories && !checks.mdFilesPresent && !checks.raceInfoExists) {
    issues.push({
      level: 'critical',
      type: 'incomplete_data',
      message: '競馬場ディレクトリがありますが、MDファイルと race_info.json の両方がありません',
    });
  }

  // Warning: race_info.json があるのに競馬場ディレクトリがない
  if (checks.raceInfoExists && !checks.trackDirectories) {
    issues.push({
      level: 'warning',
      type: 'incomplete_data',
      message: 'race_info.json が存在しますが、競馬場ディレクトリがありません',
    });
  }

  // Warning: MDファイルがあるのに race_info.json がない
  if (checks.mdFilesPresent && !checks.raceInfoExists) {
    issues.push({
      level: 'warning',
      type: 'missing_file',
      message: 'MDファイルが存在しますが、race_info.json がありません',
    });
  }

  // Warning: temp/navigation_index.json がない
  const navigationIndexPath = path.join(dayPath, 'temp', 'navigation_index.json');
  if (checks.mdFilesPresent && !fs.existsSync(navigationIndexPath)) {
    issues.push({
      level: 'warning',
      type: 'missing_file',
      message: 'temp/navigation_index.json がありません',
    });
  }

  // Info: race_info.json のみ存在（未開催レース用として正常）
  if (checks.raceInfoExists && !checks.trackDirectories && !checks.mdFilesPresent) {
    issues.push({
      level: 'info',
      type: 'incomplete_data',
      message: 'race_info.json のみ存在（未開催レース）',
    });
  }
```

### 修正後のコード

```typescript
  // ============================================
  // 検証ルール適用（修正版）
  // ============================================

  // ステップ1: 未開催レースパターンを最優先で判定
  const isUnscheduledRace = checks.raceInfoExists &&
                            !checks.trackDirectories &&
                            !checks.mdFilesPresent;

  if (isUnscheduledRace) {
    // 未開催レース: info のみ出す（正常状態）
    issues.push({
      level: 'info',
      type: 'incomplete_data',
      message: 'race_info.json のみ存在（未開催レース）',
    });
  } else {
    // ステップ2: 未開催レース以外の検証ルール

    // Critical: 競馬場ディレクトリがあるのに race_info.json がない
    if (checks.trackDirectories && !checks.raceInfoExists) {
      issues.push({
        level: 'critical',
        type: 'missing_file',
        message: '競馬場ディレクトリが存在しますが、race_info.json がありません',
      });
    }

    // Critical: 競馬場ディレクトリがあるのに MDファイルも race_info.json もない
    if (checks.trackDirectories && !checks.mdFilesPresent && !checks.raceInfoExists) {
      issues.push({
        level: 'critical',
        type: 'incomplete_data',
        message: '競馬場ディレクトリがありますが、MDファイルと race_info.json の両方がありません',
      });
    }

    // Warning: race_info.json があるのに競馬場ディレクトリがない
    // ※未開催レースは既に除外済み
    if (checks.raceInfoExists && !checks.trackDirectories) {
      issues.push({
        level: 'warning',
        type: 'incomplete_data',
        message: 'race_info.json が存在しますが、競馬場ディレクトリがありません（異常パターン）',
      });
    }

    // Warning: MDファイルがあるのに race_info.json がない
    if (checks.mdFilesPresent && !checks.raceInfoExists) {
      issues.push({
        level: 'warning',
        type: 'missing_file',
        message: 'MDファイルが存在しますが、race_info.json がありません',
      });
    }

    // Warning: temp/navigation_index.json がない
    const navigationIndexPath = path.join(dayPath, 'temp', 'navigation_index.json');
    if (checks.mdFilesPresent && !fs.existsSync(navigationIndexPath)) {
      issues.push({
        level: 'warning',
        type: 'missing_file',
        message: 'temp/navigation_index.json がありません',
      });
    }
  }

  // ステップ3: キャッシュ鮮度チェック（全パターン共通）
  checks.cacheUpToDate = await isCacheUpToDate(date);
  if (!checks.cacheUpToDate) {
    issues.push({
      level: 'warning',
      type: 'stale_cache',
      message: 'キャッシュインデックスが最新のデータより古い可能性があります',
    });
  }
```

---

## 📝 修正のポイント

### 1. 未開催レース判定を最優先

```typescript
const isUnscheduledRace = checks.raceInfoExists &&
                          !checks.trackDirectories &&
                          !checks.mdFilesPresent;
```

この条件に一致する場合は、**正常な状態**として `info` のみ出力。

### 2. if-else による排他制御

未開催レースの場合:
- ✅ `info` のみ出す
- ❌ `warning` は出さない

未開催レース以外:
- ✅ 各種 `critical` / `warning` チェックを実行

### 3. キャッシュチェックは独立

キャッシュの鮮度チェックは、未開催レースかどうかに関わらず**常に実行**。

---

## ✅ 修正手順

### 1. ファイルを開く

```bash
code keiba-cicd-core/KeibaCICD.WebViewer/src/app/api/data/validation/route.ts
```

### 2. 該当箇所を検索

**キーワード**: `// 検証ルール適用`（約260行目）

### 3. コードを置き換え

上記の「現在のコード」セクション全体を「修正後のコード」で置き換える。

### 4. 保存

Ctrl+S（Windows）/ Cmd+S（Mac）

---

## 🧪 テスト手順

### 1. WebViewerを再起動

```bash
cd keiba-cicd-core/KeibaCICD.WebViewer
npm run dev
```

### 2. テストケース1: 未開催レース

```bash
curl "http://localhost:3000/api/data/validation?date=2026-01-31"
```

**期待結果**:
```json
{
  "validation": {
    "overallStatus": "warning"  // キャッシュ警告のみ
  },
  "dates": [
    {
      "date": "2026-01-31",
      "status": "warning",
      "issues": [
        {
          "level": "info",
          "type": "incomplete_data",
          "message": "race_info.json のみ存在（未開催レース）"
        },
        {
          "level": "warning",
          "type": "stale_cache",
          "message": "キャッシュインデックスが最新のデータより古い可能性があります"
        }
      ]
    }
  ]
}
```

**確認ポイント**:
- ✅ `info` が1件のみ（未開催レース）
- ✅ `warning` は「競馬場ディレクトリがない」ではなく、「キャッシュが古い」のみ
- ✅ `critical` なし

### 3. テストケース2: 開催済みレース（正常）

```bash
# 過去の開催済みレース（MDファイルあり）
curl "http://localhost:3000/api/data/validation?date=2026-01-25"
```

**期待結果**:
- `overallStatus`: `healthy` または `warning`（キャッシュのみ）
- `critical` なし
- 競馬場ディレクトリとMDファイルが存在する場合は `info` / `warning` なし

### 4. テストケース3: 異常パターン

**手動テスト**: 一時的にファイルを移動して異常状態を作る

```bash
# race_info.json を削除（競馬場ディレクトリはある状態）
# → critical が出ることを確認
```

---

## 📋 完了チェックリスト

- [ ] `src/app/api/data/validation/route.ts` を修正
- [ ] TypeScriptコンパイルエラーなし（`npm run build`）
- [ ] テストケース1（未開催レース）で `info` のみ
- [ ] テストケース2（正常レース）で `critical` なし
- [ ] テストケース3（異常パターン）で適切な `critical` / `warning` が出る

---

## 🎯 修正完了後

カカシに報告してください。

```
修正完了。テスト結果：
- 未開催レース: info のみ ✅
- 正常レース: エラーなし ✅
- 異常パターン: 適切な警告 ✅
```

Phase 1a の残りのテストを進めます。

---

**作成者**: カカシ（AI相談役）
**優先度**: 高（Phase 1a完了のブロッカー）
