#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
三連単 Distortion Phase 1: Harville vs 実オッズの歪み分析

O6データ(odds6_sanrentan)から実オッズを読み込み、
Harville推定との乖離パターンを発見する。

検証仮説:
  H1: Harville公式は人気薄の組み合わせを過小評価する（穴馬バイアス）
  H2: 1着人気馬→2着穴馬の馬単型は実オッズが過大に付く（狙い目）
  H3: モデルEV>1の三連単はフォーメーション戦略より高ROI
  H4: ConfGap<0.10 + FavOdds 3-4 のフィルターは実オッズEVでも有効
  H5: Harville歪み率が大きい組み合わせに的中が集中する

Usage:
    python -m ml.analyze_sanrentan_distortion
    python -m ml.analyze_sanrentan_distortion --limit 500
"""

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from core.db import get_connection


# ===========================================================================
# O6 odds loading
# ===========================================================================

def load_o6_odds(race_codes: List[str]) -> Dict[str, Dict[Tuple[int, int, int], float]]:
    """odds6_sanrentan から三連単オッズを読み込み
    Returns: {race_code: {(1着,2着,3着): odds, ...}}
    """
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
                    # KUMIBAN: 6桁 = 2桁×3 (1着2着3着)
                    u1 = int(kumiban[0:2])
                    u2 = int(kumiban[2:4])
                    u3 = int(kumiban[4:6])
                    odds = float(row["ODDS"]) / 10.0  # 10倍値→実オッズ
                except (ValueError, TypeError, IndexError):
                    continue
                if odds <= 0:
                    continue
                if rc not in result:
                    result[rc] = {}
                result[rc][(u1, u2, u3)] = odds

    return result


def load_sanrentan_payouts(race_codes: List[str]) -> Dict[str, List[Tuple]]:
    """haraimodoshiから三連単実配当を取得"""
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


def _pi(s) -> int:
    try:
        return int(str(s).strip())
    except (ValueError, TypeError):
        return 0


# ===========================================================================
# Harville probability
# ===========================================================================

def harville_prob(probs: Dict[int, float], first: int, second: int, third: int) -> float:
    """Harville公式で P(first=1着, second=2着, third=3着) を計算"""
    p1 = probs.get(first, 0)
    if p1 <= 0:
        return 0

    # 1着がfirstの場合の残り馬の確率再分配
    remaining_after_1 = {k: v for k, v in probs.items() if k != first}
    total_r1 = sum(remaining_after_1.values())
    if total_r1 <= 0:
        return 0

    p2_given_1 = remaining_after_1.get(second, 0) / total_r1

    # 2着がsecondの場合の残り馬の確率再分配
    remaining_after_2 = {k: v for k, v in remaining_after_1.items() if k != second}
    total_r2 = sum(remaining_after_2.values())
    if total_r2 <= 0:
        return 0

    p3_given_12 = remaining_after_2.get(third, 0) / total_r2

    return p1 * p2_given_1 * p3_given_12


# ===========================================================================
# Predictions loading
# ===========================================================================

def load_predictions_with_results() -> List[dict]:
    """predictions.json + race JSONから予測+実着順を読み込み"""
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

            # 実着順を取得
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

            # entriesに実着順を付与
            for e in entries:
                e['actual_finish'] = actual_map.get(e.get('umaban', 0), 0)

            race['actual_map'] = actual_map
            results.append(race)

    return results


# ===========================================================================
# Analysis
# ===========================================================================

def analyze(limit: int = 0):
    print("=" * 70)
    print("  三連単 Distortion Phase 1: Harville vs 実オッズ歪み分析")
    print("=" * 70)

    # 1. Load predictions with results
    print("\n[1] Loading predictions...")
    races = load_predictions_with_results()
    print(f"  Loaded {len(races)} flat races with results")

    if limit > 0:
        races = races[-limit:]
        print(f"  Limited to last {limit} races")

    race_codes = [r['race_id'] for r in races]

    # 2. Load O6 odds
    print("\n[2] Loading O6 odds...")
    o6_odds = load_o6_odds(race_codes)
    print(f"  O6 odds: {len(o6_odds)} races")

    # 3. Load actual payouts
    print("\n[3] Loading payouts...")
    payouts = load_sanrentan_payouts(race_codes)
    print(f"  Payouts: {len(payouts)} races")

    # Filter to races with both O6 and payouts
    valid_races = []
    for race in races:
        rid = race['race_id']
        if rid in o6_odds and rid in payouts:
            valid_races.append(race)
    print(f"\n  Valid races (O6 + payouts): {len(valid_races)}")

    if not valid_races:
        print("No valid races found!")
        return

    # =========================================================================
    # H1: Harville vs 実オッズ — 人気帯別の乖離
    # =========================================================================
    print("\n" + "=" * 70)
    print("  H1: Harville推定 vs 実オッズの乖離（人気帯別）")
    print("=" * 70)

    # 各レースで的中組み合わせのHarville確率と実オッズ implied probを比較
    distortion_data = []  # (harville_prob, market_implied_prob, actual_odds, fav_rank)

    for race in valid_races:
        entries = race.get('entries', [])
        rid = race['race_id']

        # Wモデル勝率でHarville
        win_probs = {}
        for e in entries:
            uma = e.get('umaban', 0)
            pw = e.get('pred_proba_w_cal') or e.get('pred_proba_w', 0) or 0
            if uma > 0 and pw > 0:
                win_probs[uma] = pw

        if len(win_probs) < 6:
            continue

        # normalize
        total = sum(win_probs.values())
        if total <= 0:
            continue
        win_probs = {k: v / total for k, v in win_probs.items()}

        # 的中組み合わせを取得
        actual_map = race.get('actual_map', {})
        first = None
        second = None
        third = None
        for uma, pos in actual_map.items():
            if pos == 1:
                first = uma
            elif pos == 2:
                second = uma
            elif pos == 3:
                third = uma

        if not all([first, second, third]):
            continue

        # Harville確率
        h_prob = harville_prob(win_probs, first, second, third)

        # O6 implied prob
        race_o6 = o6_odds.get(rid, {})
        actual_odds = race_o6.get((first, second, third), 0)
        if actual_odds <= 0:
            continue

        market_implied = 1.0 / actual_odds if actual_odds > 0 else 0

        # 人気順位（実オッズベース）
        by_odds = sorted(entries, key=lambda e: float(e.get('odds', 999) or 999))
        fav_ranks = {}
        for i, e in enumerate(by_odds):
            fav_ranks[e.get('umaban', 0)] = i + 1

        first_rank = fav_ranks.get(first, 99)

        distortion_data.append({
            'h_prob': h_prob,
            'market_prob': market_implied,
            'actual_odds': actual_odds,
            'first_rank': first_rank,
            'distortion_ratio': h_prob / market_implied if market_implied > 0 else 0,
            'race_id': rid,
        })

    print(f"\n  分析対象: {len(distortion_data)} レース")

    if not distortion_data:
        print("No distortion data!")
        return

    # 人気帯別の歪み率
    bins = [
        ('1番人気1着', lambda d: d['first_rank'] == 1),
        ('2-3番人気1着', lambda d: 2 <= d['first_rank'] <= 3),
        ('4-6番人気1着', lambda d: 4 <= d['first_rank'] <= 6),
        ('7番人気以下1着', lambda d: d['first_rank'] >= 7),
    ]

    print(f"\n{'カテゴリ':>20} {'N':>5} {'Harville中央値':>14} {'市場中央値':>12} "
          f"{'歪み率中央値':>12} {'歪み>1(H過大)':>12}")
    print("-" * 80)

    for label, filt in bins:
        subset = [d for d in distortion_data if filt(d)]
        if not subset:
            continue
        h_arr = [d['h_prob'] for d in subset]
        m_arr = [d['market_prob'] for d in subset]
        dist_arr = [d['distortion_ratio'] for d in subset]
        over = sum(1 for d in dist_arr if d > 1.0)

        print(f"{label:>20} {len(subset):>5} {np.median(h_arr):>14.6f} "
              f"{np.median(m_arr):>12.6f} {np.median(dist_arr):>12.3f} "
              f"{over:>6}/{len(subset):>3} ({over / len(subset) * 100:.0f}%)")

    # =========================================================================
    # H2: 穴馬1着×人気馬2着の歪み（馬単型distortion）
    # =========================================================================
    print("\n" + "=" * 70)
    print("  H2: 穴馬1着 × 人気馬2着の歪みパターン")
    print("=" * 70)

    # 各的中組み合わせの1着人気 × 2着人気 クロス集計
    cross = defaultdict(lambda: {'count': 0, 'dist_sum': 0.0, 'odds_sum': 0.0})

    for race in valid_races:
        entries = race.get('entries', [])
        rid = race['race_id']
        actual_map = race.get('actual_map', {})

        first = second = third = None
        for uma, pos in actual_map.items():
            if pos == 1: first = uma
            elif pos == 2: second = uma
            elif pos == 3: third = uma

        if not all([first, second, third]):
            continue

        by_odds = sorted(entries, key=lambda e: float(e.get('odds', 999) or 999))
        fav_ranks = {}
        for i, e in enumerate(by_odds):
            fav_ranks[e.get('umaban', 0)] = i + 1

        r1 = fav_ranks.get(first, 99)
        r2 = fav_ranks.get(second, 99)

        # distortion ratio
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

        h_prob = harville_prob(win_probs, first, second, third)
        race_o6 = o6_odds.get(rid, {})
        actual_odds = race_o6.get((first, second, third), 0)
        if actual_odds <= 0:
            continue
        market_implied = 1.0 / actual_odds

        r1_bin = '1' if r1 == 1 else '2-3' if r1 <= 3 else '4-6' if r1 <= 6 else '7+'
        r2_bin = '1' if r2 == 1 else '2-3' if r2 <= 3 else '4-6' if r2 <= 6 else '7+'

        key = (r1_bin, r2_bin)
        cross[key]['count'] += 1
        cross[key]['dist_sum'] += h_prob / market_implied
        cross[key]['odds_sum'] += actual_odds

    print(f"\n{'1着人気':>10} {'2着人気':>10} {'N':>5} {'歪み率平均':>10} {'平均オッズ':>10}")
    print("-" * 55)
    for (r1b, r2b) in sorted(cross.keys()):
        d = cross[(r1b, r2b)]
        n = d['count']
        avg_dist = d['dist_sum'] / n
        avg_odds = d['odds_sum'] / n
        marker = ' ★' if avg_dist < 0.8 else ' ▲' if avg_dist < 0.95 else ''
        print(f"{r1b:>10} {r2b:>10} {n:>5} {avg_dist:>10.3f} {avg_odds:>10,.0f}{marker}")

    # =========================================================================
    # H3: 実オッズEVベースの購入戦略 ROI
    # =========================================================================
    print("\n" + "=" * 70)
    print("  H3: 実オッズEV(モデル確率×実オッズ)ベース購入戦略")
    print("=" * 70)

    ev_results = defaultdict(lambda: {'bets': 0, 'invested': 0, 'returned': 0, 'hits': 0})

    for race in valid_races:
        entries = race.get('entries', [])
        rid = race['race_id']

        # モデル勝率
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

        # 全組み合わせのEV計算
        race_o6 = o6_odds.get(rid, {})
        race_payouts = payouts.get(rid, [])

        # 的中組み合わせ
        actual_map = race.get('actual_map', {})
        first = second = third = None
        for uma, pos in actual_map.items():
            if pos == 1: first = uma
            elif pos == 2: second = uma
            elif pos == 3: third = uma
        if not all([first, second, third]):
            continue

        winning_combo = (first, second, third)
        winning_payout = 0
        for combo, pay in race_payouts:
            if combo == winning_combo:
                winning_payout = pay
                break

        # EV閾値別に購入
        for combo, odds_val in race_o6.items():
            if odds_val <= 0:
                continue
            u1, u2, u3 = combo
            h_prob = harville_prob(win_probs, u1, u2, u3)
            ev = h_prob * odds_val

            for threshold_name, threshold in [
                ('EV>1.5', 1.5), ('EV>2.0', 2.0), ('EV>3.0', 3.0),
                ('EV>5.0', 5.0), ('Top20_EV', 0),
            ]:
                if threshold_name == 'Top20_EV':
                    continue  # handled separately below
                if ev >= threshold:
                    ev_results[threshold_name]['bets'] += 1
                    ev_results[threshold_name]['invested'] += 100
                    if combo == winning_combo and winning_payout > 0:
                        ev_results[threshold_name]['returned'] += winning_payout
                        ev_results[threshold_name]['hits'] += 1

        # Top N by EV
        combo_evs = []
        for combo, odds_val in race_o6.items():
            if odds_val <= 0:
                continue
            u1, u2, u3 = combo
            h_prob = harville_prob(win_probs, u1, u2, u3)
            ev = h_prob * odds_val
            combo_evs.append((combo, ev, odds_val))

        combo_evs.sort(key=lambda x: -x[1])

        for top_n_name, top_n in [('Top10_EV', 10), ('Top20_EV', 20), ('Top50_EV', 50)]:
            for combo, ev, odds_val in combo_evs[:top_n]:
                ev_results[top_n_name]['bets'] += 1
                ev_results[top_n_name]['invested'] += 100
                if combo == winning_combo and winning_payout > 0:
                    ev_results[top_n_name]['returned'] += winning_payout
                    ev_results[top_n_name]['hits'] += 1

    print(f"\n{'戦略':>12} {'買い点':>8} {'投資':>10} {'回収':>10} {'的中':>5} {'ROI':>8}")
    print("-" * 60)
    for name in ['EV>1.5', 'EV>2.0', 'EV>3.0', 'EV>5.0', 'Top10_EV', 'Top20_EV', 'Top50_EV']:
        r = ev_results[name]
        if r['bets'] == 0:
            continue
        roi = r['returned'] / r['invested'] * 100 if r['invested'] > 0 else 0
        print(f"{name:>12} {r['bets']:>8,} {r['invested']:>10,} {r['returned']:>10,} "
              f"{r['hits']:>5} {roi:>7.1f}%")

    # =========================================================================
    # H4: 既存フィルター × 実オッズEV
    # =========================================================================
    print("\n" + "=" * 70)
    print("  H4: 既存フィルター(ConfGap/FavOdds) × 実オッズEV")
    print("=" * 70)

    filter_results = defaultdict(lambda: {'bets': 0, 'invested': 0, 'returned': 0, 'hits': 0})

    for race in valid_races:
        entries = race.get('entries', [])
        rid = race['race_id']

        # フィルター条件
        by_rp = sorted(entries, key=lambda e: e.get('rank_p') or 99)
        if len(by_rp) < 3:
            continue

        p1_prob = by_rp[0].get('pred_proba_p', 0) or 0
        p2_prob = by_rp[1].get('pred_proba_p', 0) or 0
        conf_gap = p1_prob - p2_prob

        top3_share = sum((e.get('pred_proba_p', 0) or 0) for e in by_rp[:3])
        total_p = sum((e.get('pred_proba_p', 0) or 0) for e in entries)
        if total_p > 0:
            top3_share /= total_p

        fav_odds = float(by_rp[0].get('odds', 0) or 0)

        # VB候補数
        vb_count = sum(1 for e in entries if
                       (e.get('value_bet_win') or e.get('value_bet_place')))

        # 的中組み合わせ
        actual_map = race.get('actual_map', {})
        first = second = third = None
        for uma, pos in actual_map.items():
            if pos == 1: first = uma
            elif pos == 2: second = uma
            elif pos == 3: third = uma
        if not all([first, second, third]):
            continue

        winning_combo = (first, second, third)
        race_payouts_list = payouts.get(rid, [])
        winning_payout = 0
        for combo, pay in race_payouts_list:
            if combo == winning_combo:
                winning_payout = pay
                break

        # モデル勝率
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

        race_o6 = o6_odds.get(rid, {})

        # Top20 EV picks
        combo_evs = []
        for combo, odds_val in race_o6.items():
            if odds_val <= 0:
                continue
            u1, u2, u3 = combo
            h_prob = harville_prob(win_probs, u1, u2, u3)
            ev = h_prob * odds_val
            combo_evs.append((combo, ev))
        combo_evs.sort(key=lambda x: -x[1])
        top20_combos = set(c for c, _ in combo_evs[:20])

        # 各フィルター組み合わせ
        filters = {
            'ALL': True,
            'CG<0.10': conf_gap < 0.10,
            'CG<0.05': conf_gap < 0.05,
            'FO3-4': 3.0 <= fav_odds < 4.0,
            'Sh<0.45': top3_share < 0.45,
            'VB≥3': vb_count >= 3,
            'CG10+FO34': conf_gap < 0.10 and 3.0 <= fav_odds < 4.0,
            'CG10+FO34+Sh45': conf_gap < 0.10 and 3.0 <= fav_odds < 4.0 and top3_share < 0.45,
            'CG10+FO34+VB3': conf_gap < 0.10 and 3.0 <= fav_odds < 4.0 and vb_count >= 3,
        }

        for fname, fpass in filters.items():
            if not fpass:
                continue
            for combo in top20_combos:
                key = f"{fname}_Top20"
                filter_results[key]['bets'] += 1
                filter_results[key]['invested'] += 100
                if combo == winning_combo and winning_payout > 0:
                    filter_results[key]['returned'] += winning_payout
                    filter_results[key]['hits'] += 1

    print(f"\n{'フィルター':>25} {'レース':>6} {'買い点':>8} {'的中':>5} {'ROI':>8}")
    print("-" * 60)
    for name in sorted(filter_results.keys()):
        r = filter_results[name]
        if r['bets'] == 0:
            continue
        roi = r['returned'] / r['invested'] * 100 if r['invested'] > 0 else 0
        n_races = r['bets'] // 20  # approx
        marker = ' ★' if roi > 150 else ' ▲' if roi > 100 else ''
        print(f"{name:>25} {n_races:>6} {r['bets']:>8,} {r['hits']:>5} {roi:>7.1f}%{marker}")

    # =========================================================================
    # H5: 歪み率とROIの関係
    # =========================================================================
    print("\n" + "=" * 70)
    print("  H5: Harville歪み率(H/M)とROIの関係")
    print("=" * 70)

    distortion_bins = defaultdict(lambda: {'bets': 0, 'invested': 0, 'returned': 0, 'hits': 0})

    for race in valid_races:
        entries = race.get('entries', [])
        rid = race['race_id']

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

        actual_map = race.get('actual_map', {})
        first = second = third = None
        for uma, pos in actual_map.items():
            if pos == 1: first = uma
            elif pos == 2: second = uma
            elif pos == 3: third = uma
        if not all([first, second, third]):
            continue

        winning_combo = (first, second, third)
        race_payouts_list = payouts.get(rid, [])
        winning_payout = 0
        for combo, pay in race_payouts_list:
            if combo == winning_combo:
                winning_payout = pay
                break

        race_o6 = o6_odds.get(rid, {})

        # 全組み合わせの歪み率を計算し、Top20を購入
        combo_data = []
        for combo, odds_val in race_o6.items():
            if odds_val <= 0:
                continue
            u1, u2, u3 = combo
            h_prob = harville_prob(win_probs, u1, u2, u3)
            market_implied = 1.0 / odds_val
            distortion = h_prob / market_implied if market_implied > 0 else 0
            combo_data.append((combo, distortion, odds_val, h_prob))

        # 歪み率帯別にTop20を分類
        combo_data.sort(key=lambda x: -x[1])  # 歪み率降順

        for i, (combo, dist, odds_val, h_p) in enumerate(combo_data[:50]):
            if dist >= 3.0:
                bin_name = 'dist≥3.0 (H大幅過大)'
            elif dist >= 2.0:
                bin_name = 'dist 2.0-3.0'
            elif dist >= 1.5:
                bin_name = 'dist 1.5-2.0'
            elif dist >= 1.0:
                bin_name = 'dist 1.0-1.5'
            else:
                bin_name = 'dist<1.0 (H過小)'

            distortion_bins[bin_name]['bets'] += 1
            distortion_bins[bin_name]['invested'] += 100
            if combo == winning_combo and winning_payout > 0:
                distortion_bins[bin_name]['returned'] += winning_payout
                distortion_bins[bin_name]['hits'] += 1

    print(f"\n{'歪み率帯':>25} {'買い点':>8} {'的中':>5} {'ROI':>8}")
    print("-" * 55)
    for name in ['dist≥3.0 (H大幅過大)', 'dist 2.0-3.0', 'dist 1.5-2.0',
                  'dist 1.0-1.5', 'dist<1.0 (H過小)']:
        r = distortion_bins.get(name, {'bets': 0, 'invested': 0, 'returned': 0, 'hits': 0})
        if r['bets'] == 0:
            continue
        roi = r['returned'] / r['invested'] * 100 if r['invested'] > 0 else 0
        marker = ' ★' if roi > 150 else ' ▲' if roi > 100 else ''
        print(f"{name:>25} {r['bets']:>8,} {r['hits']:>5} {roi:>7.1f}%{marker}")

    # =========================================================================
    # H5b: 歪み率2.0-3.0帯で的中した組み合わせの共通パターン深掘り
    # =========================================================================
    print("\n" + "=" * 70)
    print("  H5b: 歪み率2.0-3.0帯の的中23レース 共通パターン分析")
    print("=" * 70)

    hit_details = []  # 的中レースの詳細

    for race in valid_races:
        entries = race.get('entries', [])
        rid = race['race_id']

        win_probs = {}
        for e in entries:
            uma = e.get('umaban', 0)
            pw = e.get('pred_proba_w_cal') or e.get('pred_proba_w', 0) or 0
            if uma > 0 and pw > 0:
                win_probs[uma] = pw
        total_wp = sum(win_probs.values())
        if total_wp <= 0:
            continue
        win_probs = {k: v / total_wp for k, v in win_probs.items()}

        actual_map = race.get('actual_map', {})
        first = second = third = None
        for uma, pos in actual_map.items():
            if pos == 1: first = uma
            elif pos == 2: second = uma
            elif pos == 3: third = uma
        if not all([first, second, third]):
            continue

        winning_combo = (first, second, third)
        race_payouts_list = payouts.get(rid, [])
        winning_payout = 0
        for combo, pay in race_payouts_list:
            if combo == winning_combo:
                winning_payout = pay
                break

        race_o6 = o6_odds.get(rid, {})

        # 全組み合わせの歪み率Top50を計算
        combo_data = []
        for combo, odds_val in race_o6.items():
            if odds_val <= 0:
                continue
            u1, u2, u3 = combo
            h_prob = harville_prob(win_probs, u1, u2, u3)
            market_implied = 1.0 / odds_val
            distortion = h_prob / market_implied if market_implied > 0 else 0
            combo_data.append((combo, distortion, odds_val, h_prob))
        combo_data.sort(key=lambda x: -x[1])

        # 2.0-3.0帯で的中したか
        for i, (combo, dist, odds_val, h_p) in enumerate(combo_data[:50]):
            if not (2.0 <= dist < 3.0):
                continue
            if combo != winning_combo:
                continue
            if winning_payout <= 0:
                continue

            # このレースの詳細情報を収集
            by_odds = sorted(entries, key=lambda e: float(e.get('odds', 999) or 999))
            fav_ranks = {}
            for idx, e in enumerate(by_odds):
                fav_ranks[e.get('umaban', 0)] = idx + 1

            by_rp = sorted(entries, key=lambda e: e.get('rank_p') or 99)
            by_rw = sorted(entries, key=lambda e: e.get('rank_w') or 99)
            rank_p_map = {e.get('umaban', 0): i + 1 for i, e in enumerate(by_rp)}
            rank_w_map = {e.get('umaban', 0): i + 1 for i, e in enumerate(by_rw)}

            # 1着馬情報
            first_entry = next((e for e in entries if e.get('umaban') == first), {})
            second_entry = next((e for e in entries if e.get('umaban') == second), {})
            third_entry = next((e for e in entries if e.get('umaban') == third), {})

            # レースフィルター条件
            p1_prob = by_rp[0].get('pred_proba_p', 0) or 0
            p2_prob = by_rp[1].get('pred_proba_p', 0) or 0 if len(by_rp) > 1 else 0
            conf_gap = p1_prob - p2_prob
            fav_odds = float(by_odds[0].get('odds', 0) or 0) if by_odds else 0
            top3_share = sum((e.get('pred_proba_p', 0) or 0) for e in by_rp[:3])
            total_p = sum((e.get('pred_proba_p', 0) or 0) for e in entries)
            if total_p > 0:
                top3_share /= total_p
            vb_count = sum(1 for e in entries
                           if (e.get('value_bet_win') or e.get('value_bet_place')))

            detail = {
                'race_id': rid,
                'date': race.get('date', ''),
                'num_runners': race.get('num_runners', len(entries)),
                'distortion': dist,
                'payout': winning_payout,
                'actual_odds': odds_val,
                'rank_in_top50': i + 1,
                # 1着馬
                '1st_umaban': first,
                '1st_fav_rank': fav_ranks.get(first, 99),
                '1st_rank_p': rank_p_map.get(first, 99),
                '1st_rank_w': rank_w_map.get(first, 99),
                '1st_odds': float(first_entry.get('odds', 0) or 0),
                '1st_name': first_entry.get('horse_name', '?'),
                # 2着馬
                '2nd_umaban': second,
                '2nd_fav_rank': fav_ranks.get(second, 99),
                '2nd_rank_p': rank_p_map.get(second, 99),
                '2nd_rank_w': rank_w_map.get(second, 99),
                '2nd_odds': float(second_entry.get('odds', 0) or 0),
                '2nd_name': second_entry.get('horse_name', '?'),
                # 3着馬
                '3rd_umaban': third,
                '3rd_fav_rank': fav_ranks.get(third, 99),
                '3rd_rank_p': rank_p_map.get(third, 99),
                '3rd_rank_w': rank_w_map.get(third, 99),
                '3rd_odds': float(third_entry.get('odds', 0) or 0),
                '3rd_name': third_entry.get('horse_name', '?'),
                # レース条件
                'conf_gap': conf_gap,
                'fav_odds': fav_odds,
                'top3_share': top3_share,
                'vb_count': vb_count,
            }
            hit_details.append(detail)

    print(f"\n  的中レース: {len(hit_details)}件")

    if not hit_details:
        print("  No hits found in 2.0-3.0 band")
    else:
        # --- 個別レース一覧 ---
        print(f"\n  {'日付':>10} {'race_id':>18} {'配当':>8} {'歪み':>5} "
              f"{'1着(人気/Rp/Rw)':>16} {'2着(人気/Rp/Rw)':>16} {'3着(人気/Rp/Rw)':>16} "
              f"{'CG':>5} {'FO':>5} {'Sh':>5} {'VB':>3}")
        print("-" * 140)
        for d in sorted(hit_details, key=lambda x: x['date']):
            print(f"  {d['date']:>10} {d['race_id']:>18} {d['payout']:>8,} {d['distortion']:>5.2f} "
                  f"  {d['1st_fav_rank']:>2}/{d['1st_rank_p']:>2}/{d['1st_rank_w']:>2}"
                  f"({d['1st_odds']:>5.1f})"
                  f"  {d['2nd_fav_rank']:>2}/{d['2nd_rank_p']:>2}/{d['2nd_rank_w']:>2}"
                  f"({d['2nd_odds']:>5.1f})"
                  f"  {d['3rd_fav_rank']:>2}/{d['3rd_rank_p']:>2}/{d['3rd_rank_w']:>2}"
                  f"({d['3rd_odds']:>5.1f})"
                  f" {d['conf_gap']:>5.3f} {d['fav_odds']:>5.1f} {d['top3_share']:>5.3f} {d['vb_count']:>3}")

        # --- 集計: 1着馬の人気順位分布 ---
        print(f"\n  ◆ 1着馬の人気順位分布:")
        from collections import Counter
        c1_fav = Counter(d['1st_fav_rank'] for d in hit_details)
        for rank in sorted(c1_fav.keys()):
            pct = c1_fav[rank] / len(hit_details) * 100
            bar = '#' * int(pct / 2)
            print(f"    {rank:>2}番人気: {c1_fav[rank]:>3} ({pct:>5.1f}%) {bar}")

        # --- 集計: 1着馬のrank_w分布 ---
        print(f"\n  ◆ 1着馬のrank_w分布:")
        c1_rw = Counter(d['1st_rank_w'] for d in hit_details)
        for rank in sorted(c1_rw.keys()):
            pct = c1_rw[rank] / len(hit_details) * 100
            bar = '#' * int(pct / 2)
            print(f"    rank_w={rank:>2}: {c1_rw[rank]:>3} ({pct:>5.1f}%) {bar}")

        # --- 集計: 1着馬のrank_p分布 ---
        print(f"\n  ◆ 1着馬のrank_p分布:")
        c1_rp = Counter(d['1st_rank_p'] for d in hit_details)
        for rank in sorted(c1_rp.keys()):
            pct = c1_rp[rank] / len(hit_details) * 100
            bar = '#' * int(pct / 2)
            print(f"    rank_p={rank:>2}: {c1_rp[rank]:>3} ({pct:>5.1f}%) {bar}")

        # --- 集計: 2着馬の人気順位分布 ---
        print(f"\n  ◆ 2着馬の人気順位分布:")
        c2_fav = Counter(d['2nd_fav_rank'] for d in hit_details)
        for rank in sorted(c2_fav.keys()):
            pct = c2_fav[rank] / len(hit_details) * 100
            bar = '#' * int(pct / 2)
            print(f"    {rank:>2}番人気: {c2_fav[rank]:>3} ({pct:>5.1f}%) {bar}")

        # --- 集計: 3着馬の人気/rank分布 ---
        print(f"\n  ◆ 3着馬の人気順位分布:")
        c3_fav = Counter(d['3rd_fav_rank'] for d in hit_details)
        for rank in sorted(c3_fav.keys()):
            pct = c3_fav[rank] / len(hit_details) * 100
            bar = '#' * int(pct / 2)
            print(f"    {rank:>2}番人気: {c3_fav[rank]:>3} ({pct:>5.1f}%) {bar}")

        # --- 集計: レース条件 ---
        print(f"\n  ◆ レース条件分布:")
        cg_under_010 = sum(1 for d in hit_details if d['conf_gap'] < 0.10)
        cg_under_005 = sum(1 for d in hit_details if d['conf_gap'] < 0.05)
        fo_34 = sum(1 for d in hit_details if 3.0 <= d['fav_odds'] < 4.0)
        fo_under3 = sum(1 for d in hit_details if d['fav_odds'] < 3.0)
        fo_over4 = sum(1 for d in hit_details if d['fav_odds'] >= 4.0)
        sh_under_045 = sum(1 for d in hit_details if d['top3_share'] < 0.45)
        vb_ge3 = sum(1 for d in hit_details if d['vb_count'] >= 3)
        n = len(hit_details)
        print(f"    ConfGap < 0.10: {cg_under_010}/{n} ({cg_under_010 / n * 100:.0f}%)")
        print(f"    ConfGap < 0.05: {cg_under_005}/{n} ({cg_under_005 / n * 100:.0f}%)")
        print(f"    FavOdds < 3.0:  {fo_under3}/{n} ({fo_under3 / n * 100:.0f}%)")
        print(f"    FavOdds 3-4:    {fo_34}/{n} ({fo_34 / n * 100:.0f}%)")
        print(f"    FavOdds >= 4.0: {fo_over4}/{n} ({fo_over4 / n * 100:.0f}%)")
        print(f"    Share < 0.45:   {sh_under_045}/{n} ({sh_under_045 / n * 100:.0f}%)")
        print(f"    VB >= 3:        {vb_ge3}/{n} ({vb_ge3 / n * 100:.0f}%)")

        # --- 集計: 「隠れ実力馬」パターン ---
        print(f"\n  ◆ 「隠れ実力馬」パターン (人気≥5 & rank_w≤5):")
        hidden_1st = sum(1 for d in hit_details
                         if d['1st_fav_rank'] >= 5 and d['1st_rank_w'] <= 5)
        hidden_2nd = sum(1 for d in hit_details
                         if d['2nd_fav_rank'] >= 5 and d['2nd_rank_p'] <= 5)
        print(f"    1着に隠れ実力馬: {hidden_1st}/{n} ({hidden_1st / n * 100:.0f}%)")
        print(f"    2着に隠れ実力馬: {hidden_2nd}/{n} ({hidden_2nd / n * 100:.0f}%)")

        # --- 配当分布 ---
        payouts_arr = [d['payout'] for d in hit_details]
        print(f"\n  ◆ 配当分布:")
        print(f"    最小: ¥{min(payouts_arr):,}")
        print(f"    中央: ¥{int(np.median(payouts_arr)):,}")
        print(f"    平均: ¥{int(np.mean(payouts_arr)):,}")
        print(f"    最大: ¥{max(payouts_arr):,}")
        under_10k = sum(1 for p in payouts_arr if p < 10000)
        under_50k = sum(1 for p in payouts_arr if p < 50000)
        over_100k = sum(1 for p in payouts_arr if p >= 100000)
        print(f"    1万未満: {under_10k}/{n}, 5万未満: {under_50k}/{n}, 10万以上: {over_100k}/{n}")

    print("\n" + "=" * 70)
    print("  Phase 1 完了")
    print("=" * 70)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=0, help='Limit to last N races')
    args = parser.parse_args()
    analyze(args.limit)


if __name__ == '__main__':
    main()
