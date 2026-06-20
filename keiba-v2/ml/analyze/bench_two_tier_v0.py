#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""two_tier_v0 検証ハーネス (Session 165 / three_tier 再走)

★目的★:
  two_tier_v0 (勝負15% / 見送り ceiling<400%・様子見廃止) を predictions 実払戻 (健全期間) で
  バックテストし、 fixed_grade_v2 (本番) と並列比較。 Session 164 bench の 4致命的欠陥を是正:
    ① ceiling_R が確定combo オッズ依存 (後知恵) → ★本 bench でも同じ依存。 ただし docstring に
       明記し、 改善傾向の方向性確認に用途を限定 (ライブ再現性検証は別宿題)★。
    ② kanshi 層不発火 → ★様子見層を廃止 (Q3)。 two_tier は勝負/見送りのみ★。
    ③ v2_baseline が bankroll=30000 で89%破綻 → ★bankroll=1,000,000 既定 (Q2) で破綻させず比較★。
    ④ same-case が AI印無関係の hindsight → ★AI印4頭(◎○▲△=axis+partners[:3])で組める券面の
       max_payout に絞り直す (Q4)★。

★4戦略を並列精算★:
  - ★v2_baseline★: fixed_grade_v2 + per_race_cap = bankroll * 15% (= 勝負R と同 cap で公平比較)。
      ★全レース買う★ (見送りなし)。 two_tier の見送りゲートの純寄与を測る基準。
  - ★v2_cap3000★: fixed_grade_v2 + per_race_cap = 3000円固定 (Session 163 実本番値・参考)。
  - ★two_tier_v0★: 2分類。 勝負15% (tansho_ippon 4条件 ∧ ceiling>=400%) / 見送り (それ以外)。
  - ★shobu_only_no_ceiling★: 勝負15% だが ceiling ゲート無し (tansho_ippon のみで買う)。
      = ceiling_floor_R=400% の純寄与を測る対照群 (これより two_tier が良ければゲートが効く)。

★期間 (stale 期間 [[ml-cache-staleness-incident]] 2026-03-21〜2026-06-07 を避ける)★:
  P1: 2026-01-04 〜 2026-03-15  (健全 / 直近本番想定)
  P2: 2025-09-01 〜 2025-12-31  (健全 / 旧期間)

★精算★: mykeibadb.haraimodoshi 実払戻 ([[feedback_combo_backtest_settlement]] 教訓)。

★日次精算★: 当日 cost/payout を集計 → 翌日残高 = 前日残高 + (payout - cost)。
  bankroll が動的 cap (全戦略 bankroll 連動) に効く。 bankroll=1,000,000 なら破綻しない想定。

★出力★:
  - stdout テーブル (戦略 × ROI/maxDD/medianROI/Sharpe/winR/分類別件数)
  - JSON: data3/ml/bench_two_tier_v0_results.json
  - same-case (AI印4頭で組める券面 max_payout が大きいのに two_tier が見送ったレース) の追跡

CLI:
    python -m ml.analyze.bench_two_tier_v0
    python -m ml.analyze.bench_two_tier_v0 --bankrolls 1000000
    python -m ml.analyze.bench_two_tier_v0 --p1-start 2026-01-04 --p1-end 2026-03-15 --skip-p2
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
from ml.strategies import three_tier_sizing as tts  # noqa: E402
from ml.strategies import two_tier_sizing as tt  # noqa: E402
from ml.utils.filters import is_obstacle  # noqa: E402
from ml.utils.roi import Bet, max_drawdown, sharpe_ratio  # noqa: E402


# ===========================================================================
# 既定 (CLI 引数 default)
# ===========================================================================

DEFAULT_P1_START = "2026-01-04"
DEFAULT_P1_END = "2026-03-15"
DEFAULT_P2_START = "2025-09-01"
DEFAULT_P2_END = "2025-12-31"
DEFAULT_BANKROLLS = "1000000"      # ★Q2: bankroll=1,000,000 で破綻させず比較★
DEFAULT_V2_CAP3000 = 3000          # 参考: Session 163 実本番 cap
DEFAULT_OUTPUT = "bench_two_tier_v0_results.json"

