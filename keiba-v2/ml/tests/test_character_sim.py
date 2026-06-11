# -*- coding: utf-8 -*-
"""キャラ別バンクロールsim の単体テスト (Session 149 / T12)

DB 非依存層 (精算・base_unit スケール・OOS 分割・ringfence) を検証する。
build_tmpl_contexts (MySQL haraimodoshi + process_race) はここでは扱わない。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.analyze.simulate_bankroll_character import (  # noqa: E402
    TmplRaceCtx, aggregate_char_flat, run_character, settle_templates_cp,
    simulate_day_character,
)
from ml.strategies import characters as ch  # noqa: E402


# --- 精算 (settle_templates_cp = weight 配分 + ticket_payout) ---

def test_settle_tansho_ai2_hit():
    # tansho_ai2 = 単勝 ◎○ 2点 (weight 1.0)
    marks = {"◎": [1], "○": [2]}
    rpay = {"tansho": {1: 300}}  # 馬1=300円/100円
    cost, payout = settle_templates_cp(("tansho_ai2",), marks, rpay)
    assert cost == 200.0       # 2点 × 100
    assert payout == 300.0     # 馬1 的中のみ


def test_settle_tansho_ai2_miss():
    marks = {"◎": [1], "○": [2]}
    rpay = {"tansho": {5: 300}}  # 印馬は不的中
    cost, payout = settle_templates_cp(("tansho_ai2",), marks, rpay)
    assert cost == 200.0
    assert payout == 0.0


def test_settle_weight_applied():
    # honmei_formation の三連単ボーナスは weight=0.25 → stake/払戻が 0.25 倍
    marks = {"◎": [1], "○": [2], "▲": [3], "△": [4], "Ⅲ": [5]}
    # 三連複 ◎-相手 と 三連単 ◎○▲BOX。 ここでは三連単 1-2-3 を的中させる
    rpay = {"sanrentan": {(1, 2, 3): 10000}, "sanrenpuku": {}}
    cost, payout = settle_templates_cp(("honmei_formation",), marks, rpay)
    # 三連単 1-2-3 的中 → 10000 × weight0.25 = 2500
    assert payout == 2500.0
    assert cost > 0


# --- base_unit スケール (simulate_day_character) ---

def test_simulate_day_base_unit_scale():
    ctx = TmplRaceCtx(rid="r1", date="20251201", settle={"x": (200.0, 300.0)})
    # base_unit = 300000 × 0.0005 = 150 → cost 200×1.5=300, payout 300×1.5=450
    cost, payout = simulate_day_character(
        [ctx], day_start=10000, w_total=300000, char_key="x", unit_fraction=0.0005)
    assert abs(cost - 300.0) < 1e-6
    assert abs(payout - 450.0) < 1e-6


def test_simulate_day_compounding_grows_base():
    # w_total が増えると base_unit も増える (比例ベット = 複利)
    ctx = TmplRaceCtx(rid="r1", date="20251201", settle={"x": (100.0, 0.0)})
    c_small, _ = simulate_day_character(
        [ctx], day_start=10000, w_total=300000, char_key="x", unit_fraction=0.001)
    c_big, _ = simulate_day_character(
        [ctx], day_start=10000, w_total=600000, char_key="x", unit_fraction=0.001)
    assert abs(c_big - 2 * c_small) < 1e-6  # 総資金2倍 → bet2倍


def test_simulate_day_budget_cap():
    ctx = TmplRaceCtx(rid="r1", date="20251201", settle={"x": (200.0, 300.0)})
    # base_unit=150 → cost=300 > day_start=200 → 先着順で見送り
    cost, payout = simulate_day_character(
        [ctx], day_start=200, w_total=300000, char_key="x", unit_fraction=0.0005)
    assert cost == 0.0
    assert payout == 0.0


def test_simulate_day_skips_zero_cost():
    ctx = TmplRaceCtx(rid="r1", date="20251201", settle={"x": (0.0, 0.0)})  # 不発火
    cost, payout = simulate_day_character(
        [ctx], day_start=10000, w_total=300000, char_key="x", unit_fraction=0.0005)
    assert cost == 0.0
    assert payout == 0.0


# --- OOS 分割・月別 (aggregate_char_flat) ---

def test_aggregate_oos_split():
    by_date = {
        "20251201": [TmplRaceCtx("r1", "20251201", {"x": (100.0, 200.0)})],  # train roi 200%
        "20260201": [TmplRaceCtx("r2", "20260201", {"x": (100.0, 0.0)})],    # valid roi 0%
    }
    agg = aggregate_char_flat(by_date, "x", split="20260101")
    assert agg["roi_train"] == 200.0
    assert agg["roi_valid"] == 0.0
    assert agg["fire"] == 2
    assert agg["hits"] == 1
    assert agg["roi"] == 100.0  # (200+0)/(100+100)


def test_aggregate_median_monthly():
    # 3ヶ月 ROI = [50, 100, 150] → median 100
    by_date = {
        "20250501": [TmplRaceCtx("a", "20250501", {"x": (100.0, 50.0)})],
        "20250601": [TmplRaceCtx("b", "20250601", {"x": (100.0, 100.0)})],
        "20250701": [TmplRaceCtx("c", "20250701", {"x": (100.0, 150.0)})],
    }
    agg = aggregate_char_flat(by_date, "x", split="20260101")
    assert agg["median_roi"] == 100.0
    assert len(agg["monthly"]) == 3
    assert agg["plus_months"] == "2/3"  # 100% と 150% の2ヶ月


# --- ringfence (run_character の隔離初期資金) ---

def test_ringfence_eff_w0():
    by_date = {"20251201": [TmplRaceCtx("r1", "20251201",
                                        {"sanrentan_roman": (100.0, 0.0)})]}
    char = ch.get_character("sanrentan_roman")
    assert char.ringfenced
    res = run_character(char, by_date, w0=300000, mc=10, split="20260101")
    assert res.eff_w0 == 9000  # 300000 × 0.03


def test_non_ringfence_full_w0():
    by_date = {"20251201": [TmplRaceCtx("r1", "20251201",
                                        {"honmei": (100.0, 120.0)})]}
    char = ch.get_character("honmei")
    assert not char.ringfenced
    res = run_character(char, by_date, w0=300000, mc=10, split="20260101")
    assert res.eff_w0 == 300000


def test_characters_registry():
    keys = ch.list_characters()
    assert "honmei" in keys
    assert "sanrentan_roman" in keys
    # ringfenced は cap_pct を持つ
    roman = ch.get_character("sanrentan_roman")
    assert roman.ringfence_cap_pct > 0
    # 妙味党はオッズ依存マーカー
    assert ch.get_character("myomi").odds_dependent
