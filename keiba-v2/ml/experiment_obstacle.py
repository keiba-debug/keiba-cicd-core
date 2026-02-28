#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
障害レース専用ML実験パイプライン

平地モデル(experiment.py)のインフラを再利用し、障害レースのみで学習。
- モデル1本: LightGBM binary (is_top3予測)
- 少データ対策: num_leaves=31, min_child_samples=50, max_depth=5
- 時系列分割: Train=2019-2024, Val=2025.01-06, Test=2025.07-2026

Usage:
    python -m ml.experiment_obstacle
    python -m ml.experiment_obstacle --train-years 2019-2024 --val-years 2025.01-2025.06 --test-years 2025.07-2026.02
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
from ml.experiment import (
    load_data, load_race_json, compute_features_for_race,
    build_pit_personnel_timeline, train_model,
    calc_hit_analysis_v2, calc_roi_analysis,
    parse_period_range,
    # 特徴量定義
    BASE_FEATURES, PAST_FEATURES, TRAINER_FEATURES, JOCKEY_FEATURES,
    RUNNING_STYLE_FEATURES, ROTATION_FEATURES, SPEED_FEATURES,
    PEDIGREE_FEATURES,
    # ユーティリティ
    _iter_date_index, _format_period,
)
from core.jravan import race_id as rid

# === 障害レース用特徴量 ===
# 平地から流用可能な特徴量のみ（ペース系・調教系・コメント系はスキップ）

OBSTACLE_BASE_FEATURES = [
    'age', 'sex', 'futan', 'horse_weight', 'horse_weight_diff',
    'wakuban', 'distance', 'track_condition', 'entry_count',
    'month', 'nichi',
]

OBSTACLE_PAST_FEATURES = [
    'avg_finish_last3', 'best_finish_last5', 'last3f_avg_last3',
    'days_since_last_race', 'win_rate_all', 'top3_rate_all',
    'total_career_races', 'recent_form_trend',
    'venue_top3_rate', 'distance_fitness',
    'prev_race_entry_count', 'entry_count_change',
    'best_l3f_last5', 'finish_std_last5', 'comeback_strength_last5',
    'career_stage',
]

OBSTACLE_ROTATION_FEATURES = [
    'futan_diff', 'futan_diff_ratio', 'weight_change_ratio',
    'prev_race_popularity',
    'jockey_change',
]

# odds/popularity は市場系だが障害では精度向上に重要（モデル1本なのでA/B分離しない）
OBSTACLE_MARKET_FEATURES = ['odds', 'popularity']

OBSTACLE_FEATURE_COLS = (
    OBSTACLE_BASE_FEATURES + OBSTACLE_MARKET_FEATURES +
    OBSTACLE_PAST_FEATURES + TRAINER_FEATURES + JOCKEY_FEATURES +
    RUNNING_STYLE_FEATURES + OBSTACLE_ROTATION_FEATURES +
    SPEED_FEATURES + PEDIGREE_FEATURES
)

# ハイパーパラメータ（少データ用: 過学習抑制重視）
PARAMS_OBSTACLE = {
    'objective': 'binary',
    'metric': 'auc',
    'num_leaves': 31,
    'learning_rate': 0.03,
    'feature_fraction': 0.7,
    'bagging_fraction': 0.7,
    'bagging_freq': 5,
    'min_child_samples': 50,
    'reg_alpha': 0.5,
    'reg_lambda': 2.0,
    'max_depth': 5,
    'verbose': -1,
    'seed': 42,
    'bagging_seed': 42,
    'feature_fraction_seed': 42,
}


