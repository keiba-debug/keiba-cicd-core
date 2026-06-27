#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""gap5単勝エッジ 過学習監査 (Session 175 / 後知恵 band選択の罠を定量化)

`export_edge_validation.py` が出した core ROI 218% (odds∈[15,30)∧win_ev≥1) は、
**エッジを発見したのと同じ df_test 上で「ROIが最大になるオッズ帯」を後から選んだ**結果。
これが本物のエッジか test-set cherry-picking かを honest に評価し、
**配分に使える「素の期待ROI」を1つ確定**する。

実装する監査 (小サンプル core n≈156/的中14 を踏まえ有効なものだけ):
  1. odds帯感度サーフェス   : (lo,hi) 格子で ROI 行列。[15,30) が孤立ピークか広いプラトーか。
  2. null best-of-search    : 市場完全較正の帰無世界で band×win_ev を best-of-search した時の
                              max ROI 分布 → P(null max ≥ 218%) / ≥130% = 多条件分けの上振れの p値。
  3. 時系列ロバストネス     : test 13ヶ月を前半/後半に割り core ROI 併記 (記述のみ・小サンプル注意)。
  4. band-out 推定 (de-bias): 各月の最良 band を「他12ヶ月」で選び当月に適用 → 後知恵を抜いた honest ROI。
  5. リスク/破産           : フラクショナル固定% で bankroll path を Monte Carlo → DD分布/破産確率/必要bankroll。

入力 : C:/tmp/df_test_danger.pkl (experiment.py --dump-test / 13ヶ月OOS)。
出力 : コンソール + data3/ml/edge_audit.json。結論は docs/market_calibration_edge_map.md §8 に手で追記する。

Usage:
    python -m ml.analyze.audit_gap_edge
    python -m ml.analyze.audit_gap_edge --pkl C:/tmp/df_test_danger.pkl --nboot 2000
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import config  # noqa: E402
from ml.export_edge_validation import (  # noqa: E402
    EDGE_CLASSES,
    GAP_MIN,
    ODDS_HI,
    ODDS_LO,
    PRED_RANK_MAX,
    WIN_EV_MIN,
    load_df,
    roi_ci,
)

# 後知恵 search が触る格子 (export_edge_validation.levers と整合させる) ---------------
LO_GRID = [7, 10, 12, 15, 18, 20]
HI_GRID = [25, 30, 35, 40, 50, 1e9]
WINEV_GRID = [0.6, 0.8, 1.0, 1.2]
SIZING_LEVELS = [0.005, 0.01, 0.02, 0.03, 0.05]
NBOOT = 1000
SEED = 42


def _hi_label(hi: float) -> str:
    return f"{int(hi)}" if hi < 99999 else "inf"


def edge_sets(df: pd.DataFrame):
    """base(全オッズ3クラス前) / edge(3クラス) / core(精密化後) を返す。"""
    base = df[(df["pred_rank_w"] <= PRED_RANK_MAX) & (df["gap"] >= GAP_MIN)].copy()
    edge = base[base["cls"].isin(EDGE_CLASSES)].copy()
    core = edge[(edge["odds"] >= ODDS_LO) & (edge["odds"] < ODDS_HI)
                & (edge["win_ev"] >= WIN_EV_MIN)].copy()
    return base, edge.sort_values("race_id"), core.sort_values("race_id")


# --- 1. odds帯感度サーフェス ---------------------------------------------------
def band_sensitivity(edge: pd.DataFrame) -> list:
    """win_ev≥1 を固定し (lo,hi) を動かして ROI 行列。core=[15,30) が孤立ピークか確認。"""
    e = edge[edge["win_ev"] >= WIN_EV_MIN]
    out = []
    for lo in LO_GRID:
        for hi in HI_GRID:
            if hi <= lo:
                continue
            s = e[(e["odds"] >= lo) & (e["odds"] < hi)]
            n = int(len(s))
            roi = round(float(s["win_ret"].mean()) * 100, 1) if n else 0.0
            out.append(dict(lo=lo, hi=_hi_label(hi), n=n,
                            wins=int(s["is_win"].sum()) if n else 0, roi=roi,
                            is_core=(lo == ODDS_LO and abs(hi - ODDS_HI) < 1e-9)))
    return out


