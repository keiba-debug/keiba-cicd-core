#!/usr/bin/env python3
"""
履歴特徴量機能のテスト（モックデータ使用）
"""

import json
from pathlib import Path
import glob

def create_mock_history_data():
    """テスト用の履歴データを作成"""
    
    # accumulated/horses ディレクトリを作成
    accumulated_path = Path("Z:/KEIBA-CICD/data/accumulated/horses")
    accumulated_path.mkdir(parents=True, exist_ok=True)
    
    # テスト用の馬ID（integrated JSONから取得）
    test_horses = [
        {"horse_id": "2021104361", "name": "ドラゴンウェルズ", "style": "先行", "value": "割安"},
        {"horse_id": "2021103903", "name": "エストレラブランカ", "style": "差し", "value": "やや割安"},
        {"horse_id": "2020106095", "name": "ナイトアクア", "style": "逃げ", "value": "妥当"}
    ]
    
    for horse in test_horses:
        horse_data = {
            "horse_id": horse["horse_id"],
            "updated_at": "2025-08-23T07:00:00",
            "history": [
                {
                    "date": "2025-08-01",
                    "finish_position": "2",
                    "last_3f": "35.2",
                    "passing_orders": [3, 3, 3, 2],
                    "course": "芝",
                    "distance": "2000",
                    "odds": "5.3",
                    "popularity": "3"
                },
                {
                    "date": "2025-07-15",
                    "finish_position": "1",
                    "last_3f": "34.8",
                    "passing_orders": [2, 2, 2, 1],
                    "course": "芝",
                    "distance": "2000",
                    "odds": "3.2",
                    "popularity": "2"
                },
                {
                    "date": "2025-06-30",
                    "finish_position": "3",
                    "last_3f": "35.5",
                    "passing_orders": [4, 4, 4, 3],
                    "course": "芝",
                    "distance": "1800",
                    "odds": "8.1",
                    "popularity": "4"
                }
            ],
            "history_features": {
                "last3f_mean_3": 35.17,
                "passing_style": horse["style"],
                "course_distance_perf": {
                    "runs": 3,
                    "win": 1,
                    "in3": 3
                },
                "recency_days": 22,
                "value_flag": horse["value"]
            }
        }
        
        # ファイルに保存
        output_file = accumulated_path / f"{horse['horse_id']}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(horse_data, f, ensure_ascii=False, indent=2)
        
        print(f"Created mock data for {horse['name']} ({horse['horse_id']})")

def test_integration():
    """統合テスト：MD生成まで"""
    
    # 1. モックデータ作成
    print("\n=== Creating mock history data ===")
    create_mock_history_data()
    
    # 2. MD再生成（11Rのみ）
    print("\n=== Regenerating MD with history features ===")
    from src.integrator.markdown_generator import MarkdownGenerator
    
    # 11Rのintegrated JSONを読み込み
    json_files = glob.glob('Z:/KEIBA-CICD/data/organized/2025/08/23/*/integrated_202504020111.json')
    
    if json_files:
        with open(json_files[0], 'r', encoding='utf-8') as f:
            race_data = json.load(f)
        
        # history_featuresを手動で追加（本来はintegratorが行う）
        for entry in race_data.get('entries', []):
            horse_id = entry.get('horse_id')
            if horse_id:
                history_file = Path(f"Z:/KEIBA-CICD/data/accumulated/horses/{horse_id}.json")
                if history_file.exists():
                    with open(history_file, 'r', encoding='utf-8') as hf:
                        horse_history = json.load(hf)
                        entry['history_features'] = horse_history.get('history_features', {})
                        print(f"  Added history for {entry['horse_name']}")
        
        # MD生成
        gen = MarkdownGenerator()
        md_content = gen.generate_race_markdown(race_data)
        
        # ファイル保存
        output_path = json_files[0].replace('integrated_', '').replace('.json', '_with_history.md')
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"\nGenerated MD: {output_path}")
        
        # 適性/割安列の確認
        if '適性/割安' in md_content:
            print("[OK] History features column added to entry table")
        else:
            print("[--] History features column NOT found")
        
        # 履歴データ注目馬の確認
        if '履歴データ注目馬' in md_content:
            print("[OK] History highlights section added to race analysis")
        else:
            print("[--] History highlights section NOT found")
        
        return output_path

if __name__ == "__main__":
    output_file = test_integration()
    print(f"\n=== Test completed ===")
    print(f"Check the generated file: {output_file}")