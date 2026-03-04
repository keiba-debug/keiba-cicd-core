#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
偏差値ベースgap実験: rank gap vs deviation gap のVB品質比較

現在のgap: odds_rank - rank_p (順位差)
改善案:    z-score(model_pred) - z-score(market_implied_prob)

偏差値gapのメリット:
  - レース内のレベル差を反映
  - 頭数の多寡に依存しない
  - 大混戦vs実力差明確の区別ができる

Usage:
    python -m ml.experiment_deviation_gap
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.experiment import (
    FEATURE_COLS_VALUE, PARAMS_P,
    build_dataset, load_race_json, load_data,
    build_pit_personnel_timeline, train_model,
)
from ml.features.margin_target import add_margin_target_to_df


def compute_deviation_gap(df: pd.DataFrame) -> pd.DataFrame:
    """レース内偏差値ベースのgapを計算

    model_dev:  z-score of pred_proba_p within race (偏差値50+10z)
    market_dev: z-score of implied_prob (1/odds) within race
    dev_gap:    model_dev - market_dev
    """
    df = df.copy()

    # Market implied probability
    df['implied_prob'] = np.where(df['odds'] > 0, 1.0 / df['odds'], 0)

    dev_gaps = []
    model_devs = []
    market_devs = []

    for race_id, group in df.groupby('race_id'):
        idx = group.index

        # Model z-score
        pred = group['pred_proba_p'].values
        pred_mean = pred.mean()
        pred_std = pred.std()
        if pred_std > 1e-8:
            m_z = (pred - pred_mean) / pred_std
        else:
            m_z = np.zeros(len(pred))

        # Market z-score
        imp = group['implied_prob'].values
        imp_mean = imp.mean()
        imp_std = imp.std()
        if imp_std > 1e-8:
            mkt_z = (imp - imp_mean) / imp_std
        else:
            mkt_z = np.zeros(len(imp))

        # dev_gap = model sees more potential than market
        gap = m_z - mkt_z

        for i, ix in enumerate(idx):
            model_devs.append(50 + 10 * m_z[i])
            market_devs.append(50 + 10 * mkt_z[i])
            dev_gaps.append(gap[i])

    df['model_dev'] = model_devs
    df['market_dev'] = market_devs
    df['dev_gap'] = dev_gaps

    return df


def vb_analysis(df, gap_col, label, thresholds):
    """gap閾値ごとのVB品質を分析"""
    results = []
    for thr in thresholds:
        picks = df[df[gap_col] >= thr]
        n = len(picks)
        if n == 0:
            results.append({'threshold': thr, 'n': 0})
            continue

        wins = int(picks['is_win'].sum())
        places = int(picks['is_top3'].sum())
        total_bet = n * 100
        win_return = float(picks[picks['is_win'] == 1]['odds'].sum()) * 100
        win_roi = win_return / total_bet * 100 if total_bet > 0 else 0

        # 平均オッズ
        avg_odds = float(picks['odds'].mean())

        results.append({
            'threshold': thr,
            'n': n,
            'wins': wins,
            'win_rate': 100 * wins / n,
            'places': places,
            'place_rate': 100 * places / n,
            'win_roi': win_roi,
            'avg_odds': avg_odds,
        })

    print(f"\n  {label}:")
    print(f"  {'Thr':>6s} | {'N':>6s} | {'Win':>6s} | {'Win%':>6s} | {'Place':>6s} | {'Place%':>7s} | {'WinROI':>8s} | {'AvgOdds':>8s}")
    print(f"  {'-'*6}-+-{'-'*6}-+-{'-'*6}-+-{'-'*6}-+-{'-'*6}-+-{'-'*7}-+-{'-'*8}-+-{'-'*8}")
    for r in results:
        if r['n'] == 0:
            print(f"  {r['threshold']:6.1f} |      0 |    --- |    --- |    --- |     --- |      --- |      ---")
            continue
        print(f"  {r['threshold']:6.1f} | {r['n']:6d} | {r['wins']:6d} | {r['win_rate']:5.1f}% | "
              f"{r['places']:6d} | {r['place_rate']:6.1f}% | {r['win_roi']:7.1f}% | {r['avg_odds']:7.1f}")

    return results


