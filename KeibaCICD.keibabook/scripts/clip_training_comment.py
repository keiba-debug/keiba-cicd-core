#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
調教コメント クリップボード出力スクリプト

日付指定で調教コメントをクリップボードにコピーする

Usage:
    python clip_training_comment.py --date 20251228
    python clip_training_comment.py -d 20251228
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


def load_cyokyo_files(temp_dir: Path) -> List[Dict[str, Any]]:
    """
    tempディレクトリからcyokyo_*.jsonファイルを読み込む
    
    Returns:
        全レースの調教データリスト
    """
    all_data = []
    
    if not temp_dir.exists():
        print(f"Warning: ディレクトリが存在しません: {temp_dir}", file=sys.stderr)
        return all_data
    
    # cyokyo_*.jsonファイルを検索
    json_files = sorted(temp_dir.glob("cyokyo_*.json"))
    
    if not json_files:
        print(f"Warning: cyokyo_*.jsonファイルが見つかりません: {temp_dir}", file=sys.stderr)
        return all_data
    
    for json_file in json_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            race_info = data.get("race_info", {})
            race_id = race_info.get("race_id", "")
            race_name = race_info.get("race_name", "")
            
            training_data = data.get("training_data", [])
            
            for item in training_data:
                item["_race_id"] = race_id
                item["_race_name"] = race_name
                item["_file"] = json_file.name
                all_data.append(item)
                
        except Exception as e:
            print(f"Warning: ファイル読み込みエラー {json_file}: {e}", file=sys.stderr)
    
    return all_data


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
        タブ区切りのテキスト
    """
    lines = []
    for item in data:
        horse_name = item.get("horse_name", "")
        attack_explanation = item.get("attack_explanation", "")
        
        # 空のコメントはスキップしない（馬名だけでも出力）
        lines.append(f"{horse_name}\t{attack_explanation}")
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="調教コメント クリップボード出力",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  python clip_training_comment.py --date 20251228
  python clip_training_comment.py -d 20251228
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
    all_data = load_cyokyo_files(temp_dir)
    
    if not all_data:
        print("Error: 調教データが見つかりませんでした", file=sys.stderr)
        sys.exit(1)
    
    print(f"読み込み件数: {len(all_data)}頭")
    
    # 出力フォーマット
    output_text = format_output(all_data)
    
    # ファイル出力（オプション）
    if args.output:
        with open(args.output, "w", encoding="cp932", errors="replace") as f:
            f.write(output_text)
        print(f"ファイル出力: {args.output}")
    
    # クリップボードにコピー
    if copy_to_clipboard(output_text):
        print("クリップボードにコピーしました（馬名・調教コメント）")
    
    print(f"\n処理完了: {len(all_data)}頭")


if __name__ == "__main__":
    main()
