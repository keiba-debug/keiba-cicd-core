# -*- coding: utf-8 -*-
import csv

# コースCSVを読み込んでゴキゲンサンを探す
csv_path = "Z:/KEIBA-CICD/調教データ/chokyo_251227_コース.csv"

print(f"CSVファイル: {csv_path}")
print("=" * 60)

with open(csv_path, "r", encoding="cp932") as f:
    reader = csv.DictReader(f)
    print(f"カラム: {reader.fieldnames}")
    print()
    
    count = 0
    for row in reader:
        horse_name = row.get("馬名", "")
        if "ゴキゲンサン" in horse_name:
            count += 1
            print(f"Row {count}: {row}")
            print(f"  馬名: '{horse_name}'")
            print(f"  Lap2: '{row.get('Lap2', '')}', Lap1: '{row.get('Lap1', '')}'")
            print()

print(f"\nゴキゲンサンのデータ: {count}件")
