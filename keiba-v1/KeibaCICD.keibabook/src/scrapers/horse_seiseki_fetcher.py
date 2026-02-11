#!/usr/bin/env python3
"""
馬の競走成績テーブル取得モジュール
競馬ブックの成績ページからテーブルデータを取得してMarkdown形式に変換
"""

import re
import logging
from typing import List, Dict, Optional
from pathlib import Path
from bs4 import BeautifulSoup
import requests

logger = logging.getLogger(__name__)


class HorseSeisekiFetcher:
    """馬の競走成績テーブル取得クラス"""

    def __init__(self):
        """初期化"""
        self.base_url = "https://p.keibabook.co.jp/db/uma"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

    def fetch_seiseki_table(self, horse_id: str) -> Optional[str]:
        """
        競走成績テーブルを取得してMarkdown形式に変換

        Args:
            horse_id: 馬ID

        Returns:
            Markdown形式のテーブル文字列
        """
        url = f"{self.base_url}/{horse_id}/seiseki"

        try:
            # HTMLを取得
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()

            # BeautifulSoupで解析
            soup = BeautifulSoup(response.text, 'html.parser')

            # 成績テーブルを探す（複数のパターンに対応）
            table = None

            # パターン1: class="default seiseki"
            table = soup.find('table', {'class': 'default seiseki'})

            # パターン2: 競走成績テーブル（class="horse_table" など）
            if not table:
                table = soup.find('table', {'class': 'horse_table'})

            # パターン3: 通常のdefaultテーブル
            if not table:
                tables = soup.find_all('table', class_='default')
                # 競走成績らしいテーブルを探す（日付、競馬場、着順などのヘッダーを含む）
                for t in tables:
                    headers = t.find_all('th')
                    header_text = ' '.join([h.get_text().strip() for h in headers])
                    if '日付' in header_text or '競馬場' in header_text or '着順' in header_text:
                        table = t
                        break

            # パターン4: IDやdata属性で特定
            if not table:
                table = soup.find('table', {'id': re.compile(r'seiseki|race|result', re.I)})

            if not table:
                logger.warning(f"成績テーブルが見つかりません: {horse_id}")
                # デバッグ用にHTMLを保存
                import os
                debug_dir = Path("Z:/KEIBA-CICD/data2/debug")
                debug_dir.mkdir(parents=True, exist_ok=True)
                debug_file = debug_dir / f"seiseki_{horse_id}.html"
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(response.text)
                logger.info(f"デバッグ用HTML保存: {debug_file}")
                return None

            # Markdown形式に変換
            markdown_table = self._convert_table_to_markdown(table)

            return markdown_table

        except Exception as e:
            logger.error(f"成績テーブル取得エラー: {horse_id} - {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    def _convert_table_to_markdown(self, table) -> str:
        """
        HTMLテーブルをMarkdown形式に変換

        Args:
            table: BeautifulSoupのtable要素

        Returns:
            Markdown形式のテーブル文字列
        """
        lines = []

        # ヘッダー行を処理
        thead = table.find('thead')
        if thead:
            header_row = thead.find('tr')
            if header_row:
                headers = []
                for th in header_row.find_all('th'):
                    # テキストを取得してクリーンアップ
                    text = th.get_text().strip()
                    text = re.sub(r'\s+', ' ', text)  # 連続する空白を1つに
                    headers.append(text)

                # ヘッダー行を追加
                lines.append('| ' + ' | '.join(headers) + ' |')
                # セパレータ行を追加
                lines.append('|' + '|'.join([':---:' if self._is_numeric_column(i, table) else '---'
                                            for i in range(len(headers))]) + '|')

        # データ行を処理
        tbody = table.find('tbody')
        if tbody:
            for tr in tbody.find_all('tr'):
                row = []
                cells = tr.find_all(['td', 'th'])

                for cell in cells:
                    # セル内のすべてのテキストを取得（通過順などの隠れたテキストも含む）
                    # imgタグやspanタグ内のテキストも取得
                    text = ''

                    # リンクがある場合は優先
                    links = cell.find_all('a')
                    if links:
                        text = links[0].get_text().strip()
                    else:
                        # すべてのテキストノードを取得
                        # （spanタグ内の数字なども含める）
                        text_parts = []
                        for element in cell.descendants:
                            if isinstance(element, str):
                                part = element.strip()
                                if part:
                                    text_parts.append(part)

                        # テキストパーツを結合
                        if text_parts:
                            # 通過順の場合は-で結合、それ以外はスペースで結合
                            if all(p.isdigit() or p == '-' for p in text_parts):
                                text = '-'.join(text_parts)
                            else:
                                text = ' '.join(text_parts)
                        else:
                            # それでもテキストがない場合は通常のget_text()を使用
                            text = cell.get_text().strip()

                    # テキストをクリーンアップ
                    text = re.sub(r'\s+', ' ', text)
                    # Markdownのエスケープ
                    text = text.replace('|', '\\|')

                    row.append(text)

                if row:
                    lines.append('| ' + ' | '.join(row) + ' |')

        return '\n'.join(lines)

    def _is_numeric_column(self, col_index: int, table) -> bool:
        """
        指定された列が数値列かどうかを判定

        Args:
            col_index: 列インデックス
            table: BeautifulSoupのtable要素

        Returns:
            数値列の場合True
        """
        # 着順、人気、タイム、上がりなどの列を中央揃えにする
        numeric_keywords = ['着', '人気', 'タイム', '上がり', '馬体重', '単勝', '馬番']

        thead = table.find('thead')
        if thead:
            header_row = thead.find('tr')
            if header_row:
                headers = header_row.find_all('th')
                if col_index < len(headers):
                    header_text = headers[col_index].get_text().strip()
                    return any(keyword in header_text for keyword in numeric_keywords)

        return False

    def fetch_and_save(self, horse_id: str, output_dir: Path) -> Optional[Path]:
        """
        競走成績テーブルを取得して保存

        Args:
            horse_id: 馬ID
            output_dir: 出力ディレクトリ

        Returns:
            保存したファイルのパス
        """
        table_markdown = self.fetch_seiseki_table(horse_id)

        if not table_markdown:
            return None

        # ファイルに保存
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{horse_id}_seiseki_table.md"

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"# 競走成績テーブル\n\n")
            f.write(f"馬ID: {horse_id}\n\n")
            f.write(table_markdown)

        logger.info(f"成績テーブル保存: {output_file}")
        return output_file

    def extract_from_html(self, html_content: str) -> Optional[str]:
        """
        HTMLコンテンツから成績テーブルを抽出

        Args:
            html_content: HTML文字列

        Returns:
            Markdown形式のテーブル文字列
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # 成績テーブルを探す（複数パターンに対応）
            table = None

            # パターン1: class="default seiseki"
            table = soup.find('table', class_=['default', 'seiseki'])

            # パターン2: class="raceTable"
            if not table:
                table = soup.find('table', class_='raceTable')

            # パターン3: 最初のtableタグ
            if not table:
                table = soup.find('table')

            if not table:
                logger.warning("成績テーブルが見つかりません")
                return None

            return self._convert_table_to_markdown(table)

        except Exception as e:
            logger.error(f"HTML解析エラー: {e}")
            return None


# 使用例
if __name__ == "__main__":
    # ロギング設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # テスト実行
    fetcher = HorseSeisekiFetcher()

    # 馬ID指定で取得
    horse_id = "0883752"  # トウシンマカオ
    table = fetcher.fetch_seiseki_table(horse_id)

    if table:
        print(f"=== 馬ID: {horse_id} の競走成績 ===\n")
        print(table)
    else:
        print(f"馬ID: {horse_id} の成績テーブルを取得できませんでした")