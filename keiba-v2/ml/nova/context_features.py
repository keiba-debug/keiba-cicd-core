#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Regulus レース文脈エンジン §展開 — context特徴量 計算 + ablation (Session 177)

みねた front_ratio 系(前走3角通過順≤3)をキャッシュ済splitsに付与し、Regulus(3歳上芝OP+)の
lean_plus に上乗せして incremental AUC を測る(A: front_ratio文脈の素の価値)。

context特徴量(5):
  ctx_front_ratio    レース内 前走先行(prev3角≤3)占有率
  ctx_prev_le3       自馬の前走先行フラグ
  ctx_fr_x_le3       front_ratio × prev_le3 (高ペースで先行=巻込リスク)
  ctx_escape_sandwich 両隣枠が前走先行 ∧ 自馬非先行 (挟まれ)
  ctx_front_neighbors 隣接枠の先行馬数(0/1/2)

リーク防止: prev_le3 は対象レース日より前の最新走のみ(bisect)。
Usage: python -m ml.nova.context_features      # 計算+ablation(W/P)
       python -m ml.nova.context_features --save-only  # context列付きsplitsを保存のみ
出力: data3/ml/nova/turf_op/context_ablation.md + splits/{train,val,test}_ctx.pkl
"""
from __future__ import annotations
import sys, io, json, bisect, argparse
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import numpy as np
import pandas as pd

from core import config
from ml.experiment import FEATURE_COLS_ALL, MARKET_FEATURES, P_ONLY_FEATURES, PARAMS_P, PARAMS_W
from ml.nova.ablation_turf_op import assign_groups, fit_eval, filter_turf_op, SPLITS

LEAN_PLUS = ["basic", "form_level", "trajectory", "jrdb_idm", "jrdb_cid",
             "jrdb_other", "jockey", "pace", "class_ctx"]
CTX_COLS = ["ctx_front_ratio", "ctx_prev_le3", "ctx_fr_x_le3",
            "ctx_escape_sandwich", "ctx_front_neighbors"]
HIST = r"C:\KEIBA-CICD\data3\ml\horse_history_cache.json"


def build_horse_timeline(hist):
    """ketto -> (sorted dates[], corner3[])  for bisect lookup of prev race."""
    tl = {}
    for ketto, races in hist.items():
        rows = []
        for r in races:
            d = str(r.get("race_date", ""))
            c = r.get("corners") or []
            c3 = c[-2] if len(c) >= 2 else (c[0] if len(c) == 1 else None)
            if d and c3 is not None:
                rows.append((d, c3))
        rows.sort()
        if rows:
            tl[ketto] = ([d for d, _ in rows], [c for _, c in rows])
    return tl


def prev_le3_for(tl, ketto, date):
    e = tl.get(str(ketto))
    if not e:
        return np.nan
    dates, c3s = e
    i = bisect.bisect_left(dates, str(date))  # first >= date; prev = i-1
    if i == 0:
        return np.nan
    return float(c3s[i - 1] <= 3)


def add_context(df, tl):
    df = df.copy()
    df["ctx_prev_le3"] = [prev_le3_for(tl, k, d) for k, d in zip(df["ketto_num"], df["date"])]
    # front_ratio = レース内 prev_le3 平均(有効馬のみ)
    fr = df.groupby("race_id")["ctx_prev_le3"].transform("mean")
    df["ctx_front_ratio"] = fr
    df["ctx_fr_x_le3"] = df["ctx_front_ratio"] * df["ctx_prev_le3"].fillna(0)
    # 枠隣接(escape sandwich / front_neighbors)
    le3 = df["ctx_prev_le3"].fillna(0).values
    waku = df["wakuban"].values
    rid = df["race_id"].values
    esc = np.zeros(len(df)); nbr = np.zeros(len(df))
    # race単位で枠→le3 マップを作り隣接枠を見る
    from collections import defaultdict
    race_idx = defaultdict(list)
    for i in range(len(df)):
        race_idx[rid[i]].append(i)
    for ridx, idxs in race_idx.items():
        wk = {int(waku[i]): le3[i] for i in idxs if not np.isnan(waku[i])}
        for i in idxs:
            w0 = waku[i]
            if np.isnan(w0):
                continue
            w0 = int(w0)
            left = wk.get(w0 - 1, 0.0); right = wk.get(w0 + 1, 0.0)
            cnt = left + right
            nbr[i] = cnt
            esc[i] = 1.0 if (cnt >= 1 and le3[i] == 0.0) else 0.0
    df["ctx_escape_sandwich"] = esc
    df["ctx_front_neighbors"] = nbr
    return df


def main():
    if sys.platform == "win32":
        try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception: pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--save-only", action="store_true")
    args = ap.parse_args()

    print("[load] splits + history_cache ...")
    splits = {n: pd.read_pickle(SPLITS / f"{n}.pkl") for n in ["train", "val", "test"]}
    hist = json.load(open(HIST, encoding="utf-8"))
    tl = build_horse_timeline(hist)
    print(f"  horses with timeline: {len(tl):,}")

    for n, df in splits.items():
        d2 = add_context(df, tl)
        cov = d2["ctx_prev_le3"].notna().mean()
        print(f"  [{n}] ctx added, prev_le3 cov={cov*100:.1f}%, fr mean={d2['ctx_front_ratio'].mean():.3f}")
        d2.to_pickle(SPLITS / f"{n}_ctx.pkl")
        splits[n] = d2
    if args.save_only:
        print("[done] saved *_ctx.pkl"); return 0

    # ablation: 3歳上芝OP+ で lean_plus vs lean_plus+context
    def age3op(df):
        d = filter_turf_op(df, "_")
        return d[d["age"] >= 3] if "age" in d.columns else d
    tr, va, te = age3op(splits["train"]), age3op(splits["val"]), age3op(splits["test"])

    lines = ["# Regulus context(front_ratio系) incremental AUC — 3歳上芝OP+ (Session 177)",
             f"eval: {te['race_id'].nunique()} races / {len(te)} entries",
             "lean_plus 基準に context 5特徴量を上乗せして AUC が上がるか.\n"]
    for target in ["w", "p"]:
        label = "is_top3" if target == "p" else "is_win"
        params = PARAMS_P if target == "p" else PARAMS_W
        base_all = [f for f in FEATURE_COLS_ALL if f not in MARKET_FEATURES]
        if target == "w":
            base_all = [f for f in base_all if f not in P_ONLY_FEATURES]
        base_all = [f for f in base_all if f in tr.columns]
        groups = assign_groups(base_all)
        lean = [f for g in LEAN_PLUS if g in groups for f in groups[g]]

        r0 = fit_eval(tr, va, te, lean, params, label)
        r1 = fit_eval(tr, va, te, lean + CTX_COLS, params, label)
        lines.append(f"## target={target.upper()}")
        lines.append("| 構成 | n_feat | AUC | ΔAUC | ECE | ROI | 勝率 |")
        lines.append("|---|---|---|---|---|---|---|")
        lines.append(f"| lean_plus | {r0['n_feats']} | {r0['auc']:.4f} | — | {r0['ece_cal']:.4f} | {r0['roi']:.0f}% | {r0['winrate']}% |")
        lines.append(f"| +context | {r1['n_feats']} | {r1['auc']:.4f} | {r1['auc']-r0['auc']:+.4f} | {r1['ece_cal']:.4f} | {r1['roi']:.0f}% | {r1['winrate']}% |\n")

    out = config.ml_dir() / "nova" / "turf_op" / "context_ablation.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"[done] wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
