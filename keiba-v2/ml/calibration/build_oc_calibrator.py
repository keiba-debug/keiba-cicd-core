#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""道P: 現行 polaris(v2.3) のOOS期間(2025)で cal_p_oc を学習・評価する (Session 150)。

evaluate_period --dump-dataset で保存した (raw+結果+オッズ) pickle を読み、
直前オッズ(T-5)を join して OddsConditionedCalibrator を fit する。
2025 は v2.3 の学習外(train cutoff=2024-10)なので正当なOOS。 時系列オッズも 2025 から有る。

時系列分割: 前半(< --split)で fit / 後半(>= --split)で eval。
比較: baseline raw / cal_p(Isotonic 既存) / cal_p_oc(新) のオッズ帯別乖離・ECE。
--save: 効果確認後 calibrators.pkl に cal_p_oc を同梱 (バックアップ付き)。

CLI: python -m ml.calibration.build_oc_calibrator [--cutoff 5] [--split 20250701]
                                                  [--cutoff-only] [--save]
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from ml.calibration.odds_conditioned import OddsConditionedCalibrator  # noqa: E402

BANDS = ["<2.9", "3-9.9", "10-49.9", "50+"]


def _band(od):
    return "<2.9" if od < 3 else "3-9.9" if od < 10 else "10-49.9" if od < 50 else "50+"


def _slots(n):
    return 0 if n <= 4 else (2 if n <= 7 else 3)


def _ece(p, y, nb=10):
    p = np.asarray(p, dtype=float)
    y = np.asarray(y, dtype=float)
    edges = np.linspace(0, 1, nb + 1)
    n = len(p)
    s = 0.0
    for i in range(nb):
        m = (p >= edges[i]) & (p < edges[i + 1]) if i < nb - 1 else (p >= edges[i]) & (p <= 1.0)
        if m.sum():
            s += abs(p[m].mean() - y[m].mean()) * m.sum() / n
    return s


def _save_cal_p_oc(cal):
    import pickle
    import shutil
    from core import config
    candidates = [
        config.ml_dir() / "models" / "polaris" / "live" / "calibrators.pkl",
        config.ml_dir() / "calibrators.pkl",
    ]
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        print(f"[save] calibrators.pkl が見つからない: {candidates}")
        return
    with open(path, "rb") as f:
        cals = pickle.load(f)
    shutil.copy2(path, str(path) + ".bak_s150")
    cals["cal_p_oc"] = cal
    with open(path, "wb") as f:
        pickle.dump(cals, f)
    print(f"[save] cal_p_oc → {path}  (keys={list(cals.keys())}, backup .bak_s150)")


def main():
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    ap = argparse.ArgumentParser(description="cal_p_oc 学習・評価 (道P)")
    ap.add_argument("--dataset", default="C:/KEIBA-CICD/data3/ml/oc_calib_2025.pkl")
    ap.add_argument("--cutoff", type=int, default=5, help="発走N分前の直前オッズ")
    ap.add_argument("--split", default="20250701", help="train/valid 分割日 YYYYMMDD")
    ap.add_argument("--cutoff-only", action="store_true",
                    help="直前オッズが時系列で取れた馬のみ(確定fallback除外)")
    ap.add_argument("--save", action="store_true", help="calibrators.pkl に cal_p_oc を同梱")
    args = ap.parse_args()

    df = pd.read_pickle(args.dataset)
    df["race_id"] = df["race_id"].astype(str)
    df["date"] = df["race_id"].str[:8]
    print(f"dataset: {len(df):,} rows, {df['race_id'].nunique():,} races, "
          f"date {df['date'].min()}-{df['date'].max()}")

    starters = df[df["finish_position"] > 0].groupby("race_id").size()
    df["starters"] = df["race_id"].map(starters).fillna(0).astype(int)
    df["slots"] = df["starters"].apply(_slots)
    df = df[(df["finish_position"] > 0) & (df["slots"] > 0)].copy()
    df["y"] = (df["finish_position"] <= df["slots"]).astype(int)

    from core import odds_db
    rids = df["race_id"].unique().tolist()
    co = odds_db.batch_get_win_odds_at_cutoff(rids, minutes_before=args.cutoff)
    odds_cut, odds_src = [], []
    for rid, um in zip(df["race_id"], df["umaban"]):
        e = co.get(rid, {}).get(int(um))
        odds_cut.append(e.get("odds") if e else None)
        odds_src.append(e.get("source") if e else None)
    df["odds_cut"] = odds_cut
    df["odds_src"] = odds_src
    print(f"直前オッズ source 内訳: {df['odds_src'].value_counts(dropna=False).to_dict()}")
    df = df[df["odds_cut"].notna() & (df["odds_cut"] > 0)].copy()
    if args.cutoff_only:
        df = df[df["odds_src"] == "cutoff"].copy()
        print(f"cutoff-only(fallback除外): {len(df):,} rows")

    tr = df[df["date"] < args.split]
    va = df[df["date"] >= args.split].copy()
    print(f"train(<{args.split})={len(tr):,}  valid(>={args.split})={len(va):,}  "
          f"複勝支払い率 train={tr['y'].mean():.3f} valid={va['y'].mean():.3f}")
    if len(tr) < 500 or len(va) < 500:
        print("[ERR] train/valid サンプル不足")
        return 1

    cal = OddsConditionedCalibrator().fit(
        tr["pred_proba_p_raw"].values, tr["odds_cut"].values, tr["y"].values)
    print(f"\ncal_p_oc: {cal!r}")

    va["p_raw"] = va["pred_proba_p_raw"].clip(1e-4, 1 - 1e-4)
    va["p_calp"] = va["pred_proba_p"]
    va["p_oc"] = cal.predict(va["pred_proba_p_raw"].values, va["odds_cut"].values)
    va["band"] = va["odds_cut"].apply(_band)

    print("\n=== valid(OOS後半) オッズ帯別乖離 (予測-実現, マイナス=過小) ===")
    print(f"  {'モデル':<18}" + "".join(f"{b:>11}" for b in BANDS) + f"{'ECE':>9}")
    for name, col in [("baseline raw(現状)", "p_raw"), ("cal_p (Isotonic)", "p_calp"),
                      ("cal_p_oc ★", "p_oc")]:
        cells = []
        for b in BANDS:
            m = va["band"] == b
            cells.append(f"{(va.loc[m, col].mean() - va.loc[m, 'y'].mean()):+.3f}"
                         if m.sum() else "-")
        print(f"  {name:<18}" + "".join(f"{c:>11}" for c in cells)
              + f"{_ece(va[col].values, va['y'].values):>9.4f}")
    print("  帯別 n / 実複勝率: " + "  ".join(
        f"{b}:n={ (va['band'] == b).sum() },{va.loc[va['band'] == b, 'y'].mean():.3f}"
        for b in BANDS if (va["band"] == b).sum()))

    if args.save:
        _save_cal_p_oc(cal)
    return 0


if __name__ == "__main__":
    sys.exit(main())
