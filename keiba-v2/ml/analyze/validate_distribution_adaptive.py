#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""印①分布 (1強/混戦/大混戦) × 買い方の predictions 実払戻診断 (Session 170)

★目的★: lab (bet_template_lab・確定オッズ精算) で見えた分布所見
  「1強→単勝が最良・combo弱い / 混戦→combo / 大混戦→全滅」が、
  ★predictions の直前オッズ + haraimodoshi 実払戻★ で再現するか (後知恵でないか) を診断する。
  [[feedback_odds_gate_hindsight]]: lab/cache の確定オッズで良くても本番(直前)で消える罠を
  S148→161→162→163 で 4 回踏んだ。本番 shobu_rate を書き換える前の 5 回目防止チェック。

分布 = cliff_n_marks(strengths, 1.5) (composite pred_p 比の崖頭数・★オッズ非依存★):
  1 = 1強 / 2-4 = 混戦 / 5+ = 大混戦。

各レースを複数の買い方でサイジング → 実払戻で精算し、分布別に ROI を比較:
  - shobu_rate    : 現行本番サイザー (勝負R=rank_w◎単勝厚く / 通常R=combo flat)
  - tansho_rankw  : rank_w◎ の単勝 1 点のみ (lab「1強→単勝」仮説の本番再現チェック・100円固定)

CLI:
    python -m ml.analyze.validate_distribution_adaptive
    python -m ml.analyze.validate_distribution_adaptive --start 2025-09 --end 2026-05-31
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

from ml.analyze.backtest_bet_templates import load_haraimodoshi  # noqa: E402
from ml.analyze.backtest_selector import cliff_n_marks  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.strategies import bettype_selection as bs  # noqa: E402
from ml.strategies import bettype_sizing as sz  # noqa: E402
from ml.strategies.anaba_picks import load_anaba_backtest  # noqa: E402
from ml.utils.roi import Bet, calc_roi  # noqa: E402

DEFAULT_BANKROLL = 10000
DEFAULT_PER_RACE_CAP = 3000  # 勝負レート上限想定 (shobu_rate は内部で通常R を縮める)

# ラボ主要テンプレ (composite印・flat100円・S162実証の template_flat パスで本番条件評価)
LAB_TEMPLATES = ["fukusho_korogashi", "wide_anchor", "honmei_hoken",
                 "sanrenpuku_1jiku", "tansho_ai2", "honmei_formation"]


def _leg_payout(leg, race_pay: dict) -> float:
    """SizedLeg の実払戻 (haraimodoshi・100円あたり払戻 × amount/100)。ハズレ=0。"""
    table = race_pay.get(leg.bet_type) or {}
    h = leg.horses
    per100 = 0
    if leg.bet_type in ("tansho", "fukusho"):
        per100 = table.get(h[0], 0)
    elif leg.bet_type in ("umaren", "wide", "sanrenpuku"):
        per100 = table.get(frozenset(h), 0)
    elif leg.bet_type in ("umatan", "sanrentan"):
        per100 = table.get(tuple(h), 0)
    return leg.amount / 100.0 * per100 if per100 else 0.0


def _legs_to_bets(rid: str, legs, race_pay: dict) -> List[Bet]:
    bets: List[Bet] = []
    for leg in legs:
        p = _leg_payout(leg, race_pay)
        bets.append(Bet(race_id=rid, cost=float(leg.amount), payout=float(p),
                        is_hit=p > 0, odds=float(leg.leg_odds or 0), bet_type=leg.bet_type))
    return bets


def dist_label(cliff: int) -> str:
    if cliff == 1:
        return "1強"
    if cliff <= 4:
        return "混戦"
    return "大混戦"


