#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""券種効率ビュー — ハーヴィル確率 × 市場オッズ で「合成オッズ・期待リターン」を一覧化
(Session 138 / bettype-selection-roadmap Phase 2 = 判断支援・可視化)

設計思想: [[bettype-selection-roadmap]] / [[feedback_betting_philosophy]] §4
  買い目の基本は予想 (各馬の強さ)。 ある「軸◎」を決め、 そこから各券種へ
  「広げる」プランの (的中確率, 合成オッズ, 期待リターン) を並べて、
  「合成オッズ < 単オッズ なら広げる意味が薄い」を可視化する。
  EV>1 で全 fund する機械判断ではなく、 券種を「絞る/降りる」判断を支援する道具。

3 レイヤー (どこを差し替えるか):
  ① 強さ判定 (軸◎/相手の選定):
       specialist overlay (例: 新潟千直 niigata1000) > W/P/ADR 総合 > 単独 の優先順。
       総合 = 各シグナルを race 内 z-score 化して加重和 (重みパラメータ化)。
       ★ここが「再検証で重みを決めたい」対象。 既定は等重み (Themis: 過学習回避)。
  ② ハーヴィル入力 (勝率 p_i):  数学的に「勝率」必須 → pred_proba_w_cal (正規化)。
       specialist の display_score は top3 確率なので、 強さ判定(①)には使うが
       ハーヴィル入力(②)には使わない (勝率モデルが無いため。 将来拡張余地)。
  ③ 合成オッズ・期待リターン (全て inverse-odds staking 前提 = 各点 stakeₖ ∝ 1/oₖ):
       合成オッズ G = 1 / Σ(1/oₖ)          … 均等払戻 (inverse-odds) 定義 = ふくだの「合成2倍」感覚
       期待リターン EV = Σ pₖ / Σ(1/oₖ) = G · Σpₖ   … 「支出1あたりの期待払戻倍率」。
            EV>1.0 = 期待値プラス / EV<1.0 = 期待値マイナス。 市場には控除率 (単20%/三連系27.5%)
            があるため、 市場オッズベースでは通常ほぼ全プランで EV<1.0 が常態 (これが普通)。
            期待値の線形性で全券種正しい (ワイド多重的中も。 Session 138 で Monte Carlo 検証済)。
       的中確率 H = P(プラン内 ≥1 点が的中)  … 排反券種は Σpₖ、 ワイド/複は top3 集合分布で厳密。

  ★vs_tansho ('合成オッズ <> 単オッズ') は「広げる相対妙味」の比較であって EV の絶対水準ではない。
    合成 > 単 でも EV<1.0 (期待マイナス) はあり得る → 「広げ得≠儲かる」。 fund 判断には使わない。

市場オッズ: core.odds_db.get_all_combo_odds (DB 全7券種)。 単勝/複勝は predictions の
  最新値 (entry['odds'] / entry['place_odds_min']) を優先 (vb_refresh が更新)。

CLI:
    python -m ml.strategies.bettype_efficiency --race 2026053005021101
    python -m ml.strategies.bettype_efficiency --race 2026053005021101 --axis 3
    python -m ml.strategies.bettype_efficiency --date 2026-05-30        # 全レース → JSON artifact
    python -m ml.strategies.bettype_efficiency --date today --weights 1,1,1
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from itertools import combinations, permutations
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.strategies import harville as hv  # noqa: E402
from ml.utils.race_io import date_dir_for, load_predictions  # noqa: E402

ARTIFACT_NAME = "bettype_efficiency.json"
SCHEMA_VERSION = "1.0"

# 軸からの相手頭数 (合成オッズの「広げラダー」をどこまで作るか)
DEFAULT_N_PARTNERS = 4
# W / P / ADR の既定重み (等重み。 Themis: 過学習回避。 backtest で差し替え可能)
DEFAULT_WEIGHTS = (1.0, 1.0, 1.0)


# ---------------------------------------------------------------------------
# データ構造
# ---------------------------------------------------------------------------

