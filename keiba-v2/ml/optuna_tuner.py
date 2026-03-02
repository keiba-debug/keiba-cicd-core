#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Optuna ハイパーパラメータ＋特徴量グループ最適化

experiment.pyのデータロード・特徴量構築を再利用し、
P/W/ARモデルのLightGBMハイパラ＋特徴量グループON/OFFを自動最適化。

StudyはSQLite永続化→中断再開可能。
結果は optuna_best_params.json に保存 → experiment.py --use-optuna で読み込み。

Usage:
    python -m ml.optuna_tuner --model p --n-trials 100
    python -m ml.optuna_tuner --model w --n-trials 100
    python -m ml.optuna_tuner --model ar --n-trials 80
    python -m ml.optuna_tuner --all --n-trials 100
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

# experiment.pyから特徴量定義・データ構築を再利用
from ml.experiment import (
    BASE_FEATURES, PAST_FEATURES,
    TRAINER_FEATURES, JOCKEY_FEATURES,
    RUNNING_STYLE_FEATURES, ROTATION_FEATURES,
    PACE_FEATURES, TRAINING_FEATURES,
    SPEED_FEATURES, COMMENT_FEATURES,
    PEDIGREE_FEATURES, BABA_FEATURES,
    FEATURE_COLS_VALUE, MARKET_FEATURES,
    load_data, build_dataset, build_pit_personnel_timeline,
    load_race_json, parse_period_range,
)
from ml.features.margin_target import add_margin_target_to_df

# === 特徴量グループ定義（ON/OFF最適化対象） ===
# BASE + PAST は必須（全モデルの基盤）
FEATURE_GROUPS = {
    'trainer':       TRAINER_FEATURES,
    'jockey':        JOCKEY_FEATURES,
    'running_style': RUNNING_STYLE_FEATURES,
    'rotation':      ROTATION_FEATURES,
    'pace':          PACE_FEATURES,
    'training':      TRAINING_FEATURES,
    'speed':         SPEED_FEATURES,
    'comment':       COMMENT_FEATURES,
    'pedigree':      PEDIGREE_FEATURES,
    'baba':          BABA_FEATURES,
}

# 必須特徴量（MARKET除外済み）
MANDATORY_FEATURES = [f for f in BASE_FEATURES + PAST_FEATURES
                      if f not in MARKET_FEATURES]


def suggest_params(trial, model_type: str) -> Tuple[dict, int]:
    """Optunaのtrialからハイパーパラメータを提案

    Returns:
        (lgb_params, num_boost_round)
    """
    params = {
        'num_leaves':       trial.suggest_int('num_leaves', 31, 255),
        'max_depth':        trial.suggest_int('max_depth', 5, 12),
        'learning_rate':    trial.suggest_float('learning_rate', 0.005, 0.1, log=True),
        'feature_fraction': trial.suggest_float('feature_fraction', 0.5, 1.0),
        'bagging_fraction': trial.suggest_float('bagging_fraction', 0.5, 1.0),
        'bagging_freq':     trial.suggest_int('bagging_freq', 1, 7),
        'min_child_samples': trial.suggest_int('min_child_samples', 10, 100),
        'reg_alpha':        trial.suggest_float('reg_alpha', 0.0, 2.0),
        'reg_lambda':       trial.suggest_float('reg_lambda', 0.0, 3.0),
        'verbose':          -1,
        'seed':             42,
        'bagging_seed':     42,
        'feature_fraction_seed': 42,
    }

    num_boost_round = trial.suggest_int('num_boost_round', 500, 3000, step=100)

    if model_type in ('p', 'w'):
        params['objective'] = 'binary'
        params['metric'] = 'auc'
        if model_type == 'w':
            params['scale_pos_weight'] = trial.suggest_float(
                'scale_pos_weight', 1.0, 10.0
            )
    elif model_type == 'ar':
        params['objective'] = 'huber'
        params['metric'] = 'mae'
        params['alpha'] = trial.suggest_float('huber_delta', 0.5, 5.0)

    return params, num_boost_round


def select_features(trial) -> List[str]:
    """trialから特徴量グループON/OFFを提案し、特徴量リストを構築"""
    features = list(MANDATORY_FEATURES)

    for group_name, group_features in FEATURE_GROUPS.items():
        include = trial.suggest_categorical(f'use_{group_name}', [True, False])
        if include:
            for f in group_features:
                if f not in MARKET_FEATURES and f not in features:
                    features.append(f)

    return features


