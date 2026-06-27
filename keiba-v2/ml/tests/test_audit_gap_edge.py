# -*- coding: utf-8 -*-
"""audit_gap_edge.py の単体テスト (Session 175)

合成 df_test 上で監査関数が壊れず妥当な型/範囲を返すことを保証 (114MB pkl は使わない):
  - edge_sets: base/edge/core のフィルタが定義通り
  - band_sensitivity: 行構造と is_core フラグ
  - null_selection_bias: p値∈[0,1]
  - risk_montecarlo: キー + seed 固定で決定的
  - band_out_estimate / temporal_split: dict を返す
"""
import numpy as np
import pandas as pd

from ml.analyze import audit_gap_edge as ag

# 各月のエッジ馬のオッズ (m0/m1 が [15,30) = core / m2,m3 は外)
_EDGE_ODDS = {"202505": 18.0, "202506": 25.0, "202507": 35.0, "202508": 12.0}
_WIN_MONTHS = {"202506", "202508"}  # エッジ馬がその月 race0 で勝つ


def _df():
    rows = []
    for ym, eodds in _EDGE_ODDS.items():
        for r in range(3):  # 3 races/月・各6頭
            rid = f"{ym}{r:02d}0101010101"[:16]
            odds_list = [2.0, 4.0, 6.0, 8.0, 14.0, eodds]
            for j, od in enumerate(odds_list):
                odds_rank = j + 1
                is_edge = (j == 5)  # 最高オッズ馬を gap5 のエッジ候補に
                pred_rank_w = 1 if is_edge else odds_rank  # edge: rank1 -> gap=5
                win = 1 if (is_edge and r == 0 and ym in _WIN_MONTHS) else 0
                rows.append(dict(
                    race_id=rid, ym=ym, cls="miSHOURI" if is_edge else "OP/L",
                    odds=od, odds_rank=odds_rank, pred_rank_w=pred_rank_w,
                    gap=odds_rank - pred_rank_w,
                    win_ev=2.0 if is_edge else 0.5,
                    is_win=win, win_ret=win * od,
                ))
    return pd.DataFrame(rows)


def test_edge_sets_filters():
    base, edge, core = ag.edge_sets(_df())
    assert len(base) == 12          # 4月 × 3race のエッジ馬
    assert len(edge) == 12          # 全て miSHOURI
    assert len(core) == 6           # odds[15,30) = m0(18) + m1(25) の 6頭
    assert (core["odds"] < 30).all() and (core["odds"] >= 15).all()


def test_band_sensitivity_marks_core():
    _, edge, _ = ag.edge_sets(_df())
    sens = ag.band_sensitivity(edge)
    core_rows = [r for r in sens if r["is_core"]]
    assert len(core_rows) == 1
    assert core_rows[0]["n"] == 6   # [15,30) に 6頭
    assert all("roi" in r and "n" in r for r in sens)


def test_null_selection_bias_pvalues_in_range():
    df = _df()
    _, edge, _ = ag.edge_sets(df)
    nb = ag.null_selection_bias(df, edge, np.random.default_rng(0), 50,
                                obs_core=200.0, obs_broad=130.0)
    for key in ("p_apriori_ge_broad", "p_search_ge_core", "p_search_ge_130"):
        assert 0.0 <= nb[key] <= 1.0


def test_risk_montecarlo_keys_and_deterministic():
    _, _, core = ag.edge_sets(_df())
    r1 = ag.risk_montecarlo(core, np.random.default_rng(1), 100, 0.01)
    r2 = ag.risk_montecarlo(core, np.random.default_rng(1), 100, 0.01)
    assert r1 == r2                  # seed 固定で決定的
    for key in ("final_bank_p50", "max_dd_p95_pct", "p_below_50pct", "max_lose_streak_p95"):
        assert key in r1


def test_temporal_and_bandout_return_dict():
    _, edge, core = ag.edge_sets(_df())
    ts = ag.temporal_split(core)
    assert "first_half" in ts and "second_half" in ts
    bo = ag.band_out_estimate(edge)
    assert "roi" in bo and "n" in bo
