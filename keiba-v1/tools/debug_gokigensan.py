# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "Z:/KEIBA-CICD/調教データ")

from training_summary import (
    get_training_periods, 
    classify_lap,
    parse_date,
    is_wednesday_or_thursday
)
from datetime import datetime

# 基準日
base_date = datetime(2025, 12, 28)
print(f"基準日: {base_date}")

# 期間計算
final_dates, one_week_dates = get_training_periods(base_date)
print(f"最終追い切り期間: {[d.strftime('%Y-%m-%d') for d in final_dates]}")
print(f"一週前期間: {[d.strftime('%Y-%m-%d') for d in one_week_dates]}")

# ゴキゲンサンのデータ
print("\n=== ゴキゲンサンのコースデータ ===")
gokigen_data = [
    ("20251224", 12.5, 11.2),  # 12/24 水曜
    ("20251217", 12.3, 11.5),  # 12/17 水曜
]

for date_str, lap2, lap1 in gokigen_data:
    d = parse_date(date_str)
    classification = classify_lap(lap2, lap1)
    is_final = d in final_dates
    is_one_week = d in one_week_dates
    is_wed_thu = is_wednesday_or_thursday(d)
    
    print(f"  {date_str}: Lap2={lap2}, Lap1={lap1}")
    print(f"    分類: {classification}")
    print(f"    水木: {is_wed_thu}, 最終: {is_final}, 一週前: {is_one_week}")
