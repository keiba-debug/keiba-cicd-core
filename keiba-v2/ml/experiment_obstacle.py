#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
障害レース専用ML実験パイプライン v2.3b

P/Wデュアルモデル（市場特徴量除外 = VALUE戦略）
- P: is_top3分類 (Place)
- W: is_win分類 (Win) → EV計算可能に
- 障害固有特徴量: 難易度、経験、騎手/調教師障害成績(ベイズ平滑化)
- v2.2: 障害走限定過去走統計7個追加、NaN化、ベイズ平滑化
- v2.3: per-courseテーブル修正 + ハイレベル経験 + 平地プロフィール + avg_l3f
- v2.3b: 3軸分類 + 障害数 + 直線路面 + 同系統コース成績

Usage:
    python -m ml.experiment_obstacle
    python -m ml.experiment_obstacle --train-years 2019-2024 --val-years 2025.01-2025.06 --test-years 2025.07-2026.02
"""

import argparse
import json
import pickle
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from ml.experiment import (
    load_data, load_race_json, compute_features_for_race,
    build_pit_personnel_timeline, train_model,
    calc_hit_analysis_v2, calc_roi_analysis,
    parse_period_range,
    BASE_FEATURES, PAST_FEATURES, TRAINER_FEATURES, JOCKEY_FEATURES,
    RUNNING_STYLE_FEATURES, ROTATION_FEATURES, SPEED_FEATURES,
    PEDIGREE_FEATURES,
    _iter_date_index, _format_period,
)
from core.jravan import race_id as rid
from ml.features.obstacle_features import (
    compute_obstacle_experience,
    compute_obstacle_level,
    compute_obstacle_exp_tier,
    compute_prev_was_obstacle,
    compute_difficulty_exp_match,
    compute_jockey_obstacle_stats,
    compute_trainer_obstacle_stats,
    compute_jockey_selection,
    build_obstacle_personnel_timelines,
    compute_weight_gain_trend,
    compute_course_attributes,
    compute_prev_obstacle_level_diff,
    compute_flat_idm_avg3,
    compute_obstacle_only_past_stats,
    compute_high_level_experience,
    compute_flat_racing_profile,
    compute_venue_skill_features,
    compute_same_group_stats,
)

# === 障害レース用特徴量（市場特徴量を除外 = VALUE戦略） ===

OBSTACLE_BASE_FEATURES = [
    'age', 'sex', 'futan', 'horse_weight', 'horse_weight_diff',
    'wakuban', 'distance', 'track_condition', 'entry_count',
    'month', 'nichi',
]

OBSTACLE_PAST_FEATURES = [
    'avg_finish_last3', 'best_finish_last5', 'last3f_avg_last3',
    'days_since_last_race', 'win_rate_all', 'top3_rate_all',
    'total_career_races', 'recent_form_trend',
    'venue_top3_rate', 'distance_fitness',
    'prev_race_entry_count', 'entry_count_change',
    'best_l3f_last5', 'finish_std_last5', 'comeback_strength_last5',
    'career_stage',
]

OBSTACLE_ROTATION_FEATURES = [
    'futan_diff', 'futan_diff_ratio', 'weight_change_ratio',
    # prev_race_popularity は市場特徴量なので除外
    'jockey_change',
]

# 障害レース専用特徴量
OBSTACLE_SPECIFIC_FEATURES = [
    'obstacle_experience',          # 障害戦出走回数 (0=初障害)
    'obstacle_level',               # コース難易度 (10-53)
    'obstacle_exp_tier',            # 障害経験ビン (0-3)
    'prev_was_obstacle',            # 前走が障害だったか (0/1)
    'jockey_obstacle_races',        # 騎手の障害騎乗回数 (PIT-safe)
    'jockey_obstacle_win_rate',     # 騎手の障害勝率 (PIT-safe)
    'trainer_obstacle_top3_rate',   # 調教師の障害好走率 (PIT-safe)
    'difficulty_exp_match',         # 当該難易度帯での経験度 (0-1)
    'jockey_selected',              # 騎手選択シグナル (+1/-1/0)
    'jockey_selected_count',        # 同一前走騎手の馬数
    # --- v2.1: 予想理論 + IDM ---
    'flat_idm_avg3',                # 障害転向前の平地IDM 3走平均
    # 'is_placed_obstacle',         # 置き障害コースか → obstacle_levelで代替済み(imp=0)
    'prev_obstacle_level_diff',     # 前走obstacle_level - 今走level
    # --- v2.2: 障害走限定過去走統計 ---
    'obs_win_rate',                 # 障害のみ勝率
    'obs_top3_rate',                # 障害のみ好走率
    'obs_avg_finish_last3',         # 障害直近3走の平均着順
    'obs_last3f_avg_last3',         # 障害直近3走の上がり3F平均
    'obs_best_finish_last5',        # 障害直近5走のベスト着順
    'obs_days_since_last',          # 前走障害からの日数
    'obs_distance_fitness',         # 障害走での距離適性
    # --- v2.3: ハイレベル経験 + 平地プロフィール + コースL3F ---
    'course_avg_l3f',               # コース別平均上がり3F
    'obs_high_level_runs',          # ハイレベルコース出走数
    'obs_high_level_top3_rate',     # ハイレベルコースでの好走率
    'flat_turf_ratio',              # 平地走のうち芝の割合 (0-1)
    'flat_avg_distance',            # 平地走の平均距離 (m)
    # --- v2.3b: コースリンク ---
    'obs_same_group_top3_rate',     # 同系統コースでの障害好走率 (W:1320)
    # 'venue_skill_type',           # 3軸分類 → obstacle_levelで代替済み(P:23/W:52)
    # 'obstacle_count',             # 障害数 → obstacle_levelで代替済み(P:51/W:72)
    # 'straight_surface',           # 直線路面 → imp=0/13
    # --- v2.3 低重要度で除外 ---
    # 'has_sash_course',            # 襷コース (per-course修正済みだがimp<100)
    # 'is_high_level',              # obstacle_levelで代替済み(imp=0)
    # 'prev_was_high_level',        # imp<100
    # 'high_to_low_transfer',       # imp<100
]

# 市場特徴量は除外（VALUE戦略）
# odds, popularity, prev_race_popularity は使用しない

OBSTACLE_FEATURE_COLS = (
    OBSTACLE_BASE_FEATURES +
    OBSTACLE_PAST_FEATURES + TRAINER_FEATURES + JOCKEY_FEATURES +
    RUNNING_STYLE_FEATURES + OBSTACLE_ROTATION_FEATURES +
    OBSTACLE_SPECIFIC_FEATURES +
    SPEED_FEATURES + PEDIGREE_FEATURES
)

# === ハイパーパラメータ ===

PARAMS_OBSTACLE_P = {
    'objective': 'binary',
    'metric': 'auc',
    'num_leaves': 31,
    'learning_rate': 0.03,
    'feature_fraction': 0.7,
    'bagging_fraction': 0.7,
    'bagging_freq': 5,
    'min_child_samples': 30,
    'reg_alpha': 0.5,
    'reg_lambda': 2.0,
    'max_depth': 5,
    'verbose': -1,
    'seed': 42,
    'bagging_seed': 42,
    'feature_fraction_seed': 42,
}

PARAMS_OBSTACLE_W = {
    **PARAMS_OBSTACLE_P,
    'num_leaves': 15,
    'max_depth': 4,
    # scale_pos_weight は main() で自動計算して注入
}


def build_obstacle_dataset(
    date_index: dict,
    history_cache: dict,
    trainer_index: dict,
    jockey_index: dict,
    pace_index: dict,
    kb_ext_index: dict,
    min_year: int,
    max_year: int,
    use_db_odds: bool = True,
    race_level_index: dict = None,
    pedigree_index: dict = None,
    sire_stats_index: dict = None,
    min_month: int = None,
    max_month: int = None,
    pit_trainer_tl: dict = None,
    pit_jockey_tl: dict = None,
    jockey_obstacle_tl: dict = None,
    trainer_obstacle_tl: dict = None,
    jrdb_sed_index: dict = None,
) -> pd.DataFrame:
    """障害レースのみの特徴量DataFrameを構築"""
    date_min = min_year * 100 + (min_month or 1)
    date_max = max_year * 100 + (max_month or 12)
    label_min = f"{min_year}-{min_month:02d}" if min_month else str(min_year)
    label_max = f"{max_year}-{max_month:02d}" if max_month else str(max_year)
    print(f"\n[Build] Building obstacle dataset for {label_min} ~ {label_max}...")

    # 対象レースIDを収集
    target_races = []
    for date_str, race_id in _iter_date_index(date_index):
        ym = int(date_str[:4]) * 100 + int(date_str[5:7])
        if ym < date_min or ym > date_max:
            continue
        target_races.append((date_str, race_id))

    # DB事前オッズをバッチ取得（EV計算用に保持）
    db_odds_index = {}
    db_place_odds_index = {}
    if use_db_odds:
        try:
            from core.odds_db import batch_get_pre_race_odds, batch_get_place_odds, is_db_available
            if is_db_available():
                race_codes = [rid for _, rid in target_races]
                db_odds_index = batch_get_pre_race_odds(race_codes)
                db_place_odds_index = batch_get_place_odds(race_codes)
                print(f"[DB Odds] {len(db_odds_index):,} races with odds data")
            else:
                print("[DB Odds] mykeibadb not available, using JSON odds")
        except Exception as e:
            print(f"[DB Odds] Error: {e}, using JSON odds")

    all_rows = []
    race_count = 0
    flat_count = 0
    error_count = 0

    for date_str, race_id in target_races:
        try:
            race = load_race_json(race_id, date_str)
            # 障害レースのみ通す
            if race.get('track_type') != 'obstacle' and '障害' not in race.get('race_name', ''):
                flat_count += 1
                continue

            rows = compute_features_for_race(
                race, history_cache, trainer_index, jockey_index,
                pace_index, kb_ext_index,
                db_odds=db_odds_index.get(race_id),
                db_place_odds=db_place_odds_index.get(race_id),
                race_level_index=race_level_index,
                pedigree_index=pedigree_index,
                sire_stats_index=sire_stats_index,
                pit_trainer_tl=pit_trainer_tl,
                pit_jockey_tl=pit_jockey_tl,
            )

            # --- 障害レース専用特徴量を追加 ---
            race_date = date_str
            race_entries = race.get('entries', [])
            venue_name = race.get('venue_name', '')
            distance = race.get('distance', 0)

            # コース難易度
            obs_level = compute_obstacle_level(venue_name, distance, 'obstacle')

            # 騎手選択シグナル (レースレベル計算)
            jockey_sel = compute_jockey_selection(
                race_entries, history_cache, race_date,
            )

            for row in rows:
                kn = row.get('ketto_num', '')

                # 障害戦経験
                obs_exp = compute_obstacle_experience(kn, race_date, history_cache)
                row.update(obs_exp)

                # コース難易度
                row['obstacle_level'] = obs_level

                # 経験ビン
                row['obstacle_exp_tier'] = compute_obstacle_exp_tier(
                    obs_exp['obstacle_experience']
                )

                # 前走が障害か
                row['prev_was_obstacle'] = compute_prev_was_obstacle(
                    kn, race_date, history_cache
                )

                # 難易度帯での経験度
                row['difficulty_exp_match'] = compute_difficulty_exp_match(
                    kn, race_date, obs_level, history_cache
                )

                # 騎手の障害成績 (PIT-safe)
                jc = row.get('jockey_code', '')
                if jockey_obstacle_tl and jc:
                    j_stats = compute_jockey_obstacle_stats(
                        jc, race_date, jockey_obstacle_tl
                    )
                    row.update(j_stats)
                else:
                    row['jockey_obstacle_races'] = 0
                    row['jockey_obstacle_win_rate'] = 0.0

                # 調教師の障害成績 (PIT-safe)
                tc = row.get('trainer_code', '')
                if trainer_obstacle_tl and tc:
                    t_stats = compute_trainer_obstacle_stats(
                        tc, race_date, trainer_obstacle_tl
                    )
                    row.update(t_stats)
                else:
                    row['trainer_obstacle_top3_rate'] = 0.0

                # 騎手選択シグナル
                uma = row.get('umaban', 0)
                sel = jockey_sel.get(uma, {})
                row['jockey_selected'] = sel.get('jockey_selected', 0)
                row['jockey_selected_count'] = sel.get('jockey_selected_count', 0)

                # 近走馬体重増加トレンド
                wg = compute_weight_gain_trend(kn, race_date, history_cache)
                row.update(wg)

                # v2.3: コース属性（per-courseテーブル）
                row.update(compute_course_attributes(venue_name, distance))

                # v2.1: 前走レベル差
                row['prev_obstacle_level_diff'] = compute_prev_obstacle_level_diff(
                    kn, race_date, obs_level, history_cache
                )

                # v2.1: 平地IDM 3走平均
                row['flat_idm_avg3'] = compute_flat_idm_avg3(
                    kn, race_date, history_cache,
                    jrdb_sed_index or {}
                )

                # v2.2: 障害走限定過去走統計
                obs_past = compute_obstacle_only_past_stats(
                    kn, race_date, distance, history_cache
                )
                row.update(obs_past)

                # v2.3: ハイレベルコース経験
                hl_exp = compute_high_level_experience(
                    kn, race_date, obs_level, history_cache
                )
                row.update(hl_exp)

                # v2.3: 平地レースプロフィール
                flat_prof = compute_flat_racing_profile(
                    kn, race_date, history_cache
                )
                row.update(flat_prof)

                # v2.3b: 3軸分類 + 障害数 + 直線路面
                row.update(compute_venue_skill_features(venue_name))

                # v2.3b: 同系統コースでの障害好走率
                row.update(compute_same_group_stats(
                    kn, race_date, venue_name, history_cache
                ))

            all_rows.extend(rows)
            race_count += 1
        except Exception as e:
            error_count += 1
            if error_count <= 5:
                print(f"  ERROR: {race_id}: {e}")

    df = pd.DataFrame(all_rows)

    # object型をfloat64に変換
    for col in df.columns:
        if col in set(OBSTACLE_FEATURE_COLS) and df[col].dtype == object:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # odds_rank追加（EV分析用に保持するがモデル入力には使わない）
    if 'odds' in df.columns and len(df) > 0:
        df['odds_rank'] = df.groupby('race_id')['odds'].rank(method='min')

    print(f"[Build] {race_count:,} obstacle races, {len(df):,} entries, "
          f"{error_count} errors, {flat_count:,} flat races skipped")
    return df


def main():
    parser = argparse.ArgumentParser(description='Obstacle Race ML Experiment v2.3b (P/W)')
    parser.add_argument('--train-years', default='2019-2024',
                        help='Training period (例: 2019-2024)')
    parser.add_argument('--val-years', default='2025.01-2025.06',
                        help='Validation period (例: 2025.01-2025.06)')
    parser.add_argument('--test-years', default='2025.07-2026.02',
                        help='Test period (例: 2025.07-2026.02)')
    parser.add_argument('--no-db', action='store_true', help='DBオッズ未使用')
    parser.add_argument('--use-optuna', action='store_true',
                        help='Optuna最適化パラメータを使用')
    args = parser.parse_args()

    train_min, train_min_m, train_max, train_max_m = parse_period_range(args.train_years)
    val_min, val_min_m, val_max, val_max_m = parse_period_range(args.val_years)
    test_min, test_min_m, test_max, test_max_m = parse_period_range(args.test_years)
    use_db_odds = not args.no_db

    # Optuna パラメータ読み込み
    optuna_p_params = None
    optuna_w_params = None
    optuna_p_features = None
    optuna_w_features = None
    if args.use_optuna:
        optuna_dir = config.ml_dir() / "optuna"
        p_path = optuna_dir / "best_params_obstacle_p.json"
        w_path = optuna_dir / "best_params_obstacle_w.json"
        if p_path.exists():
            p_data = json.loads(p_path.read_text(encoding='utf-8'))
            optuna_p_params = p_data['params']
            optuna_p_features = p_data['features']
            print(f"[Optuna] P: loaded {len(optuna_p_features)} features, "
                  f"val_auc={p_data['best_value']:.4f}")
        if w_path.exists():
            w_data = json.loads(w_path.read_text(encoding='utf-8'))
            optuna_w_params = w_data['params']
            optuna_w_features = w_data['features']
            print(f"[Optuna] W: loaded {len(optuna_w_features)} features, "
                  f"val_auc={w_data['best_value']:.4f}")

    train_label = f"{_format_period(train_min, train_min_m)} ~ {_format_period(train_max, train_max_m)}"
    val_label = f"{_format_period(val_min, val_min_m)} ~ {_format_period(val_max, val_max_m)}"
    test_label = f"{_format_period(test_min, test_min_m)} ~ {_format_period(test_max, test_max_m)}"

    optuna_label = "ON" if args.use_optuna else "OFF"

    print(f"\n{'='*60}")
    print(f"  KeibaCICD - Obstacle Race ML Experiment v2.3b (P/W)")
    print(f"  Train: {train_label}")
    print(f"  Val:   {val_label} (early stopping)")
    print(f"  Optuna: {optuna_label}")
    print(f"  Test:  {test_label} (pure evaluation)")
    print(f"  DB Odds: {'ON' if use_db_odds else 'OFF'}")
    print(f"  Features: {len(OBSTACLE_FEATURE_COLS)} (market excluded)")
    print(f"  P Params: leaves={PARAMS_OBSTACLE_P['num_leaves']}, "
          f"depth={PARAMS_OBSTACLE_P['max_depth']}")
    print(f"  W Params: leaves={PARAMS_OBSTACLE_W['num_leaves']}, "
          f"depth={PARAMS_OBSTACLE_W['max_depth']}")
    print(f"{'='*60}\n")

    t0 = time.time()

    # データロード（平地と共有）
    (history_cache, trainer_index, jockey_index,
     date_index, pace_index, kb_ext_index, training_summary_index,
     race_level_index, pedigree_index, sire_stats_index,
     jrdb_sed_index, *_extra) = load_data()

    # PIT timeline（平地用）
    pit_trainer_tl, pit_jockey_tl = build_pit_personnel_timeline(
        years=list(range(2019, 2027))
    )

    # 障害専用PIT timeline（騎手/調教師の障害成績）
    print("[Build] Building obstacle personnel timelines...")
    jockey_obstacle_tl, trainer_obstacle_tl = build_obstacle_personnel_timelines(
        history_cache
    )
    print(f"  Jockeys: {len(jockey_obstacle_tl):,}, Trainers: {len(trainer_obstacle_tl):,}")

    # データセット構築
    build_kwargs = dict(
        date_index=date_index, history_cache=history_cache,
        trainer_index=trainer_index, jockey_index=jockey_index,
        pace_index=pace_index, kb_ext_index=kb_ext_index,
        use_db_odds=use_db_odds,
        race_level_index=race_level_index,
        pedigree_index=pedigree_index,
        sire_stats_index=sire_stats_index,
        pit_trainer_tl=pit_trainer_tl, pit_jockey_tl=pit_jockey_tl,
        jockey_obstacle_tl=jockey_obstacle_tl,
        trainer_obstacle_tl=trainer_obstacle_tl,
        jrdb_sed_index=jrdb_sed_index,
    )

    df_train = build_obstacle_dataset(
        **build_kwargs,
        min_year=train_min, max_year=train_max,
        min_month=train_min_m, max_month=train_max_m,
    )
    df_val = build_obstacle_dataset(
        **build_kwargs,
        min_year=val_min, max_year=val_max,
        min_month=val_min_m, max_month=val_max_m,
    )
    df_test = build_obstacle_dataset(
        **build_kwargs,
        min_year=test_min, max_year=test_max,
        min_month=test_min_m, max_month=test_max_m,
    )

    for label, df in [('Train', df_train), ('Val', df_val), ('Test', df_test)]:
        if len(df) > 0 and 'race_id' in df.columns:
            races = df['race_id'].nunique()
            wins = int(df['is_win'].sum()) if 'is_win' in df.columns else '?'
            top3 = int(df['is_top3'].sum()) if 'is_top3' in df.columns else '?'
            print(f"[Dataset] {label}: {len(df):,} entries from {races:,} races "
                  f"(wins={wins}, top3={top3})")
        else:
            print(f"[Dataset] {label}: EMPTY")

    if len(df_train) == 0 or len(df_val) == 0 or len(df_test) == 0:
        print("\nERROR: Empty dataset. Check obstacle race JSONs and race_date_index.json.")
        sys.exit(1)

    # is_win確認（compute_features_for_raceで自動算出されるはず）
    if 'is_win' not in df_train.columns:
        print("[Fix] Adding is_win column from finish_position...")
        for df in [df_train, df_val, df_test]:
            df['is_win'] = (df['finish_position'] == 1).astype(int)

    # 使用可能な特徴量を確認
    available_features = [f for f in OBSTACLE_FEATURE_COLS if f in df_train.columns]
    missing = set(OBSTACLE_FEATURE_COLS) - set(available_features)
    if missing:
        print(f"\n[Warning] {len(missing)} features not in data: {sorted(missing)[:10]}...")
    print(f"[Features] Using {len(available_features)} of {len(OBSTACLE_FEATURE_COLS)} defined features")

    # Optuna特徴量でオーバーライド
    p_features = available_features
    w_features = available_features
    if optuna_p_features:
        p_features = [f for f in optuna_p_features if f in df_train.columns]
        print(f"[Optuna P] Using {len(p_features)} features (optuna selected)")
    if optuna_w_features:
        w_features = [f for f in optuna_w_features if f in df_train.columns]
        print(f"[Optuna W] Using {len(w_features)} features (optuna selected)")

    # === P Model (Place: is_top3) ===
    print(f"\n{'='*60}")
    print(f"  Training P Model (Place: is_top3)")
    print(f"{'='*60}")

    p_params = optuna_p_params if optuna_p_params else PARAMS_OBSTACLE_P
    model_p, metrics_p, importance_p, pred_p_cal, calibrator_p, pred_p_raw = train_model(
        df_train, df_val, df_test, p_features,
        p_params, 'is_top3', 'Obstacle_P'
    )

    # === W Model (Win: is_win) ===
    print(f"\n{'='*60}")
    print(f"  Training W Model (Win: is_win)")
    print(f"{'='*60}")

    if optuna_w_params:
        params_w = optuna_w_params
        print(f"[W] Using Optuna params (spw={params_w.get('scale_pos_weight', 'N/A')})")
    else:
        # scale_pos_weight自動計算
        n_pos = int(df_train['is_win'].sum())
        n_neg = len(df_train) - n_pos
        spw = round(n_neg / n_pos, 1) if n_pos > 0 else 10.0
        params_w = {**PARAMS_OBSTACLE_W, 'scale_pos_weight': spw}
        print(f"[W] scale_pos_weight = {spw:.1f} ({n_neg}/{n_pos})")

    model_w, metrics_w, importance_w, pred_w_cal, calibrator_w, pred_w_raw = train_model(
        df_train, df_val, df_test, w_features,
        params_w, 'is_win', 'Obstacle_W'
    )

    # === 分析 ===
    df_test = df_test.copy()
    df_test['pred_proba_p'] = pred_p_cal
    df_test['pred_proba_w'] = pred_w_cal
    df_test['pred_proba_p_raw'] = pred_p_raw
    df_test['pred_proba_w_raw'] = pred_w_raw
    df_test['pred_rank_p'] = df_test.groupby('race_id')['pred_proba_p'].rank(
        ascending=False, method='min'
    )
    df_test['pred_rank_w'] = df_test.groupby('race_id')['pred_proba_w'].rank(
        ascending=False, method='min'
    )

    # EV計算
    if 'odds' in df_test.columns:
        df_test['win_ev'] = df_test['pred_proba_w'] * df_test['odds']
    else:
        df_test['win_ev'] = 0.0

    print(f"\n{'='*60}")
    print(f"  Analysis")
    print(f"{'='*60}")

    # --- P Model 分析 ---
    print(f"\n--- P Model (Place) ---")
    hit_p = calc_hit_analysis_v2(df_test, 'pred_proba_p')
    print(f"[Hit P] Top1 Place: {hit_p['top1_place_rate']:.1%} "
          f"({hit_p['top1_places']}/{hit_p['top1_total']})")
    roi_p = calc_roi_analysis(df_test.copy(), 'pred_proba_p')
    print(f"[ROI P] Top1 Place ROI: {roi_p['top1_place_roi']:.1f}%")

    # --- W Model 分析 ---
    print(f"\n--- W Model (Win) ---")
    hit_w = calc_hit_analysis_v2(df_test, 'pred_proba_w')
    print(f"[Hit W] Top1 Win: {hit_w['top1_win_rate']:.1%} "
          f"({hit_w['top1_wins']}/{hit_w['top1_total']})")
    roi_w = calc_roi_analysis(df_test.copy(), 'pred_proba_w')
    print(f"[ROI W] Top1 Win ROI: {roi_w['top1_win_roi']:.1f}%")

    # --- EV分析 ---
    print(f"\n--- EV Analysis ---")
    if 'odds' in df_test.columns:
        for ev_th in [1.0, 1.3, 1.5, 2.0]:
            subset = df_test[df_test['win_ev'] >= ev_th]
            if len(subset) > 0:
                wins = int(subset['is_win'].sum())
                payout = subset[subset['is_win'] == 1]['odds'].sum() * 100
                roi = payout / (len(subset) * 100) * 100 if len(subset) > 0 else 0
                print(f"  EV>={ev_th}: {len(subset)} bets, {wins} wins, "
                      f"ROI={roi:.1f}%")
            else:
                print(f"  EV>={ev_th}: 0 bets")

    # --- VB Gap 分析 ---
    print(f"\n--- VB Gap Analysis (rank_w) ---")
    for gap_min in [1, 3, 5]:
        if 'odds_rank' not in df_test.columns:
            break
        subset = df_test[
            (df_test['pred_rank_w'] == 1) &
            (df_test['odds_rank'] - df_test['pred_rank_w'] >= gap_min)
        ]
        if len(subset) > 0:
            wins = int(subset['is_win'].sum())
            payout = subset[subset['is_win'] == 1]['odds'].sum() * 100
            roi = payout / (len(subset) * 100) * 100 if len(subset) > 0 else 0
            print(f"  rank_w=1, gap>={gap_min}: {len(subset)} bets, "
                  f"{wins} wins, ROI={roi:.1f}%")

    # --- 特徴量重要度 ---
    print(f"\n--- Feature Importance (P Model Top 15) ---")
    sorted_imp_p = sorted(importance_p.items(), key=lambda x: x[1], reverse=True)
    for i, (feat, imp) in enumerate(sorted_imp_p[:15], 1):
        marker = ' ★' if feat in [f for f in OBSTACLE_SPECIFIC_FEATURES] else ''
        print(f"  {i:2d}. {feat:<35s} {imp:>8.0f}{marker}")

    print(f"\n--- Feature Importance (W Model Top 15) ---")
    sorted_imp_w = sorted(importance_w.items(), key=lambda x: x[1], reverse=True)
    for i, (feat, imp) in enumerate(sorted_imp_w[:15], 1):
        marker = ' ★' if feat in [f for f in OBSTACLE_SPECIFIC_FEATURES] else ''
        print(f"  {i:2d}. {feat:<35s} {imp:>8.0f}{marker}")

    # === モデル保存 ===
    ml_dir = config.ml_dir()

    # P Model
    model_p_path = ml_dir / "model_obstacle_p.txt"
    model_p.save_model(str(model_p_path))
    print(f"\n[Save] P Model saved to {model_p_path}")

    # W Model
    model_w_path = ml_dir / "model_obstacle_w.txt"
    model_w.save_model(str(model_w_path))
    print(f"[Save] W Model saved to {model_w_path}")

    # キャリブレーター保存（P+W統合）
    cal_path = ml_dir / "calibrators_obstacle.pkl"
    with open(cal_path, 'wb') as f:
        pickle.dump({'cal_p': calibrator_p, 'cal_w': calibrator_w}, f)
    print(f"[Save] Calibrators saved to {cal_path}")

    # メタデータ保存
    meta = {
        'version': 'obstacle-v2.3b',
        'model_type': 'obstacle_p_w',
        'has_win_model': True,
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'train_period': f"{_format_period(train_min, train_min_m)} ~ {_format_period(train_max, train_max_m)}",
        'val_period': f"{_format_period(val_min, val_min_m)} ~ {_format_period(val_max, val_max_m)}",
        'test_period': f"{_format_period(test_min, test_min_m)} ~ {_format_period(test_max, test_max_m)}",
        'use_optuna': args.use_optuna,
        'features_p': p_features,
        'features_w': w_features,
        'feature_count_p': len(p_features),
        'feature_count_w': len(w_features),
        'params_p': p_params,
        'params_w': params_w,
        'metrics_p': metrics_p,
        'metrics_w': metrics_w,
        'train_races': int(df_train['race_id'].nunique()),
        'train_entries': len(df_train),
        'val_races': int(df_val['race_id'].nunique()),
        'val_entries': len(df_val),
        'test_races': int(df_test['race_id'].nunique()),
        'test_entries': len(df_test),
        'feature_importance_p': [
            {'feature': f, 'importance': float(imp)}
            for f, imp in sorted_imp_p
        ],
        'feature_importance_w': [
            {'feature': f, 'importance': float(imp)}
            for f, imp in sorted_imp_w
        ],
        'hit_analysis_p': hit_p,
        'hit_analysis_w': hit_w,
        'roi_analysis_p': roi_p,
        'roi_analysis_w': roi_w,
    }

    meta_path = ml_dir / "model_obstacle_meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"[Save] Meta saved to {meta_path}")

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  Obstacle Experiment v2.3b Complete")
    print(f"  P AUC: {metrics_p['auc']:.4f}")
    print(f"  W AUC: {metrics_w['auc']:.4f}")
    print(f"  Top1 Win Rate (W): {hit_w['top1_win_rate']:.1%}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