@dataclass
class HorseStrength:
    umaban: int
    horse_name: str
    win_prob: float            # ハーヴィル入力 (正規化済 pred_proba_w_cal)
    odds: Optional[float]      # 単勝オッズ
    place_odds_min: Optional[float]
    # 強さ判定の素
    pred_w: Optional[float]
    pred_p: Optional[float]    # specialist 適用時は display_score
    ar_deviation: Optional[float]
    z_w: Optional[float]
    z_p: Optional[float]
    z_adr: Optional[float]
    composite: float
    p_source: str = "model"    # 'model' | 'specialist'
    rank_w: Optional[int] = None
    rank_p: Optional[int] = None
    rank_adr: Optional[int] = None
    rank_composite: Optional[int] = None


@dataclass
class Plan:
    bet_type: str              # tansho/fukusho/umaren/wide/umatan/sanrenpuku/sanrentan
    label: str                 # 日本語ラベル (例: "馬連 ◎-相手3")
    legs: List[List[int]]      # 各点の馬番組 (例: [[3,7],[3,11]])
    n_points: int
    hit_prob: float            # P(プラン内 ≥1点 的中)
    sum_p: float               # Σ pₖ (期待的中点数。 排反券種では hit_prob と一致)
    synthetic_odds: Optional[float]   # 合成オッズ G = 1/Σ(1/oₖ)
    expected_return: Optional[float]  # 期待リターン EV = Σpₖ/Σ(1/oₖ)
    odds_legs: List[Optional[float]]  # 各点の市場オッズ (None=未取得)
    coverage: float            # オッズが取れた点の割合 (1.0=全点)
    vs_tansho: Optional[str] = None   # 'lt' (合成<単=広げ意味薄) | 'gt' | None (基準/N/A)


@dataclass
class RaceEfficiency:
    race_id: str
    date: Optional[str]
    venue_name: Optional[str]
    race_number: Optional[int]
    grade: str
    track_type: Optional[str]
    distance: Optional[int]
    num_runners: Optional[int]
    axis_umaban: int
    axis_name: str
    axis_odds: Optional[float]
    partners: List[int]
    weights: Tuple[float, float, float]
    specialist: Optional[str]          # 'niigata1000' 等 (適用時) | None
    strengths: List[HorseStrength]
    plans: List[Plan]
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 強さ判定 (①)
# ---------------------------------------------------------------------------

def _zscores(values: Sequence[Optional[float]]) -> List[Optional[float]]:
    """None を除いた集合で z-score 化。 None はそのまま None。 std=0 は全 0。"""
    present = [v for v in values if v is not None]
    n = len(present)
    if n == 0:
        return [None] * len(values)
    mean = sum(present) / n
    var = sum((v - mean) ** 2 for v in present) / n
    std = var ** 0.5
    if std <= 1e-12:
        return [0.0 if v is not None else None for v in values]
    return [((v - mean) / std) if v is not None else None for v in values]


def _detect_specialist(pred_race: dict) -> Optional[str]:
    """適用されている specialist overlay 名を返す (なければ None)。"""
    if pred_race.get("niigata1000_applied"):
        return "niigata1000"
    return None


