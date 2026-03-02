#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ML Experiment: LightGBM 3モデル(P/W/AR)学習・評価パイプライン

モデルバージョンは model_meta.json の version フィールドで管理。
旧バージョンは versions/ に自動アーカイブされる。

3モデル体制 (市場系特徴量除外):
  Place (P):  is_top3分類 → 好走確率 (model_p.txt)
  Win   (W):  is_win分類  → 勝利確率 (model_w.txt)
  Aura  (AR): 着差回帰    → 能力予測 (model_ar.txt)

Usage:
    python -m ml.experiment [--train-years 2020-2024] [--test-years 2025-2026]
    python -m ml.experiment --no-db  # DB未使用（旧JSON確定オッズ）
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config

# === Value Bet閾値 ===
VALUE_BET_MIN_GAP = 3  # predict.pyと統一

# === 特徴量定義 ===

# JRA-VAN基本特徴量
BASE_FEATURES = [
    'age', 'sex', 'futan', 'horse_weight', 'horse_weight_diff',
    'wakuban', 'distance', 'track_type', 'track_condition', 'entry_count',
    # v4.0
    'month', 'nichi',
    # v5.40: 馬場分析特徴量
    'place_code', 'first_corner_dist',
]

# 過去走特徴量
PAST_FEATURES = [
    'avg_finish_last3', 'best_finish_last5', 'last3f_avg_last3',
    'days_since_last_race', 'win_rate_all', 'top3_rate_all',
    'total_career_races', 'recent_form_trend',
    'venue_top3_rate', 'track_type_top3_rate', 'distance_fitness',
    'prev_race_entry_count', 'entry_count_change',
    # v4.0
    'best_l3f_last5', 'finish_std_last5', 'comeback_strength_last5',
    # v5.4: ベイズ平滑化レート + career_stage
    'win_rate_smoothed', 'top3_rate_smoothed',
    'venue_top3_rate_smoothed', 'track_type_top3_rate_smoothed',
    'distance_fitness_smoothed', 'career_stage',
    # v5.6: 前走レースレベル
    'prev_race_level_vs_class', 'avg_race_level_last3', 'prev_race_level_rank',
    # v5.45: Phase P — prev→current 直接比較
    'prev_finish', 'prev_last3f', 'distance_change',
    'track_type_change', 'condition_change', 'prev_odds',
    'condition_top3_rate', 'condition_top3_rate_smoothed',
    'heavy_track_top3_rate',
    'exact_distance_top3_rate', 'exact_distance_top3_rate_smoothed',
    'surface_switch_top3_rate', 'distance_direction_top3_rate',
    'field_size_category_top3_rate',
]

# 調教師特徴量（100%マッチ）
TRAINER_FEATURES = [
    'trainer_win_rate', 'trainer_top3_rate', 'trainer_venue_top3_rate',
]

# 騎手特徴量
JOCKEY_FEATURES = [
    'jockey_win_rate', 'jockey_top3_rate', 'jockey_venue_top3_rate',
    # v5.6: 接戦勝率
    'jockey_close_win_rate',
]

# 脚質特徴量 (v3.1)
RUNNING_STYLE_FEATURES = [
    'avg_first_corner_ratio', 'avg_last_corner_ratio', 'position_gain_last5',
    'front_runner_rate', 'pace_sensitivity', 'closing_strength',
    'running_style_consistency', 'last_race_corner1_ratio',
]

# ローテ・コンディション特徴量 (v3.1)
ROTATION_FEATURES = [
    'futan_diff', 'futan_diff_ratio', 'weight_change_ratio',
    'prev_race_popularity',
    # v4.0
    'jockey_change',
    # v5.1: 降格ローテ
    'prev_grade_level', 'grade_level_diff', 'venue_rank_diff',
    'is_koukaku_venue', 'is_koukaku_female', 'is_koukaku_season',
    'is_koukaku_age', 'is_koukaku_distance', 'is_koukaku_turf_to_dirt',
    'is_koukaku_handicap', 'koukaku_rote_count',
]

# ペース特徴量 (v3.1)
PACE_FEATURES = [
    'avg_race_rpci_last3', 'prev_race_rpci', 'consumption_flag',
    'last3f_vs_race_l3_last3', 'steep_course_experience', 'steep_course_top3_rate',
    # v4.0
    'l3_unrewarded_rate_last5',
    # v5.1: 33ラップ系 + 適性系
    'avg_lap33_last3', 'prev_race_lap33',
    'best_trend_top3_rate', 'worst_trend_top3_rate', 'trend_versatility',
    # v5.2: 余力ラップ系 (ch7 5基準ベース) — 実験済み、ROI低下のため無効化
    # 'race_last1f_avg_last3', 'prev_race_last1f', 'race_decel_l1f_avg_last3',
    # 'yoriki_score_last5', 'fast_finish_top3_rate',
    # v5.2: race_trend カテゴリ特徴量 — 実験済み、低重要度のため無効化
    # 'prev_race_trend_v2_enc', 'dominant_trend_v2_enc', 'trend_switch_count_last5',
]

# 調教特徴量 (v3.3)
TRAINING_FEATURES = [
    'training_arrow_value',
    'oikiri_5f', 'oikiri_3f', 'oikiri_1f',
    'oikiri_intensity_code', 'oikiri_has_awase',
    'training_session_count', 'rest_weeks', 'oikiri_is_slope',
    # v4.0: KB印・レーティング
    'kb_rating',
    # v5.10: KB AI指数 — importance 0 (2025年〜のみ、training期間で全NaN)
    # 'kb_ai_index',
    # v4.1: CK_DATA lapRank
    'ck_laprank_score', 'ck_laprank_class', 'ck_laprank_accel',
    'ck_time_rank', 'ck_final_laprank_score',
    'ck_final_time4f', 'ck_final_lap1',
]

# KB印（市場相関が高いためMARKET扱い）
KB_MARK_FEATURES = ['kb_mark_point', 'kb_aggregate_mark_point']

# スピード指数特徴量 (v3.5)
SPEED_FEATURES = [
    'speed_idx_latest', 'speed_idx_best5', 'speed_idx_avg3',
    'speed_idx_trend', 'speed_idx_std',
]

# コメントNLP特徴量 (v5.3)
COMMENT_FEATURES = [
    'comment_stable_condition', 'comment_stable_confidence',
    'comment_stable_mark', 'comment_stable_excuse_flag',
    'comment_interview_condition', 'comment_interview_excuse_score',
    'comment_memo_condition', 'comment_memo_trouble_score',
    'comment_has_stable', 'comment_has_interview',
]

# 出遅れ特徴量 (v5.4) — importance 0 (hassouデータカバレッジ不足)
SLOW_START_FEATURES = [
    # 'horse_slow_start_rate', 'horse_slow_start_last5',
    # 'horse_slow_start_resilience',
]

# 血統特徴量 (v5.10): 事前計算の集計統計量
# v5.7: LabelEncoding直接投入は過学習で失敗
# v5.8-v5.9: バグデータ(母をsireとして集計)で偽の大幅改善
# v5.10: オフセット修正後の正しいデータでAUC改善+プリセットROI大幅改善
PEDIGREE_FEATURES = [
    'sire_top3_rate', 'bms_top3_rate', 'dam_top3_rate',    # H0: ベースライン
    'sire_fresh_advantage', 'sire_tight_penalty',           # H3/H4: 休み明け/間隔詰め
    'bms_fresh_advantage', 'bms_tight_penalty',             # H3/H4: BMS版
    'dam_fresh_advantage', 'dam_tight_penalty',             # H3/H4: Dam版
    'sire_sprint_top3_rate', 'sire_sustained_top3_rate',    # H5: 瞬発/持続(sire)
    'sire_finish_type_pref',                                # H5: 瞬発-持続 差分
    'bms_sprint_top3_rate', 'bms_sustained_top3_rate',      # H5: 瞬発/持続(bms)
    'bms_finish_type_pref',                                 # H5: BMS版差分
    'dam_sprint_top3_rate', 'dam_sustained_top3_rate',      # H5: 瞬発/持続(dam)
    'dam_finish_type_pref',                                 # H5: Dam版差分
    'sire_maturity_index',                                  # H6: 成長曲線(sire)
    'bms_maturity_index',                                   # H6: 成長曲線(bms)
    'dam_maturity_index',                                   # H6: 成長曲線(dam)
]

# 馬場特徴量 (v5.41): クッション値 + 含水率
BABA_FEATURES = [
    'cushion_value',    # 芝クッション値 (9.5=硬い高速, 7.0=柔らかい重馬場級)
    'moisture_rate',    # 走路面の含水率 (turf→turf moisture, dirt→dirt moisture)
]

# 市場系特徴量（Model Bでは除外）
# ※独自分析系（CK調教・レース分類）は v5.42 でVALUEに復帰
#   CK調教ラップ = 馬のコンディション客観データ（独自分析の軸）
#   レース分類 = 降格ローテ等の競走力学（独自分析の軸）
MARKET_FEATURES = {
    'odds', 'popularity', 'odds_rank', 'popularity_trend',
    'kb_mark_point', 'kb_aggregate_mark_point',  # v4.0: 印は市場と相関
    # v5.3: ヘッダーマークは honshi_mark と相関 → MARKET
    'comment_stable_mark',
    # v5.4: ベイズ平滑化レートは生rate+オッズと相関 → MARKET
    # （Model B精度向上がVB gap効果を殺すため除外）
    'win_rate_smoothed', 'top3_rate_smoothed',
    'venue_top3_rate_smoothed', 'track_type_top3_rate_smoothed',
    'distance_fitness_smoothed',
    # v5.45: Phase P — 平滑化条件適性率 + 前走オッズ
    'condition_top3_rate_smoothed', 'exact_distance_top3_rate_smoothed',
    'prev_odds',
}

# 派生特徴量
DERIVED_FEATURES = ['odds_rank']

# 全特徴量（Market含む、FEATURE_COLS_VALUE導出用）
FEATURE_COLS_ALL = (
    BASE_FEATURES + ['odds', 'popularity'] + DERIVED_FEATURES +
    PAST_FEATURES + TRAINER_FEATURES + JOCKEY_FEATURES +
    RUNNING_STYLE_FEATURES + ROTATION_FEATURES + ['popularity_trend'] +
    PACE_FEATURES + TRAINING_FEATURES + KB_MARK_FEATURES + SPEED_FEATURES +
    COMMENT_FEATURES + SLOW_START_FEATURES + PEDIGREE_FEATURES +
    BABA_FEATURES
)

# 共通特徴量（市場系除外 — 全モデル共通）
FEATURE_COLS_VALUE = [f for f in FEATURE_COLS_ALL if f not in MARKET_FEATURES]

# ハイパーパラメータ — Place (P) / Win (W) / Aura (AR)
PARAMS_P = {
    'objective': 'binary',
    'metric': 'auc',
    'num_leaves': 127,
    'learning_rate': 0.03,
    'feature_fraction': 0.8,
    'bagging_fraction': 0.8,
    'bagging_freq': 5,
    'min_child_samples': 50,
    'reg_alpha': 0.1,
    'reg_lambda': 1.5,
    'max_depth': 8,
    'verbose': -1,
    'seed': 42,
    'bagging_seed': 42,
    'feature_fraction_seed': 42,
}

# Win モデル用パラメータ（is_win は ~6-7% と不均衡 → scale_pos_weight で補正）
PARAMS_W = {
    **PARAMS_P,
    'scale_pos_weight': 5.0,
}

# 回帰モデル用パラメータ (着差回帰: Huber loss)
PARAMS_AR = {
    'objective': 'huber',
    'alpha': 2.0,  # Huber delta
    'metric': 'mae',
    'num_leaves': 127,
    'learning_rate': 0.03,
    'feature_fraction': 0.8,
    'bagging_fraction': 0.8,
    'bagging_freq': 5,
    'min_child_samples': 50,
    'reg_alpha': 0.1,
    'reg_lambda': 1.5,
    'max_depth': 8,
    'verbose': -1,
    'seed': 42,
    'bagging_seed': 42,
    'feature_fraction_seed': 42,
}


def load_race_json(race_id: str, date: str) -> dict:
    """レースJSONを読み込む"""
    parts = date.split('-')
    path = config.races_dir() / parts[0] / parts[1] / parts[2] / f"race_{race_id}.json"
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _iter_date_index(date_index: dict):
    """date_indexから(date_str, race_id)ペアをイテレート（新旧両形式対応）"""
    for date_str, day_data in sorted(date_index.items()):
        if isinstance(day_data, dict) and 'tracks' in day_data:
            for track in day_data['tracks']:
                for race in track.get('races', []):
                    yield date_str, race['id']
        elif isinstance(day_data, list):
            for race_id in day_data:
                yield date_str, race_id


def build_pace_index(date_index: dict) -> dict:
    """全レースJSONからペースデータを抽出して辞書化"""
    print("[Load] Building pace index...")
    pace_index = {}
    count = 0
    errors = 0

    for date_str, race_id in _iter_date_index(date_index):
        try:
            race = load_race_json(race_id, date_str)
            pace = race.get('pace') or {}
            if pace.get('rpci'):
                pace_index[race_id] = {
                    'rpci': pace.get('rpci'),
                    's3': pace.get('s3'),
                    'l3': pace.get('l3'),
                    's4': pace.get('s4'),
                    'l4': pace.get('l4'),
                    'race_trend': pace.get('race_trend'),
                    'race_trend_v2': pace.get('race_trend_v2'),
                    'lap33': pace.get('lap33'),
                    'lap_times': pace.get('lap_times'),
                }
                # レース基本情報もpace_indexに含める
                pace_index[race_id]['distance'] = race.get('distance')
                pace_index[race_id]['track_type'] = race.get('track_type')
                pace_index[race_id]['venue_code'] = race.get('venue_code')
            count += 1
        except Exception:
            errors += 1

    print(f"  Pace index: {len(pace_index):,} races with pace data "
          f"(of {count:,} total, {errors} errors)")
    return pace_index


def build_kb_ext_index(date_index: dict) -> dict:
    """kb_ext JSONからレース単位の調教データインデックスを構築

    Returns:
        dict: race_id_16 -> kb_ext JSONの内容
    """
    print("[Load] Building keibabook ext index...")
    kb_dir = config.keibabook_dir()
    kb_index = {}
    errors = 0

    for date_str, race_id in _iter_date_index(date_index):
        parts = date_str.split('-')
        day_dir = kb_dir / parts[0] / parts[1] / parts[2]
        if not day_dir.exists():
            continue

        kb_path = day_dir / f"kb_ext_{race_id}.json"
        if kb_path.exists():
            try:
                with open(kb_path, encoding='utf-8') as f:
                    kb_index[race_id] = json.load(f)
            except Exception:
                errors += 1

    print(f"  KB ext index: {len(kb_index):,} races (errors={errors})")
    return kb_index


