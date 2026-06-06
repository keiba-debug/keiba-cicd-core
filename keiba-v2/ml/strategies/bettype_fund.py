#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""配分・券種出し分け (P2b / RELEASE_0606_0607 Phase2b)

bettype_efficiency (Phase2) の plans[] を fund 判断に配線する純関数層。
レース特性から「単のみ / 増額 / 大穴100円流し / 降りる」を決める。

制約 (シズネ / feedback_betting_philosophy):
  - fund 判断は EV 絶対水準 + bankroll (Kelly)。 vs_tansho は使わない。
  - 固定プリセット・連勝増額等の動的調整はしない (レース単位の efficiency から決める)。
  - find_taste_axis は触らない (本モジュールは軸確定後の出し分けのみ)。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ml.strategies.kelly import MIN_BET_YEN, kelly_amount

BASE_BET_TYPES = ("tansho", "fukusho")
COMBO_BET_TYPES = ("umaren", "wide", "umatan", "sanrenpuku", "sanrentan")
LONGSHOT_PREFERRED = ("umaren", "wide")

# 複勝薄利 floor (bet-adjustment-items 項目1)
DEFAULT_FUKUSHO_MIN_ODDS = 1.8
DEFAULT_FUKUSHO_MIN_PROFIT_YEN = 20   # 100円あたりの期待利益 (円)

# 出し分け閾値 (backtest で調整可能・固定モードではない)
COMPOSITE_GAP_BOOST = 0.30
COMPOSITE_GAP_DOMINANT = 0.40
COMPOSITE_GAP_FLAT = 0.12
AXIS_EV_BOOST = 1.05
COMBO_WEAK_EV = 1.05
LONGSHOT_AXIS_ODDS = 8.0
LONGSHOT_FLOW_YEN = MIN_BET_YEN
KELLY_BOOST_MAX = 1.75


def _legs_key(legs) -> tuple:
    return tuple(tuple(int(h) for h in leg) for leg in legs)


def _plan_by_type(plans, bet_type: str):
    return next((p for p in plans if p.bet_type == bet_type), None)


def axis_tansho_ev(race_eff) -> Optional[float]:
    """軸◎単勝の implied EV (= win_prob × 単オッズ)。控除率前の粗 EV。"""
    axis = race_eff.axis_umaban
    strength = next((s for s in race_eff.strengths if s.umaban == axis), None)
    if strength is None:
        return None
    if strength.odds and strength.odds > 0 and strength.win_prob > 0:
        return strength.win_prob * strength.odds
    tp = _plan_by_type(race_eff.plans, "tansho")
    if tp and tp.hit_prob and race_eff.axis_odds and race_eff.axis_odds > 0:
        return tp.hit_prob * race_eff.axis_odds
    return None


def composite_gap(race_eff) -> float:
    """composite 1位 (軸) と 2位の差。 strengths は composite 降順。"""
    if len(race_eff.strengths) < 2:
        return 0.0
    top = race_eff.strengths[0].composite
    second = race_eff.strengths[1].composite
    return max(0.0, top - second)


def passes_fukusho_floor(
    plan,
    *,
    min_odds: float = DEFAULT_FUKUSHO_MIN_ODDS,
    min_expected_profit_yen: float = DEFAULT_FUKUSHO_MIN_PROFIT_YEN,
    unit: int = MIN_BET_YEN,
) -> bool:
    """低オッズ複勝 or 最低期待利益未満は除外 (bet-adjustment-items 項目1)。"""
    if plan is None or plan.bet_type != "fukusho":
        return True
    odds = plan.odds_legs[0] if plan.odds_legs else None
    if odds is None or odds < min_odds:
        return False
    if plan.expected_return is not None:
        return unit * (plan.expected_return - 1.0) >= min_expected_profit_yen
    if plan.hit_prob and odds:
        return unit * (plan.hit_prob * odds - 1.0) >= min_expected_profit_yen
    return False


def fundable_combos(plans, *, ev_floor: float) -> List:
    """EV>=floor の複合券種 (vs_tansho 不使用)。"""
    out = []
    for p in plans:
        if p.bet_type in BASE_BET_TYPES:
            continue
        if p.expected_return is None:
            continue
        if p.expected_return >= ev_floor:
            out.append(p)
    return out


def best_combo(combos: List):
    if not combos:
        return None
    return max(combos, key=lambda p: (p.expected_return or 0.0, len(p.legs)))


