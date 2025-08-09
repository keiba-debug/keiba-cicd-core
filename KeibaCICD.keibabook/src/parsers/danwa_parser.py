#!/usr/bin/env python3
"""
厩舎の話データパーサー

競馬ブックの厩舎の話ページからHTMLを解析してJSONデータを生成
"""

import re
import json
from typing import Dict, List, Any
from pathlib import Path
from bs4 import BeautifulSoup

from ..utils.logger import setup_logger


class DanwaParser:
    """厩舎の話データパーサー"""
    
    def __init__(self, debug: bool = False):
        """
        初期化
        
        Args:
            debug: デバッグモード
        """
        self.debug = debug
        self.logger = setup_logger("DanwaParser", level="DEBUG" if debug else "INFO")
    
    def parse(self, html_file_path: str) -> Dict[str, Any]:
        """
        HTMLファイルから厩舎の話データを抽出
        
        Args:
            html_file_path: HTMLファイルのパス
            
        Returns:
            Dict[str, Any]: 抽出されたデータ
        """
        try:
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # レース情報を抽出
            race_info = self._extract_race_info(soup)
            
            # 厩舎の話を抽出
            danwa_data = self._extract_danwa_data(soup)
            
            return {
                "race_info": race_info,
                "danwa_data": danwa_data
            }
            
        except Exception as e:
            self.logger.error(f"HTMLパースエラー: {e}")
            raise
    
    def _extract_race_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """レース基本情報を抽出"""
        race_info = {}
        
        try:
            # レース名
            race_name_elem = soup.find(['h1', 'h2', 'h3'], string=re.compile(r'第?\d+回|レース|厩舎|話'))
            if race_name_elem:
                race_info['race_name'] = race_name_elem.get_text().strip()
            
            # 日付情報
            date_info = soup.find('div', class_=re.compile(r'date|time'))
            if date_info:
                race_info['date_info'] = date_info.get_text().strip()
                
        except Exception as e:
            self.logger.debug(f"レース情報抽出エラー: {e}")
        
        return race_info
    
    def _extract_danwa_data(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """厩舎の話を抽出"""
        danwa_list = []
        
        try:
            # 厩舎の話テーブルを探す
            table = soup.find('table', {'id': re.compile(r'danwa|stable|comment')})
            if not table:
                table = soup.find('table', class_=re.compile(r'danwa|stable|comment'))
            if not table:
                # 一般的なテーブルから探す
                tables = soup.find_all('table')
                for t in tables:
                    if self._is_danwa_table(t):
                        table = t
                        break
            
            if not table:
                self.logger.warning("厩舎の話テーブルが見つかりません")
                return danwa_list
            
            # テーブルのヘッダーを解析
            headers = self._extract_headers(table)
            self.logger.debug(f"検出されたヘッダー: {headers}")
            
            # データ行を抽出
            rows = table.find_all('tr')
            for row in rows[1:]:  # ヘッダー行をスキップ
                danwa_data = self._extract_danwa_from_row(row, headers)
                if danwa_data and (danwa_data.get('馬番') or danwa_data.get('馬名')):
                    danwa_list.append(danwa_data)
                    
        except Exception as e:
            self.logger.error(f"厩舎の話抽出エラー: {e}")
        
        return danwa_list
    
    def _is_danwa_table(self, table) -> bool:
        """テーブルが厩舎の話テーブルかどうかを判定"""
        text = table.get_text()
        keywords = ['馬番', '馬名', '厩舎', '談話', 'コメント', '調教師', '話']
        return sum(keyword in text for keyword in keywords) >= 3
    
    def _extract_headers(self, table) -> List[str]:
        """テーブルヘッダーを抽出"""
        headers = []
        
        try:
            header_row = table.find('tr')
            if header_row:
                for th in header_row.find_all(['th', 'td']):
                    header_text = th.get_text().strip()
                    headers.append(header_text)
        except Exception as e:
            self.logger.debug(f"ヘッダー抽出エラー: {e}")
            
        return headers
    
    def _extract_danwa_from_row(self, row, headers: List[str]) -> Dict[str, str]:
        """行から厩舎の話を抽出"""
        danwa_data = {}
        
        try:
            cells = row.find_all(['td', 'th'])
            
            for i, cell in enumerate(cells):
                cell_text = cell.get_text().strip()
                
                # ヘッダーがある場合はそれを使用
                if i < len(headers):
                    header = headers[i]
                    danwa_data[header] = cell_text
                else:
                    # デフォルトのフィールド名
                    default_fields = ['馬番', '馬名', '厩舎', '調教師', 'コメント', '談話', '展望']
                    if i < len(default_fields):
                        danwa_data[default_fields[i]] = cell_text
                    else:
                        danwa_data[f'field_{i}'] = cell_text
                        
        except Exception as e:
            self.logger.debug(f"厩舎の話データ抽出エラー: {e}")
            
        return danwa_data
    
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """データの妥当性を検証"""
        try:
            if not isinstance(data, dict):
                self.logger.error("データがdict型ではありません")
                return False
            
            if 'danwa_data' not in data:
                self.logger.error("danwa_dataフィールドがありません")
                return False
            
            danwa_data = data['danwa_data']
            if not isinstance(danwa_data, list):
                self.logger.error("danwa_dataがlist型ではありません")
                return False
            
            if len(danwa_data) == 0:
                self.logger.warning("厩舎の話データがありません")
                return False
            
            # 各厩舎の話データをチェック
            for i, danwa in enumerate(danwa_data):
                if not isinstance(danwa, dict):
                    self.logger.error(f"厩舎の話データ{i}がdict型ではありません")
                    return False
            
            self.logger.info(f"データ検証OK: {len(danwa_data)}件の厩舎の話データ")
            return True
            
        except Exception as e:
            self.logger.error(f"データ検証エラー: {e}")
            return False
    
    def save_json(self, data: Dict[str, Any], output_path: str):
        """データをJSONファイルに保存"""
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"JSONファイルを保存しました: {output_path}")
            
        except Exception as e:
            self.logger.error(f"JSON保存エラー: {e}")
            raise 