def _roi(bets: List[Bet]) -> tuple:
    """(全期間ROI, 点数, 的中数, 月別ROIの中央値)。中央値=上振れ排除の安定指標。"""
    if not bets:
        return (0.0, 0, 0, 0.0)
    r = calc_roi(bets, bootstrap_n=0)
    hits = sum(1 for b in bets if b.is_hit)
    bymon: Dict[str, list] = defaultdict(lambda: [0.0, 0.0])
    for b in bets:
        ym = b.race_id[:6]
        bymon[ym][0] += b.cost
        bymon[ym][1] += b.payout
    mrois = [v[1] / v[0] * 100 for v in bymon.values() if v[0] > 0]
    med = statistics.median(mrois) if mrois else 0.0
    return (r.roi, len(bets), hits, med)


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
    args = ap.parse_args()

    from ml.export_formation_backtest import load_predictions_races
    races = load_predictions_races(start_date=args.start, end_date=args.end)
    print(f"predictions: {len(races)} races ({args.start}~{args.end}, 直前オッズ leak-free)")
    codes = [str(r.get("race_id") or "") for r in races if r.get("race_id")]
    haraimodoshi = load_haraimodoshi(codes)
    anaba = load_anaba_backtest(codes)  # 印4 (flags_bt の value_picks・最大2頭)
    print(f"  haraimodoshi: {len(haraimodoshi)}  印4(flags_bt有)={len(anaba)} races")

    # arms[dist][method] = list[Bet] ; per-race n は races_by_dist で数える
    arms: Dict[str, Dict[str, List[Bet]]] = defaultdict(lambda: defaultdict(list))
    races_by_dist: Dict[str, int] = defaultdict(int)
    n_eval = n_no_pay = 0
    tansho_amt = sz._round_unit(args.per_race_cap * sz.SHOBU_NORMAL_RATE_PCT
                                / sz.SHOBU_SHOBU_RATE_PCT)  # 通常レート相当に揃える
    for r in races:
        rid = str(r.get("race_id") or "")
        race_pay = haraimodoshi.get(rid)
        if not race_pay or not race_pay.get("tansho"):
            n_no_pay += 1
            continue
        sel = bs.evaluate_and_select(r, strategy=args.strategy, ev_floor=bs.DEFAULT_EV_FLOOR)
        if sel is None:
            continue
        race_eff = be.process_race(r, axis=sel.axis_umaban)
        if race_eff is None or not race_eff.strengths:
            continue
        # 区分 = 勝負R (tansho_H 4条件) / 通常R。 ふくだ確認: 勝負R単勝は残し、通常R を直す。
        dl = "勝負R" if sz.is_shobu_race(race_eff) else "通常R"
        n_eval += 1
        races_by_dist[dl] += 1
        races_by_dist["ALL"] += 1

        # method 1: 現行 shobu_rate
        rs = sz.size_race_shobu_rate(race_eff, sel, bankroll=args.bankroll,
                                     per_race_cap=args.per_race_cap)
        b1 = _legs_to_bets(rid, rs.legs, race_pay)
        arms[dl]["shobu_rate"].extend(b1)
        arms["ALL"]["shobu_rate"].extend(b1)

        # method 2: rank_w◎ 単勝 1 点のみ (lab「1強→単勝」の本番再現チェック)
        ax = sz._shobu_axis(race_eff)
        if ax is not None and ax.odds and ax.odds > 1.0:
            per100 = (race_pay.get("tansho") or {}).get(ax.umaban, 0)
            payout = tansho_amt / 100.0 * per100 if per100 else 0.0
            b2 = Bet(race_id=rid, cost=float(tansho_amt), payout=float(payout),
                     is_hit=payout > 0, odds=float(ax.odds), bet_type="tansho")
            arms[dl]["tansho_rankw"].append(b2)
            arms["ALL"]["tansho_rankw"].append(b2)

        # method 2.5: wide_anaba (S170 新サイザー = 通常R:ワイド堅実党 / 勝負R:単勝 + 印4ワイド)
        rs_wa = sz.size_race_wide_anaba(race_eff, sel, bankroll=args.bankroll,
                                        per_race_cap=args.per_race_cap,
                                        anaba_umabans=anaba.get(rid, []))
        bwa = _legs_to_bets(rid, rs_wa.legs, race_pay)
        arms[dl]["wide_anaba"].extend(bwa)
        arms["ALL"]["wide_anaba"].extend(bwa)

        # method 3+: ラボ主要テンプレ (composite印・flat100円・S162実証パス)
        for t in LAB_TEMPLATES:
            rs_t = sz.size_race_template_flat(race_eff, sel, bankroll=args.bankroll,
                                              per_race_cap=args.per_race_cap, template_name=t)
            bt_ = _legs_to_bets(rid, rs_t.legs, race_pay)
            arms[dl][t].extend(bt_)
            arms["ALL"][t].extend(bt_)

    print(f"  評価レース: {n_eval} (払戻なしで除外 {n_no_pay})\n")

    order = ["ALL", "勝負R", "通常R"]
    methods = ["shobu_rate", "wide_anaba", "tansho_rankw"] + LAB_TEMPLATES
    # ヘッダ (分布列・R数付き)
    print(f"  {'買い方':20}" + "".join(
        f"{dl}({races_by_dist[dl]})".rjust(15) for dl in order))
    print("  " + "-" * (20 + 15 * len(order)))
    for m in methods:
        cells = []
        for dl in order:
            roi, n, hits, med = _roi(arms[dl][m])
            hr = int(round(hits / n * 100)) if n else 0
            if dl == "ALL":
                cells.append(f"{roi:.0f}/中{med:.0f}({hr}%)" if n else "-")
            else:
                cells.append(f"{roi:.0f}%({hr}%)" if n else "-")
        tag = "★現行" if m == "shobu_rate" else ("単勝" if m == "tansho_rankw" else "lab")
        print(f"  {(m+' '+tag):20}" + "".join(c.rjust(17) for c in cells))
    print("  " + "-" * (20 + 15 * len(order)))
    print("  各セル= ROI(的中率)・predictions直前オッズ+haraimodoshi実払戻。控除率の壁=単複80%/ワイド77.5%/三連72.5%")
    print("  ★shobu_rate=現行本番 / tansho_rankw=rank_w◎単勝1点 / lab各=composite印flat100円(S162パス)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