# --- 2. null best-of-search (選択バイアスの定量化) -----------------------------
def null_selection_bias(df: pd.DataFrame, edge: pd.DataFrame, rng, nboot: int,
                        obs_core: float, obs_broad: float) -> dict:
    """市場完全較正の帰無世界で2つの p値を出す。

    帰無: 各馬の真の勝率 = レース内正規化 implied (1/odds / Σ1/odds・全出走馬で正規化)。
    この下で edge 各点の is_win を独立Bernoulli近似でサンプルし:
      (a) a-priori 検定: edge 全体(=broad)の ROI を毎回計算 → P(null ≥ obs_broad)。
          「gap≥5×3クラスのエッジがそもそも較正市場を超えるか」= 最重要の単独 p値。
      (b) best-of-search 検定: band×win_ev 格子(144組)から max ROI を選ぶ操作を再現
          (S174 が 130%→218% でやった band 精密化の再現) → P(null max ≥ obs_core)。
          後知恵 band 選択の上振れを p値化。
    """
    z = df.groupby("race_id")["odds"].transform(lambda x: (1.0 / x).sum())
    p_null = ((1.0 / df["odds"]) / z).loc[edge.index].to_numpy()
    odds = edge["odds"].to_numpy()
    winev = edge["win_ev"].to_numpy()

    masks = []
    for lo in LO_GRID:
        for hi in HI_GRID:
            if hi <= lo:
                continue
            for kev in WINEV_GRID:
                m = (odds >= lo) & (odds < hi) & (winev >= kev)
                if m.sum() >= 20:  # 極小セルは除外 (S174 core n=156 水準の搾取のみ対象)
                    masks.append(m)

    apriori = np.empty(nboot)
    maxima = np.empty(nboot)
    for b in range(nboot):
        wr = (rng.random(len(p_null)) < p_null).astype(float) * odds
        apriori[b] = wr.mean() * 100.0
        best = -1.0
        for m in masks:
            r = wr[m].mean() * 100.0
            if r > best:
                best = r
        maxima[b] = best
    return dict(
        n_combos=len(masks),
        null_apriori_mean=round(float(apriori.mean()), 1),
        null_apriori_p95=round(float(np.percentile(apriori, 95)), 1),
        p_apriori_ge_broad=round(float((apriori >= obs_broad).mean()), 4),
        null_max_mean=round(float(maxima.mean()), 1),
        null_max_p50=round(float(np.percentile(maxima, 50)), 1),
        null_max_p95=round(float(np.percentile(maxima, 95)), 1),
        null_max_p99=round(float(np.percentile(maxima, 99)), 1),
        p_search_ge_core=round(float((maxima >= obs_core).mean()), 4),
        p_search_ge_130=round(float((maxima >= 130).mean()), 4),
    )


# --- 3. 時系列ロバストネス -----------------------------------------------------
def temporal_split(core: pd.DataFrame) -> dict:
    months = sorted(core["ym"].unique())
    half = len(months) // 2
    h1, h2 = set(months[:half]), set(months[half:])
    return dict(
        first_half=dict(period=f"{months[0]}..{months[half-1]}",
                        **_roi_cell(core[core["ym"].isin(h1)])),
        second_half=dict(period=f"{months[half]}..{months[-1]}",
                         **_roi_cell(core[core["ym"].isin(h2)])),
        note="n≈半分/月数小 → 1ヶ月依存でないかの確認止まり。+EV断言の根拠にしない。",
    )


def _roi_cell(s: pd.DataFrame) -> dict:
    n = int(len(s))
    return dict(n=n, wins=int(s["is_win"].sum()) if n else 0,
                roi=round(float(s["win_ret"].mean()) * 100, 1) if n else 0.0)


