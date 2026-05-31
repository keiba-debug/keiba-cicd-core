#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""multi-bettype サイジング層 (Session 140 / 全レース multi-bettype 自動投票 v1)

bettype_selection が選んだ券種 (SelectedPlan) に「いくら賭けるか」を割り当てる純関数層。
DB/IO/subprocess なし。 bettype_scheduler から呼ばれる。

★方針 (ふくだ判断 Session140): 「アンカー◎単/複 = 既存 freebudget Kelly」+「複合 = per_race
  残予算を EV 比例配分 (plan 内は逆オッズ)」。
  複合券種の各 leg (馬連3点等) は ★排反/相関★ (同時に的中しない) なので、 naive per-leg
  Kelly は oversize になり理論的に誤り。 → 複合は plan 単位の固定予算 (per_race 残) を
  EV 比例で配分し、 plan 内 leg は合成オッズ定義 (stakeₖ∝1/oₖ) と整合する逆オッズ配分。
  元本リスクの主はアンカー Kelly、 複合は上限内の widen に留める (保守)。

★アンカーの Kelly 式は freebudget.py:182-190 を忠実にミラー (同額になることを test で担保)。
  アンカー◎単: p = 軸の pred_proba_w_cal (= HorseStrength.pred_w, calibrated), odds = axis_odds。
  アンカー◎複: p = fukusho plan の hit_prob (harville place 確率), odds = place_odds_min (最低値=保守)。

入力: be.RaceEfficiency (各 plan の odds_legs/EV/hit_prob) + bettype_selection.BetSelection。
出力: RaceSizing (SizedLeg のリスト + 内訳)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

from ml.bet_engine import calc_kelly_fraction
from ml.strategies.freebudget import BET_UNIT_YEN, MIN_BET_YEN

# アンカー (◎単/複) = 排反/相関の無い独立 1 点なので Kelly を厳密適用してよい券種。
ANCHOR_BET_TYPES = ("tansho", "fukusho")
DEFAULT_SIZER = "anchor_kelly_combo_ev"


def _legs_key(legs) -> tuple:
    """plan.legs (List[List[int]]) を hashable key 化 (順序保持)。"""
    return tuple(tuple(int(h) for h in leg) for leg in legs)


# ---------------------------------------------------------------------------
# データ構造
# ---------------------------------------------------------------------------

@dataclass
class SizedLeg:
    race_id: str
    bet_type: str
    horses: List[int]            # 買い目の馬番 (馬単/三連単は順序保持)
    amount: int                  # 100円単位
    plan_label: str
    leg_odds: Optional[float]    # この点の市場オッズ (None=未取得)
    ev: Optional[float]          # 所属 plan の期待リターン (アンカーは None)
    hit_prob: Optional[float]
    note: str = ""


@dataclass
class RaceSizing:
    race_id: str
    legs: List[SizedLeg]
    total_yen: int
    anchor_yen: int
    combo_yen: int
    per_race_cap: int
    n_dropped: int = 0
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Kelly (アンカー専用。 freebudget.py:182-190 と同一式)
# ---------------------------------------------------------------------------

