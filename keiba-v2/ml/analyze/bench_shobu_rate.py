#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""勝負レート(単勝)検証ハーネス (Session 166)

★問い★: 「勝負条件 (tansho_H 4条件) のレースだけ単勝を厚く・他は薄く」は
        『単勝を全レース一律に同額』より得か?

★設計 (ふくだ確定 2026-06-20 / docs/shobu_rate_sizing_design.md)★:
  - 発火条件: rank_w=1 ∧ win_vb_gap>=3 ∧ win_ev>=1.3 ∧ predicted_margin<=60
  - 勝負R: 単勝を厚く (SHOBU_STAKE) / 他R: 薄く (BASE_STAKE) ※見送りはしない
  - 比較: 単勝を全R一律 (総額を揃えて算出)

★母集団の定義が肝★。「他R」の単勝を何に賭けるか3パターン:
  A: ◎(rank_w=1)の単勝を毎レース (薄く広く)
  B: ◎の単勝を「人気とのズレ>=1」のレースのみ
  C: 勝負R以外は賭けない (= 勝負Rだけ単勝)

★結論 (この bench が出した・docs §3.1)★: C (勝負Rだけ) が唯一プラス。
  薄くても他Rの単勝が全体を食う。 → shobu_rate は「単勝は勝負Rだけ」を採用。

実行: python -m ml.analyze.bench_shobu_rate
"""
from collections import defaultdict
from statistics import median, pstdev

from ml.utils.backtest_cache import load_backtest_cache

BASE_STAKE = 100
SHOBU_STAKE = 600


def is_shobu(e):
    rw = e.get("rank_w") or 99
    gap = e.get("win_vb_gap") or 0
    ev = e.get("win_ev") or 0
    m = e.get("predicted_margin")
    m = 999 if m is None else m
    return rw <= 1 and gap >= 3 and ev >= 1.3 and m <= 60


def axis_entry(race):
    for e in race["entries"]:
        if (e.get("rank_w") or 99) == 1 and (e.get("odds") or 0) > 0:
            return e
    return None


def settle(stake, e):
    odds = e.get("odds") or 0
    if odds <= 0:
        return 0, 0
    return stake, (odds * stake if e.get("is_win") else 0)


def run_pop(races, pop_filter, label):
    targets = []
    for race in races:
        rid = str(race["race_id"])
        if len(rid) < 8:
            continue
        ym = f"{rid[:4]}-{rid[4:6]}"
        ax = axis_entry(race)
        if ax is None:
            continue
        shobu = is_shobu(ax)
        if shobu or pop_filter(race, ax):
            targets.append((rid, ym, ax, shobu))

    def acc(stake_fn):
        stake = pay = hit = 0
        month = defaultdict(lambda: [0, 0])
        for rid, ym, e, shobu in targets:
            s, p = settle(stake_fn(shobu), e)
            stake += s
            pay += p
            if p > 0:
                hit += 1
            month[ym][0] += s
            month[ym][1] += p
        rois = [100 * v[1] / v[0] for v in month.values() if v[0]]
        return dict(
            n=len(targets), hit=hit, stake=int(stake), pay=int(pay),
            profit=int(pay - stake), roi=100 * pay / stake if stake else 0,
            m_med=median(rois) if rois else 0,
            m_std=pstdev(rois) if len(rois) > 1 else 0,
            m_win=sum(1 for r in rois if r >= 100), m_total=len(rois))

    sr = acc(lambda shobu: SHOBU_STAKE if shobu else BASE_STAKE)
    flat_each = max(100, round(sr["stake"] / max(1, len(targets)) / 100) * 100)
    fl = acc(lambda shobu: flat_each)
    return label, flat_each, sr, fl


def print_pop(label, flat_each, sr, fl):
    print("=" * 64)
    print(f"母集団: {label}  (母数 {sr['n']}件)")
    print(f"  勝負レート(勝負{SHOBU_STAKE}/他{BASE_STAKE}): 収支{sr['profit']:+,} "
          f"ROI{sr['roi']:.1f}% 月中央{sr['m_med']:.0f}%(黒{sr['m_win']}/{sr['m_total']}・σ{sr['m_std']:.0f})")
    print(f"  一律(各{flat_each}円): 収支{fl['profit']:+,} "
          f"ROI{fl['roi']:.1f}% 月中央{fl['m_med']:.0f}%(黒{fl['m_win']}/{fl['m_total']}・σ{fl['m_std']:.0f})")
    diff = sr["profit"] - fl["profit"]
    print(f"  >>> 勝負レートの収支差: {diff:+,}円 ({'得' if diff>0 else '損' if diff<0 else '同'})")


def main():
    races = load_backtest_cache()
    print(f"\n[設定] 勝負R単勝={SHOBU_STAKE}円 / 他R単勝={BASE_STAKE}円\n")
    print_pop(*run_pop(races, lambda r, e: True, "A: ◎単勝を毎レース"))
    print_pop(*run_pop(races, lambda r, e: (e.get("win_vb_gap") or 0) >= 1,
                       "B: ◎単勝(人気ズレ>=1のみ)"))
    print_pop(*run_pop(races, lambda r, e: False, "C: 勝負Rだけ単勝(他は賭けない)"))


if __name__ == "__main__":
    main()
