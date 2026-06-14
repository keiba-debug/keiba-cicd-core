#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""買い方テンプレ ★天井視点★ backtest (Session 163 / ふくだ「天井を取る」指針)

[[payout-ceiling-strategy]]: ふくだ「回収率1000%超えは大きい・中オッズ10倍を一点で取れたら
万馬券等価」。 これまでラボ (backtest_bet_templates) は ★中央値ROI (トントン狙い)★ でしか
テンプレを評価していなかった。 本スクリプトは同じ haraimodoshi 実払戻で、 ★配当の天井★ を
測る別メトリクスでテンプレを並べ直す:

  - ROI            : 全体回収率 (損益基準・継続性のため掲載)
  - 的中率          : 1点でも当たったレース率
  - 最大単R回収      : 1レースで出た最高の回収倍率 (払戻/コスト)
  - 1000%超 回数/率  : レース単位回収率 >= 1000% のレース数と発生率 (★天井を取れた回数★)
  - 500%超 回数/率   : 同 >= 500% (中オッズ一点級)
  - 回収率分布 P50/P90/P99 : レース単位回収率の分位 (天井がどこにあるか)
  - 天井寄与         : 最高回収レース1本が総払戻に占める割合 (集中度=ホームラン依存度)

レース単位回収率 = (そのレースの全 Ticket 払戻合計) / (コスト合計) × 100。
「1000%超えを一発で取れるテンプレか」を見る正しい粒度。

★精算は haraimodoshi 実払戻★ (cache combo 近似は使わない。 [[feedback_combo_backtest_settlement]])。
印付けは marks_from_ranking (composite 降順) = ラボ backtest と同一パス。

CLI:
    python -m ml.analyze.backtest_template_ceiling
    python -m ml.analyze.backtest_template_ceiling --split-date 2026-01-01
    python -m ml.analyze.backtest_template_ceiling --source predictions --start 2026-01 --end 2026-03-16
