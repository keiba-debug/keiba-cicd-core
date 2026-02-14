#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基本特徴量: レースJSON直読み

JRA-VANデータから抽出する基本特徴量。

v4.0: month, nichi (開催日) を追加
"""


def extract_base_features(entry: dict, race: dict) -> dict:
    """レースエントリから基本特徴量を抽出"""
    sex_map = {'1': 0, '2': 1, '3': 2}  # 牡=0, 牝=1, セ=2
    track_map = {'turf': 0, 'dirt': 1}
    baba_map = {'良': 0, '稍重': 1, '重': 2, '不良': 3}

    pace = race.get('pace') or {}

    # 開催日 (race_id[12:14]): 1=開幕週, 8=最終週
    race_id = race.get('race_id', '')
    nichi = int(race_id[12:14]) if len(race_id) >= 14 else 0

    # 月
    date_str = race.get('date', '')
    month = int(date_str[5:7]) if len(date_str) >= 7 else 0

    return {
        'age': entry.get('age', 0),
        'sex': sex_map.get(entry.get('sex_cd', ''), 0),
        'futan': entry.get('futan', 0.0),
        'horse_weight': entry.get('horse_weight', 0),
        'horse_weight_diff': entry.get('horse_weight_diff', 0),
        'wakuban': entry.get('wakuban', 0),
        'umaban': entry.get('umaban', 0),
        'distance': race.get('distance', 0),
        'track_type': track_map.get(race.get('track_type', ''), 0),
        'track_condition': baba_map.get(race.get('track_condition', ''), 0),
        'entry_count': race.get('num_runners', 0),
        'odds': entry.get('odds', 0.0),
        'popularity': entry.get('popularity', 0),
        # v4.0
        'month': month,
        'nichi': nichi,
    }