def build_training_summary_index(date_index: dict) -> dict:
    """training_summary.jsonからCK_DATA調教インデックスを構築

    Returns:
        dict: date_str -> ketto_num -> summary_dict
    """
    print("[Load] Building CK_DATA training summary index...")
    ts_index = {}
    file_count = 0
    horse_count = 0

    for date_str in sorted(date_index.keys()):
        parts = date_str.split('-')
        ts_path = (config.races_dir() / parts[0] / parts[1] / parts[2]
                   / "temp" / "training_summary.json")
        if not ts_path.exists():
            continue
        try:
            with open(ts_path, encoding='utf-8') as f:
                data = json.load(f)
            summaries = data.get('summaries', {})
            day_index = {}
            for _name, entry in summaries.items():
                kn = entry.get('kettoNum', '')
                if kn:
                    day_index[kn] = entry
            if day_index:
                ts_index[date_str] = day_index
                horse_count += len(day_index)
            file_count += 1
        except Exception:
            pass

    print(f"  Training summary: {file_count:,} dates, "
          f"{horse_count:,} horse-entries")
    return ts_index


def build_pit_personnel_timeline(years: List[int] = None) -> Tuple[dict, dict]:
    """SE_DATAから調教師・騎手の累積タイムラインを構築（point-in-time safe）

    各人物について、各レース日の終了時点での累積統計を記録。
    ルックアップ時は bisect_left(dates, race_date) - 1 で race_date 以前の統計を取得。

    Returns:
        (trainer_timeline, jockey_timeline)
        timeline = {code: {dates: [...], total: [...], wins: [...], top3: [...],
                          venue: {vc: {dates, total, wins, top3}}}}
    """
    from collections import defaultdict
    from core.jravan import se_parser

    if years is None:
        years = list(range(2020, 2027))

    print(f"[PIT] Building personnel timeline from SE_DATA {years[0]}-{years[-1]}...")

    # Collect all SE_DATA records
    records = []
    for rec in se_parser.scan(years):
        fp = rec.get('finish_position', 0)
        if fp <= 0:
            continue
        records.append(rec)
    records.sort(key=lambda r: r['race_date'])
    print(f"  SE records: {len(records):,}")

    # Running cumulative stats per person
    # {code: {total, wins, top3, venue: {vc: {total, wins, top3}}}}
    trainer_run = defaultdict(lambda: {
        'total': 0, 'wins': 0, 'top3': 0,
        'venue': defaultdict(lambda: {'total': 0, 'wins': 0, 'top3': 0}),
    })
    jockey_run = defaultdict(lambda: {
        'total': 0, 'wins': 0, 'top3': 0,
        'venue': defaultdict(lambda: {'total': 0, 'wins': 0, 'top3': 0}),
    })

    # Timeline builders: {code: {dates: [], total: [], wins: [], top3: [],
    #                             venue: {vc: {dates, total, wins, top3}}}}
    trainer_tl = defaultdict(lambda: {
        'dates': [], 'total': [], 'wins': [], 'top3': [],
        'venue': defaultdict(lambda: {'dates': [], 'total': [], 'wins': [], 'top3': []}),
    })
    jockey_tl = defaultdict(lambda: {
        'dates': [], 'total': [], 'wins': [], 'top3': [],
        'venue': defaultdict(lambda: {'dates': [], 'total': [], 'wins': [], 'top3': []}),
        'close': {'dates': [], 'wins': [], 'seconds': []},
    })

    # Group records by date
    from itertools import groupby
    for date, group in groupby(records, key=lambda r: r['race_date']):
        batch = list(group)

        # Collect codes active today
        codes_today_tr = set()
        codes_today_jk = set()
        for rec in batch:
            tc = rec.get('trainer_code', '')
            jc = rec.get('jockey_code', '')
            if tc:
                codes_today_tr.add(tc)
            if jc:
                codes_today_jk.add(jc)

        # Update running stats with today's results FIRST
        for rec in batch:
            fp = rec['finish_position']
            vc = rec.get('venue_code', '')
            tc = rec.get('trainer_code', '')
            jc = rec.get('jockey_code', '')

            if tc:
                t = trainer_run[tc]
                t['total'] += 1
                if fp == 1:
                    t['wins'] += 1
                if fp <= 3:
                    t['top3'] += 1
                if vc:
                    tv = t['venue'][vc]
                    tv['total'] += 1
                    if fp == 1:
                        tv['wins'] += 1
                    if fp <= 3:
                        tv['top3'] += 1

            if jc:
                j = jockey_run[jc]
                j['total'] += 1
                if fp == 1:
                    j['wins'] += 1
                if fp <= 3:
                    j['top3'] += 1
                if vc:
                    jv = j['venue'][vc]
                    jv['total'] += 1
                    if fp == 1:
                        jv['wins'] += 1
                    if fp <= 3:
                        jv['top3'] += 1

        # Take snapshot AFTER this date's races (bisect_left - 1 で前日以前を取得)
        for tc in codes_today_tr:
            r = trainer_run[tc]
            tl = trainer_tl[tc]
            tl['dates'].append(date)
            tl['total'].append(r['total'])
            tl['wins'].append(r['wins'])
            tl['top3'].append(r['top3'])

        for jc in codes_today_jk:
            r = jockey_run[jc]
            tl = jockey_tl[jc]
            tl['dates'].append(date)
            tl['total'].append(r['total'])
            tl['wins'].append(r['wins'])
            tl['top3'].append(r['top3'])

    # Venue snapshots: take final cumulative for each (code, venue) after processing all dates
    # → actually we need per-date venue snapshots too. Rebuild them.
    # The above only snapshots the overall totals. For venue, we need to track
    # when each venue stat changes. Simpler approach: post-process.
    # For each code, iterate through all dates and record venue stats at each snapshot.
    # But that's expensive. Instead, let's rebuild venue timelines separately.

    # Rebuild venue timelines from records (grouped by code+venue+date)
    _build_venue_timelines(records, trainer_tl, jockey_tl)

    # Build close-finish timeline for jockeys from race JSONs
    _build_close_timeline(jockey_tl)

    n_tr = len(trainer_tl)
    n_jk = len(jockey_tl)
    print(f"  Trainer timeline: {n_tr:,} trainers")
    print(f"  Jockey timeline:  {n_jk:,} jockeys")

    return dict(trainer_tl), dict(jockey_tl)


def _build_venue_timelines(records: list, trainer_tl: dict, jockey_tl: dict):
    """レコードからvenue別の累積タイムラインを構築"""
    from collections import defaultdict
    from itertools import groupby

    # trainer venue running stats: {(tc, vc): {total, wins, top3}}
    tr_venue_run = defaultdict(lambda: {'total': 0, 'wins': 0, 'top3': 0})
    jk_venue_run = defaultdict(lambda: {'total': 0, 'wins': 0, 'top3': 0})

    for date, group in groupby(records, key=lambda r: r['race_date']):
        batch = list(group)

        # Collect (code, venue) pairs active today
        tr_pairs = set()
        jk_pairs = set()
        for rec in batch:
            tc = rec.get('trainer_code', '')
            jc = rec.get('jockey_code', '')
            vc = rec.get('venue_code', '')
            if tc and vc:
                tr_pairs.add((tc, vc))
            if jc and vc:
                jk_pairs.add((jc, vc))

        # Update running stats FIRST
        for rec in batch:
            fp = rec['finish_position']
            vc = rec.get('venue_code', '')
            tc = rec.get('trainer_code', '')
            jc = rec.get('jockey_code', '')

            if tc and vc:
                v = tr_venue_run[(tc, vc)]
                v['total'] += 1
                if fp == 1:
                    v['wins'] += 1
                if fp <= 3:
                    v['top3'] += 1

            if jc and vc:
                v = jk_venue_run[(jc, vc)]
                v['total'] += 1
                if fp == 1:
                    v['wins'] += 1
                if fp <= 3:
                    v['top3'] += 1

        # Snapshot AFTER update
        for tc, vc in tr_pairs:
            r = tr_venue_run[(tc, vc)]
            tl = trainer_tl[tc]['venue'][vc]
            tl['dates'].append(date)
            tl['total'].append(r['total'])
            tl['wins'].append(r['wins'])
            tl['top3'].append(r['top3'])

        for jc, vc in jk_pairs:
            r = jk_venue_run[(jc, vc)]
            tl = jockey_tl[jc]['venue'][vc]
            tl['dates'].append(date)
            tl['total'].append(r['total'])
            tl['wins'].append(r['wins'])
            tl['top3'].append(r['top3'])

            if jc and vc:
                v = jk_venue_run[(jc, vc)]
                v['total'] += 1
                if fp == 1:
                    v['wins'] += 1
                if fp <= 3:
                    v['top3'] += 1


def _build_close_timeline(jockey_tl: dict):
    """race JSONから騎手の接戦勝率累積タイムラインを構築"""
    from collections import defaultdict

    print("[PIT] Building close-finish timeline from race JSONs...")

    # Running stats: {jc: {wins, seconds}}
    close_run = defaultdict(lambda: {'wins': 0, 'seconds': 0})
    # Collect all close events with dates
    events = []

    races_dir = config.races_dir()
    race_files = sorted(races_dir.glob("**/race_[0-9]*.json"))
    race_count = 0
    close_count = 0

    for json_file in race_files:
        try:
            data = json.loads(json_file.read_text(encoding='utf-8'))
        except Exception:
            continue
        race_count += 1
        race_date = data.get('date', '')
        if not race_date:
            continue

        entries = data.get('entries', [])
        first = second = None
        for e in entries:
            fp = e.get('finish_position', 0)
            if fp == 1:
                first = e
            elif fp == 2:
                second = e
        if not first or not second:
            continue

        t1 = _parse_race_time(first.get('time', ''))
        t2 = _parse_race_time(second.get('time', ''))
        if t1 is None or t2 is None:
            continue

        if abs(t2 - t1) <= 0.1:
            close_count += 1
            jc1 = first.get('jockey_code', '')
            jc2 = second.get('jockey_code', '')
            if jc1:
                events.append((race_date, jc1, 'win'))
            if jc2:
                events.append((race_date, jc2, 'second'))

    events.sort(key=lambda x: x[0])
    print(f"  Close finishes: {close_count:,} from {race_count:,} races")

    # Build cumulative timeline from sorted events
    from itertools import groupby
    for date, group in groupby(events, key=lambda x: x[0]):
        batch = list(group)
        codes_today = set(b[1] for b in batch)

        # Update FIRST
        for _, jc, result_type in batch:
            if result_type == 'win':
                close_run[jc]['wins'] += 1
            else:
                close_run[jc]['seconds'] += 1

        # Snapshot AFTER update
        for jc in codes_today:
            r = close_run[jc]
            tl = jockey_tl[jc]['close']
            tl['dates'].append(date)
            tl['wins'].append(r['wins'])
            tl['seconds'].append(r['seconds'])


def _parse_race_time(time_str: str):
    """走破タイム文字列を秒に変換 (例: '1:14.1' -> 74.1)"""
    if not time_str:
        return None
    try:
        if ':' in time_str:
            parts = time_str.split(':')
            return float(parts[0]) * 60 + float(parts[1])
        return float(time_str)
    except (ValueError, IndexError):
        return None


def build_pit_sire_timeline(date_index: dict, pedigree_index: dict) -> Tuple[dict, dict, dict]:
    """レースJSONからsire/dam/bms累積タイムラインを構築（PIT safe）

    各sire/dam/bms IDについて、各レース日の終了時点での累積統計を記録。
    ルックアップ時は bisect_left(dates, race_date) - 1 で race_date 以前の統計を取得。

    Returns:
        (sire_tl, dam_tl, bms_tl)
    """
    from collections import defaultdict
    from itertools import groupby
    from datetime import datetime as dt

    # Thresholds (same as build_sire_stats.py)
    FRESH_DAYS = 56
    TIGHT_DAYS = 21
    RPCI_SPRINT = 49
    RPCI_SUSTAINED = 53
    YOUNG_MAX = 3
    MATURE_MIN = 4

    COUNTER_KEYS = [
        'total', 'top3',
        'fresh_runs', 'fresh_top3',
        'normal_runs', 'normal_top3',
        'tight_runs', 'tight_top3',
        'sprint_runs', 'sprint_top3',
        'sustained_runs', 'sustained_top3',
        'young_runs', 'young_top3',
        'mature_runs', 'mature_top3',
    ]

    def _new_accum():
        return {k: 0 for k in COUNTER_KEYS}

    def _new_tl():
        d = {'dates': []}
        for k in COUNTER_KEYS:
            d[k] = []
        return d

    print("[PIT] Building sire/dam/bms timeline from race JSONs...")

    sire_run = defaultdict(_new_accum)
    dam_run = defaultdict(_new_accum)
    bms_run = defaultdict(_new_accum)
    sire_tl = defaultdict(_new_tl)
    dam_tl = defaultdict(_new_tl)
    bms_tl = defaultdict(_new_tl)

    horse_last_date: dict = {}  # ketto_num → date string

    # Collect and group by date
    all_races = sorted(_iter_date_index(date_index), key=lambda x: x[0])
    race_count = 0
    entry_count = 0

    for date_str, date_group in groupby(all_races, key=lambda x: x[0]):
        date_races = list(date_group)

        # Process all races for this date
        sire_ids_today = set()
        dam_ids_today = set()
        bms_ids_today = set()
        updates = []  # (entity_type_id_tuples, is_top3, rest_cond, pace_cond, age_cond, ketto_num)

        for _, race_id in date_races:
            try:
                race = load_race_json(race_id, date_str)
            except Exception:
                continue
            race_count += 1
            rpci = (race.get('pace') or {}).get('rpci')

            for entry in race.get('entries', []):
                ketto_num = entry.get('ketto_num', '')
                if not ketto_num:
                    continue
                fp = entry.get('finish_position')
                if fp is None or fp == 0:
                    continue

                ped = pedigree_index.get(ketto_num)
                if not ped:
                    continue
                sire_id = ped.get('sire')
                dam_id = ped.get('dam')
                bms_id = ped.get('bms')
                if not sire_id and not dam_id and not bms_id:
                    continue

                entry_count += 1

                # Rest days classification
                prev = horse_last_date.get(ketto_num)
                days = None
                if prev:
                    try:
                        days = (dt.strptime(date_str, '%Y-%m-%d') - dt.strptime(prev, '%Y-%m-%d')).days
                    except ValueError:
                        pass

                if days is None:
                    rest_cond = 'debut'
                elif days >= FRESH_DAYS:
                    rest_cond = 'fresh'
                elif days <= TIGHT_DAYS:
                    rest_cond = 'tight'
                else:
                    rest_cond = 'normal'

                # Pace classification
                pace_cond = None
                if rpci is not None:
                    if rpci <= RPCI_SPRINT:
                        pace_cond = 'sprint'
                    elif rpci >= RPCI_SUSTAINED:
                        pace_cond = 'sustained'

                # Age classification
                age = entry.get('age')
                age_cond = None
                if age and age > 0:
                    if age <= YOUNG_MAX:
                        age_cond = 'young'
                    elif age >= MATURE_MIN:
                        age_cond = 'mature'

                is_top3 = fp <= 3
                if sire_id:
                    sire_ids_today.add(sire_id)
                if dam_id:
                    dam_ids_today.add(dam_id)
                if bms_id:
                    bms_ids_today.add(bms_id)

                updates.append((sire_id, dam_id, bms_id, is_top3,
                                rest_cond, pace_cond, age_cond, ketto_num))

        # Update running stats FIRST
        for sid, did, bid, is_top3, rest_cond, pace_cond, age_cond, kn in updates:
            for eid, run_dict in ((sid, sire_run), (did, dam_run), (bid, bms_run)):
                if not eid:
                    continue
                r = run_dict[eid]
                r['total'] += 1
                if is_top3:
                    r['top3'] += 1
                if rest_cond != 'debut':
                    r[f'{rest_cond}_runs'] += 1
                    if is_top3:
                        r[f'{rest_cond}_top3'] += 1
                if pace_cond:
                    r[f'{pace_cond}_runs'] += 1
                    if is_top3:
                        r[f'{pace_cond}_top3'] += 1
                if age_cond:
                    r[f'{age_cond}_runs'] += 1
                    if is_top3:
                        r[f'{age_cond}_top3'] += 1

            horse_last_date[kn] = date_str

        # Snapshot AFTER update
        for sid in sire_ids_today:
            r = sire_run[sid]
            tl = sire_tl[sid]
            tl['dates'].append(date_str)
            for k in COUNTER_KEYS:
                tl[k].append(r[k])

        for did in dam_ids_today:
            r = dam_run[did]
            tl = dam_tl[did]
            tl['dates'].append(date_str)
            for k in COUNTER_KEYS:
                tl[k].append(r[k])

        for bid in bms_ids_today:
            r = bms_run[bid]
            tl = bms_tl[bid]
            tl['dates'].append(date_str)
            for k in COUNTER_KEYS:
                tl[k].append(r[k])

        if race_count % 2000 == 0 and race_count > 0:
            print(f"  ... {race_count:,} races, {entry_count:,} entries")

    print(f"  Processed {race_count:,} races, {entry_count:,} entries")
    print(f"  Sire timeline: {len(sire_tl):,} sires")
    print(f"  Dam timeline:  {len(dam_tl):,} dams")
    print(f"  BMS timeline:  {len(bms_tl):,} BMS")

    return dict(sire_tl), dict(dam_tl), dict(bms_tl)


