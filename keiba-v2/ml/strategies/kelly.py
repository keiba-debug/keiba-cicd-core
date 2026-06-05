#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Kelly サイジングの Single Source of Truth (P1 基盤 / RELEASE_0606_0607_PLAN §3)

bettype_sizing.py と freebudget.py に二重定義されていた 1/4 Kelly の投資額計算式を
共通化した純関数モジュール。 DB/IO/subprocess なし。 配分ロジック (P2) を触るとき
1 箇所だけ直せば両呼び出し元へ反映され、 式の乖離リスクが消える。

式 (両呼び出し元と 1 円も変わらないことを test で担保):
    kelly_raw   = calc_kelly_fraction(p, odds)                    # bet_engine の Kelly fraction
    kelly_sized = min(kelly_raw * kelly_fraction, per_bet_cap_pct)
    amount      = floor(bankroll * kelly_sized / 100) * 100       # 100円単位 (切り捨て)
    cap_yen     = floor(bankroll * per_bet_cap_pct / 100) * 100   # 1点上限
    amount      = min(amount, cap_yen)
    → amount < MIN_BET_YEN (100) は不採用 (0)、 負 EV (kelly_raw<=0) や
      不正入力 (odds<=1.0 / p∉(0,1) / None) も 0。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ml.bet_engine import calc_kelly_fraction

BET_UNIT_YEN = 100   # 100円単位丸め
MIN_BET_YEN = 100    # 100円未満は不採用


@dataclass(frozen=True)
class KellySizing:
    """Kelly サイジングの内訳。 不採用 (負EV/丸め下限割れ/不正入力) のとき amount=0。"""
    amount: int          # 100円単位の投資額 (不採用は 0)
    kelly_raw: float     # calc_kelly_fraction(p, odds) (不正入力・負EV時 0.0)
    kelly_sized: float   # min(kelly_raw * kelly_fraction, per_bet_cap_pct) (同上 0.0)


def kelly_sizing(p: Optional[float], odds: Optional[float], *, bankroll: int,
                 kelly_fraction: float, per_bet_cap_pct: float) -> KellySizing:
    """1 点の Kelly 投資額と内訳 (純関数)。

    odds<=1.0 / p∉(0,1) / None / 負 Kelly / 丸め後 100円未満 はいずれも amount=0。
    内訳 (kelly_raw / kelly_sized) は freebudget の購入記録用に返す
    (丸め下限割れで amount=0 でも内訳は算出済の値を保持)。
    """
    if odds is None or odds <= 1.0 or p is None or not (0.0 < p < 1.0):
        return KellySizing(0, 0.0, 0.0)
    kelly_raw = calc_kelly_fraction(p, odds)
    if kelly_raw <= 0:
        return KellySizing(0, 0.0, 0.0)
    kelly_sized = min(kelly_raw * kelly_fraction, per_bet_cap_pct)
    amount = (int(bankroll * kelly_sized) // BET_UNIT_YEN) * BET_UNIT_YEN
    per_bet_cap_yen = (int(bankroll * per_bet_cap_pct) // BET_UNIT_YEN) * BET_UNIT_YEN
    amount = min(amount, per_bet_cap_yen)
    if amount < MIN_BET_YEN:
        return KellySizing(0, kelly_raw, kelly_sized)
    return KellySizing(amount, kelly_raw, kelly_sized)


def kelly_amount(p: Optional[float], odds: Optional[float], *, bankroll: int,
                 kelly_fraction: float, per_bet_cap_pct: float) -> int:
    """1 点の Kelly 投資額 (100円単位、 不採用は 0)。 kelly_sizing().amount の薄ラッパ。"""
    return kelly_sizing(p, odds, bankroll=bankroll, kelly_fraction=kelly_fraction,
                        per_bet_cap_pct=per_bet_cap_pct).amount
