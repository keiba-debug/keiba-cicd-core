#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A-2 メタラベリング — gap≥5単勝 pick の的中予測でベットサイズを傾斜する
(docs/ml_profit_roadmap_202607.md A-2 / López de Prado meta-labeling)

一次シグナル = 検証済みエッジ: pred_rank_w<=3 ∧ gap>=5 ∧ cls∈{未勝利,条件,重賞}
(edge_map §8: ROI130% p=0.026・的中5%・高分散)。
二次モデルの目的変数 = 「その pick が的中したか (is_win)」。
出力は買う/見送るの二値ではなく **サイズの重み** (fractional Kelly の傾斜) に使う。

時系列分離 (walk-forward・リーク無し):
  meta-train: backfill dump (test 2024.01-2025.04 / モデルは 2020-2023.09 学習)
  meta-test : S173 dump    (test 2025.05-2026.05 / モデルは 2020-2025.03 学習)
  → 未来の picks で学習して過去を当てる方向が無い。ただし一次モデルの世代が違う
    (2023.09 止め vs 2025.03 止め) 分布シフトは残る。正直に併記する。

評価 (S175 教訓: 後知恵選択の禁止・null 検定必須):
  1. meta-score 上位半分 vs 下位半分の実払戻ROI (置換 null: score シャッフル 2000回)
  2. サイジング比較: flat 1u vs quarter-Kelly(meta_p) の ROI / log-wealth / maxDD
  3. 参考: AUC (判定には使わない)

Usage:
    python -m ml.analyze.meta_label_gap \
        --train-pkl C:/KEIBA-CICD/data3/ml/df_test_meta_backfill.pkl \
        --test-pkl C:/tmp/df_test_danger.pkl
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
)

SEED = 42
NPERM = 2000
KELLY_FRAC = 0.25          # quarter-Kelly
KELLY_CAP = 0.02           # 1点あたり bankroll 2% 上限 (deep fractional, S175 §8.3)

# 文脈特徴量 (投票時点で既知のものだけ・10個以下に固定 = 過学習ガード)
META_FEATURES = [
    "log_odds", "win_ev", "gap", "pred_proba_w", "entry_count",
    "is_turf", "log_distance", "ar_deviation", "cls_mi", "cls_ju",
]


def extract_picks(pkl: str) -> pd.DataFrame:
    df = load_df(pkl)
    m = ((df["pred_rank_w"] <= PRED_RANK_MAX) & (df["gap"] >= GAP_MIN)
         & df["cls"].isin(EDGE_CLASSES))
    p = df[m].copy()
    p["log_odds"] = np.log(p["odds"].clip(lower=1.0))
    p["is_turf"] = (p["track_type"].astype(str).isin(["芝", "turf"])).astype(int)
    p["log_distance"] = np.log(pd.to_numeric(p["distance"], errors="coerce").fillna(1600))
    p["cls_mi"] = (p["cls"] == "miSHOURI").astype(int)
    p["cls_ju"] = (p["cls"] == "juushou").astype(int)
    if "ar_deviation" not in p.columns:
        p["ar_deviation"] = np.nan
    p["ar_deviation"] = pd.to_numeric(p["ar_deviation"], errors="coerce").fillna(50.0)
    for c in ["win_ev", "gap", "pred_proba_w", "entry_count"]:
        p[c] = pd.to_numeric(p[c], errors="coerce")
    return p


def fit_meta(train: pd.DataFrame):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.impute import SimpleImputer

    X = train[META_FEATURES]
    y = train["is_win"].astype(int)
    model = make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        LogisticRegression(C=0.5, max_iter=1000, random_state=SEED),
    )
    model.fit(X, y)
    return model


