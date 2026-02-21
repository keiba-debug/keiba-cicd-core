#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
着差回帰ターゲット計算ユーティリティ

race JSONのtimeフィールド(M:SS.T形式)から着差(time_behind_winner)を計算する。
experiment_regression.py と predict.py の両方から共有利用。

Phase 1: 走破タイムベース (0.1s精度)
  - 同タイムは着順×0.02sオフセットで区別
  - 5.0s上限キャップ (外れ値抑制)
  - 取消・除外(finish_position=0)はNaN

Phase 2 (将来): CHAKUSA_CODEベースでsub-0.1s区別
"""

import math
from typing import Dict, Optional

import numpy as np


def parse_time_str(time_str: str) -> float:
    """走破タイム文字列 "M:SS.T" を秒に変換

    Args:
        time_str: "1:34.5" や "0:58.2" 形式

    Returns:
        秒数 (float)。パース失敗時は NaN
    """
    if not time_str or not isinstance(time_str, str):
        return float('nan')
    try:
        if ':' in time_str:
            parts = time_str.split(':')
            minutes = int(parts[0])
            seconds = float(parts[1])
            return minutes * 60 + seconds
        else:
            return float(time_str)
    except (ValueError, IndexError):
        return float('nan')


def compute_race_margins(
    entries: list,
    cap: float = 5.0,
    same_time_offset: float = 0.02,
) -> Dict[int, float]:
    """1レースの全出走馬のtime_behind_winnerを計算

    Args:
        entries: race JSON の entries リスト
        cap: 着差上限秒数 (これを超える着差はcapで丸める)
        same_time_offset: 同タイム馬の着順差×offset で区別

    Returns:
        dict: {umaban: target_margin}
              1着 = 0.0, 取消/除外/タイムなし = NaN
    """
    # 着順・タイムを収集
    valid_entries = []
    for e in entries:
        fp = e.get('finish_position', 0)
        if fp <= 0:
            continue
        time_sec = parse_time_str(e.get('time', ''))
        valid_entries.append({
            'umaban': e.get('umaban', 0),
            'finish_position': fp,
            'time_sec': time_sec,
        })

    if not valid_entries:
        return {}

    # 1着馬のタイムを特定
    valid_entries.sort(key=lambda x: x['finish_position'])
    winner_time = float('nan')
    for ve in valid_entries:
        if ve['finish_position'] == 1 and not math.isnan(ve['time_sec']):
            winner_time = ve['time_sec']
            break

    if math.isnan(winner_time):
        return {}

    # 着差を計算
    result = {}
    for ve in valid_entries:
        umaban = ve['umaban']
        fp = ve['finish_position']
        time_sec = ve['time_sec']

        if math.isnan(time_sec):
            result[umaban] = float('nan')
            continue

        if fp == 1:
            result[umaban] = 0.0
            continue

        raw_margin = time_sec - winner_time

        # 同タイムの馬を着順で微細に区別
        # (0.1s精度 → 着順差 × 0.02s で sub-0.1s 差をつける)
        if raw_margin >= 0:
            # 同タイムグループ内の着順オフセット
            # 同じ raw_margin を持つ馬の中で、着順が後ろの馬ほどわずかに大きい値にする
            margin = raw_margin + (fp - 2) * same_time_offset * 0.1
            # ただし、raw_margin自体を超える量のオフセットはつけない
            # (次のタイム帯に食い込まないようにする)
            margin = max(margin, raw_margin)
        else:
            # タイム差がマイナス（まれ: 1着のタイムが遅い異常データ）
            margin = 0.0

        # キャップ適用
        margin = min(margin, cap)
        result[umaban] = round(margin, 3)

    return result


def add_margin_target_to_df(
    df,
    date_index: dict,
    load_race_fn,
    cap: float = 5.0,
) -> None:
    """DataFrameにtarget_marginカラムを追加 (in-place)

    Args:
        df: build_dataset()の出力DataFrame (race_id, umaban カラムが必要)
        date_index: race_date_index
        load_race_fn: load_race_json関数
        cap: 着差上限
    """
    from ml.experiment import _iter_date_index

    # race_id → date_str のマッピングを構築
    race_date_map = {}
    for date_str, race_id in _iter_date_index(date_index):
        race_date_map[race_id] = date_str

    # レースごとにmarginを計算
    margin_index = {}  # (race_id, umaban) -> margin
    processed = 0
    errors = 0

    unique_race_ids = df['race_id'].unique()
    for race_id in unique_race_ids:
        date_str = race_date_map.get(race_id)
        if not date_str:
            errors += 1
            continue
        try:
            race = load_race_fn(race_id, date_str)
            margins = compute_race_margins(race.get('entries', []), cap=cap)
            for umaban, margin in margins.items():
                margin_index[(race_id, umaban)] = margin
            processed += 1
        except Exception:
            errors += 1

    # DataFrameにマッピング
    df['target_margin'] = df.apply(
        lambda row: margin_index.get((row['race_id'], row['umaban']), float('nan')),
        axis=1,
    )

    valid = df['target_margin'].notna().sum()
    total = len(df)
    print(f"[Margin] {processed:,} races processed, {errors} errors")
    print(f"[Margin] target_margin: {valid:,}/{total:,} valid ({valid/total*100:.1f}%)")
