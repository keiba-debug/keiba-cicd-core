#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ローテーション・コンディション特徴量

斤量変化、馬体重変化、前走人気など。

v4.0: jockey_change (騎手乗り替わりフラグ) を追加
v5.1: 降格ローテ特徴量追加（7パターン + レベル差）
"""

from core.constants import GRADE_LEVEL, VENUE_RANK, VENUE_RANK_ORDER


def compute_rotation_features(
    ketto_num: str,
    race_date: str,
    futan: float,
    horse_weight: int,
    popularity: int,
    jockey_code: str,
    history_cache: dict,
    current_grade: str = '',
    current_venue: str = '',
    current_distance: int = 0,
    current_track_type: str = '',
    current_month: int = 0,
    current_is_handicap: bool = False,
    current_is_female_only: bool = False,
) -> dict:
    """
    ローテーション・コンディション関連の特徴量を計算。

    注意: popularity_trend は MARKET特徴量 → Model Bでは除外。
    降格ローテ: grade_level_diff, venue_rank_diff はMARKET、
    is_koukaku_* はVALUE候補（実験で検証）。
    """
    result = {
        'futan_diff': -1,
        'futan_diff_ratio': -1,
        'weight_change_ratio': -1,
        'prev_race_popularity': -1,
        'popularity_trend': -1,  # MARKET特徴量
        'jockey_change': None,  # v4.0: 騎手乗り替わり
        # v5.1: 降格ローテ
        'prev_grade_level': None,
        'grade_level_diff': None,
        'venue_rank_diff': None,
        'is_koukaku_venue': None,
        'is_koukaku_female': None,
        'is_koukaku_season': None,
        'is_koukaku_age': None,
        'is_koukaku_distance': None,
        'is_koukaku_turf_to_dirt': None,
        'is_koukaku_handicap': None,
        'koukaku_rote_count': None,
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

    # === 降格ローテ特徴量 (v5.1) ===
    _compute_koukaku_features(result, last,
                              current_grade, current_venue, current_distance,
                              current_track_type, current_month,
                              current_is_handicap, current_is_female_only)

    return result


def _compute_koukaku_features(
    result: dict,
    last: dict,
    current_grade: str,
    current_venue: str,
    current_distance: int,
    current_track_type: str,
    current_month: int,
    current_is_handicap: bool,
    current_is_female_only: bool,
) -> None:
    """降格ローテ7パターン + レベル差の特徴量を計算"""
    prev_grade = last.get('grade', '')
    prev_venue = last.get('venue_name', '')
    prev_distance = last.get('distance', 0)
    prev_track_type = last.get('track_type', '')
    prev_is_handicap = last.get('is_handicap', False)
    prev_is_female_only = last.get('is_female_only', False)

    # grade_level_diff: 今走 - 前走（正=降級方向、負=昇級方向）
    cur_gl = GRADE_LEVEL.get(current_grade)
    prev_gl = GRADE_LEVEL.get(prev_grade)
    if prev_gl is not None:
        result['prev_grade_level'] = prev_gl
    if cur_gl is not None and prev_gl is not None:
        result['grade_level_diff'] = cur_gl - prev_gl

    # venue_rank_diff: 今走ランク順位 - 前走ランク順位（正=降格方向）
    cur_vr = VENUE_RANK_ORDER.get(VENUE_RANK.get(current_venue, ''), None)
    prev_vr = VENUE_RANK_ORDER.get(VENUE_RANK.get(prev_venue, ''), None)
    if cur_vr is not None and prev_vr is not None:
        result['venue_rank_diff'] = cur_vr - prev_vr

    koukaku_count = 0

    # パターン①: 栗東馬割合（ダート限定）
    # 前走が上位ランク会場 → 今走が下位ランク会場
    if current_track_type == 'dirt' and cur_vr is not None and prev_vr is not None:
        is_koukaku = cur_vr > prev_vr  # 今走の方がランクが低い（数値が大きい）
        result['is_koukaku_venue'] = 1 if is_koukaku else 0
        if is_koukaku:
            koukaku_count += 1
    else:
        result['is_koukaku_venue'] = 0

    # パターン②: 性別×距離（ダート限定）
    # 前走: 牡牝混合 1400m以上ダート → 今走: 牝馬限定戦
    if (current_track_type == 'dirt'
            and current_is_female_only
            and not prev_is_female_only
            and prev_track_type == 'dirt'
            and prev_distance >= 1400):
        result['is_koukaku_female'] = 1
        koukaku_count += 1
    else:
        result['is_koukaku_female'] = 0

    # パターン③: 性別×開催時期（ダート限定）
    # 前走: 12〜4月の牡牝混合 → 今走: 5〜9月の牡牝混合
    if (current_track_type == 'dirt'
            and not current_is_female_only
            and not prev_is_female_only):
        prev_month = _extract_month(last.get('race_date', ''))
        is_prev_winter = prev_month in (12, 1, 2, 3, 4) if prev_month else False
        is_cur_summer = 5 <= current_month <= 9 if current_month else False
        if is_prev_winter and is_cur_summer:
            result['is_koukaku_season'] = 1
            koukaku_count += 1
        else:
            result['is_koukaku_season'] = 0
    else:
        result['is_koukaku_season'] = 0

    # パターン④: 馬齢（芝限定）
    # 前走: 3歳限定戦 → 今走: 3歳以上戦（古馬クラス）
    # 3歳限定 = gradeに"3歳"が含まれるか、race_classから判定
    # horse_historyにはrace_classがないが、gradeとage情報で推定可能
    # ここでは簡易判定: 前走gradeと同一 + venue違い等で推定
    # → 実際にはbuild_horse_historyにrace_class追加が必要だが、
    #   ここではgrade_level_diffで代替（同一クラスでのレベル差がメイン）
    result['is_koukaku_age'] = 0  # TODO: race_classから3歳限定→古馬判定

    # パターン⑤: 距離短縮（芝限定）
    # 前走: 芝1600m以上 → 今走: 芝1200m以下
    if (current_track_type == 'turf'
            and current_distance <= 1200
            and prev_track_type == 'turf'
            and prev_distance >= 1600):
        result['is_koukaku_distance'] = 1
        koukaku_count += 1
    else:
        result['is_koukaku_distance'] = 0

    # パターン⑥: 芝→ダート
    # 前走: 芝で3コーナー10番手以下 → 今走: ダート
    if current_track_type == 'dirt' and prev_track_type == 'turf':
        corners = last.get('corners', [])
        # 3コーナー通過順位（cornersは[1C, 2C, 3C, 4C]）
        corner3 = corners[2] if len(corners) >= 3 else 0
        if corner3 >= 10:
            result['is_koukaku_turf_to_dirt'] = 1
            koukaku_count += 1
        else:
            result['is_koukaku_turf_to_dirt'] = 0
    else:
        result['is_koukaku_turf_to_dirt'] = 0

    # パターン⑦: ハンデ戦
    # 前走: ハンデ戦以外 → 今走: ハンデ戦
    if current_is_handicap and not prev_is_handicap:
        result['is_koukaku_handicap'] = 1
        koukaku_count += 1
    else:
        result['is_koukaku_handicap'] = 0

    result['koukaku_rote_count'] = koukaku_count


def _extract_month(race_date: str) -> int:
    """YYYY-MM-DD から月を取得"""
    parts = race_date.split('-')
    if len(parts) >= 2:
        try:
            return int(parts[1])
        except ValueError:
            pass
    return 0
