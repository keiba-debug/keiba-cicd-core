# JRA-VANライブラリ使用ガイド

`common.jravan`モジュールの実践的な使用例

## 🚀 クイックスタート

### 1. セットアップ（初回のみ）

```powershell
cd E:\share\KEIBA-CICD\_keiba\keiba-cicd-core\KeibaCICD.TARGET

# 馬名インデックスを構築（約1分）
python scripts/horse_id_mapper.py --build-index
```

### 2. 基本的な使い方

```python
from common.jravan import (
    get_horse_id_by_name,
    get_horse_info,
    analyze_horse_training,
)

# 馬名からJRA-VAN IDに変換
horse_id = get_horse_id_by_name("ドウデュース")
print(horse_id)  # => "2019103487"

# 馬の基本情報を取得
info = get_horse_info("ドウデュース")
print(f"{info['name']} ({info['sex']}{info['age']}歳) {info['trainer_name']}")

# 調教データを取得
training = analyze_horse_training("ドウデュース", "20260125")
if training["final"]:
    final = training["final"]
    print(f"最終追切: {final['date']} {final['center']}{final['location']}")
    print(f"4F={final['time_4f']:.1f}s [{final['speed_class']}]")
```

## 📚 実用パターン集

### パターン1: 競馬ブックのレース出走馬に調教データを紐付け

```python
from common.jravan import get_horse_id_by_name, analyze_horse_training

# 競馬ブックから取得した出走馬リスト
horses_from_keibabook = [
    {"name": "ドウデュース", "umaban": 1},
    {"name": "イクイノックス", "umaban": 2},
    {"name": "ジャスティンパレス", "umaban": 3},
]

race_date = "20260125"

for horse in horses_from_keibabook:
    # 馬名→JRA-VAN IDに変換
    jvn_id = get_horse_id_by_name(horse["name"])

    if jvn_id:
        # 調教データ取得
        training = analyze_horse_training(jvn_id, race_date)

        # 最終追切の評価
        if training.get("final"):
            final = training["final"]
            horse["training"] = {
                "date": final["date"],
                "place": f"{final['center']}{final['location']}",
                "time_4f": final["time_4f"],
                "speed_class": final["speed_class"],
                "lap_class": final["lap_class"],
                "is_good": final["is_good_time"],
            }
            print(f"{horse['umaban']:2d}番 {horse['name']}: {horse['training']}")
        else:
            print(f"{horse['umaban']:2d}番 {horse['name']}: 調教データなし")
    else:
        print(f"{horse['umaban']:2d}番 {horse['name']}: JRA-VAN IDが見つかりません")
```

### パターン2: 複数馬の調教傾向を比較

```python
from common.jravan import analyze_horse_training

horses = ["ドウデュース", "イクイノックス", "ジャスティンパレス"]
race_date = "20260125"

print("馬名               | 本数 | タイム | 最終追切")
print("-" * 60)

for horse_name in horses:
    training = analyze_horse_training(horse_name, race_date)

    if "error" in training:
        print(f"{horse_name:15s} | データなし")
        continue

    # 調教本数
    count = training["total_count"]
    count_label = training["count_label"]

    # タイム分類
    time_class = training["time_class"] or "なし"

    # 最終追切
    final_info = "なし"
    if training.get("final"):
        final = training["final"]
        final_info = f"{final['center']}{final['location']} {final['time_4f']:.1f}s"

    print(f"{horse_name:15s} | {count:2d}本({count_label}) | {time_class:4s} | {final_info}")
```

### パターン3: レースIDを使ったデータ取得準備

```python
from common.jravan.race_id import build_race_id, parse_race_id, format_race_id_human

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

print(f"レースID: {race_id}")
# => "2026012406010208"

# レースIDをパース
info = parse_race_id(race_id)
print(f"競馬場: {info['track_name']}")
print(f"日付: {info['date']}")
print(f"レース番号: {info['race_num']}")

# 人間が読みやすい形式
print(format_race_id_human(race_id))
# => "2026年1月24日 中山 1回2日目 8R"
```

### パターン4: 競馬場コード変換

```python
from common.jravan import get_track_code, get_track_name

# 競馬場名→コード
code = get_track_code("中山")
print(code)  # => "06"

# コード→競馬場名
name = get_track_name("06")
print(name)  # => "中山"

# 全競馬場を列挙
from common.jravan.id_converter import TRACK_CODES

for code, name in TRACK_CODES.items():
    print(f"{code}: {name}")
```

### パターン5: 馬の基本情報を一括取得

```python
from common.jravan import get_horse_info

horses = ["ドウデュース", "イクイノックス", "ジャスティンパレス"]

print("馬名              | 性齢   | 所属 | 調教師")
print("-" * 60)

for horse_name in horses:
    info = get_horse_info(horse_name)

    if info:
        print(f"{info['name']:15s} | {info['sex']}{info['age']}歳 | {info['tozai']} | {info['trainer_name']}")
    else:
        print(f"{horse_name:15s} | データなし")
```

