#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
買い目エンジン (bet_engine.py)

Python側で買い目推奨を一元生成するモジュール。
フロントエンド bet-logic.ts の戦略ロジックをPython側に統合し、
predict.py / experiment.py の両方から利用する。

設計原則:
  - Win-only戦略（Place ROI<100%のため単勝のみ）
  - VB判定の主軸: EV (期待値) = calibrated_pred_proba_w × odds
  - 足切り: AR偏差値 (レース内相対評価)
  - Gapは参考情報として維持
  - 1レース最大2単勝（2番手候補の的中率>全体平均のため緩和）
  - 3プリセット: standard (EV>=1.5) / wide (EVなし) / aggressive (EV>=1.8)

VB判定フロー:
  Step 1: P%比率 >= 0.75 or Gap+EVバイパス (P%ベースのpre-filter)
  Step 2: ARd段階gap (ARd帯別に異なるgap閾値)
  Step 3: EV_win >= threshold (期待値プラス判定)
  Step 4: 1レースmax 2単勝 (gap降順で上位2頭)
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 能力R変換定数 (ability_score → rating)
# ability_score = -pred_margin_ar (符号反転: 高い=強い)
# rating = RATING_BASE + ability_score * RATING_SCALE
RATING_SCALE = 14.7
RATING_BASE = 74.2

# グレードオフセット（Method A: 相対R→絶対R変換）
# offset = grade_mean_R - global_mean_R
# absolute_R = relative_R + offset
AGE_SEPARATED_GRADES = {'G1', 'G2', 'G3', 'OP', 'Listed'}

