#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
買い目生成スクリプト（推論結果から独立実行）

predictions.json のML推論結果を読み込み、bet_engine で買い目を生成。
predict.py とは独立して実行可能 → 戦略パラメータ変更時に推論やり直し不要。

Output:
    predictions.json → ML分析のみ（betting data削除）
    bets.json        → 買い目データ（recommendations, multi_leg, sanrentan）

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
    generate_adaptive_recommendations, ADAPTIVE_RULES, apply_adaptive_kelly,
    recommendations_to_dict, recommendations_summary,
    apply_kelly_sizing,
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


def get_bets_path(date: str) -> Path:
    """bets.json のパスを取得"""
    date_parts = date.split('-')
    return (config.races_dir() / date_parts[0] / date_parts[1]
            / date_parts[2] / "bets.json")


def save_bets(date: str, bets_data: dict) -> Path:
    """bets.json に買い目データを書き込み"""
    out_path = get_bets_path(date)
    out_json = json.dumps(bets_data, ensure_ascii=False, indent=2)
    out_path.write_text(out_json, encoding='utf-8')
    return out_path


def apply_bet_engine(
    predictions_data: dict,
    budget: int = 30000,
    preset_filter: Optional[str] = None,
    bankroll: int = 100000,
) -> dict:
    """predictions_data から買い目を生成し、bets_data dict を返す

    Args:
        predictions_data: predictions.json のデータ（変更しない）
        budget: 予算
        preset_filter: 特定プリセットのみ生成（None=全プリセット）

    Returns:
        bets_data dict（bets.json に書き込む内容）
    """
    races = predictions_data.get('races', [])
    if not races:
        print("[Warning] No races in predictions data")
        return _empty_bets_data(predictions_data)

    all_recommendations = {}

    # ── ライブ margin 補正 ──
    LIVE_MARGIN_OFFSET = 16
    import copy as _copy
    live_presets = {}
    for k, v in PRESETS.items():
        p = _copy.copy(v)
        if p.win_max_predicted_margin > 0 and p.win_max_predicted_margin < 900:
            p.win_max_predicted_margin += LIVE_MARGIN_OFFSET
        live_presets[k] = p
    live_adaptive_rules = []
    for r in ADAPTIVE_RULES:
        r2 = _copy.copy(r)
        if r2.max_predicted_margin < 900:
            r2.max_predicted_margin += LIVE_MARGIN_OFFSET
        live_adaptive_rules.append(r2)

    available_presets = list(PRESETS.keys()) + ['adaptive']

    presets = live_presets
    if preset_filter:
        if preset_filter not in available_presets:
            print(f"[Error] Unknown preset: {preset_filter}. "
                  f"Available: {', '.join(available_presets)}")
            return _empty_bets_data(predictions_data)
        if preset_filter == 'adaptive':
            presets = {}
        else:
            presets = {preset_filter: live_presets[preset_filter]}

    for preset_name, preset_params in presets.items():
        recs = generate_recommendations(races, preset_params, budget=budget)
        recs = apply_kelly_sizing(recs, bankroll=bankroll)
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
        umaren_str = f", Umaren={s['umaren_bets']}" if s.get('umaren_bets') else ""
        umatan_str = f", Umatan={s['umatan_bets']}" if s.get('umatan_bets') else ""
        print(f"  {preset_name}: {s['total_bets']} bets, "
              f"Win={s['win_bets']}, Place={s['place_bets']}{wide_str}{umaren_str}{umatan_str}, "
              f"Amount={s['total_amount']:,}")

    # --- adaptive プリセット ---
    if not preset_filter or preset_filter == 'adaptive':
        relaxed_params = live_presets['relaxed']
        adaptive_recs = generate_recommendations(races, relaxed_params, budget=budget)
        adaptive_recs = apply_adaptive_kelly(adaptive_recs, races, live_adaptive_rules)
        adaptive_recs = apply_kelly_sizing(adaptive_recs, bankroll=bankroll)
        all_recommendations['adaptive'] = {
            'params': {
                'type': 'adaptive',
                'base_preset': 'relaxed',
                'rules': [r.name for r in live_adaptive_rules],
            },
            'bets': recommendations_to_dict(adaptive_recs),
            'summary': recommendations_summary(adaptive_recs),
        }
        s = recommendations_summary(adaptive_recs)
        wide_str = f", Wide={s['wide_bets']}" if s.get('wide_bets') else ""
        umaren_str = f", Umaren={s['umaren_bets']}" if s.get('umaren_bets') else ""
        umatan_str = f", Umatan={s['umatan_bets']}" if s.get('umatan_bets') else ""
        print(f"  adaptive: {s['total_bets']} bets, "
              f"Win={s['win_bets']}, Place={s['place_bets']}{wide_str}{umaren_str}{umatan_str}, "
              f"Amount={s['total_amount']:,}")

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

    # 三連単フォーメーション推奨生成
    sanrentan_output = []
    try:
        from ml.simulate_multi_leg import generate_sanrentan_formation
        san_recs = generate_sanrentan_formation(races)
        for r in san_recs:
            sanrentan_output.append({
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
        n_races = len(set(r.race_id for r in san_recs)) if san_recs else 0
        print(f"[Sanrentan] {len(sanrentan_output)} tickets across {n_races} races")
    except Exception as e:
        print(f"  [Warning] sanrentan formation failed: {e}")

    # bets_data を構築
    bets_data = {
        'date': predictions_data.get('date', ''),
        'model_version': predictions_data.get('model_version', ''),
        'bets_generated_at': datetime.now().isoformat(timespec='seconds'),
        'budget': budget,
        'bankroll': bankroll,
        'recommendations': all_recommendations,
        'multi_leg_recommendations': multi_leg_output,
        'sanrentan_formation': sanrentan_output,
    }

    return bets_data


def _empty_bets_data(predictions_data: dict) -> dict:
    return {
        'date': predictions_data.get('date', ''),
        'model_version': predictions_data.get('model_version', ''),
        'bets_generated_at': datetime.now().isoformat(timespec='seconds'),
        'recommendations': {},
        'multi_leg_recommendations': [],
        'sanrentan_formation': [],
    }


def strip_betting_fields(predictions_data: dict):
    """predictions.json から betting 関連フィールドを除去"""
    for key in ('recommendations', 'multi_leg_recommendations',
                'sanrentan_formation', 'bets_generated_at', 'predict_only'):
        predictions_data.pop(key, None)


def main():
    parser = argparse.ArgumentParser(
        description='Generate Bets - predictions.jsonから買い目を生成'
    )
    parser.add_argument('--date', help='対象日 (YYYY-MM-DD)')
    parser.add_argument('--today', action='store_true', help='今日の日付を使用')
    parser.add_argument('--budget', type=int, default=30000, help='予算 (default: 30000)')
    parser.add_argument('--preset', choices=list(PRESETS.keys()) + ['adaptive'],
                        help='特定プリセットのみ生成')
    parser.add_argument('--bankroll', type=int, default=100000,
                        help='バンクロール (Kelly推奨額計算用, default: 100000)')
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
    print(f"  Bankroll: {args.bankroll:,} (Kelly sizing)")
    if args.preset:
        print(f"  Preset: {args.preset}")
    print(f"{'='*60}\n")

    # predictions読み込み
    predictions_data = load_predictions(args.date)
    races = predictions_data.get('races', [])
    print(f"[Load] {len(races)} races for {args.date}")
    print(f"  Model: v{predictions_data.get('model_version', '?')}")

    # 買い目生成 → bets.json
    print(f"\n[BetEngine] Generating recommendations...")
    bets_data = apply_bet_engine(predictions_data, budget=args.budget,
                                 preset_filter=args.preset, bankroll=args.bankroll)
    bets_path = save_bets(args.date, bets_data)

    # predictions.json から betting fields を削除して保存
    strip_betting_fields(predictions_data)
    date_parts = args.date.split('-')
    pred_path = (config.races_dir() / date_parts[0] / date_parts[1]
                 / date_parts[2] / "predictions.json")
    pred_json = json.dumps(predictions_data, ensure_ascii=False, indent=2)
    pred_path.write_text(pred_json, encoding='utf-8')

    elapsed = time.time() - t0
    print(f"\n[Summary]")
    print(f"  Predictions: {pred_path}")
    print(f"  Bets:        {bets_path}")
    print(f"  Elapsed:     {elapsed:.1f}s")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
