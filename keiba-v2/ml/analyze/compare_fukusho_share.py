#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""複勝シェア比較: 現行 v2 (複あり) vs 複無し(単+comboに回す) の実払戻比較 (Session 163)

ふくだ疑問 [[feedback_betting_philosophy]] §5: 「単900・複600 の複600 の根拠は? 薄利非対称では?
中穴(単7-10倍)でガツン勝負ならともかく、 capの固定割合20%で複を機械的に買う意味は薄い」。
→ ふくだ判断: 複は原則無し・単とcomboに集中。 ただし Session 161 で「低オッズ複勝は実回収率高い
(削るとROI落ちる)」結果あり → ★外す前に実払戻でトレードオフを定量化★ ([[feedback_long_term_right_way]])。

比較する配分 (いずれも fixed_grade_v2 の単シェア・combo配分は同じ。 ★複シェアだけ変える★):
  - v2_with_fuku  : 現行本番 (FIXED_SHARES_V2 = strong15/15 mid30/20 weak15/10)
  - no_fuku       : 複0% (複の予算を combo に回す)。 strong15/0 mid30/0 weak15/0
  - half_fuku     : 複を半分に (strong15/8 mid30/10 weak15/5) ← 中間案の参考

メトリクス (predictions 直前オッズ + haraimodoshi 実払戻):
  - ROI / 的中率 / maxDD (損益基準)
  - ≥1000%率 (天井を取れた回数 [[payout-ceiling-strategy]])
  - 単/複/combo の払戻寄与 (どの券種が回収を生んでいるか)
  - 複の単独ROI (複legだけの回収率 = 複が割に合っているかの直接指標)

CLI:
    python -m ml.analyze.compare_fukusho_share --start 2026-01 --end 2026-03-16
    python -m ml.analyze.compare_fukusho_share --start 2025-09 --end 2025-12-31
