#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ペース特徴量

レースペースデータ(RPCI等)と馬の走破データを組み合わせた特徴量。
pace_index: {race_id: {rpci, s3, l3, s4, l4}} を外部から注入。
"""

import numpy as np

# 急坂コース: 中山(06), 阪神(09)
STEEP_VENUES = {'06', '09'}


def compute_pace_features(
    ketto_num: str,
    race_date: str,
    days_since_last_race: int,
    history_cache: dict,
    pace_index: dict,
) -> dict:
    """
    ペース関連の特徴量を計算。

    pace_index: race_id → {rpci, s3, l3, s4, l4}
    days_since_last_race: past_featuresで計算済みの値を再利用
    """
    result = {
        'avg_race_rpci_last3': -1,
        'prev_race_rpci': -1,
        'consumption_flag': 0,
        'last3f_vs_race_l3_last3': -1,
        'steep_course_experience': -1,
        'steep_course_top3_rate': -1,
        # v4.0: 上がり3F順位 vs 着順ギャップ
        'l3_unrewarded_rate_last5': None,
    }

    runs = history_cache.get(ketto_num, [])
    if not runs:
        return result

    past = [r for r in runs if r['race_date'] < race_date]
    if not past:
        return result

    last3 = past[-3:]
    last = past[-1]

    # avg_race_rpci_last3: 直近3走のレースRPCI平均
    rpcis = []
    for r in last3:
        pace = pace_index.get(r['race_id'], {})
        rpci = pace.get('rpci')
        if rpci is not None and rpci > 0:
            rpcis.append(rpci)
    if rpcis:
        result['avg_race_rpci_last3'] = round(np.mean(rpcis), 2)

    # prev_race_rpci: 前走のRPCI
    prev_pace = pace_index.get(last['race_id'], {})
    prev_rpci = prev_pace.get('rpci')
    if prev_rpci is not None and prev_rpci > 0:
        result['prev_race_rpci'] = round(prev_rpci, 2)

        # consumption_flag: 前走RPCI<=46 かつ 中間隔<=21日
        if prev_rpci <= 46 and 0 < days_since_last_race <= 21:
            result['consumption_flag'] = 1

    # last3f_vs_race_l3_last3: (馬L3 - レースL3) の3走平均
    diffs = []
    for r in last3:
        horse_l3 = r.get('last_3f', 0)
        pace = pace_index.get(r['race_id'], {})
        race_l3 = pace.get('l3')
        if horse_l3 > 0 and race_l3 is not None and race_l3 > 0:
            diffs.append(horse_l3 - race_l3)
    if diffs:
        result['last3f_vs_race_l3_last3'] = round(np.mean(diffs), 2)

    # l3_unrewarded_rate_last5: 上がりが速いのに着外のレース率 (v4.0)
    # 「脚はあるが展開不利で結果が出ない」馬を検出
    last5 = past[-5:]
    l3_fast_but_lost = 0
    l3_fast_total = 0
    for r in last5:
        horse_l3 = r.get('last_3f', 0)
        pace_data = pace_index.get(r['race_id'], {})
        race_l3 = pace_data.get('l3')
        if horse_l3 > 0 and race_l3 is not None and race_l3 > 0:
            if horse_l3 < race_l3:  # 馬のL3がレース平均より速い
                l3_fast_total += 1
                if r.get('finish_position', 0) > 3:
                    l3_fast_but_lost += 1
    if l3_fast_total > 0:
        result['l3_unrewarded_rate_last5'] = round(
            l3_fast_but_lost / l3_fast_total, 4
        )

    # steep_course_experience: 急坂場(中山/阪神)での出走割合
    if len(past) >= 2:
        steep_runs = [r for r in past if r.get('venue_code') in STEEP_VENUES]
        result['steep_course_experience'] = round(len(steep_runs) / len(past), 4)

        # steep_course_top3_rate: 急坂場での3着以内率
        if steep_runs:
            top3 = sum(1 for r in steep_runs if 1 <= r.get('finish_position', 0) <= 3)
            result['steep_course_top3_rate'] = round(top3 / len(steep_runs), 4)

    return result
