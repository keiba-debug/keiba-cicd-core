#!/usr/bin/env python3
"""
パドック情報データパーサー

競馬ブックのパドック情報ページからHTMLを解析してJSONデータを生成
注意: 競馬ブックのパドックページは評価情報が限定的な場合があります
"""

import re
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from bs4 import BeautifulSoup

from ..utils.logger import setup_logger


class PaddokParser:
    """パドック情報データパーサー（競馬ブック専用）"""
    
    def __init__(self, debug: bool = False):
        """
        初期化
        
        Args:
            debug: デバッグモード
        """
        self.debug = debug
        self.logger = setup_logger("PaddokParser", level="DEBUG" if debug else "INFO")
    
    def parse(self, html_file_path: str) -> Dict[str, Any]:
        """
        HTMLファイルからパドック情報データを抽出
        
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
        HTMLコンテンツからパドック情報データを抽出
        
        Args:
            html_content: HTMLコンテンツ
            
        Returns:
            Dict[str, Any]: 抽出されたデータ
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # レース情報を抽出
            race_info = self._extract_race_info(soup)
            
            # パドック評価情報を抽出（複数の方法を試す）
            paddock_data = []
            
            # 方法1: 構造化されたパドックデータを探す
            paddock_data = self._extract_structured_paddock_data(soup)
            
            # 方法2: テキストパターンから抽出
            if not paddock_data:
                paddock_data = self._extract_paddock_from_text(soup)
            
            # 方法3: デフォルトの空データを生成（データが見つからない場合）
            if not paddock_data:
                self.logger.warning("パドック評価データが見つかりませんでした。空のデータを返します。")
                paddock_data = self._generate_default_paddock_data()
            
            result = {
                "race_info": race_info,
                "paddock_evaluations": paddock_data,
                "evaluation_count": len(paddock_data),
                "data_status": "complete" if paddock_data else "no_data_available"
            }
            
            self.logger.info(f"パドック情報パース完了: {len(paddock_data)}頭")
            return result
            
        except Exception as e:
            self.logger.error(f"HTMLパースエラー: {e}")
            raise
    
    def _extract_race_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """レース基本情報を抽出"""
        race_info = {}
        
        try:
            # タイトルから情報抽出
            title = soup.find('title')
            if title:
                title_text = title.get_text()
                race_info['title'] = title_text.strip()
                
                # レース情報をタイトルから推測
                if '札幌' in title_text:
                    race_info['venue'] = '札幌'
                elif '函館' in title_text:
                    race_info['venue'] = '函館'
                elif '福島' in title_text:
                    race_info['venue'] = '福島'
                elif '新潟' in title_text:
                    race_info['venue'] = '新潟'
                elif '東京' in title_text:
                    race_info['venue'] = '東京'
                elif '中山' in title_text:
                    race_info['venue'] = '中山'
                elif '中京' in title_text:
                    race_info['venue'] = '中京'
                elif '京都' in title_text:
                    race_info['venue'] = '京都'
                elif '阪神' in title_text:
                    race_info['venue'] = '阪神'
                elif '小倉' in title_text:
                    race_info['venue'] = '小倉'
            
            # メタデータから情報抽出
            meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
            if meta_keywords:
                race_info['keywords'] = meta_keywords.get('content', '')
                
        except Exception as e:
            self.logger.debug(f"レース情報抽出エラー: {e}")
        
        return race_info
    
    def _extract_structured_paddock_data(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """構造化されたパドックデータを抽出"""
        paddock_data = []
        
        try:
            # テーブル構造からパドック情報を抽出
            # 競馬ブックのパドックページは「コメント」「評価」の列を持つテーブル
            table = None
            
            # テーブルを探す（コメント列があるテーブル）
            for t in soup.find_all('table'):
                headers = t.find_all('th')
                header_text = ' '.join([h.get_text() for h in headers])
                if 'コメント' in header_text and '評価' in header_text:
                    table = t
                    break
            
            if table:
                # テーブルの各行を処理
                tbody = table.find('tbody')
                if tbody:
                    rows = tbody.find_all('tr')
                else:
                    rows = table.find_all('tr')[1:]  # ヘッダー行をスキップ
                
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) >= 8:  # 必要な列数があるか確認
                        try:
                            # 馬番
                            horse_num_cell = cells[1]  # 2列目が馬番
                            horse_num = horse_num_cell.get_text().strip()
                            
                            # 馬名
                            horse_name_cell = cells[2]  # 3列目が馬名
                            horse_link = horse_name_cell.find('a')
                            if horse_link:
                                horse_name = horse_link.get_text().strip()
                            else:
                                horse_name = horse_name_cell.get_text().strip()
                            
                            # コメント（6列目）
                            comment_cell = cells[6] if len(cells) > 6 else None
                            comment = comment_cell.get_text().strip() if comment_cell else ''
                            
                            # 評価（8列目）
                            eval_cell = cells[8] if len(cells) > 8 else None
                            evaluation = eval_cell.get_text().strip() if eval_cell else ''
                            
                            if horse_num and horse_name:
                                data = {
                                    'horse_number': int(horse_num) if horse_num.isdigit() else 0,
                                    'horse_name': horse_name,
                                    'comment': comment if comment else '',
                                    'evaluation': evaluation if evaluation else '',
                                    'mark': evaluation if evaluation else ''
                                }
                                paddock_data.append(data)
                        except Exception as e:
                            self.logger.debug(f"行データ処理エラー: {e}")
                            continue
                            
        except Exception as e:
            self.logger.debug(f"構造化パドックデータ抽出エラー: {e}")
        
        return paddock_data
    
    def _parse_paddock_element(self, element) -> Optional[Dict[str, Any]]:
        """パドック要素から情報を抽出"""
        try:
            text = element.get_text().strip()
            if not text or len(text) < 3:
                return None
            
            evaluation = {}
            
            # 馬番を探す
            horse_num_match = re.search(r'(\d{1,2})番', text)
            if horse_num_match:
                evaluation['horse_number'] = int(horse_num_match.group(1))
            
            # 馬名を探す（カタカナ3文字以上）
            horse_name_match = re.search(r'([ァ-ヴー]{3,})', text)
            if horse_name_match:
                evaluation['horse_name'] = horse_name_match.group(1)
            
            # 評価マークを探す
            mark_match = re.search(r'([◎○▲△×☆★－]+)', text)
            if mark_match:
                evaluation['mark'] = mark_match.group(1)
                evaluation['evaluation'] = mark_match.group(1)  # 評価として追加
            
            # コメントを抽出（10文字以上の連続テキスト）
            comment_match = re.search(r'([^。、\n]{10,}[。、]?)', text)
            if comment_match:
                comment = comment_match.group(1)
                # パドック関連のコメントか確認
                if any(keyword in comment for keyword in ['馬体', '気配', '歩様', 'パドック', '毛艶', '状態', '仕上']):
                    evaluation['comment'] = comment
            
            return evaluation if evaluation else None
            
        except Exception as e:
            self.logger.debug(f"パドック要素パースエラー: {e}")
            return None
    
    def _extract_paddock_from_text(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """テキストパターンからパドック情報を抽出"""
        paddock_data = []
        
        try:
            # ページ全体のテキストを取得
            text = soup.get_text()
            
            # 馬番と評価のパターンを探す
            # 例: "1番 ◎" または "1 ◎"
            pattern = r'(\d{1,2})番?\s*([◎○▲△×☆★－]+)'
            matches = re.findall(pattern, text)
            
            for match in matches:
                horse_num = int(match[0])
                mark = match[1]
                
                evaluation = {
                    'horse_number': horse_num,
                    'mark': mark,
                    'evaluation': mark,
                    'comment': 'パドック評価データ'
                }
                
                paddock_data.append(evaluation)
                
        except Exception as e:
            self.logger.debug(f"テキストパターン抽出エラー: {e}")
        
        return paddock_data
    
    def _generate_default_paddock_data(self) -> List[Dict[str, Any]]:
        """デフォルトの空パドックデータを生成"""
        # 競馬ブックのパドックページにデータがない場合の処理
        # 空のリストを返すか、メッセージを含む単一のエントリを返す
        return [{
            'message': 'パドック評価データは現在利用できません',
            'data_available': False
        }]
    
    def _calculate_mark_score(self, mark: str) -> int:
        """評価マークから点数を計算"""
        mark_values = {
            'Ｓ': 5,
            'S': 5,
            'Ａ': 4,
            'A': 4,
            'Ｂ': 3,
            'B': 3,
            'Ｃ': 2,
            'C': 2,
            '◎': 5,
            '○': 4, 
            '▲': 3,
            '△': 2,
            '☆': 1,
            '★': 1,
            '×': 0,
            '－': 0,
            '': 0
        }
        
        # 複数マークの場合は最高点を採用
        max_score = 0
        for char in mark:
            score = mark_values.get(char, 0)
            if score > max_score:
                max_score = score
        
        return max_score