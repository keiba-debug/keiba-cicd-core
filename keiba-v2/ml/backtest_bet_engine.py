#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
bet_engine バックテスト

experiment.py のパイプラインで構築したテストデータに対して
bet_engine の各プリセットを適用し、実ROIを計算する。

Usage:
    python -m ml.backtest_bet_engine
"""

import json
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
    PARAMS_A, PARAMS_B, PARAMS_W, PARAMS_WV, PARAMS_REG_B,
    train_model, train_regression_model, _get_place_odds,
)
from ml.features.margin_target import add_margin_target_to_df
from ml.bet_engine import (
    PRESETS, BetStrategyParams,
    generate_recommendations, recommendations_summary,
    df_to_race_predictions, calc_bet_engine_roi,
    load_grade_offsets,
)


def main():
    print('=' * 70)
    print('  bet_engine バックテスト')
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

    print(f'[Dataset] Train={len(df_train):,}, Val={len(df_val):,}, Test={len(df_test):,}')

    # === モデル学習 ===
    print('\n[Train] Training classification models...')
    _, _, _, pred_b, cal_b = train_model(
        df_train, df_val, df_test, FEATURE_COLS_VALUE, PARAMS_B, 'is_top3', 'Cls_B'
    )
    _, _, _, pred_wv, cal_wv = train_model(
        df_train, df_val, df_test, FEATURE_COLS_VALUE, PARAMS_WV, 'is_win', 'Cls_WV'
    )

    # === 回帰モデル (着差予測) ===
    print('\n[Margin] Computing target_margin...')
    for label, df in [('train', df_train), ('val', df_val), ('test', df_test)]:
        add_margin_target_to_df(df, date_index, load_race_json, cap=5.0)

    _, _, _, pred_reg_b = train_regression_model(
        df_train, df_val, df_test, FEATURE_COLS_VALUE, PARAMS_REG_B, 'Reg_B'
    )
    df_test['pred_margin_b'] = pred_reg_b

    # 予測結果をDataFrameに追加
    df_test['pred_proba_v'] = pred_b
    df_test['pred_rank_v'] = df_test.groupby('race_id')['pred_proba_v'].rank(
        ascending=False, method='min'
    )
    df_test['pred_proba_wv'] = pred_wv
    df_test['pred_rank_wv'] = df_test.groupby('race_id')['pred_proba_wv'].rank(
        ascending=False, method='min'
    )

    # raw確率（Kelly用）
    df_test['pred_proba_v_raw'] = pred_b

    # VB gap
    df_test['vb_gap'] = (df_test['odds_rank'] - df_test['pred_rank_v']).clip(lower=0).astype(int)
    df_test['win_vb_gap'] = (df_test['odds_rank'] - df_test['pred_rank_wv']).clip(lower=0).astype(int)

    # EV (calibrated)
    if cal_b is not None:
        pred_b_cal = cal_b.predict(pred_b)
    else:
        pred_b_cal = pred_b
    if cal_wv is not None:
        pred_wv_cal = cal_wv.predict(pred_wv)
    else:
        pred_wv_cal = pred_wv

    df_test['win_ev'] = pred_wv_cal * df_test['odds']
    place_odds_col = df_test['place_odds_low'].fillna(df_test['odds'] / 3.5)
    df_test['place_ev'] = pred_b_cal * place_odds_col

    # === bet_engine バックテスト ===
    print('\n[BetEngine] Converting to race predictions format...')
    grade_offsets = load_grade_offsets()
    if grade_offsets:
        print(f'  Method A: {len(grade_offsets)} grade offsets loaded')
    race_preds = df_to_race_predictions(df_test, grade_offsets=grade_offsets)
    print(f'  {len(race_preds)} races, {sum(len(r["entries"]) for r in race_preds):,} entries')

    # キャッシュ保存（再分析用）
    cache_path = Path('C:/KEIBA-CICD/data3/ml/backtest_cache.json')
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(race_preds, f, ensure_ascii=False)
    print(f'  Cached to {cache_path}')

    print('\n' + '=' * 70)
    print('  バックテスト結果')
    print('=' * 70)

    header = (f'  {"Preset":>14} {"Bets":>5} {"TotalBet":>10} {"TotalRet":>10} {"ROI":>7} '
              f'{"WinBet":>9} {"WinRet":>9} {"WinROI":>7} {"PlcBet":>9} {"PlcRet":>9} {"PlcROI":>7}')
    print(header)
    print(f'  {"-" * 100}')

    for preset_name, preset_params in PRESETS.items():
        recs = generate_recommendations(race_preds, preset_params, budget=30000)
        roi = calc_bet_engine_roi(recs, race_preds)
        summary = recommendations_summary(recs)

        marker = ' ***' if roi['total_roi'] >= 100 else ''
        print(f'  {preset_name:>14} {roi["num_bets"]:>5} '
              f'{roi["total_bet"]:>10,} {roi["total_return"]:>10,} {roi["total_roi"]:>6.1f}%{marker}'
              f' {roi["win_bet"]:>9,} {roi["win_return"]:>9,} {roi["win_roi"]:>6.1f}%'
              f' {roi["place_bet"]:>9,} {roi["place_return"]:>9,} {roi["place_roi"]:>6.1f}%')

    # === Method A 有無比較 ===
    print(f'\n{"=" * 70}')
    print(f'  Method A 有無比較')
    print(f'{"=" * 70}')

    # Method A なし版
    race_preds_no_offset = df_to_race_predictions(df_test, grade_offsets=None)

    comparison_configs = [
        ('standard', PRESETS['standard']),
        ('wide', PRESETS['wide']),
    ]

    print(f'  {"Preset":>14} {"Mode":>12} {"Bets":>5} {"TotalBet":>10} '
          f'{"TotalRet":>10} {"ROI":>7} {"Hits":>5}')
    print(f'  {"-" * 70}')

    for name, params in comparison_configs:
        for mode, preds in [('Method A', race_preds), ('No offset', race_preds_no_offset)]:
            recs = generate_recommendations(preds, params, budget=30000)
            roi = calc_bet_engine_roi(recs, preds)
            marker = ' ***' if roi['total_roi'] >= 100 else ''
            print(f'  {name:>14} {mode:>12} {roi["num_bets"]:>5} '
                  f'{roi["total_bet"]:>10,} {roi["total_return"]:>10,} {roi["total_roi"]:>6.1f}%{marker}'
                  f' {roi["win_hits"]:>5}')

    # === Win-only rating sweep ===
    print(f'\n{"=" * 70}')
    print(f'  Win-only rating sweep (Method A)')
    print(f'{"=" * 70}')
    print(f'  {"win_gap":>8} {"min_rating":>11} {"Bets":>5} {"WinBet":>9} '
          f'{"WinRet":>9} {"WinROI":>7} {"Hits":>5}')
    print(f'  {"-" * 65}')

    for win_gap in [4, 5, 6]:
        for min_rating in [50.0, 53.0, 56.6, 59.0, 62.0, 99.0]:
            params = BetStrategyParams(
                win_min_gap=win_gap,
                win_min_rating=min_rating,
                place_min_gap=99,  # Place無効化
            )
            recs = generate_recommendations(race_preds, params, budget=30000)
            if not recs:
                continue
            roi = calc_bet_engine_roi(recs, race_preds)
            rating_label = 'none' if min_rating >= 90 else f'{min_rating:.1f}'
            marker = ' ***' if roi['win_roi'] >= 100 else ''
            print(f'  {win_gap:>8} {rating_label:>11} {roi["num_bets"]:>8} '
                  f'{roi["win_bet"]:>9,} {roi["win_return"]:>9,} {roi["win_roi"]:>6.1f}%{marker}'
                  f' {roi["win_hits"]:>5}')

    print('\nDone.')


if __name__ == '__main__':
    main()