def compute_strengths(
    pred_race: dict,
    *,
    weights: Tuple[float, float, float] = DEFAULT_WEIGHTS,
    prefer_specialist: bool = True,
) -> Tuple[List[HorseStrength], Optional[str]]:
    """entries から各馬の強さ (W/P/ADR 総合) と ハーヴィル用勝率を計算。

    Returns: (composite 降順の HorseStrength リスト, specialist名 or None)
    """
    entries = pred_race.get("entries", []) or []
    specialist = _detect_specialist(pred_race) if prefer_specialist else None

    rows = []
    for e in entries:
        umaban = e.get("umaban")
        if umaban is None:
            continue
        w = e.get("pred_proba_w_cal")
        p = e.get("pred_proba_p")
        adr = e.get("ar_deviation")
        p_source = "model"
        # specialist 適用レースは P シグナルを overlay の補正 top3 確率に差し替え
        if specialist == "niigata1000":
            ov = e.get("niigata1000") or {}
            ds = ov.get("display_score")
            if ds is not None:
                p = ds
                p_source = "specialist"
        rows.append({
            "umaban": int(umaban),
            "horse_name": str(e.get("horse_name") or ""),
            "odds": _f(e.get("odds")),
            "place_odds_min": _f(e.get("place_odds_min")),
            "pred_w": _f(w),
            "pred_p": _f(p),
            "ar_deviation": _f(adr),
            "p_source": p_source,
        })

    if not rows:
        return [], specialist

    # race 内 z-score
    zw = _zscores([r["pred_w"] for r in rows])
    zp = _zscores([r["pred_p"] for r in rows])
    za = _zscores([r["ar_deviation"] for r in rows])
    wW, wP, wA = weights

    # ハーヴィル用勝率 (正規化 pred_w)
    win_probs = hv.normalize({r["umaban"]: (r["pred_w"] or 0.0) for r in rows})

    strengths: List[HorseStrength] = []
    for i, r in enumerate(rows):
        parts = []
        if zw[i] is not None:
            parts.append((wW, zw[i]))
        if zp[i] is not None:
            parts.append((wP, zp[i]))
        if za[i] is not None:
            parts.append((wA, za[i]))
        wsum = sum(w for w, _ in parts)
        composite = (sum(w * z for w, z in parts) / wsum) if wsum > 0 else 0.0
        strengths.append(HorseStrength(
            umaban=r["umaban"],
            horse_name=r["horse_name"],
            win_prob=float(win_probs.get(r["umaban"], 0.0)),
            odds=r["odds"],
            place_odds_min=r["place_odds_min"],
            pred_w=r["pred_w"],
            pred_p=r["pred_p"],
            ar_deviation=r["ar_deviation"],
            z_w=_round(zw[i]), z_p=_round(zp[i]), z_adr=_round(za[i]),
            composite=round(composite, 4),
            p_source=r["p_source"],
        ))

    # 各シグナル別ランク (1=最強) + composite ランク
    _assign_rank(strengths, key=lambda s: (s.pred_w if s.pred_w is not None else -1), attr="rank_w")
    _assign_rank(strengths, key=lambda s: (s.pred_p if s.pred_p is not None else -1), attr="rank_p")
    _assign_rank(strengths, key=lambda s: (s.ar_deviation if s.ar_deviation is not None else -1), attr="rank_adr")
    # composite 降順。 同点 (全馬同値レース等で std=0 → z 全 0) は
    # win_prob 降順 → 馬番昇順 で決定的に並べる (axis がデータ順序依存にならないよう)
    strengths.sort(key=lambda s: (s.composite, s.win_prob, -s.umaban), reverse=True)
    for idx, s in enumerate(strengths, 1):
        s.rank_composite = idx
    return strengths, specialist


def _assign_rank(items, key, attr):
    order = sorted(items, key=key, reverse=True)
    for idx, it in enumerate(order, 1):
        setattr(it, attr, idx)


# ---------------------------------------------------------------------------
# top3 集合分布 (ワイド/複勝の「≥1的中」を厳密に出すため)
# ---------------------------------------------------------------------------

def topk_set_distribution(win_probs: Dict[int, float], k: int) -> Dict[frozenset, float]:
    """各 k 頭集合が (順不同で) top-k になる確率。 ハーヴィル ordered_prob の和。

    k=3 (8頭以上の複勝/ワイド) / k=2 (7頭以下) の双方を近似せず厳密に出す。
    """
    ids = [h for h, v in win_probs.items() if v > 0]
    dist: Dict[frozenset, float] = {}
    if len(ids) < k or k < 1:
        return dist
    for combo in combinations(ids, k):
        s = 0.0
        for order in permutations(combo, k):
            s += hv.ordered_prob(win_probs, order)
        dist[frozenset(combo)] = s
    return dist


def top3_set_distribution(win_probs: Dict[int, float]) -> Dict[frozenset, float]:
    """top3 集合分布 (= topk_set_distribution(win_probs, 3))。 後方互換用エイリアス。"""
    return topk_set_distribution(win_probs, 3)


# ---------------------------------------------------------------------------
# 合成オッズ・期待リターン (③)
# ---------------------------------------------------------------------------

