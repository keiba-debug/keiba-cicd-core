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
            
            # AI指数情報を抽出
            ai_data = self._extract_ai_data(soup)
            
            # 展開情報を抽出
            tenkai_data = self._extract_tenkai_data(soup)
            
            # 本紙の見解を抽出
            race_comment = self._extract_race_comment(soup)
            
            # AI指数を各馬のデータにマージ
            if ai_data and 'entries' in ai_data:
                for ai_entry in ai_data['entries']:
                    horse_num = ai_entry.get('horse_number')
                    # 全角数字を半角に変換
                    horse_num_normalized = horse_num.translate(str.maketrans('０１２３４５６７８９', '0123456789')) if horse_num else ''
                    for horse in horses:
                        if str(horse.get('馬番')) == str(horse_num_normalized):
                            horse['AI指数'] = ai_entry.get('ai_index', '')
                            horse['AI指数ランク'] = ai_entry.get('rank', '')
                            horse['人気指数'] = ai_entry.get('popularity_index', '')
                            break
            
            result = {
                "race_info": race_info,
                "horses": horses,
                "horse_count": len(horses),
                "ai_data": ai_data,
                "tenkai_data": tenkai_data,
                "race_comment": race_comment  # 本紙の見解を追加
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
            
            # レース条件・距離情報を抽出
            # レース番号のリストから現在のレースの情報を取得
            race_list = soup.find('ul', class_='race')
            if race_list:
                active_race = race_list.find('li', class_='active')
                if active_race:
                    race_value = active_race.get('value', '')
                    # 例: "2歳未勝利 <br>芝・1800m" から情報を抽出
                    if race_value:
                        # <br>タグで分割
                        parts = race_value.split('<br>')
                        if len(parts) >= 2:
                            # レース条件
                            race_info['race_condition'] = parts[0].strip()
                            
                            # コース情報（芝・ダート、距離）
                            course_info = parts[1].strip()
                            # "芝・1800m" を解析
                            import re
                            match = re.match(r'(芝|ダ|ダート)・?(\d+)m', course_info)
                            if match:
                                track = match.group(1)
                                distance = match.group(2)
                                race_info['track'] = '芝' if track == '芝' else 'ダ'
                                race_info['distance'] = int(distance)
                                self.logger.debug(f"コース情報抽出: {track} {distance}m")
                
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
                
                # キー名の正規化: 特殊なスペース文字（U+2003など）を削除
                # 「騎　手」→「騎手」、「短　評」→「短評」、「厩　舎」→「厩舎」
                normalized_key = re.sub(r'[\s\u2003\u3000]+', '', header_name)
                
                # 基本的なセル値を設定（正規化されたキー名を使用）
                horse_data[normalized_key] = cell_text
                
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
                    # 元のキー名でも保存（互換性のため）
                    if header_name != normalized_key:
                        horse_data[header_name] = cell_text
                    
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
            '◎': 8,  # 最重要マーク
            '○': 5,  # 重要マーク
            '▲': 3,  # 注目マーク
            '△': 2,  # 要注意マーク
            '穴': 1,  # 穴馬マーク
            '注': 1,  # 注目マーク
            '×': 0,  # 評価低
            '': 0    # 無印は0点（マイナスなし）
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
        
        # 追加: 複数者（CPU〜本誌まで）の総合印ポイントを算出
        # 対象候補キー（表記ゆれを考慮し、優先順位を設定）
        candidate_sources = [
            ('CPU', ['CPU', 'ＣＰＵ']),
            ('本誌', ['本誌', '本紙', '本誌見解', '本紙見解']),
            ('牟田雅', ['牟田雅', '牟田']),
            ('西村敬', ['西村敬', '西村']),
            ('広瀬健', ['広瀬健', '広瀬']),
            ('予想1', ['印', '印_2', '印_3', '印_4']),  # thead起因の複製カラムなどを包括
        ]
        # マーク→点（シンプル版：マイナスなし、係数なし）
        def to_point(mark_text: str, source_label: str = None) -> float:
            # 無印または空文字列の場合は0点
            if not mark_text or mark_text.strip() == '':
                return 0  # マイナスポイントを廃止

            # 基本ポイント（シンプルな加算のみ）
            base_point = 0
            for m, p in mark_values.items():
                if m != '' and m in mark_text:  # 空文字キーを除外
                    base_point = p
                    break

            # 係数を廃止し、全ての予想者を平等に扱う
            return base_point
        
        for horse in horses:
            marks_by_person = {}
            total_points = 0
            picked = 0
            # 既知キー優先で探索（無印も含む）
            for label, variants in candidate_sources:
                found = False
                for key in variants:
                    if key in horse:
                        mark_value = horse.get(key, '')
                        marks_by_person[label] = mark_value if mark_value else '無印'
                        total_points += to_point(str(mark_value), label)
                        picked += 1
                        found = True
                        break
                if found:  # foundフラグを確認
                    pass  # すでに処理済み
                if picked >= 7:  # 最大7者まで考慮
                    break
            # まだ7未満なら、残りは馬データの全キーからマークらしき値を拾う（ノイズは最小限）
            if picked < 7:
                for k, v in horse.items():
                    if k in ['馬番', '馬名', '馬名_clean', '単勝', '人気', '枠番']:
                        continue
                    if any(sym in str(v) for sym in mark_values.keys()):
                        if k not in marks_by_person:
                            marks_by_person[k] = v
                            total_points += to_point(str(v))
                            picked += 1
                            if picked >= 7:
                                break
            # 設定（ポイントを整数に丸める、マイナスなし）
            if marks_by_person or total_points != 0:
                horse['marks_by_person'] = marks_by_person
                # マイナスにならないよう、最小値を0に設定
                horse['総合印ポイント'] = max(0, int(round(total_points)))
            else:
                # 印情報がない場合も0点
                horse['総合印ポイント'] = 0

                # デバッグ用：計算詳細をログ出力（必要に応じてコメントアウト）
                # if total_points > 0:
                #     self.logger.debug(f"馬番{horse.get('馬番')} {horse.get('馬名')}: 総合P={int(round(total_points))}, 詳細={marks_by_person}")
        
        return horses
    
    def _extract_ai_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """AI指数データを抽出"""
        ai_data = {}
        
        try:
            # AI指数テーブルを探す
            ai_section = soup.find('p', class_='title', string='AI指数')
            if ai_section:
                ai_table = ai_section.find_next('table', class_='ai')
                if ai_table:
                    ai_entries = []
                    tbody = ai_table.find('tbody')
                    if tbody:
                        for row in tbody.find_all('tr'):
                            cells = row.find_all('td')
                            if len(cells) >= 5:
                                # 馬番を取得（枠番クラスから）
                                waku_elem = cells[1].find('p', class_=re.compile(r'waku\d+'))
                                horse_num = waku_elem.get_text(strip=True) if waku_elem else ''
                                
                                # 馬名を取得
                                uma_link = cells[2].find('a')
                                horse_name = uma_link.get_text(strip=True) if uma_link else cells[2].get_text(strip=True)
                                
                                entry = {
                                    'rank': cells[0].get_text(strip=True),
                                    'horse_number': horse_num,
                                    'horse_name': horse_name,
                                    'popularity_index': cells[3].get_text(strip=True),
                                    'ai_index': cells[4].get_text(strip=True)
                                }
                                ai_entries.append(entry)
                    
                    ai_data['entries'] = ai_entries
                    self.logger.info(f"AI指数データ取得: {len(ai_entries)}頭")
                    
        except Exception as e:
            self.logger.debug(f"AI指数データ抽出エラー: {e}")
        
        return ai_data
    
    def _extract_tenkai_data(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """展開データを抽出"""
        tenkai_data = {}
        
        try:
            # 展開セクションを探す
            tenkai_section = soup.find('p', class_='title', string='展開')
            if tenkai_section:
                parent_div = tenkai_section.parent
                if parent_div:
                    # ペース情報を取得
                    pace_elem = parent_div.find('p', string=re.compile(r'ペース'))
                    if pace_elem:
                        pace_text = pace_elem.get_text()
                        # 「ペース　M」のような形式から「M」を抽出
                        pace_match = re.search(r'ペース[　\s]*([A-Z\-]+)', pace_text)
                        if pace_match:
                            tenkai_data['pace'] = pace_match.group(1)
                    
                    # 展開テーブルを取得
                    tenkai_table = parent_div.find('table')
                    if tenkai_table:
                        positions = {}
                        for row in tenkai_table.find_all('tr'):
                            cells = row.find_all(['th', 'td'])
                            for i in range(0, len(cells), 2):
                                if i + 1 < len(cells):
                                    position_name = cells[i].get_text(strip=True)
                                    horse_nums = []
                                    for num_elem in cells[i + 1].find_all('span', class_='marusuji'):
                                        num_text = num_elem.get_text(strip=True)
                                        # ①②③などの丸数字から数字を抽出
                                        num_text = num_text.replace('①', '1').replace('②', '2').replace('③', '3')
                                        num_text = num_text.replace('④', '4').replace('⑤', '5').replace('⑥', '6')
                                        num_text = num_text.replace('⑦', '7').replace('⑧', '8').replace('⑨', '9')
                                        num_text = num_text.replace('⑩', '10').replace('⑪', '11').replace('⑫', '12')
                                        num_text = num_text.replace('⑬', '13').replace('⑭', '14').replace('⑮', '15')
                                        num_text = num_text.replace('⑯', '16').replace('⑰', '17').replace('⑱', '18')
                                        horse_nums.append(num_text)
                                    positions[position_name] = horse_nums
                        
                        tenkai_data['positions'] = positions
                    
                    # 展開解説を取得
                    # テーブルの後のpタグ
                    description_p = tenkai_table.find_next_sibling('p') if tenkai_table else None
                    if description_p:
                        desc_text = description_p.get_text(strip=True)
                        if desc_text and not desc_text.startswith('title'):
                            tenkai_data['description'] = desc_text
                    
                    self.logger.info(f"展開データ取得: ペース={tenkai_data.get('pace', 'N/A')}")
                    
        except Exception as e:
            self.logger.debug(f"展開データ抽出エラー: {e}")
        
        return tenkai_data
    
    def _extract_race_comment(self, soup: BeautifulSoup) -> str:
        """本紙の見解を抽出"""
        race_comment = ""
        
        try:
            # 本紙の見解セクションを探す
            comment_title = soup.find('p', class_='title', string=re.compile(r'本[紙誌]の見解'))
            if comment_title:
                # 次のp要素が見解本文
                comment_p = comment_title.find_next_sibling('p')
                if comment_p:
                    race_comment = comment_p.get_text(strip=True)
                    self.logger.debug(f"本紙の見解を抽出: {race_comment[:50]}...")
            else:
                self.logger.debug("本紙の見解が見つかりません")
                
        except Exception as e:
            self.logger.debug(f"本紙の見解抽出エラー: {e}")
        
        return race_comment
    
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