def build_obstacle_dataset(
    date_index: dict,
    history_cache: dict,
    trainer_index: dict,
    jockey_index: dict,
    pace_index: dict,
    kb_ext_index: dict,
    min_year: int,
    max_year: int,
    use_db_odds: bool = True,
    race_level_index: dict = None,
    pedigree_index: dict = None,
    sire_stats_index: dict = None,
    min_month: int = None,
    max_month: int = None,
    pit_trainer_tl: dict = None,
    pit_jockey_tl: dict = None,
) -> pd.DataFrame:
    """障害レースのみの特徴量DataFrameを構築"""
    date_min = min_year * 100 + (min_month or 1)
    date_max = max_year * 100 + (max_month or 12)
    label_min = f"{min_year}-{min_month:02d}" if min_month else str(min_year)
    label_max = f"{max_year}-{max_month:02d}" if max_month else str(max_year)
    print(f"\n[Build] Building obstacle dataset for {label_min} ~ {label_max}...")

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
                print(f"[DB Odds] {len(db_odds_index):,} races with odds data")
            else:
                print("[DB Odds] mykeibadb not available, using JSON odds")
        except Exception as e:
            print(f"[DB Odds] Error: {e}, using JSON odds")

    all_rows = []
    race_count = 0
    flat_count = 0
    error_count = 0

    for date_str, race_id in target_races:
        try:
            race = load_race_json(race_id, date_str)
            # 障害レースのみ通す
            if race.get('track_type') != 'obstacle' and '障害' not in race.get('race_name', ''):
                flat_count += 1
                continue

            rows = compute_features_for_race(
                race, history_cache, trainer_index, jockey_index,
                pace_index, kb_ext_index,
                db_odds=db_odds_index.get(race_id),
                db_place_odds=db_place_odds_index.get(race_id),
                race_level_index=race_level_index,
                pedigree_index=pedigree_index,
                sire_stats_index=sire_stats_index,
                pit_trainer_tl=pit_trainer_tl,
                pit_jockey_tl=pit_jockey_tl,
            )
            all_rows.extend(rows)
            race_count += 1
        except Exception as e:
            error_count += 1
            if error_count <= 5:
                print(f"  ERROR: {race_id}: {e}")

    df = pd.DataFrame(all_rows)

    # object型をfloat64に変換
    for col in df.columns:
        if col in set(OBSTACLE_FEATURE_COLS) and df[col].dtype == object:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # odds_rank追加
    if 'odds' in df.columns and len(df) > 0:
        df['odds_rank'] = df.groupby('race_id')['odds'].rank(method='min')

    print(f"[Build] {race_count:,} obstacle races, {len(df):,} entries, "
          f"{error_count} errors, {flat_count:,} flat races skipped")
    return df


