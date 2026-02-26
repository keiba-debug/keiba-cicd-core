#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
買い目エンジン (bet_engine.py)

Python側で買い目推奨を一元生成するモジュール。
フロントエンド bet-logic.ts の戦略ロジックをPython側に統合し、
predict.py / experiment.py の両方から利用する。

設計原則:
  - Win-only戦略（Place ROI<100%のため単勝のみ）
  - VB判定の主軸: EV (期待値) = calibrated_pred_proba_wv × odds
  - 足切り: AR偏差値 (レース内相対評価)
  - Gapは参考情報として維持
  - 1レース1単勝制約（2番手は複勝に降格）
  - 2プリセット: standard (EV>=1.3) / wide (EV>=1.2)

VB判定フロー:
  Step 1: rank_wv <= 3 (WVモデルのtop3のみ)
  Step 2: ar_deviation >= threshold (レース内足切り)
  Step 3: EV_win >= threshold (期待値プラス判定)
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 能力R変換定数 (ability_score → rating)
# ability_score = -pred_margin_b (符号反転: 高い=強い)
# rating = RATING_BASE + ability_score * RATING_SCALE
RATING_SCALE = 14.7
RATING_BASE = 74.2

# グレードオフセット（Method A: 相対R→絶対R変換）
# offset = grade_mean_R - global_mean_R
# absolute_R = relative_R + offset
AGE_SEPARATED_GRADES = {'G1', 'G2', 'G3', 'OP', 'Listed'}


def load_grade_offsets(path: str = None) -> Dict[str, float]:
    """rating_standards.jsonからグレードオフセットマップを読み込み

    Returns:
        {grade_key: offset} — offset = grade_mean_R - global_mean_R
    """
    if path is None:
        path = 'C:/KEIBA-CICD/data3/analysis/rating_standards.json'
    p = Path(path)
    if not p.exists():
        return {}

    with open(p, encoding='utf-8') as f:
        data = json.load(f)

    global_mean = data.get('metadata', {}).get('global_mean_rating')
    if global_mean is None:
        return {}

    by_grade = data.get('by_grade', {})
    offsets = {}
    for key, info in by_grade.items():
        grade_mean = info.get('rating', {}).get('mean')
        if grade_mean is not None:
            offsets[key] = round(grade_mean - global_mean, 2)

    return offsets


def get_grade_key(grade: str, age_class: str) -> str:
    """grade + age_class → rating_standards.jsonのキー"""
    if not grade:
        return ''
    if grade in AGE_SEPARATED_GRADES and age_class:
        return f"{grade}_{age_class}"
    return grade


# =====================================================================
# データ構造
# =====================================================================

@dataclass
class BetStrategyParams:
    """戦略パラメータ"""
    # --- Win (Gap primary + EV secondary) ---
    # Gap = odds_rank - rank_v (Place model基準。Win modelよりPlace modelのGapが高ROI)
    win_min_gap: int = 5              # Place-model gap filter (primary, tiersがある場合はフォールバック)
    win_min_ev: float = 0.0           # Win EV supplementary filter (0=disabled)
    win_min_rating: float = 0.0       # AR絶対閾値 (0=無効、レガシー互換)
    win_min_ar_deviation: float = 0.0  # AR偏差値足切り (0=無効, 45=推奨, tiersがある場合は最低ティアが足切りになる)
    win_max_rank: int = 3             # rank_v (Place model) pre-filter (v_ratio_min>0なら無視)
    win_v_ratio_min: float = 0.0      # V%比率フィルター (0=無効→rank_v使用, 0.75=top1の75%以上)
    # --- ARd段階フィルター ---
    # (min_ard, min_gap) のリスト。ARd高い順に定義。
    # 例: [(65, 3), (55, 4), (45, 5)] → ARd>=65ならgap>=3, ARd>=55ならgap>=4, それ未満はgap>=5
    # 空リスト = 従来のフラット閾値 (win_min_gap + win_min_ar_deviation)
    win_ard_gap_tiers: List[Tuple[float, int]] = field(default_factory=list)

    # --- Place (EV + Kelly) ---
    place_min_gap: int = 3
    place_min_rating: float = 0.0     # AR絶対閾値 (0=無効)
    place_min_ar_deviation: float = 0.0  # AR偏差値足切り (0=無効)
    place_min_ev: float = 1.0
    kelly_fraction: float = 0.25      # 1/4 Kelly
    kelly_cap: float = 0.10           # max 10% of bankroll

    # --- 共通 ---
    danger_threshold: float = 5.0     # danger score threshold
    danger_gap_boost: int = 2         # gap mode: VB gap boost needed when danger detected

    # --- 単位 ---
    min_bet: int = 100
    bet_unit: int = 100


