#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Regulus: 3歳上 芝OP+ 専用モデル 本番学習 (Session 182)

Phase 1 (`docs/ml-experiments/v9.x_turf_op_specialist_phase0.md` §6.3) で確定した
lean_plus 構成 (basic+form_level+trajectory+jrdb_idm+jrdb_cid+jrdb_other+jockey+pace+class_ctx)
= 全特徴量の約半分で全部入りに並ぶ/微増 (W: 103feat AUC0.7574 ROI80% / P: 117feat AUC0.7701 ROI82%)
を、初めて本番モデルとして学習・保存・レジストリ登録する。

payout エッジは狙わない (OP+ 市場はシャープ、汎用 polaris が ROI で上回る実験済み)。
Regulus は「経験豊富な王者級馬の対決を軌跡/CID中核で読む専門家の第二意見」= 表示専用。
bet_engine / win_ev / place_ev / is_value_bet には一切配線しない。

データは `ml.nova.ablation_turf_op --build` が作成済みの splits pickle
(train=2020-2025.03, val=2025.04, test=2025.05-2026.05, sire_cutoff=2025-03-31) を再利用する
(重い build_dataset の再実行を避ける。Phase1のリーン数値と同一条件で再現性を保つため)。

Usage:
    python -m ml.nova.train_regulus --target both
    python -m ml.nova.train_regulus --target both --set-active

Output:
    data3/ml/models/regulus/live/{model_p.txt, model_w.txt, meta.json, calibrators.pkl}
