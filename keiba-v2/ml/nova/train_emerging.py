#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""nova_emerging: 1勝クラス特化 Place モデル (Phase 1 Pilot)

polaris 2.0 と同じ FEATURE_COLS_ALL / PARAMS_P を使い、
学習データを「grade == '1勝クラス'」 に絞って再学習する。

検証仮説:
  polaris 2.0 は 1勝クラスで rank_p==1 ROI 82.6% と赤字 (polaris_segments)。
  クラスを絞れば模型が「同じクラス内の相対評価」 に集中して
  ROI 改善するか? 失敗するなら原因 (サンプル不足 / 市場との同調) を明確化する。

Usage:
    python -m ml.nova.train_emerging --version 0.1
    python -m ml.nova.train_emerging --version 0.1 --dry-run  # Test サンプル数だけ確認
    python -m ml.nova.train_emerging --version 0.1 --train-years 2020-2025.03

Output:
    data3/ml/nova/emerging/model_p.txt
    data3/ml/nova/emerging/model_meta.json
    data3/ml/nova/emerging/training_report.json
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


TARGET_GRADE = "1勝クラス"
SUB_MODEL = "emerging"


def filter_emerging(df: pd.DataFrame, split: str) -> pd.DataFrame:
    """1勝クラスのみ抽出。 警告: grade が空文字 / NaN だと取りこぼし"""
    n_before = len(df)
    races_before = df["race_id"].nunique() if n_before else 0
    df_filt = df[df["grade"] == TARGET_GRADE].copy()
    n_after = len(df_filt)
    races_after = df_filt["race_id"].nunique() if n_after else 0
    print(f"  [{split}] grade='{TARGET_GRADE}' filter: "
          f"{n_before:,} → {n_after:,} entries  "
          f"({races_before:,} → {races_after:,} races)")
    return df_filt


def build_three_splits(
    args,
    history_cache, trainer_index, jockey_index,
    date_index, pace_index, kb_ext_index, training_summary_index,
    race_level_index, pedigree_index, sire_stats_index,
    jrdb_sed_index, jrdb_kyi_index, jrdb_kaa_index,
    jrdb_cyb_index, jrdb_cha_index, jrdb_kka_index, jrdb_joa_index,
    pit_trainer_tl, pit_jockey_tl, baba_index,
):
    """train/val/test の DataFrame を返す (dry-run 時は test だけ)"""
    train_min, train_min_m, train_max, train_max_m = parse_period_range(args.train_years)
    val_min, val_min_m, val_max, val_max_m = parse_period_range(args.val_years)
    test_min, test_min_m, test_max, test_max_m = parse_period_range(args.test_years)

    common = dict(
        date_index=date_index,
        history_cache=history_cache,
        trainer_index=trainer_index,
        jockey_index=jockey_index,
        pace_index=pace_index,
        kb_ext_index=kb_ext_index,
        use_db_odds=not args.no_db,
        training_summary_index=training_summary_index,
        race_level_index=race_level_index,
        pedigree_index=pedigree_index,
        sire_stats_index=sire_stats_index,
        pit_trainer_tl=pit_trainer_tl,
        pit_jockey_tl=pit_jockey_tl,
        baba_index=baba_index,
        jrdb_sed_index=jrdb_sed_index,
        jrdb_kyi_index=jrdb_kyi_index,
        jrdb_kaa_index=jrdb_kaa_index,
        jrdb_cyb_index=jrdb_cyb_index,
        jrdb_cha_index=jrdb_cha_index,
        jrdb_kka_index=jrdb_kka_index,
        jrdb_joa_index=jrdb_joa_index,
    )

    if args.dry_run:
        print("\n[Dry-run] Building Test split only ...")
        df_test = build_dataset(
            min_year=test_min, max_year=test_max,
            min_month=test_min_m, max_month=test_max_m,
            **common,
        )
        return None, None, df_test

    print("\n[Build] Building Train split ...")
    df_train = build_dataset(
        min_year=train_min, max_year=train_max,
        min_month=train_min_m, max_month=train_max_m,
        **common,
    )
    print("\n[Build] Building Val split ...")
    df_val = build_dataset(
        min_year=val_min, max_year=val_max,
        min_month=val_min_m, max_month=val_max_m,
        **common,
    )
    print("\n[Build] Building Test split ...")
    df_test = build_dataset(
        min_year=test_min, max_year=test_max,
        min_month=test_min_m, max_month=test_max_m,
        **common,
    )
    return df_train, df_val, df_test


