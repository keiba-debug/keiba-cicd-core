# -*- coding: utf-8 -*-
"""
CK_DATA（調教データ）パーサー

parse_ck_data.pyのラッパー
"""

import sys
from pathlib import Path
from typing import List

# parse_ck_data.pyをインポート
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from parse_ck_data import (
    parse_ck_file as _parse_ck_file,
    TrainingRecord,
    get_recent_training_files,
    analyze_horse_training as _analyze_horse_training,
)

__all__ = [
    "parse_ck_file",
    "TrainingRecord",
    "get_recent_training_files",
    "analyze_horse_training",
]


def parse_ck_file(filepath: Path) -> List[TrainingRecord]:
    """
    CK_DATAファイルをパース

    Args:
        filepath: CK_DATAファイルパス

    Returns:
        TrainingRecordのリスト
    """
    return _parse_ck_file(filepath)


def analyze_horse_training(horse_id: str, race_date: str, days_back: int = 14):
    """
    馬の調教履歴を分析

    Args:
        horse_id: JRA-VAN 10桁ID
        race_date: レース日（YYYYMMDD形式）
        days_back: 遡る日数

    Returns:
        調教分析結果の辞書
    """
    return _analyze_horse_training(horse_id, race_date, days_back)
