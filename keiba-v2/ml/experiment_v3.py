#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ML Experiment v3.5: スピード指数特徴量追加

v3.5改善:
  - keibabookスピード指数特徴量 (5個): 過去5走のスピード指数から最新/最高/平均/トレンド/安定性

v3.4改善:
  - mykeibadb時系列オッズ連携: 確定オッズ→事前オッズに置換（データリーク解消）
  - Model Aの市場系特徴量がレース前に取得可能な「正当な」事前情報に
  - DB未接続/データなし時はJSON確定オッズにフォールバック

v3.3改善:
  - 詳細調教特徴量 (9個): 追い切りタイム・脚色・併せ馬・セッション数・休養週数・坂路

v3.2改善:
  - 調教特徴量 (1個): keibabook training_arrow_value (-2〜+2)

v3.1改善:
  - 脚質特徴量 (8個): コーナー通過順からの先行力・末脚力
  - ローテ特徴量 (5個): 斤量差・馬体重変化・前走人気
  - ペース特徴量 (6個): RPCI・消耗フラグ・急坂適性
  - ハイパーパラメータ: Model A/B別に最適化

v3.0:
  - trainer_top3_rate: 100%マッチ
  - jockey特徴量
  - 過去走カバレッジ: 36,008頭

特徴量構成:
  Model A (全特徴量): 基本 + 過去走 + trainer + jockey + 脚質 + ローテ + ペース + 調教 + スピード指数 + 市場系
  Model B (Value):     Model Aから市場系特徴量を除外

Usage:
    python -m ml.experiment_v3 [--train-years 2020-2024] [--test-years 2025-2026]
    python -m ml.experiment_v3 --no-db  # DB未使用（旧JSON確定オッズ）
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

# === 特徴量定義 ===

# JRA-VAN基本特徴量
BASE_FEATURES = [
    'age', 'sex', 'futan', 'horse_weight', 'horse_weight_diff',
    'wakuban', 'distance', 'track_type', 'track_condition', 'entry_count',
]

# 過去走特徴量
PAST_FEATURES = [
    'avg_finish_last3', 'best_finish_last5', 'last3f_avg_last3',
    'days_since_last_race', 'win_rate_all', 'top3_rate_all',
    'total_career_races', 'recent_form_trend',
    'venue_top3_rate', 'track_type_top3_rate', 'distance_fitness',
    'prev_race_entry_count', 'entry_count_change',
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
]

# ペース特徴量 (v3.1)
PACE_FEATURES = [
    'avg_race_rpci_last3', 'prev_race_rpci', 'consumption_flag',
    'last3f_vs_race_l3_last3', 'steep_course_experience', 'steep_course_top3_rate',
]

# 調教特徴量 (v3.3)
TRAINING_FEATURES = [
    'training_arrow_value',
    'oikiri_5f', 'oikiri_3f', 'oikiri_1f',
    'oikiri_intensity_code', 'oikiri_has_awase',
    'training_session_count', 'rest_weeks', 'oikiri_is_slope',
]

# スピード指数特徴量 (v3.5)
SPEED_FEATURES = [
    'speed_idx_latest', 'speed_idx_best5', 'speed_idx_avg3',
    'speed_idx_trend', 'speed_idx_std',
]

# 市場系特徴量（Model Bでは除外）
MARKET_FEATURES = {'odds', 'popularity', 'odds_rank', 'popularity_trend'}

# 派生特徴量
DERIVED_FEATURES = ['odds_rank']

# 全特徴量（Model A）
FEATURE_COLS_ALL = (
    BASE_FEATURES + ['odds', 'popularity'] + DERIVED_FEATURES +
    PAST_FEATURES + TRAINER_FEATURES + JOCKEY_FEATURES +
    RUNNING_STYLE_FEATURES + ROTATION_FEATURES + ['popularity_trend'] +
    PACE_FEATURES + TRAINING_FEATURES + SPEED_FEATURES
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
                }
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


def load_data() -> Tuple[dict, dict, dict, dict, dict, dict]:
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

    return history_cache, trainer_index, jockey_index, date_index, pace_index, kb_ext_index


