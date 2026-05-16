#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Polaris（現行v7.9 baseモデル）弱点分析

polarisが苦手なパターンを特定し、
追加モデル（Stars/Nebula系）の設計根拠を作る。

Usage:
    python -m ml.analyze_polaris_weakness
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import config
from core.jravan import race_id as rid_mod
from ml.utils.backtest_cache import load_backtest_cache, flatten_to_df
from ml.utils.segments import (
    bin_runners, bin_ev, bin_gap, bin_closing_strength,
    RUNNER_LABELS, EV_LABELS, GAP_LABELS, CS_LABELS,
)

DATA_ROOT = Path(config.data_root())


def load_backtest_flat():
    """backtest_cacheを馬単位のフラットDataFrameに変換"""
    races = load_backtest_cache(quiet=True)
    return flatten_to_df(races)


def analyze_market_correlation(df):
    """分析1: polarisと人気順の相関"""
    print("=" * 70)
    print("■ 分析1: Polaris予測 vs 人気順（odds_rank）の相関")
    print("=" * 70)

    valid = df[(df["rank_p"] > 0) & (df["odds_rank"] > 0)]
    corr_p = valid["rank_p"].corr(valid["odds_rank"])
    corr_w = valid["rank_w"].corr(valid["odds_rank"])

    print(f"\n  rank_p vs odds_rank 相関: {corr_p:.4f}")
    print(f"  rank_w vs odds_rank 相関: {corr_w:.4f}")

    # 一致率
    agree_exact = (valid["rank_p"] == valid["odds_rank"]).mean()
    top3_market = valid[valid["odds_rank"] <= 3]
    agree_top3 = (top3_market["rank_p"] <= 3).mean() if len(top3_market) > 0 else 0

    print(f"\n  rank_p == odds_rank 完全一致率: {agree_exact:.1%}")
    print(f"  odds_rank Top3のうちrank_pもTop3: {agree_top3:.1%}")

    # polarisが人気と異なる予測をした場合の成績
    valid = valid.copy()
    valid["model_vs_market"] = valid["rank_p"] - valid["odds_rank"]

    print("\n  ● 乖離度別の複勝率（rank_p - odds_rank）:")
    gap_bins = [-99, -5, -3, -1, 1, 3, 5, 99]
    gap_labels = ["-5~", "-4~-3", "-2~-1", "0~1", "2~3", "4~5", "6~"]
    valid["gap_band"] = pd.cut(valid["model_vs_market"], bins=gap_bins, labels=gap_labels)
    gap_stats = valid.groupby("gap_band", observed=False).agg(
        count=("is_top3", "size"),
        top3_rate=("is_top3", "mean"),
        win_rate=("is_win", "mean"),
    )
    for band, row in gap_stats.iterrows():
        if row["count"] > 0:
            print(f"    {band:>6s}: n={row['count']:>5.0f}  複勝率={row['top3_rate']:.1%}  勝率={row['win_rate']:.1%}")


