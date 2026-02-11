#!/usr/bin/env python3
"""
パドック情報定期更新スクリプト

指定された日付のレースのパドック情報を定期的に更新します。
レース開始前はパドック情報が未公開の場合が多いため、
定期的に再取得して最新の情報を反映します。
"""

import os
import sys
import json
import time
import argparse
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any

from scrapers.requests_scraper import RequestsScraper
from parsers.paddok_parser import PaddokParser
from integrator.race_data_integrator import RaceDataIntegrator
from integrator.markdown_generator import MarkdownGenerator
from utils.logger import setup_logger
from utils.date_parser import parse_date


class PaddockUpdater:
    """パドック情報更新クラス"""
    
    def __init__(self, data_root: str = None, debug: bool = False):
        """
        初期化
        
        Args:
            data_root: データルートディレクトリ
            debug: デバッグモード
        """
        self.data_root = data_root or os.getenv('KEIBA_DATA_ROOT_DIR', './data')
        self.logger = setup_logger('PaddockUpdater', level='DEBUG' if debug else 'INFO')
        self.scraper = RequestsScraper()
        self.parser = PaddokParser(debug=debug)
        self.integrator = RaceDataIntegrator()
        self.generator = MarkdownGenerator(use_organized_dir=True)
        
    def get_race_ids_for_date(self, date_str: str) -> List[str]:
        """
        指定日付のレースIDリストを取得
        
        Args:
            date_str: 日付文字列 (YYYYMMDD)
            
        Returns:
            レースIDのリスト
        """
        race_ids = []
        race_ids_file = os.path.join(self.data_root, 'race_ids', f'{date_str}_info.json')
        
        if not os.path.exists(race_ids_file):
            self.logger.warning(f"レースIDファイルが見つかりません: {race_ids_file}")
            return race_ids
        
        try:
            with open(race_ids_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for kaisai_name, races in data.get('kaisai_data', {}).items():
                for race in races:
                    if 'race_id' in race:
                        race_ids.append(race['race_id'])
                        
        except Exception as e:
            self.logger.error(f"レースID読み込みエラー: {e}")
        
        return race_ids
    
    def update_paddock_for_race(self, race_id: str) -> Dict[str, Any]:
        """
        特定レースのパドック情報を更新
        
        Args:
            race_id: レースID
            
        Returns:
            更新結果
        """
        try:
            # パドック情報を取得
            url = f'https://p.keibabook.co.jp/cyuou/paddok/{race_id}'
            html = self.scraper.scrape(url)
            
            # HTMLを一時ファイルに保存
            temp_html = f'temp_paddok_{race_id}.html'
            with open(temp_html, 'w', encoding='utf-8') as f:
                f.write(html)
            
            # パース
            paddock_data = self.parser.parse(temp_html)
            
            # 一時ファイルを削除
            os.remove(temp_html)
            
            # JSONファイルを保存
            output_path = os.path.join(self.data_root, 'temp', f'paddok_{race_id}.json')
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(paddock_data, f, ensure_ascii=False, indent=2)
            
            # 評価データがあるか確認
            has_evaluations = False
            if paddock_data.get('paddock_evaluations'):
                for eval in paddock_data['paddock_evaluations']:
                    if eval.get('evaluation') or eval.get('comment'):
                        has_evaluations = True
                        break
            
            return {
                'race_id': race_id,
                'success': True,
                'has_evaluations': has_evaluations,
                'evaluation_count': paddock_data.get('evaluation_count', 0)
            }
            
        except Exception as e:
            self.logger.error(f"パドック更新エラー ({race_id}): {e}")
            return {
                'race_id': race_id,
                'success': False,
                'error': str(e)
            }
    
    def update_integrated_and_markdown(self, race_id: str) -> bool:
        """
        統合ファイルとMarkdownを更新
        
        Args:
            race_id: レースID
            
        Returns:
            成功/失敗
        """
        try:
            # 統合ファイルを作成/更新
            integrated_data = self.integrator.create_integrated_file(race_id, save=True)
            
            if integrated_data:
                # Markdownを生成
                self.generator.generate_race_markdown(integrated_data, save=True)
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"統合/Markdown更新エラー ({race_id}): {e}")
            return False
    
    def update_all_paddocks(self, date_str: str, interval: int = 0) -> Dict[str, Any]:
        """
        指定日付の全レースのパドック情報を更新
        
        Args:
            date_str: 日付文字列 (YYYYMMDD)
            interval: 更新間隔（秒）
            
        Returns:
            更新結果サマリー
        """
        race_ids = self.get_race_ids_for_date(date_str)
        
        if not race_ids:
            self.logger.warning(f"更新対象レースがありません: {date_str}")
            return {'total': 0, 'success': 0, 'with_evaluations': 0}
        
        self.logger.info(f"{date_str}の{len(race_ids)}レースを更新します")
        
        results = {
            'total': len(race_ids),
            'success': 0,
            'failed': 0,
            'with_evaluations': 0,
            'updated_races': []
        }
        
        for i, race_id in enumerate(race_ids, 1):
            self.logger.info(f"[{i}/{len(race_ids)}] {race_id}を更新中...")
            
            # パドック情報を更新
            result = self.update_paddock_for_race(race_id)
            
            if result['success']:
                results['success'] += 1
                
                if result.get('has_evaluations'):
                    results['with_evaluations'] += 1
                    results['updated_races'].append(race_id)
                    
                    # 統合ファイルとMarkdownも更新
                    if self.update_integrated_and_markdown(race_id):
                        self.logger.info(f"  → 評価データあり、統合ファイル・Markdown更新完了")
                    else:
                        self.logger.warning(f"  → 評価データあり、統合ファイル・Markdown更新失敗")
                else:
                    self.logger.info(f"  → 評価データなし")
            else:
                results['failed'] += 1
                self.logger.error(f"  → 更新失敗: {result.get('error', 'Unknown error')}")
            
            # インターバル待機
            if interval > 0 and i < len(race_ids):
                time.sleep(interval)
        
        return results
    
    def continuous_update(self, date_str: str, update_interval: int = 300, 
                         max_iterations: int = None):
        """
        継続的にパドック情報を更新
        
        Args:
            date_str: 日付文字列 (YYYYMMDD)
            update_interval: 更新間隔（秒）
            max_iterations: 最大更新回数（Noneで無限）
        """
        iteration = 0
        
        while max_iterations is None or iteration < max_iterations:
            iteration += 1
            
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.logger.info(f"\n=== 更新サイクル {iteration} 開始 ({current_time}) ===")
            
            # パドック情報を更新
            results = self.update_all_paddocks(date_str, interval=1)
            
            # 結果サマリー
            self.logger.info(f"更新完了: 成功={results['success']}/{results['total']}, "
                           f"評価データあり={results['with_evaluations']}")
            
            if results['updated_races']:
                self.logger.info(f"評価データがあったレース: {', '.join(results['updated_races'])}")
            
            # 次の更新まで待機
            if max_iterations is None or iteration < max_iterations:
                self.logger.info(f"次の更新まで{update_interval}秒待機...")
                time.sleep(update_interval)
        
        self.logger.info("継続更新を終了します")