def compute_features_for_race(
    race: dict,
    history_cache: dict,
    trainer_index: dict,
    jockey_index: dict,
    pace_index: dict,
    kb_ext_index: dict,
    db_odds: dict = None,
) -> List[dict]:
    """1レースの全出走馬の特徴量を計算

    Args:
        db_odds: mykeibadbから取得した事前オッズ {umaban: {'odds': float, 'ninki': int}}
                 Noneの場合はJSON確定オッズを使用（従来動作）
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

    race_date = race['date']
    race_id = race['race_id']
    venue_code = race['venue_code']
    track_type = race.get('track_type', '')
    distance = race.get('distance', 0)
    entry_count = race.get('num_runners', 0)

    # kb_ext（調教データ等）
    kb_ext = kb_ext_index.get(race_id)

    rows = []
    for entry in race.get('entries', []):
        fp = entry.get('finish_position', 0)
        if fp <= 0:
            continue

        ketto_num = entry['ketto_num']

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

        # ローテ・コンディション特徴量 (v3.1)
        rot_feat = compute_rotation_features(
            ketto_num=ketto_num,
            race_date=race_date,
            futan=entry.get('futan', 0.0),
            horse_weight=entry.get('horse_weight', 0),
            popularity=entry.get('popularity', 0),
            history_cache=history_cache,
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

        # 調教特徴量 (v3.3)
        train_feat = compute_training_features(
            umaban=str(entry.get('umaban', '')),
            kb_ext=kb_ext,
        )
        feat.update(train_feat)

        # スピード指数特徴量 (v3.5)
        speed_feat = compute_speed_features(
            umaban=str(entry.get('umaban', '')),
            kb_ext=kb_ext,
        )
        feat.update(speed_feat)

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
) -> pd.DataFrame:
    """全レースの特徴量を構築してDataFrameで返す

    Args:
        use_db_odds: True=mykeibadbから事前オッズ取得, False=JSON確定オッズ（従来動作）
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
    if use_db_odds:
        try:
            from core.odds_db import batch_get_pre_race_odds, is_db_available
            if is_db_available():
                race_codes = [rid for _, rid in target_races]
                db_odds_index = batch_get_pre_race_odds(race_codes)
                ts_count = sum(1 for v in db_odds_index.values()
                               if v and any(e.get('source') == 'timeseries' for e in v.values()))
                final_count = sum(1 for v in db_odds_index.values()
                                  if v and any(e.get('source') == 'final' for e in v.values()))
                print(f"[DB Odds] {len(db_odds_index):,} races loaded "
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

    # odds_rank（レース内オッズ順位）を追加
    if 'odds' in df.columns:
        df['odds_rank'] = df.groupby('race_id')['odds'].rank(method='min')

    print(f"[Build] {race_count:,} races, {len(df):,} entries, {error_count} errors")
    return df


def train_model(
    df_train: pd.DataFrame,
    df_test: pd.DataFrame,
    feature_cols: List[str],
    params: dict,
    label_col: str = 'is_top3',
    model_name: str = 'model',
) -> Tuple:
    """LightGBMモデルを学習"""
    import lightgbm as lgb

    X_train = df_train[feature_cols].fillna(-1)
    y_train = df_train[label_col]
    X_test = df_test[feature_cols].fillna(-1)
    y_test = df_test[label_col]

    train_data = lgb.Dataset(X_train, label=y_train)
    valid_data = lgb.Dataset(X_test, label=y_test, reference=train_data)

    print(f"\n[Train] {model_name}: {len(feature_cols)} features, "
          f"train={len(X_train):,}, test={len(X_test):,}")

    model = lgb.train(
        params, train_data, num_boost_round=1500,
        valid_sets=[valid_data],
        callbacks=[
            lgb.early_stopping(stopping_rounds=50),
            lgb.log_evaluation(period=200),
        ],
    )

    # 評価
    from sklearn.metrics import roc_auc_score, accuracy_score, log_loss

    y_pred = model.predict(X_test)
    auc = roc_auc_score(y_test, y_pred)
    acc = accuracy_score(y_test, (y_pred > 0.5).astype(int))
    ll = log_loss(y_test, y_pred)

    print(f"[{model_name}] AUC={auc:.4f}, Acc={acc:.4f}, LogLoss={ll:.4f}, "
          f"BestIter={model.best_iteration}")

    # 特徴量重要度
    importance = dict(zip(feature_cols, model.feature_importance(importance_type='gain')))

    metrics = {
        'auc': round(auc, 4),
        'accuracy': round(acc, 4),
        'log_loss': round(ll, 4),
        'best_iteration': model.best_iteration,
        'train_size': len(X_train),
        'test_size': len(X_test),
    }

    return model, metrics, importance, y_pred


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


def calc_roi_analysis(df: pd.DataFrame, pred_col: str) -> dict:
    """ROI分析（Top1）"""
    df['pred_rank'] = df.groupby('race_id')[pred_col].rank(ascending=False, method='min')
    top1 = df[df['pred_rank'] == 1].copy()

    # 単勝ROI
    total_bets = len(top1) * 100
    win_return = top1[top1['is_win'] == 1]['odds'].sum() * 100
    win_roi = win_return / total_bets * 100 if total_bets > 0 else 0

    # 複勝ROI（簡易推定: odds/3.5, 最低1.1倍）
    place_hits = top1[top1['is_top3'] == 1]
    place_return = place_hits['odds'].apply(lambda o: max(o / 3.5, 1.1)).sum() * 100
    place_roi = place_return / total_bets * 100 if total_bets > 0 else 0

    return {
        'top1_win_roi': round(win_roi, 1),
        'top1_place_roi': round(place_roi, 1),
        'top1_bets': len(top1),
    }


def calc_value_bet_analysis(df: pd.DataFrame) -> List[dict]:
    """Value Bet分析: Model AとModel Bの順位乖離を利用"""
    if 'pred_rank_a' not in df.columns or 'pred_rank_v' not in df.columns:
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
            # Value Bet候補: Model Bで上位3位以内 かつ odds_rankとの乖離がmin_gap以上
            candidates = group[
                (group['pred_rank_v'] <= 3) &
                (group['odds_rank'] >= group['pred_rank_v'] + min_gap)
            ]

            for _, row in candidates.iterrows():
                bet = 100
                total_bets += bet
                total_count += 1

                if row['is_win'] == 1:
                    win_return += row['odds'] * bet
                    win_hits += 1

                if row['is_top3'] == 1:
                    place_odds = max(row['odds'] / 3.5, 1.1)
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
                'actual_position': int(row['finish_position']),
                'is_top3': int(row['is_top3']),
            })

    picks.sort(key=lambda x: (-x['gap'], x['date']))
    return picks


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


