#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A-1 市場オフセット残差モデルの評価 (docs/ml_profit_roadmap_202607.md A-1)

experiment.py --market-offset の df_test dump を、ベースライン (S173 df_test_danger.pkl)
と突き合わせて評価する。**AUC は見ない。判定は帯別較正と実払戻ROIのみ** (B-3 方針)。

検証項目:
  1. 帯別較正: オッズ帯別 model/market/actual — favorite-longshot bias (edge_map §1.2 の
     model-act 乖離: 断然帯 -0.186 / 50+倍帯 +0.011) がオフセットで消えたか。
  2. 残差 value picks の実払戻ROI (race-bootstrap CI + 市場較正 null の a-priori p値)。
     ルールは実行前に宣言 (後知恵 band 選択の禁止 = S175 教訓):
       PRIMARY  R3: win_ev >= 1.0 ∧ pred_rank_w <= 3 ∧ cls ∈ {未勝利,条件,重賞}
                    (検証済みエッジ gap≥5×3クラスと同じ構造の EV 版)
       secondary R1: win_ev >= 1.0 ∧ pred_rank_w <= 3 (クラス制限なし)
       secondary R2: win_ev >= 1.1 ∧ pred_rank_w <= 3 ∧ cls ∈ 3クラス (閾値感度の参考)
       secondary R4: レース内残差 top1 ∧ 残差 >= log(1.25) (市場より25%以上強気)
     ※ PRIMARY 以外は多重比較の参考値。採否判断は R3 のみで行う。
  3. ベースライン参照: 同期間の gap≥5×3クラス (=130%) を同一手法で再計算して併記。

Usage:
    python -m ml.analyze.eval_market_offset \
        --offset-pkl C:/KEIBA-CICD/data3/ml/df_test_a1_offset.pkl \
        --baseline-pkl C:/tmp/df_test_danger.pkl
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
    PRED_RANK_MAX,
    load_df,
    roi_ci,
)

NBOOT = 2000
SEED = 42
ODDS_BANDS = [(1.0, 1.5), (1.5, 3.0), (3.0, 10.0), (10.0, 20.0), (20.0, 50.0), (50.0, 1e9)]


def add_market_prob(df: pd.DataFrame) -> pd.DataFrame:
    """レース内正規化 implied (experiment.market_offset_logit と同一定義)。"""
    odds = pd.to_numeric(df["odds"], errors="coerce")
    inv = 1.0 / odds.where(odds > 0)
    entry_n = df.groupby("race_id")["race_id"].transform("size")
    inv = inv.fillna(1.0 / entry_n)
    denom = inv.groupby(df["race_id"]).transform("sum")
    df["p_market"] = (inv / denom).clip(1e-4, 1 - 1e-4)
    lo = np.log(df["p_market"] / (1 - df["p_market"]))
    pw = df["pred_proba_w"].clip(1e-6, 1 - 1e-6)
    df["residual"] = np.log(pw / (1 - pw)) - lo
    return df


def band_calibration(df: pd.DataFrame) -> list:
    """オッズ帯別 model vs market vs actual (edge_map §1.2 の再現)。"""
    rows = []
    for lo, hi in ODDS_BANDS:
        s = df[(df["odds"] >= lo) & (df["odds"] < hi)]
        if len(s) == 0:
            continue
        rows.append(dict(
            band=f"{lo}-{hi if hi < 1e8 else '+'}",
            n=int(len(s)),
            model=round(float(s["pred_proba_w"].mean()), 4),
            market=round(float(s["p_market"].mean()), 4),
            act=round(float(s["is_win"].mean()), 4),
            model_minus_act=round(float(s["pred_proba_w"].mean() - s["is_win"].mean()), 4),
        ))
    return rows


def apriori_null_p(picks: pd.DataFrame, rng, nboot: int, obs_roi: float) -> float:
    """市場完全較正 null: is_win ~ Bern(p_market) で ROI 分布 → P(null >= obs)。"""
    if len(picks) == 0:
        return 1.0
    p = picks["p_market"].values
    o = picks["odds"].values
    null_rois = []
    for _ in range(nboot):
        wins = rng.random(len(p)) < p
        null_rois.append((wins * o).mean() * 100)
    return float((np.array(null_rois) >= obs_roi).mean())


