#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
VBリフレッシュ: 実行時オッズでValueBet/買い目を再計算

races/YYYY/MM/DD/predictions.json のML予測結果を維持しつつ、
最新のmykeibadbオッズでVB gap/EV/is_value_bet/買い目を再計算する。

Usage:
    python -m ml.vb_refresh --date 2026-02-28
    python -m ml.vb_refresh --today
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from ml.bet_engine import (
    PRESETS, generate_recommendations,
    recommendations_to_dict, recommendations_summary,
    VB_FLOOR_MIN_WIN_EV, VB_FLOOR_MIN_ARD,
    VB_FLOOR_ARD_VB_MIN_ARD, VB_FLOOR_ARD_VB_MIN_ODDS,
)


def load_predictions(date: str) -> dict:
    """日別アーカイブ races/YYYY/MM/DD/predictions.json を読み込み"""
    date_parts = date.split('-')
    pred_path = config.races_dir() / date_parts[0] / date_parts[1] / date_parts[2] / "predictions.json"
    if not pred_path.exists():
        raise FileNotFoundError(f"predictions.json not found: {pred_path}")

    with open(pred_path, encoding='utf-8') as f:
        data = json.load(f)

    return data


def refresh_race_vb(race: dict, db_odds: Dict[int, dict],
                    db_place_odds: Dict[int, dict]) -> int:
    """1レースのVB関連フィールドを最新オッズで更新

    Returns:
        VB数
    """
    entries = race.get('entries', [])
    if not entries:
        return 0

    # オッズ更新
    for entry in entries:
        umaban = entry.get('umaban', 0)

        # 単勝オッズ更新
        if umaban in db_odds:
            new_odds = db_odds[umaban].get('odds', entry.get('odds', 0))
            entry['odds'] = new_odds
        else:
            new_odds = entry.get('odds', 0)

        # 複勝オッズ更新
        if umaban in db_place_odds:
            entry['place_odds_min'] = db_place_odds[umaban].get('odds_low')
            entry['place_odds_max'] = db_place_odds[umaban].get('odds_high')

    # odds_rank 再計算（オッズ昇順で1から付番）
    valid_entries = [(i, e) for i, e in enumerate(entries)
                     if e.get('odds', 0) > 0]
    valid_entries.sort(key=lambda x: x[1]['odds'])
    for rank, (i, e) in enumerate(valid_entries, 1):
        entries[i]['odds_rank'] = rank
    # オッズなし馬は odds_rank=0
    for e in entries:
        if e.get('odds', 0) <= 0:
            e['odds_rank'] = 0

    # VB gap, EV, is_value_bet 再計算
    vb_count = 0
    for entry in entries:
        odds_rank = entry.get('odds_rank', 0)
        rank_p = entry.get('rank_p', 0)
        rank_w = entry.get('rank_w')

        # VB gap
        entry['vb_gap'] = int(odds_rank - rank_p) if odds_rank > 0 else 0

        # Win VB gap
        entry['win_vb_gap'] = (
            int(odds_rank - rank_w) if rank_w and odds_rank > 0 else 0
        )

        # EV再計算
        pred_w_cal = entry.get('pred_proba_w_cal')
        odds = entry.get('odds', 0)
        if pred_w_cal and odds > 0:
            entry['win_ev'] = round(pred_w_cal * odds, 4)
        else:
            entry['win_ev'] = None

        pred_p_raw = entry.get('pred_proba_p_raw')
        place_low = entry.get('place_odds_min')
        if pred_p_raw and place_low and place_low > 0:
            entry['place_ev'] = round(pred_p_raw * place_low, 4)
        else:
            entry['place_ev'] = None

        # VB Floor判定
        ev_ok = (entry.get('win_ev') or 0) >= VB_FLOOR_MIN_WIN_EV
        ard_ok = (entry.get('ar_deviation') or 0) >= VB_FLOOR_MIN_ARD
        ard_vb_ok = (
            (entry.get('ar_deviation') or 0) >= VB_FLOOR_ARD_VB_MIN_ARD
            and (entry.get('odds') or 0) >= VB_FLOOR_ARD_VB_MIN_ODDS
        )
        entry['is_value_bet'] = bool((ev_ok and ard_ok) or ard_vb_ok)
        if entry['is_value_bet']:
            vb_count += 1

    return vb_count


