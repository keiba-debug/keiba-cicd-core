#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""新ロジックで水木以外が優先された馬を確認"""

import os

os.chdir(r"Z:\KEIBA-CICD\調教データ")

# 出力ファイルを確認
with open("test_output.txt", "r", encoding="cp932") as f:
    lines = f.readlines()

print(f"出力行数: {len(lines)}")
print("\n=== 水木以外の曜日が調教詳細に含まれる馬 ===")

weekday_markers = ["(月)", "(火)", "(金)", "(土)", "(日)"]
count = 0
for line in lines[1:]:  # 全件
    parts = line.strip().split("\t")
    if len(parts) >= 4:
        detail = parts[3]
        for marker in weekday_markers:
            if marker in detail:
                print(f"{parts[0]}: {parts[2]} - {detail}")
                count += 1
                break

print(f"\n合計: {count}件")
