#!/usr/bin/env python3
"""
全会場のMDファイルを再生成
"""

import json
import os
from src.integrator.markdown_generator import MarkdownGenerator

# 対象日付
date_str = "20250824"
venues = ["札幌", "新潟", "中京"]

generator = MarkdownGenerator()
total_count = 0
success_count = 0

for venue in venues:
    integrated_dir = f"Z:/KEIBA-CICD/data/organized/2025/08/24/{venue}"
    
    if not os.path.exists(integrated_dir):
        print(f"{venue}: ディレクトリが存在しません")
        continue
    
    json_files = [f for f in os.listdir(integrated_dir) if f.startswith('integrated_') and f.endswith('.json')]
    print(f"{venue}: {len(json_files)}レース")
    
    for json_file in json_files:
        total_count += 1
        json_path = os.path.join(integrated_dir, json_file)
        
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                race_data = json.load(f)
            
            # MDファイルを生成
            generator.generate_race_markdown(race_data, save=True)
            success_count += 1
        except Exception as e:
            print(f"  エラー: {json_file} - {e}")

print(f"\n=== 完了 ===")
print(f"合計: {total_count}レース")
print(f"成功: {success_count}レース")
print(f"成功率: {success_count/total_count*100:.1f}%")