# VB Floor: 購入プラン⊆VB候補 を保証する最低条件
# predict.py の is_value_bet 判定と同一基準。
# bet-engine.ts の VB_FLOOR 定数と手動同期が必要。
VB_FLOOR_MIN_WIN_EV = 1.0       # 単勝EV下限
VB_FLOOR_MIN_ARD = 50.0          # AR偏差値下限
VB_FLOOR_ARD_VB_MIN_ARD = 65.0   # ARd VBルート: ARd下限
VB_FLOOR_ARD_VB_MIN_ODDS = 10.0  # ARd VBルート: オッズ下限
VB_FLOOR_MIN_DEV_GAP = 0.7       # 偏差値gapルート: dev_gap下限
VB_FLOOR_DEV_MIN_ARD = 45.0      # 偏差値gapルート: ARd下限


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
    # Gap = odds_rank - rank_p (Place model基準。Win modelよりPlace modelのGapが高ROI)
    win_min_gap: int = 5              # Place-model gap filter (primary, tiersがある場合はフォールバック)
    win_min_ev: float = 0.0           # Win EV supplementary filter (0=disabled)
    win_min_rating: float = 0.0       # AR絶対閾値 (0=無効、レガシー互換)
    win_min_ar_deviation: float = 0.0  # AR偏差値足切り (0=無効, 45=推奨, tiersがある場合は最低ティアが足切りになる)
    win_max_rank: int = 3             # rank_p (Place model) pre-filter (v_ratio_min>0なら無視)
    win_v_ratio_min: float = 0.0      # P%比率フィルター (0=無効→rank_p使用, 0.75=top1の75%以上)
    # P%比率バイパス: P%比率が閾値未満でも、Gap+EVが十分高ければ通過させる
    # 「モデル評価は低いが市場がさらに低評価→超穴馬」を拾うルート
    win_v_bypass_gap: int = 0         # バイパス用Gap下限 (0=無効, 7=推奨)
    win_v_bypass_ev: float = 0.0      # バイパス用EV下限 (0=無効, 3.0=推奨)
    # --- ARd段階フィルター (rank gap用, レガシー互換) ---
    # (min_ard, min_gap) のリスト。ARd高い順に定義。
    # 例: [(65, 3), (55, 4), (45, 5)] → ARd>=65ならgap>=3, ARd>=55ならgap>=4, それ未満はgap>=5
    # 空リスト = 従来のフラット閾値 (win_min_gap + win_min_ar_deviation)
    win_ard_gap_tiers: List[Tuple[float, int]] = field(default_factory=list)

    # --- dev_gap (偏差値gap) フィルター ---
    # メイン選定基準: z-score(model_pred) - z-score(1/odds)
    # 的中率重視: dev_gapが大きい = モデルが市場より本当に高く評価している
    # (min_ard, min_dev_gap) のリスト。ARd高い順に定義。
    win_ard_dev_tiers: List[Tuple[float, float]] = field(default_factory=list)

    # --- Composite VB Score ---
    # 4シグナル(dev_gap/rank_gap/EV/ARd)を段階的にスコア化し、
    # 合計で選定・強弱を統合判定する。
    # 単一シグナルだけでは高スコアにならず、複数シグナルの合致が必要。
    # 0 = 無効（レガシーtierベースを使用）
    win_min_vb_score: float = 0.0    # 選定閾値 (0=無効, 5.0=推奨)
    vb_strong_score: float = 7.0     # strong分類閾値

    # --- ARd VBルート (能力 vs 市場の直接乖離) ---
    # Gapフィルターを経ない独立ルート。分類モデル(P%)が低評価でも
    # 回帰モデル(AR)が高評価 & 市場が過小評価の馬を拾う。
    # バックテスト: ARd>=65 & odds>=10 → 80件, 勝率11.2%, WinROI 179.9%
    ard_vb_min_ard: float = 0.0      # ARd下限 (0=無効, 65.0=推奨)
    ard_vb_min_odds: float = 0.0     # オッズ下限 (0=無効, 10.0=推奨)

    # --- Place (EV + Kelly) ---
    place_min_gap: int = 3
    place_min_rating: float = 0.0     # AR絶対閾値 (0=無効)
    place_min_ar_deviation: float = 0.0  # AR偏差値足切り (0=無効)
    place_min_ev: float = 1.0
    kelly_fraction: float = 0.25      # 1/4 Kelly
    kelly_cap: float = 0.10           # max 10% of bankroll

    # --- 共通 ---
    danger_threshold: float = 5.0     # danger score threshold
    danger_gap_boost: int = 0         # v5.33: gap boost廃止 (ラベルのみ、ROI希薄化防止)

    # --- Place上乗せ (単勝ベース + 条件付き複勝追加) ---
    # v6.2: 単勝は必ず100円購入。PlaceEV+ARdの条件を満たす馬に複勝を追加。
    # バックテスト: G1戦略(PEV>=1.3&ARd>=50→複200) gap>=3で ROI 115.8% (+8.1pt vs Win100%)
    #   低~中オッズ(5-20倍)は複勝が有利、高オッズ(50倍+)は単勝が有利
    #   PlaceEV>=1.3が複勝プラスの分水嶺（ROI 103-132%）
    #   複勝で2-3着の15.3%を回収 → 長期バンクロール安定化
    place_addon: bool = False               # Place上乗せ有効化
    place_addon_min_pev: float = 1.3        # 最低PlaceEV (複勝期待値)
    place_addon_min_ard: float = 50.0       # 最低ARd (能力確認)
    place_addon_amount: int = 200           # 複勝追加額 (円)

    # --- クロス配分 (strength別の単複配分) ---
    # v5.35: バンクロールSim検証でWinOnly(100/100)が最適と判明
    # → v6.2: place_addonに置き換え（cross_allocは互換性のため残存）
    cross_alloc: bool = False           # WinOnly: 全額単勝
    strong_win_pct: int = 100           # strong: 全額単勝
    normal_win_pct: int = 100           # normal: 全額単勝

    # --- 1レース複数単勝 ---
    # 0=制限なし, 1=従来(1レース1単勝), 2=最大2頭(推奨)
    # バックテスト: max=2がROI最良。2番手候補の的中率>全体平均。
    max_win_per_race: int = 2

    # --- Closing Race Boost (差し決着予測レースでのVBスコア加算) ---
    # closing_race_proba >= closing_boost_threshold のレースで
    # closing_strength >= closing_boost_min_strength の差し馬に VB スコアを加算。
    # 差し決着が予想されるレースで差し脚質の馬を優遇する。
    closing_boost_threshold: float = 0.0   # 0=無効, 0.13=推奨
    closing_boost_min_strength: float = 1.0  # closing_strength最低値
    closing_boost_score: float = 1.0       # 加算するVBスコア

    # --- Slow Start Risk Boost (出遅れリスクによるVBスコア減算) ---
    # 出遅れ常習馬にマイナスブースト。逃げ馬は出遅れでレースプラン崩壊するため倍率適用。
    # horse_slow_start_rate >= slow_start_min_rate の馬に penalty を適用。
    # 逃げ馬判定: last_race_corner1_ratio <= slow_start_front_runner_threshold
    slow_start_penalty: float = 0.0             # 0=無効, -0.5~-1.0推奨
    slow_start_min_rate: float = 0.20            # 出遅れ率20%以上で発動
    slow_start_front_runner_multiplier: float = 2.0  # 逃げ馬はpenalty倍
    slow_start_front_runner_threshold: float = 0.25  # corner1/num_runners <= これなら逃げ馬

    # --- シンプル戦略用 (rank_w + win_gap フィルタ) ---
    # rank_w制限: 0=無効, 1=rank_w=1のみ (Winモデル1位のみ購入)
    win_max_rank_w: int = 0
    # win_vb_gap制限: 0=無効, 4=推奨 (odds_rank - rank_w >= N)
    win_min_win_gap: int = 0

    # --- 単位 ---
    min_bet: int = 100
    bet_unit: int = 100