def synthetic_and_ev(
    leg_probs: Sequence[float],
    leg_odds: Sequence[Optional[float]],
) -> Tuple[Optional[float], Optional[float], float, float]:
    """合成オッズ G, 期待リターン EV, Σpₖ, coverage を返す。

    G  = 1 / Σ(1/oₖ)              (oₖ が取れた点のみ)
    EV = Σ pₖ / Σ(1/oₖ) = G·Σpₖ  (期待値の線形性 → ワイド多重的中も正しい)
    オッズ未取得 (None) の点は G/EV の計算から除外し coverage に反映。
    """
    inv_sum = 0.0
    sum_p_funded = 0.0
    n_funded = 0
    sum_p_all = sum(leg_probs)
    for p, o in zip(leg_probs, leg_odds):
        if o is not None and o > 0:
            inv_sum += 1.0 / o
            sum_p_funded += p
            n_funded += 1
    coverage = (n_funded / len(leg_odds)) if leg_odds else 0.0
    if inv_sum <= 0:
        return None, None, sum_p_all, coverage
    g = 1.0 / inv_sum
    ev = sum_p_funded / inv_sum
    return g, ev, sum_p_all, coverage


# ---------------------------------------------------------------------------
# プラン構築 (②③)
# ---------------------------------------------------------------------------

def _kumiban(*umaban: int, ordered: bool) -> str:
    seq = list(umaban) if ordered else sorted(umaban)
    return "".join(f"{u:02d}" for u in seq)


def _odds_for(combo_odds: dict, bet_type: str, legs: List[List[int]],
              ordered: bool) -> List[Optional[float]]:
    table = combo_odds.get(bet_type, {}) or {}
    out = []
    for leg in legs:
        kb = _kumiban(*leg, ordered=ordered)
        ent = table.get(kb)
        out.append(ent.get("odds") if ent else None)
    return out