"""

from __future__ import annotations

import argparse
import io
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.analyze.backtest_bet_templates import (  # noqa: E402
    cache_race_to_pred, load_haraimodoshi, ticket_payout,
)
from ml.strategies import bet_templates as bt  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.utils.backtest_cache import load_backtest_cache  # noqa: E402

CEILING_HIGH = 1000.0   # 「天井を取れた」基準 (回収率% / ふくだ「1000%超え」)
CEILING_MID = 500.0     # 中オッズ一点級 (回収率%)


@dataclass
class CeilingAgg:
    """1 テンプレの天井視点集計。 race_recoveries = レース単位の回収率% リスト。"""
    n_races: int = 0
    hit_races: int = 0
    cost: float = 0.0
    payout: float = 0.0
    race_recoveries: List[float] = field(default_factory=list)  # 各R回収率%
    max_race_payout: float = 0.0   # 最高回収レースの払戻額 (天井寄与用)

    def add_race(self, cost: float, payout: float):
        if cost <= 0:
            return
        self.n_races += 1
        self.cost += cost
        self.payout += payout
        rec = payout / cost * 100.0
        self.race_recoveries.append(rec)
        if payout > 0:
            self.hit_races += 1
        self.max_race_payout = max(self.max_race_payout, payout)

    @property
    def roi(self) -> float:
        return self.payout / self.cost * 100 if self.cost > 0 else 0.0

    @property
    def hit_rate(self) -> float:
        return self.hit_races / self.n_races * 100 if self.n_races else 0.0

    @property
    def max_recovery(self) -> float:
        return max(self.race_recoveries) if self.race_recoveries else 0.0

    def _count_ge(self, thr: float) -> int:
        return sum(1 for r in self.race_recoveries if r >= thr)

    @property
    def n_ge_1000(self) -> int:
        return self._count_ge(CEILING_HIGH)

    @property
    def n_ge_500(self) -> int:
        return self._count_ge(CEILING_MID)

    @property
    def rate_ge_1000(self) -> float:
        return self.n_ge_1000 / self.n_races * 100 if self.n_races else 0.0

    def percentile(self, p: float) -> float:
        """レース単位回収率の p 分位 (0-100)。 線形補間なしの単純最近傍。"""
        if not self.race_recoveries:
            return 0.0
        s = sorted(self.race_recoveries)
        idx = min(len(s) - 1, int(len(s) * p / 100.0))
        return s[idx]

    @property
    def ceiling_concentration(self) -> float:
        """最高回収レース1本が総払戻に占める割合% (ホームラン依存度)。"""
        return self.max_race_payout / self.payout * 100 if self.payout > 0 else 0.0


def _load_races(args) -> list:
    if args.source == "predictions":
        from ml.export_formation_backtest import load_predictions_races
        races = load_predictions_races(start_date=args.start, end_date=args.end)
        print(f"predictions.json: {len(races)} races ({args.start}~{args.end}, leak-free 直前オッズ)")
        return [("pred", r) for r in races]
    races = load_backtest_cache(path=Path(args.cache_path) if args.cache_path else None)
    print(f"backtest_cache: {len(races)} races")
    return [("cache", r) for r in races]


def run(tagged_races, *, template_names, split_date, source) -> Dict[str, CeilingAgg]:
    preds, codes = [], []
    for tag, raw in tagged_races:
        pred = raw if source == "predictions" else cache_race_to_pred(raw)
        if pred is None:
            continue
        rid = str(pred.get("race_id") or "")
        if split_date and rid[:8] < split_date:
            continue
        if source == "cache":
            # cache は finish_position で結果確定を判定 (1着が居れば確定)
            if not any(int(e.get("finish_position") or 99) == 1
                       for e in pred.get("entries", [])):
                continue
        preds.append(pred)
        codes.append(rid)
    print(f"  races={len(preds)}  loading haraimodoshi (実払戻)...")
    haraimodoshi = load_haraimodoshi(codes)
    print(f"  haraimodoshi loaded: {len(haraimodoshi)}")
    if source == "predictions":
        # predictions は finish 無し → haraimodoshi(tansho) の有無で結果確定を判定
        preds = [p for p in preds
                 if (haraimodoshi.get(str(p.get("race_id"))) or {}).get("tansho")]
        print(f"  結果確定 (haraimodoshi tansho あり): {len(preds)}")

    agg: Dict[str, CeilingAgg] = {n: CeilingAgg() for n in template_names}
    preds.sort(key=lambda p: str(p["race_id"]))
    for pred in preds:
        re_ = be.process_race(pred)
        if re_ is None or not re_.strengths:
            continue
        ranking = [s.umaban for s in re_.strengths]  # composite 降順
        marks = bt.marks_from_ranking(ranking)
        rpay = haraimodoshi.get(str(pred["race_id"]), {})
        for name in template_names:
            tickets = bt.apply_template(bt.get_template(name), marks)
            if not tickets:
                continue
            cost = 100.0 * len(tickets)
            payout = float(sum(ticket_payout(tk, rpay) for tk in tickets))
            agg[name].add_race(cost, payout)
    return agg


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--source", default="cache", choices=["cache", "predictions"],
                   help="predictions = 直前オッズ・リークなし (本番同条件)")
    p.add_argument("--cache-path", default=None)
    p.add_argument("--split-date", default=None, help="valid(>=)のみ (YYYY-MM-DD)")
    p.add_argument("--start", default="2026-01", help="predictions 期間開始 (YYYY-MM)")
    p.add_argument("--end", default="2026-03-16", help="predictions 期間終了")
    p.add_argument("--templates", default=None, help="カンマ区切り (既定=全テンプレ)")
    return p.parse_args()


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = parse_args()
    split = args.split_date.replace("-", "") if args.split_date else None
    names = ([x.strip() for x in args.templates.split(",")] if args.templates
             else bt.list_templates())

    tagged = _load_races(args)
    agg = run(tagged, template_names=names, split_date=split, source=args.source)

    print(f"\n{'='*108}")
    print(f"  ★天井視点★ テンプレ別 (flat 100円/点・haraimodoshi 実払戻・印=composite理論)")
    print(f"  {'template':<20}{'ROI':>7}{'的中':>6}{'最大回収':>9}"
          f"{'≥1000%':>8}{'≥500%':>8}{'P90':>7}{'P99':>8}{'天井依存':>8}")
    print(f"  {'-'*104}")
    # ROI でなく「1000%超え率」でソート (天井を取れる順)
    order = sorted(names, key=lambda n: agg[n].rate_ge_1000, reverse=True)
    for n in order:
        a = agg[n]
        t = bt.get_template(n)
        print(f"  {n:<20}{a.roi:>6.0f}%{a.hit_rate:>5.0f}%{a.max_recovery:>8.0f}%"
              f"{a.n_ge_1000:>4}({a.rate_ge_1000:>3.0f}%){a.n_ge_500:>8}"
              f"{a.percentile(90):>6.0f}%{a.percentile(99):>7.0f}%"
              f"{a.ceiling_concentration:>7.0f}%"
              + ("  [隔離]" if t.ringfenced else ""))
    print(f"  {'-'*104}")
    print(f"  最大回収=1レース最高の回収率 / ≥1000%・≥500%=レース単位回収率がその%以上のR数(発生率)")
    print(f"  P90/P99=レース回収率の分位(天井の高さ) / 天井依存=最高回収R1本が総払戻に占める割合(集中度)")
    print(f"\n  ★読み方 (ふくだ天井指針 [[payout-ceiling-strategy]]):★")
    print(f"   - ≥1000%率が高い = 天井を取れる回数が多い (ホームランを打てるテンプレ)")
    print(f"   - 天井依存が高い = 1本のホームラン頼み (分散大・安定しない) → 隔離資金向き")
    print(f"   - ROIが高くP90も高い = 控除率を埋めつつ天井もある = 本線候補")
    return 0


if __name__ == "__main__":
    sys.exit(main())