# --- プリセット ---
# Gap主軸 + EV補助: Place model (rank_v) のGapが最も収益性が高い
# v5.19のEV主軸はダブルキャリブレーションバグのアーティファクトだった
# AR偏差値足切り: レース内相対評価で格下を除外
# Place ROI<100%のためWin-only推奨
#
# v5.26: ARd段階フィルター導入
#   高ARd (>=65) → gap緩和 (>=3): 能力上位が過小評価なら即購入
#   中ARd (55-64) → gap中間 (>=4): 標準的な乖離要求
#   低ARd (45-54) → gap厳格 (>=5): 低能力評価には大きな乖離必須
#   ARd <45 → 不合格: 能力予測が低すぎる馬は除外
#
# バックテスト結果 (test 2025-2026, v5.11):
#   tiered:     ~1,744件, Place ROI ~124%, 利益 +41,935
#   wide(旧):   ~1,143件, Place ROI ~130%, 利益 +33,947
#
# v5.30: V%比率フィルター導入（rank_v順位ベース→V%比率ベース）
#   大混戦（top1-4がほぼ同率）で実力差のない馬を正しく拾う
#   V%比率 = 馬のV% / レース内最大V%。0.75=top1の75%以上
PRESETS: Dict[str, BetStrategyParams] = {
    'standard': BetStrategyParams(
        win_min_gap=5,              # フォールバック（ティアがカバーしない場合）
        win_min_ev=1.5,             # EV >= 1.5 supplementary filter
        win_v_ratio_min=0.75,       # V%比率 >= 75%（rank_vの代わり）
        win_ard_gap_tiers=[(65, 3), (55, 4), (45, 5)],
        place_min_gap=99,           # Place無効化
    ),
    'wide': BetStrategyParams(
        win_min_gap=5,              # フォールバック
        win_min_ev=0.0,             # EV filter disabled
        win_v_ratio_min=0.75,       # V%比率 >= 75%（rank_vの代わり）
        win_ard_gap_tiers=[(65, 3), (55, 4), (45, 5)],
        place_min_gap=99,           # Place無効化
    ),
    'aggressive': BetStrategyParams(
        win_min_gap=5,              # フォールバック
        win_min_ev=1.8,             # EV >= 1.8
        win_v_ratio_min=0.75,       # V%比率 >= 75%（rank_vの代わり）
        win_ard_gap_tiers=[(65, 3), (55, 4), (45, 5)],
        place_min_gap=99,           # Place無効化
    ),
}


@dataclass
class BetRecommendation:
    """1件の推奨買い目"""
    race_id: str
    umaban: int
    horse_name: str
    bet_type: str               # '単勝' | '複勝' | '単複'
    strength: str               # 'strong' | 'normal'
    win_amount: int = 0         # 単勝購入額 (100円単位)
    place_amount: int = 0       # 複勝購入額 (100円単位)
    # --- debug / display ---
    gap: int = 0                # VB gap (place-based)
    win_gap: int = 0            # Win VB gap
    predicted_margin: float = 0.0
    win_ev: Optional[float] = None
    place_ev: Optional[float] = None
    kelly_raw: float = 0.0
    kelly_capped: float = 0.0
    is_danger: bool = False
    danger_score: float = 0.0
    odds: float = 0.0
    place_odds_min: Optional[float] = None


# =====================================================================
# コア関数
# =====================================================================

