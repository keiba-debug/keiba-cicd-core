#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Regulus: 3歳上 芝OP+ 専用モデル 本番学習 (Session 182 / 最適化 Session 183)

Phase 1 (`docs/ml-experiments/v9.x_turf_op_specialist_phase0.md` §6.3) で確定した
lean_plus 構成 (basic+form_level+trajectory+jrdb_idm+jrdb_cid+jrdb_other+jockey+pace+class_ctx)
を本番モデルとして学習・保存・レジストリ登録する。

── Session 183 最適化 (v1.1) ────────────────────────────────────────────
v1.0 の弱点: early-stop/isotonic較正の val が 2025.04 の1ヶ月(47R/600頭)しかなく、
P が best_iter=38 で早期停止・W の較正 ECE=0.033 と不安定だった。
複数パターン比較 (scratchpad/optimize_regulus.py) の結論:
  - **val拡大 (1ヶ月→6ヶ月 2024.11-2025.04)** が最大の効き目:
      P AUC 0.7701→0.7757 / Brier 0.1476→0.1443,
      W ECE 0.0326→0.0033 (≈10x改善) / winner_in_top3 0.529→0.577。
  - P は小データ向けに正則化を強めた params(num_leaves63/depth6/mcs80/α0.3/λ3.0)が最良。
  - LambdaRank・積極的な特徴量pruning は改善せず → 不採用。
つまり構造(val)を直した上で lean_plus/binary を維持するのが最良。→ v1.1 で採用。

payout エッジは狙わない (OP+ 市場はシャープ、汎用 polaris が ROI で上回る)。
Session 183 の買い目シミュレーション(scratchpad/regulus_betting_sim.py)でも
Top1単勝/EV/gap/逆張り いずれも bootstrap CI が 100% を跨ぎ、頑健な払戻エッジは無し。
価値は本命精度・較正・ランキング(第二意見)。bet_engine には配線しない。
ただし条件別分析では **重賞(G1-G3)で本命精度が突出**(P-top1: G1 勝率50%/n=24, 重賞ROI≈103%)
= 予想品質シグナルとして shadow 監視に値する(meta.segment_analysis_* に記録)。

データは `ml.nova.ablation_turf_op --build` が作成済みの splits pickle
(train=2020-2025.03, val=2025.04, test=2025.05-2026.05, sire_cutoff=2025-03-31) を再利用し、
train+val を結合して 2024.11-2025.04 を内部valに切り出す(bigval reslice)。

Usage:
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

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import roc_auc_score, accuracy_score, log_loss

from core import config
from ml.experiment import (FEATURE_COLS_ALL, PARAMS_P, PARAMS_W, P_ONLY_FEATURES, MARKET_FEATURES,
                           calibrate_isotonic, calc_ece, calc_brier_score)
from ml.nova.ablation_turf_op import GROUP_ORDER, SPLITS, assign_groups
from ml.nova.train_turf_op import OP_GRADES, evaluate_top1_roi, filter_turf_op
from ml.model_loader import register_version

MODEL_NAME = "regulus"
VERSION = "1.2"
# 36K小データの単一seed分散を減らす seedアンサンブル (S183: P ECE0.021→0.015, W AUC+0.006, winner_in_top3改善)
ENSEMBLE_SEEDS = [42, 1, 7, 13, 21]
LEAN_GROUPS = [
    "basic", "form_level", "trajectory", "jrdb_idm", "jrdb_cid",
    "jrdb_other", "jockey", "pace", "class_ctx",
]
# bigval reslice: train+val(2020-2025.04) を結合し、末尾6ヶ月を内部valに
VAL_YM_START = 202411
VAL_YM_END = 202504
TRAIN_PERIOD = "2020.01-2024.10"
VAL_PERIOD = "2024.11-2025.04"
TEST_PERIOD = "2025.05-2026.05"
SIRE_CUTOFF = "2025-03-31"
MIN_AGE = 3

# P は小データ(≈39K)向けに正則化強め・浅め (Session183 optimize_regulus.py で最良)
PARAMS_REG_P = {**PARAMS_P, "num_leaves": 63, "max_depth": 6,
                "min_child_samples": 80, "reg_alpha": 0.3, "reg_lambda": 3.0}
PARAMS_REG_W = PARAMS_W  # W は bigval + 既定paramsが最良較正

SEGMENT_TIERS = {
    "重賞(G1-G3)": ["G1", "G2", "G3"], "Listed": ["Listed"], "OP": ["OP"],
    "G1": ["G1"], "G2": ["G2"], "G3": ["G3"],
}


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


