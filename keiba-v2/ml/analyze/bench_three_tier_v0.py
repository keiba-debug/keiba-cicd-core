#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""three_tier_v0 検証ハーネス (Session 164 / 設計案B 実装フェーズ)

★目的★:
  three_tier_v0 (勝負15% / 様子見3% / 見送り ceiling<1000% + 様子見券種ゲート) を
  predictions 実払戻 (健全期間) でバックテストし、 fixed_grade_v2 (本番) と並列比較。
  特に「見送り対象を買った場合 ROI > 買う群 ROI」なら ceiling_floor_R=1000% は害
  ([[feedback_odds_gate_hindsight]] 規律 = 検証宿題)。

★4戦略を並列精算★:
  - ★v2_baseline★: fixed_grade_v2 + per_race_cap = 3000円固定 (Session 163 本番)。
  - ★v2_dynamic★: fixed_grade_v2 + per_race_cap = bankroll * 0.08 (残高連動・対照群)。
  - ★three_tier_v0★: 3分類 + 案B 新案。 勝負15% / 様子見3% (券種ゲート) / 見送り (ceiling<1000%)。
  - ★three_tier_skip_only★: 全レート bankroll*15% 一律 + 見送り (ceiling<1000%) のみ
      = ゲートの純寄与を測る対照群 (シェア配分は v2 と同じ FIXED_SHARES_V2)。

★期間 (stale 期間 [[ml-cache-staleness-incident]] 2026-03-21〜2026-06-07 を避ける)★:
  P1: 2026-01-04 〜 2026-03-15  (健全 / 直近本番想定)
  P2: 2025-09-01 〜 2025-12-31  (健全 / 旧期間)

★精算★: mykeibadb.haraimodoshi 実払戻 (W9 / [[feedback_combo_backtest_settlement]] 教訓)。
  combo の cache payout 近似は使わない。

★日次精算★: 当日 cost/payout を集計 → 翌日残高 = 前日残高 + (payout - cost)。
  bankroll が動的サイザー (v2_dynamic / three_tier_v0) に効く。 マイナスになっても続行
  (現実の DD を測るため・bankroll<=0 は MIN_BET_YEN ガードで自動的に何も買わなくなる)。

★出力★:
  - stdout テーブル (戦略 × ROI/maxDD/medianROI/Sharpe/winR/分類別件数)
  - JSON: data3/ml/bench_three_tier_v0_results.json (戦略別月次明細・分類別内訳)
  - 6/14 東京6R 相当の追跡 (健全期間内で「1番人気<2.5倍 & ceiling予測<1000% & 実払戻合計>1000%」)

CLI:
    python -m ml.analyze.bench_three_tier_v0
    python -m ml.analyze.bench_three_tier_v0 --bankrolls 10000,30000,100000
    python -m ml.analyze.bench_three_tier_v0 --p1-start 2026-01-04 --p1-end 2026-03-15
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
from typing import Callable, Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import config  # noqa: E402
from ml.analyze.backtest_bet_templates import load_haraimodoshi  # noqa: E402
from ml.export_formation_backtest import load_predictions_races  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.strategies import bettype_selection as bs  # noqa: E402
from ml.strategies import bettype_sizing as sz  # noqa: E402
from ml.strategies import three_tier_sizing as tts  # noqa: E402
from ml.utils.filters import is_obstacle  # noqa: E402
from ml.utils.roi import Bet, calc_roi, max_drawdown, sharpe_ratio  # noqa: E402


# ===========================================================================
# 既定 (CLI 引数 default)
# ===========================================================================

DEFAULT_P1_START = "2026-01-04"
DEFAULT_P1_END = "2026-03-15"
DEFAULT_P2_START = "2025-09-01"
DEFAULT_P2_END = "2025-12-31"
DEFAULT_BANKROLLS = "30000"        # 初期残高 (カンマ区切り sweep 可)
DEFAULT_V2_BASELINE_CAP = 3000      # v2_baseline の固定 cap (Session 163 本番)
DEFAULT_V2_DYNAMIC_RATIO = 0.08     # v2_dynamic の cap = bankroll * 0.08
DEFAULT_OUTPUT = "bench_three_tier_v0_results.json"