def eval_rule(df: pd.DataFrame, mask: pd.Series, name: str, rng, nboot: int) -> dict:
    picks = df[mask].copy()
    n = int(len(picks))
    if n == 0:
        return dict(rule=name, n=0)
    roi, ci_lo, ci_hi = roi_ci(picks, rng, nboot=nboot)
    monthly = picks.groupby("ym")["win_ret"].mean() * 100
    p_null = apriori_null_p(picks, rng, nboot, roi)
    return dict(
        rule=name, n=n, wins=int(picks["is_win"].sum()),
        roi=round(roi, 1), ci=[round(ci_lo, 1), round(ci_hi, 1)],
        p_null=round(p_null, 4),
        months=int(monthly.size), plus_months=int((monthly > 100).sum()),
        mean_odds=round(float(picks["odds"].mean()), 1),
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offset-pkl", default="C:/KEIBA-CICD/data3/ml/df_test_a1_offset.pkl")
    ap.add_argument("--baseline-pkl", default="C:/tmp/df_test_danger.pkl")
    ap.add_argument("--nboot", type=int, default=NBOOT)
    args = ap.parse_args()

    rng = np.random.default_rng(SEED)

    dfo = add_market_prob(load_df(args.offset_pkl))
    dfb = add_market_prob(load_df(args.baseline_pkl))
    print(f"offset  : {dfo.shape}, ym {dfo['ym'].min()}-{dfo['ym'].max()}")
    print(f"baseline: {dfb.shape}, ym {dfb['ym'].min()}-{dfb['ym'].max()}")

    # --- 1. 帯別較正 ---
    print("\n=== 1. 帯別較正 (favorite-longshot bias 消滅チェック) ===")
    calib = {}
    for label, d in [("offset", dfo), ("baseline", dfb)]:
        rows = band_calibration(d)
        calib[label] = rows
        print(f"\n[{label}] band, n, model, market, act, model-act")
        for r in rows:
            print(f"  {r['band']:>8} n={r['n']:>6} model={r['model']:.4f} "
                  f"market={r['market']:.4f} act={r['act']:.4f} Δ={r['model_minus_act']:+.4f}")
        worst = max(abs(r["model_minus_act"]) for r in rows)
        print(f"  → max|model-act| = {worst:.4f}")

    # --- 2. 残差 value picks (ルールは docstring で事前宣言済み) ---
    print("\n=== 2. Offsetモデル value picks 実払戻ROI ===")
    cls3 = dfo["cls"].isin(EDGE_CLASSES)
    dfo["res_rank"] = dfo.groupby("race_id")["residual"].rank(ascending=False, method="min")
    rules = {
        "R3_PRIMARY(ev>=1&rank<=3&3cls)": (dfo["win_ev"] >= 1.0) & (dfo["pred_rank_w"] <= 3) & cls3,
        "R1(ev>=1&rank<=3)": (dfo["win_ev"] >= 1.0) & (dfo["pred_rank_w"] <= 3),
        "R2(ev>=1.1&rank<=3&3cls)": (dfo["win_ev"] >= 1.1) & (dfo["pred_rank_w"] <= 3) & cls3,
        "R4(res_top1&res>=ln1.25)": (dfo["res_rank"] == 1) & (dfo["residual"] >= np.log(1.25)),
    }
    results = []
    for name, mask in rules.items():
        r = eval_rule(dfo, mask, name, rng, args.nboot)
        results.append(r)
        if r["n"]:
            print(f"  {name:<32} n={r['n']:>4} wins={r['wins']:>3} ROI={r['roi']:>6.1f}% "
                  f"CI[{r['ci'][0]},{r['ci'][1]}] p_null={r['p_null']} "
                  f"+月={r['plus_months']}/{r['months']}")
        else:
            print(f"  {name:<32} n=0")

    # --- 3. ベースライン参照 (gap≥5×3クラス = headline 130%) ---
    print("\n=== 3. ベースライン gap>=5 x 3クラス (同一手法で再計算) ===")
    base_mask = ((dfb["pred_rank_w"] <= PRED_RANK_MAX) & (dfb["gap"] >= GAP_MIN)
                 & dfb["cls"].isin(EDGE_CLASSES))
    rb = eval_rule(dfb, base_mask, "baseline_gap5_3cls", rng, args.nboot)
    print(f"  n={rb['n']} wins={rb['wins']} ROI={rb['roi']}% CI{rb['ci']} p_null={rb['p_null']}")

    out = dict(
        generated=datetime.now().isoformat(timespec="seconds"),
        offset_pkl=args.offset_pkl, baseline_pkl=args.baseline_pkl,
        band_calibration=calib, offset_rules=results, baseline_ref=rb,
        note="PRIMARY=R3。他ルールは多重比較の参考値 (S175 教訓)。判定は帯別較正+R3のみ。",
    )
    out_path = config.ml_dir() / "a1_offset_eval.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved: {out_path}")


if __name__ == "__main__":
    main()
