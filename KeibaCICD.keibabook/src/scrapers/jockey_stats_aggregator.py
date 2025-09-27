"""
騎手成績集計システム
既存のレース結果データから騎手成績を集計・分析
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
from collections import defaultdict


class JockeyStatsAggregator:
    """騎手成績集計クラス"""

    def __init__(self):
        """初期化"""
        self.data_root = Path(os.getenv('KEIBA_DATA_ROOT_DIR', 'Z:/KEIBA-CICD/data'))
        self.keibabook_dir = self.data_root / 'keibabook'
        self.temp_dir = self.data_root / 'temp'  # tempディレクトリも対象に
        self.jockeys_dir = self.data_root / 'jockeys'
        self.stats_dir = self.jockeys_dir / 'stats'
        self.profiles_dir = self.jockeys_dir / 'profiles'

        # ディレクトリ作成
        self.stats_dir.mkdir(parents=True, exist_ok=True)
        self.profiles_dir.mkdir(parents=True, exist_ok=True)

        # 集計データ
        self.jockey_stats = defaultdict(lambda: {
            'total': {'rides': 0, 'wins': 0, 'seconds': 0, 'thirds': 0},
            'by_track': defaultdict(lambda: {'rides': 0, 'wins': 0}),  # 競馬場別
            'by_distance': defaultdict(lambda: {'rides': 0, 'wins': 0}),  # 距離別
            'by_surface': defaultdict(lambda: {'rides': 0, 'wins': 0}),  # 馬場別
            'by_condition': defaultdict(lambda: {'rides': 0, 'wins': 0}),  # 馬場状態別
            'monthly': defaultdict(lambda: {'rides': 0, 'wins': 0}),  # 月別
            'comments': [],  # 騎手コメント
            'win_races': []  # 勝利レース詳細
        })

    def aggregate_from_seiseki(self, start_date: str = None, end_date: str = None):
        """
        成績データから騎手成績を集計

        Args:
            start_date: 開始日 (YYYYMMDD)
            end_date: 終了日 (YYYYMMDD)
        """
        print(f"[INFO] 騎手成績集計開始: {start_date} - {end_date}")

        # seiseki_*.jsonファイルを読み込み（keibabookとtempの両方から）
        seiseki_files = list(self.keibabook_dir.glob("seiseki_*.json"))
        seiseki_files.extend(list(self.temp_dir.glob("seiseki_*.json")))

        if start_date and end_date:
            # 日付範囲でフィルタリング（race_idの形式: YYYYRRRRRRR）
            start_year = start_date.replace('-', '')[:4]
            end_year = end_date.replace('-', '')[:4]

            filtered_files = []
            for f in seiseki_files:
                # ファイル名からrace_idを抽出（seiseki_YYYYRRRRRRR.json）
                try:
                    race_id = f.stem.split('_')[1]
                    year = race_id[:4]
                    # 年でフィルタリング（詳細な日付は後でrace_nameから取得）
                    if start_year <= year <= end_year:
                        filtered_files.append(f)
                except:
                    continue

            seiseki_files = filtered_files

        print(f"[INFO] 処理対象ファイル数: {len(seiseki_files)}")

        processed_count = 0
        for seiseki_file in seiseki_files:
            try:
                with open(seiseki_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                self._process_race_data(data)
                processed_count += 1

                if processed_count % 100 == 0:
                    print(f"[INFO] {processed_count}/{len(seiseki_files)} ファイル処理済み")

            except Exception as e:
                print(f"[ERROR] ファイル読み込みエラー: {seiseki_file}, {e}")
                continue

        print(f"[INFO] 集計完了: {processed_count}ファイル処理")
        return self.jockey_stats

    def _process_race_data(self, race_data: Dict[str, Any]):
        """レースデータから騎手情報を抽出"""
        race_info = race_data.get('race_info', {})
        race_date = race_info.get('date', '')
        venue = race_info.get('venue', '')
        distance = race_info.get('distance', 0)
        track = race_info.get('track', '')
        condition = race_info.get('track_condition', '')
        race_name = race_info.get('race_name', '')

        # race_idから日付を推定（YYYYRRRRRRR形式）
        race_id = race_info.get('race_id', '')
        if race_id and len(race_id) >= 4:
            year = race_id[:4]
            # 月日は推定できないので、race_nameから抽出
            if '月' in race_name and '日' in race_name:
                import re
                date_match = re.search(r'(\d+)月(\d+)日', race_name)
                if date_match:
                    month_num = date_match.group(1).zfill(2)
                    day_num = date_match.group(2).zfill(2)
                    race_date = f"{year}-{month_num}-{day_num}"

        # 月を抽出
        month = race_date[:7] if race_date else ''

        # 'results'配列から騎手情報を抽出（tempディレクトリのJSON形式に対応）
        for result in race_data.get('results', []):
            # 騎手名を取得（騎手_2 または 騎手 フィールドから）
            jockey = result.get('騎手_2', '') or result.get('騎手', '')
            if not jockey:
                continue

            # 着順を取得
            position = result.get('着順', '')
            if not position:
                continue

            try:
                position = int(position)
            except:
                continue

            # 基本統計
            stats = self.jockey_stats[jockey]
            stats['total']['rides'] += 1

            if position == 1:
                stats['total']['wins'] += 1
                # 勝利レース詳細を保存
                horse_name = result.get('馬名', '')
                stats['win_races'].append({
                    'date': race_date,
                    'venue': venue,
                    'race_name': race_name,
                    'horse': horse_name,
                    'distance': distance,
                    'track': track,
                    'condition': condition,
                    'time': result.get('タイム', ''),
                    'margin': result.get('着差', ''),
                    'comment': result.get('interview', '') or result.get('memo', '')
                })
            elif position == 2:
                stats['total']['seconds'] += 1
            elif position == 3:
                stats['total']['thirds'] += 1

            # 条件別統計
            if venue:
                stats['by_track'][venue]['rides'] += 1
                if position == 1:
                    stats['by_track'][venue]['wins'] += 1

            if distance:
                # 距離カテゴリ分類
                if distance <= 1400:
                    dist_cat = '短距離'
                elif distance <= 1800:
                    dist_cat = 'マイル'
                elif distance <= 2200:
                    dist_cat = '中距離'
                else:
                    dist_cat = '長距離'

                stats['by_distance'][dist_cat]['rides'] += 1
                if position == 1:
                    stats['by_distance'][dist_cat]['wins'] += 1

            if track:
                stats['by_surface'][track]['rides'] += 1
                if position == 1:
                    stats['by_surface'][track]['wins'] += 1

            if condition:
                stats['by_condition'][condition]['rides'] += 1
                if position == 1:
                    stats['by_condition'][condition]['wins'] += 1

            if month:
                stats['monthly'][month]['rides'] += 1
                if position == 1:
                    stats['monthly'][month]['wins'] += 1

            # 騎手コメント（インタビュー）を保存
            interview = result.get('raw_data', {}).get('interview', '')
            if interview and position <= 3:
                stats['comments'].append({
                    'date': race_date,
                    'position': position,
                    'race': race_name,
                    'horse': entry.get('horse_name', ''),
                    'comment': interview
                })

    def calculate_win_rates(self):
        """勝率・連対率・複勝率を計算"""
        for jockey, stats in self.jockey_stats.items():
            total = stats['total']
            rides = total['rides']

            if rides > 0:
                total['win_rate'] = round(total['wins'] / rides * 100, 1)
                total['place_rate'] = round((total['wins'] + total['seconds']) / rides * 100, 1)
                total['show_rate'] = round((total['wins'] + total['seconds'] + total['thirds']) / rides * 100, 1)

                # 条件別勝率
                for category in ['by_track', 'by_distance', 'by_surface', 'by_condition', 'monthly']:
                    for key, data in stats[category].items():
                        if data['rides'] > 0:
                            data['win_rate'] = round(data['wins'] / data['rides'] * 100, 1)

    def save_aggregated_stats(self, output_file: str = None):
        """集計結果を保存"""
        if not output_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = self.stats_dir / f'jockey_stats_{timestamp}.json'

        # 勝率計算
        self.calculate_win_rates()

        # defaultdictを通常のdictに変換
        save_data = {}
        for jockey, stats in self.jockey_stats.items():
            save_data[jockey] = {
                'total': dict(stats['total']),
                'by_track': dict(stats['by_track']),
                'by_distance': dict(stats['by_distance']),
                'by_surface': dict(stats['by_surface']),
                'by_condition': dict(stats['by_condition']),
                'monthly': dict(stats['monthly']),
                'comments': stats['comments'][-10:],  # 最新10件
                'win_races': stats['win_races'][-10:]  # 最新10勝
            }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)

        print(f"[INFO] 騎手成績保存: {output_file}")
        print(f"[INFO] 集計騎手数: {len(save_data)}")

        # 上位騎手を表示
        self.show_top_jockeys()

        return output_file

    def show_top_jockeys(self, top_n: int = 10):
        """上位騎手を表示"""
        # 勝利数でソート
        sorted_jockeys = sorted(
            self.jockey_stats.items(),
            key=lambda x: x[1]['total']['wins'],
            reverse=True
        )

        print("\n=== 騎手成績ランキング (勝利数) ===")
        print("-" * 70)
        print(f"{'順位':<4} {'騎手名':<15} {'騎乗':<6} {'1着':<5} {'2着':<5} {'3着':<5} {'勝率':<7} {'連対率':<7}")
        print("-" * 70)

        for rank, (jockey, stats) in enumerate(sorted_jockeys[:top_n], 1):
            total = stats['total']
            rides = total['rides']
            if rides == 0:
                continue

            win_rate = total.get('win_rate', 0)
            place_rate = total.get('place_rate', 0)

            print(f"{rank:<4} {jockey:<15} {rides:<6} {total['wins']:<5} "
                  f"{total['seconds']:<5} {total['thirds']:<5} "
                  f"{win_rate:<6.1f}% {place_rate:<6.1f}%")

        print("\n=== 得意条件分析 (上位3騎手) ===")
        for rank, (jockey, stats) in enumerate(sorted_jockeys[:3], 1):
            print(f"\n{rank}. {jockey}")

            # 得意競馬場
            if stats['by_track']:
                best_track = max(
                    stats['by_track'].items(),
                    key=lambda x: x[1].get('win_rate', 0)
                )
                if best_track[1]['rides'] >= 10:  # 10騎乗以上
                    print(f"  得意競馬場: {best_track[0]} (勝率{best_track[1].get('win_rate', 0):.1f}%)")

            # 得意距離
            if stats['by_distance']:
                best_dist = max(
                    stats['by_distance'].items(),
                    key=lambda x: x[1].get('win_rate', 0)
                )
                if best_dist[1]['rides'] >= 10:
                    print(f"  得意距離: {best_dist[0]} (勝率{best_dist[1].get('win_rate', 0):.1f}%)")

            # 最新の勝利コメント
            if stats['comments']:
                latest_comment = stats['comments'][-1]
                print(f"  最新コメント({latest_comment['position']}着): "
                      f"\"{latest_comment['comment'][:50]}...\"")

    def generate_jockey_profiles(self):
        """騎手プロファイルMDファイルを生成"""
        print("\n[INFO] 騎手プロファイル生成開始")

        for jockey_name, stats in self.jockey_stats.items():
            if stats['total']['rides'] == 0:
                continue

            # ファイル名生成（騎手名をファイル名に使用）
            safe_name = jockey_name.replace(' ', '_').replace('/', '_')
            profile_file = self.profiles_dir / f"{safe_name}.md"

            # 既存ファイルからユーザー追記エリアを取得
            user_notes = ""
            if profile_file.exists():
                with open(profile_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if "## ユーザーメモ" in content:
                        user_notes = content.split("## ユーザーメモ")[-1].strip()

            # プロファイル作成
            self._create_jockey_profile(jockey_name, stats, profile_file, user_notes)

        print(f"[INFO] 騎手プロファイル生成完了: {self.profiles_dir}")

    def _create_jockey_profile(self, jockey_name: str, stats: Dict, profile_file: Path, user_notes: str):
        """個別騎手プロファイルを作成"""
        total = stats['total']

        lines = [
            f"# 騎手プロファイル: {jockey_name}",
            "",
            "## 基本情報",
            f"- **騎手名**: {jockey_name}",
            f"- **更新日**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## 成績統計",
            "### 通算成績",
            "| 項目 | 騎乗数 | 1着 | 2着 | 3着 | 勝率 | 連対率 | 複勝率 |",
            "|:----:|:------:|:---:|:---:|:---:|:----:|:------:|:------:|",
            f"| 全成績 | {total['rides']} | {total['wins']} | {total['seconds']} | "
            f"{total['thirds']} | {total.get('win_rate', 0):.1f}% | "
            f"{total.get('place_rate', 0):.1f}% | {total.get('show_rate', 0):.1f}% |",
            ""
        ]

        # 月別成績（最新3か月）
        if stats['monthly']:
            lines.extend([
                "### 月別成績（最新3か月）",
                "| 月 | 騎乗数 | 勝利 | 勝率 |",
                "|:--:|:------:|:----:|:----:|"
            ])

            sorted_months = sorted(stats['monthly'].items(), reverse=True)[:3]
            for month, data in sorted_months:
                lines.append(f"| {month} | {data['rides']} | {data['wins']} | "
                           f"{data.get('win_rate', 0):.1f}% |")
            lines.append("")

        # 得意条件
        lines.extend(["### 得意条件"])

        # 得意競馬場
        if stats['by_track']:
            best_track = max(
                [(k, v) for k, v in stats['by_track'].items() if v['rides'] >= 5],
                key=lambda x: x[1].get('win_rate', 0),
                default=(None, None)
            )
            if best_track[0]:
                lines.append(f"- **得意競馬場**: {best_track[0]} "
                           f"(勝率{best_track[1].get('win_rate', 0):.1f}%)")

        # 得意距離
        if stats['by_distance']:
            best_dist = max(
                [(k, v) for k, v in stats['by_distance'].items() if v['rides'] >= 5],
                key=lambda x: x[1].get('win_rate', 0),
                default=(None, None)
            )
            if best_dist[0]:
                lines.append(f"- **得意距離**: {best_dist[0]} "
                           f"(勝率{best_dist[1].get('win_rate', 0):.1f}%)")

        # 得意馬場
        if stats['by_surface']:
            best_surface = max(
                [(k, v) for k, v in stats['by_surface'].items() if v['rides'] >= 5],
                key=lambda x: x[1].get('win_rate', 0),
                default=(None, None)
            )
            if best_surface[0]:
                lines.append(f"- **得意馬場**: {best_surface[0]} "
                           f"(勝率{best_surface[1].get('win_rate', 0):.1f}%)")

        lines.append("")

        # 最近の勝利レース
        if stats['win_races']:
            lines.extend([
                "### 最近の勝利レース（最新5勝）",
                "| 日付 | 競馬場 | レース | 騎乗馬 | 距離 |",
                "|:----:|:------:|:------|:-------|:----:|"
            ])

            for race in stats['win_races'][-5:]:
                lines.append(f"| {race['date'][:10]} | {race['venue']} | "
                           f"{race['race_name'][:15]} | {race['horse'][:10]} | "
                           f"{race['distance']}m |")
            lines.append("")

        # 最新コメント
        if stats['comments']:
            lines.extend(["### 騎手コメント（最新3件）", ""])
            for comment in stats['comments'][-3:]:
                lines.append(f"**{comment['date'][:10]} {comment['race'][:15]} "
                           f"({comment['position']}着)**")
                lines.append(f"> {comment['comment'][:100]}...")
                lines.append("")

        # ユーザーメモエリア
        lines.extend([
            "---",
            "## ユーザーメモ"
        ])

        if user_notes:
            lines.append(user_notes)
        else:
            lines.extend([
                "*ここに騎手の特徴や注目ポイントを記入*",
                "",
                "- 乗り替わり時の注意点:",
                "- 得意な馬のタイプ:",
                "- その他メモ:"
            ])

        lines.extend([
            "",
            "---",
            f"*自動更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        ])

        # ファイル保存
        with open(profile_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))


if __name__ == "__main__":
    # テスト実行
    aggregator = JockeyStatsAggregator()

    # 2025年のデータを集計（tempディレクトリから）
    print("騎手成績集計を開始します...")
    aggregator.aggregate_from_seiseki("20250201", "20250930")

    # 結果を保存
    output_file = aggregator.save_aggregated_stats()

    # 騎手プロファイルMDを生成
    aggregator.generate_jockey_profiles()