#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""天井変種 backtest ハーネス (Session 168 / Part B)

★問い (ふくだ Session 168)★:
  現状サイザーは天井を抑えている (ceiling_distribution.py で実証: plan天井中央値480%・
  combo は逆オッズ配分で低配当点に厚い)。 ★天井を上げる「張り方」に変えると ROI/的中率/DD は
  どうなるか★? 後知恵ゲート (S162-165で害確定) ではなく、 ★配分の集中度だけ★ を変えて比較する。

★比較する変種 (全て本番 shobu_rate を土台に combo 配分だけ差し替え・選定/印は同一)★:
  - A0_current      : 逆オッズ・全券種 (= 本番そのもの。 基準)。
  - B1_flat         : フラット配分・全券種 (各点均等 → 高配当点も同額)。
  - B2_odds         : オッズ比例配分・全券種 (高配当点に厚く → 天井最大化)。
  - B3_sanren_flat  : フラット・三連系のみ (三連複+三連単に集中)。
  - B4_sanren_odds  : オッズ比例・三連系のみ (集中 × 天井最大化)。

★精算★: mykeibadb.haraimodoshi 実払戻 ([[feedback_combo_backtest_settlement]] 教訓)。
  per_race_cap=5200 固定 (本番=基準金額35000×勝負15%・bankroll 連動しない)。 累積PnLで maxDD。

★期間 (stale 期 2026-03-21〜06-07 を避ける・[[ml-cache-staleness-incident]])★:
  P1: 2026-01-04 〜 2026-03-15 (健全直近) / P2: 2025-09-01 〜 2025-12-31 (健全旧)。

★注意★: leg_odds (天井計算) と haraimodoshi は確定オッズ由来。 ここは ★配分の差★ を測るので
  全変種が同じオッズで精算され比較は公平 (見送り判定は無し=後知恵ゲートではない)。

★judge の視点 (ふくだに渡す論点)★:
  - ROI は上がるか/washか/下がるか (S165「買い目工夫では黒字化しない」が成り立つか)。
  - 的中率がどこまで落ち、 maxDD がどこまで膨らむか (= 上振れを買うコスト)。
  - 1000%超を実際に取れたレース数が増えるか ([[payout-ceiling-strategy]] の天井の価値)。

実行:
    python -m ml.analyze.bench_ceiling_variants
    python -m ml.analyze.bench_ceiling_variants --skip-p2
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
from ml.analyze.ceiling_distribution import (  # noqa: E402
    CEILING_BUCKETS, _bucket_label, _leg_payout, _plan_ceiling)
from ml.export_formation_backtest import load_predictions_races  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.strategies import bettype_selection as bs  # noqa: E402
from ml.strategies import bettype_sizing as sz  # noqa: E402
from ml.utils.filters import is_obstacle  # noqa: E402
from ml.utils.roi import max_drawdown, sharpe_ratio  # noqa: E402

DEFAULT_PER_RACE_CAP = 5200
DEFAULT_BANKROLL = 100000
DEFAULT_P1_START = "2026-01-04"
DEFAULT_P1_END = "2026-03-15"
DEFAULT_P2_START = "2025-09-01"
DEFAULT_P2_END = "2025-12-31"
DEFAULT_OUTPUT = "bench_ceiling_variants_results.json"

SANREN = frozenset({"sanrenpuku", "sanrentan"})

# (name, normal_combo_mode, shobu_combo_mode, allowed_types)。
#   A0〜B4 は ★normal/shobu とも同じモード★ = 純粋な uniform 比較 (combo配分の効果を分離)。
#   P_prod = ★本番採用ポリシー (Session168 ふくだ判断 A)★: 通常R flat + 勝負R odds。
VARIANTS: List[Tuple[str, str, str, Optional[frozenset]]] = [
    ("A0_current", "inverse", "inverse", None),
    ("B1_flat", "flat", "flat", None),
    ("B2_odds", "odds", "odds", None),
    ("B3_sanren_flat", "flat", "flat", SANREN),
    ("B4_sanren_odds", "odds", "odds", SANREN),
    ("P_prod", "flat", "odds", None),
]


@dataclass
class RaceOut:
    rid: str
    date: str
    cost: float
    payout: float
    plan_ceiling_R: float
    realized_R: float


