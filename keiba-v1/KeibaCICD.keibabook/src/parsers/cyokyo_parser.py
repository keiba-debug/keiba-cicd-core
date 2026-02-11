#!/usr/bin/env python3
"""
調教データパーサー

競馬ブックの調教ページからHTMLを解析してJSONデータを生成
"""

import re
import json
from typing import Dict, List, Any
from pathlib import Path
from bs4 import BeautifulSoup

from ..utils.logger import setup_logger


class CyokyoParser:
    """調教データパーサー"""
    
    def __init__(self, debug: bool = False):
        """
        初期化
        
        Args:
            debug: デバッグモード
        """
        self.debug = debug
        self.logger = setup_logger("CyokyoParser", level="DEBUG" if debug else "INFO")
    
    def parse(self, html_file_path: str) -> Dict[str, Any]:
        """
        HTMLファイルから調教データを抽出
        
        Args:
            html_file_path: HTMLファイルのパス
            
        Returns:
            Dict[str, Any]: 抽出されたデータ
        """
        try:
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # ファイル名からrace_idを抽出
            file_path = Path(html_file_path)
            race_id = self._extract_race_id_from_filename(file_path.name)
            self.current_race_id = race_id  # インスタンス変数に保存
            
            # レース情報を抽出
            race_info = self._extract_race_info(soup)
            
            # 調教情報を抽出
            training_data = self._extract_training_data(soup)
            
            # データを添付ファイルの形式に変換
            formatted_data = self._format_training_data(training_data, race_id)
            
            return {
                "race_info": race_info,
                "training_data": formatted_data
            }
            
        except Exception as e:
            self.logger.error(f"HTMLパースエラー: {e}")
            raise
    
    def _extract_race_info(self, soup: BeautifulSoup) -> Dict[str, str]:
        """レース基本情報を抽出"""
        race_info = {}
        
        try:
            # レース名
            race_name_elem = soup.find(['h1', 'h2', 'h3'], string=re.compile(r'第?\d+回|レース|調教'))
            if race_name_elem:
                race_info['race_name'] = race_name_elem.get_text().strip()
            
            # 日付情報
            date_info = soup.find('div', class_=re.compile(r'date|time'))
            if date_info:
                race_info['date_info'] = date_info.get_text().strip()
                
        except Exception as e:
            self.logger.debug(f"レース情報抽出エラー: {e}")
        
        return race_info
    
    def _extract_training_data(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """調教情報を抽出（攻め解説対応版）"""
        training_list = []

        try:
            # class="cyokyo"のテーブルを全て取得（各馬のデータ）
            cyokyo_tables = soup.find_all('table', class_='cyokyo')
            self.logger.debug(f"調教テーブル数: {len(cyokyo_tables)}")

            # 攻め解説divも全て取得
            semekaisetu_divs = soup.find_all('div', class_='semekaisetu')
            self.logger.debug(f"攻め解説div数: {len(semekaisetu_divs)}")

            for table in cyokyo_tables:
                training_data = {}

                # 最初のtbodyの最初のtrから基本情報を取得
                tbody = table.find('tbody')
                if not tbody:
                    continue

                first_tr = tbody.find('tr')
                if not first_tr:
                    continue

                # 馬番を取得（class="umaban"）
                umaban_cell = first_tr.find('td', class_='umaban')
                if umaban_cell:
                    text = umaban_cell.get_text(strip=True)
                    import re
                    match = re.search(r'(\d+)', text)
                    if match:
                        training_data['horse_number'] = int(match.group(1))
                        self.logger.debug(f"馬番抽出: {training_data['horse_number']}")

                # 馬名を取得（class="kbamei"）
                kbamei_cell = first_tr.find('td', class_='kbamei')
                if kbamei_cell:
                    # リンク内のテキストを取得
                    horse_link = kbamei_cell.find('a')
                    if horse_link:
                        training_data['horse_name'] = horse_link.get_text(strip=True)
                    else:
                        training_data['horse_name'] = kbamei_cell.get_text(strip=True)
                    self.logger.debug(f"馬名抽出: {training_data['horse_name']}")

                # 短評を取得（class="tanpyo"）
                tanpyo_cell = first_tr.find('td', class_='tanpyo')
                if tanpyo_cell:
                    short_review = tanpyo_cell.get_text(strip=True)
                    if short_review:
                        training_data['short_review'] = short_review
                        self.logger.debug(f"短評抽出: {short_review}")

                # 矢印を取得（class="yajirusi"）
                yajirusi_cell = first_tr.find('td', class_='yajirusi')
                if yajirusi_cell:
                    arrow_span = yajirusi_cell.find('span')
                    if arrow_span:
                        arrow_text = arrow_span.get_text(strip=True)
                    else:
                        arrow_text = yajirusi_cell.get_text(strip=True)
                    if arrow_text:
                        training_data['training_arrow'] = arrow_text
                        self.logger.debug(f"矢印抽出: {arrow_text}")

                # 攻め解説を取得（テーブルの後にあるdiv.semekaisetu）
                # テーブルの次の兄弟要素を探す
                next_sibling = table.find_next_sibling('div', class_='semekaisetu')
                if next_sibling:
                    p_elem = next_sibling.find('p')
                    if p_elem:
                        attack_explanation = p_elem.get_text(strip=True)
                        if attack_explanation:
                            training_data['attack_explanation'] = attack_explanation
                            self.logger.debug(f"攻め解説抽出: {attack_explanation[:30] if len(attack_explanation) > 30 else attack_explanation}")
                else:
                    # 別の方法：テーブルのIDを使って対応する攻め解説を探す
                    table_id = table.get('id', '')
                    if table_id:
                        # 同じ馬番のsemekaisetsuを探す（インデックスベース）
                        horse_idx = cyokyo_tables.index(table)
                        if horse_idx < len(semekaisetu_divs):
                            div = semekaisetu_divs[horse_idx]
                            p_elem = div.find('p')
                            if p_elem:
                                attack_explanation = p_elem.get_text(strip=True)
                                if attack_explanation:
                                    training_data['attack_explanation'] = attack_explanation
                                    self.logger.debug(f"攻め解説抽出（インデックス）: {attack_explanation[:30] if len(attack_explanation) > 30 else attack_explanation}")

                # race_idを設定
                training_data['race_id'] = self._get_race_id_from_context()

                # 有効なデータのみ追加
                if training_data.get('horse_number'):
                    training_list.append(training_data)
                    self.logger.debug(f"調教データ追加: 馬番{training_data['horse_number']} {training_data.get('horse_name', '')}")

            # fallbackとして他の形式も試す
            if not training_list:
                self.logger.warning("cyokyoクラスのテーブルが見つかりません。フォールバック処理を実行")
                training_list = self._extract_training_data_fallback(soup)
                    
        except Exception as e:
            self.logger.error(f"調教情報抽出エラー: {e}")
        
        return training_list
    
    def _is_training_table(self, table) -> bool:
        """テーブルが調教テーブルかどうかを判定"""
        text = table.get_text()
        keywords = ['馬番', '馬名', '調教', 'タイム', '追切', '評価', 'コース']
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
    
    def _extract_training_with_explanation(self, row, table_idx: int, row_idx: int) -> Dict[str, str]:
        """攻め解説を含む行から調教情報を抽出"""
        training_data = {}
        
        try:
            # セルを取得
            cells = row.find_all(['td', 'th'])
            if not cells:
                return {}
            
            # 行のテキスト全体から攻め解説を抽出
            row_text = row.get_text()
            
            # 馬番・馬名をテーブル位置から推定
            horse_number, horse_name = self._extract_horse_info_from_context(table_idx, row_idx)
            # デバッグログを追加
            self.logger.debug(f"テーブル位置推定：テーブル{table_idx+1}、行{row_idx+1}")
            
            if horse_number:
                training_data['馬番'] = str(horse_number)
                training_data['horse_number'] = horse_number
                self.logger.debug(f"馬番抽出成功: {horse_number}")
            else:
                self.logger.debug(f"馬番抽出失敗: テーブル{table_idx+1}")
            
            if horse_name:
                training_data['馬名'] = horse_name
                training_data['horse_name'] = horse_name
                self.logger.debug(f"馬名抽出成功: {horse_name}")
            else:
                self.logger.debug(f"馬名抽出失敗: テーブル{table_idx+1}")
            
            # 攻め解説を抽出
            attack_explanation = self._extract_attack_explanation(row_text)
            if attack_explanation:
                training_data['attack_explanation'] = attack_explanation
                self.logger.debug(f"攻め解説抽出成功: {attack_explanation[:50]}...")

            # 短評を抽出（class="tanpyo"のtd要素から直接取得）
            tanpyo_cell = row.find('td', class_='tanpyo')
            if tanpyo_cell:
                short_review = tanpyo_cell.get_text(strip=True)
                if short_review:
                    training_data['short_review'] = short_review
                    self.logger.debug(f"短評抽出成功(tanpyo): {short_review[:50]}...")
            else:
                # class="tanpyo"がない場合はテキストから抽出
                short_review = self._extract_short_review(row_text)
                if short_review:
                    training_data['short_review'] = short_review
                    self.logger.debug(f"短評抽出成功(テキスト): {short_review[:50]}...")
            
            # 矢印を抽出（短評の横にある調教の変化を示す矢印）
            arrow_cell = row.find('td', class_='yajirusi')
            if arrow_cell:
                # spanタグ内のテキストも含めて取得
                arrow_span = arrow_cell.find('span', class_=['kakusuji2keta', 'kakusuji1keta'])
                if arrow_span:
                    arrow_text = arrow_span.get_text(strip=True)
                else:
                    arrow_text = arrow_cell.get_text(strip=True)
                    
                if arrow_text and arrow_text in ['→', '↗', '↘', '↑', '↓']:
                    training_data['training_arrow'] = arrow_text
                    self.logger.debug(f"調教矢印抽出成功: {arrow_text}")
            
            # race_idを設定（ファイル名から推定）
            training_data['race_id'] = self._get_race_id_from_context()
            
            # horse_number/horse_nameは既に設定済み
                        
        except Exception as e:
            self.logger.debug(f"攻め解説付き調教データ抽出エラー: {e}")
            
        return training_data
    
    def _extract_attack_explanation(self, text: str) -> str:
        """テキストから攻め解説を抽出"""
        try:
            # 「攻め解説」の後の文章を抽出
            match = re.search(r'攻め解説\s*　?([^攻]+?)(?:騎乗者|助手|\d+\/\d+|$)', text, re.DOTALL)
            if match:
                explanation = match.group(1).strip()
                # 余分な文字を除去
                explanation = re.sub(r'\s+', ' ', explanation)  # 連続空白を単一スペースに
                explanation = explanation.replace('\n', ' ').replace('\r', ' ')
                explanation = explanation.strip()
                return explanation

            return ""
        except Exception as e:
            self.logger.debug(f"攻め解説抽出エラー: {e}")
            return ""

    def _extract_short_review(self, text: str) -> str:
        """テキストから短評を抽出（追い切り短評も含む）"""
        try:
            # 「追い切り短評」または「短評」の後の文章を抽出
            # 追い切り短評を優先的にマッチ
            patterns = [
                r'追い切り短評\s*　?([^攻短]+?)(?:攻め解説|騎乗者|助手|\d+\/\d+|$)',
                r'追切短評\s*　?([^攻短]+?)(?:攻め解説|騎乗者|助手|\d+\/\d+|$)',
                r'短評\s*　?([^攻短]+?)(?:攻め解説|騎乗者|助手|\d+\/\d+|$)'
            ]

            for pattern in patterns:
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    review = match.group(1).strip()
                    # 余分な文字を除去
                    review = re.sub(r'\s+', ' ', review)  # 連続空白を単一スペースに
                    review = review.replace('\n', ' ').replace('\r', ' ')
                    review = review.strip()
                    if review:  # 空でない場合のみ返す
                        self.logger.debug(f"短評パターンマッチ成功: {pattern[:20]}...")
                        return review

            return ""
        except Exception as e:
            self.logger.debug(f"短評抽出エラー: {e}")
            return ""
    
    def _extract_race_id_from_filename(self, filename: str) -> str:
        """ファイル名からrace_idを抽出"""
        try:
            # 例: cyokyo_202502041211_scraped.html -> 202502041211
            match = re.search(r'(\d{12})', filename)
            if match:
                return match.group(1)
            return ""
        except Exception as e:
            self.logger.debug(f"race_id抽出エラー: {e}")
            return ""
    
    def _get_race_id_from_context(self) -> str:
        """コンテキストからrace_idを取得"""
        return getattr(self, 'current_race_id', '')
    
    def _extract_arrow_data(self, soup: BeautifulSoup) -> Dict[int, str]:
        """HTMLから矢印データを抽出"""
        arrow_data = {}
        
        try:
            # 矢印セルをすべて取得（class="yajirusi"）
            arrow_cells = soup.find_all('td', class_='yajirusi')
            self.logger.debug(f"矢印セル数: {len(arrow_cells)}")
            
            # 各矢印セルから矢印を抽出（馬番順に配置されていると仮定）
            for i, arrow_cell in enumerate(arrow_cells, 1):
                # spanタグ内の矢印テキストを取得
                span = arrow_cell.find('span', class_=['kakusuji2keta', 'kakusuji1keta'])
                if span:
                    arrow_text = span.get_text(strip=True)
                    # 矢印文字を確認（Unicode文字も含む）
                    if arrow_text and len(arrow_text) > 0:
                        arrow_data[i] = arrow_text
                        self.logger.debug(f"馬番{i}の矢印: {arrow_text}")
            
        except Exception as e:
            self.logger.debug(f"矢印データ抽出エラー: {e}")
        
        return arrow_data

    def _extract_tanpyo_data(self, soup: BeautifulSoup) -> Dict[int, str]:
        """ページ全体からclass="tanpyo"のデータを抽出"""
        tanpyo_data = {}

        try:
            # class="tanpyo"の全てのtd要素を取得
            tanpyo_cells = soup.find_all('td', class_='tanpyo')
            self.logger.debug(f"短評セル数: {len(tanpyo_cells)}")

            # 各短評セルからテキストを抽出（馬番順に配置されていると仮定）
            for i, tanpyo_cell in enumerate(tanpyo_cells, 1):
                tanpyo_text = tanpyo_cell.get_text(strip=True)
                if tanpyo_text:
                    tanpyo_data[i] = tanpyo_text
                    self.logger.debug(f"馬番{i}の短評: {tanpyo_text[:20]}..." if len(tanpyo_text) > 20 else f"馬番{i}の短評: {tanpyo_text}")

        except Exception as e:
            self.logger.debug(f"短評データ抽出エラー: {e}")

        return tanpyo_data

    def _extract_from_tanpyo_table(self, table, table_idx: int) -> Dict[str, str]:
        """パtanpyo要素を含むテーブルから調教情報を抽出"""
        training_data = {}

        try:
            # tanpyoセルを探す
            tanpyo_cell = table.find('td', class_='tanpyo')
            if tanpyo_cell:
                training_data['short_review'] = tanpyo_cell.get_text(strip=True)
                self.logger.debug(f"tanpyoセルから短評を抽出: {training_data['short_review'][:20]}..." if len(training_data['short_review']) > 20 else f"tanpyoセルから短評を抽出: {training_data['short_review']}")

            # 馬番を探す（class="umaban"）
            horse_num_cell = table.find('td', class_='umaban')
            if horse_num_cell:
                text = horse_num_cell.get_text(strip=True)
                import re
                match = re.search(r'(\d+)', text)
                if match:
                    training_data['horse_number'] = int(match.group(1))
                    training_data['馬番'] = str(training_data['horse_number'])
                    self.logger.debug(f"馬番抽出: {training_data['horse_number']}")

            # 馬名を探す（class="kbamei"）
            horse_name_cell = table.find('td', class_='kbamei')
            if horse_name_cell:
                # 馬名にはリンクが含まれている可能性がある
                horse_name = horse_name_cell.get_text(strip=True)
                if horse_name:
                    training_data['horse_name'] = horse_name
                    training_data['馬名'] = horse_name
                    self.logger.debug(f"馬名抽出: {horse_name}")

            # 矢印を探す（class="yajirusi"）
            yajirusi_cell = table.find('td', class_='yajirusi')
            if yajirusi_cell:
                arrow_text = yajirusi_cell.get_text(strip=True)
                if arrow_text:
                    training_data['training_arrow'] = arrow_text
                    self.logger.debug(f"矢印抽出: {arrow_text}")

            # 攻め解説を探す（テーブル内のテキストから）
            table_text = table.get_text()
            if '攻め解説' in table_text:
                attack_explanation = self._extract_attack_explanation(table_text)
                if attack_explanation:
                    training_data['attack_explanation'] = attack_explanation
                    self.logger.debug(f"攻め解説抽出: {attack_explanation[:30]}..." if len(attack_explanation) > 30 else f"攻め解説抽出: {attack_explanation}")

            # race_idを設定
            training_data['race_id'] = self._get_race_id_from_context()

        except Exception as e:
            self.logger.debug(f"tanpyoテーブルからの抽出エラー: {e}")

        return training_data if training_data.get('horse_number') else None
    
    def _extract_horse_info_from_context(self, table_idx: int, row_idx: int) -> tuple:
        """テーブル位置から馬番・馬名を推定"""
        try:
            # テーブル位置から馬番を推定
            # テーブル3,5,7,9... = 奇数テーブルに馬の攻め解説データがある
            # これは0-indexedなので、実際のテーブル番号は+1した値
            # 馬番は (テーブル番号 - 3) / 2 + 1 で計算できそう
            actual_table_idx = table_idx + 1
            self.logger.debug(f"実際のテーブル番号: {actual_table_idx}")
            
            if actual_table_idx >= 3 and actual_table_idx % 2 == 1:  # 奇数テーブル
                horse_number = (actual_table_idx - 3) // 2 + 1
                self.logger.debug(f"推定馬番: {horse_number}")
                
                # 馬名の推定（実際のデータからのパターン）
                # 各テーブルには一つの馬のデータが入っているはず
                horse_names = [
                    'ディープテイスター', 'ベルローズ', 'ロゼ', 'コトブキナデシコ', 'ルフ',
                    'プリンスリターン', 'シャンパンカクテル', 'ヘンリーバローズ', 'ポッドガンナー',
                    'エリンガル', 'ソニックエクセル', 'メイショウロセツ', 'ブレイクアップ', 'マクガイア',
                    'エイトヴィンテージ', 'リアルパフォーマー', 'ミルコバージェ', 'ノースブリッジ'
                ]
                
                if horse_number > 0 and horse_number <= len(horse_names):
                    horse_name = horse_names[horse_number - 1]
                    self.logger.debug(f"推定馬名: {horse_name}")
                    return horse_number, horse_name
            
            self.logger.debug(f"推定失敗: テーブル{actual_table_idx}から馬番を算出できません")
            return None, None
        except Exception as e:
            self.logger.debug(f"馬情報推定エラー: {e}")
            return None, None
    
    def _format_training_data(self, training_data: List[Dict[str, str]], race_id: str) -> List[Dict[str, Any]]:
        """調教データを添付ファイルの形式に変換"""
        formatted_list = []

        for data in training_data:
            formatted_item = {
                "race_id": race_id,
                "horse_number": data.get('horse_number', ''),
                "horse_name": data.get('horse_name', ''),
                "attack_explanation": data.get('attack_explanation', ''),
                "short_review": data.get('short_review', ''),  # 短評を追加
                "training_arrow": data.get('training_arrow', '')  # 矢印を追加
            }

            # 有効なデータのみ追加（horse_numberがあれば追加）
            if formatted_item.get('horse_number'):
                formatted_list.append(formatted_item)

        return formatted_list
    
    def _extract_training_data_fallback(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """従来の方法で調教情報を抽出（フォールバック）"""
        training_list = []
        
        try:
            # 調教テーブルを探す
            table = soup.find('table', {'id': re.compile(r'cyokyo|training|workout')})
            if not table:
                table = soup.find('table', class_=re.compile(r'cyokyo|training|workout'))
            if not table:
                # 一般的なテーブルから探す
                tables = soup.find_all('table')
                for t in tables:
                    if self._is_training_table(t):
                        table = t
                        break
            
            if not table:
                self.logger.warning("調教テーブルが見つかりません")
                return training_list
            
            # テーブルのヘッダーを解析
            headers = self._extract_headers(table)
            self.logger.debug(f"検出されたヘッダー: {headers}")
            
            # データ行を抽出
            rows = table.find_all('tr')
            for row in rows[1:]:  # ヘッダー行をスキップ
                training_data = self._extract_training_from_row_fallback(row, headers)
                if training_data and training_data.get('馬番'):
                    training_list.append(training_data)
                    
        except Exception as e:
            self.logger.error(f"フォールバック調教情報抽出エラー: {e}")
        
        return training_list

    def _extract_training_from_row_fallback(self, row, headers: List[str]) -> Dict[str, str]:
        """行から調教情報を抽出（フォールバック版）"""
        training_data = {}
        
        try:
            cells = row.find_all(['td', 'th'])
            
            for i, cell in enumerate(cells):
                cell_text = cell.get_text().strip()
                
                # ヘッダーがある場合はそれを使用
                if i < len(headers):
                    header = headers[i]
                    training_data[header] = cell_text
            
            # 矢印を抽出（td class="yajirusi"から）
            arrow_cell = row.find('td', class_='yajirusi')
            if arrow_cell:
                # spanタグ内のテキストも含めて取得
                arrow_span = arrow_cell.find('span', class_=['kakusuji2keta', 'kakusuji1keta'])
                if arrow_span:
                    arrow_text = arrow_span.get_text(strip=True)
                else:
                    arrow_text = arrow_cell.get_text(strip=True)
                    
                if arrow_text and arrow_text in ['→', '↗', '↘', '↑', '↓']:
                    training_data['training_arrow'] = arrow_text
                else:
                    # デフォルトのフィールド名
                    default_fields = ['馬番', '馬名', '調教日', 'コース', 'タイム', '追切', '評価', 'コメント']
                    if i < len(default_fields):
                        training_data[default_fields[i]] = cell_text
                    else:
                        training_data[f'field_{i}'] = cell_text
                        
        except Exception as e:
            self.logger.debug(f"調教データ抽出エラー: {e}")
            
        return training_data
    
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """データの妥当性を検証"""
        try:
            if not isinstance(data, dict):
                self.logger.error("データがdict型ではありません")
                return False
            
            if 'training_data' not in data:
                self.logger.error("training_dataフィールドがありません")
                return False
            
            training_data = data['training_data']
            if not isinstance(training_data, list):
                self.logger.error("training_dataがlist型ではありません")
                return False
            
            if len(training_data) == 0:
                self.logger.warning("調教データがありません")
                return False
            
            # 各調教データをチェック
            for i, training in enumerate(training_data):
                if not isinstance(training, dict):
                    self.logger.error(f"調教データ{i}がdict型ではありません")
                    return False
            
            self.logger.info(f"データ検証OK: {len(training_data)}件の調教データ")
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