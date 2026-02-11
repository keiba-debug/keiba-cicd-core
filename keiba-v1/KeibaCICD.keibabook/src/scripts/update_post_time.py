#!/usr/bin/env python3
"""
既存の統合JSONファイルにpost_timeを追加するスクリプト
"""

import json
import glob
from pathlib import Path
from src.utils.post_time_mapping import get_estimated_post_time

def update_json_with_post_time(json_file_path):
    """統合JSONファイルにpost_timeを追加"""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # race_infoにpost_timeを追加
        if 'race_info' in data:
            race_number = data['race_info'].get('race_number', 0)
            if race_number:
                post_time = get_estimated_post_time(race_number)
                data['race_info']['post_time'] = post_time
                
                # ファイルを更新
                with open(json_file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                return True, post_time
        
        return False, None
        
    except Exception as e:
        print(f"Error processing {json_file_path}: {e}")
        return False, None

def main():
    # 8/23の統合JSONファイルを全て取得
    json_files = glob.glob('Z:/KEIBA-CICD/data/organized/2025/08/23/*/integrated_*.json')
    
    success = 0
    failed = 0
    
    print(f"Found {len(json_files)} integrated JSON files")
    
    for json_file in json_files:
        updated, post_time = update_json_with_post_time(json_file)
        
        if updated:
            success += 1
            race_id = Path(json_file).stem.replace('integrated_', '')
            print(f"  [OK] {race_id}: post_time={post_time}")
        else:
            failed += 1
            print(f"  [SKIP] {json_file}")
    
    print(f"\nResults: {success} updated, {failed} skipped out of {len(json_files)} total")

if __name__ == "__main__":
    main()