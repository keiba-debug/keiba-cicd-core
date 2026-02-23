"""芝/ダート別 ability_score 分析スクリプト

Phase A-5: ability_score（= -pred_margin, 高い=強い）の芝/ダート別分布・ROI・最適閾値を分析。
monthly_analysis.py のデータロード＋予測をそのまま流用。
"""

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ml.monthly_analysis import (
    load_data,
    build_dataset,
    load_v55_models,
    predict_on_df,
    bootstrap_roi_ci,
    calc_roi,
)


def main():
    t0 = time.time()
    print("=" * 70)
    print("  Ability Score Analysis: Turf vs Dirt")
    print("  Period: 2025/01 - 2026/02 | Model: v5.5")
    print("=" * 70)

    # --- データ読み込み ---
    print("\n[1] Loading data...")
    (history_cache, trainer_index, jockey_index,
     date_index, pace_index, kb_ext_index, training_summary_index) = load_data()

    print("\n[2] Building dataset...")
    df = build_dataset(
        date_index, history_cache, trainer_index, jockey_index, pace_index,
        kb_ext_index, 2025, 2026, use_db_odds=True,
        training_summary_index=training_summary_index,
    )
    df = df[(df['date'] >= '2025-01-01') & (df['date'] <= '2026-02-28')].copy()
    print(f"  Dataset: {len(df):,} entries, {df['race_id'].nunique():,} races")

    # --- モデル予測 ---
    print("\n[3] Predicting...")
    model_a, model_b, model_w, model_wv, model_reg_b, calibrators = load_v55_models()
    df = predict_on_df(df, model_a, model_b, model_w, model_wv, model_reg_b, calibrators)

    # track_type: 0=turf, 1=dirt
    df_turf = df[df['track_type'] == 0].copy()
    df_dirt = df[df['track_type'] == 1].copy()

    print(f"\n  Turf: {len(df_turf):,} entries, {df_turf['race_id'].nunique():,} races")
    print(f"  Dirt: {len(df_dirt):,} entries, {df_dirt['race_id'].nunique():,} races")

    # ================================================================
    # ① 芝/ダート別 ability 分布 + 閾値通過率
    # ================================================================
    print("\n" + "=" * 70)
    print("  ① Ability Score Distribution (Turf vs Dirt)")
    print("=" * 70)

    for label, sub in [("Turf", df_turf), ("Dirt", df_dirt)]:
        a = sub['margin']  # margin = ability_score (高い=強い)
        print(f"\n--- {label} (全{len(sub):,}頭) ---")
        print(f"  mean={a.mean():.3f}  std={a.std():.3f}  "
              f"min={a.min():.3f}  max={a.max():.3f}  median={a.median():.3f}")

        # パーセンタイル
        for pct in [10, 25, 50, 75, 90]:
            print(f"  P{pct}={a.quantile(pct/100):.3f}", end="")
        print()

        # VB候補 (win_gap>=5, pred_rank_wv<=3) のability分布
        vb = sub[(sub['win_gap'] >= 5) & (sub['pred_rank_wv'] <= 3) & (sub['odds'] > 0)]
        if len(vb) > 0:
            va = vb['margin']
            print(f"  VB候補(gap>=5): {len(vb)}頭  ability mean={va.mean():.3f} std={va.std():.3f} "
                  f"min={va.min():.3f} max={va.max():.3f}")

        # 閾値通過率
        print(f"\n  Threshold pass rates (VB gap>=5):")
        print(f"  {'閾値':>12} | {'通過数':>6} | {'通過率':>7} | {'勝':>4} | {'的中率':>6} | {'ROI':>7}")
        print(f"  " + "-" * 55)
        for thresh in [None, -0.3, -0.5, -0.8, -1.0, -1.2, -1.5, -2.0]:
            if thresh is None:
                mask = (sub['win_gap'] >= 5) & (sub['pred_rank_wv'] <= 3) & (sub['odds'] > 0)
                t_label = "no filter"
            else:
                mask = ((sub['win_gap'] >= 5) & (sub['pred_rank_wv'] <= 3) &
                        (sub['odds'] > 0) & (sub['margin'] >= thresh))
                t_label = f">= {thresh:.1f}"
            bets = sub[mask]
            n = len(bets)
            wins = int(bets['is_win'].sum()) if n > 0 else 0
            pct = n / len(vb) * 100 if len(vb) > 0 else 0
            hit = wins / n * 100 if n > 0 else 0
            roi = calc_roi(bets)
            print(f"  {t_label:>12} | {n:>6} | {pct:>6.1f}% | {wins:>4} | {hit:>5.1f}% | {roi:>6.1f}%")

    # ================================================================
    # ② 芝/ダート別 ROI (条件別)
    # ================================================================
    print("\n" + "=" * 70)
    print("  ② ROI by Condition (Turf vs Dirt)")
    print("=" * 70)

    conditions = [
        ("gap>=5 no_filter", 5, None),
        ("gap>=5 a>=-0.5", 5, -0.5),
        ("gap>=5 a>=-0.8", 5, -0.8),
        ("gap>=5 a>=-1.0", 5, -1.0),
        ("gap>=5 a>=-1.2", 5, -1.2),
        ("gap>=6 no_filter", 6, None),
        ("gap>=6 a>=-0.5", 6, -0.5),
        ("gap>=6 a>=-0.8", 6, -0.8),
        ("gap>=6 a>=-1.0", 6, -1.0),
        ("gap>=6 a>=-1.2", 6, -1.2),
    ]

    print(f"\n{'条件':>20} | {'Turf件数':>8} {'ROI':>7} {'CI':>20} | {'Dirt件数':>8} {'ROI':>7} {'CI':>20} | {'Total件数':>9} {'ROI':>7}")
    print("-" * 120)

    for label, min_gap, min_ability in conditions:
        results = []
        for sub in [df_turf, df_dirt, df]:
            mask = (sub['win_gap'] >= min_gap) & (sub['pred_rank_wv'] <= 3) & (sub['odds'] > 0)
            if min_ability is not None:
                mask = mask & (sub['margin'] >= min_ability)
            bets = sub[mask]
            ci = bootstrap_roi_ci(bets)
            results.append(ci)

        t, d, a = results
        t_ci = f"[{t['ci_low']:.0f}-{t['ci_high']:.0f}%]"
        d_ci = f"[{d['ci_low']:.0f}-{d['ci_high']:.0f}%]"
        print(f"{label:>20} | {t['count']:>5}({t['wins']}W) {t['roi']:>6.1f}% {t_ci:>20} | "
              f"{d['count']:>5}({d['wins']}W) {d['roi']:>6.1f}% {d_ci:>20} | "
              f"{a['count']:>6}({a['wins']}W) {a['roi']:>6.1f}%")

    # ================================================================
    # ③ 芝/ダート別 最適閾値探索 (fine-grained)
    # ================================================================
    print("\n" + "=" * 70)
    print("  ③ Optimal Ability Threshold Search")
    print("=" * 70)

    for label, sub, gap_values in [
        ("Turf", df_turf, [5, 6]),
        ("Dirt", df_dirt, [5, 6]),
    ]:
        print(f"\n--- {label} ---")
        for min_gap in gap_values:
            print(f"\n  gap>={min_gap}:")
            print(f"  {'閾値':>8} | {'件数':>6} | {'勝':>4} | {'的中率':>6} | {'ROI':>8} | {'CI(95%)':>20} | {'利益':>8}")
            print(f"  " + "-" * 75)

            thresholds = [None, -0.2, -0.3, -0.4, -0.5, -0.6, -0.7, -0.8, -0.9, -1.0, -1.2, -1.5, -2.0]
            for thresh in thresholds:
                mask = (sub['win_gap'] >= min_gap) & (sub['pred_rank_wv'] <= 3) & (sub['odds'] > 0)
                if thresh is not None:
                    mask = mask & (sub['margin'] >= thresh)
                bets = sub[mask]
                n = len(bets)
                if n == 0:
                    continue
                wins = int(bets['is_win'].sum())
                hit = wins / n * 100
                roi = calc_roi(bets)
                profit = (bets['is_win'] * bets['odds'] * 100).sum() - n * 100
                ci = bootstrap_roi_ci(bets)
                ci_str = f"[{ci['ci_low']:.0f}-{ci['ci_high']:.0f}%]"
                t_label = "no_filt" if thresh is None else f">={thresh:.1f}"
                print(f"  {t_label:>8} | {n:>6} | {wins:>4} | {hit:>5.1f}% | {roi:>7.1f}% | {ci_str:>20} | {profit:>+8.0f}")

    # ================================================================
    # ④ 推奨プリセット候補
    # ================================================================
    print("\n" + "=" * 70)
    print("  ④ Recommended Presets")
    print("=" * 70)

    presets = [
        # (name, gap, turf_ability, dirt_ability)
        ("current(uniform)", 6, -1.2, -1.2),
        ("turf_strict", 6, -0.5, -1.2),
        ("turf_moderate", 6, -0.8, -1.2),
        ("current_wide", 5, -1.2, -1.2),
        ("wide_turf_strict", 5, -0.5, -1.2),
    ]

    print(f"\n{'Preset':>20} | {'件数':>6} | {'勝':>4} | {'ROI':>8} | {'CI(95%)':>20} | {'利益':>8}")
    print("-" * 80)

    for name, gap, t_ab, d_ab in presets:
        mask_t = ((df_turf['win_gap'] >= gap) & (df_turf['pred_rank_wv'] <= 3) &
                  (df_turf['odds'] > 0) & (df_turf['margin'] >= t_ab))
        mask_d = ((df_dirt['win_gap'] >= gap) & (df_dirt['pred_rank_wv'] <= 3) &
                  (df_dirt['odds'] > 0) & (df_dirt['margin'] >= d_ab))
        bets = pd.concat([df_turf[mask_t], df_dirt[mask_d]])
        n = len(bets)
        wins = int(bets['is_win'].sum())
        roi = calc_roi(bets)
        profit = (bets['is_win'] * bets['odds'] * 100).sum() - n * 100
        ci = bootstrap_roi_ci(bets)
        ci_str = f"[{ci['ci_low']:.0f}-{ci['ci_high']:.0f}%]"
        print(f"{name:>20} | {n:>6} | {wins:>4} | {roi:>7.1f}% | {ci_str:>20} | {profit:>+8.0f}")

    elapsed = time.time() - t0
    print(f"\n[Done] {elapsed:.1f}s")


if __name__ == '__main__':
    main()
