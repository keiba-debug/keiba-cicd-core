#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
LambdaRank vs Binary Classification 比較実験

現行の二値分類（binary, is_win / is_top3）と
ランキング学習（LambdaRank）を同一データで比較する。

比較指標:
  1. ランキング精度: NDCG@1, @3, @5
  2. Top-N的中率: Top1勝率, Top3複勝率
  3. キャリブレーション: ECE (calibration後)
  4. バックテストROI: VB ROI (Place/Win)
  5. EV戦略ROI: rank_p + EV フィルター

Usage:
    python -m ml.experiment_lambdarank [--no-db]
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 既存パイプラインから再利用
from ml.experiment import (
    load_data, build_dataset,
    FEATURE_COLS_ALL, FEATURE_COLS_VALUE,
    PARAMS_P,
    calc_brier_score, calc_ece,
    calc_hit_analysis, calc_roi_analysis, calc_value_bet_analysis,
)

# === LambdaRank パラメータ ===
PARAMS_LR_ALL = {
    'objective': 'lambdarank',
    'metric': 'ndcg',
    'eval_at': [1, 3, 5],
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
    # label_gain: 固定5段階スケール (0-4) に合わせて設定
    # gain(i) = i: 線形ゲイン（デフォルト 2^i-1 は差が極端すぎる）
    'label_gain': [0, 1, 2, 3, 4],
}

PARAMS_LR_VALUE = {
    'objective': 'lambdarank',
    'metric': 'ndcg',
    'eval_at': [1, 3, 5],
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
    'label_gain': [0, 1, 2, 3, 4],
}


def prepare_ranking_data(df: pd.DataFrame):
    """DataFrameをLambdaRank用に準備: ソート + グループ + 関連度ラベル

    固定5段階スケール（レース頭数に依存しない）:
      1着: 4, 2着: 3, 3着: 2, 4-5着: 1, 6着以降: 0

    Returns:
        df_sorted: race_idでソートされたDataFrame
        relevance: 関連度ラベル (固定0-4スケール)
        groups: グループサイズ配列
    """
    df_sorted = df.sort_values('race_id').reset_index(drop=True)

    # 固定5段階: 頭数に依存しない一貫したスケール
    REL_MAP = {1: 4, 2: 3, 3: 2, 4: 1, 5: 1}

    relevance = []
    groups = []
    for race_id, group in df_sorted.groupby('race_id', sort=False):
        rel = group['finish_position'].map(lambda x: REL_MAP.get(x, 0))
        relevance.extend(rel.tolist())
        groups.append(len(group))

    return df_sorted, np.array(relevance, dtype=np.float32), np.array(groups)


def train_lambdarank(
    df_train: pd.DataFrame,
    df_val: pd.DataFrame,
    feature_cols: List[str],
    params: dict,
    model_name: str = 'LR',
) -> Tuple:
    """LambdaRankモデルを学習"""
    import lightgbm as lgb

    # ランキング用データ準備
    train_sorted, train_rel, train_groups = prepare_ranking_data(df_train)
    val_sorted, val_rel, val_groups = prepare_ranking_data(df_val)

    X_train = train_sorted[feature_cols]
    X_val = val_sorted[feature_cols]

    train_data = lgb.Dataset(X_train, label=train_rel, group=train_groups)
    valid_data = lgb.Dataset(X_val, label=val_rel, group=val_groups, reference=train_data)

    print(f"\n[Train] {model_name}: {len(feature_cols)} features, "
          f"train={len(X_train):,} ({len(train_groups):,} races), "
          f"val={len(X_val):,} ({len(val_groups):,} races)")

    model = lgb.train(
        params, train_data, num_boost_round=1500,
        valid_sets=[valid_data],
        callbacks=[
            lgb.early_stopping(stopping_rounds=100),
            lgb.log_evaluation(period=100),
        ],
    )

    print(f"[{model_name}] BestIter={model.best_iteration}")

    # 特徴量重要度
    importance = dict(zip(feature_cols, model.feature_importance(importance_type='gain')))

    return model, importance