# --- プリセット ---
# Gap主軸 + EV補助: Place model (rank_p) のGapが最も収益性が高い
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
# v5.30: P%比率フィルター導入（rank_p順位ベース→P%比率ベース）
#   大混戦（top1-4がほぼ同率）で実力差のない馬を正しく拾う
#   P%比率 = 馬のP% / レース内最大P%。0.75=top1の75%以上
#
# v5.30b: P%比率バイパスルート追加
#   P%比率<0.75でも Gap>=7 + EV>=3.0 なら通過（超穴馬救済）
#   バイパス単体: 58件 Win ROI 460.5%、ベースライン合算で ROI 109.7%→134.9%
#
# v5.31: tier相対strength判定 + クロス配分
#   strong = gap >= tier_gap + 2 (ARd帯別、固定gap>=7から変更)
#   ARd>=65: gap>=5, ARd>=55: gap>=6, ARd<55: gap>=7 (=現行と同じ)
#   昇格92件(N→S): 勝率8.7%, 単ROI 184.6% → クロス配分ROI +2pt改善
#   クロス配分: strong→単7:複3, normal→単3:複7 (購入金額を自動分割)
#
# v5.32: 1レース複数単勝 (max=2)
#   従来の1レース1単勝制約を緩和。2番手候補もVBとして有効。
#   バックテスト: aggressive ROI 249%→406%, wide ROI 124%→138%
#   2番手候補の的中率: 14.3% (全体5.3%) — 2番手は強い馬が多い
#   max=2が最適: 3頭目以降は勝ちなしでROI希薄化
#
# v5.34: ARd VBルート (能力 vs 市場の直接乖離)
#   Gap VBが確率ランク(rank_p) vs 市場ランクの乖離を見るのに対し、
#   ARd VBは能力(ARd) vs 市場オッズの直接乖離を見る独立ルート。
#   分類モデルが低評価(rank_p低い)でも回帰モデルが高評価(ARd高い)の馬を拾う。
#   バックテスト: ARd>=65 & odds>=10 → 80件, 勝率11.2%, WinROI 179.9%
#   現行漏れ馬(ARd>=65, Gap<=2, odds>=10): 23件, 勝率17.4%, WinROI 210%
# v5.44: Composite VB Score方式
# 4シグナル(dev_gap/rank_gap/EV/ARd)を段階的にスコア化し合計で選定。
# 単一シグナルだけでは通過できず、複数シグナルの合致が必要。
# EV>=1.0をハードフロアとして全プリセット共通で適用。
#
# バックテスト結果 (test 2025-2026, v5.12-pit3):
#   wide:       438件, WinROI 103.2%, P&L +1,390  (Score>=5.0 + EV>=1.0)
#   standard:   398件, WinROI 113.5%, P&L +5,390  (Score>=5.5 + EV>=1.0)
#   aggressive: 344件, WinROI 117.7%, P&L +6,080  (Score>=6.0 + EV>=1.0)
#
# 旧システム比較 (dev_gap/rank_gap ORルート):
#   旧aggressive(EV>=1.8): 166件, ROI 106.4% → 新: 344件, 117.7% (+11pt, 2倍のベット)
#   旧wide(EVなし):        3,753件, ROI 90.2% → 新: 438件, 103.2% (ベット数1/8で黒字化)
PRESETS: Dict[str, BetStrategyParams] = {
    'standard': BetStrategyParams(
        win_min_vb_score=5.5,       # Composite score >= 5.5
        win_min_ev=1.0,             # EV >= 1.0 hard floor
        win_v_ratio_min=0.75,       # P%比率 >= 75%
        win_v_bypass_gap=7,         # バイパス: Gap>=7
        win_v_bypass_ev=3.0,        # バイパス: EV>=3.0
        ard_vb_min_ard=65.0,        # ARd VBルート: ARd>=65
        ard_vb_min_odds=10.0,       # ARd VBルート: odds>=10
        place_min_gap=99,           # Place単独評価は無効
        place_addon=True,           # Place上乗せ: 単勝+条件付き複勝
        place_addon_min_pev=1.3,    # PlaceEV >= 1.3
        place_addon_min_ard=50.0,   # ARd >= 50
        place_addon_amount=200,     # 複勝200円追加
        cross_alloc=False,
        strong_win_pct=100,
        normal_win_pct=100,
        max_win_per_race=2,
        closing_boost_threshold=0.13,   # 差し決着予測 >= 13%でブースト
        closing_boost_min_strength=1.0, # closing_strength >= 1.0
        closing_boost_score=1.0,        # VBスコア +1.0
        # slow_start: バックテストで逆効果(除外馬の的中率8.4%>平均5%)のため無効化
        # インフラは残置、将来チューニング余地あり
    ),
    'wide': BetStrategyParams(
        win_min_vb_score=5.0,       # Composite score >= 5.0 (wider net)
        win_min_ev=1.0,             # EV >= 1.0 hard floor
        win_v_ratio_min=0.75,
        win_v_bypass_gap=7,
        win_v_bypass_ev=3.0,
        ard_vb_min_ard=65.0,
        ard_vb_min_odds=10.0,
        place_min_gap=99,           # Place単独評価は無効
        place_addon=True,           # Place上乗せ: 単勝+条件付き複勝
        place_addon_min_pev=1.3,    # PlaceEV >= 1.3
        place_addon_min_ard=50.0,   # ARd >= 50
        place_addon_amount=200,     # 複勝200円追加
        cross_alloc=False,
        strong_win_pct=100,
        normal_win_pct=100,
        max_win_per_race=2,
        closing_boost_threshold=0.13,
        closing_boost_min_strength=1.0,
        closing_boost_score=1.0,
        # slow_start: 無効化 (逆効果)
    ),
    'aggressive': BetStrategyParams(
        win_min_vb_score=6.0,       # Composite score >= 6.0 (high conviction)
        win_min_ev=1.0,             # EV >= 1.0 hard floor
        win_v_ratio_min=0.75,
        win_v_bypass_gap=7,
        win_v_bypass_ev=3.0,
        ard_vb_min_ard=65.0,
        ard_vb_min_odds=10.0,
        place_min_gap=99,           # Place単独評価は無効
        place_addon=True,           # Place上乗せ: 単勝+条件付き複勝
        place_addon_min_pev=1.3,    # PlaceEV >= 1.3
        place_addon_min_ard=50.0,   # ARd >= 50
        place_addon_amount=200,     # 複勝200円追加
        cross_alloc=False,
        strong_win_pct=100,
        normal_win_pct=100,
        max_win_per_race=2,
        closing_boost_threshold=0.13,
        closing_boost_min_strength=1.0,
        closing_boost_score=1.0,
        # slow_start: 無効化 (逆効果)
    ),
    # --- シンプル戦略 ---
    # rank_w=1（Winモデル1位）の単勝のみ。複雑なVBスコアを使わず、
    # win_vb_gap（市場ランクとの乖離）でフィルタする超シンプル戦略。
    # バックテスト結果 (v7.3, 2025-03~2026-02):
    #   simple:     139件, WinROI 143.7%, P&L +6,078 (rank_w=1, gap>=4)
    #   simple_ev2: 108件, WinROI 148.9%, P&L +5,277 (rank_w=1, EV>=2.0)
    #   simple_wide: 288件, WinROI 115.2%, P&L +4,387 (rank_w=1, gap>=3)
    'simple': BetStrategyParams(
        # rank_w=1 + win_gap>=4: モデル1位で市場5番人気以下 → 超バリュー
        win_max_rank_w=1,           # rank_w=1のみ
        win_min_win_gap=4,          # win_vb_gap>=4
        win_min_vb_score=0,         # Composite Score無効
        win_v_ratio_min=0,          # P%比率フィルタ無効
        win_max_rank=99,            # rank_pフィルタ無効
        win_min_gap=0,              # place gapフィルタ無効
        win_min_ev=0,               # evaluate_win内EV無効 (VB Floorで担保)
        ard_vb_min_ard=0,           # ARd VBルート無効
        ard_vb_min_odds=0,
        place_addon=False,          # 複勝なし: 単勝一本
        place_min_gap=99,           # 複勝単独無効
        max_win_per_race=1,         # 1レース1買い
        closing_boost_threshold=0,  # Closing boost無効
    ),
    'simple_ev2': BetStrategyParams(
        # rank_w=1 + EV>=2.0: モデル1位でEVが極端に高い → 最高ROI
        win_max_rank_w=1,
        win_min_win_gap=0,          # gap不問
        win_min_vb_score=0,
        win_v_ratio_min=0,
        win_max_rank=99,
        win_min_gap=0,
        win_min_ev=2.0,             # EV>=2.0 (evaluate_win内で適用)
        ard_vb_min_ard=0,
        ard_vb_min_odds=0,
        place_addon=False,
        place_min_gap=99,
        max_win_per_race=1,
        closing_boost_threshold=0,
    ),
    'simple_wide': BetStrategyParams(
        # rank_w=1 + win_gap>=3: simpleより広めの網
        win_max_rank_w=1,
        win_min_win_gap=3,
        win_min_vb_score=0,
        win_v_ratio_min=0,
        win_max_rank=99,
        win_min_gap=0,
        win_min_ev=0,
        ard_vb_min_ard=0,
        ard_vb_min_odds=0,
        place_addon=False,
        place_min_gap=99,
        max_win_per_race=1,
        closing_boost_threshold=0,
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
    gap: int = 0                # VB gap (place-based, rank差)
    dev_gap: float = 0.0        # 偏差値gap (z-score差, メイン選定基準)
    vb_score: float = 0.0       # コンポジットVBスコア (0-10)
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
    ar_deviation: Optional[float] = None  # AR偏差値 (strength判定の根拠表示用)


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
    dev_gap: float = 0.0,
    vb_score: float = 0.0,
) -> Tuple[bool, int]:
    """単勝評価 (composite score or tier-based)

    v5.44: Composite VB Score方式に移行。
    4シグナル(dev_gap/rank_gap/EV/ARd)を段階的にスコア化し、
    合計スコアで選定。rank_gapはベット倍率に使用。

    選定モード:
      Mode 1 (win_min_vb_score > 0): Composite Score ≥ threshold
      Mode 2 (legacy): dev_gap tier → rank_gap tier → flat threshold

    Returns:
        (should_bet, units) — units はベット倍率
        1 unit = params.bet_unit (100円)
    """
    passed = False

    # === Mode 1: Composite Score ===
    if params.win_min_vb_score > 0:
        if vb_score >= params.win_min_vb_score:
            passed = True
    else:
        # === Mode 2: Legacy tier-based ===
        # Route 1: dev_gap tier
        if params.win_ard_dev_tiers:
            for tier_ard, tier_dev in params.win_ard_dev_tiers:
                if ar_deviation is not None and ar_deviation >= tier_ard:
                    if dev_gap >= tier_dev:
                        passed = True
                    break

        # Route 2: rank_gap tier
        if not passed and params.win_ard_gap_tiers:
            for tier_ard, tier_gap in params.win_ard_gap_tiers:
                if ar_deviation is not None and ar_deviation >= tier_ard:
                    min_gap = tier_gap
                    if is_danger:
                        min_gap += params.danger_gap_boost
                    if gap >= min_gap:
                        passed = True
                    break

        # Route 3: フラット閾値
        if not passed and not params.win_ard_dev_tiers and not params.win_ard_gap_tiers:
            if params.win_min_ar_deviation > 0 and ar_deviation is not None:
                if ar_deviation < params.win_min_ar_deviation:
                    return False, 0
            min_gap = params.win_min_gap
            if is_danger:
                min_gap += params.danger_gap_boost
            if gap >= min_gap:
                passed = True

    if not passed:
        return False, 0

    # AR絶対閾値 (後方互換、0=無効)
    if params.win_min_rating > 0 and rating is not None:
        if rating < params.win_min_rating:
            return False, 0

    # === EV filter (secondary, 0=disabled) ===
    if params.win_min_ev > 0:
        if win_ev is None or win_ev < params.win_min_ev:
            return False, 0

    # ベット倍率: rank_gapが大きいとき攻める（穴馬での上乗せ）
    if gap >= 7:
        units = 3
    elif gap >= 5:
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


def compute_vb_score(
    dev_gap: float,
    gap: int,
    win_ev: Optional[float],
    ar_deviation: Optional[float],
) -> float:
    """コンポジットVBスコア: 全シグナルを統合した一元評価

    4つのシグナルを段階的に加点し、合計スコアで選定・強弱を判定する。
    単一シグナルだけでは高スコアにならず、複数シグナルの合致が必要。

    Score breakdown (max 10.0):
      dev_gap:  0-3 points (偏差値乖離: 的中率重視)
      rank_gap: 0-3 points (ランク差: 穴馬ROI)
      EV:       0-2 points (期待値)
      ARd:      0-2 points (能力偏差値)

    Returns:
        float: composite score (0.0 - 10.0)
    """
    score = 0.0

    # dev_gap: 偏差値ベースの本質的な乖離
    if dev_gap >= 1.5:
        score += 3.0
    elif dev_gap >= 1.0:
        score += 2.0
    elif dev_gap >= 0.5:
        score += 1.0

    # rank_gap: ランク差による穴馬検出
    if gap >= 7:
        score += 3.0
    elif gap >= 5:
        score += 2.0
    elif gap >= 3:
        score += 1.0

    # EV: 期待値 (calibrated probability × odds)
    ev = win_ev or 0.0
    if ev >= 2.0:
        score += 2.0
    elif ev >= 1.5:
        score += 1.5
    elif ev >= 1.0:
        score += 1.0

    # ARd: レース内能力偏差値
    ard = ar_deviation or 0.0
    if ard >= 65:
        score += 2.0
    elif ard >= 55:
        score += 1.5
    elif ard >= 50:
        score += 1.0

    return score


def detect_danger(
    entries: List[dict],
    max_odds: float = 8.0,
    max_ard: float = 53.0,
    max_pred_p: float = 0.15,
) -> Dict[int, bool]:
    """危険馬検出: odds <= max_odds & ARd < max_ard & P% < max_pred_p

    v5.33: ARd閾値 50→53 に拡大 (ラベル精度向上)
    バックテスト実績: 勝率 13.8%, 複勝率 35.3% (ベースライン 21.0%, 51.4%)

    Args:
        entries: predict_race() の出力 entries リスト
        max_odds: オッズ上限 (この値以下が対象)
        max_ard: AR偏差値上限 (この値未満が対象)
        max_pred_p: P%上限 (この値未満が対象, calibrated)

    Returns:
        {umaban: True} — 危険馬と判定された馬のみ
    """
    danger = {}
    for e in entries:
        odds = e.get('odds', 0) or 0
        ard = e.get('ar_deviation') or 0
        pred_p = e.get('pred_proba_p', 0) or 0
        if 0 < odds <= max_odds and ard < max_ard and pred_p < max_pred_p:
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
                           rank_p, odds_rank, place_odds_min, place_ev, win_ev,
                           predicted_margin (能力R rating, optional),
                           pred_proba_p_raw (optional, for Kelly),
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

        # 危険馬検出 (odds<=8 & ARd<53 & P%<15%) — ラベルのみ、gap boostなし
        danger_map = detect_danger(entries)

        # P%比率フィルター用: レース内最大P%を計算
        if params.win_v_ratio_min > 0:
            v_pcts = [(e.get('pred_proba_p_raw') or 0) for e in entries]
            race_max_v = max(v_pcts) if v_pcts else 0
        else:
            race_max_v = 0

        # Closing Race Boost: 差し決着が予想されるレースかどうか
        closing_proba = race.get('closing_race_proba', 0) or 0
        is_closing_race = (params.closing_boost_threshold > 0
                           and closing_proba >= params.closing_boost_threshold)

        race_recs: List[BetRecommendation] = []

        for e in entries:
            umaban = e['umaban']
            horse_name = e.get('horse_name', '')
            odds = e.get('odds', 0) or 0
            gap = e.get('vb_gap', 0) or 0
            win_gap = e.get('win_vb_gap', 0) or 0
            rank_p = e.get('rank_p', 99)
            rank_w = e.get('rank_w') or 99
            odds_rank = e.get('odds_rank', 0) or 0
            margin = e.get('predicted_margin')
            ar_dev = e.get('ar_deviation')
            p_top3_raw = e.get('pred_proba_p_raw')
            place_odds = e.get('place_odds_min')
            win_ev = e.get('win_ev')
            place_ev = e.get('place_ev')

            # rank_w フィルタ (simple preset用)
            if params.win_max_rank_w > 0 and rank_w > params.win_max_rank_w:
                continue

            is_danger = umaban in danger_map
            danger_score = 1.0 if is_danger else 0.0
            entry_dev_gap = e.get('dev_gap', 0) or 0

            # Composite VB Score (全シグナル統合)
            entry_vb_score = compute_vb_score(entry_dev_gap, gap, win_ev, ar_dev)

            # Closing Race Boost: 差し決着レースで差し馬にスコア加算
            if is_closing_race:
                cs = e.get('closing_strength', -1) or -1
                if cs >= params.closing_boost_min_strength:
                    entry_vb_score += params.closing_boost_score

            # Slow Start Risk: 出遅れ常習馬にマイナスブースト
            if params.slow_start_penalty < 0:
                ss_rate = e.get('horse_slow_start_rate', -1)
                if ss_rate is not None and ss_rate >= params.slow_start_min_rate:
                    penalty = params.slow_start_penalty
                    # 逃げ馬は出遅れでレースプラン崩壊するため倍率適用
                    corner1_ratio = e.get('last_race_corner1_ratio', -1)
                    if corner1_ratio is not None and 0 <= corner1_ratio <= params.slow_start_front_runner_threshold:
                        penalty *= params.slow_start_front_runner_multiplier
                    entry_vb_score += penalty

            # === VB Floor Gate: 購入プラン⊆VB候補 ===
            vb_ev_ok = (win_ev or 0) >= VB_FLOOR_MIN_WIN_EV
            vb_ard_ok = (ar_dev or 0) >= VB_FLOOR_MIN_ARD
            vb_ard_route = ((ar_dev or 0) >= VB_FLOOR_ARD_VB_MIN_ARD
                            and odds >= VB_FLOOR_ARD_VB_MIN_ODDS)
            vb_dev_route = (entry_dev_gap >= VB_FLOOR_MIN_DEV_GAP
                            and (ar_dev or 0) >= VB_FLOOR_DEV_MIN_ARD)
            if not (vb_ev_ok and vb_ard_ok) and not vb_ard_route and not vb_dev_route:
                continue

            # --- 単勝評価 ---
            # Pre-filter: P%比率 or rank_p
            #   P%比率: レース内top1のP%に対する比率で足切り（大混戦に対応）
            #   バイパス: P%比率未達でもGap+EVが十分高い穴馬を例外通過
            #   rank_p: 従来の順位ベース足切り（P%比率が0の場合のフォールバック）
            if params.win_v_ratio_min > 0:
                v_pct = p_top3_raw or 0
                v_ratio = v_pct / race_max_v if race_max_v > 0 else 0
                win_prefilter_pass = v_ratio >= params.win_v_ratio_min
                # バイパス: P%比率未達でも高Gap+高EVなら通過
                if not win_prefilter_pass and params.win_v_bypass_gap > 0 and params.win_v_bypass_ev > 0:
                    bypass_gap_ok = gap >= params.win_v_bypass_gap
                    bypass_ev_ok = (win_ev or 0) >= params.win_v_bypass_ev
                    if bypass_gap_ok and bypass_ev_ok:
                        win_prefilter_pass = True
                # dev_gapバイパス: 偏差値的に大きく乖離していれば通過
                if not win_prefilter_pass and entry_dev_gap >= 1.0:
                    win_prefilter_pass = True
            else:
                win_prefilter_pass = rank_p <= params.win_max_rank

            if not win_prefilter_pass:
                win_ok, win_units = False, 0
            else:
                win_ok, win_units = evaluate_win(
                    gap, margin, params, is_danger,
                    ar_deviation=ar_dev, win_ev=win_ev,
                    dev_gap=entry_dev_gap, vb_score=entry_vb_score,
                )

            # win_gap フィルタ (simple preset用: win_vb_gap >= N)
            if win_ok and params.win_min_win_gap > 0 and win_gap < params.win_min_win_gap:
                win_ok = False
                win_units = 0

            # --- ARd VBルート (能力 vs 市場の直接乖離) ---
            # Gap VBが不合格でも、ARdが極端に高くオッズが高い馬は独立ルートで通過
            # P%比率・Gap・EVフィルターを全てバイパスする
            ard_vb_pass = False
            if not win_ok and params.ard_vb_min_ard > 0 and params.ard_vb_min_odds > 0:
                if (ar_dev is not None and ar_dev >= params.ard_vb_min_ard
                        and odds >= params.ard_vb_min_odds):
                    win_ok = True
                    win_units = 1
                    ard_vb_pass = True

            # --- 複勝評価 ---
            # Pre-filter: P%比率 or rank_p top3
            if params.win_v_ratio_min > 0:
                place_prefilter_pass = win_prefilter_pass  # 単勝と同じ基準
            else:
                place_prefilter_pass = rank_p <= 3
            if not place_prefilter_pass:
                place_ok, kelly_frac = False, 0.0
            else:
                place_ok, kelly_frac = evaluate_place(
                    gap, margin, p_top3_raw, place_odds, params, is_danger, ar_deviation=ar_dev,
                )

            if not win_ok and not place_ok:
                continue

            # bet_type 決定 (strength判定: composite score or legacy)
            if params.win_min_vb_score > 0:
                # Composite Score mode: スコアで強弱判定
                is_strong = ard_vb_pass or entry_vb_score >= params.vb_strong_score
            else:
                # Legacy mode
                is_strong = ard_vb_pass or entry_dev_gap >= 1.5
                if not is_strong:
                    if params.win_ard_gap_tiers and ar_dev is not None:
                        strong_gap = params.win_min_gap + 2
                        for tier_ard, tier_gap in params.win_ard_gap_tiers:
                            if ar_dev >= tier_ard:
                                strong_gap = tier_gap + 2
                                break
                    else:
                        strong_gap = params.win_min_gap + 2
                    if gap >= strong_gap:
                        is_strong = True

            if win_ok and place_ok:
                bet_type = '単複'
                strength = 'strong' if is_strong else 'normal'
            elif win_ok:
                bet_type = '単勝'
                strength = 'strong' if is_strong else 'normal'
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
                dev_gap=entry_dev_gap,
                vb_score=round(entry_vb_score, 1),
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
                ar_deviation=round(ar_dev, 1) if ar_dev is not None else None,
            )
            # --- Place上乗せ: 単勝候補に条件付きで複勝追加 ---
            if win_ok and params.place_addon:
                pev = place_ev or 0
                ard = ar_dev or 0
                if pev >= params.place_addon_min_pev and ard >= params.place_addon_min_ard:
                    rec.place_amount = params.place_addon_amount
                    rec.bet_type = '単複'

            race_recs.append(rec)

        # 1レースN単勝制約 (max_win_per_race: 0=無制限, 2=推奨)
        race_recs = apply_win_per_race_limit(race_recs, max_win=params.max_win_per_race)
        all_recs.extend(race_recs)

    # 予算スケーリング
    all_recs = apply_budget(all_recs, budget, params)

    # クロス配分: strength別に単複金額を分割
    if params.cross_alloc:
        all_recs = apply_cross_allocation(all_recs, params)

    return all_recs