# same-case 検出条件 (★Q4: AI印4頭で組める券面に絞る★)。
SAMECASE_FAV_ODDS_MAX = 2.5        # 1番人気が 2.5 倍未満 (= 堅い◎)
SAMECASE_CEILING_MAX_R = 400.0     # ceiling 予測が 400% 未満 (= two_tier で見送り対象)
SAMECASE_PAYOUT_MIN_R = 400.0      # AI印4頭で組める券面の実払戻が 400% 超 (= 取れたはずの妙味)


# ===========================================================================
# 1 レース精算 (戦略別)
# ===========================================================================

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


@dataclass
class RaceResult:
    """1 レース × 1 戦略の精算結果。"""
    strategy: str
    rid: str
    date: str
    tier: str              # 'shobu' / 'miokuri' (v2 系は 'v2_normal' / 'v2_low_ceiling')
    cost: float
    payout: float
    bets: List[Bet] = field(default_factory=list)
    ceiling_R: Optional[float] = None
    fav_odds: Optional[float] = None


def _race_fav_odds(pred_race: dict) -> Optional[float]:
    """1 番人気 (popularity==1) の単勝オッズ。 entries に無ければ最小 odds をフォールバック。"""
    entries = pred_race.get("entries") or []
    fav = next((e for e in entries
                if e.get("popularity") == 1 and (e.get("odds") or 0) > 0), None)
    if fav is not None:
        return float(fav["odds"])
    odds_present = [float(e["odds"]) for e in entries
                    if e.get("odds") is not None and float(e.get("odds") or 0) > 0]
    return min(odds_present) if odds_present else None


def _settle_legs(rid: str, rs: sz.RaceSizing, race_pay: dict) -> List[Bet]:
    bets: List[Bet] = []
    for leg in rs.legs:
        payout = _leg_payout(leg, race_pay)
        bets.append(Bet(race_id=rid, cost=float(leg.amount), payout=float(payout),
                        is_hit=payout > 0, odds=float(leg.leg_odds or 0),
                        bet_type=leg.bet_type))
    return bets


def _size_v2_capped(race_eff, sel, *, bankroll: int, cap: int) -> sz.RaceSizing:
    """fixed_grade_v2 + 任意 cap。"""
    return sz.size_race_fixed_grade_v2(
        race_eff, sel, bankroll=bankroll, per_race_cap=cap)


def _size_two_tier_v0(race_eff, sel, *, bankroll: int, pred_race: dict) -> sz.RaceSizing:
    """two_tier_v0 (2分類)。"""
    return tt.size_race_two_tier(
        race_eff, sel, bankroll=bankroll, pred_race=pred_race)


def _size_shobu_only_no_ceiling(race_eff, sel, *, bankroll: int,
                                pred_race: dict) -> sz.RaceSizing:
    """勝負15% だが ceiling ゲート無し (tansho_ippon のみで買う・ceiling は無視)。

    ceiling_floor_R=0.0 を渡すことで ceiling ゲートを完全無効化。 勝負判定は同じ。
    = two_tier から ceiling ゲートだけ抜いた対照群。
    """
    return tt.size_race_two_tier(
        race_eff, sel, bankroll=bankroll, pred_race=pred_race,
        ceiling_floor_R=0.0)


# ---------------------------------------------------------------------------
# 戦略ラッパー (1 レース → RaceResult)
# ---------------------------------------------------------------------------

def _tier_from_warnings(rs: sz.RaceSizing) -> str:
    """two_tier 系 RaceSizing の warnings 先頭から tier を抽出。"""
    if rs.warnings:
        head = rs.warnings[0]
        if "two_tier=shobu" in head:
            return "shobu"
        if "two_tier=miokuri" in head:
            return "miokuri"
    return "miokuri" if not rs.legs else "shobu"