def pick_longshot_leg(plan, *, yen: int = LONGSHOT_FLOW_YEN) -> Optional[Tuple[List[int], Optional[float], int]]:
    """大穴100円流し: 複合 plan 内で最高オッズ leg 1点のみ (ローリスク枠)。"""
    if plan is None or not plan.legs:
        return None
    best_i = 0
    best_odds = -1.0
    for i, leg in enumerate(plan.legs):
        o = plan.odds_legs[i] if i < len(plan.odds_legs) else None
        if o is not None and o > best_odds:
            best_odds = o
            best_i = i
    leg = list(plan.legs[best_i])
    odds = plan.odds_legs[best_i] if best_i < len(plan.odds_legs) else None
    return leg, odds, yen


@dataclass
class FundDecision:
    """1レースの fund 出し分け (dry-run / sizing 共有)。"""
    mode: str                     # skip_all | tansho_only | boost | longshot_flow | spread
    reason: str
    kelly_boost: float = 1.0
    tansho_only: bool = False
    longshot_yen: int = 0
    longshot_bet_type: Optional[str] = None
    longshot_horses: Optional[List[int]] = None
    longshot_odds: Optional[float] = None
    longshot_label: str = ""
    axis_ev: Optional[float] = None
    composite_gap: float = 0.0
    n_fundable_combos: int = 0


def decide_fund(
    race_eff,
    *,
    ev_floor: float = 1.0,
    bankroll: int = 10000,
    kelly_fraction: float = 0.25,
    per_bet_cap_pct: float = 0.10,
    fukusho_min_odds: float = DEFAULT_FUKUSHO_MIN_ODDS,
    fukusho_min_profit_yen: float = DEFAULT_FUKUSHO_MIN_PROFIT_YEN,
) -> FundDecision:
    """RaceEfficiency から fund モードを決定 (vs_tansho 不使用)。"""
    gap = composite_gap(race_eff)
    ax_ev = axis_tansho_ev(race_eff)
    fukusho = _plan_by_type(race_eff.plans, "fukusho")
    fuk_ok = passes_fukusho_floor(
        fukusho, min_odds=fukusho_min_odds, min_expected_profit_yen=fukusho_min_profit_yen)
    combos = fundable_combos(race_eff.plans, ev_floor=ev_floor)
    n_combo = len(combos)
    best = best_combo(combos)

    axis_strength = next((s for s in race_eff.strengths if s.umaban == race_eff.axis_umaban), None)
    axis_pred_w = axis_strength.pred_w if axis_strength else None
    tansho_amt = kelly_amount(
        axis_pred_w, race_eff.axis_odds, bankroll=bankroll,
        kelly_fraction=kelly_fraction, per_bet_cap_pct=per_bet_cap_pct)
    fuk_amt = 0
    if fuk_ok and fukusho is not None:
        f_odds = fukusho.odds_legs[0] if fukusho.odds_legs else None
        fuk_amt = kelly_amount(
            fukusho.hit_prob, f_odds, bankroll=bankroll,
            kelly_fraction=kelly_fraction, per_bet_cap_pct=per_bet_cap_pct)

    base_kw = dict(axis_ev=ax_ev, composite_gap=gap, n_fundable_combos=n_combo)

    # 降りる: アンカー Kelly 0 & 複合 fund 0 & 複勝 floor 外
    if tansho_amt < MIN_BET_YEN and fuk_amt < MIN_BET_YEN and n_combo == 0:
        if gap <= COMPOSITE_GAP_FLAT and (ax_ev is None or ax_ev < 1.0):
            return FundDecision(
                mode="skip_all",
                reason="評価割れ (composite 平坦) + アンカー-EV + 複合 fund 0 → 降りる",
                **base_kw,
            )
        return FundDecision(
            mode="skip_all",
            reason="アンカー Kelly 0 + 複合 fund 0 + 複勝 floor 外 → 降りる",
            **base_kw,
        )

    kelly_boost = 1.0
    if ax_ev is not None and ax_ev >= AXIS_EV_BOOST and gap >= COMPOSITE_GAP_BOOST:
        kelly_boost = min(KELLY_BOOST_MAX, 1.0 + gap * 0.5)

    tansho_only = False
    if n_combo == 0:
        tansho_only = True
    elif gap >= COMPOSITE_GAP_DOMINANT:
        max_combo_ev = max((c.expected_return or 0.0) for c in combos)
        if max_combo_ev < COMBO_WEAK_EV:
            tansho_only = True

    longshot_yen = 0
    longshot_bet_type = None
    longshot_horses = None
    longshot_odds = None
    longshot_label = ""
    axis_odds = race_eff.axis_odds or 0.0
    if not tansho_only and best is not None and axis_odds >= LONGSHOT_AXIS_ODDS:
        ls_plan = best
        if ls_plan.bet_type not in LONGSHOT_PREFERRED:
            pref = [c for c in combos if c.bet_type in LONGSHOT_PREFERRED]
            ls_plan = best_combo(pref) or ls_plan
        picked = pick_longshot_leg(ls_plan)
        if picked is not None:
            leg, o, yen = picked
            longshot_yen = yen
            longshot_bet_type = ls_plan.bet_type
            longshot_horses = leg
            longshot_odds = o
            longshot_label = ls_plan.label

    if tansho_only:
        mode = "boost" if kelly_boost > 1.0 else "tansho_only"
        reason = (
            f"◎突出/複合EV<{COMBO_WEAK_EV} → 単のみ"
            if gap >= COMPOSITE_GAP_DOMINANT and n_combo > 0
            else "複合 fund 0 → 単勝◎に集中"
        )
        if kelly_boost > 1.0:
            reason += f" + 増額 (Kelly×{kelly_boost:.2f}, EV={ax_ev:.2f})"
        return FundDecision(
            mode=mode, reason=reason, kelly_boost=kelly_boost, tansho_only=True,
            longshot_yen=0, **base_kw,
        )

    if longshot_yen > 0 and kelly_boost <= 1.05:
        return FundDecision(
            mode="longshot_flow",
            reason=(f"軸{axis_odds:.1f}倍 + 複合EV>=floor → 大穴{longshot_yen}円流し "
                    f"({longshot_label})"),
            kelly_boost=kelly_boost, tansho_only=False,
            longshot_yen=longshot_yen, longshot_bet_type=longshot_bet_type,
            longshot_horses=longshot_horses, longshot_odds=longshot_odds,
            longshot_label=longshot_label, **base_kw,
        )

    if kelly_boost > 1.0:
        return FundDecision(
            mode="boost",
            reason=(f"自信度+EV (composite_gap={gap:.2f}, axis_EV={ax_ev:.2f}) "
                    f"→ 増額 Kelly×{kelly_boost:.2f} + 複合{n_combo}件"),
            kelly_boost=kelly_boost, tansho_only=False,
            longshot_yen=longshot_yen, longshot_bet_type=longshot_bet_type,
            longshot_horses=longshot_horses, longshot_odds=longshot_odds,
            longshot_label=longshot_label, **base_kw,
        )

    return FundDecision(
        mode="spread",
        reason=f"複合 fund {n_combo}件 (EV>={ev_floor}) + アンカー",
        kelly_boost=1.0, tansho_only=False,
        longshot_yen=longshot_yen, longshot_bet_type=longshot_bet_type,
        longshot_horses=longshot_horses, longshot_odds=longshot_odds,
        longshot_label=longshot_label, **base_kw,
    )


