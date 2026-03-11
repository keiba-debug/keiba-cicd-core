#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ML Experiment: Performance Change Prediction (IDM diff 4-class)

前走比IDM差分を4カテゴリに分類するLightGBM multiclassモデル。
experiment.pyのデータロード・特徴量計算パイプラインを流用し、
ターゲット変数だけをIDM差分の4クラスに変更。

カテゴリ:
  0: 大幅上昇 (IDM diff >= +10)
  1: 上昇     (IDM diff +4 ~ +9)
  2: 平行線   (IDM diff -4 ~ +3)
  3: 下降     (IDM diff <= -5)

Usage:
    python -m ml.experiment_performance
    python -m ml.experiment_performance --train-years 2020-2024 --test-years 2025.03-2026.02
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from ml.experiment import (
    load_data, build_dataset, build_pit_personnel_timeline,
    FEATURE_COLS_ALL, FEATURE_COLS_VALUE, MARKET_FEATURES,
)
from ml.features.career_features import compute_career_features, CAREER_FEATURE_COLS

# === カテゴリ閾値 (analyze_idm_diff.py Phase D の結果) ===
# 大幅上昇: >= +10  (15.0%)
# 上昇:     +4 ~ +9 (20.3%)
# 平行線:   -4 ~ +3 (38.3%)
# 下降:     <= -5    (26.4%)
THRESH_BIG_UP = 10
THRESH_UP = 4
THRESH_DOWN = -5

LABEL_NAMES_4 = ['big_up', 'up', 'stable', 'down']
LABEL_JP_4 = ['大幅上昇', '上昇', '平行線', '下降']

LABEL_NAMES_3 = ['up', 'stable', 'down']
LABEL_JP_3 = ['上昇', '平行線', '下降']

# グローバル設定（main()で上書きされる）
LABEL_NAMES = LABEL_NAMES_4
LABEL_JP = LABEL_JP_4
NUM_CLASSES = 4


def idm_diff_to_label_4(diff: float) -> int:
    """IDM差分を4カテゴリラベルに変換"""
    if diff >= THRESH_BIG_UP:
        return 0  # 大幅上昇
    elif diff >= THRESH_UP:
        return 1  # 上昇
    elif diff > THRESH_DOWN:
        return 2  # 平行線
    else:
        return 3  # 下降


def idm_diff_to_label_3(diff: float) -> int:
    """IDM差分を3カテゴリラベルに変換（上昇/平行線/下降）"""
    if diff >= THRESH_UP:
        return 0  # 上昇 (big_up + up統合)
    elif diff > THRESH_DOWN:
        return 1  # 平行線
    else:
        return 2  # 下降


# デフォルトは4クラス（main()で切り替え）
idm_diff_to_label = idm_diff_to_label_4


def add_idm_diff_target(df: pd.DataFrame, jrdb_sed_index: dict,
                         history_cache: dict) -> pd.DataFrame:
    """DataFrameにIDM差分ターゲット変数を追加

    各出走馬について:
      1. 当該レースのSED IDMを取得
      2. 前走(horse_historyから1つ前)のSED IDMを取得
      3. diff = current - prev をカテゴリ化

    Returns:
        IDM差分が計算できた行のみを含むDataFrame
    """
    idm_diffs = []
    labels = []
    valid_mask = []

    for _, row in df.iterrows():
        ketto_num = row.get('ketto_num', '')
        race_date = row.get('date', '')

        # 当該レースのSED IDM
        curr_key = f"{ketto_num}_{race_date}"
        curr_sed = jrdb_sed_index.get(curr_key)
        if not curr_sed or not curr_sed.get('idm'):
            valid_mask.append(False)
            idm_diffs.append(np.nan)
            labels.append(-1)
            continue

        curr_idm = curr_sed['idm']
        if curr_idm == 0:
            valid_mask.append(False)
            idm_diffs.append(np.nan)
            labels.append(-1)
            continue

        # 前走のSED IDM (horse_historyから当該レース前の最新走を取得)
        runs = history_cache.get(ketto_num, [])
        past_runs = [r for r in runs if r['race_date'] < race_date]
        if not past_runs:
            valid_mask.append(False)
            idm_diffs.append(np.nan)
            labels.append(-1)
            continue

        # 最新の前走
        prev_run = max(past_runs, key=lambda r: r['race_date'])
        prev_key = f"{ketto_num}_{prev_run['race_date']}"
        prev_sed = jrdb_sed_index.get(prev_key)
        if not prev_sed or not prev_sed.get('idm'):
            valid_mask.append(False)
            idm_diffs.append(np.nan)
            labels.append(-1)
            continue

        prev_idm = prev_sed['idm']
        if prev_idm == 0:
            valid_mask.append(False)
            idm_diffs.append(np.nan)
            labels.append(-1)
            continue

        diff = curr_idm - prev_idm
        idm_diffs.append(diff)
        labels.append(idm_diff_to_label(diff))
        valid_mask.append(True)

    df = df.copy()
    df['idm_diff'] = idm_diffs
    df['perf_label'] = labels

    # 有効な行のみ残す
    df_valid = df[valid_mask].copy()
    return df_valid