def _classify_for_v2(race_eff) -> str:
    """v2 系の便宜 tier ラベル (集計分離用)。 ceiling<400%=low_ceiling・他は normal。"""
    ceiling_R = tts.compute_ceiling_R(race_eff)
    if math.isfinite(ceiling_R) and ceiling_R < tt.CEILING_FLOOR_DEFAULT_R:
        return "v2_low_ceiling"
    return "v2_normal"


def settle_one_race(pred_race: dict, race_pay: dict, *,
                    strategy: str, bankroll: int) -> Optional[RaceResult]:
    """1 レースを 1 戦略でサイジング → 実払戻精算 → RaceResult を返す。"""
    sel = bs.evaluate_and_select(pred_race, strategy="concentrate",
                                 ev_floor=bs.DEFAULT_EV_FLOOR)
    if sel is None:
        return None
    race_eff = be.process_race(pred_race, axis=sel.axis_umaban)
    if race_eff is None:
        return None

    rid = str(pred_race.get("race_id") or race_eff.race_id)
    date = rid[:8]
    fav_odds = _race_fav_odds(pred_race)
    ceiling_R = tts.compute_ceiling_R(race_eff)

    if strategy == "v2_baseline":
        cap = max(0, int(bankroll * tt.TIER_SHARE_SHOBU))
        rs = _size_v2_capped(race_eff, sel, bankroll=bankroll, cap=cap)
        tier = _classify_for_v2(race_eff)
    elif strategy == "v2_cap3000":
        rs = _size_v2_capped(race_eff, sel, bankroll=bankroll, cap=DEFAULT_V2_CAP3000)
        tier = _classify_for_v2(race_eff)
    elif strategy == "two_tier_v0":
        rs = _size_two_tier_v0(race_eff, sel, bankroll=bankroll, pred_race=pred_race)
        tier = _tier_from_warnings(rs)
    elif strategy == "shobu_only_no_ceiling":
        rs = _size_shobu_only_no_ceiling(race_eff, sel, bankroll=bankroll,
                                         pred_race=pred_race)
        tier = _tier_from_warnings(rs)
    else:
        raise ValueError(f"unknown strategy: {strategy}")

    bets = _settle_legs(rid, rs, race_pay) if rs.legs else []
    cost = sum(b.cost for b in bets)
    payout = sum(b.payout for b in bets)
    return RaceResult(strategy=strategy, rid=rid, date=date, tier=tier,
                      cost=cost, payout=payout, bets=bets,
                      ceiling_R=ceiling_R, fav_odds=fav_odds)


# ===========================================================================
# 集計
# ===========================================================================

@dataclass
class StrategySummary:
    strategy: str
    bankroll_init: int
    bankroll_end: float
    n_races: int
    n_bet_races: int
    n_hit_races: int
    cost_total: float
    payout_total: float
    pnl: float
    roi: float
    median_race_roi: float
    win_rate: float
    max_dd: float
    max_dd_pct: float
    sharpe_monthly: float
    n_bankrupt_days: int = 0
    tier_counts: Dict[str, int] = field(default_factory=dict)
    tier_roi: Dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "strategy": self.strategy,
            "bankroll_init": self.bankroll_init,
            "bankroll_end": round(self.bankroll_end, 0),
            "n_races": self.n_races,
            "n_bet_races": self.n_bet_races,
            "n_hit_races": self.n_hit_races,
            "cost_total": round(self.cost_total, 0),
            "payout_total": round(self.payout_total, 0),
            "pnl": round(self.pnl, 0),
            "roi": round(self.roi, 2),
            "median_race_roi": round(self.median_race_roi, 2),
            "win_rate": round(self.win_rate, 2),
            "max_dd": round(self.max_dd, 0),
            "max_dd_pct": round(self.max_dd_pct, 2),
            "sharpe_monthly": round(self.sharpe_monthly, 3),
            "n_bankrupt_days": self.n_bankrupt_days,
            "tier_counts": dict(self.tier_counts),
            "tier_roi": {k: round(v, 2) for k, v in self.tier_roi.items()},
        }