def filter_plans_for_fund(plans, decision: FundDecision, *, ev_floor: float) -> Tuple[List, List]:
    """FundDecision に従い plans を selected / skipped に分ける (BetSelection 用)。"""
    selected, skipped = [], []
    for p in plans:
        if p.bet_type == "tansho":
            if decision.mode == "skip_all":
                skipped.append((p, "fund 降りる"))
            else:
                selected.append((p, decision.reason if decision.kelly_boost > 1.0
                                 else "軸◎の単勝 (基準券種・アンカー)"))
            continue
        if p.bet_type == "fukusho":
            if decision.mode == "skip_all":
                skipped.append((p, "fund 降りる"))
            elif not passes_fukusho_floor(p):
                skipped.append((p, f"複勝薄利 floor (odds<{DEFAULT_FUKUSHO_MIN_ODDS} or 期待利益不足)"))
            else:
                selected.append((p, "軸◎の複勝 (floor 通過)"))
            continue
        if decision.tansho_only or decision.mode == "skip_all":
            ev_s = f"{p.expected_return:.2f}" if p.expected_return is not None else "N/A"
            skipped.append((p, f"単のみ出し分け (EV={ev_s})"))
            continue
        if p.expected_return is None or p.expected_return < ev_floor:
            ev_s = f"{p.expected_return:.2f}" if p.expected_return is not None else "N/A"
            skipped.append((p, f"EV={ev_s}<floor({ev_floor}) → 降りる"))
        else:
            selected.append((p, f"EV={p.expected_return:.2f}>=floor → fund"))
    return selected, skipped