@dataclass
class VariantSummary:
    name: str
    n_bet: int
    n_hit: int
    cost: float
    payout: float
    pnl: float
    roi: float
    win_rate: float
    median_race_roi: float
    plan_ceiling_R_median: float
    max_dd: float
    sharpe_monthly: float
    n_realized_ge_1000: int      # 実際に回収率1000%超を取れたレース
    n_realized_ge_300: int       # 実際に回収率300%超 (おいしい的中)
    ceiling_dist: List[Tuple[str, int]] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        d["cost"] = round(self.cost)
        d["payout"] = round(self.payout)
        d["pnl"] = round(self.pnl)
        d["roi"] = round(self.roi, 1)
        d["win_rate"] = round(self.win_rate, 1)
        d["median_race_roi"] = round(self.median_race_roi, 1)
        d["plan_ceiling_R_median"] = round(self.plan_ceiling_R_median, 1)
        d["max_dd"] = round(self.max_dd)
        d["sharpe_monthly"] = round(self.sharpe_monthly, 3)
        d["ceiling_dist"] = [[lbl, c] for lbl, c in self.ceiling_dist]
        return d


def size_variant(race_eff, sel, *, normal_mode: str, shobu_mode: str,
                 allowed: Optional[frozenset],
                 per_race_cap: int, bankroll: int) -> sz.RaceSizing:
    return sz.size_race_shobu_rate(
        race_eff, sel, bankroll=bankroll, per_race_cap=per_race_cap,
        combo_alloc_mode=normal_mode, shobu_combo_alloc_mode=shobu_mode,
        combo_allowed_types=allowed)


def settle_race(race_eff, sel, race_pay: dict, *, normal_mode, shobu_mode, allowed,
                per_race_cap, bankroll) -> Optional[RaceOut]:
    rs = size_variant(race_eff, sel, normal_mode=normal_mode, shobu_mode=shobu_mode,
                      allowed=allowed, per_race_cap=per_race_cap, bankroll=bankroll)
    if not rs.legs:
        return None
    cost = float(sum(l.amount for l in rs.legs))
    if cost <= 0:
        return None
    payout = sum(_leg_payout(l, race_pay) for l in rs.legs)
    _yen, plan_R = _plan_ceiling(rs)
    rid = str(race_eff.race_id)
    return RaceOut(rid=rid, date=rid[:8], cost=cost, payout=payout,
                   plan_ceiling_R=plan_R, realized_R=(payout / cost * 100.0))


def _ceiling_dist(values: List[float]) -> List[Tuple[str, int]]:
    return [(_bucket_label(lo, hi), sum(1 for v in values if lo <= v < hi))
            for lo, hi in CEILING_BUCKETS]


def aggregate(name: str, results: List[RaceOut]) -> VariantSummary:
    n_bet = len(results)
    n_hit = sum(1 for r in results if r.payout > 0)
    cost = sum(r.cost for r in results)
    payout = sum(r.payout for r in results)
    pnl = payout - cost
    roi = (payout / cost * 100.0) if cost else 0.0
    win_rate = (n_hit / n_bet * 100.0) if n_bet else 0.0
    race_rois = [r.realized_R for r in results]
    median_race_roi = statistics.median(race_rois) if race_rois else 0.0
    plan_R = [r.plan_ceiling_R for r in results]
    plan_med = statistics.median(plan_R) if plan_R else 0.0

    # daily cumulative PnL → maxDD
    by_date: Dict[str, float] = defaultdict(float)
    for r in results:
        by_date[r.date] += (r.payout - r.cost)
    cum = []
    acc = 0.0
    for d in sorted(by_date.keys()):
        acc += by_date[d]
        cum.append(acc)
    max_dd_amount, _pct = max_drawdown(cum) if cum else (0.0, 0.0)

    # monthly sharpe
    m_pnl: Dict[str, float] = defaultdict(float)
    m_cost: Dict[str, float] = defaultdict(float)
    for r in results:
        ym = r.date[:6]
        m_pnl[ym] += (r.payout - r.cost)
        m_cost[ym] += r.cost
    m_ret = [(m_pnl[k] / m_cost[k] * 100.0) if m_cost[k] else 0.0
             for k in sorted(m_pnl.keys())]
    sharpe = sharpe_ratio(m_ret, periods_per_year=12) if len(m_ret) >= 2 else 0.0

    return VariantSummary(
        name=name, n_bet=n_bet, n_hit=n_hit, cost=cost, payout=payout, pnl=pnl,
        roi=roi, win_rate=win_rate, median_race_roi=median_race_roi,
        plan_ceiling_R_median=plan_med, max_dd=abs(max_dd_amount),
        sharpe_monthly=sharpe,
        n_realized_ge_1000=sum(1 for r in results if r.realized_R >= 1000),
        n_realized_ge_300=sum(1 for r in results if r.realized_R >= 300),
        ceiling_dist=_ceiling_dist(plan_R))


