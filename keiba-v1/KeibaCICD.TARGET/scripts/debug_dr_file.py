#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""DRファイルのフォーマットを確認するデバッグスクリプト"""

import os
from pathlib import Path

DR_FILE = Path("Y:/DE_DATA/2026/DR20260124.DAT")

def main():
    if not DR_FILE.exists():
        print(f"File not found: {DR_FILE}")
        return
    
    content = DR_FILE.read_bytes()
    lines = content.split(b'\r\n')
    
    print(f"Total lines: {len(lines)}")
    print("=" * 80)
    
    for i, line in enumerate(lines[:10]):
        if len(line) < 10:
            continue
            
        decoded = line.decode('shift_jis', errors='replace')
        
        print(f"\n--- Line {i+1} (length: {len(decoded)}) ---")
        print(f"First 2 bytes: '{decoded[:2]}'")
        print(f"Content preview: {decoded[:120]}")
        
        # RAレコードの場合、発走時刻を探す
        if decoded.startswith("RA"):
            # offset 873 (0-based index for offset 874)
            if len(decoded) > 880:
                hasso_section = decoded[870:880]
                print(f"HassoTime area (offset 870-880): '{hasso_section}'")
            
            # レースIDを確認
            print(f"RACE_ID area (offset 12-28): '{decoded[11:27]}'")
            
            # 末尾を確認（発走時刻がある場所を探す）
            last_part = decoded[-50:]
            print(f"Last 50 chars: '{last_part}'")

if __name__ == "__main__":
    main()