def _race_roi(r: RaceResult) -> Optional[float]:
    if r.cost <= 0:
        return None
    return (r.payout / r.cost) * 100.0


def _aggregate(strategy: str, bankroll_init: int,
               results: List[RaceResult], daily_pnl: List[float],
               n_bankrupt_days: int) -> StrategySummary:
    n = len(results)
    n_bet = sum(1 for r in results if r.cost > 0)
    n_hit = sum(1 for r in results if r.payout > 0 and r.cost > 0)
    cost_total = sum(r.cost for r in results)
    payout_total = sum(r.payout for r in results)
    pnl = payout_total - cost_total

    roi = (payout_total / cost_total * 100.0) if cost_total > 0 else 0.0
    win_rate = (n_hit / n_bet * 100.0) if n_bet > 0 else 0.0
    race_rois = [x for x in (_race_roi(r) for r in results if r.cost > 0) if x is not None]
    median_race_roi = statistics.median(race_rois) if race_rois else 0.0

    cum_pnl: List[float] = []
    acc = 0.0
    for d in daily_pnl:
        acc += d
        cum_pnl.append(acc)
    if cum_pnl:
        max_dd_amount, max_dd_pct = max_drawdown(cum_pnl)
    else:
        max_dd_amount, max_dd_pct = 0.0, 0.0

    monthly_pnl: Dict[str, float] = defaultdict(float)
    monthly_cost: Dict[str, float] = defaultdict(float)
    for r in results:
        ym = r.date[:6]
        monthly_pnl[ym] += (r.payout - r.cost)
        monthly_cost[ym] += r.cost
    monthly_ret = [(monthly_pnl[k] / monthly_cost[k] * 100.0) if monthly_cost[k] > 0 else 0.0
                   for k in sorted(monthly_pnl.keys())]
    sharpe = sharpe_ratio(monthly_ret, periods_per_year=12) if len(monthly_ret) >= 2 else 0.0

    tier_cost: Dict[str, float] = defaultdict(float)
    tier_payout: Dict[str, float] = defaultdict(float)
    tier_counts: Dict[str, int] = defaultdict(int)
    for r in results:
        tier_counts[r.tier] += 1
        tier_cost[r.tier] += r.cost
        tier_payout[r.tier] += r.payout
    tier_roi = {
        t: ((tier_payout[t] / tier_cost[t] * 100.0) if tier_cost[t] > 0 else 0.0)
        for t in tier_counts
    }

    return StrategySummary(
        strategy=strategy, bankroll_init=bankroll_init,
        bankroll_end=bankroll_init + pnl, n_races=n, n_bet_races=n_bet,
        n_hit_races=n_hit, cost_total=cost_total, payout_total=payout_total,
        pnl=pnl, roi=roi, median_race_roi=median_race_roi, win_rate=win_rate,
        max_dd=abs(max_dd_amount), max_dd_pct=max_dd_pct, sharpe_monthly=sharpe,
        n_bankrupt_days=n_bankrupt_days,
        tier_counts=dict(tier_counts), tier_roi=tier_roi,
    )


# ===========================================================================
# 日次精算ループ
# ===========================================================================

STRATEGIES = ("v2_baseline", "v2_cap3000", "two_tier_v0", "shobu_only_no_ceiling")


