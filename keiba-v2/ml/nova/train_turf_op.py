#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""nova_turf_op: 芝オープンクラス以上 特化モデル (Session 177 Phase 0)

polaris と同じ FEATURE_COLS_ALL / PARAMS_{P,W} を使い、学習データを
「track_type==turf AND grade in {OP, Listed, G1, G2, G3}」に絞って再学習する。

検証仮説 (ふくだ S177):
  芝OP+ は未勝利/条件と違い、出走馬の過去走実績データが豊富 →
  特徴量をより有効活用でき、特徴量重要度の構成が変わるはず。
  クラス特化で学習すると polaris(汎用) より top1 精度 / 較正が改善するか?
  (nova_emerging で試したのは低クラス[1勝/新馬=データ希薄]のみ。
   高クラスは未検証。S173: OP市場はシャープなので ROI エッジは出にくい想定
   = 価値は予想品質/本命精度/較正であって払戻エッジではない、を確認する)

Usage:
    python -m ml.nova.train_turf_op --target p --dry-run   # サンプル数 + track_type encoding 確認
    python -m ml.nova.train_turf_op --target p
    python -m ml.nova.train_turf_op --target w

Output:
    data3/ml/nova/turf_op/model_{p,w}.txt
    data3/ml/nova/turf_op/model_meta_{p,w}.json
    data3/ml/nova/turf_op/training_report_{p,w}.json
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import pandas as pd

from core import config
from ml.experiment import (
    FEATURE_COLS_ALL,
    PARAMS_P,
    PARAMS_W,
    P_ONLY_FEATURES,
    MARKET_FEATURES,
    build_dataset,
    build_pit_personnel_timeline,
    load_data,
    parse_period_range,
    train_model,
)
from ml.features.baba_features import load_baba_index


SUB_MODEL = "turf_op"
OP_GRADES = {"OP", "Listed", "G1", "G2", "G3"}


def _turf_mask(df: pd.DataFrame) -> pd.Series:
    """track_type 列が数値エンコード(0=turf,1=dirt)でも文字列('turf')でも芝を判定。"""
    tt = df["track_type"]
    if tt.dtype == object:
        s = tt.astype(str)
        return s.isin(["turf", "芝"])
    # numeric encoding: 0 = turf (experiment.py base_features track_map)
    return tt == 0


def filter_turf_op(df: pd.DataFrame, split: str) -> pd.DataFrame:
    """芝 × OP以上(OP/Listed/G1-3) のみ抽出。"""
    n_before = len(df)
    races_before = df["race_id"].nunique() if n_before else 0
    mask = _turf_mask(df) & df["grade"].isin(OP_GRADES)
    df_filt = df[mask].copy()
    n_after = len(df_filt)
    races_after = df_filt["race_id"].nunique() if n_after else 0
    print(f"  [{split}] turf & grade in {sorted(OP_GRADES)}: "
          f"{n_before:,} → {n_after:,} entries  "
          f"({races_before:,} → {races_after:,} races)")
    return df_filt


def build_three_splits(args, common):
    train_min, train_min_m, train_max, train_max_m = parse_period_range(args.train_years)
    val_min, val_min_m, val_max, val_max_m = parse_period_range(args.val_years)
    test_min, test_min_m, test_max, test_max_m = parse_period_range(args.test_years)

    if args.dry_run:
        print("\n[Dry-run] Building Test split only ...")
        df_test = build_dataset(min_year=test_min, max_year=test_max,
                                min_month=test_min_m, max_month=test_max_m, **common)
        return None, None, df_test

    print("\n[Build] Building Train split ...")
    df_train = build_dataset(min_year=train_min, max_year=train_max,
                             min_month=train_min_m, max_month=train_max_m, **common)
    print("\n[Build] Building Val split ...")
    df_val = build_dataset(min_year=val_min, max_year=val_max,
                           min_month=val_min_m, max_month=val_max_m, **common)
    print("\n[Build] Building Test split ...")
    df_test = build_dataset(min_year=test_min, max_year=test_max,
                            min_month=test_min_m, max_month=test_max_m, **common)
    return df_train, df_val, df_test


