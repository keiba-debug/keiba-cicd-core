#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
買い目生成スクリプト（推論結果から独立実行）

predictions.json のML推論結果を読み込み、bet_engine で買い目を生成。
predict.py とは独立して実行可能 → 戦略パラメータ変更時に推論やり直し不要。

Usage:
    python -m ml.generate_bets --date 2026-03-01
    python -m ml.generate_bets --date 2026-03-01 --budget 50000
    python -m ml.generate_bets --date 2026-03-01 --preset aggressive
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from ml.bet_engine import (
    PRESETS, generate_recommendations,
    recommendations_to_dict, recommendations_summary,
)


def load_predictions(date: str) -> dict:
    """日別アーカイブ races/YYYY/MM/DD/predictions.json を読み込み"""
    date_parts = date.split('-')
    pred_path = (config.races_dir() / date_parts[0] / date_parts[1]
                 / date_parts[2] / "predictions.json")
    if not pred_path.exists():
        raise FileNotFoundError(f"predictions.json not found: {pred_path}")

    with open(pred_path, encoding='utf-8') as f:
        data = json.load(f)
    return data


def apply_bet_engine(
    predictions_data: dict,
    budget: int = 30000,
    preset_filter: Optional[str] = None,
) -> dict:
    """predictions_data に recommendations を生成して書き込む

    Args:
        predictions_data: predictions.json のデータ（in-place更新）
        budget: 予算
        preset_filter: 特定プリセットのみ生成（None=全プリセット）

    Returns:
        all_recommendations dict
    """
    races = predictions_data.get('races', [])
    if not races:
        print("[Warning] No races in predictions data")
        return {}

    all_recommendations = {}
    presets = PRESETS
    if preset_filter:
        if preset_filter not in PRESETS:
            print(f"[Error] Unknown preset: {preset_filter}. "
                  f"Available: {', '.join(PRESETS.keys())}")
            return {}
        presets = {preset_filter: PRESETS[preset_filter]}

    for preset_name, preset_params in presets.items():
        recs = generate_recommendations(races, preset_params, budget=budget)
        all_recommendations[preset_name] = {
            'params': {
                'win_min_ev': preset_params.win_min_ev,
                'win_min_gap': preset_params.win_min_gap,
                'win_min_rating': preset_params.win_min_rating,
                'win_min_ar_deviation': preset_params.win_min_ar_deviation,
                'win_max_rank': preset_params.win_max_rank,
                'win_max_rank_w': preset_params.win_max_rank_w,
                'win_min_win_gap': preset_params.win_min_win_gap,
                'win_max_predicted_margin': preset_params.win_max_predicted_margin,
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
        s = recommendations_summary(recs)
        wide_str = f", Wide={s['wide_bets']}" if s.get('wide_bets') else ""
        print(f"  {preset_name}: {s['total_bets']} bets, "
              f"Win={s['win_bets']}, Place={s['place_bets']}{wide_str}, "
              f"Amount={s['total_amount']:,}")

    # predictions_data に書き込み
    predictions_data['recommendations'] = all_recommendations
    predictions_data['predict_only'] = False
    predictions_data['bets_generated_at'] = datetime.now().isoformat(timespec='seconds')

    # マルチレグ推奨生成
    multi_leg_output = []
    try:
        from ml.simulate_multi_leg import generate_recommendations as gen_multi_leg
        multi_leg_recs = gen_multi_leg(races)
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
        print(f"\n[MultiLeg] {len(multi_leg_output)} tickets across "
              f"{len(set(r.race_id for r in multi_leg_recs))} races")
    except Exception as e:
        print(f"  [Warning] multi-leg generation failed: {e}")

    predictions_data['multi_leg_recommendations'] = multi_leg_output

    return all_recommendations


def main():
    parser = argparse.ArgumentParser(
        description='Generate Bets - predictions.jsonから買い目を生成'
    )
    parser.add_argument('--date', help='対象日 (YYYY-MM-DD)')
    parser.add_argument('--today', action='store_true', help='今日の日付を使用')
    parser.add_argument('--budget', type=int, default=30000, help='予算 (default: 30000)')
    parser.add_argument('--preset', choices=list(PRESETS.keys()),
                        help='特定プリセットのみ生成')
    args = parser.parse_args()

    if args.today:
        args.date = datetime.now().strftime('%Y-%m-%d')
    if not args.date:
        parser.error('--date YYYY-MM-DD or --today is required')

    t0 = time.time()

    print(f"\n{'='*60}")
    print(f"  Generate Bets - 買い目生成")
    print(f"  Date:   {args.date}")
    print(f"  Budget: {args.budget:,}")
    if args.preset:
        print(f"  Preset: {args.preset}")
    print(f"{'='*60}\n")

    # predictions読み込み
    predictions_data = load_predictions(args.date)
    races = predictions_data.get('races', [])
    print(f"[Load] {len(races)} races for {args.date}")
    print(f"  Model: v{predictions_data.get('model_version', '?')}")

    # 買い目生成
    print(f"\n[BetEngine] Generating recommendations...")
    apply_bet_engine(predictions_data, budget=args.budget, preset_filter=args.preset)

    # 保存
    out_json = json.dumps(predictions_data, ensure_ascii=False, indent=2)
    date_parts = args.date.split('-')
    out_path = (config.races_dir() / date_parts[0] / date_parts[1]
                / date_parts[2] / "predictions.json")
    out_path.write_text(out_json, encoding='utf-8')

    elapsed = time.time() - t0
    print(f"\n[Summary]")
    print(f"  Output:  {out_path}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