def apply_win_per_race_limit(
    recs: List[BetRecommendation],
    max_win: int = 2,
) -> List[BetRecommendation]:
    """1レースN単勝制約: N+1番目以降の単勝を複勝に降格

    バックテスト結果:
      max=1: aggressive ROI 249%, wide ROI 124%
      max=2: aggressive ROI 406%, wide ROI 138% (最適)
      制限なし: aggressive ROI 406%, wide ROI 135%
    2番手候補の的中率は全体平均より高い（14.3% vs 5.3%）

    優先順位: dev_gap (偏差値乖離) → gap (rank差) → odds の順
    """
    if max_win <= 0:
        # 0 = 制限なし
        return recs

    # 単勝候補を抽出 (単勝 or 単複)
    win_candidates = [r for r in recs if r.bet_type in ('単勝', '単複')]

    if len(win_candidates) <= max_win:
        return recs

    # vb_score 降順ソート (複合スコアで優先順位)
    win_candidates.sort(key=lambda r: (-r.vb_score, -r.dev_gap, -r.odds))

    # 上位max_win頭はそのまま、それ以降を降格
    for r in win_candidates[max_win:]:
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
    # place_addon で既にセット済みの場合はスキップ
    for r in recs:
        if r.place_amount > 0:
            # place_addon等で既にセット済み → そのまま
            pass
        elif r.bet_type in ('複勝', '単複') and r.kelly_capped > 0:
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


