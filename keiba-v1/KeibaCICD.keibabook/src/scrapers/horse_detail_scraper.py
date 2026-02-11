#!/usr/bin/env python3
"""
馬詳細情報スクレイパー
競馬ブックから馬の過去成績詳細を取得する
"""

import re
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class HorseDetailScraper:
    """馬詳細情報スクレイパークラス"""

    def __init__(self):
        """初期化"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # 既存データのキャッシュディレクトリ
        self.cache_dir = Path("Z:/KEIBA-CICD/data/horses/cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch_horse_history(self, horse_id: str) -> Optional[Dict]:
        """
        馬の過去成績を取得

        Args:
            horse_id: 馬ID

        Returns:
            過去成績データ
        """
        # キャッシュチェック
        cache_file = self.cache_dir / f"{horse_id}_history.json"
        if cache_file.exists():
            # 24時間以内のキャッシュは使用
            if (datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)).days < 1:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    logger.info(f"キャッシュから読み込み: {horse_id}")
                    return json.load(f)

        # 競馬ブックから取得
        url = f"https://p.keibabook.co.jp/db/uma/{horse_id}/kanzen"

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            # 過去成績テーブルを解析
            history_data = self._parse_history_table(soup, horse_id)

            # キャッシュに保存
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)

            logger.info(f"過去成績取得成功: {horse_id}")
            return history_data

        except Exception as e:
            logger.error(f"過去成績取得エラー {horse_id}: {e}")
            return None

    def _parse_history_table(self, soup: BeautifulSoup, horse_id: str) -> Dict:
        """
        過去成績テーブルを解析

        Args:
            soup: BeautifulSoup オブジェクト
            horse_id: 馬ID

        Returns:
            解析済みデータ
        """
        history = {
            'horse_id': horse_id,
            'updated_at': datetime.now().isoformat(),
            'races': []
        }

        # 成績テーブルを探す（実際のHTML構造に合わせて調整が必要）
        tables = soup.find_all('table', class_='race_table')

        for table in tables:
            rows = table.find_all('tr')[1:]  # ヘッダーを除く

            for row in rows:
                cells = row.find_all('td')
                if len(cells) < 10:
                    continue

                race_data = {
                    '日付': cells[0].get_text(strip=True),
                    '競馬場': cells[1].get_text(strip=True),
                    'レース名': cells[2].get_text(strip=True),
                    '着順': cells[3].get_text(strip=True),
                    '騎手': cells[4].get_text(strip=True),
                    '距離': cells[5].get_text(strip=True),
                    '馬場': cells[6].get_text(strip=True),
                    'タイム': cells[7].get_text(strip=True),
                    '上がり': cells[8].get_text(strip=True),
                    'コメント': cells[9].get_text(strip=True) if len(cells) > 9 else ''
                }

                history['races'].append(race_data)

        return history

    def format_history_table(self, history_data: Dict) -> str:
        """
        過去成績をMarkdownテーブル形式にフォーマット

        Args:
            history_data: 過去成績データ

        Returns:
            Markdownテーブル文字列
        """
        if not history_data or 'races' not in history_data:
            return "過去成績データなし"

        # テーブルヘッダー
        lines = [
            "## 過去成績一覧",
            "",
            "| 日付 | 競馬場 | レース | 着順 | 騎手 | 距離 | 馬場 | タイム | 上がり | コメント |",
            "|:----:|:------:|:------|:----:|:----:|:----:|:----:|:------:|:------:|:---------|"
        ]

        # 最新10レースまで表示
        for race in history_data['races'][:10]:
            line = f"| {race.get('日付', '-')} | {race.get('競馬場', '-')} | {race.get('レース名', '-')} | " \
                   f"**{race.get('着順', '-')}** | {race.get('騎手', '-')} | {race.get('距離', '-')} | " \
                   f"{race.get('馬場', '-')} | {race.get('タイム', '-')} | {race.get('上がり', '-')} | " \
                   f"{race.get('コメント', '-')} |"
            lines.append(line)

        return '\n'.join(lines)

    def get_existing_race_data(self, race_id: str) -> Optional[Dict]:
        """
        既存のレースデータを取得

        Args:
            race_id: レースID

        Returns:
            レースデータ（存在する場合）
        """
        # 既存のJSONファイルから取得
        json_files = [
            f"Z:/KEIBA-CICD/data/temp/seiseki_{race_id}.json",
            f"Z:/KEIBA-CICD/data/temp/shutsuba_{race_id}.json",
            f"Z:/KEIBA-CICD/data/temp/cyokyo_{race_id}.json",
            f"Z:/KEIBA-CICD/data/temp/danwa_{race_id}.json",
            f"Z:/KEIBA-CICD/data/temp/paddok_{race_id}.json"
        ]

        combined_data = {}

        for json_file in json_files:
            file_path = Path(json_file)
            if file_path.exists():
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        data_type = file_path.stem.split('_')[0]
                        combined_data[data_type] = data
                        logger.debug(f"既存データ読み込み: {json_file}")
                except Exception as e:
                    logger.error(f"JSONファイル読み込みエラー {json_file}: {e}")

        return combined_data if combined_data else None

    def create_enhanced_profile(self, horse_id: str, horse_name: str,
                               existing_data: Dict = None) -> Dict:
        """
        拡張版馬プロファイルを作成

        Args:
            horse_id: 馬ID
            horse_name: 馬名
            existing_data: 既存データ

        Returns:
            拡張プロファイルデータ
        """
        profile = {
            'horse_id': horse_id,
            'horse_name': horse_name,
            'updated_at': datetime.now().isoformat(),
            'basic_info': existing_data or {},
            'history': None,
            'analysis': {
                'distance_preference': {},
                'track_preference': {},
                'condition_preference': {},
                'recent_form': '',
                'key_points': []
            }
        }

        # 過去成績を取得
        history = self.fetch_horse_history(horse_id)
        if history:
            profile['history'] = history

            # 簡易分析
            profile['analysis'] = self._analyze_history(history)

        return profile

    def _analyze_history(self, history: Dict) -> Dict:
        """
        過去成績から簡易分析

        Args:
            history: 過去成績データ

        Returns:
            分析結果
        """
        analysis = {
            'distance_preference': {},
            'track_preference': {},
            'condition_preference': {},
            'recent_form': '',
            'key_points': []
        }

        if not history or 'races' not in history:
            return analysis

        races = history['races']

        # 最近5走の着順から調子を判定
        recent_positions = []
        for race in races[:5]:
            pos = race.get('着順', '')
            if pos and pos.isdigit():
                recent_positions.append(int(pos))

        if recent_positions:
            avg_position = sum(recent_positions) / len(recent_positions)
            if avg_position <= 3:
                analysis['recent_form'] = '好調'
            elif avg_position <= 5:
                analysis['recent_form'] = '平均的'
            else:
                analysis['recent_form'] = '不調'

        # 距離適性の集計
        distance_wins = {}
        for race in races:
            distance = race.get('距離', '')
            position = race.get('着順', '')

            if distance and position and position.isdigit():
                if distance not in distance_wins:
                    distance_wins[distance] = {'wins': 0, 'runs': 0}

                distance_wins[distance]['runs'] += 1
                if int(position) <= 3:
                    distance_wins[distance]['wins'] += 1

        analysis['distance_preference'] = distance_wins

        # キーポイントの抽出
        if recent_positions and min(recent_positions) == 1:
            analysis['key_points'].append('最近勝利あり')

        if len(recent_positions) >= 3 and all(p <= 3 for p in recent_positions[:3]):
            analysis['key_points'].append('安定した上位入着')

        return analysis


# 使用例
if __name__ == "__main__":
    scraper = HorseDetailScraper()

    # テスト: カムニャックの詳細情報を取得
    test_horse_id = "0936453"
    test_horse_name = "カムニャック"

    profile = scraper.create_enhanced_profile(test_horse_id, test_horse_name)

    if profile['history']:
        table = scraper.format_history_table(profile['history'])
        print(table)
        print("\n分析結果:")
        print(json.dumps(profile['analysis'], ensure_ascii=False, indent=2))
    else:
        print("過去成績を取得できませんでした")