# --- 4. band-out 推定 (leave-one-month-out で band選択の後知恵を抜く) -----------
def band_out_estimate(edge: pd.DataFrame) -> dict:
    """各月の最良 (lo,hi) を「他の月」で選び、その band を当月 edge に適用 → 集計。

    band 選択を毎回 out-of-month で行うので「[15,30) を全体最大化で選んだ」後知恵が抜ける。
    win_ev≥1 は core 固定。小サンプルで noisy だが最も誠実な単一 ROI。
    """
    e = edge[edge["win_ev"] >= WIN_EV_MIN].copy()
    months = sorted(e["ym"].unique())
    bands = [(lo, hi) for lo in LO_GRID for hi in HI_GRID if hi > lo]
    collected = []
    chosen = []
    for m in months:
        train = e[e["ym"] != m]
        best_band, best_roi, best_n = None, -1e9, 0
        for lo, hi in bands:
            s = train[(train["odds"] >= lo) & (train["odds"] < hi)]
            if len(s) < 30:  # train 側の薄いセルは選ばない
                continue
            r = float(s["win_ret"].mean()) * 100
            if r > best_roi:
                best_band, best_roi, best_n = (lo, hi), r, len(s)
        if best_band is None:
            continue
        lo, hi = best_band
        held = e[(e["ym"] == m) & (e["odds"] >= lo) & (e["odds"] < hi)]
        collected.append(held)
        chosen.append(dict(month=m, lo=lo, hi=_hi_label(hi),
                           train_roi=round(best_roi, 1), applied_n=int(len(held))))
    if not collected:
        return dict(roi=0.0, n=0, chosen=[])
    allheld = pd.concat(collected)
    n = int(len(allheld))
    return dict(
        roi=round(float(allheld["win_ret"].mean()) * 100, 1),
        n=n, wins=int(allheld["is_win"].sum()),
        hit_rate=round(int(allheld["is_win"].sum()) / n * 100, 1) if n else 0.0,
        chosen=chosen,
    )


# --- 5. リスク/破産 Monte Carlo ------------------------------------------------
def _path_stats(wr: np.ndarray, unit: float) -> tuple:
    """win_ret 列 (=is_win*odds) を順に賭けた時の (final, maxdd, min_bank, max_lose_streak)。"""
    bank = 1.0
    peak = 1.0
    maxdd = 0.0
    lo = 1.0
    streak = 0
    maxstreak = 0
    for x in wr:
        bank += unit * (x - 1.0)  # win: unit*(odds-1) / lose: -unit
        peak = max(peak, bank)
        maxdd = min(maxdd, bank - peak)
        lo = min(lo, bank)
        if x > 0:
            streak = 0
        else:
            streak += 1
            maxstreak = max(maxstreak, streak)
    return bank, maxdd, lo, maxstreak


