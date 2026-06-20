#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""高ARD穴押さえフォーメーション backtest (Session 169 / ふくだ東京10R 4万馬券の検証)

仮説: 混戦レースで「単勝高オッズ(市場が見限る)だがモデルARDが高い(妙味穴)」馬を
  三連複フォーメーションの押さえに足すと、固い◎-相手3より総収支が良い(天井を取れる)。

比較 (三連複・実払戻 haraimodoshi・per100 flat):
  baseline : ◎(rank_w=1) + 相手3(rank_p上位3) の box  = C(3,2)=3 点
  treatment: baseline + ◎-相手-穴 の組合せ (穴=高ARDクラスタ ∩ odds[ANA_LO,ANA_HI])

出力: cost/payout/ROI/的中R%/≥1000%R数/平均点数 を baseline vs treatment、
  さらに「穴を足した増分(treatment-baseline)」の限界ROIで「押さえは元が取れるか」を見る。
  全R版 + 混戦R版(ARD上位クラスタ>=MIN_CLUSTER頭) の両方。

精算は haraimodoshi(実結果) なのでリークなし。穴選定は pre-race ARD/odds(リークなし)。

CLI:
  python -m ml.analyze.bench_ana_formation
  python -m ml.analyze.bench_ana_formation --ana-lo 20 --ana-hi 100 --partners 3 --ana-max 2
