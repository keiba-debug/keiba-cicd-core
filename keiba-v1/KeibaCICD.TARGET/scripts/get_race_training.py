#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
レース出走馬の調教データ一括取得スクリプト

レースの出走馬全頭の調教データを取得し、JSON形式で出力します。

Usage:
    python get_race_training.py --race-id 202601250511 --output training_output.json
    python get_race_training.py --horse-ids 2020105626,2022104661 --date 20260125
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# UTF-8出力
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 同一ディレクトリのparse_ck_dataをインポート
sys.path.insert(0, str(Path(__file__).parent))
from parse_ck_data import analyze_horse_training, TrainingConfig, _config

# 共通設定モジュールをインポート
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.config import get_keiba_data_root, get_races_dir

# データルート
DATA_ROOT = get_keiba_data_root()


def load_race_entries(race_id: str) -> List[str]:
    """
    レースIDから出走馬の血統登録番号リストを取得
    
    race_id: YYYYMMDDXXYY (年月日+場コード+レース番号)
    """
    horse_ids = []
    
    # integrated_YYYYMMDD.json から取得
    date_str = race_id[:8]
    year = date_str[:4]
    month = date_str[4:6]
    
    races_dir = DATA_ROOT / "races" / year / month
    integrated_file = races_dir / f"integrated_{date_str}.json"
    
    if not integrated_file.exists():
        print(f"Warning: Race data file not found: {integrated_file}", file=sys.stderr)
        return horse_ids
    
    try:
        with open(integrated_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # レースIDに一致するレースを探す
        for race in data.get('races', []):
            race_info = race.get('race_info', {})
            # race_idのフォーマット: YYYYMMDDXXYY
            file_race_id = f"{date_str}{race_info.get('venue_code', '00')}{race_info.get('race_number', '00'):02d}"
            
            if file_race_id == race_id or race_id in str(race_info):
                entries = race.get('entries', [])
                for entry in entries:
                    horse_id = entry.get('horse_id', '')
                    if horse_id and len(horse_id) == 10:
                        horse_ids.append(horse_id)
                break
    except Exception as e:
        print(f"Error loading race data: {e}", file=sys.stderr)
    
    return horse_ids


def get_race_training_data(
    horse_ids: List[str],
    race_date: str,
    days_back: int = 14
) -> Dict:
    """
    複数馬の調教データを一括取得
    """
    results = {
        "race_date": race_date,
        "generated_at": datetime.now().isoformat(),
        "horse_count": len(horse_ids),
        "entries": []
    }
    
    for horse_id in horse_ids:
        training_data = analyze_horse_training(horse_id, race_date, days_back)
        
        # エラーがなければ追加
        if training_data.get('final') or training_data.get('all_records'):
            results["entries"].append(training_data)
        else:
            # データがなくてもエントリーを追加（空データで）
            results["entries"].append({
                "horse_id": horse_id,
                "race_date": race_date,
                "total_count": 0,
                "count_label": "少",
                "time_class": "",
                "has_good_time": False,
                "final": None,
                "week_ago": None,
                "all_records": [],
                "error": training_data.get("error", "No data found")
            })
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Get training data for race entries")
    parser.add_argument("--race-id", type=str, help="Race ID (YYYYMMDDXXYY)")
    parser.add_argument("--horse-ids", type=str, help="Comma-separated horse IDs")
    parser.add_argument("--date", type=str, default=datetime.now().strftime("%Y%m%d"),
                        help="Race date (YYYYMMDD)")
    parser.add_argument("--days", type=int, default=14, help="Days to look back")
    parser.add_argument("--output", type=str, help="Output JSON file path")
    
    args = parser.parse_args()
    
    # 馬IDリストを取得
    horse_ids = []
    
    if args.race_id:
        # レースIDから馬IDを取得
        horse_ids = load_race_entries(args.race_id)
        race_date = args.race_id[:8]
        print(f"Loaded {len(horse_ids)} entries from race {args.race_id}", file=sys.stderr)
    elif args.horse_ids:
        # カンマ区切りの馬IDを使用
        horse_ids = [h.strip() for h in args.horse_ids.split(',')]
        race_date = args.date
    else:
        print("Error: Either --race-id or --horse-ids is required", file=sys.stderr)
        return 1
    
    if not horse_ids:
        print("Error: No horse IDs found", file=sys.stderr)
        return 1
    
    # 調教データを取得
    results = get_race_training_data(horse_ids, race_date, args.days)
    
    # 出力
    output_json = json.dumps(results, ensure_ascii=False, indent=2)
    
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_json)
        print(f"Output written to {args.output}", file=sys.stderr)
    else:
        print(output_json)
    
    return 0


if __name__ == "__main__":
    exit(main())
