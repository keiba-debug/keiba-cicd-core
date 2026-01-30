# -*- coding: utf-8 -*-
"""
レースID操作ユーティリティ

JRA-VAN 16桁レースIDの構築・パースを提供します。

使用例:
    from common.jravan.race_id import build_race_id, parse_race_id

    # レースID構築
    race_id = build_race_id(
        year=2026, month=1, day=24,
        track_code="06", kaiji=1, nichiji=2, race_num=8
    )
    # => "2026012406010208"

    # レースIDパース
    info = parse_race_id("2026012406010208")
    # => {"year": "2026", "month": "01", "day": "24", ...}
"""

from typing import Dict, Optional
from .id_converter import get_track_name, get_track_code


def build_race_id(
    year: int,
    month: int,
    day: int,
    track_code: str,
    kaiji: int,
    nichiji: int,
    race_num: int
) -> str:
    """
    JRA-VAN 16桁レースIDを構築

    Args:
        year: 開催年（4桁）
        month: 開催月（1-12）
        day: 開催日（1-31）
        track_code: 競馬場コード（2桁）または競馬場名
        kaiji: 回次（1-6）
        nichiji: 日次（1-12）
        race_num: レース番号（1-12）

    Returns:
        16桁のレースID（YYYYMMDDJJKKNNRR）

    使用例:
        >>> build_race_id(2026, 1, 24, "06", 1, 2, 8)
        '2026012406010208'

        >>> build_race_id(2026, 1, 24, "中山", 1, 2, 8)
        '2026012406010208'
    """
    # 競馬場名が渡された場合はコードに変換
    if len(track_code) > 2:
        track_code = get_track_code(track_code) or track_code

    return (
        f"{year:04d}"
        f"{month:02d}"
        f"{day:02d}"
        f"{track_code:0>2}"
        f"{kaiji:02d}"
        f"{nichiji:02d}"
        f"{race_num:02d}"
    )


def parse_race_id(race_id: str) -> Optional[Dict[str, str]]:
    """
    JRA-VAN 16桁レースIDをパース

    Args:
        race_id: 16桁のレースID

    Returns:
        パース結果の辞書（エラーの場合はNone）

    使用例:
        >>> info = parse_race_id("2026012406010208")
        >>> print(info["track_name"])
        '中山'
    """
    if not race_id or len(race_id) != 16:
        return None

    try:
        year = race_id[0:4]
        month = race_id[4:6]
        day = race_id[6:8]
        track_code = race_id[8:10]
        kaiji = race_id[10:12]
        nichiji = race_id[12:14]
        race_num = race_id[14:16]

        track_name = get_track_name(track_code) or f"Unknown({track_code})"

        return {
            "year": year,
            "month": month,
            "day": day,
            "date": f"{year}-{month}-{day}",
            "track_code": track_code,
            "track_name": track_name,
            "kaiji": kaiji,
            "nichiji": nichiji,
            "race_num": race_num,
            "race_id": race_id,
        }
    except Exception:
        return None


def format_race_id_human(race_id: str) -> str:
    """
    レースIDを人間が読みやすい形式に変換

    Args:
        race_id: 16桁のレースID

    Returns:
        読みやすい文字列

    使用例:
        >>> format_race_id_human("2026012406010208")
        '2026年1月24日 中山 1回2日目 8R'
    """
    info = parse_race_id(race_id)
    if not info:
        return race_id

    year = int(info["year"])
    month = int(info["month"])
    day = int(info["day"])
    track = info["track_name"]
    kaiji = int(info["kaiji"])
    nichiji = int(info["nichiji"])
    race_num = int(info["race_num"])

    return f"{year}年{month}月{day}日 {track} {kaiji}回{nichiji}日目 {race_num}R"
