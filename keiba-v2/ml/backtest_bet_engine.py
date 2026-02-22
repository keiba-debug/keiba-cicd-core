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
    race_preds = df_to_race_predictions(df_test)
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

    # === Win margin最適化 ===
    print(f'\n{"=" * 70}')
    print(f'  Win margin 最適化 (Place無し)')
    print(f'{"=" * 70}')
    print(f'  {"win_gap":>8} {"win_margin":>11} {"WinBets":>8} {"WinBet":>9} '
          f'{"WinRet":>9} {"WinROI":>7} {"Hits":>5}')
    print(f'  {"-" * 65}')

    for win_gap in [3, 4, 5, 6]:
        for win_margin in [0.6, 0.8, 1.0, 1.2, 1.5, 2.0, 99.0]:
            params = BetStrategyParams(
                win_min_gap=win_gap,
                win_max_margin=win_margin,
                place_min_gap=99,  # Place無効化
            )
            recs = generate_recommendations(race_preds, params, budget=30000)
            if not recs:
                continue
            roi = calc_bet_engine_roi(recs, race_preds)
            margin_label = 'none' if win_margin >= 90 else f'{win_margin:.1f}'
            marker = ' ***' if roi['win_roi'] >= 100 else ''
            print(f'  {win_gap:>8} {margin_label:>11} {roi["num_bets"]:>8} '
                  f'{roi["win_bet"]:>9,} {roi["win_return"]:>9,} {roi["win_roi"]:>6.1f}%{marker}'
                  f' {roi["win_hits"]:>5}')

    # === Place margin最適化 ===
    print(f'\n{"=" * 70}')
    print(f'  Place margin 最適化 (Win無し)')
    print(f'{"=" * 70}')
    print(f'  {"plc_gap":>8} {"plc_margin":>11} {"plc_ev":>7} {"Bets":>5} '
          f'{"PlcBet":>9} {"PlcRet":>9} {"PlcROI":>7} {"Hits":>5}')
    print(f'  {"-" * 70}')

    for place_gap in [2, 3, 4, 5]:
        for place_margin in [0.6, 0.8, 1.0, 1.5, 99.0]:
            for place_ev in [0.9, 1.0, 1.1, 1.2]:
                params = BetStrategyParams(
                    win_min_gap=99,  # Win無効化
                    place_min_gap=place_gap,
                    place_max_margin=place_margin,
                    place_min_ev=place_ev,
                )
                recs = generate_recommendations(race_preds, params, budget=30000)
                if not recs:
                    continue
                roi = calc_bet_engine_roi(recs, race_preds)
                margin_label = 'none' if place_margin >= 90 else f'{place_margin:.1f}'
                marker = ' ***' if roi['place_roi'] >= 100 else ''
                print(f'  {place_gap:>8} {margin_label:>11} {place_ev:>7.1f} {roi["num_bets"]:>5} '
                      f'{roi["place_bet"]:>9,} {roi["place_return"]:>9,} {roi["place_roi"]:>6.1f}%{marker}'
                      f' {roi["place_hits"]:>5}')

    # === 総合グリッドサーチ（Win+Place最適化済み組み合わせ）===
    print(f'\n{"=" * 70}')
    print(f'  総合グリッドサーチ')
    print(f'{"=" * 70}')
    print(f'  {"wg":>3} {"wm":>4} {"pg":>3} {"pm":>4} {"pev":>4} {"Bets":>5} '
          f'{"TotalROI":>9} {"WinROI":>7} {"PlcROI":>7} {"Total$":>10}')
    print(f'  {"-" * 65}')

    best_roi = 0
    best_params_str = ''

    for win_gap in [4, 5, 6]:
        for win_margin in [1.0, 1.2, 1.5]:
            for place_gap in [3, 4, 5]:
                for place_margin in [0.8, 1.0, 1.5]:
                    for place_ev in [1.0, 1.1, 1.2]:
                        params = BetStrategyParams(
                            win_min_gap=win_gap,
                            win_max_margin=win_margin,
                            place_min_gap=place_gap,
                            place_max_margin=place_margin,
                            place_min_ev=place_ev,
                        )
                        recs = generate_recommendations(race_preds, params, budget=30000)
                        if not recs:
                            continue
                        roi = calc_bet_engine_roi(recs, race_preds)
                        if roi['total_roi'] > best_roi:
                            best_roi = roi['total_roi']
                            best_params_str = f'wg={win_gap} wm={win_margin} pg={place_gap} pm={place_margin} pev={place_ev}'
                        if roi['total_roi'] >= 95:
                            marker = ' ***' if roi['total_roi'] >= 100 else ''
                            net = roi['total_return'] - roi['total_bet']
                            print(f'  {win_gap:>3} {win_margin:>4.1f} {place_gap:>3} {place_margin:>4.1f} {place_ev:>4.1f} '
                                  f'{roi["num_bets"]:>5} {roi["total_roi"]:>8.1f}%{marker} '
                                  f'{roi["win_roi"]:>6.1f}% {roi["place_roi"]:>6.1f}% '
                                  f'{net:>+10,}')

    print(f'\n  Best: {best_params_str} → ROI {best_roi:.1f}%')

    # === Win-only プリセット ===
    print(f'\n{"=" * 70}')
    print(f'  Win-only プリセット比較')
    print(f'{"=" * 70}')

    win_only_configs = [
        ('win_g4_m1.2', BetStrategyParams(win_min_gap=4, win_max_margin=1.2, place_min_gap=99)),
        ('win_g5_m1.2', BetStrategyParams(win_min_gap=5, win_max_margin=1.2, place_min_gap=99)),
        ('win_g5_m1.5', BetStrategyParams(win_min_gap=5, win_max_margin=1.5, place_min_gap=99)),
        ('win_g6_m1.2', BetStrategyParams(win_min_gap=6, win_max_margin=1.2, place_min_gap=99)),
        ('win_g4_none', BetStrategyParams(win_min_gap=4, win_max_margin=99, place_min_gap=99)),
        ('win_g5_none', BetStrategyParams(win_min_gap=5, win_max_margin=99, place_min_gap=99)),
    ]

    print(f'  {"Name":>14} {"Bets":>5} {"WinBet":>9} {"WinRet":>9} {"WinROI":>7} {"Net":>10} {"Hits":>5}')
    print(f'  {"-" * 65}')

    for name, params in win_only_configs:
        recs = generate_recommendations(race_preds, params, budget=30000)
        if not recs:
            continue
        roi = calc_bet_engine_roi(recs, race_preds)
        net = roi['win_return'] - roi['win_bet']
        marker = ' ***' if roi['win_roi'] >= 100 else ''
        print(f'  {name:>14} {roi["num_bets"]:>5} '
              f'{roi["win_bet"]:>9,} {roi["win_return"]:>9,} {roi["win_roi"]:>6.1f}%{marker}'
              f' {net:>+10,} {roi["win_hits"]:>5}')

    print('\nDone.')


if __name__ == '__main__':
    main()
