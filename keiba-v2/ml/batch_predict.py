#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
バッチ予測 — データを1回ロードして全日程を一括処理

Usage:
    python -m ml.batch_predict --from 2025-03-01 --to 2026-02-28
    python -m ml.batch_predict --from 2025-03-01 --to 2026-02-28 --with-bets
    python -m ml.batch_predict --from 2025-03-01 --to 2026-02-28 --with-bets --budget 30000
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core import config
from ml.predict import (
    load_model_and_meta, load_obstacle_model, load_master_data,
    get_races_for_date, load_keibabook_ext,
    predict_race, predict_obstacle_race, load_grade_offsets,
)


def get_all_dates(from_date: str, to_date: str) -> list:
    """date_indexから指定期間の全日付を取得"""
    di_path = config.indexes_dir() / "race_date_index.json"
    with open(di_path, encoding='utf-8') as f:
        date_index = json.load(f)

    dates = []
    for d in sorted(date_index.keys()):
        if from_date <= d <= to_date:
            dates.append(d)
    return dates


def predict_date(
    date: str,
    model_p, model_w, meta, calibrators, model_ar,
    model_obstacle, obstacle_meta, obstacle_calibrator,
    history_cache, trainer_index, jockey_index, pace_index,
    kb_ext_index, race_level_index, pedigree_index, sire_stats_index,
    baba_index, pit_trainer_tl, pit_jockey_tl,
    grade_offsets,
    with_bets: bool = False,
    budget: int = 30000,
):
    """1日分の予測を実行してpredictions.jsonを保存"""
    races = get_races_for_date(date)
    if not races:
        return 0

    has_obstacle_model = model_obstacle is not None

    # DB事前オッズ取得
    db_odds_index = {}
    db_place_odds_index = {}
    try:
        from core.odds_db import batch_get_pre_race_odds, batch_get_place_odds, is_db_available
        if is_db_available():
            race_codes = [r['race_id'] for r in races]
            db_odds_index = batch_get_pre_race_odds(race_codes)
            db_place_odds_index = batch_get_place_odds(race_codes)
    except Exception:
        pass

    # CK_DATA調教サマリ
    training_summary_day = {}
    date_parts = date.split('-')
    ts_path = (config.races_dir() / date_parts[0] / date_parts[1] / date_parts[2]
               / "temp" / "training_summary.json")
    if ts_path.exists():
        try:
            with open(ts_path, encoding='utf-8') as f:
                ts_data = json.load(f)
            for _name, entry in ts_data.get('summaries', {}).items():
                kn = entry.get('kettoNum', '')
                if kn:
                    training_summary_day[kn] = entry
        except Exception:
            pass

    # 障害/平地分離
    obstacle_races = []
    flat_races = []
    for race in races:
        race_name = race.get('race_name', '')
        track_type = race.get('track_type', '')
        if '障害' in race_name or track_type == 'obstacle':
            obstacle_races.append(race)
        else:
            flat_races.append(race)

    if not has_obstacle_model:
        obstacle_races = []

    # 平地予測
    all_predictions = []
    vb_count = 0

    for race in flat_races:
        kb_ext = load_keibabook_ext(race['race_id'], race['date'])
        pred = predict_race(
            race, kb_ext,
            model_p, meta,
            history_cache, trainer_index, jockey_index, pace_index,
            db_odds=db_odds_index.get(race['race_id']),
            training_summary_day=training_summary_day,
            model_w=model_w,
            db_place_odds=db_place_odds_index.get(race['race_id']),
            kb_ext_index=kb_ext_index,
            calibrators=calibrators,
            model_ar=model_ar,
            grade_offsets=grade_offsets,
            race_level_index=race_level_index,
            pedigree_index=pedigree_index,
            sire_stats_index=sire_stats_index,
            baba_index=baba_index,
            pit_trainer_tl=pit_trainer_tl,
            pit_jockey_tl=pit_jockey_tl,
        )
        all_predictions.append(pred)
        for e in pred['entries']:
            if e['is_value_bet']:
                vb_count += 1

    # 障害予測リダイレクト
    if has_obstacle_model:
        redirected = []
        for pred in all_predictions:
            if pred.get('_needs_obstacle_model'):
                original = next((r for r in flat_races if r['race_id'] == pred['race_id']), None)
                if original:
                    redirected.append(original)
        if redirected:
            all_predictions = [p for p in all_predictions if not p.get('_needs_obstacle_model')]
            obstacle_races.extend(redirected)

    # 障害レース予測
    obstacle_predictions = []
    if obstacle_races and has_obstacle_model:
        for race in obstacle_races:
            pred = predict_obstacle_race(
                race, model_obstacle, obstacle_meta, obstacle_calibrator,
                history_cache, trainer_index, jockey_index, pace_index,
                db_odds=db_odds_index.get(race['race_id']),
                kb_ext_index=kb_ext_index,
                race_level_index=race_level_index,
                pedigree_index=pedigree_index,
                sire_stats_index=sire_stats_index,
                pit_trainer_tl=pit_trainer_tl,
                pit_jockey_tl=pit_jockey_tl,
            )
            obstacle_predictions.append(pred)
            all_predictions.append(pred)

    # 特徴量スナップショット除去
    for pred in all_predictions:
        pred.pop('_feature_snapshot', None)

    # 買い目生成
    all_recommendations = {}
    multi_leg_output = []
    if with_bets and all_predictions:
        from ml.bet_engine import (
            PRESETS, generate_recommendations,
            recommendations_to_dict, recommendations_summary,
        )
        for preset_name, preset_params in PRESETS.items():
            recs = generate_recommendations(all_predictions, preset_params, budget=budget)
            all_recommendations[preset_name] = {
                'params': {
                    'win_min_ev': preset_params.win_min_ev,
                    'win_min_gap': preset_params.win_min_gap,
                    'win_min_rating': preset_params.win_min_rating,
                    'win_min_ar_deviation': preset_params.win_min_ar_deviation,
                    'win_max_rank': preset_params.win_max_rank,
                    'win_v_ratio_min': preset_params.win_v_ratio_min,
                    'win_v_bypass_gap': preset_params.win_v_bypass_gap,
                    'win_v_bypass_ev': preset_params.win_v_bypass_ev,
                    'place_min_gap': preset_params.place_min_gap,
                    'place_min_rating': preset_params.place_min_rating,
                    'place_min_ar_deviation': preset_params.place_min_ar_deviation,
                    'place_min_ev': preset_params.place_min_ev,
                    'kelly_fraction': preset_params.kelly_fraction,
                    'place_addon': preset_params.place_addon,
                    'place_addon_min_pev': preset_params.place_addon_min_pev,
                    'place_addon_min_ard': preset_params.place_addon_min_ard,
                    'place_addon_amount': preset_params.place_addon_amount,
                },
                'bets': recommendations_to_dict(recs),
                'summary': recommendations_summary(recs),
            }

        # マルチレグ
        try:
            from ml.simulate_multi_leg import generate_recommendations as gen_multi_leg
            multi_leg_recs = gen_multi_leg(all_predictions)
            for r in multi_leg_recs:
                multi_leg_output.append({
                    'race_id': r.race_id,
                    'venue': r.venue,
                    'race_number': r.race_num,
                    'strategy': r.strategy,
                    'ticket_type': r.ticket_type,
                    'horses': list(r.horses),
                    'horse_names': list(r.horse_names),
                    'cost': r.cost,
                    'note': r.note,
                })
        except Exception:
            pass

    # 出力
    actual_model_version = meta.get('version', '?')
    output = {
        'version': '4.1',
        'created_at': datetime.now().isoformat(timespec='seconds'),
        'date': date,
        'model_version': actual_model_version,
        'model_source': 'live',
        'model_features_value': len(meta.get('features_value', [])),
        'model_has_win': model_w is not None,
        'model_has_obstacle': has_obstacle_model,
        'odds_source': 'mykeibadb' if db_odds_index else 'json',
        'pit_mode': True,
        'predict_only': not with_bets,
        'db_odds_coverage': f"{len(db_odds_index)}/{len(races)}",
        'races': all_predictions,
        'recommendations': all_recommendations,
        'multi_leg_recommendations': multi_leg_output,
        'summary': {
            'total_races': len(all_predictions),
            'obstacle_races': len(obstacle_predictions),
            'total_entries': sum(len(p['entries']) for p in all_predictions),
            'value_bets': vb_count,
            'ev_positive_win': sum(
                1 for p in all_predictions for e in p['entries']
                if (e.get('win_ev') or 0) > 1.0
            ),
            'ev_positive_place': sum(
                1 for p in all_predictions for e in p['entries']
                if (e.get('place_ev') or 0) > 1.0
            ),
        },
    }

    # 保存
    date_parts = date.split('-')
    archive_dir = config.races_dir() / date_parts[0] / date_parts[1] / date_parts[2]
    if archive_dir.exists():
        out_path = archive_dir / "predictions.json"
        out_json = json.dumps(output, ensure_ascii=False, indent=2)
        out_path.write_text(out_json, encoding='utf-8')

    return len(all_predictions)


