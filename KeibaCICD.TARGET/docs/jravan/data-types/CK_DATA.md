# CK_DATA: 調教データ仕様書

JRA-VAN CK_DATAの解析・活用のための詳細仕様書

## 📋 概要

**CK_DATA**は馬の調教履歴データで、坂路調教とコース調教の2種類があります。

- **用途**: 調教分析、追切評価、出走前の仕上がり判定
- **更新頻度**: 毎日（調教実施後）
- **データ形式**: Shift-JIS テキストファイル（固定長レコード）

## 📂 ファイル構造

### ディレクトリ構成

```
{JV_DATA_ROOT_DIR}/CK_DATA/
└── {年}/
    └── {年月}/
        ├── HC0{YYYYMMDD}.DAT  # 美浦・坂路
        ├── HC1{YYYYMMDD}.DAT  # 栗東・坂路
        ├── WC0{YYYYMMDD}.DAT  # 美浦・コース
        └── WC1{YYYYMMDD}.DAT  # 栗東・コース
```

### ファイル命名規則

| プレフィックス | トレセン | 調教種別 | 例 |
|-------------|---------|---------|-----|
| HC0 | 美浦 | 坂路 | HC020260124.DAT |
| HC1 | 栗東 | 坂路 | HC120260124.DAT |
| WC0 | 美浦 | コース | WC020260124.DAT |
| WC1 | 栗東 | コース | WC120260124.DAT |

## 📊 レコード構造

### HC（坂路調教）- 47バイト形式

実際のTARGETデータで使用されている形式:

| 位置 | サイズ | フィールド | 説明 | 例 |
|-----|-------|----------|------|-----|
| 0 | 1 | RecordType | レコード種別（固定） | `1` |
| 1-8 | 8 | ChokyoDate | 調教年月日 (YYYYMMDD) | `20260204` |
| 9-12 | 4 | ChokyoTime | 調教時刻 (HHMM) | `0752` |
| 13-22 | 10 | KettoNum | 血統登録番号（馬ID） | `2023106359` |
| 23-26 | 4 | Time4F | 4Fタイム（0.1秒単位） | `0549` = 54.9秒 |
| 27-29 | 3 | Lap4 | ラップ4F-3F（0.1秒単位） | `145` = 14.5秒 |
| 30-33 | 4 | Time3F | 3Fタイム（0.1秒単位） | `0404` = 40.4秒 |
| 34-36 | 3 | Lap3 | ラップ3F-2F（0.1秒単位） | `138` = 13.8秒 |
| 37-40 | 4 | Time2F | 2Fタイム（0.1秒単位） | `0266` = 26.6秒 |
| 41-43 | 3 | Lap2 | ラップ2F-1F（0.1秒単位） | `136` = 13.6秒 |
| 44-46 | 3 | Lap1 | ラップ1F（0.1秒単位） | `130` = 13.0秒 |

**実例（ワイドアルバ 2026-02-04 栗東坂路）**:

```
12026020407522023106359054914504041380266136130
```

解析結果:
- 日付: 20260204
- 時刻: 0752
- 馬ID: 2023106359（ワイドアルバ）
- 4F: 54.9秒
- Lap4: 14.5秒
- 3F: 40.4秒
- Lap3: 13.8秒
- 2F: 26.6秒
- Lap2: 13.6秒
- Lap1: 13.0秒

**ラップタイム計算**:
- Lap4 = Time4F - Time3F = 54.9 - 40.4 = 14.5秒
- Lap3 = Time3F - Time2F = 40.4 - 26.6 = 13.8秒
- Lap2 = Time2F - Lap1 = 26.6 - 13.0 = 13.6秒

### WC（コース調教）- 92バイト形式

実際のTARGETデータで使用されている形式:

