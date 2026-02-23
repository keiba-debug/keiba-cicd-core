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

    # === AR偏差値足切りスイープ ===
    print(f'\n{"=" * 70}')
    print(f'  AR偏差値足切りスイープ (Method A)')
    print(f'{"=" * 70}')
    print(f'  {"win_gap":>8} {"min_dev":>8} {"Bets":>5} {"WinBet":>9} '
          f'{"WinRet":>9} {"WinROI":>7} {"Hits":>5} {"HitRate":>8} '
          f'{"P&L":>8} {"Grade分布"}')
    print(f'  {"-" * 95}')

    for win_gap in [5, 6]:
        for min_dev in [0.0, 35.0, 40.0, 43.0, 45.0, 47.0, 50.0]:
            params = BetStrategyParams(
                win_min_gap=win_gap,
                win_min_ar_deviation=min_dev,
                place_min_gap=99,  # Place無効化
            )
            recs = generate_recommendations(race_preds, params, budget=30000)
            if not recs:
                continue
            roi = calc_bet_engine_roi(recs, race_preds)

            # グレード別件数集計
            grade_counts = {}
            for r in recs:
                for race in race_preds:
                    if race['race_id'] == r.race_id:
                        g = race.get('grade', '?') or '?'
                        grade_counts[g] = grade_counts.get(g, 0) + 1
                        break

            hit_rate = roi['win_hits'] / roi['num_bets'] * 100 if roi['num_bets'] > 0 else 0
            pnl = roi['win_return'] - roi['win_bet']
            dev_label = 'none' if min_dev == 0 else f'{min_dev:.0f}'
            marker = ' ***' if roi['win_roi'] >= 100 else ''
            grade_str = ' '.join(f'{g}:{c}' for g, c in sorted(grade_counts.items())[:5])
            print(f'  {win_gap:>8} {dev_label:>8} {roi["num_bets"]:>5} '
                  f'{roi["win_bet"]:>9,} {roi["win_return"]:>9,} {roi["win_roi"]:>6.1f}%{marker}'
                  f' {roi["win_hits"]:>5} {hit_rate:>7.1f}%'
                  f' {pnl:>+8,} {grade_str}')

    # === 偏差値フィルタで削られた勝ち馬の確認 ===
    print(f'\n{"=" * 70}')
    print(f'  偏差値フィルタで削られた勝ち馬（gap>=6, dev<45）')
    print(f'{"=" * 70}')

    # gap>=6でフィルタなし版
    params_no_filter = BetStrategyParams(
        win_min_gap=6, win_min_ar_deviation=0.0, place_min_gap=99,
    )
    recs_no_filter = generate_recommendations(race_preds, params_no_filter, budget=30000)

    # gap>=6でdev>=45版
    params_dev45 = BetStrategyParams(
        win_min_gap=6, win_min_ar_deviation=45.0, place_min_gap=99,
    )
    recs_dev45 = generate_recommendations(race_preds, params_dev45, budget=30000)

    # 勝ち馬の差分を抽出
    no_filter_wins = set()
    for r in recs_no_filter:
        for race in race_preds:
            if race['race_id'] == r.race_id:
                for e in race['entries']:
                    if e['umaban'] == r.umaban and e.get('is_win', 0) == 1:
                        no_filter_wins.add((r.race_id, r.umaban))
                break

    dev45_set = {(r.race_id, r.umaban) for r in recs_dev45}
    lost_winners = no_filter_wins - {k for k in no_filter_wins if k in dev45_set}

    if lost_winners:
        print(f'  削られた勝ち馬: {len(lost_winners)}頭')
        for race_id, umaban in sorted(lost_winners):
            for race in race_preds:
                if race['race_id'] == race_id:
                    for e in race['entries']:
                        if e['umaban'] == umaban:
                            print(f'    {race_id} 馬番{umaban} {e.get("horse_name","")} '
                                  f'AR={e.get("predicted_margin","?"):.1f} dev={e.get("ar_deviation","?"):.1f} '
                                  f'odds={e.get("odds",0):.1f} gap={e.get("win_vb_gap",0)} '
                                  f'grade={race.get("grade","")}')
                    break
    else:
        print('  削られた勝ち馬: なし')

    # === EV (期待値) スイープ ===
    print(f'\n{"=" * 70}')
    print(f'  EV (期待値) スイープ')
    print(f'{"=" * 70}')
    print(f'  {"min_ev":>8} {"min_dev":>8} {"Bets":>5} {"WinBet":>9} '
          f'{"WinRet":>9} {"WinROI":>7} {"Hits":>5} {"HitRate":>8} '
          f'{"P&L":>8}')
    print(f'  {"-" * 75}')

    for min_ev in [1.0, 1.1, 1.2, 1.3, 1.5, 2.0]:
        for min_dev in [0.0, 43.0, 45.0, 47.0, 50.0]:
            params = BetStrategyParams(
                win_min_ev=min_ev,
                win_min_ar_deviation=min_dev,
                place_min_gap=99,  # Place無効化
            )
            recs = generate_recommendations(race_preds, params, budget=30000)
            if not recs:
                continue
            roi = calc_bet_engine_roi(recs, race_preds)

            hit_rate = roi['win_hits'] / roi['num_bets'] * 100 if roi['num_bets'] > 0 else 0
            pnl = roi['win_return'] - roi['win_bet']
            ev_label = f'{min_ev:.1f}'
            dev_label = 'none' if min_dev == 0 else f'{min_dev:.0f}'
            marker = ' ***' if roi['win_roi'] >= 100 else ''
            print(f'  {ev_label:>8} {dev_label:>8} {roi["num_bets"]:>5} '
                  f'{roi["win_bet"]:>9,} {roi["win_return"]:>9,} {roi["win_roi"]:>6.1f}%{marker}'
                  f' {roi["win_hits"]:>5} {hit_rate:>7.1f}%'
                  f' {pnl:>+8,}')

    # === Gap vs EV 直接比較 ===
    print(f'\n{"=" * 70}')
    print(f'  Gap vs EV 直接比較')
    print(f'{"=" * 70}')
    print(f'  {"条件":>30} {"Bets":>5} {"WinBet":>9} '
          f'{"WinRet":>9} {"WinROI":>7} {"Hits":>5} {"HitRate":>8} '
          f'{"P&L":>8}')
    print(f'  {"-" * 90}')

    comparison_conditions = [
        ('gap>=6 (旧standard)', BetStrategyParams(win_min_gap=6, place_min_gap=99)),
        ('gap>=5 (旧wide)', BetStrategyParams(win_min_gap=5, place_min_gap=99)),
        ('gap>=6 dev>=45 (前回)', BetStrategyParams(win_min_gap=6, win_min_ar_deviation=45.0, place_min_gap=99)),
        ('EV>=1.3 dev>=47 (新standard)', BetStrategyParams(win_min_ev=1.3, win_min_ar_deviation=47.0, place_min_gap=99)),
        ('EV>=1.2 dev>=45 (新wide)', BetStrategyParams(win_min_ev=1.2, win_min_ar_deviation=45.0, place_min_gap=99)),
        ('EV>=1.1 dev>=45', BetStrategyParams(win_min_ev=1.1, win_min_ar_deviation=45.0, place_min_gap=99)),
        ('EV>=1.5 dev>=45', BetStrategyParams(win_min_ev=1.5, win_min_ar_deviation=45.0, place_min_gap=99)),
        ('EV>=1.3 no-dev', BetStrategyParams(win_min_ev=1.3, place_min_gap=99)),
        ('EV>=1.2 no-dev', BetStrategyParams(win_min_ev=1.2, place_min_gap=99)),
    ]

    for label, params in comparison_conditions:
        recs = generate_recommendations(race_preds, params, budget=30000)
        if not recs:
            print(f'  {label:>30} {"---":>5}')
            continue
        roi = calc_bet_engine_roi(recs, race_preds)
        hit_rate = roi['win_hits'] / roi['num_bets'] * 100 if roi['num_bets'] > 0 else 0
        pnl = roi['win_return'] - roi['win_bet']
        marker = ' ***' if roi['win_roi'] >= 100 else ''
        print(f'  {label:>30} {roi["num_bets"]:>5} '
              f'{roi["win_bet"]:>9,} {roi["win_return"]:>9,} {roi["win_roi"]:>6.1f}%{marker}'
              f' {roi["win_hits"]:>5} {hit_rate:>7.1f}%'
              f' {pnl:>+8,}')

    # === WVモデル キャリブレーション診断 ===
    print(f'\n{"=" * 70}')
    print(f'  WVモデル キャリブレーション診断 (pred_proba_wv vs 実勝率)')
    print(f'{"=" * 70}')

    # df_test の pred_proba_wv (calibrated) と実勝率を比較
    cal_df = df_test[['race_id', 'is_win', 'odds']].copy()
    cal_df['pred_win_prob'] = pred_wv_cal
    cal_df['win_ev'] = cal_df['pred_win_prob'] * cal_df['odds']

    # 確率帯別の実勝率
    prob_bins = [0, 0.02, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50, 1.0]
    cal_df['prob_bin'] = pd.cut(cal_df['pred_win_prob'], bins=prob_bins)

    print(f'  {"prob_range":>16} {"N":>6} {"wins":>5} {"actual%":>8} {"pred_avg%":>10} '
          f'{"avg_odds":>9} {"avg_EV":>7} {"ROI%":>7}')
    print(f'  {"-" * 80}')

    for bin_label, group in cal_df.groupby('prob_bin', observed=False):
        n = len(group)
        if n == 0:
            continue
        wins = int(group['is_win'].sum())
        actual_rate = wins / n * 100
        pred_avg = group['pred_win_prob'].mean() * 100
        avg_odds = group['odds'].mean()
        avg_ev = group['win_ev'].mean()
        # ROI: 100円均一で計算
        total_bet = n * 100
        total_return = int((group['is_win'] * group['odds'] * 100).sum())
        roi_pct = total_return / total_bet * 100 if total_bet > 0 else 0
        print(f'  {str(bin_label):>16} {n:>6} {wins:>5} {actual_rate:>7.2f}% {pred_avg:>9.2f}% '
              f'{avg_odds:>9.1f} {avg_ev:>7.2f} {roi_pct:>6.1f}%')

    # EV帯別の実ROI
    print(f'\n  --- EV帯別 実ROI (rank_wv <= 3 のみ) ---')
    ev_df = cal_df.copy()
    ev_df['rank_wv'] = df_test.groupby('race_id')['pred_proba_wv'].rank(ascending=False, method='min')
    ev_df = ev_df[ev_df['rank_wv'] <= 3]

    ev_bins = [0, 0.5, 0.8, 1.0, 1.2, 1.3, 1.5, 2.0, 3.0, 100]
    ev_df['ev_bin'] = pd.cut(ev_df['win_ev'], bins=ev_bins)

    print(f'  {"ev_range":>16} {"N":>6} {"wins":>5} {"win%":>7} {"avg_odds":>9} '
          f'{"avg_EV":>7} {"ROI%":>7} {"P&L":>8}')
    print(f'  {"-" * 75}')

    for bin_label, group in ev_df.groupby('ev_bin', observed=False):
        n = len(group)
        if n == 0:
            continue
        wins = int(group['is_win'].sum())
        win_rate = wins / n * 100
        avg_odds = group['odds'].mean()
        avg_ev = group['win_ev'].mean()
        total_bet = n * 100
        total_return = int((group['is_win'] * group['odds'] * 100).sum())
        roi_pct = total_return / total_bet * 100 if total_bet > 0 else 0
        pnl = total_return - total_bet
        marker = ' ***' if roi_pct >= 100 else ''
        print(f'  {str(bin_label):>16} {n:>6} {wins:>5} {win_rate:>6.2f}% {avg_odds:>9.1f} '
              f'{avg_ev:>7.2f} {roi_pct:>6.1f}%{marker} {pnl:>+8,}')

    print('\nDone.')


if __name__ == '__main__':
    main()
