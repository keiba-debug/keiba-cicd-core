#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""妙味穴・単勝枠 シミュレーション (Session 169 / ふくだ「穴単勝枠を走らせてみよう」)

戦略: 混戦で「単勝高オッズ(市場が見限る)だがモデルARDが高い(妙味)」馬を単勝で買う。
  combo/フォメに埋めると妙味が消える (bench_ana_formation で実証) ので "単体の単勝" で捕る。
  天井(≥1000%回収)は固い馬券では構造的に出ない → 穴単勝が天井供給源。

選定 (pre-race・リークなし):
  - 高ARDクラスタ: race_max(ar_deviation) - ARD <= ard_gap
  - 妙味穴: クラスタ ∩ odds[lo,hi] ∩ 非1番人気(odds_rank>=2)
  - 1レース top_k 頭 (ARD降順)
精算: haraimodoshi 単勝 実払戻 (per100)。flat STAKE/点。

時系列順に資産曲線・最大DD・ROI・的中・≥1000%回数・頻度を出す。
複数パラメータを sweep して +EV 帯があるか探す。

CLI: python -m ml.analyze.bench_ana_tansho
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core import config  # noqa: E402
from ml.analyze.backtest_bet_templates import load_haraimodoshi  # noqa: E402

STAKE = 100


def simulate(cache, hp, *, ard_gap, lo, hi, top_k, min_ard=None):
    # 時系列順 (race_id は YYYYMMDD... 始まり)
    races = sorted(cache, key=lambda r: str(r["race_id"]))
    n_bet = hit = big = 0
    cost = payout = 0.0
    cum = peak = maxdd = 0.0
    months = {}
    for race in races:
        rid = str(race["race_id"])
        rp = hp.get(rid)
        if not rp or not rp.get("tansho"):
            continue
        ents = [e for e in race["entries"]
                if e.get("umaban") and e.get("ar_deviation") is not None and e.get("odds")]
        if len(ents) < 5:
            continue
        amax = max(e["ar_deviation"] for e in ents)
        cands = [e for e in ents
                 if amax - e["ar_deviation"] <= ard_gap
                 and lo <= e["odds"] <= hi
                 and (e.get("odds_rank") or 99) >= 2
                 and (min_ard is None or e["ar_deviation"] >= min_ard)]
        cands = sorted(cands, key=lambda e: -e["ar_deviation"])[:top_k]
        tan = rp["tansho"]
        for e in cands:
            n_bet += 1
            cost += STAKE
            per100 = tan.get(e["umaban"], 0)
            pay = STAKE / 100.0 * per100 if per100 else 0.0
            payout += pay
            if pay > 0:
                hit += 1
            if pay >= STAKE * 10:   # ≥1000%
                big += 1
            cum += pay - STAKE
            peak = max(peak, cum)
            maxdd = max(maxdd, peak - cum)
            ym = rid[:6]
            months[ym] = months.get(ym, 0) + (pay - STAKE)
    roi = payout / cost * 100 if cost else 0
    hr = hit / n_bet * 100 if n_bet else 0
    pos_months = sum(1 for v in months.values() if v > 0)
    return dict(n_bet=n_bet, roi=roi, hit=hr, big=big, cost=cost, payout=payout,
                pnl=payout - cost, maxdd=maxdd, n_months=len(months), pos_months=pos_months)


def main():
    cache = json.loads((config.ml_dir() / "backtest_cache.json").read_text(encoding="utf-8"))
    rids = [str(r["race_id"]) for r in cache]
    print(f"cache {len(rids)} races / loading haraimodoshi...")
    hp = load_haraimodoshi(rids)
    print(f"haraimodoshi {len(hp)} races\n")

    variants = [
        dict(ard_gap=5, lo=20, hi=100, top_k=1),
        dict(ard_gap=5, lo=20, hi=100, top_k=2),
        dict(ard_gap=5, lo=20, hi=50,  top_k=1),
        dict(ard_gap=3, lo=20, hi=100, top_k=1),
        dict(ard_gap=3, lo=20, hi=50,  top_k=1),
        dict(ard_gap=5, lo=10, hi=50,  top_k=1),
        dict(ard_gap=5, lo=30, hi=100, top_k=1),
        dict(ard_gap=5, lo=20, hi=100, top_k=1, min_ard=50),
        dict(ard_gap=8, lo=20, hi=100, top_k=2),
    ]
    hdr = (f"{'gap':>4}{'odds':>10}{'topk':>5}{'minARD':>7}{'n_bet':>7}{'ROI':>8}"
           f"{'的中':>7}{'≥1000':>7}{'PnL(¥100)':>11}{'maxDD':>9}{'+月/全':>8}")
    print(hdr)
    print("-" * len(hdr))
    for v in variants:
        r = simulate(cache, hp, ard_gap=v["ard_gap"], lo=v["lo"], hi=v["hi"],
                     top_k=v["top_k"], min_ard=v.get("min_ard"))
        od = f"{v['lo']:.0f}-{v['hi']:.0f}"
        ma = v.get("min_ard", "-")
        pm = f"{r['pos_months']}/{r['n_months']}"
        print(f"{v['ard_gap']:>4}{od:>10}{v['top_k']:>5}{str(ma):>7}{r['n_bet']:>7}"
              f"{r['roi']:>7.1f}%{r['hit']:>6.1f}%{r['big']:>7}{r['pnl']:>+11,.0f}"
              f"{r['maxdd']:>9,.0f}{pm:>8}")
    print("-" * len(hdr))
    print("PnL は flat ¥100/点。 maxDD は累積損益のピーク→谷 (¥)。 +月/全 = 月次プラスの月数。")


if __name__ == "__main__":
    main()