def kelly_amount(p: Optional[float], odds: Optional[float], *, bankroll: int,
                 kelly_fraction: float, per_bet_cap_pct: float) -> int:
    """1 点の Kelly 投資額 (100円単位)。 freebudget の単勝サイジングと同一式。

    f = min(calc_kelly_fraction(p, odds) * kelly_fraction, per_bet_cap_pct)
    amount = min(floor(bankroll*f/100)*100, per_bet_cap_yen)。 MIN 未満は 0。
    """
    if odds is None or odds <= 1.0 or p is None or not (0.0 < p < 1.0):
        return 0
    kelly_raw = calc_kelly_fraction(p, odds)
    if kelly_raw <= 0:
        return 0
    kelly_sized = min(kelly_raw * kelly_fraction, per_bet_cap_pct)
    amount = (int(bankroll * kelly_sized) // BET_UNIT_YEN) * BET_UNIT_YEN
    per_bet_cap_yen = (int(bankroll * per_bet_cap_pct) // BET_UNIT_YEN) * BET_UNIT_YEN
    amount = min(amount, per_bet_cap_yen)
    return amount if amount >= MIN_BET_YEN else 0


# ---------------------------------------------------------------------------
# per_race cap 按分 (freebudget_scheduler.fit_result_to_cap と同型 + アンカー保護)
# ---------------------------------------------------------------------------

def fit_legs_to_cap(legs: List[SizedLeg], cap: int, *,
                    unit: int = BET_UNIT_YEN) -> Tuple[List[SizedLeg], int]:
    """legs 合計が cap 超なら per_race 以内に按分 (比例縮小→最低unit→低EV drop)。

    ★アンカー (単/複) 保護★: drop は低 EV 順だが、 アンカーの並べ替えキーを +inf 扱いに
    して最後まで残す (複合を先に落とす)。 縮小のみなので 1 点が元値や per_bet_cap を超える
    ことはない。 戻り: (新 legs, dropped 数)。
    """
    total = sum(l.amount for l in legs)
    if cap <= 0 or total <= cap or not legs:
        return legs, 0
    factor = cap / total
    scaled: List[SizedLeg] = []
    for l in legs:
        s = int((l.amount * factor) // unit * unit)
        s = max(unit, s)
        scaled.append(SizedLeg(l.race_id, l.bet_type, l.horses, s, l.plan_label,
                               l.leg_odds, l.ev, l.hit_prob, l.note))
    cur = sum(l.amount for l in scaled)
    dropped = 0
    if cur > cap:
        # 低 EV 順に drop。 アンカーは +inf で最後まで残す (複合を先に落とす)。
        def drop_key(l: SizedLeg) -> float:
            if l.bet_type in ANCHOR_BET_TYPES:
                return float("inf")
            return l.ev if l.ev is not None else 0.0
        order = sorted(range(len(scaled)), key=lambda i: drop_key(scaled[i]))
        keep = [True] * len(scaled)
        for i in order:
            if cur <= cap:
                break
            cur -= scaled[i].amount
            keep[i] = False
            dropped += 1
        scaled = [l for l, k in zip(scaled, keep) if k]
    return scaled, dropped


# ---------------------------------------------------------------------------
# 複合: plan 内 leg を逆オッズ配分
# ---------------------------------------------------------------------------

def _alloc_inverse_odds(legs: List[List[int]], odds_legs: List[Optional[float]],
                        budget: int, *, unit: int = BET_UNIT_YEN,
                        min_bet: int = MIN_BET_YEN) -> List[Tuple[List[int], Optional[float], int]]:
    """budget を plan 内の各 leg に逆オッズ (wᵢ=1/oᵢ) で配分 (100円単位、 min 未満は 0)。

    オッズ欠損の leg は present の平均重みを割り当て (均等寄り)。 全欠損なら均等配分。
    端数は最大重み leg に寄せて budget を超えない範囲で。 戻り: [(leg, odds, amount), ...]。
    """
    n = len(legs)
    if n == 0 or budget < min_bet:
        return [(leg, (odds_legs[i] if i < len(odds_legs) else None), 0)
                for i, leg in enumerate(legs)]
    present = [(odds_legs[i] if i < len(odds_legs) else None) for i in range(n)]
    inv = [(1.0 / o) if (o and o > 0) else None for o in present]
    known = [w for w in inv if w is not None]
    fill = (sum(known) / len(known)) if known else 1.0
    weights = [w if w is not None else fill for w in inv]
    wsum = sum(weights) or 1.0
    amounts = [int((budget * (w / wsum)) // unit) * unit for w in weights]
    amounts = [a if a >= min_bet else 0 for a in amounts]
    # 端数を最大重み leg から順に unit 単位で budget 内まで上乗せ
    leftover = budget - sum(amounts)
    if leftover >= unit:
        for i in sorted(range(n), key=lambda i: weights[i], reverse=True):
            while leftover >= unit and amounts[i] >= min_bet:
                amounts[i] += unit
                leftover -= unit
                break  # 1 leg 1 回だけ上乗せ (薄く広く)
            if leftover < unit:
                break
    return [(legs[i], present[i], amounts[i]) for i in range(n)]


# ---------------------------------------------------------------------------
# サイザー本体
# ---------------------------------------------------------------------------

def size_race(race_eff, selection, *, bankroll: int, per_race_cap: int,
              kelly_fraction: float = 0.25, per_bet_cap_pct: float = 0.10,
              combo_share_of_residual: float = 1.0,
              weight_key: str = "ev") -> RaceSizing:
    """RaceEfficiency + BetSelection → 各 leg に amount を付けた RaceSizing。

    アンカー◎単/複 = freebudget Kelly。 複合 = per_race 残予算を EV 比例 → plan 内逆オッズ。
    最終 fit_legs_to_cap で per_race 以内に収める (アンカー保護)。
    """
    legs: List[SizedLeg] = []
    warnings: List[str] = []
    rid = race_eff.race_id
    axis = race_eff.axis_umaban
    axis_odds = race_eff.axis_odds
    # ★bettype_efficiency は同一券種で複数の幅 (馬連◎-相手2/3/4 等、入れ子) を別 plan として
    #   出す。 選定 plan を (bet_type, legs) で正確にマッチし、 複合は券種ごとに 1 つへ dedup
    #   (入れ子の重複買いを防ぐ)。 by_type で潰すと別幅の plan を二重サイジングしてしまう。
    eff_by_key = {(p.bet_type, _legs_key(p.legs)): p for p in race_eff.plans}
    axis_strength = next((s for s in race_eff.strengths if s.umaban == axis), None)
    axis_pred_w = axis_strength.pred_w if axis_strength else None

    sel_tansho = next((sp for sp in selection.selected_plans if sp.bet_type == "tansho"), None)
    sel_fukusho = next((sp for sp in selection.selected_plans if sp.bet_type == "fukusho"), None)

    # (A) アンカー◎単 = freebudget Kelly (p=軸 pred_w calibrated, odds=axis_odds)
    if sel_tansho is not None:
        amt = kelly_amount(axis_pred_w, axis_odds, bankroll=bankroll,
                           kelly_fraction=kelly_fraction, per_bet_cap_pct=per_bet_cap_pct)
        if amt >= MIN_BET_YEN:
            tp = eff_by_key.get(("tansho", _legs_key(sel_tansho.legs)))
            legs.append(SizedLeg(rid, "tansho", [axis], amt,
                                 tp.label if tp else "単勝 ◎", axis_odds,
                                 None, (tp.hit_prob if tp else None),
                                 "anchor freebudget Kelly"))

    # (A') アンカー◎複 = Kelly (p=fukusho hit_prob, odds=place_odds_min 最低値=保守)
    if sel_fukusho is not None:
        fp = eff_by_key.get(("fukusho", _legs_key(sel_fukusho.legs)))
        if fp is not None:
            f_odds = fp.odds_legs[0] if fp.odds_legs else None
            amt = kelly_amount(fp.hit_prob, f_odds, bankroll=bankroll,
                               kelly_fraction=kelly_fraction, per_bet_cap_pct=per_bet_cap_pct)
            if amt >= MIN_BET_YEN:
                legs.append(SizedLeg(rid, "fukusho", [axis], amt, fp.label, f_odds,
                                     None, fp.hit_prob, "anchor place Kelly (保守)"))

    anchor_yen = sum(l.amount for l in legs)

    # (B) 複合 = per_race 残予算を EV 比例で各 plan に配分 → plan 内逆オッズ
    #   ★券種ごとに 1 plan へ dedup★ (最良 EV、 同点なら広い=点数多い方)。 入れ子幅の重複買い回避。
    cap_for_residual = per_race_cap if per_race_cap > 0 else bankroll
    residual = max(0, cap_for_residual - anchor_yen)
    combo_budget = int(residual * combo_share_of_residual)
    best_by_type: Dict[str, object] = {}
    for sp in selection.selected_plans:
        if sp.bet_type in ANCHOR_BET_TYPES:
            continue
        plan = eff_by_key.get((sp.bet_type, _legs_key(sp.legs)))
        if plan is None or plan.expected_return is None:
            continue   # 市場オッズ未取得 (EV 計算不能) の plan は買わない
        cur = best_by_type.get(sp.bet_type)
        if cur is None or (plan.expected_return, len(plan.legs)) > \
                (cur.expected_return, len(cur.legs)):
            best_by_type[sp.bet_type] = plan
    combo_plans: List[Tuple[object, float]] = []
    for plan in best_by_type.values():
        w = plan.expected_return if weight_key == "ev" else (plan.hit_prob or 0.0)
        if w and w > 0:
            combo_plans.append((plan, float(w)))

    if combo_plans and combo_budget >= MIN_BET_YEN:
        wsum = sum(w for _, w in combo_plans) or 1.0
        for plan, w in combo_plans:
            plan_budget = int(combo_budget * (w / wsum))
            if plan_budget < MIN_BET_YEN:
                continue
            for leg, o, amt in _alloc_inverse_odds(plan.legs, plan.odds_legs, plan_budget):
                if amt >= MIN_BET_YEN:
                    legs.append(SizedLeg(rid, plan.bet_type, list(leg), amt, plan.label,
                                         o, plan.expected_return, plan.hit_prob,
                                         "combo EV-prop / inverse-odds"))

    # (C) per_race cap で最終 truncate (アンカー保護)
    pre_total = sum(l.amount for l in legs)
    n_dropped = 0
    if per_race_cap > 0 and pre_total > per_race_cap:
        legs, n_dropped = fit_legs_to_cap(legs, per_race_cap)
        warnings.append(f"per_race按分 {pre_total}->{sum(l.amount for l in legs)} "
                        f"drop={n_dropped}")

    total = sum(l.amount for l in legs)
    anchor_yen = sum(l.amount for l in legs if l.bet_type in ANCHOR_BET_TYPES)
    return RaceSizing(race_id=rid, legs=legs, total_yen=total, anchor_yen=anchor_yen,
                      combo_yen=total - anchor_yen, per_race_cap=per_race_cap,
                      n_dropped=n_dropped, warnings=warnings)


# ---------------------------------------------------------------------------
# プラガブルサイザー登録
# ---------------------------------------------------------------------------

SizerFn = Callable[..., RaceSizing]
SIZERS: Dict[str, SizerFn] = {DEFAULT_SIZER: size_race}


def get_sizer(name: str) -> SizerFn:
    if name not in SIZERS:
        raise ValueError(f"unknown sizer: {name!r} (allowed: {tuple(SIZERS)})")
    return SIZERS[name]
