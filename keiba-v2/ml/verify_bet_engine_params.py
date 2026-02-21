#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
bet-engine.py 実装パラメータ確定のための3検証

検証1: Calibrated確率の品質（ECE + calibration curve）
検証2: Calibrated確率 × オッズ のEV分布 × 実ROI
検証3: 統合C（分類gap + 回帰margin + calibrated EV）の最終ROI

全て既存パイプラインの出力に対する集計。
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
    FEATURE_COLS_ALL, FEATURE_COLS_VALUE,
    PARAMS_A, PARAMS_B, PARAMS_W, PARAMS_WV,
    train_model, calc_ece, calc_brier_score,
    _get_place_odds,
)
from ml.features.margin_target import add_margin_target_to_df
from core import config

import lightgbm as lgb

PARAMS_REG_VALUE = {
    'objective': 'huber', 'alpha': 2.0, 'metric': 'mae',
    'num_leaves': 127, 'learning_rate': 0.03,
    'feature_fraction': 0.8, 'bagging_fraction': 0.8, 'bagging_freq': 5,
    'min_child_samples': 50, 'reg_alpha': 0.1, 'reg_lambda': 1.5,
    'max_depth': 8, 'verbose': -1,
}


def compute_place_limit(entry_count):
    """複勝対象着順: 8頭以上=3, 5-7頭=2, 4頭以下=1"""
    if entry_count >= 8:
        return 3
    elif entry_count >= 5:
        return 2
    else:
        return 1


