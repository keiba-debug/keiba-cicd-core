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
from itertools import combinations
from typing import Dict, List, Optional, Tuple

# 能力R変換定数 (ability_score → rating) — IDMスケール
# ability_score = -pred_margin_ar (符号反転: 高い=強い)
# rating = RATING_BASE + ability_score * RATING_SCALE
# Session 90: IDMキャリブレーション適用 (0.92*旧R-11.84)
RATING_SCALE = 13.5
RATING_BASE = 56.4

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

# 障害レース用VB Floor (ARモデルなし → ARd不要、EV + dev_gap or rank_wベース)
OBSTACLE_VB_FLOOR_MIN_WIN_EV = 1.0   # 単勝EV下限
OBSTACLE_VB_FLOOR_MIN_DEV_GAP = 0.5  # 偏差値gapルート: dev_gap下限 (平地より緩い)
OBSTACLE_VB_FLOOR_MAX_RANK_W = 3     # rank_wルート: Wモデル3位以内
# 障害複勝ルート (単勝EVが低くても複勝EVが高ければ通過)
OBSTACLE_VB_FLOOR_MIN_PLACE_EV = 1.5  # 複勝EV下限 (1.1→1.5に引き上げ: 1レース複勝5頭問題対策)
OBSTACLE_VB_FLOOR_MAX_RANK_P = 3      # Pモデル3位以内（5→3に絞り込み）
# 障害ワイドルート (Pモデル Top1-2 ペア, 9頭以上)
OBSTACLE_WIDE_MIN_RUNNERS = 9         # 少頭数は配当妙味なし(<=8: ROI 58%)
OBSTACLE_WIDE_MAX_RANK_P = 2          # Pモデル Top1-2ペア

