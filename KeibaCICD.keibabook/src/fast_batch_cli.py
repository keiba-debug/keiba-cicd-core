#!/usr/bin/env python3
"""
高速バッチCLI（requests版）

RequestsScraperを使用した高速版のバッチ処理CLI
- Selenium不使用で大幅な高速化
- 並列処理対応
- 詳細な進捗表示
"""

import argparse
import logging
from datetime import datetime, timedelta

from .batch.optimized_data_fetcher import OptimizedDataFetcher
from .batch.core.common import parse_date, setup_batch_logger


def main():
    """
    高速バッチCLIのメインエントリーポイント
    """
    parser = argparse.ArgumentParser(
        description='競馬ブック高速データ取得システム（requests版）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 高速レース日程取得
  python -m src.keibabook.fast_batch_cli schedule --start-date 2025/06/07

  # 高速データ取得（並列処理）
  python -m src.keibabook.fast_batch_cli data --start-date 2025/06/07 --max-workers 8

  # 高速全処理（最大性能）
  python -m src.keibabook.fast_batch_cli full --start-date 2025/06/07 --delay 0.5 --max-workers 10

パフォーマンス改善:
  - RequestsScraperを使用（Selenium不使用）
  - 並列処理対応（最大22コア活用可能）
  - 10-20倍の速度向上
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='実行コマンド')
    
    # 共通引数
    def add_common_args(subparser):
        subparser.add_argument('--start-date', required=True, help='開始日 (YYYY/MM/DD)')
        subparser.add_argument('--end-date', help='終了日 (YYYY/MM/DD, 省略時は開始日と同じ)')
        subparser.add_argument('--delay', type=float, default=1.0, help='リクエスト間隔（秒, デフォルト: 1.0）')
        subparser.add_argument('--max-workers', type=int, default=5, help='並列処理数（デフォルト: 5）')
        subparser.add_argument('--debug', action='store_true', help='デバッグモード')
    
    # schedule サブコマンド
    schedule_parser = subparsers.add_parser('schedule', help='レース日程取得（高速版）')
    add_common_args(schedule_parser)
    
    # data サブコマンド
    data_parser = subparsers.add_parser('data', help='レースデータ取得（高速並列版）')
    add_common_args(data_parser)
    data_parser.add_argument('--data-types', default='seiseki,shutsuba,cyokyo,danwa', 
                           help='データタイプ（カンマ区切り, デフォルト: seiseki,shutsuba,cyokyo,danwa）')
    
    # full サブコマンド
    full_parser = subparsers.add_parser('full', help='全処理実行（超高速版）')
    add_common_args(full_parser)
    full_parser.add_argument('--data-types', default='seiseki,shutsuba,cyokyo,danwa',
                           help='データタイプ（カンマ区切り, デフォルト: seiseki,shutsuba,cyokyo,danwa）')
    full_parser.add_argument('--wait-between-phases', type=float, default=2.0,
                           help='Phase間待機時間（秒, デフォルト: 2.0）')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # ログ設定
    logger = setup_batch_logger('fast_batch_cli')
    logger.info("🚀 高速バッチCLI（requests版）を開始")
    logger.info(f"📊 コマンド: {args.command}")
    logger.info(f"⚡ 並列処理数: {args.max_workers}")
    logger.info(f"🔥 RequestsScraperを使用（Selenium不使用）")
    
    try:
        # 日付解析
        start_date = parse_date(args.start_date)
        end_date = parse_date(args.end_date) if args.end_date else start_date
        
        logger.info(f"📅 処理期間: {start_date} ～ {end_date}")
        
        # OptimizedDataFetcherを初期化
        fetcher = OptimizedDataFetcher(delay=args.delay, max_workers=args.max_workers)
        
        if args.command == 'schedule':
            # レース日程取得（高速版）
            logger.info("🚀 高速レース日程取得を開始")
            current_date = start_date
            total_success = 0
            total_failed = 0
            
            while current_date <= end_date:
                date_str = current_date.strftime("%Y%m%d")
                logger.info(f"⚡ 日程取得: {date_str}")
                
                success = fetcher.fetch_race_schedule_fast(date_str)
                if success:
                    total_success += 1
                    logger.info(f"✅ 日程取得成功: {date_str}")
                else:
                    total_failed += 1
                    logger.error(f"❌ 日程取得失敗: {date_str}")
                
                current_date += timedelta(days=1)
            
            logger.info(f"📊 日程取得完了: 成功 {total_success}件, 失敗 {total_failed}件")
            
        elif args.command == 'data':
            # レースデータ取得（高速並列版）
            data_types = args.data_types.split(',')
            logger.info(f"🚀 高速並列データ取得を開始: {', '.join(data_types)}")
            
            current_date = start_date
            total_success = 0
            total_failed = 0
            total_processing_time = 0
            
            while current_date <= end_date:
                date_str = current_date.strftime("%Y%m%d")
                logger.info(f"⚡ データ取得: {date_str}")
                
                summary = fetcher.fetch_all_race_data_parallel_fast(date_str, data_types)
                if summary.get('success'):
                    total_success += summary.get('total_success', 0)
                    total_failed += summary.get('total_failed', 0)
                    total_processing_time += summary.get('processing_time_seconds', 0)
                    
                    logger.info(f"✅ データ取得完了: {summary.get('total_success', 0)}件成功, "
                              f"{summary.get('total_failed', 0)}件失敗, "
                              f"{summary.get('processing_time_seconds', 0):.2f}秒")
                else:
                    logger.error(f"❌ データ取得失敗: {date_str}")
                
                current_date += timedelta(days=1)
            
            logger.info(f"📊 全データ取得完了")
            logger.info(f"✅ 総成功: {total_success}件")
            logger.info(f"❌ 総失敗: {total_failed}件")
            logger.info(f"⏱️ 総処理時間: {total_processing_time:.2f}秒")
            if total_processing_time > 0:
                logger.info(f"🚀 平均処理速度: {(total_success + total_failed) / total_processing_time:.2f}タスク/秒")
            
        elif args.command == 'full':
            # 全処理実行（超高速版）
            data_types = args.data_types.split(',')
            logger.info("🚀 超高速全処理を開始（日程取得→データ取得）")
            
            # Phase 1: レース日程取得
            logger.info("⚡ Phase 1: 高速レース日程取得")
            current_date = start_date
            schedule_success = 0
            schedule_failed = 0
            
            while current_date <= end_date:
                date_str = current_date.strftime("%Y%m%d")
                logger.info(f"📅 日程取得: {date_str}")
                
                success = fetcher.fetch_race_schedule_fast(date_str)
                if success:
                    schedule_success += 1
                else:
                    schedule_failed += 1
                
                current_date += timedelta(days=1)
            
            logger.info(f"✅ Phase 1完了: 成功 {schedule_success}件, 失敗 {schedule_failed}件")
            
            # Phase間待機
            import time
            logger.info(f"⏸️ Phase間待機: {args.wait_between_phases}秒")
            time.sleep(args.wait_between_phases)
            
            # Phase 2: レースデータ取得
            logger.info(f"⚡ Phase 2: 高速並列データ取得 ({', '.join(data_types)})")
            current_date = start_date
            total_success = 0
            total_failed = 0
            total_processing_time = 0
            
            while current_date <= end_date:
                date_str = current_date.strftime("%Y%m%d")
                logger.info(f"🏇 データ取得: {date_str}")
                
                summary = fetcher.fetch_all_race_data_parallel_fast(date_str, data_types)
                if summary.get('success'):
                    total_success += summary.get('total_success', 0)
                    total_failed += summary.get('total_failed', 0)
                    total_processing_time += summary.get('processing_time_seconds', 0)
                    
                    logger.info(f"✅ {date_str}完了: {summary.get('total_success', 0)}件成功, "
                              f"{summary.get('total_failed', 0)}件失敗, "
                              f"{summary.get('processing_time_seconds', 0):.2f}秒, "
                              f"{summary.get('tasks_per_second', 0):.2f}タスク/秒")
                
                current_date += timedelta(days=1)
            
            # 最終サマリー
            logger.info("🎉 超高速全処理完了")
            logger.info("=" * 60)
            logger.info("📊 最終結果サマリー")
            logger.info("=" * 60)
            logger.info(f"📅 Phase 1（日程取得）: 成功 {schedule_success}件, 失敗 {schedule_failed}件")
            logger.info(f"🏇 Phase 2（データ取得）: 成功 {total_success}件, 失敗 {total_failed}件")
            logger.info(f"⏱️ 総処理時間: {total_processing_time:.2f}秒")
            if total_processing_time > 0:
                logger.info(f"🚀 平均処理速度: {(total_success + total_failed) / total_processing_time:.2f}タスク/秒")
            logger.info("=" * 60)
        
        # リソース解放
        fetcher.close()
        logger.info("✅ 高速バッチCLI処理完了")
        
    except Exception as e:
        logger.error(f"❌ エラーが発生しました: {e}")
        raise


if __name__ == '__main__':
    main() 