"""

from __future__ import annotations

import argparse
import json
import pickle
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pandas as pd

from core import config
from ml.experiment import FEATURE_COLS_ALL, PARAMS_P, PARAMS_W, P_ONLY_FEATURES, MARKET_FEATURES, train_model
from ml.nova.ablation_turf_op import GROUP_ORDER, SPLITS, assign_groups
from ml.nova.train_turf_op import OP_GRADES, evaluate_top1_roi, filter_turf_op
from ml.model_loader import register_version

MODEL_NAME = "regulus"
VERSION = "1.0"
LEAN_GROUPS = [
    "basic", "form_level", "trajectory", "jrdb_idm", "jrdb_cid",
    "jrdb_other", "jockey", "pace", "class_ctx",
]
TRAIN_PERIOD = "2020-2025.03"
VAL_PERIOD = "2025.04"
TEST_PERIOD = "2025.05-2026.05"
SIRE_CUTOFF = "2025-03-31"
MIN_AGE = 3


def _age_filt(df: pd.DataFrame, label: str) -> pd.DataFrame:
    out = df[df["age"] >= MIN_AGE].copy()
    print(f"  [{label}] age>={MIN_AGE}: {len(df):,} -> {len(out):,} "
          f"({df['race_id'].nunique():,} -> {out['race_id'].nunique():,} races)")
    return out


def build_lean_feature_set(all_cols, target: str) -> list:
    """lean_plus: FEATURE_COLS_ALL のうち LEAN_GROUPS に属する特徴量のみ。"""
    base = [f for f in FEATURE_COLS_ALL if f not in MARKET_FEATURES]
    if target == "w":
        base = [f for f in base if f not in P_ONLY_FEATURES]
    base = [f for f in base if f in all_cols]
    groups = assign_groups(base)
    feats = []
    for g in GROUP_ORDER:
        if g in LEAN_GROUPS and g in groups:
            feats.extend(groups[g])
    return feats


def train_target(target: str, df_tr, df_va, df_te, args, out_dir: Path):
    label_col = "is_top3" if target == "p" else "is_win"
    params = PARAMS_P if target == "p" else PARAMS_W
    features = build_lean_feature_set(df_tr.columns, target)
    print(f"\n[Train:{target.upper()}] lean_plus features={len(features)}, "
          f"train={len(df_tr):,} val={len(df_va):,} test={len(df_te):,}")

    model, metrics, importance, pred_cal, calibrator, pred_raw = train_model(
        df_tr, df_va, df_te,
        feature_cols=features, params=params, label_col=label_col,
        model_name=f"regulus_{target}", num_boost_round=args.num_boost_round,
    )

    df_eval = df_te.copy()
    df_eval[f"pred_{target}"] = pred_cal
    roi_summary = evaluate_top1_roi(df_eval, f"pred_{target}")
    print(f"  [Regulus-{target.upper()}] Top1単勝: bets={roi_summary['n']:,} "
          f"hit_rate={roi_summary['hit_rate']}% ROI={roi_summary['roi']}% "
          f"| AUC={metrics['auc']} ECE(cal)={metrics['ece_calibrated']}")

    model.save_model(str(out_dir / f"model_{target}.txt"))
    importance_sorted = [
        {"feature": k, "importance": float(v)}
        for k, v in sorted(importance.items(), key=lambda x: -x[1])
    ]
    return {
        "features": features,
        "metrics": metrics,
        "calibrator": calibrator,
        "importance": importance_sorted,
        "roi_summary": roi_summary,
    }


def main():
    p = argparse.ArgumentParser(description="Regulus (3歳上芝OP+専用) 本番学習")
    p.add_argument("--target", default="both", choices=["p", "w", "both"])
    p.add_argument("--num-boost-round", type=int, default=1500)
    p.add_argument("--set-active", action="store_true", help="学習後にレジストリでactive_versionに設定")
    args = p.parse_args()

    targets = ["p", "w"] if args.target == "both" else [args.target]
    t0 = time.time()

    print("=" * 70)
    print(f"  Regulus 本番学習 (3歳上 芝OP+ 専用・lean_plus構成)  targets={targets}")
    print(f"  train={TRAIN_PERIOD} val={VAL_PERIOD} test={TEST_PERIOD} sire_cutoff={SIRE_CUTOFF}")
    print("=" * 70)

    print("\n[Load] cached splits (ablation_turf_op --build 済み) ...")
    df_train = pd.read_pickle(SPLITS / "train.pkl")
    df_val = pd.read_pickle(SPLITS / "val.pkl")
    df_test = pd.read_pickle(SPLITS / "test.pkl")
    print(f"[Load] train={len(df_train):,} val={len(df_val):,} test={len(df_test):,} ({time.time()-t0:.0f}s)")

    print("\n[Filter] 3歳以上 × 芝 × OP以上 ...")
    df_train_e = _age_filt(filter_turf_op(df_train, "Train"), "Train/age")
    df_val_e = _age_filt(filter_turf_op(df_val, "Val"), "Val/age")
    df_test_e = _age_filt(filter_turf_op(df_test, "Test"), "Test/age")

    if len(df_train_e) < 1000 or len(df_val_e) < 100 or len(df_test_e) < 100:
        print(f"\n  ERROR: サンプル数不足: train={len(df_train_e)} val={len(df_val_e)} test={len(df_test_e)}")
        return 1

    out_dir = config.ml_dir() / "models" / MODEL_NAME / "live"
    out_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for tgt in targets:
        results[tgt] = train_target(tgt, df_train_e, df_val_e, df_test_e, args, out_dir)

    # --- calibrators.pkl ---
    calibrators = {}
    if "p" in results:
        calibrators["cal_p"] = results["p"]["calibrator"]
    if "w" in results:
        calibrators["cal_w"] = results["w"]["calibrator"]
    with open(out_dir / "calibrators.pkl", "wb") as f:
        pickle.dump(calibrators, f)

    # --- meta.json ---
    meta = {
        "version": VERSION,
        "model_type": "regulus_turf_op_specialist",
        "description": "3歳上 芝OP以上 専用モデル (経験豊富な王者級馬の対決を軌跡/CID中核で読む専門家の第二意見)。"
                        "payoutエッジは狙わず表示専用・bet_engine配線なし。",
        "has_win_model": "w" in results,
        "has_calibrators": True,
        "created_at": datetime.now().isoformat(),
        "train_period": TRAIN_PERIOD,
        "val_period": VAL_PERIOD,
        "test_period": TEST_PERIOD,
        "sire_cutoff": SIRE_CUTOFF,
        "min_age": MIN_AGE,
        "eligibility": {"track_type": "turf", "grade_in": sorted(OP_GRADES), "min_age": MIN_AGE},
        "feature_groups": LEAN_GROUPS,
        "train_races": int(df_train_e["race_id"].nunique()),
        "train_entries": int(len(df_train_e)),
        "val_races": int(df_val_e["race_id"].nunique()),
        "val_entries": int(len(df_val_e)),
        "test_races": int(df_test_e["race_id"].nunique()),
        "test_entries": int(len(df_test_e)),
    }
    if "p" in results:
        meta["features_p"] = results["p"]["features"]
        meta["feature_count_p"] = len(results["p"]["features"])
        meta["metrics_p"] = results["p"]["metrics"]
        meta["feature_importance_p"] = results["p"]["importance"]
        meta["roi_analysis_p"] = results["p"]["roi_summary"]
    if "w" in results:
        meta["features_w"] = results["w"]["features"]
        meta["feature_count_w"] = len(results["w"]["features"])
        meta["metrics_w"] = results["w"]["metrics"]
        meta["feature_importance_w"] = results["w"]["importance"]
        meta["roi_analysis_w"] = results["w"]["roi_summary"]

    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[Save] {out_dir}/{{model_p.txt, model_w.txt, meta.json, calibrators.pkl}}")

    # --- registry ---
    registry_path = config.ml_dir() / "model_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if MODEL_NAME not in registry.get("models", {}):
        registry.setdefault("models", {})[MODEL_NAME] = {
            "name": "Regulus",
            "category": "stars",
            "description": "3歳上芝OP以上 専用モデル（経験豊富な王者級馬の対決を軌跡/CID中核で読む専門家の第二意見・表示専用）",
            "icon": "crown",
            "model_dir": f"models/{MODEL_NAME}",
            "meta_file": f"models/{MODEL_NAME}/live/meta.json",
            "versions": [],
        }
        registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[Registry] '{MODEL_NAME}' base entry created")

    p_auc = results.get("p", {}).get("metrics", {}).get("auc")
    w_auc = results.get("w", {}).get("metrics", {}).get("auc")
    n_feat = results.get("p", {}).get("features")
    register_version(
        MODEL_NAME, VERSION,
        description="lean_plus構成 本番モデル (basic+form_level+trajectory+jrdb_idm+jrdb_cid+jrdb_other+jockey+pace+class_ctx)",
        p_auc=p_auc, w_auc=w_auc,
        features=len(n_feat) if n_feat else None,
        set_active=args.set_active,
    )

    print(f"\n[Done] Total {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