def train_multiclass_model(
    df_train: pd.DataFrame,
    df_val: pd.DataFrame,
    df_test: pd.DataFrame,
    feature_cols: List[str],
    label_col: str = 'perf_label',
    num_classes: int = 4,
) -> Tuple:
    """LightGBM multiclass モデルを学習・評価"""
    import lightgbm as lgb
    from sklearn.metrics import (
        accuracy_score, log_loss, f1_score, confusion_matrix,
        classification_report,
    )

    params = {
        'objective': 'multiclass',
        'num_class': num_classes,
        'metric': 'multi_logloss',
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
        # クラス不均衡に対応
        'is_unbalance': True,
    }

    X_train = df_train[feature_cols]
    y_train = df_train[label_col]
    X_val = df_val[feature_cols]
    y_val = df_val[label_col]
    X_test = df_test[feature_cols]
    y_test = df_test[label_col]

    train_data = lgb.Dataset(X_train, label=y_train)
    valid_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

    print(f"\n[Train] Performance model: {len(feature_cols)} features, "
          f"train={len(X_train):,}, val={len(X_val):,}, test={len(X_test):,}")

    # クラス分布
    for split_name, y in [('Train', y_train), ('Val', y_val), ('Test', y_test)]:
        counts = y.value_counts().sort_index()
        dist = ', '.join(f"{LABEL_JP[i]}:{counts.get(i, 0):,}({counts.get(i, 0)/len(y)*100:.1f}%)"
                         for i in range(num_classes))
        print(f"  {split_name}: {dist}")

    model = lgb.train(
        params, train_data, num_boost_round=1500,
        valid_sets=[valid_data],
        callbacks=[
            lgb.early_stopping(stopping_rounds=50),
            lgb.log_evaluation(period=200),
        ],
    )

    # 予測（各クラスの確率）
    y_pred_proba = model.predict(X_test)  # shape: (n, 4)
    y_pred = np.argmax(y_pred_proba, axis=1)

    # === 評価 ===
    acc = accuracy_score(y_test, y_pred)
    macro_f1 = f1_score(y_test, y_pred, average='macro')
    weighted_f1 = f1_score(y_test, y_pred, average='weighted')
    ll = log_loss(y_test, y_pred_proba)

    print(f"\n{'='*60}")
    print(f"Test Results")
    print(f"{'='*60}")
    print(f"  Accuracy:    {acc:.4f}")
    print(f"  Macro-F1:    {macro_f1:.4f}")
    print(f"  Weighted-F1: {weighted_f1:.4f}")
    print(f"  LogLoss:     {ll:.4f}")
    print(f"  BestIter:    {model.best_iteration}")

    # Confusion Matrix
    cm = confusion_matrix(y_test, y_pred)
    print(f"\n  Confusion Matrix:")
    header = "        " + "  ".join(f"{LABEL_JP[i]:>6s}" for i in range(num_classes))
    print(header)
    for i in range(num_classes):
        row = f"  {LABEL_JP[i]:>6s}  " + "  ".join(f"{cm[i][j]:>6d}" for j in range(num_classes))
        # 各行の正解率
        row_total = cm[i].sum()
        row_acc = cm[i][i] / row_total if row_total > 0 else 0
        print(f"{row}  ({row_acc:.1%})")

    # Classification Report
    print(f"\n  Classification Report:")
    report = classification_report(
        y_test, y_pred, target_names=LABEL_JP, digits=4
    )
    for line in report.split('\n'):
        print(f"  {line}")

    # === Calibration分析: 予測確率 vs 実際の比率 ===
    print(f"\n  Calibration (predicted prob vs actual):")
    for cls in range(num_classes):
        pred_prob = y_pred_proba[:, cls]
        actual = (y_test.values == cls).astype(int)
        # 5分位で比較
        for q_lo, q_hi in [(0, 20), (20, 40), (40, 60), (60, 80), (80, 100)]:
            lo = np.percentile(pred_prob, q_lo)
            hi = np.percentile(pred_prob, q_hi)
            mask = (pred_prob >= lo) & (pred_prob < hi + 1e-9)
            if mask.sum() > 0:
                avg_pred = pred_prob[mask].mean()
                avg_actual = actual[mask].mean()
            else:
                avg_pred = avg_actual = 0
        # Just show overall calibration
        avg_pred_all = pred_prob.mean()
        avg_actual_all = actual.mean()
        print(f"    {LABEL_JP[cls]:>6s}: pred_avg={avg_pred_all:.3f}, actual_rate={avg_actual_all:.3f}")

    # === 特徴量重要度 ===
    importance = dict(zip(feature_cols, model.feature_importance(importance_type='gain')))
    sorted_imp = sorted(importance.items(), key=lambda x: x[1], reverse=True)

    print(f"\n  Top 30 Feature Importance (gain):")
    for i, (feat, gain) in enumerate(sorted_imp[:30]):
        print(f"    {i+1:>2d}. {feat:<40s} {gain:>10,.0f}")

    # === エントロピー分析 ===
    entropies = -np.sum(y_pred_proba * np.log(y_pred_proba + 1e-9), axis=1)
    max_entropy = np.log(num_classes)
    confidence = 1.0 - entropies / max_entropy

    print(f"\n  Entropy / Confidence Stats:")
    print(f"    Entropy:    mean={np.mean(entropies):.3f}, "
          f"median={np.median(entropies):.3f}, max_possible={max_entropy:.3f}")
    print(f"    Confidence: mean={np.mean(confidence):.3f}, "
          f"median={np.median(confidence):.3f}")

    # 正解時 vs 不正解時のconfidence
    correct_mask = y_pred == y_test.values
    if correct_mask.sum() > 0 and (~correct_mask).sum() > 0:
        print(f"    Correct predictions:   confidence={np.mean(confidence[correct_mask]):.3f}")
        print(f"    Incorrect predictions: confidence={np.mean(confidence[~correct_mask]):.3f}")

    metrics = {
        'accuracy': round(acc, 4),
        'macro_f1': round(macro_f1, 4),
        'weighted_f1': round(weighted_f1, 4),
        'log_loss': round(ll, 4),
        'best_iteration': model.best_iteration,
        'train_size': len(X_train),
        'val_size': len(X_val),
        'test_size': len(X_test),
        'confusion_matrix': cm.tolist(),
        'mean_confidence': round(float(np.mean(confidence)), 4),
    }

    return model, metrics, sorted_imp, y_pred_proba


