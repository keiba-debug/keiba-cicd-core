#!/usr/bin/env python3
"""
競馬ブック バッチ処理スクリプト

日付範囲を指定して、レースID取得からデータ取得までを自動で実行します。

使用例:
    python batch_process.py --start-date 2025/6/14 --end-date 2025/6/15 --data-types shutsuba,seiseki,cyokyo --delay 3 --wait-time 5
"""

import argparse
import sys
import os
import time
from datetime import datetime, timedelta
from pathlib import Path

# KeibaCICD.keibabook/src をパスに追加
sys.path.insert(0, str(Path(__file__).parent / "KeibaCICD.keibabook" / "src"))

from main import scrape_and_parse
from utils.config import Config
from utils.logger import setup_logger


def parse_date(date_str):
    """日付文字列をパース"""
    try:
        # YYYY/MM/DD または YY/MM/DD 形式をサポート
        if len(date_str.split('/')[0]) == 2:
            # YY/MM/DD 形式の場合、20YYに変換
            parts = date_str.split('/')
            year = int(parts[0])
            if year >= 0 and year <= 99:
                year = 2000 + year
            date_str = f"{year}/{parts[1]}/{parts[2]}"
        
        return datetime.strptime(date_str, '%Y/%m/%d').date()
    except ValueError:
        raise ValueError(f"無効な日付形式: {date_str}. YYYY/MM/DD または YY/MM/DD 形式で入力してください。")


def generate_race_ids(start_date, end_date):
    """指定期間のレースIDを生成"""
    race_ids = []
    current_date = start_date
    
    # 基本的な競馬場コード（東京、中山、阪神、京都など）
    venue_codes = ['01', '02', '03', '04', '05', '06', '07', '08']
    
    while current_date <= end_date:
        date_str = current_date.strftime('%Y%m%d')
        
        # 各競馬場・各開催・各レースのIDを生成
        for venue in venue_codes:
            for kai in ['01', '02', '03']:  # 開催回
                for race_num in range(1, 13):  # 1〜12レース
                    race_id = f"{date_str}{venue}{kai}{race_num:02d}"
                    race_ids.append(race_id)
        
        current_date += timedelta(days=1)
    
    return race_ids


def batch_process(start_date, end_date, data_types, delay=3, wait_time=5):
    """バッチ処理のメイン関数"""
    logger = setup_logger("batch_process", level="INFO")
    
    logger.info("🏇 バッチ処理を開始します")
    logger.info(f"📅 期間: {start_date} ～ {end_date}")
    logger.info(f"📊 データタイプ: {', '.join(data_types)}")
    logger.info(f"⏱️ 遅延: {delay}秒")
    logger.info(f"⏸️ 待機時間: {wait_time}秒")
    
    try:
        # Phase 1: レースID生成
        logger.info("=" * 50)
        logger.info("🔢 Phase 1: レースID生成")
        logger.info("=" * 50)
        
        race_ids = generate_race_ids(start_date, end_date)
        
        # テスト用に最初の数件のみ処理
        test_race_ids = race_ids[:10]  # 最初の10件でテスト
        
        logger.info(f"📊 生成されたレース数: {len(race_ids)}")
        logger.info(f"🧪 テスト実行: 最初の {len(test_race_ids)} 件")
        
        # Phase間待機
        logger.info(f"⏸️ Phase間待機: {wait_time}秒")
        time.sleep(wait_time)
        
        # Phase 2: データ取得
        logger.info("=" * 50)
        logger.info("⚙️ Phase 2: データ取得")
        logger.info("=" * 50)
        
        success_count = 0
        error_count = 0
        
        for i, race_id in enumerate(test_race_ids):
            logger.info(f"🏇 処理中 ({i+1}/{len(test_race_ids)}): {race_id}")
            
            try:
                # 各データタイプに対してスクレイピング実行
                for data_type in data_types:
                    if data_type == 'seiseki':
                        success = scrape_and_parse(race_id, save_html=True, use_requests=True)
                        if success:
                            success_count += 1
                        else:
                            error_count += 1
                    elif data_type == 'shutsuba':
                        # 出馬表はmulti_typeモードで取得
                        from main import scrape_and_parse_multi_type
                        success = scrape_and_parse_multi_type(race_id, ['syutuba'], save_html=True, use_requests=True)
                        if success:
                            success_count += 1
                        else:
                            error_count += 1
                    elif data_type == 'cyokyo':
                        # 調教はmulti_typeモードで取得
                        from main import scrape_and_parse_multi_type
                        success = scrape_and_parse_multi_type(race_id, ['cyokyo'], save_html=True, use_requests=True)
                        if success:
                            success_count += 1
                        else:
                            error_count += 1
                
                # 遅延
                if i < len(test_race_ids) - 1:  # 最後以外は待機
                    time.sleep(delay)
                    
            except Exception as e:
                logger.error(f"❌ エラー: {race_id} - {e}")
                error_count += 1
                continue
        
        # 結果サマリー
        logger.info("=" * 50)
        logger.info("📊 バッチ処理完了")
        logger.info("=" * 50)
        logger.info(f"✅ 成功: {success_count}")
        logger.info(f"❌ エラー: {error_count}")
        logger.info(f"📈 成功率: {success_count/(success_count+error_count)*100:.1f}%" if (success_count + error_count) > 0 else "0%")
        
        return success_count > 0
        
    except Exception as e:
        logger.error(f"❌ バッチ処理中にエラーが発生しました: {e}")
        return False


def main():
    """メイン関数"""
    parser = argparse.ArgumentParser(
        description='競馬ブック バッチ処理スクリプト',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
    python batch_process.py --start-date 2025/6/14 --end-date 2025/6/15 --data-types shutsuba,seiseki,cyokyo --delay 3 --wait-time 5
    
    python batch_process.py --start-date 25/6/14 --data-types seiseki --delay 2
        """
    )
    
    parser.add_argument('--start-date', required=True, 
                       help='取得開始日 (YYYY/MM/DD or YY/MM/DD形式)')
    parser.add_argument('--end-date', 
                       help='取得終了日 (YYYY/MM/DD or YY/MM/DD形式、省略時は開始日と同じ)')
    parser.add_argument('--data-types', default='seiseki',
                       help='取得するデータタイプ (カンマ区切り) [shutsuba,seiseki,cyokyo] (デフォルト: seiseki)')
    parser.add_argument('--delay', type=int, default=3,
                       help='リクエスト間の待機時間(秒) (デフォルト: 3)')
    parser.add_argument('--wait-time', type=int, default=5,
                       help='レースID取得とデータ取得の間の待機時間(秒) (デフォルト: 5)')
    
    args = parser.parse_args()
    
    try:
        # 日付をパース
        start_date = parse_date(args.start_date)
        end_date = parse_date(args.end_date) if args.end_date else start_date
        
        # データタイプをパース
        data_types = [dt.strip() for dt in args.data_types.split(',')]
        
        # 有効なデータタイプかチェック
        valid_types = ['shutsuba', 'seiseki', 'cyokyo']
        for dt in data_types:
            if dt not in valid_types:
                print(f"エラー: 無効なデータタイプ '{dt}'. 有効なタイプ: {', '.join(valid_types)}")
                return 1
        
        # バッチ処理実行
        success = batch_process(start_date, end_date, data_types, args.delay, args.wait_time)
        
        return 0 if success else 1
        
    except ValueError as e:
        print(f"エラー: {e}")
        return 1
    except Exception as e:
        print(f"予期しないエラー: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 