def risk_montecarlo(picks: pd.DataFrame, rng, nboot: int, stake_pct: float = 0.01) -> dict:
    """bet 列をブートストラップ resample し DD分布/破産確率を出す (フラクショナル固定%)。"""
    wr = picks["win_ret"].to_numpy()
    n = len(wr)
    if n == 0:
        return {}
    finals, dds, mins, streaks = [], [], [], []
    for _ in range(nboot):
        samp = wr[rng.integers(0, n, n)]
        f, dd, mn, ms = _path_stats(samp, stake_pct)
        finals.append(f); dds.append(dd); mins.append(mn); streaks.append(ms)
    finals = np.array(finals); dds = np.array(dds); mins = np.array(mins)
    return dict(
        stake_pct=round(stake_pct * 100, 1),
        n_bets=n,
        final_bank_p50=round(float(np.percentile(finals, 50)), 3),
        final_bank_p05=round(float(np.percentile(finals, 5)), 3),
        max_dd_p50_pct=round(float(np.percentile(dds, 50)) * 100, 1),
        max_dd_p95_pct=round(float(np.percentile(dds, 5)) * 100, 1),  # 5%tile=最悪側
        min_bank_p05=round(float(np.percentile(mins, 5)), 3),
        p_below_50pct=round(float((mins < 0.5).mean()), 4),
        p_below_70pct=round(float((mins < 0.7).mean()), 4),
        max_lose_streak_p95=int(np.percentile(streaks, 95)),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="gap5単勝エッジ 過学習監査")
    ap.add_argument("--pkl", default=r"C:/tmp/df_test_danger.pkl")
    ap.add_argument("--nboot", type=int, default=NBOOT)
    args = ap.parse_args()

    # Windows コンソール(cp932)で ≥ / ★ 等が UnicodeEncodeError にならぬよう utf-8 化
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if not Path(args.pkl).exists():
        print(f"ERROR: pkl not found: {args.pkl}\n"
              f"  generate via: python -m ml.experiment ... --dump-test {args.pkl}")
        return 1

    rng = np.random.default_rng(SEED)
    df = load_df(args.pkl)
    base, edge, core = edge_sets(df)

    broad = base[base["cls"].isin(EDGE_CLASSES)]  # = edge (全オッズ3クラス = 130%/413)
    broad_roi, broad_lo, broad_hi = roi_ci(broad, rng)
    core_roi, core_lo, core_hi = roi_ci(core, rng)

    print("=== gap5単勝エッジ 過学習監査 (S175) ===")
    print(f"  broad(committed 全オッズ3クラス): n={len(broad)} "
          f"ROI={broad_roi:.1f}% CI[{broad_lo:.0f}-{broad_hi:.0f}] wins={int(broad['is_win'].sum())}")
    print(f"  core (odds[15,30)∧win_ev≥1)     : n={len(core)} "
          f"ROI={core_roi:.1f}% CI[{core_lo:.0f}-{core_hi:.0f}] wins={int(core['is_win'].sum())}")

    sens = band_sensitivity(edge)
    print("\n--- 1. odds帯感度 (win_ev≥1固定・ROI%) [★=core] ---")
    for r in sens:
        star = " ★" if r["is_core"] else ""
        print(f"  [{r['lo']:>2},{r['hi']:>3}) n={r['n']:>3} wins={r['wins']:>2} ROI={r['roi']:>6.1f}%{star}")

    nb = null_selection_bias(df, edge, rng, args.nboot, core_roi, broad_roi)
    print(f"\n--- 2. null 検定 (較正市場・{args.nboot}回) ---")
    print(f"  (a) a-priori : null broad ROI mean={nb['null_apriori_mean']} p95={nb['null_apriori_p95']} "
          f"→ P(null ≥ {broad_roi:.0f}%)={nb['p_apriori_ge_broad']}")
    print(f"  (b) search   : {nb['n_combos']}組合せ best-of-search max mean={nb['null_max_mean']} "
          f"p95={nb['null_max_p95']} p99={nb['null_max_p99']}")
    print(f"               → P(null max ≥ {core_roi:.0f}%[core])={nb['p_search_ge_core']}  "
          f"P(null max ≥130%)={nb['p_search_ge_130']}")

    ts = temporal_split(core)
    print("\n--- 3. 時系列 (core 前半/後半) ---")
    print(f"  前半 {ts['first_half']['period']}: n={ts['first_half']['n']} ROI={ts['first_half']['roi']}%")
    print(f"  後半 {ts['second_half']['period']}: n={ts['second_half']['n']} ROI={ts['second_half']['roi']}%")

    bo = band_out_estimate(edge)
    print(f"\n--- 4. band-out 推定 (leave-one-month-out) ---")
    print(f"  honest ROI={bo['roi']}% n={bo['n']} wins={bo.get('wins',0)} hit={bo.get('hit_rate',0)}%")

    risk_core = risk_montecarlo(core, rng, args.nboot, 0.01)
    risk_broad = risk_montecarlo(broad, rng, args.nboot, 0.01)
    print(f"\n--- 5. リスク (1%/bet・{args.nboot}回ブートストラップ) ---")
    print(f"  core : final p50={risk_core['final_bank_p50']} p05={risk_core['final_bank_p05']} "
          f"maxDD p95={risk_core['max_dd_p95_pct']}% P(<50%)={risk_core['p_below_50pct']} "
          f"連敗p95={risk_core['max_lose_streak_p95']}")
    print(f"  broad: final p50={risk_broad['final_bank_p50']} p05={risk_broad['final_bank_p05']} "
          f"maxDD p95={risk_broad['max_dd_p95_pct']}% P(<50%)={risk_broad['p_below_50pct']} "
          f"連敗p95={risk_broad['max_lose_streak_p95']}")

    result = dict(
        created_at=datetime.now().isoformat(),
        session="S175",
        pkl_source=str(args.pkl),
        nboot=args.nboot,
        broad=dict(n=int(len(broad)), roi=round(broad_roi, 1),
                   ci_low=round(broad_lo, 0), ci_high=round(broad_hi, 0),
                   wins=int(broad["is_win"].sum())),
        core=dict(n=int(len(core)), roi=round(core_roi, 1),
                  ci_low=round(core_lo, 0), ci_high=round(core_hi, 0),
                  wins=int(core["is_win"].sum())),
        band_sensitivity=sens,
        null_selection_bias=nb,
        temporal_split=ts,
        band_out=bo,
        risk_core_1pct=risk_core,
        risk_broad_1pct=risk_broad,
    )
    out = config.ml_dir() / "edge_audit.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
