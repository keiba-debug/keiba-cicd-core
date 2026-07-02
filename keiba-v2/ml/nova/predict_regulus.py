#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Regulus: 3歳上芝OP+専用モデル 日次スコアリング (Session 182)

`ml.predict` 実行時に既に生成されている `feature_snapshot.json`(全馬フル特徴量)と
`predictions.json`(レース単位のgrade/track_type等メタ)を読み、対象(3歳上×芝×OP以上)の
みを Regulus でスコアリングして側路の `regulus_scores.json` を出力する。

`ml/predict.py` の predict_race()/main() は一切変更しない — 完全な非侵襲サイドチャンネル。
表示専用（第二意見）。bet_engine / win_ev / place_ev には配線しない。

Usage:
    python -m ml.nova.predict_regulus --date 2026-06-28
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import numpy as np
import lightgbm as lgb

from core import config
from ml.model_loader import load_model_safe
from ml.nova.train_turf_op import OP_GRADES

MODEL_NAME = "regulus"
MIN_AGE = 3


def _to_float(val):
    if val is None:
        return np.nan
    try:
        f = float(val)
        return np.nan if np.isnan(f) else f
    except (TypeError, ValueError):
        return np.nan


def _build_arr(entries, feat_list):
    return np.array(
        [[_to_float(e["features"].get(f, np.nan)) for f in feat_list] for e in entries],
        dtype=np.float64,
    )


def emit_date(date: str):
    date_parts = date.split("-")
    day_dir = config.races_dir() / date_parts[0] / date_parts[1] / date_parts[2]
    snap_path = day_dir / "feature_snapshot.json"
    pred_path = day_dir / "predictions.json"

    if not snap_path.exists():
        print(f"[Regulus] feature_snapshot.json not found: {snap_path} — skip")
        return None
    if not pred_path.exists():
        print(f"[Regulus] predictions.json not found: {pred_path} — skip")
        return None

    bundle = load_model_safe(MODEL_NAME)
    if bundle is None:
        print("[Regulus] model unavailable — skip")
        return None

    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    preds = json.loads(pred_path.read_text(encoding="utf-8"))
    preds_by_race = {r["race_id"]: r for r in preds.get("races", [])}

    features_p = bundle.meta.get("features_p", [])
    features_w = bundle.meta.get("features_w", [])
    cal_p = (bundle.calibrators or {}).get("cal_p")
    cal_w = (bundle.calibrators or {}).get("cal_w")

    # seedアンサンブル: 学習時に平均raw較正しているので predict も全メンバーを平均する (v1.2)
    live_dir = config.ml_dir() / "models" / MODEL_NAME / "live"
    n_seeds = len(bundle.meta.get("ensemble_seeds", [])) or 1

    def _ens_models(target, primary):
        models = [primary] if primary is not None else []
        for i in range(1, n_seeds):
            fp = live_dir / f"model_{target}_ens{i}.txt"
            if fp.exists():
                models.append(lgb.Booster(model_file=str(fp)))
        return models

    models_p = _ens_models("p", bundle.model_p)
    models_w = _ens_models("w", bundle.model_w) if bundle.has_win else []
    print(f"[Regulus] ensemble: P×{len(models_p)} W×{len(models_w)} (seeds meta={n_seeds})")

    out_races = {}
    n_eligible_races = 0
    n_scored_entries = 0

    for race in snap.get("races", []):
        race_id = race["race_id"]
        race_meta = preds_by_race.get(race_id)
        if race_meta is None:
            continue
        # track_type は predictions.json 世代で "芝"(和/新) と "turf"(英/旧) が混在 → 両対応
        if race_meta.get("track_type") not in ("芝", "turf"):
            continue
        if race_meta.get("grade") not in OP_GRADES:
            continue

        entries = [e for e in race.get("entries", []) if _to_float(e["features"].get("age")) >= MIN_AGE]
        if not entries:
            continue

        arr_p = _build_arr(entries, features_p)
        raw_p = np.mean([m.predict(arr_p) for m in models_p], axis=0)
        cal_p_vals = cal_p.predict(raw_p) if cal_p is not None else raw_p

        result_map = {}
        for i, e in enumerate(entries):
            result_map[e["umaban"]] = {
                "proba_p": round(float(cal_p_vals[i]), 4),
                "proba_p_raw": round(float(raw_p[i]), 4),
            }

        if bundle.has_win and features_w:
            arr_w = _build_arr(entries, features_w)
            raw_w = np.mean([m.predict(arr_w) for m in models_w], axis=0)
            cal_w_vals = cal_w.predict(raw_w) if cal_w is not None else raw_w
            for i, e in enumerate(entries):
                result_map[e["umaban"]]["proba_w"] = round(float(cal_w_vals[i]), 4)
                result_map[e["umaban"]]["proba_w_raw"] = round(float(raw_w[i]), 4)

        order_p = sorted(result_map.keys(), key=lambda u: -result_map[u]["proba_p_raw"])
        for rank, u in enumerate(order_p, 1):
            result_map[u]["rank_p"] = rank
        if bundle.has_win:
            order_w = sorted(result_map.keys(), key=lambda u: -result_map[u]["proba_w_raw"])
            for rank, u in enumerate(order_w, 1):
                result_map[u]["rank_w"] = rank

            # P/W blend 本命 (S183: rankavg が重賞Top1で最良・rank和昇順で総合順位)
            order_blend = sorted(
                result_map.keys(),
                key=lambda u: (result_map[u].get("rank_p", 99) + result_map[u].get("rank_w", 99),
                               -result_map[u]["proba_w_raw"]))
            for rank, u in enumerate(order_blend, 1):
                r = result_map[u]
                r["rank_blend"] = rank
                r["blend_score"] = round(0.5 * r["proba_p"] + 0.5 * r.get("proba_w", 0.0), 4)

        polaris_by_umaban = {pe["umaban"]: pe for pe in race_meta.get("entries", [])}
        for u, r in result_map.items():
            pe = polaris_by_umaban.get(u)
            if not pe:
                continue
            r["horse_name"] = pe.get("horse_name")
            r["polaris_rank_p"] = pe.get("rank_p")
            r["polaris_rank_w"] = pe.get("rank_w")
            if pe.get("rank_p") is not None:
                r["delta_rank_p"] = pe["rank_p"] - r["rank_p"]
            if bundle.has_win and pe.get("rank_w") is not None and "rank_w" in r:
                r["delta_rank_w"] = pe["rank_w"] - r["rank_w"]

        out_races[str(race_id)] = {
            "race_name": race_meta.get("race_name"),
            "venue_name": race_meta.get("venue_name"),
            "race_number": race_meta.get("race_number"),
            "grade": race_meta.get("grade"),
            "n_eligible": len(entries),
            "entries": {str(u): v for u, v in result_map.items()},
        }
        n_eligible_races += 1
        n_scored_entries += len(entries)

    output = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "model_version": bundle.version,
        "prediction_date": date,
        "eligibility": {"track_type": "芝", "grade_in": sorted(OP_GRADES), "min_age": MIN_AGE},
        "eligible_races": n_eligible_races,
        "scored_entries": n_scored_entries,
        "races": out_races,
    }
    out_path = day_dir / "regulus_scores.json"
    out_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[Regulus] {date}: {n_eligible_races} eligible races / {n_scored_entries} entries -> {out_path}")
    return out_path


def main():
    p = argparse.ArgumentParser(description="Regulus 日次スコアリング (3歳上芝OP+のみ)")
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = p.parse_args()
    result = emit_date(args.date)
    return 0 if result is not None else 1


if __name__ == "__main__":
    sys.exit(main())
