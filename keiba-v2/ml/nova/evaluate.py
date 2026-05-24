#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""nova_emerging 評価: Sel_v3 型市場乖離フィルタ sweep + polaris との同戦略比較

backtest_cache.json (polaris 全予測) と nova model_p/w.txt を組み合わせて、
1勝クラス のみで polaris vs nova の戦略 sweep を出す。

戦略カタログ (rank_X Top1 を 100円単勝買い):
  baseline   : rank_X==1 全買い
  not_fav1   : rank_X==1 && odds_rank != 1
  not_top2   : rank_X==1 && odds_rank > 2 (== vb_gap >= 2)
  gap3       : rank_X==1 && vb_gap >= 3
  gap4       : rank_X==1 && vb_gap >= 4

X は --target p (rank_p) or w (rank_w)。

Usage:
    python -m ml.nova.evaluate --target p
    python -m ml.nova.evaluate --target w
    python -m ml.nova.evaluate --target both  # P と W 両方
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from pathlib import Path
from typing import Optional

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import lightgbm as lgb
import numpy as np
import pandas as pd

from core import config
from ml.experiment import (
    build_dataset,
    build_pit_personnel_timeline,
    load_data,
    parse_period_range,
)
from ml.features.baba_features import load_baba_index
from ml.utils.backtest_cache import load_backtest_cache


TARGET_GRADE = "1勝クラス"
SUB_MODEL = "emerging"
NOVA_DIR = config.ml_dir() / "nova" / SUB_MODEL

STRATEGY_TAGS = ["baseline", "not_fav1", "not_top2", "gap3", "gap4"]


def matches_strategy(odds_rank: Optional[int], vb_gap: Optional[float], tag: str) -> bool:
    if tag == "baseline":
        return True
    if tag == "not_fav1":
        return odds_rank is not None and int(odds_rank) != 1
    if tag == "not_top2":
        return odds_rank is not None and int(odds_rank) > 2
    if tag == "gap3":
        return vb_gap is not None and float(vb_gap) >= 3
    if tag == "gap4":
        return vb_gap is not None and float(vb_gap) >= 4
    return False


def summarize_strategy(df: pd.DataFrame) -> dict:
    """df は rank_X==1 でフィルタ済みの DataFrame"""
    n = len(df)
    if n == 0:
        return {"n": 0, "hits": 0, "hit_rate": 0.0, "roi": 0.0,
                "pnl": 0.0, "mean_hit_odds": 0.0}
    hits = int(df["is_win"].sum())
    cost = n * 100.0
    payout = float(df.loc[df["is_win"] == 1, "odds"].sum()) * 100.0
    pnl = payout - cost
    roi = (payout / cost * 100.0) if cost > 0 else 0.0
    hit_rate = (hits / n * 100.0) if n > 0 else 0.0
    mean_hit_odds = (
        float(df.loc[df["is_win"] == 1, "odds"].mean())
        if hits > 0 else 0.0
    )
    return {
        "n": n,
        "hits": hits,
        "hit_rate": round(hit_rate, 2),
        "roi": round(roi, 2),
        "pnl": round(pnl, 0),
        "mean_hit_odds": round(mean_hit_odds, 2),
    }


def build_test_dataset_only(args) -> pd.DataFrame:
    """Test 期間のみ build_dataset を実行 (5分程度)"""
    print("\n[Load] index 読込開始 ...")
    t0 = time.time()
    (history_cache, trainer_index, jockey_index,
     date_index, pace_index, kb_ext_index, training_summary_index,
     race_level_index, pedigree_index, sire_stats_index,
     jrdb_sed_index, jrdb_kyi_index, jrdb_kaa_index,
     jrdb_cyb_index, jrdb_cha_index, jrdb_kka_index, jrdb_joa_index) = load_data(
        sire_cutoff=args.sire_cutoff)
    pit_trainer_tl, pit_jockey_tl = build_pit_personnel_timeline()
    baba_index = load_baba_index()
    print(f"[Load] 完了 ({time.time() - t0:.0f}s)")

    test_min, test_min_m, test_max, test_max_m = parse_period_range(args.test_years)
    print("\n[Build] Building Test split (1勝クラス除外せずに全部 build)...")
    df_test = build_dataset(
        date_index, history_cache, trainer_index, jockey_index, pace_index,
        kb_ext_index, test_min, test_max,
        use_db_odds=not args.no_db,
        training_summary_index=training_summary_index,
        race_level_index=race_level_index,
        pedigree_index=pedigree_index,
        sire_stats_index=sire_stats_index,
        min_month=test_min_m, max_month=test_max_m,
        pit_trainer_tl=pit_trainer_tl, pit_jockey_tl=pit_jockey_tl,
        baba_index=baba_index,
        jrdb_sed_index=jrdb_sed_index,
        jrdb_kyi_index=jrdb_kyi_index,
        jrdb_kaa_index=jrdb_kaa_index,
        jrdb_cyb_index=jrdb_cyb_index,
        jrdb_cha_index=jrdb_cha_index,
        jrdb_kka_index=jrdb_kka_index,
        jrdb_joa_index=jrdb_joa_index,
    )
    return df_test


