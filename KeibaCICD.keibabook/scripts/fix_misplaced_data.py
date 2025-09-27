#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
誤った日付フォルダに配置されたデータを正しい場所に移動する
"""

import os
import json
import shutil
from pathlib import Path
import argparse

def move_race_data(base_path: str, actual_date: str, dry_run: bool = True):
    """
    レースデータを正しい日付フォルダに移動

    Args:
        base_path: データディレクトリのベースパス
        actual_date: 実際の開催日 (YYYYMMDD形式)
        dry_run: True の場合は実際の移動はせず確認のみ
    """
    base_dir = Path(base_path)
    races_dir = base_dir / "races"

    if not races_dir.exists():
        print(f"Races directory not found: {races_dir}")
        return

    # 実際の日付を解析
    year = actual_date[:4]
    month = actual_date[4:6]
    day = actual_date[6:8]

    # 正しい日付フォルダ
    correct_date_dir = races_dir / year / month / day

    # race_info.jsonを読み込み
    race_info_file = correct_date_dir / "race_info.json"
    if not race_info_file.exists():
        print(f"Race info file not found: {race_info_file}")
        return

    with open(race_info_file, 'r', encoding='utf-8') as f:
        race_info = json.load(f)

    # レースIDを収集
    race_ids = []
    for venue, races in race_info.get('kaisai_data', {}).items():
        for race in races:
            race_id = race.get('race_id')
            if race_id:
                race_ids.append(race_id)

    print(f"Found {len(race_ids)} race IDs for date {actual_date}")

    # 各レースIDのデータを探して移動
    moved_count = 0
    for race_id in race_ids:
        # レースIDから誤った日付を取得
        wrong_date_str = race_id[:8]
        wrong_year = wrong_date_str[:4]
        wrong_month = wrong_date_str[4:6]
        wrong_day = wrong_date_str[6:8]

        # 誤った場所のtempフォルダ
        wrong_temp_dir = races_dir / wrong_year / wrong_month / wrong_day / "temp"

        if wrong_temp_dir.exists():
            # tempフォルダ内のファイルを探す
            for file_name in os.listdir(wrong_temp_dir):
                if race_id in file_name:
                    source_file = wrong_temp_dir / file_name
                    target_dir = correct_date_dir / "temp"

                    if not dry_run:
                        target_dir.mkdir(parents=True, exist_ok=True)

                    target_file = target_dir / file_name

                    if dry_run:
                        print(f"[DRY RUN] Would move: {source_file} -> {target_file}")
                    else:
                        print(f"Moving: {source_file} -> {target_file}")
                        shutil.move(str(source_file), str(target_file))

                    moved_count += 1

    print(f"\nTotal files {'would be moved' if dry_run else 'moved'}: {moved_count}")

    # 空になった誤ったフォルダを削除（オプション）
    if not dry_run and moved_count > 0:
        # 2025/04フォルダをチェック
        for wrong_month in ['04', '01']:
            wrong_month_dir = races_dir / year / wrong_month
            if wrong_month_dir.exists():
                # すべてのサブディレクトリが空かチェック
                is_empty = True
                for day_dir in wrong_month_dir.iterdir():
                    if day_dir.is_dir():
                        temp_dir = day_dir / "temp"
                        if temp_dir.exists() and any(temp_dir.iterdir()):
                            is_empty = False
                            break

                if is_empty:
                    print(f"Removing empty directory: {wrong_month_dir}")
                    shutil.rmtree(wrong_month_dir)

def main():
    parser = argparse.ArgumentParser(description="誤った日付フォルダのデータを修正")
    parser.add_argument("--base-path", default="Z:/KEIBA-CICD/data2",
                        help="データディレクトリのベースパス")
    parser.add_argument("--date", required=True,
                        help="実際の開催日 (YYYYMMDD形式)")
    parser.add_argument("--execute", action="store_true",
                        help="実際に移動を実行（デフォルトはドライラン）")

    args = parser.parse_args()

    if args.execute:
        print("Executing data movement...")
    else:
        print("DRY RUN MODE - No files will be moved")
        print("Add --execute flag to actually move files")

    move_race_data(args.base_path, args.date, dry_run=not args.execute)

if __name__ == "__main__":
    main()