def calibrate_scores(
    scores_val: np.ndarray,
    y_val: np.ndarray,
    scores_test: np.ndarray,
) -> np.ndarray:
    """IsotonicRegressionでスコアを確率にキャリブレーション"""
    from sklearn.isotonic import IsotonicRegression

    ir = IsotonicRegression(out_of_bounds='clip')
    ir.fit(scores_val, y_val)
    return ir.predict(scores_test), ir


def compute_ndcg(df: pd.DataFrame, score_col: str, k: int = 3) -> float:
    """レース単位のNDCG@kを計算"""
    ndcgs = []
    for race_id, group in df.groupby('race_id'):
        if len(group) < 2:
            continue
        # 関連度: prepare_ranking_dataと統一した0-4スケール
        rel_map = {1: 4, 2: 3, 3: 2, 4: 1, 5: 1}
        rels = group['finish_position'].map(lambda x: rel_map.get(x, 0)).values
        scores = group[score_col].values

        # スコアの降順でソート
        order = np.argsort(-scores)
        sorted_rels = rels[order]

        # DCG@k
        dcg = 0.0
        for i in range(min(k, len(sorted_rels))):
            dcg += (2 ** sorted_rels[i] - 1) / np.log2(i + 2)

        # IDCG@k
        ideal_rels = np.sort(rels)[::-1]
        idcg = 0.0
        for i in range(min(k, len(ideal_rels))):
            idcg += (2 ** ideal_rels[i] - 1) / np.log2(i + 2)

        if idcg > 0:
            ndcgs.append(dcg / idcg)

    return np.mean(ndcgs) if ndcgs else 0.0


def evaluate_model(
    df_test: pd.DataFrame,
    score_col: str,
    prob_win_col: str,
    prob_place_col: str,
    model_label: str,
) -> dict:
    """モデルを統一的に評価"""
    from sklearn.metrics import roc_auc_score

    results = {'model': model_label}

    # 1. NDCG
    for k in [1, 3, 5]:
        results[f'ndcg@{k}'] = round(compute_ndcg(df_test, score_col, k), 4)

    # 2. Top-N的中率
    df_test['_pred_rank'] = df_test.groupby('race_id')[score_col].rank(ascending=False, method='min')
    top1 = df_test[df_test['_pred_rank'] == 1]
    total_races = top1['race_id'].nunique()

    # Top1勝率
    top1_wins = top1[top1['is_win'] == 1]['race_id'].nunique()
    results['top1_win_rate'] = round(top1_wins / total_races, 4) if total_races > 0 else 0

    # Top1複勝率
    top1_places = top1[top1['is_top3'] == 1]['race_id'].nunique()
    results['top1_place_rate'] = round(top1_places / total_races, 4) if total_races > 0 else 0

    # Top3に1着馬が含まれる率
    top3 = df_test[df_test['_pred_rank'] <= 3]
    top3_hits = top3[top3['is_win'] == 1]['race_id'].nunique()
    results['top3_contains_winner'] = round(top3_hits / total_races, 4) if total_races > 0 else 0

    # 3. ROI
    top1_wins_data = top1[top1['is_win'] == 1]
    win_roi = top1_wins_data['odds'].sum() * 100 / (len(top1) * 100) * 100 if len(top1) > 0 else 0
    results['top1_win_roi'] = round(win_roi, 1)

    top1_places_data = top1[top1['is_top3'] == 1]

    def _place_odds(row):
        pl = row.get('place_odds_low')
        if pd.notna(pl) and pl > 0:
            return float(pl)
        return max(row['odds'] / 3.5, 1.1)

    place_return = top1_places_data.apply(_place_odds, axis=1).sum() * 100
    place_roi = place_return / (len(top1) * 100) * 100 if len(top1) > 0 else 0
    results['top1_place_roi'] = round(place_roi, 1)

    # 4. AUC (確率カラムがある場合)
    if prob_win_col in df_test.columns:
        try:
            results['auc_win'] = round(roc_auc_score(df_test['is_win'], df_test[prob_win_col]), 4)
        except Exception:
            results['auc_win'] = None
    if prob_place_col in df_test.columns:
        try:
            results['auc_place'] = round(roc_auc_score(df_test['is_top3'], df_test[prob_place_col]), 4)
        except Exception:
            results['auc_place'] = None

    # 5. キャリブレーション (確率カラムがある場合)
    if prob_win_col in df_test.columns:
        results['ece_win'] = round(calc_ece(df_test['is_win'].values, df_test[prob_win_col].values), 4)
        results['brier_win'] = round(calc_brier_score(df_test['is_win'].values, df_test[prob_win_col].values), 4)
    if prob_place_col in df_test.columns:
        results['ece_place'] = round(calc_ece(df_test['is_top3'].values, df_test[prob_place_col].values), 4)
        results['brier_place'] = round(calc_brier_score(df_test['is_top3'].values, df_test[prob_place_col].values), 4)

    # cleanup
    df_test.drop(columns=['_pred_rank'], inplace=True, errors='ignore')

    return results


