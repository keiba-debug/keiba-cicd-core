#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""combo EV ゲート floor sweep (Session 163 / ふくだ「単400だけ・3000円が券種に分かれてない」)

★バグ★: concentrate は combo 券種を should_fund (EV>=ev_floor=1.0) ★かつ★ 合成>単 で選ぶが、
  控除率20%で combo の EV はほぼ常に <1.0 → combo が選ばれず、 ★27%のレースで「単のみ」bet★。
  fixed_grade_v2 は「単薄く combo 厚く=天井を取る」思想なのに、 配分先の combo 買い目が selection
  段階で消えていた (3000円のうち combo 分が宙に浮く)。

このスクリプトは concentrate の ★combo EV floor だけ★ を下げた版で再選定し、 実払戻で:
  - 単のみ率   : sizing 結果が tansho だけになるレース率 (★ふくだの「単400だけ」)
  - 3000円消化 : per_race 平均投資額 (券種に分かれて 3000 を使えているか)
  - ROI / 的中 / ≥1000%率 (天井) / maxDD

を floor 横断で出す。 ★combo の EV は控除率込みで < 1 が普通 = EV>=1ゲートは「ボーナス券種を
全弾き」する設計ミス★。 floor を下げすぎると EV マイナス combo を乱買い → ROI で最適点を探す。

精算 = predictions 直前オッズ + haraimodoshi 実払戻 (リークなし)。
combo選定は should_fund を combo_floor で置換した _select_concentrate のミラー (本体は触らない)。

CLI:
    python -m ml.analyze.sweep_combo_ev_floor --start 2026-01 --end 2026-03-16
    python -m ml.analyze.sweep_combo_ev_floor --floors 1.0,0.85,0.7,0.5,0.0
