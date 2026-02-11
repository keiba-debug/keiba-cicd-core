#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""発走時刻の位置を特定するデバッグスクリプト"""

from pathlib import Path

DR_FILE = Path("Y:/DE_DATA/2026/DR20260124.DAT")

def main():
    content = DR_FILE.read_bytes()
    lines = content.split(b'\r\n')
    
    # 最初の3行を詳しく解析
    for i, line in enumerate(lines[:3]):
        if len(line) < 10:
            continue
            
        decoded = line.decode('shift_jis', errors='replace')
        
        # RACE_ID を表示
        race_id = decoded[11:27]
        print(f"Line {i+1}: RACE_ID = {race_id}")
        
        # 末尾50文字を1文字ずつ表示
        last50 = decoded[-50:]
        print(f"  Last 50 chars: '{last50}'")
        
        # 4桁の数字パターンを探す
        for j in range(len(last50) - 3):
            chunk = last50[j:j+4]
            if chunk.isdigit():
                hour = int(chunk[:2])
                minute = int(chunk[2:])
                # 妥当な時刻かチェック
                if 6 <= hour <= 18 and 0 <= minute <= 59:
                    # 末尾からの位置を計算
                    pos_from_end = 50 - j
                    print(f"  Found time candidate: '{chunk}' at index -{pos_from_end} (={hour}:{minute:02d})")
        
        print()

if __name__ == "__main__":
    main()
