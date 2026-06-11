#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""崖カット (assign_ai_marks step2) の感度診断 (Session 149)

S144 の「序列=composite・頭数=複勝率(P)の崖」が、 backtest_cache 全レースで
印数分布をどう出すか。 崖指標 (P=複勝率 / W=勝率 / composite-z) × しきい値を振り、
「どの指標・どのしきい値ならまともに頭数が絞れるか」を一望する。

DB 非依存 (assign_ai_marks / 簡易崖は entries の pred_proba_* のみ使用)。

CLI: python -m ml.analyze.check_cliff_ratio
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import ml.ai_marks.assign as A  # noqa: E402
from ml.analyze.backtest_bettype_fund import cache_race_to_pred  # noqa: E402
from ml.utils.backtest_cache import load_backtest_cache  # noqa: E402

MARK_MAX = 5


def _robust_z(vals):
    present = [v for v in vals if v is not None]
    if not present:
        return [0.0] * len(vals)
    med = median(present)
    filled = [med if v is None else v for v in vals]
    devs = sorted(abs(v - med) for v in filled)
    mad = devs[len(devs) // 2] if devs else 0.0
    if mad > 0:
        return [(v - med) / (1.4826 * mad) for v in filled]
    n = len(filled)
    mean = sum(filled) / n
    sd = (sum((v - mean) ** 2 for v in filled) / n) ** 0.5
    return [(v - mean) / sd for v in filled] if sd > 0 else [0.0] * n


def _ranked_values(entries, key):
    """composite 降順の順で、 指定キーの値 (崖判定対象) を返す。"""
    umab = [int(e["umaban"]) for e in entries if e.get("umaban") is not None]
    by = {int(e["umaban"]): e for e in entries if e.get("umaban") is not None}

    def col(k):
        return [float(by[u].get(k)) if isinstance(by[u].get(k), (int, float)) else None
                for u in umab]
    zc = [a + b + c for a, b, c in zip(
        _robust_z(col("pred_proba_w_cal")), _robust_z(col("pred_proba_p")),
        _robust_z(col("ar_deviation")))]
    order = sorted(range(len(umab)), key=lambda i: -zc[i])
    p = col("pred_proba_p")
    w = col("pred_proba_w_cal")
    p_med = median([x for x in p if x is not None]) if any(x is not None for x in p) else 0.0
    w_med = median([x for x in w if x is not None]) if any(x is not None for x in w) else 0.0
    return {
        "P": [p[i] if p[i] is not None else p_med for i in order],
        "W": [w[i] if w[i] is not None else w_med for i in order],
        "Z": [zc[i] for i in order],
    }


def _count_marks_ratio(vals, ratio):
    """比ベースの崖 (P/W 用)。 prev/cur >= ratio で打ち切り。"""
    cap = min(MARK_MAX, max(1, len(vals) - 1))
    n = 1
    for i in range(1, cap):
        prev, cur = vals[i - 1], vals[i]
        if cur <= 0 or prev / cur >= ratio:
            break
        n += 1
    return n


def _count_marks_gap(vals, gap):
    """差ベースの崖 (composite-z 用)。 prev-cur >= gap で打ち切り。"""
    cap = min(MARK_MAX, max(1, len(vals) - 1))
    n = 1
    for i in range(1, cap):
        if vals[i - 1] - vals[i] >= gap:
            break
        n += 1
    return n


def _dist(preds, key, thresh, mode):
    dist = {}
    for rv in preds:
        vals = rv[key]
        if mode == "ratio":
            k = _count_marks_ratio(vals, thresh)
        else:
            k = _count_marks_gap(vals, thresh)
        dist[k] = dist.get(k, 0) + 1
    tot = sum(dist.values())
    avg = sum(k * v for k, v in dist.items()) / tot
    five = dist.get(5, 0) / tot * 100
    ds = " ".join(f"{k}:{v}" for k, v in sorted(dist.items()))
    return avg, five, ds


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    races = load_backtest_cache()
    rvs = []
    for r in races:
        pred = cache_race_to_pred(r)
        if pred is None:
            continue
        ents = [e for e in pred.get("entries", []) if e.get("umaban") is not None]
        if len(ents) < 3:
            continue
        rvs.append(_ranked_values(ents, None))
    print(f"races={len(rvs)}  現行: 指標=P(複勝率) 比 CLIFF_RATIO={A.CLIFF_RATIO}\n")

    print("  --- 複勝率 P の比 (現行指標) ---")
    print(f"  {'ratio':>6}{'avg印':>7}{'5印%':>7}  分布")
    for t in [1.15, 1.2, 1.3, 1.5, 1.8, 2.0, 2.5]:
        avg, five, ds = _dist(rvs, "P", t, "ratio")
        print(f"  {t:>6.2f}{avg:>7.2f}{five:>6.0f}%  [{ds}]")

    print("\n  --- 勝率 W の比 (代替指標) ---")
    print(f"  {'ratio':>6}{'avg印':>7}{'5印%':>7}  分布")
    for t in [1.3, 1.5, 1.8, 2.0, 2.5, 3.0]:
        avg, five, ds = _dist(rvs, "W", t, "ratio")
        print(f"  {t:>6.2f}{avg:>7.2f}{five:>6.0f}%  [{ds}]")

    print("\n  --- composite-z の差 gap (代替指標) ---")
    print(f"  {'gap':>6}{'avg印':>7}{'5印%':>7}  分布")
    for t in [0.3, 0.5, 0.7, 1.0, 1.3]:
        avg, five, ds = _dist(rvs, "Z", t, "gap")
        print(f"  {t:>6.2f}{avg:>7.2f}{five:>6.0f}%  [{ds}]")

    print("\n  ※ 5印% が下がる = 頭数がちゃんと絞れている。 現行 P比2.5 は崖がほぼ立たず5印に張り付く。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