| 位置 | サイズ | フィールド | 説明 | 例 |
|-----|-------|----------|------|-----|
| 0 | 1 | RecordType | レコード種別（固定） | `0` |
| 1-8 | 8 | ChokyoDate | 調教年月日 (YYYYMMDD) | `20260205` |
| 9-12 | 4 | ChokyoTime | 調教時刻 (HHMM) | `0805` |
| 13-22 | 10 | KettoNum | 血統登録番号（馬ID） | `2023103073` |
| 23-60 | 38 | Reserved | 予約領域 | - |
| 61-64 | 4 | Time5F | 5Fタイム（0.1秒単位） | `0665` = 66.5秒 |
| 65-67 | 3 | Lap5 | ラップ5F-4F（0.1秒単位） | `139` = 13.9秒 |
| 68-71 | 4 | Time4F | 4Fタイム（0.1秒単位） | `0526` = 52.6秒 |
| 72-74 | 3 | Lap4 | ラップ4F-3F（0.1秒単位） | `130` = 13.0秒 |
| 75-78 | 4 | Time3F | 3Fタイム（0.1秒単位） | `0396` = 39.6秒 |
| 79-81 | 3 | Lap3 | ラップ3F-2F（0.1秒単位） | `131` = 13.1秒 |
| 82-85 | 4 | Time2F | 2Fタイム（0.1秒単位） | `0265` = 26.5秒 |
| 86-88 | 3 | Lap2 | ラップ2F-1F（0.1秒単位） | `129` = 12.9秒 |
| 89-91 | 3 | Lap1 | ラップ1F（0.1秒単位） | `136` = 13.6秒 |

**実例（カゼノハゴロモ 2026-02-05 美浦コース）**:

```
02026020508052023103073310000000000000000000000000000008551900665139052613003961310265129136
```

解析結果:
- 日付: 20260205
- 時刻: 0805
- 馬ID: 2023103073（カゼノハゴロモ）
- 5F: 66.5秒
- Lap5: 13.9秒
- 4F: 52.6秒
- Lap4: 13.0秒
- 3F: 39.6秒
- Lap3: 13.1秒
- 2F: 26.5秒
- Lap2: 12.9秒
- Lap1: 13.6秒

**ラップタイム計算**:
- Lap4 = Time4F - Time3F = 52.6 - 39.6 = 13.0秒
- Lap3 = Time3F - Time2F = 39.6 - 26.5 = 13.1秒
- Lap2 = Time2F - Lap1 = 26.5 - 13.6 = 12.9秒

## 🔧 データアクセス

### 基本的な読み込み

```python
from pathlib import Path
from common.jravan.ck_parser import parse_ck_file

# ファイルパス
ck_file = Path("E:/TFJV/CK_DATA/2026/202601/HC020260124.DAT")

# パース
records = parse_ck_file(ck_file)

for record in records:
    print(f"{record.date} {record.time} {record.center}{record.location}")
    print(f"  4F={record.time_4f:.1f}s  1F={record.lap_1:.1f}s")
```

### 馬の調教履歴取得

```python
from common.jravan import analyze_horse_training

# 馬ID と レース日を指定
result = analyze_horse_training(
    horse_id="2020104764",
    race_date="20260125",
    days_back=14
)

# 最終追切
if result.get("final"):
    final = result["final"]
    print(f"最終追切: {final['date']} {final['center']}{final['location']}")
    print(f"  4F={final['time_4f']:.1f}s [{final['speed_class']}]")

# 全調教履歴
for rec in result["all_records"]:
    print(f"{rec['date']} {rec['center']}{rec['location']} 4F={rec['time_4f']:.1f}s")
```

## 📈 調教評価指標

### 好タイム基準

| トレセン | 場所 | 4F基準 | ラップ基準 |
|---------|------|--------|----------|
| 美浦 | 坂路 | 52.9秒 | 13.4秒 |
| 栗東 | 坂路 | 53.9秒 | 13.9秒 |
| 美浦 | コース | 52.2秒 | 12.6秒 |
| 栗東 | コース | 52.2秒 | 12.8秒 |

### スピード分類

基準値からの差分でクラス分け:

| クラス | 条件 | 説明 |
|-------|------|------|
| S | 基準 - 2.0秒以下 | 好タイム |
| A | 基準以下 | やや好タイム |
| B | 基準 + 2.0秒以下 | 標準 |
| C | 基準 + 4.0秒以下 | やや遅め |
| D | 基準 + 4.0秒超 | 遅い |

### ラップ評価

終い1Fのラップ + 加速記号:

| 加速記号 | 条件 | 説明 |
|---------|------|------|
| + | Lap1 < Lap2 - 0.3秒 | 加速 |
| = | -0.3秒 ≤ 差分 ≤ +0.3秒 | 同じ |
| - | Lap1 > Lap2 + 0.3秒 | 減速 |

**例**: `A+` = やや好ラップ＋加速

### SS評価（最高ランク）

`upgraded_lap_class`プロパティによる自動昇格:

