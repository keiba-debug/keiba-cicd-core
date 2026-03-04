#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
着差回帰 × VB クロス集計分析

VB候補内のpredicted margin分布 × 的中率・ROIを分析し、
marginフィルタの最適閾値を探索する。
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from ml.experiment import (
    load_data, build_dataset, load_race_json,
    FEATURE_COLS_VALUE,
    PARAMS_P, train_model, _get_place_odds,
)
from ml.features.margin_target import add_margin_target_to_df

# --- データロード ---
print('[Load] Loading data...')
(history_cache, trainer_index, jockey_index,
 date_index, pace_index, kb_ext_index, training_summary_index, *_extra) = load_data()

df_train = build_dataset(
    date_index, history_cache, trainer_index, jockey_index, pace_index,
    kb_ext_index, 2020, 2023, use_db_odds=True,
    training_summary_index=training_summary_index,
)
df_val = build_dataset(
    date_index, history_cache, trainer_index, jockey_index, pace_index,
    kb_ext_index, 2024, 2024, use_db_odds=True,
    training_summary_index=training_summary_index,
)
df_test = build_dataset(
    date_index, history_cache, trainer_index, jockey_index, pace_index,
    kb_ext_index, 2025, 2026, use_db_odds=True,
    training_summary_index=training_summary_index,
)

# --- target_margin ---
print('[Margin] Computing...')
for label, df in [('train', df_train), ('val', df_val), ('test', df_test)]:
    add_margin_target_to_df(df, date_index, load_race_json, cap=5.0)

# --- Reg AR (Value) 学習 ---
import lightgbm as lgb

PARAMS_REG_VALUE = {
    'objective': 'huber', 'alpha': 2.0, 'metric': 'mae',
    'num_leaves': 127, 'learning_rate': 0.03,
    'feature_fraction': 0.8, 'bagging_fraction': 0.8, 'bagging_freq': 5,
    'min_child_samples': 50, 'reg_alpha': 0.1, 'reg_lambda': 1.5,
    'max_depth': 8, 'verbose': -1,
}

mask_tr = df_train['target_margin'].notna()
mask_vl = df_val['target_margin'].notna()

X_tr = df_train.loc[mask_tr, FEATURE_COLS_VALUE]
y_tr = df_train.loc[mask_tr, 'target_margin']
X_vl = df_val.loc[mask_vl, FEATURE_COLS_VALUE]
y_vl = df_val.loc[mask_vl, 'target_margin']

print('[Train] Reg_AR...')
train_data = lgb.Dataset(X_tr, label=y_tr)
valid_data = lgb.Dataset(X_vl, label=y_vl, reference=train_data)
model_rb = lgb.train(
    PARAMS_REG_VALUE, train_data, num_boost_round=1500,
    valid_sets=[valid_data],
    callbacks=[lgb.early_stopping(stopping_rounds=50), lgb.log_evaluation(period=500)],
)

# --- テスト予測 ---
df_test['pred_margin_ar'] = model_rb.predict(df_test[FEATURE_COLS_VALUE])
df_test['reg_rank_ar'] = df_test.groupby('race_id')['pred_margin_ar'].rank(
    ascending=True, method='min'
)

# --- 分類 P (Place) 学習 ---
print('[Train] Place...')
_, _, _, pred_cb, _ = train_model(
    df_train, df_val, df_test, FEATURE_COLS_VALUE, PARAMS_P, 'is_top3', 'Place'
)
df_test['pred_proba_p'] = pred_cb
df_test['pred_rank_p'] = df_test.groupby('race_id')['pred_proba_p'].rank(
    ascending=False, method='min'
)

# VB gap
df_test['vb_gap_cls'] = df_test['odds_rank'] - df_test['pred_rank_p']
df_test['vb_gap_reg'] = df_test['odds_rank'] - df_test['reg_rank_ar']


def roi_by_bins(df_subset, bin_col='margin_bin'):
    """ビン別ROI計算"""
    results = []
    for idx in df_subset[bin_col].cat.categories:
        mask = df_subset[bin_col] == idx
        subset = df_subset[mask]
        n = len(subset)
        if n == 0:
            continue
        total = n * 100
        win_ret = subset[subset['is_win'] == 1]['odds'].sum() * 100
        place_ret = subset[subset['is_top3'] == 1].apply(_get_place_odds, axis=1).sum() * 100
        results.append({
            'bin': str(idx),
            'count': n,
            'win_rate': round(subset['is_win'].mean(), 4),
            'top3_rate': round(subset['is_top3'].mean(), 4),
            'avg_actual': round(subset['target_margin'].mean(), 3),
            'avg_pred': round(subset['pred_margin_ar'].mean(), 3),
            'avg_odds': round(subset['odds'].mean(), 1),
            'win_roi': round(win_ret / total * 100, 1),
            'place_roi': round(place_ret / total * 100, 1),
        })
    return pd.DataFrame(results)


