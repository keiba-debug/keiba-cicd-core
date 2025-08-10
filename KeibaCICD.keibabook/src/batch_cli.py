#!/usr/bin/env python3
"""
  CLI


"""

import argparse
import sys
from datetime import date

from .batch import DataFetcher, parse_date, setup_batch_logger


def main():
    """"""
    parser = argparse.ArgumentParser(description=' ')
    
    # 
    subparsers = parser.add_subparsers(dest='command', help='')
    
    # 
    schedule_parser = subparsers.add_parser('schedule', help='')
    schedule_parser.add_argument('--start-date', type=str, required=True, 
                                help=' (YYYY/MM/DD or YY/MM/DD)')
    schedule_parser.add_argument('--end-date', type=str, 
                                help=' (YYYY/MM/DD or YY/MM/DD)')
    schedule_parser.add_argument('--delay', type=int, default=3, 
                                help='()')
    
    # 
    data_parser = subparsers.add_parser('data', help='')
    data_parser.add_argument('--start-date', type=str, required=True, 
                            help=' (YYYY/MM/DD or YY/MM/DD)')
    data_parser.add_argument('--end-date', type=str, 
                            help=' (YYYY/MM/DD or YY/MM/DD)')
    data_parser.add_argument('--data-types', type=str, default='seiseki,shutsuba,cyokyo,danwa', 
                            help=' () [seiseki,shutsuba,cyokyo,danwa]')
    data_parser.add_argument('--delay', type=int, default=3, 
                            help='()')
    
    # →
    full_parser = subparsers.add_parser('full', help='')
    full_parser.add_argument('--start-date', type=str, required=True, 
                            help=' (YYYY/MM/DD or YY/MM/DD)')
    full_parser.add_argument('--end-date', type=str, 
                            help=' (YYYY/MM/DD or YY/MM/DD)')
    full_parser.add_argument('--data-types', type=str, default='seiseki,shutsuba,cyokyo,danwa', 
                            help=' () [seiseki,shutsuba,cyokyo,danwa]')
    full_parser.add_argument('--delay', type=int, default=3, 
                            help='()')
    full_parser.add_argument('--wait-between-phases', type=int, default=5, 
                            help='()')
    
    # 
    for p in [schedule_parser, data_parser, full_parser]:
        p.add_argument('--debug', action='store_true', help='')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        # 
        start_date = parse_date(args.start_date)
        
        if args.end_date:
            end_date = parse_date(args.end_date)
        else:
            end_date = start_date
        
        # 
        fetcher = DataFetcher(delay=args.delay)
        logger = setup_batch_logger('batch_cli')
        
        logger.info(f": {args.command}")
        logger.info(f": {start_date}  {end_date}")
        
        if args.command == 'schedule':
            # 
            logger.info("")
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime("%Y%m%d")
                logger.info(f": {date_str}")
                success = fetcher.fetch_race_schedule(date_str)
                if not success:
                    logger.error(f": {date_str}")
                
                # 
                from datetime import timedelta
                current_date += timedelta(days=1)
                
                # 
                if current_date <= end_date:
                    import time
                    time.sleep(args.delay)
            
        elif args.command == 'data':
            # 
            data_types = args.data_types.split(',')
            logger.info(f": {', '.join(data_types)}")
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime("%Y%m%d")
                logger.info(f": {date_str}")
                summary = fetcher.fetch_all_race_data(date_str, data_types)
                if not summary.get('success'):
                    logger.error(f": {date_str}")
                else:
                    logger.info(f": {summary.get('total_success', 0)}, {summary.get('total_failed', 0)}")
                
                # 
                from datetime import timedelta
                current_date += timedelta(days=1)
                
                # 
                if current_date <= end_date:
                    import time
                    time.sleep(args.delay)
            
        elif args.command == 'full':
            # 
            data_types = args.data_types.split(',')
            logger.info("→")
            
            # Phase 1: 
            logger.info("Phase 1: ")
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime("%Y%m%d")
                logger.info(f": {date_str}")
                success = fetcher.fetch_race_schedule(date_str)
                if not success:
                    logger.error(f": {date_str}")
                
                # 
                from datetime import timedelta
                current_date += timedelta(days=1)
                
                # 
                if current_date <= end_date:
                    import time
                    time.sleep(args.delay)
            
            # 
            import time
            logger.info(f"Phase: {args.wait_between_phases}")
            time.sleep(args.wait_between_phases)
            
            # Phase 2: 
            logger.info(f"Phase 2:  ({', '.join(data_types)})")
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime("%Y%m%d")
                logger.info(f": {date_str}")
                summary = fetcher.fetch_all_race_data(date_str, data_types)
                if not summary.get('success'):
                    logger.error(f": {date_str}")
                else:
                    logger.info(f": {summary.get('total_success', 0)}, {summary.get('total_failed', 0)}")
                
                # 
                from datetime import timedelta
                current_date += timedelta(days=1)
                
                # 
                if current_date <= end_date:
                    import time
                    time.sleep(args.delay)
        
        logger.info("")
        return 0
        
    except Exception as e:
        logger = setup_batch_logger('batch_cli')
        logger.error(f": {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 