def _segment_analysis(df_te: pd.DataFrame, pred_cal, label_col: str) -> list:
    """グレード帯別に Top1(予測本命)単勝成績と AUC を集計 (表示専用・第二意見の得意条件マップ)。"""
    d = df_te.copy()
    d["_p"] = pred_cal
    rows = []
    for name, grades in SEGMENT_TIERS.items():
        sub = d[d["grade"].isin(grades)]
        if not len(sub):
            continue
        roi = evaluate_top1_roi(sub, "_p")
        auc = (round(float(roc_auc_score(sub[label_col], sub["_p"])), 4)
               if sub[label_col].nunique() > 1 else None)
        rows.append({
            "segment": name, "n": int(sub["race_id"].nunique()), "auc": auc,
            "top1_win_rate": roi["hit_rate"], "top1_place_rate": roi["place_rate"],
            "top1_win_roi": roi["roi"],
        })
    return rows


def _fit_ensemble(df_tr, df_va, df_te, features, params, label_col, seeds, num_boost):
    """seedを変えたN本を学習し val/test raw を平均→averaged raw で isotonic較正。
    小データ(≈36K)の単一seed分散を平均で削る。返り値=(models[list], metrics, importance_avg, pred_cal_test, calibrator)。"""
    features = [f for f in features if f in df_tr.columns]
    Xtr, ytr = df_tr[features], df_tr[label_col]
    Xva, yva = df_va[features], df_va[label_col]
    Xte, yte = df_te[features], df_te[label_col]
    models, val_raws, test_raws, imps = [], [], [], []
    for s in seeds:
        p = {**params, "seed": s, "bagging_seed": s, "feature_fraction_seed": s}
        dtr = lgb.Dataset(Xtr, label=ytr)
        dva = lgb.Dataset(Xva, label=yva, reference=dtr)
        m = lgb.train(p, dtr, num_boost_round=num_boost, valid_sets=[dva],
                      callbacks=[lgb.early_stopping(50), lgb.log_evaluation(0)])
        models.append(m)
        val_raws.append(m.predict(Xva)); test_raws.append(m.predict(Xte))
        imps.append(dict(zip(features, m.feature_importance(importance_type="gain"))))
        print(f"    seed={s:>2} best_iter={m.best_iteration} test_auc={roc_auc_score(yte, test_raws[-1]):.4f}")
    val_raw = np.mean(val_raws, axis=0); test_raw = np.mean(test_raws, axis=0)
    pred_cal, calibrator = calibrate_isotonic(val_raw, yva.values, test_raw)
    importance = {f: float(np.mean([im[f] for im in imps])) for f in features}
    metrics = {
        "auc": round(float(roc_auc_score(yte, test_raw)), 4),
        "accuracy": round(float(accuracy_score(yte, (test_raw > 0.5).astype(int))), 4),
        "log_loss": round(float(log_loss(yte, np.clip(test_raw, 1e-7, 1 - 1e-7))), 4),
        "brier_score": round(float(calc_brier_score(yte.values, test_raw)), 4),
        "ece": round(float(calc_ece(yte.values, test_raw)), 4),
        "ece_calibrated": round(float(calc_ece(yte.values, pred_cal)), 4),
        "brier_calibrated": round(float(calc_brier_score(yte.values, pred_cal)), 4),
        "log_loss_calibrated": round(float(log_loss(yte, np.clip(pred_cal, 1e-7, 1 - 1e-7))), 4),
        "auc_val": round(float(roc_auc_score(yva, val_raw)), 4),
        "best_iteration": int(np.round(np.mean([m.best_iteration for m in models]))),
        "n_seeds": len(seeds),
        "train_size": len(Xtr), "val_size": len(Xva), "test_size": len(Xte),
    }
    return models, metrics, importance, pred_cal, calibrator


def train_target(target: str, params: dict, df_tr, df_va, df_te, args, out_dir: Path):
    label_col = "is_top3" if target == "p" else "is_win"
    features = build_lean_feature_set(df_tr.columns, target)
    print(f"\n[Train:{target.upper()}] lean_plus features={len(features)}, seeds={ENSEMBLE_SEEDS}, "
          f"train={len(df_tr):,} val={len(df_va):,} test={len(df_te):,} "
          f"(num_leaves={params.get('num_leaves')} depth={params.get('max_depth')})")

    models, metrics, importance, pred_cal, calibrator = _fit_ensemble(
        df_tr, df_va, df_te, features, params, label_col, ENSEMBLE_SEEDS, args.num_boost_round)

    df_eval = df_te.copy()
    df_eval[f"pred_{target}"] = pred_cal
    roi_summary = evaluate_top1_roi(df_eval, f"pred_{target}")
    segment = _segment_analysis(df_te, pred_cal, label_col)
    print(f"  [Regulus-{target.upper()}] ens{metrics['n_seeds']} Top1単勝: bets={roi_summary['n']:,} "
          f"hit_rate={roi_summary['hit_rate']}% ROI={roi_summary['roi']}% "
          f"| AUC={metrics['auc']} ECE(cal)={metrics['ece_calibrated']} avg_iter={metrics['best_iteration']}")
    for s in segment:
        if s["segment"] in ("重賞(G1-G3)", "Listed", "OP"):
            print(f"      {s['segment']:<10} {s['n']:>3}R AUC={s['auc']} "
                  f"win={s['top1_win_rate']}% ROI={s['top1_win_roi']}%")

    # 保存: 先頭=primary(ModelBundle互換), 残り=アンサンブルメンバー(predict_regulusが平均)
    models[0].save_model(str(out_dir / f"model_{target}.txt"))
    for i, m in enumerate(models[1:], start=1):
        m.save_model(str(out_dir / f"model_{target}_ens{i}.txt"))
    importance_sorted = [
        {"feature": k, "importance": float(v)}
        for k, v in sorted(importance.items(), key=lambda x: -x[1])
    ]
    return {
        "features": features, "metrics": metrics, "calibrator": calibrator,
        "importance": importance_sorted, "roi_summary": roi_summary, "segment": segment,
    }