def run_period(label: str, start: str, end: str, *, per_race_cap: int,
               bankroll: int) -> dict:
    print(f"\n{'#' * 90}\n  期間 {label}: {start} 〜 {end}\n{'#' * 90}")
    races = load_predictions_races(start_date=start, end_date=end)
    codes = [str(r.get("race_id") or "") for r in races if r.get("race_id")]
    print(f"  predictions: {len(races)} races / haraimodoshi 読込中...")
    haraimodoshi = load_haraimodoshi(codes)
    print(f"  haraimodoshi: {len(haraimodoshi)}")

    # 選定+process は変種間で共通 → 1 回だけ計算してキャッシュ
    prepared: List[Tuple[object, object, dict]] = []
    for r in races:
        rid = str(r.get("race_id") or "")
        race_pay = haraimodoshi.get(rid)
        if not race_pay or not race_pay.get("tansho"):
            continue
        if is_obstacle(r):
            continue
        sel = bs.evaluate_and_select(r, strategy="concentrate", ev_floor=bs.DEFAULT_EV_FLOOR)
        if sel is None:
            continue
        race_eff = be.process_race(r, axis=sel.axis_umaban)
        if race_eff is None:
            continue
        prepared.append((race_eff, sel, race_pay))
    print(f"  prepared races: {len(prepared)}")

    summaries: Dict[str, VariantSummary] = {}
    for name, normal_mode, shobu_mode, allowed in VARIANTS:
        results: List[RaceOut] = []
        for race_eff, sel, race_pay in prepared:
            ro = settle_race(race_eff, sel, race_pay, normal_mode=normal_mode,
                             shobu_mode=shobu_mode, allowed=allowed,
                             per_race_cap=per_race_cap, bankroll=bankroll)
            if ro is not None:
                results.append(ro)
        summaries[name] = aggregate(name, results)
    print_table(label, summaries)
    return {"label": label, "start": start, "end": end,
            "n_prepared": len(prepared),
            "variants": {n: s.as_dict() for n, s in summaries.items()}}


def print_table(label: str, summaries: Dict[str, VariantSummary]) -> None:
    print(f"\n=== {label} ===")
    print(f"  {'variant':<16}{'n_bet':>7}{'ROI':>8}{'winR':>8}{'medR':>8}"
          f"{'天井中央':>9}{'maxDD':>10}{'Shrp':>7}{'≥1000%':>8}{'≥300%':>7}")
    print(f"  {'-' * 96}")
    for name, s in summaries.items():
        print(f"  {name:<16}{s.n_bet:>7}{s.roi:>7.1f}%{s.win_rate:>7.1f}%"
              f"{s.median_race_roi:>7.1f}%{s.plan_ceiling_R_median:>8.0f}%"
              f"{s.max_dd:>10.0f}{s.sharpe_monthly:>7.2f}"
              f"{s.n_realized_ge_1000:>8}{s.n_realized_ge_300:>7}")
    print(f"  {'-' * 96}")
    print(f"  ── 天井R 分布 (plan_ceiling・件数) ──")
    buckets = [lbl for lbl, _ in summaries["A0_current"].ceiling_dist]
    print(f"  {'variant':<16}" + "".join(f"{b:>11}" for b in buckets))
    for name, s in summaries.items():
        row = f"  {name:<16}"
        for _lbl, c in s.ceiling_dist:
            row += f"{c:>11}"
        print(row)
    print(f"\n  ★judge★: ROI が上がるか/wash か / 的中率↓・maxDD↑ の度合い / ≥1000% 的中数の増加")


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
    print(f"[設定] per_race_cap={args.per_race_cap} / bankroll={args.bankroll}")
    print(f"[変種] {[v[0] for v in VARIANTS]}")
    out = {"tool": "bench_ceiling_variants", "session": 168,
           "per_race_cap": args.per_race_cap, "bankroll": args.bankroll,
           "variants": [{"name": n, "normal_mode": nm, "shobu_mode": sm,
                         "allowed_types": (sorted(a) if a else None)}
                        for n, nm, sm, a in VARIANTS],
           "periods": []}
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
