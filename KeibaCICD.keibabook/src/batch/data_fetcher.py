#!/usr/bin/env python3
"""
データ取得モジュール（JSON専用・同一フォルダ保存）

競馬ブックからレース日程とデータを取得する統合モジュール
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from ..scrapers.keibabook_scraper import KeibabookScraper
from ..parsers.seiseki_parser import SeisekiParser
from ..parsers.syutuba_parser import SyutubaParser
from ..parsers.cyokyo_parser import CyokyoParser
from ..parsers.danwa_parser import DanwaParser
from ..parsers.nittei_parser import NitteiParser
from .core.common import ensure_batch_directories, get_race_ids_file_path, get_json_file_path

class DataFetcher:
    """
    競馬ブックデータ取得クラス（JSON専用・同一フォルダ保存）
    """
    
    def __init__(self, delay: int = 3):
        """
        初期化
        
        Args:
            delay: リクエスト間隔（秒）
        """
        self.delay = delay
        self.scraper = KeibabookScraper()
        
        # パーサーを初期化
        self.seiseki_parser = SeisekiParser()
        self.shutsuba_parser = SyutubaParser()
        self.cyokyo_parser = CyokyoParser()
        self.danwa_parser = DanwaParser()
        self.nittei_parser = NitteiParser()
        
        # ディレクトリを作成
        ensure_batch_directories()
        
        # ログ設定
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)

    def fetch_race_schedule(self, date_str: str) -> bool:
        """
        指定日のレース日程を取得してJSONで保存
        開催がない日はJSONファイルを出力しない
        
        Args:
            date_str: 日付文字列 (YYYYMMDD)
            
        Returns:
            bool: 成功時True（開催がない日もTrueを返す）
        """
        try:
            self.logger.info(f"📅 レース日程取得開始: {date_str}")
            
            # レース日程を取得
            html_content = self.scraper.get_nittei_page(date_str)
            if not html_content:
                self.logger.error(f"❌ 日程ページの取得に失敗: {date_str}")
                return False
            
            # パース処理（日付を渡す）
            parsed_data = self.nittei_parser.parse_with_date(html_content, date_str)
            if not parsed_data:
                self.logger.error(f"❌ 日程データのパースに失敗: {date_str}")
                return False
            
            # 開催がない日の判定
            total_races = parsed_data.get('total_races', 0)
            kaisai_count = parsed_data.get('kaisai_count', 0)
            
            if total_races == 0 or kaisai_count == 0:
                self.logger.info(f"📭 開催なし: {date_str} - レース数: {total_races}, 開催数: {kaisai_count}")
                self.logger.info(f"⏭️ JSONファイルは出力しません")
                return True  # 開催がない日も正常処理として扱う
            
            # JSONファイルとして保存
            json_file_path = get_json_file_path('nittei', date_str)
            with open(json_file_path, 'w', encoding='utf-8') as f:
                json.dump(parsed_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"✅ 日程JSON保存完了: {json_file_path}")
            self.logger.info(f"🏇 開催情報: {kaisai_count}開催, {total_races}レース")
            
            # レースID情報も保存
            race_ids_file = get_race_ids_file_path(date_str)
            with open(race_ids_file, 'w', encoding='utf-8') as f:
                json.dump(parsed_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"✅ レースID情報保存完了: {race_ids_file}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"❌ レース日程取得でエラー: {e}")
            return False

    def save_race_data(self, race_id: str, data_types: List[str]) -> Dict[str, bool]:
        """
        指定レースのデータを取得してJSONで保存
        
        Args:
            race_id: レースID
            data_types: 取得するデータタイプのリスト
            
        Returns:
            Dict[str, bool]: データタイプごとの成功/失敗
        """
        results = {}
        
        for data_type in data_types:
            try:
                self.logger.info(f"📊 {data_type}データ取得開始: {race_id}")
                
                # データ取得
                html_content = None
                if data_type == 'seiseki':
                    html_content = self.scraper.get_seiseki_page(race_id)
                elif data_type == 'shutsuba':
                    html_content = self.scraper.get_shutsuba_page(race_id)
                elif data_type == 'cyokyo':
                    html_content = self.scraper.get_cyokyo_page(race_id)
                elif data_type == 'danwa':
                    html_content = self.scraper.get_danwa_page(race_id)
                
                if not html_content:
                    self.logger.error(f"❌ {data_type}ページの取得に失敗: {race_id}")
                    results[data_type] = False
                    continue
                
                # パース処理
                parsed_data = None
                if data_type == 'seiseki':
                    # SeisekiParserは一時ファイルを使用する設計のため、一時的にHTMLを保存
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as tmp_file:
                        tmp_file.write(html_content)
                        tmp_file_path = tmp_file.name
                    try:
                        parsed_data = self.seiseki_parser.parse(tmp_file_path)
                    finally:
                        import os
                        os.unlink(tmp_file_path)
                elif data_type == 'shutsuba':
                    # SyutubaParserも一時ファイルを使用する設計のため、一時的にHTMLを保存
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as tmp_file:
                        tmp_file.write(html_content)
                        tmp_file_path = tmp_file.name
                    try:
                        parsed_data = self.shutsuba_parser.parse(tmp_file_path)
                    finally:
                        import os
                        os.unlink(tmp_file_path)
                elif data_type == 'cyokyo':
                    # CyokyoParserも一時ファイルを使用する設計のため、一時的にHTMLを保存
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as tmp_file:
                        tmp_file.write(html_content)
                        tmp_file_path = tmp_file.name
                    try:
                        parsed_data = self.cyokyo_parser.parse(tmp_file_path)
                    finally:
                        import os
                        os.unlink(tmp_file_path)
                elif data_type == 'danwa':
                    # DanwaParserも一時ファイルを使用する設計のため、一時的にHTMLを保存
                    import tempfile
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as tmp_file:
                        tmp_file.write(html_content)
                        tmp_file_path = tmp_file.name
                    try:
                        parsed_data = self.danwa_parser.parse(tmp_file_path)
                    finally:
                        import os
                        os.unlink(tmp_file_path)
                
                if not parsed_data:
                    self.logger.error(f"❌ {data_type}データのパースに失敗: {race_id}")
                    results[data_type] = False
                    continue
                
                # JSONファイルとして保存
                json_file_path = get_json_file_path(data_type, race_id)
                with open(json_file_path, 'w', encoding='utf-8') as f:
                    json.dump(parsed_data, f, ensure_ascii=False, indent=2)
                
                self.logger.info(f"✅ {data_type} JSON保存完了: {json_file_path}")
                results[data_type] = True
                
                # リクエスト間隔
                if self.delay > 0:
                    time.sleep(self.delay)
                    
            except Exception as e:
                self.logger.error(f"❌ {data_type}データ取得でエラー: {e}")
                results[data_type] = False
        
        return results

    def get_race_ids_from_file(self, date_str: str) -> List[str]:
        """
        保存されたレースID情報から、レースIDリストを取得
        
        Args:
            date_str: 日付文字列 (YYYYMMDD)
            
        Returns:
            List[str]: レースIDのリスト
        """
        try:
            race_ids_file = get_race_ids_file_path(date_str)
            
            if not os.path.exists(race_ids_file):
                self.logger.warning(f"⚠️ レースID情報ファイルが見つかりません: {race_ids_file}")
                return []
            
            with open(race_ids_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            race_ids = []
            kaisai_data = data.get('kaisai_data', {})
            
            for venue, races in kaisai_data.items():
                for race in races:
                    race_id = race.get('race_id')
                    if race_id:
                        race_ids.append(race_id)
            
            self.logger.info(f"📋 レースID取得完了: {len(race_ids)}件")
            return race_ids
            
        except Exception as e:
            self.logger.error(f"❌ レースID取得でエラー: {e}")
            return []

    def fetch_all_race_data(self, date_str: str, data_types: List[str]) -> Dict[str, Any]:
        """
        指定日の全レースデータを取得
        
        Args:
            date_str: 日付文字列 (YYYYMMDD)
            data_types: 取得するデータタイプのリスト
            
        Returns:
            Dict[str, Any]: 処理結果のサマリー
        """
        self.logger.info(f"🚀 全レースデータ取得開始: {date_str}")
        self.logger.info(f"📊 対象データタイプ: {', '.join(data_types)}")
        
        # レースIDを取得
        race_ids = self.get_race_ids_from_file(date_str)
        if not race_ids:
            self.logger.error(f"❌ レースIDが取得できませんでした: {date_str}")
            return {'success': False, 'error': 'No race IDs found'}
        
        # 各レースのデータを取得
        total_success = 0
        total_failed = 0
        results_by_type = {data_type: {'success': 0, 'failed': 0} for data_type in data_types}
        
        for i, race_id in enumerate(race_ids, 1):
            self.logger.info(f"🏇 レース {i}/{len(race_ids)}: {race_id}")
            
            race_results = self.save_race_data(race_id, data_types)
            
            for data_type, success in race_results.items():
                if success:
                    results_by_type[data_type]['success'] += 1
                    total_success += 1
                else:
                    results_by_type[data_type]['failed'] += 1
                    total_failed += 1
        
        # 結果サマリー
        summary = {
            'success': True,
            'date': date_str,
            'total_races': len(race_ids),
            'total_success': total_success,
            'total_failed': total_failed,
            'results_by_type': results_by_type
        }
        
        self.logger.info(f"✅ 全レースデータ取得完了")
        self.logger.info(f"📊 成功: {total_success}件, 失敗: {total_failed}件")
        
        return summary 