# 調教データ統合仕様書

KeibaCICD v4 で扱う調教データの全体像をまとめたドキュメント。
データソース、パーサー、保存形式、表示、ML特徴量の5レイヤーを網羅する。

---

## 1. データソース概要

調教データは **2つの独立したソース** から取得される。

| ソース | 取得方法 | データ形式 | 主な用途 |
|--------|---------|-----------|---------|
| **JRA-VAN CK_DATA** | TARGET frontier JV 自動蓄積 | 固定長バイナリ (Shift-JIS) | ラップ分析・好タイム判定 |
| **競馬ブック (keibabook)** | Webスクレイピング | HTML → JSON | 追切内容・脚色・短評・併せ馬 |

### 1.1 データの補完関係

```
CK_DATA (JRA-VAN)           keibabook (競馬ブック)
┌─────────────────┐          ┌──────────────────┐
│ 公式タイミング    │          │ スポッター観察     │
│ ・4F/3F/2F/1F    │          │ ・脚色(強さ)       │
│ ・ラップ区間      │          │ ・短評・解説       │
│ ・日時            │          │ ・併せ馬情報       │
│ ・全頭網羅        │          │ ・矢印評価(↑↗→↘↓) │
│                  │          │ ・セッション一覧   │
└────────┬────────┘          └────────┬─────────┘
         │                            │
         ↓                            ↓
  training_summary.json        kb_ext JSON
  (data3/races/.../temp/)      (data3/keibabook/)
         │                            │
         └──────────┬─────────────────┘
                    ↓
         TrainingAnalysisSection (WebViewer)
         training_features.py (ML)
```

**CK_DATAの強み**: 全頭のタイム・ラップを客観的に記録。ラップ加速度の定量分析が可能。
**keibabookの強み**: 脚色（馬なり/強め/一杯）、併せ馬の有無、スポッターの主観評価を提供。

---

## 2. JRA-VAN CK_DATA

### 2.1 ディレクトリ構成

```
C:\TFJV\CK_DATA\
  └── {YYYY}\
      └── {YYYYMM}\
          ├── HC0{YYYYMMDD}.DAT   # 坂路調教（美浦）
          ├── HC1{YYYYMMDD}.DAT   # 坂路調教（栗東）
          ├── WC0{YYYYMMDD}.DAT   # コース調教（美浦）
          └── WC1{YYYYMMDD}.DAT   # コース調教（栗東）
```

### 2.2 ファイル種別

| ファイル | 略語 | 調教種別 | レコード長 | recordType |
|---------|------|---------|-----------|------------|
| **HC*.DAT** | **H**ill **C**ourse | 坂路調教 | 47B + 2B CRLF | `'sakamichi'` |
| **WC*.DAT** | **W**ood **C**hip | コース調教 | 92B + 2B CRLF | `'course'` |

> **注意**: WC=坂路ではない。HC=コースでもない。略語の意味に注意。

### 2.3 HC 坂路レコード構造（47バイト）

坂路は4F(800m)が主距離。5Fフィールドは存在しない。

| 位置 | 長さ | フィールド | 説明 |
|-----|------|-----------|------|
| 0 | 1 | RecordType | 場所コード `'0'`=美浦, `'1'`=栗東 |
| 1-8 | 8 | Date | 調教日（YYYYMMDD） |
| 9-12 | 4 | Time | 調教時刻（HHMM） |
| 13-22 | 10 | KettoNum | 血統登録番号 |
| **23-26** | **4** | **Time4F** | **坂路主タイム（直接値、0.1秒単位）** |
| 27-29 | 3 | Reserved | 予備 |
| 30-33 | 4 | Time3F | 3Fタイム |
| 34-36 | 3 | Reserved | 予備 |
| 37-40 | 4 | Time2F | 2Fタイム |
| 41-43 | 3 | Lap2 | Lap2（400M-200M） |
| 44-46 | 3 | Lap1 | Lap1（200M-0M） |

### 2.4 WC コースレコード構造（92バイト）

コース調教は6F〜1Fまでの各区間データを持つ。