"""

from __future__ import annotations

import argparse
import io
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.analyze.backtest_bet_templates import load_haraimodoshi  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.strategies import bettype_selection as bs  # noqa: E402
from ml.strategies import bettype_sizing as sz  # noqa: E402

DEFAULT_BANKROLL = 10000
DEFAULT_PER_RACE_CAP = 3000
DEFAULT_FLOORS = "1.0,0.85,0.7,0.5,0.3,0.0"
COMBO_TYPES = frozenset({"umaren", "wide", "umatan", "sanrenpuku", "sanrentan"})


def _leg_payout(leg, race_pay: dict) -> float:
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


def _reselect_with_combo_floor(base_sel, race_eff, combo_floor: float):
    """base_sel (本物の BetSelection) の selected_plans を combo EV floor で組み直す。

    基準券種 (単/複) は常に fund。 combo は (EV>=combo_floor かつ 合成>単) で fund。
    BetSelection の他フィールドは base_sel のまま使い、 selected_plans だけ差し替える
    (dataclasses.replace で非破壊コピー)。 _select_concentrate のロジックのミラー。
    """
    import dataclasses
    selected = []
    for p in race_eff.plans:
        if p.bet_type in bs.BASE_BET_TYPES:
            selected.append(bs._to_selected(p, bs._base_reason(p)))
            continue
        funded = (p.expected_return is not None and p.expected_return >= combo_floor)
        merit = (p.vs_tansho == "gt")
        if funded and merit:
            selected.append(bs._to_selected(p, f"EV>={combo_floor} かつ合成>単"))
    return dataclasses.replace(base_sel, selected_plans=selected,
                               decision_reason=f"combo_floor={combo_floor} sweep")


@dataclass
class Agg:
    n: int = 0
    tan_only: int = 0
    hit: int = 0
    cost: float = 0.0
    payout: float = 0.0
    recoveries: List[float] = field(default_factory=list)
    cum: float = 0.0
    peak: float = 0.0
    max_dd: float = 0.0

    def add(self, rcost, rpayout, tan_only: bool):
        if rcost <= 0:
            return
        self.n += 1
        self.cost += rcost
        self.payout += rpayout
        if rpayout > 0:
            self.hit += 1
        if tan_only:
            self.tan_only += 1
        self.recoveries.append(rpayout / rcost * 100)
        self.cum += rpayout - rcost
        self.peak = max(self.peak, self.cum)
        self.max_dd = max(self.max_dd, self.peak - self.cum)

    @property
    def roi(self):
        return self.payout / self.cost * 100 if self.cost else 0.0

    @property
    def hit_rate(self):
        return self.hit / self.n * 100 if self.n else 0.0

    @property
    def tan_only_rate(self):
        return self.tan_only / self.n * 100 if self.n else 0.0

    @property
    def avg_cost(self):
        return self.cost / self.n if self.n else 0.0

    @property
    def rate_ge_1000(self):
        return sum(1 for r in self.recoveries if r >= 1000) / self.n * 100 if self.n else 0.0


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--start", default="2026-01")
    p.add_argument("--end", default="2026-03-16")
    p.add_argument("--floors", default=DEFAULT_FLOORS)
    p.add_argument("--bankroll", type=int, default=DEFAULT_BANKROLL)
    p.add_argument("--per-race-cap", type=int, default=DEFAULT_PER_RACE_CAP)
    return p.parse_args()


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = parse_args()
    floors = [float(x) for x in args.floors.split(",") if x.strip()]
    from ml.export_formation_backtest import load_predictions_races
    races = load_predictions_races(start_date=args.start, end_date=args.end)
    print(f"predictions.json: {len(races)} races ({args.start}~{args.end}, leak-free 直前オッズ)")
    codes = [str(r.get("race_id") or "") for r in races if r.get("race_id")]
    print("  loading haraimodoshi (実払戻)...")
    haraimodoshi = load_haraimodoshi(codes)
    print(f"  haraimodoshi loaded: {len(haraimodoshi)}\n")

    aggs: Dict[float, Agg] = {f: Agg() for f in floors}
    for r in races:
        rid = str(r.get("race_id") or "")
        race_pay = haraimodoshi.get(rid)
        if not race_pay or not race_pay.get("tansho"):
            continue
        # 軸選定は通常の concentrate (= 軸は composite◎、 ここは変えない)
        base_sel = bs.evaluate_and_select(r, strategy="concentrate", ev_floor=bs.DEFAULT_EV_FLOOR)
        if base_sel is None:
            continue
        re_ = be.process_race(r, axis=base_sel.axis_umaban)
        if re_ is None:
            continue
        for f in floors:
            sel = _reselect_with_combo_floor(base_sel, re_, f)
            rs = sz.size_race_fixed_grade(re_, sel, bankroll=args.bankroll,
                                          per_race_cap=args.per_race_cap,
                                          _shares_table=sz.FIXED_SHARES_V2,
                                          _skip_max_odds_floor=0.0)
            if not rs.legs:
                continue
            rcost = sum(l.amount for l in rs.legs)
            rpayout = sum(_leg_payout(l, race_pay) for l in rs.legs)
            tan_only = {l.bet_type for l in rs.legs} == {"tansho"}
            aggs[f].add(rcost, rpayout, tan_only)

    print(f"{'='*92}")
    print(f"  combo EV floor sweep (concentrate・複なしv2 sizing・haraimodoshi 実払戻)")
    print(f"  {'combo_floor':>11}{'単のみ率':>9}{'平均投資':>9}{'ROI':>8}{'的中':>6}"
          f"{'≥1000%':>8}{'maxDD':>9}")
    print(f"  {'-'*84}")
    for f in floors:
        a = aggs[f]
        tag = "  ←現状(1.0)" if f == 1.0 else ""
        print(f"  {f:>11.2f}{a.tan_only_rate:>8.0f}%{a.avg_cost:>8.0f}円{a.roi:>7.1f}%"
              f"{a.hit_rate:>5.0f}%{a.rate_ge_1000:>6.1f}%{a.max_dd:>9,.0f}{tag}")
    print(f"  {'-'*84}")
    print(f"  単のみ率=sizingがtanshoだけになるR% (★ふくだの単400だけ) / 平均投資=per_race実投資額")
    print(f"\n  ★読み方:★ floor を下げると単のみ率↓・平均投資↑ (3000円が券種に分かれる)。")
    print(f"     ただし下げ過ぎは EVマイナス combo 乱買い → ROI で最適点を探す。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
