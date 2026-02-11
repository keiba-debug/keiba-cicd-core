#!/usr/bin/env python3
"""
レースID情報を詳細に分析するスクリプト
"""

import json
from pathlib import Path

def main():
    # プロジェクトルートからの相対パス
    project_root = Path(__file__).parent.parent.parent.parent
    data_file = project_root / 'data' / 'keibabook' / 'race_ids' / '20250607_info.json'
    
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print('=== レース日程取得結果 ===')
    print(f'日付: {data["date"]}')
    print(f'開催数: {data.get("kaisai_count", len(data["kaisai_data"]))}')
    print(f'総レース数: {data.get("total_races", 0)}')

    print('\n=== 開催場所別レース数 ===')
    for venue, races in data['kaisai_data'].items():
        print(f'{venue}: {len(races)}レース')
        for i, race in enumerate(races[:3]):
            print(f'  {race["race_no"]}: {race["race_name"]} (ID: {race["race_id"]})')
        if len(races) > 3:
            print(f'  ... 他{len(races)-3}レース')

    print('\n=== 全レースID一覧 ===')
    all_race_ids = []
    for venue, races in data['kaisai_data'].items():
        for race in races:
            all_race_ids.append(race['race_id'])

    print(f'レースID総数: {len(all_race_ids)}')
    print('レースID:', ', '.join(all_race_ids))

if __name__ == '__main__':
    main() 