def evaluate_top1_roi(df_test: pd.DataFrame, pred_col: str) -> dict:
    """rank_p Top1 単勝 ROI 集計 (polaris と同じ評価)"""
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
    mean_hit_odds = (
        float(top1.loc[top1["is_win"] == 1, "odds"].mean())
        if hits > 0 else 0.0
    )

    # 複勝 (is_top3 == 1) ROI も参考に
    place_hits = int(top1["is_top3"].sum())
    place_rate = (place_hits / n * 100.0) if n > 0 else 0.0

    return {
        "n": n,
        "hits": hits,
        "hit_rate": round(hit_rate, 2),
        "place_hits": place_hits,
        "place_rate": round(place_rate, 2),
        "cost": round(cost, 0),
        "payout": round(payout, 0),
        "pnl": round(pnl, 0),
        "roi": round(roi, 2),
        "mean_hit_odds": round(mean_hit_odds, 2),
    }


def build_feature_set(target: str = "p") -> list:
    """polaris の features と同等。 P は P_ONLY 含む、 W は除外。"""
    base = [f for f in FEATURE_COLS_ALL if f not in MARKET_FEATURES]
    if target == "w":
        base = [f for f in base if f not in P_ONLY_FEATURES]
    return base


def load_polaris_baseline(target: str) -> dict:
    """polaris_segments JSON から 1勝クラス baseline を取得 (失敗時は None)"""
    sub = "polaris_2.0_v1" if target == "p" else "polaris_2.0_w_v1"
    path = (config.data_root() / "analysis" / "polaris_segments"
            / sub / "segments.json")
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        seg = json.load(f)
    grade_axes = seg.get("axes", {}).get("grade", {})
    one_win = grade_axes.get(TARGET_GRADE, {})
    win_roi = one_win.get("win_roi", {})
    if not win_roi:
        return None
    return {
        "n": win_roi.get("n", 0),
        "hit_rate": round(win_roi.get("hit_rate", 0.0), 2),
        "roi": round(win_roi.get("roi", 0.0), 2),
        "mean_hit_odds": round(win_roi.get("mean_hit_odds", 0.0), 2),
        "source": str(path),
    }


