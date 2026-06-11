#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""W(勝率) と P(複勝率) の分離度診断 (Session 149)

「WとPが現状ちゃんと性格分けできてるか」(ふくだ疑惑) を実測する。
WとPが順位的にほぼ同じなら、 崖指標を W/P どちらにしても序列は変わらず
「頭数の切り方」だけの違いになる。 逆に分離していれば
「勝ち切るが崩れる馬 (W高P低)」「来るが勝てない馬 (P高W低)」が居て、
◎ の選び方にも効く。

測るもの:
  - レース内 W vs P のスピアマン順位相関 (平均・分布)
  - W1位 と P1位 の一致率 / composite◎ との一致率
  - 順位が大きく入れ替わる馬 (|rank_w - rank_p| 大) の出現

DB 非依存 (entries の pred_proba_w_cal / pred_proba_p のみ)。
CLI: python -m ml.analyze.check_wp_separation
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from statistics import mean, median

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.analyze.backtest_bettype_fund import cache_race_to_pred  # noqa: E402
from ml.utils.backtest_cache import load_backtest_cache  # noqa: E402


def _ranks_desc(vals):
    """値の降順順位 (1=最高)。 同値は出現順。"""
    order = sorted(range(len(vals)), key=lambda i: -vals[i])
    r = [0] * len(vals)
    for pos, i in enumerate(order):
        r[i] = pos + 1
    return r


def _spearman(a, b):
    n = len(a)
    if n < 2:
        return 1.0
    ra, rb = _ranks_desc(a), _ranks_desc(b)
    d2 = sum((x - y) ** 2 for x, y in zip(ra, rb))
    return 1 - 6 * d2 / (n * (n * n - 1))


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    races = load_backtest_cache()
    corrs = []
    w1_eq_p1 = 0
    swap_top3 = 0     # W上位3 と P上位3 の顔ぶれが違うレース
    big_swap_horses = 0  # |rank_w - rank_p| >= 3 の馬の総数
    total_horses = 0
    n_races = 0
    for r in races:
        pred = cache_race_to_pred(r)
        if pred is None:
            continue
        ents = [e for e in pred.get("entries", []) if e.get("umaban") is not None]
        w = [e.get("pred_proba_w_cal") for e in ents]
        p = [e.get("pred_proba_p") for e in ents]
        keep = [(wv, pv) for wv, pv in zip(w, p)
                if isinstance(wv, (int, float)) and isinstance(pv, (int, float))]
        if len(keep) < 4:
            continue
        wv = [x[0] for x in keep]
        pv = [x[1] for x in keep]
        n_races += 1
        corrs.append(_spearman(wv, pv))
        rw, rp = _ranks_desc(wv), _ranks_desc(pv)
        if rw.index(1) == rp.index(1):
            w1_eq_p1 += 1
        w_top3 = {i for i in range(len(rw)) if rw[i] <= 3}
        p_top3 = {i for i in range(len(rp)) if rp[i] <= 3}
        if w_top3 != p_top3:
            swap_top3 += 1
        for i in range(len(rw)):
            total_horses += 1
            if abs(rw[i] - rp[i]) >= 3:
                big_swap_horses += 1

    print(f"races={n_races}\n")
    print(f"  W vs P スピアマン順位相関:  平均 {mean(corrs):.3f}  中央値 {median(corrs):.3f}")
    print(f"    (1.0=完全に同じ順位 / 0.0=無関係。 0.95+ なら『ほぼ同じもの』)")
    print(f"  分布: " + "  ".join(
        f"{lo:.1f}-{lo+0.1:.1f}:{sum(1 for c in corrs if lo <= c < lo + 0.1)}"
        for lo in [0.7, 0.8, 0.9]) + f"  >=1.0:{sum(1 for c in corrs if c >= 0.999)}")
    print()
    print(f"  W1位 = P1位 の一致率:        {w1_eq_p1 / n_races * 100:.1f}%")
    print(f"  W上位3 ≠ P上位3 のレース:    {swap_top3 / n_races * 100:.1f}% "
          f"(顔ぶれが入れ替わる)")
    print(f"  順位が3つ以上ズレる馬:        {big_swap_horses / total_horses * 100:.1f}% "
          f"(全 {total_horses} 頭中)")
    print()
    print("  → 相関0.95+/一致率高 なら『WとPは実質同じ序列』= 崖指標の W/P 選択は")
    print("     頭数の切り方の違いに留まる。 相関低/入替多 なら性格が分離している。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