def analyze_practical_value(df_test: pd.DataFrame, y_pred_proba: np.ndarray):
    """実用性分析: パフォ変動予測がP/W/ARに貢献できるか"""
    print(f"\n{'='*60}")
    print(f"Practical Value Analysis")
    print(f"{'='*60}")

    df = df_test.copy()
    n_cls = y_pred_proba.shape[1]
    for i, name in enumerate(LABEL_NAMES):
        df[f'pred_{name}'] = y_pred_proba[:, i]
    df['pred_label'] = np.argmax(y_pred_proba, axis=1)

    # クラスインデックスを動的に取得
    down_idx = LABEL_NAMES.index('down')
    up_indices = [i for i, n in enumerate(LABEL_NAMES) if n in ('up', 'big_up')]

    # 「下降予測された人気馬」の分析
    print(f"\n  [Danger Signal] 下降予測 × 人気上位(1-3番人気):")
    popular = df[df['popularity'].between(1, 3)]
    popular_down = popular[popular['pred_label'] == down_idx]
    if len(popular_down) > 0:
        avg_finish = popular_down['finish_position'].mean()
        top3_rate = (popular_down['is_top3'] == 1).mean()
        win_rate = (popular_down['is_win'] == 1).mean()
        print(f"    対象: {len(popular_down):,} / {len(popular):,} "
              f"({len(popular_down)/len(popular)*100:.1f}%)")
        print(f"    平均着順: {avg_finish:.1f}")
        print(f"    複勝率: {top3_rate:.1%} (全人気馬: {(popular['is_top3']==1).mean():.1%})")
        print(f"    勝率: {win_rate:.1%} (全人気馬: {(popular['is_win']==1).mean():.1%})")
    else:
        print(f"    対象なし")

    # 「上昇予測された中穴馬」の分析
    print(f"\n  [Value Signal] 上昇予測 × 中穴(4-9番人気):")
    mid_pop = df[df['popularity'].between(4, 9)]
    mid_up = mid_pop[mid_pop['pred_label'].isin(up_indices)]
    if len(mid_up) > 0:
        avg_finish = mid_up['finish_position'].mean()
        top3_rate = (mid_up['is_top3'] == 1).mean()
        win_rate = (mid_up['is_win'] == 1).mean()
        print(f"    対象: {len(mid_up):,} / {len(mid_pop):,} "
              f"({len(mid_up)/len(mid_pop)*100:.1f}%)")
        print(f"    平均着順: {avg_finish:.1f}")
        print(f"    複勝率: {top3_rate:.1%} (全中穴: {(mid_pop['is_top3']==1).mean():.1%})")
        print(f"    勝率: {win_rate:.1%} (全中穴: {(mid_pop['is_win']==1).mean():.1%})")
    else:
        print(f"    対象なし")

    # P%との相関
    pred_up_score = sum(y_pred_proba[:, i] for i in up_indices)
    pred_down_score = y_pred_proba[:, down_idx]

    if 'jrdb_idm_trend' in df.columns:
        valid_mask = df['jrdb_idm_trend'].notna()
        if valid_mask.sum() > 0:
            corr_idm_trend = df.loc[valid_mask, 'jrdb_idm_trend'].corr(
                pd.Series(pred_up_score[valid_mask.values], index=df.index[valid_mask])
            )
            print(f"\n  [Correlation] pred_up_score vs jrdb_idm_trend: r={corr_idm_trend:.3f}")

    # is_top3との相関
    corr_top3 = pd.Series(pred_down_score, index=df.index).corr(df['is_top3'].astype(float))
    print(f"  [Correlation] pred_down vs is_top3: r={corr_top3:.3f}")
    corr_top3_up = pd.Series(pred_up_score, index=df.index).corr(df['is_top3'].astype(float))
    print(f"  [Correlation] pred_up_total vs is_top3: r={corr_top3_up:.3f}")


