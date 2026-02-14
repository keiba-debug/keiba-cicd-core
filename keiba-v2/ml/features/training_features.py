#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
調教特徴量 (v4.1)

keibabook拡張データ(kb_ext)から調教関連の特徴量を抽出。
CK_DATA(JRA-VAN調教)のlapRank/timeRank特徴量も追加。

v4.1: CK_DATA lapRank/timeRank/finalLap特徴量追加 (training_summary.json)
v4.0: KB印・レーティング (mark_point, aggregate_mark_point, rating) を追加
v3.3: cyokyo_detail (追い切りタイム・脚色・併せ馬・セッション数) を追加
v3.2: training_arrow_value のみ

データソース:
  1. data3/keibabook/YYYY/MM/DD/kb_ext_{race_id}.json
     → entries[umaban].cyokyo_detail / mark_point / rating
  2. data3/races/YYYY/MM/DD/temp/training_summary.json (CK_DATA集計)
     → summaries[horseName].lapRank / timeRank / finalLap etc.
"""

import re
from typing import Optional


# 脚色 → 数値コード
INTENSITY_MAP = {
    '一杯に追う': 4,
    '一杯追う': 4,
    '追って一杯': 4,
    '叩き一杯': 4,
    '末強め追う': 3,
    '強めに追う': 2,
    '強め追う': 2,
    'G前仕掛け': 2,
    '馬なり余力': 1,
    '馬なり': 1,
    'ゲートなり': 0,
}


def _parse_intensity(text: str) -> int:
    """脚色テキストを数値に変換。不明なら-1。"""
    if not text:
        return -1
    for key, val in INTENSITY_MAP.items():
        if key in text:
            return val
    return -1


def _parse_rest_weeks(rest_period: str) -> int:
    """'中3週' → 3, '中1週' → 1, 空 → -1"""
    if not rest_period:
        return -1
    m = re.search(r'中(\d+)週', rest_period)
    if m:
        return int(m.group(1))
    return -1


def _is_slope_course(course: str) -> int:
    """坂路コースかどうか (美坂, 栗坂 → 1, それ以外 → 0)"""
    if not course:
        return -1
    return 1 if '坂' in course else 0


# === CK_DATA lapRank エンコーディング ===

# lapRank → 順序スコア (0=欠損, 1=D-, 16=SS)
LAPRANK_SCORES = {
    'SS': 16, 'S+': 15, 'S=': 14, 'S-': 13,
    'A+': 12, 'A=': 11, 'A-': 10,
    'B+': 9,  'B=': 8,  'B-': 7,
    'C+': 6,  'C=': 5,  'C-': 4,
    'D+': 3,  'D=': 2,  'D-': 1,
}

# lapRank → 基本クラス (D=0, C=1, B=2, A=3, S=4, SS=5)
LAPRANK_CLASS = {
    'SS': 5, 'S+': 4, 'S=': 4, 'S-': 4,
    'A+': 3, 'A=': 3, 'A-': 3,
    'B+': 2, 'B=': 2, 'B-': 2,
    'C+': 1, 'C=': 1, 'C-': 1,
    'D+': 0, 'D=': 0, 'D-': 0,
}

# lapRank → 加速コード (+1=加速, 0=等速, -1=減速)
LAPRANK_ACCEL = {
    'SS': 1,  # SSは加速or等速が条件
    'S+': 1, 'S=': 0, 'S-': -1,
    'A+': 1, 'A=': 0, 'A-': -1,
    'B+': 1, 'B=': 0, 'B-': -1,
    'C+': 1, 'C=': 0, 'C-': -1,
    'D+': 1, 'D=': 0, 'D-': -1,
}


def _encode_laprank(laprank: str) -> tuple:
    """lapRank文字列を (score, class, accel) に変換"""
    if not laprank or laprank not in LAPRANK_SCORES:
        return (None, None, None)
    return (
        LAPRANK_SCORES[laprank],
        LAPRANK_CLASS[laprank],
        LAPRANK_ACCEL[laprank],
    )


def compute_training_features(
    umaban: str,
    kb_ext: dict | None,
    ck_training: dict | None = None,
) -> dict:
    """1頭の調教特徴量を計算

    Args:
        umaban: 馬番（文字列）
        kb_ext: kb_ext JSONの内容（Noneならデータなし）
        ck_training: CK_DATA training_summary の1頭分 (ketto_numでマッチ済み)
                     keys: lapRank, timeRank, finalLap, finalTime4F, finalLap1 etc.

    Returns:
        dict: 特徴量辞書
    """
    default = {
        'training_arrow_value': -1,
        'oikiri_5f': -1.0,
        'oikiri_3f': -1.0,
        'oikiri_1f': -1.0,
        'oikiri_intensity_code': -1,
        'oikiri_has_awase': -1,
        'training_session_count': -1,
        'rest_weeks': -1,
        'oikiri_is_slope': -1,
        # KB印・レーティング (v4.0)
        'kb_mark_point': None,
        'kb_aggregate_mark_point': None,
        'kb_rating': None,
        # CK_DATA lapRank (v4.1)
        'ck_laprank_score': None,
        'ck_laprank_class': None,
        'ck_laprank_accel': None,
        'ck_time_rank': None,
        'ck_final_laprank_score': None,
        'ck_final_time4f': None,
        'ck_final_lap1': None,
    }

    if not kb_ext:
        return default

    entries = kb_ext.get('entries', {})
    entry = entries.get(str(umaban))
    if not entry:
        return default

    result = dict(default)

    # training_arrow_value: -2(↓) 〜 +2(↑)
    tav = entry.get('training_arrow_value')
    if tav is not None:
        result['training_arrow_value'] = tav

    # KB印・レーティング (v4.0)
    mp = entry.get('mark_point')
    if mp is not None:
        result['kb_mark_point'] = mp
    amp = entry.get('aggregate_mark_point')
    if amp is not None:
        result['kb_aggregate_mark_point'] = amp
    rating = entry.get('rating')
    if rating is not None:
        result['kb_rating'] = rating

    # cyokyo_detail (cyokyo_enricherで追加済みの場合)
    detail = entry.get('cyokyo_detail')
    if not detail:
        return result

    oikiri = detail.get('oikiri_summary', {})

    # 追い切りタイム
    if oikiri.get('oikiri_5f') is not None:
        result['oikiri_5f'] = oikiri['oikiri_5f']
    if oikiri.get('oikiri_3f') is not None:
        result['oikiri_3f'] = oikiri['oikiri_3f']
    if oikiri.get('oikiri_1f') is not None:
        result['oikiri_1f'] = oikiri['oikiri_1f']

    # 脚色コード
    result['oikiri_intensity_code'] = _parse_intensity(
        oikiri.get('oikiri_intensity', '')
    )

    # 併せ馬有無
    if oikiri.get('oikiri_has_awase') is not None:
        result['oikiri_has_awase'] = 1 if oikiri['oikiri_has_awase'] else 0

    # セッション数
    result['training_session_count'] = detail.get(
        'oikiri_summary', {}
    ).get('session_count', -1)

    # 休養週数
    result['rest_weeks'] = _parse_rest_weeks(
        detail.get('rest_period', '')
    )

    # 坂路コースか
    result['oikiri_is_slope'] = _is_slope_course(
        oikiri.get('oikiri_course', '')
    )

    # === CK_DATA調教特徴量 (v4.1) ===
    if ck_training:
        # 総合lapRank (SS〜D-)
        lr = ck_training.get('lapRank', '')
        score, cls, accel = _encode_laprank(lr)
        if score is not None:
            result['ck_laprank_score'] = score
            result['ck_laprank_class'] = cls
            result['ck_laprank_accel'] = accel

        # timeRank (タイムレベル 1-5)
        tr = ck_training.get('timeRank', '')
        if tr and tr.isdigit():
            result['ck_time_rank'] = int(tr)

        # 最終追い切りlapRank
        fl = ck_training.get('finalLap', '')
        fl_score, _, _ = _encode_laprank(fl)
        if fl_score is not None:
            result['ck_final_laprank_score'] = fl_score

        # 最終追い切り4Fタイム
        ft4f = ck_training.get('finalTime4F')
        if ft4f is not None and isinstance(ft4f, (int, float)) and ft4f > 0:
            result['ck_final_time4f'] = float(ft4f)

        # 最終追い切りラスト1F
        fl1 = ck_training.get('finalLap1')
        if fl1 is not None and isinstance(fl1, (int, float)) and fl1 > 0:
            result['ck_final_lap1'] = float(fl1)

    return result
