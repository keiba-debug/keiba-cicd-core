#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IDM差分分布分析スクリプト

horse_history_cache + jrdb_sed_index を結合し、
前走比IDM差分(当該レースIDM - 前走IDM)の分布を分析。
パフォーマンス変動予測モデルのカテゴリ閾値を決定する。

Usage:
    python -m ml.analyze_idm_diff
"""

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import config


def main():
    print("=" * 60)
    print("IDM差分(当該レース - 前走)分布分析")
    print("=" * 60)

    # --- データロード ---
    print("\n[Load] Loading data...")

    hh_path = config.ml_dir() / "horse_history_cache.json"
    with open(hh_path, encoding='utf-8') as f:
        history_cache = json.load(f)
    print(f"  Horse history: {len(history_cache):,} horses")

    sed_path = config.indexes_dir() / "jrdb_sed_index.json"
    with open(sed_path, encoding='utf-8') as f:
        jrdb_sed_index = json.load(f)
    print(f"  JRDB SED index: {len(jrdb_sed_index):,} entries")

    # --- IDM差分を収集 ---
    print("\n[Analyze] Computing IDM diffs...")

    diffs = []  # (idm_diff, current_idm, prev_idm, age, career_run, ketto_num, race_date)
    no_sed_current = 0
    no_sed_prev = 0
    zero_idm = 0
    total_pairs = 0

    for ketto_num, runs in history_cache.items():
        if len(runs) < 2:
            continue

        # 時系列順にソート
        sorted_runs = sorted(runs, key=lambda r: r['race_date'])

        for i in range(1, len(sorted_runs)):
            total_pairs += 1
            curr = sorted_runs[i]
            prev = sorted_runs[i - 1]

            # 障害レースを除外
            if curr.get('track_type') == 'obstacle' or prev.get('track_type') == 'obstacle':
                continue

            # SED IDMを取得
            curr_key = f"{ketto_num}_{curr['race_date']}"
            prev_key = f"{ketto_num}_{prev['race_date']}"

            curr_sed = jrdb_sed_index.get(curr_key)
            if not curr_sed:
                no_sed_current += 1
                continue

            prev_sed = jrdb_sed_index.get(prev_key)
            if not prev_sed:
                no_sed_prev += 1
                continue

            curr_idm = curr_sed.get('idm')
            prev_idm = prev_sed.get('idm')

            if curr_idm is None or prev_idm is None:
                continue
            if curr_idm == 0 or prev_idm == 0:
                zero_idm += 1
                continue

            idm_diff = curr_idm - prev_idm

            # 年齢を計算（race_dateの年 - 馬の生年、概算）
            race_year = int(curr['race_date'][:4])
            career_run = i + 1  # 何走目か

            diffs.append({
                'idm_diff': idm_diff,
                'curr_idm': curr_idm,
                'prev_idm': prev_idm,
                'career_run': career_run,
                'race_year': race_year,
                'race_date': curr['race_date'],
                'distance': curr.get('distance', 0),
                'track_type': curr.get('track_type', ''),
                'finish_position': curr.get('finish_position', 0),
            })

    print(f"\n  Total consecutive pairs: {total_pairs:,}")
    print(f"  No SED (current): {no_sed_current:,}")
    print(f"  No SED (prev): {no_sed_prev:,}")
    print(f"  Zero IDM (skipped): {zero_idm:,}")
    print(f"  Valid IDM diffs: {len(diffs):,}")

    if not diffs:
        print("ERROR: No valid IDM diffs found!")
        return

    # --- 基本統計量 ---
    idm_diffs = np.array([d['idm_diff'] for d in diffs])

    print("\n" + "=" * 60)
    print("基本統計量")
    print("=" * 60)
    print(f"  N          = {len(idm_diffs):,}")
    print(f"  Mean       = {np.mean(idm_diffs):.2f}")
    print(f"  Median     = {np.median(idm_diffs):.2f}")
    print(f"  Std        = {np.std(idm_diffs):.2f}")
    print(f"  Min        = {np.min(idm_diffs)}")
    print(f"  Max        = {np.max(idm_diffs)}")
    print(f"  Q25        = {np.percentile(idm_diffs, 25):.1f}")
    print(f"  Q75        = {np.percentile(idm_diffs, 75):.1f}")
    print(f"  IQR        = {np.percentile(idm_diffs, 75) - np.percentile(idm_diffs, 25):.1f}")

    # --- パーセンタイル ---
    print("\n" + "=" * 60)
    print("パーセンタイル分布")
    print("=" * 60)
    for p in [1, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 99]:
        val = np.percentile(idm_diffs, p)
        print(f"  P{p:02d} = {val:+.1f}")

    # --- ヒストグラム（テキスト版） ---
    print("\n" + "=" * 60)
    print("IDM差分ヒストグラム (bin=2)")
    print("=" * 60)
    bins = list(range(-30, 32, 2))
    hist, edges = np.histogram(idm_diffs, bins=bins)
    max_count = max(hist)
    for i, count in enumerate(hist):
        bar_len = int(count / max_count * 50) if max_count > 0 else 0
        lo, hi = edges[i], edges[i + 1]
        pct = count / len(idm_diffs) * 100
        print(f"  [{lo:+3.0f},{hi:+3.0f}) {'#' * bar_len} {count:,} ({pct:.1f}%)")

    # --- カテゴリ閾値の候補を評価 ---
    print("\n" + "=" * 60)
    print("カテゴリ閾値候補の評価")
    print("=" * 60)

    candidates = [
        # (name, big_up_thresh, up_thresh, down_thresh)
        ("A: ±2/±8",  8,  2, -3),
        ("B: ±3/±8",  8,  3, -4),
        ("C: ±3/±10", 10, 3, -4),
        ("D: ±4/±10", 10, 4, -5),
        ("E: ±2/±6",  6,  2, -3),
        ("F: ±3/±6",  6,  3, -4),
    ]

    for name, big_up, up, down in candidates:
        n_big_up = np.sum(idm_diffs >= big_up)
        n_up = np.sum((idm_diffs >= up) & (idm_diffs < big_up))
        n_flat = np.sum((idm_diffs > down) & (idm_diffs < up))
        n_down = np.sum(idm_diffs <= down)
        total = len(idm_diffs)

        print(f"\n  {name}: 大幅上昇(>={big_up}) / 上昇({up}~{big_up-1}) / 平行線({down+1}~{up-1}) / 下降(<={down})")
        print(f"    大幅上昇: {n_big_up:>7,} ({n_big_up/total*100:5.1f}%)")
        print(f"    上昇:     {n_up:>7,} ({n_up/total*100:5.1f}%)")
        print(f"    平行線:   {n_flat:>7,} ({n_flat/total*100:5.1f}%)")
        print(f"    下降:     {n_down:>7,} ({n_down/total*100:5.1f}%)")

    # --- キャリアフェーズ別の分布 ---
    print("\n" + "=" * 60)
    print("キャリアフェーズ別のIDM差分統計")
    print("=" * 60)

    phases = [
        ("2走目 (debut+1)", lambda d: d['career_run'] == 2),
        ("3-5走目 (若駒)", lambda d: 3 <= d['career_run'] <= 5),
        ("6-10走目 (成長期)", lambda d: 6 <= d['career_run'] <= 10),
        ("11-20走目 (安定期)", lambda d: 11 <= d['career_run'] <= 20),
        ("21走目~ (ベテラン)", lambda d: d['career_run'] >= 21),
    ]

    for phase_name, cond in phases:
        phase_diffs = np.array([d['idm_diff'] for d in diffs if cond(d)])
        if len(phase_diffs) == 0:
            continue
        print(f"\n  {phase_name} (n={len(phase_diffs):,})")
        print(f"    Mean={np.mean(phase_diffs):+.2f}, Std={np.std(phase_diffs):.2f}, "
              f"Median={np.median(phase_diffs):+.1f}")
        # 上昇/下降の割合
        n_up = np.sum(phase_diffs >= 2)
        n_down = np.sum(phase_diffs <= -3)
        print(f"    上昇(>=+2): {n_up/len(phase_diffs)*100:.1f}%, "
              f"下降(<=-3): {n_down/len(phase_diffs)*100:.1f}%")

    # --- 芝/ダート別 ---
    print("\n" + "=" * 60)
    print("芝/ダート別のIDM差分統計")
    print("=" * 60)

    for tt in ['turf', 'dirt']:
        tt_diffs = np.array([d['idm_diff'] for d in diffs if d['track_type'] == tt])
        if len(tt_diffs) == 0:
            continue
        label = '芝' if tt == 'turf' else 'ダート'
        print(f"\n  {label} (n={len(tt_diffs):,})")
        print(f"    Mean={np.mean(tt_diffs):+.2f}, Std={np.std(tt_diffs):.2f}, "
              f"Median={np.median(tt_diffs):+.1f}")

    # --- 年別トレンド ---
    print("\n" + "=" * 60)
    print("年別のIDM差分統計")
    print("=" * 60)

    years = sorted(set(d['race_year'] for d in diffs))
    for year in years:
        yr_diffs = np.array([d['idm_diff'] for d in diffs if d['race_year'] == year])
        if len(yr_diffs) == 0:
            continue
        print(f"  {year}: n={len(yr_diffs):>6,}, Mean={np.mean(yr_diffs):+.2f}, "
              f"Std={np.std(yr_diffs):.2f}, Median={np.median(yr_diffs):+.1f}")

    print("\n" + "=" * 60)
    print("分析完了")
    print("=" * 60)


if __name__ == '__main__':
    main()