def analyze_upset_detection(df):
    """分析2: 人気薄好走の見逃し率"""
    print("\n" + "=" * 70)
    print("■ 分析2: 人気薄好走（激走）の検出力")
    print("=" * 70)

    upsets = df[df["is_upset"]]
    big_upsets = df[df["is_big_upset"]]
    total_races = df["race_id"].nunique()

    print(f"\n  激走馬(odds>=10 & top3): {len(upsets)}頭 / {total_races}R ({len(upsets)/total_races:.1f}頭/R)")
    print(f"  大激走(odds>=20 & top3): {len(big_upsets)}頭 / {total_races}R ({len(big_upsets)/total_races:.1f}頭/R)")

    if len(upsets) > 0:
        print(f"\n  ● 激走馬のpolaris rank_p分布:")
        desc = upsets["rank_p"].describe()
        print(f"    平均: {desc['mean']:.1f}位  中央値: {desc['50%']:.1f}位  25%ile: {desc['25%']:.1f}  75%ile: {desc['75%']:.1f}")

        print(f"\n  ● 激走馬のrank_p帯別内訳:")
        rank_bins = [0, 3, 5, 8, 99]
        rank_labels = ["Top3", "4-5位", "6-8位", "9位~"]
        upsets_c = upsets.copy()
        upsets_c["rank_band"] = pd.cut(upsets_c["rank_p"], bins=rank_bins, labels=rank_labels)
        for band in rank_labels:
            cnt = (upsets_c["rank_band"] == band).sum()
            pct = cnt / len(upsets_c) * 100
            print(f"    {band:>6s}: {cnt:>4d}頭 ({pct:>5.1f}%)")

    if len(big_upsets) > 0:
        print(f"\n  ● 大激走馬(odds>=20)のrank_p帯別:")
        big_c = big_upsets.copy()
        big_c["rank_band"] = pd.cut(big_c["rank_p"], bins=[0, 3, 5, 8, 99], labels=["Top3", "4-5位", "6-8位", "9位~"])
        for band in ["Top3", "4-5位", "6-8位", "9位~"]:
            cnt = (big_c["rank_band"] == band).sum()
            pct = cnt / len(big_c) * 100
            print(f"    {band:>6s}: {cnt:>4d}頭 ({pct:>5.1f}%)")

    # 激走馬の特徴（どんな条件で起きるか）
    if len(upsets) >= 20:
        print(f"\n  ● 激走が多い条件:")
        print(f"    馬場別:")
        for t in ["芝", "ダ"]:
            sub_all = df[df["track_type"] == t]
            sub_up = upsets[upsets["track_type"] == t]
            rate = len(sub_up) / sub_all["race_id"].nunique() if sub_all["race_id"].nunique() > 0 else 0
            print(f"      {t}: {len(sub_up)}頭 ({rate:.2f}頭/R)")

        print(f"    クラス別:")
        for g in ["新馬", "未勝利", "1勝", "2勝", "3勝", "OP", "リステッド", "G3", "G2", "G1"]:
            sub_all = df[df["grade"] == g]
            sub_up = upsets[upsets["grade"] == g]
            n_races = sub_all["race_id"].nunique()
            if n_races >= 10:
                rate = len(sub_up) / n_races
                print(f"      {g:>8s}: {len(sub_up):>3d}頭 / {n_races:>4d}R ({rate:.2f}頭/R)")


def analyze_odds_band_calibration(df):
    """分析3: オッズ帯別のキャリブレーション"""
    print("\n" + "=" * 70)
    print("■ 分析3: オッズ帯別キャリブレーション & ROI")
    print("=" * 70)

    print(f"\n  {'オッズ帯':>10s}  {'頭数':>6s}  {'実複勝率':>8s}  {'予測P平均':>8s}  {'乖離':>6s}  {'実勝率':>6s}  {'単勝ROI':>8s}")
    print("  " + "-" * 68)

    for band in df["odds_band"].cat.categories:
        sub = df[df["odds_band"] == band]
        if len(sub) == 0:
            continue
        actual_p = sub["is_top3"].mean()
        pred_p = sub["pred_p"].mean()
        actual_w = sub["is_win"].mean()
        gap_p = pred_p - actual_p
        # 単勝ROI: 全頭均等買い
        win_return = sub[sub["is_win"]]["odds"].sum()
        roi = win_return / len(sub) * 100
        print(
            f"  {band:>10s}  {len(sub):>6d}  {actual_p:>8.1%}  {pred_p:>8.1%}  {gap_p:>+6.1%}  "
            f"{actual_w:>6.1%}  {roi:>7.1f}%"
        )


