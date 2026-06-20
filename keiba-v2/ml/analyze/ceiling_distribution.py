#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""現状サイザーの「天井分布」可視化ハーネス (Session 168)

★問い (ふくだ Session 168)★:
  「馬券の買い方が保守的すぎる。 回収率1000%超を基本方針にしないと改善しないのでは?」

★この bench の役割★:
  方針を決める前に、 ★現状の本番サイザー (shobu_rate) が実際に出す買い目の「天井」を
  実データで定量化★ する (想像で「保守的」と言わない・[[feedback_no_fabricated_tool_results]])。

★天井 (ceiling) の定義★:
  - plan_ceiling_R = ★我々の買い目の最大払戻倍率★ = max_leg(amount × leg_odds) / cost × 100。
      その買い目で「一番高い点」が当たったら回収率は何%か。 = 我々が設計した天井。
  - marks_ceiling_R = ★AI印4頭で取れたはずの最大払戻倍率★ (後知恵・実払戻 haraimodoshi)。
      ◎○▲△の部分集合で組める券面のうち実払戻 per100 が最大のもの / cost × 100。
      = 「印は当てたのに、 その配当を取りにいく買い目を組まなかった」上限。
  ★plan_ceiling << marks_ceiling なら「保守的 = 自分の印の中の高配当を取りこぼしている」★。

★注意★: leg_odds / haraimodoshi はいずれも ★確定オッズ★ 由来 (時系列なし)。 ここでは
  「買い目の天井を記述する」用途であって ★見送りゲート (S162-165で害確定) ではない★ ので
  後知恵問題は当たらない。 ただし marks_ceiling は実払戻=完全な後知恵上限である点に留意。

★本番パラメータ (config.json 2026-06-20)★: 基準金額35000 × 勝負15% = per_race_cap 5200円。
  通常R はサイザー内で 5/15 倍 (≈1700円) に縮む。 bankroll=100000。

実行:
    python -m ml.analyze.ceiling_distribution
    python -m ml.analyze.ceiling_distribution --skip-p2
    python -m ml.analyze.ceiling_distribution --per-race-cap 5200
