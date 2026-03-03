#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
障害レース専用特徴量

1. obstacle_experience: 当該馬の障害戦出走回数（0=初障害）
2. jockey_selected: 騎手選択シグナル
   - 前走同じ騎手が乗っていた馬が同一レースに複数出走
   - その騎手が今回選んだ馬=1、選ばれなかった馬=-1、それ以外=0
3. obstacle_jockey_exp: 当該騎手の障害戦騎乗回数（少ない=経験不足）
"""

from typing import Dict, List


def compute_obstacle_experience(
    ketto_num: str,
    race_date: str,
    history_cache: dict,
) -> dict:
    """馬の障害戦経験回数を算出

    Args:
        ketto_num: 血統番号
        race_date: 当該レース日 (YYYY-MM-DD)
        history_cache: {ketto_num: [records...]}

    Returns:
        {'obstacle_experience': int}
    """
    records = history_cache.get(ketto_num, [])
    count = 0
    for rec in records:
        rd = rec.get('race_date', '')
        if rd >= race_date:
            continue  # 未来のレースは除外
        if rec.get('track_type') == 'obstacle':
            count += 1
    return {'obstacle_experience': count}


def compute_jockey_selection(
    entries: List[dict],
    history_cache: dict,
    race_date: str,
) -> Dict[int, dict]:
    """レース内の騎手選択シグナルを計算

    前走で同じ騎手が乗っていた馬が複数出走する場合、
    その騎手が今回も継続騎乗する馬 = 「選ばれた馬」(+1)
    その騎手が乗り替わりになった馬 = 「選ばれなかった馬」(-1)

    Args:
        entries: レースJSONのentries（各entry要素にjockey_code, ketto_numが必要）
        history_cache: {ketto_num: [records...]}
        race_date: 当該レース日 (YYYY-MM-DD)

    Returns:
        {umaban: {'jockey_selected': int, 'jockey_selected_count': int}}
        jockey_selected_count: 同一前走騎手の馬が何頭いるか
    """
    # Step 1: 各エントリの「前走騎手」を取得
    # prev_jockey_map: {umaban: prev_jockey_code}
    # curr_jockey_map: {umaban: current_jockey_code}
    prev_jockey_map = {}
    curr_jockey_map = {}

    for entry in entries:
        umaban = entry.get('umaban', 0)
        ketto_num = entry.get('ketto_num', '')
        curr_jockey = entry.get('jockey_code', '')

        if not ketto_num or not curr_jockey:
            continue

        curr_jockey_map[umaban] = curr_jockey

        # 前走の騎手を取得
        records = history_cache.get(ketto_num, [])
        prev_jockey = ''
        for rec in reversed(records):
            rd = rec.get('race_date', '')
            if rd < race_date:
                prev_jockey = rec.get('jockey_code', '')
                break

        if prev_jockey:
            prev_jockey_map[umaban] = prev_jockey

    # Step 2: 前走騎手でグルーピング → 複数馬に乗っていた騎手を特定
    # jockey_to_umabans: {prev_jockey: [umaban1, umaban2, ...]}
    from collections import defaultdict
    jockey_to_umabans = defaultdict(list)
    for umaban, pj in prev_jockey_map.items():
        jockey_to_umabans[pj].append(umaban)

    # Step 3: 複数馬に乗っていた騎手 → 今回選んだ馬/選ばなかった馬を判定
    result = {}
    all_umabans = {e.get('umaban', 0) for e in entries if e.get('umaban', 0) > 0}

    for umaban in all_umabans:
        result[umaban] = {'jockey_selected': 0, 'jockey_selected_count': 0}

    for prev_jockey, umabans in jockey_to_umabans.items():
        if len(umabans) < 2:
            continue  # 1頭だけなら選択シグナルなし

        # この騎手が今回乗る馬を特定
        for uma in umabans:
            curr_j = curr_jockey_map.get(uma, '')
            group_size = len(umabans)
            if curr_j == prev_jockey:
                # 前走と同じ騎手 = 選ばれた
                result[uma] = {
                    'jockey_selected': 1,
                    'jockey_selected_count': group_size,
                }
            else:
                # 騎手が乗り替わり = 選ばれなかった
                result[uma] = {
                    'jockey_selected': -1,
                    'jockey_selected_count': group_size,
                }

    return result