def analyze_condition_weakness(df):
    """分析4: 条件別の精度差"""
    print("\n" + "=" * 70)
    print("■ 分析4: 条件別のpolaris精度（rank_p=1の成績）")
    print("=" * 70)

    top1 = df[df["rank_p"] == 1]
    overall_win = top1["is_win"].mean()
    overall_top3 = top1["is_top3"].mean()
    print(f"\n  全体: n={len(top1)}  勝率={overall_win:.1%}  複勝率={overall_top3:.1%}")

    # track_type
    print("\n  ● 馬場別:")
    for track in ["芝", "ダ"]:
        sub = top1[top1["track_type"] == track]
        if len(sub) > 0:
            diff_w = sub["is_win"].mean() - overall_win
            print(f"    {track}: n={len(sub)}  勝率={sub['is_win'].mean():.1%}({diff_w:+.1%})  複勝率={sub['is_top3'].mean():.1%}")

    # grade
    print("\n  ● クラス別:")
    grade_order = ["新馬", "未勝利", "1勝", "2勝", "3勝", "OP", "リステッド", "G3", "G2", "G1"]
    for g in grade_order:
        sub = top1[top1["grade"] == g]
        if len(sub) >= 10:
            diff_w = sub["is_win"].mean() - overall_win
            marker = " <<WEAK" if diff_w < -0.05 else (" <<STRONG" if diff_w > 0.05 else "")
            print(f"    {g:>8s}: n={len(sub):>4d}  勝率={sub['is_win'].mean():.1%}({diff_w:+.1%})  複勝率={sub['is_top3'].mean():.1%}{marker}")

    # 頭数帯
    print("\n  ● 頭数帯別:")
    top1_c = top1.copy()
    top1_c["runner_band"] = bin_runners(top1_c["num_runners"])
    for band in RUNNER_LABELS:
        sub = top1_c[top1_c["runner_band"] == band]
        if len(sub) >= 10:
            diff_w = sub["is_win"].mean() - overall_win
            print(f"    {band:>8s}: n={len(sub):>4d}  勝率={sub['is_win'].mean():.1%}({diff_w:+.1%})  複勝率={sub['is_top3'].mean():.1%}")


def analyze_false_positives(df):
    """分析5: polarisが高評価だったのに走らなかった馬"""
    print("\n" + "=" * 70)
    print("■ 分析5: Polaris高評価の不発 & Top3全滅パターン")
    print("=" * 70)

    # rank_p=1 の着順分布
    top1 = df[df["rank_p"] == 1]
    print(f"\n  ● rank_p=1の着順分布:")
    for pos in range(1, 6):
        cnt = (top1["finish"] == pos).sum()
        print(f"    {pos}着: {cnt}回 ({cnt/len(top1):.1%})")
    miss = (top1["finish"] > 5).sum()
    print(f"    掲示板外: {miss}回 ({miss/len(top1):.1%})")

    # Top3全滅レース
    total_races = 0
    full_miss = 0
    miss_details = []

    for race_id, group in df.groupby("race_id"):
        top3_model = group[group["rank_p"] <= 3]
        if len(top3_model) == 0:
            continue
        total_races += 1
        if top3_model["is_top3"].sum() == 0:
            full_miss += 1
            actual_top3 = group[group["is_top3"]]
            if len(actual_top3) > 0:
                miss_details.append({
                    "race_id": race_id,
                    "avg_odds_rank": actual_top3["odds_rank"].mean(),
                    "avg_odds": actual_top3["odds"].mean(),
                    "grade": group["grade"].iloc[0],
                    "track_type": group["track_type"].iloc[0],
                    "num_runners": group["num_runners"].iloc[0],
                })

    print(f"\n  ● rank_p Top3 全滅レース: {full_miss}/{total_races} ({full_miss/total_races:.1%})")

    if miss_details:
        fm_df = pd.DataFrame(miss_details)
        print(f"\n    全滅レースで実際に来た馬:")
        print(f"      平均odds_rank: {fm_df['avg_odds_rank'].mean():.1f}番人気")
        print(f"      平均オッズ: {fm_df['avg_odds'].mean():.1f}倍")
        print(f"      平均頭数: {fm_df['num_runners'].mean():.1f}頭")

        print(f"\n    全滅レースのクラス分布:")
        for g, cnt in fm_df["grade"].value_counts().head(8).items():
            pct = cnt / len(fm_df) * 100
            print(f"      {g}: {cnt}R ({pct:.1f}%)")

        print(f"\n    全滅レースの馬場分布:")
        for t, cnt in fm_df["track_type"].value_counts().items():
            pct = cnt / len(fm_df) * 100
            print(f"      {t}: {cnt}R ({pct:.1f}%)")