def run_period(races: List[dict], haraimodoshi: Dict[str, dict],
               bankroll_init: int) -> Dict[str, Tuple[StrategySummary, List[RaceResult]]]:
    """期間内 races を日次でループ → 戦略別に bankroll を進める。"""
    by_date: Dict[str, List[Tuple[dict, dict]]] = defaultdict(list)
    for r in races:
        rid = str(r.get("race_id") or "")
        race_pay = haraimodoshi.get(rid)
        if not race_pay or not race_pay.get("tansho"):
            continue
        if is_obstacle(r):
            continue
        date = r.get("date") or r.get("_date") or rid[:8]
        by_date[date].append((r, race_pay))

    state: Dict[str, dict] = {s: {"bankroll": float(bankroll_init),
                                  "results": [], "daily_pnl": [], "bankrupt_days": 0}
                              for s in STRATEGIES}

    for date in sorted(by_date.keys()):
        day_races = by_date[date]
        day_state: Dict[str, Tuple[float, float]] = {s: (0.0, 0.0) for s in STRATEGIES}
        for pred_race, race_pay in day_races:
            for strat in STRATEGIES:
                bankroll = max(0, int(state[strat]["bankroll"]))
                if bankroll <= 0:
                    rid = str(pred_race.get("race_id") or "")
                    rr = RaceResult(strategy=strat, rid=rid, date=date,
                                    tier="bankrupt", cost=0.0, payout=0.0)
                else:
                    rr = settle_one_race(pred_race, race_pay,
                                         strategy=strat, bankroll=bankroll)
                if rr is None:
                    continue
                state[strat]["results"].append(rr)
                c, p = day_state[strat]
                day_state[strat] = (c + rr.cost, p + rr.payout)
        for strat in STRATEGIES:
            c, p = day_state[strat]
            day_pnl = p - c
            state[strat]["daily_pnl"].append(day_pnl)
            state[strat]["bankroll"] += day_pnl
            if state[strat]["bankroll"] <= 0:
                state[strat]["bankrupt_days"] += 1

    out: Dict[str, Tuple[StrategySummary, List[RaceResult]]] = {}
    for strat in STRATEGIES:
        summary = _aggregate(strat, bankroll_init,
                             state[strat]["results"], state[strat]["daily_pnl"],
                             state[strat]["bankrupt_days"])
        out[strat] = (summary, state[strat]["results"])
    return out


# ===========================================================================
# same-case 追跡 (★Q4: AI印4頭で組める券面の max_payout★)
# ===========================================================================

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
    """印4頭の組合せで組める券面のうち、 実払戻 (per100) 最大のものを返す。

    payout の key (組合せ) が印4頭の ★部分集合★ なら「印で取れた券面」と判定。
    返値 = (max_per100, bet_type_label)。 1 件も無ければ (0, '')。

    ★Session 164 ④ の是正★: 旧 bench は全 entries の全券種最大 payout を取っていたため、
    1番人気崩壊レースの万馬券 (axis=◎では絶対取れない) を「取れたはずの妙味」と誤計上した。
    印4頭サブセット制約で「AI印で実際に組める券面」だけに絞る。
    """
    mark_set = set(marks)
    best = 0
    best_bt = ""
    for bt, table in race_pay.items():
        if not isinstance(table, dict):
            continue
        for key, per100 in table.items():
            if not per100 or per100 <= best:
                continue
            # key を馬番集合に正規化
            if bt in ("tansho", "fukusho"):
                combo = {int(key)}
            elif bt in ("umaren", "wide", "sanrenpuku"):
                combo = {int(x) for x in key}        # frozenset
            elif bt in ("umatan", "sanrentan"):
                combo = {int(x) for x in key}        # tuple
            else:
                continue
            if combo <= mark_set:                    # 印4頭の部分集合か
                best = int(per100)
                best_bt = bt
    return best, best_bt