def build_plans(
    strengths: List[HorseStrength],
    win_probs: Dict[int, float],
    combo_odds: dict,
    *,
    axis: int,
    partners: List[int],
    n_runners: int,
) -> List[Plan]:
    """軸 axis から各券種へ広げるプラン群を構築。"""
    plans: List[Plan] = []
    by_umaban = {s.umaban: s for s in strengths}
    axis_odds = by_umaban[axis].odds if axis in by_umaban else None
    axis_place = by_umaban[axis].place_odds_min if axis in by_umaban else None
    places_k = 3 if n_runners >= 8 else 2  # 複勝/ワイド着内数 (7頭以下は2)
    # places_k 着集合の分布 (k=2/3 とも厳密。 7頭以下も近似せず正確に ≥1的中を出す)
    set_dist = topk_set_distribution(win_probs, places_k)

    def _fukusho_hit(u: int) -> float:
        return sum(p for s, p in set_dist.items() if u in s)

    def _wide_pair_hit(a: int, b: int) -> float:
        return sum(p for s, p in set_dist.items() if a in s and b in s)

    def _wide_nagashi_hit(a: int, ps: List[int]) -> float:
        # 軸 a を含み、 かつ相手集合と交わる top-k 集合の確率和 = ≥1点的中 (容斥不要、 排反な集合の和)
        pset = set(ps)
        return sum(p for s, p in set_dist.items() if a in s and (s & pset))

    def add(bet_type, label, legs, leg_probs, leg_odds, *, is_base=False, compare=True):
        g, ev, sum_p, cov = synthetic_and_ev(leg_probs, leg_odds)
        # 的中確率 (排反券種は Σpₖ、 ワイド/複は呼び側で別途 hit を渡す→ leg_probs と別)
        plan = Plan(
            bet_type=bet_type, label=label,
            legs=[list(l) for l in legs], n_points=len(legs),
            hit_prob=0.0, sum_p=round(sum_p, 5),
            synthetic_odds=_round(g), expected_return=_round(ev),
            odds_legs=[_round(o) for o in leg_odds], coverage=round(cov, 3),
        )
        # vs 単オッズ判定
        if compare and g is not None and axis_odds:
            plan.vs_tansho = "lt" if g < axis_odds else "gt"
        elif is_base:
            plan.vs_tansho = None
        return plan

    # 1. 単勝 ◎
    p_axis = win_probs.get(axis, 0.0)
    plan = add("tansho", "単勝 ◎", [[axis]], [p_axis], [axis_odds],
               is_base=True, compare=False)
    plan.hit_prob = round(p_axis, 5)
    plans.append(plan)

    # 2. 複勝 ◎
    fhit = _fukusho_hit(axis)
    plan = add("fukusho", "複勝 ◎", [[axis]], [fhit], [axis_place], compare=False)
    plan.hit_prob = round(fhit, 5)
    plans.append(plan)

    # 3-5. 馬連 ◎-相手 N (top2/3/4)
    for k in (2, 3, 4):
        ps = partners[:k]
        if len(ps) < k:
            break
        legs = [[axis, b] for b in ps]
        probs = [hv.umaren_prob(win_probs, axis, b) for b in ps]
        odds = _odds_for(combo_odds, "umaren", legs, ordered=False)
        plan = add("umaren", f"馬連 ◎-相手{k}", legs, probs, odds)
        plan.hit_prob = round(sum(probs), 5)  # 排反
        plans.append(plan)

    # 6-7. ワイド ◎-相手 N (top2/3)
    for k in (2, 3):
        ps = partners[:k]
        if len(ps) < k:
            break
        legs = [[axis, b] for b in ps]
        probs = [_wide_pair_hit(axis, b) for b in ps]   # 個別 (EV は線形性で OK)
        odds = _odds_for(combo_odds, "wide", legs, ordered=False)
        plan = add("wide", f"ワイド ◎-相手{k}", legs, probs, odds)
        plan.hit_prob = round(_wide_nagashi_hit(axis, ps), 5)  # ≥1的中 (厳密)
        plans.append(plan)

    # 8-9. 馬単 ◎→相手 N (top2/3)
    for k in (2, 3):
        ps = partners[:k]
        if len(ps) < k:
            break
        legs = [[axis, b] for b in ps]
        probs = [hv.umatan_prob(win_probs, axis, b) for b in ps]
        odds = _odds_for(combo_odds, "umatan", legs, ordered=True)
        plan = add("umatan", f"馬単 ◎→相手{k}", legs, probs, odds)
        plan.hit_prob = round(sum(probs), 5)  # 排反
        plans.append(plan)

    # 10. 三連複 ◎軸 - 相手3 (box pairs)
    if len(partners) >= 3:
        ps = partners[:3]
        legs = [[axis, a, b] for a, b in combinations(ps, 2)]
        probs = [hv.sanrenpuku_prob(win_probs, axis, a, b) for a, b in combinations(ps, 2)]
        odds = _odds_for(combo_odds, "sanrenpuku", legs, ordered=False)
        plan = add("sanrenpuku", "三連複 ◎-相手3", legs, probs, odds)
        plan.hit_prob = round(sum(probs), 5)  # 排反 (異なる3頭集合)
        plans.append(plan)

    # 11. 三連単 ◎1着 → 相手3 (2-3着 順列)
    if len(partners) >= 3:
        ps = partners[:3]
        legs = [[axis, a, b] for a, b in permutations(ps, 2)]
        probs = [hv.sanrentan_prob(win_probs, axis, a, b) for a, b in permutations(ps, 2)]
        odds = _odds_for(combo_odds, "sanrentan", legs, ordered=True)
        plan = add("sanrentan", "三連単 ◎→相手3", legs, probs, odds)
        plan.hit_prob = round(sum(probs), 5)  # 排反
        plans.append(plan)

    return plans


# ---------------------------------------------------------------------------
# レース評価
# ---------------------------------------------------------------------------

