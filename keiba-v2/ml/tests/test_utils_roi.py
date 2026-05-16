#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ml/utils/roi.py ユニットテスト"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from ml.utils.roi import (
    Bet, RoiResult,
    calc_roi, calc_win_roi, bootstrap_roi_ci,
    sharpe_ratio, sortino_ratio, max_drawdown,
    losing_streaks, consecutive_loss_months,
    calc_brier_score, calc_ece, calibration_curve,
)


class TestCalcRoiList:
    def test_empty(self):
        r = calc_roi([])
        assert r.n == 0
        assert r.roi == 0
        assert not r

    def test_all_hit(self):
        # 1点100円、オッズ2.0で的中 → 200円戻り、ROI 200%
        bets = [Bet("R1", cost=100, payout=200, is_hit=True, odds=2.0)]
        r = calc_roi(bets)
        assert r.n == 1
        assert r.cost == 100
        assert r.payout == 200
        assert r.pnl == 100
        assert r.roi == 200.0
        assert r.hit_rate == 100.0
        assert r.mean_hit_odds == 2.0

    def test_all_miss(self):
        bets = [Bet("R1", cost=100, payout=0, is_hit=False)]
        r = calc_roi(bets)
        assert r.roi == 0
        assert r.pnl == -100
        assert r.hit_rate == 0

    def test_mixed(self):
        bets = [
            Bet("R1", 100, 0, False),
            Bet("R2", 100, 500, True, odds=5.0),
            Bet("R3", 100, 0, False),
            Bet("R4", 100, 200, True, odds=2.0),
        ]
        r = calc_roi(bets)
        assert r.n == 4
        assert r.cost == 400
        assert r.payout == 700
        assert r.roi == 175.0
        assert r.hits == 2
        assert r.hit_rate == 50.0
        # mean hit odds = (5+2)/2 = 3.5
        assert r.mean_hit_odds == pytest.approx(3.5)


class TestCalcRoiDataFrame:
    def test_basic(self):
        pd = pytest.importorskip("pandas")
        df = pd.DataFrame({
            "race_id": ["R1", "R2", "R3"],
            "cost":    [100, 100, 100],
            "payout":  [0, 200, 0],
            "odds":    [3.0, 2.0, 5.0],
        })
        r = calc_roi(df, odds_col="odds")
        assert r.n == 3
        assert r.payout == 200
        assert r.roi == pytest.approx(66.6, abs=0.1)
        assert r.hits == 1


class TestCalcWinRoi:
    def test_basic(self):
        pd = pytest.importorskip("pandas")
        df = pd.DataFrame({
            "race_id": ["R1", "R2", "R3", "R4"],
            "odds":    [3.0, 5.0, 2.0, 10.0],
            "is_win":  [1,    0,   1,   0],
        })
        r = calc_win_roi(df)
        # hits: R1(3.0*100=300), R3(2.0*100=200) → total payout 500
        # cost: 400
        assert r.payout == 500
        assert r.cost == 400
        assert r.roi == 125.0
        assert r.hit_rate == 50.0


class TestBootstrap:
    def test_ci_ordered(self):
        bets = [
            Bet(f"R{i}", 100, 200 if i % 2 == 0 else 0, i % 2 == 0, odds=2.0)
            for i in range(20)
        ]
        ci_low, ci_high = bootstrap_roi_ci(bets, n_bootstrap=500, seed=42)
        assert ci_low <= ci_high
        # 期待 ROI 100% 前後
        assert 50 < ci_high < 200

    def test_calc_roi_with_bootstrap(self):
        bets = [
            Bet(f"R{i}", 100, 250 if i % 4 == 0 else 0, i % 4 == 0, odds=2.5)
            for i in range(40)
        ]
        r = calc_roi(bets, bootstrap_n=300, seed=42)
        assert r.bootstrap_n == 300
        assert r.ci_low > 0 or r.ci_low == 0
        assert r.ci_high >= r.ci_low
        assert r.ci_width == r.ci_high - r.ci_low


class TestRiskMetrics:
    def test_sharpe_positive(self):
        returns = [5.0, 3.0, -1.0, 4.0, 2.0, 6.0]
        sr = sharpe_ratio(returns, periods_per_year=12)
        assert sr > 0

    def test_sharpe_empty(self):
        assert sharpe_ratio([]) == 0
        assert sharpe_ratio([1.0]) == 0

    def test_sortino_no_downside(self):
        # 全期間プラス → 下方リスク 0 → inf
        import math
        assert math.isinf(sortino_ratio([1, 2, 3, 4]))

    def test_max_drawdown(self):
        cum = [0, 100, 200, 150, 50, 100, 80]
        dd, dd_pct = max_drawdown(cum)
        # peak 200 → 50 → -150
        assert dd == -150
        assert dd_pct == pytest.approx(-75.0)

    def test_max_drawdown_monotonic(self):
        cum = [0, 100, 200]
        dd, _ = max_drawdown(cum)
        assert dd == 0

    def test_max_drawdown_empty(self):
        assert max_drawdown([]) == (0.0, 0.0)


class TestStreaks:
    def test_losing_streak(self):
        hits = [0, 0, 0, 1, 0, 0, 1, 0, 0, 0, 0]
        out = losing_streaks(hits)
        assert out["max_streak"] == 4
        # streaks: 3, 2, 4 → avg = 3.0
        assert out["avg_streak"] == 3.0
        assert out["streak_10plus"] == 0

    def test_no_loss(self):
        out = losing_streaks([1, 1, 1])
        assert out["max_streak"] == 0

    def test_ten_plus(self):
        hits = [0] * 15 + [1] + [0] * 3
        out = losing_streaks(hits)
        assert out["max_streak"] == 15
        assert out["streak_10plus"] == 1
        assert out["max_streak_loss"] == 1500

    def test_consecutive_loss_months(self):
        pnl = [-100, -50, 200, -300, -400, -500, 100]
        assert consecutive_loss_months(pnl) == 3


class TestProbabilisticMetrics:
    def test_brier_perfect(self):
        y_true = [1, 0, 1, 0]
        y_pred = [1.0, 0.0, 1.0, 0.0]
        assert calc_brier_score(y_true, y_pred) == 0.0

    def test_brier_worst(self):
        y_true = [1, 0]
        y_pred = [0.0, 1.0]
        assert calc_brier_score(y_true, y_pred) == 1.0

    def test_ece_perfect(self):
        y_true = [1, 1, 0, 0]
        y_pred = [0.9, 0.9, 0.1, 0.1]
        # mostly aligned, ECE should be small
        assert calc_ece(y_true, y_pred, n_bins=5) < 0.2

    def test_ece_empty(self):
        assert calc_ece([], []) == 0.0

    def test_calibration_curve(self):
        y_true = [1, 0, 1, 0, 1, 0, 1, 0]
        y_pred = [0.9, 0.8, 0.7, 0.6, 0.4, 0.3, 0.2, 0.1]
        rows = calibration_curve(y_true, y_pred, n_bins=5)
        assert len(rows) == 5
        for row in rows:
            assert "bin_lo" in row
            assert "n" in row