def detect_same_case_races(races: List[dict],
                           haraimodoshi: Dict[str, dict]) -> List[dict]:
    """健全期間内で「◎堅い & ceiling予測<400% & ★AI印4頭で組める券面の実払戻>400%★」を抽出。
    = two_tier では見送り判定だが、 AI印で実際に取れた高配当があったケース。
    """
    out: List[dict] = []
    for r in races:
        rid = str(r.get("race_id") or "")
        race_pay = haraimodoshi.get(rid)
        if not race_pay or not race_pay.get("tansho"):
            continue
        if is_obstacle(r):
            continue
        fav = _race_fav_odds(r)
        if fav is None or fav >= SAMECASE_FAV_ODDS_MAX:
            continue
        sel = bs.evaluate_and_select(r, strategy="concentrate",
                                     ev_floor=bs.DEFAULT_EV_FLOOR)
        if sel is None:
            continue
        race_eff = be.process_race(r, axis=sel.axis_umaban)
        if race_eff is None:
            continue
        ceiling_R = tts.compute_ceiling_R(race_eff)
        if not math.isfinite(ceiling_R) or ceiling_R >= SAMECASE_CEILING_MAX_R:
            continue
        marks = _ai_marks(race_eff)
        max_pay, max_bt = _max_payout_within_marks(race_pay, marks)
        if max_pay < SAMECASE_PAYOUT_MIN_R:
            continue
        # ★着順検証★: ◎(axis) が 3着内に来たか (fukusho key = 3着内馬番)。
        #   max_payout 券面が ◎絡みか (◎が組合せに含まれるか) も判定。
        axis = getattr(race_eff, "axis_umaban", None)
        fukusho_horses = set((race_pay.get("fukusho") or {}).keys())
        axis_in_top3 = axis in fukusho_horses if axis is not None else False
        axis_in_maxpay = _is_axis_in_max_payout(race_pay, marks, axis, max_pay, max_bt)
        out.append({
            "race_id": rid,
            "date": r.get("date") or rid[:8],
            "venue_name": r.get("venue_name", ""),
            "race_number": r.get("race_number"),
            "fav_odds": round(fav, 1),
            "ceiling_R": round(ceiling_R, 1),
            "ai_marks": marks,
            "axis_umaban": axis,
            "axis_in_top3": axis_in_top3,        # ◎が3着内に来たか
            "axis_in_max_payout": axis_in_maxpay,  # max_payout 券面が◎絡みか
            "max_payout_per100_in_marks": max_pay,
            "max_payout_bet_type": max_bt,
        })
    return out


def _is_axis_in_max_payout(race_pay: dict, marks: List[int], axis: Optional[int],
                           max_pay: int, max_bt: str) -> bool:
    """max_payout を出した券面 (印部分集合) が ◎(axis) を含むか。

    ◎絡みの券面でないと「axis=◎ では取れない高配当」= 印は当たったが◎は飛んだケース。
    """
    if axis is None or not max_bt:
        return False
    table = race_pay.get(max_bt) or {}
    mark_set = set(marks)
    for key, per100 in table.items():
        if int(per100 or 0) != int(max_pay):
            continue
        if max_bt in ("tansho", "fukusho"):
            combo = {int(key)}
        else:
            combo = {int(x) for x in key}
        if combo <= mark_set and axis in combo:
            return True
    return False


# ===========================================================================
# 出力
# ===========================================================================

def _format_pct(v: float) -> str:
    return f"{v:6.1f}%"


def print_strategy_table(label: str, summaries: Dict[str, StrategySummary]) -> None:
    print(f"\n=== {label} ===")
    print(f"  {'strategy':<24}{'n_races':>9}{'n_bet':>8}{'n_hit':>8}"
          f"{'ROI':>9}{'medR':>9}{'winR':>9}{'maxDD':>11}{'DD%':>8}{'bkrpt':>7}{'Shrp':>7}")
    print(f"  {'-' * 110}")
    for strat, s in summaries.items():
        print(f"  {strat:<24}{s.n_races:>9d}{s.n_bet_races:>8d}{s.n_hit_races:>8d}"
              f"{_format_pct(s.roi):>9}{_format_pct(s.median_race_roi):>9}"
              f"{_format_pct(s.win_rate):>9}"
              f"{s.max_dd:>11.0f}{s.max_dd_pct:>7.1f}%{s.n_bankrupt_days:>7d}"
              f"{s.sharpe_monthly:>7.2f}")
    print(f"  {'-' * 110}")
    print(f"  ★judge★: two_tier_v0.ROI > v2_baseline.ROI なら 二層化+ceiling400% が優位")
    print(f"           two_tier_v0.ROI > shobu_only_no_ceiling.ROI なら ceiling400% ゲートが効く")
    print(f"           two_tier_v0.maxDD < v2_baseline.maxDD なら見送りで DD を抑えられている")