def analyze_roi_comparison(df):
    """分析6: 単勝均等買いROI — polaris vs 人気順"""
    print("\n" + "=" * 70)
    print("■ 分析6: 単勝均等買いROI（polaris rank_p vs odds_rank）")
    print("=" * 70)

    print(f"\n  {'順位':>6s}  {'polaris勝率':>12s}  {'polaris単ROI':>12s}  {'人気順勝率':>12s}  {'人気順単ROI':>12s}  {'差':>6s}")
    print("  " + "-" * 65)

    for rank in range(1, 9):
        p_sub = df[df["rank_p"] == rank]
        p_win = p_sub["is_win"].mean() if len(p_sub) > 0 else 0
        p_roi = (p_sub[p_sub["is_win"]]["odds"].sum() / len(p_sub) * 100) if len(p_sub) > 0 else 0

        m_sub = df[df["odds_rank"] == rank]
        m_win = m_sub["is_win"].mean() if len(m_sub) > 0 else 0
        m_roi = (m_sub[m_sub["is_win"]]["odds"].sum() / len(m_sub) * 100) if len(m_sub) > 0 else 0

        diff = p_roi - m_roi
        print(f"  {rank:>5d}位  {p_win:>11.1%}  {p_roi:>11.1f}%  {m_win:>11.1%}  {m_roi:>11.1f}%  {diff:>+5.1f}")


def analyze_ev_effectiveness(df):
    """分析7: EV（期待値）の実効性"""
    print("\n" + "=" * 70)
    print("■ 分析7: win_ev帯別の実績")
    print("=" * 70)

    valid = df[df["win_ev"] > 0]
    if len(valid) == 0:
        print("  win_ev データなし")
        return

    valid = valid.copy()
    valid["ev_band"] = bin_ev(valid["win_ev"])

    print(f"\n  {'EV帯':>10s}  {'頭数':>6s}  {'勝率':>6s}  {'単勝ROI':>8s}  {'平均odds':>8s}")
    print("  " + "-" * 48)

    for band in EV_LABELS:
        sub = valid[valid["ev_band"] == band]
        if len(sub) == 0:
            continue
        win_rate = sub["is_win"].mean()
        roi = (sub[sub["is_win"]]["odds"].sum() / len(sub) * 100) if len(sub) > 0 else 0
        avg_odds = sub["odds"].mean()
        marker = " *" if band in ["1.0-1.3", "1.3-1.5", "1.5-2.0", "2.0+"] and roi > 100 else ""
        print(f"  {band:>10s}  {len(sub):>6d}  {win_rate:>6.1%}  {roi:>7.1f}%  {avg_odds:>7.1f}{marker}")


def analyze_vb_gap_value(df):
    """分析8: VBギャップ（モデルと市場の乖離）の価値"""
    print("\n" + "=" * 70)
    print("■ 分析8: VBギャップ帯別の実績（モデルが市場より高く評価）")
    print("=" * 70)

    valid = df[df["vb_gap"] > 0]  # モデルが市場より高評価
    if len(valid) == 0:
        print("  VBギャップデータなし")
        return

    valid = valid.copy()
    valid["gap_band"] = bin_gap(valid["vb_gap"])

    print(f"\n  {'Gap帯':>6s}  {'頭数':>6s}  {'複勝率':>8s}  {'勝率':>6s}  {'単ROI':>7s}  {'平均odds':>8s}")
    print("  " + "-" * 52)

    for band in GAP_LABELS:
        sub = valid[valid["gap_band"] == band]
        if len(sub) == 0:
            continue
        top3 = sub["is_top3"].mean()
        win = sub["is_win"].mean()
        roi = (sub[sub["is_win"]]["odds"].sum() / len(sub) * 100) if len(sub) > 0 else 0
        avg_odds = sub["odds"].mean()
        print(f"  {band:>6s}  {len(sub):>6d}  {top3:>8.1%}  {win:>6.1%}  {roi:>6.1f}%  {avg_odds:>7.1f}")