| 位置 | 長さ | フィールド | 説明 |
|-----|------|-----------|------|
| 0 | 1 | RecordType | 場所コード `'0'`=美浦, `'1'`=栗東 |
| 1-8 | 8 | Date | 調教日（YYYYMMDD） |
| 9-12 | 4 | Time | 調教時刻（HHMM） |
| 13-22 | 10 | KettoNum | 血統登録番号 |
| 23-67 | 45 | Reserved | 予備/フラグ |
| 68-71 | 4 | Time4F | 4Fタイム（0.1秒単位） |
| 72-74 | 3 | Lap4 | Lap4（800M-600M） |
| 75-78 | 4 | Time3F | 3Fタイム |
| 79-81 | 3 | Lap3 | Lap3（600M-400M） |
| 82-85 | 4 | Time2F | 2Fタイム |
| 86-88 | 3 | Lap2 | Lap2（400M-200M） |
| 89-91 | 3 | Lap1 | Lap1（200M-0M） |

### 2.5 タイム値の変換

全タイム/ラップ値は0.1秒単位の整数で格納。

```
"0527" → 52.7秒   "548" → 54.8秒   "124" → 12.4秒
```

### 2.6 RecordType（先頭バイト）

| 値 | 意味 |
|----|------|
| `'0'` | 美浦トレーニングセンター |
| `'1'` | 栗東トレーニングセンター |

**これは有効/無効フラグではない。** 両方とも有効な調教レコード。
ファイル名の場所コード（WC**0** / WC**1**）と同じ値になる。

---

## 3. 競馬ブック調教データ

### 3.1 データ取得フロー

```
keibabook Web  →  scraper.py (HTML取得)
                      ↓
              debug HTML files (cyokyo_{race_id_12}_{timestamp}_requests.html)
                      ↓
              cyokyo_parser.py (HTML解析)
                      ↓
              cyokyo_enricher.py (kb_ext JSONに統合)
                      ↓
              kb_ext JSON → entries[umaban].cyokyo_detail
```

### 3.2 取得データ（セッション単位）

```json
{
  "is_oikiri": true,        // 追い切りか否か
  "rider": "騎手名",
  "date": "2/12(水)",
  "course": "美Ｗ",          // コース名 (後述)
  "condition": "良",         // 良 / 稍 / 重 / 不良
  "times": {
    "1mile": null,           // 1マイルタイム (秒, nullable)
    "7f": null,
    "6f": null,
    "5f": 67.0,              // 5Fタイム
    "half_mile": 52.4,       // ハーフマイル (≈3F+α)
    "3f": 37.6,
    "1f": 12.0
  },
  "position": "［８］",       // 回り位置 (内外)
  "intensity": "馬なり余力",  // 脚色
  "comment": "好調持続",
  "awase": "xxx馬と併せ"      // 併せ馬情報 (nullable)
}
```

### 3.3 追切サマリー（oikiri_summary）

`extract_oikiri_summary()` が最終追切セッションから生成：

| フィールド | 型 | 説明 |
|-----------|-----|------|
| oikiri_course | string | 最終追切コース名 |
| oikiri_condition | string | 馬場状態 |
| oikiri_5f / 3f / 1f | float\|null | タイム（秒） |
| oikiri_intensity | string | 脚色テキスト |
| oikiri_rider | string | 騎乗者 |
| oikiri_comment | string | セッション短評 |
| oikiri_has_awase | bool | 併せ馬の有無 |
| session_count | int | セッション数 |
| rest_period | string | 休養間隔（例: "中3週"） |
| training_arrow | string | 矢印評価 ↑ ↗ → ↘ ↓ |
| training_arrow_value | int | 矢印数値 (-2〜+2) |

### 3.4 コース名一覧

| コース名 | 場所 | 種別 | 備考 |
|---------|------|------|------|
| 美Ｗ | 美浦 | ウッドチップコース | WC_DATに対応 |
| 美坂 | 美浦 | 坂路 | HC_DATに対応 |
| 美Ｐ | 美浦 | ポリトラック | |
| 美芝 | 美浦 | 芝コース | |
| 美ダ | 美浦 | ダートコース | |
| 栗Ｗ | 栗東 | ウッドチップ | WC_DATに対応 |
| 栗坂 | 栗東 | 坂路 | HC_DATに対応 |
| 栗Ｐ | 栗東 | ポリトラック | |
| 栗芝 | 栗東 | 芝コース | |
| 栗ダ | 栗東 | ダートコース | |
| 栗Ｂ / 美Ｂ | | Bコース | CK_DATA対応不明 |

### 3.5 脚色コード

