#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""セグメント分割 (bin) ユーティリティ

ml/ 配下で散在していたオッズ帯/頭数帯/ARd帯/gap帯/EV帯/距離帯/月別の
ビン分割ロジックを集約。 デフォルトのビン定義は既存スクリプトと一致させる。

analyze_polaris_weakness の odds_band/runner_band/ev_band/gap_band/cs_band と
互換 (ラベル文字列も含む)。
"""

from __future__ import annotations

from typing import Optional, Sequence

import numpy as np

try:
    import pandas as pd
except ImportError:
    pd = None


# ===========================================================================
# Default bin edges & labels
# ===========================================================================

# オッズ帯: analyze_polaris_weakness L76-77 と一致
ODDS_BINS = [0, 3, 5, 10, 20, 50, float("inf")]
ODDS_LABELS = ["~3.0", "3.1~5.0", "5.1~10", "10.1~20", "20.1~50", "50+"]

# 頭数帯: analyze_polaris_weakness L236-237 と一致
RUNNER_BINS = [0, 8, 12, 16, 99]
RUNNER_LABELS = ["~8頭", "9-12頭", "13-16頭", "17頭~"]

# Value Bet ギャップ帯: analyze_polaris_weakness L368-369 と一致
GAP_BINS = [0, 2, 4, 6, 8, 99]
GAP_LABELS = ["1-2", "3-4", "5-6", "7-8", "9+"]

# EV 帯: analyze_polaris_weakness L338-339 と一致
EV_BINS = [0, 0.5, 0.8, 1.0, 1.3, 1.5, 2.0, 99]
EV_LABELS = ["<0.5", "0.5-0.8", "0.8-1.0", "1.0-1.3", "1.3-1.5", "1.5-2.0", "2.0+"]

# Closing Strength 帯: analyze_polaris_weakness L398-399 と一致
CS_BINS = [0, 0.5, 1.0, 1.5, 2.0, 99]
CS_LABELS = ["~0.5", "0.5-1.0", "1.0-1.5", "1.5-2.0", "2.0+"]

# 距離帯 (1段階細かい — Section 12.3 補完項)
DISTANCE_BINS = [0, 1200, 1400, 1600, 1800, 2000, 2200, 2400, 9999]
DISTANCE_LABELS = [
    "~1200", "1300-1400", "1500-1600", "1700-1800",
    "1900-2000", "2100-2200", "2300-2400", "2500+",
]

# AR Deviation 帯
ARD_BINS = [-99, -2, -1, 0, 1, 2, 99]
ARD_LABELS = ["~-2", "-2~-1", "-1~0", "0~1", "1~2", "2+"]

# Novelty スコア帯 (analyze_novelty 由来; 連続値だが帯化)
NOVELTY_BINS = [-1, 0, 1, 2, 3, 4, 5, 99]
NOVELTY_LABELS = ["0", "1", "2", "3", "4", "5", "6+"]

# Model 信頼度 (conf_gap)
CONFIDENCE_BINS = [-99, 0, 0.05, 0.10, 0.15, 0.20, 99]
CONFIDENCE_LABELS = ["~0", "0~0.05", "0.05~0.10", "0.10~0.15", "0.15~0.20", "0.20+"]


# ===========================================================================
# Binning helpers
# ===========================================================================

def _cut(values, bins, labels):
    """pd.cut の薄いラッパー — pandas 未インストール時は ImportError"""
    if pd is None:
        raise ImportError("pandas is required for segment binning")
    return pd.cut(values, bins=bins, labels=labels, right=True, include_lowest=True)


def bin_odds(values, bins: Optional[Sequence] = None, labels: Optional[Sequence] = None):
    """オッズを帯にビン化 (~3.0 / 3.1~5.0 / 5.1~10 / 10.1~20 / 20.1~50 / 50+)"""
    return _cut(values, bins or ODDS_BINS, labels or ODDS_LABELS)


def bin_runners(values, bins: Optional[Sequence] = None, labels: Optional[Sequence] = None):
    """頭数を帯にビン化 (~8頭 / 9-12頭 / 13-16頭 / 17頭~)"""
    return _cut(values, bins or RUNNER_BINS, labels or RUNNER_LABELS)


def bin_gap(values, bins: Optional[Sequence] = None, labels: Optional[Sequence] = None):
    """Value Bet ギャップを帯にビン化 (1-2 / 3-4 / 5-6 / 7-8 / 9+)"""
    return _cut(values, bins or GAP_BINS, labels or GAP_LABELS)


def bin_ev(values, bins: Optional[Sequence] = None, labels: Optional[Sequence] = None):
    """EV を帯にビン化 (<0.5 / 0.5-0.8 / 0.8-1.0 / 1.0-1.3 / 1.3-1.5 / 1.5-2.0 / 2.0+)"""
    return _cut(values, bins or EV_BINS, labels or EV_LABELS)


def bin_closing_strength(values, bins: Optional[Sequence] = None, labels: Optional[Sequence] = None):
    """末脚力スコアを帯にビン化"""
    return _cut(values, bins or CS_BINS, labels or CS_LABELS)


def bin_distance(values, bins: Optional[Sequence] = None, labels: Optional[Sequence] = None):
    """距離を帯にビン化 (~1200 / 1300-1400 / 1500-1600 / .../ 2500+)"""
    return _cut(values, bins or DISTANCE_BINS, labels or DISTANCE_LABELS)


def bin_ard(values, bins: Optional[Sequence] = None, labels: Optional[Sequence] = None):
    """AR Deviation を帯にビン化"""
    return _cut(values, bins or ARD_BINS, labels or ARD_LABELS)


def bin_novelty(values, bins: Optional[Sequence] = None, labels: Optional[Sequence] = None):
    """Novelty スコアを帯にビン化"""
    return _cut(values, bins or NOVELTY_BINS, labels or NOVELTY_LABELS)


def bin_confidence(values, bins: Optional[Sequence] = None, labels: Optional[Sequence] = None):
    """モデル信頼度 (conf_gap) を帯にビン化"""
    return _cut(values, bins or CONFIDENCE_BINS, labels or CONFIDENCE_LABELS)


# ===========================================================================
# Date / month / race-attr utilities
# ===========================================================================

def race_id_to_date(race_id: str) -> str:
    """race_id 16桁 (YYYYMMDDJJKKNNRR) → 'YYYY-MM-DD'"""
    rid = str(race_id)
    if len(rid) < 8:
        return ""
    return f"{rid[:4]}-{rid[4:6]}-{rid[6:8]}"


def race_id_to_month(race_id: str) -> str:
    """race_id → 'YYYY-MM'"""
    rid = str(race_id)
    if len(rid) < 6:
        return ""
    return f"{rid[:4]}-{rid[4:6]}"


def bin_month(dates):
    """date 列 (YYYY-MM-DD 文字列) → 月 (YYYY-MM) 列"""
    if pd is None:
        raise ImportError("pandas is required for bin_month")
    return pd.Series(dates).astype(str).str[:7]


# ===========================================================================
# Race attribute helpers
# ===========================================================================

_HANDICAP_KEYWORDS = ("ハンデ", "HC", "handicap", "ハンディ")


def is_handicap(race: dict) -> bool:
    """ハンデ戦かどうか判定

    判定基準:
        - race['weight_type'] == 'ハンデ' / 'handicap'
        - race['race_name'] / race['race_subname'] に 'ハンデ' / 'HC' 含む
    """
    if not isinstance(race, dict):
        return False
    wt = (race.get("weight_type") or "").lower()
    if "handicap" in wt or "ハンデ" in (race.get("weight_type") or ""):
        return True
    for key in ("race_name", "race_subname", "subtitle"):
        text = race.get(key) or ""
        for kw in _HANDICAP_KEYWORDS:
            if kw.lower() in text.lower():
                return True
    return False