def main():
    p = argparse.ArgumentParser(description="Regulus (3歳上芝OP+専用) 本番学習 v1.1")
    p.add_argument("--target", default="both", choices=["p", "w", "both"])
    p.add_argument("--num-boost-round", type=int, default=1500)
    p.add_argument("--set-active", action="store_true", help="学習後にレジストリでactive_versionに設定")
    args = p.parse_args()

    targets = ["p", "w"] if args.target == "both" else [args.target]
    t0 = time.time()

    print("=" * 70)
    print(f"  Regulus 本番学習 v{VERSION} (3歳上 芝OP+ 専用・lean_plus・bigval)  targets={targets}")
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

    # bigval reslice: train+val を結合し 2024.11-2025.04 を内部val, それ以前を train に
    alltv = pd.concat([df_train_e, df_val_e], ignore_index=True)
    ym = alltv["race_id"].str[:6].astype(int)
    df_val_e = alltv[(ym >= VAL_YM_START) & (ym <= VAL_YM_END)].copy()
    df_train_e = alltv[ym < VAL_YM_START].copy()
    print(f"[BigVal] internal_train={len(df_train_e):,} ({df_train_e['race_id'].nunique()}R) "
          f"internal_val={len(df_val_e):,} ({df_val_e['race_id'].nunique()}R)")

    if len(df_train_e) < 1000 or len(df_val_e) < 100 or len(df_test_e) < 100:
        print(f"\n  ERROR: サンプル数不足: train={len(df_train_e)} val={len(df_val_e)} test={len(df_test_e)}")
        return 1

    out_dir = config.ml_dir() / "models" / MODEL_NAME / "live"
    out_dir.mkdir(parents=True, exist_ok=True)

    param_map = {"p": PARAMS_REG_P, "w": PARAMS_REG_W}
    results = {}
    for tgt in targets:
        results[tgt] = train_target(tgt, param_map[tgt], df_train_e, df_val_e, df_test_e, args, out_dir)

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
        "optimization_note": (
            "v1.2(S183): v1.1のbigval(early-stop/較正valを1ヶ月→6ヶ月2024.11-2025.04)に加え、"
            "seedを変えた5本のアンサンブル平均で小データ分散を低減。"
            "P ECE 0.021→0.015・W AUC 0.757→0.762・winner_in_top3 改善。"
            "P paramsは小データ向け正則化強め(leaves63/depth6/mcs80)。LambdaRank/pruning/G3+絞り込みは不採用"
            "(G3+絞りはデータ痩せでAUC急落=学習≠適用条件でよい[feedback_train_scope_not_match_eval])。"
            "買い目sim: 頑健な払戻エッジ無し(bootstrap CIが100%跨ぎ)=市場シャープの事前想定通り。"
            "但し重賞(G1-G3)は本命精度突出=第二意見/shadow監視に有用(P/W blendのrankavg本命が重賞で最良)。"
        ),
        "has_win_model": "w" in results,
        "has_calibrators": True,
        "ensemble_seeds": ENSEMBLE_SEEDS,
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
        meta["segment_analysis_p"] = results["p"]["segment"]
    if "w" in results:
        meta["features_w"] = results["w"]["features"]
        meta["feature_count_w"] = len(results["w"]["features"])
        meta["metrics_w"] = results["w"]["metrics"]
        meta["feature_importance_w"] = results["w"]["importance"]
        meta["roi_analysis_w"] = results["w"]["roi_summary"]
        meta["segment_analysis_w"] = results["w"]["segment"]

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
        description="bigval + 5seedアンサンブル (val 1→6ヶ月, P正則化強め, seed平均で分散低減)。lean_plus/binary維持。",
        p_auc=p_auc, w_auc=w_auc,
        features=len(n_feat) if n_feat else None,
        set_active=args.set_active,
    )

    print(f"\n[Done] Total {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
