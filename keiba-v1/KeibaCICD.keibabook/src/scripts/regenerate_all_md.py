#!/usr/bin/env python3
"""
統合JSONから全MDファイルを再生成するスクリプト
"""

import json
import glob
from pathlib import Path
from src.integrator.markdown_generator import MarkdownGenerator

def main():
    # ジェネレータ初期化
    generator = MarkdownGenerator(use_organized_dir=True)
    
    # 8/23の統合JSONファイルを全て取得
    json_files = glob.glob('Z:/KEIBA-CICD/data/organized/2025/08/23/*/integrated_*.json')
    
    success = 0
    failed = 0
    
    print(f"Found {len(json_files)} integrated JSON files")
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                race_data = json.load(f)
            
            # Markdown生成
            generator.generate_race_markdown(race_data, save=True)
            success += 1
            race_id = race_data.get('meta', {}).get('race_id', 'unknown')
            print(f"  [OK] {race_id}")
            
        except Exception as e:
            failed += 1
            print(f"  [ERROR] {json_file}: {e}")
    
    print(f"\nResults: {success} success, {failed} failed out of {len(json_files)} total")

if __name__ == "__main__":
    main()