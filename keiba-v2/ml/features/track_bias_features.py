#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
トラックバイアス × 前崩れ特徴量

KAA (馬場状態) + SED (コーナー通過順/着順) から:
  A. 当日バイアス特徴量 (レースレベル / Closingモデル + P/W/ARモデル共通)
  B. 過去走バイアス補正 (馬レベル / P/W/ARモデル) — IDM補正は将来Phase

データフロー:
  KAA index ({venue_code}_{race_date}) → 当日の馬場状態
  SED index ({ketto_num}_{race_date}) → 過去走のペース/コーナー通過順

特徴量カテゴリ:
  A. 当日トラックバイアス (KAA由来, 6個)
     - kaa_turf_bias: 芝内外差 (turf_inner - turf_outer, 正=外差し有利)
     - kaa_turf_inner: 芝内回り状態 (1-4, 4=荒れ)
     - kaa_straight_bias: 直線馬場差 (inner系 - outer系, 正=外有利)
     - kaa_is_outer_bias: 外差しバイアスフラグ (inner>=3 & outer<=2)
     - kaa_dirt_bias: ダート内外差 (dirt_inner - dirt_outer)
     - kaa_surface_condition: 走路面のコンディション (1-4)

  B. 過去走前崩れ経験 (SED由来, 馬レベル, 5個)
     - pace_collapse_exp_last5: 過去5走の前崩れレース数
     - pace_collapse_benefit_last5: 前崩れで好走した回数 (差し・追込で3着以内)
     - avg_corner4_ratio_last3: 最近3走の4角通過順位比率 (平均)
     - high_pace_exp_last5: 過去5走のHペースレース数
     - bias_race_exp_last5: 過去5走で外差しバイアスレースに出た回数