def main():
    p = argparse.ArgumentParser(description="nova_emerging Pilot 学習")
    p.add_argument("--train-years", default="2020-2025.03")
    p.add_argument("--val-years", default="2025.04")
    p.add_argument("--test-years", default="2025.05-2026.03")
    p.add_argument("--version", default="0.1",
                   help="nova_emerging バージョン (model_meta に記録)")
    p.add_argument("--target", default="p", choices=["p", "w"],
                   help="学習ターゲット (p=is_top3 Place / w=is_win Win)")
    p.add_argument("--num-boost-round", type=int, default=1500)
    p.add_argument("--no-db", action="store_true", help="DB オッズ未使用")
    p.add_argument("--sire-cutoff", default="2025-04-30",
                   help="血統統計カットオフ (テスト期間リーク防止)")
    p.add_argument("--dry-run", action="store_true",
                   help="Test 期間だけ build し 1勝クラス サンプル数を表示して終了")
    args = p.parse_args()

    # === target 別 config ===
    if args.target == "p":
        label_col = "is_top3"
        params = PARAMS_P
        model_tag = "P"
        model_filename = "model_p.txt"
    else:  # w
        label_col = "is_win"
        params = PARAMS_W
        model_tag = "W"
        model_filename = "model_w.txt"

    print("=" * 70)
    print(f"  nova_emerging Pilot 学習  (target grade: {TARGET_GRADE}, target_label: {label_col})")
    print(f"  version: {args.version}  model: {model_filename}")
    print(f"  train={args.train_years}, val={args.val_years}, test={args.test_years}")
    print(f"  sire_cutoff={args.sire_cutoff}, dry_run={args.dry_run}")
    print("=" * 70)

    t0 = time.time()

    # === データロード ===
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

    # === データセット構築 ===
    df_train, df_val, df_test = build_three_splits(
        args,
        history_cache, trainer_index, jockey_index,
        date_index, pace_index, kb_ext_index, training_summary_index,
        race_level_index, pedigree_index, sire_stats_index,
        jrdb_sed_index, jrdb_kyi_index, jrdb_kaa_index,
        jrdb_cyb_index, jrdb_cha_index, jrdb_kka_index, jrdb_joa_index,
        pit_trainer_tl, pit_jockey_tl, baba_index,
    )

    # === 1勝クラス filter ===
    print(f"\n[Filter] grade='{TARGET_GRADE}' のみ抽出:")
    if df_train is not None:
        df_train_e = filter_emerging(df_train, "Train")
        df_val_e = filter_emerging(df_val, "Val")
    df_test_e = filter_emerging(df_test, "Test")

    if args.dry_run:
        print("\n[Dry-run] 完了。 サンプル数のみ報告。")
        print(f"  Test 1勝クラス: {len(df_test_e):,} entries / "
              f"{df_test_e['race_id'].nunique():,} races")
        # 月次内訳
        df_test_e["year_month"] = df_test_e["race_id"].str[:6]
        monthly = df_test_e.groupby("year_month").agg(
            n_entries=("race_id", "size"),
            n_races=("race_id", "nunique"),
        ).reset_index()
        print("  月別 Test 1勝クラス:")
        print(monthly.to_string(index=False))
        return 0

    if len(df_train_e) < 1000 or len(df_val_e) < 100 or len(df_test_e) < 100:
        print("\n  ERROR: サンプル数が学習に不十分:")
        print(f"  Train={len(df_train_e)}, Val={len(df_val_e)}, Test={len(df_test_e)}")
        return 1

    # === LightGBM 学習 ===
    features = build_feature_set(args.target)
    features = [f for f in features if f in df_train_e.columns]
    print(f"\n[Train] features={len(features)}, "
          f"num_boost_round={args.num_boost_round}, target_label={label_col}")

    model, metrics, importance, pred_cal, calibrator, pred_raw = train_model(
        df_train_e, df_val_e, df_test_e,
        feature_cols=features,
        params=params,
        label_col=label_col,
        model_name=f"nova_emerging_{model_tag}",
        num_boost_round=args.num_boost_round,
    )

    # === Test 評価: rank Top1 単勝 ROI ===
    df_eval = df_test_e.copy()
    pred_col = f"pred_proba_{args.target}_nova"
    df_eval[pred_col] = pred_cal
    df_eval[f"{pred_col}_raw"] = pred_raw
    roi_summary = evaluate_top1_roi(df_eval, pred_col)

    polaris_baseline = load_polaris_baseline(args.target)

    print("\n" + "=" * 70)
    print(f"  Test 評価 (1勝クラスのみ, target={args.target})")
    print("=" * 70)
    print(f"  rank_{args.target} Top1 単勝:  bets={roi_summary['n']:,}  "
          f"hits={roi_summary['hits']}  "
          f"hit_rate={roi_summary['hit_rate']}%  "
          f"ROI={roi_summary['roi']}%  "
          f"P&L={roi_summary['pnl']:+,.0f}")
    print(f"                       place_hits={roi_summary['place_hits']}  "
          f"place_rate={roi_summary['place_rate']}%  "
          f"mean_hit_odds={roi_summary['mean_hit_odds']}")

    if polaris_baseline:
        print(f"\n  polaris 2.0 {model_tag} baseline (1勝クラス):  "
              f"bets={polaris_baseline['n']}  ROI=+{polaris_baseline['roi']}%  "
              f"hit_rate={polaris_baseline['hit_rate']}%  "
              f"mean_hit_odds={polaris_baseline['mean_hit_odds']}")
        diff_roi = roi_summary["roi"] - polaris_baseline["roi"]
        diff_hit = roi_summary["hit_rate"] - polaris_baseline["hit_rate"]
        verdict = ("🟢 polaris 上回り" if diff_roi >= 10
                   else "🟡 同程度 (±10pt)" if abs(diff_roi) < 10
                   else "🔴 polaris 下回り")
        print(f"\n  nova - polaris:  ROI {diff_roi:+.1f}pt  "
              f"hit_rate {diff_hit:+.1f}pt  → {verdict}")
    else:
        print(f"\n  polaris 2.0 {model_tag} baseline: 見つからず (skip)")
        diff_roi, diff_hit, verdict = 0.0, 0.0, "N/A"

    # === 保存 ===
    out_dir = config.ml_dir() / "nova" / SUB_MODEL
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / model_filename
    model.save_model(str(model_path))
    print(f"\n[Save] {model_path}")

    meta = {
        "sub_model": SUB_MODEL,
        "target_grade": TARGET_GRADE,
        "target_label": label_col,
        "model_tag": model_tag,
        "version": args.version,
        "trained_at": datetime.now().isoformat(timespec="seconds"),
        "train_period": args.train_years,
        "val_period": args.val_years,
        "test_period": args.test_years,
        "sire_cutoff": args.sire_cutoff,
        "features": features,
        "num_features": len(features),
        "n_train": int(len(df_train_e)),
        "n_val": int(len(df_val_e)),
        "n_test": int(len(df_test_e)),
        "n_test_races": int(df_test_e["race_id"].nunique()),
        "metrics": metrics,
        "params": params,
        "elapsed_sec": int(time.time() - t0),
    }
    meta_path = out_dir / f"model_meta_{args.target}.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Save] {meta_path}")

    report = {
        "target": args.target,
        "test_period": args.test_years,
        "roi_summary_nova": roi_summary,
        "polaris_baseline": polaris_baseline,
        "diff": {
            "roi_pt": round(diff_roi, 2),
            "hit_rate_pt": round(diff_hit, 2),
            "verdict": verdict,
        },
        "metrics": metrics,
        "top_importance": sorted(
            importance.items(), key=lambda x: -x[1])[:20],
    }
    report_path = out_dir / f"training_report_{args.target}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Save] {report_path}")

    print(f"\n[Done] Total {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