def load_data() -> Tuple[dict, dict, dict, dict, dict, dict, dict, dict, dict]:
    """data3からデータをロード"""
    print("[Load] Loading data3...")

    # Horse history cache
    hh_path = config.ml_dir() / "horse_history_cache.json"
    with open(hh_path, encoding='utf-8') as f:
        history_cache = json.load(f)
    print(f"  Horse history: {len(history_cache):,} horses")

    # Trainers
    tr_path = config.masters_dir() / "trainers.json"
    with open(tr_path, encoding='utf-8') as f:
        trainers_list = json.load(f)
    trainer_index = {t['code']: t for t in trainers_list}
    print(f"  Trainers: {len(trainer_index):,}")

    # Jockeys
    jk_path = config.masters_dir() / "jockeys.json"
    with open(jk_path, encoding='utf-8') as f:
        jockeys_list = json.load(f)
    jockey_index = {j['code']: j for j in jockeys_list}
    print(f"  Jockeys: {len(jockey_index):,}")

    # Date index
    di_path = config.indexes_dir() / "race_date_index.json"
    with open(di_path, encoding='utf-8') as f:
        date_index = json.load(f)
    print(f"  Date index: {len(date_index):,} dates")

    # Race level index (v5.6)
    rl_path = config.indexes_dir() / "race_level_index.json"
    race_level_index = {}
    if rl_path.exists():
        with open(rl_path, encoding='utf-8') as f:
            race_level_index = json.load(f)
        print(f"  Race level index: {len(race_level_index):,} races")
    else:
        print("  Race level index: NOT FOUND (skipping)")

    # Pedigree index (v5.7)
    ped_path = config.indexes_dir() / "pedigree_index.json"
    pedigree_index = {}
    if ped_path.exists():
        with open(ped_path, encoding='utf-8') as f:
            pedigree_index = json.load(f)
        print(f"  Pedigree index: {len(pedigree_index):,} horses")
    else:
        print("  Pedigree index: NOT FOUND (skipping)")

    # Sire stats index (v5.8)
    sire_path = config.indexes_dir() / "sire_stats_index.json"
    sire_stats_index = {}
    if sire_path.exists():
        with open(sire_path, encoding='utf-8') as f:
            sire_stats_index = json.load(f)
        n_sire = len(sire_stats_index.get('sire', {}))
        n_dam = len(sire_stats_index.get('dam', {}))
        n_bms = len(sire_stats_index.get('bms', {}))
        print(f"  Sire stats: {n_sire:,} sires, {n_dam:,} dams, {n_bms:,} BMS")
    else:
        print("  Sire stats: NOT FOUND (skipping)")

    # Pace index
    pace_index = build_pace_index(date_index)

    # Keibabook ext index
    kb_ext_index = build_kb_ext_index(date_index)

    # CK_DATA training summary index
    training_summary_index = build_training_summary_index(date_index)

    return (history_cache, trainer_index, jockey_index,
            date_index, pace_index, kb_ext_index, training_summary_index,
            race_level_index, pedigree_index, sire_stats_index)


def compute_features_for_race(
    race: dict,
    history_cache: dict,
    trainer_index: dict,
    jockey_index: dict,
    pace_index: dict,
    kb_ext_index: dict,
    db_odds: dict = None,
    training_summary_index: dict = None,
    db_place_odds: dict = None,
    race_level_index: dict = None,
    pedigree_index: dict = None,
    sire_stats_index: dict = None,
    pit_trainer_tl: dict = None,
    pit_jockey_tl: dict = None,
    pit_sire_tl: dict = None,
    pit_dam_tl: dict = None,
    pit_bms_tl: dict = None,
    baba_index: dict = None,
) -> List[dict]:
    """1レースの全出走馬の特徴量を計算

    Args:
        db_odds: mykeibadbから取得した事前オッズ {umaban: {'odds': float, 'ninki': int}}
        training_summary_index: CK_DATA調教サマリ {date_str: {ketto_num: summary}}
        db_place_odds: mykeibadb複勝オッズ {umaban: {'odds_low': float, 'odds_high': float}}
        race_level_index: レースレベルインデックス {race_id: {level_vs_class, level_rank, ...}}
        pedigree_index: 血統インデックス {ketto_num: {sire: hansyoku_num, bms: hansyoku_num}}
    """
    from ml.features.base_features import extract_base_features
    from ml.features.past_features import compute_past_features
    from ml.features.trainer_features import get_trainer_features
    from ml.features.jockey_features import get_jockey_features
    from ml.features.running_style_features import compute_running_style_features
    from ml.features.rotation_features import compute_rotation_features
    from ml.features.pace_features import compute_pace_features
    from ml.features.training_features import compute_training_features
    from ml.features.speed_features import compute_speed_features
    from ml.features.comment_features import compute_comment_features
    from ml.features.slow_start_features import compute_slow_start_features
    from ml.features.pedigree_features import get_pedigree_features, build_sire_index
    from ml.features.baba_features import get_baba_features

    # Sire/Dam/BMS index (build once per race call)
    _sire_idx, _dam_idx, _bms_idx = build_sire_index(sire_stats_index or {})

    race_date = race['date']
    race_id = race['race_id']
    venue_code = race['venue_code']
    venue_name = race.get('venue_name', '')
    track_type = race.get('track_type', '')
    distance = race.get('distance', 0)
    entry_count = race.get('num_runners', 0)
    current_grade = race.get('grade', '')
    track_condition_str = race.get('track_condition', '')  # v5.45: 文字列版
    current_age_class = race.get('age_class', '')
    if not current_age_class:
        ages = [e.get('age', 0) for e in race.get('entries', []) if e.get('age', 0) > 0]
        if ages:
            min_a, max_a = min(ages), max(ages)
            if max_a == 2:
                current_age_class = '2歳'
            elif min_a <= 3 and max_a == 3:
                current_age_class = '3歳'
            else:
                current_age_class = '古馬'
    current_is_handicap = race.get('is_handicap', False)
    current_is_female_only = race.get('is_female_only', False)
    current_month = int(race_date.split('-')[1]) if len(race_date.split('-')) >= 2 else 0

    # kb_ext（調教データ等）
    kb_ext = kb_ext_index.get(race_id)

    # CK_DATA調教サマリ（日付単位）
    ts_day = (training_summary_index or {}).get(race_date, {})

    rows = []
    for entry in race.get('entries', []):
        fp = entry.get('finish_position', 0)
        if fp <= 0:
            continue

        ketto_num = entry.get('ketto_num', '')

        # 基本特徴量
        feat = extract_base_features(entry, race)

        # DB事前オッズで上書き（データリーク解消）
        umaban = entry.get('umaban', 0)
        if db_odds and umaban in db_odds:
            feat['odds'] = db_odds[umaban]['odds']
            ninki = db_odds[umaban].get('ninki')
            if ninki is not None:
                feat['popularity'] = ninki

        # 過去走特徴量
        past = compute_past_features(
            ketto_num=ketto_num,
            race_date=race_date,
            venue_code=venue_code,
            track_type=track_type,
            distance=distance,
            entry_count=entry_count,
            history_cache=history_cache,
            race_level_index=race_level_index,
            track_condition=track_condition_str,
        )
        feat.update(past)

        # 調教師特徴量
        tc = entry.get('trainer_code', '')
        trainer_feat = get_trainer_features(
            tc, venue_code, trainer_index,
            race_date=race_date, pit_timeline=pit_trainer_tl,
        )
        feat.update(trainer_feat)

        # 騎手特徴量
        jc = entry.get('jockey_code', '')
        jockey_feat = get_jockey_features(
            jc, venue_code, jockey_index,
            race_date=race_date, pit_timeline=pit_jockey_tl,
        )
        feat.update(jockey_feat)

        # 脚質特徴量 (v3.1)
        rs_feat = compute_running_style_features(
            ketto_num=ketto_num,
            race_date=race_date,
            entry_count=entry_count,
            history_cache=history_cache,
        )
        feat.update(rs_feat)

        # ローテ・コンディション特徴量 (v3.1 + v5.1 降格ローテ)
        rot_feat = compute_rotation_features(
            ketto_num=ketto_num,
            race_date=race_date,
            futan=entry.get('futan', 0.0),
            horse_weight=entry.get('horse_weight', 0),
            popularity=entry.get('popularity', 0),
            jockey_code=entry.get('jockey_code', ''),
            history_cache=history_cache,
            current_grade=current_grade,
            current_venue=venue_name,
            current_distance=distance,
            current_track_type=track_type,
            current_month=current_month,
            current_is_handicap=current_is_handicap,
            current_is_female_only=current_is_female_only,
        )
        feat.update(rot_feat)

        # ペース特徴量 (v3.1)
        pace_feat = compute_pace_features(
            ketto_num=ketto_num,
            race_date=race_date,
            days_since_last_race=past.get('days_since_last_race', -1),
            history_cache=history_cache,
            pace_index=pace_index,
        )
        feat.update(pace_feat)

        # 調教特徴量 (v3.3 + v4.1 CK_DATA)
        ck_training = ts_day.get(ketto_num) if ketto_num else None
        train_feat = compute_training_features(
            umaban=str(entry.get('umaban', '')),
            kb_ext=kb_ext,
            ck_training=ck_training,
        )
        feat.update(train_feat)

        # スピード指数特徴量 (v3.5)
        speed_feat = compute_speed_features(
            umaban=str(entry.get('umaban', '')),
            kb_ext=kb_ext,
        )
        feat.update(speed_feat)

        # コメントNLP特徴量 (v5.3)
        comment_feat = compute_comment_features(
            umaban=str(entry.get('umaban', '')),
            kb_ext=kb_ext,
        )
        feat.update(comment_feat)

        # 出遅れ特徴量 (v5.4)
        slow_feat = compute_slow_start_features(
            ketto_num=ketto_num,
            race_date=race_date,
            history_cache=history_cache,
            kb_ext_index=kb_ext_index,
        )
        feat.update(slow_feat)

        # 血統特徴量 (v5.9): 事前計算の集計統計量
        ped_feat = get_pedigree_features(
            ketto_num, pedigree_index or {}, _sire_idx, _dam_idx, _bms_idx,
            race_date=race_date,
            pit_sire_tl=pit_sire_tl, pit_dam_tl=pit_dam_tl, pit_bms_tl=pit_bms_tl,
        )
        feat.update(ped_feat)

        # 馬場特徴量 (v5.41)
        baba_feat = get_baba_features(race_id, track_type, baba_index or {})
        feat.update(baba_feat)

        # メタ情報（学習には使わないが分析用）
        feat['race_id'] = race_id
        feat['date'] = race_date
        feat['ketto_num'] = ketto_num
        feat['horse_name'] = entry.get('horse_name', '')
        feat['umaban'] = entry.get('umaban', 0)
        feat['venue_name'] = race.get('venue_name', '')
        feat['grade'] = current_grade
        feat['age_class'] = current_age_class
        feat['finish_position'] = fp
        feat['is_top3'] = 1 if fp <= 3 else 0
        feat['is_win'] = 1 if fp == 1 else 0

        # DB複勝オッズ（ROI分析用、学習には使わない）
        if db_place_odds and umaban in db_place_odds:
            feat['place_odds_low'] = db_place_odds[umaban].get('odds_low', np.nan)
        else:
            feat['place_odds_low'] = np.nan

        rows.append(feat)

    return rows