| コード | 脚色テキスト | 意味 |
|--------|------------|------|
| 4 | 一杯に追う / 一杯追う / 叩き一杯 | 最大負荷 |
| 3 | 末強め追う | ラスト強め |
| 2 | 強めに追う / G前仕掛け | やや強め |
| 1 | 馬なり余力 / 馬なり | リラックス |
| 0 | ゲートなり | ゲート練習 |
| -1 | (不明) | デフォルト |

---

## 4. 保存データ形式

### 4.1 training_summary.json（CK_DATA由来）

保存先: `data3/races/{YYYY}/{MM}/{DD}/temp/training_summary.json`

```json
{
  "meta": {
    "date": "20260214",
    "created_at": "2026-02-14T15:30:00.000Z",
    "ranges": {
      "finalStart": "20260211",    // 最終追切期間（水）
      "finalEnd": "20260212",      // 最終追切期間（木）
      "weekAgoStart": "20260204",  // 1週前追切期間（水）
      "weekAgoEnd": "20260205"     // 1週前追切期間（木）
    },
    "count": 3671
  },
  "summaries": {
    "ツクバヴァンガード": {
      "horseName": "ツクバヴァンガード",
      "kettoNum": "2023101037",
      "trainerName": "",
      "lapRank": "B+",         // 全期間最高ランク
      "timeRank": "コ",        // 好タイム種別 (坂/コ/両/"")
      "detail": "最終:コースB+ 1週前:コースB-",
      "finalLocation": "コ",   // 最終追切場所
      "finalSpeed": "",        // ◎=好タイム
      "finalLap": "B+",        // 最終追切ラップランク
      "finalTime4F": 52.7,     // 最終追切4Fタイム
      "finalLap1": 12.4,       // 最終追切Lap1
      "weekendLocation": null,
      "weekendLap": null,
      "weekAgoLocation": "コ",
      "weekAgoLap": "B-",
      "weekAgoSpeed": "◎",
      "weekAgoTime4F": 51.8,
      "weekAgoLap1": 12.5
    }
  }
}
```

### 4.2 TrainingSummary インターフェース

```typescript
interface TrainingSummary {
  horseName: string;
  kettoNum: string;
  trainerName: string;
  lapRank: string;        // SS / S+ / A- / B= / C+ / D- 等
  timeRank: string;       // 坂 / コ / 両 / ""
  detail: string;         // "最終:坂路A+ 1週前:コースB-"

  // 各期間のベストレコード
  finalLocation?: string;   // 坂 / コ
  finalSpeed?: string;      // ◎ = 好タイム
  finalLap?: string;        // ラップランク
  finalTime4F?: number;
  finalLap1?: number;

  weekendLocation?: string;
  weekendSpeed?: string;
  weekendLap?: string;
  weekendTime4F?: number;
  weekendLap1?: number;

  weekAgoLocation?: string;
  weekAgoSpeed?: string;
  weekAgoLap?: string;
  weekAgoTime4F?: number;
  weekAgoLap1?: number;
}
```

### 4.3 kb_ext JSON 内の調教データ

保存先: `data3/keibabook/{YYYY}/{MM}/{DD}/kb_ext_{race_id_16}.json`

```
kb_ext.entries[umaban]:
  ├── training_arrow: "→"           // 矢印
  ├── training_arrow_value: 0       // 数値化
  ├── training_data:
  │     ├── short_review: "好調示す" // 短評
  │     ├── attack_explanation: ""   // 攻め解説
  │     ├── evaluation: ""
  │     ├── training_load: ""
  │     └── training_rank: ""
  └── cyokyo_detail:                 // ← cyokyo_enricher が追加
        ├── horse_code: "0898432"
        ├── sessions: [...]          // セッション配列
        ├── rest_period: "中1週"
        └── oikiri_summary: {...}    // 追切サマリー
```

---

## 5. ラップ分析仕様

### 5.1 ラップランク分類

全期間の全レコードから最高ランクを選出して `lapRank` とする。

| ランク | Lap2条件 | Lap1条件 | 追加条件 |
|--------|---------|---------|---------|
| **SS** | < 12.0 | < 12.0 | 好タイム + 加速or同タイム |
| **S+/S=/S-** | < 12.0 | < 12.0 | 2F連続11秒台 |
| **A+/A=/A-** | >= 12.0 | < 12.0 | 終い11秒台（加速） |
| **B+/B=/B-** | < 13.0 | < 13.0 | 12秒台キープ |
| **C+/C=/C-** | any | < 13.0 | 終い12秒台 |
| **D+/D=/D-** | any | >= 13.0 | 終い13秒台以上 |