def evaluate_race(
    pred_race: dict,
    combo_odds: dict,
    *,
    axis: Optional[int] = None,
    weights: Tuple[float, float, float] = DEFAULT_WEIGHTS,
    n_partners: int = DEFAULT_N_PARTNERS,
    prefer_specialist: bool = True,
) -> Optional[RaceEfficiency]:
    strengths, specialist = compute_strengths(
        pred_race, weights=weights, prefer_specialist=prefer_specialist)
    if not strengths:
        return None
    win_probs = {s.umaban: s.win_prob for s in strengths}
    n_runners = pred_race.get("num_runners") or len([s for s in strengths if s.win_prob > 0])

    # 軸: 指定 or composite 最上位
    if axis is None:
        axis = strengths[0].umaban
    by = {s.umaban: s for s in strengths}
    if axis not in by:
        axis = strengths[0].umaban
    # 相手: 軸を除いた composite 上位
    partners = [s.umaban for s in strengths if s.umaban != axis][:n_partners]

    plans = build_plans(strengths, win_probs, combo_odds,
                        axis=axis, partners=partners, n_runners=n_runners or 0)

    warnings = []
    if sum(win_probs.values()) <= 0:
        warnings.append("勝率情報が不足 (pred_proba_w_cal が全馬欠損) → 的中確率を算出できません")
    if len(partners) < 3:
        warnings.append(f"相手{len(partners)}頭のため三連複・三連単プランは生成されません")
    combo_plans = [p for p in plans if p.bet_type not in ("tansho", "fukusho")]
    if combo_plans and all(p.synthetic_odds is None for p in combo_plans):
        warnings.append("組み合わせ券種の市場オッズが未取得 (DB にオッズ無し)")

    axis_s = by[axis]
    return RaceEfficiency(
        race_id=str(pred_race.get("race_id")),
        date=pred_race.get("date"),
        venue_name=pred_race.get("venue_name"),
        race_number=pred_race.get("race_number"),
        grade=str(pred_race.get("grade") or ""),
        track_type=pred_race.get("track_type"),
        distance=pred_race.get("distance"),
        num_runners=pred_race.get("num_runners"),
        axis_umaban=axis, axis_name=axis_s.horse_name, axis_odds=axis_s.odds,
        partners=partners, weights=weights, specialist=specialist,
        strengths=strengths, plans=plans, warnings=warnings,
    )


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def _f(v) -> Optional[float]:
    try:
        if v is None or v == "":
            return None
        f = float(v)
        return f
    except (ValueError, TypeError):
        return None


def _round(v, nd: int = 3):
    return round(v, nd) if isinstance(v, (int, float)) else None


def _load_combo_odds(race_id: str) -> dict:
    """DB から全券種オッズを取得 (DB 未接続なら空)。"""
    try:
        from core.odds_db import get_all_combo_odds, is_db_available
        if not is_db_available():
            return {}
        return get_all_combo_odds(race_id)
    except Exception:
        return {}


def race_to_dict(re_: RaceEfficiency) -> dict:
    d = asdict(re_)
    d["weights"] = list(re_.weights)
    return d


def process_race(
    pred_race: dict, *,
    axis: Optional[int] = None,
    weights: Tuple[float, float, float] = DEFAULT_WEIGHTS,
    n_partners: int = DEFAULT_N_PARTNERS,
) -> Optional[RaceEfficiency]:
    combo_odds = _load_combo_odds(str(pred_race.get("race_id")))
    return evaluate_race(pred_race, combo_odds, axis=axis,
                         weights=weights, n_partners=n_partners)


def process_date(
    date_str: str, *,
    weights: Tuple[float, float, float] = DEFAULT_WEIGHTS,
    n_partners: int = DEFAULT_N_PARTNERS,
    dry_run: bool = False,
    verbose: bool = True,
) -> dict:
    date_str = resolve_date(date_str)
    day_dir = date_dir_for(date_str)
    predictions = load_predictions(day_dir)
    if predictions is None:
        if verbose:
            print(f"  [{date_str}] predictions.json なし → スキップ")
        return {"date": date_str, "n_races": 0, "skipped": True}

    races = predictions.get("races", []) or []
    results = []
    for r in races:
        re_ = process_race(r, weights=weights, n_partners=n_partners)
        if re_ is not None:
            results.append(re_)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "date": date_str,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "weights": list(weights),
        "n_partners": n_partners,
        "n_races": len(results),
        "races": [race_to_dict(re_) for re_ in results],
    }
    if not dry_run:
        out_path = day_dir / ARTIFACT_NAME
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                            encoding="utf-8")
        if verbose:
            print(f"  [{date_str}] {len(results)} races → {out_path}")
    return {"date": date_str, "n_races": len(results), "skipped": False}


def resolve_date(date_str: str) -> str:
    if date_str.strip().lower() == "today":
        return datetime.now().strftime("%Y-%m-%d")
    return date_str


# ---------------------------------------------------------------------------
# CLI 表示
# ---------------------------------------------------------------------------