def main():
    parser = argparse.ArgumentParser(description='Obstacle Race ML Experiment')
    parser.add_argument('--train-years', default='2019-2024',
                        help='Training period (例: 2019-2024)')
    parser.add_argument('--val-years', default='2025.01-2025.06',
                        help='Validation period (例: 2025.01-2025.06)')
    parser.add_argument('--test-years', default='2025.07-2026.02',
                        help='Test period (例: 2025.07-2026.02)')
    parser.add_argument('--no-db', action='store_true', help='DBオッズ未使用')
    args = parser.parse_args()

    train_min, train_min_m, train_max, train_max_m = parse_period_range(args.train_years)
    val_min, val_min_m, val_max, val_max_m = parse_period_range(args.val_years)
    test_min, test_min_m, test_max, test_max_m = parse_period_range(args.test_years)
    use_db_odds = not args.no_db

    train_label = f"{_format_period(train_min, train_min_m)} ~ {_format_period(train_max, train_max_m)}"
    val_label = f"{_format_period(val_min, val_min_m)} ~ {_format_period(val_max, val_max_m)}"
    test_label = f"{_format_period(test_min, test_min_m)} ~ {_format_period(test_max, test_max_m)}"

    print(f"\n{'='*60}")
    print(f"  KeibaCICD - Obstacle Race ML Experiment")
    print(f"  Train: {train_label}")
    print(f"  Val:   {val_label} (early stopping)")
    print(f"  Test:  {test_label} (pure evaluation)")
    print(f"  DB Odds: {'ON' if use_db_odds else 'OFF'}")
    print(f"  Features: {len(OBSTACLE_FEATURE_COLS)}")
    print(f"  Params: leaves={PARAMS_OBSTACLE['num_leaves']}, "
          f"depth={PARAMS_OBSTACLE['max_depth']}, "
          f"min_child={PARAMS_OBSTACLE['min_child_samples']}")
    print(f"{'='*60}\n")

    t0 = time.time()

    # データロード（平地と共有）
    (history_cache, trainer_index, jockey_index,
     date_index, pace_index, kb_ext_index, training_summary_index,
     race_level_index, pedigree_index, sire_stats_index) = load_data()

    # PIT timeline
    pit_trainer_tl, pit_jockey_tl = build_pit_personnel_timeline(
        years=list(range(2019, 2027))
    )

    # データセット構築
    df_train = build_obstacle_dataset(
        date_index, history_cache, trainer_index, jockey_index,
        pace_index, kb_ext_index, train_min, train_max,
        use_db_odds=use_db_odds,
        race_level_index=race_level_index,
        pedigree_index=pedigree_index,
        sire_stats_index=sire_stats_index,
        min_month=train_min_m, max_month=train_max_m,
        pit_trainer_tl=pit_trainer_tl, pit_jockey_tl=pit_jockey_tl,
    )
    df_val = build_obstacle_dataset(
        date_index, history_cache, trainer_index, jockey_index,
        pace_index, kb_ext_index, val_min, val_max,
        use_db_odds=use_db_odds,
        race_level_index=race_level_index,
        pedigree_index=pedigree_index,
        sire_stats_index=sire_stats_index,
        min_month=val_min_m, max_month=val_max_m,
        pit_trainer_tl=pit_trainer_tl, pit_jockey_tl=pit_jockey_tl,
    )
    df_test = build_obstacle_dataset(
        date_index, history_cache, trainer_index, jockey_index,
        pace_index, kb_ext_index, test_min, test_max,
        use_db_odds=use_db_odds,
        race_level_index=race_level_index,
        pedigree_index=pedigree_index,
        sire_stats_index=sire_stats_index,
        min_month=test_min_m, max_month=test_max_m,
        pit_trainer_tl=pit_trainer_tl, pit_jockey_tl=pit_jockey_tl,
    )

    for label, df in [('Train', df_train), ('Val', df_val), ('Test', df_test)]:
        if len(df) > 0 and 'race_id' in df.columns:
            print(f"[Dataset] {label}: {len(df):,} entries from "
                  f"{df['race_id'].nunique():,} races")
        else:
            print(f"[Dataset] {label}: EMPTY")

    if len(df_train) == 0 or len(df_val) == 0 or len(df_test) == 0:
        print("\nERROR: Empty dataset. Check if obstacle race JSONs exist "
              "and race_date_index.json is rebuilt (python -m builders.build_race_index).")
        sys.exit(1)

    # 使用可能な特徴量を確認（データにない列はスキップ）
    available_features = [f for f in OBSTACLE_FEATURE_COLS if f in df_train.columns]
    missing = set(OBSTACLE_FEATURE_COLS) - set(available_features)
    if missing:
        print(f"\n[Warning] {len(missing)} features not in data: {sorted(missing)[:10]}...")
    print(f"[Features] Using {len(available_features)} of {len(OBSTACLE_FEATURE_COLS)} defined features")

    # === モデル学習 ===
    model, metrics, importance, pred_cal, calibrator, pred_raw = train_model(
        df_train, df_val, df_test, available_features,
        PARAMS_OBSTACLE, 'is_top3', 'Obstacle_Top3'
    )

    # 予測結果をDataFrameに追加
    df_test = df_test.copy()
    df_test['pred_proba'] = pred_cal
    df_test['pred_proba_raw'] = pred_raw
    df_test['pred_rank'] = df_test.groupby('race_id')['pred_proba'].rank(
        ascending=False, method='min'
    )

    # === 分析 ===
    print(f"\n{'='*60}")
    print(f"  Analysis")
    print(f"{'='*60}")

    # Top-N的中率
    hit_analysis = calc_hit_analysis_v2(df_test, 'pred_proba')
    print(f"\n[Hit] Top1 Win: {hit_analysis['top1_win_rate']:.1%} "
          f"({hit_analysis['top1_wins']}/{hit_analysis['top1_total']})")
    print(f"[Hit] Top1 Place: {hit_analysis['top1_place_rate']:.1%} "
          f"({hit_analysis['top1_places']}/{hit_analysis['top1_total']})")

    # ROI分析
    roi = calc_roi_analysis(df_test, 'pred_proba')
    print(f"\n[ROI] Top1 Win ROI:   {roi['top1_win_roi']:.1f}%")
    print(f"[ROI] Top1 Place ROI: {roi['top1_place_roi']:.1f}%")

    # 特徴量重要度 Top15
    sorted_imp = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    print(f"\n[Importance] Top 15:")
    for i, (feat, imp) in enumerate(sorted_imp[:15], 1):
        print(f"  {i:2d}. {feat:<35s} {imp:>8.0f}")

    # 人気別的中率
    print(f"\n[Popularity Analysis]")
    for pop_range, label in [((1, 3), "1-3番人気"), ((4, 6), "4-6番人気"), ((7, 99), "7番人気以下")]:
        subset = df_test[(df_test['popularity'] >= pop_range[0]) &
                         (df_test['popularity'] <= pop_range[1])]
        if len(subset) > 0:
            top3_rate = subset['is_top3'].mean()
            pred_top3 = subset[subset['pred_rank'] <= 3]
            pred_hit = pred_top3['is_top3'].mean() if len(pred_top3) > 0 else 0
            print(f"  {label}: 実績好走率={top3_rate:.1%}, "
                  f"モデルTop3選出→好走率={pred_hit:.1%} (n={len(pred_top3)})")

    # === モデル保存 ===
    ml_dir = config.ml_dir()
    model_path = ml_dir / "model_obstacle.txt"
    model.save_model(str(model_path))
    print(f"\n[Save] Model saved to {model_path}")

    # キャリブレーター保存
    import pickle
    cal_path = ml_dir / "calibrator_obstacle.pkl"
    with open(cal_path, 'wb') as f:
        pickle.dump(calibrator, f)
    print(f"[Save] Calibrator saved to {cal_path}")

    # メタデータ保存
    meta = {
        'version': 'obstacle-v1.0',
        'model_type': 'obstacle_top3',
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'train_period': f"{_format_period(train_min, train_min_m)} ~ {_format_period(train_max, train_max_m)}",
        'val_period': f"{_format_period(val_min, val_min_m)} ~ {_format_period(val_max, val_max_m)}",
        'test_period': f"{_format_period(test_min, test_min_m)} ~ {_format_period(test_max, test_max_m)}",
        'features': available_features,
        'feature_count': len(available_features),
        'params': PARAMS_OBSTACLE,
        'metrics': metrics,
        'train_races': int(df_train['race_id'].nunique()),
        'train_entries': len(df_train),
        'val_races': int(df_val['race_id'].nunique()),
        'val_entries': len(df_val),
        'test_races': int(df_test['race_id'].nunique()),
        'test_entries': len(df_test),
        'feature_importance': [
            {'feature': f, 'importance': float(imp)}
            for f, imp in sorted_imp
        ],
        'hit_analysis': hit_analysis,
        'roi_analysis': roi,
    }

    meta_path = ml_dir / "model_obstacle_meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"[Save] Meta saved to {meta_path}")

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  Obstacle Experiment Complete")
    print(f"  AUC: {metrics['auc']:.4f}")
    print(f"  Top1 Win Rate: {hit_analysis['top1_win_rate']:.1%}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
