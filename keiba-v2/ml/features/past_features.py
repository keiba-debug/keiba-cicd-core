#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
過去走成績特徴量

horse_history_cache.jsonから馬の過去走成績を計算。
v2のcompute_past_features()を移植・拡張。
"""

from typing import Dict, List, Optional


def compute_past_features(
    ketto_num: str,
    race_date: str,
    venue_code: str,
    track_type: str,  # "turf" or "dirt"
    distance: int,
    entry_count: int,
    history_cache: dict,
) -> dict:
    """
    馬の過去走成績から特徴量を計算。

    時系列リーク防止: race_date より前のレースのみ使用。
    """
    result = {
        'avg_finish_last3': -1,
        'best_finish_last5': -1,
        'last3f_avg_last3': -1,
        'days_since_last_race': -1,
        'win_rate_all': -1,
        'top3_rate_all': -1,
        'total_career_races': 0,
        'recent_form_trend': -1,
        'venue_top3_rate': -1,
        'track_type_top3_rate': -1,
        'distance_fitness': -1,
        'prev_race_entry_count': -1,
        'entry_count_change': -1,
    }

    runs = history_cache.get(ketto_num, [])
    if not runs:
        return result

    # 時系列フィルタ: race_date より前の走歴のみ
    past = [r for r in runs if r['race_date'] < race_date]
    if not past:
        return result

    result['total_career_races'] = len(past)

    # 直近N走
    last3 = past[-3:]
    last5 = past[-5:]

    # 平均着順（直近3走）
    positions_3 = [r['finish_position'] for r in last3 if r['finish_position'] > 0]
    if positions_3:
        result['avg_finish_last3'] = round(sum(positions_3) / len(positions_3), 2)

    # 最高着順（直近5走）
    positions_5 = [r['finish_position'] for r in last5 if r['finish_position'] > 0]
    if positions_5:
        result['best_finish_last5'] = min(positions_5)

    # 上がり3F平均（直近3走）
    l3f = [r['last_3f'] for r in last3 if r.get('last_3f', 0) > 0]
    if l3f:
        result['last3f_avg_last3'] = round(sum(l3f) / len(l3f), 1)

    # 前走からの間隔（日数）
    from datetime import datetime
    try:
        last_date = datetime.strptime(past[-1]['race_date'], '%Y-%m-%d')
        current_date = datetime.strptime(race_date, '%Y-%m-%d')
        result['days_since_last_race'] = (current_date - last_date).days
    except (ValueError, KeyError):
        pass

    # 通算成績
    total = len(past)
    wins = sum(1 for r in past if r['finish_position'] == 1)
    top3 = sum(1 for r in past if 1 <= r['finish_position'] <= 3)
    result['win_rate_all'] = round(wins / total, 4) if total > 0 else 0
    result['top3_rate_all'] = round(top3 / total, 4) if total > 0 else 0

    # 近走トレンド（正=上昇傾向）
    if len(positions_3) >= 2:
        result['recent_form_trend'] = positions_3[0] - positions_3[-1]

    # 場所別成績
    track_type_int = 0 if track_type == 'turf' else 1
    venue_runs = [r for r in past if r.get('venue_code') == venue_code]
    if venue_runs:
        v_top3 = sum(1 for r in venue_runs if 1 <= r['finish_position'] <= 3)
        result['venue_top3_rate'] = round(v_top3 / len(venue_runs), 4)

    # トラックタイプ別成績
    tt_key = 'turf' if track_type_int == 0 else 'dirt'
    tt_runs = [r for r in past if r.get('track_type') == tt_key]
    if tt_runs:
        t_top3 = sum(1 for r in tt_runs if 1 <= r['finish_position'] <= 3)
        result['track_type_top3_rate'] = round(t_top3 / len(tt_runs), 4)

    # 距離適性（±200m）
    dist_runs = [r for r in past if abs(r.get('distance', 0) - distance) <= 200]
    if dist_runs:
        d_top3 = sum(1 for r in dist_runs if 1 <= r['finish_position'] <= 3)
        result['distance_fitness'] = round(d_top3 / len(dist_runs), 4)

    # 前走出走頭数・変化
    last_race = past[-1]
    prev_ec = last_race.get('num_runners', 0)
    if prev_ec > 0:
        result['prev_race_entry_count'] = prev_ec
        result['entry_count_change'] = entry_count - prev_ec

    return result
