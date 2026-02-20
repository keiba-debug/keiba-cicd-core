#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ペース特徴量

レースペースデータ(RPCI等)と馬の走破データを組み合わせた特徴量。
pace_index: {race_id: {rpci, s3, l3, s4, l4, race_trend_v2, lap33, lap_times, ...}} を外部から注入。
"""

from collections import Counter, defaultdict
import numpy as np

# 急坂コース: 中山(06), 阪神(09)
STEEP_VENUES = {'06', '09'}

# 余力ラップ基準閾値 (ch7「競馬思考」ベース)
YORIKI_L1F_THRESHOLD = 11.4    # 基準1: ラスト1F ≤ 11.4秒
YORIKI_L2F_THRESHOLD = 22.7    # 基準2: ラスト2F合計 ≤ 22.7秒
YORIKI_L3F_MARGIN = 0.5        # 基準3: 馬L3がレースL3より0.5秒以上速い
YORIKI_L4F_THRESHOLD = 46.0    # 基準4: ラスト4F ≤ 46.0秒 (1600m以上)
YORIKI_L5F_THRESHOLD = 58.2    # 基準5: ラスト5F ≤ 58.2秒 (1600m以上)
FAST_FINISH_L1F = 11.5         # 速い上がりレースの閾値

# race_trend_v2 → 整数エンコード (瞬発→持続の順序)
TREND_V2_ENCODE = {
    'sprint': 0,
    'sprint_mild': 1,
    'even': 2,
    'long_sprint': 3,
    'sustained_hp': 4,
    'sustained_strong': 5,
    'sustained_doroashi': 6,
}


def _last_nf(lap_times, n):
    """ラスト N ハロンの合計タイムを計算"""
    if not lap_times or len(lap_times) < n:
        return None
    return round(sum(lap_times[-n:]), 1)


def compute_pace_features(
    ketto_num: str,
    race_date: str,
    days_since_last_race: int,
    history_cache: dict,
    pace_index: dict,
) -> dict:
    """
    ペース関連の特徴量を計算。

    pace_index: race_id → {rpci, s3, l3, s4, l4, race_trend_v2, lap33, ...}
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
        # v5.1: 33ラップ系
        'avg_lap33_last3': None,
        'prev_race_lap33': None,
        # v5.1: 適性系
        'best_trend_top3_rate': None,
        'worst_trend_top3_rate': None,
        'trend_versatility': None,
        # v5.2: 余力ラップ系 (ch7 5基準ベース)
        'race_last1f_avg_last3': None,
        'prev_race_last1f': None,
        'race_decel_l1f_avg_last3': None,
        'yoriki_score_last5': None,
        'fast_finish_top3_rate': None,
        # v5.2: race_trend カテゴリ特徴量
        'prev_race_trend_v2_enc': None,
        'dominant_trend_v2_enc': None,
        'trend_switch_count_last5': None,
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

    # ===== v5.1: 33ラップ系特徴量 =====

    # avg_lap33_last3: 直近3走の平均33ラップ値
    lap33_vals = []
    for r in last3:
        pace_data = pace_index.get(r['race_id'], {})
        lap33 = pace_data.get('lap33')
        if lap33 is not None:
            lap33_vals.append(lap33)
    if lap33_vals:
        result['avg_lap33_last3'] = round(np.mean(lap33_vals), 2)

    # prev_race_lap33: 前走の33ラップ値
    prev_lap33 = prev_pace.get('lap33')
    if prev_lap33 is not None:
        result['prev_race_lap33'] = round(prev_lap33, 2)

    # ===== v5.1: 適性系特徴量 =====
    # trend別の3着内率を計算（v2分類を使用）

    if len(past) >= 3:
        trend_stats = defaultdict(lambda: {'total': 0, 'top3': 0})
        for r in past:
            pace_data = pace_index.get(r['race_id'], {})
            trend = pace_data.get('race_trend_v2')
            if not trend:
                continue
            trend_stats[trend]['total'] += 1
            if 1 <= r.get('finish_position', 0) <= 3:
                trend_stats[trend]['top3'] += 1

        # 最低2レース以上のtrendのみ使用
        trend_rates = {}
        for trend, stats in trend_stats.items():
            if stats['total'] >= 2:
                trend_rates[trend] = stats['top3'] / stats['total']

        if trend_rates:
            rates = list(trend_rates.values())
            result['best_trend_top3_rate'] = round(max(rates), 4)
            result['worst_trend_top3_rate'] = round(min(rates), 4)
            # trend_versatility: 標準偏差（低=万能、高=適性偏り）
            if len(rates) >= 2:
                result['trend_versatility'] = round(float(np.std(rates)), 4)

    # ===== v5.2: 余力ラップ特徴量 (ch7 5基準ベース) =====
    # レースの lap_times（1Fごと）からラスト1F/2F等を算出し、
    # 馬の「余力」を定量化する。

    # race_last1f_avg_last3: 直近3走のレースラスト1F平均
    last1f_vals = []
    for r in last3:
        pace_data = pace_index.get(r['race_id'], {})
        laps = pace_data.get('lap_times')
        l1f = _last_nf(laps, 1)
        if l1f is not None:
            last1f_vals.append(l1f)
    if last1f_vals:
        result['race_last1f_avg_last3'] = round(np.mean(last1f_vals), 2)

    # prev_race_last1f: 前走のレースラスト1F
    prev_laps = prev_pace.get('lap_times')
    prev_l1f = _last_nf(prev_laps, 1)
    if prev_l1f is not None:
        result['prev_race_last1f'] = round(prev_l1f, 1)

    # race_decel_l1f_avg_last3: ラスト1Fの減速度(last_1f - 2nd_to_last_1f)の3走平均
    # 正=減速(疲労環境), 負=加速(余力環境)
    decel_vals = []
    for r in last3:
        pace_data = pace_index.get(r['race_id'], {})
        laps = pace_data.get('lap_times')
        if laps and len(laps) >= 2:
            decel = laps[-1] - laps[-2]
            decel_vals.append(decel)
    if decel_vals:
        result['race_decel_l1f_avg_last3'] = round(np.mean(decel_vals), 3)

    # yoriki_score_last5: 直近5走で余力基準を満たしたレース数（3着以内限定）
    # ch7の5基準: L1F≤11.4, L2F≤22.7, 馬L3差≥0.5, L4F≤46.0(1600m+), L5F≤58.2(1600m+)
    yoriki_count = 0
    yoriki_eligible = 0
    for r in last5:
        fp = r.get('finish_position', 0)
        if not (1 <= fp <= 3):
            continue
        pace_data = pace_index.get(r['race_id'], {})
        laps = pace_data.get('lap_times')
        if not laps:
            continue
        yoriki_eligible += 1
        dist = pace_data.get('distance') or r.get('distance', 0)
        score = 0
        # 基準1: ラスト1F
        l1f = _last_nf(laps, 1)
        if l1f is not None and l1f <= YORIKI_L1F_THRESHOLD:
            score += 1
        # 基準2: ラスト2F
        l2f = _last_nf(laps, 2)
        if l2f is not None and l2f <= YORIKI_L2F_THRESHOLD:
            score += 1
        # 基準3: 馬L3がレースL3より0.5秒以上速い
        horse_l3 = r.get('last_3f', 0)
        race_l3 = pace_data.get('l3')
        if horse_l3 > 0 and race_l3 and race_l3 > 0:
            if race_l3 - horse_l3 >= YORIKI_L3F_MARGIN:
                score += 1
        # 基準4: ラスト4F (1600m以上)
        if dist >= 1600:
            l4f = _last_nf(laps, 4)
            if l4f is not None and l4f <= YORIKI_L4F_THRESHOLD:
                score += 1
        # 基準5: ラスト5F (1600m以上)
        if dist >= 1600:
            l5f = _last_nf(laps, 5)
            if l5f is not None and l5f <= YORIKI_L5F_THRESHOLD:
                score += 1
        if score > 0:
            yoriki_count += 1
    if yoriki_eligible > 0:
        result['yoriki_score_last5'] = yoriki_count

    # fast_finish_top3_rate: 速い上がりレース(L1F≤11.5)での好走率
    fast_total = 0
    fast_top3 = 0
    for r in past:
        pace_data = pace_index.get(r['race_id'], {})
        laps = pace_data.get('lap_times')
        l1f = _last_nf(laps, 1)
        if l1f is not None and l1f <= FAST_FINISH_L1F:
            fast_total += 1
            if 1 <= r.get('finish_position', 0) <= 3:
                fast_top3 += 1
    if fast_total >= 2:
        result['fast_finish_top3_rate'] = round(fast_top3 / fast_total, 4)

    # ===== v5.2: race_trend カテゴリ特徴量 =====

    # prev_race_trend_v2_enc: 前走のrace_trend_v2を整数エンコード
    prev_trend = prev_pace.get('race_trend_v2')
    if prev_trend and prev_trend in TREND_V2_ENCODE:
        result['prev_race_trend_v2_enc'] = TREND_V2_ENCODE[prev_trend]

    # 直近5走のtrend_v2を収集
    trend_seq = []
    for r in last5:
        pace_data = pace_index.get(r['race_id'], {})
        t = pace_data.get('race_trend_v2')
        if t and t in TREND_V2_ENCODE:
            trend_seq.append(t)

    if trend_seq:
        # dominant_trend_v2_enc: 最頻のtrend_v2
        most_common = Counter(trend_seq).most_common(1)[0][0]
        result['dominant_trend_v2_enc'] = TREND_V2_ENCODE[most_common]

        # trend_switch_count_last5: 連続するレース間でtrendが変わった回数
        if len(trend_seq) >= 2:
            switches = sum(1 for i in range(1, len(trend_seq)) if trend_seq[i] != trend_seq[i - 1])
            result['trend_switch_count_last5'] = switches

    return result
