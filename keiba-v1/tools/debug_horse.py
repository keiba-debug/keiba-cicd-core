#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""特定の馬のデータを調べる"""

import glob
import csv
from datetime import datetime

horse_name = "ゴキゲンサン"
output_file = "keiba-cicd-core/tools/debug_result.txt"
base_date = datetime(2025, 12, 28)

results = []

# CSVを探す
csv_files = glob.glob('Z:/KEIBA-CICD/*/*.csv')
sakamichi_file = None
course_file = None
for f in csv_files:
    if '251227' in f:
        if '坂路' in f:
            sakamichi_file = f
        elif 'コース' in f:
            course_file = f

results.append(f"=== 検索対象: {horse_name} ===\n")
results.append(f"基準日: {base_date.strftime('%Y-%m-%d')}\n\n")

all_records = []

# 坂路CSV
if sakamichi_file:
    results.append(f"坂路CSV: {sakamichi_file}\n")
    with open(sakamichi_file, 'r', encoding='cp932') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if horse_name in row.get('馬名', ''):
                rec = {
                    'source': '坂路',
                    'date_str': row.get('年月日', ''),
                    'weekday': row.get('曜日', ''),
                    'lap2': row.get('Lap2', ''),
                    'lap1': row.get('Lap1', ''),
                }
                all_records.append(rec)

# コースCSV
if course_file:
    results.append(f"コースCSV: {course_file}\n")
    with open(course_file, 'r', encoding='cp932') as file:
        reader = csv.DictReader(file)
        for row in reader:
            if horse_name in row.get('馬名', ''):
                rec = {
                    'source': 'コース',
                    'date_str': row.get('年月日', ''),
                    'weekday': row.get('曜日', ''),
                    'lap2': row.get('Lap2', ''),
                    'lap1': row.get('Lap1', ''),
                }
                all_records.append(rec)

results.append(f"\n=== {horse_name} のデータ ({len(all_records)}件) ===\n")

# 水木判定
def is_wed_thu(weekday):
    return weekday in ('水', '木')

# 分類判定（新ルール: S > A > B > C > D）
def classify(lap2_str, lap1_str):
    try:
        lap2 = float(lap2_str) if lap2_str else None
        lap1 = float(lap1_str) if lap1_str else None
        if lap2 is None or lap1 is None:
            return None, "データなし"
        
        if lap2 > lap1:
            direction = "+"
        elif lap2 < lap1:
            direction = "-"
        else:
            direction = "="
        
        def get_level(lap):
            if lap < 12.0:
                return 1  # 11秒台以下
            elif lap < 13.0:
                return 2  # 12秒台
            else:
                return 3  # 13秒台以上
        
        lap2_level = get_level(lap2)
        lap1_level = get_level(lap1)
        
        # S: Lap2が11秒台以下 AND Lap1が11秒台以下
        if lap2_level == 1 and lap1_level == 1:
            return f"S{direction}", f"Lap2={lap2}, Lap1={lap1}"
        # A: Lap1が11秒台以下 AND Lap2が12秒台以上
        elif lap1_level == 1 and lap2_level >= 2:
            return f"A{direction}", f"Lap2={lap2}, Lap1={lap1}"
        # B: Lap2が12秒台 AND Lap1が12秒台
        elif lap2_level == 2 and lap1_level == 2:
            return f"B{direction}", f"Lap2={lap2}, Lap1={lap1}"
        # C: Lap1が12秒台 AND (Lap2が11秒台以下 or 13秒台以上)
        elif lap1_level == 2 and (lap2_level == 1 or lap2_level == 3):
            return f"C{direction}", f"Lap2={lap2}, Lap1={lap1}"
        # D: Lap1が13秒台以上
        elif lap1_level == 3:
            return f"D{direction}", f"Lap2={lap2}, Lap1={lap1}"
        else:
            return None, f"分類不可: Lap2={lap2}, Lap1={lap1}"
    except:
        return None, "エラー"

wed_thu_count = 0
other_count = 0

for rec in all_records:
    classification, detail = classify(rec['lap2'], rec['lap1'])
    is_wed_thu_flag = is_wed_thu(rec['weekday'])
    
    if is_wed_thu_flag:
        wed_thu_count += 1
    else:
        other_count += 1
    
    results.append(f"  日付: {rec['date_str']} ({rec['weekday']}) - {rec['source']}\n")
    results.append(f"    分類: {classification} ({detail})\n")
    results.append(f"    水木: {'Yes' if is_wed_thu_flag else 'No'}\n\n")

results.append(f"\n=== 集計 ===\n")
results.append(f"水・木のデータ: {wed_thu_count}件\n")
results.append(f"その他のデータ: {other_count}件\n")

if wed_thu_count == 0:
    results.append("\n→ 水・木がないため、直近2回のデータが出力対象\n")
    # 日付降順でソート
    all_records.sort(key=lambda x: x['date_str'], reverse=True)
    results.append("直近2回:\n")
    for rec in all_records[:2]:
        classification, detail = classify(rec['lap2'], rec['lap1'])
        results.append(f"  {rec['date_str']} ({rec['weekday']}) {rec['source']}: {classification}\n")

# 結果をファイルに書き込み
with open(output_file, 'w', encoding='utf-8') as f:
    f.writelines(results)

print(f"結果を {output_file} に出力しました")
