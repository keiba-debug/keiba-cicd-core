#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CI Power Analysis: 何件あればCI幅が許容範囲に入るか

Session 44のBootstrap CI結果から、件数 vs CI幅の関係を理論推定し、
bet数増加のための最適な戦略を導き出す。

理論: Bootstrap std ∝ 1/√n_races
      σ_per_race = bootstrap_std * √n_races  (定数)
      new_std = σ_per_race / √n_new
      CI_width ≈ 2 * 1.96 * new_std
"""

import json
import math
import sys
import io
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def load_session44_data():
    """Session 44の結果JSONからCI関連データを抽出"""
    result_path = Path("C:/KEIBA-CICD/data3/ml/ml_experiment_v3_result.json")
    with open(result_path, encoding='utf-8') as f:
        data = json.load(f)

    # bet_engine presets
    be = data.get('bet_engine_presets', {})
    presets = {}
    for name in ['win_only', 'standard', 'conservative', 'aggressive']:
        if name in be:
            p = be[name]
            presets[name] = {
                'num_bets': p['num_bets'],
                'total_roi': p['total_roi'],
                'win_roi': p.get('win_roi', 0),
                'ci_low': p['bootstrap_ci_low'],
                'ci_high': p['bootstrap_ci_high'],
                'ci_std': p['bootstrap_std'],
                'ci_width': round(p['bootstrap_ci_high'] - p['bootstrap_ci_low'], 1),
            }

    # model-level bootstrap CI (win model = pred_rank_wv)
    vb = data.get('value_bets', {})
    model_ci_win = vb.get('bootstrap_ci_win', [])
    model_ci_place = vb.get('bootstrap_ci_place', [])

    return presets, model_ci_win, model_ci_place


def extrapolate_ci(current_std, current_n_races, target_n_races):
    """現在のstdとn_racesから、target_n_racesでのCI幅を推定"""
    sigma_per_race = current_std * math.sqrt(current_n_races)
    new_std = sigma_per_race / math.sqrt(target_n_races)
    ci_width = 2 * 1.96 * new_std
    return ci_width, new_std


def required_n_for_ci_width(current_std, current_n_races, target_ci_width):
    """目標CI幅を達成するのに必要なn_racesを逆算"""
    sigma_per_race = current_std * math.sqrt(current_n_races)
    # target_ci_width = 2 * 1.96 * sigma_per_race / sqrt(n)
    # sqrt(n) = 2 * 1.96 * sigma_per_race / target_ci_width
    # n = (2 * 1.96 * sigma_per_race / target_ci_width)^2
    n = (2 * 1.96 * sigma_per_race / target_ci_width) ** 2
    return math.ceil(n)


def required_n_for_significance(roi, current_std, current_n_races, threshold=100.0):
    """ROI > threshold を95% CIで確認するのに必要なn_races"""
    if roi <= threshold:
        return float('inf')  # ROI自体が閾値以下
    sigma_per_race = current_std * math.sqrt(current_n_races)
    # CI_low > threshold → ROI - 1.96 * sigma_per_race / sqrt(n) > threshold
    # sqrt(n) > 1.96 * sigma_per_race / (ROI - threshold)
    n = (1.96 * sigma_per_race / (roi - threshold)) ** 2
    return math.ceil(n)


def main():
    presets, model_ci_win, model_ci_place = load_session44_data()

    print("=" * 80)
    print("CI Power Analysis — Session 45")
    print("=" * 80)

    # === 1. 現状サマリー ===
    print("\n### 1. 現状サマリー（Session 44 結果）\n")
    print(f"{'Preset':<15} {'Bets':>5} {'ROI':>7} {'CI Low':>7} {'CI High':>8} {'CI幅':>6} {'Std':>6}")
    print("-" * 60)
    for name, d in presets.items():
        print(f"{name:<15} {d['num_bets']:>5} {d['total_roi']:>6.1f}% "
              f"{d['ci_low']:>6.1f}% {d['ci_high']:>7.1f}% "
              f"{d['ci_width']:>5.1f} {d['ci_std']:>5.1f}")

    # Model-level (margin filter なし)
    print("\n### Model-level CI（margin filter なし）\n")
    print("  Win model (pred_rank_wv):")
    print(f"  {'Gap':>3} {'Bets':>5} {'Races':>6} {'Win ROI':>8} {'CI':>20} {'CI幅':>6} {'Std':>6}")
    print("  " + "-" * 60)
    for item in model_ci_win:
        ci_w = item['win_roi_ci_high'] - item['win_roi_ci_low']
        print(f"  {item['min_gap']:>3} {item['bet_count']:>5} {item['n_races_with_vb']:>6} "
              f"{item['win_roi']:>7.1f}% [{item['win_roi_ci_low']:>5.1f}-{item['win_roi_ci_high']:>5.1f}%] "
              f"{ci_w:>5.1f} {item['win_roi_std']:>5.1f}")

    print("\n  Place model (pred_rank_v):")
    print(f"  {'Gap':>3} {'Bets':>5} {'Races':>6} {'Win ROI':>8} {'CI':>20} {'CI幅':>6} {'Std':>6}")
    print("  " + "-" * 60)
    for item in model_ci_place:
        ci_w = item['win_roi_ci_high'] - item['win_roi_ci_low']
        print(f"  {item['min_gap']:>3} {item['bet_count']:>5} {item['n_races_with_vb']:>6} "
              f"{item['win_roi']:>7.1f}% [{item['win_roi_ci_low']:>5.1f}-{item['win_roi_ci_high']:>5.1f}%] "
              f"{ci_w:>5.1f} {item['win_roi_std']:>5.1f}")

    # === 2. CI幅 vs 必要件数（理論推定） ===
    print("\n" + "=" * 80)
    print("### 2. CI幅 vs 必要レース数（理論推定）")
    print("    σ_per_race = bootstrap_std × √n_races  (定数)")
    print("    CI_width ≈ 2 × 1.96 × σ_per_race / √n_new")
    print("=" * 80)

    # bet_engine presets から推定
    # win_only: bet_engine uses race-level resampling internally
    # 推定にはmodel-level dataを使う（n_races_with_vb が分かるから）
    print("\n--- Model-level Win model (pred_rank_wv) ---\n")
    target_widths = [50, 40, 30, 20, 15, 10]
    for item in model_ci_win:
        gap = item['min_gap']
        std = item['win_roi_std']
        n_races = item['n_races_with_vb']
        sigma_pr = std * math.sqrt(n_races)
        print(f"  Gap>={gap}: 現在 {n_races}races, std={std}, σ_per_race={sigma_pr:.1f}")
        print(f"  {'Target CI幅':>15} {'必要races':>12} {'倍率':>6} {'推定年数':>8}")
        for tw in target_widths:
            n_req = required_n_for_ci_width(std, n_races, tw)
            ratio = n_req / n_races
            # テスト期間14ヶ月 → 年あたりn_races/14*12
            races_per_year = n_races / 14 * 12
            years_needed = n_req / races_per_year if races_per_year > 0 else float('inf')
            print(f"  {tw:>10}pp {n_req:>12,} {ratio:>5.1f}x {years_needed:>7.1f}y")
        print()

    # === 3. ROI > 100% を確認するのに必要なレース数 ===
    print("=" * 80)
    print("### 3. ROI > 100% を95% CIで確認するのに必要なレース数")
    print("    CI_low > 100% ⟺ ROI - 1.96 × σ_per_race / √n > 100")
    print("=" * 80)

    # bet_engine presets
    print("\n--- Bet Engine Presets ---\n")
    # win_onlyのn_racesを推定: bet_engine resamples differently
    # win_onlyは356 bets / gap>=5条件 → model-level gap>=5 has 733 races
    # margin filter cuts ~58% → ~300 races with margin-filtered VBs
    # 近似として使う

    # model-levelから推定
    print(f"  {'Strategy':<20} {'ROI':>6} {'σ_per_race':>10} {'必要races':>12} {'倍率':>6} {'推定年数':>8}")
    print("  " + "-" * 70)

    for item in model_ci_win:
        gap = item['min_gap']
        roi = item['win_roi']
        std = item['win_roi_std']
        n_races = item['n_races_with_vb']
        sigma_pr = std * math.sqrt(n_races)
        n_req = required_n_for_significance(roi, std, n_races, 100.0)
        ratio = n_req / n_races if n_req < float('inf') else float('inf')
        races_per_year = n_races / 14 * 12
        years = n_req / races_per_year if n_req < float('inf') and races_per_year > 0 else float('inf')
        label = f"Win model gap>={gap}"
        print(f"  {label:<20} {roi:>5.1f}% {sigma_pr:>9.1f} {n_req:>12,} {ratio:>5.1f}x {years:>7.1f}y")

    print()
    for item in model_ci_place:
        gap = item['min_gap']
        roi = item['win_roi']
        std = item['win_roi_std']
        n_races = item['n_races_with_vb']
        sigma_pr = std * math.sqrt(n_races)
        n_req = required_n_for_significance(roi, std, n_races, 100.0)
        ratio = n_req / n_races if n_req < float('inf') else float('inf')
        races_per_year = n_races / 14 * 12
        years = n_req / races_per_year if n_req < float('inf') and races_per_year > 0 else float('inf')
        label = f"Place model gap>={gap}"
        print(f"  {label:<20} {roi:>5.1f}% {sigma_pr:>9.1f} {n_req:>12,} {ratio:>5.1f}x {years:>7.1f}y")

    # === 4. bet_engine win_only 固有分析 ===
    print("\n" + "=" * 80)
    print("### 4. Bet Engine win_only 固有分析")
    print("=" * 80)

    wo = presets['win_only']
    # win_only: 356 bets, margin filter active
    # Assume ~300 unique races (some races have multiple VB picks)
    # More precise: gap>=5 model-level has 733 races, margin cuts ~50%
    estimated_n_races = 300  # conservative estimate
    std = wo['ci_std']
    roi = wo['total_roi']
    sigma_pr = std * math.sqrt(estimated_n_races)

    print(f"\n  現状: {wo['num_bets']} bets, ROI={roi}%, CI=[{wo['ci_low']}-{wo['ci_high']}%]")
    print(f"  推定レース数: ~{estimated_n_races}, bootstrap_std={std}")
    print(f"  σ_per_race (推定): {sigma_pr:.1f}")

    print(f"\n  {'Target':>15} {'必要races':>12} {'倍率':>6} {'推定年数':>8}")
    print("  " + "-" * 45)
    for tw in target_widths:
        n_req = required_n_for_ci_width(std, estimated_n_races, tw)
        ratio = n_req / estimated_n_races
        years = n_req / (estimated_n_races / 14 * 12)
        print(f"  CI幅{tw:>3}pp {n_req:>12,} {ratio:>5.1f}x {years:>7.1f}y")

    n_sig = required_n_for_significance(roi, std, estimated_n_races, 100.0)
    years_sig = n_sig / (estimated_n_races / 14 * 12) if n_sig < float('inf') else float('inf')
    print(f"\n  ROI>100%確認(95%CI): {n_sig:,} races ({n_sig/estimated_n_races:.1f}x), ~{years_sig:.1f}年")

    # === 5. 結論と推奨 ===
    print("\n" + "=" * 80)
    print("### 5. 結論と推奨")
    print("=" * 80)

    print("""
  ■ 現実認識
    - win_only(gap>=5, margin<=1.2)でROI>100%を95%CIで確認するには
      現在の~25倍のデータ（~30年分）が必要
    - これはバックテスト期間の延長だけでは不可能

  ■ 実行可能な選択肢
    A) margin filter撤廃 → 件数2.4倍(356→854), ただしROI 80.7%(赤字)
    B) gap>=4に緩和 → 件数4倍(356→1413), ROI 83.5%
    C) gap>=3に緩和 → 件数6.4倍(356→2286), ROI 86.0%
    D) gap>=2に緩和 → 件数10.5倍(356→3730), ROI 84.4%

  ■ ジレンマ
    件数を増やすとCI幅は狭まるが、ROI自体が下がる
    → 件数を増やしてもROI<100%が確認されるだけの可能性

  ■ 推奨アクション
    1. まず margin filter なし + gap>=5 で走らせる（854件、ROI 80.7%）
       → margin filterの効果をCI込みで評価できるか確認
    2. 訓練期間を2020-2022、val=2023、test=2024-2026に変更
       → テスト期間が2倍（28ヶ月）、件数も約2倍
    3. 上記①②の組み合わせで最もCI幅が狭い条件を探す
    4. subsampling実験: gap>=2の3730件をサブサンプリングして
       n vs CI幅の実測カーブを描く（理論推定の検証）
    """)


if __name__ == '__main__':
    main()