"""

from __future__ import annotations

import argparse
import io
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.analyze.backtest_bet_templates import load_haraimodoshi  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.strategies import bettype_selection as bs  # noqa: E402
from ml.strategies import bettype_sizing as sz  # noqa: E402

DEFAULT_BANKROLL = 10000
DEFAULT_PER_RACE_CAP = 3000

# 比較する複シェア表 (単シェアは同一・複だけ変える)。
#   ★Session 163 で FIXED_SHARES_V2 は複=0 に変更済 (no_fuku が本番)★。 トレードオフを見せるため
#   旧 v2 配分 (複あり) を明示テーブルで残してベースライン比較する。
OLD_V2_WITH_FUKU = {"strong": (0.15, 0.15), "mid": (0.30, 0.20), "weak": (0.15, 0.10)}
SHARE_VARIANTS: Dict[str, dict] = {
    "with_fuku(旧v2)": OLD_V2_WITH_FUKU,                      # 旧配分 (複あり)
    "no_fuku(現本番)": sz.FIXED_SHARES_V2,                    # 現本番 (複=0・複勝はキャラへ移譲)
    "half_fuku": {"strong": (0.15, 0.08), "mid": (0.30, 0.10), "weak": (0.15, 0.05)},
}


def _leg_payout(leg: sz.SizedLeg, race_pay: dict) -> float:
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


@dataclass
class Agg:
    n_races: int = 0
    hit_races: int = 0
    cost: float = 0.0
    payout: float = 0.0
    # 券種別 cost/payout
    by_type_cost: Dict[str, float] = field(default_factory=lambda: {})
    by_type_payout: Dict[str, float] = field(default_factory=lambda: {})
    race_recoveries: List[float] = field(default_factory=list)
    cum: float = 0.0
    peak: float = 0.0
    max_dd: float = 0.0

    def add(self, rcost: float, rpayout: float, legs_by_type: Dict[str, tuple]):
        if rcost <= 0:
            return
        self.n_races += 1
        self.cost += rcost
        self.payout += rpayout
        if rpayout > 0:
            self.hit_races += 1
        self.race_recoveries.append(rpayout / rcost * 100)
        for bt_, (c, p) in legs_by_type.items():
            grp = "tansho" if bt_ == "tansho" else ("fukusho" if bt_ == "fukusho" else "combo")
            self.by_type_cost[grp] = self.by_type_cost.get(grp, 0.0) + c
            self.by_type_payout[grp] = self.by_type_payout.get(grp, 0.0) + p
        self.cum += rpayout - rcost
        self.peak = max(self.peak, self.cum)
        self.max_dd = max(self.max_dd, self.peak - self.cum)

    @property
    def roi(self):
        return self.payout / self.cost * 100 if self.cost else 0.0

    @property
    def hit_rate(self):
        return self.hit_races / self.n_races * 100 if self.n_races else 0.0

    @property
    def rate_ge_1000(self):
        n = sum(1 for r in self.race_recoveries if r >= 1000)
        return n / self.n_races * 100 if self.n_races else 0.0

    def grp_roi(self, grp):
        c = self.by_type_cost.get(grp, 0.0)
        return self.by_type_payout.get(grp, 0.0) / c * 100 if c else 0.0

    def grp_share(self, grp):
        return self.by_type_cost.get(grp, 0.0) / self.cost * 100 if self.cost else 0.0


def size_and_settle(pred_race, race_pay, shares, *, bankroll, per_race_cap):
    sel = bs.evaluate_and_select(pred_race, strategy="concentrate", ev_floor=bs.DEFAULT_EV_FLOOR)
    if sel is None:
        return None
    re_ = be.process_race(pred_race, axis=sel.axis_umaban)
    if re_ is None:
        return None
    rs = sz.size_race_fixed_grade(re_, sel, bankroll=bankroll, per_race_cap=per_race_cap,
                                  _shares_table=shares, _skip_max_odds_floor=0.0)
    rcost = rpayout = 0.0
    by_type: Dict[str, list] = {}
    for leg in rs.legs:
        p = _leg_payout(leg, race_pay)
        rcost += leg.amount
        rpayout += p
        ce = by_type.setdefault(leg.bet_type, [0.0, 0.0])
        ce[0] += leg.amount
        ce[1] += p
    return rcost, rpayout, {k: tuple(v) for k, v in by_type.items()}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--start", default="2026-01")
    p.add_argument("--end", default="2026-03-16")
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
    from ml.export_formation_backtest import load_predictions_races
    races = load_predictions_races(start_date=args.start, end_date=args.end)
    print(f"predictions.json: {len(races)} races ({args.start}~{args.end}, leak-free 直前オッズ)")
    codes = [str(r.get("race_id") or "") for r in races if r.get("race_id")]
    print("  loading haraimodoshi (実払戻)...")
    haraimodoshi = load_haraimodoshi(codes)
    print(f"  haraimodoshi loaded: {len(haraimodoshi)}")

    aggs = {name: Agg() for name in SHARE_VARIANTS}
    n_eval = 0
    for r in races:
        rid = str(r.get("race_id") or "")
        race_pay = haraimodoshi.get(rid)
        if not race_pay or not race_pay.get("tansho"):
            continue
        ok = False
        for name, shares in SHARE_VARIANTS.items():
            res = size_and_settle(r, race_pay, shares, bankroll=args.bankroll,
                                  per_race_cap=args.per_race_cap)
            if res is None:
                continue
            rcost, rpayout, by_type = res
            if rcost <= 0:
                continue
            aggs[name].add(rcost, rpayout, by_type)
            ok = True
        if ok:
            n_eval += 1
    print(f"  評価レース: {n_eval}\n")

    print(f"{'='*100}")
    print(f"  複勝シェア比較 (fixed_grade_v2 ベース・複シェアだけ変える・haraimodoshi 実払戻)")
    print(f"  {'配分':<14}{'ROI':>7}{'的中':>6}{'≥1000%':>8}{'maxDD':>9}"
          f"{'  単share/ROI':>16}{'  複share/ROI':>16}{'  comboshare/ROI':>18}")
    print(f"  {'-'*96}")
    for name in SHARE_VARIANTS:
        a = aggs[name]
        print(f"  {name:<14}{a.roi:>6.1f}%{a.hit_rate:>5.0f}%{a.rate_ge_1000:>6.1f}%"
              f"{a.max_dd:>9,.0f}"
              f"   {a.grp_share('tansho'):>3.0f}%/{a.grp_roi('tansho'):>4.0f}%"
              f"   {a.grp_share('fukusho'):>3.0f}%/{a.grp_roi('fukusho'):>4.0f}%"
              f"     {a.grp_share('combo'):>3.0f}%/{a.grp_roi('combo'):>4.0f}%")
    print(f"  {'-'*96}")
    print(f"  単/複/combo の share=投資配分% ROI=その券種だけの回収率% (複ROIが複を買う価値の直接指標)")
    print(f"\n  ★読み方:★")
    print(f"   - no_fuku の ROI が v2_with_fuku 以上 → 複を外して単/comboに回すのは正解")
    print(f"   - 複ROIが控除率(複80%)を大きく下回る → 複は割に合っていない (外す根拠)")
    print(f"   - no_fuku の ≥1000%率が上がる → 複の予算が combo に回り天井が上がった")
    return 0


if __name__ == "__main__":
    sys.exit(main())
