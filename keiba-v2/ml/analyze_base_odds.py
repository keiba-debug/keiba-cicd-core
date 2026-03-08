"""
基準オッズ vs 実オッズ vs モデル予測 のバックテスト分析

Phase 1: JRDB基準オッズの有用性を検証
- 基準オッズ vs 実オッズの乖離と的中率の関係
- smart money仮説の検証
- モデル推奨馬のオッズ帯別ROI分析
"""

import json
import glob
import os
import sys
import numpy as np
from collections import defaultdict
from pathlib import Path

DATA_DIR = "C:/KEIBA-CICD/data3"


def load_kyi_index():
    """JRDB KYI index (base_odds, base_popularity etc.)"""
    path = f"{DATA_DIR}/indexes/jrdb_kyi_index.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_races_with_results(year_range=(2024, 2025)):
    """Load race JSONs with finish results, merge with predictions if available"""
    races = []
    for year in range(year_range[0], year_range[1] + 1):
        pattern = f"{DATA_DIR}/races/{year}/**/race_[0-9]*.json"
        files = glob.glob(pattern, recursive=True)
        for fpath in files:
            with open(fpath, encoding="utf-8") as f:
                race = json.load(f)
            # Only include races with results
            has_results = any(
                e.get("finish_position") and e["finish_position"] > 0
                for e in race.get("entries", [])
            )
            if has_results and race.get("num_runners", 0) >= 5:
                races.append(race)
    return races


def load_predictions_index(year_range=(2024, 2025)):
    """Load all predictions.json files, indexed by race_id"""
    pred_index = {}
    for year in range(year_range[0], year_range[1] + 1):
        pattern = f"{DATA_DIR}/races/{year}/**/predictions.json"
        for fpath in glob.glob(pattern, recursive=True):
            try:
                with open(fpath, encoding="utf-8") as f:
                    pdata = json.load(f)
                for r in pdata.get("races", []):
                    rid = r.get("race_id")
                    if rid:
                        pred_index[rid] = {
                            e.get("umaban"): e for e in r.get("entries", [])
                        }
            except Exception:
                continue
    return pred_index


