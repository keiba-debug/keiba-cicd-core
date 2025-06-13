#!/usr/bin/env python3
"""
競馬ブック バッチ処理 CLI

統合されたバッチ処理システムのコマンドラインインターフェース
"""

import argparse
import sys
from datetime import date

from .batch import DataFetcher, parse_date, setup_batch_logger


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(description='競馬ブック バッチ処理システム')
    
    # サブコマンドを設定
    subparsers = parser.add_subparsers(dest='command', help='利用可能なコマンド')
    
    # レース日程取得コマンド
    schedule_parser = subparsers.add_parser('schedule', help='レース日程を取得')
    schedule_parser.add_argument('--start-date', type=str, required=True, 
                                help='取得開始日 (YYYY/MM/DD or YY/MM/DD)')
    schedule_parser.add_argument('--end-date', type=str, 
                                help='取得終了日 (YYYY/MM/DD or YY/MM/DD、省略時は開始日と同じ)')
    schedule_parser.add_argument('--delay', type=int, default=3, 
                                help='リクエスト間の待機時間(秒)')
    
    # レースデータ取得コマンド
    data_parser = subparsers.add_parser('data', help='レースデータを取得')
    data_parser.add_argument('--start-date', type=str, required=True, 
                            help='取得開始日 (YYYY/MM/DD or YY/MM/DD)')
    data_parser.add_argument('--end-date', type=str, 
                            help='取得終了日 (YYYY/MM/DD or YY/MM/DD、省略時は開始日と同じ)')
    data_parser.add_argument('--data-types', type=str, default='seiseki,shutsuba,cyokyo,danwa', 
                            help='取得するデータタイプ (カンマ区切り) [seiseki,shutsuba,cyokyo,danwa]')
    data_parser.add_argument('--delay', type=int, default=3, 
                            help='リクエスト間の待機時間(秒)')
    
    # 全処理コマンド（日程取得→データ取得）
    full_parser = subparsers.add_parser('full', help='日程取得からデータ取得まで全て実行')
    full_parser.add_argument('--start-date', type=str, required=True, 
                            help='取得開始日 (YYYY/MM/DD or YY/MM/DD)')
    full_parser.add_argument('--end-date', type=str, 
                            help='取得終了日 (YYYY/MM/DD or YY/MM/DD、省略時は開始日と同じ)')
    full_parser.add_argument('--data-types', type=str, default='seiseki,shutsuba,cyokyo,danwa', 
                            help='取得するデータタイプ (カンマ区切り) [seiseki,shutsuba,cyokyo,danwa]')
    full_parser.add_argument('--delay', type=int, default=3, 
                            help='リクエスト間の待機時間(秒)')
    full_parser.add_argument('--wait-between-phases', type=int, default=5, 
                            help='日程取得とデータ取得の間の待機時間(秒)')
    
    # 共通オプション
    for p in [schedule_parser, data_parser, full_parser]:
        p.add_argument('--debug', action='store_true', help='デバッグモードを有効化')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    try:
        # 日付をパース
        start_date = parse_date(args.start_date)
        
        if args.end_date:
            end_date = parse_date(args.end_date)
        else:
            end_date = start_date
        
        # データ取得クラスを初期化
        fetcher = DataFetcher(delay=args.delay)
        logger = setup_batch_logger('batch_cli')
        
        logger.info(f"バッチ処理を開始: {args.command}")
        logger.info(f"期間: {start_date} ～ {end_date}")
        
        if args.command == 'schedule':
            # レース日程取得
            logger.info("レース日程取得を開始")
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime("%Y%m%d")
                logger.info(f"日程取得: {date_str}")
                success = fetcher.fetch_race_schedule(date_str)
                if not success:
                    logger.error(f"日程取得に失敗: {date_str}")
                
                # 次の日へ
                from datetime import timedelta
                current_date += timedelta(days=1)
                
                # 最後の日以外は待機
                if current_date <= end_date:
                    import time
                    time.sleep(args.delay)
            
        elif args.command == 'data':
            # レースデータ取得
            data_types = args.data_types.split(',')
            logger.info(f"レースデータ取得を開始: {', '.join(data_types)}")
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime("%Y%m%d")
                logger.info(f"データ取得: {date_str}")
                summary = fetcher.fetch_all_race_data(date_str, data_types)
                if not summary.get('success'):
                    logger.error(f"データ取得に失敗: {date_str}")
                else:
                    logger.info(f"データ取得完了: {summary.get('total_success', 0)}件成功, {summary.get('total_failed', 0)}件失敗")
                
                # 次の日へ
                from datetime import timedelta
                current_date += timedelta(days=1)
                
                # 最後の日以外は待機
                if current_date <= end_date:
                    import time
                    time.sleep(args.delay)
            
        elif args.command == 'full':
            # 全処理実行
            data_types = args.data_types.split(',')
            logger.info("全処理を開始（日程取得→データ取得）")
            
            # Phase 1: レース日程取得
            logger.info("Phase 1: レース日程取得")
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime("%Y%m%d")
                logger.info(f"日程取得: {date_str}")
                success = fetcher.fetch_race_schedule(date_str)
                if not success:
                    logger.error(f"日程取得に失敗: {date_str}")
                
                # 次の日へ
                from datetime import timedelta
                current_date += timedelta(days=1)
                
                # 最後の日以外は待機
                if current_date <= end_date:
                    import time
                    time.sleep(args.delay)
            
            # 待機
            import time
            logger.info(f"Phase間待機: {args.wait_between_phases}秒")
            time.sleep(args.wait_between_phases)
            
            # Phase 2: レースデータ取得
            logger.info(f"Phase 2: レースデータ取得 ({', '.join(data_types)})")
            current_date = start_date
            while current_date <= end_date:
                date_str = current_date.strftime("%Y%m%d")
                logger.info(f"データ取得: {date_str}")
                summary = fetcher.fetch_all_race_data(date_str, data_types)
                if not summary.get('success'):
                    logger.error(f"データ取得に失敗: {date_str}")
                else:
                    logger.info(f"データ取得完了: {summary.get('total_success', 0)}件成功, {summary.get('total_failed', 0)}件失敗")
                
                # 次の日へ
                from datetime import timedelta
                current_date += timedelta(days=1)
                
                # 最後の日以外は待機
                if current_date <= end_date:
                    import time
                    time.sleep(args.delay)
        
        logger.info("バッチ処理が完了しました")
        return 0
        
    except Exception as e:
        logger = setup_batch_logger('batch_cli')
        logger.error(f"エラーが発生しました: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 