"""
from __future__ import annotations
import argparse
import json
import sys
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import config  # noqa: E402
from ml.analyze.backtest_bet_templates import load_haraimodoshi  # noqa: E402

STAKE = 100  # per point


@dataclass
class Agg:
    n_races: int = 0
    cost: float = 0.0
    payout: float = 0.0
    hit_races: int = 0
    big_races: int = 0   # 払戻/cost >= 10 (≥1000%)
    n_points: int = 0

    def add(self, cost, payout, npts):
        if cost <= 0:
            return
        self.n_races += 1
        self.cost += cost
        self.payout += payout
        self.n_points += npts
        if payout > 0:
            self.hit_races += 1
        if payout >= cost * 10:
            self.big_races += 1

    @property
    def roi(self):
        return self.payout / self.cost * 100 if self.cost else 0.0


def _settle(tickets, race_pay):
    """tickets: set[frozenset(3 umaban)] → (payout円, hit_count)。 per100 flat。"""
    table = (race_pay or {}).get("sanrenpuku") or {}
    payout = 0.0
    for t in tickets:
        per100 = table.get(t, 0)
        if per100:
            payout += STAKE / 100.0 * per100
    return payout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ana-lo", type=float, default=20.0)
    ap.add_argument("--ana-hi", type=float, default=100.0)
    ap.add_argument("--partners", type=int, default=3)
    ap.add_argument("--ana-max", type=int, default=2, help="押さえに足す穴の最大頭数")
    ap.add_argument("--ard-gap", type=float, default=5.0, help="ARD上位クラスタ判定 (max-ARD<=gap)")
    ap.add_argument("--min-cluster", type=int, default=3, help="混戦判定: クラスタ頭数>=")
    args = ap.parse_args()

    cache = json.loads((config.ml_dir() / "backtest_cache.json").read_text(encoding="utf-8"))
    race_ids = [str(r["race_id"]) for r in cache]
    print(f"cache races: {len(race_ids)}  / loading haraimodoshi...")
    hp = load_haraimodoshi(race_ids)
    print(f"haraimodoshi: {len(hp)} races")

    base_all, trt_all = Agg(), Agg()
    base_kon, trt_kon = Agg(), Agg()       # 混戦のみ
    base_anaR, trt_anaR = Agg(), Agg()     # 穴が実在したレースのみ
    n_with_ana = 0

    for race in cache:
        rid = str(race["race_id"])
        race_pay = hp.get(rid)
        if not race_pay or not race_pay.get("sanrenpuku"):
            continue
        ents = [e for e in race["entries"]
                if e.get("umaban") and e.get("ar_deviation") is not None and e.get("odds")]
        if len(ents) < 4:
            continue
        ards = [e["ar_deviation"] for e in ents]
        amax = max(ards)
        cluster = [e for e in ents if amax - e["ar_deviation"] <= args.ard_gap]
        is_kon = len(cluster) >= args.min_cluster

        # axis = rank_w==1 (◎)。無ければ ARD 最大
        axis_e = next((e for e in ents if e.get("rank_w") == 1), None)
        if axis_e is None:
            axis_e = max(ents, key=lambda e: e["ar_deviation"])
        axis = axis_e["umaban"]

        # 相手 = rank_p 上位 (axis 除く)
        partners = [e["umaban"] for e in sorted(ents, key=lambda e: (e.get("rank_p") or 99))
                    if e["umaban"] != axis][:args.partners]
        if len(partners) < 2:
            continue

        # 穴 = 高ARDクラスタ ∩ odds[lo,hi] \ {axis,partners}, ARD降順 top ana_max
        used = {axis, *partners}
        ana = [e["umaban"] for e in sorted(cluster, key=lambda e: -e["ar_deviation"])
               if e["umaban"] not in used
               and args.ana_lo <= e["odds"] <= args.ana_hi][:args.ana_max]

        # baseline tickets: 三連複 {axis} + 2 of partners
        base_t = {frozenset((axis, a, b)) for a, b in combinations(partners, 2)}
        # treatment: baseline + {axis, partner, ana}
        trt_t = set(base_t)
        for an in ana:
            for p in partners:
                trt_t.add(frozenset((axis, p, an)))

        base_cost = len(base_t) * STAKE
        trt_cost = len(trt_t) * STAKE
        base_pay = _settle(base_t, race_pay)
        trt_pay = _settle(trt_t, race_pay)

        base_all.add(base_cost, base_pay, len(base_t))
        trt_all.add(trt_cost, trt_pay, len(trt_t))
        if is_kon:
            base_kon.add(base_cost, base_pay, len(base_t))
            trt_kon.add(trt_cost, trt_pay, len(trt_t))
        if ana:
            n_with_ana += 1
            base_anaR.add(base_cost, base_pay, len(base_t))
            trt_anaR.add(trt_cost, trt_pay, len(trt_t))

    def row(label, a):
        avg_pts = a.n_points / a.n_races if a.n_races else 0
        return (f"{label:<26}{a.n_races:>6}{avg_pts:>7.1f}{a.cost:>11,.0f}{a.payout:>13,.0f}"
                f"{a.roi:>8.1f}%{a.hit_races/a.n_races*100 if a.n_races else 0:>7.1f}%"
                f"{a.big_races:>8}")

    hdr = f"{'群':<26}{'R数':>6}{'平均点':>7}{'cost':>11}{'payout':>13}{'ROI':>8}{'的中R':>8}{'≥1000R':>8}"
    print(f"\nana=高ARD(max-{args.ard_gap})∩odds[{args.ana_lo:.0f},{args.ana_hi:.0f}] / partners={args.partners} / ana_max={args.ana_max}")
    print("="*len(hdr))
    print(hdr)
    print("-"*len(hdr))
    print(row("[全R] baseline ◎-相手3", base_all))
    print(row("[全R] +穴押さえ", trt_all))
    print(row(f"[混戦R≥{args.min_cluster}] baseline", base_kon))
    print(row(f"[混戦R≥{args.min_cluster}] +穴押さえ", trt_kon))
    print(row("[穴実在R] baseline", base_anaR))
    print(row("[穴実在R] +穴押さえ", trt_anaR))
    print("-"*len(hdr))
    # 限界ROI: 穴を足した増分だけ
    dcost = trt_anaR.cost - base_anaR.cost
    dpay = trt_anaR.payout - base_anaR.payout
    print(f"\n穴実在R={n_with_ana}  穴押さえ増分: cost+{dcost:,.0f} payout+{dpay:,.0f} "
          f"→ 限界ROI {dpay/dcost*100 if dcost else 0:.1f}% (穴legだけの元取り)")


if __name__ == "__main__":
    main()
