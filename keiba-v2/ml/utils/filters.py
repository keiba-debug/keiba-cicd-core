#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""障害レース除外/最小サンプル/win_only/selective フィルタ

ml/ 配下で散在していた以下のロジックを集約:
- track_type == 'obstacle' / '障害' / race_name に "障" 含む の除外
- 最小サンプル数チェック (n<30 で警告)
- monthly_analysis.filter_win_only / filter_selective
"""

from __future__ import annotations

from typing import Iterable, List

try:
    import pandas as pd
except ImportError:
    pd = None


# ===========================================================================
# Obstacle race detection
# ===========================================================================

_OBSTACLE_TRACK_VALUES = {"obstacle", "障害", "steeplechase"}


def is_obstacle(race: dict) -> bool:
    """レースが障害かどうか判定

    判定基準 (どれか1つ満たせば障害扱い):
        - race['track_type'] が 'obstacle' / '障害'
        - race['race_name'] に '障' を含む
    """
    if not isinstance(race, dict):
        return False
    if race.get("track_type") in _OBSTACLE_TRACK_VALUES:
        return True
    if "障" in (race.get("race_name") or ""):
        return True
    return False


def exclude_obstacle(races: Iterable[dict]) -> List[dict]:
    """障害レースを除外したリストを返す"""
    return [r for r in races if not is_obstacle(r)]


def split_by_obstacle(races: Iterable[dict]) -> tuple[List[dict], List[dict]]:
    """(flat, obstacle) に分割"""
    flat, obs = [], []
    for r in races:
        (obs if is_obstacle(r) else flat).append(r)
    return flat, obs


# ===========================================================================
# Sample size
# ===========================================================================

MIN_SAMPLE_DEFAULT = 30


def has_min_samples(n: int, threshold: int = MIN_SAMPLE_DEFAULT) -> bool:
    """サンプル数が閾値以上か"""
    return n >= threshold


def sample_size_marker(n: int, threshold: int = MIN_SAMPLE_DEFAULT) -> str:
    """サンプル数に応じた警告マーカー文字列を返す

    - n >= threshold → ''
    - n >= threshold/3 → ' [低サンプル]'
    - n < threshold/3 → ' [要警戒]'
    """
    if n >= threshold:
        return ""
    if n >= threshold // 3:
        return " [低サンプル]"
    return " [要警戒]"


# ===========================================================================
# Strategy filters (monthly_analysis 由来)
# ===========================================================================

def filter_win_only(df, min_gap: float = 5, min_ability: float = -1.2):
    """単勝のみ条件でフィルタ

    条件: pred_rank_w <= 3 AND win_gap >= min_gap
          AND margin >= min_ability AND odds > 0
    """
    if pd is None:
        raise ImportError("pandas is required for filter_win_only")
    mask = (
        (df["pred_rank_w"] <= 3)
        & (df["win_gap"] >= min_gap)
        & (df["margin"] >= min_ability)
        & (df["odds"] > 0)
    )
    return df[mask].copy()


def filter_selective(
    df,
    min_gap: float = 6,
    min_ev: float = 1.2,
    min_ability: float = -0.8,
):
    """selective 条件でフィルタ

    条件: pred_rank_w <= 3 AND win_gap >= min_gap
          AND win_ev >= min_ev AND margin >= min_ability AND odds > 0
    """
    if pd is None:
        raise ImportError("pandas is required for filter_selective")
    mask = (
        (df["pred_rank_w"] <= 3)
        & (df["win_gap"] >= min_gap)
        & (df["win_ev"] >= min_ev)
        & (df["margin"] >= min_ability)
        & (df["odds"] > 0)
    )
    return df[mask].copy()
