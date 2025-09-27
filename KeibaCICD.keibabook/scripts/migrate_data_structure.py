#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
データフォルダ構造の移行スクリプト
現在の構造から新しい日付ベースの階層構造に移行する
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime
import argparse

class DataStructureMigrator:
    def __init__(self, base_path="Z:/KEIBA-CICD/data", dry_run=True):
        self.base_path = Path(base_path)
        self.dry_run = dry_run
        self.migration_log = []

    def log(self, message):
        """移行ログを記録"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)
        self.migration_log.append(log_entry)

    def migrate_organized_data(self):
        """organized フォルダのデータを新構造に移行"""
        organized_path = self.base_path / "organized"
        if not organized_path.exists():
            self.log(f"Organized folder not found: {organized_path}")
            return

        # 年/月/日の階層を走査
        for year_dir in organized_path.iterdir():
            if not year_dir.is_dir() or not year_dir.name.isdigit():
                continue

            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir() or not month_dir.name.isdigit():
                    continue

                for day_dir in month_dir.iterdir():
                    if not day_dir.is_dir() or not day_dir.name.isdigit():
                        continue

                    # 新しいパスを構築
                    date_str = f"{year_dir.name}{month_dir.name.zfill(2)}{day_dir.name.zfill(2)}"
                    new_base = self.base_path / "races" / year_dir.name / month_dir.name.zfill(2) / day_dir.name.zfill(2)

                    # 競馬場ごとのディレクトリを処理
                    for venue_dir in day_dir.iterdir():
                        if not venue_dir.is_dir():
                            continue

                        new_venue_path = new_base / venue_dir.name

                        if not self.dry_run:
                            new_venue_path.mkdir(parents=True, exist_ok=True)

                        # ファイルを移動
                        for file_path in venue_dir.glob("*"):
                            if file_path.is_file():
                                new_file_path = new_venue_path / file_path.name
                                self.log(f"Move: {file_path} -> {new_file_path}")

                                if not self.dry_run:
                                    shutil.copy2(file_path, new_file_path)

    def migrate_parsed_data(self):
        """parsed フォルダのデータを新構造に移行"""
        parsed_path = self.base_path / "parsed"
        if not parsed_path.exists():
            self.log(f"Parsed folder not found: {parsed_path}")
            return

        # YYYYMMDDフォルダを処理
        for date_dir in parsed_path.iterdir():
            if not date_dir.is_dir() or not date_dir.name.isdigit() or len(date_dir.name) != 8:
                continue

            # 日付を解析
            date_str = date_dir.name
            year = date_str[:4]
            month = date_str[4:6]
            day = date_str[6:8]

            # 新しいパスを構築
            new_base = self.base_path / "races" / year / month / day / "parsed"

            if not self.dry_run:
                new_base.mkdir(parents=True, exist_ok=True)

            # ファイルを移動
            for file_path in date_dir.glob("*"):
                if file_path.is_file():
                    new_file_path = new_base / file_path.name
                    self.log(f"Move: {file_path} -> {new_file_path}")

                    if not self.dry_run:
                        shutil.copy2(file_path, new_file_path)

    def migrate_temp_files(self):
        """temp フォルダのファイルを適切な日付フォルダに移行"""
        temp_path = self.base_path / "temp"
        if not temp_path.exists():
            self.log(f"Temp folder not found: {temp_path}")
            return

        for file_path in temp_path.glob("*"):
            if not file_path.is_file():
                continue

            # ファイル名から日付を抽出 (例: cyokyo_202504050810.json)
            filename = file_path.name
            date_match = None

            # レースIDパターン (202504050810)
            if "_20" in filename:
                parts = filename.split("_")
                for part in parts:
                    if part.startswith("20") and len(part) >= 12:
                        date_match = part[:8]
                        break

            if date_match:
                year = date_match[:4]
                month = date_match[4:6]
                day = date_match[6:8]

                new_base = self.base_path / "races" / year / month / day / "temp"

                if not self.dry_run:
                    new_base.mkdir(parents=True, exist_ok=True)

                new_file_path = new_base / file_path.name
                self.log(f"Move: {file_path} -> {new_file_path}")

                if not self.dry_run:
                    shutil.copy2(file_path, new_file_path)
            else:
                self.log(f"Cannot determine date for: {file_path}")

    def migrate_race_ids(self):
        """race_ids フォルダのファイルを適切な日付フォルダに移行"""
        race_ids_path = self.base_path / "race_ids"
        if not race_ids_path.exists():
            self.log(f"Race IDs folder not found: {race_ids_path}")
            return

        for file_path in race_ids_path.glob("*.json"):
            if not file_path.is_file():
                continue

            # ファイル名から日付を抽出 (例: 20250927_info.json)
            filename = file_path.stem  # .jsonを除く
            if filename.endswith("_info"):
                date_str = filename.replace("_info", "")

                if len(date_str) == 8 and date_str.isdigit():
                    year = date_str[:4]
                    month = date_str[4:6]
                    day = date_str[6:8]

                    new_base = self.base_path / "races" / year / month / day

                    if not self.dry_run:
                        new_base.mkdir(parents=True, exist_ok=True)

                    # race_info.json として保存
                    new_file_path = new_base / "race_info.json"
                    self.log(f"Move: {file_path} -> {new_file_path}")

                    if not self.dry_run:
                        shutil.copy2(file_path, new_file_path)

    def create_summary_json(self):
        """各日付フォルダにsummary.jsonを作成"""
        races_path = self.base_path / "races"
        if not races_path.exists():
            return

        for year_dir in races_path.iterdir():
            if not year_dir.is_dir():
                continue

            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir():
                    continue

                for day_dir in month_dir.iterdir():
                    if not day_dir.is_dir():
                        continue

                    # その日のレース情報を集約
                    summary = {
                        "date": f"{year_dir.name}-{month_dir.name}-{day_dir.name}",
                        "venues": [],
                        "total_races": 0,
                        "files": {
                            "parsed": [],
                            "temp": [],
                            "integrated": [],
                            "markdown": []
                        }
                    }

                    # 競馬場を検索
                    for venue_dir in day_dir.iterdir():
                        if venue_dir.is_dir() and venue_dir.name not in ["parsed", "temp"]:
                            summary["venues"].append(venue_dir.name)

                            # ファイルをカテゴリ分け
                            for file_path in venue_dir.glob("*.json"):
                                if "integrated" in file_path.name:
                                    summary["files"]["integrated"].append(file_path.name)

                            for file_path in venue_dir.glob("*.md"):
                                summary["files"]["markdown"].append(file_path.name)

                    # parsed フォルダ
                    parsed_dir = day_dir / "parsed"
                    if parsed_dir.exists():
                        for file_path in parsed_dir.glob("*"):
                            summary["files"]["parsed"].append(file_path.name)

                    # temp フォルダ
                    temp_dir = day_dir / "temp"
                    if temp_dir.exists():
                        for file_path in temp_dir.glob("*"):
                            summary["files"]["temp"].append(file_path.name)

                    # summary.json を保存
                    summary_path = day_dir / "summary.json"
                    self.log(f"Create summary: {summary_path}")

                    if not self.dry_run:
                        with open(summary_path, 'w', encoding='utf-8') as f:
                            json.dump(summary, f, ensure_ascii=False, indent=2)

    def cleanup_old_structure(self):
        """移行完了後、古い構造を削除（オプション）"""
        if self.dry_run:
            self.log("Dry run mode: Skipping cleanup")
            return

        old_dirs = ["organized", "parsed", "temp", "race_ids"]

        for dir_name in old_dirs:
            dir_path = self.base_path / dir_name
            if dir_path.exists():
                self.log(f"Remove old directory: {dir_path}")
                # 安全のため、実際の削除はコメントアウト
                # shutil.rmtree(dir_path)

    def save_migration_log(self):
        """移行ログを保存"""
        log_path = self.base_path / f"migration_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

        with open(log_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(self.migration_log))

        self.log(f"Migration log saved: {log_path}")

    def run(self):
        """移行処理を実行"""
        self.log(f"Starting migration {'(DRY RUN)' if self.dry_run else ''}")
        self.log(f"Base path: {self.base_path}")

        # 1. organized フォルダの移行
        self.log("\n=== Migrating organized data ===")
        self.migrate_organized_data()

        # 2. parsed フォルダの移行
        self.log("\n=== Migrating parsed data ===")
        self.migrate_parsed_data()

        # 3. temp フォルダの移行
        self.log("\n=== Migrating temp files ===")
        self.migrate_temp_files()

        # 4. race_ids フォルダの移行
        self.log("\n=== Migrating race IDs ===")
        self.migrate_race_ids()

        # 5. summary.json の作成
        if not self.dry_run:
            self.log("\n=== Creating summary files ===")
            self.create_summary_json()

        # 6. 移行ログの保存
        self.save_migration_log()

        # 7. クリーンアップ（オプション）
        # self.cleanup_old_structure()

        self.log("\n=== Migration completed ===")

def main():
    parser = argparse.ArgumentParser(description="データフォルダ構造の移行")
    parser.add_argument("--base-path", default="Z:/KEIBA-CICD/data",
                        help="データフォルダのベースパス")
    parser.add_argument("--execute", action="store_true",
                        help="実際に移行を実行（デフォルトはドライラン）")

    args = parser.parse_args()

    migrator = DataStructureMigrator(
        base_path=args.base_path,
        dry_run=not args.execute
    )

    migrator.run()

if __name__ == "__main__":
    main()