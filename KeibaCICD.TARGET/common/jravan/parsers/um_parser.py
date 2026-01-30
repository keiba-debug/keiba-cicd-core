# -*- coding: utf-8 -*-
"""
UM_DATA（馬マスタデータ）パーサー

parse_jv_horse_data.pyのラッパー
"""

import sys
from pathlib import Path
from typing import List, Optional

# parse_jv_horse_data.pyをインポート
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from parse_jv_horse_data import (
    find_horse_by_id as _find_horse_by_id,
    search_horses_by_name as _search_horses_by_name,
    find_horse_by_name as _find_horse_by_name,
    HorseRecord,
)

__all__ = [
    "find_horse_by_id",
    "search_horses_by_name",
    "find_horse_by_name",
    "HorseRecord",
]


def find_horse_by_id(horse_id: str) -> Optional[HorseRecord]:
    """
    馬IDで検索

    Args:
        horse_id: 10桁の血統登録番号

    Returns:
        HorseRecord（見つからない場合はNone）
    """
    return _find_horse_by_id(horse_id)


def search_horses_by_name(query: str, limit: int = 20) -> List[HorseRecord]:
    """
    馬名で部分一致検索

    Args:
        query: 検索文字列
        limit: 最大件数

    Returns:
        HorseRecordのリスト
    """
    return _search_horses_by_name(query, limit)


def find_horse_by_name(name: str) -> Optional[str]:
    """
    馬名で完全一致検索し、10桁馬IDを返す

    Args:
        name: 馬名（完全一致）

    Returns:
        10桁の血統登録番号（見つからない場合はNone）
    """
    return _find_horse_by_name(name)
