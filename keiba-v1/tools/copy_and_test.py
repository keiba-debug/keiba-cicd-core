#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
調教データスクリプトのコピーとテスト
"""

import shutil
import glob
import os
import subprocess
import sys


def main():
    # 調教データフォルダ内のファイルを探す
    py_files = glob.glob('Z:/KEIBA-CICD/*/*.py')
    csv_files = glob.glob('Z:/KEIBA-CICD/*/*.csv')
    
    print("=== Found files ===")
    for f in py_files:
        print(f"  PY: {f}")
    for f in csv_files:
        print(f"  CSV: {f}")
    
    # training_summary.pyを探してコピー（test_ではないもの）
    training_script = None
    for py_path in py_files:
        basename = os.path.basename(py_path)
        if 'training_summary' in basename and not basename.startswith('test_'):
            training_script = py_path
            break
    
    if not training_script:
        print("Error: training_summary.py not found")
        return 1
    
    # CSVファイルを判別
    sakamichi_csv = None
    course_csv = None
    
    for csv_path in csv_files:
        with open(csv_path, "rb") as f:
            first_line = f.readline()
            if b"Time1,Time2,Time3,Time4,Lap4" in first_line:
                sakamichi_csv = csv_path
            elif b"5F,4F,3F,2F,1F,Lap5" in first_line:
                course_csv = csv_path
    
    print(f"\n=== Identified files ===")
    print(f"  Script: {training_script}")
    print(f"  Sakamichi: {sakamichi_csv}")
    print(f"  Course: {course_csv}")
    
    # テスト実行
    output_path = "keiba-cicd-core/tools/output_test.txt"
    cmd = [sys.executable, training_script, "--date", "20251228", "--output", output_path]
    
    if sakamichi_csv:
        cmd.extend(["--sakamichi", sakamichi_csv])
    if course_csv:
        cmd.extend(["--course", course_csv])
    
    print(f"\n=== Executing ===")
    print(f"  {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    
    # 結果をファイルに書き込む
    log_path = "keiba-cicd-core/tools/test_log.txt"
    with open(log_path, "w", encoding="utf-8") as log:
        log.write("=== stdout ===\n")
        log.write(result.stdout or "(empty)")
        log.write("\n\n=== stderr ===\n")
        log.write(result.stderr or "(empty)")
        log.write(f"\n\nExit code: {result.returncode}\n")
    
    print(f"Log written to: {log_path}")
    print(f"Exit code: {result.returncode}")
    
    # 出力ファイルを確認
    if os.path.exists(output_path):
        print(f"\n=== Output file ===")
        with open(output_path, "r", encoding="cp932", errors="replace") as f:
            lines = f.readlines()
            for i, line in enumerate(lines[:20]):
                print(f"{i+1}: {line.rstrip()}")
            if len(lines) > 20:
                print(f"... ({len(lines)} lines total)")
    
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
