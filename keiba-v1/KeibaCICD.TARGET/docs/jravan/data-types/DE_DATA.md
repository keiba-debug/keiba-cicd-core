# DE_DATA: 出馬表データ仕様書

JRA-VAN DE_DATAの解析・活用のための詳細仕様書

## 📋 概要

**DE_DATA**はレース前の出馬表情報を格納したファイルです。

- **用途**: レース情報取得、発走時刻、出走馬一覧、オッズ情報
- **更新頻度**: 毎日（レース前日～当日）
- **データ形式**: Shift-JIS テキストファイル（可変長レコード）
- **主要レコード**: RA（レース情報）, SE（出走馬情報）

## 📂 ファイル構造

### ディレクトリ構成

```
{JV_DATA_ROOT_DIR}/DE_DATA/
└── {年}/
    └── DR{YYYYMMDD}.DAT  # 日付ごとの出馬表
```

### ファイル命名規則

| ファイル名 | 説明 | 例 |
|----------|------|-----|
| DR{YYYYMMDD}.DAT | 指定日の出馬表 | DR20260124.DAT |

## 📊 レコード構造

### RAレコード（レース情報）

**レコード長**: 約751バイト（可変）

| 位置 (0-based) | サイズ | フィールド | 説明 | 例 |
|---------------|-------|----------|------|-----|
| 0-1 | 2 | RecordType | レコード種別 | `RA` |
| 11-14 | 4 | Year | 開催年 | `2026` |
| 15-18 | 4 | MonthDay | 開催月日 (MMDD) | `0124` |
| 19-20 | 2 | JyoCD | 競馬場コード (01-10) | `06` |
| 21-22 | 2 | Kaiji | 回次 | `01` |
| 23-24 | 2 | Nichiji | 日次 | `02` |
| 25-26 | 2 | RaceNum | レース番号 (01-12) | `08` |
| 27-86 | 60 | RaceName | レース名 | `東京新聞杯` |
| -17~-13 | 4 | HassoTime | 発走時刻 (HHMM) | `1550` |

**注意**:
- レコードIDは offset 11-26 の16バイト
- 発走時刻は末尾から17番目から4桁（HHMM形式）

### SEレコード（出走馬情報）

**レコード長**: 約800バイト（可変）

| 位置 | サイズ | フィールド | 説明 | 例 |
|-----|-------|----------|------|-----|
| 0-1 | 2 | RecordType | レコード種別 | `SE` |
| 11-26 | 16 | RaceID | レースID | `2026012406010208` |
| 27-28 | 2 | Umaban | 馬番 | `01` |
| 29-30 | 2 | Wakuban | 枠番 | `1` |
| 31-40 | 10 | KettoNum | 血統登録番号（馬ID） | `2019103487` |
| ... | ... | ... | その他（騎手、馬体重など） | - |

## 🔧 データアクセス

### レース情報取得

```python
from common.jravan.race_parser import get_race_times_for_date

# 指定日のレース発走時刻を取得
race_times = get_race_times_for_date("2026-01-24")

for track, races in race_times.items():
    print(f"[{track}競馬場]")
    for race in races:
        print(f"  {race['race_num']:2d}R {race['hasso_time']} {race['race_name']}")
```

### レースIDの構築

```python
from common.jravan.race_id import build_race_id

# レースIDを構築
race_id = build_race_id(
    year=2026,
    month=1,
    day=24,
    track_code="06",  # 中山
    kaiji=1,
    nichiji=2,
    race_num=8
)
# => "2026012406010208"
```

### race_info.jsonへの発走時刻追加

```python
from common.jravan.race_parser import update_race_info_json

# 競馬ブックのrace_info.jsonに発走時刻を追加
updated_count = update_race_info_json(
    date_str="2026-01-24",
    race_times=race_times,
    dry_run=False
)

print(f"{updated_count} レースの発走時刻を更新")
```

## 🎯 実用例

### 当日のレース発走時刻取得

```powershell
cd KeibaCICD.TARGET
python scripts/parse_jv_race_data.py --date 2026-01-24
```

出力例:
```
[DATE] 2026-01-24 の発走時刻一覧
============================================================

[TRACK] 中山競馬場 (12レース)
----------------------------------------
   1R  10:10  3歳未勝利
   2R  10:45  3歳未勝利
   ...
   8R  15:50  東京新聞杯
```

### race_info.jsonの更新

```powershell
python scripts/parse_jv_race_data.py --date 2026-01-24 --update-race-info
```

## 🔍 トラブルシューティング

### DRファイルが見つからない

```python
from common.config import get_jv_de_data_path

de_path = get_jv_de_data_path()
print(f"DE_DATAパス: {de_path}")

# ファイル確認
import os
dr_file = de_path / "2026" / "DR20260124.DAT"
print(f"存在: {os.path.exists(dr_file)}")
```

### 発走時刻が正しく取得できない

発走時刻は末尾から-17~-13の4桁です。レコード長が不足している場合があります。

```python
# デバッグモード
$env:JV_DEBUG = "1"
python scripts/parse_jv_race_data.py --date 2026-01-24 --verbose
```

## 📚 関連リソース

### プロジェクト内

- [parse_jv_race_data.py](../../../scripts/parse_jv_race_data.py) - DE_DATAパーサー
- [update_race_start_times.py](../../../scripts/update_race_start_times.py) - 発走時刻更新ツール
- [ID変換](../ID_MAPPING.md) - レースID変換

### CLI使用例

```powershell
# レース情報取得
python scripts/parse_jv_race_data.py --date 2026-01-24

# JSON出力
python scripts/parse_jv_race_data.py --date 2026-01-24 --output race_times.json

# race_info.json更新（ドライラン）
python scripts/parse_jv_race_data.py --date 2026-01-24 --update-race-info --dry-run

# race_info.json更新（実行）
python scripts/parse_jv_race_data.py --date 2026-01-24 --update-race-info
```

---

*最終更新: 2026-01-30*
