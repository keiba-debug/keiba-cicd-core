#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
障害レース Optuna ハイパーパラメータ＋特徴量グループ最適化

experiment_obstacle.pyのデータロード・特徴量構築を再利用し、
P/Wモデルの最適化を実行。

StudyはSQLite永続化→中断再開可能。
結果は optuna/best_params_obstacle_p.json, best_params_obstacle_w.json に保存。

Usage:
    python -m ml.optuna_tuner_obstacle --model p --n-trials 60
    python -m ml.optuna_tuner_obstacle --model w --n-trials 60
    python -m ml.optuna_tuner_obstacle --all --n-trials 60
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from ml.experiment import (
    load_data, build_pit_personnel_timeline,
    TRAINER_FEATURES, JOCKEY_FEATURES,
    RUNNING_STYLE_FEATURES, SPEED_FEATURES,
    PEDIGREE_FEATURES,
    parse_period_range, _format_period,
)
from ml.experiment_obstacle import (
    OBSTACLE_BASE_FEATURES, OBSTACLE_PAST_FEATURES,
    OBSTACLE_ROTATION_FEATURES, OBSTACLE_SPECIFIC_FEATURES,
    OBSTACLE_FEATURE_COLS,
    build_obstacle_dataset,
)
from ml.features.obstacle_features import (
    build_obstacle_personnel_timelines,
)


# === 特徴量グループ定義（ON/OFF最適化対象） ===
# OBSTACLE_BASE + OBSTACLE_PAST は必須（常にON）

OBS_FEATURE_GROUPS = {
    'trainer':       TRAINER_FEATURES,
    'jockey':        JOCKEY_FEATURES,
    'running_style': RUNNING_STYLE_FEATURES,
    'rotation':      OBSTACLE_ROTATION_FEATURES,
    'speed':         SPEED_FEATURES,
    'pedigree':      PEDIGREE_FEATURES,
    # 障害固有特徴量をサブグループに分割
    'obs_core': [
        'obstacle_experience', 'obstacle_level', 'obstacle_exp_tier',
        'prev_was_obstacle', 'difficulty_exp_match',
    ],
    'obs_personnel': [
        'jockey_obstacle_races', 'jockey_obstacle_win_rate',
        'trainer_obstacle_top3_rate',
        'jockey_selected', 'jockey_selected_count',
    ],
    'obs_idm_level': [
        'flat_idm_avg3', 'prev_obstacle_level_diff',
    ],
    'obs_past_stats': [
        'obs_win_rate', 'obs_top3_rate', 'obs_avg_finish_last3',
        'obs_last3f_avg_last3', 'obs_best_finish_last5',
        'obs_days_since_last', 'obs_distance_fitness',
    ],
    'obs_profile': [
        'course_avg_l3f', 'obs_high_level_runs', 'obs_high_level_top3_rate',
        'flat_turf_ratio', 'flat_avg_distance',
        'obs_same_group_top3_rate',
    ],
}

# 必須特徴量（常にON）
MANDATORY_FEATURES = OBSTACLE_BASE_FEATURES + OBSTACLE_PAST_FEATURES


def suggest_params(trial, model_type: str) -> Tuple[dict, int]:
    """障害モデル用HP提案（データ8K件向けのコンパクトな範囲）"""
    params = {
        'num_leaves':       trial.suggest_int('num_leaves', 7, 63),
        'max_depth':        trial.suggest_int('max_depth', 3, 8),
        'learning_rate':    trial.suggest_float('learning_rate', 0.005, 0.1, log=True),
        'feature_fraction': trial.suggest_float('feature_fraction', 0.5, 1.0),
        'bagging_fraction': trial.suggest_float('bagging_fraction', 0.5, 1.0),
        'bagging_freq':     trial.suggest_int('bagging_freq', 1, 7),
        'min_child_samples': trial.suggest_int('min_child_samples', 10, 60),
        'reg_alpha':        trial.suggest_float('reg_alpha', 0.0, 3.0),
        'reg_lambda':       trial.suggest_float('reg_lambda', 0.0, 5.0),
        'verbose':          -1,
        'seed':             42,
        'bagging_seed':     42,
        'feature_fraction_seed': 42,
        'objective':        'binary',
        'metric':           'auc',
    }

    num_boost_round = trial.suggest_int('num_boost_round', 100, 1000, step=50)

    if model_type == 'w':
        params['scale_pos_weight'] = trial.suggest_float(
            'scale_pos_weight', 3.0, 15.0
        )

    return params, num_boost_round


