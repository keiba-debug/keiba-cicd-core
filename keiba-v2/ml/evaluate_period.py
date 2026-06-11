#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
保存済み polaris モデルを指定期間の OOS データで評価する。

α/β/v2.3 の共通 test 比較用。AUC(P/W) + Top1 ROI + Bootstrap CI (1000×)。

Usage:
    python -m ml.evaluate_period --version 2.3 --test-years 2025.07-2026.05
    python -m ml.evaluate_period --version live --test-years 2025.07-2026.05 --sire-cutoff 2025-06-30
"""

import argparse
import io
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ml.experiment import (
    build_dataset,
    build_pit_personnel_timeline,
    calc_roi_analysis,
    calc_vb_bootstrap_ci,
    load_data,
    parse_period_range,
)
from ml.model_loader import load_model


def calc_top1_roi_bootstrap(
    df: pd.DataFrame,
    pred_col: str,
    n_bootstrap: int = 1000,
    ci_level: float = 0.95,
) -> dict:
    """Top1 単勝 ROI のレース単位 Bootstrap CI"""
    rng = np.random.default_rng(42)
    alpha = (1 - ci_level) / 2

    df = df.copy()
    df["_pred_rank"] = df.groupby("race_id")[pred_col].rank(ascending=False, method="min")
    top1 = df[df["_pred_rank"] == 1]
    race_ids = top1["race_id"].unique().tolist()
    n_races = len(race_ids)
    if n_races == 0:
        return {"top1_win_roi": 0, "top1_win_roi_ci_low": 0, "top1_win_roi_ci_high": 0, "n_races": 0}

    race_returns = {}
    for rid, grp in top1.groupby("race_id"):
        row = grp.iloc[0]
        race_returns[rid] = row["odds"] * 100 if row["is_win"] == 1 else 0

    total_bet = n_races * 100
    total_return = sum(race_returns.values())
    win_roi = total_return / total_bet * 100

    boot_rois = []
    for _ in range(n_bootstrap):
        sampled = rng.choice(race_ids, size=n_races, replace=True)
        b_ret = sum(race_returns[rid] for rid in sampled)
        boot_rois.append(b_ret / total_bet * 100)

    boot = np.array(boot_rois)
    return {
        "top1_win_roi": round(win_roi, 1),
        "top1_win_roi_ci_low": round(float(np.percentile(boot, alpha * 100)), 1),
        "top1_win_roi_ci_high": round(float(np.percentile(boot, (1 - alpha) * 100)), 1),
        "n_races": n_races,
    }


def evaluate_model(version: str, test_years: str, sire_cutoff: str = None,
                   dump_path: str = None) -> dict:
    test_min, test_min_m, test_max, test_max_m = parse_period_range(test_years)

    bundle = load_model("polaris", version=None if version == "live" else version)
    meta = bundle.meta
    fpm = meta.get("features_per_model", {})
    features_p = fpm.get("p") or meta.get("features_value", [])
    features_w = fpm.get("w") or meta.get("features_value", [])

    print(f"\n[Eval] polaris v{meta.get('version', version)} on test={test_years}")
    print(f"  source={bundle.source}, P feats={len(features_p)}, W feats={len(features_w)}")

    (history_cache, trainer_index, jockey_index,
     date_index, pace_index, kb_ext_index, training_summary_index,
     race_level_index, pedigree_index, sire_stats_index,
     jrdb_sed_index, jrdb_kyi_index, jrdb_kaa_index,
     jrdb_cyb_index, jrdb_cha_index, jrdb_kka_index, jrdb_joa_index) = load_data(
        sire_cutoff=sire_cutoff)

    pit_trainer_tl, pit_jockey_tl = build_pit_personnel_timeline()

    from ml.features.baba_features import load_baba_index
    baba_index = load_baba_index()

    df_test = build_dataset(
        date_index, history_cache, trainer_index, jockey_index, pace_index,
        kb_ext_index, test_min, test_max, use_db_odds=True,
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
    print(f"  test rows={len(df_test):,}, races={df_test['race_id'].nunique():,}")

    pred_p_raw = bundle.model_p.predict(df_test[features_p])
    pred_w_raw = bundle.model_w.predict(df_test[features_w])

    cal_p = bundle.calibrators.get("cal_p") if bundle.calibrators else None
    cal_w = bundle.calibrators.get("cal_w") if bundle.calibrators else None
    pred_p = cal_p.predict(pred_p_raw) if cal_p is not None else pred_p_raw
    pred_w = cal_w.predict(pred_w_raw) if cal_w is not None else pred_w_raw

    df_test["pred_proba_p"] = pred_p
    df_test["pred_proba_w"] = pred_w
    df_test["pred_rank_p"] = df_test.groupby("race_id")["pred_proba_p"].rank(
        ascending=False, method="min")
    df_test["pred_rank_w"] = df_test.groupby("race_id")["pred_proba_w"].rank(
        ascending=False, method="min")

    # Session 150: オッズ条件付き較正(cal_p_oc)の学習用に raw+結果+オッズを保存。
    # 別工程で直前オッズ(T-5)を join して OddsConditionedCalibrator を fit/eval する。
    if dump_path:
        df_test["pred_proba_p_raw"] = pred_p_raw
        keep = ["race_id", "umaban", "odds", "finish_position", "is_top3", "is_win",
                "pred_proba_p_raw", "pred_proba_p", "place_odds_low"]
        keep = [c for c in keep if c in df_test.columns]
        df_test[keep].to_pickle(dump_path)
        print(f"  [dump] dataset → {dump_path}  ({len(df_test):,} rows, cols={keep})")

    from sklearn.metrics import roc_auc_score
    p_auc = roc_auc_score(df_test["is_top3"], pred_p)
    w_auc = roc_auc_score(df_test["is_win"], pred_w)

    roi_p = calc_roi_analysis(df_test, "pred_proba_p")
    roi_w = calc_roi_analysis(df_test, "pred_proba_w")
    bs_p = calc_top1_roi_bootstrap(df_test, "pred_proba_p")
    bs_w = calc_top1_roi_bootstrap(df_test, "pred_proba_w")
    vb_bs_p = calc_vb_bootstrap_ci(df_test, rank_col="pred_rank_p")
    vb_bs_w = calc_vb_bootstrap_ci(df_test, rank_col="pred_rank_w")

    result = {
        "version": meta.get("version", version),
        "test_years": test_years,
        "sire_cutoff": sire_cutoff,
        "p_auc": round(p_auc, 4),
        "w_auc": round(w_auc, 4),
        "p_top1_win_roi": roi_p["top1_win_roi"],
        "w_top1_win_roi": roi_w["top1_win_roi"],
        "p_top1_bootstrap": bs_p,
        "w_top1_bootstrap": bs_w,
        "vb_bootstrap_place": vb_bs_p,
        "vb_bootstrap_win": vb_bs_w,
        "n_test_rows": len(df_test),
        "n_test_races": int(df_test["race_id"].nunique()),
    }

    print(f"\n  P AUC={p_auc:.4f}, W AUC={w_auc:.4f}")
    print(f"  P Top1 ROI={roi_p['top1_win_roi']:.1f}% "
          f"[{bs_p['top1_win_roi_ci_low']:.1f}% - {bs_p['top1_win_roi_ci_high']:.1f}%]")
    print(f"  W Top1 ROI={roi_w['top1_win_roi']:.1f}% "
          f"[{bs_w['top1_win_roi_ci_low']:.1f}% - {bs_w['top1_win_roi_ci_high']:.1f}%]")

    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="live", help="polaris バージョン (live / 2.3 / 2.4a 等)")
    ap.add_argument("--test-years", required=True, help="評価期間 (例: 2025.07-2026.05)")
    ap.add_argument("--sire-cutoff", default=None, help="血統統計カットオフ YYYY-MM-DD")
    ap.add_argument("--output", default=None, help="結果 JSON 出力パス")
    ap.add_argument("--dump-dataset", default=None,
                    help="raw+結果+オッズを pickle 保存 (cal_p_oc 学習用)")
    args = ap.parse_args()

    result = evaluate_model(args.version, args.test_years, args.sire_cutoff,
                            dump_path=args.dump_dataset)
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  Saved: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
