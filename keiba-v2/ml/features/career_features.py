#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
キャリア全走特徴量 + 不確実性フラグ

horse_history_cache + jrdb_sed_index を結合し、
全キャリアIDMデータからトレンド・安定性・ピーク距離を計算。
また、パフォ変動予測の不確実性を示すフラグ特徴量も提供。

Phase 2特徴量 for Performance Change Prediction model.
"""

from typing import Dict, Optional
import statistics


def compute_career_features(
    ketto_num: str,
    race_date: str,
    history_cache: dict,
    jrdb_sed_index: dict,
    current_track_type: str = '',    # 'turf' / 'dirt'
    current_distance: int = 0,
    current_venue_code: str = '',
    current_jockey_code: str = '',
) -> dict:
    """
    全キャリアIDM + 不確実性フラグ特徴量を計算。

    Args:
        ketto_num: 10桁血統登録番号
        race_date: 当該レース日 (YYYY-MM-DD)
        history_cache: {ketto_num: [{race_date, ...}, ...]}
        jrdb_sed_index: {ketto_num_race_date: {idm, ...}}
        current_track_type: 当該レースの芝/ダート
        current_distance: 当該レースの距離
        current_venue_code: 当該レースの場所コード
        current_jockey_code: 当該レースの騎手コード

    Returns:
        dict: career_ / uncertainty_ プレフィックス付き特徴量
    """
    result = {
        # --- キャリアIDM統計 ---
        'career_idm_slope': 0.0,           # 全走IDMの線形回帰傾斜（正=成長中）
        'career_idm_std': -1.0,            # 全走IDMの標準偏差（ムラ度）
        'career_idm_best_vs_recent': 0.0,  # ベストIDM - 直近3走平均（ピークからの距離）
        'career_idm_peak_recency': -1,     # ベストIDMが何走前か（0=直近走）
        'career_idm_cv': -1.0,             # IDM変動係数(std/mean, ムラ度の正規化版)
        'career_idm_range': 0.0,           # max - min IDM（レンジ）
        'career_idm_median': -1.0,         # 全走IDM中央値

        # --- キャリア着順統計 ---
        'career_finish_slope': 0.0,        # 全走着順の線形回帰傾斜（負=改善中）
        'career_consistency': -1.0,        # 着順の変動係数（安定度）
        'career_improvement_runs': 0,      # 直近5走中、前走比IDM改善した回数

        # --- IDM差分統計 ---
        'career_idm_diff_mean': 0.0,       # 全走IDM差分(前走比)の平均
        'career_idm_diff_std': -1.0,       # 全走IDM差分の標準偏差（変動のブレ幅）
        'career_idm_diff_last': 0.0,       # 直近のIDM差分

        # --- 条件替わりIDM変動パターン (Phase 2.5) ---
        'cond_surface_switch_idm_avg': 0.0,   # 芝↔ダート替わり時のIDM変動平均
        'cond_surface_switch_count': 0,        # 芝↔ダート替わり経験回数
        'cond_dist_extend_idm_avg': 0.0,       # 距離延長(+200m以上)時のIDM変動平均
        'cond_dist_shorten_idm_avg': 0.0,      # 距離短縮(-200m以上)時のIDM変動平均
        'cond_layoff_idm_avg': 0.0,            # 休養明け(56日+)復帰走のIDM変動平均
        'cond_layoff_idm_count': 0,            # 休養明け復帰経験回数
        'cond_same_surface_idm_avg': -1.0,     # 同馬場(今回と同じ芝/ダート)でのIDM平均
        'cond_same_dist_idm_avg': -1.0,        # 同距離帯(±200m)でのIDM平均
        'cond_class_up_idm_avg': 0.0,          # 昇級時のIDM変動平均
        'cond_class_down_idm_avg': 0.0,        # 降級時のIDM変動平均

        # --- 条件替わりインタラクション (Phase 2.5b) ---
        # 「今回まさにその条件替わりが起きる」時のみパターン平均を発火
        'cond_now_surface_switch': 0.0,   # 今回芝↔ダ替わり × 過去パターン平均
        'cond_now_dist_extend': 0.0,      # 今回距離延長 × 過去パターン平均
        'cond_now_dist_shorten': 0.0,     # 今回距離短縮 × 過去パターン平均
        'cond_now_layoff': 0.0,           # 今回休養明け × 過去パターン平均
        'cond_now_surface_idm_diff': 0.0, # 同馬場IDM平均 - 全体IDM平均（適性差）
        'cond_now_dist_idm_diff': 0.0,    # 同距離帯IDM平均 - 全体IDM平均（距離適性差）

        # --- 不確実性フラグ ---
        'uncertainty_career_short': 0,     # キャリア3走以下
        'uncertainty_first_surface': 0,    # 初芝 or 初ダート
        'uncertainty_first_distance': 0,   # 初距離帯(±200m以内の経験なし)
        'uncertainty_first_venue': 0,      # 初コース
        'uncertainty_long_layoff': 0,      # 長期休養(140日+, ≈20週)
        'uncertainty_jockey_change': 0,    # 騎手乗替
        'uncertainty_score': 0,            # 不確実性合計スコア(0-6)
    }

    past_runs = history_cache.get(ketto_num, [])
    past = [r for r in past_runs if r.get('race_date', '') < race_date]

    if not past:
        result['uncertainty_career_short'] = 1
        result['uncertainty_score'] = 6  # 全て不明
        return result

    # ソート（時系列順）
    past_sorted = sorted(past, key=lambda r: r['race_date'])
    n_runs = len(past_sorted)

    # === 全走IDMを取得 ===
    idm_series = []  # (run_index, idm)
    for i, r in enumerate(past_sorted):
        rd = r.get('race_date', '')
        sed_key = f"{ketto_num}_{rd}"
        sed = jrdb_sed_index.get(sed_key)
        if sed and sed.get('idm') and sed['idm'] > 0:
            idm_series.append((i, float(sed['idm'])))

    # === キャリアIDM統計 ===
    if len(idm_series) >= 2:
        idm_vals = [v for _, v in idm_series]
        indices = [i for i, _ in idm_series]

        # 線形回帰傾斜（OLS: y=IDM, x=走番号）
        n = len(idm_vals)
        x_mean = sum(indices) / n
        y_mean = sum(idm_vals) / n
        num = sum((x - x_mean) * (y - y_mean) for x, y in zip(indices, idm_vals))
        den = sum((x - x_mean) ** 2 for x in indices)
        if den > 0:
            result['career_idm_slope'] = round(num / den, 3)

        # 標準偏差 / CV
        if n >= 3:
            std = statistics.stdev(idm_vals)
            result['career_idm_std'] = round(std, 2)
            if y_mean > 0:
                result['career_idm_cv'] = round(std / y_mean, 3)

        # ベストIDM vs 直近3走平均
        best_idm = max(idm_vals)
        recent3 = idm_vals[-3:] if len(idm_vals) >= 3 else idm_vals
        recent_avg = statistics.mean(recent3)
        result['career_idm_best_vs_recent'] = round(best_idm - recent_avg, 1)

        # ベストIDMが何走前か
        best_run_idx = max(i for i, v in idm_series if v == best_idm)
        result['career_idm_peak_recency'] = n_runs - 1 - best_run_idx

        # レンジ, 中央値
        result['career_idm_range'] = round(max(idm_vals) - min(idm_vals), 1)
        result['career_idm_median'] = round(statistics.median(idm_vals), 1)

    elif len(idm_series) == 1:
        result['career_idm_median'] = idm_series[0][1]

    # === IDM差分統計 ===
    if len(idm_series) >= 2:
        idm_vals = [v for _, v in idm_series]
        diffs = [idm_vals[i] - idm_vals[i-1] for i in range(1, len(idm_vals))]
        result['career_idm_diff_mean'] = round(statistics.mean(diffs), 2)
        result['career_idm_diff_last'] = round(diffs[-1], 1)
        if len(diffs) >= 2:
            result['career_idm_diff_std'] = round(statistics.stdev(diffs), 2)

        # 直近5走中IDM改善した回数
        recent_diffs = diffs[-5:] if len(diffs) >= 5 else diffs
        result['career_improvement_runs'] = sum(1 for d in recent_diffs if d > 0)

    # === キャリア着順統計 ===
    finish_positions = [r.get('finish_position', 0) for r in past_sorted
                        if r.get('finish_position', 0) > 0]
    if len(finish_positions) >= 3:
        # 着順の線形回帰傾斜
        n_fp = len(finish_positions)
        x_mean_fp = (n_fp - 1) / 2
        y_mean_fp = statistics.mean(finish_positions)
        num_fp = sum((i - x_mean_fp) * (y - y_mean_fp)
                     for i, y in enumerate(finish_positions))
        den_fp = sum((i - x_mean_fp) ** 2 for i in range(n_fp))
        if den_fp > 0:
            result['career_finish_slope'] = round(num_fp / den_fp, 3)

        # 変動係数
        std_fp = statistics.stdev(finish_positions)
        if y_mean_fp > 0:
            result['career_consistency'] = round(std_fp / y_mean_fp, 3)

    # === 条件替わりIDM変動パターン (Phase 2.5) ===
    # 連続走ペアを走査し、条件替わり時のIDM変動を蓄積
    # idm_by_run[i] = run index i のIDM値 (なければNone)
    idm_by_run = {}
    for run_idx, idm_val in idm_series:
        idm_by_run[run_idx] = idm_val

    surface_switch_diffs = []
    dist_extend_diffs = []
    dist_shorten_diffs = []
    layoff_diffs = []
    class_up_diffs = []
    class_down_diffs = []
    same_surface_idms = []
    same_dist_idms = []

    # クラス序列マップ（小さいほど下級）
    _grade_order = {
        '新馬': 1, '未勝利': 2,
        '1勝': 3, '1勝クラス': 3, '500万下': 3,
        '2勝': 4, '2勝クラス': 4, '1000万下': 4,
        '3勝': 5, '3勝クラス': 5, '1600万下': 5,
        'OP': 6, 'オープン': 6, 'L': 6, 'リステッド': 6,
        'G3': 7, 'G2': 8, 'G1': 9,
    }

    for i in range(len(past_sorted)):
        r = past_sorted[i]
        r_idm = idm_by_run.get(i)

        # 同馬場IDM蓄積（今回と同じ芝/ダート）
        if current_track_type and r.get('track_type', '') == current_track_type and r_idm is not None:
            same_surface_idms.append(r_idm)

        # 同距離帯IDM蓄積（今回と±200m以内）
        r_dist = r.get('distance', 0)
        if current_distance > 0 and r_dist > 0 and abs(r_dist - current_distance) <= 200 and r_idm is not None:
            same_dist_idms.append(r_idm)

        # 連続走ペアの条件変化検出（i-1 → i）
        if i == 0:
            continue
        prev = past_sorted[i - 1]
        prev_idm = idm_by_run.get(i - 1)
        if r_idm is None or prev_idm is None:
            continue
        idm_diff = r_idm - prev_idm

        # 芝↔ダート替わり
        r_tt = r.get('track_type', '')
        prev_tt = prev.get('track_type', '')
        if r_tt and prev_tt and r_tt != prev_tt:
            surface_switch_diffs.append(idm_diff)

        # 距離変更
        prev_dist = prev.get('distance', 0)
        if r_dist > 0 and prev_dist > 0:
            dist_change = r_dist - prev_dist
            if dist_change >= 200:
                dist_extend_diffs.append(idm_diff)
            elif dist_change <= -200:
                dist_shorten_diffs.append(idm_diff)

        # 休養明け（56日+）
        try:
            from datetime import date as _date
            rd_cur = _date.fromisoformat(r.get('race_date', ''))
            rd_prev = _date.fromisoformat(prev.get('race_date', ''))
            if (rd_cur - rd_prev).days >= 56:
                layoff_diffs.append(idm_diff)
        except (ValueError, TypeError):
            pass

        # 昇級/降級
        r_grade = _grade_order.get(r.get('grade', ''), 0)
        prev_grade = _grade_order.get(prev.get('grade', ''), 0)
        if r_grade > 0 and prev_grade > 0:
            if r_grade > prev_grade:
                class_up_diffs.append(idm_diff)
            elif r_grade < prev_grade:
                class_down_diffs.append(idm_diff)

    # 結果反映
    if surface_switch_diffs:
        result['cond_surface_switch_idm_avg'] = round(statistics.mean(surface_switch_diffs), 2)
        result['cond_surface_switch_count'] = len(surface_switch_diffs)
    if dist_extend_diffs:
        result['cond_dist_extend_idm_avg'] = round(statistics.mean(dist_extend_diffs), 2)
    if dist_shorten_diffs:
        result['cond_dist_shorten_idm_avg'] = round(statistics.mean(dist_shorten_diffs), 2)
    if layoff_diffs:
        result['cond_layoff_idm_avg'] = round(statistics.mean(layoff_diffs), 2)
        result['cond_layoff_idm_count'] = len(layoff_diffs)
    if same_surface_idms:
        result['cond_same_surface_idm_avg'] = round(statistics.mean(same_surface_idms), 1)
    if same_dist_idms:
        result['cond_same_dist_idm_avg'] = round(statistics.mean(same_dist_idms), 1)
    if class_up_diffs:
        result['cond_class_up_idm_avg'] = round(statistics.mean(class_up_diffs), 2)
    if class_down_diffs:
        result['cond_class_down_idm_avg'] = round(statistics.mean(class_down_diffs), 2)

    # === 条件替わりインタラクション (Phase 2.5b) ===
    # 「今回まさにその条件替わりが起きる」× 過去パターン平均
    if past_sorted:
        last_run = past_sorted[-1]

        # 今回芝↔ダート替わり
        last_tt = last_run.get('track_type', '')
        if current_track_type and last_tt and current_track_type != last_tt:
            result['cond_now_surface_switch'] = result['cond_surface_switch_idm_avg']

        # 今回距離変更
        last_dist = last_run.get('distance', 0)
        if current_distance > 0 and last_dist > 0:
            d_change = current_distance - last_dist
            if d_change >= 200:
                result['cond_now_dist_extend'] = result['cond_dist_extend_idm_avg']
            elif d_change <= -200:
                result['cond_now_dist_shorten'] = result['cond_dist_shorten_idm_avg']

        # 今回休養明け（56日+）
        try:
            from datetime import date as _date
            last_rd = _date.fromisoformat(last_run.get('race_date', ''))
            cur_rd = _date.fromisoformat(race_date)
            if (cur_rd - last_rd).days >= 56:
                result['cond_now_layoff'] = result['cond_layoff_idm_avg']
        except (ValueError, TypeError):
            pass

    # 同馬場/同距離のIDM適性差（全体IDM平均との差）
    if len(idm_series) >= 2:
        overall_idm_avg = statistics.mean([v for _, v in idm_series])
        if result['cond_same_surface_idm_avg'] > -1:
            result['cond_now_surface_idm_diff'] = round(
                result['cond_same_surface_idm_avg'] - overall_idm_avg, 1)
        if result['cond_same_dist_idm_avg'] > -1:
            result['cond_now_dist_idm_diff'] = round(
                result['cond_same_dist_idm_avg'] - overall_idm_avg, 1)

    # === 不確実性フラグ ===
    # キャリア3走以下
    if n_runs <= 3:
        result['uncertainty_career_short'] = 1

    # 初芝/初ダート
    if current_track_type:
        tt_history = set(r.get('track_type', '') for r in past_sorted)
        if current_track_type not in tt_history:
            result['uncertainty_first_surface'] = 1

    # 初距離帯 (±200m以内の経験なし)
    if current_distance > 0:
        dist_history = [r.get('distance', 0) for r in past_sorted if r.get('distance', 0) > 0]
        if dist_history:
            has_similar = any(abs(d - current_distance) <= 200 for d in dist_history)
            if not has_similar:
                result['uncertainty_first_distance'] = 1
        else:
            result['uncertainty_first_distance'] = 1

    # 初コース
    if current_venue_code:
        venue_history = set(r.get('venue_code', '') for r in past_sorted)
        if current_venue_code not in venue_history:
            result['uncertainty_first_venue'] = 1

    # 長期休養 (140日+)
    if past_sorted:
        last_race_date = past_sorted[-1].get('race_date', '')
        if last_race_date and race_date:
            try:
                from datetime import date
                ld = date.fromisoformat(last_race_date)
                cd = date.fromisoformat(race_date)
                days_off = (cd - ld).days
                if days_off >= 140:
                    result['uncertainty_long_layoff'] = 1
            except (ValueError, TypeError):
                pass

    # 騎手乗替
    if current_jockey_code and past_sorted:
        last_jockey = past_sorted[-1].get('jockey_code', '')
        if last_jockey and last_jockey != current_jockey_code:
            result['uncertainty_jockey_change'] = 1

    # 不確実性合計スコア
    result['uncertainty_score'] = (
        result['uncertainty_career_short'] +
        result['uncertainty_first_surface'] +
        result['uncertainty_first_distance'] +
        result['uncertainty_first_venue'] +
        result['uncertainty_long_layoff'] +
        result['uncertainty_jockey_change']
    )

    return result


# 特徴量名リスト（experiment.pyで使用）
CAREER_FEATURE_COLS = [
    # キャリアIDM統計
    'career_idm_slope', 'career_idm_std', 'career_idm_best_vs_recent',
    'career_idm_peak_recency', 'career_idm_cv', 'career_idm_range',
    'career_idm_median',
    # キャリア着順統計
    'career_finish_slope', 'career_consistency', 'career_improvement_runs',
    # IDM差分統計
    'career_idm_diff_mean', 'career_idm_diff_std', 'career_idm_diff_last',
    # 条件替わりIDM変動パターン (Phase 2.5)
    'cond_surface_switch_idm_avg', 'cond_surface_switch_count',
    'cond_dist_extend_idm_avg', 'cond_dist_shorten_idm_avg',
    'cond_layoff_idm_avg', 'cond_layoff_idm_count',
    'cond_same_surface_idm_avg', 'cond_same_dist_idm_avg',
    'cond_class_up_idm_avg', 'cond_class_down_idm_avg',
    # 条件替わりインタラクション (Phase 2.5b)
    'cond_now_surface_switch', 'cond_now_dist_extend', 'cond_now_dist_shorten',
    'cond_now_layoff', 'cond_now_surface_idm_diff', 'cond_now_dist_idm_diff',
    # 不確実性フラグ
    'uncertainty_career_short', 'uncertainty_first_surface',
    'uncertainty_first_distance', 'uncertainty_first_venue',
    'uncertainty_long_layoff', 'uncertainty_jockey_change',
    'uncertainty_score',
]
