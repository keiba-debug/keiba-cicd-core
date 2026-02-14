# CK_DATA 調教データ仕様

TARGET frontier JV の調教データ（CK_DATA）の構造と読み取り方法を解説します。

## 概要

CK_DATAディレクトリには、JRA-VAN Data Lab.から取得した調教データが格納されています。
**2種類のファイルタイプ**で坂路調教とコース調教を区別します:

| ファイル | 略語の意味 | 調教種別 | レコード長 |
|---------|-----------|---------|-----------|
| **HC*.DAT** | **H**ill **C**ourse（坂路） | 坂路調教 | 47バイト + CRLF |
| **WC*.DAT** | **W**ood **C**hip（ウッドチップ面） | コース調教 | 92バイト + CRLF |

## ディレクトリ構造

```
C:\TFJV\CK_DATA\
  ├── 2024\
  │   ├── 202401\
  │   │   ├── HC020240101.DAT  # 坂路調教（美浦）
  │   │   ├── HC120240101.DAT  # 坂路調教（栗東）
  │   │   ├── WC020240101.DAT  # コース調教（美浦・ウッド）
  │   │   └── WC120240101.DAT  # コース調教（栗東・ウッド）
  │   └── ...
  └── 2026\
      └── 202602\
          └── ...
```

## ファイル命名規則

| パターン | 説明 |
|---------|------|
| `HC{場所}{YYYYMMDD}.DAT` | 坂路調教データ（Hill Course） |
| `WC{場所}{YYYYMMDD}.DAT` | コース調教データ（Wood Chip） |

**場所コード:**
- `0`: 美浦トレーニングセンター
- `1`: 栗東トレーニングセンター

**RecordType（各レコードの先頭バイト）:**
- `'0'`: 美浦の調教レコード
- `'1'`: 栗東の調教レコード
- **注意**: これは有効/無効フラグではなく場所コード。両方とも有効な調教レコード。

## 坂路調教レコード構造（HC*.DAT）

固定長**47バイト**（+CRLF 2バイト = 49バイト/レコード）

坂路調教は4F(800m)が主タイム。5Fフィールドは存在しない。

| 位置 | 長さ | フィールド | 説明 |
|-----|------|-----------|------|
| 0 | 1 | RecordType | 場所コード（'0'=美浦, '1'=栗東） |
| 1-8 | 8 | Date | 調教日（YYYYMMDD） |
| 9-12 | 4 | Time | 調教時刻（HHMM） |
| 13-22 | 10 | KettoNum | 血統登録番号 |
| 23-26 | 4 | **Time4F** | **4Fタイム（坂路主タイム、直接値）** |
| 27-29 | 3 | Reserved | 予備 |
| 30-33 | 4 | Time3F | 3Fタイム |
| 34-36 | 3 | Reserved | 予備 |
| 37-40 | 4 | Time2F | 2Fタイム |
| 41-43 | 3 | Lap2 | Lap2（400M-200M区間） |
| 44-46 | 3 | Lap1 | Lap1（200M-0M区間） |

## コース調教レコード構造（WC*.DAT）

固定長**92バイト**（+CRLF 2バイト = 94バイト/レコード）

コース調教は6F〜1Fまでの各区間データを持つ。

| 位置 | 長さ | フィールド | 説明 |
|-----|------|-----------|------|
| 0 | 1 | RecordType | 場所コード（'0'=美浦, '1'=栗東） |
| 1-8 | 8 | Date | 調教日（YYYYMMDD） |
| 9-12 | 4 | Time | 調教時刻（HHMM） |
| 13-22 | 10 | KettoNum | 血統登録番号 |
| 23-67 | 45 | Reserved | 予備/フラグ |
| 68-71 | 4 | Time4F | 4Fタイム（0.1秒単位） |
| 72-74 | 3 | Lap4 | Lap4（800M-600M区間） |
| 75-78 | 4 | Time3F | 3Fタイム（0.1秒単位） |
| 79-81 | 3 | Lap3 | Lap3（600M-400M区間） |
| 82-85 | 4 | Time2F | 2Fタイム（0.1秒単位） |
| 86-88 | 3 | Lap2 | Lap2（400M-200M区間） |
| 89-91 | 3 | Lap1 | Lap1（200M-0M区間） |