def analyze(kyi, races, pred_index):
    """Main analysis"""
    # Collect data points: each horse with base_odds + actual_odds + result
    records = []
    missing_kyi = 0
    matched = 0

    for race in races:
        race_id = race.get("race_id", "")
        date = race.get("date", "")
        venue_code = str(race.get("venue_code", ""))
        track_type = race.get("track_type", "")

        # Obstacle skip
        if "障" in race.get("race_name", "") or track_type == "障害":
            continue

        pred_entries = pred_index.get(race_id, {})

        for entry in race.get("entries", []):
            ketto_num = entry.get("ketto_num", "")
            umaban = entry.get("umaban")
            finish_pos = entry.get("finish_position")
            actual_odds = entry.get("odds")

            if not ketto_num or not finish_pos or not actual_odds:
                continue
            if finish_pos <= 0 or actual_odds <= 0:
                continue

            # KYI lookup
            kyi_key = f"{ketto_num}_{date}"
            kyi_data = kyi.get(kyi_key)
            if not kyi_data:
                missing_kyi += 1
                continue

            base_odds = kyi_data.get("base_odds")
            base_pop = kyi_data.get("base_popularity")
            if not base_odds or base_odds <= 0:
                continue

            # Prediction data
            pred = pred_entries.get(umaban, {})
            pred_proba_w = pred.get("pred_proba_w_cal")
            ar_deviation = pred.get("ar_deviation")
            rank_p = pred.get("rank_p")
            rank_w = pred.get("rank_w")
            win_ev = pred.get("win_ev")
            is_vb = pred.get("is_value_bet", False)

            matched += 1
            records.append({
                "race_id": race_id,
                "date": date,
                "umaban": umaban,
                "finish_pos": finish_pos,
                "is_win": finish_pos == 1,
                "is_top3": finish_pos <= 3,
                "actual_odds": actual_odds,
                "base_odds": base_odds,
                "base_pop": base_pop,
                "odds_move": actual_odds / base_odds,  # >1 = odds drifted up
                "log_odds_move": np.log(actual_odds / base_odds),
                "pred_proba_w": pred_proba_w,
                "ar_deviation": ar_deviation,
                "rank_p": rank_p,
                "rank_w": rank_w,
                "win_ev": win_ev,
                "is_vb": is_vb,
                "num_runners": race.get("num_runners", 0),
                "track_type": track_type,
            })

    print(f"\n=== データ概要 ===")
    print(f"対象レース数: {len(races)}")
    print(f"KYIマッチ: {matched}, KYI不一致: {missing_kyi}")
    print(f"分析レコード: {len(records)}")

    if not records:
        print("No data!")
        return

    # ============================================
    # 分析1: 基準オッズ vs 実オッズの乖離と勝率
    # ============================================
    print(f"\n{'='*60}")
    print("分析1: オッズ変動方向と勝率・回収率")
    print(f"{'='*60}")
    print("odds_move = 実オッズ / 基準オッズ")
    print("  >1.0: オッズ上昇（人気落ち）  <1.0: オッズ下降（人気上昇）")

    bins = [
        ("大幅↓ (≤0.5)", lambda r: r["odds_move"] <= 0.5),
        ("↓ (0.5-0.7)", lambda r: 0.5 < r["odds_move"] <= 0.7),
        ("やや↓ (0.7-0.9)", lambda r: 0.7 < r["odds_move"] <= 0.9),
        ("変化なし (0.9-1.1)", lambda r: 0.9 < r["odds_move"] <= 1.1),
        ("やや↑ (1.1-1.5)", lambda r: 1.1 < r["odds_move"] <= 1.5),
        ("↑ (1.5-2.0)", lambda r: 1.5 < r["odds_move"] <= 2.0),
        ("大幅↑ (>2.0)", lambda r: r["odds_move"] > 2.0),
    ]

    print(f"\n{'カテゴリ':<22} {'件数':>6} {'勝率':>7} {'複勝率':>7} {'単回収':>7} {'複回収':>7}")
    print("-" * 65)

    for label, cond in bins:
        subset = [r for r in records if cond(r)]
        n = len(subset)
        if n < 50:
            continue
        wins = sum(1 for r in subset if r["is_win"])
        top3 = sum(1 for r in subset if r["is_top3"])
        win_return = sum(r["actual_odds"] for r in subset if r["is_win"])
        # 複勝は概算（実オッズの1/3で近似）
        place_return = sum(r["actual_odds"] / 3.0 for r in subset if r["is_top3"])
        print(f"{label:<22} {n:>6} {wins/n*100:>6.1f}% {top3/n*100:>6.1f}% {win_return/n*100:>6.1f}% {place_return/n*100:>6.1f}%")

    # ============================================
    # 分析2: 人気帯別のオッズ変動効果
    # ============================================
    print(f"\n{'='*60}")
    print("分析2: 基準人気帯別のオッズ変動と勝率")
    print(f"{'='*60}")

    pop_bins = [
        ("1-3人気", lambda r: r["base_pop"] and r["base_pop"] <= 3),
        ("4-6人気", lambda r: r["base_pop"] and 4 <= r["base_pop"] <= 6),
        ("7-9人気", lambda r: r["base_pop"] and 7 <= r["base_pop"] <= 9),
        ("10人気以下", lambda r: r["base_pop"] and r["base_pop"] >= 10),
    ]

    move_cats = [
        ("人気↑(≤0.7)", lambda r: r["odds_move"] <= 0.7),
        ("変化小(0.7-1.3)", lambda r: 0.7 < r["odds_move"] <= 1.3),
        ("人気↓(>1.3)", lambda r: r["odds_move"] > 1.3),
    ]

    for pop_label, pop_cond in pop_bins:
        pop_subset = [r for r in records if pop_cond(r)]
        print(f"\n  【{pop_label}】(n={len(pop_subset)})")
        print(f"  {'オッズ変動':<18} {'件数':>6} {'勝率':>7} {'複勝率':>7} {'単回収':>7}")
        print(f"  {'-'*50}")
        for m_label, m_cond in move_cats:
            subset = [r for r in pop_subset if m_cond(r)]
            n = len(subset)
            if n < 30:
                print(f"  {m_label:<18} {n:>6}  (サンプル不足)")
                continue
            wins = sum(1 for r in subset if r["is_win"])
            top3 = sum(1 for r in subset if r["is_top3"])
            win_return = sum(r["actual_odds"] for r in subset if r["is_win"])
            print(f"  {m_label:<18} {n:>6} {wins/n*100:>6.1f}% {top3/n*100:>6.1f}% {win_return/n*100:>6.1f}%")

    # ============================================
    # 分析3: smart money仮説検証
    # 同じ基準オッズ帯で実オッズが異なる馬の比較
    # ============================================
    print(f"\n{'='*60}")
    print("分析3: Smart Money仮説")
    print("同じ基準オッズ帯で、実オッズが下がった馬 vs 上がった馬")
    print(f"{'='*60}")

    base_bins = [
        ("基準3-5倍", 3, 5),
        ("基準5-10倍", 5, 10),
        ("基準10-20倍", 10, 20),
        ("基準20-50倍", 20, 50),
    ]

    for label, lo, hi in base_bins:
        subset = [r for r in records if lo <= r["base_odds"] < hi]
        if len(subset) < 100:
            continue
        down = [r for r in subset if r["odds_move"] <= 0.7]  # 実オッズ大幅低下
        same = [r for r in subset if 0.85 <= r["odds_move"] <= 1.15]  # ほぼ変化なし
        up = [r for r in subset if r["odds_move"] >= 1.5]  # 実オッズ大幅上昇

        print(f"\n  【{label}】(全{len(subset)}件)")
        for cat_label, cat_data in [("実オッズ↓(≤0.7x)", down), ("変化なし(0.85-1.15x)", same), ("実オッズ↑(≥1.5x)", up)]:
            n = len(cat_data)
            if n < 20:
                print(f"    {cat_label:<22} n={n} (サンプル不足)")
                continue
            wins = sum(1 for r in cat_data if r["is_win"])
            top3 = sum(1 for r in cat_data if r["is_top3"])
            win_return = sum(r["actual_odds"] for r in cat_data if r["is_win"])
            avg_odds = np.mean([r["actual_odds"] for r in cat_data])
            print(f"    {cat_label:<22} n={n:>5} 勝率{wins/n*100:>5.1f}% 複勝率{top3/n*100:>5.1f}% 単回収{win_return/n*100:>5.1f}% 平均実オッズ{avg_odds:>5.1f}")

    # ============================================
    # 分析4: モデル推奨馬 × オッズ変動
    # ============================================
    print(f"\n{'='*60}")
    print("分析4: モデル推奨馬(ARd≥55 & rank_p≤3) × オッズ変動")
    print(f"{'='*60}")

    model_picks = [r for r in records
                   if r["ar_deviation"] is not None
                   and r["ar_deviation"] >= 55
                   and r["rank_p"] is not None
                   and r["rank_p"] <= 3]

    print(f"\nモデル推奨馬: {len(model_picks)}件")

    if model_picks:
        move_bins_detail = [
            ("人気しすぎ(≤0.6x)", lambda r: r["odds_move"] <= 0.6),
            ("やや人気(0.6-0.85x)", lambda r: 0.6 < r["odds_move"] <= 0.85),
            ("想定通り(0.85-1.15x)", lambda r: 0.85 < r["odds_move"] <= 1.15),
            ("やや妙味(1.15-1.5x)", lambda r: 1.15 < r["odds_move"] <= 1.5),
            ("おいしい(>1.5x)", lambda r: r["odds_move"] > 1.5),
        ]

        print(f"\n{'カテゴリ':<22} {'件数':>6} {'勝率':>7} {'複勝率':>7} {'単回収':>7} {'平均EV':>7}")
        print("-" * 65)

        for label, cond in move_bins_detail:
            subset = [r for r in model_picks if cond(r)]
            n = len(subset)
            if n < 10:
                print(f"{label:<22} {n:>6}  (サンプル不足)")
                continue
            wins = sum(1 for r in subset if r["is_win"])
            top3 = sum(1 for r in subset if r["is_top3"])
            win_return = sum(r["actual_odds"] for r in subset if r["is_win"])
            avg_ev = np.mean([r["win_ev"] for r in subset if r["win_ev"] is not None]) if any(r["win_ev"] for r in subset) else 0
            print(f"{label:<22} {n:>6} {wins/n*100:>6.1f}% {top3/n*100:>6.1f}% {win_return/n*100:>6.1f}% {avg_ev:>6.2f}")

    # ============================================
    # 分析5: VB馬のオッズ変動別パフォーマンス
    # ============================================
    print(f"\n{'='*60}")
    print("分析5: 既存VB推奨馬 × オッズ変動")
    print(f"{'='*60}")

    vb_picks = [r for r in records if r["is_vb"]]
    print(f"VB推奨馬: {len(vb_picks)}件")

    if vb_picks:
        print(f"\n{'カテゴリ':<22} {'件数':>6} {'勝率':>7} {'複勝率':>7} {'単回収':>7}")
        print("-" * 55)
        for label, cond in move_bins_detail:
            subset = [r for r in vb_picks if cond(r)]
            n = len(subset)
            if n < 5:
                print(f"{label:<22} {n:>6}  (サンプル不足)")
                continue
            wins = sum(1 for r in subset if r["is_win"])
            top3 = sum(1 for r in subset if r["is_top3"])
            win_return = sum(r["actual_odds"] for r in subset if r["is_win"])
            print(f"{label:<22} {n:>6} {wins/n*100:>6.1f}% {top3/n*100:>6.1f}% {win_return/n*100:>6.1f}%")

    # ============================================
    # 分析6: 基準オッズ自体の精度
    # ============================================
    print(f"\n{'='*60}")
    print("分析6: 基準オッズの予測精度（参考）")
    print(f"{'='*60}")

    base_odds_bins = [
        ("1-3倍", 1, 3),
        ("3-5倍", 3, 5),
        ("5-10倍", 5, 10),
        ("10-20倍", 10, 20),
        ("20-50倍", 20, 50),
        ("50倍以上", 50, 9999),
    ]

    print(f"\n{'基準オッズ帯':<14} {'件数':>6} {'勝率':>7} {'期待勝率':>8} {'複勝率':>7}")
    print("-" * 50)
    for label, lo, hi in base_odds_bins:
        subset = [r for r in records if lo <= r["base_odds"] < hi]
        n = len(subset)
        if n < 50:
            continue
        wins = sum(1 for r in subset if r["is_win"])
        top3 = sum(1 for r in subset if r["is_top3"])
        expected = 1.0 / ((lo + hi) / 2) * 100 if hi < 9999 else 1.0 / 75 * 100
        print(f"{label:<14} {n:>6} {wins/n*100:>6.1f}% {expected:>7.1f}% {top3/n*100:>6.1f}%")


if __name__ == "__main__":
    print("基準オッズ vs 実オッズ vs モデル予測 バックテスト分析")
    print("=" * 60)

    print("\nKYI index loading...")
    kyi = load_kyi_index()
    print(f"  KYI entries: {len(kyi)}")

    print("Race data loading (2024-2025)...")
    races = load_races_with_results((2024, 2025))
    print(f"  Races with results: {len(races)}")

    print("Predictions loading...")
    pred_index = load_predictions_index((2024, 2025))
    print(f"  Predictions: {len(pred_index)} races")

    analyze(kyi, races, pred_index)
