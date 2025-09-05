#!/usr/bin/env python3
"""
テスト用レース結果データを作成
"""

import json
import glob
import shutil

def add_test_results(json_file_path):
    """統合JSONファイルにテスト用の結果データを追加"""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # バックアップを作成
        backup_path = json_file_path.replace('.json', '_backup.json')
        shutil.copy2(json_file_path, backup_path)
        
        # テスト用の結果データを追加
        if 'entries' in data and len(data['entries']) > 0:
            # 上位3頭に結果を追加
            test_results = [
                {
                    'finish_position': '1',
                    'time': '2:01.5',
                    'margin': '',
                    'last_3f': '34.8',
                    'passing_orders': [3, 3, 3, 2],
                    'last_corner_position': '2'
                },
                {
                    'finish_position': '2',
                    'time': '2:01.7',
                    'margin': '1',
                    'last_3f': '35.1',
                    'passing_orders': [6, 6, 6, 5],
                    'last_corner_position': '5'
                },
                {
                    'finish_position': '3',
                    'time': '2:01.9',
                    'margin': '1',
                    'last_3f': '35.3',
                    'passing_orders': [8, 7, 7, 8],
                    'last_corner_position': '8'
                }
            ]
            
            for i, result in enumerate(test_results):
                if i < len(data['entries']):
                    data['entries'][i]['result'] = result
            
            # レースペース情報を追加
            if 'race_info' not in data:
                data['race_info'] = {}
            
            data['race_info']['race_pace'] = {
                'first3f': '35.8',
                'last3f': '36.2',
                'pace_label': 'ややスロー'
            }
            
            # 払戻情報を追加
            data['payouts'] = [
                {'type': 'tansho', 'combination': '9', 'amount': 1230, 'popularity': ''},
                {'type': 'fukusho', 'combination': '9', 'amount': 320, 'popularity': ''},
                {'type': 'fukusho', 'combination': '15', 'amount': 180, 'popularity': ''},
                {'type': 'umaren', 'combination': '9-15', 'amount': 4560, 'popularity': ''},
                {'type': 'wide', 'combination': '9-15', 'amount': 1230, 'popularity': ''},
                {'type': 'umatan', 'combination': '9-15', 'amount': 8950, 'popularity': ''},
                {'type': 'sanrenpuku', 'combination': '9-14-15', 'amount': 23400, 'popularity': ''},
                {'type': 'sanrentan', 'combination': '9-15-14', 'amount': 98200, 'popularity': ''}
            ]
            
            # ファイルを更新
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return True
        
        return False
        
    except Exception as e:
        print(f"Error processing {json_file_path}: {e}")
        return False

def main():
    # 最初の1つのJSONファイルにテストデータを追加
    json_files = glob.glob('Z:/KEIBA-CICD/data/organized/2025/08/23/*/integrated_*.json')
    
    if json_files:
        test_file = json_files[10]  # 11Rのファイルを選択
        print(f"Adding test results to: {test_file}")
        
        if add_test_results(test_file):
            print("Test results added successfully")
            print("Backup created with _backup.json suffix")
        else:
            print("Failed to add test results")
    else:
        print("No integrated JSON files found")

if __name__ == "__main__":
    main()