def apply_cross_allocation(
    recs: List[BetRecommendation],
    params: BetStrategyParams,
) -> List[BetRecommendation]:
    """クロス配分: strength別に単複金額を分割。

    VB判定は単勝ベースだが、購入時はstrengthに応じて単複に配分する。
    strong → 単勝重視 (例: 単7:複3)
    normal → 複勝重視 (例: 単3:複7)
    """
    for r in recs:
        total = r.win_amount + r.place_amount
        if total <= 0:
            continue

        if r.strength == 'strong':
            win_pct = params.strong_win_pct
        else:
            win_pct = params.normal_win_pct

        place_pct = 100 - win_pct

        r.win_amount = max(params.min_bet,
                           round_to_unit(total * win_pct / 100, params.bet_unit))
        r.place_amount = max(params.min_bet,
                             round_to_unit(total * place_pct / 100, params.bet_unit))

        # bet_typeを更新
        if r.win_amount > 0 and r.place_amount > 0:
            r.bet_type = '単複'
        elif r.win_amount > 0:
            r.bet_type = '単勝'
        else:
            r.bet_type = '複勝'

    return recs


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

def df_to_race_predictions(
    df_test,
    grade_offsets: Dict[str, float] = None,
    closing_proba_map: Dict[str, float] = None,
) -> List[dict]:
    """DataFrame → generate_recommendations() 入力形式に変換

    experiment.py / backtest_bet_engine.py の両方から利用。
    df_test には pred_rank_p, odds_rank, pred_margin_ar 等が必要。

    Args:
        grade_offsets: Method A グレードオフセット {grade_key: offset}
            Noneの場合はオフセットなし（従来の相対R）
        closing_proba_map: {race_id: closing_race_proba} レースレベル差し決着確率
            Noneの場合は0（closing boostなし）
    """
    import pandas as pd
    import numpy as np

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
            relative_rating = RATING_BASE - float(row['pred_margin_ar']) * RATING_SCALE if pd.notna(row.get('pred_margin_ar')) else None
            absolute_rating = (relative_rating + offset) if relative_rating is not None else None

            entries.append({
                'umaban': int(row['umaban']),
                'horse_name': str(row.get('horse_name', '')),
                'odds': float(row.get('odds', 0)),
                'vb_gap': int(row.get('vb_gap', 0)),
                'win_vb_gap': int(row.get('win_vb_gap', 0)),
                'rank_p': int(row.get('pred_rank_p', 99)),
                'rank_w': int(row.get('pred_rank_w', 99)) if pd.notna(row.get('pred_rank_w')) else 99,
                'odds_rank': int(row.get('odds_rank', 0)),
                'place_odds_min': float(row['place_odds_low']) if pd.notna(row.get('place_odds_low')) else None,
                'pred_proba_p_raw': float(row.get('pred_proba_p_raw', 0)),
                'predicted_margin': absolute_rating,
                'win_ev': float(row.get('win_ev', 0)) if pd.notna(row.get('win_ev')) else None,
                'place_ev': float(row.get('place_ev', 0)) if pd.notna(row.get('place_ev')) else None,
                'comment_memo_trouble_score': float(row.get('comment_memo_trouble', 0)),
                # closing model 連携
                'closing_strength': float(row.get('closing_strength', -1)) if pd.notna(row.get('closing_strength')) else -1,
                # slow start risk
                'horse_slow_start_rate': float(row.get('horse_slow_start_rate', -1)) if pd.notna(row.get('horse_slow_start_rate')) else -1,
                'last_race_corner1_ratio': float(row.get('last_race_corner1_ratio', -1)) if pd.notna(row.get('last_race_corner1_ratio')) else -1,
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

        # dev_gap計算（偏差値ベースの乖離: モデル評価 vs 市場評価）
        preds = np.array([e.get('pred_proba_p_raw', 0) or 0 for e in entries])
        implied = np.array([1.0 / e['odds'] if e['odds'] > 0 else 0 for e in entries])
        pred_mean, pred_std = preds.mean(), max(preds.std(), 1e-8)
        imp_mean, imp_std = implied.mean(), max(implied.std(), 1e-8)
        for i, e in enumerate(entries):
            model_z = (preds[i] - pred_mean) / pred_std
            market_z = (implied[i] - imp_mean) / imp_std
            e['dev_gap'] = round(float(model_z - market_z), 3)

        closing_proba = 0.0
        if closing_proba_map:
            closing_proba = closing_proba_map.get(str(race_id), 0.0)

        races.append({
            'race_id': str(race_id),
            'track_type': str(row.get('track_type_name', '')),
            'grade': grade,
            'age_class': age_class,
            'grade_offset': offset,
            'closing_race_proba': closing_proba,
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