def predict_nova(df_test: pd.DataFrame, target: str) -> pd.DataFrame:
    """nova model で pred_proba を計算"""
    meta_path = NOVA_DIR / f"model_meta_{target}.json"
    model_path = NOVA_DIR / f"model_{target}.txt"
    if not meta_path.exists() or not model_path.exists():
        raise FileNotFoundError(
            f"nova model not found: {model_path} / {meta_path}\n"
            f"先に python -m ml.nova.train_emerging --target {target} を実行してください")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    # 旧版 meta は "features_p" / "features_w" キーだったので fallback
    features = meta.get("features") or meta.get("features_p") or meta.get("features_w")
    if not features:
        raise KeyError(f"'features' not found in {meta_path}")
    missing = [f for f in features if f not in df_test.columns]
    if missing:
        print(f"  WARNING: {len(missing)} features missing in test data, filling NaN")
        for f in missing:
            df_test[f] = np.nan
    model = lgb.Booster(model_file=str(model_path))
    preds = model.predict(df_test[features])
    df_test[f"pred_proba_{target}_nova"] = preds
    df_test[f"rank_{target}_nova"] = (
        df_test.groupby("race_id")[f"pred_proba_{target}_nova"]
        .rank(ascending=False, method="first").astype(int)
    )
    print(f"[Predict] nova_{target}: {len(df_test):,} entries predicted")
    return df_test


def flatten_polaris_cache(races: list) -> pd.DataFrame:
    """backtest_cache の races を馬単位 DataFrame に展開"""
    rows = []
    for r in races:
        rid = str(r["race_id"])
        grade = r.get("grade", "")
        for e in r.get("entries", []):
            rows.append({
                "race_id": rid,
                "grade_cache": grade,
                "umaban": int(e.get("umaban", 0)),
                "odds_cache": e.get("odds"),
                "vb_gap_cache": e.get("vb_gap"),
                "odds_rank_cache": e.get("odds_rank"),
                "rank_p_polaris": e.get("rank_p"),
                "rank_w_polaris": e.get("rank_w"),
                "pred_proba_p_raw_polaris": e.get("pred_proba_p_raw"),
                "is_win_cache": e.get("is_win"),
                "is_top3_cache": e.get("is_top3"),
                "finish_position_cache": e.get("finish_position"),
            })
    return pd.DataFrame(rows)


def evaluate_target(df: pd.DataFrame, target: str, model_label: str) -> dict:
    """1モデル × 全戦略を集計"""
    # rank_X == 1 でフィルタ
    rank_col = f"rank_{target}_{model_label.lower()}"
    if rank_col not in df.columns:
        return None
    top1 = df[df[rank_col] == 1].copy()
    if len(top1) == 0:
        return None

    out = {}
    for tag in STRATEGY_TAGS:
        mask = top1.apply(
            lambda row: matches_strategy(
                row.get("odds_rank"), row.get("vb_gap"), tag),
            axis=1,
        )
        df_strat = top1[mask]
        out[tag] = summarize_strategy(df_strat)
    return out


def print_comparison(polaris_summary: dict, nova_summary: dict,
                     target: str, model_label: str = "polaris") -> None:
    print(f"\n  -- rank_{target} Top1 戦略 sweep ({model_label} vs nova) --")
    print(f"  {'Strategy':<12} {'bets_pol':>9} {'roi_pol%':>9} "
          f"{'hit_pol%':>9} {'odds_pol':>9} {'bets_nova':>10} {'roi_nova%':>10} "
          f"{'hit_nova%':>10} {'odds_nova':>10} {'diff_roi':>10}")
    print("  " + "-" * 110)
    for tag in STRATEGY_TAGS:
        p = polaris_summary.get(tag, {}) if polaris_summary else {}
        n = nova_summary.get(tag, {}) if nova_summary else {}
        if not p and not n:
            continue
        p_bets = p.get("n", 0)
        n_bets = n.get("n", 0)
        p_roi = p.get("roi", 0.0)
        n_roi = n.get("roi", 0.0)
        diff = n_roi - p_roi if (p_bets and n_bets) else 0.0
        print(f"  {tag:<12} {p_bets:>9,} {p_roi:>8.1f}% "
              f"{p.get('hit_rate', 0):>8.1f}% {p.get('mean_hit_odds', 0):>9.2f} "
              f"{n_bets:>10,} {n_roi:>9.1f}% "
              f"{n.get('hit_rate', 0):>9.1f}% {n.get('mean_hit_odds', 0):>10.2f} "
              f"{diff:>+9.1f}pt")