def evaluate_vb_strategy(
    df_test: pd.DataFrame,
    rank_col: str,
    model_label: str,
) -> List[dict]:
    """Value Bet戦略を評価"""
    if rank_col not in df_test.columns or 'odds_rank' not in df_test.columns:
        return []

    results = []
    for min_gap in [2, 3, 4, 5]:
        total_bets = 0
        place_return = 0
        win_return = 0
        place_hits = 0
        win_hits = 0
        total_count = 0

        for race_id, group in df_test.groupby('race_id'):
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
                    # DB複勝オッズがあればそれを使用、なければ推定
                    place_low = row.get('place_odds_low')
                    if pd.notna(place_low) and place_low > 0:
                        place_odds = float(place_low)
                    else:
                        place_odds = max(row['odds'] / 3.5, 1.1)
                    place_return += place_odds * bet
                    place_hits += 1

        place_roi = place_return / total_bets * 100 if total_bets > 0 else 0
        win_roi = win_return / total_bets * 100 if total_bets > 0 else 0
        hit_rate = place_hits / total_count if total_count > 0 else 0

        results.append({
            'model': model_label,
            'min_gap': min_gap,
            'bet_count': total_count,
            'place_hits': place_hits,
            'place_hit_rate': round(hit_rate, 4),
            'place_roi': round(place_roi, 1),
            'win_hits': win_hits,
            'win_roi': round(win_roi, 1),
        })
    return results


