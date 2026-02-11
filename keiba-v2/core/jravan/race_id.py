#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JRA-VAN 16桁レースID操作ユーティリティ

形式: YYYYMMDDJJKKNNRR
    YYYY: 年
    MM:   月
    DD:   日
    JJ:   場所コード (01-10)
    KK:   回次
    NN:   日次
    RR:   レース番号

例: 2026012406010208 = 2026年1月24日 中山 1回2日目 8R
"""

from typing import Dict, Optional
from ..constants import VENUE_CODES, VENUE_NAMES_TO_CODES


def build(
    year: int, month: int, day: int,
    venue_code: str, kai: int, nichi: int, race_num: int,
) -> str:
    """16桁レースIDを構築"""
    if len(venue_code) > 2:
        venue_code = VENUE_NAMES_TO_CODES.get(venue_code, venue_code)
    return (
        f"{year:04d}{month:02d}{day:02d}"
        f"{venue_code:0>2}{kai:02d}{nichi:02d}{race_num:02d}"
    )


def build_from_se(
    year: str, month_day: str,
    venue_code: str, kai: int, nichi: int, race_num: int,
) -> str:
    """SE_DATAのフィールドから16桁レースIDを構築"""
    mm = month_day[:2]
    dd = month_day[2:4]
    return f"{year}{mm}{dd}{venue_code:0>2}{kai:02d}{nichi:02d}{race_num:02d}"


def parse(race_id: str) -> Optional[Dict[str, str]]:
    """16桁レースIDをパース"""
    if not race_id or len(race_id) != 16:
        return None
    try:
        venue_code = race_id[8:10]
        return {
            "year": race_id[0:4],
            "month": race_id[4:6],
            "day": race_id[6:8],
            "date": f"{race_id[0:4]}-{race_id[4:6]}-{race_id[6:8]}",
            "venue_code": venue_code,
            "venue_name": VENUE_CODES.get(venue_code, f"?({venue_code})"),
            "kai": race_id[10:12],
            "nichi": race_id[12:14],
            "race_num": race_id[14:16],
        }
    except Exception:
        return None


def to_human(race_id: str) -> str:
    """人間が読める形式に変換"""
    info = parse(race_id)
    if not info:
        return race_id
    return (
        f"{int(info['year'])}年{int(info['month'])}月{int(info['day'])}日 "
        f"{info['venue_name']} {int(info['kai'])}回{int(info['nichi'])}日目 "
        f"{int(info['race_num'])}R"
    )


def to_date_path(race_id: str) -> str:
    """race_idからYYYY/MM/DDパスを生成"""
    info = parse(race_id)
    if not info:
        return ""
    return f"{info['year']}/{info['month']}/{info['day']}"
