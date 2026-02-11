# -*- coding: utf-8 -*-
import sys
sys.path.insert(0, "Z:/KEIBA-CICD/調教データ")

from training_summary import (
    get_training_periods,
    read_course_csv,
    classify_lap,
    get_classification_priority,
    is_wednesday_or_thursday,
    SPECIAL_WEEKDAY_CLASSES
)
from datetime import datetime

# 基準日
base_date = datetime(2025, 12, 28)

# 期間計算
final_dates, one_week_dates = get_training_periods(base_date)
final_date_set = set(d.date() for d in final_dates)
one_week_date_set = set(d.date() for d in one_week_dates)

print(f"基準日: {base_date}")
print(f"最終期間(date): {final_date_set}")
print(f"一週前期間(date): {one_week_date_set}")
print()

# コースCSVを読み込み
course_records = read_course_csv("Z:/KEIBA-CICD/調教データ/chokyo_251227_コース.csv")
print(f"コースデータ読込: {len(course_records)}件")
print()

# ゴキゲンサンのデータを探す
print("=== ゴキゲンサンのレコード ===")
for rec in course_records:
    if "ゴキゲンサン" in rec.get("horse_name", ""):
        rec_date = rec["date"].date()
        is_wed_thu = is_wednesday_or_thursday(rec["date"])
        in_final = rec_date in final_date_set
        in_one_week = rec_date in one_week_date_set
        in_special = rec["classification"] in SPECIAL_WEEKDAY_CLASSES if rec["classification"] else False
        
        print(f"  日付: {rec['date_str']} ({rec_date})")
        print(f"    分類: {rec['classification']}, 優先度: {rec['priority']}")
        print(f"    水木: {is_wed_thu}")
        print(f"    final_date_set含む: {in_final}")
        print(f"    one_week_date_set含む: {in_one_week}")
        print(f"    SPECIAL_WEEKDAY_CLASSES: {in_special}")
        
        # 判定結果
        if in_final:
            print(f"    → final_dataに追加される")
        elif in_one_week:
            print(f"    → one_week_dataに追加される")
        elif not is_wed_thu and in_special:
            print(f"    → other_dataに追加される")
        else:
            print(f"    → 【どこにも追加されない！】")
        print()
