#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""回顧(kaiko) A/B 実験の結果比較 (Session 169)

experiment.py --no-save が ml/experiments/result_{version}.json に吐いた
複数の実験結果を読み、P/W AUC・gap別VB ROI・ブートCI を横並びで表示する。

使い方:
  python -m ml.analyze.compare_kaiko_ab kaiko-base kaiko-A kaiko-AB
  （引数 = 比較したい version 文字列。第1引数を baseline 扱いして差分を出す）
"""
import json
import sys
from core import config


def _load(version: str) -> dict:
    p = config.ml_dir() / "experiments" / f"result_{version}.json"
    if not p.exists():
        print(f"  [MISSING] {p}")
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _auc(r, model):
    return r.get("models", {}).get(model, {}).get("metrics", {}).get("auc")


def _feat_count(r, model):
    return r.get("models", {}).get(model, {}).get("feature_count")


def _vb_rows(r):
    """{(side, gap): (roi, n_bet, n_races, ci_low, ci_high)}"""
    out = {}
    vb = r.get("value_bets", {})
    for row in vb.get("by_rank_gap", []) or []:
        g = row.get("min_gap")
        out[("place", g)] = (row.get("place_roi"), row.get("bet_count"),
                             row.get("race_count"))
    for row in vb.get("win_by_rank_gap", []) or []:
        g = row.get("min_gap")
        out[("win", g)] = (row.get("win_roi") or row.get("roi"),
                           row.get("bet_count"), row.get("race_count"))
    # bootstrap CI
    for side, key in (("place", "bootstrap_ci_place"), ("win", "bootstrap_ci_win")):
        for row in vb.get(key, []) or []:
            g = row.get("min_gap")
            lo = row.get("ci_low") or row.get("roi_ci_low")
            hi = row.get("ci_high") or row.get("roi_ci_high")
            if (side, g) in out:
                out[(side, g)] = out[(side, g)] + (lo, hi)
    return out


def main():
    versions = sys.argv[1:]
    if not versions:
        print("usage: python -m ml.analyze.compare_kaiko_ab <ver1> <ver2> ...")
        sys.exit(1)

    results = {v: _load(v) for v in versions}
    results = {v: r for v, r in results.items() if r}
    if not results:
        print("no results found")
        sys.exit(1)

    base = versions[0]

    print(f"\n{'='*78}")
    print(f"  回顧(kaiko) A/B 比較 — baseline = {base}")
    print(f"{'='*78}")

    # --- AUC / feature count ---
    print(f"\n{'version':<14}{'P feat':>8}{'P AUC':>10}{'ΔP':>9}{'W feat':>8}{'W AUC':>10}{'ΔW':>9}")
    base_pa = _auc(results[base], "place")
    base_wa = _auc(results[base], "win")
    for v in versions:
        r = results.get(v)
        if not r:
            continue
        pa, wa = _auc(r, "place"), _auc(r, "win")
        dpa = (pa - base_pa) if (pa is not None and base_pa is not None) else None
        dwa = (wa - base_wa) if (wa is not None and base_wa is not None) else None
        ds = lambda x: f"{x:+.4f}" if x is not None else "   -"
        print(f"{v:<14}{_feat_count(r,'place') or 0:>8}{pa or 0:>10.4f}{ds(dpa):>9}"
              f"{_feat_count(r,'win') or 0:>8}{wa or 0:>10.4f}{ds(dwa):>9}")

    # --- VB ROI by gap ---
    base_vb = _vb_rows(results[base])
    for side in ("place", "win"):
        print(f"\n  [{side.upper()}] VB ROI by gap (baseline={base})")
        print(f"  {'gap':>4} {'version':<14}{'ROI%':>8}{'Δ':>8}{'n_bet':>8}{'races':>7}{'CI(boot)':>20}")
        gaps = sorted({g for (s, g) in base_vb if s == side})
        for g in gaps:
            for v in versions:
                r = results.get(v)
                if not r:
                    continue
                row = _vb_rows(r).get((side, g))
                if not row:
                    continue
                roi, nb, nr = row[0], row[1], row[2]
                ci = ""
                if len(row) >= 5 and row[3] is not None:
                    ci = f"[{row[3]:.1f}, {row[4]:.1f}]"
                broi = base_vb.get((side, g), (None,))[0]
                d = (roi - broi) if (roi is not None and broi is not None) else None
                ds = f"{d:+.1f}" if d is not None else "  -"
                mark = " <-base" if v == base else ""
                print(f"  {g:>4} {v:<14}{(roi or 0):>8.1f}{ds:>8}{nb or 0:>8}{nr or 0:>7}{ci:>20}{mark}")
            print()


if __name__ == "__main__":
    main()
