#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""出力ファイルの検証"""

import sys

def main():
    filepath = "keiba-cicd-core/tools/output_test.txt"
    output_filepath = "keiba-cicd-core/tools/verify_result.txt"
    
    with open(filepath, "r", encoding="cp932") as f:
        lines = f.readlines()
    
    result = []
    result.append(f"Total lines: {len(lines)}")
    result.append("\n=== Header ===")
    result.append(lines[0].rstrip())
    
    result.append("\n=== Sample data (first 10 horses) ===")
    for line in lines[1:11]:
        parts = line.rstrip().split("\t")
        if len(parts) >= 4:
            result.append(f"馬名: {parts[0]}")
            result.append(f"  調教師: {parts[1]}")
            result.append(f"  調教分類: {parts[2]}")
            result.append(f"  調教詳細: {parts[3]}")
            result.append("")
    
    # UTF-8で書き出し
    with open(output_filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(result))
    
    print(f"Result written to: {output_filepath}")

if __name__ == "__main__":
    main()