def main():
    parser = argparse.ArgumentParser(description='バッチ予測 — 全日程一括処理')
    parser.add_argument('--from', dest='from_date', required=True,
                        help='開始日 (YYYY-MM-DD)')
    parser.add_argument('--to', dest='to_date', required=True,
                        help='終了日 (YYYY-MM-DD)')
    parser.add_argument('--with-bets', action='store_true',
                        help='買い目も生成')
    parser.add_argument('--budget', type=int, default=30000,
                        help='予算 (default: 30000)')
    args = parser.parse_args()

    t0 = time.time()
    print(f"\n{'='*60}")
    print(f"  Batch Predict")
    print(f"  Period: {args.from_date} ~ {args.to_date}")
    print(f"  Bets:   {'ON' if args.with_bets else 'OFF'}")
    print(f"{'='*60}\n")

    # 日付リスト
    dates = get_all_dates(args.from_date, args.to_date)
    print(f"[Dates] {len(dates)} days found")

    # モデルロード
    print("\n[Load] Loading models...")
    model_p, model_w, meta, calibrators, model_ar = load_model_and_meta()
    model_obstacle, obstacle_meta, obstacle_calibrator = load_obstacle_model()
    print(f"  Model v{meta.get('version', '?')}")

    # マスタデータロード
    print("[Load] Loading master data...")
    (history_cache, trainer_index, jockey_index, pace_index,
     kb_ext_index, race_level_index, pedigree_index, sire_stats_index,
     baba_index, pit_trainer_tl, pit_jockey_tl) = load_master_data()

    # グレードオフセット
    grade_offsets = load_grade_offsets()

    load_time = time.time() - t0
    print(f"\n[Load] Done in {load_time:.1f}s")

    # バッチ予測
    total_races = 0
    for i, date in enumerate(dates):
        dt0 = time.time()
        n = predict_date(
            date,
            model_p, model_w, meta, calibrators, model_ar,
            model_obstacle, obstacle_meta, obstacle_calibrator,
            history_cache, trainer_index, jockey_index, pace_index,
            kb_ext_index, race_level_index, pedigree_index, sire_stats_index,
            baba_index, pit_trainer_tl, pit_jockey_tl,
            grade_offsets,
            with_bets=args.with_bets,
            budget=args.budget,
        )
        total_races += n
        dt = time.time() - dt0
        prog = f"[{i+1}/{len(dates)}]"
        print(f"  {prog} {date}: {n} races ({dt:.1f}s)")

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print(f"  Complete: {len(dates)} days, {total_races} races")
    print(f"  Elapsed: {elapsed:.0f}s ({elapsed/60:.1f}min)")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
