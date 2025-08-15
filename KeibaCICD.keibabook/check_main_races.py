"""明日のメインレース確認スクリプト"""
import json
from pathlib import Path

def check_main_races():
    """8/17のメインレース（10R, 11R）を確認"""
    data_file = Path("Z:/KEIBA-CICD/data/temp/nittei_20250817.json")
    
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print("=" * 60)
    print(f"[DATE] {data['date']} のメインレース")
    print("=" * 60)
    
    main_races = []
    
    for kaisai_name, races in data['kaisai_data'].items():
        print(f"\n【{kaisai_name}】")
        for race in races:
            if race['race_no'] in ['10R', '11R']:
                print(f"  {race['race_no']}: {race['race_name']} ({race['course']})")
                print(f"    レースID: {race['race_id']}")
                
                # 重賞判定（G1, G2, G3が含まれているか）
                if 'Ｇ' in race['race_name'] or '記念' in race['race_name']:
                    main_races.append({
                        'kaisai': kaisai_name,
                        'race_no': race['race_no'],
                        'race_name': race['race_name'],
                        'race_id': race['race_id'],
                        'course': race['course'],
                        'is_graded': True
                    })
                else:
                    main_races.append({
                        'kaisai': kaisai_name,
                        'race_no': race['race_no'],
                        'race_name': race['race_name'],
                        'race_id': race['race_id'],
                        'course': race['course'],
                        'is_graded': False
                    })
    
    print("\n" + "=" * 60)
    print("[GRADED] 重賞・特別レース")
    print("=" * 60)
    
    for race in main_races:
        if race['is_graded'] or '記念' in race['race_name']:
            print(f"[*] {race['kaisai']} {race['race_no']}: {race['race_name']}")
            print(f"   レースID: {race['race_id']}")
            print(f"   コース: {race['course']}")
    
    return main_races

if __name__ == "__main__":
    main_races = check_main_races()
    print(f"\n合計 {len(main_races)} レースのメインレースを確認しました。")