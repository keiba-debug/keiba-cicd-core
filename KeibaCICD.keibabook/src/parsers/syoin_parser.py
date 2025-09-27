#!/usr/bin/env python3
"""
前走インタビューデータパーサー

競馬ブックの前走インタビューページからHTMLを解析してJSONデータを生成
"""

import re
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from bs4 import BeautifulSoup

from ..utils.logger import setup_logger


class SyoinParser:
    """前走インタビューデータパーサー（競馬ブック専用）"""
    
    def __init__(self, debug: bool = False):
        """
        初期化
        
        Args:
            debug: デバッグモード
        """
        self.debug = debug
        self.logger = setup_logger("SyoinParser", level="DEBUG" if debug else "INFO")
    
    def parse(self, html_file_path: str) -> Dict[str, Any]:
        """
        HTMLファイルから前走インタビューデータを抽出
        
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
        HTMLコンテンツから前走インタビューデータを抽出
        
        Args:
            html_content: HTMLコンテンツ
            
        Returns:
            Dict[str, Any]: 抽出されたデータ
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # レース情報を抽出
            race_info = self._extract_race_info(soup)
            
            # インタビュー情報を抽出
            interviews = self._extract_interviews(soup)
            
            result = {
                "race_info": race_info,
                "interviews": interviews,
                "interview_count": len(interviews)
            }
            
            self.logger.info(f"前走インタビューパース完了: {len(interviews)}件")
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
            
            # メタデータから情報抽出
            meta_keywords = soup.find('meta', attrs={'name': 'keywords'})
            if meta_keywords:
                race_info['keywords'] = meta_keywords.get('content', '')
                
        except Exception as e:
            self.logger.debug(f"レース情報抽出エラー: {e}")
        
        return race_info
    
    def _extract_interviews(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """インタビュー情報を抽出"""
        interviews = []

        try:
            # まず、syoinクラスのテーブルを探す（競馬ブックの標準形式）
            syoin_table = soup.find('table', class_='syoin')
            if syoin_table:
                # テーブルヘッダーからカラム構成を確認
                headers = []
                thead = syoin_table.find('thead')
                if thead:
                    header_row = thead.find('tr')
                    if header_row:
                        for th in header_row.find_all('th'):
                            headers.append(th.get_text().strip())

                # データ行を処理
                tbody = syoin_table.find('tbody')
                if tbody:
                    rows = tbody.find_all('tr')
                    for row in rows:
                        interview_data = self._parse_syoin_table_row(row, headers)
                        if interview_data:
                            interviews.append(interview_data)

            # syoinテーブルがない場合、他の形式を試す
            if not interviews:
                # インタビューコンテンツを探す
                interview_blocks = soup.find_all('div', class_=re.compile(r'(interview|comment|talk)', re.I))

                if interview_blocks:
                    for block in interview_blocks:
                        interview_data = self._parse_interview_block(block)
                        if interview_data:
                            interviews.append(interview_data)
                else:
                    # 別のパターンを試す - 通常のテーブル形式の場合
                    tables = soup.find_all('table')
                    for table in tables:
                        if 'syoin' not in str(table.get('class', [])):  # syoinテーブル以外
                            rows = table.find_all('tr')
                            for row in rows:
                                interview_data = self._parse_interview_row(row)
                                if interview_data:
                                    interviews.append(interview_data)
            
            # インタビューが見つからない場合、全文検索
            if not interviews:
                # 騎手名パターンで検索
                jockey_pattern = re.compile(r'([^　\s]+騎手|[^　\s]+ジョッキー)')
                text_blocks = soup.find_all(text=jockey_pattern)
                
                for text in text_blocks:
                    parent = text.parent
                    if parent:
                        interview_data = self._extract_interview_from_text(parent)
                        if interview_data:
                            interviews.append(interview_data)
            
        except Exception as e:
            self.logger.debug(f"インタビュー抽出エラー: {e}")
        
        return interviews
    
    def _parse_interview_block(self, block) -> Optional[Dict[str, Any]]:
        """インタビューブロックから情報を抽出"""
        try:
            interview = {}

            # 馬番・馬名を探す
            horse_info = block.find(class_=re.compile(r'(horse|uma|number)', re.I))
            if horse_info:
                text = horse_info.get_text().strip()
                # 馬番を抽出
                horse_num_match = re.search(r'(\d+)番?', text)
                if horse_num_match:
                    interview['horse_number'] = int(horse_num_match.group(1))

                # 馬名を抽出
                horse_name_match = re.search(r'([ァ-ヴー]+)', text)
                if horse_name_match:
                    interview['horse_name'] = horse_name_match.group(1)

            # 騎手名と着順を探す（「馬名（着順）騎手名」形式から抽出）
            jockey_elem = block.find(text=re.compile(r'騎手'))
            if jockey_elem:
                jockey_text = jockey_elem.strip()
                # パターン: 馬名（着順）騎手名騎手
                full_match = re.search(r'([ァ-ヴー]+)（(\d+着|[０-９]+着)）([^騎]+)騎手', jockey_text)
                if full_match:
                    interview['horse_name'] = full_match.group(1)
                    interview['finish_position'] = full_match.group(2)
                    interview['jockey'] = full_match.group(3)
                else:
                    # シンプルパターン: 騎手名のみ
                    jockey_match = re.search(r'([^　\s]+)騎手', jockey_text)
                    if jockey_match:
                        interview['jockey'] = jockey_match.group(1)

            # インタビュー内容を抽出して分割
            comment_elem = block.find(class_=re.compile(r'(comment|text|content)', re.I))
            if comment_elem:
                full_comment = comment_elem.get_text().strip()
            else:
                # ブロック全体のテキストから抽出
                full_text = block.get_text().strip()
                # 騎手名の後のテキストをコメントとして抽出
                if 'jockey' in interview:
                    parts = full_text.split(interview['jockey'] + '騎手')
                    if len(parts) > 1:
                        full_comment = parts[1].strip()
                    else:
                        full_comment = full_text
                else:
                    full_comment = full_text

            # インタビューと次走へのメモを分離
            self._split_interview_and_memo(interview, full_comment)

            # 前走情報を抽出
            prev_race = block.find(text=re.compile(r'前走|前回'))
            if prev_race:
                interview['previous_race_mention'] = prev_race.strip()

            # comment フィールドも保持（後方互換性）
            if 'interview' in interview or 'next_race_memo' in interview:
                interview['comment'] = full_comment

            return interview if interview else None

        except Exception as e:
            self.logger.debug(f"インタビューブロックパースエラー: {e}")
            return None

    def _parse_syoin_table_row(self, row, headers: List[str]) -> Optional[Dict[str, Any]]:
        """syoinテーブルの行から情報を抽出"""
        try:
            cells = row.find_all('td')
            if not cells:
                return None

            interview = {}

            # ヘッダーとセルを対応付けて処理
            for i, cell in enumerate(cells):
                if i >= len(headers):
                    break

                header = headers[i]
                cell_text = cell.get_text().strip()

                # 枠番
                if '枠' in header and '番' in header:
                    # 枠番の数値を抽出
                    waku_p = cell.find('p', class_=re.compile(r'waku\d'))
                    if waku_p:
                        waku_text = waku_p.get_text().strip()
                        if waku_text.isdigit():
                            interview['waku_ban'] = int(waku_text)

                # 馬番
                elif header == '馬番' or (header == '馬' and cells[i].get('class') == ['umaban']):
                    if cell_text.isdigit():
                        interview['horse_number'] = int(cell_text)

                # 馬名
                elif '馬' in header and '名' in header:
                    # 馬名リンクを探す
                    horse_link = cell.find('a', class_='umalink_click')
                    if horse_link:
                        interview['horse_name'] = horse_link.get_text().strip()
                    elif cell_text and len(cell_text) > 1:
                        # カタカナの馬名を抽出
                        horse_name_match = re.search(r'([ァ-ヴー]{2,})', cell_text)
                        if horse_name_match:
                            interview['horse_name'] = horse_name_match.group(1)

                # 前走インタビュー
                elif '前走' in header and 'インタビュー' in header:
                    if cell_text:
                        # 騎手名と着順を含む場合の処理
                        jockey_match = re.search(r'([ァ-ヴー]+)（(\d+着)）([^騎]+)騎手', cell_text)
                        if jockey_match:
                            if not interview.get('horse_name'):
                                interview['horse_name'] = jockey_match.group(1)
                            interview['finish_position'] = jockey_match.group(2)
                            interview['jockey'] = jockey_match.group(3)
                            # 騎手情報の後のテキストをインタビューとして抽出
                            parts = cell_text.split(jockey_match.group(0))
                            if len(parts) > 1:
                                interview['interview'] = parts[1].strip()
                        else:
                            # 騎手情報がない場合は全体をインタビューとする
                            interview['interview'] = cell_text

                # 次走へのメモ
                elif '次走' in header or 'メモ' in header:
                    if cell_text:
                        # HTMLコメントやリンクタグを除去
                        cleaned_text = re.sub(r'<!--.*?-->', '', cell_text)
                        cleaned_text = re.sub(r'<[^>]+>', '', cleaned_text)
                        interview['next_race_memo'] = cleaned_text.strip()

            # 後方互換性のため、commentフィールドも設定
            if 'interview' in interview or 'next_race_memo' in interview:
                # 両方ある場合は結合、片方しかない場合はその値を使用
                if 'interview' in interview and 'next_race_memo' in interview:
                    interview['comment'] = f"{interview.get('interview', '')} 次走へのメモ：{interview.get('next_race_memo', '')}"
                elif 'interview' in interview:
                    interview['comment'] = interview['interview']
                elif 'next_race_memo' in interview:
                    interview['comment'] = interview['next_race_memo']

            return interview if interview else None

        except Exception as e:
            self.logger.debug(f"syoinテーブル行パースエラー: {e}")
            return None

    def _split_interview_and_memo(self, interview: Dict[str, Any], text: str) -> None:
        """インタビュー内容と次走へのメモを分離"""
        if not text:
            return

        # 次走へのメモのキーワード
        memo_keywords = [
            '次走へのメモ', '次走メモ', '次走へ', '次走',
            '今後', '次回', '次戦', 'メモ'
        ]

        # キーワードで分割
        for keyword in memo_keywords:
            if keyword in text:
                parts = text.split(keyword, 1)
                if len(parts) == 2:
                    interview['interview'] = parts[0].strip()
                    # キーワードの後の「：」や「:」を除去
                    memo_text = parts[1].strip()
                    if memo_text.startswith((':', '：')):
                        memo_text = memo_text[1:].strip()
                    interview['next_race_memo'] = memo_text
                    return

        # 分割できない場合は全体をインタビューとして保存
        interview['interview'] = text
    
    def _parse_interview_row(self, row) -> Optional[Dict[str, Any]]:
        """テーブル行からインタビュー情報を抽出"""
        try:
            cells = row.find_all(['td', 'th'])
            if len(cells) < 2:
                return None
            
            interview = {}
            
            # セルから情報を抽出
            for i, cell in enumerate(cells):
                text = cell.get_text().strip()
                
                # 馬番チェック
                if re.match(r'^\d+$', text):
                    interview['horse_number'] = int(text)
                
                # 馬名チェック
                elif re.match(r'^[ァ-ヴー]+$', text):
                    interview['horse_name'] = text
                
                # 騎手名チェック
                elif '騎手' in text:
                    jockey_match = re.search(r'([^　\s]+)騎手', text)
                    if jockey_match:
                        interview['jockey'] = jockey_match.group(1)
                
                # コメント（長文の場合）
                elif len(text) > 20:
                    interview['comment'] = text
            
            return interview if 'comment' in interview else None
            
        except Exception as e:
            self.logger.debug(f"テーブル行パースエラー: {e}")
            return None
    
    def _extract_interview_from_text(self, element) -> Optional[Dict[str, Any]]:
        """テキスト要素からインタビュー情報を抽出"""
        try:
            interview = {}

            # 親要素のテキストを取得
            parent_text = element.get_text().strip()

            # 騎手名と着順を抽出（「馬名（着順）騎手名」形式）
            full_match = re.search(r'([ァ-ヴー]+)（(\d+着|[０-９]+着)）([^騎]+)(騎手|ジョッキー)', parent_text)
            if full_match:
                interview['horse_name'] = full_match.group(1)
                interview['finish_position'] = full_match.group(2)
                interview['jockey'] = full_match.group(3)
                jockey_pattern = full_match.group(0)
            else:
                # シンプルな騎手名パターン
                jockey_match = re.search(r'([^　\s]+)(騎手|ジョッキー)', parent_text)
                if jockey_match:
                    interview['jockey'] = jockey_match.group(1)
                    jockey_pattern = jockey_match.group(0)
                else:
                    jockey_pattern = None

            if jockey_pattern:
                # 騎手名の後のテキストをコメントとして抽出
                parts = parent_text.split(jockey_pattern)
                if len(parts) > 1 and len(parts[1].strip()) > 10:
                    full_comment = parts[1].strip()
                    # インタビューと次走へのメモを分離
                    self._split_interview_and_memo(interview, full_comment)
                    # 後方互換性のためcommentフィールドも保持
                    interview['comment'] = full_comment

            # 馬番・馬名を近くの要素から探す
            prev_sibling = element.find_previous_sibling()
            next_sibling = element.find_next_sibling()

            for sibling in [prev_sibling, next_sibling]:
                if sibling:
                    sibling_text = sibling.get_text().strip()

                    # 馬番を探す
                    horse_num_match = re.search(r'(\d+)番?', sibling_text)
                    if horse_num_match and 'horse_number' not in interview:
                        interview['horse_number'] = int(horse_num_match.group(1))

                    # 馬名を探す（まだ抽出されていない場合）
                    if 'horse_name' not in interview:
                        horse_name_match = re.search(r'([ァ-ヴー]{2,})', sibling_text)
                        if horse_name_match:
                            interview['horse_name'] = horse_name_match.group(1)

            return interview if ('interview' in interview or 'next_race_memo' in interview or 'comment' in interview) else None

        except Exception as e:
            self.logger.debug(f"テキスト抽出エラー: {e}")
            return None
    
    def save_json(self, data: Dict[str, Any], output_path: str) -> None:
        """
        データをJSONファイルとして保存
        
        Args:
            data: 保存するデータ
            output_path: 出力ファイルパス
        """
        try:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"JSONファイル保存完了: {output_path}")
            
        except Exception as e:
            self.logger.error(f"JSONファイル保存エラー: {e}")
            raise