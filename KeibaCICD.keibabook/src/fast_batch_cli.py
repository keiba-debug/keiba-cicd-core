#!/usr/bin/env python3
"""
CLIrequests

RequestsScraperCLI
- Selenium
- 
- 
"""

import argparse
import logging
from datetime import datetime, timedelta

from .batch.optimized_data_fetcher import OptimizedDataFetcher
from .batch.core.common import parse_date, setup_batch_logger


def main():
    """
    CLI
    """
    parser = argparse.ArgumentParser(
        description='requests',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
:
  # 
  python -m src.keibabook.fast_batch_cli schedule --start-date 2025/06/07

  # 
  python -m src.keibabook.fast_batch_cli data --start-date 2025/06/07 --max-workers 8

  # 
  python -m src.keibabook.fast_batch_cli full --start-date 2025/06/07 --delay 0.5 --max-workers 10

:
  - RequestsScraperSelenium
  - 22
  - 10-20
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='')
    
    # 
    def add_common_args(subparser):
        subparser.add_argument('--start-date', required=True, help=' (YYYY/MM/DD)')
        subparser.add_argument('--end-date', help=' (YYYY/MM/DD, )')
        subparser.add_argument('--delay', type=float, default=1.0, help=', : 1.0')
        subparser.add_argument('--max-workers', type=int, default=5, help=': 5')
        subparser.add_argument('--debug', action='store_true', help='')
    
    # schedule 
    schedule_parser = subparsers.add_parser('schedule', help='')
    add_common_args(schedule_parser)
    
    # data 
    data_parser = subparsers.add_parser('data', help='')
    add_common_args(data_parser)
    data_parser.add_argument('--data-types', default='seiseki,shutsuba,cyokyo,danwa,syoin,paddok', 
                           help=', : seiseki,shutsuba,cyokyo,danwa,syoin,paddok')
    
    # full 
    full_parser = subparsers.add_parser('full', help='')
    add_common_args(full_parser)
    full_parser.add_argument('--data-types', default='seiseki,shutsuba,cyokyo,danwa,syoin,paddok',
                           help=', : seiseki,shutsuba,cyokyo,danwa,syoin,paddok')
    full_parser.add_argument('--wait-between-phases', type=float, default=2.0,
                           help='Phase, : 2.0')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 
    logger = setup_batch_logger('fast_batch_cli')
    logger.info("[START] CLIrequests")
    logger.info(f"[DATA] : {args.command}")
    logger.info(f"[FAST] : {args.max_workers}")
    logger.info(f"[HOT] RequestsScraperSelenium")
    
    try:
        # 
        start_date = parse_date(args.start_date)
        end_date = parse_date(args.end_date) if args.end_date else start_date
        
        logger.info(f"[DATE] : {start_date}  {end_date}")
        
        # OptimizedDataFetcher
        fetcher = OptimizedDataFetcher(delay=args.delay, max_workers=args.max_workers)
        
        if args.command == 'schedule':
            # 
            logger.info("[START] ")
            current_date = start_date
            total_success = 0
            total_failed = 0
            
            while current_date <= end_date:
                date_str = current_date.strftime("%Y%m%d")
                logger.info(f"[FAST] : {date_str}")
                
                success = fetcher.fetch_race_schedule_fast(date_str)
                if success:
                    total_success += 1
                    logger.info(f"[OK] : {date_str}")
                else:
                    total_failed += 1
                    logger.error(f"[ERROR] : {date_str}")
                
                current_date += timedelta(days=1)
            
            logger.info(f"[DATA] :  {total_success},  {total_failed}")
            
        elif args.command == 'data':
            # 
            data_types = args.data_types.split(',')
            logger.info(f"[START] : {', '.join(data_types)}")
            
            current_date = start_date
            total_success = 0
            total_failed = 0
            total_processing_time = 0
            
            while current_date <= end_date:
                date_str = current_date.strftime("%Y%m%d")
                logger.info(f"[FAST] : {date_str}")
                
                summary = fetcher.fetch_all_race_data_parallel_fast(date_str, data_types)
                if summary.get('success'):
                    total_success += summary.get('total_success', 0)
                    total_failed += summary.get('total_failed', 0)
                    total_processing_time += summary.get('processing_time_seconds', 0)
                    
                    logger.info(f"[OK] : {summary.get('total_success', 0)}, "
                              f"{summary.get('total_failed', 0)}, "
                              f"{summary.get('processing_time_seconds', 0):.2f}")
                else:
                    logger.error(f"[ERROR] : {date_str}")
                
                current_date += timedelta(days=1)
            
            logger.info(f"[DATA] ")
            logger.info(f"[OK] : {total_success}")
            logger.info(f"[ERROR] : {total_failed}")
            logger.info(f"[TIME] : {total_processing_time:.2f}")
            if total_processing_time > 0:
                logger.info(f"[START] : {(total_success + total_failed) / total_processing_time:.2f}/")
            
        elif args.command == 'full':
            # 
            data_types = args.data_types.split(',')
            logger.info("[START] →")
            
            # Phase 1: 
            logger.info("[FAST] Phase 1: ")
            current_date = start_date
            schedule_success = 0
            schedule_failed = 0
            
            while current_date <= end_date:
                date_str = current_date.strftime("%Y%m%d")
                logger.info(f"[DATE] : {date_str}")
                
                success = fetcher.fetch_race_schedule_fast(date_str)
                if success:
                    schedule_success += 1
                else:
                    schedule_failed += 1
                
                current_date += timedelta(days=1)
            
            logger.info(f"[OK] Phase 1:  {schedule_success},  {schedule_failed}")
            
            # Phase
            import time
            logger.info(f"[PAUSE] Phase: {args.wait_between_phases}")
            time.sleep(args.wait_between_phases)
            
            # Phase 2: 
            logger.info(f"[FAST] Phase 2:  ({', '.join(data_types)})")
            current_date = start_date
            total_success = 0
            total_failed = 0
            total_processing_time = 0
            
            while current_date <= end_date:
                date_str = current_date.strftime("%Y%m%d")
                logger.info(f"[RACE] : {date_str}")
                
                summary = fetcher.fetch_all_race_data_parallel_fast(date_str, data_types)
                if summary.get('success'):
                    total_success += summary.get('total_success', 0)
                    total_failed += summary.get('total_failed', 0)
                    total_processing_time += summary.get('processing_time_seconds', 0)
                    
                    logger.info(f"[OK] {date_str}: {summary.get('total_success', 0)}, "
                              f"{summary.get('total_failed', 0)}, "
                              f"{summary.get('processing_time_seconds', 0):.2f}, "
                              f"{summary.get('tasks_per_second', 0):.2f}/")
                
                current_date += timedelta(days=1)
            
            # 
            logger.info("[DONE] ")
            logger.info("=" * 60)
            logger.info("[DATA] ")
            logger.info("=" * 60)
            logger.info(f"[DATE] Phase 1:  {schedule_success},  {schedule_failed}")
            logger.info(f"[RACE] Phase 2:  {total_success},  {total_failed}")
            logger.info(f"[TIME] : {total_processing_time:.2f}")
            if total_processing_time > 0:
                logger.info(f"[START] : {(total_success + total_failed) / total_processing_time:.2f}/")
            logger.info("=" * 60)
        
        # 
        fetcher.close()
        logger.info("[OK] CLI")
        
    except Exception as e:
        logger.error(f"[ERROR] : {e}")
        raise


if __name__ == '__main__':
    main() 