def evaluate_win(
    gap: int,
    rating: Optional[float],
    params: BetStrategyParams,
    is_danger: bool = False,
    ar_deviation: Optional[float] = None,
    win_ev: Optional[float] = None,
) -> Tuple[bool, int]:
    """単勝評価 (Gap primary + EV secondary)

    ARd段階フィルターがある場合:
      ARd帯域ごとに異なるgap閾値を適用。高ARd=緩いgap、低ARd=厳しいgap。
      どのティアにも該当しなければ不合格。

    従来モード (tiers空):
      Step 1: AR偏差値足切り
      Step 2: Gap >= threshold
      Step 3: EV >= threshold

    Returns:
        (should_bet, units) — units はベット倍率
        1 unit = params.bet_unit (100円)
    """
    # === ARd段階フィルター ===
    if params.win_ard_gap_tiers:
        # ティアからgap閾値を決定（ARd高い順にチェック）
        min_gap = None
        for tier_ard, tier_gap in params.win_ard_gap_tiers:
            if ar_deviation is not None and ar_deviation >= tier_ard:
                min_gap = tier_gap
                break
        if min_gap is None:
            # どのティアにも該当しない（ARdが全ティア未満）→ 不合格
            return False, 0

        if is_danger:
            min_gap += params.danger_gap_boost

        if gap < min_gap:
            return False, 0
    else:
        # === 従来のフラット閾値 ===
        # AR偏差値足切り (0=無効)
        if params.win_min_ar_deviation > 0 and ar_deviation is not None:
            if ar_deviation < params.win_min_ar_deviation:
                return False, 0

        min_gap = params.win_min_gap
        if is_danger:
            min_gap += params.danger_gap_boost

        if gap < min_gap:
            return False, 0

    # AR絶対閾値 (後方互換、0=無効)
    if params.win_min_rating > 0 and rating is not None:
        if rating < params.win_min_rating:
            return False, 0

    # === EV filter (secondary, 0=disabled) ===
    if params.win_min_ev > 0:
        if win_ev is None or win_ev < params.win_min_ev:
            return False, 0

    # ベット倍率: gap が大きいほど厚く
    if gap >= min_gap + 3:
        units = 3
    elif gap >= min_gap + 1:
        units = 2
    else:
        units = 1

    return True, units


def evaluate_place(
    gap: int,
    rating: Optional[float],
    p_top3: Optional[float],
    place_odds: Optional[float],
    params: BetStrategyParams,
    is_danger: bool = False,
    ar_deviation: Optional[float] = None,
) -> Tuple[bool, float]:
    """複勝評価 (gap + AR偏差値足切り + EV + Kelly)

    Returns:
        (should_bet, kelly_fraction) — kelly_fraction は 0~kelly_cap の範囲
    """
    min_gap = params.place_min_gap
    if is_danger:
        min_gap += params.danger_gap_boost

    if gap < min_gap:
        return False, 0.0

    # AR偏差値足切り (0=無効)
    if params.place_min_ar_deviation > 0 and ar_deviation is not None:
        if ar_deviation < params.place_min_ar_deviation:
            return False, 0.0

    # AR絶対閾値 (後方互換、0=無効)
    if params.place_min_rating > 0 and rating is not None:
        if rating < params.place_min_rating:
            return False, 0.0

    # EV フィルタ (確率・オッズがある場合)
    if p_top3 is not None and place_odds is not None and place_odds > 0:
        ev = p_top3 * place_odds
        if ev < params.place_min_ev:
            return False, 0.0

        # Kelly sizing
        kelly = calc_kelly_fraction(p_top3, place_odds)
        kelly_sized = kelly * params.kelly_fraction  # fractional Kelly
        kelly_sized = min(kelly_sized, params.kelly_cap)

        if kelly_sized <= 0:
            return False, 0.0

        return True, kelly_sized
    else:
        # EV計算不能（オッズ不明）→ gap だけで判定、固定サイズ
        return True, 0.02  # 2% of bankroll as fallback


def calc_kelly_fraction(prob: float, odds: float) -> float:
    """Kelly Criterion: f* = (b*p - q) / b

    Args:
        prob: P(top3) — calibrated確率 (raw, sum≈3.0)
        odds: 複勝最低オッズ

    Returns:
        Kelly fraction (0 if negative = don't bet)
    """
    b = odds - 1.0
    if b <= 0 or prob <= 0:
        return 0.0
    q = 1.0 - prob
    f = (b * prob - q) / b
    return max(0.0, f)