def print_tier_breakdown(summaries: Dict[str, StrategySummary]) -> None:
    print(f"\n  -- tier 別件数 (件数/ROI%) --")
    all_tiers = set()
    for s in summaries.values():
        all_tiers.update(s.tier_counts.keys())
    tier_order = ["shobu", "miokuri", "v2_normal", "v2_low_ceiling", "bankrupt"]
    ordered = [t for t in tier_order if t in all_tiers] + \
              sorted(all_tiers - set(tier_order))
    head = "  " + f"{'strategy':<24}" + "".join(f"{t:>18}" for t in ordered)
    print(head)
    for strat, s in summaries.items():
        row = "  " + f"{strat:<24}"
        for t in ordered:
            n = s.tier_counts.get(t, 0)
            rr = s.tier_roi.get(t, 0.0)
            row += f"{n:>5d}/{rr:>10.1f}%"
        print(row)


# ===========================================================================
# main
# ===========================================================================

def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--p1-start", default=DEFAULT_P1_START)
    p.add_argument("--p1-end", default=DEFAULT_P1_END)
    p.add_argument("--p2-start", default=DEFAULT_P2_START)
    p.add_argument("--p2-end", default=DEFAULT_P2_END)
    p.add_argument("--bankrolls", default=DEFAULT_BANKROLLS,
                   help="初期残高 sweep (カンマ区切り。 既定=1000000)")
    p.add_argument("--output", default=DEFAULT_OUTPUT)
    p.add_argument("--skip-p2", action="store_true")
    p.add_argument("--skip-samecase", action="store_true")
    return p.parse_args()