def wealth_path(stakes: np.ndarray, rets: np.ndarray) -> dict:
    """stake (bankroll比) の系列で bankroll path を回す (時系列順)。"""
    bk = 1.0
    peak, maxdd = 1.0, 0.0
    for s, r in zip(stakes, rets):
        bet = bk * s
        bk = bk - bet + bet * r  # r = odds if win else 0
        peak = max(peak, bk)
        maxdd = max(maxdd, (peak - bk) / peak)
        if bk <= 0:
            return dict(final=0.0, maxdd=1.0, ruined=True)
    return dict(final=round(bk, 4), maxdd=round(maxdd, 4), ruined=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-pkl", default="C:/KEIBA-CICD/data3/ml/df_test_meta_backfill.pkl")
    ap.add_argument("--test-pkl", default="C:/tmp/df_test_danger.pkl")
    ap.add_argument("--nperm", type=int, default=NPERM)
    args = ap.parse_args()

    rng = np.random.default_rng(SEED)

    tr = extract_picks(args.train_pkl)
    te = extract_picks(args.test_pkl)
    print(f"meta-train picks: {len(tr)} (ym {tr['ym'].min()}-{tr['ym'].max()}), "
          f"hit={tr['is_win'].mean():.3f}, ROI={tr['win_ret'].mean()*100:.1f}%")
    print(f"meta-test  picks: {len(te)} (ym {te['ym'].min()}-{te['ym'].max()}), "
          f"hit={te['is_win'].mean():.3f}, ROI={te['win_ret'].mean()*100:.1f}%")

    model = fit_meta(tr)
    te = te.sort_values(["race_id"]).copy()
    te["meta_p"] = model.predict_proba(te[META_FEATURES])[:, 1]

    from sklearn.metrics import roc_auc_score
    auc = roc_auc_score(te["is_win"], te["meta_p"]) if te["is_win"].nunique() > 1 else np.nan
    print(f"\n[参考] meta AUC on test picks: {auc:.4f} (判定には使わない)")

    # --- 1. 上位半分 vs 下位半分 + 置換 null ---
    med = te["meta_p"].median()
    top = te[te["meta_p"] >= med]
    bot = te[te["meta_p"] < med]
    roi_top = top["win_ret"].mean() * 100
    roi_bot = bot["win_ret"].mean() * 100 if len(bot) else 0.0
    print(f"\n=== 1. meta-score 半割 ===")
    print(f"  top half: n={len(top)} wins={int(top['is_win'].sum())} ROI={roi_top:.1f}%")
    print(f"  bot half: n={len(bot)} wins={int(bot['is_win'].sum())} ROI={roi_bot:.1f}%")

    null_top = []
    vals = te["win_ret"].values
    k = len(top)
    for _ in range(args.nperm):
        idx = rng.permutation(len(vals))[:k]
        null_top.append(vals[idx].mean() * 100)
    p_perm = float((np.array(null_top) >= roi_top).mean())
    print(f"  置換null (score無情報): P(top-half ROI >= {roi_top:.1f}%) = {p_perm:.4f}")

    # --- 2. サイジング比較 (flat vs quarter-Kelly(meta_p)) ---
    print(f"\n=== 2. サイジング比較 (時系列順・bankroll path) ===")
    rets = te["win_ret"].values  # odds if win else 0 (1単位賭けた時の回収)
    odds = te["odds"].values
    flat = wealth_path(np.full(len(te), 0.005), rets)
    kelly_f = (te["meta_p"].values * odds - 1) / np.maximum(odds - 1, 1e-9)
    stakes = np.clip(kelly_f * KELLY_FRAC, 0.0, KELLY_CAP)
    kelly = wealth_path(stakes, rets)
    n_skip = int((stakes <= 0).sum())
    print(f"  flat 0.5%/bet : final={flat['final']}x maxDD={flat['maxdd']*100:.0f}%")
    print(f"  1/4Kelly(meta): final={kelly['final']}x maxDD={kelly['maxdd']*100:.0f}% "
          f"(skip {n_skip}/{len(te)} = meta_p×odds<1 で0賭け)")

    # --- 係数 (解釈用) ---
    lr = model.named_steps["logisticregression"]
    coefs = dict(zip(META_FEATURES, [round(float(c), 3) for c in lr.coef_[0]]))
    print(f"\n係数 (標準化後): {coefs}")

    out = dict(
        generated=datetime.now().isoformat(timespec="seconds"),
        train_pkl=args.train_pkl, test_pkl=args.test_pkl,
        n_train=len(tr), n_test=len(te),
        train_roi=round(float(tr["win_ret"].mean() * 100), 1),
        test_roi=round(float(te["win_ret"].mean() * 100), 1),
        auc_ref=round(float(auc), 4) if auc == auc else None,
        top_half=dict(n=len(top), roi=round(float(roi_top), 1)),
        bot_half=dict(n=len(bot), roi=round(float(roi_bot), 1)),
        p_perm=round(p_perm, 4),
        sizing=dict(flat=flat, kelly=kelly, kelly_frac=KELLY_FRAC, kelly_cap=KELLY_CAP),
        coefs=coefs,
        caveat="一次モデル世代差 (train=2023.09止めモデルのpicks / test=2025.03止め)。"
               "採否は p_perm と sizing 比較で判断。AUC は参考のみ。",
    )
    out_path = config.ml_dir() / "meta_label_gap_eval.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved: {out_path}")


if __name__ == "__main__":
    main()