def select_features(trial) -> List[str]:
    """特徴量グループON/OFFを提案し、特徴量リストを構築"""
    features = list(MANDATORY_FEATURES)

    for group_name, group_features in OBS_FEATURE_GROUPS.items():
        include = trial.suggest_categorical(f'use_{group_name}', [True, False])
        if include:
            for f in group_features:
                if f not in features:
                    features.append(f)

    return features


def create_objective(
    model_type: str,
    df_train: pd.DataFrame,
    df_val: pd.DataFrame,
):
    """Optuna objective関数を生成"""
    import lightgbm as lgb

    label_col = 'is_top3' if model_type == 'p' else 'is_win'

    def objective(trial):
        params, num_boost_round = suggest_params(trial, model_type)
        feature_cols = select_features(trial)
        feature_cols = [f for f in feature_cols if f in df_train.columns]

        if len(feature_cols) < 10:
            return float('-inf')

        X_train = df_train[feature_cols]
        y_train = df_train[label_col]
        X_val = df_val[feature_cols]
        y_val = df_val[label_col]

        train_data = lgb.Dataset(X_train, label=y_train)
        valid_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

        model = lgb.train(
            params, train_data, num_boost_round=num_boost_round,
            valid_sets=[valid_data],
            callbacks=[
                lgb.early_stopping(stopping_rounds=50),
                lgb.log_evaluation(period=0),
            ],
        )

        y_pred_val = model.predict(X_val)

        from sklearn.metrics import roc_auc_score
        score = roc_auc_score(y_val, y_pred_val)

        trial.set_user_attr('best_iteration', model.best_iteration)
        trial.set_user_attr('n_features', len(feature_cols))

        return score

    return objective


def run_optimization(
    model_type: str,
    df_train: pd.DataFrame,
    df_val: pd.DataFrame,
    n_trials: int = 60,
    timeout: Optional[int] = None,
) -> dict:
    """1モデルのOptuna最適化を実行"""
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    optuna_dir = config.ml_dir() / "optuna"
    optuna_dir.mkdir(parents=True, exist_ok=True)

    study_name = f"keiba_obstacle_{model_type}"
    storage = f"sqlite:///{optuna_dir / f'study_obstacle_{model_type}.db'}"

    study = optuna.create_study(
        study_name=study_name,
        storage=storage,
        direction='maximize',
        load_if_exists=True,
        pruner=optuna.pruners.MedianPruner(n_startup_trials=10),
    )

    objective = create_objective(model_type, df_train, df_val)

    completed_before = len(study.trials)
    print(f"\n[Optuna Obstacle] Model={model_type.upper()}, "
          f"trials={n_trials}, existing={completed_before}")

    study.optimize(
        objective,
        n_trials=n_trials,
        timeout=timeout,
        show_progress_bar=True,
    )

    best = study.best_trial
    print(f"\n[Optuna Obstacle] Best trial #{best.number}: "
          f"val_auc={best.value:.6f}")
    print(f"  best_iteration={best.user_attrs.get('best_iteration')}")
    print(f"  n_features={best.user_attrs.get('n_features')}")

    # ベストパラメータ抽出
    best_params = {}
    feature_group_flags = {}
    for key, val in best.params.items():
        if key.startswith('use_'):
            feature_group_flags[key] = val
        else:
            best_params[key] = val

    num_boost_round = best_params.pop('num_boost_round', 500)

    best_params['objective'] = 'binary'
    best_params['metric'] = 'auc'
    best_params['verbose'] = -1
    best_params['seed'] = 42
    best_params['bagging_seed'] = 42
    best_params['feature_fraction_seed'] = 42

    # ベスト特徴量リスト構築
    best_features = list(MANDATORY_FEATURES)
    for group_name, group_features in OBS_FEATURE_GROUPS.items():
        if feature_group_flags.get(f'use_{group_name}', True):
            for f in group_features:
                if f not in best_features:
                    best_features.append(f)

    result = {
        'model_type': f'obstacle_{model_type}',
        'best_trial': best.number,
        'best_value': round(best.value, 6),
        'total_trials': len(study.trials),
        'params': best_params,
        'num_boost_round': num_boost_round,
        'features': best_features,
        'feature_groups': feature_group_flags,
        'n_features': len(best_features),
        'best_iteration': best.user_attrs.get('best_iteration'),
        'optimized_at': datetime.now().isoformat(timespec='seconds'),
    }

    out_path = optuna_dir / f"best_params_obstacle_{model_type}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2),
                        encoding='utf-8')
    print(f"  Saved: {out_path}")

    # Top HP表示
    print(f"\n  Best Parameters (Obstacle {model_type.upper()}):")
    for key in sorted(best_params.keys()):
        if key not in ('verbose', 'seed', 'bagging_seed',
                        'feature_fraction_seed', 'objective', 'metric'):
            print(f"    {key:>25}: {best_params[key]}")
    print(f"    {'num_boost_round':>25}: {num_boost_round}")

    print(f"\n  Feature Groups:")
    for group_name in OBS_FEATURE_GROUPS:
        flag = feature_group_flags.get(f'use_{group_name}', True)
        marker = 'ON' if flag else 'OFF'
        count = len(OBS_FEATURE_GROUPS[group_name])
        print(f"    {group_name:>15}: {marker} ({count} features)")

    return result