### パターン6: 調教データの詳細分析

```python
from common.jravan import analyze_horse_training

training = analyze_horse_training("ドウデュース", "20260125", days_back=14)

print(f"=== {training.get('horse_id', '')} の調教分析 ===\n")

# サマリー
print(f"調教本数: {training['total_count']}本 ({training['count_label']})")
print(f"タイム分類: {training['time_class'] or 'なし'}")
print(f"坂路: {training['n_sakamichi']}本 / コース: {training['n_course']}本")
print()

# 最終追切（当週水・木）
if training.get("final"):
    final = training["final"]
    print("■ 最終追切（当週水・木）")
    print(f"  {final['date']} {final['time']} {final['center']}{final['location']}")
    print(f"  4F={final['time_4f']:.1f}s [{final['speed_class']}]")
    print(f"  1F={final['lap_1']:.1f}s [{final['lap_class']}]")
    print(f"  好タイム: {'✓' if final['is_good_time'] else '×'}")
    print()

# 土日追切（前週土・日）
if training.get("weekend"):
    we = training["weekend"]
    print("■ 土日追切（前週土・日）")
    print(f"  {we['date']} {we['time']} {we['center']}{we['location']}")
    print(f"  4F={we['time_4f']:.1f}s [{we['speed_class']}]")
    print()

# 全調教履歴
print("■ 全調教履歴")
for rec in training["all_records"]:
    good_mark = "★" if rec["is_good_time"] else " "
    print(f"  {rec['date']} {rec['time']} {rec['center']}{rec['location']} "
          f"4F={rec['time_4f']:.1f}s [{rec['speed_class']}] "
          f"1F={rec['lap_1']:.1f}s [{rec['lap_class']}] {good_mark}")
```

## 🔍 エラーハンドリング

### 馬が見つからない場合

```python
from common.jravan import get_horse_id_by_name, get_horse_info

horse_name = "存在しない馬"

# ID変換
horse_id = get_horse_id_by_name(horse_name)
if horse_id is None:
    print(f"馬 '{horse_name}' が見つかりません")
    # 部分一致で検索
    from common.jravan.parsers import search_horses_by_name
    similar = search_horses_by_name(horse_name[:3])
    if similar:
        print("もしかして:")
        for h in similar[:5]:
            print(f"  - {h.name}")

# 馬情報取得
info = get_horse_info(horse_name)
if info is None:
    print(f"馬情報が見つかりません")
```

### 調教データがない場合

```python
from common.jravan import analyze_horse_training

training = analyze_horse_training("ドウデュース", "20260125")

if "error" in training:
    print(f"エラー: {training['error']}")
elif training["total_count"] == 0:
    print("調教データが見つかりません（期間内に調教なし）")
else:
    print(f"調教データ取得成功: {training['total_count']}本")
```

## 📦 バッチ処理例

### 出走馬全頭の調教レポート生成

```python
from common.jravan import analyze_horse_training
import json

# 出走馬リスト
horses = ["ドウデュース", "イクイノックス", "ジャスティンパレス"]
race_date = "20260125"

# レポート生成
report = {
    "race_date": race_date,
    "horses": []
}

for horse_name in horses:
    training = analyze_horse_training(horse_name, race_date)

    if "error" not in training:
        horse_report = {
            "name": horse_name,
            "horse_id": training.get("horse_id"),
            "training_count": training["total_count"],
            "count_label": training["count_label"],
            "time_class": training["time_class"],
        }

        if training.get("final"):
            horse_report["final"] = training["final"]

        report["horses"].append(horse_report)

# JSON出力
output_file = "training_report.json"
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(f"レポート出力完了: {output_file}")
```

## 🧪 デバッグTips

### インデックスの状態確認

```python
from common.jravan.id_converter import rebuild_index

# インデックス再構築（時間がかかる）
count = rebuild_index()
print(f"インデックス構築完了: {count} 頭")
```

### データソースの確認

```python
from common.config import (
    get_keiba_data_root,
    get_jv_data_root,
    get_jv_ck_data_path,
)

print(f"KEIBA_DATA_ROOT: {get_keiba_data_root()}")
print(f"JV_DATA_ROOT: {get_jv_data_root()}")
print(f"CK_DATA: {get_jv_ck_data_path()}")
```

## 📚 関連ドキュメント

- [JRA-VAN データ仕様書](./README.md)
- [ID変換仕様](./ID_MAPPING.md)
- [CK_DATA仕様](./data-types/CK_DATA.md)
- [UM_DATA仕様](./data-types/UM_DATA.md)

---

*最終更新: 2026-01-30*
