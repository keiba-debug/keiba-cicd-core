#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""三連単フォーメーション (S171) の predictions 実払戻バリデーション。

★目的★: 新サイザー sanrentan_formation を ★predictions 直前オッズ + haraimodoshi 実払戻★ で
  検証し、 天井(≥1000%R・最高配当)/的中率/発動率/maxDD/月別中央値を現行 wide_anaba と比較する。
  [[feedback_odds_gate_hindsight]]: 確定オッズの後知恵に今 project で5回騙されかけた。 本番に
  入れる前に必ず本番同条件 (直前オッズ+実払戻) で測る。

精算: load_haraimodoshi (実払戻・順序 tuple)。 三連単 trim 用オッズは odds6_sanrentan の確定値を
  ★注入★ (時系列スナップショット無し=trim判断のみ確定近似。 ROI精算は実払戻でリークなし)。
  単勝/複勝/ワイドの直前オッズは predictions 内 (vb_refresh・leak-free)。

CLI:
    python -m ml.analyze.validate_sanrentan_formation
    python -m ml.analyze.validate_sanrentan_formation --start 2026-03 --end 2026-05-31
    python -m ml.analyze.validate_sanrentan_formation --max-points 36 --head-ev-floor 1.0
"""
from __future__ import annotations

import argparse
import io
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.odds_db import get_final_trifecta_odds  # noqa: E402
from ml.analyze.analyze_paddock_signal import load_paddock_marks  # noqa: E402
from ml.analyze.backtest_bet_templates import load_haraimodoshi  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.strategies import bettype_selection as bs  # noqa: E402
from ml.strategies import bettype_sizing as sz  # noqa: E402
from ml.strategies.anaba_picks import load_anaba_backtest  # noqa: E402
from ml.utils.roi import Bet, calc_roi  # noqa: E402

DEFAULT_BANKROLL = 10000
DEFAULT_PER_RACE_CAP = 5200   # 本番 = 35000×15% (勝負レート上限)。 通常R は内部で 5/15 に縮む。


def _leg_payout(leg, race_pay: dict) -> float:
    table = race_pay.get(leg.bet_type) or {}
    h = leg.horses
    if leg.bet_type in ("tansho", "fukusho"):
        per100 = table.get(h[0], 0)
    elif leg.bet_type in ("umaren", "wide", "sanrenpuku"):
        per100 = table.get(frozenset(h), 0)
    else:  # umatan / sanrentan = 順序
        per100 = table.get(tuple(h), 0)
    return leg.amount / 100.0 * per100 if per100 else 0.0


def _legs_to_bets(rid: str, legs, race_pay: dict) -> List[Bet]:
    out = []
    for leg in legs:
        p = _leg_payout(leg, race_pay)
        out.append(Bet(race_id=rid, cost=float(leg.amount), payout=float(p),
                       is_hit=p > 0, odds=float(leg.leg_odds or 0), bet_type=leg.bet_type))
    return out


class RaceAgg:
    """method 別・レース粒度の集計 (ROI/的中/天井/DD)。"""
    def __init__(self):
        self.bets: List[Bet] = []
        self.race_cost: Dict[str, float] = defaultdict(float)
        self.race_pay: Dict[str, float] = defaultdict(float)
        self.fired: set = set()

    def add_race(self, rid, bets: List[Bet]):
        if not bets:
            return
        self.fired.add(rid)
        for b in bets:
            self.bets.append(b)
            self.race_cost[rid] += b.cost
            self.race_pay[rid] += b.payout

    def summary(self) -> dict:
        if not self.bets:
            return {}
        r = calc_roi(self.bets, bootstrap_n=0)
        # レース粒度の天井: payout/cost 比
        ratios, max_pay = [], 0.0
        big = 0  # ≥1000% レース数
        for rid in self.fired:
            c, p = self.race_cost[rid], self.race_pay[rid]
            if c <= 0:
                continue
            ratios.append(p / c)
            max_pay = max(max_pay, p)
            if p >= c * 10:
                big += 1
        hit_races = sum(1 for rid in self.fired if self.race_pay[rid] > 0)
        # 月別中央値
        bymon: Dict[str, list] = defaultdict(lambda: [0.0, 0.0])
        for b in self.bets:
            ym = b.race_id[:6]
            bymon[ym][0] += b.cost
            bymon[ym][1] += b.payout
        mrois = [v[1] / v[0] * 100 for v in bymon.values() if v[0] > 0]
        med = statistics.median(mrois) if mrois else 0.0
        # maxDD (時系列=race_id昇順の純損益累積)
        cum, peak, dd = 0.0, 0.0, 0.0
        for rid in sorted(self.fired):
            cum += self.race_pay[rid] - self.race_cost[rid]
            peak = max(peak, cum)
            dd = min(dd, cum - peak)
        total_cost = sum(self.race_cost.values())
        avg_pts = len(self.bets) / len(self.fired) if self.fired else 0
        return {
            "roi": r.roi, "n_races": len(self.fired), "n_bets": len(self.bets),
            "avg_pts": avg_pts, "hit_race_pct": hit_races / len(self.fired) * 100 if self.fired else 0,
            "med_roi": med, "big1000": big, "max_pay": max_pay,
            "maxDD": dd, "total_cost": total_cost, "pnl": sum(self.race_pay.values()) - total_cost,
        }


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--start", default="2026-01")
    ap.add_argument("--end", default="2026-05-31")
    ap.add_argument("--strategy", default="concentrate")
    ap.add_argument("--bankroll", type=int, default=DEFAULT_BANKROLL)
    ap.add_argument("--per-race-cap", type=int, default=DEFAULT_PER_RACE_CAP)
    ap.add_argument("--max-points", type=int, default=None)
    ap.add_argument("--head-ev-floor", type=float, default=None)
    ap.add_argument("--win-prob-floor", type=float, default=None)
    args = ap.parse_args()

    from ml.export_formation_backtest import load_predictions_races
    races = load_predictions_races(start_date=args.start, end_date=args.end)
    print(f"predictions: {len(races)} races ({args.start}~{args.end}, 直前オッズ leak-free)")
    codes = [str(r.get("race_id") or "") for r in races if r.get("race_id")]
    haraimodoshi = load_haraimodoshi(codes)
    anaba = load_anaba_backtest(codes)
    paddock = load_paddock_marks(codes)
    print(f"  haraimodoshi={len(haraimodoshi)}  印4(flags_bt)={len(anaba)}  パドック={len(paddock)}")

    fkw = {}
    if args.max_points is not None:
        fkw["max_points"] = args.max_points
    if args.head_ev_floor is not None:
        fkw["head_ev_floor"] = args.head_ev_floor
    if args.win_prob_floor is not None:
        fkw["win_prob_floor"] = args.win_prob_floor

    # arms[dist][method]
    arms: Dict[str, Dict[str, RaceAgg]] = defaultdict(lambda: defaultdict(RaceAgg))
    races_by_dist: Dict[str, int] = defaultdict(int)
    n_eval = n_no_pay = n_odds = 0

    for i, r in enumerate(races):
        rid = str(r.get("race_id") or "")
        race_pay = haraimodoshi.get(rid)
        if not race_pay or not race_pay.get("sanrentan"):
            n_no_pay += 1
            continue
        sel = bs.evaluate_and_select(r, strategy=args.strategy, ev_floor=bs.DEFAULT_EV_FLOOR)
        if sel is None:
            continue
        race_eff = be.process_race(r, axis=sel.axis_umaban)
        if race_eff is None or not race_eff.strengths:
            continue
        n_eval += 1
        if n_eval % 200 == 0:
            print(f"   ... {n_eval} races evaluated", file=sys.stderr)
        dl = "勝負R" if sz.is_shobu_race(race_eff) else "通常R"
        races_by_dist[dl] += 1
        races_by_dist["ALL"] += 1

        # 三連単確定オッズを注入 (trim 用)
        st_odds = get_final_trifecta_odds(rid)
        if st_odds:
            n_odds += 1

        # method 1: sanrentan_formation (S171・本命検証対象)
        rs_f = sz.size_race_sanrentan_formation(
            race_eff, sel, bankroll=args.bankroll, per_race_cap=args.per_race_cap,
            sanrentan_odds=st_odds, anaba_umabans=anaba.get(rid, []),
            paddock_marks=paddock.get(rid, {}), **fkw)
        bf = _legs_to_bets(rid, rs_f.legs, race_pay)
        for d in (dl, "ALL"):
            arms[d]["formation"].add_race(rid, bf)

        # method 2: wide_anaba (現行本番・比較基準)
        rs_w = sz.size_race_wide_anaba(
            race_eff, sel, bankroll=args.bankroll, per_race_cap=args.per_race_cap,
            anaba_umabans=anaba.get(rid, []))
        bw = _legs_to_bets(rid, rs_w.legs, race_pay)
        for d in (dl, "ALL"):
            arms[d]["wide_anaba"].add_race(rid, bw)

    print(f"  評価レース={n_eval} (払戻なし除外={n_no_pay}・三連単確定OD取得={n_odds})\n")

    order = ["ALL", "勝負R", "通常R"]
    methods = ["formation", "wide_anaba"]
    hdr = (f"  {'method/分布':18}{'発動R':>7}{'点/R':>6}{'ROI':>7}{'月中央':>7}"
           f"{'的中R%':>7}{'≥1000R':>8}{'最高配当':>11}{'maxDD':>11}{'PnL':>11}")
    for dl in order:
        print(f"\n■ {dl} (全{races_by_dist[dl]}R)")
        print(hdr)
        print("  " + "-" * (len(hdr) - 2))
        for m in methods:
            s = arms[dl][m].summary()
            if not s:
                print(f"  {m:18}{'-':>7}")
                continue
            print(f"  {m:18}{s['n_races']:>7}{s['avg_pts']:>6.1f}{s['roi']:>6.0f}%"
                  f"{s['med_roi']:>6.0f}%{s['hit_race_pct']:>6.0f}%{s['big1000']:>8}"
                  f"{s['max_pay']:>11,.0f}{s['maxDD']:>11,.0f}{s['pnl']:>+11,.0f}")
    print("\n  ★formation=三連単F(S171) / wide_anaba=現行本番。 控除率の壁: 三連系72.5% / ワイド77.5%")
    print("  ★天井=≥1000%R数・最高配当が三連単Fの存在意義 (固い馬券では構造的に出ない・S169)")
    print("  ★精算=haraimodoshi実払戻(リークなし)。 trim用三連単ODは確定値注入(時系列なし=近似)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
