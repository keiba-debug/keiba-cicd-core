#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
差し追込好走予測 — レースレベル特徴量

「3着以内に差し/追込が2頭以上入るレース」を予測するための特徴量。
1レース → 1行のDataFrame行を生成。

特徴量グループ:
  A. コース特性 (8個): distance, track_type, place_code, etc.
  B. メンバー構成・脚質分布 (14個): closing_strength集計, front_runner密度, etc.
  C. ペース予測指標 (5個): 先行馬密度→ペース圧力推定
  D. コース歴史統計 (4個, PIT safe): CourseClosingTimelineによる累積統計
  E. 馬場 (2個): cushion_value, moisture_rate
"""

import bisect
from collections import defaultdict
from typing import Dict, List, Optional

import numpy as np

from ml.features.base_features import FIRST_CORNER_DIST


# === ターゲット変数 ===

def is_closer(entry: dict, num_runners: int) -> bool:
    """最終コーナーで後方半分にいた馬が3着以内かどうか"""
    corners = entry.get('corners', [])
    fp = entry.get('finish_position', 0)
    if not corners or fp <= 0 or fp > 3 or num_runners <= 0:
        return False
    return corners[-1] / num_runners > 0.5


def compute_closing_label(race: dict) -> Optional[int]:
    """is_closing_race: 3着以内に差し追込が2頭以上 → 1, else 0

    少頭数(< 8)は除外(None)。障害レースも除外。
    """
    n = race.get('num_runners', 0)
    if n < 8:
        return None
    track_type = race.get('track_type', '')
    if track_type == 'obstacle' or '障害' in race.get('race_name', ''):
        return None
    entries = race.get('entries', [])
    closers_in_top3 = sum(1 for e in entries if is_closer(e, n))
    return 1 if closers_in_top3 >= 2 else 0


# === 距離カテゴリ ===

def _distance_category(distance: int) -> str:
    if distance <= 1400:
        return 'sprint'
    elif distance <= 1800:
        return 'mile'
    elif distance <= 2200:
        return 'mid'
    else:
        return 'long'


# === コース歴史統計 (PIT safe) ===

class CourseClosingTimeline:
    """コース別の差し追込好走累積タイムライン（PIT safe）

    全レースを日付順に処理し、各コース条件での差し追込好走率を累積。
    lookup時は bisect_left(dates, race_date) - 1 で race_date「以前」の統計を返す。
    """

    def __init__(self):
        # {course_key: {dates: [], total: [], closing: [], rpci_sum: []}}
        self.timeline: Dict[str, dict] = {}
        # {cond_key: {dates: [], total: [], closing: []}}
        self.cond_timeline: Dict[str, dict] = {}

    def build(self, race_iter):
        """(race_dict, date_str) のイテレータからタイムラインを構築

        Args:
            race_iter: (race_dict, date_str) を返すイテレータ（日付昇順）
        """
        # 日付単位のバッファ
        course_buf = defaultdict(lambda: {'total': 0, 'closing': 0, 'rpci_sum': 0.0})
        cond_buf = defaultdict(lambda: {'total': 0, 'closing': 0})

        current_date = None
        sorted_races = []

        for race, date_str in race_iter:
            sorted_races.append((date_str, race))

        # 日付でソート
        sorted_races.sort(key=lambda x: x[0])

        for date_str, race in sorted_races:
            if date_str != current_date and current_date is not None:
                self._flush(current_date, course_buf, cond_buf)
                course_buf = defaultdict(lambda: {'total': 0, 'closing': 0, 'rpci_sum': 0.0})
                cond_buf = defaultdict(lambda: {'total': 0, 'closing': 0})
            current_date = date_str

            label = compute_closing_label(race)
            if label is None:
                continue

            venue = race.get('venue_name', '')
            track_type = race.get('track_type', '')
            distance = race.get('distance', 0)
            dist_cat = _distance_category(distance)
            track_cond = race.get('track_condition', '')
            rpci = (race.get('pace') or {}).get('rpci', 0) or 0

            course_key = f"{venue}_{track_type}_{dist_cat}"
            course_buf[course_key]['total'] += 1
            course_buf[course_key]['closing'] += label
            course_buf[course_key]['rpci_sum'] += rpci

            cond_key = f"{track_type}_{track_cond}"
            cond_buf[cond_key]['total'] += 1
            cond_buf[cond_key]['closing'] += label

        # 最終日のフラッシュ
        if current_date is not None:
            self._flush(current_date, course_buf, cond_buf)

    def _flush(self, date_str, course_buf, cond_buf):
        for key, buf in course_buf.items():
            if key not in self.timeline:
                self.timeline[key] = {'dates': [], 'total': [], 'closing': [], 'rpci_sum': []}
            tl = self.timeline[key]
            prev_total = tl['total'][-1] if tl['total'] else 0
            prev_closing = tl['closing'][-1] if tl['closing'] else 0
            prev_rpci = tl['rpci_sum'][-1] if tl['rpci_sum'] else 0.0
            tl['dates'].append(date_str)
            tl['total'].append(prev_total + buf['total'])
            tl['closing'].append(prev_closing + buf['closing'])
            tl['rpci_sum'].append(prev_rpci + buf['rpci_sum'])

        for key, buf in cond_buf.items():
            if key not in self.cond_timeline:
                self.cond_timeline[key] = {'dates': [], 'total': [], 'closing': []}
            tl = self.cond_timeline[key]
            prev_total = tl['total'][-1] if tl['total'] else 0
            prev_closing = tl['closing'][-1] if tl['closing'] else 0
            tl['dates'].append(date_str)
            tl['total'].append(prev_total + buf['total'])
            tl['closing'].append(prev_closing + buf['closing'])

    def lookup(self, venue: str, track_type: str, distance: int,
               track_condition: str, race_date: str) -> dict:
        """race_date以前のコース統計を返す (PIT safe)"""
        result = {
            'course_closing_rate': -1.0,
            'course_closing_count': 0,
            'course_avg_rpci': -1.0,
            'track_cond_closing_rate': -1.0,
        }

        dist_cat = _distance_category(distance)
        course_key = f"{venue}_{track_type}_{dist_cat}"
        tl = self.timeline.get(course_key)
        if tl and tl['dates']:
            idx = bisect.bisect_left(tl['dates'], race_date) - 1
            if idx >= 0:
                total = tl['total'][idx]
                if total >= 10:  # 最低10レースのサンプル
                    result['course_closing_rate'] = round(tl['closing'][idx] / total, 4)
                    result['course_closing_count'] = total
                    result['course_avg_rpci'] = round(tl['rpci_sum'][idx] / total, 2)

        cond_key = f"{track_type}_{track_condition}"
        ctl = self.cond_timeline.get(cond_key)
        if ctl and ctl['dates']:
            idx = bisect.bisect_left(ctl['dates'], race_date) - 1
            if idx >= 0:
                total = ctl['total'][idx]
                if total >= 20:
                    result['track_cond_closing_rate'] = round(ctl['closing'][idx] / total, 4)

        return result


# === レースレベル特徴量 ===

# 特徴量名リスト（experiment_closing.pyで参照）
CLOSING_RACE_FEATURES = [
    # A. コース特性
    'distance', 'is_turf', 'track_condition', 'place_code',
    'entry_count', 'first_corner_dist', 'month', 'distance_category',
    'nichi',
    # B. メンバー構成・脚質分布
    'closing_strength_mean', 'closing_strength_max', 'closing_strength_q75',
    'n_strong_closers', 'n_strong_closers_ratio',
    'position_gain_mean', 'position_gain_max', 'n_position_gainers',
    'avg_first_corner_ratio_mean',
    'front_runner_count', 'front_runner_ratio',
    'pace_sensitivity_mean', 'running_style_diversity',
    'last3f_avg_mean',
    # C. ペース予測指標
    'n_senkou_horses', 'senkou_ratio', 'pace_pressure',
    'avg_race_rpci_members', 'consumption_flag_count',
    # D. コース歴史統計
    'course_closing_rate', 'course_closing_count',
    'course_avg_rpci', 'track_cond_closing_rate',
    # E. 馬場・開催進行
    'cushion_value', 'moisture_rate',
    'is_late_kaisai', 'turf_late_kaisai',
    'moisture_x_late', 'cushion_low',
]


def compute_closing_race_features(
    race: dict,
    horse_features: List[dict],
    course_timeline: Optional[CourseClosingTimeline] = None,
    baba_features: Optional[dict] = None,
) -> dict:
    """1レースのレースレベル特徴量を計算

    Args:
        race: レースJSON
        horse_features: compute_features_for_race()が返した馬レベル特徴量のリスト
        course_timeline: コース歴史統計タイムライン (PIT safe)
        baba_features: get_baba_features()の戻り値 (1つで十分、レース共通)
    """
    race_date = race.get('date', '')
    race_id = race.get('race_id', '')
    venue_name = race.get('venue_name', '')
    track_type = race.get('track_type', '')
    distance = race.get('distance', 0)
    entry_count = race.get('num_runners', 0)
    place_code = race.get('venue_code', '')
    track_condition = race.get('track_condition', '')

    # track_condition → 数値 (良=0, 稍重=1, 重=2, 不良=3)
    cond_map = {'良': 0, '稍重': 1, '重': 2, '不良': 3}
    cond_val = cond_map.get(track_condition, -1)

    # month
    month = int(race_date.split('-')[1]) if len(race_date.split('-')) >= 2 else 0

    # nichi (開催日: 1=開幕週, 8=最終週)
    nichi = int(race_id[12:14]) if len(race_id) >= 14 else 0
    is_turf = 1 if track_type == 'turf' else 0

    # first_corner_dist
    fcd = FIRST_CORNER_DIST.get((venue_name, track_type, distance), -1)

    feat = {
        # A. コース特性
        'distance': distance,
        'is_turf': is_turf,
        'track_condition': cond_val,
        'place_code': int(place_code) if place_code.isdigit() else -1,
        'entry_count': entry_count,
        'first_corner_dist': fcd,
        'month': month,
        'distance_category': ['sprint', 'mile', 'mid', 'long'].index(
            _distance_category(distance)
        ),
        'nichi': nichi,
    }

    # B. メンバー構成・脚質分布 — 馬レベル特徴量を集計
    closing_strengths = []
    position_gains = []
    first_corner_ratios = []
    front_runner_rates = []
    pace_sensitivities = []
    last3f_avgs = []
    rpci_members = []
    consumption_count = 0

    for hf in horse_features:
        cs = hf.get('closing_strength', -1)
        if cs != -1:
            closing_strengths.append(cs)

        pg = hf.get('position_gain_last5', -1)
        if pg != -1:
            position_gains.append(pg)

        fcr = hf.get('avg_first_corner_ratio', -1)
        if fcr != -1:
            first_corner_ratios.append(fcr)

        frr = hf.get('front_runner_rate', -1)
        if frr != -1:
            front_runner_rates.append(frr)

        ps = hf.get('pace_sensitivity', -1)
        if ps != -1:
            pace_sensitivities.append(ps)

        l3f = hf.get('last3f_avg_last3', -1)
        if l3f != -1 and l3f > 0:
            last3f_avgs.append(l3f)

        rpci = hf.get('avg_race_rpci_last3', -1)
        if rpci != -1 and rpci > 0:
            rpci_members.append(rpci)

        cf = hf.get('consumption_flag', 0)
        if cf == 1:
            consumption_count += 1

    # closing_strength 集計
    if closing_strengths:
        arr = np.array(closing_strengths)
        feat['closing_strength_mean'] = round(float(np.mean(arr)), 4)
        feat['closing_strength_max'] = round(float(np.max(arr)), 4)
        feat['closing_strength_q75'] = round(float(np.percentile(arr, 75)), 4)
        n_strong = sum(1 for x in closing_strengths if x > 1.0)
        feat['n_strong_closers'] = n_strong
        feat['n_strong_closers_ratio'] = round(n_strong / entry_count, 4) if entry_count > 0 else 0
    else:
        feat['closing_strength_mean'] = -1
        feat['closing_strength_max'] = -1
        feat['closing_strength_q75'] = -1
        feat['n_strong_closers'] = 0
        feat['n_strong_closers_ratio'] = 0

    # position_gain 集計
    if position_gains:
        feat['position_gain_mean'] = round(float(np.mean(position_gains)), 4)
        feat['position_gain_max'] = round(float(np.max(position_gains)), 4)
        feat['n_position_gainers'] = sum(1 for x in position_gains if x > 0.1)
    else:
        feat['position_gain_mean'] = -1
        feat['position_gain_max'] = -1
        feat['n_position_gainers'] = 0

    # first_corner_ratio 集計
    if first_corner_ratios:
        feat['avg_first_corner_ratio_mean'] = round(float(np.mean(first_corner_ratios)), 4)
        feat['running_style_diversity'] = round(float(np.std(first_corner_ratios)), 4)
    else:
        feat['avg_first_corner_ratio_mean'] = -1
        feat['running_style_diversity'] = -1

    # front_runner 集計
    if front_runner_rates:
        fr_count = sum(1 for x in front_runner_rates if x > 0.6)
        feat['front_runner_count'] = fr_count
        feat['front_runner_ratio'] = round(fr_count / entry_count, 4) if entry_count > 0 else 0
    else:
        feat['front_runner_count'] = 0
        feat['front_runner_ratio'] = 0

    # pace_sensitivity 集計
    if pace_sensitivities:
        feat['pace_sensitivity_mean'] = round(float(np.mean(pace_sensitivities)), 4)
    else:
        feat['pace_sensitivity_mean'] = -1

    # last3f_avg 集計
    if last3f_avgs:
        feat['last3f_avg_mean'] = round(float(np.mean(last3f_avgs)), 4)
    else:
        feat['last3f_avg_mean'] = -1

    # C. ペース予測指標
    if first_corner_ratios:
        n_senkou = sum(1 for x in first_corner_ratios if x < 0.3)
        feat['n_senkou_horses'] = n_senkou
        feat['senkou_ratio'] = round(n_senkou / entry_count, 4) if entry_count > 0 else 0
        # ペース圧力: 逃げ馬(front_runner_rate>0.6)＋先行馬(first_corner<0.25)
        n_pace_makers = sum(
            1 for i, fcr in enumerate(first_corner_ratios)
            if fcr < 0.25 or (i < len(front_runner_rates) and front_runner_rates[i] > 0.6)
        )
        feat['pace_pressure'] = round(n_pace_makers / entry_count, 4) if entry_count > 0 else 0
    else:
        feat['n_senkou_horses'] = 0
        feat['senkou_ratio'] = 0
        feat['pace_pressure'] = 0

    if rpci_members:
        feat['avg_race_rpci_members'] = round(float(np.mean(rpci_members)), 2)
    else:
        feat['avg_race_rpci_members'] = -1

    feat['consumption_flag_count'] = consumption_count

    # D. コース歴史統計
    if course_timeline:
        course_stats = course_timeline.lookup(
            venue_name, track_type, distance, track_condition, race_date
        )
        feat.update(course_stats)
    else:
        feat['course_closing_rate'] = -1.0
        feat['course_closing_count'] = 0
        feat['course_avg_rpci'] = -1.0
        feat['track_cond_closing_rate'] = -1.0

    # E. 馬場・開催進行
    cushion = baba_features.get('cushion_value', np.nan) if baba_features else np.nan
    moisture = baba_features.get('moisture_rate', np.nan) if baba_features else np.nan
    feat['cushion_value'] = cushion
    feat['moisture_rate'] = moisture

    # 開催後半フラグ (nichi >= 5 = 芝が荒れて差し有利になりやすい)
    is_late = 1 if nichi >= 5 else 0
    feat['is_late_kaisai'] = is_late
    # 芝 × 開催後半 (芝の開催後半は馬場悪化で差し有利)
    feat['turf_late_kaisai'] = is_turf * is_late
    # 含水率 × 開催後半 (荒れた馬場 + 水分 → 先行不利)
    feat['moisture_x_late'] = moisture * is_late if not np.isnan(moisture) else np.nan
    # クッション値が低い (柔らかい馬場 = 差し有利傾向)
    feat['cushion_low'] = 1 if (not np.isnan(cushion) and cushion < 8.0) else 0

    return feat
