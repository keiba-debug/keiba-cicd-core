#!/usr/bin/env python3
"""
CLI

CLI
"""

import argparse
import logging
import os
from datetime import datetime, timedelta

from .integrator.race_data_integrator import RaceDataIntegrator
from .batch.core.common import parse_date, setup_batch_logger


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
  python -m src.keibabook.integrator_cli single --race-id 202501010101
  
  # 
  python -m src.keibabook.integrator_cli batch --date 2025/01/01
  
  # 
  python -m src.keibabook.integrator_cli update --race-id 202501010101
  
  # 
  python -m src.keibabook.integrator_cli batch --start-date 2025/01/01 --end-date 2025/01/03

:
  - 1
  - 
  - 
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='')
    
    # single  - 
    single_parser = subparsers.add_parser('single', help='')
    single_parser.add_argument('--race-id', required=True, help='ID (: 202501010101)')
    single_parser.add_argument('--output-dir', help='')
    single_parser.add_argument('--organized', action='store_true', help='organizedディレクトリ構造で保存')
    
    # batch  - 
    batch_parser = subparsers.add_parser('batch', help='/')
    batch_parser.add_argument('--date', help=' (YYYY/MM/DD)')
    batch_parser.add_argument('--start-date', help=' (YYYY/MM/DD)')
    batch_parser.add_argument('--end-date', help=' (YYYY/MM/DD)')
    batch_parser.add_argument('--organized', action='store_true', help='organizedディレクトリ構造で保存')
    
    # update  - 
    update_parser = subparsers.add_parser('update', help='')
    update_parser.add_argument('--race-id', help='ID')
    update_parser.add_argument('--date', help=' (YYYY/MM/DD)')
    update_parser.add_argument('--organized', action='store_true', help='organizedディレクトリ構造で保存')
    
    # analyze  - 
    analyze_parser = subparsers.add_parser('analyze', help='')
    analyze_parser.add_argument('--race-id', required=True, help='ID')
    analyze_parser.add_argument('--output-format', choices=['json', 'text', 'html'], 
                               default='text', help='')
    analyze_parser.add_argument('--organized', action='store_true', help='organizedディレクトリ構造で保存')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 
    logger = setup_batch_logger('integrator_cli')
    logger.info("[DATA] CLI")
    logger.info(f"[TARGET] : {args.command}")
    
    try:
        # use_organized_dirフラグの確認
        use_organized = getattr(args, 'organized', False)
        
        # 
        integrator = RaceDataIntegrator(use_organized_dir=use_organized)
        
        if args.command == 'single':
            # 
            logger.info(f"[MEMO] : {args.race_id}")
            
            result = integrator.create_integrated_file(args.race_id)
            
            if result:
                logger.info(f"[OK] : {args.race_id}")
                logger.info(f"[DATA] : {len(result['entries'])}")
                
                # 
                sources = result['meta']['data_sources']
                logger.info(f"[FILE] :")
                for key, status in sources.items():
                    emoji = "[OK]" if status == "" else "[ERROR]"
                    logger.info(f"  {emoji} {key}: {status}")
            else:
                logger.error(f"[ERROR] : {args.race_id}")
                
        elif args.command == 'batch':
            # 
            if args.date:
                # 
                date_obj = parse_date(args.date)
                date_str = date_obj.strftime("%Y%m%d")
                
                logger.info(f"[DATE] : {date_str}")
                summary = integrator.batch_create_integrated_files(date_str)
                
                if summary['success']:
                    logger.info(f"[OK] ")
                    logger.info(f"[DATA] :")
                    logger.info(f"  : {summary['total_races']}")
                    logger.info(f"  : {summary['success_count']}")
                    logger.info(f"  : {summary['failed_count']}")
                    logger.info(f"  : {summary['success_rate']:.1f}%")
                    
            elif args.start_date:
                # 
                start_date = parse_date(args.start_date)
                end_date = parse_date(args.end_date) if args.end_date else start_date
                
                logger.info(f"[DATE] : {start_date}  {end_date}")
                
                current_date = start_date
                total_success = 0
                total_failed = 0
                total_races = 0
                
                while current_date <= end_date:
                    date_str = current_date.strftime("%Y%m%d")
                    logger.info(f"[CALENDAR] : {date_str}")
                    
                    summary = integrator.batch_create_integrated_files(date_str)
                    if summary.get('success'):
                        total_races += summary.get('total_races', 0)
                        total_success += summary.get('success_count', 0)
                        total_failed += summary.get('failed_count', 0)
                    
                    current_date += timedelta(days=1)
                
                logger.info(f"[TARGET] ")
                logger.info(f"[DATA] :")
                logger.info(f"  : {(end_date - start_date).days + 1}")
                logger.info(f"  : {total_races}")
                logger.info(f"  : {total_success}")
                logger.info(f"  : {total_failed}")
                if total_races > 0:
                    logger.info(f"  : {(total_success / total_races * 100):.1f}%")
            else:
                logger.error("")
                
        elif args.command == 'update':
            # 
            if args.race_id:
                logger.info(f"[REFRESH] : {args.race_id}")
                success = integrator.update_with_results(args.race_id)
                
                if success:
                    logger.info(f"[OK] : {args.race_id}")
                else:
                    logger.error(f"[ERROR] : {args.race_id}")
                    
            elif args.date:
                # 
                date_obj = parse_date(args.date)
                date_str = date_obj.strftime("%Y%m%d")
                
                logger.info(f"[REFRESH] : {date_str}")
                
                # ID
                from .batch.core.common import get_race_ids_file_path
                race_ids_file = get_race_ids_file_path(date_str)
                
                if os.path.exists(race_ids_file):
                    import json
                    with open(race_ids_file, 'r', encoding='utf-8') as f:
                        race_ids_data = json.load(f)
                    
                    race_ids = []
                    for venue, races in race_ids_data.get('kaisai_data', {}).items():
                        race_ids.extend(races)
                    
                    success_count = 0
                    for race_id in race_ids:
                        if integrator.update_with_results(race_id):
                            success_count += 1
                    
                    logger.info(f"[OK] : {success_count}/{len(race_ids)}")
                else:
                    logger.error(f"ID: {date_str}")
            else:
                logger.error("ID")
                
        elif args.command == 'analyze':
            # 
            logger.info(f"[SEARCH] : {args.race_id}")
            
            # 
            integrated_path = integrator._get_integrated_file_path(args.race_id)
            
            if os.path.exists(integrated_path):
                import json
                with open(integrated_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                logger.info(f"[DATA] ")
                logger.info(f"=" * 60)
                
                # 
                race_info = data['race_info']
                logger.info(f"[DATE] : {race_info['date']}")
                logger.info(f"[VENUE] : {race_info['venue']} {race_info['race_number']}R")
                logger.info(f"[TROPHY] : {race_info['race_name']}")
                logger.info(f"[RULER] : {race_info['track']}{race_info['distance']}m")
                logger.info(f"[CLOUD] : {race_info['weather']} / : {race_info['track_condition']}")
                
                # 
                logger.info(f"[HORSE] : {len(data['entries'])}")
                
                # 
                if data['analysis']['favorites']:
                    logger.info(f"[STAR] :")
                    for fav in data['analysis']['favorites']:
                        logger.info(f"  {fav['horse_number']} {fav['horse_name']} ({fav['odds_rank']})")
                
                # 
                if data['analysis']['training_highlights']:
                    logger.info(f"[STRONG] :")
                    for highlight in data['analysis']['training_highlights']:
                        logger.info(f"  {highlight}")
                
                # 
                data_completeness = {
                    '': 0,
                    '': 0,
                    '': 0,
                    '': 0
                }
                
                for entry in data['entries']:
                    if entry.get('entry_data'):
                        data_completeness[''] += 1
                    if entry.get('training_data'):
                        data_completeness[''] += 1
                    if entry.get('stable_comment'):
                        data_completeness[''] += 1
                    if entry.get('result'):
                        data_completeness[''] += 1
                
                logger.info(f"[FILE] :")
                total_horses = len(data['entries'])
                for dtype, count in data_completeness.items():
                    percentage = (count / total_horses * 100) if total_horses > 0 else 0
                    logger.info(f"  {dtype}: {count}/{total_horses} ({percentage:.1f}%)")
                
                logger.info(f"=" * 60)
            else:
                logger.error(f": {args.race_id}")
        
        logger.info("[OK] CLI")
        
    except Exception as e:
        logger.error(f"[ERROR] : {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise


if __name__ == '__main__':
    main()