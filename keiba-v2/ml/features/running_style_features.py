#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
脚質特徴量

horse_history_cacheのcornersフィールドから脚質パターンを計算。
"""

import numpy as np
from typing import List


def compute_running_style_features(
    ketto_num: str,
    race_date: str,
    entry_count: int,
    history_cache: dict,
) -> dict:
    """
    脚質関連の特徴量を計算。

    corners: [5, 5, 3] のような配列（各コーナーでの通過順位）
    corners[0] = 最初のコーナー, corners[-1] = 最終コーナー
    """
    result = {
        'avg_first_corner_ratio': -1,
        'avg_last_corner_ratio': -1,
        'position_gain_last5': -1,
        'front_runner_rate': -1,
        'pace_sensitivity': -1,
        'closing_strength': -1,
        'running_style_consistency': -1,
        'last_race_corner1_ratio': -1,
    }

    runs = history_cache.get(ketto_num, [])
    if not runs:
        return result

    past = [r for r in runs if r['race_date'] < race_date]
    if not past:
        return result

    # cornersが有効な走のみ
    valid = [r for r in past if r.get('corners') and len(r['corners']) > 0 and r.get('num_runners', 0) > 0]
    if not valid:
        return result

    last5 = valid[-5:]
    last3 = valid[-3:]

    # avg_first_corner_ratio: 直近5走の corners[0]/num_runners 平均
    fc_ratios = [r['corners'][0] / r['num_runners'] for r in last5]
    result['avg_first_corner_ratio'] = round(np.mean(fc_ratios), 4)

    # avg_last_corner_ratio: 直近5走の corners[-1]/num_runners 平均
    lc_ratios = [r['corners'][-1] / r['num_runners'] for r in last5]
    result['avg_last_corner_ratio'] = round(np.mean(lc_ratios), 4)

    # position_gain_last5: (corners[0] - finish) / num_runners 平均
    gains = []
    for r in last5:
        fp = r.get('finish_position', 0)
        if fp > 0:
            gains.append((r['corners'][0] - fp) / r['num_runners'])
    if gains:
        result['position_gain_last5'] = round(np.mean(gains), 4)

    # front_runner_rate: 直近5走で corners[0] <= 3 の割合
    front_count = sum(1 for r in last5 if r['corners'][0] <= 3)
    result['front_runner_rate'] = round(front_count / len(last5), 4)

    # pace_sensitivity: 先行時(corners[0]<=3) vs 非先行時の着順差
    front_positions = [r['finish_position'] for r in valid if r['corners'][0] <= 3 and r['finish_position'] > 0]
    back_positions = [r['finish_position'] for r in valid if r['corners'][0] > 3 and r['finish_position'] > 0]
    if front_positions and back_positions:
        result['pace_sensitivity'] = round(np.mean(back_positions) - np.mean(front_positions), 2)

    # closing_strength: 直近3走の (最終corner順位 - finish) 平均
    close_vals = []
    for r in last3:
        fp = r.get('finish_position', 0)
        if fp > 0:
            close_vals.append(r['corners'][-1] - fp)
    if close_vals:
        result['closing_strength'] = round(np.mean(close_vals), 2)

    # running_style_consistency: corners[0]/num_runners の標準偏差
    if len(fc_ratios) >= 2:
        result['running_style_consistency'] = round(float(np.std(fc_ratios)), 4)

    # last_race_corner1_ratio: 前走の corners[0]/num_runners
    last = valid[-1]
    result['last_race_corner1_ratio'] = round(last['corners'][0] / last['num_runners'], 4)

    return result