def create_objective(
    model_type: str,
    df_train: pd.DataFrame,
    df_val: pd.DataFrame,
    feature_cols_all: List[str],
):
    """Optuna objective関数を生成

    Args:
        model_type: 'p' (Place), 'w' (Win), 'ar' (Aura)
        df_train, df_val: 学習・検証データ
        feature_cols_all: 全特徴量の上限リスト（DataFrameに存在する列のみ使用）
    """
    import lightgbm as lgb

    if model_type in ('p', 'w'):
        label_col = 'is_top3' if model_type == 'p' else 'is_win'
    else:
        label_col = 'target_margin'

    def objective(trial):
        # ハイパーパラメータ提案
        params, num_boost_round = suggest_params(trial, model_type)

        # 特徴量グループ選択
        feature_cols = select_features(trial)
        # DataFrameに存在する列のみ
        feature_cols = [f for f in feature_cols if f in df_train.columns]

        if len(feature_cols) < 10:
            return float('-inf') if model_type != 'ar' else float('inf')

        # AR: NaN target除外
        if model_type == 'ar':
            mask_train = df_train[label_col].notna()
            mask_val = df_val[label_col].notna()
            X_train = df_train.loc[mask_train, feature_cols]
            y_train = df_train.loc[mask_train, label_col]
            X_val = df_val.loc[mask_val, feature_cols]
            y_val = df_val.loc[mask_val, label_col]
        else:
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
                lgb.log_evaluation(period=0),  # 非表示
            ],
        )

        y_pred_val = model.predict(X_val)

        if model_type in ('p', 'w'):
            from sklearn.metrics import roc_auc_score
            score = roc_auc_score(y_val, y_pred_val)
        else:
            from sklearn.metrics import mean_absolute_error
            score = -mean_absolute_error(y_val, y_pred_val)  # 最大化

        # trialにベスト反復を記録
        trial.set_user_attr('best_iteration', model.best_iteration)
        trial.set_user_attr('n_features', len(feature_cols))

        return score

    return objective


