"""
騎手情報スクレーパー
競馬ブックから騎手成績・リーディング情報を取得
"""

import os
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
import requests
from bs4 import BeautifulSoup

import sys
import os
# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import get_logger

# SessionManagerの簡易実装
class SessionManager:
    """セッション管理の簡易実装"""
    def get_session(self):
        session = requests.Session()
        # Cookieを環境変数から設定
        session.cookies.set('KEIBA_SESSION', os.getenv('KEIBABOOK_SESSION', ''))
        session.cookies.set('XSRF-TOKEN', os.getenv('KEIBABOOK_XSRF_TOKEN', ''))
        session.cookies.set('TK', os.getenv('KEIBABOOK_TK', ''))
        return session


class JockeyScraper:
    """騎手情報スクレーパー"""

    def __init__(self):
        """初期化"""
        self.logger = get_logger(__name__)
        self.session_manager = SessionManager()
        self.session = self.session_manager.get_session()

        # データ保存先
        self.data_root = Path(os.getenv('KEIBA_DATA_ROOT_DIR', 'Z:/KEIBA-CICD/data'))
        self.jockeys_dir = self.data_root / 'jockeys'
        self.profiles_dir = self.jockeys_dir / 'profiles'
        self.stats_dir = self.jockeys_dir / 'stats'
        self.leading_dir = self.jockeys_dir / 'leading'

        # ディレクトリ作成
        for dir_path in [self.profiles_dir, self.stats_dir, self.leading_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def scrape_leading_jockeys(self, year: int = None, month: int = None) -> Dict[str, Any]:
        """
        リーディング騎手情報を取得

        Args:
            year: 年（省略時は現在年）
            month: 月（省略時は現在月）

        Returns:
            リーディング情報
        """
        if not year:
            year = datetime.now().year
        if not month:
            month = datetime.now().month

        url = "https://p.keibabook.co.jp/db/leading/jockey"

        try:
            self.logger.info(f"リーディング騎手情報取得: {year}年{month}月")

            # ページ取得
            response = self.session.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # リーディング情報を解析
            leading_data = self._parse_leading_page(soup, year, month)

            # 保存
            output_dir = self.leading_dir / str(year)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_file = output_dir / f"{year}{month:02d}.json"

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(leading_data, f, ensure_ascii=False, indent=2)

            self.logger.info(f"リーディング情報保存: {output_file}")
            return leading_data

        except Exception as e:
            self.logger.error(f"リーディング情報取得エラー: {e}")
            return {}

    def scrape_jockey_profile(self, jockey_id: str, jockey_name: str = None) -> Dict[str, Any]:
        """
        騎手詳細情報を取得

        Args:
            jockey_id: 騎手ID
            jockey_name: 騎手名（省略時はページから取得）

        Returns:
            騎手プロファイル情報
        """
        url = f"https://p.keibabook.co.jp/db/jockey/{jockey_id}"

        try:
            self.logger.info(f"騎手情報取得: ID={jockey_id}")

            # ページ取得
            response = self.session.get(url)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # 騎手情報を解析
            profile_data = self._parse_jockey_page(soup, jockey_id)

            if not jockey_name:
                jockey_name = profile_data.get('name', jockey_id)

            # プロファイル生成
            self._generate_jockey_profile(jockey_id, jockey_name, profile_data)

            return profile_data

        except Exception as e:
            self.logger.error(f"騎手情報取得エラー: ID={jockey_id}, {e}")
            return {}

    def _parse_leading_page(self, soup: BeautifulSoup, year: int, month: int) -> Dict[str, Any]:
        """リーディングページを解析"""
        leading_data = {
            'year': year,
            'month': month,
            'updated_at': datetime.now().isoformat(),
            'rankings': []
        }

        # テーブルを探す（実際のHTML構造に合わせて調整が必要）
        table = soup.find('table', class_='leading-table')
        if not table:
            return leading_data

        rows = table.find_all('tr')[1:]  # ヘッダー行をスキップ
        for row in rows:
            cells = row.find_all('td')
            if len(cells) >= 7:
                ranking = {
                    'rank': cells[0].text.strip(),
                    'jockey_id': self._extract_jockey_id(cells[1]),
                    'jockey_name': cells[1].text.strip(),
                    'wins': int(cells[2].text.strip()),
                    'seconds': int(cells[3].text.strip()),
                    'thirds': int(cells[4].text.strip()),
                    'rides': int(cells[5].text.strip()),
                    'win_rate': float(cells[6].text.strip().replace('%', '')),
                    'prize_money': cells[7].text.strip() if len(cells) > 7 else ''
                }
                leading_data['rankings'].append(ranking)

        return leading_data

    def _parse_jockey_page(self, soup: BeautifulSoup, jockey_id: str) -> Dict[str, Any]:
        """騎手ページを解析"""
        profile_data = {
            'jockey_id': jockey_id,
            'name': '',
            'affiliation': '',  # 所属（美浦/栗東）
            'license_year': '',
            'stats': {},
            'recent_rides': [],
            'best_tracks': [],
            'best_distances': []
        }

        # 騎手名取得（実際のHTML構造に合わせて調整が必要）
        name_elem = soup.find('h1', class_='jockey-name')
        if name_elem:
            profile_data['name'] = name_elem.text.strip()

        # 成績テーブル解析
        stats_table = soup.find('table', class_='stats-table')
        if stats_table:
            profile_data['stats'] = self._parse_stats_table(stats_table)

        return profile_data

    def _parse_stats_table(self, table) -> Dict[str, Any]:
        """成績テーブルを解析"""
        stats = {
            'total': {'wins': 0, 'seconds': 0, 'thirds': 0, 'rides': 0},
            'this_year': {'wins': 0, 'seconds': 0, 'thirds': 0, 'rides': 0},
            'turf': {'wins': 0, 'seconds': 0, 'thirds': 0, 'rides': 0},
            'dirt': {'wins': 0, 'seconds': 0, 'thirds': 0, 'rides': 0}
        }

        # 実際のテーブル構造に合わせて実装
        return stats

    def _extract_jockey_id(self, cell) -> str:
        """セルから騎手IDを抽出"""
        link = cell.find('a')
        if link and 'href' in link.attrs:
            # URLから騎手IDを抽出
            href = link['href']
            if '/jockey/' in href:
                return href.split('/jockey/')[-1].split('/')[0]
        return ''

    def _generate_jockey_profile(self, jockey_id: str, jockey_name: str, profile_data: Dict[str, Any]):
        """騎手プロファイルMDファイルを生成"""

        # 出力ファイルパス
        output_file = self.profiles_dir / f"{jockey_id}_{jockey_name}.md"

        # 既存のユーザーメモを保持
        user_memo = ""
        if output_file.exists():
            with open(output_file, 'r', encoding='utf-8') as f:
                content = f.read()
                if "## ユーザーメモ" in content:
                    user_memo = content.split("## ユーザーメモ")[-1].strip()

        # プロファイル生成
        lines = [
            f"# 騎手プロファイル: {jockey_name}",
            "",
            "## 基本情報",
            f"- **騎手ID**: {jockey_id}",
            f"- **所属**: {profile_data.get('affiliation', '-')}",
            f"- **免許取得**: {profile_data.get('license_year', '-')}",
            "",
            "## 成績統計",
            "### 通算成績",
            "| 項目 | 1着 | 2着 | 3着 | 着外 | 勝率 | 連対率 | 複勝率 |",
            "|:----:|:---:|:---:|:---:|:----:|:----:|:------:|:------:|"
        ]

        # 成績データ追加
        stats = profile_data.get('stats', {})
        if stats.get('total'):
            total = stats['total']
            wins = total.get('wins', 0)
            seconds = total.get('seconds', 0)
            thirds = total.get('thirds', 0)
            rides = total.get('rides', 1)  # ゼロ除算防止
            outs = rides - wins - seconds - thirds

            win_rate = (wins / rides * 100) if rides > 0 else 0
            place_rate = ((wins + seconds) / rides * 100) if rides > 0 else 0
            show_rate = ((wins + seconds + thirds) / rides * 100) if rides > 0 else 0

            lines.append(f"| 全成績 | {wins} | {seconds} | {thirds} | {outs} | {win_rate:.1f}% | {place_rate:.1f}% | {show_rate:.1f}% |")

        lines.extend([
            "",
            "### 今年の成績",
            "| 月 | 騎乗数 | 勝利 | 勝率 | 連対率 | 賞金(万円) |",
            "|:--:|:------:|:----:|:----:|:------:|:----------:|",
            "| - | - | - | -% | -% | - |",
            "",
            "### 得意条件",
            "- **得意距離**: -",
            "- **得意競馬場**: -",
            "- **得意馬場**: -",
            "",
            "### 騎乗馬との相性",
            "| 馬名 | 騎乗回数 | 成績 | 勝率 |",
            "|:----:|:--------:|:----:|:----:|",
            "| - | - | - | -% |",
            "",
            "## 特記事項",
            "### 騎乗傾向",
            "- （データから分析される傾向を記載）",
            "",
            "### 乗り替わり成績",
            "- 他騎手→当騎手: -",
            "- 当騎手→他騎手: -",
            "",
            "## 競馬ブックリンク",
            f"- [騎手情報詳細](https://p.keibabook.co.jp/db/jockey/{jockey_id})",
            "",
            "---",
            "## ユーザーメモ"
        ])

        if user_memo:
            lines.append(user_memo)
        else:
            lines.append("*予想に役立つ情報を記入*")

        lines.extend([
            "",
            "---",
            f"*最終更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        ])

        # ファイル保存
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

        self.logger.info(f"騎手プロファイル生成: {output_file}")

    def update_jockey_stats_from_race(self, race_data: Dict[str, Any]):
        """
        レース結果から騎手成績を更新

        Args:
            race_data: レースデータ（統合JSON）
        """
        # レース情報取得
        race_id = race_data.get('meta', {}).get('race_id', '')
        race_date = race_data.get('race_info', {}).get('date', '')

        # 各出走馬の騎手情報を処理
        for entry in race_data.get('entries', []):
            jockey_name = entry.get('entry_data', {}).get('jockey', '')
            if not jockey_name:
                continue

            # 騎手成績を更新
            result = entry.get('result', {})
            if result:
                # 騎手別の成績データを蓄積
                self._update_jockey_monthly_stats(jockey_name, race_date, result)

    def _update_jockey_monthly_stats(self, jockey_name: str, race_date: str, result: Dict[str, Any]):
        """月次騎手成績を更新"""
        # 実装は省略（データベース的な処理が必要）
        pass


if __name__ == "__main__":
    # テスト実行
    scraper = JockeyScraper()

    # リーディング情報取得
    scraper.scrape_leading_jockeys(2025, 9)

    # 特定騎手の情報取得（例）
    # scraper.scrape_jockey_profile("00666", "ルメール")