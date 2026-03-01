#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Speed Index回帰実験: スピード指数をターゲットにした回帰モデル

TARGETのスピード指数データ(SP files)を回帰ターゲットとして使用。
馬場差・ペース補正も特徴量として追加。

既存のREG_AR（着差回帰）と比較して、パフォーマンス予測としての
優位性を検証する。

Usage:
    python -m ml.experiment_speed_idx
"""

import argparse
import json
import sys
import time
from pathlib import Path
from collections import defaultdict

import numpy as np
import pandas as pd
import lightgbm as lgb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from ml.experiment import (
    FEATURE_COLS_ALL, FEATURE_COLS_VALUE, PARAMS_AR,
    build_dataset, load_race_json, _iter_date_index,
    load_data,
    build_pit_personnel_timeline,
)
from ml.features.margin_target import add_margin_target_to_df


# ============================================================
# Data Loaders
# ============================================================

def load_speed_index() -> dict:
    """TARGETスピード指数(SP files)を読み込み

    Returns:
        dict: {race_id_16: {umaban: speed_idx_int}}
    """
    speed_dir = config.analysis_dir() / "speed"
    sp_data = {}
    total = 0
    invalid = 0

    for year_dir in sorted(speed_dir.iterdir()):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        for sp_file in year_dir.glob("SP*.csv"):
            with open(sp_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    parts = line.split(",")
                    if len(parts) != 2 or len(parts[0]) != 18:
                        continue
                    race_id = parts[0][:16]
                    umaban = int(parts[0][16:18])
                    val_str = parts[1].strip()
                    if val_str in ("--", ""):
                        invalid += 1
                        continue
                    try:
                        val = int(val_str)
                    except ValueError:
                        invalid += 1
                        continue
                    if race_id not in sp_data:
                        sp_data[race_id] = {}
                    sp_data[race_id][umaban] = val
                    total += 1

    print(f"[Load] Speed index: {total:,} entries, {len(sp_data):,} races ({invalid} invalid)")
    return sp_data


def load_baba_data() -> dict:
    """馬場差データを読み込み

    Returns:
        dict: {rx_code: float} (馬場差秒数, -=高速, +=低速)
        rx_code = "RX{venue2}{year2}{kai1}{nichi1}{race2}"
    """
    speed_dir = config.analysis_dir() / "speed"
    baba = {}

    for baba_file in sorted(speed_dir.glob("baba*.csv")):
        with open(baba_file, encoding="shift_jis", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(",")
                if len(parts) < 3:
                    continue
                rx_code = parts[1].strip().strip('"')
                val_str = parts[2].strip().strip('"').strip()

                if len(val_str) < 4:
                    continue

                # Parse: "XX±Y.Y" → float
                sign_val = val_str[2:]  # skip 2-char distance code
                if not sign_val:
                    continue
                try:
                    baba_val = float(sign_val)
                    baba[rx_code] = baba_val
                except ValueError:
                    continue

    print(f"[Load] Baba (track bias): {len(baba):,} entries")
    return baba


def load_pace_data() -> dict:
    """ペース補正データを読み込み

    Returns:
        dict: {rx_code: float} (補正秒数, blank=0)
    """
    speed_dir = config.analysis_dir() / "speed"
    pace = {}

    for pace_file in sorted(speed_dir.glob("pace*.csv")):
        with open(pace_file, encoding="shift_jis", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split(",")
                if len(parts) < 3:
                    continue
                rx_code = parts[1].strip().strip('"')
                val_str = parts[2].strip().strip('"').strip()

                if not val_str or val_str == "     ":
                    # No correction needed = 0
                    pace[rx_code] = 0.0
                    continue

                if len(val_str) < 4:
                    pace[rx_code] = 0.0
                    continue

                sign_val = val_str[2:]  # skip 2-char distance code
                try:
                    pace[rx_code] = float(sign_val)
                except ValueError:
                    pace[rx_code] = 0.0

    print(f"[Load] Pace correction: {len(pace):,} entries "
          f"({sum(1 for v in pace.values() if v != 0.0)} non-zero)")
    return pace


def race_id_to_rx_code(race_id: str) -> str:
    """16桁race_idをRXコードに変換

    race_id: YYYYMMDDJJKKNNRRle (2025010506010101)
    rx_code: RX{JJ}{YY}{K}{N}{RR} (RX06251101)
    """
    if len(race_id) != 16:
        return ""
    venue = race_id[8:10]      # JJ
    year2 = race_id[2:4]       # YY
    kai = str(int(race_id[10:12]))   # K (strip leading zero)
    nichi = str(int(race_id[12:14])) # N (strip leading zero)
    race = race_id[14:16]      # RR
    return f"RX{venue}{year2}{kai}{nichi}{race}"


def add_speed_idx_target(df: pd.DataFrame, sp_data: dict,
                         baba_data: dict, pace_data: dict) -> pd.DataFrame:
    """DataFrameにスピード指数ターゲットと馬場差/ペース補正特徴量を追加"""

    speed_vals = []
    baba_vals = []
    pace_vals = []

    for _, row in df.iterrows():
        race_id = str(row.get("race_id", ""))
        umaban = int(row.get("umaban", 0))

        # Speed index target
        sp_race = sp_data.get(race_id, {})
        sp_val = sp_race.get(umaban, np.nan)
        speed_vals.append(sp_val)

        # Baba / Pace features
        rx = race_id_to_rx_code(race_id)
        baba_vals.append(baba_data.get(rx, 0.0))
        pace_vals.append(pace_data.get(rx, 0.0))

    df = df.copy()
    df["target_speed_idx"] = speed_vals
    df["baba_diff"] = baba_vals
    df["pace_correction"] = pace_vals

    valid = df["target_speed_idx"].notna().sum()
    total = len(df)
    print(f"[SpeedIdx] {valid:,}/{total:,} entries with speed index ({100*valid/total:.1f}%)")

    baba_nonzero = (df["baba_diff"] != 0).sum()
    pace_nonzero = (df["pace_correction"] != 0).sum()
    print(f"[Features] baba_diff: {baba_nonzero:,} non-zero, "
          f"pace_correction: {pace_nonzero:,} non-zero")

    return df


# ============================================================
# Experiment
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Speed Index Regression Experiment")
    parser.add_argument("--train-years", default="2020-2024")
    parser.add_argument("--test-years", default="2025-2026")
    args = parser.parse_args()

    t0 = time.time()
    train_start, train_end = map(int, args.train_years.split("-"))
    test_start, test_end = map(int, args.test_years.split("-"))

    print("=" * 60)
    print("  Speed Index Regression Experiment")
    print(f"  Train: {train_start} ~ {train_end}")
    print(f"  Val:   2025-01 ~ 2025-02")
    print(f"  Test:  {test_start} ~ {test_end}")
    print("=" * 60)

    # === Load master data (reuse experiment.py's load_data) ===
    (history_cache, trainer_index, jockey_index,
     date_index, pace_index, kb_ext_index, training_summary_index,
     race_level_index, pedigree_index, sire_stats_index) = load_data()

    pit_trainer_tl, pit_jockey_tl = build_pit_personnel_timeline()

    from ml.features.baba_features import load_baba_index
    baba_index = load_baba_index(range(train_start, test_end + 1))

    # === Load speed analysis data ===
    sp_data = load_speed_index()
    baba_data = load_baba_data()
    pace_correction_data = load_pace_data()

    # === Build datasets ===
    common_args = dict(
        date_index=date_index,
        history_cache=history_cache,
        trainer_index=trainer_index,
        jockey_index=jockey_index,
        pace_index=pace_index,
        kb_ext_index=kb_ext_index,
        training_summary_index=training_summary_index,
        race_level_index=race_level_index,
        pedigree_index=pedigree_index,
        sire_stats_index=sire_stats_index,
        pit_trainer_tl=pit_trainer_tl,
        pit_jockey_tl=pit_jockey_tl,
        baba_index=baba_index,
    )

    df_train = build_dataset(min_year=train_start, max_year=train_end, **common_args)
    df_val = build_dataset(min_year=2025, max_year=2025, min_month=1, max_month=2, **common_args)
    df_test = build_dataset(min_year=test_start, max_year=test_end, **common_args)

    # Add speed index target + baba/pace features
    df_train = add_speed_idx_target(df_train, sp_data, baba_data, pace_correction_data)
    df_val = add_speed_idx_target(df_val, sp_data, baba_data, pace_correction_data)
    df_test = add_speed_idx_target(df_test, sp_data, baba_data, pace_correction_data)

    # Also add margin target for comparison
    add_margin_target_to_df(df_train, date_index, load_race_json)
    add_margin_target_to_df(df_val, date_index, load_race_json)
    add_margin_target_to_df(df_test, date_index, load_race_json)

    # === Feature columns ===
    # VALUE features + baba_diff + pace_correction
    feature_cols_sp = FEATURE_COLS_VALUE + ["baba_diff", "pace_correction"]

    print(f"\n[Dataset] Train: {len(df_train):,}, Val: {len(df_val):,}, Test: {len(df_test):,}")
    print(f"[Features] {len(feature_cols_sp)} features (VALUE {len(FEATURE_COLS_VALUE)} + baba_diff + pace_correction)")

    # === Filter to entries with speed index ===
    mask_train = df_train["target_speed_idx"].notna()
    mask_val = df_val["target_speed_idx"].notna()
    mask_test = df_test["target_speed_idx"].notna()

    # Remove extreme outliers (|speed_idx| > 200)
    mask_train = mask_train & (df_train["target_speed_idx"].abs() <= 200)
    mask_val = mask_val & (df_val["target_speed_idx"].abs() <= 200)
    mask_test = mask_test & (df_test["target_speed_idx"].abs() <= 200)

    X_train = df_train.loc[mask_train, feature_cols_sp].values.astype(np.float32)
    y_train = df_train.loc[mask_train, "target_speed_idx"].values
    X_val = df_val.loc[mask_val, feature_cols_sp].values.astype(np.float32)
    y_val = df_val.loc[mask_val, "target_speed_idx"].values
    X_test = df_test.loc[mask_test, feature_cols_sp].values.astype(np.float32)
    y_test = df_test.loc[mask_test, "target_speed_idx"].values

    print(f"\n[Regression] Train: {len(X_train):,}, Val: {len(X_val):,}, Test: {len(X_test):,}")
    print(f"  y_train: mean={y_train.mean():.1f}, std={y_train.std():.1f}")
    print(f"  y_test:  mean={y_test.mean():.1f}, std={y_test.std():.1f}")

    # === Train Speed Index model ===
    params_sp = {
        **PARAMS_AR,
        "metric": "mae",
    }

    print(f"\n[Train] REG_SP: {len(feature_cols_sp)} features, "
          f"target=speed_idx, loss=huber")

    ds_train = lgb.Dataset(X_train, label=y_train, feature_name=feature_cols_sp)
    ds_val = lgb.Dataset(X_val, label=y_val, feature_name=feature_cols_sp, reference=ds_train)

    callbacks = [
        lgb.early_stopping(50),
        lgb.log_evaluation(200),
    ]

    model_sp = lgb.train(
        params_sp, ds_train,
        num_boost_round=3000,
        valid_sets=[ds_val],
        callbacks=callbacks,
    )

    # === Evaluate ===
    pred_test = model_sp.predict(X_test)
    mae_sp = np.mean(np.abs(pred_test - y_test))
    corr_sp = np.corrcoef(pred_test, y_test)[0, 1]

    print(f"\n[REG_SP] MAE={mae_sp:.2f}, Corr={corr_sp:.4f}, BestIter={model_sp.best_iteration}")

    # === Train REG_AR (margin) for comparison ===
    mask_m_train = df_train["target_margin"].notna() & mask_train
    mask_m_val = df_val["target_margin"].notna() & mask_val
    mask_m_test = df_test["target_margin"].notna() & mask_test

    # Use same VALUE features (without baba_diff/pace_correction) for fair comparison
    X_m_train = df_train.loc[mask_m_train, FEATURE_COLS_VALUE].values.astype(np.float32)
    y_m_train = df_train.loc[mask_m_train, "target_margin"].values
    X_m_val = df_val.loc[mask_m_val, FEATURE_COLS_VALUE].values.astype(np.float32)
    y_m_val = df_val.loc[mask_m_val, "target_margin"].values
    X_m_test = df_test.loc[mask_m_test, FEATURE_COLS_VALUE].values.astype(np.float32)
    y_m_test = df_test.loc[mask_m_test, "target_margin"].values

    print(f"\n[Train] REG_AR: {len(FEATURE_COLS_VALUE)} features, "
          f"target=margin, loss=huber")

    ds_m_train = lgb.Dataset(X_m_train, label=y_m_train, feature_name=FEATURE_COLS_VALUE)
    ds_m_val = lgb.Dataset(X_m_val, label=y_m_val, feature_name=FEATURE_COLS_VALUE, reference=ds_m_train)

    model_margin = lgb.train(
        {**PARAMS_AR, "metric": "mae"},
        ds_m_train,
        num_boost_round=3000,
        valid_sets=[ds_m_val],
        callbacks=[lgb.early_stopping(50), lgb.log_evaluation(200)],
    )

    pred_m_test = model_margin.predict(X_m_test)
    mae_margin = np.mean(np.abs(pred_m_test - y_m_test))
    corr_margin = np.corrcoef(pred_m_test, y_m_test)[0, 1]

    print(f"[REG_AR] MAE={mae_margin:.4f}s, Corr={corr_margin:.4f}, BestIter={model_margin.best_iteration}")

    # === Ranking quality comparison ===
    # How well does each model rank horses within a race?
    print("\n" + "=" * 60)
    print("  Ranking Quality Comparison (within-race)")
    print("=" * 60)

    # For REG_SP: group by race, check if highest predicted speed_idx = winner
    test_df_sp = df_test.loc[mask_test].copy()
    test_df_sp["pred_speed_idx"] = pred_test

    # For REG_AR: same check
    test_df_margin = df_test.loc[mask_m_test].copy()
    test_df_margin["pred_margin"] = pred_m_test

    # Top1 accuracy for speed index model
    sp_top1_win = 0
    sp_top1_place = 0
    sp_race_count = 0
    for race_id, group in test_df_sp.groupby("race_id"):
        if len(group) < 3:
            continue
        sp_race_count += 1
        top1_idx = group["pred_speed_idx"].idxmax()  # Highest speed = best
        top1_fp = group.loc[top1_idx, "finish_position"]
        if top1_fp == 1:
            sp_top1_win += 1
        if top1_fp <= 3:
            sp_top1_place += 1

    # Top1 accuracy for margin model
    m_top1_win = 0
    m_top1_place = 0
    m_race_count = 0
    for race_id, group in test_df_margin.groupby("race_id"):
        if len(group) < 3:
            continue
        m_race_count += 1
        top1_idx = group["pred_margin"].idxmin()  # Lowest margin = best (closest to winner)
        top1_fp = group.loc[top1_idx, "finish_position"]
        if top1_fp == 1:
            m_top1_win += 1
        if top1_fp <= 3:
            m_top1_place += 1

    print(f"\n  REG_SP (speed_idx): Top1 Win={sp_top1_win}/{sp_race_count} "
          f"({100*sp_top1_win/max(sp_race_count,1):.1f}%), "
          f"Top1 Place={sp_top1_place}/{sp_race_count} "
          f"({100*sp_top1_place/max(sp_race_count,1):.1f}%)")
    print(f"  REG_AR (margin):    Top1 Win={m_top1_win}/{m_race_count} "
          f"({100*m_top1_win/max(m_race_count,1):.1f}%), "
          f"Top1 Place={m_top1_place}/{m_race_count} "
          f"({100*m_top1_place/max(m_race_count,1):.1f}%)")

    # Top1 ROI
    sp_roi_data = []
    for race_id, group in test_df_sp.groupby("race_id"):
        if len(group) < 3:
            continue
        top1_idx = group["pred_speed_idx"].idxmax()
        top1 = group.loc[top1_idx]
        odds = top1.get("odds", 0)
        fp = top1.get("finish_position", 99)
        if odds > 0:
            payout = odds if fp == 1 else 0
            sp_roi_data.append(payout)

    m_roi_data = []
    for race_id, group in test_df_margin.groupby("race_id"):
        if len(group) < 3:
            continue
        top1_idx = group["pred_margin"].idxmin()
        top1 = group.loc[top1_idx]
        odds = top1.get("odds", 0)
        fp = top1.get("finish_position", 99)
        if odds > 0:
            payout = odds if fp == 1 else 0
            m_roi_data.append(payout)

    if sp_roi_data:
        sp_roi = sum(sp_roi_data) / len(sp_roi_data)
        print(f"\n  REG_SP Top1 Win ROI: {sp_roi*100:.1f}% ({len(sp_roi_data)} bets)")
    if m_roi_data:
        m_roi = sum(m_roi_data) / len(m_roi_data)
        print(f"  REG_AR Top1 Win ROI: {m_roi*100:.1f}% ({len(m_roi_data)} bets)")

    # === Feature importance ===
    print(f"\n  REG_SP Feature Importance (Top 15):")
    importance = model_sp.feature_importance(importance_type="gain")
    imp_pairs = sorted(zip(feature_cols_sp, importance), key=lambda x: -x[1])
    for name, imp in imp_pairs[:15]:
        print(f"    {name:>35s}: {imp:,.0f}")

    # === Summary ===
    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  Summary")
    print(f"{'='*60}")
    print(f"  REG_SP (speed_idx):  MAE={mae_sp:.2f}, Corr={corr_sp:.4f}")
    print(f"  REG_AR (margin):     MAE={mae_margin:.4f}s, Corr={corr_margin:.4f}")
    print(f"  Note: MAE scales differ (speed_idx ~0-100 vs margin ~0-3s)")
    print(f"  Key comparison: Correlation and ranking quality")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
