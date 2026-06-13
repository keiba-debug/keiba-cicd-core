# -*- coding: utf-8 -*-
"""ml.analyze.validate_live_predictions の純粋関数テスト (Session 152, E-009)

集計の核 (帯分け・gapバケット・ブートROI・較正乖離) を合成データで検証。
本番 JSON / DB には触れない。
"""

from ml.analyze.validate_live_predictions import (
    OPTION_REGISTRY,
    bootstrap_roi,
    calibration_gap,
    freshness_label,
    fukusho_payout,
    gap_buckets,
    monthly_breakdown,
    odds_band,
    opt_high_conviction,
    row_month,
)


def test_odds_band():
    assert odds_band(2.9) == "<2.9"
    assert odds_band(3.0) == "3-9.9"   # 境界は上の帯
    assert odds_band(9.9) == "3-9.9"
    assert odds_band(10.0) == "10-49.9"
    assert odds_band(60.0) == "50+"


def test_gap_buckets_cumulative():
    # gap=5 は >=0,>=2,>=4 を満たすが >=6 は満たさない
    assert gap_buckets(5) == [">=0", ">=2", ">=4"]
    assert gap_buckets(6) == [">=0", ">=2", ">=4", ">=6"]
    assert gap_buckets(0) == [">=0"]
    assert gap_buckets(-3) == []        # 市場より低評価はどのバケットにも入らない
    assert gap_buckets(None) == []      # 欠損


def test_freshness_label():
    assert freshness_label(None) == "unknown"   # メタ無し=劣化期間/旧形式
    assert freshness_label(True) == "stale"
    assert freshness_label(False) == "fresh"


def test_bootstrap_roi_basic():
    # 4bet中1的中・オッズ3.2 → 払戻320円 / 賭け400円 = ROI 80%
    r = bootstrap_roi([320.0, 0.0, 0.0, 0.0])
    assert r["n"] == 4
    assert abs(r["roi"] - 80.0) < 1e-6
    # CI は roi を挟む（下限<=roi<=上限）
    assert r["ci_low"] <= r["roi"] <= r["ci_high"]


def test_bootstrap_roi_all_hit_and_empty():
    # 全的中・オッズ2.0 → 200円払戻×2 / 200賭け = ROI 200%
    r = bootstrap_roi([200.0, 200.0])
    assert abs(r["roi"] - 200.0) < 1e-6
    # 空
    z = bootstrap_roi([])
    assert z["n"] == 0 and z["roi"] == 0.0


def test_bootstrap_roi_deterministic_seed():
    # seed 固定なので2回呼んで一致（回帰防止）
    a = bootstrap_roi([320.0, 0.0, 500.0, 0.0])
    b = bootstrap_roi([320.0, 0.0, 500.0, 0.0])
    assert a == b


def test_calibration_gap():
    # 予測平均0.30 - 実現平均0.50 = -0.20 (過小評価)
    assert calibration_gap([0.3, 0.3], [1, 0]) == -0.2
    # 完全一致
    assert calibration_gap([0.5, 0.5], [1, 0]) == 0.0
    # 空
    assert calibration_gap([], []) is None


def test_fukusho_payout():
    fuku = {3: 150, 7: 120, 12: 480}   # 馬番→100円あたり確定配当
    assert fukusho_payout(fuku, 3) == 150.0     # in-the-money
    assert fukusho_payout(fuku, 7) == 120.0
    assert fukusho_payout(fuku, 5) == 0.0       # 圏外
    assert fukusho_payout(fuku, "12") == 480.0  # 文字列馬番も int 解釈
    assert fukusho_payout(fuku, None) == 0.0    # 馬番欠損
    assert fukusho_payout({}, 3) == 0.0         # 配当テーブル空(未確定)


def test_fukusho_roi_via_bootstrap():
    # 複勝ROIは bootstrap_roi に確定配当列を渡す。3bet中2的中(150,120)→270/300=90%
    r = bootstrap_roi([150.0, 0.0, 120.0])
    assert abs(r["roi"] - 90.0) < 1e-6
    assert r["ci_low"] <= r["roi"] <= r["ci_high"]


def test_row_month():
    assert row_month("2026-06-07") == "2026-06"
    assert row_month("2026-12-31") == "2026-12"
    assert row_month("") is None
    assert row_month(None) is None


def _mk_row(day, gap, tan_hit, fuku_payout, odds):
    return {"day": day, "gap": gap, "tansho_hit": tan_hit,
            "fukusho_payout": fuku_payout, "cutoff_odds": odds}


def test_monthly_breakdown_splits_by_month_and_gap():
    # 5月3bet(1的中 odds4.0→単勝400/複勝150)・6月3bet(全外し)。min_n=2 で両月とも表示。
    rows = (
        [_mk_row("2026-05-10", 3, 1, 150.0, 4.0)]
        + [_mk_row("2026-05-11", 3, 0, 0.0, 6.0) for _ in range(2)]
        + [_mk_row("2026-06-10", 3, 0, 0.0, 5.0) for _ in range(3)]
    )
    out = monthly_breakdown(rows, gap_min=None, min_n=2)
    assert set(out) == {"2026-05", "2026-06"}
    # 5月 単勝: 400/300=133%、複勝: 150/300=50%
    assert abs(out["2026-05"]["tansho_roi"] - 133.3) < 0.5
    assert abs(out["2026-05"]["fukusho_roi"] - 50.0) < 1e-6
    # 6月 全外し → 0%
    assert out["2026-06"]["tansho_roi"] == 0.0
    # gap フィルタ: gap>=4 は該当 0 件 → 空
    assert monthly_breakdown(rows, gap_min=4, min_n=1) == {}
    # min_n 未達の月は除外
    assert monthly_breakdown(rows[:1], gap_min=None, min_n=2) == {}


def test_option_registry():
    # none は恒等
    rows = [_mk_row("2026-05-10", 3, 1, 150.0, 4.0),
            _mk_row("2026-05-11", 0, 0, 0.0, 6.0),
            _mk_row("2026-05-12", None, 0, 0.0, 8.0)]
    assert OPTION_REGISTRY["none"](rows) is rows
    # high_conviction は gap>=2 のみ（gap=0/None は落とす）。payout/hit は不変＝精算整合を保つ
    kept = opt_high_conviction(rows)
    assert len(kept) == 1 and kept[0]["gap"] == 3
    assert kept[0]["fukusho_payout"] == 150.0 and kept[0]["tansho_hit"] == 1
