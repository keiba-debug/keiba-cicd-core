#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""fixed_grade_v2 見送りゲートの実払戻検証 (Session 163 / 宿題: [[bet-template-lab]] 末尾)

★検証する仮説★: fixed_grade_v2 の見送りゲート
  「このレースで作れる最高の合成オッズ (配当の天井) < SKIP_MAX_ODDS_FLOOR (=5.0倍) なら降りる」
  は、 本当に「買わない方が良いレース」を捨てているか? それとも
  [[feedback_odds_gate_hindsight]] の罠 (オッズ条件ゲートは cache の確定オッズで良く見えても
  predictions の直前オッズ実払戻では消える) か?

★検証方法 (後知恵を排す)★:
  - レース源 = ★predictions.json (vb_refresh 直前オッズ = 本番ゲート判定と同条件・リークなし)★。
    合成オッズ (ゲートの判定変数) は process_race が predictions の odds から作る = 直前オッズ。
    cache (確定オッズ) で判定すると後知恵になる ([[feedback_odds_gate_hindsight]])。
  - 精算 = ★haraimodoshi 実払戻★ (combo の cache payout 近似は使わない・W9/教訓 [[feedback_combo_backtest_settlement]])。
  - サイザー = fixed_grade_v1 (= ゲート無し本体)。 各レースに「ゲートが降りるか」フラグを付け、
    keep 群 (買う) / skip 群 (降りる) の実払戻 ROI を分けて集計。
    ★決定的比較★: skip 群 (降りる対象) の実 ROI が keep 群以上なら、 ゲートは儲かるレースを
    捨てている = 害 (後知恵の罠)。 skip 群が明確に低ければゲートは正当 (本当に買わない方が良い)。
  - 閾値 floor を sweep (0=ゲート無し / 3 / 4 / 5 / 6 / 7 / 8倍) し、 各 floor での
    「全体 ROI」「skip 群 ROI / keep 群 ROI」「skip レース数 (降り率)」を出す。

CLI:
    python -m ml.analyze.validate_v2_skip_gate
    python -m ml.analyze.validate_v2_skip_gate --start 2026-01 --end 2026-03-16
    python -m ml.analyze.validate_v2_skip_gate --floors 0,3,4,5,6,7,8 --bootstrap 1000