# 激戦ワイド (Intense Wide - hit-focused)
GEKISEN_WIDE_MAX_ENTRIES = 14
GEKISEN_WIDE_MIN_PAIR_AGREE = 3
GEKISEN_WIDE_MIN_ODDS = 2.0  # ワイドオッズフロア (BT: <2.0→ROI 72%, >=2.0→ROI 103%)


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
    # 能力R上限: 0=無効, 60=推奨 (predicted_margin <= N → 接戦予測フィルタ)
    # 高すぎるR(=圧倒的実力差)はオッズに既に織り込み済み → 除外
    win_max_predicted_margin: float = 0.0

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
    # --- Intersection Filter (推奨) ---
    # rank_w=1 + gap>=4 + EV>=1.3 + predicted_margin<=60 の全交差条件。
    # バックテスト結果 (v7.3, 2025-03~2026-02):
    #   46件, 的中率19.6%, WinROI 310.7%, P&L +9,690
    #   利益は100% Intersection条件内（他ティアは全てマイナスROI）
    # BETTING_STRATEGY_v3.0.md 参照
    'intersection': BetStrategyParams(
        win_max_rank_w=1,               # rank_w=1のみ
        win_min_win_gap=4,              # win_vb_gap>=4
        win_min_ev=1.3,                 # EV>=1.3 (evaluate_win内で適用)
        win_max_predicted_margin=43.4,  # IDMスケール (旧R<=60, 接戦フィルタ)
        win_min_vb_score=0,             # Composite Score無効
        win_v_ratio_min=0,              # P%比率フィルタ無効
        win_max_rank=99,                # rank_pフィルタ無効
        win_min_gap=0,                  # place gapフィルタ無効
        ard_vb_min_ard=0,              # ARd VBルート無効
        ard_vb_min_odds=0,
        place_addon=False,              # 複勝なし: 単勝一本
        place_min_gap=99,               # 複勝単独無効
        max_win_per_race=1,             # 1レース1買い
        closing_boost_threshold=0,      # Closing boost無効
    ),
    # --- Relaxed Intersection (intersection の緩和版) ---
    # rank_w=1 + gap>=2 + EV>=1.5 + predicted_margin<=43.4
    # gap=2&EV>=1.5のバイパスルール追加 (14件, ROI 150%)
    # バンクロールSim (v7.3.1, 2025-03~2026-02):
    #   adaptive K1/4 で ROI+182%, K1/8 で ROI+151% (Sharpe 0.096)
    #   単勝56件(的中率16%) + ワイド139件(odds>=2.0, ROI 103%) + 馬連139件(ROI 110%)
    'relaxed': BetStrategyParams(
        win_max_rank_w=1,               # rank_w=1のみ
        win_min_win_gap=2,              # win_vb_gap>=2 (旧: 3, バイパスルール)
        win_min_ev=1.3,                 # EV>=1.3 (gap=2バイパス, 1.5→1.3緩和)
        win_max_predicted_margin=43.4,  # IDMスケール (接戦フィルタ)
        win_min_vb_score=0,             # Composite Score無効
        win_v_ratio_min=0,              # P%比率フィルタ無効
        win_max_rank=99,                # rank_pフィルタ無効
        win_min_gap=0,                  # place gapフィルタ無効
        ard_vb_min_ard=0,              # ARd VBルート無効
        ard_vb_min_odds=0,
        place_addon=False,              # 複勝なし: 単勝一本
        place_min_gap=99,               # 複勝単独無効
        max_win_per_race=1,             # 1レース1買い
        closing_boost_threshold=0,      # Closing boost無効
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
    bet_type: str               # '単勝' | '複勝' | '単複' | 'ワイド' | '馬連' | '馬単'
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
    kelly_win_frac: float = 0.0     # Kelly fraction for win bet (raw f*)
    kelly_amount: int = 0           # Kelly推奨合計額 (bankroll * f* * fraction, 100円丸め)
    is_danger: bool = False
    danger_score: float = 0.0
    odds: float = 0.0
    place_odds_min: Optional[float] = None
    ar_deviation: Optional[float] = None  # AR偏差値 (strength判定の根拠表示用)
    wide_pair: Optional[List[int]] = None  # ワイド対象ペア [umaban1, umaban2]
    wide_source: Optional[str] = None     # ワイド出所: '障害' | '激戦'
    market_signal: Optional[str] = None   # 基準オッズ市場シグナル (鉄板/軸向き/妙味/etc.)


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
    is_obstacle: bool = False,
) -> Tuple[bool, float]:
    """複勝評価 (gap + AR偏差値足切り + EV + Kelly)

    Returns:
        (should_bet, kelly_fraction) — kelly_fraction は 0~kelly_cap の範囲
    """
    # 障害レース複勝EVバイパス: place_ev >= 1.1 ならgapチェック不要
    if is_obstacle and p_top3 is not None and place_odds is not None and place_odds > 0:
        obs_ev = p_top3 * place_odds
        if obs_ev >= OBSTACLE_VB_FLOOR_MIN_PLACE_EV:
            kelly = calc_kelly_fraction(p_top3, place_odds)
            kelly_sized = kelly * params.kelly_fraction
            kelly_sized = min(kelly_sized, params.kelly_cap)
            return (kelly_sized > 0), max(kelly_sized, 0.0)

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
    is_obstacle: bool = False,
) -> float:
    """コンポジットVBスコア: 全シグナルを統合した一元評価

    4つのシグナルを段階的に加点し、合計スコアで選定・強弱を判定する。
    単一シグナルだけでは高スコアにならず、複数シグナルの合致が必要。

    Score breakdown (max 10.0):
      dev_gap:  0-3 points (偏差値乖離: 的中率重視)
      rank_gap: 0-3 points (ランク差: 穴馬ROI)
      EV:       0-2 points (期待値)
      ARd:      0-2 points (能力偏差値) ※障害レースはARなし→EV+rank_wで補填

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

    if is_obstacle:
        # 障害レース: ARモデルなし → EV枠を拡張して補填
        # EV >= 2.5 で追加 +2.0, EV >= 1.5 で +1.0 (ARd代替)
        if ev >= 2.5:
            score += 2.0
        elif ev >= 1.5:
            score += 1.0
    else:
        # ARd: レース内能力偏差値 (平地のみ)
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
# ワイド/馬連オッズ取得
# =====================================================================

def _make_kumiban(u1: int, u2: int) -> str:
    """馬番ペアからKUMIBAN文字列を生成 (例: (3, 14) -> '0314')"""
    a, b = sorted([u1, u2])
    return f"{a:02d}{b:02d}"


def _fetch_wide_odds_for_race(race_id: str) -> Dict[str, dict]:
    """レースのワイドオッズをDBから取得。DB未接続時は空dictを返す。
    race_id = race_code (同じ16桁フォーマット)。"""
    try:
        from core.odds_db import get_final_wide_odds
        return get_final_wide_odds(race_id)
    except Exception:
        return {}


def _fetch_umaren_odds_for_race(race_id: str) -> Dict[str, dict]:
    """レースの馬連オッズをDBから取得。DB未接続時は空dictを返す。"""
    try:
        from core.odds_db import get_final_quinella_odds
        return get_final_quinella_odds(race_id)
    except Exception:
        return {}


def _lookup_wide_odds(wide_odds: Dict[str, dict], u1: int, u2: int) -> float:
    """ワイドオッズのルックアップ。odds_lowを返す（保守的）。なければ0.0。"""
    kumiban = _make_kumiban(u1, u2)
    entry = wide_odds.get(kumiban)
    if entry:
        return entry.get('odds_low', 0.0) or 0.0
    return 0.0


def _lookup_umaren_odds(umaren_odds: Dict[str, dict], u1: int, u2: int) -> float:
    """馬連オッズのルックアップ。なければ0.0。"""
    kumiban = _make_kumiban(u1, u2)
    entry = umaren_odds.get(kumiban)
    if entry:
        return entry.get('odds', 0.0) or 0.0
    return 0.0


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
        is_obstacle = race.get('track_type') == 'obstacle'

        if not entries:
            continue

        # 危険馬検出 (odds<=8 & ARd<53 & P%<15%) — ラベルのみ、gap boostなし
        # 障害レースはARなし → danger検出スキップ
        danger_map = {} if is_obstacle else detect_danger(entries)

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
            entry_vb_score = compute_vb_score(entry_dev_gap, gap, win_ev, ar_dev, is_obstacle=is_obstacle)

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
            if is_obstacle:
                # 障害レース: ワイド/馬連のみ（後段で生成）→ 単勝/複勝/単複はスキップ
                continue
            else:
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

            # 接戦フィルタ: 能力R上限 (intersection preset用)
            # R が高すぎる = 実力差が大きすぎ → オッズに織り込み済みで VALUE なし
            if win_ok and params.win_max_predicted_margin > 0 and margin is not None:
                if margin > params.win_max_predicted_margin:
                    win_ok = False
                    win_units = 0

            # --- ARd VBルート (能力 vs 市場の直接乖離) ---
            # Gap VBが不合格でも、ARdが極端に高くオッズが高い馬は独立ルートで通過
            # P%比率・Gap・EVフィルターを全てバイパスする
            # 障害レースはARなし → スキップ
            ard_vb_pass = False
            if not is_obstacle and not win_ok and params.ard_vb_min_ard > 0 and params.ard_vb_min_odds > 0:
                if (ar_dev is not None and ar_dev >= params.ard_vb_min_ard
                        and odds >= params.ard_vb_min_odds):
                    win_ok = True
                    win_units = 1
                    ard_vb_pass = True

            # --- 複勝評価 ---
            # Pre-filter: P%比率 or rank_p top3
            # 障害レース: 複勝EVが高い馬は prefilter バイパス (ランダム性高→EV重視)
            if is_obstacle and (place_ev or 0) >= OBSTACLE_VB_FLOOR_MIN_PLACE_EV:
                place_prefilter_pass = True  # 障害複勝EV基準通過
            elif params.win_v_ratio_min > 0:
                place_prefilter_pass = win_prefilter_pass  # 単勝と同じ基準
            else:
                place_prefilter_pass = rank_p <= 3
            if not place_prefilter_pass:
                place_ok, kelly_frac = False, 0.0
            else:
                place_ok, kelly_frac = evaluate_place(
                    gap, margin, p_top3_raw, place_odds, params, is_danger,
                    ar_deviation=ar_dev, is_obstacle=is_obstacle,
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

            # Kelly fraction for win bet
            win_kelly_f = 0.0
            if win_ok and odds > 1 and (win_ev or 0) > 0:
                p_win = (win_ev or 0) / odds
                win_kelly_f = calc_kelly_fraction(p_win, odds)

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
                kelly_win_frac=round(win_kelly_f, 4),
                is_danger=is_danger,
                danger_score=danger_score,
                odds=odds,
                place_odds_min=place_odds,
                ar_deviation=round(ar_dev, 1) if ar_dev is not None else None,
                market_signal=e.get('market_signal'),
            )
            # --- Place上乗せ: 単勝候補に条件付きで複勝追加 ---
            # 障害レースはARd不要、PlaceEVのみで判定
            if win_ok and params.place_addon:
                pev = place_ev or 0
                ard = ar_dev or 0
                addon_ok = (pev >= params.place_addon_min_pev
                            and (is_obstacle or ard >= params.place_addon_min_ard))
                if addon_ok:
                    rec.place_amount = params.place_addon_amount
                    rec.bet_type = '単複'

            race_recs.append(rec)

        # 1レースN単勝制約 (max_win_per_race: 0=無制限, 2=推奨)
        race_recs = apply_win_per_race_limit(race_recs, max_win=params.max_win_per_race)
        all_recs.extend(race_recs)

        # --- ワイド/馬連オッズの事前取得 ---
        _wide_odds_cache: Dict[str, dict] = {}
        _umaren_odds_cache: Dict[str, dict] = {}

        # --- 障害ワイド: Pモデル Top1-2 ペア (9頭以上) ---
        if is_obstacle and len(entries) >= OBSTACLE_WIDE_MIN_RUNNERS:
            sorted_by_rp = sorted(entries, key=lambda x: x.get('rank_p', 99))
            if len(sorted_by_rp) >= 2:
                e1, e2 = sorted_by_rp[0], sorted_by_rp[1]
                if (e1.get('rank_p', 99) <= OBSTACLE_WIDE_MAX_RANK_P
                        and e2.get('rank_p', 99) <= OBSTACLE_WIDE_MAX_RANK_P):
                    u1, u2 = e1['umaban'], e2['umaban']
                    n1, n2 = e1.get('horse_name', '?'), e2.get('horse_name', '?')
                    # ワイド/馬連オッズ取得 (初回のみDB問い合わせ)
                    if not _wide_odds_cache:
                        _wide_odds_cache = _fetch_wide_odds_for_race(race_id)
                    if not _umaren_odds_cache:
                        _umaren_odds_cache = _fetch_umaren_odds_for_race(race_id)
                    wide_rec = BetRecommendation(
                        race_id=race_id,
                        umaban=min(u1, u2),
                        horse_name=f"{n1}-{n2}",
                        bet_type='ワイド',
                        strength='strong',
                        win_amount=params.bet_unit,
                        place_amount=0,
                        odds=_lookup_wide_odds(_wide_odds_cache, u1, u2),
                        wide_pair=sorted([u1, u2]),
                        wide_source='障害',
                    )
                    all_recs.append(wide_rec)

                    # 障害馬連: 同じTop1-2ペア (rank_p 1位→2位の順)
                    umaren_rec = BetRecommendation(
                        race_id=race_id,
                        umaban=e1['umaban'],
                        horse_name=f"{n1}-{n2}",
                        bet_type='馬連',
                        strength='strong',
                        win_amount=params.bet_unit,
                        place_amount=0,
                        odds=_lookup_umaren_odds(_umaren_odds_cache, u1, u2),
                        wide_pair=sorted([u1, u2]),
                        wide_source='障害',
                    )
                    all_recs.append(umaren_rec)

            # 障害馬単: 3パターン（重複排除）
            # BT分析: P1→P2が11.2%で最高的中率、W1→W2が7.8%
            # v2.5bモデルではW Top1勝率45%に上昇→W1ベースも期待大
            sorted_by_rw = sorted(entries, key=lambda x: x.get('rank_w') or 99)
            if len(sorted_by_rw) >= 2 and len(sorted_by_rp) >= 2:
                w1 = sorted_by_rw[0]
                w2 = sorted_by_rw[1]
                p1 = sorted_by_rp[0]
                p2 = sorted_by_rp[1]
                umatan_pairs_added = set()  # (1着馬番, 2着馬番) で重複排除

                def _add_umatan(first_e, second_e):
                    pair_key = (first_e['umaban'], second_e['umaban'])
                    if pair_key in umatan_pairs_added:
                        return
                    if pair_key[0] == pair_key[1]:
                        return
                    umatan_pairs_added.add(pair_key)
                    f_uma, s_uma = pair_key
                    f_name = first_e.get('horse_name', '?')
                    s_name = second_e.get('horse_name', '?')
                    est_umaren = _lookup_umaren_odds(
                        _umaren_odds_cache, f_uma, s_uma
                    ) if _umaren_odds_cache else 0
                    est_odds = round(est_umaren * 2, 1) if est_umaren else 0
                    rec = BetRecommendation(
                        race_id=race_id,
                        umaban=f_uma,
                        horse_name=f"{f_name}→{s_name}",
                        bet_type='馬単',
                        strength='normal',
                        win_amount=params.bet_unit,
                        place_amount=0,
                        odds=est_odds,
                        wide_pair=[f_uma, s_uma],  # 1着→2着の順
                        wide_source='障害',
                    )
                    all_recs.append(rec)

                # (1) P1→P2: 最高的中率11.2%
                _add_umatan(p1, p2)
                # (2) W1→W2: 7.8%、v2.5bで上昇期待
                _add_umatan(w1, w2)
                # (3) P1→W2: P1≠W1の場合のクロス 6.9%
                if p1['umaban'] != w1['umaban']:
                    _add_umatan(p1, w2)

        # --- 激戦ワイド: pair_agree フィルタ (非障害, 14頭以下) ---
        # v5: ワイドオッズフロア>=2.0追加 + 馬連同時生成
        # BT: 全件ROI 85%→odds>=2.0でROI 103%, +馬連でROI 107%
        if not is_obstacle and len(entries) <= GEKISEN_WIDE_MAX_ENTRIES:
            # pair_agree: rank_p, rank_w, ar_deviation, odds_rankのtop2が何個一致するか
            sorted_by_rp = sorted(entries, key=lambda x: x.get('rank_p', 99))
            sorted_by_rw = sorted(entries, key=lambda x: x.get('rank_w', 99))
            sorted_by_ard = sorted(entries, key=lambda x: -float(x.get('ar_deviation', 0) or 0))
            sorted_by_odds = sorted(entries, key=lambda x: float(x.get('odds', 999) or 999))

            top2_sets = []
            for ranking in [sorted_by_rp, sorted_by_rw, sorted_by_ard, sorted_by_odds]:
                if len(ranking) >= 2:
                    top2_sets.append(frozenset([ranking[0]['umaban'], ranking[1]['umaban']]))

            if top2_sets:
                # Count how many rankings agree with rank_p's top2
                rp_top2 = top2_sets[0]
                pair_agree = sum(1 for s in top2_sets[1:] if s == rp_top2)

                if pair_agree >= GEKISEN_WIDE_MIN_PAIR_AGREE:
                    p_top2 = sorted_by_rp[:2]
                    u1, u2 = p_top2[0]['umaban'], p_top2[1]['umaban']
                    n1, n2 = p_top2[0].get('horse_name', '?'), p_top2[1].get('horse_name', '?')

                    # ワイド/馬連オッズ取得 (初回のみDB問い合わせ)
                    if not _wide_odds_cache:
                        _wide_odds_cache = _fetch_wide_odds_for_race(race_id)
                    if not _umaren_odds_cache:
                        _umaren_odds_cache = _fetch_umaren_odds_for_race(race_id)

                    wide_odds = _lookup_wide_odds(_wide_odds_cache, u1, u2)

                    # ワイドオッズフロア: <2.0は配当妙味なし (BT: ROI 72%)
                    if wide_odds >= GEKISEN_WIDE_MIN_ODDS:
                        wide_rec = BetRecommendation(
                            race_id=race_id,
                            umaban=min(u1, u2),
                            horse_name=f"{n1}-{n2}",
                            bet_type='ワイド',
                            strength='strong',
                            win_amount=params.bet_unit,
                            place_amount=0,
                            odds=wide_odds,
                            wide_pair=sorted([u1, u2]),
                            wide_source='激戦',
                        )
                        all_recs.append(wide_rec)

                        # 激戦馬連: 同じTop1-2ペア (ワイドオッズフロア通過時のみ)
                        # BT: ワイド+馬連両方でROI 107% (odds_w>=2.0時)
                        umaren_rec = BetRecommendation(
                            race_id=race_id,
                            umaban=p_top2[0]['umaban'],
                            horse_name=f"{n1}-{n2}",
                            bet_type='馬連',
                            strength='strong',
                            win_amount=params.bet_unit,
                            place_amount=0,
                            odds=_lookup_umaren_odds(_umaren_odds_cache, u1, u2),
                            wide_pair=sorted([u1, u2]),
                            wide_source='激戦',
                        )
                        all_recs.append(umaren_rec)

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


def apply_kelly_sizing(
    recs: List[BetRecommendation],
    bankroll: int,
    kelly_fraction: float = 0.25,
    kelly_cap: float = 0.05,
) -> List[BetRecommendation]:
    """Kelly Criterion でベット額を計算し kelly_amount にセット

    松風 Themis 方式: 確率 × オッズ → Kelly → bankroll × f* × fraction

    Args:
        recs: 推奨リスト (kelly_win_frac が計算済み)
        bankroll: 現在のバンクロール (円)
        kelly_fraction: フラクショナルKelly (1/4=0.25が推奨)
        kelly_cap: 1ベットの最大bankroll比率 (5%=0.05)
    """
    for r in recs:
        if r.bet_type in ('単勝', '単複'):
            raw_f = r.kelly_win_frac
            f = min(raw_f * kelly_fraction, kelly_cap)
            win_kelly = max(100, round_to_unit(bankroll * f))
            # 単複の場合: 複勝分はplace Kelly or place_addonベース
            if r.bet_type == '単複':
                place_kelly = max(100, round_to_unit(bankroll * min(r.kelly_capped * kelly_fraction, kelly_cap))) if r.kelly_capped > 0 else r.place_amount
                r.kelly_amount = win_kelly + max(place_kelly, r.place_amount)
            else:
                r.kelly_amount = win_kelly
        elif r.bet_type == '複勝':
            if r.kelly_capped > 0:
                f = min(r.kelly_capped * kelly_fraction, kelly_cap)
                r.kelly_amount = max(100, round_to_unit(bankroll * f))
            else:
                r.kelly_amount = r.place_amount or 100
        elif r.bet_type == 'ワイド':
            # ワイド: 補助券種のため固定比率（bankroll × 1%）
            r.kelly_amount = max(100, round_to_unit(bankroll * 0.01))
        elif r.bet_type == '馬連':
            # 馬連: 補助券種のため固定比率（bankroll × 1%、ペア調整でワイド以下に制限）
            r.kelly_amount = max(100, round_to_unit(bankroll * 0.01))
        else:
            r.kelly_amount = r.win_amount + r.place_amount

    # ペア調整: 同じペアのワイド≥馬連を保証（ワイドは当たりやすいので多く）
    pair_wide_map: Dict[str, BetRecommendation] = {}
    for r in recs:
        if r.bet_type == 'ワイド' and r.wide_pair:
            key = f"{r.race_id}_{sorted(r.wide_pair)}"
            pair_wide_map[key] = r
    for r in recs:
        if r.bet_type == '馬連' and r.wide_pair:
            key = f"{r.race_id}_{sorted(r.wide_pair)}"
            wide_rec = pair_wide_map.get(key)
            if wide_rec:
                # 馬連 <= ワイド を保証。ワイドのほうが小さい場合はワイドに合わせる
                if r.kelly_amount > wide_rec.kelly_amount:
                    r.kelly_amount = wide_rec.kelly_amount

    return recs


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
    wide_bets = [r for r in recs if r.bet_type == 'ワイド']
    umaren_bets = [r for r in recs if r.bet_type == '馬連']
    umatan_bets = [r for r in recs if r.bet_type == '馬単']

    return {
        'total_bets': len(recs),
        'total_amount': sum(r.win_amount + r.place_amount for r in recs),
        'win_bets': len(win_bets),
        'place_bets': len(place_bets),
        'wide_bets': len(wide_bets),
        'umaren_bets': len(umaren_bets),
        'umatan_bets': len(umatan_bets),
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
    # ワイド/馬連/馬単 別集計
    wide_bet = 0
    wide_return = 0
    wide_hits = 0
    umaren_bet = 0
    umaren_return = 0
    umaren_hits = 0
    umatan_bet = 0
    umatan_return = 0
    umatan_hits = 0

    for r in recs:
        # --- ワイド/馬連: ペア判定 ---
        if r.bet_type in ('ワイド', '馬連', '馬単') and r.wide_pair:
            bet_amt = r.win_amount
            u1, u2 = r.wide_pair[0], r.wide_pair[1]
            e1 = entry_lookup.get((r.race_id, u1))
            e2 = entry_lookup.get((r.race_id, u2))
            if e1 is None or e2 is None:
                continue

            if r.bet_type == 'ワイド':
                wide_bet += bet_amt
                # ワイドヒット: 両方3着内
                if e1.get('is_top3', 0) and e2.get('is_top3', 0):
                    ret = r.odds * bet_amt if r.odds > 0 else 0
                    wide_return += ret
                    wide_hits += 1
            elif r.bet_type == '馬連':
                umaren_bet += bet_amt
                # 馬連ヒット: 両方2着内
                fp1 = e1.get('finish_position', 99)
                fp2 = e2.get('finish_position', 99)
                if fp1 <= 2 and fp2 <= 2:
                    ret = r.odds * bet_amt if r.odds > 0 else 0
                    umaren_return += ret
                    umaren_hits += 1
            else:  # 馬単
                umatan_bet += bet_amt
                # 馬単ヒット: pair[0]が1着 かつ pair[1]が2着
                fp1 = e1.get('finish_position', 99)
                fp2 = e2.get('finish_position', 99)
                if fp1 == 1 and fp2 == 2:
                    ret = r.odds * bet_amt if r.odds > 0 else 0
                    umatan_return += ret
                    umatan_hits += 1
            continue

        # --- 単勝/複勝/単複 ---
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

    total_bet = total_win_bet + total_place_bet + wide_bet + umaren_bet + umatan_bet
    total_return = total_win_return + total_place_return + wide_return + umaren_return + umatan_return

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
        'wide_bet': wide_bet,
        'wide_return': round(wide_return),
        'wide_roi': round(wide_return / wide_bet * 100, 1) if wide_bet > 0 else 0,
        'wide_hits': wide_hits,
        'umaren_bet': umaren_bet,
        'umaren_return': round(umaren_return),
        'umaren_roi': round(umaren_return / umaren_bet * 100, 1) if umaren_bet > 0 else 0,
        'umaren_hits': umaren_hits,
        'umatan_bet': umatan_bet,
        'umatan_return': round(umatan_return),
        'umatan_roi': round(umatan_return / umatan_bet * 100, 1) if umatan_bet > 0 else 0,
        'umatan_hits': umatan_hits,
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


# =====================================================================
# Adaptive Rules System (適応型作戦)
# =====================================================================
#
# レース状況（自信度・危険馬・頭数等）に応じて買い方を変える。
# 各ルールは優先順に評価し、最初にマッチしたルールで買い目を生成。
# 1レースで複数ルールが異なる馬にマッチすることもある。
#
# バックテスト結果 (3,364平地, 2025-03~2026-02):
#   danger_sniper: 13 bets, ROI 240% (危険馬レース×gap>=4×EV>=1.3)
#   ard_head:      ARd>=70×rank_w=1 → 高確信単勝
#   low_conf_ev:   73 bets, ROI 116% (低自信度×EV>=2.0)
#   gekisen_wide:  419 bets, ROI ~100% (激戦ワイド)
#   relaxed_base:  55 bets, ROI ~143% (relaxed条件)

@dataclass
class AdaptiveRule:
    """1つの適応型ルール"""
    name: str
    description: str
    # レース条件
    require_danger: Optional[bool] = None     # True=危険馬あり, False=なし, None=不問
    min_confidence: Optional[float] = None     # レース自信度下限 (0-100)
    max_confidence: Optional[float] = None     # レース自信度上限 (0-100)
    min_entries: int = 0                       # 最低頭数
    max_entries: int = 99                      # 最大頭数
    # 馬条件
    max_rank_w: int = 99                       # rank_w上限
    min_win_gap: int = 0                       # win_vb_gap下限
    min_win_ev: float = 0.0                    # win EV下限
    max_predicted_margin: float = 999.0        # predicted_margin上限
    min_ar_deviation: float = 0.0              # AR偏差値下限
    # VB Floor Gate (デフォルトTrue: 安全弁)
    apply_vb_floor: bool = True
    # 買い方
    bet_type: str = '単勝'                     # '単勝' | 'ワイド'
    kelly_fraction: float = 0.125              # Kelly fraction (1/8)
    max_per_race: int = 1                      # 1レースmax件数


@dataclass
class RaceContext:
    """レース状況の分析結果"""
    race_id: str
    confidence: float         # 0-100
    has_danger: bool
    danger_umabans: Dict[int, bool]
    num_entries: int
    p_gap: float              # P% top1-top2 gap
    pw_agree: bool            # rank_p top1 == rank_w top1
    ard_top1: float           # rank_p=1のARd


def compute_race_context(entries: List[dict]) -> RaceContext:
    """レースのエントリーから状況指標を計算

    Args:
        entries: generate_recommendations形式のentries
            (rank_p, rank_w, ar_deviation, pred_proba_p_raw, odds等)

    Returns:
        RaceContext with confidence score, danger detection, etc.
    """
    if not entries:
        return RaceContext(
            race_id='', confidence=0, has_danger=False,
            danger_umabans={}, num_entries=0,
            p_gap=0, pw_agree=False, ard_top1=50,
        )

    race_id = entries[0].get('race_id', '') if entries else ''

    # rank_p top1, top2
    sorted_by_rp = sorted(entries, key=lambda x: x.get('rank_p', 99))
    sorted_by_rw = sorted(entries, key=lambda x: x.get('rank_w', 99))

    top1_p = sorted_by_rp[0] if sorted_by_rp else {}
    top2_p = sorted_by_rp[1] if len(sorted_by_rp) >= 2 else {}

    # P% gap (top1 - top2)
    p1 = top1_p.get('pred_proba_p_raw') or 0
    p2 = top2_p.get('pred_proba_p_raw') or 0
    p_gap = p1 - p2

    # PW agreement
    top1_rp_uma = top1_p.get('umaban', -1)
    top1_rw_uma = sorted_by_rw[0].get('umaban', -2) if sorted_by_rw else -2
    pw_agree = top1_rp_uma == top1_rw_uma

    # ARd top1
    ard_top1 = top1_p.get('ar_deviation') or 50.0

    # Confidence score (0-100)
    #   p_gap: 差が大きい = 自信あり (0-0.15 → 0-40点)
    #   pw_agree: 一致 = 自信あり (0 or 30点)
    #   ard_top1: 高い = 自信あり (40-70 → 0-30点)
    p_gap_score = min(40.0, p_gap / 0.15 * 40.0) if p_gap > 0 else 0
    pw_score = 30.0 if pw_agree else 0.0
    ard_score = min(30.0, max(0.0, (ard_top1 - 40.0) / 30.0 * 30.0))
    confidence = round(p_gap_score + pw_score + ard_score, 1)

    # 危険馬検出
    danger_map = detect_danger(entries)

    return RaceContext(
        race_id=race_id,
        confidence=confidence,
        has_danger=len(danger_map) > 0,
        danger_umabans=danger_map,
        num_entries=len(entries),
        p_gap=p_gap,
        pw_agree=pw_agree,
        ard_top1=ard_top1,
    )


# --- デフォルト適応型ルール (バックテスト検証済み) ---
# 優先順に評価。先のルールが優先。同一馬×同一券種は先ルール採用。
#
# 設計思想:
#   relaxed_baseと同じ55件を買うが、ルールのKelly fractionを変える。
#   高確信ベット(danger_sniper, high_ev)は厚く、低確信は薄く。
#
# バックテスト結果 (3,364平地, v2_nowide):
#   danger_sniper:  16 bets, Kelly=K1/3 (危険馬レースx高gap高EV)
#   high_ev_win:    27 bets, Kelly=K1/4 (EV>=1.5の高期待値)
#   relaxed_base:   12 bets, Kelly=K1/8 (残りのrelaxed条件)
#   合計55件 (=relaxedと同一銘柄)
#
#   K1/8: Final 103,240 / ROI +106.5% / DD 19% (relaxed K1/8: +52.6%)
#   K1/4: Final 115,790 / ROI +131.6% / DD 20% (relaxed K1/4: +128.2%)
#   Flat:  ROI 179% (relaxed: 103%)
#
# NOTE: gekisen_wide(ROI 93%)は足を引っ張るため外した。
# NOTE: ARd>=65単体は ROI 78% (赤字)。gap交差でのみ価値あり。
# NOTE: relaxed_base(ROI 98%)は実質±0。外すとK1/4で+1.4pt改善。
#   → v5: danger_sniper + high_ev_win の2ルールが最高効率。
#   K1/8: +126.6%, K1/4: +135.2%
ADAPTIVE_RULES: List[AdaptiveRule] = [
    AdaptiveRule(
        name='danger_sniper',
        description='危険馬レースで狙い撃ち (K1/3)',
        require_danger=True,
        max_rank_w=1,
        min_win_gap=4,
        min_win_ev=1.3,
        max_predicted_margin=43.4,
        bet_type='単勝',
        kelly_fraction=0.33,       # K1/3 (最高確信)
        max_per_race=1,
    ),
    AdaptiveRule(
        name='high_ev_win',
        description='高EV単勝 (K1/4)',
        max_rank_w=1,
        min_win_gap=2,
        min_win_ev=1.3,
        max_predicted_margin=43.4,
        bet_type='単勝',
        kelly_fraction=0.25,       # K1/4
        max_per_race=1,
    ),
]


def _check_gekisen_wide(entries: List[dict]) -> Optional[Tuple[dict, dict]]:
    """激戦ワイド条件チェック: pair_agree >= 3 なら top2ペアを返す"""
    sorted_by_rp = sorted(entries, key=lambda x: x.get('rank_p', 99))
    sorted_by_rw = sorted(entries, key=lambda x: x.get('rank_w', 99))
    sorted_by_ard = sorted(entries, key=lambda x: -float(x.get('ar_deviation', 0) or 0))
    sorted_by_odds = sorted(entries, key=lambda x: float(x.get('odds', 999) or 999))

    top2_sets = []
    for ranking in [sorted_by_rp, sorted_by_rw, sorted_by_ard, sorted_by_odds]:
        if len(ranking) >= 2:
            top2_sets.append(frozenset([ranking[0]['umaban'], ranking[1]['umaban']]))

    if not top2_sets:
        return None

    rp_top2 = top2_sets[0]
    pair_agree = sum(1 for s in top2_sets[1:] if s == rp_top2)

    if pair_agree >= GEKISEN_WIDE_MIN_PAIR_AGREE:
        return (sorted_by_rp[0], sorted_by_rp[1])
    return None


def generate_adaptive_recommendations(
    race_predictions: List[dict],
    rules: List[AdaptiveRule] = None,
    budget: int = 30000,
) -> List[BetRecommendation]:
    """適応型ルールで全レースの買い目を生成

    各レースのコンテキスト（自信度・危険馬等）を分析し、
    ルールを優先順に評価して買い目を生成する。

    Args:
        race_predictions: predict_race() / df_to_race_predictions() の出力
        rules: AdaptiveRuleリスト (None=ADAPTIVE_RULES)
        budget: 総予算 (円)

    Returns:
        BetRecommendation のリスト
    """
    if rules is None:
        rules = ADAPTIVE_RULES

    all_recs: List[BetRecommendation] = []

    for race in race_predictions:
        race_id = race['race_id']
        entries = race.get('entries', [])
        is_obstacle = race.get('track_type') == 'obstacle'

        if not entries or is_obstacle:
            # 障害レースは従来ロジック（別途generate_recommendationsで対応）
            continue

        # レース状況分析
        ctx = compute_race_context(entries)

        # ワイドオッズキャッシュ (遅延取得)
        _wide_odds_cache: Dict[str, dict] = {}

        # 各ルールをレースに適用
        race_recs: List[BetRecommendation] = []

        for rule in rules:
            # === レース条件チェック ===
            if rule.require_danger is not None:
                if rule.require_danger and not ctx.has_danger:
                    continue
                if not rule.require_danger and ctx.has_danger:
                    continue

            if rule.min_confidence is not None and ctx.confidence < rule.min_confidence:
                continue
            if rule.max_confidence is not None and ctx.confidence > rule.max_confidence:
                continue
            if ctx.num_entries < rule.min_entries or ctx.num_entries > rule.max_entries:
                continue

            # === ワイド特殊処理 ===
            if rule.bet_type == 'ワイド':
                pair = _check_gekisen_wide(entries)
                if pair is None:
                    continue
                e1, e2 = pair
                u1, u2 = e1['umaban'], e2['umaban']
                n1, n2 = e1.get('horse_name', '?'), e2.get('horse_name', '?')
                if not _wide_odds_cache:
                    _wide_odds_cache = _fetch_wide_odds_for_race(race_id)
                wide_rec = BetRecommendation(
                    race_id=race_id,
                    umaban=min(u1, u2),
                    horse_name=f"{n1}-{n2}",
                    bet_type='ワイド',
                    strength='strong',
                    win_amount=100,
                    place_amount=0,
                    kelly_capped=rule.kelly_fraction,  # ルール固有のKelly fraction
                    odds=_lookup_wide_odds(_wide_odds_cache, u1, u2),
                    wide_pair=sorted([u1, u2]),
                    wide_source='激戦',
                    market_signal=f'rule:{rule.name}',
                )
                race_recs.append(wide_rec)
                continue

            # === 単勝: 馬レベルの条件チェック ===
            rule_hits: List[BetRecommendation] = []

            for e in entries:
                umaban = e['umaban']
                rank_w = e.get('rank_w') or 99
                win_gap = e.get('win_vb_gap', 0) or 0
                win_ev = e.get('win_ev')
                margin = e.get('predicted_margin')
                ar_dev = e.get('ar_deviation')
                odds = e.get('odds', 0) or 0
                gap = e.get('vb_gap', 0) or 0
                dev_gap_val = e.get('dev_gap', 0) or 0

                # rank_w
                if rank_w > rule.max_rank_w:
                    continue
                # win_gap
                if win_gap < rule.min_win_gap:
                    continue
                # win_ev
                if rule.min_win_ev > 0 and (win_ev is None or win_ev < rule.min_win_ev):
                    continue
                # predicted_margin
                if rule.max_predicted_margin < 999 and margin is not None:
                    if margin > rule.max_predicted_margin:
                        continue
                # ar_deviation
                if rule.min_ar_deviation > 0:
                    if ar_dev is None or ar_dev < rule.min_ar_deviation:
                        continue

                # VB Floor Gate
                if rule.apply_vb_floor:
                    vb_ev_ok = (win_ev or 0) >= VB_FLOOR_MIN_WIN_EV
                    vb_ard_ok = (ar_dev or 0) >= VB_FLOOR_MIN_ARD
                    vb_ard_route = ((ar_dev or 0) >= VB_FLOOR_ARD_VB_MIN_ARD
                                    and odds >= VB_FLOOR_ARD_VB_MIN_ODDS)
                    vb_dev_route = (dev_gap_val >= VB_FLOOR_MIN_DEV_GAP
                                    and (ar_dev or 0) >= VB_FLOOR_DEV_MIN_ARD)
                    if not (vb_ev_ok and vb_ard_ok) and not vb_ard_route and not vb_dev_route:
                        continue

                # Composite score (表示用)
                vb_score = compute_vb_score(dev_gap_val, gap, win_ev, ar_dev)

                is_danger = umaban in ctx.danger_umabans
                # Kelly fraction for win
                win_kelly_f = 0.0
                if odds > 1 and (win_ev or 0) > 0:
                    p_win = (win_ev or 0) / odds
                    win_kelly_f = calc_kelly_fraction(p_win, odds)

                rec = BetRecommendation(
                    race_id=race_id,
                    umaban=umaban,
                    horse_name=e.get('horse_name', ''),
                    bet_type='単勝',
                    strength='strong' if win_gap >= 6 or (ar_dev or 0) >= 65 else 'normal',
                    win_amount=100,
                    place_amount=0,
                    gap=gap,
                    dev_gap=dev_gap_val,
                    vb_score=round(vb_score, 1),
                    win_gap=win_gap,
                    predicted_margin=round(margin, 1) if margin is not None else 0.0,
                    win_ev=round(win_ev, 4) if win_ev is not None else None,
                    place_ev=round(e.get('place_ev', 0), 4) if e.get('place_ev') is not None else None,
                    kelly_win_frac=round(win_kelly_f, 4),
                    kelly_capped=rule.kelly_fraction,  # ルール固有のKelly fraction
                    is_danger=is_danger,
                    danger_score=1.0 if is_danger else 0.0,
                    odds=odds,
                    place_odds_min=e.get('place_odds_min'),
                    ar_deviation=round(ar_dev, 1) if ar_dev is not None else None,
                    market_signal=f'rule:{rule.name}',
                )
                rule_hits.append(rec)

            # max_per_race制約 (win_ev順で優先)
            if rule.max_per_race > 0 and len(rule_hits) > rule.max_per_race:
                rule_hits.sort(key=lambda r: -(r.win_ev or 0))
                rule_hits = rule_hits[:rule.max_per_race]

            race_recs.extend(rule_hits)

        # 重複排除: 同じ馬に複数ルールがマッチした場合、先のルール(優先)を採用
        seen_umabans: set = set()
        deduped: List[BetRecommendation] = []
        for rec in race_recs:
            key = (rec.umaban, rec.bet_type)
            if key not in seen_umabans:
                seen_umabans.add(key)
                deduped.append(rec)
        all_recs.extend(deduped)

    return all_recs


def apply_adaptive_kelly(
    recs: List[BetRecommendation],
    race_predictions: List[dict],
    rules: List[AdaptiveRule] = None,
) -> List[BetRecommendation]:
    """既存ベットリストに adaptive Kelly 率を上書き

    relaxed 等のプリセットで生成されたベットに対して、
    adaptive ルールをマッチングし kelly_capped を上書きする。
    ワイド/馬連等の非単勝ベットはそのまま維持（kelly_capped変更なし）。

    Args:
        recs: generate_recommendations() の出力
        race_predictions: predict出力 (races リスト)
        rules: AdaptiveRuleリスト (None=ADAPTIVE_RULES)

    Returns:
        kelly_capped 上書き済みの BetRecommendation リスト
    """
    if rules is None:
        rules = ADAPTIVE_RULES

    # race_id -> entries マップ
    race_map: Dict[str, List[dict]] = {}
    for race in race_predictions:
        race_map[race['race_id']] = race.get('entries', [])

    # race_id -> context キャッシュ
    ctx_cache: Dict[str, RaceContext] = {}

    result: List[BetRecommendation] = []
    for rec in recs:
        # 単勝以外はそのまま
        if rec.bet_type != '\u5358\u52dd':
            result.append(rec)
            continue

        entries = race_map.get(rec.race_id, [])
        if not entries:
            result.append(rec)
            continue

        # コンテキスト取得
        if rec.race_id not in ctx_cache:
            ctx_cache[rec.race_id] = compute_race_context(entries)
        ctx = ctx_cache[rec.race_id]

        # エントリデータ取得
        entry = next((e for e in entries if e['umaban'] == rec.umaban), None)
        if not entry:
            result.append(rec)
            continue

        # ルールマッチ（優先順）
        matched_rule = None
        rank_w = entry.get('rank_w') or 99
        win_gap = entry.get('win_vb_gap', 0) or 0
        win_ev = entry.get('win_ev')
        margin = entry.get('predicted_margin')
        ar_dev = entry.get('ar_deviation')

        for rule in rules:
            if rule.bet_type != '\u5358\u52dd':
                continue
            # レース条件
            if rule.require_danger is not None:
                if rule.require_danger and not ctx.has_danger:
                    continue
                if not rule.require_danger and ctx.has_danger:
                    continue
            if rule.min_confidence is not None and ctx.confidence < rule.min_confidence:
                continue
            if rule.max_confidence is not None and ctx.confidence > rule.max_confidence:
                continue
            # 馬条件
            if rank_w > rule.max_rank_w:
                continue
            if win_gap < rule.min_win_gap:
                continue
            if rule.min_win_ev > 0 and (win_ev is None or win_ev < rule.min_win_ev):
                continue
            if rule.max_predicted_margin < 999 and margin is not None and margin > rule.max_predicted_margin:
                continue
            if rule.min_ar_deviation > 0 and (ar_dev is None or ar_dev < rule.min_ar_deviation):
                continue
            matched_rule = rule
            break

        if matched_rule:
            rec = BetRecommendation(
                **{**rec.__dict__, 'kelly_capped': matched_rule.kelly_fraction,
                   'market_signal': f'rule:{matched_rule.name}'}
            )
        result.append(rec)

    return result
