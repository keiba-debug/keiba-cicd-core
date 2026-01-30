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
| 0 | 1 | RecordType | レコード種別（固定） | `0` |
| 1-8 | 8 | ChokyoDate | 調教年月日 (YYYYMMDD) | `20260124` |
| 9-12 | 4 | ChokyoTime | 調教時刻 (HHMM) | `0500` |
| 13-22 | 10 | KettoNum | 血統登録番号（馬ID） | `2020104764` |
| 23-26 | 4 | Reserved | 予約領域 | - |
| 27 | 1 | Reserved | 予約領域 | - |
| 28-30 | 3 | Time4F | 4Fタイム（0.1秒単位） | `680` = 68.0秒 |
| 31-33 | 3 | Time3F | 3Fタイム（0.1秒単位） | `495` = 49.5秒 |
| 34-37 | 4 | Reserved | 予約領域 | - |
| 38-40 | 3 | LapTime2 | ラップ2F-1F（0.1秒単位） | `142` = 14.2秒 |
| 41-43 | 3 | LapTime1 | ラップ1F（0.1秒単位） | `143` = 14.3秒 |
| 44-46 | 3 | CRLF | 改行コード | `\r\n` |

**実例**:

```
02026010206572020101174066316804951670328164164
```

解析結果:
- 日付: 20260102
- 時刻: 0657
- 馬ID: 2020101174
- 4F: 68.0秒
- 3F: 49.5秒
- Lap2: 14.2秒
- Lap1: 14.3秒

### WC（コース調教）- 47バイト形式

| 位置 | サイズ | フィールド | 説明 | 例 |
|-----|-------|----------|------|-----|
| 0 | 1 | RecordType | レコード種別（固定） | `1` |
| 1-8 | 8 | ChokyoDate | 調教年月日 (YYYYMMDD) | `20260124` |
| 9-12 | 4 | ChokyoTime | 調教時刻 (HHMM) | `0600` |
| 13-22 | 10 | KettoNum | 血統登録番号（馬ID） | `2020104764` |
| 23-26 | 4 | Time5F | 5Fタイム（0.1秒単位） | - |
| 27-30 | 4 | Time4F | 4Fタイム（0.1秒単位） | `530` = 53.0秒 |
| 31-34 | 4 | Time3F | 3Fタイム（0.1秒単位） | `390` = 39.0秒 |
| 35-37 | 3 | Unknown | 不明 | - |
| 38-40 | 3 | LapTime2 | ラップ2F-1F（0.1秒単位） | `130` = 13.0秒 |
| 41-43 | 3 | LapTime1 | ラップ1F（0.1秒単位） | `125` = 12.5秒 |

**注意**: WCには`Lap4`と`Lap3`がないため、パース時は`0.0`で埋める

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