def build_dataset(
    date_index: dict,
    history_cache: dict,
    trainer_index: dict,
    jockey_index: dict,
    pace_index: dict,
    kb_ext_index: dict,
    min_year: int,
    max_year: int,
    use_db_odds: bool = True,
    training_summary_index: dict = None,
    race_level_index: dict = None,
    pedigree_index: dict = None,
    sire_stats_index: dict = None,
    min_month: int = None,
    max_month: int = None,
    pit_trainer_tl: dict = None,
    pit_jockey_tl: dict = None,
    pit_sire_tl: dict = None,
    pit_dam_tl: dict = None,
    pit_bms_tl: dict = None,
    baba_index: dict = None,
) -> pd.DataFrame:
    """全レースの特徴量を構築してDataFrameで返す

    Args:
        min_year, max_year: 年範囲（必須）
        min_month: min_yearの開始月（1-12, None=1月から）
        max_month: max_yearの終了月（1-12, None=12月まで）
        use_db_odds: True=mykeibadbから事前オッズ取得, False=JSON確定オッズ（従来動作）
        training_summary_index: CK_DATA調教サマリインデックス
        race_level_index: レースレベルインデックス
    """
    # 月フィルタ: YYYYMM形式の整数で比較
    date_min = min_year * 100 + (min_month or 1)
    date_max = max_year * 100 + (max_month or 12)
    label_min = f"{min_year}-{min_month:02d}" if min_month else str(min_year)
    label_max = f"{max_year}-{max_month:02d}" if max_month else str(max_year)
    print(f"\n[Build] Building dataset for {label_min} ~ {label_max}...")

    # 対象レースIDを収集
    target_races = []
    for date_str, race_id in _iter_date_index(date_index):
        ym = int(date_str[:4]) * 100 + int(date_str[5:7])
        if ym < date_min or ym > date_max:
            continue
        target_races.append((date_str, race_id))

    # DB事前オッズをバッチ取得
    db_odds_index = {}
    db_place_odds_index = {}
    if use_db_odds:
        try:
            from core.odds_db import batch_get_pre_race_odds, batch_get_place_odds, is_db_available
            if is_db_available():
                race_codes = [rid for _, rid in target_races]
                db_odds_index = batch_get_pre_race_odds(race_codes)
                db_place_odds_index = batch_get_place_odds(race_codes)
                ts_count = sum(1 for v in db_odds_index.values()
                               if v and any(e.get('source') == 'timeseries' for e in v.values()))
                final_count = sum(1 for v in db_odds_index.values()
                                  if v and any(e.get('source') == 'final' for e in v.values()))
                print(f"[DB Odds] Win: {len(db_odds_index):,} races, "
                      f"Place: {len(db_place_odds_index):,} races "
                      f"(timeseries={ts_count:,}, final={final_count:,}, "
                      f"no_data={len(target_races)-len(db_odds_index):,})")
            else:
                print("[DB Odds] mykeibadb not available, using JSON odds")
        except Exception as e:
            print(f"[DB Odds] Error: {e}, using JSON odds")

    all_rows = []
    race_count = 0
    error_count = 0

    obstacle_count = 0
    for date_str, race_id in target_races:
        try:
            race = load_race_json(race_id, date_str)
            # 障害レースを除外（平地モデル専用）
            if '障害' in race.get('race_name', '') or race.get('track_type') == 'obstacle':
                obstacle_count += 1
                continue
            rows = compute_features_for_race(
                race, history_cache, trainer_index, jockey_index,
                pace_index, kb_ext_index,
                db_odds=db_odds_index.get(race_id),
                training_summary_index=training_summary_index,
                db_place_odds=db_place_odds_index.get(race_id),
                race_level_index=race_level_index,
                pedigree_index=pedigree_index,
                sire_stats_index=sire_stats_index,
                pit_trainer_tl=pit_trainer_tl,
                pit_jockey_tl=pit_jockey_tl,
                pit_sire_tl=pit_sire_tl,
                pit_dam_tl=pit_dam_tl,
                pit_bms_tl=pit_bms_tl,
                baba_index=baba_index,
            )
            all_rows.extend(rows)
            race_count += 1
        except Exception as e:
            error_count += 1
            if error_count <= 3:
                print(f"  ERROR: {race_id}: {e}")

        if race_count % 1000 == 0 and race_count > 0:
            print(f"  ... {race_count:,} races, {len(all_rows):,} entries")

    df = pd.DataFrame(all_rows)

    # None-only特徴量列をfloat64に変換（LightGBMはobject型を受け付けない）
    for col in df.columns:
        if col in set(FEATURE_COLS_ALL) and df[col].dtype == object:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # odds_rank（レース内オッズ順位）を追加
    if 'odds' in df.columns:
        df['odds_rank'] = df.groupby('race_id')['odds'].rank(method='min')

    msg = f"[Build] {race_count:,} races, {len(df):,} entries, {error_count} errors"
    if obstacle_count > 0:
        msg += f", {obstacle_count} obstacle races excluded"
    print(msg)
    return df


def calc_brier_score(y_true, y_pred) -> float:
    """Brier Score: 確率予測の精度指標 (低いほど良い)"""
    return float(np.mean((y_pred - y_true) ** 2))


def calc_ece(y_true, y_pred, n_bins: int = 10) -> float:
    """Expected Calibration Error: キャリブレーション誤差

    予測確率をビンに分割し、各ビンの「予測平均」と「実際の正例率」の
    加重平均差を計算。低いほどキャリブレーションが良い。
    """
    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        mask = (y_pred >= bin_edges[i]) & (y_pred < bin_edges[i + 1])
        if mask.sum() == 0:
            continue
        bin_acc = y_true[mask].mean()
        bin_conf = y_pred[mask].mean()
        ece += mask.sum() / len(y_true) * abs(bin_acc - bin_conf)
    return float(ece)


def calibrate_isotonic(
    scores_val: np.ndarray,
    y_val: np.ndarray,
    scores_test: np.ndarray,
) -> Tuple:
    """IsotonicRegressionでスコアを確率にキャリブレーション

    Args:
        scores_val: Validationセットの予測スコア（fitに使用）
        y_val: Validationセットの正解ラベル
        scores_test: テストセットの予測スコア（transformに使用）

    Returns:
        (calibrated_test_scores, isotonic_regressor)
    """
    from sklearn.isotonic import IsotonicRegression

    ir = IsotonicRegression(out_of_bounds='clip')
    ir.fit(scores_val, y_val)
    return ir.predict(scores_test), ir


def train_model(
    df_train: pd.DataFrame,
    df_val: pd.DataFrame,
    df_test: pd.DataFrame,
    feature_cols: List[str],
    params: dict,
    label_col: str = 'is_top3',
    model_name: str = 'model',
    num_boost_round: int = 1500,
) -> Tuple:
    """LightGBMモデルを学習

    3-way split: train=学習, val=early stopping, test=純粋評価
    NaN処理はLightGBMネイティブに委ねる（fillna(-1)しない）
    IsotonicRegressionでキャリブレーション（valセットでfit → testセットに適用）
    """
    import lightgbm as lgb

    X_train = df_train[feature_cols]
    y_train = df_train[label_col]
    X_val = df_val[feature_cols]
    y_val = df_val[label_col]
    X_test = df_test[feature_cols]
    y_test = df_test[label_col]

    train_data = lgb.Dataset(X_train, label=y_train)
    valid_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

    print(f"\n[Train] {model_name}: {len(feature_cols)} features, "
          f"train={len(X_train):,}, val={len(X_val):,}, test={len(X_test):,}")

    model = lgb.train(
        params, train_data, num_boost_round=num_boost_round,
        valid_sets=[valid_data],
        callbacks=[
            lgb.early_stopping(stopping_rounds=50),
            lgb.log_evaluation(period=200),
        ],
    )

    # テストセットで純粋評価（early stoppingに使っていない）
    from sklearn.metrics import roc_auc_score, accuracy_score, log_loss

    y_pred_raw = model.predict(X_test)
    y_pred_val = model.predict(X_val)

    # IsotonicRegressionキャリブレーション
    y_pred_cal, calibrator = calibrate_isotonic(
        y_pred_val, y_val.values, y_pred_raw
    )

    # Raw metrics
    auc = roc_auc_score(y_test, y_pred_raw)
    acc = accuracy_score(y_test, (y_pred_raw > 0.5).astype(int))
    ll = log_loss(y_test, y_pred_raw)
    brier = calc_brier_score(y_test.values, y_pred_raw)
    ece = calc_ece(y_test.values, y_pred_raw)

    # Calibrated metrics
    ece_cal = calc_ece(y_test.values, y_pred_cal)
    brier_cal = calc_brier_score(y_test.values, y_pred_cal)
    ll_cal = log_loss(y_test, np.clip(y_pred_cal, 1e-7, 1 - 1e-7))

    auc_val = roc_auc_score(y_val, y_pred_val)

    print(f"[{model_name}] Test:  AUC={auc:.4f}, Acc={acc:.4f}, LogLoss={ll:.4f}, "
          f"Brier={brier:.4f}, ECE={ece:.4f}")
    print(f"[{model_name}] Cal:   ECE={ece_cal:.4f} (isotonic), "
          f"Brier={brier_cal:.4f}, LogLoss={ll_cal:.4f}")
    print(f"[{model_name}] Val:   AUC={auc_val:.4f} (early stopping set)")
    print(f"[{model_name}] BestIter={model.best_iteration}")

    # 特徴量重要度
    importance = dict(zip(feature_cols, model.feature_importance(importance_type='gain')))

    metrics = {
        'auc': round(auc, 4),
        'accuracy': round(acc, 4),
        'log_loss': round(ll, 4),
        'brier_score': round(brier, 4),
        'ece': round(ece, 4),
        'ece_calibrated': round(ece_cal, 4),
        'brier_calibrated': round(brier_cal, 4),
        'log_loss_calibrated': round(ll_cal, 4),
        'auc_val': round(auc_val, 4),
        'best_iteration': model.best_iteration,
        'train_size': len(X_train),
        'val_size': len(X_val),
        'test_size': len(X_test),
    }

    return model, metrics, importance, y_pred_cal, calibrator, y_pred_raw


def calc_hit_analysis(df: pd.DataFrame, pred_col: str) -> List[dict]:
    """Top-N的中率分析（従来互換: legacy形式）"""
    results = []
    for top_n in [1, 2, 3]:
        df['pred_rank'] = df.groupby('race_id')[pred_col].rank(ascending=False, method='min')
        picks = df[df['pred_rank'] <= top_n]
        total = picks['race_id'].nunique()
        hits = picks[picks['is_win'] == 1]['race_id'].nunique() if top_n == 1 else \
               picks[picks['is_top3'] == 1]['race_id'].nunique()

        hit_rate = hits / total if total > 0 else 0
        results.append({
            'top_n': top_n,
            'hit_rate': round(hit_rate, 4),
            'hits': int(hits),
            'total': int(total),
        })
    return results


def calc_hit_analysis_v2(df: pd.DataFrame, pred_col: str, ascending: bool = False) -> dict:
    """Top-N的中率 詳細分析 v2。

    Returns:
        {
            'top1_win_rate': float,      # Top1が1着の確率
            'top1_place_rate': float,     # Top1が3着内の確率
            'top1_total': int,
            'top1_wins': int,
            'top1_places': int,
            'top3_distribution': [       # Top3選出のうち何頭が3着内か
                {'count': 0, 'races': N, 'pct': float},  # 0頭
                {'count': 1, 'races': N, 'pct': float},
                {'count': 2, 'races': N, 'pct': float},
                {'count': 3, 'races': N, 'pct': float},
            ],
            'legacy': [...]              # 従来形式（互換性）
        }
    """
    df['_hit_rank'] = df.groupby('race_id')[pred_col].rank(
        ascending=ascending, method='min'
    )

    # --- Top1 成績 ---
    top1 = df[df['_hit_rank'] == 1]
    top1_total = int(top1['race_id'].nunique())
    top1_wins = int(top1[top1['is_win'] == 1]['race_id'].nunique())
    top1_places = int(top1[top1['is_top3'] == 1]['race_id'].nunique())

    # --- Top3 的中分布 (0/1/2/3頭) ---
    top3 = df[df['_hit_rank'] <= 3].copy()
    top3_hit_counts = top3.groupby('race_id')['is_top3'].sum().astype(int)
    total_races = int(df['race_id'].nunique())
    distribution = []
    for cnt in [0, 1, 2, 3]:
        if cnt == 0:
            # Top3に選出されたレースのうち0頭的中 + Top3に3頭未満しかいないレース
            races_with_top3 = int(top3_hit_counts[top3_hit_counts == 0].count())
            races_without_top3 = total_races - int(top3_hit_counts.count())
            n_races = races_with_top3 + races_without_top3
        else:
            n_races = int(top3_hit_counts[top3_hit_counts == cnt].count())
        distribution.append({
            'count': cnt,
            'races': n_races,
            'pct': round(n_races / total_races * 100, 1) if total_races > 0 else 0,
        })

    # --- 従来形式 (legacy互換) ---
    legacy = []
    for top_n in [1, 2, 3]:
        picks = df[df['_hit_rank'] <= top_n]
        total = picks['race_id'].nunique()
        hits = picks[picks['is_win'] == 1]['race_id'].nunique() if top_n == 1 else \
               picks[picks['is_top3'] == 1]['race_id'].nunique()
        legacy.append({
            'top_n': top_n,
            'hit_rate': round(hits / total, 4) if total > 0 else 0,
            'hits': int(hits),
            'total': int(total),
        })

    df.drop(columns=['_hit_rank'], inplace=True, errors='ignore')

    return {
        'top1_win_rate': round(top1_wins / top1_total, 4) if top1_total > 0 else 0,
        'top1_place_rate': round(top1_places / top1_total, 4) if top1_total > 0 else 0,
        'top1_total': top1_total,
        'top1_wins': top1_wins,
        'top1_places': top1_places,
        'top3_distribution': distribution,
        'legacy': legacy,
    }


def calc_ard_threshold_analysis(df: pd.DataFrame) -> List[dict]:
    """ARd(AR偏差値)閾値別の勝率・好走率分析。

    Returns:
        [
            {'threshold': 50, 'total': N, 'wins': N, 'win_rate': float,
             'places': N, 'place_rate': float},
            ...
        ]
    """
    results = []
    for threshold in [50, 55, 60, 65, 70]:
        subset = df[df['ar_deviation'] >= threshold]
        total = len(subset)
        if total == 0:
            results.append({
                'threshold': threshold,
                'total': 0, 'wins': 0, 'win_rate': 0,
                'places': 0, 'place_rate': 0,
            })
            continue
        wins = int(subset['is_win'].sum())
        places = int(subset['is_top3'].sum())
        results.append({
            'threshold': threshold,
            'total': total,
            'wins': wins,
            'win_rate': round(wins / total, 4),
            'places': places,
            'place_rate': round(places / total, 4),
        })
    return results


def _get_place_odds(row) -> float:
    """複勝オッズを取得: DB実績値があればそれを使用、なければ推定"""
    place_low = row.get('place_odds_low')
    if pd.notna(place_low) and place_low > 0:
        return float(place_low)
    # DB複勝オッズなし: 単勝オッズから推定
    return max(row['odds'] / 3.5, 1.1)


def calc_roi_analysis(df: pd.DataFrame, pred_col: str, ascending: bool = False) -> dict:
    """ROI分析（Top1）"""
    df['pred_rank'] = df.groupby('race_id')[pred_col].rank(ascending=ascending, method='min')
    top1 = df[df['pred_rank'] == 1].copy()

    # 単勝ROI
    total_bets = len(top1) * 100
    win_return = top1[top1['is_win'] == 1]['odds'].sum() * 100
    win_roi = win_return / total_bets * 100 if total_bets > 0 else 0

    # 複勝ROI: DB実複勝オッズを優先、なければ推定
    place_hits = top1[top1['is_top3'] == 1]
    place_return = place_hits.apply(_get_place_odds, axis=1).sum() * 100
    place_roi = place_return / total_bets * 100 if total_bets > 0 else 0

    # DB複勝オッズのカバレッジ
    has_db_place = 0
    if 'place_odds_low' in top1.columns:
        has_db_place = int(top1['place_odds_low'].notna().sum())

    return {
        'top1_win_roi': round(win_roi, 1),
        'top1_place_roi': round(place_roi, 1),
        'top1_bets': len(top1),
        'place_odds_db_count': has_db_place,
    }