def run_optimization(
    model_type: str,
    df_train: pd.DataFrame,
    df_val: pd.DataFrame,
    n_trials: int = 100,
    timeout: Optional[int] = None,
) -> dict:
    """1モデルのOptuna最適化を実行"""
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)

    # Study永続化ディレクトリ
    optuna_dir = config.ml_dir() / "optuna"
    optuna_dir.mkdir(parents=True, exist_ok=True)

    study_name = f"keiba_{model_type}"
    storage = f"sqlite:///{optuna_dir / f'study_{model_type}.db'}"

    study = optuna.create_study(
        study_name=study_name,
        storage=storage,
        direction='maximize',
        load_if_exists=True,
        pruner=optuna.pruners.MedianPruner(n_startup_trials=10),
    )

    objective = create_objective(model_type, df_train, df_val, FEATURE_COLS_VALUE)

    completed_before = len(study.trials)
    print(f"\n[Optuna] Model={model_type.upper()}, "
          f"trials={n_trials}, existing={completed_before}")

    study.optimize(
        objective,
        n_trials=n_trials,
        timeout=timeout,
        show_progress_bar=True,
    )

    best = study.best_trial
    print(f"\n[Optuna] Best trial #{best.number}: value={best.value:.6f}")
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

    # LightGBMパラメータとnum_boost_roundを分離
    num_boost_round = best_params.pop('num_boost_round', 1500)

    # モデル固有パラメータの整理
    if model_type in ('p', 'w'):
        best_params['objective'] = 'binary'
        best_params['metric'] = 'auc'
    if model_type == 'ar':
        best_params['objective'] = 'huber'
        best_params['metric'] = 'mae'
        if 'huber_delta' in best_params:
            best_params['alpha'] = best_params.pop('huber_delta')

    best_params['verbose'] = -1
    best_params['seed'] = 42
    best_params['bagging_seed'] = 42
    best_params['feature_fraction_seed'] = 42

    # ベスト特徴量リスト構築
    best_features = list(MANDATORY_FEATURES)
    for group_name, group_features in FEATURE_GROUPS.items():
        if feature_group_flags.get(f'use_{group_name}', True):
            for f in group_features:
                if f not in MARKET_FEATURES and f not in best_features:
                    best_features.append(f)

    result = {
        'model_type': model_type,
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

    # 個別結果保存
    out_path = optuna_dir / f"best_params_{model_type}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"  Saved: {out_path}")

    # Top10パラメータ表示
    print(f"\n  Best Parameters (Model {model_type.upper()}):")
    for key in sorted(best_params.keys()):
        if key not in ('verbose', 'seed', 'bagging_seed', 'feature_fraction_seed',
                        'objective', 'metric'):
            print(f"    {key:>25}: {best_params[key]}")
    print(f"    {'num_boost_round':>25}: {num_boost_round}")

    print(f"\n  Feature Groups:")
    for group_name in FEATURE_GROUPS:
        flag = feature_group_flags.get(f'use_{group_name}', True)
        marker = 'ON' if flag else 'OFF'
        count = len(FEATURE_GROUPS[group_name])
        print(f"    {group_name:>15}: {marker} ({count} features)")

    return result


def save_combined_results(results: Dict[str, dict]):
    """全モデルの結果を統合JSONに保存"""
    optuna_dir = config.ml_dir() / "optuna"
    combined = {
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'models': {},
    }
    for model_type, result in results.items():
        combined['models'][model_type] = result

    out_path = optuna_dir / "optuna_best_params.json"
    out_path.write_text(json.dumps(combined, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n[Combined] Saved: {out_path}")


def main():
    parser = argparse.ArgumentParser(description='Optuna HP + Feature Group Tuner')
    parser.add_argument('--model', choices=['p', 'w', 'ar'],
                        help='最適化対象モデル (p=Place, w=Win, ar=Aura)')
    parser.add_argument('--all', action='store_true',
                        help='全モデル(P/W/AR)を順次最適化')
    parser.add_argument('--n-trials', type=int, default=100,
                        help='試行回数 (default: 100)')
    parser.add_argument('--timeout', type=int, default=None,
                        help='タイムアウト秒 (default: None)')
    parser.add_argument('--train-years', default='2020-2024',
                        help='学習期間 (default: 2020-2024)')
    parser.add_argument('--val-years', default='2025.01-2025.02',
                        help='検証期間 (default: 2025.01-2025.02)')
    parser.add_argument('--no-db', action='store_true',
                        help='DBオッズ未使用')
    args = parser.parse_args()

    if not args.model and not args.all:
        parser.error('--model or --all is required')

    models_to_tune = ['p', 'w', 'ar'] if args.all else [args.model]

    print(f"\n{'='*60}")
    print(f"  KeibaCICD v6 - Optuna HP + Feature Tuner")
    print(f"  Models: {', '.join(m.upper() for m in models_to_tune)}")
    print(f"  Trials: {args.n_trials}")
    print(f"  Train:  {args.train_years}")
    print(f"  Val:    {args.val_years}")
    print(f"{'='*60}\n")

    t0 = time.time()

    # データロード（experiment.pyの関数を再利用）
    (history_cache, trainer_index, jockey_index,
     date_index, pace_index, kb_ext_index, training_summary_index,
     race_level_index, pedigree_index, sire_stats_index) = load_data()

    pit_trainer_tl, pit_jockey_tl = build_pit_personnel_timeline()

    from ml.features.baba_features import load_baba_index
    baba_index = load_baba_index()

    use_db_odds = not args.no_db

    # データセット構築
    train_min, train_min_m, train_max, train_max_m = parse_period_range(args.train_years)
    val_min, val_min_m, val_max, val_max_m = parse_period_range(args.val_years)

    df_train = build_dataset(
        date_index, history_cache, trainer_index, jockey_index,
        pace_index, kb_ext_index,
        train_min, train_max, use_db_odds=use_db_odds,
        training_summary_index=training_summary_index,
        race_level_index=race_level_index,
        pedigree_index=pedigree_index,
        sire_stats_index=sire_stats_index,
        min_month=train_min_m, max_month=train_max_m,
        pit_trainer_tl=pit_trainer_tl, pit_jockey_tl=pit_jockey_tl,
        baba_index=baba_index,
    )

    df_val = build_dataset(
        date_index, history_cache, trainer_index, jockey_index,
        pace_index, kb_ext_index,
        val_min, val_max, use_db_odds=use_db_odds,
        training_summary_index=training_summary_index,
        race_level_index=race_level_index,
        pedigree_index=pedigree_index,
        sire_stats_index=sire_stats_index,
        min_month=val_min_m, max_month=val_max_m,
        pit_trainer_tl=pit_trainer_tl, pit_jockey_tl=pit_jockey_tl,
        baba_index=baba_index,
    )

    # AR用 margin target追加
    if 'ar' in models_to_tune:
        print("\n[Margin] Computing target_margin...")
        add_margin_target_to_df(df_train, date_index, load_race_json, cap=5.0)
        add_margin_target_to_df(df_val, date_index, load_race_json, cap=5.0)

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

    # 統合結果保存
    if len(results) > 1:
        save_combined_results(results)
    elif len(results) == 1:
        # 単一モデルでも既存の他モデル結果とマージ
        optuna_dir = config.ml_dir() / "optuna"
        combined_path = optuna_dir / "optuna_best_params.json"
        existing = {}
        if combined_path.exists():
            existing = json.loads(combined_path.read_text(encoding='utf-8'))
        if 'models' not in existing:
            existing = {'models': {}}
        existing['models'].update(results)
        existing['created_at'] = datetime.now().isoformat(timespec='seconds')
        combined_path.write_text(
            json.dumps(existing, ensure_ascii=False, indent=2), encoding='utf-8'
        )
        print(f"\n[Combined] Updated: {combined_path}")

    elapsed = time.time() - t0
    print(f"\n[Done] Total elapsed: {elapsed:.0f}s ({elapsed/60:.1f}min)")


if __name__ == '__main__':
    main()