bins = [0, 0.3, 0.5, 0.8, 1.0, 1.5, 5.0]
labels = ['<0.3', '0.3-0.5', '0.5-0.8', '0.8-1.0', '1.0-1.5', '1.5+']

# ===================================================================
# 分析1: 回帰VB候補のmargin分布
# ===================================================================
print()
print('=' * 80)
print('  分析1: 回帰AR VB候補(reg_rank_ar<=3 & gap>=N) のmargin分布')
print('=' * 80)

for gap_min in [3, 4, 5]:
    vb = df_test[(df_test['reg_rank_ar'] <= 3) & (df_test['vb_gap_reg'] >= gap_min)].copy()
    vb['margin_bin'] = pd.cut(vb['pred_margin_ar'], bins=bins, labels=labels, right=True)
    result = roi_by_bins(vb)
    print(f'\n--- Reg AR VB (gap>={gap_min}): {len(vb)} bets ---')
    print(result.to_string(index=False))

# ===================================================================
# 分析2: 分類VB候補のmargin分布
# ===================================================================
print()
print('=' * 80)
print('  分析2: Place VB候補(pred_rank_p<=3 & gap>=3) のmargin分布')
print('=' * 80)

vb_cls = df_test[(df_test['pred_rank_p'] <= 3) & (df_test['vb_gap_cls'] >= 3)].copy()
vb_cls['margin_bin'] = pd.cut(vb_cls['pred_margin_ar'], bins=bins, labels=labels, right=True)
result_cls = roi_by_bins(vb_cls)
print(f'\n--- Place VB (gap>=3): {len(vb_cls)} bets ---')
print(result_cls.to_string(index=False))

# ===================================================================
# 分析3: ハイブリッド — 分類VB + margin閾値フィルタ
# ===================================================================
print()
print('=' * 80)
print('  分析3: ハイブリッド (Place VB gap>=3 + margin閾値)')
print('=' * 80)

print(f'\n  {"margin_th":>10} {"bets":>6} {"top3%":>7} {"win%":>7} {"avg_odds":>9} {"Win_ROI":>9} {"Place_ROI":>10}')
print(f'  {"-"*62}')

for threshold in [0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.5, 2.0, 999]:
    if threshold < 999:
        mask = ((df_test['pred_rank_p'] <= 3) &
                (df_test['vb_gap_cls'] >= 3) &
                (df_test['pred_margin_ar'] <= threshold))
    else:
        mask = ((df_test['pred_rank_p'] <= 3) &
                (df_test['vb_gap_cls'] >= 3))
    subset = df_test[mask]
    if len(subset) == 0:
        continue
    total = len(subset) * 100
    win_ret = subset[subset['is_win'] == 1]['odds'].sum() * 100
    place_hits = subset[subset['is_top3'] == 1]
    place_ret = place_hits.apply(_get_place_odds, axis=1).sum() * 100
    win_roi = win_ret / total * 100
    place_roi = place_ret / total * 100
    top3_rate = subset['is_top3'].mean()
    win_rate = subset['is_win'].mean()
    avg_odds = subset['odds'].mean()

    label = f'<={threshold}s' if threshold < 999 else 'ALL'
    print(f'  {label:>10} {len(subset):>6} {top3_rate:>6.1%} {win_rate:>6.1%} '
          f'{avg_odds:>9.1f} {win_roi:>8.1f}% {place_roi:>9.1f}%')

# ===================================================================
# 分析4: gap別 × margin閾値 ヒートマップ
# ===================================================================
print()
print('=' * 80)
print('  分析4: Place ROI ヒートマップ (gap × margin閾値)')
print('=' * 80)

print(f'\n  {"":>10}', end='')
for th in [0.5, 0.8, 1.0, 1.5, 999]:
    label = f'<={th}s' if th < 999 else 'ALL'
    print(f' {label:>10}', end='')
print()
print(f'  {"-"*62}')

for gap_min in [2, 3, 4, 5]:
    print(f'  gap>={gap_min:<4}', end='')
    for th in [0.5, 0.8, 1.0, 1.5, 999]:
        if th < 999:
            mask = ((df_test['pred_rank_p'] <= 3) &
                    (df_test['vb_gap_cls'] >= gap_min) &
                    (df_test['pred_margin_ar'] <= th))
        else:
            mask = ((df_test['pred_rank_p'] <= 3) &
                    (df_test['vb_gap_cls'] >= gap_min))
        subset = df_test[mask]
        if len(subset) == 0:
            print(f' {"N/A":>10}', end='')
            continue
        total = len(subset) * 100
        place_ret = subset[subset['is_top3'] == 1].apply(_get_place_odds, axis=1).sum() * 100
        roi = place_ret / total * 100
        n = len(subset)
        marker = '***' if roi >= 100 else ''
        print(f' {roi:>6.1f}%({n:>3}){marker}', end='')
    print()

print('\nDone.')