def main():
    p = argparse.ArgumentParser(description="nova_emerging Sel_v3 sweep evaluator")
    p.add_argument("--target", default="both", choices=["p", "w", "both"])
    p.add_argument("--test-years", default="2025.05-2026.03")
    p.add_argument("--no-db", action="store_true")
    p.add_argument("--sire-cutoff", default="2025-04-30")
    p.add_argument("--cache-suffix", default=None,
                   help="backtest_cache_{suffix}.json (default: backtest_cache.json)")
    p.add_argument("--save", action="store_true",
                   help="集計を data3/analysis/nova_emerging_eval/ に保存")
    args = p.parse_args()

    print("=" * 78)
    print(f"  nova_emerging 戦略 sweep  (target: {args.target}, grade: {TARGET_GRADE})")
    print(f"  test_years: {args.test_years}")
    print("=" * 78)

    # === backtest_cache 読込 (polaris 予測) ===
    races = load_backtest_cache(suffix=args.cache_suffix)
    df_cache = flatten_polaris_cache(races)
    print(f"[Cache] flattened: {len(df_cache):,} entries from {df_cache['race_id'].nunique():,} races")

    # === Test build_dataset (nova の特徴量計算用) ===
    df_test = build_test_dataset_only(args)
    df_test["race_id"] = df_test["race_id"].astype(str)
    df_test["umaban"] = df_test["umaban"].astype(int)

    # === nova predict ===
    targets = ["p", "w"] if args.target == "both" else [args.target]
    for t in targets:
        df_test = predict_nova(df_test, t)

    # === Join cache + nova preds ===
    df = df_test.merge(df_cache, on=["race_id", "umaban"], how="inner")
    print(f"\n[Join] merged: {len(df):,} entries")

    # === 1勝クラス フィルタ ===
    # grade は cache 側にもあるが、 df_test 側 (build_dataset 出力) の grade を信頼
    df_one = df[df["grade"] == TARGET_GRADE].copy()
    print(f"[Filter] grade='{TARGET_GRADE}': {len(df_one):,} entries / "
          f"{df_one['race_id'].nunique():,} races")

    # === 集計 ===
    summaries = {}
    for t in targets:
        # polaris の rank も _polaris suffix で揃える
        polaris_col = f"rank_{t}_polaris"
        nova_col = f"rank_{t}_nova"
        # polaris rank が文字列の場合があるので数値化
        df_one[polaris_col] = pd.to_numeric(df_one[polaris_col], errors="coerce")
        # is_win / odds の null 行を除外 (確定済みのみ)
        df_eval = df_one.dropna(subset=["is_win", "odds"]).copy()
        df_eval["is_win"] = df_eval["is_win"].astype(int)
        df_eval["odds"] = df_eval["odds"].astype(float)

        # polaris 集計用 view
        df_pol = df_eval.copy()
        df_pol[f"rank_{t}_polaris_view"] = df_pol[polaris_col]
        # nova の rank と独立に各々 Top1 取る → 別の馬になりうる
        polaris_summary = {}
        nova_summary = {}
        for tag in STRATEGY_TAGS:
            # polaris
            top1_pol = df_eval[df_eval[polaris_col] == 1]
            mask_pol = top1_pol.apply(
                lambda row: matches_strategy(
                    row.get("odds_rank"), row.get("vb_gap"), tag),
                axis=1,
            )
            polaris_summary[tag] = summarize_strategy(top1_pol[mask_pol])
            # nova
            top1_nova = df_eval[df_eval[nova_col] == 1]
            mask_nova = top1_nova.apply(
                lambda row: matches_strategy(
                    row.get("odds_rank"), row.get("vb_gap"), tag),
                axis=1,
            )
            nova_summary[tag] = summarize_strategy(top1_nova[mask_nova])

        print_comparison(polaris_summary, nova_summary, t, "polaris")
        summaries[t] = {
            "polaris": polaris_summary,
            "nova": nova_summary,
        }

        # === Concur フィルタ (polaris Top1 == nova Top1) ===
        concur_top1 = df_eval[
            (df_eval[polaris_col] == 1) & (df_eval[nova_col] == 1)
        ].copy()
        if len(concur_top1) > 0:
            concur_sum = {}
            for tag in STRATEGY_TAGS:
                mask = concur_top1.apply(
                    lambda row: matches_strategy(
                        row.get("odds_rank"), row.get("vb_gap"), tag),
                    axis=1,
                )
                concur_sum[tag] = summarize_strategy(concur_top1[mask])
            print(f"\n  -- rank_{t} Concur (polaris==nova) 戦略 sweep --")
            print(f"  {'Strategy':<12} {'bets':>6} {'hits':>5} "
                  f"{'hit%':>6} {'ROI%':>7} {'P&L':>9} {'odds':>7}")
            for tag in STRATEGY_TAGS:
                s = concur_sum[tag]
                print(f"  {tag:<12} {s['n']:>6} {s['hits']:>5} "
                      f"{s['hit_rate']:>5.1f}% {s['roi']:>6.1f}% "
                      f"{s['pnl']:>+9,.0f} {s['mean_hit_odds']:>7.2f}")
            summaries[t]["concur"] = concur_sum

    if args.save:
        out_dir = config.data_root() / "analysis" / "nova_emerging_eval"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "strategy_sweep.json"
        out_path.write_text(
            json.dumps(summaries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n[Save] {out_path}")

    print("\n[Done]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