# 6/14 東京6R 相当の検出条件 (健全期間内で同型を見つけて three_tier の hit を追跡)。
SAMECASE_FAV_ODDS_MAX = 2.5        # 1番人気が 2.5 倍未満 (= 堅い◎)
SAMECASE_CEILING_MAX_R = 1000.0    # ceiling 予測が 1000% 未満 (= three_tier で見送り対象)
SAMECASE_PAYOUT_MIN_R = 1000.0     # 実払戻合計が 1000% 超 (= 結果は当たって配当跳ねた)


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
    tier: str              # 'shobu' / 'kanshi' / 'miokuri' / 'v2' (v2 系は 'v2')
    cost: float
    payout: float
    bets: List[Bet] = field(default_factory=list)
    ceiling_R: Optional[float] = None   # 6/14 同型検出用
    fav_odds: Optional[float] = None    # 同上


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


def _size_v2_baseline(race_eff, sel, *, bankroll: int) -> sz.RaceSizing:
    """fixed_grade_v2 + cap=3000円固定 (Session 163 本番)。"""
    return sz.size_race_fixed_grade_v2(
        race_eff, sel, bankroll=bankroll, per_race_cap=DEFAULT_V2_BASELINE_CAP)


def _size_v2_dynamic(race_eff, sel, *, bankroll: int) -> sz.RaceSizing:
    """fixed_grade_v2 + cap = bankroll * 0.08 (残高連動)。"""
    cap = max(0, int(bankroll * DEFAULT_V2_DYNAMIC_RATIO))
    return sz.size_race_fixed_grade_v2(
        race_eff, sel, bankroll=bankroll, per_race_cap=cap)


def _size_three_tier_v0(race_eff, sel, *, bankroll: int, pred_race: dict) -> sz.RaceSizing:
    """three_tier_v0 (3分類 + 案B 新案)。"""
    return tts.size_race_three_tier(
        race_eff, sel, bankroll=bankroll, pred_race=pred_race)


def _size_three_tier_skip_only(race_eff, sel, *, bankroll: int) -> sz.RaceSizing:
    """全レート bankroll*15% 一律 + 見送り (ceiling<1000%) のみ。 配分は v2 と同じ。

    シェアは fixed_grade_v2 (FIXED_SHARES_V2) のまま。 cap だけ tier_share_shobu=0.15。
    見送りゲートだけは three_tier の ceiling_R<1000% を使う (ゲートの純寄与を測る対照群)。
    """
    cap = max(0, int(bankroll * tts.TIER_SHARE_SHOBU))
    if cap <= 0:
        return sz.RaceSizing(race_id=race_eff.race_id, legs=[], total_yen=0,
                             anchor_yen=0, combo_yen=0, per_race_cap=0,
                             warnings=["skip_only: cap<=0"])
    ceiling_R = tts.compute_ceiling_R(race_eff)
    if ceiling_R < tts.CEILING_FLOOR_DEFAULT_R:
        return sz.RaceSizing(race_id=race_eff.race_id, legs=[], total_yen=0,
                             anchor_yen=0, combo_yen=0, per_race_cap=0,
                             warnings=[f"skip_only miokuri: ceiling_R={ceiling_R:.0f}%"])
    # ceiling 通過 → fixed_grade_v2 で買う (cap=bankroll*15%)。
    return sz.size_race_fixed_grade_v2(
        race_eff, sel, bankroll=bankroll, per_race_cap=cap)


# ---------------------------------------------------------------------------
# 戦略ラッパー (1 レース → RaceResult)
# ---------------------------------------------------------------------------