def calc_value_bet_analysis(df: pd.DataFrame, rank_col: str = 'pred_rank_p') -> List[dict]:
    """Value Bet分析: モデル順位とオッズ順位の乖離を利用"""
    if rank_col not in df.columns or 'odds_rank' not in df.columns:
        return []

    results = []
    for min_gap in [2, 3, 4, 5]:
        total_bets = 0
        place_return = 0
        win_return = 0
        place_hits = 0
        win_hits = 0
        total_count = 0

        for race_id, group in df.groupby('race_id'):
            # Value Bet候補: モデルで上位3位以内 かつ odds_rankとの乖離がmin_gap以上
            candidates = group[
                (group[rank_col] <= 3) &
                (group['odds_rank'] >= group[rank_col] + min_gap)
            ]

            for _, row in candidates.iterrows():
                bet = 100
                total_bets += bet
                total_count += 1

                if row['is_win'] == 1:
                    win_return += row['odds'] * bet
                    win_hits += 1

                if row['is_top3'] == 1:
                    place_odds = _get_place_odds(row)
                    place_return += place_odds * bet
                    place_hits += 1

        place_roi = place_return / total_bets * 100 if total_bets > 0 else 0
        win_roi = win_return / total_bets * 100 if total_bets > 0 else 0
        hit_rate = place_hits / total_count if total_count > 0 else 0

        results.append({
            'min_gap': min_gap,
            'bet_count': total_count,
            'win_hits': win_hits,
            'win_roi': round(win_roi, 1),
            'place_hits': place_hits,
            'place_hit_rate': round(hit_rate, 4),
            'place_roi': round(place_roi, 1),
        })

    return results


def calc_vb_bootstrap_ci(
    df: pd.DataFrame,
    rank_col: str = 'pred_rank_p',
    n_bootstrap: int = 1000,
    ci_level: float = 0.95,
) -> List[dict]:
    """Value Bet ROIのBootstrap信頼区間をレース単位リサンプリングで推定

    レース単位でリサンプリングする理由:
    - 同一レース内の馬は独立ではない（1頭が勝てば他は負け）
    - 馬単位でリサンプリングすると統計的独立性の仮定が崩れる

    Returns:
        gap条件ごとの {min_gap, bet_count, place_roi, win_roi,
                       place_roi_ci_low, place_roi_ci_high,
                       win_roi_ci_low, win_roi_ci_high} のリスト
    """
    if rank_col not in df.columns or 'odds_rank' not in df.columns:
        return []

    rng = np.random.default_rng(42)
    alpha = (1 - ci_level) / 2  # 0.025 for 95% CI

    results = []
    for min_gap in [2, 3, 4, 5]:
        # --- レース単位でVBベット結果を集計 ---
        race_bets = {}  # {race_id: [(bet_amount, win_return, place_return), ...]}
        for race_id, group in df.groupby('race_id'):
            candidates = group[
                (group[rank_col] <= 3) &
                (group['odds_rank'] >= group[rank_col] + min_gap)
            ]
            if len(candidates) == 0:
                continue
            bets = []
            for _, row in candidates.iterrows():
                bet = 100
                w_ret = row['odds'] * bet if row['is_win'] == 1 else 0
                p_odds = _get_place_odds(row)
                p_ret = p_odds * bet if row['is_top3'] == 1 else 0
                bets.append((bet, w_ret, p_ret))
            race_bets[race_id] = bets

        race_ids = list(race_bets.keys())
        n_races = len(race_ids)
        if n_races == 0:
            results.append({
                'min_gap': min_gap, 'bet_count': 0,
                'place_roi': 0, 'win_roi': 0,
                'place_roi_ci_low': 0, 'place_roi_ci_high': 0,
                'win_roi_ci_low': 0, 'win_roi_ci_high': 0,
            })
            continue

        # 原データのROI
        total_bet = sum(b for rid in race_ids for b, _, _ in race_bets[rid])
        total_w = sum(w for rid in race_ids for _, w, _ in race_bets[rid])
        total_p = sum(p for rid in race_ids for _, _, p in race_bets[rid])
        place_roi = total_p / total_bet * 100 if total_bet > 0 else 0
        win_roi = total_w / total_bet * 100 if total_bet > 0 else 0
        bet_count = sum(len(race_bets[rid]) for rid in race_ids)

        # --- Bootstrap ---
        boot_place_rois = []
        boot_win_rois = []
        for _ in range(n_bootstrap):
            sampled = rng.choice(race_ids, size=n_races, replace=True)
            b_bet = 0
            b_w = 0
            b_p = 0
            for rid in sampled:
                for bet, w_ret, p_ret in race_bets[rid]:
                    b_bet += bet
                    b_w += w_ret
                    b_p += p_ret
            if b_bet > 0:
                boot_place_rois.append(b_p / b_bet * 100)
                boot_win_rois.append(b_w / b_bet * 100)

        boot_place = np.array(boot_place_rois)
        boot_win = np.array(boot_win_rois)

        results.append({
            'min_gap': min_gap,
            'bet_count': bet_count,
            'n_races_with_vb': n_races,
            'place_roi': round(place_roi, 1),
            'win_roi': round(win_roi, 1),
            'place_roi_ci_low': round(float(np.percentile(boot_place, alpha * 100)), 1) if len(boot_place) > 0 else 0,
            'place_roi_ci_high': round(float(np.percentile(boot_place, (1 - alpha) * 100)), 1) if len(boot_place) > 0 else 0,
            'win_roi_ci_low': round(float(np.percentile(boot_win, alpha * 100)), 1) if len(boot_win) > 0 else 0,
            'win_roi_ci_high': round(float(np.percentile(boot_win, (1 - alpha) * 100)), 1) if len(boot_win) > 0 else 0,
            'place_roi_std': round(float(np.std(boot_place)), 1) if len(boot_place) > 0 else 0,
            'win_roi_std': round(float(np.std(boot_win)), 1) if len(boot_win) > 0 else 0,
        })

    return results


def calc_ev_gap_comparison(
    df: pd.DataFrame,
    n_bootstrap: int = 1000,
    ci_level: float = 0.95,
) -> dict:
    """EV vs gap vs gap+EV の条件比較分析（Bootstrap CI付き）

    条件:
    - A: gap>=N + margin<=M (gapのみ)
    - B: EV>=T + margin<=M (EVのみ)
    - C: gap>=N + EV>=T + margin<=M (gap+EV併用)

    win_ev = calibrated_win_prob × win_odds (既にdf_testに計算済み)
    """
    required = ['pred_rank_p', 'odds_rank', 'win_ev', 'pred_margin_ar', 'odds', 'is_win']
    if not all(c in df.columns for c in required):
        return {}

    rng = np.random.default_rng(42)
    alpha = (1 - ci_level) / 2

    def _bootstrap_win_roi(filtered_df):
        """フィルタ済みDFからレース単位Bootstrap CIを計算"""
        race_bets = {}
        for race_id, group in filtered_df.groupby('race_id'):
            bets = []
            for _, row in group.iterrows():
                bet = 100
                w_ret = row['odds'] * bet if row['is_win'] == 1 else 0
                bets.append((bet, w_ret))
            race_bets[race_id] = bets

        race_ids = list(race_bets.keys())
        n_races = len(race_ids)
        if n_races == 0:
            return {'count': 0, 'n_races': 0, 'win_roi': 0,
                    'ci_low': 0, 'ci_high': 0, 'ci_width': 0, 'std': 0,
                    'wins': 0, 'win_rate': 0, 'avg_odds': 0, 'pnl': 0}

        total_bet = sum(b for rid in race_ids for b, _ in race_bets[rid])
        total_ret = sum(r for rid in race_ids for _, r in race_bets[rid])
        count = sum(len(race_bets[rid]) for rid in race_ids)
        wins = int(filtered_df['is_win'].sum())
        win_roi = total_ret / total_bet * 100 if total_bet > 0 else 0
        avg_odds = float(filtered_df['odds'].mean())

        boot_rois = []
        for _ in range(n_bootstrap):
            sampled = rng.choice(race_ids, size=n_races, replace=True)
            b_bet = sum(b for rid in sampled for b, _ in race_bets[rid])
            b_ret = sum(r for rid in sampled for _, r in race_bets[rid])
            if b_bet > 0:
                boot_rois.append(b_ret / b_bet * 100)

        boot_arr = np.array(boot_rois) if boot_rois else np.array([0.0])
        ci_low = float(np.percentile(boot_arr, alpha * 100))
        ci_high = float(np.percentile(boot_arr, (1 - alpha) * 100))

        return {
            'count': count,
            'n_races': n_races,
            'wins': wins,
            'win_rate': round(wins / count * 100, 1) if count > 0 else 0,
            'win_roi': round(win_roi, 1),
            'avg_odds': round(avg_odds, 1),
            'pnl': round(total_ret - total_bet),
            'ci_low': round(ci_low, 1),
            'ci_high': round(ci_high, 1),
            'ci_width': round(ci_high - ci_low, 1),
            'std': round(float(np.std(boot_arr)), 1),
        }

    # VB候補: Place model top3
    vb_base = df[(df['pred_rank_p'] <= 3) & (df['odds'] > 0)].copy()
    vb_base['gap'] = (vb_base['odds_rank'] - vb_base['pred_rank_p']).clip(lower=0).astype(int)

    results = {'conditions': [], 'ev_grid': []}

    # --- EV threshold grid search ---
    ev_thresholds = [1.1, 1.2, 1.3, 1.5, 1.8, 2.0]
    gap_levels = [5, 6, 7]
    margin_levels = [0.8, 1.2]

    for margin in margin_levels:
        margin_mask = vb_base['pred_margin_ar'] <= margin

        for ev_th in ev_thresholds:
            ev_mask = vb_base['win_ev'] >= ev_th

            for gap in gap_levels:
                gap_mask = vb_base['gap'] >= gap

                # A: gap only
                a_df = vb_base[gap_mask & margin_mask]
                # B: EV only
                b_df = vb_base[ev_mask & margin_mask]
                # C: gap + EV
                c_df = vb_base[gap_mask & ev_mask & margin_mask]

                row = {
                    'gap': gap,
                    'ev_threshold': ev_th,
                    'margin': margin,
                    'A_gap_only': _bootstrap_win_roi(a_df),
                    'B_ev_only': _bootstrap_win_roi(b_df),
                    'C_gap_ev': _bootstrap_win_roi(c_df),
                }
                results['ev_grid'].append(row)

    # --- Summary: best conditions ---
    print("\n[Analysis] EV vs Gap comparison...")
    print(f"  {'Condition':<30} {'N':>5} {'ROI':>7} {'CI':>18} {'Width':>6} {'Wins':>5} {'P&L':>8}")
    print(f"  {'-'*80}")

    # Show key comparisons for margin=0.8
    for row in results['ev_grid']:
        if row['margin'] != 0.8:
            continue
        gap = row['gap']
        ev = row['ev_threshold']
        for cond_key, cond_label in [('A_gap_only', f'gap>={gap} m<=0.8'),
                                      ('B_ev_only', f'EV>={ev} m<=0.8'),
                                      ('C_gap_ev', f'gap>={gap}+EV>={ev} m<=0.8')]:
            d = row[cond_key]
            if d['count'] == 0:
                continue
            # Only print unique A conditions once
            if cond_key == 'A_gap_only' and ev != ev_thresholds[0]:
                continue
            if cond_key == 'B_ev_only' and gap != gap_levels[0]:
                continue
            print(f"  {cond_label:<30} {d['count']:>5} {d['win_roi']:>6.1f}% "
                  f"[{d['ci_low']:>5.1f}-{d['ci_high']:>5.1f}%] {d['ci_width']:>5.1f} "
                  f"{d['wins']:>5} {d['pnl']:>+8,}")

    return results


def collect_value_bet_picks(df: pd.DataFrame, min_gap: int = 3) -> List[dict]:
    """テスト期間のValue Bet候補を個別レコードとして収集"""
    if 'pred_rank_p' not in df.columns or 'odds_rank' not in df.columns:
        return []

    picks = []
    for race_id, group in df.groupby('race_id'):
        candidates = group[
            (group['pred_rank_p'] <= 3) &
            (group['odds_rank'] >= group['pred_rank_p'] + min_gap)
        ]
        for _, row in candidates.iterrows():
            gap = int(row['odds_rank'] - row['pred_rank_p'])
            picks.append({
                'race_id': str(row['race_id']),
                'date': str(row['date']),
                'venue': str(row.get('venue_name', '')),
                'grade': str(row.get('grade', '')),
                'horse_number': int(row.get('umaban', 0)),
                'horse_name': str(row.get('horse_name', '')),
                'place_rank': int(row['pred_rank_p']),
                'odds_rank': int(row['odds_rank']),
                'gap': gap,
                'odds': round(float(row['odds']), 1) if row['odds'] > 0 else None,
                'pred_proba_place': round(float(row['pred_proba_p']), 4),
                'predicted_margin': round(float(row['pred_margin_ar']), 3) if pd.notna(row.get('pred_margin_ar')) else None,
                'win_ev': round(float(row['win_ev']), 3) if 'win_ev' in row.index and pd.notna(row.get('win_ev')) else None,
                'actual_position': int(row['finish_position']),
                'is_top3': int(row['is_top3']),
            })

    picks.sort(key=lambda x: (-x['gap'], x['date']))
    return picks


def calc_gap_margin_grid(df: pd.DataFrame) -> List[dict]:
    """gap × margin クロス集計 (ML Report ヒートマップ用)

    VB候補 (pred_rank_p <= 3) に対して、gap閾値とmargin閾値の
    組み合わせごとの件数・単勝ROI・複勝ROIを計算する。
    """
    if 'pred_rank_p' not in df.columns or 'pred_margin_ar' not in df.columns:
        return []

    grid = []
    for min_gap in [3, 4, 5, 6]:
        for max_margin in [0.6, 0.8, 1.0, 1.2, 1.5, None]:
            mask = (
                (df['pred_rank_p'] <= 3) &
                (df['odds_rank'] >= df['pred_rank_p'] + min_gap)
            )
            if max_margin is not None:
                mask = mask & (df['pred_margin_ar'] <= max_margin)
            subset = df[mask]
            if len(subset) == 0:
                continue

            total_bet = len(subset) * 100
            win_return = float(subset[subset['is_win'] == 1]['odds'].sum()) * 100
            place_col = 'place_odds_low' if 'place_odds_low' in df.columns else 'place_odds_min'
            if place_col in df.columns:
                place_return = float(subset[subset['is_top3'] == 1][place_col].fillna(0).sum()) * 100
            else:
                place_return = 0

            grid.append({
                'min_gap': min_gap,
                'max_margin': max_margin,
                'count': int(len(subset)),
                'win_hits': int(subset['is_win'].sum()),
                'win_roi': round(win_return / total_bet * 100, 1) if total_bet > 0 else 0,
                'place_hits': int(subset['is_top3'].sum()),
                'place_roi': round(place_return / total_bet * 100, 1) if total_bet > 0 else 0,
            })
    return grid


