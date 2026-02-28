#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
基本特徴量: レースJSON直読み

JRA-VANデータから抽出する基本特徴量。

v4.0: month, nichi (開催日) を追加
v5.40: place_code, first_corner_dist を追加
"""

# 1角までの概算距離 (venue_name, track_type, distance) → meters
# analyze_baba_report.py [17] の分析結果に基づく
FIRST_CORNER_DIST = {
    ('東京', 'turf', 1400): 540, ('東京', 'turf', 1600): 540,
    ('東京', 'turf', 1800): 340, ('東京', 'turf', 2000): 540,
    ('東京', 'turf', 2400): 350,
    ('東京', 'dirt', 1300): 150, ('東京', 'dirt', 1400): 270,
    ('東京', 'dirt', 1600): 470, ('東京', 'dirt', 2100): 350,
    ('中山', 'turf', 1200): 200, ('中山', 'turf', 1600): 250,
    ('中山', 'turf', 1800): 460, ('中山', 'turf', 2000): 260,
    ('中山', 'turf', 2200): 460, ('中山', 'turf', 2500): 260,
    ('中山', 'dirt', 1200): 250, ('中山', 'dirt', 1800): 450,
    ('阪神', 'turf', 1200): 280, ('阪神', 'turf', 1400): 310,
    ('阪神', 'turf', 1600): 450, ('阪神', 'turf', 1800): 310,
    ('阪神', 'turf', 2000): 450, ('阪神', 'turf', 2200): 280,
    ('阪神', 'turf', 2400): 440,
    ('阪神', 'dirt', 1200): 270, ('阪神', 'dirt', 1400): 460,
    ('阪神', 'dirt', 1800): 260, ('阪神', 'dirt', 2000): 460,
    ('京都', 'turf', 1200): 280, ('京都', 'turf', 1400): 400,
    ('京都', 'turf', 1600): 280, ('京都', 'turf', 1800): 400,
    ('京都', 'turf', 2000): 280, ('京都', 'turf', 2200): 400,
    ('京都', 'turf', 2400): 350,
    ('京都', 'dirt', 1200): 280, ('京都', 'dirt', 1400): 420,
    ('京都', 'dirt', 1800): 250, ('京都', 'dirt', 1900): 350,
    ('中京', 'turf', 1200): 310, ('中京', 'turf', 1400): 510,
    ('中京', 'turf', 1600): 310, ('中京', 'turf', 2000): 350,
    ('中京', 'turf', 2200): 350,
    ('中京', 'dirt', 1200): 310, ('中京', 'dirt', 1400): 510,
    ('中京', 'dirt', 1800): 310, ('中京', 'dirt', 1900): 410,
    ('新潟', 'turf', 1000): 999, ('新潟', 'turf', 1200): 440,
    ('新潟', 'turf', 1400): 450, ('新潟', 'turf', 1600): 350,
    ('新潟', 'turf', 1800): 250, ('新潟', 'turf', 2000): 450,
    ('新潟', 'dirt', 1200): 380, ('新潟', 'dirt', 1800): 280,
    ('福島', 'turf', 1200): 320, ('福島', 'turf', 1800): 380,
    ('福島', 'turf', 2000): 310, ('福島', 'turf', 2600): 310,
    ('福島', 'dirt', 1150): 300, ('福島', 'dirt', 1700): 360,
    ('小倉', 'turf', 1200): 310, ('小倉', 'turf', 1800): 320,
    ('小倉', 'turf', 2000): 310,
    ('小倉', 'dirt', 1000): 200, ('小倉', 'dirt', 1700): 350,
    ('札幌', 'turf', 1200): 310, ('札幌', 'turf', 1500): 310,
    ('札幌', 'turf', 1800): 310, ('札幌', 'turf', 2000): 310,
    ('札幌', 'dirt', 1000): 200, ('札幌', 'dirt', 1700): 360,
    ('函館', 'turf', 1200): 280, ('函館', 'turf', 1800): 330,
    ('函館', 'turf', 2000): 250,
    ('函館', 'dirt', 1000): 200, ('函館', 'dirt', 1700): 350,
}

# place_code → venue_name (JRA-VAN)
PLACE_NAMES = {
    '01': '札幌', '02': '函館', '03': '福島', '04': '新潟',
    '05': '東京', '06': '中山', '07': '中京', '08': '京都',
    '09': '阪神', '10': '小倉',
}


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

    # v5.40: place_code (場所コード 1-10)
    place_code_str = race_id[8:10] if len(race_id) >= 10 else '00'
    place_code = int(place_code_str) if place_code_str.isdigit() else 0

    # v5.40: first_corner_dist (1角までの距離)
    track_type_str = race.get('track_type', '')
    distance = race.get('distance', 0)
    venue_name = PLACE_NAMES.get(place_code_str, '')
    fc_key = (venue_name, track_type_str, distance)
    first_corner_dist = FIRST_CORNER_DIST.get(fc_key)  # None if not found

    return {
        'age': entry.get('age', 0),
        'sex': sex_map.get(entry.get('sex_cd', ''), 0),
        'futan': entry.get('futan', 0.0),
        'horse_weight': entry.get('horse_weight', 0),
        'horse_weight_diff': entry.get('horse_weight_diff', 0),
        'wakuban': entry.get('wakuban', 0),
        'umaban': entry.get('umaban', 0),
        'distance': distance,
        'track_type': track_map.get(track_type_str, 0),
        'track_condition': baba_map.get(race.get('track_condition', ''), 0),
        'entry_count': race.get('num_runners', 0),
        'odds': entry.get('odds', 0.0),
        'popularity': entry.get('popularity', 0),
        # v4.0
        'month': month,
        'nichi': nichi,
        # v5.40: 馬場分析特徴量
        'place_code': place_code,
        'first_corner_dist': first_corner_dist,
    }