def parse_year_range(s: str) -> Tuple[int, int]:
    if '-' in s:
        parts = s.split('-', 1)
        return int(parts[0]), int(parts[1])
    y = int(s)
    return y, y


def main():
    parser = argparse.ArgumentParser(description='ML Experiment v3')
    parser.add_argument('--train-years', default='2020-2024', help='Training year range')
    parser.add_argument('--test-years', default='2025-2026', help='Test year range')
    parser.add_argument('--no-db', action='store_true', help='DBオッズ未使用（JSON確定オッズ）')
    args = parser.parse_args()

    train_min, train_max = parse_year_range(args.train_years)
    test_min, test_max = parse_year_range(args.test_years)
    use_db_odds = not args.no_db

    print(f"\n{'='*60}")
    print(f"  KeibaCICD v4 - ML Experiment v3.4")
    print(f"  Train: {train_min}-{train_max}")
    print(f"  Test:  {test_min}-{test_max}")
    print(f"  DB Odds: {'ON' if use_db_odds else 'OFF (JSON fallback)'}")
    print(f"  Model A features: {len(FEATURE_COLS_ALL)}")
    print(f"  Model B features: {len(FEATURE_COLS_VALUE)}")
    print(f"{'='*60}\n")

    t0 = time.time()

    # データロード
    history_cache, trainer_index, jockey_index, date_index, pace_index, kb_ext_index = load_data()

    # データセット構築
    df_train = build_dataset(
        date_index, history_cache, trainer_index, jockey_index, pace_index,
        kb_ext_index, train_min, train_max, use_db_odds=use_db_odds,
    )
    df_test = build_dataset(
        date_index, history_cache, trainer_index, jockey_index, pace_index,
        kb_ext_index, test_min, test_max, use_db_odds=use_db_odds,
    )

    print(f"\n[Dataset] Train: {len(df_train):,} entries from "
          f"{df_train['race_id'].nunique():,} races")
    print(f"[Dataset] Test:  {len(df_test):,} entries from "
          f"{df_test['race_id'].nunique():,} races")

    # Model A: 全特徴量
    model_a, metrics_a, importance_a, pred_a = train_model(
        df_train, df_test, FEATURE_COLS_ALL, PARAMS_A, 'is_top3', 'Model_A'
    )

    # Model B: Value特徴量（市場系除外）
    model_b, metrics_b, importance_b, pred_b = train_model(
        df_train, df_test, FEATURE_COLS_VALUE, PARAMS_B, 'is_top3', 'Model_B'
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

    # 分析
    print("\n[Analysis] Hit rate analysis...")
    hit_a = calc_hit_analysis(df_test, 'pred_proba_a')
    hit_b = calc_hit_analysis(df_test, 'pred_proba_v')

    roi_a = calc_roi_analysis(df_test, 'pred_proba_a')
    roi_b = calc_roi_analysis(df_test, 'pred_proba_v')

    print("\n[Analysis] Value Bet analysis...")
    vb_analysis = calc_value_bet_analysis(df_test)
    vb_picks = collect_value_bet_picks(df_test, min_gap=2)
    print(f"  Value Bet picks: {len(vb_picks)} entries (gap >= 2)")

    print("\n[Analysis] Collecting race predictions...")
    race_preds = collect_race_predictions(df_test)
    print(f"  Race predictions: {len(race_preds)} races")

    # 結果表示
    print(f"\n{'='*60}")
    print(f"  Results")
    print(f"{'='*60}")
    print(f"\n  Model A (Accuracy): AUC={metrics_a['auc']}, Iter={metrics_a['best_iteration']}")
    print(f"  Model B (Value):    AUC={metrics_b['auc']}, Iter={metrics_b['best_iteration']}")

    print(f"\n  Hit Analysis (Model A):")
    for h in hit_a:
        print(f"    Top{h['top_n']}: {h['hit_rate']:.1%} ({h['hits']}/{h['total']})")

    print(f"\n  Hit Analysis (Model B):")
    for h in hit_b:
        print(f"    Top{h['top_n']}: {h['hit_rate']:.1%} ({h['hits']}/{h['total']})")

    print(f"\n  ROI (Model A): Win={roi_a['top1_win_roi']:.1f}%, Place={roi_a['top1_place_roi']:.1f}%")
    print(f"  ROI (Model B): Win={roi_b['top1_win_roi']:.1f}%, Place={roi_b['top1_place_roi']:.1f}%")

    print(f"\n  Value Bet Analysis:")
    for vb in vb_analysis:
        marker = " ***" if vb['place_roi'] >= 100 else ""
        print(f"    gap>={vb['min_gap']}: {vb['bet_count']:,} bets, "
              f"hit={vb['place_hit_rate']:.1%}, ROI={vb['place_roi']:.1f}%{marker}")

    print(f"\n  Feature Importance (Model A Top 10):")
    sorted_imp_a = sorted(importance_a.items(), key=lambda x: x[1], reverse=True)[:10]
    for fname, imp in sorted_imp_a:
        print(f"    {fname:>25}: {imp:,.0f}")

    print(f"\n  Feature Importance (Model B Top 10):")
    sorted_imp_b = sorted(importance_b.items(), key=lambda x: x[1], reverse=True)[:10]
    for fname, imp in sorted_imp_b:
        print(f"    {fname:>25}: {imp:,.0f}")

    # モデル保存
    model_dir = config.ml_dir()
    config.ensure_dir(model_dir)

    model_a.save_model(str(model_dir / "model_a.txt"))
    model_b.save_model(str(model_dir / "model_b.txt"))

    meta = {
        'version': '3.4',
        'features_all': FEATURE_COLS_ALL,
        'features_value': FEATURE_COLS_VALUE,
        'market_features': list(MARKET_FEATURES),
        'odds_source': 'mykeibadb' if use_db_odds else 'json_confirmed',
        'created_at': datetime.now().isoformat(timespec='seconds'),
    }
    (model_dir / "model_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8'
    )

    # 結果JSON保存
    result = {
        'version': '3.4',
        'experiment': 'ml_experiment_v3',
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'split': {
            'train': f"{train_min}-{train_max}",
            'test': f"{test_min}-{test_max}",
        },
        'models': {
            'accuracy': {
                'features': FEATURE_COLS_ALL,
                'feature_count': len(FEATURE_COLS_ALL),
                'metrics': metrics_a,
                'feature_importance': [
                    {'feature': f, 'importance': int(i)}
                    for f, i in sorted(importance_a.items(), key=lambda x: -x[1])
                ],
            },
            'value': {
                'features': FEATURE_COLS_VALUE,
                'feature_count': len(FEATURE_COLS_VALUE),
                'metrics': metrics_b,
                'feature_importance': [
                    {'feature': f, 'importance': int(i)}
                    for f, i in sorted(importance_b.items(), key=lambda x: -x[1])
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
        },
        'value_bets': {
            'by_rank_gap': vb_analysis,
        },
        'value_bet_picks': vb_picks,
        'race_predictions': race_preds,
    }

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
