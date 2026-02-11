#!/usr/bin/env python3
"""
レース日程パーサー

競馬ブックのレース日程ページからレース情報を抽出
"""

import re
import logging
from typing import Dict, List, Optional, Any
from bs4 import BeautifulSoup
from .base_parser import BaseParser

class NitteiParser(BaseParser):
    """レース日程データパーサー"""
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
    
    def parse_html_content(self, html_content: str) -> Optional[Dict[str, Any]]:
        """
        レース日程HTMLをパースしてJSONデータを生成
        
        Args:
            html_content: レース日程ページのHTML
            
        Returns:
            Dict[str, Any]: パース結果のJSONデータ
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 日付を抽出
            date_str = self._extract_date(soup)
            if not date_str:
                self.logger.error("日付の抽出に失敗しました")
                return None
            
            return self._parse_with_date_internal(soup, date_str)
            
        except Exception as e:
            self.logger.error(f"レース日程パースでエラー: {e}")
            return None
    
    def parse_with_date(self, html_content: str, date_str: str) -> Optional[Dict[str, Any]]:
        """
        レース日程HTMLをパースしてJSONデータを生成（日付指定版）
        
        Args:
            html_content: レース日程ページのHTML
            date_str: 日付文字列 (YYYYMMDD)
            
        Returns:
            Dict[str, Any]: パース結果のJSONデータ
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            return self._parse_with_date_internal(soup, date_str)
            
        except Exception as e:
            self.logger.error(f"レース日程パースでエラー: {e}")
            return None
    
    def _parse_with_date_internal(self, soup: BeautifulSoup, date_str: str) -> Optional[Dict[str, Any]]:
        """内部的なパース処理"""
        try:
            # 開催データを抽出（日付も渡す）
            kaisai_data = self._extract_kaisai_data(soup, date_str)
            if not kaisai_data:
                self.logger.warning("開催データが見つかりませんでした")
                return {
                    "date": date_str,
                    "kaisai_data": {},
                    "total_races": 0,
                    "kaisai_count": 0
                }
            
            # 統計情報を計算
            total_races = sum(len(races) for races in kaisai_data.values())
            kaisai_count = len(kaisai_data)
            
            result = {
                "date": date_str,
                "kaisai_data": kaisai_data,
                "total_races": total_races,
                "kaisai_count": kaisai_count
            }
            
            self.logger.info(f"レース日程パース完了: {kaisai_count}開催, {total_races}レース")
            return result
            
        except Exception as e:
            self.logger.error(f"レース日程パースでエラー: {e}")
            return None
    
    def _extract_date(self, soup: BeautifulSoup) -> Optional[str]:
        """HTMLから日付を抽出"""
        try:
            # URLから日付を抽出する方法もあるが、ページ内容から抽出を試行
            # タイトルやヘッダーから日付情報を探す
            title = soup.find('title')
            if title:
                title_text = title.get_text()
                # YYYYMMDD形式の日付を探す
                date_match = re.search(r'(\d{8})', title_text)
                if date_match:
                    return date_match.group(1)
            
            # その他の方法で日付を探す
            # 日付が見つからない場合は、現在の処理では外部から渡される想定
            return None
            
        except Exception as e:
            self.logger.error(f"日付抽出でエラー: {e}")
            return None
    
    def _extract_kaisai_data(self, soup: BeautifulSoup, date_str: str = None) -> Dict[str, List[Dict[str, str]]]:
        """開催データを抽出"""
        kaisai_data = {}
        
        try:
            # 修正: kaisaiクラスのdiv内にある全てのkaisaiテーブルを取得
            kaisai_div = soup.find('div', class_='kaisai')
            if not kaisai_div:
                self.logger.warning("kaisaiクラスのdivが見つかりませんでした")
                return kaisai_data
            
            # kaisai div内の全てのkaisaiテーブルを取得
            kaisai_tables = kaisai_div.find_all('table', class_='kaisai')
            self.logger.info(f"kaisaiテーブル数: {len(kaisai_tables)}")
            
            for table_idx, table in enumerate(kaisai_tables):
                rows = table.find_all('tr')
                kaisai_name = None
                races = []
                
                for row in rows:
                    # 開催場所名を取得（th class="midasi"）
                    th = row.find('th', class_='midasi')
                    if th:
                        kaisai_name = th.get_text(strip=True)
                        self.logger.info(f"開催場所発見: {kaisai_name}")
                        continue
                    
                    # レース情報を取得
                    tds = row.find_all('td')
                    if len(tds) < 2:
                        continue
                    
                    # td[0]から「数字+R」形式のレース番号を抽出
                    # HTML構造変更で「1RMy馬」のように「My馬」が含まれるようになった
                    td0_text = tds[0].get_text(strip=True)
                    race_no_match = re.match(r'^(\d+R)', td0_text)
                    if not race_no_match:
                        continue
                    race_no = race_no_match.group(1)
                    
                    # レース名・コース・IDを取得
                    a = tds[1].find('a', href=True)
                    if not a:
                        continue
                    
                    href = a['href']
                    # レースIDを抽出
                    race_id = self._extract_race_id(href)
                    if not race_id:
                        continue
                    
                    # レース名とコース情報を取得
                    ps = tds[1].find_all('p')
                    race_name = ps[0].get_text(strip=True) if len(ps) > 0 else ''
                    course = ps[1].get_text(strip=True) if len(ps) > 1 else ''
                    
                    # 発走時刻を取得（3番目のtdから）
                    start_time = None
                    start_at = None
                    if len(tds) >= 3:
                        time_text = tds[2].get_text(strip=True)
                        start_time = self._extract_start_time(time_text)
                        if start_time:
                            # ISO8601形式も生成
                            start_at = self._create_iso8601_time(date_str, start_time)
                    
                    race_info = {
                        'race_no': race_no,
                        'race_name': race_name,
                        'course': course,
                        'race_id': race_id
                    }
                    
                    # 発走時刻が取得できた場合のみ追加
                    if start_time:
                        race_info['start_time'] = start_time
                    if start_at:
                        race_info['start_at'] = start_at
                    
                    races.append(race_info)
                
                if kaisai_name and races:
                    kaisai_data[kaisai_name] = races
                    self.logger.info(f"開催場所 {kaisai_name}: {len(races)}レース")
                elif kaisai_name:
                    self.logger.warning(f"開催場所 {kaisai_name}: レースが見つかりませんでした")
                else:
                    self.logger.warning(f"テーブル{table_idx+1}: 開催場所名が見つかりませんでした")
        
        except Exception as e:
            self.logger.error(f"開催データ抽出でエラー: {e}")
        
        return kaisai_data
    
    def _extract_race_id(self, href: str) -> Optional[str]:
        """hrefからレースIDを抽出"""
        try:
            # shutsuba, seiseki, cyokyo, danwa等のURLからレースIDを抽出
            patterns = [
                r'/shutsuba/(\d{12})',
                r'/seiseki/(\d{12})',
                r'/cyokyo/\d+/\d+/(\d{12})',
                r'/danwa/\d+/(\d{12})',
                r'/(\d{12})'  # 一般的なパターン
            ]
            
            for pattern in patterns:
                match = re.search(pattern, href)
                if match:
                    return match.group(1)
            
            return None
            
        except Exception as e:
            self.logger.error(f"レースID抽出でエラー: {e}")
            return None
    
    def _extract_start_time(self, text: str) -> Optional[str]:
        """テキストから発走時刻を抽出（HH:MM形式）"""
        try:
            # 時刻パターンを検索（例: 10:05, 15:30）
            # 「調教」などの文字が前にあってもマッチするように修正
            time_pattern = r'([01]?\d|2[0-3]):([0-5]\d)'
            match = re.search(time_pattern, text)
            if match:
                hour = match.group(1).zfill(2)  # 1桁の場合は0埋め
                minute = match.group(2)
                return f"{hour}:{minute}"
            return None
        except Exception as e:
            self.logger.debug(f"発走時刻抽出でエラー: {e}")
            return None
    
    def _create_iso8601_time(self, date_str: str, time_str: str) -> Optional[str]:
        """日付と時刻からISO8601形式の日時文字列を生成"""
        try:
            from datetime import datetime
            # YYYYMMDD形式をYYYY-MM-DD形式に変換
            year = date_str[:4]
            month = date_str[4:6]
            day = date_str[6:8]
            
            # HH:MM形式の時刻を分解
            hour, minute = time_str.split(':')
            
            # ISO8601形式の文字列を生成（JST）
            iso_time = f"{year}-{month}-{day}T{hour}:{minute}:00+09:00"
            return iso_time
        except Exception as e:
            self.logger.debug(f"ISO8601時刻生成でエラー: {e}")
            return None
    
    def parse(self, html_file_path: str) -> Dict[str, Any]:
        """
        HTMLファイルをパースしてデータを抽出する（BaseParserの抽象メソッド実装）
        
        Args:
            html_file_path: HTMLファイルのパス
            
        Returns:
            Dict[str, Any]: 抽出されたデータ
        """
        try:
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # ファイル名から日付を抽出
            import os
            import re
            filename = os.path.basename(html_file_path)
            date_match = re.search(r'(\d{8})', filename)
            if date_match:
                date_str = date_match.group(1)
                result = self.parse_with_date(html_content, date_str)
                return result if result is not None else {}
            else:
                # 日付が見つからない場合は現在日付を使用
                from datetime import datetime
                date_str = datetime.now().strftime('%Y%m%d')
                result = self.parse_with_date(html_content, date_str)
                return result if result is not None else {}
                
        except Exception as e:
            self.logger.error(f"HTMLファイルパースでエラー: {e}")
            return {}
    
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        抽出されたデータを検証する（BaseParserの抽象メソッド実装）
        
        Args:
            data: 検証対象のデータ
            
        Returns:
            bool: データが有効な場合True
        """
        try:
            if not isinstance(data, dict):
                self.logger.error("データがdict型ではありません")
                return False
            
            # 必須フィールドの確認
            required_fields = ['date', 'kaisai_data', 'total_races', 'kaisai_count']
            for field in required_fields:
                if field not in data:
                    self.logger.error(f"必須フィールドが不足: {field}")
                    return False
            
            # 日付フィールドの確認
            date_str = data.get('date')
            if not isinstance(date_str, str) or len(date_str) != 8:
                self.logger.error("日付フィールドが無効です")
                return False
            
            # 開催データの確認
            kaisai_data = data.get('kaisai_data')
            if not isinstance(kaisai_data, dict):
                self.logger.error("kaisai_dataがdict型ではありません")
                return False
            
            # 統計情報の確認
            total_races = data.get('total_races', 0)
            kaisai_count = data.get('kaisai_count', 0)
            
            if not isinstance(total_races, int) or total_races < 0:
                self.logger.error("total_racesが無効です")
                return False
            
            if not isinstance(kaisai_count, int) or kaisai_count < 0:
                self.logger.error("kaisai_countが無効です")
                return False
            
            # 開催データの詳細確認
            actual_total_races = 0
            for venue, races in kaisai_data.items():
                if not isinstance(races, list):
                    self.logger.error(f"開催場所 {venue} のレースデータがlist型ではありません")
                    return False
                
                actual_total_races += len(races)
                
                # 各レースの確認
                for race in races:
                    if not isinstance(race, dict):
                        self.logger.error("レースデータがdict型ではありません")
                        return False
                    
                    race_required_fields = ['race_no', 'race_name', 'course', 'race_id']
                    for field in race_required_fields:
                        if field not in race:
                            self.logger.error(f"レースデータに必須フィールドが不足: {field}")
                            return False
            
            # 統計情報の整合性確認
            if actual_total_races != total_races:
                self.logger.warning(f"total_racesの不整合: 実際={actual_total_races}, 記録={total_races}")
            
            if len(kaisai_data) != kaisai_count:
                self.logger.warning(f"kaisai_countの不整合: 実際={len(kaisai_data)}, 記録={kaisai_count}")
            
            self.logger.info(f"データ検証OK: {kaisai_count}開催, {total_races}レース")
            return True
            
        except Exception as e:
            self.logger.error(f"データ検証でエラー: {e}")
            return False 