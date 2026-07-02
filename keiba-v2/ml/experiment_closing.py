#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
差し追込好走予測モデル実験パイプライン

「3着以内に差し/追込が2頭以上入るレース」を予測するレースレベル分類モデル。
experiment_obstacle.py のパターンを踏襲し、experiment.py のインフラを再利用。

- 1行 = 1レース（馬レベル特徴量をレースレベルに集計）
- LightGBM binary classification
- 少頭数(< 8)・障害レースは除外

Usage:
    python -m ml.experiment_closing
    python -m ml.experiment_closing --train-years 2020-2024 --val-years 2025.01-2025.02 --test-years 2025.03-2026.02
"""

import argparse
import json
import pickle
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
    build_pit_personnel_timeline,
    calibrate_isotonic, calc_brier_score, calc_ece,
    parse_period_range, _iter_date_index, _format_period,
)
from ml.features.closing_race_features import (
    CLOSING_RACE_FEATURES,
    CourseClosingTimeline,
    compute_closing_label,
    compute_closing_race_features,
)
from ml.features.baba_features import get_baba_features, load_baba_index, race_id_to_baba_key
from ml.utils.filters import is_obstacle
from core.jravan import race_id as rid

# === ハイパーパラメータ ===
PARAMS_CLOSING = {
    'objective': 'binary',
    'metric': 'auc',
    'num_leaves': 63,
    'learning_rate': 0.03,
    'feature_fraction': 0.8,
    'bagging_fraction': 0.8,
    'bagging_freq': 5,
    'min_child_samples': 30,
    'reg_alpha': 0.3,
    'reg_lambda': 2.0,
    'max_depth': 6,
    'scale_pos_weight': 8.5,
    'verbose': -1,
    'seed': 42,
    'bagging_seed': 42,
    'feature_fraction_seed': 42,
}

# Session 183: Regulus v1.2 レシピを Eclipse に移植。
#  - dataset キャッシュ(重い再構築を1回だけ) → 以後は高速反復
#  - seedアンサンブル(小データのレース単位モデルの分散低減)
ENSEMBLE_SEEDS = [42, 1, 7, 13, 21]
CLOSING_CACHE = config.ml_dir() / "nova" / "closing" / "splits"


def _fit_closing_ensemble(df_train, df_val, df_test, feature_cols, params, label_col,
                          seeds, num_boost_round=1500, stopping_rounds=150):
    """seedを変えたN本を学習し val/test raw を平均→averaged raw で isotonic較正 (Regulus v1.2と同型)。
    返り値=(models[list], metrics, importance_avg, pred_cal_test, calibrator, pred_raw_test)。"""
    import lightgbm as lgb
    from sklearn.metrics import roc_auc_score, accuracy_score, log_loss

    Xtr, ytr = df_train[feature_cols], df_train[label_col]
    Xva, yva = df_val[feature_cols], df_val[label_col]
    Xte, yte = df_test[feature_cols], df_test[label_col]
    models, val_raws, test_raws, imps = [], [], [], []
    print(f"\n[Train-Ensemble] ClosingRace: {len(feature_cols)} feat, "
          f"train={len(Xtr):,} val={len(Xva):,} test={len(Xte):,}, seeds={seeds}")
    for s in seeds:
        p = {**params, "seed": s, "bagging_seed": s, "feature_fraction_seed": s}
        dtr = lgb.Dataset(Xtr, label=ytr)
        dva = lgb.Dataset(Xva, label=yva, reference=dtr)
        m = lgb.train(p, dtr, num_boost_round=num_boost_round, valid_sets=[dva],
                      callbacks=[lgb.early_stopping(stopping_rounds=stopping_rounds),
                                 lgb.log_evaluation(0)])
        models.append(m)
        val_raws.append(m.predict(Xva)); test_raws.append(m.predict(Xte))
        imps.append(dict(zip(feature_cols, m.feature_importance(importance_type="gain"))))
        print(f"    seed={s:>2} best_iter={m.best_iteration} test_auc={roc_auc_score(yte, test_raws[-1]):.4f}")
    val_raw = np.mean(val_raws, axis=0); test_raw = np.mean(test_raws, axis=0)
    pred_cal, calibrator = calibrate_isotonic(val_raw, yva.values, test_raw)
    importance = {f: float(np.mean([im[f] for im in imps])) for f in feature_cols}
    metrics = {
        'auc': round(float(roc_auc_score(yte, test_raw)), 4),
        'accuracy': round(float(accuracy_score(yte, (test_raw > 0.5).astype(int))), 4),
        'log_loss': round(float(log_loss(yte, np.clip(test_raw, 1e-7, 1 - 1e-7))), 4),
        'brier_score': round(float(calc_brier_score(yte.values, test_raw)), 4),
        'ece': round(float(calc_ece(yte.values, test_raw)), 4),
        'ece_calibrated': round(float(calc_ece(yte.values, pred_cal)), 4),
        'brier_calibrated': round(float(calc_brier_score(yte.values, pred_cal)), 4),
        'log_loss_calibrated': round(float(log_loss(yte, np.clip(pred_cal, 1e-7, 1 - 1e-7))), 4),
        'auc_val': round(float(roc_auc_score(yva, val_raw)), 4),
        'best_iteration': int(np.round(np.mean([m.best_iteration for m in models]))),
        'n_seeds': len(seeds),
        'train_size': len(Xtr), 'val_size': len(Xva), 'test_size': len(Xte),
    }
    return models, metrics, importance, pred_cal, calibrator, test_raw


def train_closing_model(
    df_train: pd.DataFrame,
    df_val: pd.DataFrame,
    df_test: pd.DataFrame,
    feature_cols: List[str],
    params: dict,
    label_col: str = 'is_closing_race',
    model_name: str = 'ClosingRace',
    num_boost_round: int = 1500,
    stopping_rounds: int = 150,
) -> Tuple:
    """差し追込モデル用の学習関数

    val setが小さい(~500レース)ため、stopping_roundsを大きめに設定。
    """
    import lightgbm as lgb
    from sklearn.metrics import roc_auc_score, accuracy_score, log_loss

    X_train = df_train[feature_cols]
    y_train = df_train[label_col]
    X_val = df_val[feature_cols]
    y_val = df_val[label_col]
    X_test = df_test[feature_cols]
    y_test = df_test[label_col]

    train_data = lgb.Dataset(X_train, label=y_train)
    valid_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

    print(f"\n[Train] {model_name}: {len(feature_cols)} features, "
          f"train={len(X_train):,}, val={len(X_val):,}, test={len(X_test):,}, "
          f"stopping_rounds={stopping_rounds}")

    model = lgb.train(
        params, train_data, num_boost_round=num_boost_round,
        valid_sets=[valid_data],
        callbacks=[
            lgb.early_stopping(stopping_rounds=stopping_rounds),
            lgb.log_evaluation(period=200),
        ],
    )

    y_pred_raw = model.predict(X_test)
    y_pred_val = model.predict(X_val)

    y_pred_cal, calibrator = calibrate_isotonic(
        y_pred_val, y_val.values, y_pred_raw
    )

    auc = roc_auc_score(y_test, y_pred_raw)
    acc = accuracy_score(y_test, (y_pred_raw > 0.5).astype(int))
    ll = log_loss(y_test, y_pred_raw)
    brier = calc_brier_score(y_test.values, y_pred_raw)
    ece = calc_ece(y_test.values, y_pred_raw)
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


def build_course_timeline(
    date_index: dict,
) -> CourseClosingTimeline:
    """全レースJSONからコース歴史統計タイムラインを構築"""
    print("[Build] Building course closing timeline...")

    def race_iter():
        for date_str, race_id in _iter_date_index(date_index):
            try:
                race = load_race_json(race_id, date_str)
                yield race, date_str
            except Exception:
                continue

    timeline = CourseClosingTimeline()
    timeline.build(race_iter())

    total_courses = len(timeline.timeline)
    print(f"[Build] Course timeline: {total_courses} course patterns")
    return timeline


def build_closing_dataset(
    date_index: dict,
    history_cache: dict,
    trainer_index: dict,
    jockey_index: dict,
    pace_index: dict,
    kb_ext_index: dict,
    min_year: int,
    max_year: int,
    course_timeline: CourseClosingTimeline,
    baba_index: dict = None,
    use_db_odds: bool = True,
    race_level_index: dict = None,
    pedigree_index: dict = None,
    sire_stats_index: dict = None,
    min_month: int = None,
    max_month: int = None,
    pit_trainer_tl: dict = None,
    pit_jockey_tl: dict = None,
) -> pd.DataFrame:
    """差し追込レースレベルの特徴量DataFrameを構築

    1行 = 1レース。障害レース・少頭数(< 8)を除外。
    """
    date_min = min_year * 100 + (min_month or 1)
    date_max = max_year * 100 + (max_month or 12)
    label_min = f"{min_year}-{min_month:02d}" if min_month else str(min_year)
    label_max = f"{max_year}-{max_month:02d}" if max_month else str(max_year)
    print(f"\n[Build] Building closing dataset for {label_min} ~ {label_max}...")

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
    skipped_obstacle = 0
    skipped_small = 0
    error_count = 0

    for date_str, race_id in target_races:
        try:
            race = load_race_json(race_id, date_str)

            # 障害レースは除外
            if is_obstacle(race):
                skipped_obstacle += 1
                continue

            # ターゲット計算（少頭数もここで除外）
            label = compute_closing_label(race)
            if label is None:
                skipped_small += 1
                continue

            # 馬レベル特徴量を計算（既存インフラ再利用）
            horse_features = compute_features_for_race(
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

            # 馬場特徴量
            track_type = race.get('track_type', '')
            baba_feat = get_baba_features(race_id, track_type, baba_index or {})

            # レースレベル特徴量に集計
            race_feat = compute_closing_race_features(
                race, horse_features,
                course_timeline=course_timeline,
                baba_features=baba_feat,
            )

            # メタ情報
            race_feat['race_id'] = race_id
            race_feat['date'] = date_str
            race_feat['venue_name'] = race.get('venue_name', '')
            race_feat['is_closing_race'] = label

            all_rows.append(race_feat)
            race_count += 1

        except Exception as e:
            error_count += 1
            if error_count <= 5:
                print(f"  ERROR: {race_id}: {e}")

    df = pd.DataFrame(all_rows)

    # object型をfloat64に変換
    for col in df.columns:
        if col in set(CLOSING_RACE_FEATURES) and df[col].dtype == object:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    pos_count = df['is_closing_race'].sum() if len(df) > 0 else 0
    pos_rate = pos_count / len(df) if len(df) > 0 else 0

    print(f"[Build] {race_count:,} races ({pos_count:.0f} closing={pos_rate:.1%}), "
          f"{error_count} errors, "
          f"skip: {skipped_obstacle} obstacle, {skipped_small} small field")
    return df


def calc_threshold_analysis(y_true: np.ndarray, y_pred: np.ndarray) -> List[dict]:
    """閾値別のPrecision/Recall/F1を計算"""
    results = []
    for threshold in [0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40]:
        predicted_positive = y_pred >= threshold
        n_predicted = predicted_positive.sum()
        if n_predicted == 0:
            results.append({
                'threshold': threshold,
                'precision': 0, 'recall': 0, 'f1': 0,
                'n_predicted': 0, 'n_correct': 0,
            })
            continue
        true_positive = (predicted_positive & (y_true == 1)).sum()
        total_positive = (y_true == 1).sum()
        precision = true_positive / n_predicted if n_predicted > 0 else 0
        recall = true_positive / total_positive if total_positive > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        results.append({
            'threshold': threshold,
            'precision': round(precision, 4),
            'recall': round(recall, 4),
            'f1': round(f1, 4),
            'n_predicted': int(n_predicted),
            'n_correct': int(true_positive),
        })
    return results


def calc_subset_analysis(df: pd.DataFrame, pred_col: str, group_col: str) -> List[dict]:
    """サブセット別AUC分析"""
    from sklearn.metrics import roc_auc_score
    results = []
    for group_val, group_df in df.groupby(group_col):
        if len(group_df) < 20 or group_df['is_closing_race'].nunique() < 2:
            continue
        try:
            auc = roc_auc_score(group_df['is_closing_race'], group_df[pred_col])
            pos_rate = group_df['is_closing_race'].mean()
            results.append({
                'group': str(group_val),
                'auc': round(auc, 4),
                'n_races': len(group_df),
                'positive_rate': round(pos_rate, 4),
            })
        except Exception:
            continue
    return sorted(results, key=lambda x: -x['auc'])


def main():
    parser = argparse.ArgumentParser(description='Closing Race ML Experiment')
    # S183: fresh + bigval 既定 (旧liveは train~2024-06 で stale, val 1ヶ月問題も回避)
    parser.add_argument('--train-years', default='2020-2024.12',
                        help='Training period (例: 2020-2024.12)')
    parser.add_argument('--val-years', default='2025.01-2025.06',
                        help='Validation period (6ヶ月 bigval, 例: 2025.01-2025.06)')
    parser.add_argument('--test-years', default='2025.07-2026.06',
                        help='Test period (例: 2025.07-2026.06)')
    parser.add_argument('--no-db', action='store_true', help='DBオッズ未使用')
    parser.add_argument('--rebuild-cache', action='store_true',
                        help='splitsキャッシュを強制再構築 (既定: 期間一致なら再利用)')
    parser.add_argument('--no-ensemble', action='store_true',
                        help='seedアンサンブルを無効化 (単一seed)')
    args = parser.parse_args()

    train_min, train_min_m, train_max, train_max_m = parse_period_range(args.train_years)
    val_min, val_min_m, val_max, val_max_m = parse_period_range(args.val_years)
    test_min, test_min_m, test_max, test_max_m = parse_period_range(args.test_years)
    use_db_odds = not args.no_db

    train_label = f"{_format_period(train_min, train_min_m)} ~ {_format_period(train_max, train_max_m)}"
    val_label = f"{_format_period(val_min, val_min_m)} ~ {_format_period(val_max, val_max_m)}"
    test_label = f"{_format_period(test_min, test_min_m)} ~ {_format_period(test_max, test_max_m)}"

    print(f"\n{'='*60}")
    print(f"  KeibaCICD - Closing Race ML Experiment")
    print(f"  差し追込好走予測: 3着以内に差し/追込 2頭以上")
    print(f"  Train: {train_label}")
    print(f"  Val:   {val_label} (early stopping)")
    print(f"  Test:  {test_label} (pure evaluation)")
    print(f"  DB Odds: {'ON' if use_db_odds else 'OFF'}")
    print(f"  Features: {len(CLOSING_RACE_FEATURES)}")
    print(f"  Params: leaves={PARAMS_CLOSING['num_leaves']}, "
          f"depth={PARAMS_CLOSING['max_depth']}, "
          f"min_child={PARAMS_CLOSING['min_child_samples']}, "
          f"scale_pos_weight={PARAMS_CLOSING['scale_pos_weight']}")
    print(f"{'='*60}\n")

    t0 = time.time()

    # === splits キャッシュ (重い再構築を1回だけ・期間一致なら再利用) ===
    periods = {"train": args.train_years, "val": args.val_years, "test": args.test_years}
    cache_meta = CLOSING_CACHE / "periods.json"
    cache_ok = (not args.rebuild_cache and cache_meta.exists()
                and (CLOSING_CACHE / "train.pkl").exists()
                and (CLOSING_CACHE / "val.pkl").exists()
                and (CLOSING_CACHE / "test.pkl").exists())
    if cache_ok:
        try:
            cache_ok = json.loads(cache_meta.read_text(encoding="utf-8")) == periods
        except Exception:
            cache_ok = False

    if cache_ok:
        print(f"[Cache] Loading cached closing splits from {CLOSING_CACHE} (periods match)")
        df_train = pd.read_pickle(CLOSING_CACHE / "train.pkl")
        df_val = pd.read_pickle(CLOSING_CACHE / "val.pkl")
        df_test = pd.read_pickle(CLOSING_CACHE / "test.pkl")
    else:
        # データロード (重い)
        (history_cache, trainer_index, jockey_index,
         date_index, pace_index, kb_ext_index, training_summary_index,
         race_level_index, pedigree_index, sire_stats_index, *_extra) = load_data()

        pit_trainer_tl, pit_jockey_tl = build_pit_personnel_timeline(
            years=list(range(2020, 2027))
        )
        baba_index = load_baba_index()
        print(f"[Load] Baba index: {len(baba_index):,} entries")
        course_timeline = build_course_timeline(date_index)

        common_args = dict(
            date_index=date_index, history_cache=history_cache,
            trainer_index=trainer_index, jockey_index=jockey_index,
            pace_index=pace_index, kb_ext_index=kb_ext_index,
            course_timeline=course_timeline, baba_index=baba_index,
            use_db_odds=use_db_odds, race_level_index=race_level_index,
            pedigree_index=pedigree_index, sire_stats_index=sire_stats_index,
            pit_trainer_tl=pit_trainer_tl, pit_jockey_tl=pit_jockey_tl,
        )
        df_train = build_closing_dataset(
            min_year=train_min, max_year=train_max,
            min_month=train_min_m, max_month=train_max_m, **common_args)
        df_val = build_closing_dataset(
            min_year=val_min, max_year=val_max,
            min_month=val_min_m, max_month=val_max_m, **common_args)
        df_test = build_closing_dataset(
            min_year=test_min, max_year=test_max,
            min_month=test_min_m, max_month=test_max_m, **common_args)

        CLOSING_CACHE.mkdir(parents=True, exist_ok=True)
        df_train.to_pickle(CLOSING_CACHE / "train.pkl")
        df_val.to_pickle(CLOSING_CACHE / "val.pkl")
        df_test.to_pickle(CLOSING_CACHE / "test.pkl")
        cache_meta.write_text(json.dumps(periods, ensure_ascii=False), encoding="utf-8")
        print(f"[Cache] Saved closing splits to {CLOSING_CACHE}")

    for label, df in [('Train', df_train), ('Val', df_val), ('Test', df_test)]:
        if len(df) > 0:
            pos = df['is_closing_race'].sum()
            print(f"[Dataset] {label}: {len(df):,} races, "
                  f"closing={pos:.0f} ({pos/len(df):.1%})")
        else:
            print(f"[Dataset] {label}: EMPTY")

    if len(df_train) == 0 or len(df_val) == 0 or len(df_test) == 0:
        print("\nERROR: Empty dataset.")
        sys.exit(1)

    # scale_pos_weight を実データから自動調整
    pos_rate = df_train['is_closing_race'].mean()
    if pos_rate > 0:
        auto_weight = round((1 - pos_rate) / pos_rate, 1)
        PARAMS_CLOSING['scale_pos_weight'] = auto_weight
        print(f"[Params] Auto scale_pos_weight = {auto_weight} (pos_rate={pos_rate:.3f})")

    # 使用可能な特徴量を確認
    available_features = [f for f in CLOSING_RACE_FEATURES if f in df_train.columns]
    missing = set(CLOSING_RACE_FEATURES) - set(available_features)
    if missing:
        print(f"\n[Warning] {len(missing)} features not in data: {sorted(missing)}")
    print(f"[Features] Using {len(available_features)} of {len(CLOSING_RACE_FEATURES)} defined features")

    # === モデル学習 (既定=5seedアンサンブル / --no-ensemble で単一) ===
    if args.no_ensemble:
        model, metrics, importance, pred_cal, calibrator, pred_raw = train_closing_model(
            df_train, df_val, df_test, available_features,
            PARAMS_CLOSING, 'is_closing_race', 'ClosingRace', stopping_rounds=150)
        models = [model]
    else:
        models, metrics, importance, pred_cal, calibrator, pred_raw = _fit_closing_ensemble(
            df_train, df_val, df_test, available_features,
            PARAMS_CLOSING, 'is_closing_race', ENSEMBLE_SEEDS, stopping_rounds=150)
        model = models[0]
    print(f"[Model] {'ensemble x'+str(len(models)) if len(models) > 1 else 'single'} | "
          f"AUC={metrics['auc']} ECE(cal)={metrics['ece_calibrated']} avg_iter={metrics['best_iteration']}")

    # 予測結果をDataFrameに追加
    df_test = df_test.copy()
    df_test['pred_proba'] = pred_cal
    df_test['pred_proba_raw'] = pred_raw

    # === 分析 ===
    print(f"\n{'='*60}")
    print(f"  Analysis")
    print(f"{'='*60}")

    # AUC-PR
    from sklearn.metrics import average_precision_score
    pr_auc = average_precision_score(df_test['is_closing_race'], pred_raw)
    print(f"\n[PR-AUC] {pr_auc:.4f} (random baseline: {df_test['is_closing_race'].mean():.4f})")

    # 閾値分析
    thr_results = calc_threshold_analysis(
        df_test['is_closing_race'].values, pred_cal
    )
    print(f"\n[Threshold Analysis]")
    print(f"  {'Threshold':>10s} {'Prec':>8s} {'Recall':>8s} {'F1':>8s} {'n_pred':>8s} {'n_corr':>8s}")
    for r in thr_results:
        print(f"  {r['threshold']:>10.2f} {r['precision']:>8.1%} {r['recall']:>8.1%} "
              f"{r['f1']:>8.3f} {r['n_predicted']:>8d} {r['n_correct']:>8d}")

    # 特徴量重要度 Top15
    sorted_imp = sorted(importance.items(), key=lambda x: x[1], reverse=True)
    print(f"\n[Importance] Top 15:")
    for i, (feat, imp) in enumerate(sorted_imp[:15], 1):
        print(f"  {i:2d}. {feat:<35s} {imp:>8.0f}")

    # コース別精度
    if 'is_turf' in df_test.columns:
        print(f"\n[Surface Analysis]")
        for surface_val, surface_name in [(1, '芝'), (0, 'ダート')]:
            subset = df_test[df_test['is_turf'] == surface_val]
            if len(subset) > 20 and subset['is_closing_race'].nunique() == 2:
                from sklearn.metrics import roc_auc_score
                s_auc = roc_auc_score(subset['is_closing_race'], subset['pred_proba_raw'])
                s_pos = subset['is_closing_race'].mean()
                print(f"  {surface_name}: AUC={s_auc:.4f}, "
                      f"closing={s_pos:.1%}, n={len(subset)}")

    # 距離カテゴリ別精度
    if 'distance_category' in df_test.columns:
        print(f"\n[Distance Category Analysis]")
        dist_names = {0: 'Sprint(~1400)', 1: 'Mile(~1800)',
                      2: 'Mid(~2200)', 3: 'Long(2400+)'}
        dist_results = calc_subset_analysis(df_test, 'pred_proba_raw', 'distance_category')
        for r in dist_results:
            name = dist_names.get(int(r['group']), r['group'])
            print(f"  {name}: AUC={r['auc']:.4f}, "
                  f"closing={r['positive_rate']:.1%}, n={r['n_races']}")

    # 競馬場別精度
    print(f"\n[Venue Analysis]")
    venue_results = calc_subset_analysis(df_test, 'pred_proba_raw', 'venue_name')
    for r in venue_results[:10]:
        print(f"  {r['group']}: AUC={r['auc']:.4f}, "
              f"closing={r['positive_rate']:.1%}, n={r['n_races']}")

    # === モデル保存 ===
    ml_dir = config.ml_dir()
    model_path = ml_dir / "model_closing.txt"
    # 古いアンサンブルメンバーを掃除してから保存 (seed数変更/単一化時のstale防止)
    for stale in ml_dir.glob("model_closing_ens*.txt"):
        stale.unlink()
    model.save_model(str(model_path))
    for i, m in enumerate(models[1:], start=1):
        m.save_model(str(ml_dir / f"model_closing_ens{i}.txt"))
    print(f"\n[Save] Model saved to {model_path}"
          + (f" + {len(models)-1} ensemble members" if len(models) > 1 else ""))

    # キャリブレーター保存
    cal_path = ml_dir / "calibrator_closing.pkl"
    with open(cal_path, 'wb') as f:
        pickle.dump(calibrator, f)
    print(f"[Save] Calibrator saved to {cal_path}")

    # メタデータ保存
    meta = {
        'version': 'closing-v2.0' if args.no_ensemble else 'closing-v2.1',
        'model_type': 'closing_race',
        'description': '差し追込好走予測: 3着以内に差し/追込 2頭以上'
                       + ('' if args.no_ensemble else '（S183: fresh再学習+5seedアンサンブル+datasetキャッシュ）'),
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'train_period': train_label,
        'val_period': val_label,
        'test_period': test_label,
        'features': available_features,
        'feature_count': len(available_features),
        'params': PARAMS_CLOSING,
        'ensemble_seeds': ENSEMBLE_SEEDS if not args.no_ensemble else [42],
        'metrics': metrics,
        'pr_auc': round(pr_auc, 4),
        'threshold_analysis': thr_results,
        'train_races': len(df_train),
        'train_positive_rate': round(df_train['is_closing_race'].mean(), 4),
        'val_races': len(df_val),
        'test_races': len(df_test),
        'test_positive_rate': round(df_test['is_closing_race'].mean(), 4),
        'feature_importance': [
            {'feature': f, 'importance': float(imp)}
            for f, imp in sorted_imp
        ],
    }

    meta_path = ml_dir / "model_closing_meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"[Save] Meta saved to {meta_path}")

    # === 標準スキーム(models/eclipse/live/)に同期 ===
    # model_loader / predict_closing は legacy root ではなく models/eclipse/live/ を読むため、
    # ここへ標準名(model_p.txt / model_p_ens*.txt / calibrators.pkl / meta.json)で必ず同期する。
    # (ML Report は root の model_closing_meta.json を meta_file 経由で読むので root も維持)
    live_dir = ml_dir / "models" / "eclipse" / "live"
    live_dir.mkdir(parents=True, exist_ok=True)
    for stale in live_dir.glob("model_p_ens*.txt"):
        stale.unlink()
    model.save_model(str(live_dir / "model_p.txt"))
    for i, m in enumerate(models[1:], start=1):
        m.save_model(str(live_dir / f"model_p_ens{i}.txt"))
    with open(live_dir / "calibrators.pkl", 'wb') as f:
        pickle.dump(calibrator, f)
    (live_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"[Save] Synced standard scheme to {live_dir}"
          + (f" (+{len(models)-1} ens members)" if len(models) > 1 else ""))

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  Closing Race Experiment Complete")
    print(f"  AUC-ROC: {metrics['auc']:.4f}")
    print(f"  AUC-PR:  {pr_auc:.4f}")
    print(f"  Brier:   {metrics['brier_score']:.4f}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
