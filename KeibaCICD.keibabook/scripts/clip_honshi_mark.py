#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
本誌印 クリップボード出力スクリプト

日付指定で競馬ブック本誌印をクリップボードにコピーする

Usage:
    python clip_honshi_mark.py --date 20260111
    python clip_honshi_mark.py -d 20260111
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import List, Dict, Any


def get_keiba_data_root() -> Path:
    """KEIBA_DATA_ROOT_DIRを取得"""
    root = os.environ.get("KEIBA_DATA_ROOT_DIR")
    if root:
        return Path(root)
    # デフォルトパス
    return Path("Z:/KEIBA-CICD/data2")


def get_temp_dir(base_date: str) -> Path:
    """
    日付からtempディレクトリのパスを取得
    
    Args:
        base_date: YYYYMMDD形式の日付
    
    Returns:
        tempディレクトリのパス
    """
    year = base_date[:4]
    month = base_date[4:6]
    day = base_date[6:8]
    
    root = get_keiba_data_root()
    return root / "races" / year / month / day / "temp"


def load_integrated_files(temp_dir: Path) -> List[Dict[str, Any]]:
    """
    tempディレクトリからintegrated_*.jsonファイルを読み込む
    
    Returns:
        全馬のエントリーデータリスト
    """
    all_entries = []
    
    if not temp_dir.exists():
        print(f"Warning: ディレクトリが存在しません: {temp_dir}", file=sys.stderr)
        return all_entries
    
    # integrated_*.jsonファイルを検索
    json_files = sorted(temp_dir.glob("integrated_*.json"))
    
    if not json_files:
        print(f"Warning: integrated_*.jsonファイルが見つかりません: {temp_dir}", file=sys.stderr)
        return all_entries
    
    for json_file in json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            race_info = data.get("race_info", {})
            race_number = race_info.get("race_number", 0)
            venue = race_info.get("venue", "")
            
            entries = data.get("entries", [])
            
            for entry in entries:
                horse_name = entry.get("horse_name", "")
                entry_data = entry.get("entry_data", {})
                marks_by_person = entry_data.get("marks_by_person", {})
                honshi_mark = marks_by_person.get("本紙", "")
                
                all_entries.append({
                    "horse_name": horse_name,
                    "honshi_mark": honshi_mark,
                    "race_number": race_number,
                    "venue": venue,
                    "_file": json_file.name
                })
                
        except Exception as e:
            print(f"Warning: ファイル読み込みエラー {json_file}: {e}", file=sys.stderr)
    
    return all_entries


def copy_to_clipboard(text: str) -> bool:
    """
    テキストをクリップボードにコピー（Windows専用）
    
    Returns:
        成功したらTrue
    """
    try:
        process = subprocess.Popen(
            ['clip'],
            stdin=subprocess.PIPE,
            shell=True
        )
        process.communicate(text.encode('cp932', errors='replace'))
        return process.returncode == 0
    except Exception as e:
        print(f"Warning: クリップボードへのコピーに失敗: {e}", file=sys.stderr)
        return False


def format_output(data: List[Dict[str, Any]]) -> str:
    """
    出力フォーマットに変換
    
    Returns:
        タブ区切りのテキスト（馬名\t本誌印）
    """
    lines = []
    for item in data:
        horse_name = item.get("horse_name", "")
        honshi_mark = item.get("honshi_mark", "")
        
        lines.append(f"{horse_name}\t{honshi_mark}")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="本誌印 クリップボード出力",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python clip_honshi_mark.py --date 20260111
  python clip_honshi_mark.py -d 20260111
        """
    )
    
    parser.add_argument(
        "-d", "--date",
        type=str,
        required=True,
        help="日付（YYYYMMDD形式）"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="ファイル出力する場合のパス（省略時はクリップボードのみ）"
    )
    
    args = parser.parse_args()
    
    # 日付のバリデーション
    if len(args.date) != 8 or not args.date.isdigit():
        print(f"Error: 日付形式が不正です: {args.date}（YYYYMMDD形式で指定してください）", file=sys.stderr)
        sys.exit(1)
    
    # tempディレクトリを取得
    temp_dir = get_temp_dir(args.date)
    print(f"データディレクトリ: {temp_dir}")
    
    # データ読み込み
    all_entries = load_integrated_files(temp_dir)
    
    if not all_entries:
        print("Error: データが見つかりませんでした", file=sys.stderr)
        sys.exit(1)
    
    print(f"読み込み件数: {len(all_entries)}頭")
    
    # 出力フォーマット
    output_text = format_output(all_entries)
    
    # ファイル出力（オプション）
    if args.output:
        with open(args.output, "w", encoding="cp932", errors="replace") as f:
            f.write(output_text)
        print(f"ファイル出力: {args.output}")
    
    # クリップボードにコピー
    if copy_to_clipboard(output_text):
        print("クリップボードにコピーしました（馬名・本誌印）")
    
    print(f"\n処理完了: {len(all_entries)}頭")


if __name__ == "__main__":
    main()
