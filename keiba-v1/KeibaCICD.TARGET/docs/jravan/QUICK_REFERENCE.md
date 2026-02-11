# JRA-VANライブラリ クイックリファレンス

よく使う機能の一覧表

## 🔑 ID変換

| 関数 | 説明 | 例 |
|-----|------|-----|
| `get_horse_id_by_name(name)` | 馬名 → JRA-VAN 10桁ID | `get_horse_id_by_name("ドウデュース")` |
| `get_horse_name_by_id(id)` | ID → 馬名 | `get_horse_name_by_id("2019103487")` |
| `get_track_code(name)` | 競馬場名 → コード | `get_track_code("中山")` → `"06"` |
| `get_track_name(code)` | コード → 競馬場名 | `get_track_name("06")` → `"中山"` |
| `get_trainer_jvn_code(kb_id)` | 厩舎ID → JRA-VAN調教師コード | `get_trainer_jvn_code("ｳ011")` → `"01234"` |
| `get_trainer_info(kb_id)` | 厩舎ID → 調教師情報 | `get_trainer_info("ｳ011")` |

## 📊 データ取得

| 関数 | 説明 | 例 |
|-----|------|-----|
| `get_horse_info(identifier)` | 馬の基本情報 | `get_horse_info("ドウデュース")` |
| `analyze_horse_training(identifier, date)` | 調教データ分析 | `analyze_horse_training("ドウデュース", "20260125")` |
| `get_training_data(id, date, days_back)` | 調教データ取得（IDのみ） | `get_training_data("2019103487", "20260125")` |

## 🏇 レースID操作

| 関数 | 説明 | 例 |
|-----|------|-----|
| `build_race_id(...)` | レースID構築 | `build_race_id(2026, 1, 24, "06", 1, 2, 8)` |
| `parse_race_id(race_id)` | レースIDパース | `parse_race_id("2026012406010208")` |
| `format_race_id_human(race_id)` | 人間が読みやすい形式 | `format_race_id_human("2026012406010208")` |

## 📋 調教データ構造

```python
{
    "horse_id": "2019103487",
    "race_date": "20260125",
    "total_count": 8,           # 調教本数
    "count_label": "多",         # 本数評価 (多/普/少)
    "time_class": "両",          # タイム分類 (両/坂/コ/なし)
    "has_good_time": True,      # 好タイムあり
    "n_sakamichi": 5,           # 坂路本数
    "n_course": 3,              # コース本数
    "final": {                  # 最終追切（当週水・木）
        "date": "20260123",
        "time": "0600",
        "center": "栗東",
        "location": "坂路",
        "time_4f": 51.2,
        "lap_1": 12.8,
        "speed_class": "A",
        "lap_class": "A+",
        "is_good_time": True
    },
    "weekend": {...},           # 土日追切（前週土・日）
    "week_ago": {...},          # 一週前追切（前週水・木）
    "all_records": [...]        # 全調教履歴
}
```

## 🏇 馬情報構造

```python
{
    "horse_id": "2019103487",
    "name": "ドウデュース",
    "name_kana": "ドウデュース",
    "name_eng": "Do Deuce",
    "birth_date": "20190412",
    "sex": "牡",
    "age": 6,
    "tozai": "栗東",
    "trainer_code": "01234",
    "trainer_name": "友道康夫",
    "owner_name": "（株）Ｇ1レーシング",
    "breeder_name": "ノーザンファーム",
    "is_active": True
}
```

## 🎯 スピード/ラップ分類

### スピード分類（4Fタイム）

| クラス | 説明 | 基準からの差 |
|-------|------|-------------|
| S | 好タイム | -2.0秒以下 |
| A | やや好タイム | 0秒以下 |
| B | 標準 | +2.0秒以下 |
| C | やや遅め | +4.0秒以下 |
| D | 遅い | +4.0秒超 |

### ラップ分類（終い1F）

| 記号 | 説明 | 条件 |
|-----|------|------|
| + | 加速 | Lap1 < Lap2 - 0.3秒 |
| = | 同じ | 差分が±0.3秒以内 |
| - | 減速 | Lap1 > Lap2 + 0.3秒 |

## 🏁 競馬場コード

| コード | 競馬場 | コード | 競馬場 |
|-------|--------|-------|--------|
| 01 | 札幌 | 06 | 中山 |
| 02 | 函館 | 07 | 中京 |
| 03 | 福島 | 08 | 京都 |
| 04 | 新潟 | 09 | 阪神 |
| 05 | 東京 | 10 | 小倉 |

## 💻 よく使うインポート

```python
from common.jravan import (
    # ID変換
    get_horse_id_by_name,
    get_horse_name_by_id,
    get_track_code,
    get_track_name,
    # 調教師ID変換
    get_trainer_jvn_code,
    get_trainer_info,
    # データ取得
    get_horse_info,
    analyze_horse_training,
    # レースID
    build_race_id,
    parse_race_id,
)
```

## 🚀 ワンライナー

```python
# 馬名から調教データ取得
from common.jravan import analyze_horse_training
training = analyze_horse_training("ドウデュース", "20260125")

# 最終追切の評価
final = training.get("final")
print(f"{final['time_4f']:.1f}s [{final['speed_class']}]" if final else "なし")

# 馬の基本情報
from common.jravan import get_horse_info
info = get_horse_info("ドウデュース")
print(f"{info['name']} ({info['sex']}{info['age']}歳) {info['trainer_name']}")

# レースID構築
from common.jravan import build_race_id
race_id = build_race_id(2026, 1, 24, "中山", 1, 2, 8)
```

## 🔧 セットアップコマンド

```powershell
# 初回セットアップ（馬名インデックス構築）
cd E:\share\KEIBA-CICD\_keiba\keiba-cicd-core\KeibaCICD.TARGET
python scripts/horse_id_mapper.py --build-index

# インデックス情報表示
python scripts/horse_id_mapper.py --info

# 馬名検索
python scripts/horse_id_mapper.py --name "ドウデュース"

# 調教師インデックス構築（初期版は手動マッピング）
python scripts/build_trainer_index.py --build-index

# 調教師インデックス情報表示
python scripts/build_trainer_index.py --info
```

## 📚 ドキュメント

- [README](./README.md) - 概要
- [使用ガイド](./USAGE_GUIDE.md) - 実践例
- [ID変換仕様](./ID_MAPPING.md) - ID変換の詳細
- [CK_DATA仕様](./data-types/CK_DATA.md) - 調教データ
- [UM_DATA仕様](./data-types/UM_DATA.md) - 馬マスタ

---

*最終更新: 2026-01-30*
