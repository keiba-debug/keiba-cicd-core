"""
成績パーサー

競馬ブックの成績ページから情報を抽出します。
"""

import re
from typing import Any, Dict, List

from bs4 import BeautifulSoup

from .base_parser import BaseParser
from ..utils.config import Config


class SeisekiParser(BaseParser):
    """
    成績ページのパーサー
    
    競馬ブックの成績ページから以下の情報を抽出します：
    - レース情報
    - 出走馬の成績
    - インタビュー
    - 次走へのメモ
    """
    
    def __init__(self, debug: bool = False):
        """
        初期化
        
        Args:
            debug: デバッグモードの有効化
        """
        super().__init__(debug)
    
    def parse(self, html_file_path: str) -> Dict[str, Any]:
        """
        HTMLファイルをパースして成績データを抽出する
        
        Args:
            html_file_path: HTMLファイルのパス
            
        Returns:
            Dict[str, Any]: 抽出された成績データ
        """
        self.logger.info("成績データの抽出を開始します")
        
        # HTMLを読み込み
        soup = self.load_html(html_file_path)
        
        # レース情報を抽出
        race_info = self._extract_race_info(soup)
        
        # 成績データを抽出
        results = self._extract_results(soup)
        
        # インタビューとメモを抽出
        interviews_and_memos = self._extract_interviews_and_memos(soup)
        
        # 結果をマージ
        results = self._merge_interview_memo_data(results, interviews_and_memos)
        
        data = {
            "race_info": race_info,
            "results": results
        }
        
        # データ検証
        if self.validate_data(data):
            self.logger.info(f"成績データの抽出が完了しました。出走頭数: {len(results)}頭")
        else:
            self.logger.warning("抽出されたデータに問題がある可能性があります")
        
        return data
    
    def _extract_race_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        レース情報を抽出する
        
        Args:
            soup: BeautifulSoupオブジェクト
            
        Returns:
            Dict[str, str]: レース情報
        """
        race_info = {}
        
        # レース名を抽出
        race_name_element = soup.find('h1')
        if race_name_element:
            race_info["race_name"] = self.extract_text_safely(race_name_element)
        
        self.debug_log("レース情報を抽出しました", race_info)
        return race_info
    
    def _extract_results(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """
        成績データを抽出する
        
        Args:
            soup: BeautifulSoupオブジェクト
            
        Returns:
            List[Dict[str, str]]: 成績データのリスト
        """
        results = []
        
        # テーブルを検索
        table = soup.find('table', {'class': 'raceTable'})
        if not table:
            self.logger.warning("成績テーブルが見つかりません")
            return results
        
        # ヘッダー行を取得
        header_row = table.find('tr')
        if not header_row:
            self.logger.warning("ヘッダー行が見つかりません")
            return results
        
        headers = [self.extract_text_safely(th) for th in header_row.find_all(['th', 'td'])]
        self.debug_log("テーブルヘッダー", headers)
        
        # データ行を処理
        for row in table.find_all('tr')[1:]:  # ヘッダー行をスキップ
            cells = row.find_all(['td', 'th'])
            if len(cells) >= len(headers):
                row_data = {}
                for i, cell in enumerate(cells[:len(headers)]):
                    if i < len(headers):
                        row_data[headers[i]] = self.extract_text_safely(cell)
                
                if row_data:
                    results.append(row_data)
        
        self.debug_log(f"成績データを抽出しました", f"{len(results)}頭")
        return results
    
    def _extract_interviews_and_memos(self, soup: BeautifulSoup) -> Dict[str, Dict[str, str]]:
        """
        インタビューとメモを抽出する
        
        Args:
            soup: BeautifulSoupオブジェクト
            
        Returns:
            Dict[str, Dict[str, str]]: 馬名をキーとしたインタビューとメモのデータ
        """
        interviews_and_memos = {}
        
        # bameiboxクラスの要素を検索
        bameibox_elements = soup.find_all('div', class_='bameibox')
        
        for element in bameibox_elements:
            # 馬名を抽出
            horse_name = self._extract_horse_name_from_element(element)
            if not horse_name:
                continue
            
            # テキストを抽出
            text = self.extract_text_safely(element)
            
            # インタビューかメモかを判定
            if self._is_interview_text(text):
                interview_content = self._clean_interview_text(text)
                if horse_name not in interviews_and_memos:
                    interviews_and_memos[horse_name] = {}
                interviews_and_memos[horse_name]["interview"] = interview_content
                self.debug_log(f"interview", f"raw='{text[:50]}...', horse='{horse_name}', body='{interview_content[:50]}...'")
            else:
                memo_content = self._clean_memo_text(text)
                if horse_name not in interviews_and_memos:
                    interviews_and_memos[horse_name] = {}
                interviews_and_memos[horse_name]["memo"] = memo_content
                self.debug_log(f"memo", f"raw='{text[:50]}...', horse='{horse_name}', body='{memo_content[:50]}...'")
        
        return interviews_and_memos
    
    def _extract_horse_name_from_element(self, element) -> str:
        """
        要素から馬名を抽出する
        
        Args:
            element: BeautifulSoupの要素
            
        Returns:
            str: 馬名
        """
        text = self.extract_text_safely(element)
        
        # パターン1: 馬名（着順）の形式
        pattern1 = r'^([^（]+)（[^）]*）'
        match = re.match(pattern1, text)
        if match:
            return match.group(1).strip()
        
        # パターン2: 馬名……の形式
        pattern2 = r'^([^…]+)…'
        match = re.match(pattern2, text)
        if match:
            return match.group(1).strip()
        
        return ""
    
    def _is_interview_text(self, text: str) -> bool:
        """
        テキストがインタビューかどうかを判定する
        
        Args:
            text: 判定対象のテキスト
            
        Returns:
            bool: インタビューの場合True
        """
        # 着順と騎手名が含まれている場合はインタビュー
        interview_pattern = r'[（(][０-９\d]+着[）)].*?騎手'
        return bool(re.search(interview_pattern, text))
    
    def _clean_interview_text(self, text: str) -> str:
        """
        インタビューテキストをクリーニングする
        
        Args:
            text: クリーニング対象のテキスト
            
        Returns:
            str: クリーニング後のテキスト
        """
        # 馬名と着順部分を除去
        pattern = r'^[^（]*（[^）]*）\s*'
        cleaned_text = re.sub(pattern, '', text)
        return self.clean_text(cleaned_text)
    
    def _clean_memo_text(self, text: str) -> str:
        """
        メモテキストをクリーニングする
        
        Args:
            text: クリーニング対象のテキスト
            
        Returns:
            str: クリーニング後のテキスト
        """
        # 馬名と「……」部分を除去
        pattern = r'^[^…]*…+'
        cleaned_text = re.sub(pattern, '', text)
        return self.clean_text(cleaned_text)
    
    def _merge_interview_memo_data(
        self, 
        results: List[Dict[str, str]], 
        interviews_and_memos: Dict[str, Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """
        成績データにインタビューとメモを統合する
        
        Args:
            results: 成績データのリスト
            interviews_and_memos: インタビューとメモのデータ
            
        Returns:
            List[Dict[str, str]]: 統合された成績データ
        """
        for result in results:
            horse_name = result.get("馬名", "")
            if horse_name in interviews_and_memos:
                result["interview"] = interviews_and_memos[horse_name].get("interview", "")
                result["memo"] = interviews_and_memos[horse_name].get("memo", "")
            else:
                result["interview"] = ""
                result["memo"] = ""
        
        return results
    
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        抽出されたデータを検証する
        
        Args:
            data: 検証対象のデータ
            
        Returns:
            bool: データが有効な場合True
        """
        # 基本構造の確認
        if not isinstance(data, dict):
            self.logger.error("データがdict型ではありません")
            return False
        
        if "race_info" not in data or "results" not in data:
            self.logger.error("必要なキー（race_info, results）が不足しています")
            return False
        
        # レース情報の確認
        race_info = data["race_info"]
        if not isinstance(race_info, dict) or not race_info.get("race_name"):
            self.logger.error("レース情報が不正です")
            return False
        
        # 成績データの確認
        results = data["results"]
        if not isinstance(results, list) or len(results) == 0:
            self.logger.error("成績データが空または不正です")
            return False
        
        # 各成績データの確認
        required_fields = ["着順", "馬名", "騎手"]
        for i, result in enumerate(results):
            if not isinstance(result, dict):
                self.logger.error(f"成績データ{i}がdict型ではありません")
                return False
            
            for field in required_fields:
                if field not in result or not result[field]:
                    self.logger.warning(f"成績データ{i}に必要なフィールド'{field}'がありません")
        
        return True