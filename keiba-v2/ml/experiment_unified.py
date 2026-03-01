#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
統合パフォーマンスモデル実験

3つのアプローチを比較して、P+W+ARを1モデルに統合できるか検証:
  1. Margin回帰 (現行AR) — Huber loss, target=time_behind_winner
  2. LambdaRank — Learning-to-Rank, レース内順位最適化
  3. Finish Position回帰 — Huber loss, target=着順

評価指標:
  - Top1 Win率 / Top1 好走率
  - Top1 Win ROI (単勝)
  - スコア→勝利確率キャリブレーション精度 (Brier, ECE)
  - スコア→好走確率キャリブレーション精度
  - VB再現性 (gap計算→既存VB Floorでのhit率)

Usage:
    python -m ml.experiment_unified
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    roc_auc_score, brier_score_loss, mean_absolute_error,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from ml.experiment import (
    FEATURE_COLS_VALUE, PARAMS_AR, PARAMS_P, PARAMS_W,
    build_dataset, load_race_json, load_data,
    build_pit_personnel_timeline,
)
from ml.features.margin_target import add_margin_target_to_df


# ============================================================
# LambdaRank パラメータ
# ============================================================
PARAMS_RANK = {
    'objective': 'lambdarank',
    'metric': 'ndcg',
    'ndcg_eval_at': [1, 3, 5],
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
    'lambdarank_truncation_level': 10,
}