def detect_danger(
    entries: List[dict],
    max_odds: float = 8.0,
    max_ard: float = 50.0,
    max_pred_v: float = 0.15,
) -> Dict[int, bool]:
    """危険馬検出: odds <= max_odds & ARd < max_ard & V% < max_pred_v

    バックテスト実績: 勝率 8.7%, 複勝率 27.9% (ベースライン 21.0%, 51.4%)

    Args:
        entries: predict_race() の出力 entries リスト
        max_odds: オッズ上限 (この値以下が対象)
        max_ard: AR偏差値上限 (この値未満が対象)
        max_pred_v: V%上限 (この値未満が対象, calibrated)

    Returns:
        {umaban: True} — 危険馬と判定された馬のみ
    """
    danger = {}
    for e in entries:
        odds = e.get('odds', 0) or 0
        ard = e.get('ar_deviation') or 0
        pred_v = e.get('pred_proba_v', 0) or 0
        if 0 < odds <= max_odds and ard < max_ard and pred_v < max_pred_v:
            danger[e['umaban']] = True
    return danger


# =====================================================================
# パイプライン
# =====================================================================

def generate_recommendations(
    race_predictions: List[dict],
    params: BetStrategyParams,
    budget: int = 30000,
) -> List[BetRecommendation]:
    """全レースの推奨買い目を生成

    Args:
        race_predictions: predict_race() の出力リスト
            各レースに必要なフィールド:
              - race_id, track_type, entries[]
              - entries[]: umaban, horse_name, odds, vb_gap, win_vb_gap,
                           rank_v, odds_rank, place_odds_min, place_ev, win_ev,
                           predicted_margin (能力R rating, optional),
                           pred_proba_v_raw (optional, for Kelly),
                           comment_memo_trouble_score (optional)
        params: 戦略パラメータ
        budget: 総予算 (円)

    Returns:
        BetRecommendation のリスト（budget スケーリング済み）
    """
    all_recs: List[BetRecommendation] = []

    for race in race_predictions:
        race_id = race['race_id']
        entries = race.get('entries', [])

        if not entries:
            continue

        # 危険馬検出 (odds<=8 & ARd<50 & V%<15%)
        danger_map = detect_danger(entries)

        # V%比率フィルター用: レース内最大V%を計算
        if params.win_v_ratio_min > 0:
            v_pcts = [(e.get('pred_proba_v_raw') or 0) for e in entries]
            race_max_v = max(v_pcts) if v_pcts else 0
        else:
            race_max_v = 0

        race_recs: List[BetRecommendation] = []

        for e in entries:
            umaban = e['umaban']
            horse_name = e.get('horse_name', '')
            odds = e.get('odds', 0) or 0
            gap = e.get('vb_gap', 0) or 0
            win_gap = e.get('win_vb_gap', 0) or 0
            rank_v = e.get('rank_v', 99)
            rank_wv = e.get('rank_wv') or 99
            odds_rank = e.get('odds_rank', 0) or 0
            margin = e.get('predicted_margin')
            ar_dev = e.get('ar_deviation')
            p_top3_raw = e.get('pred_proba_v_raw')
            place_odds = e.get('place_odds_min')
            win_ev = e.get('win_ev')
            place_ev = e.get('place_ev')

            is_danger = umaban in danger_map
            danger_score = 1.0 if is_danger else 0.0

            # --- 単勝評価 ---
            # Pre-filter: V%比率 or rank_v
            #   V%比率: レース内top1のV%に対する比率で足切り（大混戦に対応）
            #   rank_v: 従来の順位ベース足切り（V%比率が0の場合のフォールバック）
            if params.win_v_ratio_min > 0:
                v_pct = p_top3_raw or 0
                v_ratio = v_pct / race_max_v if race_max_v > 0 else 0
                win_prefilter_pass = v_ratio >= params.win_v_ratio_min
            else:
                win_prefilter_pass = rank_v <= params.win_max_rank

            if not win_prefilter_pass:
                win_ok, win_units = False, 0
            else:
                # Gap = vb_gap (Place model基準: odds_rank - rank_v)
                win_ok, win_units = evaluate_win(
                    gap, margin, params, is_danger,
                    ar_deviation=ar_dev, win_ev=win_ev,
                )

            # --- 複勝評価 ---
            # Pre-filter: V%比率 or rank_v top3
            if params.win_v_ratio_min > 0:
                place_prefilter_pass = win_prefilter_pass  # 単勝と同じ基準
            else:
                place_prefilter_pass = rank_v <= 3
            if not place_prefilter_pass:
                place_ok, kelly_frac = False, 0.0
            else:
                place_ok, kelly_frac = evaluate_place(
                    gap, margin, p_top3_raw, place_odds, params, is_danger, ar_deviation=ar_dev,
                )

            if not win_ok and not place_ok:
                continue

            # bet_type 決定 (Gap基準でstrength判定)
            if win_ok and place_ok:
                bet_type = '単複'
                strength = 'strong' if (gap >= params.win_min_gap + 2 or
                                        gap >= params.place_min_gap + 2) else 'normal'
            elif win_ok:
                bet_type = '単勝'
                strength = 'strong' if gap >= params.win_min_gap + 2 else 'normal'
            else:
                bet_type = '複勝'
                strength = 'strong' if gap >= params.place_min_gap + 2 else 'normal'

            rec = BetRecommendation(
                race_id=race_id,
                umaban=umaban,
                horse_name=horse_name,
                bet_type=bet_type,
                strength=strength,
                win_amount=win_units * params.bet_unit if win_ok else 0,
                place_amount=0,  # Kelly sizing in apply_budget
                gap=gap,
                win_gap=win_gap,
                predicted_margin=round(margin, 1) if margin is not None else 0.0,
                win_ev=round(win_ev, 4) if win_ev is not None else None,
                place_ev=round(place_ev, 4) if place_ev is not None else None,
                kelly_raw=round(kelly_frac / params.kelly_fraction, 4) if kelly_frac > 0 and params.kelly_fraction > 0 else 0.0,
                kelly_capped=round(kelly_frac, 4),
                is_danger=is_danger,
                danger_score=danger_score,
                odds=odds,
                place_odds_min=place_odds,
            )
            race_recs.append(rec)

        # 1レース1単勝制約
        race_recs = apply_single_win_constraint(race_recs)
        all_recs.extend(race_recs)

    # 予算スケーリング
    all_recs = apply_budget(all_recs, budget, params)

    return all_recs