def augment_career_features(
    df: pd.DataFrame,
    history_cache: dict,
    jrdb_sed_index: dict,
) -> pd.DataFrame:
    """DataFrameにキャリア全走特徴量 + 不確実性フラグを追加

    itertuples()で高速化（iterrows()の10倍以上速い）
    """
    # 列名のインデックスを事前取得
    cols = list(df.columns)
    idx_ketto = cols.index('ketto_num') if 'ketto_num' in cols else -1
    idx_date = cols.index('date') if 'date' in cols else -1
    idx_tt = cols.index('track_type') if 'track_type' in cols else -1
    idx_dist = cols.index('distance') if 'distance' in cols else -1
    idx_place = cols.index('place_code') if 'place_code' in cols else -1

    career_rows = []
    for tup in df.itertuples(index=False):
        ketto_num = tup[idx_ketto] if idx_ketto >= 0 else ''
        race_date = tup[idx_date] if idx_date >= 0 else ''
        tt_val = tup[idx_tt] if idx_tt >= 0 else 0
        dist_val = tup[idx_dist] if idx_dist >= 0 else 0
        place_val = tup[idx_place] if idx_place >= 0 else 0

        feat = compute_career_features(
            ketto_num=str(ketto_num),
            race_date=str(race_date),
            history_cache=history_cache,
            jrdb_sed_index=jrdb_sed_index,
            current_track_type='turf' if tt_val == 0 else 'dirt',
            current_distance=int(dist_val) if dist_val else 0,
            current_venue_code=str(int(place_val)) if place_val else '',
        )
        career_rows.append(feat)

    career_df = pd.DataFrame(career_rows, index=df.index)
    return pd.concat([df, career_df], axis=1)


def parse_period_range(s: str):
    """Parse period like '2020-2024' or '2025.01-2025.02' into (min_year, min_month, max_year, max_month)"""
    from ml.experiment import parse_period_range as _parse
    return _parse(s)


