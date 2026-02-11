# -*- coding: utf-8 -*-
"""
ID変換ユーティリティ

競馬ブックとJRA-VANのID変換を提供します。

使用例:
    from common.jravan.id_converter import get_horse_id_by_name

    # 馬名からJRA-VAN 10桁IDに変換
    horse_id = get_horse_id_by_name("ドウデュース")
    # => "2019103487"
"""

import sys
from pathlib import Path
from typing import Optional

# horse_id_mapper.pyをインポート
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from horse_id_mapper import get_jvn_horse_id, rebuild_horse_index


# 競馬場コード対応表
TRACK_CODES = {
    "01": "札幌",
    "02": "函館",
    "03": "福島",
    "04": "新潟",
    "05": "東京",
    "06": "中山",
    "07": "中京",
    "08": "京都",
    "09": "阪神",
    "10": "小倉",
}

# 逆引き辞書
TRACK_NAMES_TO_CODES = {v: k for k, v in TRACK_CODES.items()}


def get_horse_id_by_name(horse_name: str) -> Optional[str]:
    """
    馬名からJRA-VAN 10桁IDに変換

    Args:
        horse_name: 馬名（完全一致）

    Returns:
        10桁の血統登録番号（見つからない場合はNone）

    使用例:
        >>> get_horse_id_by_name("ドウデュース")
        '2019103487'
    """
    return get_jvn_horse_id(horse_name)


def get_horse_name_by_id(horse_id: str) -> Optional[str]:
    """
    JRA-VAN 10桁IDから馬名を取得

    Args:
        horse_id: 10桁の血統登録番号

    Returns:
        馬名（見つからない場合はNone）

    使用例:
        >>> get_horse_name_by_id("2019103487")
        'ドウデュース'
    """
    from .parsers.um_parser import find_horse_by_id

    horse = find_horse_by_id(horse_id)
    return horse.name if horse else None


def get_track_code(track_name: str) -> Optional[str]:
    """
    競馬場名からJRA-VAN競馬場コード（2桁）に変換

    Args:
        track_name: 競馬場名（例: "中山"）

    Returns:
        2桁の競馬場コード（見つからない場合はNone）

    使用例:
        >>> get_track_code("中山")
        '06'
    """
    return TRACK_NAMES_TO_CODES.get(track_name)


def get_track_name(track_code: str) -> Optional[str]:
    """
    JRA-VAN競馬場コードから競馬場名に変換

    Args:
        track_code: 2桁の競馬場コード（例: "06"）

    Returns:
        競馬場名（見つからない場合はNone）

    使用例:
        >>> get_track_name("06")
        '中山'
    """
    return TRACK_CODES.get(track_code)


def rebuild_index() -> int:
    """
    馬名インデックスを再構築

    Returns:
        登録馬数

    使用例:
        >>> count = rebuild_index()
        >>> print(f"インデックス構築完了: {count} 頭")
    """
    return rebuild_horse_index()