### タイム値の変換

タイム値は0.1秒単位の整数で格納されています。

```typescript
// 例: "0527" → 52.7秒, "548" → 54.8秒
function formatTime(raw: string): string {
  const val = parseInt(raw, 10);
  const sec = Math.floor(val / 10);
  const tenth = val % 10;
  return `${sec}.${tenth}`;
}
```

## TypeScriptリーダー

`keiba-v2/web/src/lib/data/target-training-reader.ts` で読み取り機能を提供しています。

### 主要関数

```typescript
// 指定日の全調教データを取得
async function getTrainingDataForDate(dateStr: string): Promise<TrainingRecord[]>

// 調教サマリーを生成（2週間分のデータを集計）
async function generateTrainingSummary(baseDateStr: string): Promise<TrainingSummary[]>

// 調教ラップ分類を計算
function calculateLapRank(lap2, lap1, time4f, location, recordType): string

// 調教データに馬名を付加
async function enrichTrainingRecordsWithHorseNames(records): Promise<TrainingRecord[]>
```

### TrainingRecord インターフェース

```typescript
interface TrainingRecord {
  recordType: 'sakamichi' | 'course';  // HC=sakamichi, WC=course
  date: string;           // YYYY/MM/DD
  time: string;           // HH:MM
  kettoNum: string;       // 血統登録番号（10桁）
  location: string;       // 'Miho' or 'Ritto'
  time4f?: string;        // 4Fタイム（例: "52.3"）
  time3f?: string;        // 3Fタイム
  time2f?: string;        // 2Fタイム
  lap2?: string;          // ラップ2
  lap1?: string;          // ラップ1
  // WCコース専用
  lap4?: string;          // ラップ4
  lap3?: string;          // ラップ3
}
```

## 調教ラップ分類定義

| 分類 | 条件 | 説明 |
|-----|------|------|
| SS | 好タイム + S分類 + 加速or同タイム | 最高評価 |
| S+/S=/S- | Lap2・Lap1が11秒台以下 | 好ラップ |
| A+/A=/A- | 終い11秒台以下、Lap2は12秒台以上 | 好加速 |
| B+/B=/B- | Lap2・Lap1が12秒台 | 良 |
| C+/C=/C- | 終い12秒台 | 普通 |
| D+/D=/D- | 終い13秒台以上 | 軽め |

### 好タイム基準（4Fタイム）

| 場所 | 種別 | 基準 |
|-----|------|------|
| 美浦 | 坂路 (HC) | 52.9秒以下 |
| 栗東 | 坂路 (HC) | 53.9秒以下 |
| 美浦/栗東 | コース (WC) | 52.2秒以下 |

## 注意事項

1. **WC/HC の意味**: WC = Wood Chip（コース調教）、HC = Hill Course（坂路調教）。名前の略語に注意。

2. **RecordType ≠ 有効フラグ**: 各レコードの先頭バイト('0'=美浦, '1'=栗東)は場所を示す。両方とも有効な調教レコード。

3. **坂路に5Fフィールドはない**: HC(坂路)のoffset 23は4Fタイム（直接値）。坂路は4F(800m)が主距離のため5F以上のデータは存在しない。

4. **馬名の取得**: DATファイルには馬名が含まれていないため、血統登録番号をキーにSE_DATA/UM_DATA/horse master JSONから取得する。

5. **エンコーディング**: ファイルはShift-JISで格納。Node.jsでは `iconv-lite` を使用してデコード。

6. **キャッシュ**: `fileBufferCache` でメモリキャッシュ。`clearTrainingCache()` でクリア可能。

## 関連ドキュメント

- [SE_DATA 馬毎レース成績仕様](./SE_DATA_馬毎レース成績仕様.md)
- [TARGET_DATA 構造一覧](./TARGET_DATA_構造一覧.md)