def main():
    parser = argparse.ArgumentParser(description='Performance Change Prediction Experiment')
    parser.add_argument('--train-years', default='2020-2024')
    parser.add_argument('--val-years', default='2025.01-2025.02')
    parser.add_argument('--test-years', default='2025.03-2026.02')
    parser.add_argument('--no-db', action='store_true')
    parser.add_argument('--sire-cutoff', type=str, default=None)
    parser.add_argument('--use-market', action='store_true',
                        help='市場特徴量も含める（デフォルト: VALUE特徴量のみ）')
    parser.add_argument('--no-career', action='store_true',
                        help='キャリア特徴量を追加しない（Phase 1比較用）')
    parser.add_argument('--three-class', action='store_true',
                        help='3クラス分類（上昇/平行線/下降）を使用')
    parser.add_argument('--save-model', action='store_true',
                        help='モデルをmodel_perf.txtとして保存（スタッキング用）')
    args = parser.parse_args()

    train_min, train_min_m, train_max, train_max_m = parse_period_range(args.train_years)
    val_min, val_min_m, val_max, val_max_m = parse_period_range(args.val_years)
    test_min, test_min_m, test_max, test_max_m = parse_period_range(args.test_years)
    use_db_odds = not args.no_db

    use_career = not args.no_career
    use_3class = args.three_class

    # グローバル設定を更新
    global LABEL_NAMES, LABEL_JP, NUM_CLASSES, idm_diff_to_label
    if use_3class:
        LABEL_NAMES = LABEL_NAMES_3
        LABEL_JP = LABEL_JP_3
        NUM_CLASSES = 3
        idm_diff_to_label = idm_diff_to_label_3
    else:
        LABEL_NAMES = LABEL_NAMES_4
        LABEL_JP = LABEL_JP_4
        NUM_CLASSES = 4
        idm_diff_to_label = idm_diff_to_label_4

    class_label = "3-class" if use_3class else "4-class"
    career_label = "career" if use_career else "baseline"
    phase_label = f"{class_label} + {career_label}"

    print(f"\n{'='*60}")
    print(f"  Performance Change Prediction - {phase_label}")
    print(f"  Target: IDM diff {class_label} (multiclass)")
    print(f"  Thresholds: big_up>={THRESH_BIG_UP}, up>={THRESH_UP}, down<={THRESH_DOWN}")
    print(f"  Train: {args.train_years}")
    print(f"  Val:   {args.val_years}")
    print(f"  Test:  {args.test_years}")
    print(f"  Features: {'ALL (market incl.)' if args.use_market else 'VALUE (no market)'}")
    print(f"  Career features: {'ON' if use_career else 'OFF'}")
    print(f"{'='*60}\n")

    t0 = time.time()

    # --- データロード ---
    (history_cache, trainer_index, jockey_index,
     date_index, pace_index, kb_ext_index, training_summary_index,
     race_level_index, pedigree_index, sire_stats_index,
     jrdb_sed_index, jrdb_kyi_index, jrdb_kaa_index) = load_data(
        sire_cutoff=args.sire_cutoff)

    pit_trainer_tl, pit_jockey_tl = build_pit_personnel_timeline()

    from ml.features.baba_features import load_baba_index
    baba_index = load_baba_index()

    # --- データセット構築 ---
    common_args = dict(
        date_index=date_index,
        history_cache=history_cache,
        trainer_index=trainer_index,
        jockey_index=jockey_index,
        pace_index=pace_index,
        kb_ext_index=kb_ext_index,
        use_db_odds=use_db_odds,
        training_summary_index=training_summary_index,
        race_level_index=race_level_index,
        pedigree_index=pedigree_index,
        sire_stats_index=sire_stats_index,
        pit_trainer_tl=pit_trainer_tl,
        pit_jockey_tl=pit_jockey_tl,
        baba_index=baba_index,
        jrdb_sed_index=jrdb_sed_index,
        jrdb_kyi_index=jrdb_kyi_index,
        jrdb_kaa_index=jrdb_kaa_index,
    )

    df_train = build_dataset(min_year=train_min, max_year=train_max,
                              min_month=train_min_m, max_month=train_max_m, **common_args)
    df_val = build_dataset(min_year=val_min, max_year=val_max,
                            min_month=val_min_m, max_month=val_max_m, **common_args)
    df_test = build_dataset(min_year=test_min, max_year=test_max,
                             min_month=test_min_m, max_month=test_max_m, **common_args)

    print(f"\n[Dataset] Raw sizes:")
    print(f"  Train: {len(df_train):,} entries")
    print(f"  Val:   {len(df_val):,} entries")
    print(f"  Test:  {len(df_test):,} entries")

    # --- キャリア特徴量を追加 (Phase 2) ---
    if use_career:
        print(f"\n[Career] Adding career + uncertainty features ({len(CAREER_FEATURE_COLS)} cols)...")
        t_career = time.time()
        df_train = augment_career_features(df_train, history_cache, jrdb_sed_index)
        print(f"  Train: done ({time.time()-t_career:.0f}s)")
        t_career = time.time()
        df_val = augment_career_features(df_val, history_cache, jrdb_sed_index)
        print(f"  Val: done ({time.time()-t_career:.0f}s)")
        t_career = time.time()
        df_test = augment_career_features(df_test, history_cache, jrdb_sed_index)
        print(f"  Test: done ({time.time()-t_career:.0f}s)")

    # --- IDM差分ターゲットを追加 ---
    print(f"\n[Target] Adding IDM diff target...")
    df_train = add_idm_diff_target(df_train, jrdb_sed_index, history_cache)
    df_val = add_idm_diff_target(df_val, jrdb_sed_index, history_cache)
    df_test = add_idm_diff_target(df_test, jrdb_sed_index, history_cache)

    print(f"  After IDM diff filter:")
    print(f"  Train: {len(df_train):,} entries ({len(df_train)/max(1,len(df_train))*100:.0f}% coverage)")
    print(f"  Val:   {len(df_val):,} entries")
    print(f"  Test:  {len(df_test):,} entries")

    # IDM差分の基本統計
    for name, df_split in [('Train', df_train), ('Val', df_val), ('Test', df_test)]:
        diffs = df_split['idm_diff']
        print(f"  {name} IDM diff: mean={diffs.mean():+.2f}, std={diffs.std():.2f}, "
              f"median={diffs.median():+.1f}")

    # --- 特徴量選択 ---
    if args.use_market:
        feature_cols = list(FEATURE_COLS_ALL)
    else:
        feature_cols = list(FEATURE_COLS_VALUE)

    # キャリア特徴量を追加
    if use_career:
        feature_cols = feature_cols + CAREER_FEATURE_COLS

    # DataFrameに存在する特徴量のみ使用
    available = set(df_train.columns)
    feature_cols = [f for f in feature_cols if f in available]
    n_career = len([f for f in CAREER_FEATURE_COLS if f in available]) if use_career else 0
    print(f"\n[Features] Using {len(feature_cols)} features"
          f"{f' (+{n_career} career/uncertainty)' if use_career else ''}")

    # --- モデル訓練 ---
    model, metrics, sorted_imp, y_pred_proba = train_multiclass_model(
        df_train, df_val, df_test, feature_cols,
        num_classes=NUM_CLASSES,
    )

    # --- 実用性分析 ---
    analyze_practical_value(df_test, y_pred_proba)

    # --- 結果保存 ---
    elapsed = time.time() - t0
    print(f"\n[Done] Total time: {elapsed:.0f}s ({elapsed/60:.1f}min)")

    result = {
        'experiment': f'performance_change_{"v2_career" if use_career else "v1_baseline"}',
        'thresholds': {
            'big_up': THRESH_BIG_UP,
            'up': THRESH_UP,
            'down': THRESH_DOWN,
        },
        'label_names': LABEL_NAMES,
        'metrics': metrics,
        'feature_importance_top50': [
            {'feature': f, 'gain': int(g)} for f, g in sorted_imp[:50]
        ],
        'feature_count': len(feature_cols),
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'elapsed_seconds': round(elapsed, 1),
    }

    result_path = config.ml_dir() / "experiment_performance_result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n[Saved] {result_path}")

    # --- モデル保存 (--save-model) ---
    if args.save_model:
        model_path = config.ml_dir() / "model_perf.txt"
        model.save_model(str(model_path))
        print(f"[Saved] {model_path}")

        meta = {
            'model_type': 'performance_change',
            'num_classes': NUM_CLASSES,
            'label_names': LABEL_NAMES,
            'label_jp': LABEL_JP,
            'feature_cols': feature_cols,
            'use_career': use_career,
            'train_period': '2020-2024',
            'best_iteration': model.best_iteration,
            'accuracy': metrics['accuracy'],
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        }
        meta_path = config.ml_dir() / "model_perf_meta.json"
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"[Saved] {meta_path}")


if __name__ == '__main__':
    main()
