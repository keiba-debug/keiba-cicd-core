# -*- coding: utf-8 -*-
import csv

csv_path = r"Y:\TXT\PCI中山ダート1200.csv"

with open(csv_path, encoding="cp932") as f:
    reader = csv.reader(f)
    headers = next(reader)
    
    print(f"列数: {len(headers)}")
    print()
    
    # 関連する列を表示
    print("=== 関連列 ===")
    for i, h in enumerate(headers):
        if any(k in h for k in ["着", "PCI", "ID", "印"]):
            print(f"  {i:3d}: {h}")
    
    print()
    print("=== サンプルデータ (3行) ===")
    for j, row in enumerate(reader):
        if j >= 3:
            break
        print(f"行{j+1}:")
        print(f"  列0 (確定着順?): {row[0]}")
        print(f"  列26 (PCI?): {row[26]}")
        print(f"  列120 (レースID?): {row[120] if len(row) > 120 else 'N/A'}")
        print()
