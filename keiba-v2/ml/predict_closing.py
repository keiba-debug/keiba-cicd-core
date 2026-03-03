#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
差し追込好走予測 — ライブ推論

既存 predictions.json にレースレベルの closing_race_proba を追記する。
predict.py 実行後に実行する想定。

Usage:
    python -m ml.predict_closing --date 2026-02-28
    python -m ml.predict_closing --latest
"""

import argparse
import json
import pickle
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import lightgbm as lgb
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from ml.experiment import (
    load_race_json, _iter_date_index,
    compute_features_for_race, load_data,
    build_pit_personnel_timeline,
)
from ml.features.closing_race_features import (
    CLOSING_RACE_FEATURES,
    CourseClosingTimeline,
    compute_closing_race_features,
)
from ml.features.baba_features import get_baba_features, load_baba_index


def load_closing_model():
    """差し追込モデルをロード"""
    ml_dir = config.ml_dir()
    model_path = ml_dir / "model_closing.txt"
    cal_path = ml_dir / "calibrator_closing.pkl"
    meta_path = ml_dir / "model_closing_meta.json"

    if not model_path.exists():
        raise FileNotFoundError(
            f"model_closing.txt が見つかりません (in {ml_dir})\n"
            "先に python -m ml.experiment_closing を実行してください"
        )

    model = lgb.Booster(model_file=str(model_path))

    calibrator = None
    if cal_path.exists():
        with open(cal_path, 'rb') as f:
            calibrator = pickle.load(f)

    meta = {}
    if meta_path.exists():
        with open(meta_path, encoding='utf-8') as f:
            meta = json.load(f)

    return model, calibrator, meta


def predict_closing_for_date(
    date: str,
    model,
    calibrator,
    meta: dict,
    history_cache: dict,
    trainer_index: dict,
    jockey_index: dict,
    pace_index: dict,
    kb_ext_index: dict,
    course_timeline: CourseClosingTimeline,
    baba_index: dict,
    race_level_index: dict = None,
    pedigree_index: dict = None,
    sire_stats_index: dict = None,
    pit_trainer_tl: dict = None,
    pit_jockey_tl: dict = None,
) -> dict:
    """指定日のレースの差し決着度を予測

    Returns:
        {race_id: closing_race_proba} の辞書
    """
    features = meta.get('features', CLOSING_RACE_FEATURES)

    # 指定日のレースJSONを読み込み
    date_parts = date.split('-')
    race_dir = config.races_dir() / date_parts[0] / date_parts[1] / date_parts[2]

    if not race_dir.exists():
        print(f"[Warning] Race dir not found: {race_dir}")
        return {}

    # DB事前オッズ取得
    db_odds_index = {}
    db_place_odds_index = {}
    try:
        from core.odds_db import batch_get_pre_race_odds, batch_get_place_odds, is_db_available
        if is_db_available():
            import glob as glob_mod
            race_files = list(race_dir.glob("race_[0-9]*.json"))
            race_ids = [f.stem.replace('race_', '') for f in race_files]
            db_odds_index = batch_get_pre_race_odds(race_ids)
            db_place_odds_index = batch_get_place_odds(race_ids)
    except Exception:
        pass

    results = {}
    race_count = 0

    for race_file in sorted(race_dir.glob("race_[0-9]*.json")):
        try:
            with open(race_file, encoding='utf-8') as f:
                race = json.load(f)

            race_id = race.get('race_id', '')
            track_type = race.get('track_type', '')
            num_runners = race.get('num_runners', 0)

            # 障害・少頭数はスキップ
            if track_type == 'obstacle' or '障害' in race.get('race_name', ''):
                continue
            if num_runners < 8:
                continue

            # 馬レベル特徴量を計算
            horse_features = compute_features_for_race(
                race, history_cache, trainer_index, jockey_index,
                pace_index, kb_ext_index,
                db_odds=db_odds_index.get(race_id),
                db_place_odds=db_place_odds_index.get(race_id),
                race_level_index=race_level_index,
                pedigree_index=pedigree_index,
                sire_stats_index=sire_stats_index,
                pit_trainer_tl=pit_trainer_tl,
                pit_jockey_tl=pit_jockey_tl,
            )

            # 馬場特徴量
            baba_feat = get_baba_features(race_id, track_type, baba_index)

            # レースレベル特徴量に集計
            race_feat = compute_closing_race_features(
                race, horse_features,
                course_timeline=course_timeline,
                baba_features=baba_feat,
            )

            # 推論
            feat_values = [race_feat.get(f, np.nan) for f in features]
            X = np.array([feat_values])
            pred_raw = float(model.predict(X)[0])

            # キャリブレーション
            if calibrator is not None:
                pred_cal = float(calibrator.predict([pred_raw])[0])
                pred_cal = max(0.0, min(1.0, pred_cal))
            else:
                pred_cal = pred_raw

            results[race_id] = round(pred_cal, 4)
            race_count += 1

        except Exception as e:
            print(f"  ERROR: {race_file.name}: {e}")

    print(f"[Closing] {race_count} races predicted for {date}")
    return results


def main():
    parser = argparse.ArgumentParser(description='Closing Race Prediction')
    parser.add_argument('--date', help='予測対象日 (YYYY-MM-DD)')
    parser.add_argument('--latest', action='store_true', help='最新の開催日')
    args = parser.parse_args()

    # 日付決定
    if args.latest:
        di_path = config.indexes_dir() / "race_date_index.json"
        with open(di_path, encoding='utf-8') as f:
            date_index = json.load(f)
        date = max(date_index.keys())
        print(f"[Date] Latest: {date}")
    elif args.date:
        date = args.date
    else:
        date = datetime.now().strftime('%Y-%m-%d')

    print(f"\n{'='*60}")
    print(f"  KeibaCICD - Closing Race Prediction")
    print(f"  Date: {date}")
    print(f"{'='*60}\n")

    t0 = time.time()

    # モデルロード
    model, calibrator, meta = load_closing_model()
    print(f"[Model] Closing model loaded: {meta.get('version', '?')}, "
          f"{meta.get('feature_count', '?')} features")

    # データロード
    (history_cache, trainer_index, jockey_index,
     date_index, pace_index, kb_ext_index, _training_summary_index,
     race_level_index, pedigree_index, sire_stats_index) = load_data()

    # PIT timeline
    pit_trainer_tl, pit_jockey_tl = build_pit_personnel_timeline(
        years=list(range(2020, 2027))
    )

    # 馬場データ
    baba_index = load_baba_index()

    # コース歴史統計タイムライン
    from ml.experiment_closing import build_course_timeline
    course_timeline = build_course_timeline(date_index)

    # 予測実行
    closing_probs = predict_closing_for_date(
        date, model, calibrator, meta,
        history_cache, trainer_index, jockey_index,
        pace_index, kb_ext_index,
        course_timeline, baba_index,
        race_level_index=race_level_index,
        pedigree_index=pedigree_index,
        sire_stats_index=sire_stats_index,
        pit_trainer_tl=pit_trainer_tl,
        pit_jockey_tl=pit_jockey_tl,
    )

    if not closing_probs:
        print("[Warning] No predictions generated")
        sys.exit(0)

    # predictions.json に追記
    date_parts = date.split('-')
    pred_path = config.races_dir() / date_parts[0] / date_parts[1] / date_parts[2] / "predictions.json"

    if pred_path.exists():
        with open(pred_path, encoding='utf-8') as f:
            pred_data = json.load(f)

        # 各レースに closing_race_proba を追記
        updated = 0
        for race_obj in pred_data.get('races', []):
            race_id = race_obj.get('race_id', '')
            if race_id in closing_probs:
                race_obj['closing_race_proba'] = closing_probs[race_id]
                updated += 1

        pred_data['has_closing_model'] = True
        pred_data['closing_model_version'] = meta.get('version', '?')

        pred_path.write_text(
            json.dumps(pred_data, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        print(f"[Save] Updated {updated} races in {pred_path}")
    else:
        # predictions.jsonがない場合は単独ファイルを作成
        standalone = {
            'created_at': datetime.now().isoformat(timespec='seconds'),
            'date': date,
            'closing_model_version': meta.get('version', '?'),
            'closing_predictions': closing_probs,
        }
        out_path = config.races_dir() / date_parts[0] / date_parts[1] / date_parts[2] / "closing_predictions.json"
        out_path.write_text(
            json.dumps(standalone, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        print(f"[Save] Standalone output: {out_path}")

    # サマリー
    probs = list(closing_probs.values())
    elapsed = time.time() - t0
    print(f"\n[Summary]")
    print(f"  Races:    {len(probs)}")
    print(f"  Mean:     {np.mean(probs):.3f}")
    print(f"  Max:      {max(probs):.3f}")
    print(f"  >= 0.15:  {sum(1 for p in probs if p >= 0.15)} races")
    print(f"  Elapsed:  {elapsed:.1f}s")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
