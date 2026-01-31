# SE_DATA 馬毎レース成績データ仕様

## 概要

TARGET frontier JVの`SE_DATA`ディレクトリには、馬毎のレース成績データが格納されています。

参考: [TARGET FAQ - 馬毎レース情報データ](https://targetfaq.jra-van.jp/faq/detail?site=SVKNEGBV&category=4011&id=518)

## ディレクトリ構造

```
Y:\SE_DATA\
├── 2024\
│   ├── SR202401.DAT   # レース毎成績
│   ├── SU202401.DAT   # 馬毎成績（メイン）
│   ├── SU202401.IDX   # 馬毎インデックス
│   └── ...
├── 2025\
│   └── ...
└── 2026\
    └── ...
```

## ファイル種別

| プレフィックス | 内容 |
|---------------|------|
| SR*.DAT | レース毎の全馬成績 |
| SU*.DAT | 馬毎のレース成績（馬単位で集約） |
| SU*.IDX | 馬毎インデックス（高速検索用） |
| SH*.DAT | 地方競馬成績 |

## SU*.DAT レコード構造

固定長555バイト（CRLF含む）、Shift-JIS エンコーディング

### JV_SE_RACE_UMA 構造体

| オフセット | 長さ | フィールド | 説明 |
|-----------|------|-----------|------|
| 0 | 2 | RecordType | "SE" |
| 2 | 8 | Date | 開催日 YYYYMMDD |
| 11 | 16 | RaceId | 年+場所+回+日+R番号 |
| 27 | 1 | Wakuban | 枠番 |
| 28 | 2 | Umaban | 馬番 |
| 30 | 10 | KettoNum | 血統登録番号 |
| 40 | 36 | Bamei | 馬名 |
| 78 | 1 | SexCD | 性別コード |
| 82 | 2 | Barei | 馬齢 |
| 90 | 8 | ChokyosiRyakusyo | 調教師名略称 |
| 288 | 3 | Futan | 負担重量（0.1kg単位） |
| 306 | 8 | KisyuRyakusyo | 騎手名略称 |
| 324 | 3 | BaTaijyu | 馬体重 |
| 327 | 1 | ZogenFugo | 増減符号 (+/-) |
| 328 | 3 | ZogenSa | 増減差 |
| 334 | 2 | KakuteiJyuni | 確定着順 |
| 338 | 4 | Time | 走破タイム |
| 384 | 2 | Jyuni1c | 1コーナー順位 |
| 386 | 2 | Jyuni2c | 2コーナー順位 |
| 388 | 2 | Jyuni3c | 3コーナー順位 |
| 390 | 2 | Jyuni4c | 4コーナー順位 |
| 392 | 5 | Odds | 単勝オッズ（×10） |
| 397 | 2 | Ninki | 単勝人気 |
| 400 | 3 | HaronTimeL3 | 上がり3Fタイム |
| 553 | 2 | CRLF | レコード区切り |

### 競馬場コード

| コード | 名称 |
|-------|------|
| 01 | 札幌 |
| 02 | 函館 |
| 03 | 福島 |
| 04 | 新潟 |
| 05 | 東京 |
| 06 | 中山 |
| 07 | 中京 |
| 08 | 京都 |
| 09 | 阪神 |
| 10 | 小倉 |

## 使用例（TypeScript）

```typescript
import { getHorseRaceResultsFromTarget } from '@/lib/data/target-race-result-reader';

// 血統登録番号で検索
const results = await getHorseRaceResultsFromTarget('2021105630');

for (const race of results) {
  console.log(`${race.raceDate} ${race.venue}${race.raceNumber}R: ${race.finishPosition}着`);
}
```

## 特徴

1. **高速検索**: 馬ID別インデックスにより、任意の馬の全戦歴を高速に取得可能
2. **全履歴**: 1954年以降の全レース成績を保持
3. **固定長**: 555バイト固定長のため、オフセット計算で直接アクセス可能

## 競馬ブックデータとの統合

TARGET SE_DATAは基本成績のみ。以下は競馬ブックデータ（integrated_*.json）から取得：

- レース名、クラス
- 距離、馬場状態
- 本誌印、短評
- 調教コメント
- 厩舎談話
- パドック評価

WebViewer では TARGET をベース、競馬ブックデータをマージして表示。