サフィックス: `+`=加速(Lap2>Lap1), `=`=同タイム, `-`=減速(Lap2<Lap1)

### 5.2 好タイム基準（4Fタイム）

| 場所 | 種別 | 基準 |
|-----|------|------|
| 美浦 | 坂路 (HC) | **52.9秒以下** |
| 栗東 | 坂路 (HC) | **53.9秒以下** |
| 美浦/栗東 | コース (WC) | **52.2秒以下** |

### 5.3 timeRank（好タイム種別）

| 値 | 意味 |
|----|------|
| 坂 | 坂路で好タイムあり |
| コ | コースで好タイムあり |
| 両 | 坂路・コース両方で好タイムあり |
| "" | 好タイムなし |

### 5.4 追切期間の定義

レース開催日から逆算：

| 期間 | 曜日 | 説明 |
|------|------|------|
| **最終追切** (final) | 水・木 | レース週の本追切 |
| **土日追切** (weekend) | 金・土・日 | 最終と1週前の間 |
| **1週前追切** (weekAgo) | 前週水・木 | 先週の追切 |

---

## 6. WebViewer表示

### 6.1 TrainingAnalysisSection 表示列

コンポーネント: `web/src/components/race-v2/TrainingAnalysisSection.tsx`

| 列 | ソース | 表示内容 |
|----|--------|---------|
| 枠・番・馬名 | entry | 基本情報 |
| 調教師 | entry + trainer_patterns | 名前 + パターン★ |
| **今走調教** | **CK_DATA** (training_summary) | 最終/土日/1週前のラップランク |
| 脚色 | **keibabook** (oikiri_summary) | 一杯/末強/強め/馬なり |
| 併 | **keibabook** (oikiri_summary) | 併せ馬の有無 |
| 前走調教 | CK_DATA (前走training_summary) | 前走の調教詳細 |
| 評価 | **keibabook** (training_arrow) | ↑ ↗ → ↘ ↓ |
| 短評・解説 | **keibabook** (training_data) | 短評テキスト |

### 6.2 色分けルール

**ラップランクの色**:
- SS: yellow, S系: teal, A系: cyan, B系: blue, C系: orange, D系: red
- サフィックス `+`: 明るめ, `-`: 暗め

**脚色の色**:
- 一杯: 赤(太字), 末強: 橙(太字), 強め: 琥珀, 馬なり: 緑, ゲート: 灰

**矢印の色**:
- ↑/↗: 緑, →: 灰, ↘/↓: 赤

---

## 7. ML特徴量

### 7.1 現在のML特徴量（keibabook由来）

ファイル: `ml/features/training_features.py`

| 特徴量 | 型 | 範囲 | ソース |
|--------|-----|------|--------|
| training_arrow_value | int | -2〜2 | kb_ext.training_arrow_value |
| oikiri_5f | float | 40〜80+ | cyokyo_detail.oikiri_summary |
| oikiri_3f | float | 30〜50+ | cyokyo_detail.oikiri_summary |
| oikiri_1f | float | 10〜15+ | cyokyo_detail.oikiri_summary |
| oikiri_intensity_code | int | -1〜4 | cyokyo_detail.oikiri_summary |
| oikiri_has_awase | int | -1, 0, 1 | cyokyo_detail.oikiri_summary |
| training_session_count | int | -1〜20+ | cyokyo_detail.oikiri_summary |
| rest_weeks | int | -1〜10+ | cyokyo_detail.rest_period |
| oikiri_is_slope | int | -1, 0, 1 | cyokyo_detail.oikiri_course |
| kb_mark_point | float | 0〜50+ | kb_ext.mark_point |
| kb_aggregate_mark_point | float | 0〜100+ | kb_ext.aggregate_mark_point |
| kb_rating | float | 0〜100+ | kb_ext.rating |

**デフォルト値**: データ欠損時は `-1` / `-1.0` / `None`

### 7.2 未使用（CK_DATA由来、v4.9で追加予定）

