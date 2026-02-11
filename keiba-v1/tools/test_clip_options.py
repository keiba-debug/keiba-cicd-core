#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""クリップボードオプションのテスト"""

import subprocess
import sys
import os

os.chdir(r"Z:\KEIBA-CICD\調教データ")

print("=== --clip-lap テスト ===")
result = subprocess.run([
    sys.executable,
    "training_summary.py",
    "--sakamichi", "chokyo_坂路.csv",
    "--course", "chokyo_コース.csv",
    "--date", "20251228",
    "--output", "test_output.txt",
    "--clip-lap"
], capture_output=True, text=True, encoding='cp932')
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

print("\n=== --clip-time テスト ===")
result = subprocess.run([
    sys.executable,
    "training_summary.py",
    "--sakamichi", "chokyo_坂路.csv",
    "--course", "chokyo_コース.csv",
    "--date", "20251228",
    "--output", "test_output.txt",
    "--clip-time"
], capture_output=True, text=True, encoding='cp932')
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

print("\n=== --clip-detail テスト ===")
result = subprocess.run([
    sys.executable,
    "training_summary.py",
    "--sakamichi", "chokyo_坂路.csv",
    "--course", "chokyo_コース.csv",
    "--date", "20251228",
    "--output", "test_output.txt",
    "--clip-detail"
], capture_output=True, text=True, encoding='cp932')
print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)

print("\n=== ヘルプ表示テスト ===")
result = subprocess.run([
    sys.executable,
    "training_summary.py",
    "--help"
], capture_output=True, text=True, encoding='cp932')
# オプション部分のみ表示
lines = result.stdout.split('\n')
for line in lines:
    if '--clip' in line:
        print(line)
