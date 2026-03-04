#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
障害レース専用特徴量

1. obstacle_experience: 当該馬の障害戦出走回数（0=初障害）
2. jockey_selected: 騎手選択シグナル
3. obstacle_level: コース難易度 (10-53)
4. obstacle_exp_tier: 障害経験ビン (0=初,1=1-3,2=4-10,3=11+)
5. prev_was_obstacle: 前走が障害だったか
6. jockey_obstacle_races / jockey_obstacle_win_rate: 騎手の障害成績 (PIT-safe)
7. trainer_obstacle_top3_rate: 調教師の障害好走率 (PIT-safe)
8. difficulty_exp_match: 当該難易度帯での経験度
"""

from collections import defaultdict
from typing import Dict, List, Tuple

# ── コース難易度テーブル (web UI obstacle analysis page由来) ──
# Key: (venue_name, distance, surface) → difficulty level (10-53)
OBSTACLE_LEVEL_TABLE: Dict[Tuple[str, int, str], int] = {
    # 京都 (最高難度)
    ('京都', 3930, '芝'): 53, ('京都', 3170, '芝'): 44,
    ('京都', 3170, 'ダ'): 43, ('京都', 2910, 'ダ'): 36,
    # 阪神
    ('阪神', 3900, '芝'): 40, ('阪神', 3140, '芝'): 34,
    ('阪神', 3110, 'ダ'): 34, ('阪神', 2970, 'ダ'): 33,
    # 中山
    ('中山', 4250, '芝'): 37, ('中山', 4100, '芝'): 35,
    ('中山', 3570, '芝'): 34, ('中山', 3560, '芝'): 33,
    ('中山', 3200, 'ダ'): 31, ('中山', 3210, '芝'): 31,
    ('中山', 2880, 'ダ'): 21,
    # 東京
    ('東京', 3110, '芝'): 29, ('東京', 3000, 'ダ'): 28,
    ('東京', 3100, 'ダ'): 28,
    # 小倉
    ('小倉', 3390, '芝'): 27, ('小倉', 2860, '芝'): 24,
    # 中京
    ('中京', 3300, '芝'): 25, ('中京', 3330, '芝'): 25,
    ('中京', 3000, '芝'): 23,
    # 新潟
    ('新潟', 3250, '芝'): 22, ('新潟', 3290, '芝'): 22,
    ('新潟', 2850, '芝'): 18, ('新潟', 2890, '芝'): 18,
    # 福島
    ('福島', 3350, '芝'): 19, ('福島', 3380, '芝'): 19,
    ('福島', 2750, '芝'): 15, ('福島', 2770, '芝'): 15,
}

# 会場別のデフォルト難易度（テーブルにないコース用）
_VENUE_DEFAULT_LEVEL = {
    '京都': 44, '阪神': 35, '中山': 33, '東京': 28,
    '小倉': 25, '中京': 24, '新潟': 20, '福島': 17,
}


def compute_obstacle_level(
    venue_name: str,
    distance: int,
    track_type_raw: str,
) -> int:
    """コース難易度レベルを返す (10-53)

    Args:
        venue_name: 会場名（京都, 中山, etc.）
        distance: 距離(m)
        track_type_raw: 'turf'/'dirt'/'obstacle' — 障害は芝ベースだが
                        一部ダートコースあり。surfaceは距離+会場で判定。
    """
    # 障害レースのsurface判定: テーブルを芝/ダ両方で探す
    for surface in ('芝', 'ダ'):
        key = (venue_name, distance, surface)
        if key in OBSTACLE_LEVEL_TABLE:
            return OBSTACLE_LEVEL_TABLE[key]

    # テーブルにない → 会場デフォルト or 全体中央値
    return _VENUE_DEFAULT_LEVEL.get(venue_name, 25)


def compute_obstacle_experience(
    ketto_num: str,
    race_date: str,
    history_cache: dict,
) -> dict:
    """馬の障害戦経験回数を算出

    Returns:
        {'obstacle_experience': int}
    """
    records = history_cache.get(ketto_num, [])
    count = 0
    for rec in records:
        rd = rec.get('race_date', '')
        if rd >= race_date:
            continue
        if rec.get('track_type') == 'obstacle':
            count += 1
    return {'obstacle_experience': count}


def compute_obstacle_exp_tier(obstacle_experience: int) -> int:
    """障害経験をビン化: 0=初障害, 1=1-3戦, 2=4-10戦, 3=11+"""
    if obstacle_experience == 0:
        return 0
    if obstacle_experience <= 3:
        return 1
    if obstacle_experience <= 10:
        return 2
    return 3


def compute_prev_was_obstacle(
    ketto_num: str,
    race_date: str,
    history_cache: dict,
) -> int:
    """前走が障害レースだったか (1=障害, 0=平地/初出走)"""
    records = history_cache.get(ketto_num, [])
    for rec in reversed(records):
        rd = rec.get('race_date', '')
        if rd < race_date:
            return 1 if rec.get('track_type') == 'obstacle' else 0
    return 0


def compute_difficulty_exp_match(
    ketto_num: str,
    race_date: str,
    current_level: int,
    history_cache: dict,
    level_tolerance: int = 10,
) -> float:
    """当該難易度帯での経験度 (0.0-1.0)

    過去の障害レースのうち、当該コース難易度±toleranceに出走した割合。
    """
    records = history_cache.get(ketto_num, [])
    total_obs = 0
    match_count = 0
    for rec in records:
        rd = rec.get('race_date', '')
        if rd >= race_date:
            continue
        if rec.get('track_type') != 'obstacle':
            continue
        total_obs += 1
        # 過去レースの難易度を計算
        past_venue = rec.get('venue_name', '')
        past_dist = rec.get('distance', 0)
        past_level = compute_obstacle_level(past_venue, past_dist, 'obstacle')
        if abs(past_level - current_level) <= level_tolerance:
            match_count += 1

    if total_obs == 0:
        return 0.0
    return match_count / total_obs


# ── PIT-safe 騎手/調教師 障害タイムライン ──

def build_obstacle_personnel_timelines(
    history_cache: dict,
) -> Tuple[Dict[str, list], Dict[str, list]]:
    """history_cacheから障害レースの騎手/調教師タイムラインを構築

    Returns:
        (jockey_timeline, trainer_timeline)
        jockey_timeline: {jockey_code: [(race_date, is_win, is_top3), ...]}  sorted by date
        trainer_timeline: {trainer_code: [(race_date, is_top3), ...]}  sorted by date
    """
    jockey_tl: Dict[str, list] = defaultdict(list)
    trainer_tl: Dict[str, list] = defaultdict(list)

    for ketto_num, records in history_cache.items():
        if isinstance(records, dict):
            continue
        for rec in records:
            if rec.get('track_type') != 'obstacle':
                continue
            rd = rec.get('race_date', '')
            if not rd:
                continue
            fp = rec.get('finish_position')
            if fp is None or fp == 0:
                continue
            num_runners = rec.get('num_runners', 18)
            place_cutoff = 3 if num_runners >= 8 else (2 if num_runners >= 5 else 1)
            is_win = 1 if fp == 1 else 0
            is_top3 = 1 if fp <= place_cutoff else 0

            jc = rec.get('jockey_code', '')
            tc = rec.get('trainer_code', '')
            if jc:
                jockey_tl[jc].append((rd, is_win, is_top3))
            if tc:
                trainer_tl[tc].append((rd, is_top3))

    # ソート
    for jc in jockey_tl:
        jockey_tl[jc].sort(key=lambda x: x[0])
    for tc in trainer_tl:
        trainer_tl[tc].sort(key=lambda x: x[0])

    return dict(jockey_tl), dict(trainer_tl)


def compute_jockey_obstacle_stats(
    jockey_code: str,
    race_date: str,
    jockey_obstacle_tl: dict,
) -> dict:
    """PIT-safe: 当該日以前の騎手の障害成績

    Returns:
        {'jockey_obstacle_races': int, 'jockey_obstacle_win_rate': float}
    """
    records = jockey_obstacle_tl.get(jockey_code, [])
    if not records:
        return {'jockey_obstacle_races': 0, 'jockey_obstacle_win_rate': 0.0}

    # bisectで当該日以前のレコード数を取得
    from bisect import bisect_left
    dates = [r[0] for r in records]
    idx = bisect_left(dates, race_date)

    if idx == 0:
        return {'jockey_obstacle_races': 0, 'jockey_obstacle_win_rate': 0.0}

    total = idx
    wins = sum(1 for r in records[:idx] if r[1] == 1)
    return {
        'jockey_obstacle_races': total,
        'jockey_obstacle_win_rate': wins / total if total > 0 else 0.0,
    }


def compute_trainer_obstacle_stats(
    trainer_code: str,
    race_date: str,
    trainer_obstacle_tl: dict,
) -> dict:
    """PIT-safe: 当該日以前の調教師の障害好走率

    Returns:
        {'trainer_obstacle_top3_rate': float}
    """
    records = trainer_obstacle_tl.get(trainer_code, [])
    if not records:
        return {'trainer_obstacle_top3_rate': 0.0}

    from bisect import bisect_left
    dates = [r[0] for r in records]
    idx = bisect_left(dates, race_date)

    if idx == 0:
        return {'trainer_obstacle_top3_rate': 0.0}

    total = idx
    top3s = sum(1 for r in records[:idx] if r[1] == 1)
    return {
        'trainer_obstacle_top3_rate': top3s / total if total > 0 else 0.0,
    }


def compute_jockey_selection(
    entries: List[dict],
    history_cache: dict,
    race_date: str,
) -> Dict[int, dict]:
    """レース内の騎手選択シグナルを計算

    前走で同じ騎手が乗っていた馬が複数出走する場合、
    その騎手が今回も継続騎乗する馬 = 「選ばれた馬」(+1)
    その騎手が乗り替わりになった馬 = 「選ばれなかった馬」(-1)

    Returns:
        {umaban: {'jockey_selected': int, 'jockey_selected_count': int}}
    """
    prev_jockey_map = {}
    curr_jockey_map = {}

    for entry in entries:
        umaban = entry.get('umaban', 0)
        ketto_num = entry.get('ketto_num', '')
        curr_jockey = entry.get('jockey_code', '')

        if not ketto_num or not curr_jockey:
            continue

        curr_jockey_map[umaban] = curr_jockey

        records = history_cache.get(ketto_num, [])
        prev_jockey = ''
        for rec in reversed(records):
            rd = rec.get('race_date', '')
            if rd < race_date:
                prev_jockey = rec.get('jockey_code', '')
                break

        if prev_jockey:
            prev_jockey_map[umaban] = prev_jockey

    jockey_to_umabans = defaultdict(list)
    for umaban, pj in prev_jockey_map.items():
        jockey_to_umabans[pj].append(umaban)

    result = {}
    all_umabans = {e.get('umaban', 0) for e in entries if e.get('umaban', 0) > 0}

    for umaban in all_umabans:
        result[umaban] = {'jockey_selected': 0, 'jockey_selected_count': 0}

    for prev_jockey, umabans in jockey_to_umabans.items():
        if len(umabans) < 2:
            continue

        for uma in umabans:
            curr_j = curr_jockey_map.get(uma, '')
            group_size = len(umabans)
            if curr_j == prev_jockey:
                result[uma] = {
                    'jockey_selected': 1,
                    'jockey_selected_count': group_size,
                }
            else:
                result[uma] = {
                    'jockey_selected': -1,
                    'jockey_selected_count': group_size,
                }

    return result
