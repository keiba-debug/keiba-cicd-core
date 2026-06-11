#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""崖指標比較: P崖(現行) vs W崖 vs 固定top5 で頭数を決めテンプレROIを比較 (Session 149)

較正診断で P が人気馬を過小評価と判明 → 崖を P 生で引くと歪む。 W(較正良好 ECE1.1%)で
引く案を主候補に、 現行(P崖2.5)・固定top5 と並べて ai実印 (= 印の付いた馬だけで買う) の
ROI を比較する。 序列は composite 固定、 頭数だけ崖指標で変える。

★検証基本方針 原則3: ブートストラップ95%CI付き・月別中央値・OOS(valid) 併記。
  仮説は事前固定 (W崖2.0 / P崖2.5 / 固定top5 の3つだけ。 総当たり禁止)。
  精算は haraimodoshi 実配当 (確定オッズ=実運用より甘い旨は承知の上)。

CLI: python -m ml.analyze.backtest_cliff_compare --split-date 2026-01-01
"""

from __future__ import annotations

import argparse
import io
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.analyze.backtest_bet_templates import load_haraimodoshi, ticket_payout  # noqa: E402
from ml.analyze.backtest_bettype_fund import cache_race_to_pred  # noqa: E402
from ml.strategies import bet_templates as bt  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.utils.backtest_cache import load_backtest_cache  # noqa: E402

TEMPLATES = ["wide_anchor", "honmei_plus_tansho"]
# 崖指標 (事前固定): 名前 -> (値キー W/P, 比しきい値) / (None,None)=固定top5
CLIFFS = {
    "P崖2.5(現行)": ("P", 2.5),
    "W崖2.0": ("W", 2.0),
    "固定top5": (None, None),
}


def cliff_n(vals, ratio, cap=5):
    """composite 降順に並んだ指標値で、 prev/cur>=ratio の崖まで頭数を返す。"""
    c = min(cap, max(1, len(vals) - 1))
    n = 1
    for i in range(1, c):
        prev, cur = vals[i - 1], vals[i]
        if cur <= 0 or prev / cur >= ratio:
            break
        n += 1
    return n


def _settle(tmpl, marks, rpay):
    cost = payout = 0.0
    for tk in bt.apply_template(bt.get_template(tmpl), marks):
        cost += 100.0 * tk.weight
        p = ticket_payout(tk, rpay)
        if p > 0:
            payout += p * tk.weight
    return cost, payout


def build(races, haraimodoshi):
    recs = []
    nmarks_dist = {c: defaultdict(int) for c in CLIFFS}
    for raw in races:
        pred = cache_race_to_pred(raw)
        if pred is None:
            continue
        if not any(int(e.get("finish_position") or 99) == 1 for e in pred.get("entries", [])):
            continue
        re_ = be.process_race(pred)
        if re_ is None or not re_.strengths:
            continue
        s = re_.strengths  # composite 降順
        umab = [x.umaban for x in s]
        wv = [x.pred_w if x.pred_w is not None else 0.0 for x in s]
        pv = [x.pred_p if x.pred_p is not None else 0.0 for x in s]
        rid = str(pred["race_id"])
        rpay = haraimodoshi.get(rid, {})
        cell = {}
        for cname, (key, thr) in CLIFFS.items():
            if key is None:
                n = min(5, len(umab))
            else:
                n = cliff_n(wv if key == "W" else pv, thr)
            nmarks_dist[cname][n] += 1
            marks = bt.marks_from_ranking(umab[:n])
            for t in TEMPLATES:
                cell[(cname, t)] = _settle(t, marks, rpay)
        recs.append({"date": rid[:8], "cell": cell})
    return recs, nmarks_dist


def agg(recs, key, split, rng):
    pairs = [r["cell"][key] for r in recs if r["cell"][key][0] > 0]
    if not pairs:
        return None
    arr = np.array(pairs, dtype=float)
    cost = arr[:, 0].sum()
    pay = arr[:, 1].sum()
    roi = pay / cost * 100 if cost else 0.0
    # ブートストラップ95%CI (レース単位リサンプリング)
    n = len(arr)
    boot = []
    for _ in range(2000):
        idx = rng.integers(0, n, n)
        c = arr[idx, 0].sum()
        boot.append(arr[idx, 1].sum() / c * 100 if c else 0.0)
    boot.sort()
    lo, hi = boot[50], boot[1949]
    # 月別中央値 + OOS
    monthly = defaultdict(lambda: [0.0, 0.0])
    tr_c = tr_p = va_c = va_p = 0.0
    for r in recs:
        c, p = r["cell"][key]
        if c <= 0:
            continue
        monthly[r["date"][:6]][0] += c
        monthly[r["date"][:6]][1] += p
        if r["date"] < split:
            tr_c += c
            tr_p += p
        else:
            va_c += c
            va_p += p
    mrois = sorted((mp / mc * 100 if mc else 0.0) for mc, mp in monthly.values())
    med = median(mrois) if mrois else 0.0
    plus = sum(1 for x in mrois if x >= 100)
    return dict(fire=len(pairs), roi=roi, lo=lo, hi=hi, median=med,
                plus=f"{plus}/{len(mrois)}", oos=(va_p / va_c * 100 if va_c else 0.0))


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cache-path", default=None)
    ap.add_argument("--split-date", default="2026-01-01")
    args = ap.parse_args()
    split = args.split_date.replace("-", "")

    races = load_backtest_cache(path=Path(args.cache_path) if args.cache_path else None)
    codes = [str(r.get("race_id")) for r in races if r.get("race_id")]
    print(f"backtest_cache: {len(races)} races  split={args.split_date}")
    print("  loading haraimodoshi + building (process_race)...")
    haraimodoshi = load_haraimodoshi(codes)
    recs, nmarks_dist = build(races, haraimodoshi)
    print(f"  records={len(recs)}")
    print("\n  印数分布 (崖指標別):")
    for c in CLIFFS:
        d = nmarks_dist[c]
        tot = sum(d.values())
        avg = sum(k * v for k, v in d.items()) / tot if tot else 0
        print(f"    {c:<14} avg={avg:.2f}  " + " ".join(f"{k}:{v}" for k, v in sorted(d.items())))

    rng = np.random.default_rng(12345)
    for tmpl in TEMPLATES:
        print(f"\n{'='*92}")
        print(f"  ◆ {tmpl}")
        print(f"  {'崖指標':<14}{'fire':>6}{'ROI':>8}{'95%CI':>17}{'中央値':>8}{'OOSvalid':>9}{'+月':>7}")
        print(f"  {'-'*88}")
        for cname in CLIFFS:
            a = agg(recs, (cname, tmpl), split, rng)
            if a is None:
                continue
            ci = f"[{a['lo']:.0f}-{a['hi']:.0f}]"
            print(f"  {cname:<14}{a['fire']:>6}{a['roi']:>7.1f}%{ci:>17}"
                  f"{a['median']:>7.1f}%{a['oos']:>8.1f}%{a['plus']:>7}")
    print(f"\n  {'-'*88}")
    print("  CI=ブートストラップ95% (2000回・レース単位)。 CI下限>100 でなければ「勝ち」とは言えない。")
    print("  ※精算は確定オッズ haraimodoshi (実運用=直前オッズより甘い)。 妙味党系オッズ依存は別途割引。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
