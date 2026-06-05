# -*- coding: utf-8 -*-
"""ml.strategies.kelly (Kelly サイジング SSoT) の単体テスト。

bettype_sizing / freebudget が二重定義していた 1/4 Kelly 投資額式を共通化した
純関数モジュールの境界検証:
  - 負 EV → 0
  - per_bet_cap_pct 上限への張り付き
  - 100円単位丸め (切り捨て)
  - 不正入力 (None / p∉(0,1) / odds<=1) → 0
  - kelly_sizing の内訳 (kelly_raw / kelly_sized) と amount の整合
  - kelly_amount は kelly_sizing().amount の薄ラッパ

Usage:
    cd keiba-v2
    python -m pytest ml/tests/test_kelly.py -v
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from ml.bet_engine import calc_kelly_fraction
from ml.strategies import kelly


def test_kelly_amount_matches_documented_formula():
    # p=0.3, odds=5.0: b=4, kelly_raw=(4*0.3-0.7)/4=0.125, sized=min(0.03125,0.10)=0.03125
    # amount = int(10000*0.03125)//100*100 = 312//100*100 = 300
    amt = kelly.kelly_amount(0.3, 5.0, bankroll=10000, kelly_fraction=0.25, per_bet_cap_pct=0.10)
    assert amt == 300


def test_negative_ev_returns_zero():
    # p=0.1, odds=5.0: EV=0.5<1 → kelly_raw=(4*0.1-0.9)/4=-0.125<=0 → 0
    assert kelly.kelly_amount(0.1, 5.0, bankroll=10000, kelly_fraction=0.25,
                              per_bet_cap_pct=0.10) == 0
    s = kelly.kelly_sizing(0.1, 5.0, bankroll=10000, kelly_fraction=0.25, per_bet_cap_pct=0.10)
    assert s.amount == 0
    assert s.kelly_raw == 0.0   # 負EVは内訳も 0 に潰す


def test_caps_at_per_bet_pct():
    # 高 p で per_bet_cap (= bankroll*0.10 = 1000) に張り付く
    amt = kelly.kelly_amount(0.6, 3.0, bankroll=10000, kelly_fraction=1.0, per_bet_cap_pct=0.10)
    assert amt == 1000
    # cap を緩めれば張り付き解除で素の Kelly 額が出る。
    bigger = kelly.kelly_amount(0.6, 3.0, bankroll=10000, kelly_fraction=1.0, per_bet_cap_pct=0.50)
    # kelly_raw=0.4 だが 0.4 は IEEE-754 で 0.3999… のため int(10000*0.3999…)=3999、
    # //100*100=3900 (切り捨て)。 旧式の float-floor 挙動を 1 円単位で再現していることの確認。
    assert bigger == 3900
    assert bigger > 1000    # cap(=5000) に張り付かず素の Kelly が出ている


def test_rounds_down_to_100_yen_unit():
    s = kelly.kelly_sizing(0.3, 5.0, bankroll=10000, kelly_fraction=0.25, per_bet_cap_pct=0.10)
    assert s.amount % kelly.BET_UNIT_YEN == 0
    # int(10000*0.03125)=312 → 300 (切り捨て、 400 ではない)
    assert s.amount == 300


def test_below_min_bet_returns_zero():
    # 小 bankroll で丸め後 100円未満 → 不採用 (amount=0)。 内訳は算出済の値を保持。
    s = kelly.kelly_sizing(0.3, 5.0, bankroll=1000, kelly_fraction=0.25, per_bet_cap_pct=0.10)
    # int(1000*0.03125)=31 → 31//100*100 = 0 → MIN(100) 未満 → 0
    assert s.amount == 0
    assert s.kelly_raw == pytest.approx(0.125)   # 不採用でも内訳は計算済


@pytest.mark.parametrize("p,odds", [
    (None, 5.0), (0.3, None), (0.0, 5.0), (1.0, 5.0), (-0.1, 5.0), (0.3, 1.0), (0.3, 0.5),
])
def test_invalid_inputs_return_zero(p, odds):
    assert kelly.kelly_amount(p, odds, bankroll=10000, kelly_fraction=0.25,
                              per_bet_cap_pct=0.10) == 0
    s = kelly.kelly_sizing(p, odds, bankroll=10000, kelly_fraction=0.25, per_bet_cap_pct=0.10)
    assert s == kelly.KellySizing(0, 0.0, 0.0)


def test_sizing_breakdown_consistent():
    s = kelly.kelly_sizing(0.3, 5.0, bankroll=10000, kelly_fraction=0.25, per_bet_cap_pct=0.10)
    assert s.kelly_raw == pytest.approx(calc_kelly_fraction(0.3, 5.0))     # 0.125
    assert s.kelly_sized == pytest.approx(min(s.kelly_raw * 0.25, 0.10))   # 0.03125
    assert s.amount == 300


def test_kelly_amount_is_thin_wrapper():
    # kelly_amount(...) は常に kelly_sizing(...).amount と一致
    for p, odds in [(0.3, 5.0), (0.6, 3.0), (0.1, 5.0), (0.25, 4.0), (0.5, 2.5)]:
        s = kelly.kelly_sizing(p, odds, bankroll=10000, kelly_fraction=0.25, per_bet_cap_pct=0.10)
        a = kelly.kelly_amount(p, odds, bankroll=10000, kelly_fraction=0.25, per_bet_cap_pct=0.10)
        assert a == s.amount


def test_parity_with_bettype_sizing_and_freebudget_callers():
    # SSoT 抽出後も両呼び出し元の口が同じ式を指していることを軽く確認
    from ml.strategies import bettype_sizing as sz
    from ml.strategies import freebudget as fb

    # bettype_sizing.kelly_amount は kelly のもの (re-export)
    assert sz.kelly_amount is kelly.kelly_amount
    # freebudget は kelly_sizing を直接利用 (定数も re-export)
    assert fb.BET_UNIT_YEN == kelly.BET_UNIT_YEN == 100
    assert fb.MIN_BET_YEN == kelly.MIN_BET_YEN == 100
