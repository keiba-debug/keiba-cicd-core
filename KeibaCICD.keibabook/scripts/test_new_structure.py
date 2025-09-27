#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
新しいフォルダ構造のテストスクリプト
"""

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

# プロジェクトのルートディレクトリをPythonパスに追加
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.data_paths import DataPathConfig
from src.integrator.markdown_generator import MarkdownGenerator

def test_path_config():
    """DataPathConfigのテスト"""
    print("\n=== DataPathConfig テスト ===")

    # テスト用の一時ディレクトリを作成
    with tempfile.TemporaryDirectory() as temp_dir:
        config = DataPathConfig(base_path=temp_dir, use_new_structure=True)

        # 日付パスのテスト
        date_str = "20250927"
        race_date_path = config.get_race_date_path(date_str)
        expected = Path(temp_dir) / "races" / "2025" / "09" / "27"
        print(f"Race date path: {race_date_path}")
        assert race_date_path == expected, f"Expected {expected}, got {race_date_path}"
        print("[OK] Race date path: OK")

        # 競馬場パスのテスト
        venue_path = config.get_venue_path(date_str, "中山")
        expected = race_date_path / "中山"
        print(f"Venue path: {venue_path}")
        assert venue_path == expected, f"Expected {expected}, got {venue_path}"
        print("[OK] Venue path: OK")

        # Parsedパスのテスト
        parsed_path = config.get_parsed_path(date_str)
        expected = race_date_path / "parsed"
        print(f"Parsed path: {parsed_path}")
        assert parsed_path == expected, f"Expected {expected}, got {parsed_path}"
        print("[OK] Parsed path: OK")

        # Tempパスのテスト
        temp_path = config.get_temp_path(date_str)
        expected = race_date_path / "temp"
        print(f"Temp path: {temp_path}")
        assert temp_path == expected, f"Expected {expected}, got {temp_path}"
        print("[OK] Temp path: OK")

        # Race infoパスのテスト
        race_info_path = config.get_race_info_path(date_str)
        expected = race_date_path / "race_info.json"
        print(f"Race info path: {race_info_path}")
        assert race_info_path == expected, f"Expected {expected}, got {race_info_path}"
        print("[OK] Race info path: OK")

        # 統合JSONパスのテスト
        race_id = "202504050810"
        integrated_path = config.get_integrated_json_path(race_id, "中山")
        expected = Path(temp_dir) / "races" / "2025" / "04" / "05" / "中山" / f"integrated_{race_id}.json"
        print(f"Integrated JSON path: {integrated_path}")
        assert integrated_path == expected, f"Expected {expected}, got {integrated_path}"
        print("[OK] Integrated JSON path: OK")

        # Markdownパスのテスト
        markdown_path = config.get_markdown_path(race_id, "中山")
        expected = Path(temp_dir) / "races" / "2025" / "04" / "05" / "中山" / f"{race_id}.md"
        print(f"Markdown path: {markdown_path}")
        assert markdown_path == expected, f"Expected {expected}, got {markdown_path}"
        print("[OK] Markdown path: OK")

        print("\n[SUCCESS] DataPathConfig テスト: すべて成功")

def test_directory_creation():
    """ディレクトリ作成のテスト"""
    print("\n=== ディレクトリ作成テスト ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        config = DataPathConfig(base_path=temp_dir, use_new_structure=True)

        # ディレクトリを作成
        date_str = "20250927"
        venue_path = config.get_venue_path(date_str, "中山")
        config.ensure_directories(venue_path)

        # ディレクトリが存在することを確認
        assert venue_path.exists(), f"Directory not created: {venue_path}"
        print(f"[OK] Created directory: {venue_path}")

        # ファイルパスでも親ディレクトリが作成されることを確認
        markdown_file = venue_path / "test.md"
        config.ensure_directories(markdown_file)
        assert venue_path.exists(), f"Parent directory not created for file path"
        print(f"[OK] Parent directory created for file path")

        print("\n[SUCCESS] ディレクトリ作成テスト: すべて成功")

def test_markdown_generator():
    """MarkdownGeneratorの新構造対応テスト"""
    print("\n=== MarkdownGenerator テスト ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        # 環境変数を設定
        os.environ['KEIBA_DATA_ROOT_DIR'] = temp_dir
        os.environ['USE_NEW_DATA_STRUCTURE'] = 'true'

        # ジェネレーターを作成
        generator = MarkdownGenerator()

        # 新構造フラグが有効なことを確認
        assert generator.use_new_structure, "New structure flag not enabled"
        print("[OK] New structure flag: OK")

        # テスト用のrace_info.jsonを作成
        date_str = "20250927"
        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]

        race_info_dir = Path(temp_dir) / "races" / year / month / day
        race_info_dir.mkdir(parents=True, exist_ok=True)

        race_info_data = {
            "date": date_str,
            "kaisai_data": {
                "4回中山8日目": [
                    {
                        "race_no": "10R",
                        "race_name": "勝浦特別",
                        "course": "芝外・1200m",
                        "race_id": "202504050810",
                        "start_time": "15:00"
                    }
                ]
            }
        }

        race_info_file = race_info_dir / "race_info.json"
        with open(race_info_file, 'w', encoding='utf-8') as f:
            json.dump(race_info_data, f, ensure_ascii=False, indent=2)

        print(f"[OK] Created test race_info.json: {race_info_file}")

        # race_infoを読み込み
        generator.load_actual_dates()

        # マッピングが正しく読み込まれたか確認
        race_id = "202504050810"
        assert race_id in generator.actual_date_map, "Race ID not in date map"
        assert generator.actual_date_map[race_id] == date_str, "Incorrect date mapping"
        print(f"[OK] Race date mapping: OK")

        assert race_id in generator.venue_name_map, "Race ID not in venue map"
        assert generator.venue_name_map[race_id] == "中山", "Incorrect venue mapping"
        print(f"[OK] Venue name mapping: OK")

        # 出力パスが新構造になっているか確認
        test_race_data = {'meta': {'race_id': race_id}}
        output_path = generator._get_output_path(test_race_data)
        # actual_date_mapが設定されているので、実際の日付(20250927)が使われる
        expected_path = os.path.join(temp_dir, 'races', '2025', '09', '27', '中山', f'{race_id}.md')

        assert output_path == expected_path, f"Expected {expected_path}, got {output_path}"
        print(f"[OK] Output path: {output_path}")

        print("\n[SUCCESS] MarkdownGenerator テスト: すべて成功")

        # 環境変数をクリア
        del os.environ['USE_NEW_DATA_STRUCTURE']

def test_migration_compatibility():
    """新旧構造の互換性テスト"""
    print("\n=== 互換性テスト ===")

    with tempfile.TemporaryDirectory() as temp_dir:
        # 旧構造でテスト
        old_config = DataPathConfig(base_path=temp_dir, use_new_structure=False)
        date_str = "20250927"

        old_race_info = old_config.get_race_info_path(date_str)
        expected = Path(temp_dir) / "race_ids" / f"{date_str}_info.json"
        assert old_race_info == expected, f"Old structure path incorrect"
        print(f"[OK] Old structure race_info: {old_race_info}")

        # 新構造でテスト
        new_config = DataPathConfig(base_path=temp_dir, use_new_structure=True)
        new_race_info = new_config.get_race_info_path(date_str)
        expected = Path(temp_dir) / "races" / "2025" / "09" / "27" / "race_info.json"
        assert new_race_info == expected, f"New structure path incorrect"
        print(f"[OK] New structure race_info: {new_race_info}")

        print("\n[SUCCESS] 互換性テスト: すべて成功")

def main():
    """メインテスト実行"""
    print("=" * 60)
    print("新しいフォルダ構造のテストを開始します")
    print("=" * 60)

    try:
        test_path_config()
        test_directory_creation()
        test_markdown_generator()
        test_migration_compatibility()

        print("\n" + "=" * 60)
        print("[COMPLETE] すべてのテストが成功しました！")
        print("=" * 60)

    except AssertionError as e:
        print(f"\n[ERROR] テストが失敗しました: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()