| 候補特徴量 | 型 | ソース | 期待される効果 |
|-----------|-----|--------|-------------|
| ck_lap_rank_score | int | training_summary.lapRank | ラップ加速度の定量評価 |
| ck_final_time4f | float | training_summary.finalTime4F | 最終追切タイム |
| ck_final_lap1 | float | training_summary.finalLap1 | 終いのラップ |
| ck_final_is_slope | int | training_summary.finalLocation | 追切場所（坂/コ） |
| ck_has_good_time | int | training_summary.timeRank | 好タイムの有無 |
| ck_weekago_rank_score | int | training_summary.weekAgoLap | 1週前の仕上がり |

---

## 8. 処理パイプライン

### 8.1 TypeScript (CK_DATA → training_summary)

```
target-training-reader.ts
  ├── getTrainingDataForDate(dateStr)     # 指定日の全WC/HCファイルを読み込み
  │     ├── parseWcRecordFromText()       # WC(コース) → recordType:'course'
  │     └── parseHcRecordFromText()       # HC(坂路) → recordType:'sakamichi'
  ├── enrichTrainingRecordsWithHorseNames()  # 馬名付加 (SE/UM/master JSON)
  ├── generateTrainingSummary(baseDateStr)   # 2週間分を集計
  │     ├── calculateLapRank()            # SS〜D- 分類
  │     ├── calculateTimeRank()           # 好タイム種別
  │     └── generateTrainingDetail()      # テキスト詳細
  └── 保存 → training_summary.json

training-summary-reader.ts
  ├── getTrainingSummaryMap(date)          # 読込 or lazy生成
  ├── getPreviousTrainingBatch()           # 前走調教一括取得
  └── findKettoNumFromRecentTraining()     # 馬名→kettoNum逆引き
```

### 8.2 Python (keibabook → kb_ext)

```
scraper.py → batch_scraper.py            # HTML取得
cyokyo_parser.py                         # HTML解析
  ├── parse_cyokyo_html()                # セッション配列抽出
  └── extract_oikiri_summary()           # 追切サマリー計算
cyokyo_enricher.py                       # kb_ext JSONに統合
  └── enrich_kb_ext(kb_ext_path, html)   # race_id_12でマッチ
```

### 8.3 バッチ処理

| 操作 | エンドポイント | 説明 |
|------|-------------|------|
| training_summary一括生成 | POST `/api/admin/batch-training-summary` | SSEストリーミング |
| 生成状況確認 | GET `/api/admin/batch-training-summary` | 未生成日付リスト |
| keibabook調教付加 | `python -m keibabook.cyokyo_enricher --year 2025` | CLI |

---

## 9. ID体系の対応

| 対象 | JRA-VAN (CK_DATA) | keibabook | 備考 |
|------|-------------------|-----------|------|
| レースID | 16桁 (`YYYYMMDDJJKKNNRR`) | 12桁 (`YYYYMMDDNNRR`) | 場所コード体系が異なる |
| 馬ID | 10桁 ketto_num | 7桁 horse_code | 別体系、変換不可 |
| 馬名 | KettoNum→SE/UM/master検索 | HTMLから直接取得 | 馬名でマッチ |

### 場所コードの違い

| 場所 | JRA-VAN | keibabook |
|------|---------|-----------|
| 東京 | 05 | 06 |
| 中山 | 06 | 01 |
| 阪神 | 09 | 03 |
| 京都 | 08 | 04 |

変換は venue_name（日本語）経由で行う。

---

## 10. 既知の問題と対応履歴

| Session | 問題 | 修正 |
|---------|------|------|
| 19 | 美浦('0')レコードが無視されていた | RecordType filter修正 |
| 19 | WC/HCのバイトオフセットずれ | 全オフセット修正 |
| 19 | 馬名解決でSE_DATAのみ参照 | UM_DATA + master JSONフォールバック追加 |
| **20** | **WC/HCのrecordTypeが逆** | **WC→course, HC→sakamichi に修正** |
| **20** | **HC offset 23をtime5fとして読み近似** | **time4f直接値に修正** |

---

## 11. 今後の拡張計画

### v4.9: CK_DATA lapRankをML特徴量化
- training_summary.jsonの構造化データをPythonから参照
- lapRank score(0-16)、finalTime4F、finalLap1等をfeature化
- experiment_v3.pyにレース内確率正規化を同時追加

### 将来構想
- keibabookコース名とCK_DATAファイル種別のクロスチェック（品質検証）
- 調教パターン分析（週前→最終のrank変化パターン）
- 調教師別の仕上げパターン特徴量
