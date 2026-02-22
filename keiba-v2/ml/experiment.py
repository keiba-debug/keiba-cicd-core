#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ML Experiment: LightGBMデュアルモデル学習・評価パイプライン

モデルバージョンは model_meta.json の version フィールドで管理。
旧バージョンは versions/ に自動アーカイブされる。

特徴量構成:
  Model A (全特徴量): 基本 + 過去走 + trainer + jockey + 脚質 + ローテ + ペース + 調教 + スピード指数 + KB印 + 市場系
  Model B (Value):     Model Aから市場系特徴量を除外

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
]

# 調教師特徴量（100%マッチ）
TRAINER_FEATURES = [
    'trainer_win_rate', 'trainer_top3_rate', 'trainer_venue_top3_rate',
]

# 騎手特徴量
JOCKEY_FEATURES = [
    'jockey_win_rate', 'jockey_top3_rate', 'jockey_venue_top3_rate',
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

# 市場系特徴量（Model Bでは除外）
MARKET_FEATURES = {
    'odds', 'popularity', 'odds_rank', 'popularity_trend',
    'kb_mark_point', 'kb_aggregate_mark_point',  # v4.0: 印は市場と相関
    # v4.1: CK_DATA調教は市場に織り込み済み → Model Bから除外
    'ck_laprank_score', 'ck_laprank_class', 'ck_laprank_accel',
    'ck_time_rank', 'ck_final_laprank_score', 'ck_final_time4f', 'ck_final_lap1',
    # v5.1: クラス・会場差は出馬表で自明 → MARKET
    'prev_grade_level', 'grade_level_diff', 'venue_rank_diff',
    # v5.3: ヘッダーマークは honshi_mark と相関 → MARKET
    'comment_stable_mark',
    # v5.4: ベイズ平滑化レートは生rate+オッズと相関 → MARKET
    # （Model B精度向上がVB gap効果を殺すため除外）
    'win_rate_smoothed', 'top3_rate_smoothed',
    'venue_top3_rate_smoothed', 'track_type_top3_rate_smoothed',
    'distance_fitness_smoothed',
}

# 派生特徴量
DERIVED_FEATURES = ['odds_rank']

# 全特徴量（Model A）
FEATURE_COLS_ALL = (
    BASE_FEATURES + ['odds', 'popularity'] + DERIVED_FEATURES +
    PAST_FEATURES + TRAINER_FEATURES + JOCKEY_FEATURES +
    RUNNING_STYLE_FEATURES + ROTATION_FEATURES + ['popularity_trend'] +
    PACE_FEATURES + TRAINING_FEATURES + KB_MARK_FEATURES + SPEED_FEATURES +
    COMMENT_FEATURES + SLOW_START_FEATURES
)

# Value特徴量（Model B = 市場系除外）
FEATURE_COLS_VALUE = [f for f in FEATURE_COLS_ALL if f not in MARKET_FEATURES]

# ハイパーパラメータ（Model A/B別）
PARAMS_A = {
    'objective': 'binary',
    'metric': 'auc',
    'num_leaves': 63,
    'learning_rate': 0.03,
    'feature_fraction': 0.8,
    'bagging_fraction': 0.8,
    'bagging_freq': 5,
    'min_child_samples': 30,
    'reg_alpha': 0.1,
    'reg_lambda': 1.0,
    'max_depth': 7,
    'verbose': -1,
}

PARAMS_B = {
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
}

# Win モデル用パラメータ（is_win は ~6-7% と不均衡 → scale_pos_weight で補正）
PARAMS_W = {
    **PARAMS_A,
    'scale_pos_weight': 5.0,
}

PARAMS_WV = {
    **PARAMS_B,
    'scale_pos_weight': 5.0,
}

# 回帰モデル用パラメータ (着差回帰: Huber loss)
PARAMS_REG_B = {
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


def load_data() -> Tuple[dict, dict, dict, dict, dict, dict, dict]:
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

    # Pace index
    pace_index = build_pace_index(date_index)

    # Keibabook ext index
    kb_ext_index = build_kb_ext_index(date_index)

    # CK_DATA training summary index
    training_summary_index = build_training_summary_index(date_index)

    return (history_cache, trainer_index, jockey_index,
            date_index, pace_index, kb_ext_index, training_summary_index)


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
) -> List[dict]:
    """1レースの全出走馬の特徴量を計算

    Args:
        db_odds: mykeibadbから取得した事前オッズ {umaban: {'odds': float, 'ninki': int}}
        training_summary_index: CK_DATA調教サマリ {date_str: {ketto_num: summary}}
        db_place_odds: mykeibadb複勝オッズ {umaban: {'odds_low': float, 'odds_high': float}}
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

    race_date = race['date']
    race_id = race['race_id']
    venue_code = race['venue_code']
    venue_name = race.get('venue_name', '')
    track_type = race.get('track_type', '')
    distance = race.get('distance', 0)
    entry_count = race.get('num_runners', 0)
    current_grade = race.get('grade', '')
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
        )
        feat.update(past)

        # 調教師特徴量
        tc = entry.get('trainer_code', '')
        trainer_feat = get_trainer_features(tc, venue_code, trainer_index)
        feat.update(trainer_feat)

        # 騎手特徴量
        jc = entry.get('jockey_code', '')
        jockey_feat = get_jockey_features(jc, venue_code, jockey_index)
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

        # メタ情報（学習には使わないが分析用）
        feat['race_id'] = race_id
        feat['date'] = race_date
        feat['ketto_num'] = ketto_num
        feat['horse_name'] = entry.get('horse_name', '')
        feat['umaban'] = entry.get('umaban', 0)
        feat['venue_name'] = race.get('venue_name', '')
        feat['grade'] = race.get('grade', '')
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
) -> pd.DataFrame:
    """全レースの特徴量を構築してDataFrameで返す

    Args:
        use_db_odds: True=mykeibadbから事前オッズ取得, False=JSON確定オッズ（従来動作）
        training_summary_index: CK_DATA調教サマリインデックス
    """
    print(f"\n[Build] Building dataset for {min_year}-{max_year}...")

    # 対象レースIDを収集
    target_races = []
    for date_str, race_id in _iter_date_index(date_index):
        year = int(date_str[:4])
        if year < min_year or year > max_year:
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

    for date_str, race_id in target_races:
        try:
            race = load_race_json(race_id, date_str)
            rows = compute_features_for_race(
                race, history_cache, trainer_index, jockey_index,
                pace_index, kb_ext_index,
                db_odds=db_odds_index.get(race_id),
                training_summary_index=training_summary_index,
                db_place_odds=db_place_odds_index.get(race_id),
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
    _numeric_cols = set(FEATURE_COLS_ALL)
    for col in df.columns:
        if col in _numeric_cols and df[col].dtype == object:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # odds_rank（レース内オッズ順位）を追加
    if 'odds' in df.columns:
        df['odds_rank'] = df.groupby('race_id')['odds'].rank(method='min')

    print(f"[Build] {race_count:,} races, {len(df):,} entries, {error_count} errors")
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
        params, train_data, num_boost_round=1500,
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

    return model, metrics, importance, y_pred_cal, calibrator


def calc_hit_analysis(df: pd.DataFrame, pred_col: str) -> List[dict]:
    """Top-N的中率分析"""
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


def _get_place_odds(row) -> float:
    """複勝オッズを取得: DB実績値があればそれを使用、なければ推定"""
    place_low = row.get('place_odds_low')
    if pd.notna(place_low) and place_low > 0:
        return float(place_low)
    # DB複勝オッズなし: 単勝オッズから推定
    return max(row['odds'] / 3.5, 1.1)


def calc_roi_analysis(df: pd.DataFrame, pred_col: str) -> dict:
    """ROI分析（Top1）"""
    df['pred_rank'] = df.groupby('race_id')[pred_col].rank(ascending=False, method='min')
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


def calc_value_bet_analysis(df: pd.DataFrame, rank_col: str = 'pred_rank_v') -> List[dict]:
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
    rank_col: str = 'pred_rank_v',
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
    required = ['pred_rank_v', 'odds_rank', 'win_ev', 'pred_margin_b', 'odds', 'is_win']
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
    vb_base = df[(df['pred_rank_v'] <= 3) & (df['odds'] > 0)].copy()
    vb_base['gap'] = (vb_base['odds_rank'] - vb_base['pred_rank_v']).clip(lower=0).astype(int)

    results = {'conditions': [], 'ev_grid': []}

    # --- EV threshold grid search ---
    ev_thresholds = [1.1, 1.2, 1.3, 1.5, 1.8, 2.0]
    gap_levels = [5, 6, 7]
    margin_levels = [0.8, 1.2]

    for margin in margin_levels:
        margin_mask = vb_base['pred_margin_b'] <= margin

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
    if 'pred_rank_v' not in df.columns or 'odds_rank' not in df.columns:
        return []

    picks = []
    for race_id, group in df.groupby('race_id'):
        candidates = group[
            (group['pred_rank_v'] <= 3) &
            (group['odds_rank'] >= group['pred_rank_v'] + min_gap)
        ]
        for _, row in candidates.iterrows():
            gap = int(row['odds_rank'] - row['pred_rank_v'])
            picks.append({
                'race_id': str(row['race_id']),
                'date': str(row['date']),
                'venue': str(row.get('venue_name', '')),
                'grade': str(row.get('grade', '')),
                'horse_number': int(row.get('umaban', 0)),
                'horse_name': str(row.get('horse_name', '')),
                'value_rank': int(row['pred_rank_v']),
                'odds_rank': int(row['odds_rank']),
                'gap': gap,
                'odds': round(float(row['odds']), 1) if row['odds'] > 0 else None,
                'pred_proba_accuracy': round(float(row['pred_proba_a']), 4),
                'pred_proba_value': round(float(row['pred_proba_v']), 4),
                'predicted_margin': round(float(row['pred_margin_b']), 3) if pd.notna(row.get('pred_margin_b')) else None,
                'win_ev': round(float(row['win_ev']), 3) if 'win_ev' in row.index and pd.notna(row.get('win_ev')) else None,
                'actual_position': int(row['finish_position']),
                'is_top3': int(row['is_top3']),
            })

    picks.sort(key=lambda x: (-x['gap'], x['date']))
    return picks


def calc_gap_margin_grid(df: pd.DataFrame) -> List[dict]:
    """gap × margin クロス集計 (ML Report ヒートマップ用)

    VB候補 (pred_rank_v <= 3) に対して、gap閾値とmargin閾値の
    組み合わせごとの件数・単勝ROI・複勝ROIを計算する。
    """
    if 'pred_rank_v' not in df.columns or 'pred_margin_b' not in df.columns:
        return []

    grid = []
    for min_gap in [3, 4, 5, 6]:
        for max_margin in [0.6, 0.8, 1.0, 1.2, 1.5, None]:
            mask = (
                (df['pred_rank_v'] <= 3) &
                (df['odds_rank'] >= df['pred_rank_v'] + min_gap)
            )
            if max_margin is not None:
                mask = mask & (df['pred_margin_b'] <= max_margin)
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


def collect_race_predictions(df: pd.DataFrame) -> List[dict]:
    """テスト期間のレース別予測データを収集"""
    races = []
    for race_id, group in df.groupby('race_id'):
        group_sorted = group.sort_values('pred_proba_a', ascending=False)
        row0 = group_sorted.iloc[0]
        horses = []
        for _, row in group_sorted.iterrows():
            horses.append({
                'horse_number': int(row.get('umaban', 0)),
                'horse_name': str(row.get('horse_name', '')),
                'pred_proba_accuracy': round(float(row['pred_proba_a']), 4),
                'pred_proba_value': round(float(row['pred_proba_v']), 4),
                'pred_top3': int(row['pred_rank_a'] <= 3),
                'actual_position': int(row['finish_position']),
                'actual_top3': int(row['is_top3']),
                'odds_rank': int(row['odds_rank']) if row.get('odds_rank', 0) > 0 else None,
                'odds': round(float(row['odds']), 1) if row.get('odds', 0) > 0 else None,
                'value_rank': int(row['pred_rank_v']),
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
    model_name: str = 'Reg_B',
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

    print(f"\n[Train] {model_name}: {len(feature_cols)} features, "
          f"train={len(X_train):,}, val={len(X_val):,}, test={len(X_test):,}")

    train_data = lgb.Dataset(X_train, label=y_train)
    valid_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

    model = lgb.train(
        params, train_data, num_boost_round=1500,
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
    feature_cols_all: List[str],
    feature_cols_value: List[str],
    params_a: dict,
    params_b: dict,
    unified_pred_a: np.ndarray,
    unified_pred_b: np.ndarray,
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
    split_features_all = [f for f in feature_cols_all if f != 'track_type']
    split_features_value = [f for f in feature_cols_value if f != 'track_type']
    print(f"  Features (excl track_type): A={len(split_features_all)}, B={len(split_features_value)}")

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

        # Model A (split)
        model_a_s, metrics_a_s, _, pred_a_s, _ = train_model(
            tr, vl, ts, split_features_all, params_a, 'is_top3', f'A_{track_label}'
        )

        # Model B (split)
        model_b_s, metrics_b_s, _, pred_b_s, _ = train_model(
            tr, vl, ts, split_features_value, params_b, 'is_top3', f'B_{track_label}'
        )

        # 統一モデルの同じサブセットでの性能
        test_mask = df_test['track_type'] == track_val
        unified_a_sub = unified_pred_a[test_mask.values]
        unified_b_sub = unified_pred_b[test_mask.values]
        y_test_sub = ts['is_top3']

        unified_auc_a = roc_auc_score(y_test_sub, unified_a_sub)
        unified_auc_b = roc_auc_score(y_test_sub, unified_b_sub)

        # VB分析（分離モデル）
        ts_copy = ts.copy()
        ts_copy['pred_proba_a'] = pred_a_s
        ts_copy['pred_proba_v'] = pred_b_s
        ts_copy['pred_rank_a'] = ts_copy.groupby('race_id')['pred_proba_a'].rank(ascending=False, method='min')
        ts_copy['pred_rank_v'] = ts_copy.groupby('race_id')['pred_proba_v'].rank(ascending=False, method='min')
        vb_split = calc_value_bet_analysis(ts_copy)

        # 統一モデルのVB分析（同サブセット）
        ts_unified = ts.copy()
        ts_unified['pred_proba_a'] = unified_a_sub
        ts_unified['pred_proba_v'] = unified_b_sub
        ts_unified['pred_rank_a'] = ts_unified.groupby('race_id')['pred_proba_a'].rank(ascending=False, method='min')
        ts_unified['pred_rank_v'] = ts_unified.groupby('race_id')['pred_proba_v'].rank(ascending=False, method='min')
        vb_unified = calc_value_bet_analysis(ts_unified)

        # ROI分析
        roi_split_a = calc_roi_analysis(ts_copy, 'pred_proba_a')
        roi_split_b = calc_roi_analysis(ts_copy, 'pred_proba_v')
        roi_unified_a = calc_roi_analysis(ts_unified, 'pred_proba_a')
        roi_unified_b = calc_roi_analysis(ts_unified, 'pred_proba_v')

        # 比較表示
        print(f"\n  === {track_label.upper()} 比較 ===")
        print(f"  {'Model':<15} {'統一AUC':>10} {'分離AUC':>10} {'差分':>10}")
        print(f"  {'A (Accuracy)':<15} {unified_auc_a:>10.4f} {metrics_a_s['auc']:>10.4f} {metrics_a_s['auc']-unified_auc_a:>+10.4f}")
        print(f"  {'B (Value)':<15} {unified_auc_b:>10.4f} {metrics_b_s['auc']:>10.4f} {metrics_b_s['auc']-unified_auc_b:>+10.4f}")

        print(f"\n  ROI (Top1):")
        print(f"  {'Model':<15} {'統一Win':>10} {'分離Win':>10} {'統一Place':>12} {'分離Place':>12}")
        print(f"  {'A':<15} {roi_unified_a['top1_win_roi']:>9.1f}% {roi_split_a['top1_win_roi']:>9.1f}% "
              f"{roi_unified_a['top1_place_roi']:>11.1f}% {roi_split_a['top1_place_roi']:>11.1f}%")
        print(f"  {'B':<15} {roi_unified_b['top1_win_roi']:>9.1f}% {roi_split_b['top1_win_roi']:>9.1f}% "
              f"{roi_unified_b['top1_place_roi']:>11.1f}% {roi_split_b['top1_place_roi']:>11.1f}%")

        print(f"\n  VB Place ROI:")
        print(f"  {'Gap':<10} {'統一':>10} {'分離':>10} {'差分':>10}")
        for vu, vs in zip(vb_unified, vb_split):
            diff = vs['place_roi'] - vu['place_roi']
            marker = " ***" if diff > 0 else ""
            print(f"  >={vu['min_gap']:<8} {vu['place_roi']:>9.1f}% {vs['place_roi']:>9.1f}% {diff:>+9.1f}%{marker}")

        results[track_label] = {
            'split_metrics_a': metrics_a_s,
            'split_metrics_b': metrics_b_s,
            'unified_auc_a': round(unified_auc_a, 4),
            'unified_auc_b': round(unified_auc_b, 4),
            'split_vb': vb_split,
            'unified_vb': vb_unified,
            'split_roi_a': roi_split_a,
            'split_roi_b': roi_split_b,
            'unified_roi_a': roi_unified_a,
            'unified_roi_b': roi_unified_b,
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


def main():
    parser = argparse.ArgumentParser(description='ML Experiment v3')
    parser.add_argument('--train-years', default='2020-2023', help='Training year range')
    parser.add_argument('--val-years', default='2024', help='Validation year range (early stopping)')
    parser.add_argument('--test-years', default='2025-2026', help='Test year range (pure evaluation)')
    parser.add_argument('--no-db', action='store_true', help='DBオッズ未使用（JSON確定オッズ）')
    parser.add_argument('--split-track', action='store_true', help='芝/ダート分離モデル実験 (H-21)')
    parser.add_argument('--version', default=None, help='モデルバージョン文字列 (例: 5.3)')
    parser.add_argument('--prune-bottom', type=int, default=0,
                        help='Importance下位N%%の特徴量を除外 (例: 20)')
    parser.add_argument('--exclude-features', nargs='+', default=[],
                        help='除外する特徴量名のリスト (例: --exclude-features feat1 feat2)')
    args = parser.parse_args()

    train_min, train_max = parse_year_range(args.train_years)
    val_min, val_max = parse_year_range(args.val_years)
    test_min, test_max = parse_year_range(args.test_years)
    use_db_odds = not args.no_db

    # バージョン文字列: CLI指定 or 自動生成
    if args.version:
        experiment_version = args.version
    else:
        # デフォルト: model_meta.json の現バージョンから自動インクリメント案内
        current_meta_path = config.ml_dir() / "model_meta.json"
        if current_meta_path.exists():
            current_meta = json.loads(current_meta_path.read_text(encoding='utf-8'))
            current_ver = current_meta.get('version', '?')
            print(f"\n  WARNING: --version 未指定。現在のバージョンは v{current_ver}")
            print(f"  推奨: --version {current_ver} または新バージョンを指定してください")
        experiment_version = None  # 後で入力を求めるか、従来のハードコード値を使う

    print(f"\n{'='*60}")
    print(f"  KeibaCICD v4 - ML Experiment")
    print(f"  Train: {train_min}-{train_max}")
    print(f"  Val:   {val_min}-{val_max} (early stopping)")
    print(f"  Test:  {test_min}-{test_max} (pure evaluation)")
    print(f"  DB Odds: {'ON' if use_db_odds else 'OFF (JSON fallback)'}")
    print(f"  Model A features: {len(FEATURE_COLS_ALL)}")
    print(f"  Model B features: {len(FEATURE_COLS_VALUE)}")
    print(f"  NaN handling: LightGBM native")
    print(f"{'='*60}\n")

    t0 = time.time()

    # データロード
    (history_cache, trainer_index, jockey_index,
     date_index, pace_index, kb_ext_index, training_summary_index) = load_data()

    # データセット構築（3-way split）
    df_train = build_dataset(
        date_index, history_cache, trainer_index, jockey_index, pace_index,
        kb_ext_index, train_min, train_max, use_db_odds=use_db_odds,
        training_summary_index=training_summary_index,
    )
    df_val = build_dataset(
        date_index, history_cache, trainer_index, jockey_index, pace_index,
        kb_ext_index, val_min, val_max, use_db_odds=use_db_odds,
        training_summary_index=training_summary_index,
    )
    df_test = build_dataset(
        date_index, history_cache, trainer_index, jockey_index, pace_index,
        kb_ext_index, test_min, test_max, use_db_odds=use_db_odds,
        training_summary_index=training_summary_index,
    )

    print(f"\n[Dataset] Train: {len(df_train):,} entries from "
          f"{df_train['race_id'].nunique():,} races")
    print(f"[Dataset] Val:   {len(df_val):,} entries from "
          f"{df_val['race_id'].nunique():,} races")
    print(f"[Dataset] Test:  {len(df_test):,} entries from "
          f"{df_test['race_id'].nunique():,} races")

    # === Feature Pruning ===
    feature_cols_all = list(FEATURE_COLS_ALL)
    feature_cols_value = list(FEATURE_COLS_VALUE)
    pruned_features = []

    if args.exclude_features:
        exclude_set = set(args.exclude_features)
        before_all = len(feature_cols_all)
        before_val = len(feature_cols_value)
        feature_cols_all = [f for f in feature_cols_all if f not in exclude_set]
        feature_cols_value = [f for f in feature_cols_value if f not in exclude_set]
        pruned_features = sorted(exclude_set)
        removed_all = before_all - len(feature_cols_all)
        removed_val = before_val - len(feature_cols_value)
        print(f"\n[Exclude] Removing {len(exclude_set)} specified features")
        print(f"  Model A: {before_all} → {len(feature_cols_all)} (-{removed_all})")
        print(f"  Model B: {before_val} → {len(feature_cols_value)} (-{removed_val})")
        print(f"  Excluded: {sorted(exclude_set)}")

    if args.prune_bottom > 0:
        # 前回のexperiment結果からimportance読み込み
        prev_result_path = config.ml_dir() / "ml_experiment_v3_result.json"
        if prev_result_path.exists():
            prev_result = json.loads(prev_result_path.read_text(encoding='utf-8'))
            # Model B (value) のimportanceを基準にする（VB戦略の核）
            imp_b = prev_result.get('models', {}).get('value', {}).get('feature_importance', [])
            imp_a = prev_result.get('models', {}).get('accuracy', {}).get('feature_importance', [])
            if imp_b:
                # Model B importance下位N%を除外
                n_prune_b = max(1, len(imp_b) * args.prune_bottom // 100)
                prune_b = set(item['feature'] for item in imp_b[-n_prune_b:])
                # Model A importance下位N%も除外
                n_prune_a = max(1, len(imp_a) * args.prune_bottom // 100) if imp_a else 0
                prune_a = set(item['feature'] for item in imp_a[-n_prune_a:]) if imp_a else set()

                feature_cols_value = [f for f in feature_cols_value if f not in prune_b]
                feature_cols_all = [f for f in feature_cols_all if f not in prune_a]
                pruned_features = sorted(prune_b | prune_a)

                print(f"\n[Pruning] Removing bottom {args.prune_bottom}% features")
                print(f"  Model A: {len(FEATURE_COLS_ALL)} → {len(feature_cols_all)} "
                      f"(-{len(FEATURE_COLS_ALL) - len(feature_cols_all)} features)")
                print(f"  Model B: {len(FEATURE_COLS_VALUE)} → {len(feature_cols_value)} "
                      f"(-{len(FEATURE_COLS_VALUE) - len(feature_cols_value)} features)")
                print(f"  Pruned (B): {sorted(prune_b)}")
                if prune_a - prune_b:
                    print(f"  Pruned (A only): {sorted(prune_a - prune_b)}")
        else:
            print(f"\n[Pruning] WARNING: No previous result found at {prev_result_path}")
            print(f"  Run experiment without --prune-bottom first to generate importance data")

    # === Place モデル (is_top3) ===
    # Model A: 全特徴量
    model_a, metrics_a, importance_a, pred_a, cal_a = train_model(
        df_train, df_val, df_test, feature_cols_all, PARAMS_A, 'is_top3', 'Model_A'
    )

    # Model B: Value特徴量（市場系除外）
    model_b, metrics_b, importance_b, pred_b, cal_b = train_model(
        df_train, df_val, df_test, feature_cols_value, PARAMS_B, 'is_top3', 'Model_B'
    )

    # === Win モデル (is_win) ===
    # Model W: 全特徴量
    model_w, metrics_w, importance_w, pred_w, cal_w = train_model(
        df_train, df_val, df_test, feature_cols_all, PARAMS_W, 'is_win', 'Model_W'
    )

    # Model WV: Value特徴量（市場系除外）
    model_wv, metrics_wv, importance_wv, pred_wv, cal_wv = train_model(
        df_train, df_val, df_test, feature_cols_value, PARAMS_WV, 'is_win', 'Model_WV'
    )

    # === 回帰モデル (着差予測) ===
    from ml.features.margin_target import add_margin_target_to_df
    print("\n[Margin] Computing target_margin...")
    for label, df in [('train', df_train), ('val', df_val), ('test', df_test)]:
        add_margin_target_to_df(df, date_index, load_race_json, cap=5.0)

    model_reg_b, metrics_reg_b, importance_reg_b, pred_reg_b = train_regression_model(
        df_train, df_val, df_test, feature_cols_value, PARAMS_REG_B, 'Reg_B'
    )

    # 予測結果をDataFrameに追加
    df_test['pred_proba_a'] = pred_a
    df_test['pred_proba_v'] = pred_b
    df_test['pred_rank_a'] = df_test.groupby('race_id')['pred_proba_a'].rank(
        ascending=False, method='min'
    )
    df_test['pred_rank_v'] = df_test.groupby('race_id')['pred_proba_v'].rank(
        ascending=False, method='min'
    )
    # Win モデル
    df_test['pred_proba_w'] = pred_w
    df_test['pred_proba_wv'] = pred_wv
    df_test['pred_rank_w'] = df_test.groupby('race_id')['pred_proba_w'].rank(
        ascending=False, method='min'
    )
    df_test['pred_rank_wv'] = df_test.groupby('race_id')['pred_proba_wv'].rank(
        ascending=False, method='min'
    )
    # 回帰モデル
    df_test['pred_margin_b'] = pred_reg_b

    # EV (calibrated) — EV分析・bet_engine両方で使用
    pred_wv_cal = cal_wv.predict(pred_wv) if cal_wv is not None else pred_wv
    pred_b_cal = cal_b.predict(pred_b) if cal_b is not None else pred_b
    df_test['win_ev'] = pred_wv_cal * df_test['odds']

    # 分析
    print("\n[Analysis] Hit rate analysis...")
    hit_a = calc_hit_analysis(df_test, 'pred_proba_a')
    hit_b = calc_hit_analysis(df_test, 'pred_proba_v')

    roi_a = calc_roi_analysis(df_test, 'pred_proba_a')
    roi_b = calc_roi_analysis(df_test, 'pred_proba_v')
    roi_w = calc_roi_analysis(df_test, 'pred_proba_w')
    roi_wv = calc_roi_analysis(df_test, 'pred_proba_wv')

    print("\n[Analysis] Value Bet analysis (Place model)...")
    vb_analysis = calc_value_bet_analysis(df_test, rank_col='pred_rank_v')
    vb_picks = collect_value_bet_picks(df_test, min_gap=VALUE_BET_MIN_GAP)
    print(f"  Value Bet picks: {len(vb_picks)} entries (gap >= {VALUE_BET_MIN_GAP})")

    print("\n[Analysis] Value Bet analysis (Win model)...")
    vb_win_analysis = calc_value_bet_analysis(df_test, rank_col='pred_rank_wv')
    print(f"  Win VB analysis done")

    print("\n[Analysis] Bootstrap ROI confidence intervals...")
    vb_bootstrap_place = calc_vb_bootstrap_ci(df_test, rank_col='pred_rank_v')
    vb_bootstrap_win = calc_vb_bootstrap_ci(df_test, rank_col='pred_rank_wv')
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
        df_test['pred_proba_v_raw'] = pred_b
        df_test['vb_gap'] = (df_test['odds_rank'] - df_test['pred_rank_v']).clip(lower=0).astype(int)
        df_test['win_vb_gap'] = (df_test['odds_rank'] - df_test['pred_rank_wv']).clip(lower=0).astype(int)

        # place_ev (win_evは既に計算済み)
        place_odds_col = df_test['place_odds_low'].fillna(df_test['odds'] / 3.5)
        df_test['place_ev'] = pred_b_cal * place_odds_col

        bet_race_preds = bet_df_to_recs(df_test)

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
    print(f"\n  --- Place Models (target=is_top3) ---")
    print(f"  Model A (Accuracy): AUC={metrics_a['auc']}, Brier={metrics_a['brier_score']}, "
          f"ECE={metrics_a['ece']}, Iter={metrics_a['best_iteration']}")
    print(f"  Model B (Value):    AUC={metrics_b['auc']}, Brier={metrics_b['brier_score']}, "
          f"ECE={metrics_b['ece']}, Iter={metrics_b['best_iteration']}")

    print(f"\n  --- Win Models (target=is_win) ---")
    print(f"  Model W (Accuracy): AUC={metrics_w['auc']}, Brier={metrics_w['brier_score']}, "
          f"ECE={metrics_w['ece']}, Iter={metrics_w['best_iteration']}")
    print(f"  Model WV (Value):   AUC={metrics_wv['auc']}, Brier={metrics_wv['brier_score']}, "
          f"ECE={metrics_wv['ece']}, Iter={metrics_wv['best_iteration']}")

    print(f"\n  --- Regression Model (target=margin) ---")
    print(f"  Reg B (Value):      MAE={metrics_reg_b['mae']}, Corr={metrics_reg_b['correlation']}, "
          f"Iter={metrics_reg_b['best_iteration']}")

    print(f"\n  Hit Analysis (Model A - Place):")
    for h in hit_a:
        print(f"    Top{h['top_n']}: {h['hit_rate']:.1%} ({h['hits']}/{h['total']})")

    print(f"\n  Hit Analysis (Model B - Place Value):")
    for h in hit_b:
        print(f"    Top{h['top_n']}: {h['hit_rate']:.1%} ({h['hits']}/{h['total']})")

    print(f"\n  ROI (Model A): Win={roi_a['top1_win_roi']:.1f}%, Place={roi_a['top1_place_roi']:.1f}%")
    print(f"  ROI (Model B): Win={roi_b['top1_win_roi']:.1f}%, Place={roi_b['top1_place_roi']:.1f}%")
    print(f"  ROI (Model W): Win={roi_w['top1_win_roi']:.1f}%, Place={roi_w['top1_place_roi']:.1f}%")
    print(f"  ROI (Model WV):Win={roi_wv['top1_win_roi']:.1f}%, Place={roi_wv['top1_place_roi']:.1f}%")

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

    print(f"\n  Feature Importance (Model A Top 10):")
    sorted_imp_a = sorted(importance_a.items(), key=lambda x: x[1], reverse=True)[:10]
    for fname, imp in sorted_imp_a:
        print(f"    {fname:>25}: {imp:,.0f}")

    print(f"\n  Feature Importance (Model B Top 10):")
    sorted_imp_b = sorted(importance_b.items(), key=lambda x: x[1], reverse=True)[:10]
    for fname, imp in sorted_imp_b:
        print(f"    {fname:>25}: {imp:,.0f}")

    # H-21: 芝/ダート分離モデル実験
    track_split_results = None
    if args.split_track:
        track_split_results = run_track_split_experiment(
            df_train, df_val, df_test,
            feature_cols_all, feature_cols_value,
            PARAMS_A, PARAMS_B,
            pred_a, pred_b,
        )

    # バージョン未指定の場合はフォールバック
    if not experiment_version:
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
            files=["model_a.txt", "model_b.txt", "model_w.txt", "model_wv.txt",
                   "model_reg_b.txt",
                   "model_meta.json", "ml_experiment_v3_result.json",
                   "calibrators.pkl"],
            metadata={"created_at": old_meta.get("created_at", "")},
        )

    model_a.save_model(str(model_dir / "model_a.txt"))
    model_b.save_model(str(model_dir / "model_b.txt"))
    model_w.save_model(str(model_dir / "model_w.txt"))
    model_wv.save_model(str(model_dir / "model_wv.txt"))
    model_reg_b.save_model(str(model_dir / "model_reg_b.txt"))

    # IsotonicRegressionキャリブレーター保存
    import pickle
    calibrators = {'cal_a': cal_a, 'cal_b': cal_b, 'cal_w': cal_w, 'cal_wv': cal_wv}
    with open(model_dir / "calibrators.pkl", 'wb') as f:
        pickle.dump(calibrators, f)
    print(f"  Calibrators saved: {list(calibrators.keys())}")

    import sklearn
    meta = {
        'version': experiment_version,
        'features_all': feature_cols_all,
        'features_value': feature_cols_value,
        'market_features': list(MARKET_FEATURES),
        'targets': {'place': 'is_top3', 'win': 'is_win', 'margin': 'target_margin'},
        'odds_source': 'mykeibadb' if use_db_odds else 'json_confirmed',
        'has_calibrators': True,
        'has_regression_model': True,
        'sklearn_version': sklearn.__version__,
        'created_at': datetime.now().isoformat(timespec='seconds'),
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
            'train': f"{train_min}-{train_max}",
            'val': f"{val_min}-{val_max}",
            'test': f"{test_min}-{test_max}",
        },
        'pruning': {
            'prune_bottom_pct': args.prune_bottom,
            'pruned_features': pruned_features,
        } if pruned_features else None,
        'models': {
            'accuracy': {
                'target': 'is_top3',
                'features': feature_cols_all,
                'feature_count': len(feature_cols_all),
                'metrics': metrics_a,
                'feature_importance': [
                    {'feature': f, 'importance': int(i)}
                    for f, i in sorted(importance_a.items(), key=lambda x: -x[1])
                ],
            },
            'value': {
                'target': 'is_top3',
                'features': feature_cols_value,
                'feature_count': len(feature_cols_value),
                'metrics': metrics_b,
                'feature_importance': [
                    {'feature': f, 'importance': int(i)}
                    for f, i in sorted(importance_b.items(), key=lambda x: -x[1])
                ],
            },
            'win_accuracy': {
                'target': 'is_win',
                'features': feature_cols_all,
                'feature_count': len(feature_cols_all),
                'metrics': metrics_w,
                'feature_importance': [
                    {'feature': f, 'importance': int(i)}
                    for f, i in sorted(importance_w.items(), key=lambda x: -x[1])
                ],
            },
            'win_value': {
                'target': 'is_win',
                'features': feature_cols_value,
                'feature_count': len(feature_cols_value),
                'metrics': metrics_wv,
                'feature_importance': [
                    {'feature': f, 'importance': int(i)}
                    for f, i in sorted(importance_wv.items(), key=lambda x: -x[1])
                ],
            },
            'regression_value': {
                'target': 'target_margin',
                'features': feature_cols_value,
                'feature_count': len(feature_cols_value),
                'metrics': metrics_reg_b,
                'feature_importance': [
                    {'feature': f, 'importance': int(i)}
                    for f, i in sorted(importance_reg_b.items(), key=lambda x: -x[1])[:20]
                ],
            },
        },
        'hit_analysis': {
            'accuracy': hit_a,
            'value': hit_b,
        },
        'roi_analysis': {
            'accuracy': roi_a,
            'value': roi_b,
            'win_accuracy': roi_w,
            'win_value': roi_wv,
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