def analyze_closing_strength_impact(df):
    """分析9: 末脚力（closing_strength）とpolarisの関係"""
    print("\n" + "=" * 70)
    print("■ 分析9: 末脚力スコア別の成績")
    print("=" * 70)

    valid = df[df["closing_strength"] > 0]
    if len(valid) == 0:
        print("  closing_strengthデータなし")
        return

    valid = valid.copy()
    valid["cs_band"] = bin_closing_strength(valid["closing_strength"])

    print(f"\n  {'末脚帯':>8s}  {'頭数':>6s}  {'複勝率':>8s}  {'勝率':>6s}  {'平均rank_p':>10s}  {'激走率':>6s}")
    print("  " + "-" * 55)

    for band in CS_LABELS:
        sub = valid[valid["cs_band"] == band]
        if len(sub) == 0:
            continue
        top3 = sub["is_top3"].mean()
        win = sub["is_win"].mean()
        avg_rank = sub["rank_p"].mean()
        upset = (sub["is_top3"] & (sub["odds"] >= 10)).mean()
        print(f"  {band:>8s}  {len(sub):>6d}  {top3:>8.1%}  {win:>6.1%}  {avg_rank:>10.1f}  {upset:>6.1%}")


def summarize_weaknesses(df):
    """弱点サマリー"""
    print("\n" + "=" * 70)
    print("■ 弱点サマリー → 追加モデル設計への示唆")
    print("=" * 70)

    valid = df[(df["rank_p"] > 0) & (df["odds_rank"] > 0)]
    corr = valid["rank_p"].corr(valid["odds_rank"])

    upsets = df[df["is_upset"]]
    upset_in_top5 = upsets[upsets["rank_p"] <= 5]
    upset_catch = len(upset_in_top5) / len(upsets) if len(upsets) > 0 else 0

    total_r = 0
    miss_r = 0
    for _, group in df.groupby("race_id"):
        top3m = group[group["rank_p"] <= 3]
        if len(top3m) == 0:
            continue
        total_r += 1
        if top3m["is_top3"].sum() == 0:
            miss_r += 1
    full_miss = miss_r / total_r if total_r > 0 else 0

    # polaris rank_p=1 勝率
    top1 = df[df["rank_p"] == 1]
    top1_win = top1["is_win"].mean()

    # EV>=1.0 の実ROI
    ev_pos = df[df["win_ev"] >= 1.0]
    ev_roi = (ev_pos[ev_pos["is_win"]]["odds"].sum() / len(ev_pos) * 100) if len(ev_pos) > 0 else 0

    print(f"""
  ━━━ Polarisの強み ━━━
  ✓ rank_p=1 勝率: {top1_win:.1%}
  ✓ EV>=1.0 単勝ROI: {ev_roi:.1f}%

  ━━━ Polarisの弱点 ━━━
  1. 人気順との相関: {corr:.3f}
     → 独自視点が弱い。人気順をなぞりがち

  2. 激走馬キャッチ率(rank_p<=5): {upset_catch:.1%}
     → 残り{1-upset_catch:.1%}の穴馬を見逃し

  3. Top3全滅率: {full_miss:.1%}
     → 上位3頭が全員3着外だったレース

  ━━━ 追加モデルへの示唆 ━━━

  【Stars系（馬単位）】
  ● sirius（激走）: 見逃し{1-upset_catch:.0%}の穴馬を専用ラベルで学習
  ● nova（残差）: odds_rankとの乖離を学習し、独自視点を強化
  ● vega（血統）: 条件別弱点（特定クラス/距離）を血統視点で補完

  【Nebula系（レース単位）】
  ● aurora（荒れ度）: Top3全滅レースを事前予測→sirius重視判断
  ● eclipse（差し追込）: 既存closingモデルの発展形
""")


def main():
    print("Polaris（現行v7.9 baseモデル）弱点分析")
    print("=" * 70)

    print("Loading backtest_cache.json ...")
    df = load_backtest_flat()
    print(f"  {len(df):,}エントリ / {df['race_id'].nunique():,}レース")
    print(f"  期間: {df['date'].min()} ~ {df['date'].max()}")
    print()

    analyze_market_correlation(df)
    analyze_upset_detection(df)
    analyze_odds_band_calibration(df)
    analyze_condition_weakness(df)
    analyze_false_positives(df)
    analyze_roi_comparison(df)
    analyze_ev_effectiveness(df)
    analyze_vb_gap_value(df)
    analyze_closing_strength_impact(df)
    summarize_weaknesses(df)


if __name__ == "__main__":
    main()