def main():
    parser = argparse.ArgumentParser(description='VB Refresh - 最新オッズでVB/買い目再計算')
    parser.add_argument('--date', help='対象日 (YYYY-MM-DD)')
    parser.add_argument('--today', action='store_true', help='今日の日付を使用')
    args = parser.parse_args()

    if args.today:
        args.date = datetime.now().strftime('%Y-%m-%d')
    if not args.date:
        parser.error('--date YYYY-MM-DD or --today is required')

    t0 = time.time()

    print(f"\n{'='*60}")
    print(f"  VB Refresh - 最新オッズで再計算")
    print(f"{'='*60}\n")

    # predictions読み込み
    date = args.date
    predictions_data = load_predictions(date)

    races = predictions_data.get('races', [])
    if not races:
        print(f"No races in predictions.json for {date}")
        return

    print(f"[Load] {len(races)} races for {date}")
    print(f"  Model: v{predictions_data.get('model_version', '?')}")
    print(f"  Original odds: {predictions_data.get('odds_source', '?')}")
    prev_predict_only = predictions_data.get('predict_only', False)
    if prev_predict_only:
        print(f"  Status: predict_only (VB未計算)")

    # 最新DBオッズ取得
    db_odds_index = {}
    db_place_odds_index = {}
    try:
        from core.odds_db import batch_get_pre_race_odds, batch_get_place_odds, is_db_available
        if is_db_available():
            race_codes = [r['race_id'] for r in races]
            db_odds_index = batch_get_pre_race_odds(race_codes)
            db_place_odds_index = batch_get_place_odds(race_codes)
            print(f"[DB Odds] Win: {len(db_odds_index)}/{len(races)}, "
                  f"Place: {len(db_place_odds_index)}/{len(races)} races")
        else:
            print("[DB Odds] mykeibadb not available, keeping existing odds")
    except Exception as e:
        print(f"[DB Odds] Error: {e}, keeping existing odds")

    # VBリフレッシュ
    print(f"\n[VB Refresh] Recalculating VB/EV with latest odds...")
    total_vb = 0
    for race in races:
        race_id = race.get('race_id', '')
        db_odds = db_odds_index.get(race_id, {})
        db_place_odds = db_place_odds_index.get(race_id, {})
        vb = refresh_race_vb(race, db_odds, db_place_odds)
        total_vb += vb

        venue = race.get('venue_name', '?')
        rn = race.get('race_number', '?')
        entries = race.get('entries', [])
        top1 = entries[0] if entries else None
        top1_name = top1['horse_name'] if top1 else '?'
        vb_marker = f' [VB={vb}]' if vb > 0 else ''
        print(f"  {venue}{rn}R: Top1={top1_name}{vb_marker}")

    # 買い目推奨再生成 (bet_engine)
    print(f"\n[BetEngine] Generating recommendations...")
    all_recommendations = {}
    for preset_name, preset_params in PRESETS.items():
        recs = generate_recommendations(races, preset_params, budget=30000)
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
            },
            'bets': recommendations_to_dict(recs),
            'summary': recommendations_summary(recs),
        }
        s = recommendations_summary(recs)
        print(f"  {preset_name}: {s['total_bets']} bets, "
              f"Win={s['win_bets']}, Place={s['place_bets']}, "
              f"Amount={s['total_amount']:,}")

    # マルチレグ推奨再生成
    print(f"\n[MultiLeg] Generating multi-leg recommendations...")
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
        print(f"  {len(multi_leg_output)} tickets across "
              f"{len(set(r.race_id for r in multi_leg_recs))} races")
    except Exception as e:
        print(f"  [Warning] multi-leg generation failed: {e}")

    # 結果更新
    predictions_data['recommendations'] = all_recommendations
    predictions_data['multi_leg_recommendations'] = multi_leg_output
    predictions_data['predict_only'] = False
    predictions_data['vb_refreshed_at'] = datetime.now().isoformat(timespec='seconds')
    predictions_data['summary']['value_bets'] = total_vb
    predictions_data['summary']['ev_positive_win'] = sum(
        1 for p in races for e in p.get('entries', [])
        if (e.get('win_ev') or 0) > 1.0
    )
    predictions_data['summary']['ev_positive_place'] = sum(
        1 for p in races for e in p.get('entries', [])
        if (e.get('place_ev') or 0) > 1.0
    )

    # 保存（日別アーカイブのみ）
    out_json = json.dumps(predictions_data, ensure_ascii=False, indent=2)

    date_parts = date.split('-')
    out_path = config.races_dir() / date_parts[0] / date_parts[1] / date_parts[2] / "predictions.json"
    out_path.write_text(out_json, encoding='utf-8')

    elapsed = time.time() - t0

    print(f"\n[Summary]")
    print(f"  Races:      {len(races)}")
    print(f"  Value Bets: {total_vb}")
    print(f"  Output:     {out_path}")
    print(f"  Elapsed:    {elapsed:.1f}s")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