def main():
    parser = argparse.ArgumentParser(description="Deviation Gap Experiment")
    parser.add_argument("--train-years", default="2020-2024")
    parser.add_argument("--test-years", default="2025-2026")
    args = parser.parse_args()

    t0 = time.time()
    train_start, train_end = map(int, args.train_years.split("-"))
    test_start, test_end = map(int, args.test_years.split("-"))

    print("=" * 70)
    print("  Deviation Gap Experiment: rank gap vs z-score gap")
    print(f"  Train: {train_start} ~ {train_end}")
    print(f"  Test:  {test_start} ~ {test_end}")
    print("=" * 70)

    # === Load data ===
    (history_cache, trainer_index, jockey_index,
     date_index, pace_index, kb_ext_index, training_summary_index,
     race_level_index, pedigree_index, sire_stats_index, *_extra) = load_data()

    pit_trainer_tl, pit_jockey_tl = build_pit_personnel_timeline()

    from ml.features.baba_features import load_baba_index
    baba_index = load_baba_index(range(train_start, test_end + 1))

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

    feature_cols = FEATURE_COLS_VALUE

    # === Train Model P ===
    print("\n[Train] Model P (is_top3, VALUE features)...")
    model_p, metrics_p, _, pred_p, cal_p, pred_p_raw = train_model(
        df_train, df_val, df_test, feature_cols, PARAMS_P, 'is_top3', 'Cls_P'
    )
    df_test['pred_proba_p'] = pred_p

    # === Compute rank-based gap (現行) ===
    df_test['rank_p'] = df_test.groupby('race_id')['pred_proba_p'].rank(
        ascending=False, method='min'
    )
    if 'odds_rank' not in df_test.columns or df_test['odds_rank'].isna().all():
        df_test['odds_rank'] = df_test.groupby('race_id')['odds'].rank(
            ascending=True, method='min'
        )
    df_test['rank_gap'] = df_test['odds_rank'] - df_test['rank_p']

    # === Compute deviation-based gap (改善案) ===
    df_test = compute_deviation_gap(df_test)

    # === 基本統計 ===
    print(f"\n  Test set: {len(df_test):,} entries, "
          f"{df_test['race_id'].nunique():,} races")
    print(f"\n  rank_gap:  mean={df_test['rank_gap'].mean():.2f}, "
          f"std={df_test['rank_gap'].std():.2f}, "
          f"min={df_test['rank_gap'].min():.0f}, max={df_test['rank_gap'].max():.0f}")
    print(f"  dev_gap:   mean={df_test['dev_gap'].mean():.2f}, "
          f"std={df_test['dev_gap'].std():.2f}, "
          f"min={df_test['dev_gap'].min():.2f}, max={df_test['dev_gap'].max():.2f}")
    print(f"  model_dev: mean={df_test['model_dev'].mean():.1f}, "
          f"std={df_test['model_dev'].std():.1f}")
    print(f"  market_dev:mean={df_test['market_dev'].mean():.1f}, "
          f"std={df_test['market_dev'].std():.1f}")

    # === rank gap vs dev gap の相関 ===
    corr = np.corrcoef(df_test['rank_gap'].values, df_test['dev_gap'].values)[0, 1]
    print(f"\n  Correlation(rank_gap, dev_gap): {corr:.4f}")

    # === VB品質比較 ===
    print("\n" + "=" * 70)
    print("  VB Quality Comparison")
    print("=" * 70)

    # Rank gap (現行)
    rank_thresholds = [1, 2, 3, 4, 5, 6, 7]
    results_rank = vb_analysis(df_test, 'rank_gap', 'Rank Gap (current)', rank_thresholds)

    # Deviation gap
    # dev_gap のスケール: z-score差なので概ね -3~+3
    # rank_gap>=3 相当の閾値を探る
    dev_thresholds = [0.3, 0.5, 0.7, 1.0, 1.3, 1.5, 2.0]
    results_dev = vb_analysis(df_test, 'dev_gap', 'Deviation Gap (proposed)', dev_thresholds)

    # === 同一件数での比較 ===
    print("\n" + "=" * 70)
    print("  Same-Volume Comparison (件数を揃えて比較)")
    print("=" * 70)

    # rank_gap>=3 の件数を基準にする
    rank3_count = len(df_test[df_test['rank_gap'] >= 3])
    print(f"\n  Baseline: rank_gap>=3 → {rank3_count:,} picks")

    # dev_gapでrank3_countに最も近い閾値を探す
    best_dev_thr = None
    best_dev_diff = float('inf')
    for thr in np.arange(0.1, 3.0, 0.05):
        n = len(df_test[df_test['dev_gap'] >= thr])
        diff = abs(n - rank3_count)
        if diff < best_dev_diff:
            best_dev_diff = diff
            best_dev_thr = thr

    dev_equiv_count = len(df_test[df_test['dev_gap'] >= best_dev_thr])
    print(f"  Equivalent: dev_gap>={best_dev_thr:.2f} → {dev_equiv_count:,} picks")

    # 直接比較
    picks_rank = df_test[df_test['rank_gap'] >= 3]
    picks_dev = df_test[df_test['dev_gap'] >= best_dev_thr]

    for label, picks in [('rank_gap>=3', picks_rank),
                         (f'dev_gap>={best_dev_thr:.2f}', picks_dev)]:
        n = len(picks)
        wins = int(picks['is_win'].sum())
        places = int(picks['is_top3'].sum())
        bet = n * 100
        win_return = float(picks[picks['is_win'] == 1]['odds'].sum()) * 100
        roi = win_return / bet * 100 if bet > 0 else 0
        avg_odds = float(picks['odds'].mean())
        print(f"  {label:>20s}: N={n:5d}, win={wins} ({100*wins/n:.1f}%), "
              f"place={places} ({100*places/n:.1f}%), ROI={roi:.1f}%, "
              f"avgOdds={avg_odds:.1f}")

    # === overlap分析 ===
    overlap = picks_rank.index.intersection(picks_dev.index)
    rank_only = picks_rank.index.difference(picks_dev.index)
    dev_only = picks_dev.index.difference(picks_rank.index)

    print(f"\n  Overlap analysis:")
    print(f"    Both:      {len(overlap):,} picks")
    print(f"    Rank only: {len(rank_only):,} picks")
    print(f"    Dev only:  {len(dev_only):,} picks")

    # rank_only の品質
    if len(rank_only) > 0:
        ro = df_test.loc[rank_only]
        ro_wins = int(ro['is_win'].sum())
        ro_places = int(ro['is_top3'].sum())
        ro_bet = len(ro) * 100
        ro_ret = float(ro[ro['is_win'] == 1]['odds'].sum()) * 100
        ro_roi = ro_ret / ro_bet * 100 if ro_bet > 0 else 0
        print(f"    Rank-only quality: win={ro_wins}/{len(ro)} ({100*ro_wins/len(ro):.1f}%), "
              f"place={100*ro_places/len(ro):.1f}%, ROI={ro_roi:.1f}%")

    # dev_only の品質
    if len(dev_only) > 0:
        do = df_test.loc[dev_only]
        do_wins = int(do['is_win'].sum())
        do_places = int(do['is_top3'].sum())
        do_bet = len(do) * 100
        do_ret = float(do[do['is_win'] == 1]['odds'].sum()) * 100
        do_roi = do_ret / do_bet * 100 if do_bet > 0 else 0
        print(f"    Dev-only quality:  win={do_wins}/{len(do)} ({100*do_wins/len(do):.1f}%), "
              f"place={100*do_places/len(do):.1f}%, ROI={do_roi:.1f}%")

    # === オッズ帯別分析 ===
    print("\n" + "=" * 70)
    print("  Odds Range Analysis (dev_gap picks)")
    print("=" * 70)

    odds_ranges = [(1, 5), (5, 10), (10, 20), (20, 50), (50, 200)]
    for lo, hi in odds_ranges:
        picks = df_test[(df_test['dev_gap'] >= best_dev_thr) &
                        (df_test['odds'] >= lo) & (df_test['odds'] < hi)]
        n = len(picks)
        if n < 5:
            print(f"  odds {lo:3d}-{hi:3d}: {n:4d} picks (too few)")
            continue
        wins = int(picks['is_win'].sum())
        places = int(picks['is_top3'].sum())
        bet = n * 100
        ret = float(picks[picks['is_win'] == 1]['odds'].sum()) * 100
        roi = ret / bet * 100 if bet > 0 else 0
        print(f"  odds {lo:3d}-{hi:3d}: {n:4d} picks, win={wins} ({100*wins/n:.1f}%), "
              f"place={places} ({100*places/n:.1f}%), ROI={roi:.1f}%")

    # 同じくrank_gapで
    print()
    for lo, hi in odds_ranges:
        picks = df_test[(df_test['rank_gap'] >= 3) &
                        (df_test['odds'] >= lo) & (df_test['odds'] < hi)]
        n = len(picks)
        if n < 5:
            print(f"  odds {lo:3d}-{hi:3d}: {n:4d} picks (too few) [rank_gap]")
            continue
        wins = int(picks['is_win'].sum())
        places = int(picks['is_top3'].sum())
        bet = n * 100
        ret = float(picks[picks['is_win'] == 1]['odds'].sum()) * 100
        roi = ret / bet * 100 if bet > 0 else 0
        print(f"  odds {lo:3d}-{hi:3d}: {n:4d} picks, win={wins} ({100*wins/n:.1f}%), "
              f"place={places} ({100*places/n:.1f}%), ROI={roi:.1f}% [rank_gap]")

    # === サンプルケース: dev_gapが大きいが rank_gapが小さい馬 ===
    print("\n" + "=" * 70)
    print("  Interesting Cases: high dev_gap but low rank_gap")
    print("  (=偏差値的には大きく乖離しているが順位差は小さい)")
    print("=" * 70)

    interesting = df_test[(df_test['dev_gap'] >= 1.5) & (df_test['rank_gap'] <= 2)]
    if len(interesting) > 0:
        print(f"\n  {len(interesting)} entries found")
        wins = int(interesting['is_win'].sum())
        places = int(interesting['is_top3'].sum())
        bet = len(interesting) * 100
        ret = float(interesting[interesting['is_win'] == 1]['odds'].sum()) * 100
        roi = ret / bet * 100 if bet > 0 else 0
        print(f"  Win={wins}/{len(interesting)} ({100*wins/len(interesting):.1f}%), "
              f"Place={places} ({100*places/len(interesting):.1f}%), "
              f"ROI={roi:.1f}%")

        sample = interesting.nlargest(10, 'dev_gap')[
            ['race_id', 'umaban', 'finish_position', 'odds', 'rank_p',
             'odds_rank', 'rank_gap', 'pred_proba_p', 'model_dev',
             'market_dev', 'dev_gap']
        ]
        print(f"\n  Top 10 by dev_gap:")
        print(sample.to_string(index=False))

    # === 逆ケース: rank_gapが大きいが dev_gapが小さい馬 ===
    print("\n  Reverse: high rank_gap but low dev_gap")
    print("  (=順位差は大きいが偏差値的には僅差)")

    reverse = df_test[(df_test['rank_gap'] >= 5) & (df_test['dev_gap'] <= 0.5)]
    if len(reverse) > 0:
        print(f"\n  {len(reverse)} entries found")
        wins = int(reverse['is_win'].sum())
        places = int(reverse['is_top3'].sum())
        bet = len(reverse) * 100
        ret = float(reverse[reverse['is_win'] == 1]['odds'].sum()) * 100
        roi = ret / bet * 100 if bet > 0 else 0
        print(f"  Win={wins}/{len(reverse)} ({100*wins/len(reverse):.1f}%), "
              f"Place={places} ({100*places/len(reverse):.1f}%), "
              f"ROI={roi:.1f}%")
        print("  → These are picks rank_gap would select but shouldn't (low quality)")

    elapsed = time.time() - t0
    print(f"\n  Elapsed: {elapsed:.1f}s")
    print("=" * 70)


if __name__ == "__main__":
    main()
