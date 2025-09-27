#!/usr/bin/env python3
"""
RaceDataIntegratorのデバッグ - start_timeが統合JSONに反映されない問題の調査
"""

import json
import os
from src.integrator.race_data_integrator import RaceDataIntegrator

# 対象レースID（札幌11R）
race_id = "202502080211"
date_str = "20250824"

# race_ids JSONを読み込み
race_ids_file = f"Z:/KEIBA-CICD/data/race_ids/{date_str}_info.json"
print(f"race_ids JSONを読み込み: {race_ids_file}")

with open(race_ids_file, 'r', encoding='utf-8') as f:
    race_ids_data = json.load(f)

# 該当レースのstart_timeを確認
for venue, races in race_ids_data.get('kaisai_data', {}).items():
    for race in races:
        if race.get('race_id') == race_id:
            print(f"\nrace_ids JSONの該当レース情報:")
            print(f"  venue: {venue}")
            print(f"  race_no: {race.get('race_no')}")
            print(f"  race_name: {race.get('race_name')}")
            print(f"  start_time: {race.get('start_time')}")
            print(f"  start_at: {race.get('start_at')}")
            break

# RaceDataIntegratorを初期化
integrator = RaceDataIntegrator(use_organized_dir=True)
# マッピングを設定
integrator.actual_date_map[race_id] = date_str
integrator.venue_name_map[race_id] = "札幌"

# 統合ファイルを作成（race_ids_dataを渡す）
print(f"\n統合ファイルを作成中...")
result = integrator.create_integrated_file(race_id, save=False, race_ids_data=race_ids_data)

if result:
    # race_info部分を確認
    race_info = result.get('race_info', {})
    print(f"\n統合データのrace_info:")
    print(f"  date: {race_info.get('date')}")
    print(f"  venue: {race_info.get('venue')}")
    print(f"  race_number: {race_info.get('race_number')}")
    print(f"  race_name: {race_info.get('race_name')}")
    print(f"  post_time: {race_info.get('post_time')}")
    print(f"  start_time: {race_info.get('start_time', 'なし')}")
    print(f"  start_at: {race_info.get('start_at', 'なし')}")
    
    # 既存の統合JSONファイルも確認
    integrated_file = f"Z:/KEIBA-CICD/data/organized/2025/08/24/札幌/integrated_{race_id}.json"
    if os.path.exists(integrated_file):
        print(f"\n既存の統合JSONファイルを確認: {integrated_file}")
        with open(integrated_file, 'r', encoding='utf-8') as f:
            existing_data = json.load(f)
            existing_race_info = existing_data.get('race_info', {})
            print(f"  既存のstart_time: {existing_race_info.get('start_time', 'なし')}")
            print(f"  既存のstart_at: {existing_race_info.get('start_at', 'なし')}")
else:
    print("統合データの作成に失敗しました")