def calc_gap_ard_grid(df: pd.DataFrame) -> List[dict]:
    """gap × ARd クロス集計 (ML Report ヒートマップ用)

    VB候補 (pred_rank_p <= 3) に対して、gap閾値とARd閾値の
    組み合わせごとの件数・単勝ROI・複勝ROIを計算する。
    """
    if 'pred_rank_p' not in df.columns or 'ar_deviation' not in df.columns:
        return []

    grid = []
    for min_gap in [3, 4, 5, 6]:
        for min_ard in [None, 45, 50, 55, 60, 65]:
            mask = (
                (df['pred_rank_p'] <= 3) &
                (df['odds_rank'] >= df['pred_rank_p'] + min_gap)
            )
            if min_ard is not None:
                mask = mask & (df['ar_deviation'] >= min_ard)
            subset = df[mask]
            if len(subset) == 0:
                continue

            total_bet = len(subset) * 100
            win_return = float(subset[subset['is_win'] == 1]['odds'].sum()) * 100
            place_col = 'place_odds_low' if 'place_odds_low' in df.columns else 'place_odds_min'
            place_return = 0.0
            if place_col in df.columns:
                place_subset = subset[subset['is_top3'] == 1]
                place_return = float(place_subset[place_col].fillna(
                    subset['odds'] / 3.5
                ).clip(lower=1.1).sum()) * 100 if len(place_subset) > 0 else 0.0

            grid.append({
                'min_gap': min_gap,
                'min_ard': min_ard,
                'count': int(len(subset)),
                'win_hits': int(subset['is_win'].sum()),
                'win_roi': round(win_return / total_bet * 100, 1) if total_bet > 0 else 0,
                'place_hits': int(subset['is_top3'].sum()),
                'place_roi': round(place_return / total_bet * 100, 1) if total_bet > 0 else 0,
            })
    return grid


def collect_race_predictions(df: pd.DataFrame) -> List[dict]:
    """テスト期間のレース別予測データを収集"""
    races = []
    for race_id, group in df.groupby('race_id'):
        group_sorted = group.sort_values('pred_proba_p', ascending=False)
        row0 = group_sorted.iloc[0]
        horses = []
        for _, row in group_sorted.iterrows():
            horses.append({
                'horse_number': int(row.get('umaban', 0)),
                'horse_name': str(row.get('horse_name', '')),
                'pred_proba_place': round(float(row['pred_proba_p']), 4),
                'pred_top3': int(row['pred_rank_p'] <= 3),
                'actual_position': int(row['finish_position']),
                'actual_top3': int(row['is_top3']),
                'odds_rank': int(row['odds_rank']) if row.get('odds_rank', 0) > 0 else None,
                'odds': round(float(row['odds']), 1) if row.get('odds', 0) > 0 else None,
                'place_rank': int(row['pred_rank_p']),
            })
        races.append({
            'race_id': str(race_id),
            'date': str(row0['date']),
            'venue': str(row0.get('venue_name', '')),
            'grade': str(row0.get('grade', '')),
            'entry_count': len(group),
            'horses': horses,
        })
    races.sort(key=lambda x: (x['date'], x['race_id']))
    return races


def train_regression_model(
    df_train: pd.DataFrame,
    df_val: pd.DataFrame,
    df_test: pd.DataFrame,
    feature_cols: List[str],
    params: dict,
    model_name: str = 'Aura',
    num_boost_round: int = 1500,
) -> Tuple:
    """着差回帰モデル (LGBMRegressor) を学習

    target_margin カラムが必要（add_margin_target_to_df() で事前追加）。
    NOTE: 分類モデルと異なりcalibratorを返さない (4-tuple)。
    将来 margin→P(win) 変換が必要な場合は calibrator 追加を検討。

    Returns:
        (model, metrics, importance, all_predictions)
        all_predictions: df_test 全行の予測値 (NaN target の馬含む)
    """
    import lightgbm as lgb

    mask_train = df_train['target_margin'].notna()
    mask_val = df_val['target_margin'].notna()
    mask_test = df_test['target_margin'].notna()

    X_train = df_train.loc[mask_train, feature_cols]
    y_train = df_train.loc[mask_train, 'target_margin']
    X_val = df_val.loc[mask_val, feature_cols]
    y_val = df_val.loc[mask_val, 'target_margin']
    X_test = df_test.loc[mask_test, feature_cols]
    y_test = df_test.loc[mask_test, 'target_margin']

    # 血統カテゴリ特徴量の検出
    print(f"\n[Train] {model_name}: {len(feature_cols)} features, "
          f"train={len(X_train):,}, val={len(X_val):,}, test={len(X_test):,}")

    train_data = lgb.Dataset(X_train, label=y_train)
    valid_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

    model = lgb.train(
        params, train_data, num_boost_round=num_boost_round,
        valid_sets=[valid_data],
        callbacks=[
            lgb.early_stopping(stopping_rounds=50),
            lgb.log_evaluation(period=200),
        ],
    )

    # テスト精度 (target_margin が有効な馬のみ)
    y_pred = model.predict(X_test)
    from sklearn.metrics import mean_absolute_error
    mae = mean_absolute_error(y_test, y_pred)
    corr = np.corrcoef(y_test, y_pred)[0, 1]

    print(f"[{model_name}] MAE={mae:.4f}s, Corr={corr:.4f}, BestIter={model.best_iteration}")

    # 全テストデータの予測（NaN target の馬含む）
    all_pred = model.predict(df_test[feature_cols])

    metrics = {
        'mae': round(mae, 4),
        'correlation': round(corr, 4),
        'best_iteration': model.best_iteration,
    }
    importance = dict(zip(feature_cols, model.feature_importance(importance_type='gain')))

    return model, metrics, importance, all_pred


def run_track_split_experiment(
    df_train: pd.DataFrame,
    df_val: pd.DataFrame,
    df_test: pd.DataFrame,
    feature_cols_value: List[str],
    params_p: dict,
    unified_pred_p: np.ndarray,
):
    """芝/ダート分離モデル実験 (H-21)

    統一モデルと分離モデルの性能を比較する。
    track_type特徴量は分離後に定数になるため除外する。
    """
    from sklearn.metrics import roc_auc_score

    print(f"\n{'='*60}")
    print("  H-21: 芝/ダート分離モデル実験")
    print(f"{'='*60}")

    # track_type を除外（分離後は定数）
    split_features = [f for f in feature_cols_value if f != 'track_type']
    print(f"  Features (excl track_type): {len(split_features)}")

    # track_type: 0=turf, 1=dirt（base_features.pyのtrack_map）
    results = {}
    for track_label, track_val in [('turf', 0), ('dirt', 1)]:
        print(f"\n--- {track_label.upper()} ---")
        tr = df_train[df_train['track_type'] == track_val]
        vl = df_val[df_val['track_type'] == track_val]
        ts = df_test[df_test['track_type'] == track_val]
        print(f"  Train: {len(tr):,}, Val: {len(vl):,}, Test: {len(ts):,}")

        if len(ts) < 100:
            print(f"  SKIP: insufficient test data")
            continue

        # Place model (split)
        model_p_s, metrics_p_s, _, pred_p_s, _, _ = train_model(
            tr, vl, ts, split_features, params_p, 'is_top3', f'P_{track_label}'
        )

        # 統一モデルの同じサブセットでの性能
        test_mask = df_test['track_type'] == track_val
        unified_p_sub = unified_pred_p[test_mask.values]
        y_test_sub = ts['is_top3']

        unified_auc_p = roc_auc_score(y_test_sub, unified_p_sub)

        # VB分析（分離モデル）
        ts_copy = ts.copy()
        ts_copy['pred_proba_p'] = pred_p_s
        ts_copy['pred_rank_p'] = ts_copy.groupby('race_id')['pred_proba_p'].rank(ascending=False, method='min')
        vb_split = calc_value_bet_analysis(ts_copy, rank_col='pred_rank_p')

        # 統一モデルのVB分析（同サブセット）
        ts_unified = ts.copy()
        ts_unified['pred_proba_p'] = unified_p_sub
        ts_unified['pred_rank_p'] = ts_unified.groupby('race_id')['pred_proba_p'].rank(ascending=False, method='min')
        vb_unified = calc_value_bet_analysis(ts_unified, rank_col='pred_rank_p')

        # ROI分析
        roi_split_p = calc_roi_analysis(ts_copy, 'pred_proba_p')
        roi_unified_p = calc_roi_analysis(ts_unified, 'pred_proba_p')

        # 比較表示
        print(f"\n  === {track_label.upper()} 比較 ===")
        print(f"  {'Model':<15} {'統一AUC':>10} {'分離AUC':>10} {'差分':>10}")
        print(f"  {'Place (P)':<15} {unified_auc_p:>10.4f} {metrics_p_s['auc']:>10.4f} {metrics_p_s['auc']-unified_auc_p:>+10.4f}")

        print(f"\n  ROI (Top1):")
        print(f"  {'Model':<15} {'統一Win':>10} {'分離Win':>10} {'統一Place':>12} {'分離Place':>12}")
        print(f"  {'P':<15} {roi_unified_p['top1_win_roi']:>9.1f}% {roi_split_p['top1_win_roi']:>9.1f}% "
              f"{roi_unified_p['top1_place_roi']:>11.1f}% {roi_split_p['top1_place_roi']:>11.1f}%")

        print(f"\n  VB Place ROI:")
        print(f"  {'Gap':<10} {'統一':>10} {'分離':>10} {'差分':>10}")
        for vu, vs in zip(vb_unified, vb_split):
            diff = vs['place_roi'] - vu['place_roi']
            marker = " ***" if diff > 0 else ""
            print(f"  >={vu['min_gap']:<8} {vu['place_roi']:>9.1f}% {vs['place_roi']:>9.1f}% {diff:>+9.1f}%{marker}")

        results[track_label] = {
            'split_metrics_p': metrics_p_s,
            'unified_auc_p': round(unified_auc_p, 4),
            'split_vb': vb_split,
            'unified_vb': vb_unified,
            'split_roi_p': roi_split_p,
            'unified_roi_p': roi_unified_p,
            'test_races': int(ts['race_id'].nunique()),
            'test_entries': len(ts),
        }

    return results


def parse_year_range(s: str) -> Tuple[int, int]:
    if '-' in s:
        parts = s.split('-', 1)
        return int(parts[0]), int(parts[1])
    y = int(s)
    return y, y


def _parse_period(s: str) -> Tuple[int, int]:
    """期間指定をパース → (year, month) タプル

    形式: "2020" → (2020, None), "2025.02" → (2025, 2)
    """
    if '.' in s:
        parts = s.split('.', 1)
        return int(parts[0]), int(parts[1])
    return int(s), None


def parse_period_range(s: str) -> Tuple[int, int, int, int]:
    """期間範囲をパース → (min_year, min_month, max_year, max_month)

    形式例:
        "2020-2024"       → (2020, None, 2024, None)   # 年単位
        "2025.01-2025.02" → (2025, 1, 2025, 2)         # 月単位
        "2020-2025.02"    → (2020, None, 2025, 2)       # 混在OK
        "2024"            → (2024, None, 2024, None)     # 単年
        "2025.03"         → (2025, 3, 2025, 3)           # 単月
    """
    if '-' in s:
        # "-" の位置を探す（ただし "2025.03-2026.02" のように "." の後の "-" は区切り）
        # 簡易パース: 最初の '-' で分割、ただし "YYYY.MM" の内部にはない
        # → まず全体を '-' で split して再構成
        tokens = s.split('-')
        # tokens例: ["2020", "2025.02"] or ["2025.01", "2025.02"] or ["2020", "2024"]
        if len(tokens) == 2:
            min_y, min_m = _parse_period(tokens[0])
            max_y, max_m = _parse_period(tokens[1])
        elif len(tokens) == 3:
            # "2025.01-2025.02" のようなケースではないので
            # "2020-2025.02" のようなケースを想定（token[0]="2020", token[1]="2025.02"にはならない）
            # 実際のパターン: 最初の token が年、残りを結合
            min_y, min_m = _parse_period(tokens[0])
            max_y, max_m = _parse_period('-'.join(tokens[1:]))
        else:
            raise ValueError(f"Invalid period range: {s}")
        return min_y, min_m, max_y, max_m
    else:
        y, m = _parse_period(s)
        return y, m, y, m


def _format_period(year: int, month: int = None) -> str:
    """期間をラベル文字列に変換"""
    if month:
        return f"{year}-{month:02d}"
    return str(year)


def _suggest_next_version(current_ver: str) -> str:
    """現バージョンから次のマイナーバージョンを提案"""
    try:
        parts = current_ver.split('.')
        if len(parts) >= 2:
            major = parts[0]
            minor = int(parts[1]) + 1
            return f"{major}.{minor}"
    except (ValueError, IndexError):
        pass
    return f"{current_ver}.1"