def main():
    parser = argparse.ArgumentParser(description='LambdaRank vs Binary 比較実験')
    parser.add_argument('--no-db', action='store_true', help='DB odds未使用')
    parser.add_argument('--train-years', default='2020-2023')
    parser.add_argument('--val-years', default='2024-2024')
    parser.add_argument('--test-years', default='2025-2026')
    args = parser.parse_args()

    train_range = [int(x) for x in args.train_years.split('-')]
    val_range = [int(x) for x in args.val_years.split('-')]
    test_range = [int(x) for x in args.test_years.split('-')]

    print("=" * 80)
    print("  LambdaRank vs Binary Classification 比較実験")
    print(f"  Train: {train_range[0]}-{train_range[1]}, Val: {val_range[0]}-{val_range[1]}, "
          f"Test: {test_range[0]}-{test_range[1]}")
    print("=" * 80)

    # === データロード ===
    t0 = time.time()
    data = load_data()
    (history_cache, trainer_index, jockey_index,
     date_index, pace_index, kb_ext_index, training_summary_index, *_extra) = data

    use_db = not args.no_db

    # 共通データセット構築（1回だけ）
    df_train = build_dataset(date_index, history_cache, trainer_index, jockey_index,
                             pace_index, kb_ext_index, train_range[0], train_range[1],
                             use_db_odds=use_db, training_summary_index=training_summary_index)
    df_val = build_dataset(date_index, history_cache, trainer_index, jockey_index,
                           pace_index, kb_ext_index, val_range[0], val_range[1],
                           use_db_odds=use_db, training_summary_index=training_summary_index)
    df_test = build_dataset(date_index, history_cache, trainer_index, jockey_index,
                            pace_index, kb_ext_index, test_range[0], test_range[1],
                            use_db_odds=use_db, training_summary_index=training_summary_index)

    print(f"\n[Data] Load time: {time.time() - t0:.0f}s")
    print(f"  Train: {len(df_train):,} entries")
    print(f"  Val:   {len(df_val):,} entries")
    print(f"  Test:  {len(df_test):,} entries")

    import lightgbm as lgb

    all_results = []
    all_vb = []

    # ========================================
    # A. Binary Classification (現行)
    # ========================================
    print("\n" + "=" * 60)
    print("  [A] Binary Classification (現行)")
    print("=" * 60)

    # A-1: Place Binary (All features)
    from ml.experiment import train_model as train_binary
    model_a, metrics_a, imp_a, pred_a, _ = train_binary(
        df_train, df_val, df_test, FEATURE_COLS_ALL, PARAMS_P, 'is_top3', 'Binary_PM')
    df_test['pred_bin_pm'] = pred_a
    df_test['pred_rank_bin_pm'] = df_test.groupby('race_id')['pred_bin_pm'].rank(ascending=False, method='min')

    # A-2: Place Binary (Value features = Model P)
    model_v, metrics_v, imp_v, pred_v, _ = train_binary(
        df_train, df_val, df_test, FEATURE_COLS_VALUE, PARAMS_P, 'is_top3', 'Binary_PA')
    df_test['pred_bin_pa'] = pred_v
    df_test['pred_rank_bin_pa'] = df_test.groupby('race_id')['pred_bin_pa'].rank(ascending=False, method='min')

    # A-3: Win Binary (All features)
    from ml.experiment import PARAMS_W
    model_w, metrics_w, imp_w, pred_w, _ = train_binary(
        df_train, df_val, df_test, FEATURE_COLS_ALL, PARAMS_W, 'is_win', 'Binary_WM')
    df_test['pred_bin_wm'] = pred_w
    df_test['pred_rank_bin_wm'] = df_test.groupby('race_id')['pred_bin_wm'].rank(ascending=False, method='min')

    # A-4: Win Binary (Value features = Model W)
    model_w_v, metrics_w_v, imp_w_v, pred_w_v, _ = train_binary(
        df_train, df_val, df_test, FEATURE_COLS_VALUE, PARAMS_W, 'is_win', 'Binary_WA')
    df_test['pred_bin_wa'] = pred_w_v
    df_test['pred_rank_bin_wa'] = df_test.groupby('race_id')['pred_bin_wa'].rank(ascending=False, method='min')

    # Binary評価
    for score_col, prob_w, prob_p, label in [
        ('pred_bin_pm', 'pred_bin_wm', 'pred_bin_pm', 'Binary PM (Place,Mkt)'),
        ('pred_bin_pa', 'pred_bin_wa', 'pred_bin_pa', 'Binary PA (Place,Abl)'),
        ('pred_bin_wm', 'pred_bin_wm', 'pred_bin_pm', 'Binary WM (Win,Mkt)'),
        ('pred_bin_wa', 'pred_bin_wa', 'pred_bin_pa', 'Binary WA (Win,Abl)'),
    ]:
        res = evaluate_model(df_test, score_col, prob_w, prob_p, label)
        all_results.append(res)

    # Binary VB
    for rank_col, label in [
        ('pred_rank_bin_pa', 'Binary PA VB'),
        ('pred_rank_bin_wa', 'Binary WA VB'),
    ]:
        vb = evaluate_vb_strategy(df_test, rank_col, label)
        all_vb.extend(vb)

    # ========================================
    # B. LambdaRank
    # ========================================
    print("\n" + "=" * 60)
    print("  [B] LambdaRank")
    print("=" * 60)

    # B-1: LambdaRank (All features)
    model_lr_all, imp_lr_all = train_lambdarank(
        df_train, df_val, FEATURE_COLS_ALL, PARAMS_LR_ALL, 'LR_All')

    # テストセット予測
    test_sorted, test_rel, test_groups = prepare_ranking_data(df_test)
    scores_lr_all = model_lr_all.predict(test_sorted[FEATURE_COLS_ALL])

    # Valセット予測 (キャリブレーション用)
    val_sorted, val_rel, val_groups = prepare_ranking_data(df_val)
    scores_lr_all_val = model_lr_all.predict(val_sorted[FEATURE_COLS_ALL])

    # キャリブレーション: score → P(win), score → P(top3)
    prob_win_lr_all, _ = calibrate_scores(
        scores_lr_all_val, val_sorted['is_win'].values, scores_lr_all)
    prob_place_lr_all, _ = calibrate_scores(
        scores_lr_all_val, val_sorted['is_top3'].values, scores_lr_all)

    # テストDFにマッピング (test_sortedの順序でdf_testに戻す)
    test_sorted['score_lr_all'] = scores_lr_all
    test_sorted['prob_win_lr_all'] = prob_win_lr_all
    test_sorted['prob_place_lr_all'] = prob_place_lr_all
    test_sorted['pred_rank_lr_all'] = test_sorted.groupby('race_id')['score_lr_all'].rank(
        ascending=False, method='min')

    # B-2: LambdaRank (Value features)
    model_lr_val, imp_lr_val = train_lambdarank(
        df_train, df_val, FEATURE_COLS_VALUE, PARAMS_LR_VALUE, 'LR_Value')

    scores_lr_val = model_lr_val.predict(test_sorted[FEATURE_COLS_VALUE])
    scores_lr_val_v = model_lr_val.predict(val_sorted[FEATURE_COLS_VALUE])

    prob_win_lr_val, _ = calibrate_scores(
        scores_lr_val_v, val_sorted['is_win'].values, scores_lr_val)
    prob_place_lr_val, _ = calibrate_scores(
        scores_lr_val_v, val_sorted['is_top3'].values, scores_lr_val)

    test_sorted['score_lr_val'] = scores_lr_val
    test_sorted['prob_win_lr_val'] = prob_win_lr_val
    test_sorted['prob_place_lr_val'] = prob_place_lr_val
    test_sorted['pred_rank_lr_val'] = test_sorted.groupby('race_id')['score_lr_val'].rank(
        ascending=False, method='min')

    # LambdaRank評価
    for score_col, prob_w, prob_p, label in [
        ('score_lr_all', 'prob_win_lr_all', 'prob_place_lr_all', 'LambdaRank All (Mkt)'),
        ('score_lr_val', 'prob_win_lr_val', 'prob_place_lr_val', 'LambdaRank Val (Abl)'),
    ]:
        res = evaluate_model(test_sorted, score_col, prob_w, prob_p, label)
        all_results.append(res)

    # LambdaRank VB
    for rank_col, label in [
        ('pred_rank_lr_val', 'LR Value VB'),
    ]:
        vb = evaluate_vb_strategy(test_sorted, rank_col, label)
        all_vb.extend(vb)

    # ========================================
    # 結果比較表
    # ========================================
    print("\n" + "=" * 80)
    print("  比較結果サマリ")
    print("=" * 80)

    # メイン比較表
    print(f"\n  {'モデル':<28} {'NDCG@1':>7} {'NDCG@3':>7} {'NDCG@5':>7} "
          f"{'Top1勝':>6} {'Top1複':>6} {'単ROI':>6} {'複ROI':>6}")
    print(f"  {'-'*28} {'-'*7} {'-'*7} {'-'*7} {'-'*6} {'-'*6} {'-'*6} {'-'*6}")
    for r in all_results:
        ndcg1 = r.get('ndcg@1', 0)
        ndcg3 = r.get('ndcg@3', 0)
        ndcg5 = r.get('ndcg@5', 0)
        t1w = r.get('top1_win_rate', 0) * 100
        t1p = r.get('top1_place_rate', 0) * 100
        wroi = r.get('top1_win_roi', 0)
        proi = r.get('top1_place_roi', 0)
        print(f"  {r['model']:<28} {ndcg1:>6.4f} {ndcg3:>6.4f} {ndcg5:>6.4f} "
              f"{t1w:>5.1f}% {t1p:>5.1f}% {wroi:>5.1f}% {proi:>5.1f}%")

    # キャリブレーション比較
    print(f"\n  {'モデル':<28} {'AUC(Win)':>9} {'AUC(Place)':>10} "
          f"{'ECE(Win)':>9} {'ECE(Place)':>10} {'Brier(Win)':>10} {'Brier(Pl)':>10}")
    print(f"  {'-'*28} {'-'*9} {'-'*10} {'-'*9} {'-'*10} {'-'*10} {'-'*10}")
    for r in all_results:
        aw = r.get('auc_win')
        ap = r.get('auc_place')
        ew = r.get('ece_win')
        ep = r.get('ece_place')
        bw = r.get('brier_win')
        bp = r.get('brier_place')
        aw_s = f"{aw:.4f}" if aw is not None else "   N/A"
        ap_s = f"{ap:.4f}" if ap is not None else "    N/A"
        ew_s = f"{ew:.4f}" if ew is not None else "   N/A"
        ep_s = f"{ep:.4f}" if ep is not None else "    N/A"
        bw_s = f"{bw:.4f}" if bw is not None else "    N/A"
        bp_s = f"{bp:.4f}" if bp is not None else "    N/A"
        print(f"  {r['model']:<28} {aw_s:>9} {ap_s:>10} {ew_s:>9} {ep_s:>10} {bw_s:>10} {bp_s:>10}")

    # VB比較
    print(f"\n  Value Bet比較 (gap>=3):")
    print(f"  {'モデル':<20} {'件数':>5} {'Place的中率':>9} {'Place ROI':>9} {'Win ROI':>8}")
    print(f"  {'-'*20} {'-'*5} {'-'*9} {'-'*9} {'-'*8}")
    for v in all_vb:
        if v['min_gap'] == 3:
            hr = v['place_hit_rate'] * 100
            print(f"  {v['model']:<20} {v['bet_count']:>5} {hr:>8.1f}% {v['place_roi']:>8.1f}% {v['win_roi']:>7.1f}%")

    # 特徴量重要度比較 (Top10)
    print(f"\n  特徴量重要度 Top10 比較:")
    print(f"  {'Rank':>4} {'Binary PM':<25} {'LR All':<25} {'Binary PA':<25} {'LR Value':<25}")
    bin_pm_top = sorted(imp_a.items(), key=lambda x: -x[1])[:10]
    lr_all_top = sorted(imp_lr_all.items(), key=lambda x: -x[1])[:10]
    bin_pa_top = sorted(imp_v.items(), key=lambda x: -x[1])[:10]
    lr_val_top = sorted(imp_lr_val.items(), key=lambda x: -x[1])[:10]
    for i in range(10):
        bp = f"{bin_pm_top[i][0]}" if i < len(bin_pm_top) else ""
        la = f"{lr_all_top[i][0]}" if i < len(lr_all_top) else ""
        bv = f"{bin_pa_top[i][0]}" if i < len(bin_pa_top) else ""
        lv = f"{lr_val_top[i][0]}" if i < len(lr_val_top) else ""
        print(f"  {i+1:>4} {bp:<25} {la:<25} {bv:<25} {lv:<25}")

    # 総合評価
    total_time = time.time() - t0
    print(f"\n  総実行時間: {total_time:.0f}秒")

    # 結果保存
    output = {
        'config': {
            'train_years': args.train_years,
            'val_years': args.val_years,
            'test_years': args.test_years,
            'use_db': use_db,
        },
        'results': all_results,
        'vb_results': all_vb,
        'feature_importance': {
            'binary_pm_top20': sorted(imp_a.items(), key=lambda x: -x[1])[:20],
            'lr_all_top20': sorted(imp_lr_all.items(), key=lambda x: -x[1])[:20],
            'binary_pa_top20': sorted(imp_v.items(), key=lambda x: -x[1])[:20],
            'lr_value_top20': sorted(imp_lr_val.items(), key=lambda x: -x[1])[:20],
        },
    }

    from core import config
    out_path = config.ml_dir() / "lambdarank_experiment_result.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  結果保存: {out_path}")


if __name__ == "__main__":
    main()
