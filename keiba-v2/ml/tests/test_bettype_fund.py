# -*- coding: utf-8 -*-
"""P2b bettype_fund の単体テスト"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.strategies import bettype_efficiency as be
from ml.strategies import bettype_fund as bf
from ml.strategies import bettype_selection as bs


def _strength(umaban, *, pred_w, odds, composite, win_prob=None):
    wp = win_prob if win_prob is not None else pred_w
    return be.HorseStrength(
        umaban=umaban, horse_name=f"H{umaban}", win_prob=wp, odds=odds,
        place_odds_min=1.5 if umaban == 1 else 2.5,
        pred_w=pred_w, pred_p=None, ar_deviation=None,
        z_w=None, z_p=None, z_adr=None, composite=composite,
    )


def _plan(bet_type, label, *, ev, odds, hit=0.2, legs=None):
    lg = legs or [[1]]
    return be.Plan(
        bet_type=bet_type, label=label, legs=lg, n_points=len(lg),
        hit_prob=hit, sum_p=hit, synthetic_odds=odds, expected_return=ev,
        odds_legs=[odds], coverage=1.0, vs_tansho="gt" if ev and ev > 1 else "lt",
    )


def _race(plans, *, axis=1, axis_odds=5.0, strengths=None):
    return be.RaceEfficiency(
        race_id="2026053005021101", date="2026-05-30", venue_name="東京",
        race_number=11, grade="G1", track_type="芝", distance=2400,
        num_runners=12, axis_umaban=axis, axis_name="軸", axis_odds=axis_odds,
        partners=[2, 3], weights=(1, 1, 1), specialist=None,
        strengths=strengths or [], plans=plans, warnings=[],
    )


class TestFukushoFloor:
    def test_low_odds_rejected(self):
        p = _plan("fukusho", "複勝", ev=1.05, odds=1.5, hit=0.7)
        assert bf.passes_fukusho_floor(p, min_odds=1.8) is False

    def test_thin_profit_rejected(self):
        p = _plan("fukusho", "複勝", ev=1.05, odds=2.0, hit=0.52)
        assert bf.passes_fukusho_floor(p, min_expected_profit_yen=20) is False

    def test_passes_floor(self):
        p = _plan("fukusho", "複勝", ev=1.25, odds=2.2, hit=0.6)
        assert bf.passes_fukusho_floor(p) is True


class TestDecideFund:
    def test_skip_all_on_negative_anchor(self):
        plans = [
            _plan("tansho", "単勝", ev=None, odds=2.0, hit=0.05, legs=[[1]]),
            _plan("umaren", "馬連", ev=0.8, odds=5.0, legs=[[1, 2]]),
        ]
        strengths = [_strength(1, pred_w=0.05, odds=2.0, composite=1.0),
                     _strength(2, pred_w=0.04, odds=10.0, composite=0.5)]
        d = bf.decide_fund(_race(plans, axis_odds=2.0, strengths=strengths))
        assert d.mode == "skip_all"

    def test_tansho_only_when_no_combo(self):
        plans = [
            _plan("tansho", "単勝", ev=None, odds=5.0, hit=0.25, legs=[[1]]),
            _plan("umaren", "馬連", ev=0.9, odds=8.0, legs=[[1, 2]]),
        ]
        strengths = [_strength(1, pred_w=0.25, odds=5.0, composite=1.2),
                     _strength(2, pred_w=0.15, odds=12.0, composite=0.3)]
        d = bf.decide_fund(_race(plans, axis_odds=5.0, strengths=strengths))
        assert d.tansho_only is True
        assert d.mode in ("tansho_only", "boost")

    def test_boost_on_strong_axis(self):
        plans = [
            _plan("tansho", "単勝", ev=None, odds=4.0, hit=0.35, legs=[[1]]),
            _plan("umaren", "馬連", ev=1.15, odds=10.0, legs=[[1, 2]]),
        ]
        strengths = [_strength(1, pred_w=0.35, odds=4.0, composite=1.5),
                     _strength(2, pred_w=0.12, odds=15.0, composite=0.2)]
        d = bf.decide_fund(_race(plans, axis_odds=4.0, strengths=strengths))
        assert d.kelly_boost > 1.0
        assert d.mode == "boost"

    def test_longshot_flow_on_high_axis_odds(self):
        plans = [
            _plan("tansho", "単勝", ev=None, odds=12.0, hit=0.12, legs=[[1]]),
            _plan("umaren", "馬連", ev=1.2, odds=25.0, legs=[[1, 2], [1, 3]]),
        ]
        strengths = [_strength(1, pred_w=0.12, odds=12.0, composite=0.8),
                     _strength(2, pred_w=0.10, odds=20.0, composite=0.5)]
        d = bf.decide_fund(_race(plans, axis_odds=12.0, strengths=strengths))
        assert d.longshot_yen == 100
        assert d.longshot_horses is not None


class TestAdaptiveSelection:
    def test_adaptive_skip_all(self):
        plans = [
            _plan("tansho", "単勝", ev=None, odds=1.5, hit=0.05, legs=[[1]]),
            _plan("umaren", "馬連", ev=0.7, odds=4.0, legs=[[1, 2]]),
        ]
        strengths = [_strength(1, pred_w=0.05, odds=1.5, composite=0.05),
                     _strength(2, pred_w=0.04, odds=20.0, composite=0.04)]
        sel = bs.select_plans(_race(plans, axis_odds=1.5, strengths=strengths), strategy="adaptive")
        assert sel.strategy == "skip_all"
        assert sel.selected_plans == []
        assert sel.fund_mode == "skip_all"

    def test_adaptive_fukusho_floor_skips_thin_place(self):
        plans = [
            _plan("tansho", "単勝", ev=None, odds=5.0, hit=0.30, legs=[[1]]),
            _plan("fukusho", "複勝", ev=1.02, odds=1.5, hit=0.7, legs=[[1]]),
        ]
        strengths = [_strength(1, pred_w=0.30, odds=5.0, composite=1.0),
                     _strength(2, pred_w=0.15, odds=8.0, composite=0.2)]
        sel = bs.select_plans(_race(plans, axis_odds=5.0, strengths=strengths), strategy="adaptive")
        types = [p.bet_type for p in sel.selected_plans]
        assert "tansho" in types
        assert "fukusho" not in types
