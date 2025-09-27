"""
競馬ブックの完全成績ページから馬の過去レースIDを取得
"""

import requests
from bs4 import BeautifulSoup
import json
import os
from pathlib import Path
from typing import List, Dict, Optional
import logging
from datetime import datetime
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class HorsePastRacesFetcher:
    """馬の過去レース情報を取得するクラス"""

    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://p.keibabook.co.jp"
        self.data_dir = Path("Z:/KEIBA-CICD/data/horses/past_races")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # セッション設定（環境変数から取得）
        cookie_str = os.getenv('KEIBABOOK_COOKIE', '')
        if cookie_str:
            self.session.headers.update({
                'Cookie': cookie_str,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })

    def fetch_horse_race_list(self, horse_id: str) -> List[Dict]:
        """
        馬の競走成績ページからレースIDリストを取得

        Args:
            horse_id: 馬ID

        Returns:
            レース情報のリスト
        """
        # seisekiページに変更（kanzenページには個別レースリンクがないため）
        url = f"{self.base_url}/db/uma/{horse_id}/seiseki"
        logger.info(f"取得開始: {url}")

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            # HTMLの一部をデバッグ出力
            logger.debug(f"Response length: {len(response.text)}")
            if len(response.text) < 1000:
                logger.warning(f"Short response: {response.text[:500]}")

            # HTMLを一時ファイルに保存（デバッグ用）
            debug_file = self.data_dir / f"debug_{horse_id}.html"
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
            logger.debug(f"HTML saved to {debug_file}")

            soup = BeautifulSoup(response.text, 'html.parser')

            # レース情報を含むテーブルを探す
            races = []

            # 成績テーブルを探す（複数のパターンに対応）
            tables = soup.find_all('table', class_=['race-table', 'seiseki-table', 'tb01'])

            # テーブルが見つからない場合、全テーブルを検索
            if not tables:
                tables = soup.find_all('table')
                logger.debug(f"Found {len(tables)} tables without specific class")

            # 全リンクも確認（テーブル外の可能性）
            all_links = soup.find_all('a', href=True)
            logger.debug(f"Total links found: {len(all_links)}")

            # seisekiページはレース結果ページへのリンクを含む
            # /cyuou/seiseki/XXXXXXXXXXXX 形式のリンクを探す
            race_links = []
            for a in all_links:
                href = a.get('href', '')
                # レースIDのパターンにマッチするリンクを探す
                if '/cyuou/seiseki/' in href and href.split('/')[-1].isdigit():
                    race_id = href.split('/')[-1]
                    if len(race_id) == 12:  # レースIDは12桁
                        text = a.text.strip()
                        race_links.append((href, text, race_id))

            logger.debug(f"Race links with IDs found: {len(race_links)}")
            for i, (href, text, rid) in enumerate(race_links[:5]):
                logger.debug(f"Link {i+1}: {rid} - {text[:30]}")

            for table in tables:
                rows = table.find_all('tr')

                for row in rows:
                    # レースリンクを探す
                    # 完全成績ページは通常、各レースにリンクがある
                    cells = row.find_all('td')
                    race_link = None

                    # seisekiページの場合、レースリンクは特定のパターン
                    for cell in cells:
                        link = cell.find('a', href=lambda x: x and '/cyuou/seiseki/' in x)
                        if link:
                            race_link = link
                            break

                    if race_link:
                        href = race_link.get('href', '')
                        race_id = href.split('/')[-1]

                        # 12桁のレースIDのみ処理
                        if len(race_id) != 12 or not race_id.isdigit():
                            continue

                        # その他の情報を取得
                        cells = row.find_all('td')
                        race_info = {
                            'race_id': race_id,
                            'url': f"{self.base_url}{href}",
                            'date': '',
                            'race_name': race_link.text.strip() if race_link.text else '',
                            'race_class': '',  # レースクラス（未勝利、1勝クラスなど）
                            '競馬場': '',  # 競馬場名
                            '着順': '',
                            '騎手': '',
                            'タイム': '',
                            '距離': '',
                            '馬場': '',
                            '人気': '',
                            '馬体重': '',
                            '増減': '',
                            '上がり': '',
                            '通過': '',
                            '厩舎コメント': '',
                            '枠番': '',
                            '馬番': '',
                            '頭数': ''
                        }

                        # セルから情報を抽出（テーブル構造に依存）
                        if len(cells) > 0:
                            # 日付（最初のセル）
                            date_text = cells[0].text.strip()
                            # 「2021/09/05　」のような形式から日付を抽出
                            import re
                            date_match = re.match(r'(\d{4}/\d{2}/\d{2})', date_text)
                            if date_match:
                                race_info['date'] = date_match.group(1)

                            # レースクラス情報（3番目のセル付近、G1/G2/G3/未勝利など）
                            if len(cells) > 3:
                                grade_text = cells[3].text.strip()
                                # G1/G2/G3等のグレードレース
                                if 'G1' in grade_text or 'G2' in grade_text or 'G3' in grade_text:
                                    race_info['race_class'] = grade_text
                                # 障害レース
                                elif '障害' in grade_text:
                                    race_info['race_class'] = grade_text
                                # その他のクラス
                                else:
                                    race_info['race_class'] = grade_text

                            # 競馬場情報を探す（2番目のセル付近）
                            if len(cells) > 1:
                                venue_text = cells[1].text.strip()
                                # 「1中京1」のようなパターンから競馬場を抽出
                                venue_match = re.search(r'(東京|中山|阪神|京都|中京|小倉|新潟|福島|札幌|函館)', venue_text)
                                if venue_match:
                                    race_info['競馬場'] = venue_match.group(1)

                            # 着順を探す（class属性を持つtdタグ）
                            for cell in cells:
                                # data1st, data2nd, data3rd などのクラスを持つセル
                                if cell.get('class'):
                                    class_names = cell.get('class')
                                    if any('data' in cls for cls in class_names):
                                        race_info['着順'] = cell.text.strip()
                                        break

                            # クラス属性で見つからない場合は位置で推測（8列目付近）
                            if not race_info['着順'] and len(cells) > 8:
                                text = cells[8].text.strip()
                                if text.isdigit() and int(text) <= 20:
                                    race_info['着順'] = text

                            # 騎手名を探す（kisyuリンク）
                            for cell in cells:
                                jockey_link = cell.find('a', href=lambda x: x and '/kisyu/' in x)
                                if jockey_link:
                                    race_info['騎手'] = jockey_link.text.strip()
                                    break

                            # 枠番・馬番・頭数を探す（より正確なインデックスで）
                            # HTML構造: 頭数(5), 枠番(6), 馬番(7)
                            if len(cells) > 7:
                                # 頭数（5番目のセル）
                                text5 = cells[5].text.strip()
                                if text5.isdigit() and 1 <= int(text5) <= 18:
                                    race_info['頭数'] = text5
                                # 枠番（6番目のセル）
                                text6 = cells[6].text.strip()
                                if text6.isdigit() and 1 <= int(text6) <= 8:
                                    race_info['枠番'] = text6
                                # 馬番（7番目のセル）
                                text7 = cells[7].text.strip()
                                if text7.isdigit() and 1 <= int(text7) <= 18:
                                    race_info['馬番'] = text7

                            # 距離・馬場・人気・馬体重を探す
                            for i, cell in enumerate(cells):
                                text = cell.text.strip()
                                # 距離パターン（芝1800、ダ2000、障2880など）
                                if re.match(r'[芝ダ障]\d{3,4}', text):
                                    race_info['距離'] = text
                                # 馬場状態（良、稍重、重、不良） - 通常2番目のセル
                                elif i == 2 and text in ['良', '稍', '重', '不良', '稍重']:
                                    race_info['馬場'] = text
                                # タイム（1.23.4のような形式）
                                elif re.match(r'\d+\.\d+\.\d+', text):
                                    race_info['タイム'] = text
                                # 人気（9番目のセル付近）
                                elif i == 9 and text.isdigit() and 1 <= int(text) <= 18:
                                    if not race_info['人気']:  # まだ設定されていない場合のみ
                                        race_info['人気'] = text
                                # 馬体重（400-600の範囲の数字）
                                elif text.isdigit() and 400 <= int(text) <= 600:
                                    race_info['馬体重'] = text
                                # 増減（+10, -5などのパターン）
                                elif re.match(r'[+-]?\d+', text) and i > 10:
                                    if text.startswith(('+', '-')) or (text.isdigit() and int(text) < 30):
                                        race_info['増減'] = text
                                # 上がり（30-45の範囲の小数）
                                elif re.match(r'\d{2}\.\d', text):
                                    try:
                                        val = float(text)
                                        if 30 <= val <= 45:
                                            race_info['上がり'] = text
                                    except:
                                        pass

                        # 前のレースに休養コメントがあるか確認
                        prev_row = row.find_previous_sibling('tr', class_='kanzendata_kyuyou')
                        if prev_row:
                            kyuyou_td = prev_row.find('td', class_='kyuyou')
                            if kyuyou_td:
                                kyuyou_text = kyuyou_td.text.strip()
                                if kyuyou_text:
                                    race_info['厩舎コメント'] = kyuyou_text

                        races.append(race_info)
                        logger.debug(f"レース発見: {race_id} - {race_info['race_name']}")
                        logger.debug(f"  詳細: 着順={race_info['着順']}, 人気={race_info['人気']}, 馬体重={race_info['馬体重']}")
                        logger.debug(f"  追加: 競馬場={race_info.get('競馬場')}, 距離={race_info['距離']}, 馬場={race_info['馬場']}, 枠={race_info['枠番']}, 頭数={race_info['頭数']}")

            # キャッシュとして保存
            cache_file = self.data_dir / f"{horse_id}_races.json"
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'horse_id': horse_id,
                    'updated_at': datetime.now().isoformat(),
                    'races': races
                }, f, ensure_ascii=False, indent=2)

            # 通過順位の取得（別のテーブルから）
            tuka_elements = soup.find_all('ul', class_='tuka')
            for i, tuka in enumerate(tuka_elements[:len(races)]):
                if i < len(races):
                    positions = []
                    for li in tuka.find_all('li'):
                        span = li.find('span')
                        if span and span.text.strip() and span.text.strip() != '**':
                            positions.append(span.text.strip())
                    if positions:
                        races[i]['通過'] = '-'.join(positions)

            # 日付でソート（新しい順）- レースIDが大きいほど新しい
            races.sort(key=lambda x: x.get('race_id', ''), reverse=True)

            logger.info(f"取得完了: {len(races)}レース")
            return races

        except requests.RequestException as e:
            logger.error(f"HTTP エラー: {e}")

            # キャッシュがあれば返す
            cache_file = self.data_dir / f"{horse_id}_races.json"
            if cache_file.exists():
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"キャッシュから取得: {len(data['races'])}レース")
                    return data['races']

            return []
        except Exception as e:
            logger.error(f"エラー: {e}")
            return []

    def fetch_race_details(self, race_id: str) -> Optional[Dict]:
        """
        レースIDから詳細情報を取得

        Args:
            race_id: レースID

        Returns:
            レース詳細情報
        """
        # 既存のseisekiファイルを確認
        seiseki_file = Path(f"Z:/KEIBA-CICD/data/keibabook/seiseki_{race_id}.json")
        if seiseki_file.exists():
            with open(seiseki_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        # tempディレクトリも確認
        temp_file = Path(f"Z:/KEIBA-CICD/data/temp/seiseki_{race_id}.json")
        if temp_file.exists():
            with open(temp_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        # 新規取得（レート制限に注意）
        url = f"{self.base_url}/cyuou/seiseki/{race_id}"

        try:
            time.sleep(0.5)  # レート制限対策
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            # パースして必要な情報を抽出
            soup = BeautifulSoup(response.text, 'html.parser')

            # 簡易的な情報抽出（詳細は既存のseisekiパーサーを参照）
            race_data = {
                'race_id': race_id,
                'url': url,
                'fetched_at': datetime.now().isoformat()
            }

            return race_data

        except Exception as e:
            logger.error(f"レース詳細取得エラー {race_id}: {e}")
            return None

    def get_horse_past_races_with_details(self, horse_id: str, horse_name: str, limit: int = 10) -> List[Dict]:
        """
        馬の過去レース成績を詳細情報付きで取得

        Args:
            horse_id: 馬ID
            horse_name: 馬名
            limit: 取得する最大レース数

        Returns:
            過去レース成績のリスト
        """
        # レースIDリストを取得
        race_list = self.fetch_horse_race_list(horse_id)

        if not race_list:
            logger.warning(f"レースリスト取得失敗: {horse_id} {horse_name}")
            return []

        # 最新のレースから詳細を取得
        past_races = []

        for race_info in race_list[:limit]:
            race_id = race_info['race_id']

            # 詳細情報を取得
            details = self.fetch_race_details(race_id)

            if details:
                # race_infoとdetailsをマージ
                merged = {**race_info, **details}
                past_races.append(merged)
            else:
                # 詳細が取得できない場合も基本情報は保持
                past_races.append(race_info)

        return past_races


def main():
    """テスト実行"""
    # ログレベルをDEBUGに設定
    logging.getLogger().setLevel(logging.DEBUG)

    fetcher = HorsePastRacesFetcher()

    # テスト馬（フェーングロッテン）
    test_horse_id = "0887084"
    test_horse_name = "フェーングロッテン"

    print(f"テスト取得: {test_horse_name} ({test_horse_id})")

    # Cookie設定状況を確認
    cookie = os.getenv('KEIBABOOK_COOKIE', '')
    if not cookie:
        print("警告: KEIBABOOK_COOKIE環境変数が設定されていません")
        print("ローカルキャッシュまたは既存データから取得を試みます")

    # レースリスト取得
    races = fetcher.fetch_horse_race_list(test_horse_id)

    if races:
        print(f"取得成功: {len(races)}レース")
        for race in races[:5]:
            print(f"  - {race['date']} {race['race_name']} {race['着順']}着")
    else:
        print("取得失敗または0レース")


if __name__ == "__main__":
    main()