def apply_single_win_constraint(
    recs: List[BetRecommendation],
) -> List[BetRecommendation]:
    """1レース1単勝制約: 2番目以降の単勝を複勝に降格

    優先順位: gap (Place-model based) の大きい馬が単勝を取る
    """
    # 単勝候補を抽出 (単勝 or 単複)
    win_candidates = [r for r in recs if r.bet_type in ('単勝', '単複')]

    if len(win_candidates) <= 1:
        return recs

    # gap 降順ソート (Place model基準)
    win_candidates.sort(key=lambda r: (-r.gap, -r.odds))

    # 1番目はそのまま、2番目以降を降格
    winner = win_candidates[0]
    for r in win_candidates[1:]:
        if r.bet_type == '単勝':
            # 単勝 → 複勝に降格 (kelly_capped > 0 なら)
            if r.kelly_capped > 0:
                r.bet_type = '複勝'
                r.win_amount = 0
            else:
                # Kelly も 0 → 推奨取り消し
                recs.remove(r)
        elif r.bet_type == '単複':
            # 単複 → 複勝に降格
            r.bet_type = '複勝'
            r.win_amount = 0

    return recs


def apply_budget(
    recs: List[BetRecommendation],
    budget: int,
    params: BetStrategyParams,
) -> List[BetRecommendation]:
    """Kelly fraction → 実金額に変換し、予算内にスケーリング

    Steps:
    1. Place: kelly_capped × budget → 100円単位に丸め
    2. Win: units × bet_unit (既にセット済み)
    3. 合計 > budget なら按分縮小
    """
    if not recs:
        return recs

    # Step 1: Place金額を仮計算
    for r in recs:
        if r.bet_type in ('複勝', '単複') and r.kelly_capped > 0:
            raw_amount = r.kelly_capped * budget
            rounded = max(params.min_bet,
                          round_to_unit(raw_amount, params.bet_unit))
            r.place_amount = rounded
        elif r.bet_type == '複勝' and r.kelly_capped <= 0:
            # gap だけで通ったがKelly不可 → 最小ベット
            r.place_amount = params.min_bet

    # Step 2: 合計チェック
    total = sum(r.win_amount + r.place_amount for r in recs)

    if total > budget and total > 0:
        # 按分縮小
        scale = budget / total
        for r in recs:
            if r.win_amount > 0:
                r.win_amount = max(params.min_bet,
                                   round_to_unit(r.win_amount * scale, params.bet_unit))
            if r.place_amount > 0:
                r.place_amount = max(params.min_bet,
                                     round_to_unit(r.place_amount * scale, params.bet_unit))

    return recs