# Finish position回帰パラメータ
PARAMS_FP = {
    'objective': 'huber',
    'alpha': 3.0,  # finish_pos range wider than margin
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


# ============================================================
# Helpers
# ============================================================

def make_lambdarank_groups(df: pd.DataFrame) -> np.ndarray:
    """race_idごとのグループサイズを返す (LambdaRank用)"""
    return df.groupby('race_id', sort=False).size().values


def make_relevance_labels(df: pd.DataFrame) -> np.ndarray:
    """着順からLambdaRank用のrelevanceラベルを生成

    着順が良いほど高いrelevanceスコア:
      1着=5, 2着=4, 3着=3, 4-5着=2, 6-8着=1, 9着以下=0
    """
    fp = df['finish_position'].values
    relevance = np.zeros(len(fp), dtype=np.int32)
    relevance[fp == 1] = 5
    relevance[fp == 2] = 4
    relevance[fp == 3] = 3
    relevance[(fp >= 4) & (fp <= 5)] = 2
    relevance[(fp >= 6) & (fp <= 8)] = 1
    return relevance


def calibrate_scores(
    scores_train: np.ndarray, y_train: np.ndarray,
    scores_test: np.ndarray,
) -> Tuple[np.ndarray, IsotonicRegression]:
    """スコア→確率へのキャリブレーション (IsotonicRegression)"""
    cal = IsotonicRegression(y_min=0.001, y_max=0.999, out_of_bounds='clip')
    cal.fit(scores_train, y_train)
    return cal.predict(scores_test), cal


def compute_ece(y_true, y_prob, n_bins=10):
    """Expected Calibration Error"""
    bin_boundaries = np.linspace(0, 1, n_bins + 1)
    ece = 0
    for i in range(n_bins):
        mask = (y_prob >= bin_boundaries[i]) & (y_prob < bin_boundaries[i + 1])
        if mask.sum() == 0:
            continue
        avg_pred = y_prob[mask].mean()
        avg_true = y_true[mask].mean()
        ece += mask.sum() * abs(avg_pred - avg_true)
    return ece / len(y_true)


def evaluate_model(
    df_test: pd.DataFrame,
    score_col: str,
    higher_is_better: bool,
    model_name: str,
    cal_win: IsotonicRegression = None,
    cal_place: IsotonicRegression = None,
) -> dict:
    """統一評価: ランキング + キャリブレーション + ROI"""

    results = {'name': model_name}

    # --- ランキング品質 ---
    top1_win = 0
    top1_place = 0
    race_count = 0
    roi_data = []

    for race_id, group in df_test.groupby('race_id'):
        if len(group) < 3:
            continue
        race_count += 1

        if higher_is_better:
            top1_idx = group[score_col].idxmax()
        else:
            top1_idx = group[score_col].idxmin()

        top1 = group.loc[top1_idx]
        fp = int(top1['finish_position'])

        if fp == 1:
            top1_win += 1
        if fp <= 3:
            top1_place += 1

        odds = top1.get('odds', 0)
        if odds > 0:
            payout = odds if fp == 1 else 0
            roi_data.append(payout)

    results['top1_win'] = top1_win
    results['top1_place'] = top1_place
    results['race_count'] = race_count
    results['top1_win_rate'] = top1_win / max(race_count, 1)
    results['top1_place_rate'] = top1_place / max(race_count, 1)
    results['top1_win_roi'] = sum(roi_data) / max(len(roi_data), 1)

    # --- Top3精度 ---
    top3_win = 0
    top3_place = 0
    for race_id, group in df_test.groupby('race_id'):
        if len(group) < 3:
            continue
        if higher_is_better:
            top3_idx = group[score_col].nlargest(3).index
        else:
            top3_idx = group[score_col].nsmallest(3).index
        top3 = group.loc[top3_idx]
        top3_win += int(top3['is_win'].sum())
        top3_place += int(top3['is_top3'].sum())

    results['top3_win'] = top3_win
    results['top3_place'] = top3_place
    results['top3_place_rate'] = top3_place / (race_count * 3) if race_count > 0 else 0

    # --- キャリブレーション品質 ---
    if cal_win is not None and f'{score_col}_win_prob' in df_test.columns:
        win_prob = df_test[f'{score_col}_win_prob'].values
        y_win = df_test['is_win'].values
        results['win_auc'] = round(roc_auc_score(y_win, win_prob), 4)
        results['win_brier'] = round(brier_score_loss(y_win, win_prob), 4)
        results['win_ece'] = round(compute_ece(y_win, win_prob), 4)

    if cal_place is not None and f'{score_col}_place_prob' in df_test.columns:
        place_prob = df_test[f'{score_col}_place_prob'].values
        y_place = df_test['is_top3'].values
        results['place_auc'] = round(roc_auc_score(y_place, place_prob), 4)
        results['place_brier'] = round(brier_score_loss(y_place, place_prob), 4)
        results['place_ece'] = round(compute_ece(y_place, place_prob), 4)

    return results


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Unified Performance Model Experiment")
    parser.add_argument("--train-years", default="2020-2024")
    parser.add_argument("--test-years", default="2025-2026")
    args = parser.parse_args()

    t0 = time.time()
    train_start, train_end = map(int, args.train_years.split("-"))
    test_start, test_end = map(int, args.test_years.split("-"))

    print("=" * 70)
    print("  Unified Performance Model Experiment")
    print(f"  Train: {train_start} ~ {train_end}")
    print(f"  Val:   2025-01 ~ 2025-02")
    print(f"  Test:  {test_start} ~ {test_end}")
    print(f"  Features: VALUE ({len(FEATURE_COLS_VALUE)} features, no market)")
    print("=" * 70)

    # === Load data ===
    (history_cache, trainer_index, jockey_index,
     date_index, pace_index, kb_ext_index, training_summary_index,
     race_level_index, pedigree_index, sire_stats_index) = load_data()

    pit_trainer_tl, pit_jockey_tl = build_pit_personnel_timeline()

    from ml.features.baba_features import load_baba_index
    baba_index = load_baba_index(range(train_start, test_end + 1))

    common_args = dict(
        date_index=date_index,
        history_cache=history_cache,
        trainer_index=trainer_index,
        jockey_index=jockey_index,
        pace_index=pace_index,
        kb_ext_index=kb_ext_index,
        training_summary_index=training_summary_index,
        race_level_index=race_level_index,
        pedigree_index=pedigree_index,
        sire_stats_index=sire_stats_index,
        pit_trainer_tl=pit_trainer_tl,
        pit_jockey_tl=pit_jockey_tl,
        baba_index=baba_index,
    )

    df_train = build_dataset(min_year=train_start, max_year=train_end, **common_args)
    df_val = build_dataset(min_year=2025, max_year=2025, min_month=1, max_month=2, **common_args)
    df_test = build_dataset(min_year=test_start, max_year=test_end, **common_args)

    # Margin targets
    print("\n[Margin] Computing target_margin...")
    add_margin_target_to_df(df_train, date_index, load_race_json)
    add_margin_target_to_df(df_val, date_index, load_race_json)
    add_margin_target_to_df(df_test, date_index, load_race_json)

    feature_cols = FEATURE_COLS_VALUE

    print(f"\n[Dataset] Train: {len(df_train):,}, Val: {len(df_val):,}, Test: {len(df_test):,}")
    print(f"[Features] {len(feature_cols)} features (VALUE, no market)")

    all_results = []

    # ============================================================
    # 1. Margin Regression (現行 AR)
    # ============================================================
    print("\n" + "=" * 70)
    print("  [1/3] Margin Regression (AR)")
    print("=" * 70)

    mask_m = {
        'train': df_train['target_margin'].notna(),
        'val': df_val['target_margin'].notna(),
        'test': df_test['target_margin'].notna(),
    }

    X_m_train = df_train.loc[mask_m['train'], feature_cols].values.astype(np.float32)
    y_m_train = df_train.loc[mask_m['train'], 'target_margin'].values
    X_m_val = df_val.loc[mask_m['val'], feature_cols].values.astype(np.float32)
    y_m_val = df_val.loc[mask_m['val'], 'target_margin'].values
    X_m_test = df_test.loc[mask_m['test'], feature_cols].values.astype(np.float32)
    y_m_test = df_test.loc[mask_m['test'], 'target_margin'].values

    print(f"  Train: {len(X_m_train):,}, Val: {len(X_m_val):,}, Test: {len(X_m_test):,}")

    ds_m_train = lgb.Dataset(X_m_train, label=y_m_train, feature_name=feature_cols)
    ds_m_val = lgb.Dataset(X_m_val, label=y_m_val, feature_name=feature_cols, reference=ds_m_train)

    model_margin = lgb.train(
        {**PARAMS_AR, 'metric': 'mae'},
        ds_m_train, num_boost_round=2000,
        valid_sets=[ds_m_val],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(200)],
    )

    pred_margin_test = model_margin.predict(df_test[feature_cols].values.astype(np.float32))
    df_test['pred_margin'] = pred_margin_test
    # Lower margin = better (0.0 = winner) → use negative for ranking
    df_test['score_margin'] = -pred_margin_test

    mae_m = mean_absolute_error(y_m_test, pred_margin_test[mask_m['test']])
    corr_m = np.corrcoef(y_m_test, pred_margin_test[mask_m['test']])[0, 1]
    print(f"  MAE={mae_m:.4f}s, Corr={corr_m:.4f}, BestIter={model_margin.best_iteration}")

    # Calibrate margin → probabilities (using val set)
    pred_margin_val = model_margin.predict(df_val[feature_cols].values.astype(np.float32))
    score_margin_val = -pred_margin_val

    prob_win_test, cal_margin_win = calibrate_scores(
        score_margin_val, df_val['is_win'].values,
        -pred_margin_test
    )
    prob_place_test, cal_margin_place = calibrate_scores(
        score_margin_val, df_val['is_top3'].values,
        -pred_margin_test
    )
    df_test['score_margin_win_prob'] = prob_win_test
    df_test['score_margin_place_prob'] = prob_place_test

    result_margin = evaluate_model(
        df_test, 'score_margin', higher_is_better=True,
        model_name='Margin Regression',
        cal_win=cal_margin_win, cal_place=cal_margin_place,
    )
    result_margin['mae'] = round(mae_m, 4)
    result_margin['corr'] = round(corr_m, 4)
    result_margin['best_iter'] = model_margin.best_iteration
    all_results.append(result_margin)

    # ============================================================
    # 2. LambdaRank
    # ============================================================
    print("\n" + "=" * 70)
    print("  [2/3] LambdaRank (Learning to Rank)")
    print("=" * 70)

    rel_train = make_relevance_labels(df_train)
    rel_val = make_relevance_labels(df_val)
    groups_train = make_lambdarank_groups(df_train)
    groups_val = make_lambdarank_groups(df_val)

    X_r_train = df_train[feature_cols].values.astype(np.float32)
    X_r_val = df_val[feature_cols].values.astype(np.float32)

    print(f"  Train: {len(X_r_train):,} ({len(groups_train):,} groups), "
          f"Val: {len(X_r_val):,} ({len(groups_val):,} groups)")
    print(f"  Relevance distribution (train): "
          f"5={np.sum(rel_train==5):,}, 4={np.sum(rel_train==4):,}, "
          f"3={np.sum(rel_train==3):,}, 2={np.sum(rel_train==2):,}, "
          f"1={np.sum(rel_train==1):,}, 0={np.sum(rel_train==0):,}")

    ds_r_train = lgb.Dataset(
        X_r_train, label=rel_train,
        group=groups_train, feature_name=feature_cols,
    )
    ds_r_val = lgb.Dataset(
        X_r_val, label=rel_val,
        group=groups_val, feature_name=feature_cols,
        reference=ds_r_train,
    )

    model_rank = lgb.train(
        PARAMS_RANK, ds_r_train, num_boost_round=2000,
        valid_sets=[ds_r_val],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(200)],
    )

    pred_rank_test = model_rank.predict(df_test[feature_cols].values.astype(np.float32))
    df_test['score_rank'] = pred_rank_test

    print(f"  BestIter={model_rank.best_iteration}")

    # Calibrate rank score → probabilities
    pred_rank_val = model_rank.predict(X_r_val)
    prob_win_r, cal_rank_win = calibrate_scores(
        pred_rank_val, df_val['is_win'].values,
        pred_rank_test
    )
    prob_place_r, cal_rank_place = calibrate_scores(
        pred_rank_val, df_val['is_top3'].values,
        pred_rank_test
    )
    df_test['score_rank_win_prob'] = prob_win_r
    df_test['score_rank_place_prob'] = prob_place_r

    result_rank = evaluate_model(
        df_test, 'score_rank', higher_is_better=True,
        model_name='LambdaRank',
        cal_win=cal_rank_win, cal_place=cal_rank_place,
    )
    result_rank['best_iter'] = model_rank.best_iteration
    all_results.append(result_rank)

    # ============================================================
    # 3. Finish Position Regression
    # ============================================================
    print("\n" + "=" * 70)
    print("  [3/3] Finish Position Regression")
    print("=" * 70)

    X_fp_train = df_train[feature_cols].values.astype(np.float32)
    y_fp_train = df_train['finish_position'].values.astype(np.float32)
    X_fp_val = df_val[feature_cols].values.astype(np.float32)
    y_fp_val = df_val['finish_position'].values.astype(np.float32)

    print(f"  Train: {len(X_fp_train):,}, Val: {len(X_fp_val):,}")
    print(f"  y_train: mean={y_fp_train.mean():.1f}, std={y_fp_train.std():.1f}")

    ds_fp_train = lgb.Dataset(X_fp_train, label=y_fp_train, feature_name=feature_cols)
    ds_fp_val = lgb.Dataset(X_fp_val, label=y_fp_val, feature_name=feature_cols, reference=ds_fp_train)

    model_fp = lgb.train(
        PARAMS_FP, ds_fp_train, num_boost_round=2000,
        valid_sets=[ds_fp_val],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(200)],
    )

    pred_fp_test = model_fp.predict(df_test[feature_cols].values.astype(np.float32))
    df_test['pred_fp'] = pred_fp_test
    # Lower finish position = better → use negative for ranking
    df_test['score_fp'] = -pred_fp_test

    mae_fp = mean_absolute_error(df_test['finish_position'].values, pred_fp_test)
    corr_fp = np.corrcoef(df_test['finish_position'].values, pred_fp_test)[0, 1]
    print(f"  MAE={mae_fp:.2f} positions, Corr={corr_fp:.4f}, BestIter={model_fp.best_iteration}")

    # Calibrate fp score → probabilities
    pred_fp_val = model_fp.predict(X_fp_val)
    prob_win_fp, cal_fp_win = calibrate_scores(
        -pred_fp_val, df_val['is_win'].values,
        -pred_fp_test
    )
    prob_place_fp, cal_fp_place = calibrate_scores(
        -pred_fp_val, df_val['is_top3'].values,
        -pred_fp_test
    )
    df_test['score_fp_win_prob'] = prob_win_fp
    df_test['score_fp_place_prob'] = prob_place_fp

    result_fp = evaluate_model(
        df_test, 'score_fp', higher_is_better=True,
        model_name='Finish Position Regression',
        cal_win=cal_fp_win, cal_place=cal_fp_place,
    )
    result_fp['mae'] = round(mae_fp, 4)
    result_fp['corr'] = round(corr_fp, 4)
    result_fp['best_iter'] = model_fp.best_iteration
    all_results.append(result_fp)

    # ============================================================
    # 4. Baseline: 現行 Model P + W (参照用)
    # ============================================================
    print("\n" + "=" * 70)
    print("  [Baseline] Current Model P (is_top3) + W (is_win)")
    print("=" * 70)

    # Model P
    from ml.experiment import train_model
    model_p, metrics_p, importance_p, pred_p, cal_p, pred_p_raw = train_model(
        df_train, df_val, df_test, feature_cols, PARAMS_P, 'is_top3', 'Cls_P'
    )
    df_test['pred_proba_p'] = pred_p

    # Model W
    model_w, metrics_w, importance_w, pred_w, cal_w, pred_w_raw = train_model(
        df_train, df_val, df_test, feature_cols, PARAMS_W, 'is_win', 'Cls_W'
    )
    df_test['pred_proba_w'] = pred_w

    # P results
    result_p = evaluate_model(
        df_test, 'pred_proba_p', higher_is_better=True,
        model_name='Model P (is_top3 binary)',
    )
    result_p['auc'] = metrics_p['auc']
    result_p['brier'] = metrics_p['brier_score']
    result_p['best_iter'] = metrics_p['best_iteration']

    # W results
    result_w = evaluate_model(
        df_test, 'pred_proba_w', higher_is_better=True,
        model_name='Model W (is_win binary)',
    )
    result_w['auc'] = metrics_w['auc']
    result_w['brier'] = metrics_w['brier_score']
    result_w['best_iter'] = metrics_w['best_iteration']

    # ============================================================
    # Summary
    # ============================================================
    elapsed = time.time() - t0
    print("\n" + "=" * 70)
    print("  COMPARISON RESULTS")
    print("=" * 70)

    # Main ranking comparison
    print(f"\n  {'Model':^30s} | {'Top1 Win':>10s} | {'Top1 Place':>10s} | {'Top1 ROI':>10s} | {'Top3 Place':>10s}")
    print(f"  {'-'*30}-+-{'-'*10}-+-{'-'*10}-+-{'-'*10}-+-{'-'*10}")
    for r in all_results:
        print(f"  {r['name']:30s} | "
              f"{r['top1_win_rate']*100:9.1f}% | "
              f"{r['top1_place_rate']*100:9.1f}% | "
              f"{r['top1_win_roi']*100:9.1f}% | "
              f"{r['top3_place_rate']*100:9.1f}%")

    # Baseline comparison
    print(f"\n  --- Baseline (current separate models) ---")
    print(f"  {result_p['name']:30s} | "
          f"{result_p['top1_win_rate']*100:9.1f}% | "
          f"{result_p['top1_place_rate']*100:9.1f}% | "
          f"{result_p['top1_win_roi']*100:9.1f}% | "
          f"{result_p['top3_place_rate']*100:9.1f}%")
    print(f"  {result_w['name']:30s} | "
          f"{result_w['top1_win_rate']*100:9.1f}% | "
          f"{result_w['top1_place_rate']*100:9.1f}% | "
          f"{result_w['top1_win_roi']*100:9.1f}% | "
          f"{result_w['top3_place_rate']*100:9.1f}%")

    # Calibration comparison
    print(f"\n  Calibration Quality (score → probability):")
    print(f"  {'Model':^30s} | {'Win AUC':>10s} | {'Win Brier':>10s} | {'Win ECE':>10s} | {'Place AUC':>10s} | {'Place Brier':>10s}")
    print(f"  {'-'*30}-+-{'-'*10}-+-{'-'*10}-+-{'-'*10}-+-{'-'*10}-+-{'-'*10}")
    for r in all_results:
        w_auc = f"{r.get('win_auc', 0)*100:9.2f}" if 'win_auc' in r else '       N/A'
        w_brier = f"{r.get('win_brier', 0):10.4f}" if 'win_brier' in r else '       N/A'
        w_ece = f"{r.get('win_ece', 0):10.4f}" if 'win_ece' in r else '       N/A'
        p_auc = f"{r.get('place_auc', 0)*100:9.2f}" if 'place_auc' in r else '       N/A'
        p_brier = f"{r.get('place_brier', 0):10.4f}" if 'place_brier' in r else '       N/A'
        print(f"  {r['name']:30s} | {w_auc}% | {w_brier} | {w_ece} | {p_auc}% | {p_brier}")

    print(f"\n  Baseline AUC (direct binary):")
    print(f"  Model P (is_top3): AUC={result_p.get('auc', 'N/A')}")
    print(f"  Model W (is_win):  AUC={result_w.get('auc', 'N/A')}")

    # Feature importance for best unified model
    print(f"\n  Feature Importance - LambdaRank (Top 15):")
    imp = model_rank.feature_importance(importance_type='gain')
    imp_pairs = sorted(zip(feature_cols, imp), key=lambda x: -x[1])
    for name, importance in imp_pairs[:15]:
        print(f"    {name:>35s}: {importance:,.0f}")

    print(f"\n  Feature Importance - Margin Regression (Top 15):")
    imp_m = model_margin.feature_importance(importance_type='gain')
    imp_pairs_m = sorted(zip(feature_cols, imp_m), key=lambda x: -x[1])
    for name, importance in imp_pairs_m[:15]:
        print(f"    {name:>35s}: {importance:,.0f}")

    # VB simulation
    print(f"\n  --- VB Simulation (gap-based pick quality) ---")
    for model_name, score_col, higher in [
        ('Margin', 'score_margin', True),
        ('LambdaRank', 'score_rank', True),
        ('FinishPos', 'score_fp', True),
        ('Model_P', 'pred_proba_p', True),
    ]:
        # Compute rank_v equivalent
        df_test[f'rank_{model_name}'] = df_test.groupby('race_id')[score_col].rank(
            ascending=not higher, method='min'
        )
        # gap = odds_rank - rank_v
        if 'odds_rank' in df_test.columns:
            df_test[f'gap_{model_name}'] = df_test['odds_rank'] - df_test[f'rank_{model_name}']

            # VB-like filtering: gap >= 3
            vb_picks = df_test[df_test[f'gap_{model_name}'] >= 3]
            vb_total = len(vb_picks)
            if vb_total > 0:
                vb_wins = int(vb_picks['is_win'].sum())
                vb_places = int(vb_picks['is_top3'].sum())
                vb_bet = vb_total * 100
                vb_win_return = float(vb_picks[vb_picks['is_win'] == 1]['odds'].sum()) * 100
                vb_roi = vb_win_return / vb_bet * 100 if vb_bet > 0 else 0
                print(f"  {model_name:12s} gap>=3: {vb_total:4d} picks, "
                      f"win={vb_wins} ({100*vb_wins/vb_total:.1f}%), "
                      f"place={vb_places} ({100*vb_places/vb_total:.1f}%), "
                      f"WinROI={vb_roi:.1f}%")
            else:
                print(f"  {model_name:12s} gap>=3: 0 picks")

    print(f"\n  Elapsed: {elapsed:.1f}s")
    print("=" * 70)


if __name__ == "__main__":
    main()