def main():
    parser = argparse.ArgumentParser(
        description='Obstacle Race Optuna HP + Feature Group Tuner'
    )
    parser.add_argument('--model', choices=['p', 'w'],
                        help='最適化対象モデル (p=Place, w=Win)')
    parser.add_argument('--all', action='store_true',
                        help='P/W両方を順次最適化')
    parser.add_argument('--n-trials', type=int, default=60,
                        help='試行回数 (default: 60)')
    parser.add_argument('--timeout', type=int, default=None,
                        help='タイムアウト秒 (default: None)')
    parser.add_argument('--train-years', default='2019-2024',
                        help='学習期間 (default: 2019-2024)')
    parser.add_argument('--val-years', default='2025.01-2025.06',
                        help='検証期間 (default: 2025.01-2025.06)')
    parser.add_argument('--no-db', action='store_true',
                        help='DBオッズ未使用')
    args = parser.parse_args()

    if not args.model and not args.all:
        parser.error('--model or --all is required')

    models_to_tune = ['p', 'w'] if args.all else [args.model]

    print(f"\n{'='*60}")
    print(f"  KeibaCICD - Obstacle Optuna HP + Feature Tuner")
    print(f"  Models: {', '.join(m.upper() for m in models_to_tune)}")
    print(f"  Trials: {args.n_trials}")
    print(f"  Train:  {args.train_years}")
    print(f"  Val:    {args.val_years}")
    print(f"  Feature groups: {len(OBS_FEATURE_GROUPS)} "
          f"(mandatory={len(MANDATORY_FEATURES)})")
    print(f"{'='*60}\n")

    t0 = time.time()

    # データロード
    (history_cache, trainer_index, jockey_index,
     date_index, pace_index, kb_ext_index, training_summary_index,
     race_level_index, pedigree_index, sire_stats_index,
     jrdb_sed_index, *_extra) = load_data()

    pit_trainer_tl, pit_jockey_tl = build_pit_personnel_timeline(
        years=list(range(2019, 2027))
    )

    print("[Build] Building obstacle personnel timelines...")
    jockey_obstacle_tl, trainer_obstacle_tl = build_obstacle_personnel_timelines(
        history_cache
    )
    print(f"  Jockeys: {len(jockey_obstacle_tl):,}, "
          f"Trainers: {len(trainer_obstacle_tl):,}")

    use_db_odds = not args.no_db

    train_min, train_min_m, train_max, train_max_m = parse_period_range(
        args.train_years
    )
    val_min, val_min_m, val_max, val_max_m = parse_period_range(
        args.val_years
    )

    build_kwargs = dict(
        date_index=date_index, history_cache=history_cache,
        trainer_index=trainer_index, jockey_index=jockey_index,
        pace_index=pace_index, kb_ext_index=kb_ext_index,
        use_db_odds=use_db_odds,
        race_level_index=race_level_index,
        pedigree_index=pedigree_index,
        sire_stats_index=sire_stats_index,
        pit_trainer_tl=pit_trainer_tl, pit_jockey_tl=pit_jockey_tl,
        jockey_obstacle_tl=jockey_obstacle_tl,
        trainer_obstacle_tl=trainer_obstacle_tl,
        jrdb_sed_index=jrdb_sed_index,
    )

    df_train = build_obstacle_dataset(
        **build_kwargs,
        min_year=train_min, max_year=train_max,
        min_month=train_min_m, max_month=train_max_m,
    )
    df_val = build_obstacle_dataset(
        **build_kwargs,
        min_year=val_min, max_year=val_max,
        min_month=val_min_m, max_month=val_max_m,
    )

    # is_win確認
    if 'is_win' not in df_train.columns:
        for df in [df_train, df_val]:
            df['is_win'] = (df['finish_position'] == 1).astype(int)

    print(f"\n[Data] train={len(df_train):,}, val={len(df_val):,}")

    # 最適化実行
    results = {}
    for model_type in models_to_tune:
        result = run_optimization(
            model_type, df_train, df_val,
            n_trials=args.n_trials,
            timeout=args.timeout,
        )
        results[model_type] = result

    elapsed = time.time() - t0
    print(f"\n[Done] Total elapsed: {elapsed:.0f}s ({elapsed/60:.1f}min)")


if __name__ == '__main__':
    main()
