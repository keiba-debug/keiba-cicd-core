# CK_DATA 調教データ仕様

TARGET frontier JV の調教データ（CK_DATA）の構造と読み取り方法を解説します。

## 概要

CK_DATAディレクトリには、JRA-VAN Data Lab.から取得した調教データが格納されています。
主に坂路調教とコース調教の2種類のデータがあります。

## ディレクトリ構造

```
Y:\CK_DATA\
  ├── 2024\
  │   ├── 202401\
  │   │   ├── HC020240101.DAT  # 坂路調教（美浦）
  │   │   ├── HC120240101.DAT  # 坂路調教（栗東）
  │   │   ├── WC020240101.DAT  # コース調教（美浦・ウッド）
  │   │   └── WC120240101.DAT  # コース調教（栗東・ウッド）
  │   └── ...
  └── 2026\
      └── 202601\
          └── ...
```

## ファイル命名規則

| パターン | 説明 |
|---------|------|
| `HC{場所}{YYYYMMDD}.DAT` | 坂路調教データ |
| `WC{場所}{YYYYMMDD}.DAT` | コース調教データ（ウッド） |

**場所コード:**
- `0`: 美浦トレーニングセンター
- `1`: 栗東トレーニングセンター

## 坂路調教レコード構造（HC*.DAT）

固定長**47バイト**（+CRLF 2バイト）

**注意**: TARGET実データではタイムのオフセットが上記と異なる場合があります。実サンプル `02026010206572020101174066316804951670328164164` に合わせ、parse_ck_data.py では Time4F=28-30(3桁)、Time3F=31-33(3桁)、Lap2=38-40、Lap1=41-43 でパースしています。

| 位置 | 長さ | フィールド | 説明 |
|-----|------|-----------|------|
| 0 | 1 | RecordType | レコードタイプ（'0' or '1'） |
| 1-8 | 8 | Date | 調教日（YYYYMMDD） |
| 9-12 | 4 | Time | 調教時刻（HHMM） |
| 13-22 | 10 | KettoNum | 血統登録番号 |
| 23-26 | 4 | Time5F | 5Fタイム |
| 27-30 | 4 | Time4F | 4Fタイム（実データでは28-30の3桁のことも） |
| 31-34 | 4 | Time3F | 3Fタイム（実データでは31-33の3桁のことも） |
| 35-37 | 3 | 不明 | |
| 38-40 | 3 | Lap2 | Lap2 |
| 41-43 | 3 | Lap1 | Lap1 |

### タイム値の変換

タイム値は0.1秒単位の整数で格納されています。

```typescript
// 例: "548" → 54.8秒
function formatTime(raw: string): string {
  const val = parseInt(raw, 10);
  const sec = Math.floor(val / 10);
  const tenth = val % 10;
  return `${sec}.${tenth}`;
}
```

## コース調教レコード構造（WC*.DAT）

固定長**92バイト**（+CRLF 2バイト）

| 位置 | 長さ | フィールド | 説明 |
|-----|------|-----------|------|
| 0 | 1 | RecordType | レコードタイプ（常に '1'） |
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

## TypeScriptリーダー

`KeibaCICD.WebViewer/src/lib/data/target-training-reader.ts` で読み取り機能を提供しています。

### 主要関数

```typescript
// 指定日の全調教データを取得
async function getTrainingDataForDate(dateStr: string): Promise<TrainingRecord[]>

// 利用可能な日付一覧を取得
function getAvailableTrainingDates(year: number, month: number): string[]

// 調教ラップ分類を計算
function calculateLapRank(lap2: string, lap1: string, time4f: string, location: string): string

// 調教データに馬名を付加
async function enrichTrainingRecordsWithHorseNames(records: TrainingRecord[]): Promise<TrainingRecord[]>
```

### 使用例

```typescript
import { 
  getTrainingDataForDate, 
  enrichTrainingRecordsWithHorseNames,
  calculateLapRank 
} from '@/lib/data/target-training-reader';

// 2026年1月23日の調教データを取得
const records = await getTrainingDataForDate('20260123');

// 馬名を付加
const enrichedRecords = await enrichTrainingRecordsWithHorseNames(records);

// ラップ分類を計算
for (const record of enrichedRecords) {
  const lapRank = calculateLapRank(
    record.lap2 || '', 
    record.lap1 || '', 
    record.time4f || '', 
    record.location
  );
  console.log(`${record.horseName}: ${lapRank}`);
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
| 美浦 | 坂路 | 52.9秒以下 |
| 栗東 | 坂路 | 53.9秒以下 |
| 美浦/栗東 | コース | 52.2秒以下 |

## デバッグAPI

開発時の確認用APIエンドポイント：

```
GET /api/debug/training?date=YYYYMMDD
GET /api/debug/training?action=dates&year=2026&month=1
```

## 注意事項

1. **馬名の取得**: DATファイルには馬名が含まれていないため、血統登録番号をキーにSE_DATA（馬毎レース成績）から取得する必要があります。

2. **エンコーディング**: ファイルはShift-JISで格納されています。Node.jsで読み込む際は `iconv-lite` を使用してデコードしてください。

3. **キャッシュ**: 大量のファイルを読み込むため、`fileBufferCache` でメモリキャッシュを行っています。必要に応じて `clearTrainingCache()` でクリアしてください。

## 関連ドキュメント

- [SE_DATA 馬毎レース成績仕様](./SE_DATA_馬毎レース成績仕様.md)
- [TARGET_DATA 構造一覧](./TARGET_DATA_構造一覧.md)
- [調教データ作成スクリプト開発](./調教データ作成スクリプト開発.md)