def _classify_for_v2(race_eff, sel, pred_race: dict) -> str:
    """v2 系の便宜 tier ラベル (集計分離用)。 ceiling<1000%=miokuri 相当・他は買う。
    v2 自身は降りないが、 統計の比較対象として「降りた群」を識別したいときに使う。"""
    ceiling_R = tts.compute_ceiling_R(race_eff)
    if ceiling_R < tts.CEILING_FLOOR_DEFAULT_R:
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
        rs = _size_v2_baseline(race_eff, sel, bankroll=bankroll)
        tier = _classify_for_v2(race_eff, sel, pred_race)
    elif strategy == "v2_dynamic":
        rs = _size_v2_dynamic(race_eff, sel, bankroll=bankroll)
        tier = _classify_for_v2(race_eff, sel, pred_race)
    elif strategy == "three_tier_v0":
        rs = _size_three_tier_v0(race_eff, sel, bankroll=bankroll, pred_race=pred_race)
        # tier 名は warnings 先頭から抽出 (three_tier=... が必ず付く)
        tier = "kanshi"
        if rs.warnings:
            head = rs.warnings[0]
            if "three_tier=shobu" in head:
                tier = "shobu"
            elif "three_tier=miokuri" in head:
                tier = "miokuri"
            elif "three_tier=kanshi" in head:
                tier = "kanshi"
        # 空 RaceSizing でも tier=miokuri が立つ
    elif strategy == "three_tier_skip_only":
        rs = _size_three_tier_skip_only(race_eff, sel, bankroll=bankroll)
        tier = "miokuri" if not rs.legs else "v2_normal"
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
    n_bet_races: int      # 実際に買い目が出たレース (cost>0)
    n_hit_races: int      # 1点でも当たったレース
    cost_total: float
    payout_total: float
    pnl: float
    roi: float            # %
    median_race_roi: float    # レース別 ROI 中央値 (cost>0 のみ)
    win_rate: float       # bet_races のうち payout>0 の割合 (%)
    max_dd: float         # 累積 P&L の maxDD (絶対値)
    max_dd_pct: float     # peak からの %
    sharpe_monthly: float
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
            "tier_counts": dict(self.tier_counts),
            "tier_roi": {k: round(v, 2) for k, v in self.tier_roi.items()},
        }


def _race_roi(r: RaceResult) -> Optional[float]:
    if r.cost <= 0:
        return None
    return (r.payout / r.cost) * 100.0


def _aggregate(strategy: str, bankroll_init: int,
                results: List[RaceResult], daily_pnl: List[float]) -> StrategySummary:
    n = len(results)
    n_bet = sum(1 for r in results if r.cost > 0)
    n_hit = sum(1 for r in results if r.payout > 0 and r.cost > 0)
    cost_total = sum(r.cost for r in results)
    payout_total = sum(r.payout for r in results)
    pnl = payout_total - cost_total

    roi = (payout_total / cost_total * 100.0) if cost_total > 0 else 0.0
    win_rate = (n_hit / n_bet * 100.0) if n_bet > 0 else 0.0
    race_rois = [_race_roi(r) for r in results if r.cost > 0]
    race_rois = [x for x in race_rois if x is not None]
    median_race_roi = statistics.median(race_rois) if race_rois else 0.0

    # MaxDD は日次累積 P&L 系列で測る (レース別だと隣接相関で過小評価)
    cum_pnl: List[float] = []
    acc = 0.0
    for d in daily_pnl:
        acc += d
        cum_pnl.append(acc)
    if cum_pnl:
        max_dd_amount, max_dd_pct = max_drawdown(cum_pnl)
    else:
        max_dd_amount, max_dd_pct = 0.0, 0.0

    # 月次 Sharpe (date YYYYMMDD → YYYYMM 単位の P&L / cost)
    monthly_pnl: Dict[str, float] = defaultdict(float)
    monthly_cost: Dict[str, float] = defaultdict(float)
    for r in results:
        ym = r.date[:6]
        monthly_pnl[ym] += (r.payout - r.cost)
        monthly_cost[ym] += r.cost
    monthly_ret = [(monthly_pnl[k] / monthly_cost[k] * 100.0) if monthly_cost[k] > 0 else 0.0
                   for k in sorted(monthly_pnl.keys())]
    sharpe = sharpe_ratio(monthly_ret, periods_per_year=12) if len(monthly_ret) >= 2 else 0.0

    # tier 別集計
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
        tier_counts=dict(tier_counts), tier_roi=tier_roi,
    )


# ===========================================================================
# 日次精算ループ
# ===========================================================================

STRATEGIES = ("v2_baseline", "v2_dynamic", "three_tier_v0", "three_tier_skip_only")


