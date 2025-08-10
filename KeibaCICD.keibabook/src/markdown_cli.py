"""
Markdown形式統合ファイル生成CLI
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.integrator.markdown_generator import MarkdownGenerator
from src.integrator.race_data_integrator import RaceDataIntegrator
from src.batch.core.common import setup_batch_logger, get_race_ids_file_path, parse_date


def main():
    parser = argparse.ArgumentParser(description='レースデータをMarkdown形式で生成')
    
    subparsers = parser.add_subparsers(dest='command', help='サブコマンド')
    
    # single: 単一レースのMarkdown生成
    single_parser = subparsers.add_parser('single', help='単一レースのMarkdown生成')
    single_parser.add_argument('--race-id', required=True, help='レースID (例: 202501080511)')
    single_parser.add_argument('--regenerate', action='store_true', help='JSONから再生成')
    single_parser.add_argument('--organized', action='store_true', help='organizedディレクトリ以下に出力')
    
    # batch: 日付指定での一括生成
    batch_parser = subparsers.add_parser('batch', help='日付指定での一括Markdown生成')
    batch_parser.add_argument('--date', help='対象日付 (YYYY/MM/DD)')
    batch_parser.add_argument('--start-date', help='開始日')
    batch_parser.add_argument('--end-date', help='終了日')
    batch_parser.add_argument('--organized', action='store_true', help='organizedディレクトリ以下に出力')
    
    # convert: 既存のJSONファイルからMarkdown生成
    convert_parser = subparsers.add_parser('convert', help='既存JSONからMarkdown変換')
    convert_parser.add_argument('--input-dir', help='入力ディレクトリ')
    convert_parser.add_argument('--organized', action='store_true', help='organizedディレクトリ以下に出力')
    
    # preview: Markdown生成プレビュー（保存なし）
    preview_parser = subparsers.add_parser('preview', help='Markdownプレビュー')
    preview_parser.add_argument('--race-id', required=True, help='レースID')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # ロガー初期化
    logger = setup_batch_logger('markdown_cli')
    logger.info("[START] Markdown生成CLI")
    logger.info(f"[COMMAND]: {args.command}")
    
    try:
        # ジェネレータ初期化
        use_organized = getattr(args, 'organized', False)
        generator = MarkdownGenerator(use_organized_dir=use_organized)
        integrator = RaceDataIntegrator(use_organized_dir=use_organized)
        
        if args.command == 'single':
            # 単一レースのMarkdown生成
            logger.info(f"[RACE]: {args.race_id}")
            
            if args.regenerate:
                # JSONファイルから再生成
                json_path = os.path.join(
                    os.getenv('KEIBA_DATA_ROOT_DIR', './data'),
                    'integrated',
                    f'integrated_{args.race_id}.json'
                )
                
                if os.path.exists(json_path):
                    with open(json_path, 'r', encoding='utf-8') as f:
                        race_data = json.load(f)
                else:
                    logger.error(f"[ERROR] 統合ファイルが見つかりません: {json_path}")
                    return
            else:
                # データを新規取得して生成
                race_data = integrator.create_integrated_file(args.race_id, save=False)
                if not race_data:
                    logger.error(f"[ERROR] データ取得失敗: {args.race_id}")
                    return
            
            # Markdown生成
            md_path = generator._get_output_path(race_data)
            generator.generate_race_markdown(race_data, save=True)
            
            logger.info(f"[SUCCESS] Markdown生成完了: {md_path}")
            
            # ファイルサイズ表示
            file_size = os.path.getsize(md_path)
            logger.info(f"[SIZE]: {file_size:,} bytes")
            
        elif args.command == 'batch':
            # 日付指定での一括生成
            if args.date:
                dates = [parse_date(args.date).strftime("%Y%m%d")]
            elif args.start_date:
                start = parse_date(args.start_date)
                end = parse_date(args.end_date) if args.end_date else start
                dates = []
                current = start
                while current <= end:
                    dates.append(current.strftime("%Y%m%d"))
                    current = current.replace(day=current.day + 1)
            else:
                logger.error("[ERROR] 日付を指定してください")
                return
            
            total_count = 0
            success_count = 0
            
            for date_str in dates:
                logger.info(f"[DATE]: {date_str}")
                
                # レースIDを取得
                race_ids_file = get_race_ids_file_path(date_str)
                if not os.path.exists(race_ids_file):
                    logger.warning(f"[SKIP] レースIDファイルなし: {date_str}")
                    continue
                
                with open(race_ids_file, 'r', encoding='utf-8') as f:
                    race_ids_data = json.load(f)
                
                # 各レースを処理
                for venue, races in race_ids_data.get('kaisai_data', {}).items():
                    for race in races:
                        race_id = race['race_id'] if isinstance(race, dict) else race
                        total_count += 1
                        
                        try:
                            # 統合データを作成または取得
                            race_data = integrator.create_integrated_file(race_id, save=True)
                            
                            if race_data:
                                # Markdown生成
                                generator.generate_race_markdown(race_data, save=True)
                                success_count += 1
                                logger.info(f"  [OK] {race_id}")
                            else:
                                logger.warning(f"  [SKIP] データ取得失敗: {race_id}")
                        
                        except Exception as e:
                            logger.error(f"  [ERROR] {race_id}: {e}")
            
            logger.info(f"[COMPLETE] 処理完了: {success_count}/{total_count}")
            
        elif args.command == 'convert':
            # 既存JSONからの変換
            input_dir = args.input_dir or os.path.join(
                os.getenv('KEIBA_DATA_ROOT_DIR', './data'),
                'integrated'
            )
            
            logger.info(f"[INPUT]: {input_dir}")
            
            result = generator.batch_generate(input_dir)
            
            logger.info(f"[COMPLETE] 変換完了")
            logger.info(f"  成功: {result['success']}")
            logger.info(f"  失敗: {result['failed']}")
            logger.info(f"  合計: {result['total']}")
            
        elif args.command == 'preview':
            # プレビュー表示
            logger.info(f"[PREVIEW]: {args.race_id}")
            
            # データ取得
            json_path = os.path.join(
                os.getenv('KEIBA_DATA_ROOT_DIR', './data'),
                'integrated',
                f'integrated_{args.race_id}.json'
            )
            
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    race_data = json.load(f)
                
                # Markdown生成（保存なし）
                markdown_text = generator.generate_race_markdown(race_data, save=False)
                
                # コンソールに出力
                print("\n" + "="*60)
                print(markdown_text)
                print("="*60 + "\n")
                
                logger.info(f"[SIZE]: {len(markdown_text):,} characters")
            else:
                logger.error(f"[ERROR] ファイルが見つかりません: {json_path}")
        
        logger.info("[END] Markdown生成CLI")
        
    except Exception as e:
        logger.error(f"[ERROR] 予期しないエラー: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()