def round_to_unit(amount: float, unit: int = 100) -> int:
    """金額を unit 単位に丸める (切り捨て)"""
    return int(amount // unit) * unit


# =====================================================================
# 出力ヘルパー
# =====================================================================

def recommendations_to_dict(recs: List[BetRecommendation]) -> List[dict]:
    """BetRecommendation リストを JSON シリアライズ用 dict に変換"""
    return [asdict(r) for r in recs]


def recommendations_summary(recs: List[BetRecommendation]) -> dict:
    """推奨一覧のサマリー統計"""
    if not recs:
        return {
            'total_bets': 0,
            'total_amount': 0,
            'win_bets': 0,
            'place_bets': 0,
            'win_amount': 0,
            'place_amount': 0,
            'strong_count': 0,
            'danger_count': 0,
        }

    win_bets = [r for r in recs if r.bet_type in ('単勝', '単複')]
    place_bets = [r for r in recs if r.bet_type in ('複勝', '単複')]

    return {
        'total_bets': len(recs),
        'total_amount': sum(r.win_amount + r.place_amount for r in recs),
        'win_bets': len(win_bets),
        'place_bets': len(place_bets),
        'win_amount': sum(r.win_amount for r in recs),
        'place_amount': sum(r.place_amount for r in recs),
        'strong_count': sum(1 for r in recs if r.strength == 'strong'),
        'danger_count': sum(1 for r in recs if r.is_danger),
    }


# =====================================================================
# バックテスト用ユーティリティ
# =====================================================================

def df_to_race_predictions(df_test, grade_offsets: Dict[str, float] = None) -> List[dict]:
    """DataFrame → generate_recommendations() 入力形式に変換

    experiment.py / backtest_bet_engine.py の両方から利用。
    df_test には pred_rank_v, odds_rank, pred_margin_b 等が必要。

    Args:
        grade_offsets: Method A グレードオフセット {grade_key: offset}
            Noneの場合はオフセットなし（従来の相対R）
    """
    import pandas as pd

    races = []
    for race_id, group in df_test.groupby('race_id'):
        # グレードオフセット（Method A）
        offset = 0.0
        grade = ''
        age_class = ''
        if grade_offsets:
            row0 = group.iloc[0]
            grade = str(row0.get('grade', ''))
            age_class = str(row0.get('age_class', ''))
            grade_key = get_grade_key(grade, age_class)
            offset = grade_offsets.get(grade_key, 0.0)

        entries = []
        for _, row in group.iterrows():
            relative_rating = RATING_BASE - float(row['pred_margin_b']) * RATING_SCALE if pd.notna(row.get('pred_margin_b')) else None
            absolute_rating = (relative_rating + offset) if relative_rating is not None else None

            entries.append({
                'umaban': int(row['umaban']),
                'horse_name': str(row.get('horse_name', '')),
                'odds': float(row.get('odds', 0)),
                'vb_gap': int(row.get('vb_gap', 0)),
                'win_vb_gap': int(row.get('win_vb_gap', 0)),
                'rank_v': int(row.get('pred_rank_v', 99)),
                'rank_wv': int(row.get('pred_rank_wv', 99)) if pd.notna(row.get('pred_rank_wv')) else 99,
                'odds_rank': int(row.get('odds_rank', 0)),
                'place_odds_min': float(row['place_odds_low']) if pd.notna(row.get('place_odds_low')) else None,
                'pred_proba_v_raw': float(row.get('pred_proba_v_raw', 0)),
                'predicted_margin': absolute_rating,
                'win_ev': float(row.get('win_ev', 0)) if pd.notna(row.get('win_ev')) else None,
                'place_ev': float(row.get('place_ev', 0)) if pd.notna(row.get('place_ev')) else None,
                'comment_memo_trouble_score': float(row.get('comment_memo_trouble', 0)),
                # 結果情報（ROI計算用）
                'finish_position': int(row.get('finish_position', 0)),
                'is_win': int(row.get('is_win', 0)),
                'is_top3': int(row.get('is_top3', 0)),
            })
        # AR偏差値を計算（レース内相対評価、mean=50, std=10）
        ar_scores = [e['predicted_margin'] for e in entries if e['predicted_margin'] is not None]
        if len(ar_scores) >= 2:
            import numpy as np
            ar_mean = np.mean(ar_scores)
            ar_std = max(np.std(ar_scores), 3.0)  # 少頭数のstd不安定対策
            for e in entries:
                if e['predicted_margin'] is not None:
                    e['ar_deviation'] = round(50 + 10 * (e['predicted_margin'] - ar_mean) / ar_std, 1)
                else:
                    e['ar_deviation'] = None
        else:
            for e in entries:
                e['ar_deviation'] = 50.0

        races.append({
            'race_id': str(race_id),
            'track_type': str(row.get('track_type_name', '')),
            'grade': grade,
            'age_class': age_class,
            'grade_offset': offset,
            'entries': entries,
        })
    return races


def calc_bet_engine_roi(recs: List[BetRecommendation], race_predictions: List[dict]) -> dict:
    """推奨買い目の実ROI計算

    Args:
        recs: generate_recommendations() の出力
        race_predictions: df_to_race_predictions() の出力（結果付き）

    Returns:
        dict: ROI統計
    """
    entry_lookup = {}
    for race in race_predictions:
        for e in race['entries']:
            entry_lookup[(race['race_id'], e['umaban'])] = e

    total_win_bet = 0
    total_place_bet = 0
    total_win_return = 0
    total_place_return = 0
    win_hits = 0
    place_hits = 0

    for r in recs:
        entry = entry_lookup.get((r.race_id, r.umaban))
        if entry is None:
            continue

        if r.win_amount > 0:
            total_win_bet += r.win_amount
            if entry['is_win']:
                total_win_return += entry['odds'] * r.win_amount
                win_hits += 1

        if r.place_amount > 0:
            total_place_bet += r.place_amount
            if entry['is_top3']:
                place_odds = entry.get('place_odds_min')
                if place_odds and place_odds > 0:
                    total_place_return += place_odds * r.place_amount
                else:
                    total_place_return += max(entry['odds'] / 3.5, 1.1) * r.place_amount
                place_hits += 1

    total_bet = total_win_bet + total_place_bet
    total_return = total_win_return + total_place_return

    return {
        'total_bet': total_bet,
        'total_return': round(total_return),
        'total_roi': round(total_return / total_bet * 100, 1) if total_bet > 0 else 0,
        'win_bet': total_win_bet,
        'win_return': round(total_win_return),
        'win_roi': round(total_win_return / total_win_bet * 100, 1) if total_win_bet > 0 else 0,
        'win_hits': win_hits,
        'place_bet': total_place_bet,
        'place_return': round(total_place_return),
        'place_roi': round(total_place_return / total_place_bet * 100, 1) if total_place_bet > 0 else 0,
        'place_hits': place_hits,
        'num_bets': len(recs),
    }


def rescale_budget(recs: List[dict], new_budget: int, unit: int = 100) -> List[dict]:
    """フロントエンドから呼ぶ予算リスケール

    predict.py が出力した recommendations (dict list) を受け取り、
    new_budget に合わせて win_amount / place_amount を按分リスケール。
    """
    if not recs:
        return recs

    total = sum(r.get('win_amount', 0) + r.get('place_amount', 0) for r in recs)
    if total <= 0:
        return recs

    scale = new_budget / total
    result = []
    for r in recs:
        r2 = dict(r)
        wa = r2.get('win_amount', 0)
        pa = r2.get('place_amount', 0)
        if wa > 0:
            r2['win_amount'] = max(unit, int(wa * scale // unit) * unit)
        if pa > 0:
            r2['place_amount'] = max(unit, int(pa * scale // unit) * unit)
        result.append(r2)
    return result
