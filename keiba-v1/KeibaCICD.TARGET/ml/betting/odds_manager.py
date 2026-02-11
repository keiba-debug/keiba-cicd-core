# -*- coding: utf-8 -*-
"""
オッズ管理モジュール

JRA-VANから取得したオッズデータを管理し、期待値計算に提供します。
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import pandas as pd
import re

# プロジェクトルートをパスに追加
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from common.config import get_jv_data_root


class OddsManager:
    """オッズデータ管理クラス"""

    def __init__(self, jv_data_root: Path = None):
        """
        初期化

        Args:
            jv_data_root: JV-Dataルートディレクトリ
        """
        self.jv_data_root = jv_data_root or get_jv_data_root()
        self.odds_dir = self.jv_data_root / "ODDS"

        # オッズキャッシュ
        self._cache = {}

    def get_latest_odds_file(
        self,
        race_date: str,
        odds_type: str = "O1"
    ) -> Optional[Path]:
        """
        最新のオッズファイルを取得

        Args:
            race_date: レース日付（YYYYMMDD）
            odds_type: オッズ種別（O1=単勝・複勝, O2=馬連, etc.）

        Returns:
            最新オッズファイルのパス（見つからない場合はNone）
        """
        if not self.odds_dir.exists():
            print(f"⚠️ オッズディレクトリが見つかりません: {self.odds_dir}")
            return None

        # パターン: O1_20260201_1530.txt
        pattern = f"{odds_type}_{race_date}_*.txt"
        files = sorted(self.odds_dir.glob(pattern), reverse=True)

        if files:
            return files[0]  # 最新（タイムスタンプが最も大きい）
        else:
            print(f"⚠️ オッズファイルが見つかりません: {pattern}")
            return None

    def parse_o1_file(self, file_path: Path) -> Dict[str, Dict]:
        """
        O1ファイル（単勝・複勝オッズ）をパース

        Args:
            file_path: O1ファイルパス

        Returns:
            {race_id: {horse_id: {'win_odds': float, 'place_odds_min': float, 'place_odds_max': float}}}
        """
        odds_data = {}

        with open(file_path, 'r', encoding='shift-jis') as f:
            for line in f:
                # O1レコードのフォーマット（簡易版）
                # レースID: 位置12-27 (16桁)
                # 馬番: 位置28-29 (2桁)
                # 単勝オッズ: 位置30-34 (5桁、100倍)
                # 複勝オッズ下限: 位置35-39 (5桁、100倍)
                # 複勝オッズ上限: 位置40-44 (5桁、100倍)

                if len(line) < 44:
                    continue

                race_id = line[11:27].strip()
                umaban = line[27:29].strip()

                try:
                    win_odds_raw = int(line[29:34].strip() or 0)
                    place_odds_min_raw = int(line[34:39].strip() or 0)
                    place_odds_max_raw = int(line[39:44].strip() or 0)

                    win_odds = win_odds_raw / 10.0
                    place_odds_min = place_odds_min_raw / 10.0
                    place_odds_max = place_odds_max_raw / 10.0

                    if race_id not in odds_data:
                        odds_data[race_id] = {}

                    odds_data[race_id][umaban] = {
                        'win_odds': win_odds,
                        'place_odds_min': place_odds_min,
                        'place_odds_max': place_odds_max
                    }

                except (ValueError, IndexError) as e:
                    print(f"⚠️ オッズパースエラー: {e}")
                    continue

        return odds_data

    def get_race_odds(
        self,
        race_id: str,
        race_date: str,
        snapshot_time: str = "latest"
    ) -> Optional[Dict]:
        """
        特定レースのオッズを取得

        Args:
            race_id: レースID（16桁）
            race_date: レース日付（YYYYMMDD）
            snapshot_time: スナップショット時刻（"latest", "HHMM", "morning", "closing"）

        Returns:
            {horse_id: {'win_odds': float, 'place_odds_min': float, ...}}
        """
        # キャッシュチェック
        cache_key = f"{race_id}_{snapshot_time}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # スナップショット時刻の解釈
        if snapshot_time == "latest":
            odds_file = self.get_latest_odds_file(race_date, odds_type="O1")
        elif snapshot_time == "morning":
            # 朝オッズ（例：10:00）
            odds_file = self.odds_dir / f"O1_{race_date}_1000.txt"
        elif snapshot_time == "closing":
            # 締切前オッズ（例：15:30）
            odds_file = self.odds_dir / f"O1_{race_date}_1530.txt"
        else:
            # 指定時刻（HHMM形式）
            odds_file = self.odds_dir / f"O1_{race_date}_{snapshot_time}.txt"

        if not odds_file or not odds_file.exists():
            print(f"⚠️ オッズファイルが見つかりません: {odds_file}")
            return None

        # パース
        all_odds = self.parse_o1_file(odds_file)

        # 指定レースのオッズを抽出
        race_odds = all_odds.get(race_id)

        if race_odds:
            # キャッシュに保存
            self._cache[cache_key] = race_odds

        return race_odds

    def get_horse_odds(
        self,
        race_id: str,
        race_date: str,
        umaban: str,
        snapshot_time: str = "latest"
    ) -> Optional[Dict]:
        """
        特定の馬のオッズを取得

        Args:
            race_id: レースID
            race_date: レース日付
            umaban: 馬番（2桁文字列、例："01"）
            snapshot_time: スナップショット時刻

        Returns:
            {'win_odds': float, 'place_odds_min': float, 'place_odds_max': float}
        """
        race_odds = self.get_race_odds(race_id, race_date, snapshot_time)

        if not race_odds:
            return None

        return race_odds.get(umaban)

    def get_odds_history(
        self,
        race_id: str,
        race_date: str
    ) -> List[Tuple[str, Dict]]:
        """
        レースのオッズ履歴を取得（時系列）

        Args:
            race_id: レースID
            race_date: レース日付

        Returns:
            [(snapshot_time, {umaban: odds_dict}), ...]
        """
        history = []

        # すべてのオッズファイルを取得
        pattern = f"O1_{race_date}_*.txt"
        files = sorted(self.odds_dir.glob(pattern))

        for file_path in files:
            # ファイル名から時刻を抽出
            match = re.search(r'O1_\d{8}_(\d{4})\.txt', file_path.name)
            if match:
                snapshot_time = match.group(1)

                # パース
                all_odds = self.parse_o1_file(file_path)
                race_odds = all_odds.get(race_id)

                if race_odds:
                    history.append((snapshot_time, race_odds))

        return history

    def export_to_csv(
        self,
        race_id: str,
        race_date: str,
        output_path: Path
    ):
        """
        オッズ履歴をCSVにエクスポート

        Args:
            race_id: レースID
            race_date: レース日付
            output_path: 出力先パス
        """
        history = self.get_odds_history(race_id, race_date)

        if not history:
            print(f"⚠️ オッズ履歴が見つかりません: {race_id}")
            return

        # DataFrameに変換
        records = []
        for snapshot_time, race_odds in history:
            for umaban, odds in race_odds.items():
                records.append({
                    'race_id': race_id,
                    'snapshot_time': snapshot_time,
                    'umaban': umaban,
                    'win_odds': odds['win_odds'],
                    'place_odds_min': odds['place_odds_min'],
                    'place_odds_max': odds['place_odds_max']
                })

        df = pd.DataFrame(records)
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"✓ オッズ履歴エクスポート完了: {output_path}")


# 使用例
if __name__ == "__main__":
    manager = OddsManager()

    # テスト: 2026年2月1日の東京11Rのオッズを取得
    race_id = "2026020105010211"
    race_date = "20260201"

    # 最新オッズ
    latest_odds = manager.get_race_odds(race_id, race_date, snapshot_time="latest")
    if latest_odds:
        print("=== 最新オッズ ===")
        for umaban, odds in latest_odds.items():
            print(f"{umaban}番: 単勝 {odds['win_odds']:.1f}倍, 複勝 {odds['place_odds_min']:.1f}-{odds['place_odds_max']:.1f}倍")

    # 朝オッズ
    morning_odds = manager.get_race_odds(race_id, race_date, snapshot_time="morning")
    if morning_odds:
        print("\n=== 朝オッズ (10:00) ===")
        for umaban, odds in morning_odds.items():
            print(f"{umaban}番: 単勝 {odds['win_odds']:.1f}倍")

    # 締切前オッズ
    closing_odds = manager.get_race_odds(race_id, race_date, snapshot_time="closing")
    if closing_odds:
        print("\n=== 締切前オッズ (15:30) ===")
        for umaban, odds in closing_odds.items():
            print(f"{umaban}番: 単勝 {odds['win_odds']:.1f}倍")

    # オッズ履歴をCSV出力
    output_path = project_root / "ml" / "data" / "odds_history_sample.csv"
    manager.export_to_csv(race_id, race_date, output_path)
