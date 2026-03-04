#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
着差回帰実験: LGBMRegressor vs 既存二値分類の比較

着差 (time_behind_winner) を直接予測する回帰モデルを学習し、
既存の二値分類モデル (is_top3 / is_win) とランキング性能・ROIを比較する。

回帰ターゲット:
  target_margin = (走破タイム - 1着タイム) 秒
  - 1着 = 0.0
  - 上限 5.0s (Huber loss delta=2.0 で外れ値ロバスト)
  - 同タイムは着順×0.02sオフセット

評価指標:
  1. 回帰精度: MAE, RMSE, R²
  2. ランキング精度: NDCG@1, @3, @5
  3. Top-N的中率: Top1勝率, Top3複勝率
  4. IsotonicRegression: 回帰スコア → P(win), P(top3) 変換
  5. バックテストROI: VB ROI (Place/Win)

Usage:
    python -m ml.experiment_regression [--no-db]
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

# 既存パイプラインから再利用
from ml.experiment import (
    load_data, build_dataset, load_race_json,
    FEATURE_COLS_ALL, FEATURE_COLS_VALUE, MARKET_FEATURES,
    PARAMS_P,
    calc_brier_score, calc_ece, calibrate_isotonic,
    calc_hit_analysis, calc_roi_analysis, calc_value_bet_analysis,
    VALUE_BET_MIN_GAP,
)
from ml.features.margin_target import add_margin_target_to_df
from core import config

