#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
bet_engine バックテスト

liveモデル（保存済み）をロードしてテストデータに対して
bet_engine の各プリセットを適用し、実ROIを計算する。

Usage:
    python -m ml.backtest_bet_engine
    python -m ml.backtest_bet_engine --retrain   # 旧方式：独自にモデル学習
"""

import argparse
import json
import pickle
import re
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core import config
from ml.experiment import (
    load_data, build_dataset, load_race_json,
    FEATURE_COLS_ALL, FEATURE_COLS_VALUE,
    PARAMS_P, PARAMS_W, PARAMS_AR,
    train_model, train_regression_model, _get_place_odds,
    build_pit_personnel_timeline,
)
from ml.features.margin_target import add_margin_target_to_df
from ml.features.baba_features import load_baba_index, get_baba_features
from ml.bet_engine import (
    PRESETS, BetStrategyParams,
    generate_recommendations, recommendations_summary,
    df_to_race_predictions, calc_bet_engine_roi,
    load_grade_offsets, compute_vb_score,
)
from ml.experiment import compute_features_for_race
from ml.features.closing_race_features import (
    CLOSING_RACE_FEATURES,
    CourseClosingTimeline,
    compute_closing_race_features,
)


def compute_closing_probas(
    df_test,
    history_cache, trainer_index, jockey_index,
    pace_index, kb_ext_index, date_index,
    baba_index,
    race_level_index=None, pedigree_index=None,
    sire_stats_index=None,
    pit_trainer_tl=None, pit_jockey_tl=None,
    jrdb_sed_index=None, jrdb_kyi_index=None, jrdb_kaa_index=None,
) -> dict:
    """テスト用レースの closing_race_proba を計算

    Returns:
        {race_id_str: proba} の辞書
    """
    ml_dir = config.ml_dir()
    model_path = ml_dir / "model_closing.txt"
    cal_path = ml_dir / "calibrator_closing.pkl"
    meta_path = ml_dir / "model_closing_meta.json"

    if not model_path.exists():
        print('[Closing] model_closing.txt not found, skipping')
        return {}

    model = lgb.Booster(model_file=str(model_path))
    calibrator = None
    if cal_path.exists():
        with open(cal_path, 'rb') as f:
            calibrator = pickle.load(f)

    meta = {}
    if meta_path.exists():
        with open(meta_path, encoding='utf-8') as f:
            meta = json.load(f)

    features = meta.get('features', CLOSING_RACE_FEATURES)

    # CourseClosingTimeline を構築
    from ml.experiment_closing import build_course_timeline
    course_timeline = build_course_timeline(date_index)

    # race_id → date の逆引きマップを構築
    rid_to_date = {}
    for date_str, day_data in date_index.items():
        if isinstance(day_data, dict) and 'tracks' in day_data:
            for track in day_data['tracks']:
                for race in track.get('races', []):
                    rid_to_date[str(race['id'])] = date_str
        elif isinstance(day_data, list):
            for rid in day_data:
                rid_to_date[str(rid)] = date_str

    # テストの全race_idを取得
    race_ids = df_test['race_id'].unique()
    print(f'[Closing] Computing closing_race_proba for {len(race_ids)} races...')

    results = {}
    errors = 0
    skipped = 0
    sample_errors = []
    for race_id in race_ids:
        try:
            rid_str = str(race_id)
            date_str = rid_to_date.get(rid_str)
            if not date_str:
                # race_idから日付を推定 (YYYYMMDD...)
                date_str = f'{rid_str[:4]}-{rid_str[4:6]}-{rid_str[6:8]}'

            race = load_race_json(rid_str, date_str)
            if race is None:
                skipped += 1
                continue

            track_type = race.get('track_type', '')
            if track_type == 'obstacle' or '障害' in race.get('race_name', ''):
                skipped += 1
                continue
            if race.get('num_runners', 0) < 8:
                skipped += 1
                continue

            horse_features = compute_features_for_race(
                race, history_cache, trainer_index, jockey_index,
                pace_index, kb_ext_index,
                race_level_index=race_level_index,
                pedigree_index=pedigree_index,
                sire_stats_index=sire_stats_index,
                pit_trainer_tl=pit_trainer_tl,
                pit_jockey_tl=pit_jockey_tl,
                jrdb_sed_index=jrdb_sed_index,
                jrdb_kyi_index=jrdb_kyi_index,
                jrdb_kaa_index=jrdb_kaa_index,
            )

            baba_feat = get_baba_features(rid_str, track_type, baba_index)

            race_feat = compute_closing_race_features(
                race, horse_features,
                course_timeline=course_timeline,
                baba_features=baba_feat,
            )

            feat_values = [race_feat.get(f, np.nan) for f in features]
            X = np.array([feat_values])
            pred_raw = float(model.predict(X)[0])

            if calibrator is not None:
                pred_cal = float(calibrator.predict([pred_raw])[0])
                pred_cal = max(0.0, min(1.0, pred_cal))
            else:
                pred_cal = pred_raw

            results[rid_str] = round(pred_cal, 4)
        except Exception as e:
            errors += 1
            if len(sample_errors) < 3:
                sample_errors.append(f'{race_id}: {e}')

    print(f'[Closing] Done: {len(results)} races predicted, {skipped} skipped, {errors} errors')
    if sample_errors:
        for se in sample_errors:
            print(f'  Sample error: {se}')
    if results:
        high_count = sum(1 for p in results.values() if p >= 0.13)
        print(f'  >= 0.13 (boost threshold): {high_count} races ({high_count/len(results)*100:.1f}%)')

    return results


def _parse_split_label(label: str):
    """model_meta split label → (min_year, max_year, min_month, max_month)

    Examples:
        '2020 ~ 2024'        → (2020, 2024, None, None)
        '2025-01 ~ 2025-02'  → (2025, 2025, 1, 2)
        '2025-03 ~ 2026-02'  → (2025, 2026, 3, 2)
    """
    m = re.match(r'(\d{4})(?:-(\d{2}))?\s*~\s*(\d{4})(?:-(\d{2}))?', label)
    if not m:
        raise ValueError(f"Cannot parse split label: {label}")
    min_y = int(m.group(1))
    max_y = int(m.group(3))
    min_m = int(m.group(2)) if m.group(2) else None
    max_m = int(m.group(4)) if m.group(4) else None
    return min_y, max_y, min_m, max_m


def main():
    parser = argparse.ArgumentParser(description='bet_engine バックテスト')
    parser.add_argument('--retrain', action='store_true',
                        help='独自にモデル学習（旧方式、liveモデルとは異なる結果）')
    parser.add_argument('--sire-cutoff', type=str, default=None,
                        help='血統統計カットオフ日 (YYYY-MM-DD)。未指定時はmodel_metaから自動取得')
    args = parser.parse_args()

    print('=' * 70)
    if args.retrain:
        print('  bet_engine バックテスト (retrain mode: 独自学習)')
    else:
        print('  bet_engine バックテスト (live model mode)')
    print('=' * 70)

    # === sire_cutoff 決定 ===
    sire_cutoff = args.sire_cutoff
    if not sire_cutoff and not args.retrain:
        # liveモデルのmodel_metaからsire_cutoffを取得
        meta_path = config.ml_dir() / "model_meta.json"
        if meta_path.exists():
            with open(meta_path, encoding='utf-8') as f:
                _meta = json.load(f)
            sire_cutoff = _meta.get('sire_cutoff')
            if sire_cutoff:
                print(f'[Sire] Using cutoff from model_meta: {sire_cutoff}')
            else:
                # model_metaにsire_cutoff未記録の場合、trainの末日から推定
                split = _meta.get('split', {})
                train_label = split.get('train', '')
                m = re.match(r'.*~\s*(\d{4})(?:-(\d{2}))?', train_label)
                if m:
                    end_y = int(m.group(1))
                    end_m = int(m.group(2)) if m.group(2) else 12
                    import calendar
                    end_d = calendar.monthrange(end_y, end_m)[1]
                    sire_cutoff = f'{end_y}-{end_m:02d}-{end_d:02d}'
                    print(f'[Sire] Derived cutoff from train split "{train_label}": {sire_cutoff}')
    elif not sire_cutoff and args.retrain:
        # retrain: 訓練期間2020-2023 → cutoff=2023-12-31
        sire_cutoff = '2023-12-31'
        print(f'[Sire] Using retrain cutoff: {sire_cutoff}')

    if not sire_cutoff:
        print('[Sire] WARNING: sire_cutoff未設定 → 全データの血統統計を使用（リーク注意！）')

    # === データロード ===
    print('\n[Load] Loading data...')
    (history_cache, trainer_index, jockey_index,
     date_index, pace_index, kb_ext_index, training_summary_index,
     race_level_index, pedigree_index, sire_stats_index,
     jrdb_sed_index, jrdb_kyi_index, jrdb_kaa_index) = load_data(
        sire_cutoff=sire_cutoff)

    # PIT timelines
    pit_trainer_tl, pit_jockey_tl = build_pit_personnel_timeline()
    baba_index = load_baba_index()

    if args.retrain:
        # === 旧方式: 独自にモデル学習 (2020-2023/2024/2025-2026) ===
        df_train = build_dataset(
            date_index, history_cache, trainer_index, jockey_index, pace_index,
            kb_ext_index, 2020, 2023, use_db_odds=True,
            training_summary_index=training_summary_index,
            race_level_index=race_level_index,
            pedigree_index=pedigree_index,
            sire_stats_index=sire_stats_index,
            pit_trainer_tl=pit_trainer_tl, pit_jockey_tl=pit_jockey_tl,
            baba_index=baba_index,
            jrdb_sed_index=jrdb_sed_index, jrdb_kyi_index=jrdb_kyi_index,
            jrdb_kaa_index=jrdb_kaa_index,
        )
        df_val = build_dataset(
            date_index, history_cache, trainer_index, jockey_index, pace_index,
            kb_ext_index, 2024, 2024, use_db_odds=True,
            training_summary_index=training_summary_index,
            race_level_index=race_level_index,
            pedigree_index=pedigree_index,
            sire_stats_index=sire_stats_index,
            pit_trainer_tl=pit_trainer_tl, pit_jockey_tl=pit_jockey_tl,
            baba_index=baba_index,
            jrdb_sed_index=jrdb_sed_index, jrdb_kyi_index=jrdb_kyi_index,
            jrdb_kaa_index=jrdb_kaa_index,
        )
        df_test = build_dataset(
            date_index, history_cache, trainer_index, jockey_index, pace_index,
            kb_ext_index, 2025, 2026, use_db_odds=True,
            training_summary_index=training_summary_index,
            race_level_index=race_level_index,
            pedigree_index=pedigree_index,
            sire_stats_index=sire_stats_index,
            pit_trainer_tl=pit_trainer_tl, pit_jockey_tl=pit_jockey_tl,
            baba_index=baba_index,
            jrdb_sed_index=jrdb_sed_index, jrdb_kyi_index=jrdb_kyi_index,
            jrdb_kaa_index=jrdb_kaa_index,
        )
        print(f'[Dataset] Train={len(df_train):,}, Val={len(df_val):,}, Test={len(df_test):,}')

        print('\n[Train] Training classification models...')
        _, _, _, pred_p, cal_p, pred_p_raw = train_model(
            df_train, df_val, df_test, FEATURE_COLS_VALUE, PARAMS_P, 'is_top3', 'Place'
        )
        _, _, _, pred_w, cal_w, pred_w_raw = train_model(
            df_train, df_val, df_test, FEATURE_COLS_VALUE, PARAMS_W, 'is_win', 'Win'
        )

        print('\n[Margin] Computing target_margin...')
        for label, df in [('train', df_train), ('val', df_val), ('test', df_test)]:
            add_margin_target_to_df(df, date_index, load_race_json, cap=5.0)

        _, _, _, pred_ar = train_regression_model(
            df_train, df_val, df_test, FEATURE_COLS_VALUE, PARAMS_AR, 'Aura'
        )
    else:
        # === 新方式: liveモデルをロードしてテストデータで予測 ===
        ml_dir = config.ml_dir()
        meta_path = ml_dir / "model_meta.json"
        with open(meta_path, encoding='utf-8') as f:
            meta = json.load(f)

        split = meta['split']
        features_value = meta['features_value']
        print(f'[Model] v{meta["version"]}: {split["train"]} → {split["test"]}')
        print(f'[Model] Features: {len(features_value)}')

        # Load models
        model_p = lgb.Booster(model_file=str(ml_dir / "model_p.txt"))
        model_w = lgb.Booster(model_file=str(ml_dir / "model_w.txt"))
        model_ar = lgb.Booster(model_file=str(ml_dir / "model_ar.txt"))

        # Load calibrators
        cal_p, cal_w = None, None
        cal_path = ml_dir / "calibrators.pkl"
        if cal_path.exists():
            with open(cal_path, 'rb') as f:
                cals = pickle.load(f)
            cal_p = cals.get('cal_p')
            cal_w = cals.get('cal_w')
            print(f'[Model] Calibrators: {list(cals.keys())}')

        # Build test dataset using model's split
        test_min_y, test_max_y, test_min_m, test_max_m = _parse_split_label(split['test'])
        print(f'[Dataset] Test period: {split["test"]}')

        df_test = build_dataset(
            date_index, history_cache, trainer_index, jockey_index, pace_index,
            kb_ext_index, test_min_y, test_max_y, use_db_odds=True,
            training_summary_index=training_summary_index,
            race_level_index=race_level_index,
            pedigree_index=pedigree_index,
            sire_stats_index=sire_stats_index,
            min_month=test_min_m, max_month=test_max_m,
            pit_trainer_tl=pit_trainer_tl, pit_jockey_tl=pit_jockey_tl,
            baba_index=baba_index,
            jrdb_sed_index=jrdb_sed_index, jrdb_kyi_index=jrdb_kyi_index,
            jrdb_kaa_index=jrdb_kaa_index,
        )
        print(f'[Dataset] Test={len(df_test):,}')

        # Margin target
        print('\n[Margin] Computing target_margin...')
        add_margin_target_to_df(df_test, date_index, load_race_json, cap=5.0)

        # Predict using loaded models (per-model features if Optuna optimized)
        features_per_model = meta.get('features_per_model')
        feats_p = features_per_model['p'] if features_per_model and 'p' in features_per_model else features_value
        feats_w = features_per_model['w'] if features_per_model and 'w' in features_per_model else features_value
        feats_ar = features_per_model['ar'] if features_per_model and 'ar' in features_per_model else features_value
        pred_p = model_p.predict(df_test[feats_p].values)
        pred_w = model_w.predict(df_test[feats_w].values)
        pred_ar = model_ar.predict(df_test[feats_ar].values)

        print(f'[Predict] P: mean={pred_p.mean():.4f}, W: mean={pred_w.mean():.4f}, '
              f'AR: mean={pred_ar.mean():.2f}')

    df_test['pred_margin_ar'] = pred_ar

    # 予測結果をDataFrameに追加
    df_test['pred_proba_p'] = pred_p
    df_test['pred_rank_p'] = df_test.groupby('race_id')['pred_proba_p'].rank(
        ascending=False, method='min'
    )
    df_test['pred_proba_w'] = pred_w
    df_test['pred_rank_w'] = df_test.groupby('race_id')['pred_proba_w'].rank(
        ascending=False, method='min'
    )

    # raw確率（Kelly用）
    df_test['pred_proba_p_raw'] = pred_p

    # VB gap
    df_test['vb_gap'] = (df_test['odds_rank'] - df_test['pred_rank_p']).clip(lower=0).astype(int)
    df_test['win_vb_gap'] = (df_test['odds_rank'] - df_test['pred_rank_w']).clip(lower=0).astype(int)

    # EV (calibrated)
    if cal_p is not None:
        pred_p_cal = cal_p.predict(pred_p)
    else:
        pred_p_cal = pred_p
    if cal_w is not None:
        pred_w_cal = cal_w.predict(pred_w)
    else:
        pred_w_cal = pred_w

    df_test['win_ev'] = pred_w_cal * df_test['odds']
    place_odds_col = df_test['place_odds_low'].fillna(df_test['odds'] / 3.5)
    df_test['place_ev'] = pred_p_cal * place_odds_col

    # === Closing Model 推論 ===
    closing_proba_map = compute_closing_probas(
        df_test,
        history_cache, trainer_index, jockey_index,
        pace_index, kb_ext_index, date_index,
        baba_index,
        race_level_index=race_level_index,
        pedigree_index=pedigree_index,
        sire_stats_index=sire_stats_index,
        pit_trainer_tl=pit_trainer_tl,
        pit_jockey_tl=pit_jockey_tl,
        jrdb_sed_index=jrdb_sed_index,
        jrdb_kyi_index=jrdb_kyi_index,
        jrdb_kaa_index=jrdb_kaa_index,
    )

    # === bet_engine バックテスト ===
    print('\n[BetEngine] Converting to race predictions format...')
    grade_offsets = load_grade_offsets()
    if grade_offsets:
        print(f'  Method A: {len(grade_offsets)} grade offsets loaded')
    race_preds = df_to_race_predictions(
        df_test, grade_offsets=grade_offsets,
        closing_proba_map=closing_proba_map,
    )
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
    race_preds_no_offset = df_to_race_predictions(df_test, grade_offsets=None, closing_proba_map=closing_proba_map)

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
        for min_rating in [34.0, 37.0, 40.0, 42.5, 45.0, 99.0]:  # IDMスケール
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

    # === Composite VB Score Sweep ===
    print(f'\n{"=" * 70}')
    print(f'  Composite VB Score Sweep')
    print(f'{"=" * 70}')
    print(f'  {"score":>6} {"min_ev":>7} {"Bets":>5} {"WinBet":>9} '
          f'{"WinRet":>9} {"WinROI":>7} {"Hits":>5} {"HitRate":>8} '
          f'{"P&L":>8} {"Strong":>7}')
    print(f'  {"-" * 85}')

    for min_score in [3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0]:
        for min_ev in [0.0, 1.0, 1.5]:
            params = BetStrategyParams(
                win_min_vb_score=min_score,
                win_min_ev=min_ev,
                win_v_ratio_min=0.75,
                win_v_bypass_gap=7,
                win_v_bypass_ev=3.0,
                ard_vb_min_ard=65.0,
                ard_vb_min_odds=10.0,
                place_min_gap=99,
                max_win_per_race=2,
            )
            recs = generate_recommendations(race_preds, params, budget=30000)
            if not recs:
                continue
            roi = calc_bet_engine_roi(recs, race_preds)
            hit_rate = roi['win_hits'] / roi['num_bets'] * 100 if roi['num_bets'] > 0 else 0
            pnl = roi['win_return'] - roi['win_bet']
            strong_count = sum(1 for r in recs if r.strength == 'strong')
            ev_label = f'{min_ev:.1f}' if min_ev > 0 else 'none'
            marker = ' ***' if roi['win_roi'] >= 100 else ''
            print(f'  {min_score:>6.1f} {ev_label:>7} {roi["num_bets"]:>5} '
                  f'{roi["win_bet"]:>9,} {roi["win_return"]:>9,} {roi["win_roi"]:>6.1f}%{marker}'
                  f' {roi["win_hits"]:>5} {hit_rate:>7.1f}%'
                  f' {pnl:>+8,} {strong_count:>5}S')

    # === Score分布の確認 ===
    print(f'\n{"=" * 70}')
    print(f'  VB Score Distribution (全テストデータ)')
    print(f'{"=" * 70}')

    all_scores = []
    for race in race_preds:
        for e in race['entries']:
            s = compute_vb_score(
                e.get('dev_gap', 0) or 0,
                e.get('vb_gap', 0) or 0,
                e.get('win_ev'),
                e.get('ar_deviation'),
            )
            all_scores.append({
                'score': s,
                'is_win': e.get('is_win', 0),
                'odds': e.get('odds', 0),
            })

    import pandas as pd
    score_df = pd.DataFrame(all_scores)
    score_bins = [0, 1, 2, 3, 4, 5, 6, 7, 8, 10]
    score_df['bin'] = pd.cut(score_df['score'], bins=score_bins, right=False)

    print(f'  {"score_range":>12} {"N":>6} {"wins":>5} {"win%":>7} {"avg_odds":>9} '
          f'{"ROI%":>7}')
    print(f'  {"-" * 55}')

    for bin_label, group in score_df.groupby('bin', observed=False):
        n = len(group)
        if n == 0:
            continue
        wins = int(group['is_win'].sum())
        win_rate = wins / n * 100
        avg_odds = group['odds'].mean()
        total_bet = n * 100
        total_return = int((group['is_win'] * group['odds'] * 100).sum())
        roi_pct = total_return / total_bet * 100 if total_bet > 0 else 0
        marker = ' ***' if roi_pct >= 100 else ''
        print(f'  {str(bin_label):>12} {n:>6} {wins:>5} {win_rate:>6.2f}% {avg_odds:>9.1f} '
              f'{roi_pct:>6.1f}%{marker}')

    # === Winモデル キャリブレーション診断 ===
    print(f'\n{"=" * 70}')
    print(f'  Winモデル キャリブレーション診断 (pred_proba_w vs 実勝率)')
    print(f'{"=" * 70}')

    # df_test の pred_proba_w (calibrated) と実勝率を比較
    cal_df = df_test[['race_id', 'is_win', 'odds']].copy()
    cal_df['pred_win_prob'] = pred_w_cal
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
    print(f'\n  --- EV帯別 実ROI (rank_w <= 3 のみ) ---')
    ev_df = cal_df.copy()
    ev_df['rank_w'] = df_test.groupby('race_id')['pred_proba_w'].rank(ascending=False, method='min')
    ev_df = ev_df[ev_df['rank_w'] <= 3]

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

    # === P Model 廃止実験: W-only vs P+W 比較 ===
    print(f'\n{"=" * 70}')
    print(f'  P Model 廃止実験: W-only vs P+W (Composite VB Score)')
    print(f'{"=" * 70}')
    print(f'  現状: gap=rank_p, dev_gap=P_raw, P%ratio=P_raw')
    print(f'  実験: gap=rank_w, dev_gap=W_raw, W%ratio=W_raw')

    # df_testのコピーで P→W に全置換
    df_test_w = df_test.copy()
    df_test_w['pred_proba_p_raw'] = pred_w        # P raw → W raw
    df_test_w['pred_rank_p'] = df_test_w['pred_rank_w']  # rank_p → rank_w
    df_test_w['vb_gap'] = df_test_w['win_vb_gap']         # gap → W gap

    race_preds_w = df_to_race_predictions(df_test_w, grade_offsets=grade_offsets, closing_proba_map=closing_proba_map)
    print(f'  W-only: {len(race_preds_w)} races')

    # ヘッダー
    print(f'\n  {"Preset":>14} {"Mode":>8} {"Bets":>5} {"TotalBet":>10} '
          f'{"TotalRet":>10} {"ROI":>7} {"Hits":>5} {"HitRate":>8} '
          f'{"P&L":>8} {"Strong":>7}')
    print(f'  {"-" * 100}')

    for preset_name, preset_params in PRESETS.items():
        for mode, preds in [('P+W', race_preds), ('W-only', race_preds_w)]:
            recs = generate_recommendations(preds, preset_params, budget=30000)
            roi = calc_bet_engine_roi(recs, preds)
            if roi['num_bets'] == 0:
                print(f'  {preset_name:>14} {mode:>8} {"---":>5}')
                continue
            hit_rate = roi['win_hits'] / roi['num_bets'] * 100
            pnl = roi['total_return'] - roi['total_bet']
            strong_count = sum(1 for r in recs if r.strength == 'strong')
            marker = ' ***' if roi['total_roi'] >= 100 else ''
            print(f'  {preset_name:>14} {mode:>8} {roi["num_bets"]:>5} '
                  f'{roi["total_bet"]:>10,} {roi["total_return"]:>10,} {roi["total_roi"]:>6.1f}%{marker}'
                  f' {roi["win_hits"]:>5} {hit_rate:>7.1f}%'
                  f' {pnl:>+8,} {strong_count:>5}S')

    # Composite Score Sweep (W-only)
    print(f'\n  --- W-only Composite Score Sweep ---')
    print(f'  {"score":>6} {"min_ev":>7} {"Bets":>5} {"WinBet":>9} '
          f'{"WinRet":>9} {"WinROI":>7} {"Hits":>5} {"HitRate":>8} '
          f'{"P&L":>8}')
    print(f'  {"-" * 75}')

    for min_score in [4.0, 4.5, 5.0, 5.5, 6.0, 6.5, 7.0]:
        for min_ev in [0.0, 1.0]:
            params = BetStrategyParams(
                win_min_vb_score=min_score,
                win_min_ev=min_ev,
                win_v_ratio_min=0.75,
                win_v_bypass_gap=7,
                win_v_bypass_ev=3.0,
                ard_vb_min_ard=65.0,
                ard_vb_min_odds=10.0,
                place_min_gap=99,
                max_win_per_race=2,
            )
            recs = generate_recommendations(race_preds_w, params, budget=30000)
            if not recs:
                continue
            roi = calc_bet_engine_roi(recs, race_preds_w)
            hit_rate = roi['win_hits'] / roi['num_bets'] * 100 if roi['num_bets'] > 0 else 0
            pnl = roi['win_return'] - roi['win_bet']
            ev_label = f'{min_ev:.1f}' if min_ev > 0 else 'none'
            marker = ' ***' if roi['win_roi'] >= 100 else ''
            print(f'  {min_score:>6.1f} {ev_label:>7} {roi["num_bets"]:>5} '
                  f'{roi["win_bet"]:>9,} {roi["win_return"]:>9,} {roi["win_roi"]:>6.1f}%{marker}'
                  f' {roi["win_hits"]:>5} {hit_rate:>7.1f}%'
                  f' {pnl:>+8,}')

    # VBで選ばれる馬の重複率
    print(f'\n  --- P+W vs W-only: 選定馬の重複率 ---')
    for preset_name, preset_params in PRESETS.items():
        recs_p = generate_recommendations(race_preds, preset_params, budget=30000)
        recs_w = generate_recommendations(race_preds_w, preset_params, budget=30000)
        set_p = {(r.race_id, r.umaban) for r in recs_p}
        set_w = {(r.race_id, r.umaban) for r in recs_w}
        overlap = set_p & set_w
        only_p = set_p - set_w
        only_w = set_w - set_p
        print(f'  {preset_name:>14}: P+W={len(set_p)}, W-only={len(set_w)}, '
              f'overlap={len(overlap)}, P独自={len(only_p)}, W独自={len(only_w)}')

        # P独自の勝ち馬（Pがなくなると失う）
        p_only_wins = []
        for race_id, umaban in only_p:
            for race in race_preds:
                if race['race_id'] == race_id:
                    for e in race['entries']:
                        if e['umaban'] == umaban and e.get('is_win', 0) == 1:
                            p_only_wins.append(f'{race_id}:馬番{umaban}({e.get("horse_name","")})')
                    break
        if p_only_wins:
            print(f'    ↑ P独自の勝ち馬: {len(p_only_wins)}頭 — {", ".join(p_only_wins[:5])}')

        # W独自の勝ち馬（W-onlyで新たに拾える）
        w_only_wins = []
        for race_id, umaban in only_w:
            for race in race_preds_w:
                if race['race_id'] == race_id:
                    for e in race['entries']:
                        if e['umaban'] == umaban and e.get('is_win', 0) == 1:
                            w_only_wins.append(f'{race_id}:馬番{umaban}({e.get("horse_name","")})')
                    break
        if w_only_wins:
            print(f'    ↑ W独自の勝ち馬: {len(w_only_wins)}頭 — {", ".join(w_only_wins[:5])}')

    # === Closing Boost 有無比較 ===
    if closing_proba_map:
        print(f'\n{"=" * 70}')
        print(f'  Closing Boost 有無比較 (threshold=0.13, boost_score=1.0)')
        print(f'{"=" * 70}')

        print(f'  {"Preset":>14} {"Mode":>12} {"Bets":>5} {"TotalBet":>10} '
              f'{"TotalRet":>10} {"ROI":>7} {"WinROI":>7} {"PlcROI":>7} {"P&L":>8}')
        print(f'  {"-" * 95}')

        for preset_name, preset_params in PRESETS.items():
            # Boost ON (current preset, threshold=0.13)
            recs_on = generate_recommendations(race_preds, preset_params, budget=30000)
            roi_on = calc_bet_engine_roi(recs_on, race_preds)

            # Boost OFF (threshold=0 → 無効)
            import dataclasses
            params_off = dataclasses.replace(preset_params, closing_boost_threshold=0.0)
            recs_off = generate_recommendations(race_preds, params_off, budget=30000)
            roi_off = calc_bet_engine_roi(recs_off, race_preds)

            for mode, roi in [('Boost OFF', roi_off), ('Boost ON', roi_on)]:
                if roi['num_bets'] == 0:
                    print(f'  {preset_name:>14} {mode:>12} {"---":>5}')
                    continue
                pnl = roi['total_return'] - roi['total_bet']
                marker = ' ***' if roi['total_roi'] >= 100 else ''
                print(f'  {preset_name:>14} {mode:>12} {roi["num_bets"]:>5} '
                      f'{roi["total_bet"]:>10,} {roi["total_return"]:>10,} {roi["total_roi"]:>6.1f}%{marker}'
                      f' {roi["win_roi"]:>6.1f}% {roi["place_roi"]:>6.1f}%'
                      f' {pnl:>+8,}')

        # Boost ON で追加された馬の詳細
        print(f'\n  --- Closing Boost で追加/変更された買い目 ---')
        for preset_name in ['standard']:
            preset_params = PRESETS[preset_name]
            recs_on = generate_recommendations(race_preds, preset_params, budget=30000)
            params_off = dataclasses.replace(preset_params, closing_boost_threshold=0.0)
            recs_off = generate_recommendations(race_preds, params_off, budget=30000)

            set_on = {(r.race_id, r.umaban): r for r in recs_on}
            set_off = {(r.race_id, r.umaban) for r in recs_off}

            new_bets = [(k, v) for k, v in set_on.items() if k not in set_off]
            if new_bets:
                print(f'  {preset_name}: Boost ONで新規 {len(new_bets)} bets')
                win_count = 0
                for (rid, uma), rec in new_bets[:10]:
                    for race in race_preds:
                        if race['race_id'] == rid:
                            closing_p = race.get('closing_race_proba', 0)
                            for e in race['entries']:
                                if e['umaban'] == uma:
                                    is_win = e.get('is_win', 0)
                                    if is_win:
                                        win_count += 1
                                    print(f'    {rid} 馬番{uma} {e.get("horse_name",""):8s} '
                                          f'cs={e.get("closing_strength",-1):+.1f} '
                                          f'closing={closing_p:.2f} '
                                          f'odds={e.get("odds",0):.1f} '
                                          f'{"WIN!" if is_win else ""}')
                            break
                if len(new_bets) > 10:
                    print(f'    ... ({len(new_bets) - 10} more)')
                print(f'    うち的中: {win_count}/{len(new_bets)}')

        # Boost score sweep
        print(f'\n  --- Closing Boost Score Sweep (standard preset) ---')
        print(f'  {"threshold":>10} {"boost":>6} {"Bets":>5} {"TotalBet":>10} '
              f'{"TotalRet":>10} {"ROI":>7} {"P&L":>8}')
        print(f'  {"-" * 65}')

        base_params = PRESETS['standard']
        for threshold in [0.0, 0.10, 0.13, 0.15, 0.18, 0.20]:
            for boost_score in [0.5, 1.0, 1.5, 2.0]:
                if threshold == 0.0 and boost_score != 1.0:
                    continue  # OFF は1回だけ
                params = dataclasses.replace(
                    base_params,
                    closing_boost_threshold=threshold,
                    closing_boost_score=boost_score,
                )
                recs = generate_recommendations(race_preds, params, budget=30000)
                roi = calc_bet_engine_roi(recs, race_preds)
                if roi['num_bets'] == 0:
                    continue
                pnl = roi['total_return'] - roi['total_bet']
                t_label = 'OFF' if threshold == 0 else f'{threshold:.2f}'
                marker = ' ***' if roi['total_roi'] >= 100 else ''
                print(f'  {t_label:>10} {boost_score:>6.1f} {roi["num_bets"]:>5} '
                      f'{roi["total_bet"]:>10,} {roi["total_return"]:>10,} {roi["total_roi"]:>6.1f}%{marker}'
                      f' {pnl:>+8,}')

        # === W-only + Closing Boost 比較 ===
        print(f'\n{"=" * 70}')
        print(f'  W-only + Closing Boost 有無比較')
        print(f'{"=" * 70}')

        print(f'  {"Preset":>14} {"Mode":>12} {"Bets":>5} {"TotalBet":>10} '
              f'{"TotalRet":>10} {"ROI":>7} {"WinROI":>7} {"PlcROI":>7} {"P&L":>8}')
        print(f'  {"-" * 95}')

        for preset_name, preset_params in PRESETS.items():
            # W-only Boost ON
            recs_on = generate_recommendations(race_preds_w, preset_params, budget=30000)
            roi_on = calc_bet_engine_roi(recs_on, race_preds_w)

            # W-only Boost OFF
            params_off = dataclasses.replace(preset_params, closing_boost_threshold=0.0)
            recs_off = generate_recommendations(race_preds_w, params_off, budget=30000)
            roi_off = calc_bet_engine_roi(recs_off, race_preds_w)

            for mode, roi in [('Boost OFF', roi_off), ('Boost ON', roi_on)]:
                if roi['num_bets'] == 0:
                    print(f'  {preset_name:>14} {mode:>12} {"---":>5}')
                    continue
                pnl = roi['total_return'] - roi['total_bet']
                marker = ' ***' if roi['total_roi'] >= 100 else ''
                print(f'  {preset_name:>14} {mode:>12} {roi["num_bets"]:>5} '
                      f'{roi["total_bet"]:>10,} {roi["total_return"]:>10,} {roi["total_roi"]:>6.1f}%{marker}'
                      f' {roi["win_roi"]:>6.1f}% {roi["place_roi"]:>6.1f}%'
                      f' {pnl:>+8,}')

        # W-only Boost score sweep
        print(f'\n  --- W-only Closing Boost Score Sweep (standard preset) ---')
        print(f'  {"threshold":>10} {"boost":>6} {"Bets":>5} {"TotalBet":>10} '
              f'{"TotalRet":>10} {"ROI":>7} {"P&L":>8}')
        print(f'  {"-" * 65}')

        base_params = PRESETS['standard']
        for threshold in [0.0, 0.10, 0.13, 0.15, 0.18, 0.20]:
            for boost_score in [0.5, 1.0, 1.5, 2.0]:
                if threshold == 0.0 and boost_score != 1.0:
                    continue
                params = dataclasses.replace(
                    base_params,
                    closing_boost_threshold=threshold,
                    closing_boost_score=boost_score,
                )
                recs = generate_recommendations(race_preds_w, params, budget=30000)
                roi = calc_bet_engine_roi(recs, race_preds_w)
                if roi['num_bets'] == 0:
                    continue
                pnl = roi['total_return'] - roi['total_bet']
                t_label = 'OFF' if threshold == 0 else f'{threshold:.2f}'
                marker = ' ***' if roi['total_roi'] >= 100 else ''
                print(f'  {t_label:>10} {boost_score:>6.1f} {roi["num_bets"]:>5} '
                      f'{roi["total_bet"]:>10,} {roi["total_return"]:>10,} {roi["total_roi"]:>6.1f}%{marker}'
                      f' {pnl:>+8,}')

        # W-only Boost で追加された馬の詳細
        print(f'\n  --- W-only Closing Boost で追加された買い目 (standard) ---')
        preset_params = PRESETS['standard']
        recs_on = generate_recommendations(race_preds_w, preset_params, budget=30000)
        params_off = dataclasses.replace(preset_params, closing_boost_threshold=0.0)
        recs_off = generate_recommendations(race_preds_w, params_off, budget=30000)

        set_on = {(r.race_id, r.umaban): r for r in recs_on}
        set_off = {(r.race_id, r.umaban) for r in recs_off}

        new_bets = [(k, v) for k, v in set_on.items() if k not in set_off]
        if new_bets:
            print(f'  Boost ONで新規 {len(new_bets)} bets')
            win_count = 0
            for (rid, uma), rec in sorted(new_bets, key=lambda x: x[0])[:15]:
                for race in race_preds_w:
                    if race['race_id'] == rid:
                        closing_p = race.get('closing_race_proba', 0)
                        for e in race['entries']:
                            if e['umaban'] == uma:
                                is_win = e.get('is_win', 0)
                                if is_win:
                                    win_count += 1
                                print(f'    {rid} 馬番{uma} {e.get("horse_name",""):8s} '
                                      f'cs={e.get("closing_strength",-1):+.1f} '
                                      f'closing={closing_p:.2f} '
                                      f'odds={e.get("odds",0):.1f} '
                                      f'{"WIN!" if is_win else ""}')
                        break
            # 全体の的中率
            total_wins = sum(
                1 for (rid, uma), _ in new_bets
                for race in race_preds_w if race['race_id'] == rid
                for e in race['entries'] if e['umaban'] == uma and e.get('is_win', 0) == 1
            )
            if len(new_bets) > 15:
                print(f'    ... ({len(new_bets) - 15} more)')
            print(f'    うち的中: {total_wins}/{len(new_bets)} ({total_wins/len(new_bets)*100:.1f}%)')
        else:
            print(f'  Boost ONで新規追加なし')

    # =================================================================
    #  Slow Start Risk Boost 比較 (W-only)
    # =================================================================
    print(f'\n{"=" * 70}')
    print(f'  W-only + Slow Start Risk Boost 有無比較')
    print(f'{"=" * 70}')

    print(f'  {"Preset":>14} {"Mode":>14} {"Bets":>5} {"TotalBet":>10} '
          f'{"TotalRet":>10} {"ROI":>7} {"P&L":>8}')
    print(f'  {"-" * 75}')

    for preset_name, preset_params in PRESETS.items():
        # Slow Start ON (default from preset)
        recs_on = generate_recommendations(race_preds_w, preset_params, budget=30000)
        roi_on = calc_bet_engine_roi(recs_on, race_preds_w)

        # Slow Start OFF
        params_off = dataclasses.replace(preset_params, slow_start_penalty=0.0)
        recs_off = generate_recommendations(race_preds_w, params_off, budget=30000)
        roi_off = calc_bet_engine_roi(recs_off, race_preds_w)

        for mode, roi in [('SS-Boost OFF', roi_off), ('SS-Boost ON', roi_on)]:
            if roi['num_bets'] == 0:
                print(f'  {preset_name:>14} {mode:>14} {"---":>5}')
                continue
            pnl = roi['total_return'] - roi['total_bet']
            marker = ' ***' if roi['total_roi'] >= 100 else ''
            print(f'  {preset_name:>14} {mode:>14} {roi["num_bets"]:>5} '
                  f'{roi["total_bet"]:>10,} {roi["total_return"]:>10,} {roi["total_roi"]:>6.1f}%{marker}'
                  f' {pnl:>+8,}')

    # Slow Start パラメータスイープ (W-only, standard preset)
    print(f'\n  --- Slow Start Risk Parameter Sweep (W-only, standard) ---')
    print(f'  {"penalty":>8} {"min_rate":>9} {"fr_mult":>8} {"Bets":>5} {"TotalBet":>10} '
          f'{"TotalRet":>10} {"ROI":>7} {"P&L":>8}')
    print(f'  {"-" * 75}')

    base_params = PRESETS['standard']
    for penalty in [0.0, -0.5, -1.0, -1.5, -2.0]:
        for min_rate in [0.15, 0.20, 0.25, 0.30]:
            if penalty == 0.0 and min_rate != 0.20:
                continue  # OFF は1回だけ
            for fr_mult in [1.0, 2.0, 3.0]:
                if penalty == 0.0 and fr_mult != 2.0:
                    continue
                params = dataclasses.replace(
                    base_params,
                    slow_start_penalty=penalty,
                    slow_start_min_rate=min_rate,
                    slow_start_front_runner_multiplier=fr_mult,
                )
                recs = generate_recommendations(race_preds_w, params, budget=30000)
                roi = calc_bet_engine_roi(recs, race_preds_w)
                if roi['num_bets'] == 0:
                    continue
                pnl = roi['total_return'] - roi['total_bet']
                p_label = 'OFF' if penalty == 0 else f'{penalty:.1f}'
                marker = ' ***' if roi['total_roi'] >= 100 else ''
                print(f'  {p_label:>8} {min_rate:>9.2f} {fr_mult:>8.1f} {roi["num_bets"]:>5} '
                      f'{roi["total_bet"]:>10,} {roi["total_return"]:>10,} {roi["total_roi"]:>6.1f}%{marker}'
                      f' {pnl:>+8,}')

    # Slow Start Boost で除外された馬の詳細 (W-only, standard)
    print(f'\n  --- Slow Start Risk で除外された買い目 (W-only, standard) ---')
    preset_params = PRESETS['standard']
    recs_on = generate_recommendations(race_preds_w, preset_params, budget=30000)
    params_off = dataclasses.replace(preset_params, slow_start_penalty=0.0)
    recs_off = generate_recommendations(race_preds_w, params_off, budget=30000)

    set_on = {(r.race_id, r.umaban) for r in recs_on}
    set_off = {(r.race_id, r.umaban): r for r in recs_off}

    removed_bets = [(k, v) for k, v in set_off.items() if k not in set_on]
    if removed_bets:
        print(f'  SS-Boostで除外: {len(removed_bets)} bets')
        win_count = 0
        for (rid, uma), rec in sorted(removed_bets, key=lambda x: x[0])[:15]:
            for race in race_preds_w:
                if race['race_id'] == rid:
                    for e in race['entries']:
                        if e['umaban'] == uma:
                            is_win = e.get('is_win', 0)
                            if is_win:
                                win_count += 1
                            ss_rate = e.get('horse_slow_start_rate', -1)
                            c1_ratio = e.get('last_race_corner1_ratio', -1)
                            is_fr = '逃' if (c1_ratio >= 0 and c1_ratio <= 0.25) else ''
                            print(f'    {rid} 馬番{uma} {e.get("horse_name",""):8s} '
                                  f'ss_rate={ss_rate:.2f} c1r={c1_ratio:.2f} {is_fr:>2s} '
                                  f'odds={e.get("odds",0):.1f} '
                                  f'{"WIN!" if is_win else ""}')
                    break
        total_wins = sum(
            1 for (rid, uma), _ in removed_bets
            for race in race_preds_w if race['race_id'] == rid
            for e in race['entries'] if e['umaban'] == uma and e.get('is_win', 0) == 1
        )
        if len(removed_bets) > 15:
            print(f'    ... ({len(removed_bets) - 15} more)')
        print(f'    うち的中: {total_wins}/{len(removed_bets)} ({total_wins/len(removed_bets)*100:.1f}%)')
    else:
        print(f'  SS-Boostで除外なし')

    print('\nDone.')


if __name__ == '__main__':
    main()
