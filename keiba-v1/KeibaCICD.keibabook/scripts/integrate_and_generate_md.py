#!/usr/bin/env python3
"""
レースデータ統合とMarkdown生成スクリプト
"""

import sys
import os
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.integrator.race_data_integrator import RaceDataIntegrator
from src.integrator.markdown_generator import MarkdownGenerator
import argparse
import logging

def main():
    parser = argparse.ArgumentParser(description='レースデータ統合とMarkdown生成')
    parser.add_argument('--race-id', required=True, help='レースID')
    parser.add_argument('--date', help='日付 (YYYYMMDD)')
    parser.add_argument('--venue', help='競馬場名')
    parser.add_argument('--race-number', help='レース番号')
    parser.add_argument('--overwrite', action='store_true', help='既存ファイルを上書き')
    parser.add_argument('--debug', action='store_true', help='デバッグモード')
    
    args = parser.parse_args()
    
    # ロギング設定
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # データ統合
        integrator = RaceDataIntegrator()
        integrated_data = integrator.create_integrated_file(args.race_id, save=False)
        
        if not integrated_data:
            print(f"エラー: レースID {args.race_id} のデータ統合に失敗しました。")
            return 1
        
        # Markdown生成
        generator = MarkdownGenerator()
        
        # 日付と競馬場の設定
        if args.date:
            generator.actual_date_map[args.race_id] = args.date
        if args.venue:
            generator.venue_name_map[args.race_id] = args.venue
        if args.race_number:
            integrated_data['race_info']['race_number'] = args.race_number
        
        # Markdown生成
        markdown_content = generator.generate_race_markdown(integrated_data)
        
        # ファイル保存
        output_path = generator._get_output_path(integrated_data)
        output_file = Path(output_path)
        
        if output_file.exists() and not args.overwrite:
            print(f"警告: ファイル {output_file} は既に存在します。上書きするには --overwrite を使用してください。")
            return 1
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(markdown_content, encoding='utf-8')
        
        print(f"Markdownファイルを生成しました: {output_file}")
        return 0
        
    except Exception as e:
        print(f"エラー: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())