# === 回帰モデル パラメータ ===
PARAMS_REG_ALL = {
    'objective': 'huber',
    'alpha': 2.0,  # Huber loss delta
    'metric': 'mae',
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

PARAMS_REG_VALUE = {
    'objective': 'huber',
    'alpha': 2.0,
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


def train_regression_model(
    df_train: pd.DataFrame,
    df_val: pd.DataFrame,
    df_test: pd.DataFrame,
    feature_cols: List[str],
    params: dict,
    model_name: str = 'Reg',
) -> Tuple:
    """LGBMRegressorを学習

    Returns:
        (model, metrics, importance, test_predictions)
    """
    import lightgbm as lgb

    # NaN target を除外
    mask_train = df_train['target_margin'].notna()
    mask_val = df_val['target_margin'].notna()
    mask_test = df_test['target_margin'].notna()

    X_train = df_train.loc[mask_train, feature_cols]
    y_train = df_train.loc[mask_train, 'target_margin']
    X_val = df_val.loc[mask_val, feature_cols]
    y_val = df_val.loc[mask_val, 'target_margin']
    X_test = df_test.loc[mask_test, feature_cols]
    y_test = df_test.loc[mask_test, 'target_margin']

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

    # テスト予測
    y_pred = model.predict(X_test)

    # 回帰指標
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)
    corr = np.corrcoef(y_test, y_pred)[0, 1]

    print(f"[{model_name}] MAE={mae:.4f}s, RMSE={rmse:.4f}s, R2={r2:.4f}, Corr={corr:.4f}")
    print(f"[{model_name}] BestIter={model.best_iteration}")

    # 予測値を全テストデータに展開（NaN targetの馬にも予測する）
    all_pred = model.predict(df_test[feature_cols])

    metrics = {
        'mae': round(mae, 4),
        'rmse': round(rmse, 4),
        'r2': round(r2, 4),
        'correlation': round(corr, 4),
        'best_iteration': model.best_iteration,
        'train_size': len(X_train),
        'val_size': len(X_val),
        'test_size': len(X_test),
    }

    importance = dict(zip(feature_cols, model.feature_importance(importance_type='gain')))

    return model, metrics, importance, all_pred


def compute_ndcg(df: pd.DataFrame, pred_col: str, k_list: List[int] = [1, 3, 5]) -> Dict[str, float]:
    """NDCG@kをレース単位で計算

    回帰の場合: predicted margin が小さい馬ほど上位
    relevance: finish_position → {1:4, 2:3, 3:2, 4:1, 5:1, else:0}
    """
    rel_map = {1: 4, 2: 3, 3: 2, 4: 1, 5: 1}
    results = {}

    for k in k_list:
        ndcg_scores = []
        for race_id, group in df.groupby('race_id'):
            if len(group) < 2:
                continue

            # 予測順位（marginが小さい順 = ascending）
            sorted_by_pred = group.sort_values(pred_col, ascending=True)
            # 理想順位（着順の小さい順）
            sorted_by_actual = group.sort_values('finish_position', ascending=True)

            # DCG@k
            dcg = 0.0
            for i, (_, row) in enumerate(sorted_by_pred.head(k).iterrows()):
                rel = rel_map.get(row['finish_position'], 0)
                dcg += rel / np.log2(i + 2)

            # IDCG@k
            idcg = 0.0
            for i, (_, row) in enumerate(sorted_by_actual.head(k).iterrows()):
                rel = rel_map.get(row['finish_position'], 0)
                idcg += rel / np.log2(i + 2)

            if idcg > 0:
                ndcg_scores.append(dcg / idcg)

        results[f'ndcg@{k}'] = round(np.mean(ndcg_scores), 4) if ndcg_scores else 0.0
    return results


def calc_regression_hit_analysis(df: pd.DataFrame, pred_col: str) -> List[dict]:
    """回帰モデルのTop-N的中率（margin が小さい順 = 上位）"""
    # 予測marginのランク (ascending: marginが小さい方が上位)
    df['reg_rank'] = df.groupby('race_id')[pred_col].rank(ascending=True, method='min')

    results = []
    for top_n in [1, 2, 3]:
        picks = df[df['reg_rank'] <= top_n]
        total = picks['race_id'].nunique()
        if top_n == 1:
            hits = picks[picks['is_win'] == 1]['race_id'].nunique()
        else:
            hits = picks[picks['is_top3'] == 1]['race_id'].nunique()

        hit_rate = hits / total if total > 0 else 0
        results.append({
            'top_n': top_n,
            'hit_rate': round(hit_rate, 4),
            'hits': int(hits),
            'total': int(total),
        })
    return results


def calc_regression_roi(df: pd.DataFrame, pred_col: str) -> dict:
    """回帰モデルTop1のROI分析（margin小さい順）"""
    from ml.experiment import _get_place_odds

    df['reg_rank'] = df.groupby('race_id')[pred_col].rank(ascending=True, method='min')
    top1 = df[df['reg_rank'] == 1].copy()

    total_bets = len(top1) * 100
    win_return = top1[top1['is_win'] == 1]['odds'].sum() * 100
    win_roi = win_return / total_bets * 100 if total_bets > 0 else 0

    place_hits = top1[top1['is_top3'] == 1]
    place_return = place_hits.apply(_get_place_odds, axis=1).sum() * 100
    place_roi = place_return / total_bets * 100 if total_bets > 0 else 0

    return {
        'top1_win_roi': round(win_roi, 1),
        'top1_place_roi': round(place_roi, 1),
        'top1_bets': len(top1),
    }


def calc_regression_vb_analysis(
    df: pd.DataFrame,
    reg_rank_col: str = 'reg_rank_ar',
) -> List[dict]:
    """回帰モデルのValue Bet分析

    reg_rank_ar (Value回帰モデル) × odds_rank の乖離
    """
    from ml.experiment import _get_place_odds

    if reg_rank_col not in df.columns or 'odds_rank' not in df.columns:
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
            candidates = group[
                (group[reg_rank_col] <= 3) &
                (group['odds_rank'] >= group[reg_rank_col] + min_gap)
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


def derive_probabilities(
    df: pd.DataFrame,
    reg_pred_col: str,
    label_col: str,
    model_name: str,
) -> Tuple[np.ndarray, object]:
    """回帰スコアからIsotonicRegressionで確率を導出

    margin が小さい馬ほど勝ちやすい → neg_margin = -margin を使って
    IsotonicRegressionで P(label=1 | neg_margin) をfit

    val/test split は df['_split'] カラムで区別
    """
    from sklearn.isotonic import IsotonicRegression

    val_mask = df['_split'] == 'val'
    test_mask = df['_split'] == 'test'

    # neg_margin: 値が大きいほど勝ちやすい（IsotonicRegressionの単調増加方向に合わせる）
    neg_pred_val = -df.loc[val_mask, reg_pred_col].values
    neg_pred_test = -df.loc[test_mask, reg_pred_col].values
    y_val = df.loc[val_mask, label_col].values
    y_test = df.loc[test_mask, label_col].values

    ir = IsotonicRegression(out_of_bounds='clip')
    ir.fit(neg_pred_val, y_val)
    proba_test = ir.predict(neg_pred_test)

    # 評価
    from sklearn.metrics import roc_auc_score
    auc = roc_auc_score(y_test, proba_test)
    ece = calc_ece(y_test, proba_test)
    brier = calc_brier_score(y_test, proba_test)

    print(f"[{model_name}→{label_col}] AUC={auc:.4f}, ECE={ece:.4f}, Brier={brier:.4f}")

    return proba_test, ir


def parse_year_range(s: str) -> Tuple[int, int]:
    if '-' in s:
        parts = s.split('-', 1)
        return int(parts[0]), int(parts[1])
    y = int(s)
    return y, y


def main():
    parser = argparse.ArgumentParser(description='着差回帰実験')
    parser.add_argument('--train-years', default='2020-2023', help='Training year range')
    parser.add_argument('--val-years', default='2024', help='Validation year range')
    parser.add_argument('--test-years', default='2025-2026', help='Test year range')
    parser.add_argument('--no-db', action='store_true', help='DBオッズ未使用')
    parser.add_argument('--cap', type=float, default=5.0, help='着差上限 (秒)')
    args = parser.parse_args()

    # Windows cp932 対策
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')

    train_min, train_max = parse_year_range(args.train_years)
    val_min, val_max = parse_year_range(args.val_years)
    test_min, test_max = parse_year_range(args.test_years)
    use_db_odds = not args.no_db

    print(f"\n{'='*60}")
    print(f"  着差回帰実験 (Margin Regression)")
    print(f"  Train: {train_min}-{train_max}")
    print(f"  Val:   {val_min}-{val_max}")
    print(f"  Test:  {test_min}-{test_max}")
    print(f"  Margin cap: {args.cap}s")
    print(f"  Loss: Huber (delta=2.0)")
    print(f"  DB Odds: {'ON' if use_db_odds else 'OFF'}")
    print(f"{'='*60}\n")

    t0 = time.time()

    # === データロード（既存パイプラインを再利用） ===
    (history_cache, trainer_index, jockey_index,
     date_index, pace_index, kb_ext_index, training_summary_index, *_extra) = load_data()

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

    # === target_margin 追加 ===
    print("\n[Margin] Computing target_margin for all splits...")
    for label, df in [('train', df_train), ('val', df_val), ('test', df_test)]:
        print(f"  {label}:")
        add_margin_target_to_df(df, date_index, load_race_json, cap=args.cap)

    # ターゲット分布
    for label, df in [('train', df_train), ('val', df_val), ('test', df_test)]:
        valid = df['target_margin'].dropna()
        print(f"  [{label}] target_margin: mean={valid.mean():.3f}s, "
              f"median={valid.median():.3f}s, std={valid.std():.3f}s, "
              f"max={valid.max():.3f}s, zeros={int((valid == 0).sum())}")

    print(f"\n[Dataset] Train: {len(df_train):,} entries from "
          f"{df_train['race_id'].nunique():,} races")
    print(f"[Dataset] Val:   {len(df_val):,} entries from "
          f"{df_val['race_id'].nunique():,} races")
    print(f"[Dataset] Test:  {len(df_test):,} entries from "
          f"{df_test['race_id'].nunique():,} races")

    # ===================================================================
    # Part 1: 回帰モデル学習
    # ===================================================================
    print(f"\n{'='*60}")
    print(f"  Part 1: 回帰モデル学習")
    print(f"{'='*60}")

    # Reg A: 全特徴量
    model_ra, metrics_ra, imp_ra, pred_ra = train_regression_model(
        df_train, df_val, df_test, FEATURE_COLS_ALL,
        PARAMS_REG_ALL, 'Reg_A',
    )

    # Reg AR: Value特徴量
    model_rb, metrics_rb, imp_rb, pred_rb = train_regression_model(
        df_train, df_val, df_test, FEATURE_COLS_VALUE,
        PARAMS_REG_VALUE, 'Reg_AR',
    )

    df_test['pred_margin_a'] = pred_ra
    df_test['pred_margin_ar'] = pred_rb

    # ===================================================================
    # Part 2: 既存二値分類モデルの学習 (比較用)
    # ===================================================================
    print(f"\n{'='*60}")
    print(f"  Part 2: 既存二値分類モデル (比較ベースライン)")
    print(f"{'='*60}")

    from ml.experiment import train_model, PARAMS_W

    # Place models
    _, metrics_ca, _, pred_ca, _ = train_model(
        df_train, df_val, df_test, FEATURE_COLS_ALL, PARAMS_P, 'is_top3', 'Place_All'
    )
    _, metrics_cb, _, pred_cb, _ = train_model(
        df_train, df_val, df_test, FEATURE_COLS_VALUE, PARAMS_P, 'is_top3', 'Place'
    )

    # Win models
    _, metrics_cw, _, pred_cw, _ = train_model(
        df_train, df_val, df_test, FEATURE_COLS_ALL, PARAMS_W, 'is_win', 'Win_All'
    )
    _, metrics_cwv, _, pred_cwv, _ = train_model(
        df_train, df_val, df_test, FEATURE_COLS_VALUE, PARAMS_W, 'is_win', 'Win'
    )

    df_test['pred_proba_p_all'] = pred_ca
    df_test['pred_proba_p'] = pred_cb
    df_test['pred_proba_w_all'] = pred_cw
    df_test['pred_proba_w'] = pred_cwv

    df_test['pred_rank_p_all'] = df_test.groupby('race_id')['pred_proba_p_all'].rank(ascending=False, method='min')
    df_test['pred_rank_p'] = df_test.groupby('race_id')['pred_proba_p'].rank(ascending=False, method='min')

    # 回帰ランク
    df_test['reg_rank_a'] = df_test.groupby('race_id')['pred_margin_a'].rank(ascending=True, method='min')
    df_test['reg_rank_ar'] = df_test.groupby('race_id')['pred_margin_ar'].rank(ascending=True, method='min')

    # ===================================================================
    # Part 3: IsotonicRegression で確率導出
    # ===================================================================
    print(f"\n{'='*60}")
    print(f"  Part 3: 回帰→確率変換 (IsotonicRegression)")
    print(f"{'='*60}")

    # val/test 結合して _split でマーク
    df_val_tmp = df_val.copy()
    df_test_tmp = df_test.copy()
    df_val_tmp['_split'] = 'val'
    df_test_tmp['_split'] = 'test'

    # val の回帰予測も必要
    pred_ra_val = model_ra.predict(df_val[FEATURE_COLS_ALL])
    pred_rb_val = model_rb.predict(df_val[FEATURE_COLS_VALUE])
    df_val_tmp['pred_margin_a'] = pred_ra_val
    df_val_tmp['pred_margin_ar'] = pred_rb_val

    df_combined = pd.concat([df_val_tmp, df_test_tmp], ignore_index=True)

    # Reg A → P(top3), P(win)
    proba_ra_top3, _ = derive_probabilities(df_combined, 'pred_margin_a', 'is_top3', 'Reg_A')
    proba_ra_win, _ = derive_probabilities(df_combined, 'pred_margin_a', 'is_win', 'Reg_A')

    # Reg AR → P(top3), P(win)
    proba_rb_top3, _ = derive_probabilities(df_combined, 'pred_margin_ar', 'is_top3', 'Reg_AR')
    proba_rb_win, _ = derive_probabilities(df_combined, 'pred_margin_ar', 'is_win', 'Reg_AR')

    # df_test に確率を付加（combined の test 部分のみ）
    test_idx = df_combined['_split'] == 'test'
    df_test['reg_proba_a_top3'] = proba_ra_top3
    df_test['reg_proba_a_win'] = proba_ra_win
    df_test['reg_proba_b_top3'] = proba_rb_top3
    df_test['reg_proba_b_win'] = proba_rb_win

    # ===================================================================
    # Part 4: 比較分析
    # ===================================================================
    print(f"\n{'='*60}")
    print(f"  Part 4: 比較分析")
    print(f"{'='*60}")

    # --- NDCG ---
    print(f"\n  --- NDCG Comparison ---")
    # 分類は確率が高い順 → -pred_proba でNDCG計算
    df_test['neg_pred_p_all'] = -df_test['pred_proba_p_all']
    df_test['neg_pred_p'] = -df_test['pred_proba_p']

    ndcg_cls_a = compute_ndcg(df_test, 'neg_pred_p_all')
    ndcg_cls_b = compute_ndcg(df_test, 'neg_pred_p')
    ndcg_reg_a = compute_ndcg(df_test, 'pred_margin_a')
    ndcg_reg_b = compute_ndcg(df_test, 'pred_margin_ar')

    print(f"  {'Model':<15} {'NDCG@1':>8} {'NDCG@3':>8} {'NDCG@5':>8}")
    print(f"  {'-'*43}")
    for label, ndcg in [('Place All', ndcg_cls_a), ('Place Value', ndcg_cls_b),
                         ('Reg A (All)', ndcg_reg_a), ('Reg AR (Value)', ndcg_reg_b)]:
        print(f"  {label:<15} {ndcg['ndcg@1']:>8.4f} {ndcg['ndcg@3']:>8.4f} {ndcg['ndcg@5']:>8.4f}")

    # --- Hit Analysis ---
    print(f"\n  --- Hit Rate Comparison ---")
    hit_cls_a = calc_hit_analysis(df_test, 'pred_proba_p_all')
    hit_cls_b = calc_hit_analysis(df_test, 'pred_proba_p')
    hit_reg_a = calc_regression_hit_analysis(df_test, 'pred_margin_a')
    hit_reg_b = calc_regression_hit_analysis(df_test, 'pred_margin_ar')

    print(f"  {'Model':<15} {'Top1 Win':>10} {'Top2 Top3':>10} {'Top3 Top3':>10}")
    print(f"  {'-'*47}")
    for label, hits in [('Place All', hit_cls_a), ('Place', hit_cls_b),
                         ('Reg A', hit_reg_a), ('Reg AR', hit_reg_b)]:
        print(f"  {label:<15} {hits[0]['hit_rate']:>9.1%} {hits[1]['hit_rate']:>9.1%} {hits[2]['hit_rate']:>9.1%}")

    # --- ROI ---
    print(f"\n  --- ROI Comparison (Top1) ---")
    roi_cls_a = calc_roi_analysis(df_test, 'pred_proba_p_all')
    roi_cls_b = calc_roi_analysis(df_test, 'pred_proba_p')
    roi_reg_a = calc_regression_roi(df_test, 'pred_margin_a')
    roi_reg_b = calc_regression_roi(df_test, 'pred_margin_ar')

    print(f"  {'Model':<15} {'Win ROI':>10} {'Place ROI':>12}")
    print(f"  {'-'*39}")
    for label, roi in [('Place All', roi_cls_a), ('Place', roi_cls_b),
                         ('Reg A', roi_reg_a), ('Reg AR', roi_reg_b)]:
        print(f"  {label:<15} {roi['top1_win_roi']:>9.1f}% {roi['top1_place_roi']:>11.1f}%")

    # --- Value Bet (Place) ---
    print(f"\n  --- Value Bet Analysis (Place) ---")
    vb_cls = calc_value_bet_analysis(df_test, rank_col='pred_rank_p')
    vb_reg = calc_regression_vb_analysis(df_test, reg_rank_col='reg_rank_ar')

    print(f"  {'Gap':<6} {'Place Bets':>10} {'Place ROI':>10} {'Reg_AR Bets':>10} {'Reg_AR ROI':>10} {'差分':>8}")
    print(f"  {'-'*56}")
    for vc, vr in zip(vb_cls, vb_reg):
        diff = vr['place_roi'] - vc['place_roi']
        marker = " ***" if diff > 0 else ""
        print(f"  >={vc['min_gap']:<4} {vc['bet_count']:>10} {vc['place_roi']:>9.1f}% "
              f"{vr['bet_count']:>10} {vr['place_roi']:>9.1f}% {diff:>+7.1f}%{marker}")

    # --- 回帰→確率 vs 直接分類 ---
    print(f"\n  --- 回帰→確率 vs 直接分類 (AUC/ECE) ---")
    from sklearn.metrics import roc_auc_score

    y_top3 = df_test['is_top3'].values
    y_win = df_test['is_win'].values

    print(f"  {'Model':<20} {'Target':>8} {'AUC':>8} {'ECE':>8} {'Brier':>8}")
    print(f"  {'-'*56}")

    comparisons = [
        ('Place All (direct)', 'is_top3', pred_ca, y_top3),
        ('Reg A→iso', 'is_top3', proba_ra_top3, y_top3),
        ('Place (direct)', 'is_top3', pred_cb, y_top3),
        ('Reg AR→iso', 'is_top3', proba_rb_top3, y_top3),
        ('Win All (direct)', 'is_win', pred_cw, y_win),
        ('Reg A→iso', 'is_win', proba_ra_win, y_win),
        ('Win (direct)', 'is_win', pred_cwv, y_win),
        ('Reg AR→iso', 'is_win', proba_rb_win, y_win),
    ]

    for label, target, pred, y_true in comparisons:
        auc = roc_auc_score(y_true, pred)
        ece = calc_ece(y_true, pred)
        brier = calc_brier_score(y_true, pred)
        print(f"  {label:<20} {target:>8} {auc:>8.4f} {ece:>8.4f} {brier:>8.4f}")

    # --- Feature Importance ---
    print(f"\n  Feature Importance (Reg A Top 10):")
    sorted_imp = sorted(imp_ra.items(), key=lambda x: x[1], reverse=True)[:10]
    for fname, imp in sorted_imp:
        print(f"    {fname:>30}: {imp:,.0f}")

    print(f"\n  Feature Importance (Reg AR Top 10):")
    sorted_imp = sorted(imp_rb.items(), key=lambda x: x[1], reverse=True)[:10]
    for fname, imp in sorted_imp:
        print(f"    {fname:>30}: {imp:,.0f}")

    # ===================================================================
    # 結果保存
    # ===================================================================
    elapsed = time.time() - t0

    result = {
        'experiment': 'margin_regression',
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'elapsed_sec': round(elapsed, 1),
        'margin_cap': args.cap,
        'split': {
            'train': f"{train_min}-{train_max}",
            'val': f"{val_min}-{val_max}",
            'test': f"{test_min}-{test_max}",
        },
        'regression': {
            'reg_a': metrics_ra,
            'reg_ar': metrics_rb,
        },
        'classification_baseline': {
            'place_all': metrics_ca,
            'place': metrics_cb,
            'win_all': metrics_cw,
            'win': metrics_cwv,
        },
        'ndcg': {
            'place_all': ndcg_cls_a,
            'place': ndcg_cls_b,
            'reg_a': ndcg_reg_a,
            'reg_ar': ndcg_reg_b,
        },
        'roi': {
            'place_all': roi_cls_a,
            'place': roi_cls_b,
            'reg_a': roi_reg_a,
            'reg_ar': roi_reg_b,
        },
        'value_bet_place': {
            'place': vb_cls,
            'reg_ar': vb_reg,
        },
        'feature_importance_reg_a': [
            {'feature': f, 'importance': int(i)}
            for f, i in sorted(imp_ra.items(), key=lambda x: -x[1])[:20]
        ],
        'feature_importance_reg_ar': [
            {'feature': f, 'importance': int(i)}
            for f, i in sorted(imp_rb.items(), key=lambda x: -x[1])[:20]
        ],
    }

    result_path = config.ml_dir() / "experiment_regression_result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n[Save] Result saved to {result_path}")
    print(f"\n  Total elapsed: {elapsed:.0f}s ({elapsed/60:.1f}min)")


if __name__ == '__main__':
    main()
