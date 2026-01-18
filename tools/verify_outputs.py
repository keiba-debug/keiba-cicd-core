# -*- coding: utf-8 -*-
import os

base_dir = "Z:/KEIBA-CICD/調教データ"
files = [
    f"{base_dir}/test_output.txt",
    f"{base_dir}/test_output.xlsx"
]

print("=== 出力ファイル確認 ===")
for f in files:
    if os.path.exists(f):
        size = os.path.getsize(f)
        print(f"  {os.path.basename(f)}: {size} bytes [OK]")
    else:
        print(f"  {os.path.basename(f)}: 見つかりません [NG]")

# テキストファイルの内容確認
print("\n=== テキストファイル内容（先頭5行）===")
txt_path = f"{base_dir}/test_output.txt"
with open(txt_path, 'r', encoding='cp932') as f:
    for i, line in enumerate(f):
        if i >= 5:
            break
        print(f"  {line.rstrip()}")

# ゴキゲンサン確認
print("\n=== ゴキゲンサン確認 ===")
with open(txt_path, 'r', encoding='cp932') as f:
    for line in f:
        if 'ゴキゲンサン' in line:
            print(f"  {line.strip()}")
            break