def evaluate_top1_roi(df_test: pd.DataFrame, pred_col: str) -> dict:
    if pred_col not in df_test.columns or len(df_test) == 0:
        return {"n": 0, "hits": 0, "hit_rate": 0.0, "roi": 0.0, "pnl": 0.0}
    df = df_test.copy()
    df["pred_rank"] = df.groupby("race_id")[pred_col].rank(ascending=False, method="first")
    top1 = df[df["pred_rank"] == 1].copy()
    n = len(top1)
    hits = int(top1["is_win"].sum())
    cost = n * 100.0
    payout = float(top1.loc[top1["is_win"] == 1, "odds"].sum()) * 100.0
    pnl = payout - cost
    roi = (payout / cost * 100.0) if cost > 0 else 0.0
    hit_rate = (hits / n * 100.0) if n > 0 else 0.0
    mean_hit_odds = (float(top1.loc[top1["is_win"] == 1, "odds"].mean()) if hits > 0 else 0.0)
    place_hits = int(top1["is_top3"].sum())
    place_rate = (place_hits / n * 100.0) if n > 0 else 0.0
    return {
        "n": n, "hits": hits, "hit_rate": round(hit_rate, 2),
        "place_hits": place_hits, "place_rate": round(place_rate, 2),
        "cost": round(cost, 0), "payout": round(payout, 0), "pnl": round(pnl, 0),
        "roi": round(roi, 2), "mean_hit_odds": round(mean_hit_odds, 2),
    }


def build_feature_set(target: str = "p") -> list:
    base = [f for f in FEATURE_COLS_ALL if f not in MARKET_FEATURES]
    if target == "w":
        base = [f for f in base if f not in P_ONLY_FEATURES]
    return base


def train_one(target, variant, df_tr, df_va, df_te, args, out_dir, t0):
    """1 (target, variant) を学習・評価・保存。

    variant: 'gen' = 汎用(全データ学習) / 'spec' = 芝OP+特化(絞り学習)。
    df_te は両 variant とも芝OP+ test (df_test_e) を渡す → 同一 test 行で apples-to-apples。
    汎用は val も全データを渡す(isotonic を全体で fit)→芝OP+ に適用。
    """
    label_col = "is_top3" if target == "p" else "is_win"
    params = PARAMS_P if target == "p" else PARAMS_W
    model_tag = f"{variant}_{target.upper()}"

    features = build_feature_set(target)
    features = [f for f in features if f in df_tr.columns]
    print(f"\n[Train:{model_tag}] features={len(features)}, "
          f"train={len(df_tr):,} val={len(df_va):,} test={len(df_te):,}, label={label_col}")

    model, metrics, importance, pred_cal, calibrator, pred_raw = train_model(
        df_tr, df_va, df_te,
        feature_cols=features, params=params, label_col=label_col,
        model_name=f"nova_turf_op_{model_tag}", num_boost_round=args.num_boost_round,
    )

    df_eval = df_te.copy()
    pred_col = f"pred_{target}_{variant}"
    df_eval[pred_col] = pred_cal
    roi_summary = evaluate_top1_roi(df_eval, pred_col)

    print(f"  [{model_tag}] 芝OP+ rank Top1 単勝: bets={roi_summary['n']:,} "
          f"hits={roi_summary['hits']} hit_rate={roi_summary['hit_rate']}% "
          f"ROI={roi_summary['roi']}% mean_hit_odds={roi_summary['mean_hit_odds']}  "
          f"| AUC={metrics['auc']} ECE(cal)={metrics['ece_calibrated']} Brier(cal)={metrics['brier_calibrated']}")

    model.save_model(str(out_dir / f"model_{variant}_{target}.txt"))
    report = {
        "target": target, "variant": variant, "test_period": args.test_years,
        "n_train": int(len(df_tr)), "n_test": int(len(df_te)),
        "n_test_races": int(df_te["race_id"].nunique()),
        "roi_summary": roi_summary, "metrics": metrics,
        "importance": dict(sorted(importance.items(), key=lambda x: -x[1])),
        "sire_cutoff": args.sire_cutoff,
    }
    (out_dir / f"training_report_{variant}_{target}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [Save] model_{variant}_{target}.txt + training_report_{variant}_{target}.json")
    return roi_summary, metrics


