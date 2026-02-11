#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
データパス設定モジュール
新しいフォルダ構造に対応したパス管理
"""

from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

class DataPathConfig:
    """データパスの設定と管理"""

    def __init__(self, base_path: str = "Z:/KEIBA-CICD/data", use_new_structure: bool = True):
        """
        初期化

        Args:
            base_path: データフォルダのベースパス
            use_new_structure: 新しいフォルダ構造を使用するかどうか
        """
        self.base_path = Path(base_path)
        self.use_new_structure = use_new_structure

    def get_date_parts(self, date_str: str) -> tuple:
        """
        日付文字列を年、月、日に分解

        Args:
            date_str: YYYYMMDD形式の日付文字列

        Returns:
            (year, month, day) のタプル
        """
        if len(date_str) != 8 or not date_str.isdigit():
            raise ValueError(f"Invalid date format: {date_str}")

        year = date_str[:4]
        month = date_str[4:6]
        day = date_str[6:8]

        return year, month, day

    def get_race_date_path(self, date_str: str) -> Path:
        """
        レース日付のベースパスを取得

        Args:
            date_str: YYYYMMDD形式の日付文字列

        Returns:
            日付フォルダのパス
        """
        if self.use_new_structure:
            year, month, day = self.get_date_parts(date_str)
            return self.base_path / "races" / year / month / day
        else:
            # 旧構造（互換性のため）
            year, month, day = self.get_date_parts(date_str)
            return self.base_path / "organized" / year / month / day

    def get_venue_path(self, date_str: str, venue: str) -> Path:
        """
        競馬場別のパスを取得

        Args:
            date_str: YYYYMMDD形式の日付文字列
            venue: 競馬場名（例: "中山", "阪神"）

        Returns:
            競馬場フォルダのパス
        """
        base = self.get_race_date_path(date_str)
        return base / venue

    def get_parsed_path(self, date_str: str) -> Path:
        """
        パース済みデータのパスを取得

        Args:
            date_str: YYYYMMDD形式の日付文字列

        Returns:
            parsedフォルダのパス
        """
        if self.use_new_structure:
            base = self.get_race_date_path(date_str)
            return base / "parsed"
        else:
            # 旧構造
            return self.base_path / "parsed" / date_str

    def get_temp_path(self, date_str: Optional[str] = None) -> Path:
        """
        一時ファイルのパスを取得

        Args:
            date_str: YYYYMMDD形式の日付文字列（省略時は共通temp）

        Returns:
            tempフォルダのパス
        """
        if self.use_new_structure and date_str:
            base = self.get_race_date_path(date_str)
            return base / "temp"
        else:
            # 旧構造または日付なし
            return self.base_path / "temp"

    def get_race_info_path(self, date_str: str) -> Path:
        """
        レース情報JSONのパスを取得

        Args:
            date_str: YYYYMMDD形式の日付文字列

        Returns:
            race_info.jsonのパス
        """
        if self.use_new_structure:
            base = self.get_race_date_path(date_str)
            return base / "race_info.json"
        else:
            # 旧構造
            return self.base_path / "race_ids" / f"{date_str}_info.json"

    def get_integrated_json_path(self, race_id: str, venue: str = None) -> Path:
        """
        統合JSONファイルのパスを取得

        Args:
            race_id: レースID（例: "202504050810"）
            venue: 競馬場名（新構造で必要）

        Returns:
            integrated JSONのパス
        """
        # race_idから日付を抽出
        date_str = race_id[:8]

        if self.use_new_structure:
            if not venue:
                # 競馬場を自動判定（race_idの9-10桁目から）
                venue_code = race_id[8:10]
                venue = self._get_venue_from_code(venue_code)

            venue_path = self.get_venue_path(date_str, venue)
            return venue_path / f"integrated_{race_id}.json"
        else:
            # 旧構造
            year, month, day = self.get_date_parts(date_str)
            venue_code = race_id[8:10]
            venue = self._get_venue_from_code(venue_code)
            return self.base_path / "organized" / year / month / day / venue / f"integrated_{race_id}.json"

    def get_markdown_path(self, race_id: str, venue: str = None) -> Path:
        """
        MarkdownファイルのPATHを取得

        Args:
            race_id: レースID（例: "202504050810"）
            venue: 競馬場名（新構造で必要）

        Returns:
            markdownファイルのパス
        """
        # race_idから日付を抽出
        date_str = race_id[:8]

        if self.use_new_structure:
            if not venue:
                # 競馬場を自動判定
                venue_code = race_id[8:10]
                venue = self._get_venue_from_code(venue_code)

            venue_path = self.get_venue_path(date_str, venue)
            return venue_path / f"{race_id}.md"
        else:
            # 旧構造
            year, month, day = self.get_date_parts(date_str)
            venue_code = race_id[8:10]
            venue = self._get_venue_from_code(venue_code)
            return self.base_path / "organized" / year / month / day / venue / f"{race_id}.md"

    def _get_venue_from_code(self, venue_code: str) -> str:
        """
        競馬場コードから競馬場名を取得

        Args:
            venue_code: 競馬場コード（2桁）

        Returns:
            競馬場名
        """
        venue_map = {
            "01": "札幌",
            "02": "函館",
            "03": "福島",
            "04": "新潟",
            "05": "東京",
            "06": "中山",
            "07": "中京",
            "08": "京都",
            "09": "阪神",
            "10": "小倉"
        }
        return venue_map.get(venue_code, "unknown")

    def ensure_directories(self, path: Path) -> None:
        """
        ディレクトリが存在しない場合は作成

        Args:
            path: 作成するパス
        """
        if path.suffix:
            # ファイルパスの場合は親ディレクトリを作成
            path.parent.mkdir(parents=True, exist_ok=True)
        else:
            # ディレクトリパスの場合はそのまま作成
            path.mkdir(parents=True, exist_ok=True)

    def list_available_dates(self) -> List[str]:
        """
        利用可能な日付のリストを取得

        Returns:
            YYYYMMDD形式の日付文字列のリスト
        """
        dates = []

        if self.use_new_structure:
            races_path = self.base_path / "races"
            if races_path.exists():
                for year_dir in races_path.iterdir():
                    if year_dir.is_dir():
                        for month_dir in year_dir.iterdir():
                            if month_dir.is_dir():
                                for day_dir in month_dir.iterdir():
                                    if day_dir.is_dir():
                                        date_str = f"{year_dir.name}{month_dir.name}{day_dir.name}"
                                        dates.append(date_str)
        else:
            # 旧構造
            organized_path = self.base_path / "organized"
            if organized_path.exists():
                for year_dir in organized_path.iterdir():
                    if year_dir.is_dir():
                        for month_dir in year_dir.iterdir():
                            if month_dir.is_dir():
                                for day_dir in month_dir.iterdir():
                                    if day_dir.is_dir():
                                        date_str = f"{year_dir.name}{month_dir.name.zfill(2)}{day_dir.name.zfill(2)}"
                                        dates.append(date_str)

        return sorted(dates)

    def get_summary_path(self, date_str: str) -> Path:
        """
        サマリーJSONのパスを取得

        Args:
            date_str: YYYYMMDD形式の日付文字列

        Returns:
            summary.jsonのパス
        """
        if self.use_new_structure:
            base = self.get_race_date_path(date_str)
            return base / "summary.json"
        else:
            # 旧構造にはsummary.jsonは存在しない
            return None

# グローバルインスタンス（デフォルト設定）
default_config = DataPathConfig()

def get_path_config(use_new_structure: bool = None) -> DataPathConfig:
    """
    パス設定のインスタンスを取得

    Args:
        use_new_structure: 新構造を使用するか（Noneの場合はデフォルト）

    Returns:
        DataPathConfig インスタンス
    """
    if use_new_structure is None:
        return default_config
    else:
        return DataPathConfig(use_new_structure=use_new_structure)