def run_period(races: List[dict], haraimodoshi: Dict[str, dict],
                bankroll_init: int) -> Dict[str, Tuple[StrategySummary, List[RaceResult]]]:
    """期間内 races を日次でループ → 戦略別に bankroll を進める。

    日次精算: その日の cost/payout 合計 → 翌日 bankroll に反映。
    bankroll は戦略ごとに独立 (v2_baseline は変動しても cap 固定なので結果不変)。
    """
    # date → [pred_race, race_pay] のグルーピング
    by_date: Dict[str, List[Tuple[dict, dict]]] = defaultdict(list)
    for r in races:
        rid = str(r.get("race_id") or "")
        race_pay = haraimodoshi.get(rid)
        if not race_pay or not race_pay.get("tansho"):
            continue  # 結果未確定 / 中止
        if is_obstacle(r):
            continue
        date = r.get("date") or r.get("_date") or rid[:8]
        by_date[date].append((r, race_pay))

    # 戦略別の状態
    state: Dict[str, dict] = {s: {"bankroll": float(bankroll_init),
                                  "results": [], "daily_pnl": []}
                              for s in STRATEGIES}

    for date in sorted(by_date.keys()):
        day_races = by_date[date]
        day_state: Dict[str, Tuple[float, float]] = {s: (0.0, 0.0) for s in STRATEGIES}
        for pred_race, race_pay in day_races:
            for strat in STRATEGIES:
                bankroll = max(0, int(state[strat]["bankroll"]))
                if bankroll <= 0:
                    # 残高ゼロ → 何も買えないが結果として race を残す (n_races 用)
                    rs = sz.RaceSizing(race_id=str(pred_race.get("race_id") or ""),
                                        legs=[], total_yen=0, anchor_yen=0,
                                        combo_yen=0, per_race_cap=0,
                                        warnings=["bankroll<=0"])
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
        # 日次終了 → 翌日に反映
        for strat in STRATEGIES:
            c, p = day_state[strat]
            day_pnl = p - c
            state[strat]["daily_pnl"].append(day_pnl)
            state[strat]["bankroll"] += day_pnl

    out: Dict[str, Tuple[StrategySummary, List[RaceResult]]] = {}
    for strat in STRATEGIES:
        summary = _aggregate(strat, bankroll_init,
                              state[strat]["results"], state[strat]["daily_pnl"])
        out[strat] = (summary, state[strat]["results"])
    return out


# ===========================================================================
# 6/14 東京6R 同型レース追跡
# ===========================================================================

