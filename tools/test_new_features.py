# -*- coding: utf-8 -*-
"""新機能のテスト"""
import subprocess
import sys

base_dir = "Z:/KEIBA-CICD/調教データ"
script = f"{base_dir}/training_summary.py"
sakamichi = f"{base_dir}/chokyo_251228_坂路.csv"
course = f"{base_dir}/chokyo_251228_コース.csv"
output_txt = f"{base_dir}/test_output.txt"
output_xlsx = f"{base_dir}/test_output.xlsx"

print("=== テスト1: 通常のテキスト出力 ===")
cmd1 = [
    sys.executable, script,
    "--sakamichi", sakamichi,
    "--course", course,
    "--date", "20251229",
    "--output", output_txt
]
result1 = subprocess.run(cmd1, capture_output=True, text=True, encoding='cp932')
print(result1.stdout)
if result1.returncode != 0:
    print(f"Error: {result1.stderr}")

print("\n=== テスト2: クリップボード出力（馬名・調教分類）===")
cmd2 = [
    sys.executable, script,
    "--sakamichi", sakamichi,
    "--course", course,
    "--date", "20251229",
    "--output", output_txt,
    "--clip-class"
]
result2 = subprocess.run(cmd2, capture_output=True, text=True, encoding='cp932')
print(result2.stdout)
if result2.returncode != 0:
    print(f"Error: {result2.stderr}")

print("\n=== テスト3: Excel出力 ===")
cmd3 = [
    sys.executable, script,
    "--sakamichi", sakamichi,
    "--course", course,
    "--date", "20251229",
    "--output", output_xlsx,
    "--excel"
]
result3 = subprocess.run(cmd3, capture_output=True, text=True, encoding='cp932')
print(result3.stdout)
if result3.returncode != 0:
    print(f"Error: {result3.stderr}")

# ファイル確認
import os
print("\n=== 出力ファイル確認 ===")
for f in [output_txt, output_xlsx]:
    if os.path.exists(f):
        size = os.path.getsize(f)
        print(f"  {os.path.basename(f)}: {size} bytes ✅")
    else:
        print(f"  {os.path.basename(f)}: 見つかりません ❌")
