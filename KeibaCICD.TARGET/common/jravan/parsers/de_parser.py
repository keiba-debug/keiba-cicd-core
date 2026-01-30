# -*- coding: utf-8 -*-
"""
DE_DATA（出馬表データ）パーサー

parse_jv_race_data.pyのラッパー
"""

import sys
from pathlib import Path
from typing import Dict, List

# parse_jv_race_data.pyをインポート
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from parse_jv_race_data import (
    parse_dr_file as _parse_dr_file,
    get_race_times_for_date as _get_race_times_for_date,
    RaceRecord,
)

__all__ = [
    "parse_dr_file",
    "get_race_times_for_date",
    "RaceRecord",
]


def parse_dr_file(file_path: Path) -> List[RaceRecord]:
    """
    DRファイル（出馬表レース情報）を解析

    Args:
        file_path: DRファイルパス

    Returns:
        RaceRecordのリスト
    """
    return _parse_dr_file(file_path)


def get_race_times_for_date(date_str: str) -> Dict[str, List[dict]]:
    """
    指定日付のレース発走時刻を取得

    Args:
        date_str: 日付文字列 (YYYY-MM-DD形式)

    Returns:
        競馬場ごとの発走時刻データ
    """
    return _get_race_times_for_date(date_str)