def detect_same_case_races(races: List[dict], haraimodoshi: Dict[str, dict]) -> List[dict]:
    """健全期間内で 6/14 東京6R 相当 = 1番人気<2.5倍 & ceiling予測<1000% &
    実払戻合計>1000% のレースを抽出。 「three_tier では見送り判定だが実際は大配当」のケース。
    実払戻合計 = haraimodoshi 全7券種の中で 100円あたり最大 payout を採用。
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
        # 実払戻 (per100 = 回収率) の最大を取る
        max_payout = 0
        for bt_, table in race_pay.items():
            if not isinstance(table, dict):
                continue
            for v in table.values():
                if v and v > max_payout:
                    max_payout = v
        if max_payout < SAMECASE_PAYOUT_MIN_R:
            continue
        out.append({
            "race_id": rid,
            "date": r.get("date") or rid[:8],
            "venue_name": r.get("venue_name", ""),
            "race_number": r.get("race_number"),
            "fav_odds": fav,
            "ceiling_R": round(ceiling_R, 1),
            "max_payout_per100": int(max_payout),
        })
    return out


# ===========================================================================
# 出力
# ===========================================================================

def _format_pct(v: float) -> str:
    return f"{v:6.1f}%"


def print_strategy_table(label: str, summaries: Dict[str, StrategySummary]) -> None:
    print(f"\n=== {label} ===")
    print(f"  {'strategy':<24}{'n_races':>9}{'n_bet':>8}{'n_hit':>8}"
          f"{'ROI':>9}{'medR':>9}{'winR':>9}{'maxDD':>10}{'DD%':>8}{'Sharpe':>9}")
    print(f"  {'-' * 105}")
    for strat, s in summaries.items():
        print(f"  {strat:<24}{s.n_races:>9d}{s.n_bet_races:>8d}{s.n_hit_races:>8d}"
              f"{_format_pct(s.roi):>9}{_format_pct(s.median_race_roi):>9}"
              f"{_format_pct(s.win_rate):>9}"
              f"{s.max_dd:>10.0f}{s.max_dd_pct:>7.1f}%{s.sharpe_monthly:>9.2f}")
    print(f"  {'-' * 105}")
    print(f"  ★judge★: three_tier_v0.ROI > v2_baseline.ROI なら新案が優位")
    print(f"           skip_only.ROI < v2_baseline.ROI なら ceiling_floor_R=1000% は害 "
          f"([[feedback_odds_gate_hindsight]])")


def print_tier_breakdown(summaries: Dict[str, StrategySummary]) -> None:
    print(f"\n  -- tier 別件数 (件数/ROI%) --")
    all_tiers = set()
    for s in summaries.values():
        all_tiers.update(s.tier_counts.keys())
    tier_order = ["shobu", "kanshi", "miokuri", "v2_normal", "v2_low_ceiling", "bankrupt"]
    ordered = [t for t in tier_order if t in all_tiers] + \
              sorted(all_tiers - set(tier_order))
    head = "  " + f"{'strategy':<24}" + "".join(f"{t:>18}" for t in ordered)
    print(head)
    for strat, s in summaries.items():
        row = "  " + f"{strat:<24}"
        for t in ordered:
            n = s.tier_counts.get(t, 0)
            r = s.tier_roi.get(t, 0.0)
            row += f"{n:>5d}/{r:>10.1f}%"
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
                   help="初期残高 sweep (カンマ区切り。 既定=30000)")
    p.add_argument("--output", default=DEFAULT_OUTPUT,
                   help="JSON 出力ファイル名 (data3/ml/ 下)")
    p.add_argument("--skip-p2", action="store_true", help="P2 (2025-09〜12) をスキップ")
    p.add_argument("--skip-samecase", action="store_true",
                   help="6/14 同型レース検出をスキップ (高速化)")
    return p.parse_args()


def run_one_period(label: str, start: str, end: str, bankrolls: List[int],
                   skip_samecase: bool) -> dict:
    """1 期間を読み込み → 戦略 × 残高 で run_period → 出力辞書を返す。"""
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
        print(f"\n  -- 6/14 東京6R 同型レース検出 --")
        same_case = detect_same_case_races(races, haraimodoshi)
        print(f"  同型レース (◎堅い & ceiling<1000% & 実払戻>1000%): {len(same_case)} 件")
        for sc in same_case[:10]:
            print(f"    {sc['date']} {sc['venue_name']} R{sc['race_number']} "
                  f"fav={sc['fav_odds']:.1f} ceiling={sc['ceiling_R']:.0f}% "
                  f"max_payout={sc['max_payout_per100']}円")
        if len(same_case) > 10:
            print(f"    ... 他 {len(same_case) - 10} 件")
        # three_tier_v0 が実際に取れたか (既に走らせた runs を再利用)
        sc_ids = {sc["race_id"] for sc in same_case}
        for br in bankrolls:
            ttv = runs_by_bankroll[br]["three_tier_v0"][1]
            tt_total = sum(1 for r in ttv if r.rid in sc_ids)
            tt_bet = sum(1 for r in ttv if r.rid in sc_ids and r.cost > 0)
            tt_hit = sum(1 for r in ttv if r.rid in sc_ids
                         and r.payout > 0 and r.cost > 0)
            print(f"  three_tier_v0 / 残高{br:,}円: 同型 {tt_total} 件中 "
                  f"買い目あり {tt_bet} 件 / 的中 {tt_hit} 件 (見送ったのは {tt_total-tt_bet} 件)")
            same_case_tracking[str(br)] = {
                "n_same_case": tt_total, "n_bet": tt_bet, "n_hit": tt_hit,
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
        "same_case_tracking_three_tier_v0": same_case_tracking,
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
        "tool": "bench_three_tier_v0",
        "design_doc": "docs/auto_purchase_sizing_design.md (Session 164 案B)",
        "strategies": list(STRATEGIES),
        "params": {
            "v2_baseline_cap_yen": DEFAULT_V2_BASELINE_CAP,
            "v2_dynamic_ratio": DEFAULT_V2_DYNAMIC_RATIO,
            "tier_share_shobu": tts.TIER_SHARE_SHOBU,
            "tier_share_kanshi": tts.TIER_SHARE_KANSHI,
            "ceiling_floor_R": tts.CEILING_FLOOR_DEFAULT_R,
            "margin_max_default": tts.MARGIN_MAX_DEFAULT,
            "kanshi_w_min": tts.KANSHI_W_MIN_DEFAULT,
            "kanshi_p_min_small": tts.KANSHI_P_MIN_SMALL_DEFAULT,
            "kanshi_p_min_large": tts.KANSHI_P_MIN_LARGE_DEFAULT,
            "kanshi_shares": tts.KANSHI_SHARES_DEFAULT,
        },
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
