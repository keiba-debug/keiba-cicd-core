#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""勝負条件 (単勝一本 tansho_H) の実態プロファイル (Session 166)

★目的★: shobu_rate サイザーの発火条件 = tansho_H 4条件 (rank_w◎) の実態を可視化し、
  「勝負レート」設計の土台数字を出す。 docs/shobu_rate_sizing_design.md §2.2 の出典。

★出すもの★: 件数 / 出現頻度 (R/日) / 的中率 / Flat ROI / オッズ帯分布 / 月別ばらつき。

★勝負条件 (4つ全部)★: rank_w=1 ∧ win_vb_gap>=3 ∧ win_ev>=1.3 ∧ predicted_margin<=60。

実行: python -m ml.analyze.profile_shobu_condition
"""
from collections import defaultdict
from statistics import median

from ml.utils.backtest_cache import load_backtest_cache

# tansho_H 条件 (= bettype_sizing.SHOBU_* と同値・SSoT はあちら)
MAX_RANK_W = 1
MIN_GAP = 3
MIN_EV = 1.3
MAX_MARGIN = 60


def passes(e):
    rw = e.get("rank_w") or 99
    gap = e.get("win_vb_gap") or 0
    ev = e.get("win_ev") or 0
    margin = e.get("predicted_margin")
    margin = 999 if margin is None else margin
    return rw <= MAX_RANK_W and gap >= MIN_GAP and ev >= MIN_EV and margin <= MAX_MARGIN


def odds_band(o):
    if o < 2.0:
        return "1.x"
    if o < 3.0:
        return "2.x"
    if o < 5.0:
        return "3-4.x"
    if o < 7.0:
        return "5-6.x"
    if o < 10.0:
        return "7-9.x"
    if o < 20.0:
        return "10-19"
    return "20+"


def main():
    races = load_backtest_cache()
    dates = set()
    bets = []
    by_month = defaultdict(list)
    band_count = defaultdict(int)
    band_hit = defaultdict(int)

    for race in races:
        rid = str(race["race_id"])
        if len(rid) < 8:
            continue
        ym = f"{rid[:4]}-{rid[4:6]}"
        dates.add(rid[:8])
        for e in race["entries"]:
            if not passes(e):
                continue
            odds = e.get("odds") or 0
            if odds <= 0:
                continue
            is_win = bool(e.get("is_win"))
            payout = odds * 100 if is_win else 0
            bets.append((rid, odds, is_win, payout))
            by_month[ym].append((100, payout))
            band = odds_band(odds)
            band_count[band] += 1
            if is_win:
                band_hit[band] += 1

    n = len(bets)
    if n == 0:
        print("勝負条件該当なし")
        return
    n_hit = sum(1 for b in bets if b[2])
    total_stake = n * 100
    total_pay = sum(b[3] for b in bets)
    n_days = len(dates)
    n_race_days = len({b[0][:8] for b in bets})

    print("=" * 60)
    print(f"backtest_cache 総レース数: {len(races):,} / 全開催日数: {n_days}")
    print("=" * 60)
    print(f"勝負条件 (tansho_H) 件数: {n}")
    print(f"  全開催日あたり: {n / n_days:.2f} R/日 / 出た日あたり: {n / n_race_days:.2f} R")
    print(f"的中: {n_hit}/{n} = {100*n_hit/n:.1f}%")
    print(f"Flat ROI: {100*total_pay/total_stake:.1f}% "
          f"(賭け{total_stake:,}円 → 払戻{int(total_pay):,}円)")
    print("\n--- オッズ帯分布 ---")
    for band in ["1.x", "2.x", "3-4.x", "5-6.x", "7-9.x", "10-19", "20+"]:
        c = band_count[band]
        if c == 0:
            continue
        h = band_hit[band]
        print(f"  {band:>6}: {c:4d}件 ({100*c/n:4.1f}%) 的中{h:3d} ({100*h/c:4.1f}%)")
    print("\n--- 月別 Flat ROI ---")
    monthly = []
    for ym in sorted(by_month):
        rows = by_month[ym]
        stake = sum(r[0] for r in rows)
        pay = sum(r[1] for r in rows)
        roi = 100 * pay / stake if stake else 0
        monthly.append(roi)
        hm = sum(1 for r in rows if r[1] > 0)
        print(f"  {ym}: {len(rows):3d}件 的中{hm:2d} ROI {roi:6.1f}%")
    if monthly:
        win = sum(1 for r in monthly if r >= 100)
        print(f"\n月別ROI 中央値 {median(monthly):.1f}% / 最小 {min(monthly):.1f}% / "
              f"最大 {max(monthly):.1f}% / 100%超 {win}/{len(monthly)}ヶ月")


if __name__ == "__main__":
    main()
