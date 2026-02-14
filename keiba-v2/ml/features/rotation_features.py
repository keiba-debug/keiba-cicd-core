#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ローテーション・コンディション特徴量

斤量変化、馬体重変化、前走人気など。

v4.0: jockey_change (騎手乗り替わりフラグ) を追加
"""


def compute_rotation_features(
    ketto_num: str,
    race_date: str,
    futan: float,
    horse_weight: int,
    popularity: int,
    jockey_code: str,
    history_cache: dict,
) -> dict:
    """
    ローテーション・コンディション関連の特徴量を計算。

    注意: popularity_trend は MARKET特徴量 → Model Bでは除外。
    """
    result = {
        'futan_diff': -1,
        'futan_diff_ratio': -1,
        'weight_change_ratio': -1,
        'prev_race_popularity': -1,
        'popularity_trend': -1,  # MARKET特徴量
        'jockey_change': None,  # v4.0: 騎手乗り替わり
    }

    runs = history_cache.get(ketto_num, [])
    if not runs:
        return result

    past = [r for r in runs if r['race_date'] < race_date]
    if not past:
        return result

    last = past[-1]

    # futan_diff: 今走斤量 - 前走斤量
    prev_futan = last.get('futan', 0)
    if futan > 0 and prev_futan > 0:
        result['futan_diff'] = round(futan - prev_futan, 1)
        result['futan_diff_ratio'] = round((futan - prev_futan) / prev_futan, 4)

    # weight_change_ratio: (今走馬体重 - 前走馬体重) / 前走馬体重
    prev_weight = last.get('horse_weight', 0)
    if horse_weight > 0 and prev_weight > 0:
        result['weight_change_ratio'] = round((horse_weight - prev_weight) / prev_weight, 4)

    # prev_race_popularity: 前走の人気順
    prev_pop = last.get('popularity', 0)
    if prev_pop > 0:
        result['prev_race_popularity'] = prev_pop

    # popularity_trend: 今走人気 - 前走人気 (正=人気落ち)
    if popularity > 0 and prev_pop > 0:
        result['popularity_trend'] = popularity - prev_pop

    # jockey_change: 騎手乗り替わり (v4.0)
    prev_jockey = last.get('jockey_code', '')
    if jockey_code and prev_jockey:
        result['jockey_change'] = 0 if jockey_code == prev_jockey else 1

    return result