def run_one_period(label: str, start: str, end: str, bankrolls: List[int],
                   skip_samecase: bool) -> dict:
    print(f"\n{'=' * 100}")
    print(f"  期間: {label} ({start} 〜 {end})")
    print(f"{'=' * 100}")
    races = load_predictions_races(start_date=start, end_date=end)
    print(f"  predictions.json: {len(races)} races")
    codes = [str(r.get("race_id") or "") for r in races if r.get("race_id")]
    print("  loading haraimodoshi (実払戻)...")
    haraimodoshi = load_haraimodoshi(codes)
    print(f"  haraimodoshi loaded: {len(haraimodoshi)}")

    by_bankroll: Dict[int, Dict[str, StrategySummary]] = {}
    runs_by_bankroll: Dict[int, Dict[str, Tuple[StrategySummary, List[RaceResult]]]] = {}
    for br in bankrolls:
        print(f"\n  --- 初期残高 {br:,}円 で日次精算 ---")
        runs = run_period(races, haraimodoshi, bankroll_init=br)
        runs_by_bankroll[br] = runs
        summaries = {strat: pkg[0] for strat, pkg in runs.items()}
        by_bankroll[br] = summaries
        print_strategy_table(f"{label} / 初期残高 {br:,}円", summaries)
        print_tier_breakdown(summaries)

    same_case: List[dict] = []
    same_case_tracking: Dict[str, dict] = {}
    if not skip_samecase:
        print(f"\n  -- same-case 検出 (◎堅い & ceiling<400% & AI印4頭券面 実払戻>400%) --")
        same_case = detect_same_case_races(races, haraimodoshi)
        print(f"  same-case: {len(same_case)} 件")
        for sc in same_case[:12]:
            mk = "◎来" if sc.get("axis_in_top3") else "◎飛"
            mp = "◎絡" if sc.get("axis_in_max_payout") else "◎無"
            print(f"    {sc['date']} {sc['venue_name']} R{sc['race_number']} "
                  f"fav={sc['fav_odds']:.1f} ceiling={sc['ceiling_R']:.0f}% "
                  f"印={sc['ai_marks']} [{mk}/{mp}] "
                  f"max_payout={sc['max_payout_per100_in_marks']}円"
                  f"({sc['max_payout_bet_type']})")
        if len(same_case) > 12:
            print(f"    ... 他 {len(same_case) - 12} 件")
        # ★着順検証★ (Q4: ceiling ゲートの害を測る)
        n_axis_top3 = sum(1 for sc in same_case if sc.get("axis_in_top3"))
        n_axis_maxpay = sum(1 for sc in same_case if sc.get("axis_in_max_payout"))
        print(f"  ★着順検証★: {len(same_case)} 件中 ◎が3着内={n_axis_top3} 件 "
              f"/ max_payout券面が◎絡み={n_axis_maxpay} 件")
        print(f"    → ◎絡み={n_axis_maxpay}件 = axis=◎ で実際に取れたはずの妙味 "
              f"(これが多いほど ceiling<400% 見送りは害)")
        print(f"    → ◎無={len(same_case) - n_axis_maxpay}件 = ◎が飛んだ高配当 "
              f"(axis=◎ では元々取れない = 見送りは正当)")
        sc_ids = {sc["race_id"] for sc in same_case}
        for br in bankrolls:
            ttv = runs_by_bankroll[br]["two_tier_v0"][1]
            tt_total = sum(1 for r in ttv if r.rid in sc_ids)
            tt_bet = sum(1 for r in ttv if r.rid in sc_ids and r.cost > 0)
            print(f"  two_tier_v0 / 残高{br:,}円: same-case {tt_total} 件中 "
                  f"買い目あり {tt_bet} 件 (見送ったのは {tt_total - tt_bet} 件)")
            same_case_tracking[str(br)] = {
                "n_same_case": tt_total, "n_bet": tt_bet,
                "n_missed_by_miokuri": tt_total - tt_bet,
            }

    return {
        "label": label,
        "start": start,
        "end": end,
        "n_races_loaded": len(races),
        "n_haraimodoshi": len(haraimodoshi),
        "by_bankroll": {
            str(br): {strat: s.as_dict() for strat, s in summ.items()}
            for br, summ in by_bankroll.items()
        },
        "same_case_races": same_case,
        "same_case_tracking_two_tier_v0": same_case_tracking,
    }


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                          errors="replace")
        except (AttributeError, ValueError):
            pass
    args = parse_args()
    bankrolls = [int(x.strip()) for x in args.bankrolls.split(",") if x.strip()]

    out_payload: dict = {
        "tool": "bench_two_tier_v0",
        "design_doc": "docs/auto_purchase_sizing_design.md (Session 165 = three_tier 再走)",
        "strategies": list(STRATEGIES),
        "fixes_from_s164": {
            "Q1_ceiling_floor_R": tt.CEILING_FLOOR_DEFAULT_R,
            "Q2_bankroll_default": bankrolls,
            "Q3_two_tier": "様子見廃止 (勝負/見送りのみ)",
            "Q4_samecase": "AI印4頭(◎○▲△=axis+partners[:3])で組める券面の max_payout",
        },
        "params": {
            "tier_share_shobu": tt.TIER_SHARE_SHOBU,
            "ceiling_floor_R": tt.CEILING_FLOOR_DEFAULT_R,
            "v2_cap3000": DEFAULT_V2_CAP3000,
            "samecase_fav_odds_max": SAMECASE_FAV_ODDS_MAX,
            "samecase_ceiling_max_R": SAMECASE_CEILING_MAX_R,
            "samecase_payout_min_R": SAMECASE_PAYOUT_MIN_R,
        },
        "ceiling_source_warning": ("ceiling_R は確定 combo オッズ (時系列なし) 由来。 "
                                   "ライブ再現不可。 本番投入前に◎単勝ベース等への置換が宿題 "
                                   "[[feedback_odds_gate_hindsight]]"),
        "bankrolls_initial": bankrolls,
        "periods": [],
    }

    p1 = run_one_period("P1 (健全直近)", args.p1_start, args.p1_end,
                        bankrolls, skip_samecase=args.skip_samecase)
    out_payload["periods"].append(p1)

    if not args.skip_p2:
        p2 = run_one_period("P2 (健全旧期間)", args.p2_start, args.p2_end,
                            bankrolls, skip_samecase=args.skip_samecase)
        out_payload["periods"].append(p2)

    out_path = config.ml_dir() / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out_payload, f, ensure_ascii=False, indent=2)
    print(f"\n結果出力: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