def main():
    p = argparse.ArgumentParser(description="nova_turf_op 学習 (芝OP+特化)")
    p.add_argument("--train-years", default="2020-2025.03")
    p.add_argument("--val-years", default="2025.04")
    p.add_argument("--test-years", default="2025.05-2026.05")
    p.add_argument("--version", default="0.1")
    p.add_argument("--target", default="both", choices=["p", "w", "both"])
    p.add_argument("--num-boost-round", type=int, default=1500)
    p.add_argument("--no-db", action="store_true")
    p.add_argument("--sire-cutoff", default="2025-03-31")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    targets = ["p", "w"] if args.target == "both" else [args.target]
    print("=" * 70)
    print(f"  nova_turf_op 学習  (芝 × OP以上)  targets={targets}")
    print(f"  version: {args.version}")
    print(f"  train={args.train_years}, val={args.val_years}, test={args.test_years}")
    print(f"  sire_cutoff={args.sire_cutoff}, dry_run={args.dry_run}")
    print("=" * 70)

    t0 = time.time()
    print("\n[Load] index 読込開始 ...")
    (history_cache, trainer_index, jockey_index,
     date_index, pace_index, kb_ext_index, training_summary_index,
     race_level_index, pedigree_index, sire_stats_index,
     jrdb_sed_index, jrdb_kyi_index, jrdb_kaa_index,
     jrdb_cyb_index, jrdb_cha_index, jrdb_kka_index, jrdb_joa_index) = load_data(
        sire_cutoff=args.sire_cutoff)
    pit_trainer_tl, pit_jockey_tl = build_pit_personnel_timeline()
    baba_index = load_baba_index()
    print(f"[Load] Baba index: {len(baba_index):,} races")
    print(f"[Load] 完了 ({time.time() - t0:.0f}s)")

    common = dict(
        date_index=date_index, history_cache=history_cache,
        trainer_index=trainer_index, jockey_index=jockey_index,
        pace_index=pace_index, kb_ext_index=kb_ext_index,
        use_db_odds=not args.no_db,
        training_summary_index=training_summary_index,
        race_level_index=race_level_index, pedigree_index=pedigree_index,
        sire_stats_index=sire_stats_index,
        pit_trainer_tl=pit_trainer_tl, pit_jockey_tl=pit_jockey_tl,
        baba_index=baba_index,
        jrdb_sed_index=jrdb_sed_index, jrdb_kyi_index=jrdb_kyi_index,
        jrdb_kaa_index=jrdb_kaa_index, jrdb_cyb_index=jrdb_cyb_index,
        jrdb_cha_index=jrdb_cha_index, jrdb_kka_index=jrdb_kka_index,
        jrdb_joa_index=jrdb_joa_index,
    )

    df_train, df_val, df_test = build_three_splits(args, common)

    # === track_type encoding 確認 (dry-run 時に必ず表示) ===
    if args.dry_run:
        print("\n[Probe] df_test track_type dtype:", df_test["track_type"].dtype)
        print("[Probe] track_type value_counts:",
              df_test["track_type"].value_counts(dropna=False).to_dict())
        print("[Probe] grade value_counts:",
              df_test["grade"].value_counts(dropna=False).to_dict())

    print(f"\n[Filter] 芝 × OP以上 のみ抽出:")
    if df_train is not None:
        df_train_e = filter_turf_op(df_train, "Train")
        df_val_e = filter_turf_op(df_val, "Val")
    df_test_e = filter_turf_op(df_test, "Test")

    if args.dry_run:
        print("\n[Dry-run] 完了。 サンプル数のみ報告。")
        print(f"  Test 芝OP+: {len(df_test_e):,} entries / "
              f"{df_test_e['race_id'].nunique():,} races")
        if len(df_test_e):
            df_test_e = df_test_e.copy()
            df_test_e["year_month"] = df_test_e["race_id"].str[:6]
            monthly = df_test_e.groupby("year_month").agg(
                n_entries=("race_id", "size"), n_races=("race_id", "nunique")).reset_index()
            print("  月別 Test 芝OP+:")
            print(monthly.to_string(index=False))
            print("  grade 内訳:", df_test_e["grade"].value_counts().to_dict())
        return 0

    if len(df_train_e) < 1000 or len(df_val_e) < 100 or len(df_test_e) < 100:
        print("\n  ERROR: サンプル数が学習に不十分:")
        print(f"  Train={len(df_train_e)}, Val={len(df_val_e)}, Test={len(df_test_e)}")
        return 1

    out_dir = config.ml_dir() / "nova" / SUB_MODEL
    out_dir.mkdir(parents=True, exist_ok=True)
    # apples-to-apples: 同一特徴量/期間/cutoff で 汎用(全データ) と 特化(芝OP+) を学習し、
    # 両方とも芝OP+ test(df_test_e) で評価する。
    for tgt in targets:
        print("\n" + "#" * 70)
        print(f"#  target={tgt.upper()}  ::  GEN(全データ) vs SPEC(芝OP+)  ::  eval on 芝OP+")
        print("#" * 70)
        train_one(tgt, "gen", df_train, df_val, df_test_e, args, out_dir, t0)
        train_one(tgt, "spec", df_train_e, df_val_e, df_test_e, args, out_dir, t0)

    print(f"\n[Done] Total {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
