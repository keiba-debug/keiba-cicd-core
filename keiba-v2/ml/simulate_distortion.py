#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
三連単 Distortion戦略 バックテスト + バンクロールシミュレーション

H5b発見に基づく購入戦略:
  条件: FavOdds < 3.0 AND ConfGap < 0.10
  購入: Harville歪み率 2.0-3.0 の組み合わせ上位N点

Usage:
    python -m ml.simulate_distortion
    python -m ml.simulate_distortion --top-n 10
    python -m ml.simulate_distortion --dist-min 1.5 --dist-max 4.0
"""

import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from core.db import get_connection


# ===========================================================================
# Data loading (reuse from analyze_sanrentan_distortion)
# ===========================================================================

def _pi(s) -> int:
    try:
        return int(str(s).strip())
    except (ValueError, TypeError):
        return 0


def load_o6_odds(race_codes: List[str]) -> Dict[str, Dict[Tuple[int, int, int], float]]:
    result = {}
    batch_size = 100
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        for start in range(0, len(race_codes), batch_size):
            batch = race_codes[start:start + batch_size]
            placeholders = ",".join(["%s"] * len(batch))
            sql = (f"SELECT RACE_CODE, KUMIBAN, ODDS "
                   f"FROM odds6_sanrentan "
                   f"WHERE RACE_CODE IN ({placeholders})")
            cur.execute(sql, batch)
            for row in cur.fetchall():
                rc = row["RACE_CODE"].strip()
                kumiban = str(row["KUMIBAN"]).strip()
                try:
                    u1 = int(kumiban[0:2])
                    u2 = int(kumiban[2:4])
                    u3 = int(kumiban[4:6])
                    odds = float(row["ODDS"]) / 10.0
                except (ValueError, TypeError, IndexError):
                    continue
                if odds <= 0:
                    continue
                if rc not in result:
                    result[rc] = {}
                result[rc][(u1, u2, u3)] = odds
    return result


def load_sanrentan_payouts(race_codes: List[str]) -> Dict[str, List[Tuple]]:
    result = {}
    batch_size = 500
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        for start in range(0, len(race_codes), batch_size):
            batch = race_codes[start:start + batch_size]
            placeholders = ",".join(["%s"] * len(batch))
            cols = ["RACE_CODE", "FUSEIRITSU_FLAG_SANRENTAN"]
            for i in range(1, 7):
                cols.extend([
                    f"SANRENTAN{i}_KUMIBAN1",
                    f"SANRENTAN{i}_KUMIBAN2",
                    f"SANRENTAN{i}_KUMIBAN3",
                    f"SANRENTAN{i}_HARAIMODOSHIKIN",
                ])
            sql = (f"SELECT {', '.join(cols)} FROM haraimodoshi "
                   f"WHERE RACE_CODE IN ({placeholders})")
            cur.execute(sql, batch)
            for row in cur.fetchall():
                rc = row["RACE_CODE"].strip()
                if (row.get("FUSEIRITSU_FLAG_SANRENTAN", "0") or "0") == "1":
                    continue
                payouts = []
                for i in range(1, 7):
                    k1 = _pi(row.get(f"SANRENTAN{i}_KUMIBAN1", ""))
                    k2 = _pi(row.get(f"SANRENTAN{i}_KUMIBAN2", ""))
                    k3 = _pi(row.get(f"SANRENTAN{i}_KUMIBAN3", ""))
                    pay = _pi(row.get(f"SANRENTAN{i}_HARAIMODOSHIKIN", ""))
                    if k1 and k2 and k3 and pay:
                        payouts.append(((k1, k2, k3), pay))
                if payouts:
                    result[rc] = payouts
    return result


def harville_prob(probs: Dict[int, float], first: int, second: int, third: int) -> float:
    p1 = probs.get(first, 0)
    if p1 <= 0:
        return 0
    remaining = {k: v for k, v in probs.items() if k != first}
    total_r1 = sum(remaining.values())
    if total_r1 <= 0:
        return 0
    p2 = remaining.get(second, 0) / total_r1
    remaining2 = {k: v for k, v in remaining.items() if k != second}
    total_r2 = sum(remaining2.values())
    if total_r2 <= 0:
        return 0
    p3 = remaining2.get(third, 0) / total_r2
    return p1 * p2 * p3


def load_predictions_with_results() -> List[dict]:
    races_dir = config.races_dir()
    results = []
    for pred_path in sorted(races_dir.glob("**/predictions.json")):
        try:
            with open(pred_path, encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            continue
        races_list = data.get('races', []) if isinstance(data, dict) else data
        if isinstance(races_list, str):
            continue
        for race in races_list:
            if not isinstance(race, dict):
                continue
            if race.get('track_type') == 'obstacle':
                continue
            entries = race.get('entries', [])
            if not entries or len(entries) < 6:
                continue
            race_id = race.get('race_id', '')
            date_str = race.get('date', '')
            if not date_str:
                continue
            parts = date_str.split('-')
            if len(parts) != 3:
                continue
            race_json_path = (races_dir / parts[0] / parts[1] / parts[2]
                              / f"race_{race_id}.json")
            try:
                with open(race_json_path, encoding='utf-8') as f:
                    race_data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                continue
            actual_map = {}
            for e in race_data.get('entries', []):
                uma = e.get('umaban', 0)
                fp = e.get('finish_position', 0)
                if uma > 0 and fp > 0:
                    actual_map[uma] = fp
            if len(actual_map) < 3:
                continue
            for e in entries:
                e['actual_finish'] = actual_map.get(e.get('umaban', 0), 0)
            race['actual_map'] = actual_map
            results.append(race)
    return results


# ===========================================================================
# Strategy
# ===========================================================================

@dataclass
class DayResult:
    date: str
    races_total: int = 0
    races_fired: int = 0
    bets: int = 0
    invested: int = 0
    returned: int = 0
    hits: int = 0
    hit_details: list = field(default_factory=list)


def run_strategy(races: list, o6_odds: dict, payouts: dict,
                 dist_min: float = 2.0, dist_max: float = 3.0,
                 top_n: int = 5,
                 fav_odds_max: float = 3.0,
                 conf_gap_max: float = 0.10,
                 require_model_top3: bool = False) -> List[DayResult]:
    """歪み率戦略の日別バックテスト"""

    day_results = {}

    for race in races:
        entries = race.get('entries', [])
        rid = race['race_id']
        date = race.get('date', '')

        if rid not in o6_odds or rid not in payouts:
            continue

        if date not in day_results:
            day_results[date] = DayResult(date=date)
        dr = day_results[date]
        dr.races_total += 1

        # --- レースフィルター ---
        by_rp = sorted(entries, key=lambda e: e.get('rank_p') or 99)
        if len(by_rp) < 3:
            continue

        p1_prob = by_rp[0].get('pred_proba_p', 0) or 0
        p2_prob = by_rp[1].get('pred_proba_p', 0) or 0
        conf_gap = p1_prob - p2_prob

        by_odds = sorted(entries, key=lambda e: float(e.get('odds', 999) or 999))
        fav_odds = float(by_odds[0].get('odds', 0) or 0) if by_odds else 0

        if fav_odds >= fav_odds_max:
            continue
        if conf_gap >= conf_gap_max:
            continue

        # --- モデル勝率 ---
        win_probs = {}
        for e in entries:
            uma = e.get('umaban', 0)
            pw = e.get('pred_proba_w_cal') or e.get('pred_proba_w', 0) or 0
            if uma > 0 and pw > 0:
                win_probs[uma] = pw
        total = sum(win_probs.values())
        if total <= 0:
            continue
        win_probs = {k: v / total for k, v in win_probs.items()}

        # --- 歪み率計算 ---
        race_o6 = o6_odds[rid]
        combo_data = []
        for combo, odds_val in race_o6.items():
            if odds_val <= 0:
                continue
            u1, u2, u3 = combo
            h_prob = harville_prob(win_probs, u1, u2, u3)
            market_implied = 1.0 / odds_val
            if market_implied <= 0:
                continue
            distortion = h_prob / market_implied

            if distortion < dist_min or distortion >= dist_max:
                continue

            # オプション: 1着馬がモデルrank_w Top3に限定
            if require_model_top3:
                by_rw = sorted(entries, key=lambda e: e.get('rank_w') or 99)
                rw_top3 = set(e.get('umaban') for e in by_rw[:3])
                if u1 not in rw_top3:
                    continue

            combo_data.append((combo, distortion, odds_val))

        if not combo_data:
            continue

        # 歪み率降順でTop N
        combo_data.sort(key=lambda x: -x[1])
        selected = combo_data[:top_n]

        dr.races_fired += 1

        # --- 的中判定 ---
        actual_map = race.get('actual_map', {})
        first = second = third = None
        for uma, pos in actual_map.items():
            if pos == 1: first = uma
            elif pos == 2: second = uma
            elif pos == 3: third = uma
        winning_combo = (first, second, third) if all([first, second, third]) else None

        winning_payout = 0
        if winning_combo:
            for combo, pay in payouts[rid]:
                if combo == winning_combo:
                    winning_payout = pay
                    break

        for combo, dist, odds_val in selected:
            dr.bets += 1
            dr.invested += 100
            if winning_combo and combo == winning_combo and winning_payout > 0:
                dr.returned += winning_payout
                dr.hits += 1
                dr.hit_details.append({
                    'race_id': rid,
                    'combo': combo,
                    'distortion': dist,
                    'payout': winning_payout,
                    'odds': odds_val,
                })

    return sorted(day_results.values(), key=lambda d: d.date)


def simulate_bankroll(day_results: List[DayResult],
                      initial: int = 100_000,
                      bet_pct: float = 0.01) -> dict:
    """バンクロールシミュレーション"""
    bankroll = initial
    peak = initial
    max_dd = 0
    history = []
    total_bets = 0
    total_invested = 0
    total_returned = 0
    total_hits = 0
    win_days = 0
    lose_days = 0

    for dr in day_results:
        if dr.bets == 0:
            continue

        day_bet_unit = max(100, int(bankroll * bet_pct / 100) * 100)
        day_invested = dr.bets * day_bet_unit
        day_returned = 0

        for hd in dr.hit_details:
            day_returned += int(day_bet_unit / 100 * hd['payout'])

        bankroll = bankroll - day_invested + day_returned
        total_bets += dr.bets
        total_invested += day_invested
        total_returned += day_returned
        total_hits += dr.hits

        if bankroll > peak:
            peak = bankroll
        dd = (peak - bankroll) / peak * 100 if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

        if day_returned > day_invested:
            win_days += 1
        elif day_returned < day_invested:
            lose_days += 1

        history.append({
            'date': dr.date,
            'bankroll': bankroll,
            'bets': dr.bets,
            'invested': day_invested,
            'returned': day_returned,
            'hits': dr.hits,
        })

    flat_roi = total_returned / total_invested * 100 if total_invested > 0 else 0

    return {
        'initial': initial,
        'final': bankroll,
        'roi_pct': round((bankroll - initial) / initial * 100, 1),
        'flat_roi': round(flat_roi, 1),
        'max_dd': round(max_dd, 1),
        'total_bets': total_bets,
        'total_invested': total_invested,
        'total_returned': total_returned,
        'total_hits': total_hits,
        'hit_rate': round(total_hits / total_bets * 100, 2) if total_bets > 0 else 0,
        'win_days': win_days,
        'lose_days': lose_days,
        'days': len(history),
        'history': history,
    }


# ===========================================================================
# Main
# ===========================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--top-n', type=int, default=5)
    parser.add_argument('--dist-min', type=float, default=2.0)
    parser.add_argument('--dist-max', type=float, default=3.0)
    parser.add_argument('--fav-max', type=float, default=3.0)
    parser.add_argument('--cg-max', type=float, default=0.10)
    parser.add_argument('--model-top3', action='store_true')
    args = parser.parse_args()

    print("=" * 70)
    print("  三連単 Distortion戦略 バックテスト")
    print(f"  歪み率: {args.dist_min}-{args.dist_max} | Top {args.top_n}点")
    print(f"  FavOdds < {args.fav_max} | ConfGap < {args.cg_max}")
    if args.model_top3:
        print(f"  1着: rank_w Top3限定")
    print("=" * 70)

    # Load data
    print("\n[1] Loading predictions...")
    races = load_predictions_with_results()
    print(f"  {len(races)} flat races")

    race_codes = [r['race_id'] for r in races]

    print("[2] Loading O6 odds...")
    o6 = load_o6_odds(race_codes)
    print(f"  {len(o6)} races with O6")

    print("[3] Loading payouts...")
    pays = load_sanrentan_payouts(race_codes)
    print(f"  {len(pays)} races with payouts")

    # Run strategy
    print("\n[4] Running strategy...")
    day_results = run_strategy(
        races, o6, pays,
        dist_min=args.dist_min,
        dist_max=args.dist_max,
        top_n=args.top_n,
        fav_odds_max=args.fav_max,
        conf_gap_max=args.cg_max,
        require_model_top3=args.model_top3,
    )

    # Summary
    total_races = sum(d.races_total for d in day_results)
    fired_races = sum(d.races_fired for d in day_results)
    total_bets = sum(d.bets for d in day_results)
    total_invested = sum(d.invested for d in day_results)
    total_returned = sum(d.returned for d in day_results)
    total_hits = sum(d.hits for d in day_results)
    flat_roi = total_returned / total_invested * 100 if total_invested > 0 else 0

    print(f"\n  レース: {total_races} → フィルター通過: {fired_races} ({fired_races / total_races * 100:.1f}%)")
    print(f"  買い点: {total_bets:,} (avg {total_bets / fired_races:.1f}点/R)" if fired_races else "  買い点: 0")
    print(f"  的中: {total_hits} ({total_hits / total_bets * 100:.2f}%)" if total_bets else "  的中: 0")
    print(f"  Flat ROI: {flat_roi:.1f}%")
    print(f"  投資: ¥{total_invested:,} → 回収: ¥{total_returned:,}")

    if total_hits > 0:
        avg_pay = total_returned / total_hits
        print(f"  平均配当: ¥{int(avg_pay):,}")

    # 的中レース一覧
    all_hits = []
    for d in day_results:
        all_hits.extend(d.hit_details)

    if all_hits:
        print(f"\n  {'日付':>10} {'race_id':>18} {'歪み率':>6} {'配当':>8}")
        print("  " + "-" * 50)
        for h in sorted(all_hits, key=lambda x: x['race_id']):
            date = h['race_id'][:4] + '-' + h['race_id'][4:6] + '-' + h['race_id'][6:8]
            print(f"  {date:>10} {h['race_id']:>18} {h['distortion']:>6.2f} ¥{h['payout']:>8,}")

    # Bankroll simulation
    print("\n" + "=" * 70)
    print("  バンクロールシミュレーション")
    print("=" * 70)

    for pct_label, pct in [('1%', 0.01), ('2%', 0.02), ('3%', 0.03), ('5%', 0.05), ('flat100', 0)]:
        if pct == 0:
            # flat 100 mode
            sim = simulate_bankroll(day_results, initial=100_000, bet_pct=0)
            # Override: flat 100 = just use flat amounts
            bankroll = 100_000
            peak = 100_000
            max_dd = 0
            for dr in day_results:
                if dr.bets == 0:
                    continue
                day_inv = dr.bets * 100
                day_ret = 0
                for hd in dr.hit_details:
                    day_ret += hd['payout']
                bankroll += day_ret - day_inv
                if bankroll > peak:
                    peak = bankroll
                dd = (peak - bankroll) / peak * 100 if peak > 0 else 0
                if dd > max_dd:
                    max_dd = dd
            roi_pct = (bankroll - 100_000) / 100_000 * 100
            print(f"  {pct_label:>6} | Final {bankroll:>10,} | ROI {roi_pct:>+7.1f}% | "
                  f"Flat {flat_roi:>5.1f}% | DD {max_dd:>5.1f}%")
        else:
            sim = simulate_bankroll(day_results, initial=100_000, bet_pct=pct)
            marker = ' ***' if sim['final'] > 100_000 else ''
            print(f"  {pct_label:>6} | Final {sim['final']:>10,} | ROI {sim['roi_pct']:>+7.1f}% | "
                  f"Flat {sim['flat_roi']:>5.1f}% | DD {sim['max_dd']:>5.1f}%{marker}")

    # Variant strategies
    print("\n" + "=" * 70)
    print("  バリエーション比較")
    print("=" * 70)

    variants = [
        ('Base(2-3,T5)', {'dist_min': 2.0, 'dist_max': 3.0, 'top_n': 5}),
        ('Wide(1.5-3,T5)', {'dist_min': 1.5, 'dist_max': 3.0, 'top_n': 5}),
        ('Narrow(2-3,T3)', {'dist_min': 2.0, 'dist_max': 3.0, 'top_n': 3}),
        ('Big(2-3,T10)', {'dist_min': 2.0, 'dist_max': 3.0, 'top_n': 10}),
        ('High(2.5-3,T5)', {'dist_min': 2.5, 'dist_max': 3.0, 'top_n': 5}),
        ('Wider(2-4,T5)', {'dist_min': 2.0, 'dist_max': 4.0, 'top_n': 5}),
        ('NoFilter(2-3,T5)', {'dist_min': 2.0, 'dist_max': 3.0, 'top_n': 5,
                              'fav_odds_max': 99, 'conf_gap_max': 99}),
        ('FO<4(2-3,T5)', {'dist_min': 2.0, 'dist_max': 3.0, 'top_n': 5,
                          'fav_odds_max': 4.0}),
        ('RwTop3(2-3,T5)', {'dist_min': 2.0, 'dist_max': 3.0, 'top_n': 5,
                            'require_model_top3': True}),
        ('CG05(2-3,T5)', {'dist_min': 2.0, 'dist_max': 3.0, 'top_n': 5,
                          'conf_gap_max': 0.05}),
    ]

    print(f"\n  {'戦略':>20} {'発動R':>6} {'買い点':>7} {'的中':>4} {'Flat ROI':>9} {'3% Final':>10}")
    print("  " + "-" * 65)

    for name, params in variants:
        v_day = run_strategy(
            races, o6, pays,
            dist_min=params.get('dist_min', 2.0),
            dist_max=params.get('dist_max', 3.0),
            top_n=params.get('top_n', 5),
            fav_odds_max=params.get('fav_odds_max', args.fav_max),
            conf_gap_max=params.get('conf_gap_max', args.cg_max),
            require_model_top3=params.get('require_model_top3', False),
        )
        v_bets = sum(d.bets for d in v_day)
        v_inv = sum(d.invested for d in v_day)
        v_ret = sum(d.returned for d in v_day)
        v_hits = sum(d.hits for d in v_day)
        v_fired = sum(d.races_fired for d in v_day)
        v_roi = v_ret / v_inv * 100 if v_inv > 0 else 0
        v_sim = simulate_bankroll(v_day, 100_000, 0.03)
        marker = ' ★' if v_roi > 150 else ' ▲' if v_roi > 100 else ''
        print(f"  {name:>20} {v_fired:>6} {v_bets:>7,} {v_hits:>4} {v_roi:>8.1f}% {v_sim['final']:>10,}{marker}")

    print("\n  Done.")


if __name__ == '__main__':
    main()