"""

from typing import Dict, List, Optional


# === 特徴量名リスト ===

# 当日バイアス (KAA由来) — レース共通
TRACK_BIAS_RACE_FEATURES = [
    'kaa_turf_bias',
    'kaa_turf_inner',
    'kaa_straight_bias',
    'kaa_is_outer_bias',
    'kaa_dirt_bias',
    'kaa_surface_condition',
]

# 過去走前崩れ経験 (SED由来) — 馬レベル
TRACK_BIAS_HORSE_FEATURES = [
    'pace_collapse_exp_last5',
    'pace_collapse_benefit_last5',
    'avg_corner4_ratio_last3',
    'high_pace_exp_last5',
    'bias_race_exp_last5',
]

# 全特徴量名 (experiment.pyで参照)
TRACK_BIAS_FEATURE_COLS = TRACK_BIAS_RACE_FEATURES + TRACK_BIAS_HORSE_FEATURES


def _is_pace_collapse(sed_entry: dict) -> bool:
    """前崩れ判定: 4角3番手以内の馬の着順が頭数/2より大きい

    個別馬レベルでは: この馬が4角3番手以内 & 着順が頭数/2以下でなかった = 前崩れに巻き込まれた
    レースレベルでは: 全馬の4角3番手以内の平均着順 > 頭数/2

    ここでは個別馬の「前崩れレース経験」を判定するため、
    レースペースがHかつ、この馬が先行していた(corner4 <= 3)のに着順が半分以下だった場合。
    ただし、pace=Hだけでも前崩れ経験としてカウント。
    """
    race_pace = sed_entry.get('race_pace', '')
    return race_pace == 'H'


def _is_outer_bias_race(kaa_entry: dict, track_type: str) -> bool:
    """外差しバイアスレース判定

    芝: turf_inner >= 3 and turf_outer <= 2
    ダート: dirt_inner >= 3 and dirt_outer <= 2
    """
    if track_type == 'turf':
        inner = kaa_entry.get('turf_inner', 0)
        outer = kaa_entry.get('turf_outer', 0)
    else:
        inner = kaa_entry.get('dirt_inner', 0)
        outer = kaa_entry.get('dirt_outer', 0)
    return inner >= 3 and outer <= 2


def compute_race_bias_features(
    race_id: str,
    race_date: str,
    track_type: str,
    kaa_index: dict,
) -> dict:
    """当日のトラックバイアス特徴量を計算 (KAA由来)

    Args:
        race_id: 16桁レースID
        race_date: YYYY-MM-DD形式
        track_type: 'turf' or 'dirt'
        kaa_index: jrdb_kaa_index.json のデータ

    Returns:
        dict: TRACK_BIAS_RACE_FEATURES の値
    """
    result = {
        'kaa_turf_bias': -1,
        'kaa_turf_inner': -1,
        'kaa_straight_bias': -1,
        'kaa_is_outer_bias': 0,
        'kaa_dirt_bias': -1,
        'kaa_surface_condition': -1,
    }

    if not race_id or len(race_id) < 16 or not kaa_index:
        return result

    venue_code = race_id[8:10]
    kaa_key = f"{venue_code}_{race_date}"
    kaa = kaa_index.get(kaa_key)
    if not kaa:
        return result

    # 芝バイアス
    turf_inner = kaa.get('turf_inner', 0)
    turf_outer = kaa.get('turf_outer', 0)
    if turf_inner > 0 and turf_outer > 0:
        result['kaa_turf_bias'] = turf_inner - turf_outer
        result['kaa_turf_inner'] = turf_inner

    # 直線バイアス
    s_innermost = kaa.get('straight_innermost', 0)
    s_inner = kaa.get('straight_inner', 0)
    s_outer = kaa.get('straight_outer', 0)
    s_outermost = kaa.get('straight_outermost', 0)
    inner_avg = (s_innermost + s_inner) / 2 if (s_innermost + s_inner) > 0 else 0
    outer_avg = (s_outer + s_outermost) / 2 if (s_outer + s_outermost) > 0 else 0
    if inner_avg > 0 or outer_avg > 0:
        result['kaa_straight_bias'] = round(inner_avg - outer_avg, 1)

    # 外差しバイアスフラグ
    result['kaa_is_outer_bias'] = 1 if _is_outer_bias_race(kaa, track_type) else 0

    # ダートバイアス
    dirt_inner = kaa.get('dirt_inner', 0)
    dirt_outer = kaa.get('dirt_outer', 0)
    if dirt_inner > 0 and dirt_outer > 0:
        result['kaa_dirt_bias'] = dirt_inner - dirt_outer

    # 走路面コンディション
    if track_type == 'turf':
        result['kaa_surface_condition'] = kaa.get('turf_condition_code', -1)
    else:
        result['kaa_surface_condition'] = kaa.get('dirt_condition_code', -1)

    return result


def compute_horse_bias_features(
    ketto_num: str,
    race_date: str,
    sed_index: dict,
    kaa_index: dict,
    history_cache: dict,
) -> dict:
    """馬の過去走トラックバイアス/前崩れ経験を計算 (SED + KAA由来)

    Args:
        ketto_num: 10桁馬ID
        race_date: 当該レースの日付 (YYYY-MM-DD)
        sed_index: jrdb_sed_index.json のデータ
        kaa_index: jrdb_kaa_index.json のデータ
        history_cache: 過去走履歴キャッシュ

    Returns:
        dict: TRACK_BIAS_HORSE_FEATURES の値
    """
    result = {
        'pace_collapse_exp_last5': 0,
        'pace_collapse_benefit_last5': 0,
        'avg_corner4_ratio_last3': -1.0,
        'high_pace_exp_last5': 0,
        'bias_race_exp_last5': 0,
    }

    if not ketto_num or not sed_index:
        return result

    # 過去走のSEDエントリを収集 (race_date以前のもの)
    past_sed_entries = []
    horse_data = history_cache.get(ketto_num, [])
    # history_cache: {ketto_num: [過去走リスト]}
    past_races = horse_data if isinstance(horse_data, list) else horse_data.get('past_races', [])

    for pr in past_races:
        pr_date = pr.get('race_date', '')
        if not pr_date or pr_date >= race_date:
            continue

        sed_key = f"{ketto_num}_{pr_date}"
        sed_entry = sed_index.get(sed_key)
        if sed_entry:
            past_sed_entries.append(sed_entry)

    if not past_sed_entries:
        return result

    # 日付降順でソート (最新が先頭)
    past_sed_entries.sort(key=lambda x: x.get('race_date', ''), reverse=True)

    # last5
    last5 = past_sed_entries[:5]
    last3 = past_sed_entries[:3]

    # 前崩れ経験 (Hペースレース)
    pace_collapse_count = 0
    benefit_count = 0
    high_pace_count = 0

    for entry in last5:
        race_pace = entry.get('race_pace', '')
        corner4 = entry.get('corner4', 0)
        fp = entry.get('finish_position', 0)
        num_runners = entry.get('num_runners', 0)

        if race_pace == 'H':
            high_pace_count += 1
            # 前崩れ: Hペースで先行(corner4 <= num_runners/3)
            if corner4 > 0 and num_runners > 0 and corner4 <= num_runners / 3:
                pace_collapse_count += 1
            # 前崩れ恩恵: Hペースで後方から好走
            if corner4 > 0 and num_runners > 0 and corner4 > num_runners / 2 and fp <= 3:
                benefit_count += 1

    result['pace_collapse_exp_last5'] = pace_collapse_count
    result['pace_collapse_benefit_last5'] = benefit_count
    result['high_pace_exp_last5'] = high_pace_count

    # 4角通過順位比率 (last3の平均)
    corner4_ratios = []
    for entry in last3:
        corner4 = entry.get('corner4', 0)
        num_runners = entry.get('num_runners', 0)
        if corner4 > 0 and num_runners > 0:
            corner4_ratios.append(corner4 / num_runners)

    if corner4_ratios:
        result['avg_corner4_ratio_last3'] = round(
            sum(corner4_ratios) / len(corner4_ratios), 4
        )

    # 外差しバイアスレース経験
    bias_count = 0
    for entry in last5:
        entry_date = entry.get('race_date', '')
        entry_venue = entry.get('venue_code', '')
        if not entry_date or not entry_venue:
            continue

        kaa_key = f"{entry_venue:>02}_{entry_date}"
        kaa = kaa_index.get(kaa_key)
        if not kaa:
            continue

        # track_codeからtrack_typeを判定 (1=芝, 2=ダート)
        track_code = entry.get('track_code', 0)
        entry_track_type = 'turf' if track_code == 1 else 'dirt'

        if _is_outer_bias_race(kaa, entry_track_type):
            bias_count += 1

    result['bias_race_exp_last5'] = bias_count

    return result