"""

from __future__ import annotations

import argparse
import io
import json
import math
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import config  # noqa: E402
from ml.analyze.backtest_bet_templates import load_haraimodoshi  # noqa: E402
from ml.export_formation_backtest import load_predictions_races  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.strategies import bettype_selection as bs  # noqa: E402
from ml.strategies import bettype_sizing as sz  # noqa: E402
from ml.utils.filters import is_obstacle  # noqa: E402


# ---------------------------------------------------------------------------
# 精算/印 ヘルパー (自己完結。 bench_two_tier_v0 の同名関数と同値・依存を切るためインライン)
# ---------------------------------------------------------------------------

def _leg_payout(leg: sz.SizedLeg, race_pay: dict) -> float:
    """SizedLeg の実払戻 (haraimodoshi per100 × amount/100)。 ハズレ=0。"""
    table = race_pay.get(leg.bet_type) or {}
    horses = leg.horses
    per100 = 0
    if leg.bet_type in ("tansho", "fukusho"):
        per100 = table.get(horses[0], 0)
    elif leg.bet_type in ("umaren", "wide", "sanrenpuku"):
        per100 = table.get(frozenset(horses), 0)
    elif leg.bet_type in ("umatan", "sanrentan"):
        per100 = table.get(tuple(horses), 0)
    return leg.amount / 100.0 * per100 if per100 else 0.0


def _ai_marks(race_eff) -> List[int]:
    """AI印4頭 = ◎(axis) + ○▲△(partners[:3])。 重複除去。"""
    axis = getattr(race_eff, "axis_umaban", None)
    partners = list(getattr(race_eff, "partners", None) or [])
    marks: List[int] = []
    if axis is not None:
        marks.append(int(axis))
    for p in partners[:3]:
        if int(p) not in marks:
            marks.append(int(p))
    return marks


def _max_payout_within_marks(race_pay: dict, marks: List[int]) -> Tuple[int, str]:
    """印4頭の部分集合で組める券面のうち実払戻 (per100) 最大のものを返す。 無ければ (0, '')。"""
    mark_set = set(marks)
    best = 0
    best_bt = ""
    for bt, table in race_pay.items():
        if not isinstance(table, dict):
            continue
        for key, per100 in table.items():
            if not per100 or per100 <= best:
                continue
            if bt in ("tansho", "fukusho"):
                combo = {int(key)}
            elif bt in ("umaren", "wide", "sanrenpuku", "umatan", "sanrentan"):
                combo = {int(x) for x in key}
            else:
                continue
            if combo <= mark_set:
                best = int(per100)
                best_bt = bt
    return best, best_bt

# 本番値 (config.json) — per_race_cap=基準金額35000×勝負15%。
DEFAULT_PER_RACE_CAP = 5200
DEFAULT_BANKROLL = 100000
DEFAULT_P1_START = "2026-01-04"
DEFAULT_P1_END = "2026-03-15"
DEFAULT_P2_START = "2025-09-01"
DEFAULT_P2_END = "2025-12-31"
DEFAULT_OUTPUT = "ceiling_distribution_results.json"

# 天井R のバケット境界 (%)。
CEILING_BUCKETS = [(0, 200), (200, 400), (400, 700), (700, 1000),
                   (1000, 2000), (2000, 5000), (5000, math.inf)]


@dataclass
class RaceCeiling:
    rid: str
    date: str
    tier: str                     # 'shobu' / 'normal'
    cost: float
    plan_ceiling_yen: float       # 我々の買い目の最大払戻 (max_leg amount×odds)
    plan_ceiling_R: float         # /cost ×100
    marks_ceiling_yen: float      # AI印4頭で取れた実払戻 max (cost に合わせ amount=cost と仮定でなく per100基準)
    marks_ceiling_R: float
    realized_payout: float        # 実際の払戻 (我々の買い目)
    realized_R: float
    bt_yen: Dict[str, float] = field(default_factory=dict)  # 券種別投入額


def _plan_ceiling(rs: sz.RaceSizing) -> Tuple[float, float]:
    """買い目の最大払戻 (yen, /cost%)。 leg_odds が None の点は対象外。"""
    cost = sum(l.amount for l in rs.legs)
    if cost <= 0:
        return 0.0, 0.0
    best = 0.0
    for l in rs.legs:
        if l.leg_odds and l.leg_odds > 0:
            best = max(best, l.amount * l.leg_odds)
    return best, (best / cost * 100.0)


def _marks_ceiling(race_eff, race_pay: dict, cost: float) -> Tuple[float, float]:
    """AI印4頭(◎○▲△)で取れた実払戻の最大 (per100→cost相当に換算)。

    印部分集合で組める券面の実払戻 per100 が最大のもの。 「100円買っていたら」基準なので
    cost に対する倍率は (max_per100 / 100) で表す (= 1点100円ベースの回収率)。
    """
    marks = _ai_marks(race_eff)
    max_per100, _bt = _max_payout_within_marks(race_pay, marks)
    if max_per100 <= 0:
        return 0.0, 0.0
    # per100 基準の倍率 (100円1点で取った時の回収率)。 cost 非依存の「印の天井」。
    return float(max_per100), float(max_per100)  # per100 == 100円あたり払戻 = 回収率%


def analyze_race(pred_race: dict, race_pay: dict, *, per_race_cap: int,
                 bankroll: int) -> Optional[RaceCeiling]:
    sel = bs.evaluate_and_select(pred_race, strategy="concentrate",
                                 ev_floor=bs.DEFAULT_EV_FLOOR)
    if sel is None:
        return None
    race_eff = be.process_race(pred_race, axis=sel.axis_umaban)
    if race_eff is None:
        return None
    rid = str(pred_race.get("race_id") or race_eff.race_id)
    rs = sz.size_race_shobu_rate(race_eff, sel, bankroll=bankroll,
                                 per_race_cap=per_race_cap)
    if not rs.legs:
        return None
    tier = "shobu" if sz.is_shobu_race(race_eff) else "normal"
    cost = float(sum(l.amount for l in rs.legs))
    plan_ceil_yen, plan_ceil_R = _plan_ceiling(rs)
    marks_ceil_yen, marks_ceil_R = _marks_ceiling(race_eff, race_pay, cost)
    realized = sum(_leg_payout(l, race_pay) for l in rs.legs)
    bt_yen: Dict[str, float] = defaultdict(float)
    for l in rs.legs:
        bt_yen[l.bet_type] += l.amount
    return RaceCeiling(
        rid=rid, date=rid[:8], tier=tier, cost=cost,
        plan_ceiling_yen=plan_ceil_yen, plan_ceiling_R=plan_ceil_R,
        marks_ceiling_yen=marks_ceil_yen, marks_ceiling_R=marks_ceil_R,
        realized_payout=realized, realized_R=(realized / cost * 100.0 if cost else 0.0),
        bt_yen=dict(bt_yen))


def _bucket_label(lo: float, hi: float) -> str:
    if hi == math.inf:
        return f"{int(lo)}%+"
    return f"{int(lo)}-{int(hi)}%"


def _distribution(values: List[float]) -> List[Tuple[str, int, float]]:
    out = []
    n = len(values) or 1
    for lo, hi in CEILING_BUCKETS:
        c = sum(1 for v in values if lo <= v < hi)
        out.append((_bucket_label(lo, hi), c, 100.0 * c / n))
    return out


def summarize(results: List[RaceCeiling], label: str) -> dict:
    n = len(results)
    shobu = [r for r in results if r.tier == "shobu"]
    normal = [r for r in results if r.tier == "normal"]
    plan_R = [r.plan_ceiling_R for r in results]
    marks_R = [r.marks_ceiling_R for r in results]
    realized_R = [r.realized_R for r in results]

    # 券種別予算配分 (全体)
    bt_total: Dict[str, float] = defaultdict(float)
    cost_total = 0.0
    for r in results:
        cost_total += r.cost
        for bt, y in r.bt_yen.items():
            bt_total[bt] += y
    bt_share = {bt: 100.0 * y / cost_total for bt, y in bt_total.items()} if cost_total else {}

    def med(xs):
        return statistics.median(xs) if xs else 0.0

    # plan_ceiling が marks_ceiling を「取りこぼし」ている割合 (plan < marks の件数)
    n_under = sum(1 for r in results if r.marks_ceiling_R > r.plan_ceiling_R + 1)
    # plan_ceiling >= 1000% の件数 (現状で天井1000%超を狙えている買い目)
    n_plan_ge1000 = sum(1 for r in results if r.plan_ceiling_R >= 1000)
    # marks_ceiling >= 1000% (印の中に1000%超の配当があった件数 = 取りにいけば届いた)
    n_marks_ge1000 = sum(1 for r in results if r.marks_ceiling_R >= 1000)

    return {
        "label": label,
        "n_races": n,
        "n_shobu": len(shobu),
        "n_normal": len(normal),
        "cost_total": round(cost_total),
        "realized_payout_total": round(sum(r.realized_payout for r in results)),
        "roi_pct": round(100.0 * sum(r.realized_payout for r in results) / cost_total, 1)
                   if cost_total else 0.0,
        "hit_races": sum(1 for r in results if r.realized_payout > 0),
        "plan_ceiling_R_median": round(med(plan_R), 1),
        "plan_ceiling_R_median_shobu": round(med([r.plan_ceiling_R for r in shobu]), 1),
        "plan_ceiling_R_median_normal": round(med([r.plan_ceiling_R for r in normal]), 1),
        "marks_ceiling_R_median": round(med(marks_R), 1),
        "realized_R_median": round(med(realized_R), 1),
        "n_plan_ceiling_ge_1000": n_plan_ge1000,
        "n_marks_ceiling_ge_1000": n_marks_ge1000,
        "n_plan_under_marks": n_under,
        "plan_ceiling_distribution": _distribution(plan_R),
        "marks_ceiling_distribution": _distribution(marks_R),
        "bt_share_pct": {k: round(v, 1) for k, v in sorted(bt_share.items(),
                                                           key=lambda x: -x[1])},
    }


def print_summary(s: dict) -> None:
    print(f"\n{'=' * 78}")
    print(f"  {s['label']}  (買えたレース {s['n_races']}件 = 勝負 {s['n_shobu']} / 通常 {s['n_normal']})")
    print(f"{'=' * 78}")
    print(f"  実績: ROI {s['roi_pct']}% / 的中 {s['hit_races']}R / "
          f"投入 {s['cost_total']:,}円 → 払戻 {s['realized_payout_total']:,}円")
    print(f"\n  ── 天井R 中央値 ──")
    print(f"    我々の買い目の天井 (plan): {s['plan_ceiling_R_median']}%  "
          f"[勝負R {s['plan_ceiling_R_median_shobu']}% / 通常R {s['plan_ceiling_R_median_normal']}%]")
    print(f"    AI印4頭で取れた天井 (marks/後知恵): {s['marks_ceiling_R_median']}%")
    print(f"    実際の回収率 中央値 (realized): {s['realized_R_median']}%")
    print(f"\n  ── 我々の買い目の天井R 分布 (plan_ceiling) ──")
    for lbl, c, pct in s["plan_ceiling_distribution"]:
        bar = "#" * int(pct / 2)
        print(f"    {lbl:>10}: {c:>4}件 ({pct:4.1f}%) {bar}")
    print(f"\n  ── AI印4頭で取れた天井R 分布 (marks_ceiling・後知恵上限) ──")
    for lbl, c, pct in s["marks_ceiling_distribution"]:
        bar = "#" * int(pct / 2)
        print(f"    {lbl:>10}: {c:>4}件 ({pct:4.1f}%) {bar}")
    print(f"\n  ── 予算配分 (券種別 %) ──")
    for bt, pct in s["bt_share_pct"].items():
        print(f"    {bt:>11}: {pct:5.1f}%")
    print(f"\n  ── 保守性の指標 ──")
    print(f"    買い目の天井>=1000% のレース: {s['n_plan_ceiling_ge_1000']} / {s['n_races']}件")
    print(f"    印の中に1000%超があった (取りにいけば届いた): {s['n_marks_ceiling_ge_1000']} / {s['n_races']}件")
    print(f"    買い目の天井 < 印の天井 (取りこぼし): {s['n_plan_under_marks']} / {s['n_races']}件")


def run_period(label: str, start: str, end: str, *, per_race_cap: int,
               bankroll: int) -> dict:
    print(f"\n{'#' * 78}\n  期間 {label}: {start} 〜 {end}\n{'#' * 78}")
    races = load_predictions_races(start_date=start, end_date=end)
    codes = [str(r.get("race_id") or "") for r in races if r.get("race_id")]
    print(f"  predictions: {len(races)} races / haraimodoshi 読込中...")
    haraimodoshi = load_haraimodoshi(codes)
    print(f"  haraimodoshi: {len(haraimodoshi)}")
    results: List[RaceCeiling] = []
    for r in races:
        rid = str(r.get("race_id") or "")
        race_pay = haraimodoshi.get(rid)
        if not race_pay or not race_pay.get("tansho"):
            continue
        if is_obstacle(r):
            continue
        rc = analyze_race(r, race_pay, per_race_cap=per_race_cap, bankroll=bankroll)
        if rc is not None:
            results.append(rc)
    s = summarize(results, label)
    print_summary(s)
    return s


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--p1-start", default=DEFAULT_P1_START)
    p.add_argument("--p1-end", default=DEFAULT_P1_END)
    p.add_argument("--p2-start", default=DEFAULT_P2_START)
    p.add_argument("--p2-end", default=DEFAULT_P2_END)
    p.add_argument("--per-race-cap", type=int, default=DEFAULT_PER_RACE_CAP)
    p.add_argument("--bankroll", type=int, default=DEFAULT_BANKROLL)
    p.add_argument("--output", default=DEFAULT_OUTPUT)
    p.add_argument("--skip-p2", action="store_true")
    return p.parse_args()


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                          errors="replace")
        except (AttributeError, ValueError):
            pass
    args = parse_args()
    print(f"[設定] per_race_cap={args.per_race_cap} (勝負R) / bankroll={args.bankroll}")
    out = {"tool": "ceiling_distribution", "session": 168,
           "per_race_cap": args.per_race_cap, "bankroll": args.bankroll,
           "sizer": "shobu_rate (本番)", "periods": []}
    out["periods"].append(run_period("P1 (健全直近)", args.p1_start, args.p1_end,
                                     per_race_cap=args.per_race_cap, bankroll=args.bankroll))
    if not args.skip_p2:
        out["periods"].append(run_period("P2 (健全旧)", args.p2_start, args.p2_end,
                                         per_race_cap=args.per_race_cap, bankroll=args.bankroll))
    out_path = config.ml_dir() / args.output
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n結果出力: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
