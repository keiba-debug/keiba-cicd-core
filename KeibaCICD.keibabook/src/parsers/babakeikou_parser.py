#!/usr/bin/env python3
"""
馬場情報データパーサー

競馬ブックの馬場情報ページからHTMLを解析してJSONデータを生成

URL形式: https://p.keibabook.co.jp/cyuou/babakeikou/{YYYYMMDD}{場コード}
例: https://p.keibabook.co.jp/cyuou/babakeikou/2025092701

馬場情報には以下の情報が含まれる:
- 含水率（芝・ダート）
- クッション値（芝）
- 馬場状態
- 馬場傾向・特記事項
"""

import re
from typing import Dict, List, Any, Optional
from pathlib import Path
from bs4 import BeautifulSoup

from ..utils.logger import setup_logger


class BabaKeikouParser:
    """馬場情報データパーサー（競馬ブック専用）"""
    
    # 場コードから競馬場名へのマッピング
    PLACE_CODE_MAP = {
        "01": "阪神",
        "02": "函館",
        "03": "福島",
        "04": "新潟",
        "05": "中山",
        "06": "中京",
        "07": "小倉",
        "08": "京都",
        "09": "東京",
        "10": "札幌",
    }
    
    def __init__(self, debug: bool = False):
        """
        初期化
        
        Args:
            debug: デバッグモード
        """
        self.debug = debug
        self.logger = setup_logger("BabaKeikouParser", level="DEBUG" if debug else "INFO")
    
    def parse(self, html_file_path: str) -> Dict[str, Any]:
        """
        HTMLファイルから馬場情報データを抽出
        
        Args:
            html_file_path: HTMLファイルのパス
            
        Returns:
            Dict[str, Any]: 抽出されたデータ
        """
        try:
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            return self.parse_html_content(html_content)
            
        except Exception as e:
            self.logger.error(f"HTMLファイルパースエラー: {e}")
            raise
    
    def parse_html_content(self, html_content: str) -> Dict[str, Any]:
        """
        HTMLコンテンツから馬場情報データを抽出
        
        Args:
            html_content: HTMLコンテンツ
            
        Returns:
            Dict[str, Any]: 抽出されたデータ
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 基本情報を抽出
            basic_info = self._extract_basic_info(soup)
            
            # 芝馬場情報を抽出
            turf_info = self._extract_turf_info(soup)
            
            # ダート馬場情報を抽出
            dirt_info = self._extract_dirt_info(soup)
            
            # 馬場傾向・コメントを抽出
            comments = self._extract_comments(soup)
            
            # 含水率データを抽出
            moisture_data = self._extract_moisture_data(soup)
            
            result = {
                "basic_info": basic_info,
                "turf": turf_info,
                "dirt": dirt_info,
                "moisture": moisture_data,
                "comments": comments,
                "parse_status": "success"
            }
            
            self.logger.info(f"馬場情報パース完了")
            return result
            
        except Exception as e:
            self.logger.error(f"HTMLパースエラー: {e}")
            return {
                "parse_status": "error",
                "error_message": str(e)
            }
    
    def _extract_basic_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """基本情報を抽出"""
        info = {
            "date": "",
            "place": "",
            "weather": "",
        }
        
        try:
            # 日付を抽出
            date_elem = soup.find(text=re.compile(r'\d{4}年\d{1,2}月\d{1,2}日'))
            if date_elem:
                info["date"] = date_elem.strip()
            
            # 競馬場名を抽出
            # h2やh1タグから競馬場名を探す
            for tag in ['h2', 'h1', 'div']:
                heading = soup.find(tag, text=re.compile(r'回.+日目'))
                if heading:
                    text = heading.get_text()
                    # 「4回阪神8日目」のようなパターンから競馬場名を抽出
                    match = re.search(r'\d+回(.+?)\d+日目', text)
                    if match:
                        info["place"] = match.group(1)
                    break
            
            # 天候を抽出
            weather_patterns = ['晴', '曇', '雨', '小雨', '小雪', '雪']
            text_content = soup.get_text()
            for pattern in weather_patterns:
                if pattern in text_content:
                    info["weather"] = pattern
                    break
            
        except Exception as e:
            self.logger.warning(f"基本情報抽出エラー: {e}")
        
        return info
    
    def _extract_turf_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """芝馬場情報を抽出"""
        turf = {
            "condition": "",  # 良/稍重/重/不良
            "cushion_value": "",  # クッション値
            "moisture_rate": "",  # 含水率
            "note": ""
        }
        
        try:
            # テーブルから芝情報を探す
            tables = soup.find_all('table')
            for table in tables:
                text = table.get_text()
                if '芝' in text and ('良' in text or '稍' in text or '重' in text):
                    # 馬場状態を抽出
                    condition_match = re.search(r'芝[：:・\s]*([良稍重不]+)', text)
                    if condition_match:
                        turf["condition"] = condition_match.group(1)
                    
                    # クッション値を抽出
                    cushion_match = re.search(r'クッション[値]*[：:・\s]*(\d+\.?\d*)', text)
                    if cushion_match:
                        turf["cushion_value"] = cushion_match.group(1)
                    
                    # 含水率を抽出
                    moisture_match = re.search(r'含水率[：:・\s]*(\d+\.?\d*)', text)
                    if moisture_match:
                        turf["moisture_rate"] = moisture_match.group(1)
            
            # divやpタグからも探す
            for elem in soup.find_all(['div', 'p', 'span', 'td']):
                text = elem.get_text()
                
                # 芝の馬場状態
                if '芝' in text and turf["condition"] == "":
                    match = re.search(r'芝[：:・\s]*([良稍重不]+)', text)
                    if match:
                        turf["condition"] = match.group(1)
                
                # クッション値
                if 'クッション' in text and turf["cushion_value"] == "":
                    match = re.search(r'クッション[値]*[：:・\s]*(\d+\.?\d*)', text)
                    if match:
                        turf["cushion_value"] = match.group(1)
        
        except Exception as e:
            self.logger.warning(f"芝馬場情報抽出エラー: {e}")
        
        return turf
    
    def _extract_dirt_info(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """ダート馬場情報を抽出"""
        dirt = {
            "condition": "",  # 良/稍重/重/不良
            "moisture_rate": "",  # 含水率
            "note": ""
        }
        
        try:
            # テーブルからダート情報を探す
            tables = soup.find_all('table')
            for table in tables:
                text = table.get_text()
                if 'ダ' in text or 'ダート' in text:
                    # 馬場状態を抽出
                    condition_match = re.search(r'ダ[ート]*[：:・\s]*([良稍重不]+)', text)
                    if condition_match:
                        dirt["condition"] = condition_match.group(1)
                    
                    # 含水率を抽出
                    moisture_match = re.search(r'含水率[：:・\s]*(\d+\.?\d*)', text)
                    if moisture_match:
                        dirt["moisture_rate"] = moisture_match.group(1)
            
            # divやpタグからも探す
            for elem in soup.find_all(['div', 'p', 'span', 'td']):
                text = elem.get_text()
                
                # ダートの馬場状態
                if ('ダ' in text or 'ダート' in text) and dirt["condition"] == "":
                    match = re.search(r'ダ[ート]*[：:・\s]*([良稍重不]+)', text)
                    if match:
                        dirt["condition"] = match.group(1)
        
        except Exception as e:
            self.logger.warning(f"ダート馬場情報抽出エラー: {e}")
        
        return dirt
    
    def _extract_moisture_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """含水率データを抽出（詳細）"""
        moisture = {
            "turf_inner": "",  # 芝内回り
            "turf_outer": "",  # 芝外回り
            "dirt": "",  # ダート
            "measurement_time": ""  # 測定時刻
        }
        
        try:
            text_content = soup.get_text()
            
            # 含水率のパターンを探す
            # 「芝　良（内8.0％・外8.2%）」のようなパターン
            turf_pattern = re.search(r'芝[^\d]*[（(]?内?\s*(\d+\.?\d*)[%％].*外?\s*(\d+\.?\d*)[%％]', text_content)
            if turf_pattern:
                moisture["turf_inner"] = turf_pattern.group(1)
                moisture["turf_outer"] = turf_pattern.group(2)
            else:
                # 単一値のパターン
                single_turf = re.search(r'芝[^\d]*含水率[^\d]*(\d+\.?\d*)[%％]', text_content)
                if single_turf:
                    moisture["turf_inner"] = single_turf.group(1)
            
            # ダート含水率
            dirt_pattern = re.search(r'ダ[ート]*[^\d]*含水率[^\d]*(\d+\.?\d*)[%％]', text_content)
            if dirt_pattern:
                moisture["dirt"] = dirt_pattern.group(1)
            
            # 測定時刻
            time_pattern = re.search(r'(\d{1,2}[時:]\d{2})[分]?\s*[現測]', text_content)
            if time_pattern:
                moisture["measurement_time"] = time_pattern.group(1)
        
        except Exception as e:
            self.logger.warning(f"含水率データ抽出エラー: {e}")
        
        return moisture
    
    def _extract_comments(self, soup: BeautifulSoup) -> List[str]:
        """馬場傾向・コメントを抽出"""
        comments = []
        
        try:
            # コメントや特記事項のセクションを探す
            comment_keywords = ['傾向', '注意', 'ポイント', '特記', 'コメント', '備考']
            
            for keyword in comment_keywords:
                elems = soup.find_all(text=re.compile(keyword))
                for elem in elems:
                    parent = elem.parent
                    if parent:
                        # 次の兄弟要素からテキストを取得
                        next_elem = parent.find_next_sibling()
                        if next_elem:
                            text = next_elem.get_text().strip()
                            if text and len(text) > 5:
                                comments.append(text)
            
            # 重複を削除
            comments = list(set(comments))
        
        except Exception as e:
            self.logger.warning(f"コメント抽出エラー: {e}")
        
        return comments
    
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """
        抽出されたデータを検証
        
        Args:
            data: 検証対象のデータ
            
        Returns:
            bool: データが有効な場合True
        """
        if data.get("parse_status") == "error":
            return False
        
        # 少なくとも芝かダートの馬場状態が取得できていればOK
        turf_condition = data.get("turf", {}).get("condition", "")
        dirt_condition = data.get("dirt", {}).get("condition", "")
        
        return bool(turf_condition or dirt_condition)
    
    def save_json(self, data: Dict[str, Any], output_path: str) -> None:
        """
        データをJSONファイルとして保存
        
        Args:
            data: 保存するデータ
            output_path: 出力先パス
        """
        import json
        
        try:
            path = Path(output_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"馬場情報JSONを保存しました: {output_path}")
        
        except Exception as e:
            self.logger.error(f"JSON保存エラー: {e}")
            raise


def main():
    """テスト用エントリポイント"""
    import sys
    
    if len(sys.argv) < 2:
        print("使用方法: python babakeikou_parser.py <HTMLファイルパス>")
        sys.exit(1)
    
    html_path = sys.argv[1]
    parser = BabaKeikouParser(debug=True)
    result = parser.parse(html_path)
    
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