| 条件 | 結果 |
|------|------|
| 好タイム AND `lap_class == "S+"` | `upgraded_lap_class = "SS"` |
| 好タイム AND `lap_class == "S="` | `upgraded_lap_class = "SS"` |
| 上記以外 | `upgraded_lap_class = lap_class`（変化なし） |

**SS評価の意味**:
- 4Fタイムが好タイム基準以下（例：美浦坂路なら52.9秒以下）
- かつ、終い1Fのラップが基準-1.5秒以下（S分類）
- かつ、加速（+）または同タイム（=）

**例**:
- 美浦坂路で4F=52.0秒、Lap1=11.8秒、Lap2=12.2秒 → `lap_class="S+"` → `upgraded_lap_class="SS"` ⭐
- 美浦坂路で4F=53.5秒、Lap1=11.8秒、Lap2=12.2秒 → `lap_class="S+"` → `upgraded_lap_class="S+"`（好タイムでないのでSSに昇格しない）
- 美浦坂路で4F=52.0秒、Lap1=11.9秒、Lap2=11.5秒 → `lap_class="S-"` → `upgraded_lap_class="S-"`（減速なのでSSに昇格しない）

### 調教本数評価

14日間の調教本数:

| 本数 | ラベル | 評価 |
|-----|--------|------|
| 8本以上 | 多 | 充実 |
| 4-7本 | 普 | 標準 |
| 3本以下 | 少 | 不足 |

## 🎯 実用例

### 最終追切チェック

レース当週の水曜・木曜の調教（最終追切）を確認:

```python
result = analyze_horse_training("2020104764", "20260125")

if result["final"]:
    final = result["final"]
    # 好タイムかチェック
    if final["is_good_time"]:
        print("✓ 好タイムで仕上げ")
    # 加速しているかチェック
    if final["acceleration"] == "+":
        print("✓ 終いに加速")
```

### 土日追切チェック

前週の土日に強い調教を行ったかチェック:

```python
if result["weekend"]:
    weekend = result["weekend"]
    if weekend["time_4f"] <= 52.0:
        print("✓ 前週土日に強い調教")
```

### 調教パターン分類

```python
# 調教本数
count_label = result["count_label"]  # "多" / "普" / "少"

# タイム分類
time_class = result["time_class"]
# "両" = 坂路もコースも好タイム
# "坂" = 坂路のみ好タイム
# "コ" = コースのみ好タイム
# "" = 好タイムなし

print(f"調教: 本数[{count_label}] タイム[{time_class}]")
```

## 🔍 トラブルシューティング

### ファイルが見つからない

```python
from common.config import get_jv_ck_data_path

ck_root = get_jv_ck_data_path()
print(f"CK_DATAパス: {ck_root}")

# 環境変数を確認
import os
print(f"JV_DATA_ROOT_DIR: {os.getenv('JV_DATA_ROOT_DIR')}")
```

### 馬の調教データが0件

1. **馬IDが正しいか確認**:
   ```python
   from common.jravan import get_horse_id_by_name
   horse_id = get_horse_id_by_name("ドウデュース")
   ```

2. **調教ファイルが存在するか確認**:
   ```python
   from common.jravan.ck_parser import get_recent_training_files
   files = get_recent_training_files("20260125", 14)
   print(f"Found {len(files)} files")
   ```

3. **デバッグモードで詳細確認**:
   ```powershell
   $env:CK_DEBUG = "1"
   python scripts/parse_ck_data.py --horse 2020104764 --date 20260125
   ```

### 坂路とコースの判定がおかしい

ファイル名の先頭2文字（`HC`, `WC`）で判定しています。ファイル名が正しいか確認:

```powershell
ls E:\TFJV\CK_DATA\2026\202601\*.DAT
```

## 📚 関連リソース

### プロジェクト内

- [parse_ck_data.py](../../../scripts/parse_ck_data.py) - CK_DATAパーサー実装
- [共通設定](../../../common/config.py) - パス管理
- [ID変換](../ID_MAPPING.md) - 馬ID変換方法

### CLI使用例

```powershell
# 馬の調教データ取得
python scripts/parse_ck_data.py --horse 2020104764 --date 20260125 --days 14

# JSON形式で出力
python scripts/parse_ck_data.py --horse 2020104764 --date 20260125 --json

# フォーマット解析（デバッグ用）
python scripts/parse_ck_data.py --debug --file "E:\TFJV\CK_DATA\2026\202601\HC020260124.DAT"
```

---

*最終更新: 2026-01-30*