"""

from __future__ import annotations

import argparse
import io
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.analyze.backtest_bet_templates import load_haraimodoshi  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.strategies import bettype_selection as bs  # noqa: E402
from ml.strategies import bettype_sizing as sz  # noqa: E402
from ml.utils.roi import Bet, calc_roi  # noqa: E402

DEFAULT_BANKROLL = 10000
DEFAULT_PER_RACE_CAP = 3000
DEFAULT_FLOORS = "0,3,4,5,6,7,8"


# ---------------------------------------------------------------------------
# 1 レースを v1 (ゲート無し本体) でサイジングし、 実払戻で精算
# ---------------------------------------------------------------------------

def _leg_payout(leg: sz.SizedLeg, race_pay: dict) -> float:
    """SizedLeg の実払戻 (haraimodoshi・100円あたり payout × amount/100)。 ハズレ=0。"""
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


@dataclass
class RaceResult:
    rid: str
    date: str
    max_synth: Optional[float]   # このレースで作れる最高の合成オッズ (ゲートの判定変数・直前オッズ)
    cost: float
    payout: float
    bets: List[Bet] = field(default_factory=list)

    @property
    def hit(self) -> bool:
        return self.payout > 0


def size_and_settle(pred_race: dict, race_pay: dict, *,
                    strategy: str, bankroll: int, per_race_cap: int
                    ) -> Optional[RaceResult]:
    """1 レースを fixed_grade_v1 (ゲート無し) でサイジング → 実払戻で精算。

    ★ゲート無し本体 (size_race_fixed_grade) を使う★。 各レースに max 合成オッズを付けて返し、
    集計側で floor ごとに keep/skip を切る (= 同じサイジング結果を floor 横断で再利用)。
    """
    sel = bs.evaluate_and_select(pred_race, strategy=strategy, ev_floor=bs.DEFAULT_EV_FLOOR)
    if sel is None:
        return None
    race_eff = be.process_race(pred_race, axis=sel.axis_umaban)
    if race_eff is None:
        return None
    # ★ゲート無し本体★ = size_race_fixed_grade (v1 配分。 floor は集計側で切るのでここは 0)。
    #   ※注: v1 と v2 は配分割合 (FIXED_SHARES vs FIXED_SHARES_V2) が違うため、 ゲート単独の
    #     寄与を見るには配分は固定すべき。 ここでは ★v2 の配分 (FIXED_SHARES_V2)★ で買い目を作り、
    #     その上で floor だけ動かす = 「v2 の買い方で、 見送りゲートの floor を変えたら ROI が
    #     どう動くか」を測る (= ゲートの純寄与)。 配分を v1 にしたい場合は _shares_table を外す。
    rs = sz.size_race_fixed_grade(
        race_eff, sel, bankroll=bankroll, per_race_cap=per_race_cap,
        _shares_table=sz.FIXED_SHARES_V2, _skip_max_odds_floor=0.0)
    max_synth = sz._max_synthetic_odds(race_eff)
    rid = str(pred_race["race_id"])
    date = rid[:8]
    bets: List[Bet] = []
    for leg in rs.legs:
        payout = _leg_payout(leg, race_pay)
        bets.append(Bet(race_id=rid, cost=float(leg.amount), payout=float(payout),
                        is_hit=payout > 0, odds=float(leg.leg_odds or 0),
                        bet_type=leg.bet_type))
    cost = sum(b.cost for b in bets)
    payout = sum(b.payout for b in bets)
    return RaceResult(rid=rid, date=date, max_synth=max_synth,
                      cost=cost, payout=payout, bets=bets)


# ---------------------------------------------------------------------------
# floor ごとの keep/skip 集計
# ---------------------------------------------------------------------------

@dataclass
class ArmSummary:
    floor: float
    n_total: int          # ゲート判定対象レース (max_synth が取れたレース)
    n_skip: int           # ゲートが降りるレース
    n_keep: int           # ゲートが買うレース
    keep_roi: float
    keep_cost: float
    keep_payout: float
    keep_ci_low: float
    keep_ci_high: float
    skip_roi: float       # ★降りる対象を「もし買っていたら」の実 ROI (後知恵チェックの核心)
    skip_cost: float
    skip_payout: float
    skip_hit_rate: float
    keep_hit_rate: float


def summarize_floor(results: List[RaceResult], floor: float, *, bootstrap_n: int
                    ) -> ArmSummary:
    """floor で keep/skip を切り、 各群の実払戻 ROI を出す。

    max_synth が None (オッズ全欠損) のレースは ★ゲートは降りない★ (本体と同じ安全側=買う) →
    keep 群に入れる。 floor=0 は全レース keep (ゲート無し)。
    """
    keep_bets: List[Bet] = []
    skip_bets: List[Bet] = []
    n_skip = n_keep = 0
    keep_hit = skip_hit = 0
    for r in results:
        # 本体ロジックと同一: floor>0 かつ max_synth が取れて floor 未満 → skip。 それ以外 keep。
        is_skip = floor > 0 and r.max_synth is not None and r.max_synth < floor
        if is_skip:
            n_skip += 1
            skip_bets.extend(r.bets)
            if r.hit:
                skip_hit += 1
        else:
            n_keep += 1
            keep_bets.extend(r.bets)
            if r.hit:
                keep_hit += 1
    keep_roi = calc_roi(keep_bets, bootstrap_n=bootstrap_n)
    skip_roi = calc_roi(skip_bets, bootstrap_n=0) if skip_bets else None
    return ArmSummary(
        floor=floor, n_total=len(results), n_skip=n_skip, n_keep=n_keep,
        keep_roi=keep_roi.roi, keep_cost=keep_roi.cost, keep_payout=keep_roi.payout,
        keep_ci_low=keep_roi.ci_low, keep_ci_high=keep_roi.ci_high,
        skip_roi=(skip_roi.roi if skip_roi else 0.0),
        skip_cost=(skip_roi.cost if skip_roi else 0.0),
        skip_payout=(skip_roi.payout if skip_roi else 0.0),
        skip_hit_rate=(skip_hit / n_skip * 100 if n_skip else 0.0),
        keep_hit_rate=(keep_hit / n_keep * 100 if n_keep else 0.0),
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--start", default="2026-01", help="predictions 期間開始 (YYYY-MM)")
    p.add_argument("--end", default="2026-03-16", help="predictions 期間終了 (YYYY-MM-DD)")
    p.add_argument("--strategy", default="concentrate",
                   help="軸選定 strategy (本番 = concentrate)")
    p.add_argument("--floors", default=DEFAULT_FLOORS,
                   help="検証する見送り floor (カンマ区切り・0=ゲート無し)")
    p.add_argument("--bootstrap", type=int, default=1000)
    p.add_argument("--bankroll", type=int, default=DEFAULT_BANKROLL)
    p.add_argument("--per-race-cap", type=int, default=DEFAULT_PER_RACE_CAP)
    return p.parse_args()


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                          errors="replace")
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
    print(f"  haraimodoshi loaded: {len(haraimodoshi)}")

    # 各レースを v2 配分でサイジング → 実払戻精算 (floor 横断で再利用)
    results: List[RaceResult] = []
    n_no_result = 0
    for r in races:
        rid = str(r.get("race_id") or "")
        race_pay = haraimodoshi.get(rid)
        # 結果未確定 / 中止 (tansho 払戻が無い) は除外 = 本番で投票しても精算できないレース
        if not race_pay or not race_pay.get("tansho"):
            n_no_result += 1
            continue
        res = size_and_settle(r, race_pay, strategy=args.strategy,
                              bankroll=args.bankroll, per_race_cap=args.per_race_cap)
        if res is None or not res.bets:
            continue
        results.append(res)
    print(f"  評価レース: {len(results)} (結果未確定/買い目無しで除外 {n_no_result}+)")

    # max_synth 分布 (ゲートの判定変数)
    synths = sorted(r.max_synth for r in results if r.max_synth is not None)
    if synths:
        q = lambda f: synths[min(len(synths) - 1, int(len(synths) * f))]
        print(f"  max合成オッズ分布: min={synths[0]:.1f} "
              f"Q25={q(0.25):.1f} 中央={q(0.5):.1f} Q75={q(0.75):.1f} max={synths[-1]:.1f}")

    print(f"\n{'='*100}")
    print(f"  見送りゲート floor sweep (predictions 直前オッズ判定・haraimodoshi 実払戻)")
    print(f"  {'floor':>6}{'降り率':>9}{'skip的中':>9}{'keep的中':>9}"
          f"{'  keep ROI (買う群)':>22}{'  skip ROI (降りた群=もし買えば)':>30}")
    print(f"  {'-'*96}")
    base = None
    for fl in floors:
        s = summarize_floor(results, fl, bootstrap_n=args.bootstrap)
        if fl == 0:
            base = s
        skip_pct = s.n_skip / s.n_total * 100 if s.n_total else 0.0
        keep_str = (f"{s.keep_roi:6.1f}% [{s.keep_ci_low:.0f},{s.keep_ci_high:.0f}]"
                    f" n={s.n_keep}")
        if s.n_skip:
            skip_str = f"{s.skip_roi:6.1f}% (的中{s.skip_hit_rate:.0f}%, n={s.n_skip})"
        else:
            skip_str = "-"
        print(f"  {fl:>6.0f}{skip_pct:>8.1f}%{s.skip_hit_rate:>8.0f}%{s.keep_hit_rate:>8.0f}%"
              f"{keep_str:>22}{skip_str:>30}")
    print(f"  {'-'*96}")
    print(f"  keep ROI=ゲートが買うレースの実払戻 ROI / skip ROI=降りた対象を『もし買っていたら』の実 ROI")
    print(f"  ★判定★: skip ROI < keep ROI なら見送りは正当 (儲からないレースを捨てている)。")
    print(f"          skip ROI >= keep ROI なら見送りは害 ([[feedback_odds_gate_hindsight]] の罠)。")

    # 結論サマリ (本番 floor=5.0 を基準に)
    prod = summarize_floor(results, sz.SKIP_MAX_ODDS_FLOOR, bootstrap_n=args.bootstrap)
    print(f"\n=== 本番 floor={sz.SKIP_MAX_ODDS_FLOOR} の判定 ===")
    if base:
        print(f"  ゲート無し (全レース)  : ROI {base.keep_roi:.1f}%  n={base.n_keep}")
    print(f"  ゲート ON (keep=買う)  : ROI {prod.keep_roi:.1f}%  n={prod.n_keep}  "
          f"(降り {prod.n_skip}R = {prod.n_skip/prod.n_total*100:.1f}%)")
    if prod.n_skip:
        print(f"  降りた {prod.n_skip}R の実 ROI : {prod.skip_roi:.1f}%  (的中 {prod.skip_hit_rate:.0f}%)")
        verdict = "✅ 正当 (降りた群が低 ROI)" if prod.skip_roi < prod.keep_roi - 1 else \
                  ("❌ 害 (降りた群の方が高 ROI=後知恵の罠)" if prod.skip_roi > prod.keep_roi + 1
                   else "△ 中立 (差が小さい・ゲートの価値は薄い)")
        print(f"  → {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
