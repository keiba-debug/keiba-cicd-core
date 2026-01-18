#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""新しい分類ロジックのテスト（SS分類・調教タイム分類）"""

import subprocess
import sys
import os

# 調教データフォルダへ移動
os.chdir(r"Z:\KEIBA-CICD\調教データ")

# テスト実行
result = subprocess.run([
    sys.executable,
    "training_summary.py",
    "--sakamichi", "chokyo_坂路.csv",
    "--course", "chokyo_コース.csv",
    "--date", "20251228",
    "--output", "test_output.txt"
], capture_output=True, text=True, encoding='cp932')

print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)
print(f"Exit code: {result.returncode}")

# 出力ファイルの内容を確認
if result.returncode == 0:
    print("\n=== 出力ファイルの先頭10行 ===")
    with open("test_output.txt", "r", encoding="cp932") as f:
        for i, line in enumerate(f):
            if i >= 10:
                break
            print(line.rstrip())
    
    print("\n=== SS分類の馬 ===")
    with open("test_output.txt", "r", encoding="cp932") as f:
        lines = f.readlines()
        ss_count = 0
        for line in lines[1:]:
            parts = line.strip().split("\t")
            if len(parts) >= 3 and parts[2] == "SS":
                print(f"{parts[0]}: {parts[2]} / {parts[3]} / {parts[4] if len(parts) > 4 else ''}")
                ss_count += 1
        print(f"\nSS分類の馬: {ss_count}頭")
    
    print("\n=== 調教タイム分類の分布 ===")
    with open("test_output.txt", "r", encoding="cp932") as f:
        lines = f.readlines()
        time_dist = {"坂": 0, "コ": 0, "両": 0, "－": 0}
        for line in lines[1:]:
            parts = line.strip().split("\t")
            if len(parts) >= 4:
                time_class = parts[3]
                if time_class in time_dist:
                    time_dist[time_class] += 1
        for k, v in time_dist.items():
            print(f"  {k}: {v}頭")
