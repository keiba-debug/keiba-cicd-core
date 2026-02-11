# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "Z:/KEIBA-CICD/調教データ")

from training_summary import (
    aggregate_horse_data,
    read_sakamichi_csv,
    read_course_csv,
)
from datetime import datetime

# 基準日
base_date = datetime(2025, 12, 28)

# CSVを読み込み
sakamichi_records = read_sakamichi_csv("Z:/KEIBA-CICD/調教データ/chokyo_251227_坂路.csv")
course_records = read_course_csv("Z:/KEIBA-CICD/調教データ/chokyo_251227_コース.csv")

print(f"坂路データ: {len(sakamichi_records)}件")
print(f"コースデータ: {len(course_records)}件")

# 集計
result = aggregate_horse_data(sakamichi_records, course_records, base_date)

print(f"集計結果: {len(result)}頭")
print()

# ゴキゲンサンを探す
if "ゴキゲンサン" in result:
    print("=== ゴキゲンサンの集計結果 ===")
    goki = result["ゴキゲンサン"]
    for k, v in goki.items():
        print(f"  {k}: {v}")
else:
    print("【ゴキゲンサンが集計結果に含まれていない！】")
    
    # 名前が微妙に違う可能性を確認
    print("\n類似する馬名を検索:")
    for name in result.keys():
        if "ゴキゲン" in name or "サン" in name:
            print(f"  - {name}")
