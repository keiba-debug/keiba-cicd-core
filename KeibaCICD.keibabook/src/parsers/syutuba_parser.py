#!/usr/bin/env python3
"""
出馬表データパーサー

競馬ブックの出馬表ページからHTMLを解析してJSONデータを生成
"""

import re
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from bs4 import BeautifulSoup

from ..utils.logger import setup_logger


class SyutubaParser:
    """出馬表データパーサー（競馬ブック専用）"""
    
    def __init__(self, debug: bool = False):
        """
        初期化
        
        Args:
            debug: デバッグモード
        """
        self.debug = debug
        self.logger = setup_logger("SyutubaParser", level="DEBUG" if debug else "INFO")
    
    def parse(self, html_file_path: str) -> Dict[str, Any]:
        """
        HTMLファイルから出馬表データを抽出
        
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
        HTMLコンテンツから出馬表データを抽出
        
        Args:
            html_content: HTMLコンテンツ
            
        Returns:
            Dict[str, Any]: 抽出されたデータ
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # レース情報を抽出
            race_info = self._extract_race_info(soup)
            
            # 出走馬情報を抽出
            horses = self._extract_horses(soup)
            
            result = {
                "race_info": race_info,
                "horses": horses,
                "horse_count": len(horses)
            }
            
            self.logger.info(f"出馬表パース完了: {len(horses)}頭")
            return result
            
        except Exception as e:
            self.logger.error(f"HTMLパースエラー: {e}")
            raise
    
    def _extract_race_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """レース基本情報を抽出"""
        race_info = {}
        
        try:
            # レース名（タイトルから抽出）
            title = soup.find('title')
            if title:
                title_text = title.get_text()
                race_info['title'] = title_text.strip()
            
            # レース条件・距離情報
            # 競馬ブックの出馬表ページから具体的な情報を抽出
            # （実際のHTMLを見て詳細を実装）
                
        except Exception as e:
            self.logger.debug(f"レース情報抽出エラー: {e}")
        
        return race_info
    
    def _extract_horses(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """出走馬情報を抽出（競馬ブック専用）"""
        horses = []
        
        try:
            # 競馬ブックの出馬表テーブルを探す
            # syutubaクラスまたはumacdリンクを含むテーブルを特定
            target_table = None
            
            # まずsyutubaクラスのテーブルを探す
            syutuba_table = soup.find('table', class_=re.compile(r'syutuba'))
            if syutuba_table:
                target_table = syutuba_table
                self.logger.debug("syutubaクラスのテーブル発見")
            else:
                # umacdリンクを含むテーブルを探す
                tables = soup.find_all('table')
                for table in tables:
                    umacd_links = table.find_all('a', attrs={'umacd': True})
                    if len(umacd_links) > 5:  # 複数の馬がいるテーブル
                        target_table = table
                        self.logger.debug(f"umacdリンクを含むテーブル発見: {len(umacd_links)}個")
                        break
            
            if not target_table:
                self.logger.warning("出馬表テーブルが見つかりません")
                return horses
            
            # theadからヘッダーを取得
            thead = target_table.find('thead')
            headers = []
            if thead:
                header_row = thead.find('tr')
                if header_row:
                    headers = self._extract_headers_from_row(header_row)
                    self.logger.debug(f"ヘッダー: {headers}")
            
            # tbodyからデータ行を取得
            tbody = target_table.find('tbody')
            if tbody:
                data_rows = tbody.find_all('tr')
                self.logger.debug(f"データ行数: {len(data_rows)}")
            else:
                # tbodyがない場合は全ての行から取得（ヘッダー行をスキップ）
                all_rows = target_table.find_all('tr')
                data_rows = all_rows[1:] if len(all_rows) > 1 else all_rows
                self.logger.debug(f"データ行数（tbodyなし）: {len(data_rows)}")
            
            # データ行を解析
            for i, row in enumerate(data_rows):
                horse_data = self._extract_horse_from_row(row, headers)
                if horse_data and horse_data.get('馬番'):
                    horses.append(horse_data)
                    self.logger.debug(f"馬データ抽出: {horse_data.get('馬番')}番 {horse_data.get('馬名_clean', horse_data.get('馬名', 'N/A'))}")
            
            # 本誌見解の印ポイントを集計
            self._calculate_mark_points(horses)
                    
        except Exception as e:
            self.logger.error(f"出走馬情報抽出エラー: {e}")
        
        return horses
    
    def _extract_headers_from_row(self, header_row) -> List[str]:
        """ヘッダー行からカラム名を抽出"""
        headers = []
        
        try:
            cells = header_row.find_all(['th', 'td'])
            for cell in cells:
                header_text = cell.get_text(strip=True)
                headers.append(header_text)
        except Exception as e:
            self.logger.debug(f"ヘッダー抽出エラー: {e}")
            
        return headers
    
    def _extract_horse_from_row(self, row, headers: List[str]) -> Optional[Dict[str, Any]]:
        """行から馬の情報を抽出（umacd対応）"""
        horse_data = {}
        
        try:
            cells = row.find_all(['td', 'th'])
            
            # 各セルを解析
            for i, cell in enumerate(cells):
                cell_text = cell.get_text(strip=True)
                
                # ヘッダー名を取得
                header_name = headers[i] if i < len(headers) else f'field_{i}'
                
                # 基本的なセル値を設定
                horse_data[header_name] = cell_text
                
                # umacd属性を持つリンクを探す（馬名セル）
                umacd_link = cell.find('a', attrs={'umacd': True})
                if umacd_link:
                    umacd = umacd_link.get('umacd')
                    horse_name = umacd_link.get_text(strip=True)
                    href = umacd_link.get('href', '')
                    
                    # umacd情報を追加
                    horse_data['umacd'] = umacd
                    horse_data['馬名_clean'] = horse_name  # クリーンな馬名
                    horse_data['馬名_link'] = href
                    
                    self.logger.debug(f"umacd抽出: {horse_name} (umacd: {umacd})")
                
                # その他の特殊なリンクや属性も抽出可能
                # 例：騎手リンク、調教師リンクなど
                
            # 馬番が数字でない場合はスキップ
            bano = horse_data.get('馬番', '')
            if not bano.isdigit():
                return None
                
        except Exception as e:
            self.logger.debug(f"馬データ抽出エラー: {e}")
            return None
            
        return horse_data
    
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """データの妥当性を検証"""
        try:
            if not isinstance(data, dict):
                self.logger.error("データがdict型ではありません")
                return False
            
            if 'horses' not in data:
                self.logger.error("horsesフィールドがありません")
                return False
            
            horses = data['horses']
            if not isinstance(horses, list):
                self.logger.error("horsesがlist型ではありません")
                return False
            
            if len(horses) == 0:
                self.logger.warning("出走馬がいません")
                return False
            
            # 各馬のデータをチェック
            umacd_count = 0
            for i, horse in enumerate(horses):
                if not isinstance(horse, dict):
                    self.logger.error(f"馬データ{i}がdict型ではありません")
                    return False
                
                # umacdの存在確認
                if horse.get('umacd'):
                    umacd_count += 1
            
            self.logger.info(f"データ検証OK: {len(horses)}頭の出走馬 (umacd: {umacd_count}頭)")
            return True
            
        except Exception as e:
            self.logger.error(f"データ検証エラー: {e}")
            return False
    
    def _calculate_mark_points(self, horses: List[Dict[str, Any]]) -> None:
        """
        本誌見解の印からポイントを計算して各馬に追加
        
        ◎: 5点
        ○: 4点
        ▲: 3点
        △: 2点
        穴: 1点
        注: 1点
        """
        mark_values = {
            '◎': 5,
            '○': 4,
            '▲': 3,
            '△': 2,
            '穴': 1,
            '注': 1,
            '×': 0
        }
        
        # 印の集計
        mark_summary = {
            '◎': [],
            '○': [],
            '▲': [],
            '△': [],
            '穴': [],
            '注': []
        }
        
        for horse in horses:
            # 本誌欄を探す（複数のキー名に対応）
            honshi_mark = horse.get('本誌') or horse.get('本紙') or horse.get('本誌見解') or ''
            
            if honshi_mark:
                # ポイント計算
                mark_point = 0
                for mark, point in mark_values.items():
                    if mark in honshi_mark:
                        mark_point = max(mark_point, point)
                        # 集計に追加
                        if mark in mark_summary:
                            mark_summary[mark].append({
                                '馬番': horse.get('馬番'),
                                '馬名': horse.get('馬名_clean') or horse.get('馬名', '')
                            })
                
                # 馬データにポイントを追加
                horse['本誌印ポイント'] = mark_point
                horse['本誌印'] = honshi_mark
                
                self.logger.debug(f"印ポイント計算: {horse.get('馬番')}番 {honshi_mark} = {mark_point}点")
        
        # 印ポイントでソート（降順）
        horses.sort(key=lambda x: x.get('本誌印ポイント', 0), reverse=True)
        
        # サマリー情報をログ出力
        for mark, horses_with_mark in mark_summary.items():
            if horses_with_mark:
                names = ', '.join([f"{h['馬番']}番{h['馬名']}" for h in horses_with_mark])
                self.logger.info(f"本誌{mark}: {names}")
        
        # 追加: 複数者（CPU〜本誌まで）の総合印ポイントを算出（最大5者）
        # 対象候補キー（表記ゆれを考慮）
        candidate_sources = [
            ('CPU', ['CPU', 'ＣＰＵ']),
            ('本誌', ['本誌', '本紙', '本誌見解', '本紙見解']),
            ('予想1', ['印', '印_2', '印_3', '印_4']),  # thead起因の複製カラムなどを包括
        ]
        # マーク→点
        def to_point(mark_text: str) -> int:
            if not mark_text:
                return 0
            for m, p in mark_values.items():
                if m in mark_text:
                    return p
            return 0
        
        for horse in horses:
            marks_by_person = {}
            total_points = 0
            picked = 0
            # 既知キー優先で探索
            for label, variants in candidate_sources:
                for key in variants:
                    if key in horse and horse.get(key):
                        marks_by_person[label] = horse.get(key)
                        total_points += to_point(str(horse.get(key)))
                        picked += 1
                        break
                if picked >= 5:
                    break
            # まだ5未満なら、残りは馬データの全キーからマークらしき値を拾う（ノイズは最小限）
            if picked < 5:
                for k, v in horse.items():
                    if k in ['馬番', '馬名', '馬名_clean', '単勝', '人気', '枠番']:
                        continue
                    if any(sym in str(v) for sym in mark_values.keys()):
                        if k not in marks_by_person:
                            marks_by_person[k] = v
                            total_points += to_point(str(v))
                            picked += 1
                            if picked >= 5:
                                break
            # 設定
            if marks_by_person:
                horse['marks_by_person'] = marks_by_person
                horse['総合印ポイント'] = total_points
        
        return horses
    
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