#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""馬名でCSVを検索する"""

import glob
import csv
import sys

horse_name = "ゴキゲンサン"

print(f"=== 検索対象: {horse_name} ===\n")

# CSVファイルを探す
csv_files = glob.glob('Z:/KEIBA-CICD/*/*.csv')

found_in_sakamichi = []
found_in_course = []

for f in csv_files:
    if '251227' not in f:
        continue
    
    try:
        with open(f, 'r', encoding='cp932') as file:
            reader = csv.reader(file)
            header = next(reader, None)
            
            # 馬名のカラムインデックスを探す
            horse_idx = None
            if header:
                for i, col in enumerate(header):
                    if '馬名' in col:
                        horse_idx = i
                        break
            
            if horse_idx is None:
                horse_idx = 3  # デフォルト
            
            for row in reader:
                if len(row) > horse_idx and horse_name in row[horse_idx]:
                    if '坂路' in f:
                        found_in_sakamichi.append((f, row))
                    elif 'コース' in f:
                        found_in_course.append((f, row))
                    else:
                        print(f"Found in {f}: {row}")
    except Exception as e:
        print(f"Error reading {f}: {e}")

print(f"=== 坂路CSV ===")
if found_in_sakamichi:
    for f, row in found_in_sakamichi:
        print(f"  日付: {row[1] if len(row) > 1 else 'N/A'}")
        print(f"  曜日: {row[2] if len(row) > 2 else 'N/A'}")
        print(f"  馬名: {row[3] if len(row) > 3 else 'N/A'}")
        print(f"  調教師: {row[4] if len(row) > 4 else 'N/A'}")
        print(f"  Lap2: {row[10] if len(row) > 10 else 'N/A'}")
        print(f"  Lap1: {row[11] if len(row) > 11 else 'N/A'}")
        print()
else:
    print("  見つかりませんでした")

print(f"\n=== コースCSV ===")
if found_in_course:
    for f, row in found_in_course:
        print(f"  日付: {row[3] if len(row) > 3 else 'N/A'}")
        print(f"  曜日: {row[4] if len(row) > 4 else 'N/A'}")
        print(f"  馬名: {row[5] if len(row) > 5 else 'N/A'}")
        print(f"  調教師: {row[6] if len(row) > 6 else 'N/A'}")
        print(f"  Lap2: {row[15] if len(row) > 15 else 'N/A'}")
        print(f"  Lap1: {row[16] if len(row) > 16 else 'N/A'}")
        print()
else:
    print("  見つかりませんでした")

print("\n=== 出力ファイル確認 ===")
try:
    with open('keiba-cicd-core/tools/output_test.txt', 'r', encoding='cp932') as f:
        for line in f:
            if horse_name in line:
                print(f"  出力に含まれています: {line.strip()}")
                break
        else:
            print(f"  出力に含まれていません")
except Exception as e:
    print(f"  Error: {e}")