def main():
    print('=' * 70)
    print('  bet-engine.py パラメータ検証')
    print('=' * 70)

    # === データロード ===
    print('\n[Load] Loading data...')
    (history_cache, trainer_index, jockey_index,
     date_index, pace_index, kb_ext_index, training_summary_index) = load_data()

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

    # target_margin
    print('\n[Margin] Computing target_margin...')
    for label, df in [('train', df_train), ('val', df_val), ('test', df_test)]:
        add_margin_target_to_df(df, date_index, load_race_json, cap=5.0)

    # place_limit
    df_test['place_limit'] = df_test['entry_count'].apply(compute_place_limit)

    # place_odds_min
    df_test['place_odds_min'] = df_test.apply(_get_place_odds, axis=1)

    print(f'\n[Dataset] Train: {len(df_train):,}, Val: {len(df_val):,}, Test: {len(df_test):,}')

    # === 4モデル学習 (calibrated) ===
    print('\n[Train] Training 4 classification models...')

    # Model A (Place, All features)
    _, metrics_a, _, pred_a_cal, cal_a = train_model(
        df_train, df_val, df_test, FEATURE_COLS_ALL, PARAMS_A, 'is_top3', 'Model_A'
    )
    # Model B/V (Place, Value features)
    _, metrics_v, _, pred_v_cal, cal_v = train_model(
        df_train, df_val, df_test, FEATURE_COLS_VALUE, PARAMS_B, 'is_top3', 'Model_V'
    )
    # Model W (Win, All features)
    _, metrics_w, _, pred_w_cal, cal_w = train_model(
        df_train, df_val, df_test, FEATURE_COLS_ALL, PARAMS_W, 'is_win', 'Model_W'
    )
    # Model WV (Win, Value features)
    _, metrics_wv, _, pred_wv_cal, cal_wv = train_model(
        df_train, df_val, df_test, FEATURE_COLS_VALUE, PARAMS_WV, 'is_win', 'Model_WV'
    )

    df_test['pred_a_cal'] = pred_a_cal
    df_test['pred_v_cal'] = pred_v_cal
    df_test['pred_w_cal'] = pred_w_cal
    df_test['pred_wv_cal'] = pred_wv_cal

    # Classification ranks
    df_test['pred_rank_v'] = df_test.groupby('race_id')['pred_v_cal'].rank(
        ascending=False, method='min'
    )
    df_test['pred_rank_a'] = df_test.groupby('race_id')['pred_a_cal'].rank(
        ascending=False, method='min'
    )

    # VB gap (classification)
    df_test['vb_gap'] = df_test['odds_rank'] - df_test['pred_rank_v']

    # === Reg B (Value) ===
    print('\n[Train] Training Reg_B...')
    mask_tr = df_train['target_margin'].notna()
    mask_vl = df_val['target_margin'].notna()
    X_tr = df_train.loc[mask_tr, FEATURE_COLS_VALUE]
    y_tr = df_train.loc[mask_tr, 'target_margin']
    X_vl = df_val.loc[mask_vl, FEATURE_COLS_VALUE]
    y_vl = df_val.loc[mask_vl, 'target_margin']

    train_data = lgb.Dataset(X_tr, label=y_tr)
    valid_data = lgb.Dataset(X_vl, label=y_vl, reference=train_data)
    model_rb = lgb.train(
        PARAMS_REG_VALUE, train_data, num_boost_round=1500,
        valid_sets=[valid_data],
        callbacks=[lgb.early_stopping(stopping_rounds=50), lgb.log_evaluation(period=500)],
    )
    df_test['pred_margin_b'] = model_rb.predict(df_test[FEATURE_COLS_VALUE])
    df_test['reg_rank_v'] = df_test.groupby('race_id')['pred_margin_b'].rank(
        ascending=True, method='min'
    )

    # ===================================================================
    # 検証1: Calibrated確率の品質（ECE + calibration curve）
    # ===================================================================
    print(f'\n{"="*70}')
    print(f'  検証1: Calibrated確率の品質')
    print(f'{"="*70}')

    from sklearn.calibration import calibration_curve

    models_for_cal = [
        ('Model_WV (win)',  df_test['is_win'].values,  pred_wv_cal, 'EV単勝用'),
        ('Model_V (top3)',  df_test['is_top3'].values, pred_v_cal,  'EV複勝用'),
        ('Model_W (win)',   df_test['is_win'].values,  pred_w_cal,  '参考'),
        ('Model_A (top3)',  df_test['is_top3'].values, pred_a_cal,  '参考'),
    ]

    print(f'\n  {"Model":<20} {"ECE":>8} {"MaxCE":>8} {"Brier":>8} {"判定":>8}')
    print(f'  {"-"*56}')

    cal_details = []
    for name, y_true, y_prob, usage in models_for_cal:
        prob_true, prob_pred = calibration_curve(y_true, y_prob, n_bins=10, strategy='uniform')
        ece = float(np.mean(np.abs(prob_true - prob_pred)))
        max_ce = float(np.max(np.abs(prob_true - prob_pred)))
        brier = calc_brier_score(y_true, y_prob)

        if ece < 0.03:
            judge = '良好'
        elif ece < 0.05:
            judge = '許容'
        else:
            judge = '要改善'

        print(f'  {name:<20} {ece:>8.4f} {max_ce:>8.4f} {brier:>8.4f} {judge:>8}')
        cal_details.append((name, usage, prob_true, prob_pred))

    for name, usage, prob_true, prob_pred in cal_details:
        print(f'\n  {name} ({usage}) calibration curve:')
        print(f'    {"predicted":>10} {"actual":>10} {"diff":>10} {"bar":>20}')
        for pp, pt in zip(prob_pred, prob_true):
            diff = pt - pp
            bar_len = int(abs(diff) * 200)
            bar_char = '+' if diff > 0 else '-'
            bar = bar_char * min(bar_len, 30)
            print(f'    {pp:>10.4f} {pt:>10.4f} {diff:>+10.4f} {bar}')

    # ===================================================================
    # 検証2: Calibrated確率 × オッズ のEV分布
    # ===================================================================
    print(f'\n{"="*70}')
    print(f'  検証2: EV帯別 実ROI')
    print(f'{"="*70}')

    # VB候補: gap >= 3 & pred_rank_v <= 3
    vb = df_test[
        (df_test['pred_rank_v'] <= 3) &
        (df_test['vb_gap'] >= 3)
    ].copy()

    # EV計算
    vb['win_ev'] = vb['pred_wv_cal'] * vb['odds']
    vb['place_ev'] = vb['pred_v_cal'] * vb['place_odds_min']

    print(f'\n  VB候補: {len(vb)} bets (gap>=3, rank_v<=3)')
    print(f'  Win EV:   mean={vb["win_ev"].mean():.3f}, median={vb["win_ev"].median():.3f}')
    print(f'  Place EV: mean={vb["place_ev"].mean():.3f}, median={vb["place_ev"].median():.3f}')

    # --- 分析A: Win EV帯別 ---
    print(f'\n  === Win EV帯別 実ROI ===')
    ev_bins = [(0.0, 0.3), (0.3, 0.5), (0.5, 0.8), (0.8, 1.0), (1.0, 1.2),
               (1.2, 1.5), (1.5, 2.0), (2.0, 99)]
    print(f'  {"EV帯":>12} {"n":>6} {"hitRate":>8} {"avgOdds":>9} {"Win ROI":>9}')
    print(f'  {"-"*46}')

    for lo, hi in ev_bins:
        mask = (vb['win_ev'] >= lo) & (vb['win_ev'] < hi)
        subset = vb[mask]
        n = len(subset)
        if n == 0:
            continue
        wins = subset[subset['is_win'] == 1]
        payout = (wins['odds'] * 100).sum()
        roi = payout / (n * 100) * 100
        hit_rate = len(wins) / n
        label = f'[{lo:.1f},{hi:.1f})' if hi < 99 else f'[{lo:.1f},+)'
        print(f'  {label:>12} {n:>6} {hit_rate:>7.1%} {subset["odds"].mean():>9.1f} {roi:>8.1f}%')

    # --- 分析B: Place EV帯別 ---
    print(f'\n  === Place EV帯別 実ROI ===')
    print(f'  {"EV帯":>12} {"n":>6} {"hitRate":>8} {"avgOdds":>9} {"PlaceROI":>9}')
    print(f'  {"-"*46}')

    for lo, hi in ev_bins:
        mask = (vb['place_ev'] >= lo) & (vb['place_ev'] < hi)
        subset = vb[mask]
        n = len(subset)
        if n == 0:
            continue
        hits = subset[subset['finish_position'] <= subset['place_limit']]
        payout = (hits['place_odds_min'] * 100).sum()
        roi = payout / (n * 100) * 100
        hit_rate = len(hits) / n
        label = f'[{lo:.1f},{hi:.1f})' if hi < 99 else f'[{lo:.1f},+)'
        print(f'  {label:>12} {n:>6} {hit_rate:>7.1%} {subset["place_odds_min"].mean():>9.1f} {roi:>8.1f}%')

    # --- 分析C: EV閾値フィルタ ---
    print(f'\n  === EV閾値フィルタ (VB gap>=3 内) ===')
    print(f'  {"threshold":>10} {"Win_n":>7} {"Win_ROI":>9} {"Place_n":>8} {"PlaceROI":>9}')
    print(f'  {"-"*46}')

    for ev_th in [0.0, 0.5, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.5]:
        # Win
        if ev_th > 0:
            w_mask = vb['win_ev'] >= ev_th
        else:
            w_mask = pd.Series(True, index=vb.index)
        w_sub = vb[w_mask]
        w_n = len(w_sub)
        if w_n > 0:
            w_pay = (w_sub[w_sub['is_win'] == 1]['odds'] * 100).sum()
            w_roi = w_pay / (w_n * 100) * 100
        else:
            w_roi = 0

        # Place
        if ev_th > 0:
            p_mask = vb['place_ev'] >= ev_th
        else:
            p_mask = pd.Series(True, index=vb.index)
        p_sub = vb[p_mask]
        p_n = len(p_sub)
        if p_n > 0:
            p_hits = p_sub[p_sub['finish_position'] <= p_sub['place_limit']]
            p_pay = (p_hits['place_odds_min'] * 100).sum()
            p_roi = p_pay / (p_n * 100) * 100
        else:
            p_roi = 0

        label = f'>={ev_th:.1f}' if ev_th > 0 else 'ALL'
        print(f'  {label:>10} {w_n:>7} {w_roi:>8.1f}% {p_n:>8} {p_roi:>8.1f}%')

    # 単調増加チェック
    print(f'\n  単調増加チェック:')
    win_rois_by_ev = []
    place_rois_by_ev = []
    for lo, hi in [(0.3, 0.5), (0.5, 0.8), (0.8, 1.0), (1.0, 1.5), (1.5, 99)]:
        mask_w = (vb['win_ev'] >= lo) & (vb['win_ev'] < hi)
        mask_p = (vb['place_ev'] >= lo) & (vb['place_ev'] < hi)
        sw = vb[mask_w]
        sp = vb[mask_p]
        if len(sw) > 0:
            wr = (sw[sw['is_win'] == 1]['odds'] * 100).sum() / (len(sw) * 100) * 100
            win_rois_by_ev.append(wr)
        if len(sp) > 0:
            ph = sp[sp['finish_position'] <= sp['place_limit']]
            pr = (ph['place_odds_min'] * 100).sum() / (len(sp) * 100) * 100
            place_rois_by_ev.append(pr)

    win_monotonic = all(win_rois_by_ev[i] <= win_rois_by_ev[i+1]
                        for i in range(len(win_rois_by_ev)-1)) if len(win_rois_by_ev) > 1 else True
    place_monotonic = all(place_rois_by_ev[i] <= place_rois_by_ev[i+1]
                          for i in range(len(place_rois_by_ev)-1)) if len(place_rois_by_ev) > 1 else True
    print(f'  Win EV帯別ROI 単調増加: {"Yes" if win_monotonic else "No"} {win_rois_by_ev}')
    print(f'  Place EV帯別ROI 単調増加: {"Yes" if place_monotonic else "No"} {place_rois_by_ev}')

    # ===================================================================
    # 検証3: 統合C（gap × margin × EV）グリッドサーチ
    # ===================================================================
    print(f'\n{"="*70}')
    print(f'  検証3: 統合C グリッドサーチ')
    print(f'{"="*70}')

    # 全テストに対してEV計算
    df_test['win_ev'] = df_test['pred_wv_cal'] * df_test['odds']
    df_test['place_ev'] = df_test['pred_v_cal'] * df_test['place_odds_min']

    results = []
    for min_gap in [2, 3, 4, 5]:
        for max_margin in [0.8, 1.0, 1.2, 1.5, 99.0]:
            for min_ev in [0.0, 0.8, 0.9, 1.0, 1.1, 1.2]:
                # Base filter: classification VB
                base_mask = (
                    (df_test['pred_rank_v'] <= 3) &
                    (df_test['vb_gap'] >= min_gap)
                )
                # Margin filter
                if max_margin < 99:
                    base_mask = base_mask & (df_test['pred_margin_b'] <= max_margin)

                subset = df_test[base_mask]

                if len(subset) == 0:
                    continue

                # Win: EV filter on win_ev
                if min_ev > 0:
                    win_sub = subset[subset['win_ev'] >= min_ev]
                else:
                    win_sub = subset
                w_n = len(win_sub)

                # Place: EV filter on place_ev
                if min_ev > 0:
                    place_sub = subset[subset['place_ev'] >= min_ev]
                else:
                    place_sub = subset
                p_n = len(place_sub)

                # Win ROI
                if w_n > 0:
                    w_pay = (win_sub[win_sub['is_win'] == 1]['odds'] * 100).sum()
                    w_roi = w_pay / (w_n * 100) * 100
                else:
                    w_roi = 0

                # Place ROI
                if p_n > 0:
                    p_hits = place_sub[place_sub['finish_position'] <= place_sub['place_limit']]
                    p_pay = (p_hits['place_odds_min'] * 100).sum()
                    p_roi = p_pay / (p_n * 100) * 100
                else:
                    p_roi = 0

                results.append({
                    'gap': min_gap,
                    'margin': max_margin,
                    'min_ev': min_ev,
                    'win_n': w_n,
                    'win_roi': round(w_roi, 1),
                    'place_n': p_n,
                    'place_roi': round(p_roi, 1),
                    'base_n': len(subset),
                })

    df_r = pd.DataFrame(results)

    # Win ROI Top 15 (n >= 50)
    print(f'\n  --- Win ROI Top 15 (n>=50) ---')
    top_w = df_r[df_r['win_n'] >= 50].nlargest(15, 'win_roi')
    print(f'  {"gap":>4} {"margin":>7} {"min_ev":>7} {"win_n":>6} {"win_roi":>9} {"place_n":>8} {"place_roi":>10}')
    print(f'  {"-"*53}')
    for _, row in top_w.iterrows():
        mg = f'{row["margin"]:.1f}' if row['margin'] < 99 else 'ALL'
        ev = f'{row["min_ev"]:.1f}' if row['min_ev'] > 0 else 'ALL'
        w_marker = ' ***' if row['win_roi'] >= 100 else ''
        print(f'  {int(row["gap"]):>4} {mg:>7} {ev:>7} {int(row["win_n"]):>6} {row["win_roi"]:>8.1f}%{w_marker}'
              f' {int(row["place_n"]):>8} {row["place_roi"]:>9.1f}%')

    # Place ROI Top 15 (n >= 50)
    print(f'\n  --- Place ROI Top 15 (n>=50) ---')
    top_p = df_r[df_r['place_n'] >= 50].nlargest(15, 'place_roi')
    print(f'  {"gap":>4} {"margin":>7} {"min_ev":>7} {"win_n":>6} {"win_roi":>9} {"place_n":>8} {"place_roi":>10}')
    print(f'  {"-"*53}')
    for _, row in top_p.iterrows():
        mg = f'{row["margin"]:.1f}' if row['margin'] < 99 else 'ALL'
        ev = f'{row["min_ev"]:.1f}' if row['min_ev'] > 0 else 'ALL'
        p_marker = ' ***' if row['place_roi'] >= 100 else ''
        print(f'  {int(row["gap"]):>4} {mg:>7} {ev:>7} {int(row["win_n"]):>6} {row["win_roi"]:>8.1f}%'
              f' {int(row["place_n"]):>8} {row["place_roi"]:>9.1f}%{p_marker}')

    # 推奨候補: Win ROI >= 95% & n >= 100
    print(f'\n  --- 推奨候補 (Win ROI>=95% & n>=100) ---')
    cand_w = df_r[(df_r['win_roi'] >= 95) & (df_r['win_n'] >= 100)].sort_values('win_roi', ascending=False)
    if len(cand_w) > 0:
        print(f'  {"gap":>4} {"margin":>7} {"min_ev":>7} {"win_n":>6} {"win_roi":>9}')
        print(f'  {"-"*35}')
        for _, row in cand_w.head(20).iterrows():
            mg = f'{row["margin"]:.1f}' if row['margin'] < 99 else 'ALL'
            ev = f'{row["min_ev"]:.1f}' if row['min_ev'] > 0 else 'ALL'
            print(f'  {int(row["gap"]):>4} {mg:>7} {ev:>7} {int(row["win_n"]):>6} {row["win_roi"]:>8.1f}%')
    else:
        print('  (該当なし)')

    # 推奨候補: Place ROI >= 95% & n >= 100
    print(f'\n  --- 推奨候補 (Place ROI>=95% & n>=100) ---')
    cand_p = df_r[(df_r['place_roi'] >= 95) & (df_r['place_n'] >= 100)].sort_values('place_roi', ascending=False)
    if len(cand_p) > 0:
        print(f'  {"gap":>4} {"margin":>7} {"min_ev":>7} {"place_n":>8} {"place_roi":>10}')
        print(f'  {"-"*38}')
        for _, row in cand_p.head(20).iterrows():
            mg = f'{row["margin"]:.1f}' if row['margin'] < 99 else 'ALL'
            ev = f'{row["min_ev"]:.1f}' if row['min_ev'] > 0 else 'ALL'
            print(f'  {int(row["gap"]):>4} {mg:>7} {ev:>7} {int(row["place_n"]):>8} {row["place_roi"]:>9.1f}%')
    else:
        print('  (該当なし)')

    # === ヒートマップ: gap × margin (EV filter固定) ===
    print(f'\n  --- Place ROI ヒートマップ (EVフィルタ=1.0) ---')
    print(f'  {"":>10}', end='')
    margin_vals = [0.8, 1.0, 1.2, 1.5, 99.0]
    for m in margin_vals:
        label = f'm<={m:.1f}' if m < 99 else 'm=ALL'
        print(f' {label:>12}', end='')
    print()
    print(f'  {"-"*74}')

    for g in [2, 3, 4, 5]:
        print(f'  gap>={g:<4}', end='')
        for m in margin_vals:
            row = df_r[(df_r['gap'] == g) & (df_r['margin'] == m) & (df_r['min_ev'] == 1.0)]
            if len(row) > 0:
                r = row.iloc[0]
                n = int(r['place_n'])
                roi = r['place_roi']
                marker = '***' if roi >= 100 else ''
                print(f' {roi:>6.1f}%({n:>3}){marker}', end='')
            else:
                print(f' {"N/A":>12}', end='')
        print()

    print(f'\n  --- Win ROI ヒートマップ (EVフィルタ=1.0) ---')
    print(f'  {"":>10}', end='')
    for m in margin_vals:
        label = f'm<={m:.1f}' if m < 99 else 'm=ALL'
        print(f' {label:>12}', end='')
    print()
    print(f'  {"-"*74}')

    for g in [2, 3, 4, 5]:
        print(f'  gap>={g:<4}', end='')
        for m in margin_vals:
            row = df_r[(df_r['gap'] == g) & (df_r['margin'] == m) & (df_r['min_ev'] == 1.0)]
            if len(row) > 0:
                r = row.iloc[0]
                n = int(r['win_n'])
                roi = r['win_roi']
                marker = '***' if roi >= 100 else ''
                print(f' {roi:>6.1f}%({n:>3}){marker}', end='')
            else:
                print(f' {"N/A":>12}', end='')
        print()

    # EVフィルタなしのヒートマップも
    print(f'\n  --- Place ROI ヒートマップ (EVフィルタなし) ---')
    print(f'  {"":>10}', end='')
    for m in margin_vals:
        label = f'm<={m:.1f}' if m < 99 else 'm=ALL'
        print(f' {label:>12}', end='')
    print()
    print(f'  {"-"*74}')

    for g in [2, 3, 4, 5]:
        print(f'  gap>={g:<4}', end='')
        for m in margin_vals:
            row = df_r[(df_r['gap'] == g) & (df_r['margin'] == m) & (df_r['min_ev'] == 0.0)]
            if len(row) > 0:
                r = row.iloc[0]
                n = int(r['place_n'])
                roi = r['place_roi']
                marker = '***' if roi >= 100 else ''
                print(f' {roi:>6.1f}%({n:>3}){marker}', end='')
            else:
                print(f' {"N/A":>12}', end='')
        print()

    print(f'\n  --- Win ROI ヒートマップ (EVフィルタなし) ---')
    print(f'  {"":>10}', end='')
    for m in margin_vals:
        label = f'm<={m:.1f}' if m < 99 else 'm=ALL'
        print(f' {label:>12}', end='')
    print()
    print(f'  {"-"*74}')

    for g in [2, 3, 4, 5]:
        print(f'  gap>={g:<4}', end='')
        for m in margin_vals:
            row = df_r[(df_r['gap'] == g) & (df_r['margin'] == m) & (df_r['min_ev'] == 0.0)]
            if len(row) > 0:
                r = row.iloc[0]
                n = int(r['win_n'])
                roi = r['win_roi']
                marker = '***' if roi >= 100 else ''
                print(f' {roi:>6.1f}%({n:>3}){marker}', end='')
            else:
                print(f' {"N/A":>12}', end='')
        print()

    # === EVフィルタ効果の差分 ===
    print(f'\n  --- EVフィルタ効果 (gap=3, margin=ALL) ---')
    print(f'  {"min_ev":>7} {"Win_n":>7} {"Win_ROI":>9} {"Place_n":>8} {"PlaceROI":>9} {"W_diff":>8} {"P_diff":>8}')
    print(f'  {"-"*60}')

    base_w = df_r[(df_r['gap'] == 3) & (df_r['margin'] == 99.0) & (df_r['min_ev'] == 0.0)]
    base_w_roi = base_w.iloc[0]['win_roi'] if len(base_w) > 0 else 0
    base_p_roi = base_w.iloc[0]['place_roi'] if len(base_w) > 0 else 0

    for ev in [0.0, 0.8, 0.9, 1.0, 1.1, 1.2]:
        row = df_r[(df_r['gap'] == 3) & (df_r['margin'] == 99.0) & (df_r['min_ev'] == ev)]
        if len(row) > 0:
            r = row.iloc[0]
            ev_label = f'{ev:.1f}' if ev > 0 else 'ALL'
            w_diff = r['win_roi'] - base_w_roi
            p_diff = r['place_roi'] - base_p_roi
            print(f'  {ev_label:>7} {int(r["win_n"]):>7} {r["win_roi"]:>8.1f}%'
                  f' {int(r["place_n"]):>8} {r["place_roi"]:>8.1f}%'
                  f' {w_diff:>+7.1f}% {p_diff:>+7.1f}%')

    print(f'\n  --- marginフィルタ効果 (gap=3, EV=1.0) ---')
    print(f'  {"margin":>7} {"Win_n":>7} {"Win_ROI":>9} {"Place_n":>8} {"PlaceROI":>9}')
    print(f'  {"-"*44}')

    for m in [0.8, 1.0, 1.2, 1.5, 99.0]:
        row = df_r[(df_r['gap'] == 3) & (df_r['margin'] == m) & (df_r['min_ev'] == 1.0)]
        if len(row) > 0:
            r = row.iloc[0]
            ml = f'{m:.1f}' if m < 99 else 'ALL'
            print(f'  {ml:>7} {int(r["win_n"]):>7} {r["win_roi"]:>8.1f}%'
                  f' {int(r["place_n"]):>8} {r["place_roi"]:>8.1f}%')

    print('\nDone.')


if __name__ == '__main__':
    main()