def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(
        description='パドック情報定期更新スクリプト',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 本日のパドック情報を1回更新
  python -m src.paddock_updater --date today
  
  # 特定日付のパドック情報を更新
  python -m src.paddock_updater --date 2025/08/10
  
  # 5分間隔で継続的に更新（最大20回）
  python -m src.paddock_updater --date today --continuous --interval 300 --max-iterations 20
  
  # 10分間隔で無限に更新
  python -m src.paddock_updater --date today --continuous --interval 600
        """
    )
    
    parser.add_argument('--date', required=True, 
                       help='更新対象日付 (YYYY/MM/DD or today)')
    parser.add_argument('--continuous', action='store_true',
                       help='継続的に更新する')
    parser.add_argument('--interval', type=int, default=300,
                       help='更新間隔（秒）デフォルト: 300秒')
    parser.add_argument('--max-iterations', type=int,
                       help='最大更新回数（指定なしで無限）')
    parser.add_argument('--debug', action='store_true',
                       help='デバッグモード')
    
    args = parser.parse_args()
    
    # 日付をパース
    if args.date.lower() == 'today':
        date_obj = datetime.now()
    else:
        date_obj = parse_date(args.date)
    
    date_str = date_obj.strftime('%Y%m%d')
    
    # 更新実行
    updater = PaddockUpdater(debug=args.debug)
    
    if args.continuous:
        # 継続更新モード
        updater.continuous_update(
            date_str, 
            update_interval=args.interval,
            max_iterations=args.max_iterations
        )
    else:
        # 1回更新モード
        results = updater.update_all_paddocks(date_str, interval=1)
        
        print(f"\n更新結果:")
        print(f"  総レース数: {results['total']}")
        print(f"  成功: {results['success']}")
        print(f"  失敗: {results['failed']}")
        print(f"  評価データあり: {results['with_evaluations']}")
        
        if results['updated_races']:
            print(f"  評価データがあったレース:")
            for race_id in results['updated_races']:
                print(f"    - {race_id}")


if __name__ == '__main__':
    main()