def _print_race(re_: RaceEfficiency) -> None:
    print(f"\n=== {re_.race_id} {re_.venue_name or '?'} {re_.race_number or '?'}R "
          f"{re_.grade} {re_.track_type or ''}{re_.distance or ''} "
          f"{re_.num_runners or '?'}頭 ===")
    spec = f" [specialist={re_.specialist}]" if re_.specialist else ""
    print(f"軸◎ {re_.axis_umaban}番 {re_.axis_name} "
          f"単{(re_.axis_odds or 0):.1f}倍  相手={re_.partners}{spec}  "
          f"weights(W,P,ADR)={re_.weights}")
    print("  強さ上位:")
    for s in re_.strengths[:6]:
        print(f"    {s.rank_composite}. {s.umaban:2d} {s.horse_name[:8]:8s} "
              f"comp={s.composite:+.2f} (rW{s.rank_w}/rP{s.rank_p}/rADR{s.rank_adr}) "
              f"p_win={s.win_prob:.3f} src={s.p_source}")
    print(f"  {'プラン':<16}{'点':>3}{'的中%':>7}{'合成OD':>8}{'期待R':>7}  vs単")
    for p in re_.plans:
        g = f"{p.synthetic_odds:.1f}" if p.synthetic_odds is not None else "--"
        ev = f"{p.expected_return:.2f}" if p.expected_return is not None else "--"
        flag = ""
        if p.vs_tansho == "lt":
            flag = "⚠合成<単"
        elif p.vs_tansho == "gt":
            flag = "↑広げ得"
        cov = "" if p.coverage >= 0.999 else f" (cov{p.coverage:.0%})"
        print(f"  {p.label:<16}{p.n_points:>3}{p.hit_prob*100:>6.1f}%"
              f"{g:>8}{ev:>7}  {flag}{cov}")
    for w in re_.warnings:
        print(f"  ⚠ {w}")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--race", help="単一レース (race_code 16桁) を stdout 表示")
    g.add_argument("--date", help="日付の全レース → JSON artifact (today 可)")
    p.add_argument("--axis", type=int, default=None, help="軸馬番を上書き (--race時)")
    p.add_argument("--weights", default=None, help="W,P,ADR 重み (例: 2,1,1)")
    p.add_argument("--n-partners", type=int, default=DEFAULT_N_PARTNERS)
    p.add_argument("--dry-run", action="store_true", help="JSON 書かず表示のみ")
    p.add_argument("--json", action="store_true", help="--race を JSON で stdout 出力")
    return p.parse_args()


def _parse_weights(s: Optional[str]) -> Tuple[float, float, float]:
    if not s:
        return DEFAULT_WEIGHTS
    parts = [float(x) for x in s.split(",")]
    if len(parts) != 3:
        raise ValueError("--weights は 'W,P,ADR' の3値")
    return (parts[0], parts[1], parts[2])


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                          errors="replace")
        except (AttributeError, ValueError):
            pass
    args = parse_args()
    weights = _parse_weights(args.weights)

    if args.race:
        # 単一レース: predictions から該当 race を探す
        date_guess = f"{args.race[:4]}-{args.race[4:6]}-{args.race[6:8]}"
        day_dir = date_dir_for(date_guess)
        predictions = load_predictions(day_dir)
        if predictions is None:
            print(f"predictions.json が見つからない ({date_guess})")
            return 1
        pred_race = next((r for r in predictions.get("races", [])
                          if str(r.get("race_id")) == args.race), None)
        if pred_race is None:
            print(f"race {args.race} が predictions に無い")
            return 1
        re_ = process_race(pred_race, axis=args.axis, weights=weights,
                           n_partners=args.n_partners)
        if re_ is None:
            print("評価不能 (entries 無し)")
            return 1
        if args.json:
            print(json.dumps(race_to_dict(re_), ensure_ascii=False, indent=2))
        else:
            _print_race(re_)
        return 0

    result = process_date(args.date, weights=weights, n_partners=args.n_partners,
                          dry_run=args.dry_run)
    print(f"\n[Done] {result.get('n_races', 0)} races")
    return 0


if __name__ == "__main__":
    sys.exit(main())
