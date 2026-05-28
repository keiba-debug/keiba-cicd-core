#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ledger v2 idempotency key 計算 (Session 129)

設計: 14_LEDGER_SCHEMA.md §2.1, §3.1.2

- raw_legs を bet_type 別に正規化 (馬連は sort、 馬単は順序保持、 etc.)
- ticket idempotency_key = sha256(race_id + bet_type + normalized_legs + strategy_name)
- portfolio idempotency_key = sha256(race_id + strategy + sorted ticket sigs)
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


# bet_type → 正規化ルール
# - 順序意味なし: ソート (tansho/fukusho/wakuren/umaren/wide/sanrenpuku)
# - 順序意味あり: そのまま (umatan/sanrentan)
_ORDER_INSENSITIVE = {"tansho", "fukusho", "wakuren", "umaren", "wide", "sanrenpuku"}


def normalize_raw_legs(bet_type: str, raw_legs: dict[str, Any]) -> dict[str, Any]:
    """raw_legs を bet_type に応じて正規化。 idempotency 計算前に必須。

    - horses[] / box[] / partners[] は順序意味なしの bet_type ではソート
    - axis_Nst / jiku1/2 / aite3 は元の順序保持 (axis_1st と axis_2nd の意味が違う)
    """
    out: dict[str, Any] = {}
    sort_needed = bet_type in _ORDER_INSENSITIVE

    for key, val in raw_legs.items():
        if not isinstance(val, list):
            out[key] = val
            continue
        if not val or not all(isinstance(x, int) for x in val):
            out[key] = list(val)
            continue
        if sort_needed and key in {"horses", "box"}:
            out[key] = sorted(val)
        elif key == "partners":
            # nagashi の partners は常に sort して良い (順序意味なし)
            out[key] = sorted(val)
        elif key in {"axis", "axis_1st", "axis_2nd", "axis_3rd",
                     "jiku1", "jiku2", "aite3"}:
            # axis 内部はソート (axis=[5,3] と axis=[3,5] は同じ)
            out[key] = sorted(val)
        else:
            out[key] = list(val)
    return out


def make_ticket_idempotency_key(
    race_id: str,
    bet_type: str,
    raw_legs: dict[str, Any],
    strategy_name: str,
) -> str:
    """ticket レベルの冪等キー (14_LEDGER_SCHEMA §2.1)"""
    normalized = normalize_raw_legs(bet_type, raw_legs)
    legs_json = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    payload = f"{race_id}:{bet_type}:{legs_json}:{strategy_name}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"tk-{digest[:24]}"


def make_portfolio_idempotency_key(
    race_id: str,
    portfolio_strategy: str,
    tickets: list[dict[str, Any]],
) -> str:
    """portfolio レベルの冪等キー (14_LEDGER_SCHEMA §3.1.2)"""
    sigs = []
    for t in tickets:
        legs_json = json.dumps(
            normalize_raw_legs(t["bet_type"], t["raw_legs"]),
            ensure_ascii=False, sort_keys=True,
        )
        sigs.append(f"{t['bet_type']}:{legs_json}:{t['total_amount']}")
    sigs.sort()
    payload = f"{race_id}:{portfolio_strategy}:{'|'.join(sigs)}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"pf-{digest[:32]}"


# 競馬場コード → 1 文字 (14_LEDGER_SCHEMA §3.1)
# race_id 16桁: YYYYMMDDJJKKNNRR → 9-10桁目が場コード (01..10)
_VENUE_CODE_MAP = {
    "01": "S",  # 札幌
    "02": "X",  # 函館
    "03": "F",  # 福島
    "04": "A",  # 新潟
    "05": "T",  # 東京
    "06": "N",  # 中山
    "07": "C",  # 中京
    "08": "K",  # 京都
    "09": "H",  # 阪神
    "10": "I",  # 小倉
}


def venue_code_from_race_id(race_id: str) -> str:
    """race_id 16桁から venue 1 文字を返す。 不明時は 'Z'"""
    if not isinstance(race_id, str) or len(race_id) != 16:
        return "Z"
    return _VENUE_CODE_MAP.get(race_id[8:10], "Z")


def race_no_from_race_id(race_id: str) -> str:
    """race_id 16桁から race_no 2桁を返す (例: '08')"""
    if not isinstance(race_id, str) or len(race_id) != 16:
        return "00"
    return race_id[14:16]


def date_from_race_id(race_id: str) -> str:
    """race_id 16桁から YYYY-MM-DD を返す"""
    if not isinstance(race_id, str) or len(race_id) != 16:
        return ""
    return f"{race_id[0:4]}-{race_id[4:6]}-{race_id[6:8]}"
