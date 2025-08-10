#!/usr/bin/env python3
"""
CLI

CLI
"""

import argparse
import logging
import os
from datetime import datetime

from .utils.file_organizer import FileOrganizer
from .batch.core.common import setup_batch_logger


def main():
    """
    CLI
    """
    parser = argparse.ArgumentParser(
        description='',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
:
  # 
  python -m src.organizer_cli organize
  
  # 
  python -m src.organizer_cli organize --copy
  
  # 
  python -m src.organizer_cli index
  
  # 
  python -m src.organizer_cli find --date 2025/01/01 --venue 
  
  # 
  python -m src.organizer_cli stats

:
  organized/
   /
      /
         /
            /
               /
               /
               /
               /
            /
            /
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='')
    
    # organize  - 
    organize_parser = subparsers.add_parser('organize', help='')
    organize_parser.add_argument('--source-dir', help='')
    organize_parser.add_argument('--copy', action='store_true', 
                                help='')
    organize_parser.add_argument('--dry-run', action='store_true',
                                help='')
    organize_parser.add_argument('--delete-original', action='store_true',
                                help='整理後に元ファイルを削除')
    
    # index  - 
    index_parser = subparsers.add_parser('index', help='')
    index_parser.add_argument('--output', help='')
    
    # find  - 
    find_parser = subparsers.add_parser('find', help='')
    find_parser.add_argument('--date', help=' (YYYY/MM/DD)')
    find_parser.add_argument('--venue', help='')
    find_parser.add_argument('--data-type', 
                            choices=['nittei', 'seiseki', 'shutsuba', 'cyokyo', 'danwa', 'integrated'],
                            help='')
    
    # stats  - 
    stats_parser = subparsers.add_parser('stats', help='')
    stats_parser.add_argument('--detailed', action='store_true', help='')
    
    # clean  - 
    clean_parser = subparsers.add_parser('clean', help='')
    clean_parser.add_argument('--dry-run', action='store_true',
                             help='')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 
    logger = setup_batch_logger('organizer_cli')
    logger.info("[FOLDER] CLI")
    logger.info(f"[TARGET] : {args.command}")
    
    try:
        # FileOrganizer
        organizer = FileOrganizer()
        # 実際の開催日マッピングをロード
        organizer.load_actual_dates()
        
        if args.command == 'organize':
            # デフォルトはtempフォルダ
            default_source = os.path.join(os.getenv('KEIBA_DATA_ROOT_DIR', './data'), 'temp')
            source_dir = args.source_dir or default_source
            
            if args.dry_run:
                logger.info("[SEARCH] : /")
                
                # 
                import glob
                json_files = glob.glob(os.path.join(source_dir, '*.json'))
                json_files.extend(glob.glob(os.path.join(source_dir, '*/*.json')))
                
                logger.info(f"[DATA] : {len(json_files)}")
                for json_file in json_files[:10]:  # 10
                    filename = os.path.basename(json_file)
                    file_info = organizer._extract_info_from_filename(filename)
                    if file_info:
                        target_dir = organizer._get_organized_path(file_info)
                        logger.info(f"  {filename} -> {target_dir}")
                
                if len(json_files) > 10:
                    logger.info(f"  ...  {len(json_files) - 10}")
            else:
                # 
                action = "" if args.copy else ""
                logger.info(f"[FILE] {action}")
                logger.info(f"[FOLDER] : {source_dir}")
                logger.info(f"[FOLDER] : {organizer.organized_root}")
                
                summary = organizer.organize_directory(source_dir, copy=args.copy)
                
                if summary['success']:
                    logger.info(f"[OK] ")
                    logger.info(f"[DATA] :")
                    logger.info(f"  : {summary['total_files']}")
                    logger.info(f"  : {summary['success_count']}")
                    logger.info(f"  : {summary['failed_count']}")
                    logger.info(f"[FOLDER] : {summary['organized_root']}")
                    
                    # 元ファイル削除オプション
                    if args.delete_original and args.copy:
                        logger.info("[DELETE] tempフォルダのファイルを削除中...")
                        deleted_count = 0
                        failed_delete = 0
                        
                        # tempフォルダが存在する場合のみ処理
                        if os.path.exists(source_dir) and 'temp' in source_dir:
                            import glob
                            import shutil
                            
                            # tempフォルダ内の全JSONファイルを削除
                            json_files = glob.glob(os.path.join(source_dir, '*.json'))
                            
                            for json_file in json_files:
                                try:
                                    os.remove(json_file)
                                    deleted_count += 1
                                    logger.debug(f"  [DEL] {os.path.basename(json_file)}")
                                except Exception as e:
                                    failed_delete += 1
                                    logger.error(f"  [ERR] {os.path.basename(json_file)}: {e}")
                            
                            logger.info(f"[DELETE] 削除完了: {deleted_count}件")
                            if failed_delete > 0:
                                logger.warning(f"[WARNING] 削除失敗: {failed_delete}件")
                        else:
                            logger.warning("[WARNING] tempフォルダが見つかりません")
                    
        elif args.command == 'index':
            # 
            logger.info("[INDEX] ")
            
            index = organizer.create_index()
            
            logger.info(f"[OK] ")
            logger.info(f"[DATA] :")
            logger.info(f"  : {index['statistics']['total_files']}")
            
            # 
            if index['statistics']['by_year']:
                logger.info(f"[DATE] :")
                for year, count in sorted(index['statistics']['by_year'].items()):
                    logger.info(f"  {year}: {count}")
            
            # 
            if index['statistics']['by_venue']:
                logger.info(f"[VENUE] :")
                for venue, count in sorted(index['statistics']['by_venue'].items()):
                    logger.info(f"  {venue}: {count}")
            
            # 
            if index['statistics']['by_data_type']:
                logger.info(f"[DATA] :")
                for dtype, count in sorted(index['statistics']['by_data_type'].items()):
                    logger.info(f"  {dtype}: {count}")
                    
        elif args.command == 'find':
            # 
            conditions = []
            if args.date:
                date_str = args.date.replace('/', '')
                conditions.append(f"={args.date}")
            else:
                date_str = None
            
            if args.venue:
                conditions.append(f"={args.venue}")
            
            if args.data_type:
                conditions.append(f"={args.data_type}")
            
            logger.info(f"[SEARCH] : {', '.join(conditions) if conditions else ''}")
            
            matches = organizer.find_files(
                date=date_str,
                venue=args.venue,
                data_type=args.data_type
            )
            
            if matches:
                logger.info(f"[DATA] {len(matches)}:")
                for i, file_path in enumerate(matches[:20], 1):  # 20
                    rel_path = os.path.relpath(file_path, organizer.organized_root)
                    logger.info(f"  {i}. {rel_path}")
                
                if len(matches) > 20:
                    logger.info(f"  ...  {len(matches) - 20}")
            else:
                logger.info("[ERROR] ")
                
        elif args.command == 'stats':
            # 
            logger.info("[DATA] ")
            
            stats = organizer.get_storage_stats()
            
            logger.info(f"[FILE] : {stats['file_count']}")
            logger.info(f"[SAVE] : {stats['total_size_mb']} MB")
            
            if stats['file_count'] > 0:
                avg_size_kb = (stats['total_size_bytes'] / stats['file_count']) / 1024
                logger.info(f"[DOC] : {avg_size_kb:.2f} KB")
            
            if args.detailed and stats['by_data_type']:
                logger.info(f"\n[DATA] :")
                for dtype, info in stats['by_data_type'].items():
                    logger.info(f"  {dtype}:")
                    logger.info(f"    : {info['count']}")
                    logger.info(f"    : {info['size_mb']} MB")
                    if info['count'] > 0:
                        avg_kb = (info['size_bytes'] / info['count']) / 1024
                        logger.info(f"    : {avg_kb:.2f} KB")
                        
        elif args.command == 'clean':
            # 
            logger.info("[CLEAN] ")
            
            if args.dry_run:
                logger.info("[SEARCH] : ")
            
            # 
            logger.info("[WARN] ")
        
        logger.info("[OK] CLI")
        
    except Exception as e:
        logger.error(f"[ERROR] : {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise


if __name__ == '__main__':
    main()