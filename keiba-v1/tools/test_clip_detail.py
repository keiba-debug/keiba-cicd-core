# -*- coding: utf-8 -*-
"""クリップボード出力（調教詳細）のテスト"""
import subprocess
import sys

base_dir = "Z:/KEIBA-CICD/調教データ"
script = f"{base_dir}/training_summary.py"
sakamichi = f"{base_dir}/chokyo_251228_坂路.csv"
course = f"{base_dir}/chokyo_251228_コース.csv"
output_txt = f"{base_dir}/test_output.txt"

print("=== クリップボード出力（馬名・調教詳細）===")
cmd = [
    sys.executable, script,
    "--sakamichi", sakamichi,
    "--course", course,
    "--date", "20251229",
    "--output", output_txt,
    "--clip-detail"
]
result = subprocess.run(cmd, capture_output=True, text=True, encoding='cp932')
print(result.stdout)
if result.returncode != 0:
    print(f"Error: {result.stderr}")

print("\n=== クリップボードの内容を確認（先頭5行）===")
# Windowsでクリップボードの内容を取得
import subprocess
clip_result = subprocess.run(['powershell', '-command', 'Get-Clipboard'], 
                             capture_output=True, text=True, encoding='cp932')
lines = clip_result.stdout.strip().split('\n')
for i, line in enumerate(lines[:5]):
    print(f"  {line}")
print(f"\n  ... 合計 {len(lines)} 行")
