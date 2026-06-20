#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""勝負Rで◎の複勝を保険に足すか? 検証 (Session 166)

★前提 (ふくだ確定)★: 単勝は勝負R (tansho_H) だけ買う。
★問い★: その勝負Rで◎の複勝を保険に足すと得か?
  単勝のみ(600円) vs 単勝600 + 複勝{100,200,300,600}円。

★結論 (この bench が出した・docs §3.2)★: 複勝を足すほど収支もROIもまっすぐ下がる。
  単勝外れ時に複で取り返せたのは複600円でも僅か → ◎の複勝が安すぎる。 → 複勝は足さない。

複勝は place_odds_min × is_top3 で精算。
実行: python -m ml.analyze.bench_shobu_fukusho_insurance
"""
from collections import defaultdict
from statistics import median, pstdev

from ml.utils.backtest_cache import load_backtest_cache

TANSHO_STAKE = 600


def is_shobu(e):
    rw = e.get("rank_w") or 99
    gap = e.get("win_vb_gap") or 0
    ev = e.get("win_ev") or 0
    m = e.get("predicted_margin")
    m = 999 if m is None else m
    return rw <= 1 and gap >= 3 and ev >= 1.3 and m <= 60


def collect():
    races = load_backtest_cache()
    rows = []
    for race in races:
        rid = str(race["race_id"])
        if len(rid) < 8:
            continue
        ym = f"{rid[:4]}-{rid[4:6]}"
        for e in race["entries"]:
            if is_shobu(e) and (e.get("odds") or 0) > 0:
                rows.append((ym, e.get("odds") or 0, bool(e.get("is_win")),
                             e.get("place_odds_min") or 0, bool(e.get("is_top3"))))
    return rows


def simulate(rows, fuku_stake):
    stake = pay = win_hit = top3_hit = 0
    month = defaultdict(lambda: [0, 0])
    miss_n = miss_rec = 0
    for ym, wo, iswin, po, istop3 in rows:
        s = TANSHO_STAKE + fuku_stake
        p = (wo * TANSHO_STAKE if iswin else 0)
        if fuku_stake > 0 and istop3 and po > 0:
            p += po * fuku_stake
        stake += s
        pay += p
        if iswin:
            win_hit += 1
        if istop3:
            top3_hit += 1
        month[ym][0] += s
        month[ym][1] += p
        if not iswin:
            miss_n += 1
            if fuku_stake > 0 and istop3 and po * fuku_stake >= s:
                miss_rec += 1
    n = len(rows)
    rois = [100 * v[1] / v[0] for v in month.values() if v[0]]
    return dict(
        fuku=fuku_stake, n=n, profit=int(pay - stake),
        roi=100 * pay / stake if stake else 0,
        win_rate=100 * win_hit / n if n else 0,
        top3_rate=100 * top3_hit / n if n else 0,
        m_med=median(rois) if rois else 0, m_std=pstdev(rois) if len(rois) > 1 else 0,
        m_win=sum(1 for r in rois if r >= 100), m_total=len(rois),
        miss_n=miss_n, miss_rec=miss_rec)


def main():
    rows = collect()
    print(f"勝負R (tansho_H) 母数: {len(rows)}件 / 単勝{TANSHO_STAKE}円固定\n")
    print(f"{'複勝':>5} {'収支':>9} {'ROI':>6} {'単的中':>6} {'複圏内':>6} "
          f"{'月中央':>6} {'σ':>4} {'黒月':>5} {'外れ複取返':>9}")
    for fuku in [0, 100, 200, 300, 600]:
        r = simulate(rows, fuku)
        rec = f"{r['miss_rec']}/{r['miss_n']}" if fuku > 0 else "-"
        print(f"{fuku:>5} {r['profit']:>+9,} {r['roi']:>5.1f}% "
              f"{r['win_rate']:>5.1f}% {r['top3_rate']:>5.1f}% "
              f"{r['m_med']:>5.0f}% {r['m_std']:>4.0f} {r['m_win']:>2}/{r['m_total']:<2} {rec:>9}")
    print("\n複勝0=単勝のみ。 足すほど赤字 → 保険は不要 (docs §3.2)。")


if __name__ == "__main__":
    main()