def main():
    parser = argparse.ArgumentParser(description='ML Experiment v3')
    parser.add_argument('--train-years', default='2020-2024',
                        help='Training period (例: 2020-2024, 2020-2025.02)')
    parser.add_argument('--val-years', default='2025.01-2025.02',
                        help='Validation period (例: 2024, 2025.01-2025.02)')
    parser.add_argument('--test-years', default='2025.03-2026.02',
                        help='Test period (例: 2025-2026, 2025.03-2026.02)')
    parser.add_argument('--no-db', action='store_true', help='DBオッズ未使用（JSON確定オッズ）')
    parser.add_argument('--split-track', action='store_true', help='芝/ダート分離モデル実験 (H-21)')
    parser.add_argument('--version', default=None, help='モデルバージョン文字列 (例: 5.3)')
    parser.add_argument('--prune-bottom', type=int, default=0,
                        help='Importance下位N%%の特徴量を除外 (例: 20)')
    parser.add_argument('--exclude-features', nargs='+', default=[],
                        help='除外する特徴量名のリスト (例: --exclude-features feat1 feat2)')
    parser.add_argument('--use-optuna', action='store_true',
                        help='Optuna最適化済みパラメータを使用 (ml/optuna/optuna_best_params.json)')
    args = parser.parse_args()

    train_min, train_min_m, train_max, train_max_m = parse_period_range(args.train_years)
    val_min, val_min_m, val_max, val_max_m = parse_period_range(args.val_years)
    test_min, test_min_m, test_max, test_max_m = parse_period_range(args.test_years)
    use_db_odds = not args.no_db

    # バージョン文字列: CLI指定 or 自動生成
    # 特徴量変更検出: 現在のコードの特徴量リストと保存済みモデルを比較
    current_meta_path = config.ml_dir() / "model_meta.json"
    saved_features = set()
    current_ver = '?'
    if current_meta_path.exists():
        current_meta = json.loads(current_meta_path.read_text(encoding='utf-8'))
        current_ver = current_meta.get('version', '?')
        saved_features = set(current_meta.get('features_value', []) + current_meta.get('market_features', []))

    code_features = set(FEATURE_COLS_ALL)
    features_changed = saved_features and code_features != saved_features
    if features_changed:
        added = code_features - saved_features
        removed = saved_features - code_features
        print(f"\n  {'!'*60}")
        print(f"  特徴量変更を検出（現行 v{current_ver} からの差分）:")
        if added:
            print(f"    追加 (+{len(added)}): {', '.join(sorted(added))}")
        if removed:
            print(f"    削除 (-{len(removed)}): {', '.join(sorted(removed))}")
        print(f"  {'!'*60}")

    if args.version:
        experiment_version = args.version
        if features_changed and args.version == current_ver:
            print(f"\n  WARNING: 特徴量が変更されていますが同じバージョン v{current_ver} が指定されました。")
            print(f"  新バージョンの指定を推奨します。続行します...")
    else:
        if features_changed:
            print(f"\n  ERROR: 特徴量が変更されています。新バージョンを --version で指定してください。")
            print(f"  例: --version {_suggest_next_version(current_ver)}")
            sys.exit(1)
        else:
            experiment_version = None  # 特徴量変更なし → 後で既存バージョンを再利用

    train_label = f"{_format_period(train_min, train_min_m)} ~ {_format_period(train_max, train_max_m)}"
    val_label = f"{_format_period(val_min, val_min_m)} ~ {_format_period(val_max, val_max_m)}"
    test_label = f"{_format_period(test_min, test_min_m)} ~ {_format_period(test_max, test_max_m)}"

    print(f"\n{'='*60}")
    print(f"  KeibaCICD v4 - ML Experiment")
    print(f"  Train: {train_label}")
    print(f"  Val:   {val_label} (early stopping)")
    print(f"  Test:  {test_label} (pure evaluation)")
    print(f"  DB Odds: {'ON' if use_db_odds else 'OFF (JSON fallback)'}")
    print(f"  Model A features: {len(FEATURE_COLS_ALL)}")
    print(f"  Model B features: {len(FEATURE_COLS_VALUE)}")
    print(f"  NaN handling: LightGBM native")
    print(f"{'='*60}\n")

    t0 = time.time()

    # データロード
    (history_cache, trainer_index, jockey_index,
     date_index, pace_index, kb_ext_index, training_summary_index,
     race_level_index, pedigree_index, sire_stats_index) = load_data()

    # Point-in-time: 調教師・騎手の累積タイムライン構築
    pit_trainer_tl, pit_jockey_tl = build_pit_personnel_timeline()

    # 馬場データ (v5.41)
    from ml.features.baba_features import load_baba_index
    baba_index = load_baba_index()
    print(f"[Load] Baba index: {len(baba_index):,} races")

    # Note: sire/dam/bms PIT is intentionally NOT applied.
    # Sire stats are population-level (change slowly), not individual-level leakage.
    # PIT correction hurts AUC significantly (-0.03~-0.05) with no ROI benefit.
    # build_pit_sire_timeline() is available but disabled.

    # データセット構築（3-way split）
    df_train = build_dataset(
        date_index, history_cache, trainer_index, jockey_index, pace_index,
        kb_ext_index, train_min, train_max, use_db_odds=use_db_odds,
        training_summary_index=training_summary_index,
        race_level_index=race_level_index,
        pedigree_index=pedigree_index,
        sire_stats_index=sire_stats_index,
        min_month=train_min_m, max_month=train_max_m,
        pit_trainer_tl=pit_trainer_tl, pit_jockey_tl=pit_jockey_tl,
        baba_index=baba_index,
    )
    df_val = build_dataset(
        date_index, history_cache, trainer_index, jockey_index, pace_index,
        kb_ext_index, val_min, val_max, use_db_odds=use_db_odds,
        training_summary_index=training_summary_index,
        race_level_index=race_level_index,
        pedigree_index=pedigree_index,
        sire_stats_index=sire_stats_index,
        min_month=val_min_m, max_month=val_max_m,
        pit_trainer_tl=pit_trainer_tl, pit_jockey_tl=pit_jockey_tl,
        baba_index=baba_index,
    )
    df_test = build_dataset(
        date_index, history_cache, trainer_index, jockey_index, pace_index,
        kb_ext_index, test_min, test_max, use_db_odds=use_db_odds,
        training_summary_index=training_summary_index,
        race_level_index=race_level_index,
        pedigree_index=pedigree_index,
        sire_stats_index=sire_stats_index,
        min_month=test_min_m, max_month=test_max_m,
        pit_trainer_tl=pit_trainer_tl, pit_jockey_tl=pit_jockey_tl,
        baba_index=baba_index,
    )

    print(f"\n[Dataset] Train: {len(df_train):,} entries from "
          f"{df_train['race_id'].nunique():,} races")
    print(f"[Dataset] Val:   {len(df_val):,} entries from "
          f"{df_val['race_id'].nunique():,} races")
    print(f"[Dataset] Test:  {len(df_test):,} entries from "
          f"{df_test['race_id'].nunique():,} races")

    # === Feature Pruning ===
    feature_cols_value = list(FEATURE_COLS_VALUE)
    pruned_features = []

    if args.exclude_features:
        exclude_set = set(args.exclude_features)
        before_val = len(feature_cols_value)
        feature_cols_value = [f for f in feature_cols_value if f not in exclude_set]
        pruned_features = sorted(exclude_set)
        removed_val = before_val - len(feature_cols_value)
        print(f"\n[Exclude] Removing {len(exclude_set)} specified features")
        print(f"  Features: {before_val} → {len(feature_cols_value)} (-{removed_val})")
        print(f"  Excluded: {sorted(exclude_set)}")

    if args.prune_bottom > 0:
        # 前回のexperiment結果からimportance読み込み
        prev_result_path = config.ml_dir() / "ml_experiment_v3_result.json"
        if prev_result_path.exists():
            prev_result = json.loads(prev_result_path.read_text(encoding='utf-8'))
            # Place (P) モデルのimportanceを基準にする（VB戦略の核）
            imp_p = prev_result.get('models', {}).get('place', {}).get('feature_importance', [])
            if imp_p:
                n_prune = max(1, len(imp_p) * args.prune_bottom // 100)
                prune_set = set(item['feature'] for item in imp_p[-n_prune:])

                feature_cols_value = [f for f in feature_cols_value if f not in prune_set]
                pruned_features = sorted(prune_set)

                print(f"\n[Pruning] Removing bottom {args.prune_bottom}% features")
                print(f"  Features: {len(FEATURE_COLS_VALUE)} → {len(feature_cols_value)} "
                      f"(-{len(FEATURE_COLS_VALUE) - len(feature_cols_value)} features)")
                print(f"  Pruned: {sorted(prune_set)}")
        else:
            print(f"\n[Pruning] WARNING: No previous result found at {prev_result_path}")
            print(f"  Run experiment without --prune-bottom first to generate importance data")

    # === Optunaパラメータロード ===
    optuna_optimized = False
    optuna_num_boost_round = {}  # モデル別num_boost_round
    optuna_feature_cols = {}     # モデル別特徴量リスト
    # ローカルコピー（グローバル変数を関数内で再代入するとスコープ問題が起きるため）
    params_p = dict(PARAMS_P)
    params_w = dict(PARAMS_W)
    params_ar = dict(PARAMS_AR)
    if args.use_optuna:
        optuna_path = config.ml_dir() / "optuna" / "optuna_best_params.json"
        if not optuna_path.exists():
            print(f"\n  ERROR: Optuna結果が見つかりません: {optuna_path}")
            print(f"  先に python -m ml.optuna_tuner --all を実行してください")
            sys.exit(1)
        optuna_data = json.loads(optuna_path.read_text(encoding='utf-8'))
        optuna_models = optuna_data.get('models', {})

        for model_key in ['p', 'w', 'ar']:
            if model_key in optuna_models:
                opt = optuna_models[model_key]
                opt_params = opt.get('params', {})
                opt_nbr = opt.get('num_boost_round', 1500)
                opt_features = opt.get('features')

                # ハイパーパラメータ上書き
                if model_key == 'p':
                    params_p = {**params_p, **opt_params}
                elif model_key == 'w':
                    params_w = {**params_w, **opt_params}
                elif model_key == 'ar':
                    params_ar = {**params_ar, **opt_params}
                optuna_num_boost_round[model_key] = opt_nbr

                # モデル別特徴量リスト
                if opt_features:
                    optuna_feature_cols[model_key] = [
                        f for f in opt_features if f in df_train.columns
                    ]

                print(f"  [Optuna] Model {model_key.upper()}: "
                      f"trial#{opt.get('best_trial')}, "
                      f"value={opt.get('best_value')}, "
                      f"nbr={opt_nbr}, features={len(opt_features or [])}")

        # デフォルト特徴量をPモデルのOptuna結果で上書き（W/ARに個別結果がなければこれを使う）
        if 'p' in optuna_feature_cols:
            feature_cols_value = optuna_feature_cols['p']

        optuna_optimized = True
        print(f"  [Optuna] Loaded params from {optuna_path}")

    # モデル別特徴量（Optunaで個別最適化されていればそちらを使う）
    features_p = optuna_feature_cols.get('p', feature_cols_value)
    features_w = optuna_feature_cols.get('w', feature_cols_value)
    features_ar = optuna_feature_cols.get('ar', feature_cols_value)

    # === Place モデル P (is_top3) ===
    model_p, metrics_p, importance_p, pred_p, cal_p, pred_p_raw = train_model(
        df_train, df_val, df_test, features_p, params_p, 'is_top3', 'Place',
        num_boost_round=optuna_num_boost_round.get('p', 1500),
    )

    # === Win モデル W (is_win) ===
    model_w, metrics_w, importance_w, pred_w, cal_w, pred_w_raw = train_model(
        df_train, df_val, df_test, features_w, params_w, 'is_win', 'Win',
        num_boost_round=optuna_num_boost_round.get('w', 1500),
    )

    # === Aura モデル AR (着差回帰) ===
    from ml.features.margin_target import add_margin_target_to_df
    print("\n[Margin] Computing target_margin...")
    for label, df in [('train', df_train), ('val', df_val), ('test', df_test)]:
        add_margin_target_to_df(df, date_index, load_race_json, cap=5.0)

    model_ar, metrics_ar, importance_ar, pred_ar = train_regression_model(
        df_train, df_val, df_test, features_ar, params_ar, 'Aura',
        num_boost_round=optuna_num_boost_round.get('ar', 1500),
    )

    # 予測結果をDataFrameに追加
    df_test['pred_proba_p'] = pred_p
    df_test['pred_rank_p'] = df_test.groupby('race_id')['pred_proba_p'].rank(
        ascending=False, method='min'
    )
    # Win モデル
    df_test['pred_proba_w'] = pred_w
    df_test['pred_rank_w'] = df_test.groupby('race_id')['pred_proba_w'].rank(
        ascending=False, method='min'
    )
    # Aura (回帰) モデル
    df_test['pred_margin_ar'] = pred_ar

    # EV (calibrated) — EV分析・bet_engine両方で使用
    # NOTE: pred_w/pred_p は train_model() 内で既にIsotonic calibration済み
    pred_w_cal = pred_w  # already calibrated by train_model()
    pred_p_cal = pred_p  # already calibrated by train_model()
    df_test['win_ev'] = pred_w_cal * df_test['odds']

    # --- キャリブレーション診断: 確率帯別の予測vs実際 ---
    print("\n[Calibration] Win model (W) - probability bin analysis (calibrated):")
    print(f"  {'Bin':>12} {'Pred':>8} {'Actual':>8} {'Ratio':>7} {'N':>7}")
    print(f"  {'-'*48}")
    y_test_win = df_test['is_win'].values
    bin_edges_diag = [0, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50, 1.0]
    for i in range(len(bin_edges_diag) - 1):
        lo, hi = bin_edges_diag[i], bin_edges_diag[i + 1]
        mask = (pred_w_cal >= lo) & (pred_w_cal < hi)
        if mask.sum() == 0:
            continue
        pred_mean = pred_w_cal[mask].mean()
        actual_mean = y_test_win[mask].mean()
        ratio = actual_mean / pred_mean if pred_mean > 0 else float('inf')
        print(f"  {lo:.0%}-{hi:.0%}  {pred_mean:>8.4f} {actual_mean:>8.4f} {ratio:>6.2f}x {mask.sum():>7,}")

    print(f"\n[Calibration] Place model (P) - probability bin analysis (calibrated):")
    print(f"  {'Bin':>12} {'Pred':>8} {'Actual':>8} {'Ratio':>7} {'N':>7}")
    print(f"  {'-'*48}")
    y_test_top3 = df_test['is_top3'].values
    bin_edges_place = [0, 0.10, 0.20, 0.30, 0.40, 0.50, 0.70, 1.0]
    for i in range(len(bin_edges_place) - 1):
        lo, hi = bin_edges_place[i], bin_edges_place[i + 1]
        mask = (pred_p_cal >= lo) & (pred_p_cal < hi)
        if mask.sum() == 0:
            continue
        pred_mean = pred_p_cal[mask].mean()
        actual_mean = y_test_top3[mask].mean()
        ratio = actual_mean / pred_mean if pred_mean > 0 else float('inf')
        print(f"  {lo:.0%}-{hi:.0%}  {pred_mean:>8.4f} {actual_mean:>8.4f} {ratio:>6.2f}x {mask.sum():>7,}")

    # Raw vs Calibrated comparison
    print(f"\n[Calibration] Raw vs Calibrated summary (Win model):")
    print(f"  Raw    mean={pred_w_raw.mean():.6f}, min={pred_w_raw.min():.6f}, max={pred_w_raw.max():.6f}")
    print(f"  Cal    mean={pred_w_cal.mean():.6f}, min={pred_w_cal.min():.6f}, max={pred_w_cal.max():.6f}")
    print(f"  Actual win_rate={y_test_win.mean():.6f}")

    # --- AR偏差値 (ARd) を df_test に計算 ---
    # predict.py / bet_engine.py と同じロジック: RATING変換後にARdを算出
    from ml.bet_engine import RATING_BASE, RATING_SCALE
    df_test['_ar_rating'] = RATING_BASE - df_test['pred_margin_ar'] * RATING_SCALE
    ar_groups = df_test.groupby('race_id')['_ar_rating']
    ar_mean = ar_groups.transform('mean')
    ar_std = ar_groups.transform('std').clip(lower=3.0)  # floor=3.0はレーティングスケール
    df_test['ar_deviation'] = (50 + 10 * (df_test['_ar_rating'] - ar_mean) / ar_std).round(1)
    df_test.drop(columns=['_ar_rating'], inplace=True)

    # 分析
    print("\n[Analysis] Hit rate analysis (v2)...")
    hit_p = calc_hit_analysis(df_test, 'pred_proba_p')
    hit_v2_place = calc_hit_analysis_v2(df_test, 'pred_proba_p')
    hit_v2_win = calc_hit_analysis_v2(df_test, 'pred_proba_w')
    hit_v2_aura = calc_hit_analysis_v2(df_test, 'pred_margin_ar', ascending=True)
    ard_analysis = calc_ard_threshold_analysis(df_test)
    print(f"  Top1 好走率: P={hit_v2_place['top1_place_rate']:.1%} W={hit_v2_win['top1_place_rate']:.1%} AR={hit_v2_aura['top1_place_rate']:.1%}")
    print(f"  Top1 勝率:   P={hit_v2_place['top1_win_rate']:.1%} W={hit_v2_win['top1_win_rate']:.1%} AR={hit_v2_aura['top1_win_rate']:.1%}")
    print(f"  ARd閾値別:")
    for a in ard_analysis:
        print(f"    ARd>={a['threshold']}: {a['total']}頭 勝率{a['win_rate']:.1%} 好走率{a['place_rate']:.1%}")

    roi_p = calc_roi_analysis(df_test, 'pred_proba_p')
    roi_w = calc_roi_analysis(df_test, 'pred_proba_w')
    roi_ar = calc_roi_analysis(df_test, 'pred_margin_ar', ascending=True)

    print("\n[Analysis] Value Bet analysis (Place model)...")
    vb_analysis = calc_value_bet_analysis(df_test, rank_col='pred_rank_p')
    vb_picks = collect_value_bet_picks(df_test, min_gap=VALUE_BET_MIN_GAP)
    print(f"  Value Bet picks: {len(vb_picks)} entries (gap >= {VALUE_BET_MIN_GAP})")

    print("\n[Analysis] Value Bet analysis (Win model)...")
    vb_win_analysis = calc_value_bet_analysis(df_test, rank_col='pred_rank_w')
    print(f"  Win VB analysis done")

    print("\n[Analysis] Bootstrap ROI confidence intervals...")
    vb_bootstrap_place = calc_vb_bootstrap_ci(df_test, rank_col='pred_rank_p')
    vb_bootstrap_win = calc_vb_bootstrap_ci(df_test, rank_col='pred_rank_w')
    for bs in vb_bootstrap_place:
        g = bs['min_gap']
        print(f"  Place gap>={g}: ROI {bs['place_roi']:>6.1f}% "
              f"[{bs['place_roi_ci_low']:.1f}% - {bs['place_roi_ci_high']:.1f}%] "
              f"(n={bs['bet_count']}, races={bs['n_races_with_vb']})")
    for bs in vb_bootstrap_win:
        g = bs['min_gap']
        print(f"  Win   gap>={g}: ROI {bs['win_roi']:>6.1f}% "
              f"[{bs['win_roi_ci_low']:.1f}% - {bs['win_roi_ci_high']:.1f}%] "
              f"(n={bs['bet_count']}, races={bs['n_races_with_vb']})")

    # --- EV vs Gap 比較分析 ---
    ev_gap_results = calc_ev_gap_comparison(df_test)

    print("\n[Analysis] Collecting race predictions...")
    race_preds = collect_race_predictions(df_test)
    print(f"  Race predictions: {len(race_preds)} races")

    print("\n[Analysis] Gap × Margin grid...")
    gap_margin_grid = calc_gap_margin_grid(df_test)
    print(f"  Gap×Margin grid: {len(gap_margin_grid)} cells")

    print("\n[Analysis] Gap × ARd grid...")
    gap_ard_grid = calc_gap_ard_grid(df_test)
    print(f"  Gap×ARd grid: {len(gap_ard_grid)} cells")

    # --- bet_engine プリセット バックテスト ---
    print("\n[Analysis] bet_engine preset backtest...")
    bet_engine_presets = {}
    try:
        from ml.bet_engine import (
            PRESETS as BET_PRESETS,
            generate_recommendations as bet_gen_recs,
            df_to_race_predictions as bet_df_to_recs,
            calc_bet_engine_roi as bet_calc_roi,
        )
        from dataclasses import asdict as _asdict

        # df_test にbet_engine用の追加列を計算
        # pred_p_raw: LightGBM生出力（Kelly計算用。sum≈3.0でP(top3)として正しい）
        df_test['pred_proba_p_raw'] = pred_p_raw
        df_test['vb_gap'] = (df_test['odds_rank'] - df_test['pred_rank_p']).clip(lower=0).astype(int)
        df_test['win_vb_gap'] = (df_test['odds_rank'] - df_test['pred_rank_w']).clip(lower=0).astype(int)

        # place_ev (win_evは既に計算済み)
        place_odds_col = df_test['place_odds_low'].fillna(df_test['odds'] / 3.5)
        df_test['place_ev'] = pred_p_cal * place_odds_col

        # grade offsets for Method A (AR absolute rating)
        from ml.bet_engine import load_grade_offsets as _load_grade_offsets
        _grade_offsets = _load_grade_offsets()
        if _grade_offsets:
            print(f"  Grade offsets: {len(_grade_offsets)} grades loaded")

        bet_race_preds = bet_df_to_recs(df_test, grade_offsets=_grade_offsets)

        # entry lookup for ROI calc
        entry_lookup = {}
        for race in bet_race_preds:
            for e in race['entries']:
                entry_lookup[(race['race_id'], e['umaban'])] = e

        for preset_name, preset_params in BET_PRESETS.items():
            recs = bet_gen_recs(bet_race_preds, preset_params, budget=30000)
            roi = bet_calc_roi(recs, bet_race_preds)

            # --- Bootstrap CI for bet_engine ROI ---
            # Group bets by race_id
            race_bet_results = {}
            for r in recs:
                entry = entry_lookup.get((r.race_id, r.umaban))
                if entry is None:
                    continue
                if r.race_id not in race_bet_results:
                    race_bet_results[r.race_id] = []
                w_bet = r.win_amount if r.win_amount > 0 else 0
                p_bet = r.place_amount if r.place_amount > 0 else 0
                w_ret = entry['odds'] * r.win_amount if r.win_amount > 0 and entry['is_win'] else 0
                p_ret = 0
                if r.place_amount > 0 and entry['is_top3']:
                    p_odds = entry.get('place_odds_min')
                    if p_odds and p_odds > 0:
                        p_ret = p_odds * r.place_amount
                    else:
                        p_ret = max(entry['odds'] / 3.5, 1.1) * r.place_amount
                race_bet_results[r.race_id].append((w_bet + p_bet, w_ret + p_ret))

            rng = np.random.default_rng(42)
            boot_rois = []
            race_ids_with_bets = list(race_bet_results.keys())
            n_races_bet = len(race_ids_with_bets)
            if n_races_bet > 0:
                for _ in range(1000):
                    sampled = rng.choice(race_ids_with_bets, size=n_races_bet, replace=True)
                    b_bet = sum(bet for rid in sampled for bet, _ in race_bet_results[rid])
                    b_ret = sum(ret for rid in sampled for _, ret in race_bet_results[rid])
                    if b_bet > 0:
                        boot_rois.append(b_ret / b_bet * 100)
                boot_arr = np.array(boot_rois)
                ci_low = round(float(np.percentile(boot_arr, 2.5)), 1)
                ci_high = round(float(np.percentile(boot_arr, 97.5)), 1)
                ci_std = round(float(np.std(boot_arr)), 1)
            else:
                ci_low, ci_high, ci_std = 0, 0, 0

            bet_engine_presets[preset_name] = {
                'params': _asdict(preset_params),
                **roi,
                'bootstrap_ci_low': ci_low,
                'bootstrap_ci_high': ci_high,
                'bootstrap_std': ci_std,
            }
            marker = ' ***' if roi['total_roi'] >= 100 else ''
            print(f"  {preset_name:>14}: ROI {roi['total_roi']:>6.1f}%{marker}  "
                  f"[{ci_low:.1f}% - {ci_high:.1f}%]  "
                  f"(bets={roi['num_bets']}, net={roi['total_return'] - roi['total_bet']:+,})")
    except Exception as e:
        print(f"  bet_engine backtest failed (non-fatal): {e}")
        bet_engine_presets = {}

    # 結果表示
    print(f"\n{'='*60}")
    print(f"  Results")
    print(f"{'='*60}")
    print(f"\n  --- Place Model P (target=is_top3) ---")
    print(f"  Place (P):  AUC={metrics_p['auc']}, Brier={metrics_p['brier_score']}, "
          f"ECE={metrics_p['ece']}, Iter={metrics_p['best_iteration']}")

    print(f"\n  --- Win Model W (target=is_win) ---")
    print(f"  Win   (W):  AUC={metrics_w['auc']}, Brier={metrics_w['brier_score']}, "
          f"ECE={metrics_w['ece']}, Iter={metrics_w['best_iteration']}")

    print(f"\n  --- Aura Model AR (target=margin) ---")
    print(f"  Aura  (AR): MAE={metrics_ar['mae']}, Corr={metrics_ar['correlation']}, "
          f"Iter={metrics_ar['best_iteration']}")

    print(f"\n  Hit Analysis (Place P):")
    for h in hit_p:
        print(f"    Top{h['top_n']}: {h['hit_rate']:.1%} ({h['hits']}/{h['total']})")

    print(f"\n  ROI (Place P): Win={roi_p['top1_win_roi']:.1f}%, Place={roi_p['top1_place_roi']:.1f}%")
    print(f"  ROI (Win W):   Win={roi_w['top1_win_roi']:.1f}%, Place={roi_w['top1_place_roi']:.1f}%")
    print(f"  ROI (Aura AR): Win={roi_ar['top1_win_roi']:.1f}%, Place={roi_ar['top1_place_roi']:.1f}%")

    print(f"\n  Value Bet Analysis (Place):")
    for vb in vb_analysis:
        marker = " ***" if vb['place_roi'] >= 100 else ""
        print(f"    gap>={vb['min_gap']}: {vb['bet_count']:,} bets, "
              f"hit={vb['place_hit_rate']:.1%}, ROI={vb['place_roi']:.1f}%{marker}")

    print(f"\n  Value Bet Analysis (Win):")
    for vb in vb_win_analysis:
        marker = " ***" if vb['win_roi'] >= 100 else ""
        print(f"    gap>={vb['min_gap']}: {vb['bet_count']:,} bets, "
              f"win_hit={vb['win_hits']}, win_ROI={vb['win_roi']:.1f}%{marker}")

    print(f"\n  Feature Importance (Place P Top 10):")
    sorted_imp_p = sorted(importance_p.items(), key=lambda x: x[1], reverse=True)[:10]
    for fname, imp in sorted_imp_p:
        print(f"    {fname:>25}: {imp:,.0f}")

    print(f"\n  Feature Importance (Win W Top 10):")
    sorted_imp_w = sorted(importance_w.items(), key=lambda x: x[1], reverse=True)[:10]
    for fname, imp in sorted_imp_w:
        print(f"    {fname:>25}: {imp:,.0f}")

    # H-21: 芝/ダート分離モデル実験
    track_split_results = None
    if args.split_track:
        track_split_results = run_track_split_experiment(
            df_train, df_val, df_test,
            feature_cols_value,
            params_p,
            pred_p,
        )

    # バージョン未指定の場合はmodel_meta.jsonから読む
    if not experiment_version:
        meta_path = config.ml_dir() / "model_meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding='utf-8'))
            experiment_version = meta.get('version', '5.5')
        else:
            experiment_version = '5.5'
        print(f"\n  [WARN] --version 未指定のため v{experiment_version} を使用")

    # モデル保存（旧バージョンをアーカイブしてから上書き）
    model_dir = config.ml_dir()
    config.ensure_dir(model_dir)

    current_meta_path = model_dir / "model_meta.json"
    if current_meta_path.exists():
        from core.versioning import archive_before_save
        old_meta = json.loads(current_meta_path.read_text(encoding='utf-8'))
        old_ver = old_meta.get('version', 'unknown')
        archive_before_save(
            base_dir=model_dir,
            version=old_ver,
            files=["model_p.txt", "model_w.txt", "model_ar.txt",
                   "model_meta.json", "ml_experiment_v3_result.json",
                   "calibrators.pkl"],
            metadata={"created_at": old_meta.get("created_at", "")},
        )

    model_p.save_model(str(model_dir / "model_p.txt"))
    model_w.save_model(str(model_dir / "model_w.txt"))
    model_ar.save_model(str(model_dir / "model_ar.txt"))

    # IsotonicRegressionキャリブレーター保存
    import pickle
    calibrators = {'cal_p': cal_p, 'cal_w': cal_w}
    with open(model_dir / "calibrators.pkl", 'wb') as f:
        pickle.dump(calibrators, f)
    print(f"  Calibrators saved: {list(calibrators.keys())}")

    import sklearn
    # features_value = 全モデルの特徴量union（predict.pyが使う）
    all_features_union = list(dict.fromkeys(features_p + features_w + features_ar))
    meta = {
        'version': experiment_version,
        'features_value': all_features_union,
        'market_features': list(MARKET_FEATURES),
        'targets': {'place': 'is_top3', 'win': 'is_win', 'margin': 'target_margin'},
        'odds_source': 'mykeibadb' if use_db_odds else 'json_confirmed',
        'has_calibrators': True,
        'has_regression_model': True,
        'has_pedigree_features': True,
        'pedigree_features': PEDIGREE_FEATURES,
        'sklearn_version': sklearn.__version__,
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'split': {'train': train_label, 'val': val_label, 'test': test_label},
        'optuna_optimized': optuna_optimized,
    }
    # Optunaでモデル別特徴量が異なる場合、個別リストも保存
    if optuna_optimized and optuna_feature_cols:
        meta['features_per_model'] = {
            'p': features_p,
            'w': features_w,
            'ar': features_ar,
        }
    (model_dir / "model_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    # 結果JSON保存
    result = {
        'version': experiment_version,
        'experiment': 'ml_experiment_v3',
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'split': {
            'train': train_label,
            'val': val_label,
            'test': test_label,
        },
        'pruning': {
            'prune_bottom_pct': args.prune_bottom,
            'pruned_features': pruned_features,
        } if pruned_features else None,
        'models': {
            'place': {
                'target': 'is_top3',
                'features': features_p,
                'feature_count': len(features_p),
                'metrics': metrics_p,
                'feature_importance': [
                    {'feature': f, 'importance': int(i)}
                    for f, i in sorted(importance_p.items(), key=lambda x: -x[1])
                ],
            },
            'win': {
                'target': 'is_win',
                'features': features_w,
                'feature_count': len(features_w),
                'metrics': metrics_w,
                'feature_importance': [
                    {'feature': f, 'importance': int(i)}
                    for f, i in sorted(importance_w.items(), key=lambda x: -x[1])
                ],
            },
            'aura': {
                'target': 'target_margin',
                'features': features_ar,
                'feature_count': len(features_ar),
                'metrics': metrics_ar,
                'feature_importance': [
                    {'feature': f, 'importance': int(i)}
                    for f, i in sorted(importance_ar.items(), key=lambda x: -x[1])
                ],
            },
        },
        'hit_analysis': {
            'place': hit_p,
            'place_v2': hit_v2_place,
            'win_v2': hit_v2_win,
            'aura_v2': hit_v2_aura,
            'ard_analysis': ard_analysis,
        },
        'roi_analysis': {
            'place': roi_p,
            'win': roi_w,
            'aura': roi_ar,
        },
        'value_bets': {
            'by_rank_gap': vb_analysis,
            'win_by_rank_gap': vb_win_analysis,
            'bootstrap_ci_place': vb_bootstrap_place,
            'bootstrap_ci_win': vb_bootstrap_win,
        },
        'value_bet_picks': vb_picks,
        'race_predictions': race_preds,
        'gap_margin_grid': gap_margin_grid,
        'gap_ard_grid': gap_ard_grid,
        'ev_gap_comparison': ev_gap_results if ev_gap_results else None,
        'bet_engine_presets': bet_engine_presets if bet_engine_presets else None,
    }

    if track_split_results:
        result['track_split_experiment'] = track_split_results

    result_path = model_dir / "ml_experiment_v3_result.json"
    result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    elapsed = time.time() - t0
    print(f"\n  Elapsed: {elapsed:.1f}s")
    print(f"  Models saved to: {model_dir}")
    print(f"  Results saved to: {result_path}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
