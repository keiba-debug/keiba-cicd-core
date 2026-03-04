#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
シンプル戦略分析: rank_w=1 買い + ワイド戦略
backtest_cache.json を使って各種シンプル戦略のROIを検証

Usage:
    python -m ml.analyze_simple_strategy
"""

import json
import sys
from pathlib import Path
from collections import defaultdict

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')


def load_cache() -> list:
    cache_path = Path('C:/KEIBA-CICD/data3/ml/backtest_cache.json')
    with open(cache_path, encoding='utf-8') as f:
        return json.load(f)


def calc_roi(bets: list) -> dict:
    """bets = [(bet_amount, return_amount, hit_bool), ...]"""
    if not bets:
        return {'n': 0, 'bet': 0, 'ret': 0, 'roi': 0, 'hits': 0, 'hit_rate': 0, 'pnl': 0}
    n = len(bets)
    total_bet = sum(b[0] for b in bets)
    total_ret = sum(b[1] for b in bets)
    hits = sum(1 for b in bets if b[2])
    return {
        'n': n,
        'bet': total_bet,
        'ret': total_ret,
        'roi': total_ret / total_bet * 100 if total_bet > 0 else 0,
        'hits': hits,
        'hit_rate': hits / n * 100 if n > 0 else 0,
        'pnl': total_ret - total_bet,
    }


def fmt_roi(r: dict, marker=True) -> str:
    m = ' ***' if marker and r['roi'] >= 100 else ''
    return (f"{r['n']:>5} {r['bet']:>10,} {r['ret']:>10,} {r['roi']:>6.1f}%{m}"
            f" {r['hits']:>5} {r['hit_rate']:>6.1f}% {r['pnl']:>+9,}")


def main():
    races = load_cache()
    print(f'Loaded {len(races)} races, {sum(len(r["entries"]) for r in races):,} entries')
    dates = sorted(set(r['race_id'][:8] for r in races))
    print(f'Period: {dates[0]} ~ {dates[-1]}')

    # ========================================
    # Section 1: rank_w=1 単勝 戦略
    # ========================================
    print(f'\n{"=" * 80}')
    print(f'  Section 1: rank_w=1 単勝 (Win) 戦略')
    print(f'{"=" * 80}')

    # Baseline: rank_w=1 全買い (100円均一)
    all_bets = {}  # condition_name -> [(bet, ret, hit)]

    for race in races:
        entries = race['entries']
        for e in entries:
            if e['rank_w'] != 1:
                continue

            odds = e.get('odds', 0) or 0
            is_win = e.get('is_win', 0)
            is_top3 = e.get('is_top3', 0)
            win_ev = e.get('win_ev', 0) or 0
            place_ev = e.get('place_ev', 0) or 0
            ar_dev = e.get('ar_deviation', 50) or 50
            dev_gap = e.get('dev_gap', 0) or 0
            win_gap = e.get('win_vb_gap', 0) or 0
            place_odds = e.get('place_odds_min') or (odds / 3.5 if odds > 0 else 1.1)
            closing_str = e.get('closing_strength', 0) or 0

            win_ret = int(odds * 100) if is_win else 0
            place_ret = int(place_odds * 100) if is_top3 else 0

            # --- 単勝 戦略 ---
            # 1. 全買い
            all_bets.setdefault('全買い', []).append((100, win_ret, is_win))

            # 2. EV >= 1.0
            if win_ev >= 1.0:
                all_bets.setdefault('EV>=1.0', []).append((100, win_ret, is_win))

            # 3. EV >= 1.3
            if win_ev >= 1.3:
                all_bets.setdefault('EV>=1.3', []).append((100, win_ret, is_win))

            # 4. EV >= 1.5
            if win_ev >= 1.5:
                all_bets.setdefault('EV>=1.5', []).append((100, win_ret, is_win))

            # 5. ARd >= 55
            if ar_dev >= 55:
                all_bets.setdefault('ARd>=55', []).append((100, win_ret, is_win))

            # 6. ARd >= 60
            if ar_dev >= 60:
                all_bets.setdefault('ARd>=60', []).append((100, win_ret, is_win))

            # 7. odds範囲フィルタ
            if 3.0 <= odds <= 30.0:
                all_bets.setdefault('odds 3-30', []).append((100, win_ret, is_win))
            if 5.0 <= odds <= 50.0:
                all_bets.setdefault('odds 5-50', []).append((100, win_ret, is_win))
            if odds >= 3.0:
                all_bets.setdefault('odds>=3', []).append((100, win_ret, is_win))

            # 8. EV+ARd組合せ
            if win_ev >= 1.0 and ar_dev >= 55:
                all_bets.setdefault('EV>=1.0 & ARd>=55', []).append((100, win_ret, is_win))
            if win_ev >= 1.3 and ar_dev >= 50:
                all_bets.setdefault('EV>=1.3 & ARd>=50', []).append((100, win_ret, is_win))
            if win_ev >= 1.3 and ar_dev >= 55:
                all_bets.setdefault('EV>=1.3 & ARd>=55', []).append((100, win_ret, is_win))

            # 9. win_gap (rank_w=1なのにオッズが高い=人気ない)
            if win_gap >= 2:
                all_bets.setdefault('win_gap>=2', []).append((100, win_ret, is_win))
            if win_gap >= 3:
                all_bets.setdefault('win_gap>=3', []).append((100, win_ret, is_win))
            if win_gap >= 4:
                all_bets.setdefault('win_gap>=4', []).append((100, win_ret, is_win))

            # 10. win_gap + EV組合せ
            if win_gap >= 2 and win_ev >= 1.0:
                all_bets.setdefault('gap>=2 & EV>=1.0', []).append((100, win_ret, is_win))
            if win_gap >= 3 and win_ev >= 1.3:
                all_bets.setdefault('gap>=3 & EV>=1.3', []).append((100, win_ret, is_win))
            if win_gap >= 2 and win_ev >= 1.3:
                all_bets.setdefault('gap>=2 & EV>=1.3', []).append((100, win_ret, is_win))

            # 11. dev_gap (偏差値乖離) + EV
            if dev_gap >= 0.5:
                all_bets.setdefault('dev_gap>=0.5', []).append((100, win_ret, is_win))
            if dev_gap >= 0.5 and win_ev >= 1.0:
                all_bets.setdefault('dev>=0.5 & EV>=1.0', []).append((100, win_ret, is_win))
            if dev_gap >= 0.8 and win_ev >= 1.0:
                all_bets.setdefault('dev>=0.8 & EV>=1.0', []).append((100, win_ret, is_win))

            # --- 複勝 戦略 ---
            all_bets.setdefault('[複勝] 全買い', []).append((100, place_ret, is_top3))
            if place_ev >= 1.0:
                all_bets.setdefault('[複勝] PlcEV>=1.0', []).append((100, place_ret, is_top3))
            if place_ev >= 1.3:
                all_bets.setdefault('[複勝] PlcEV>=1.3', []).append((100, place_ret, is_top3))
            if ar_dev >= 55:
                all_bets.setdefault('[複勝] ARd>=55', []).append((100, place_ret, is_top3))
            if ar_dev >= 60:
                all_bets.setdefault('[複勝] ARd>=60', []).append((100, place_ret, is_top3))

    print(f'\n  {"戦略":>28} {"Bets":>5} {"TotalBet":>10} {"TotalRet":>10} '
          f'{"ROI":>7}  {"Hits":>5} {"HitRate":>7} {"P&L":>9}')
    print(f'  {"-" * 95}')

    # Sort: 単勝 first, then 複勝
    win_keys = [k for k in all_bets if not k.startswith('[')]
    place_keys = [k for k in all_bets if k.startswith('[')]

    for key in win_keys:
        r = calc_roi(all_bets[key])
        print(f'  {key:>28} {fmt_roi(r)}')

    print(f'  {"-" * 95}')
    for key in place_keys:
        r = calc_roi(all_bets[key])
        print(f'  {key:>28} {fmt_roi(r)}')

    # ========================================
    # Section 2: rank_w=1 + rank_w=2 戦略
    # ========================================
    print(f'\n{"=" * 80}')
    print(f'  Section 2: rank_w 上位2頭 戦略')
    print(f'{"=" * 80}')

    top2_bets = {}

    for race in races:
        entries = sorted(race['entries'], key=lambda x: x.get('rank_w', 99))
        rw1 = [e for e in entries if e.get('rank_w') == 1]
        rw2 = [e for e in entries if e.get('rank_w') == 2]

        if not rw1:
            continue
        e1 = rw1[0]
        e2 = rw2[0] if rw2 else None

        odds1 = e1.get('odds', 0) or 0
        is_win1 = e1.get('is_win', 0)
        is_top3_1 = e1.get('is_top3', 0)
        ev1 = e1.get('win_ev', 0) or 0

        # rank_w=1 単勝 + rank_w=1 複勝 (単複)
        place_odds1 = e1.get('place_odds_min') or (odds1 / 3.5 if odds1 > 0 else 1.1)
        win_ret1 = int(odds1 * 100) if is_win1 else 0
        plc_ret1 = int(place_odds1 * 100) if is_top3_1 else 0

        # 単複: 単100+複100
        top2_bets.setdefault('単複(100+100)', []).append(
            (200, win_ret1 + plc_ret1, is_win1 or is_top3_1))

        # 単複: 単100+複200
        top2_bets.setdefault('単複(100+200)', []).append(
            (300, win_ret1 + int(place_odds1 * 200) if is_top3_1 else win_ret1, is_win1 or is_top3_1))

        if e2:
            odds2 = e2.get('odds', 0) or 0
            is_win2 = e2.get('is_win', 0)
            is_top3_2 = e2.get('is_top3', 0)
            ev2 = e2.get('win_ev', 0) or 0
            place_odds2 = e2.get('place_odds_min') or (odds2 / 3.5 if odds2 > 0 else 1.1)
            win_ret2 = int(odds2 * 100) if is_win2 else 0
            plc_ret2 = int(place_odds2 * 100) if is_top3_2 else 0

            # rank_w 1-2 各単勝 (200円投下)
            top2_bets.setdefault('1-2各単勝(100x2)', []).append(
                (200, win_ret1 + win_ret2, is_win1 or is_win2))

            # rank_w 1-2 各複勝 (200円投下)
            top2_bets.setdefault('1-2各複勝(100x2)', []).append(
                (200, plc_ret1 + plc_ret2, is_top3_1 or is_top3_2))

    print(f'\n  {"戦略":>28} {"Bets":>5} {"TotalBet":>10} {"TotalRet":>10} '
          f'{"ROI":>7}  {"Hits":>5} {"HitRate":>7} {"P&L":>9}')
    print(f'  {"-" * 95}')

    for key in top2_bets:
        r = calc_roi(top2_bets[key])
        print(f'  {key:>28} {fmt_roi(r)}')

    # ========================================
    # Section 3: ワイド戦略 (rank_w=1 軸)
    # ========================================
    print(f'\n{"=" * 80}')
    print(f'  Section 3: ワイド戦略 (rank_w=1 軸)')
    print(f'  ※ ワイドオッズは推定値 (place_odds積ベース)')
    print(f'{"=" * 80}')

    wide_bets = {}

    for race in races:
        entries = race['entries']
        num_runners = len(entries)
        if num_runners < 5:
            continue

        rw1 = [e for e in entries if e.get('rank_w') == 1]
        if not rw1:
            continue
        e1 = rw1[0]
        is_top3_1 = e1.get('is_top3', 0)
        odds1 = e1.get('odds', 0) or 0
        place_odds1 = e1.get('place_odds_min') or (odds1 / 3.5 if odds1 > 0 else 1.1)
        ar_dev1 = e1.get('ar_deviation', 50) or 50
        ev1 = e1.get('win_ev', 0) or 0

        # ワイド相手候補: rank_w=2, rank_p=1 (if != rank_w=1), rank_w=3
        partners = {}
        for e in entries:
            if e['umaban'] == e1['umaban']:
                continue
            rw = e.get('rank_w', 99)
            rp = e.get('rank_p', 99)
            if rw == 2:
                partners['rw2'] = e
            if rw == 3:
                partners['rw3'] = e
            if rp == 1 and rw != 1:
                partners['rp1'] = e
            if rp == 2 and rw != 1:
                partners['rp2'] = e

        for partner_key, e2 in partners.items():
            is_top3_2 = e2.get('is_top3', 0)
            odds2 = e2.get('odds', 0) or 0
            place_odds2 = e2.get('place_odds_min') or (odds2 / 3.5 if odds2 > 0 else 1.1)

            # ワイド的中: 両方top3
            wide_hit = is_top3_1 and is_top3_2

            # ワイドオッズ推定: 経験則 (place_odds_1 * place_odds_2 * adjustment)
            # JRAワイド: 2頭がともに3着以内
            # 実際のワイドオッズ ≈ (place_odds1 - 1) * (place_odds2 - 1) * factor + 1
            # 人気馬同士: factor≈2.0, 穴馬含む: factor≈2.5
            min_odds = min(odds1, odds2)
            if min_odds <= 5:
                factor = 1.8
            elif min_odds <= 15:
                factor = 2.2
            else:
                factor = 2.5
            wide_odds_est = max(1.1, (place_odds1 - 1) * (place_odds2 - 1) * factor + 1)

            wide_ret = int(wide_odds_est * 100) if wide_hit else 0

            # ワイド戦略
            label = f'rw1→{partner_key}'
            wide_bets.setdefault(label, []).append((100, wide_ret, wide_hit))

            # フィルタ付き
            if ev1 >= 1.0:
                wide_bets.setdefault(f'{label} (EV1>=1.0)', []).append((100, wide_ret, wide_hit))
            if ar_dev1 >= 55:
                wide_bets.setdefault(f'{label} (ARd1>=55)', []).append((100, wide_ret, wide_hit))

    print(f'\n  {"戦略":>32} {"Bets":>5} {"TotalBet":>10} {"TotalRet":>10} '
          f'{"ROI":>7}  {"Hits":>5} {"HitRate":>7} {"P&L":>9}')
    print(f'  {"-" * 100}')

    for key in sorted(wide_bets.keys()):
        r = calc_roi(wide_bets[key])
        print(f'  {key:>32} {fmt_roi(r)}')

    # ========================================
    # Section 4: ワイドBOX戦略
    # ========================================
    print(f'\n{"=" * 80}')
    print(f'  Section 4: ワイドBOX戦略 (rank_w上位N頭のBOX)')
    print(f'{"=" * 80}')

    wide_box_bets = {}

    for race in races:
        entries = race['entries']
        num_runners = len(entries)
        if num_runners < 5:
            continue

        by_rank_w = sorted(entries, key=lambda x: x.get('rank_w', 99))

        for box_size in [2, 3]:
            box = by_rank_w[:box_size]
            if len(box) < box_size:
                continue

            # ワイドBOX: C(box_size, 2) 通り
            from itertools import combinations
            pairs = list(combinations(box, 2))
            num_pairs = len(pairs)

            total_bet_box = num_pairs * 100
            total_ret_box = 0
            any_hit = False

            for ea, eb in pairs:
                is_top3_a = ea.get('is_top3', 0)
                is_top3_b = eb.get('is_top3', 0)
                odds_a = ea.get('odds', 0) or 0
                odds_b = eb.get('odds', 0) or 0
                place_odds_a = ea.get('place_odds_min') or (odds_a / 3.5 if odds_a > 0 else 1.1)
                place_odds_b = eb.get('place_odds_min') or (odds_b / 3.5 if odds_b > 0 else 1.1)

                hit = is_top3_a and is_top3_b
                min_odds = min(odds_a, odds_b)
                factor = 1.8 if min_odds <= 5 else (2.2 if min_odds <= 15 else 2.5)
                wide_odds = max(1.1, (place_odds_a - 1) * (place_odds_b - 1) * factor + 1)

                if hit:
                    total_ret_box += int(wide_odds * 100)
                    any_hit = True

            label = f'ワイドBOX rw上位{box_size}頭'
            wide_box_bets.setdefault(label, []).append(
                (total_bet_box, total_ret_box, any_hit))

            # EV1>=1.0 filter (rank_w=1のEVで判断)
            e1 = by_rank_w[0]
            ev1 = e1.get('win_ev', 0) or 0
            ar1 = e1.get('ar_deviation', 50) or 50

            if ev1 >= 1.0:
                wide_box_bets.setdefault(f'{label} (EV1>=1.0)', []).append(
                    (total_bet_box, total_ret_box, any_hit))
            if ar1 >= 55:
                wide_box_bets.setdefault(f'{label} (ARd1>=55)', []).append(
                    (total_bet_box, total_ret_box, any_hit))

    print(f'\n  {"戦略":>36} {"Bets":>5} {"TotalBet":>10} {"TotalRet":>10} '
          f'{"ROI":>7}  {"Hits":>5} {"HitRate":>7} {"P&L":>9}')
    print(f'  {"-" * 105}')

    for key in sorted(wide_box_bets.keys()):
        r = calc_roi(wide_box_bets[key])
        print(f'  {key:>36} {fmt_roi(r)}')

    # ========================================
    # Section 5: 条件交差分析 (rank_w=1 単勝)
    # ========================================
    print(f'\n{"=" * 80}')
    print(f'  Section 5: 条件交差分析 (rank_w=1 単勝)')
    print(f'  行=EVフィルタ, 列=追加条件')
    print(f'{"=" * 80}')

    # Build raw data for rank_w=1
    rw1_data = []
    for race in races:
        for e in race['entries']:
            if e.get('rank_w') != 1:
                continue
            rw1_data.append({
                'odds': e.get('odds', 0) or 0,
                'is_win': e.get('is_win', 0),
                'win_ev': e.get('win_ev', 0) or 0,
                'ar_dev': e.get('ar_deviation', 50) or 50,
                'dev_gap': e.get('dev_gap', 0) or 0,
                'win_gap': e.get('win_vb_gap', 0) or 0,
                'place_ev': e.get('place_ev', 0) or 0,
                'closing_str': e.get('closing_strength', 0) or 0,
                'grade': race.get('grade', ''),
                'track_type': race.get('track_type', ''),
                'race_id': race['race_id'],
            })

    print(f'  rank_w=1 total: {len(rw1_data)} entries')

    # Cross analysis: EV thresholds x additional filters
    ev_thresholds = [0.0, 0.8, 1.0, 1.2, 1.3, 1.5, 2.0]
    add_filters = {
        'なし': lambda d: True,
        'ARd>=55': lambda d: d['ar_dev'] >= 55,
        'ARd>=60': lambda d: d['ar_dev'] >= 60,
        'gap>=2': lambda d: d['win_gap'] >= 2,
        'gap>=3': lambda d: d['win_gap'] >= 3,
        'odds>=3': lambda d: d['odds'] >= 3.0,
        'odds 3-30': lambda d: 3.0 <= d['odds'] <= 30.0,
        'dev>=0.5': lambda d: d['dev_gap'] >= 0.5,
    }

    print(f'\n  {"EV>=":>6}', end='')
    for f_name in add_filters:
        print(f' {f_name:>14}', end='')
    print()
    print(f'  {"-" * (6 + 15 * len(add_filters))}')

    for ev_min in ev_thresholds:
        label = f'{ev_min:.1f}' if ev_min > 0 else 'none'
        print(f'  {label:>6}', end='')
        for f_name, f_fn in add_filters.items():
            filtered = [d for d in rw1_data
                        if (ev_min == 0 or d['win_ev'] >= ev_min) and f_fn(d)]
            n = len(filtered)
            if n == 0:
                print(f' {"---":>14}', end='')
                continue
            wins = sum(1 for d in filtered if d['is_win'])
            total_bet = n * 100
            total_ret = sum(int(d['odds'] * 100) for d in filtered if d['is_win'])
            roi = total_ret / total_bet * 100 if total_bet > 0 else 0
            m = '*' if roi >= 100 else ' '
            print(f' {n:>4}/{roi:>5.0f}%{m:>1} ', end='')
        print()

    # ========================================
    # Section 6: 月別ROI推移 (ベスト戦略)
    # ========================================
    print(f'\n{"=" * 80}')
    print(f'  Section 6: 月別ROI推移')
    print(f'{"=" * 80}')

    # Define strategies to track monthly
    strategies = {
        '単勝 全買い': lambda d: True,
        '単勝 EV>=1.0': lambda d: d['win_ev'] >= 1.0,
        '単勝 EV>=1.3': lambda d: d['win_ev'] >= 1.3,
        '単勝 EV>=1.0 ARd>=55': lambda d: d['win_ev'] >= 1.0 and d['ar_dev'] >= 55,
        '単勝 gap>=2 EV>=1.0': lambda d: d['win_gap'] >= 2 and d['win_ev'] >= 1.0,
        '単勝 gap>=3 EV>=1.3': lambda d: d['win_gap'] >= 3 and d['win_ev'] >= 1.3,
    }

    # Group by month
    monthly = defaultdict(lambda: defaultdict(list))
    for d in rw1_data:
        month = d['race_id'][:6]  # YYYYMM
        for s_name, s_fn in strategies.items():
            if s_fn(d):
                is_win = d['is_win']
                ret = int(d['odds'] * 100) if is_win else 0
                monthly[month][s_name].append((100, ret, is_win))

    months = sorted(monthly.keys())

    print(f'\n  {"月":>7}', end='')
    for s_name in strategies:
        print(f' {s_name:>20}', end='')
    print()
    print(f'  {"-" * (7 + 21 * len(strategies))}')

    cumul = defaultdict(lambda: [0, 0])  # [bet, ret]
    for m in months:
        m_label = f'{m[:4]}/{m[4:]}'
        print(f'  {m_label:>7}', end='')
        for s_name in strategies:
            bets = monthly[m].get(s_name, [])
            r = calc_roi(bets)
            cumul[s_name][0] += r['bet']
            cumul[s_name][1] += r['ret']
            c_roi = cumul[s_name][1] / cumul[s_name][0] * 100 if cumul[s_name][0] > 0 else 0
            if r['n'] > 0:
                print(f' {r["n"]:>3}b {r["roi"]:>5.0f}% c{c_roi:>5.0f}%', end='')
            else:
                print(f' {"":>20}', end='')
        print()

    # ========================================
    # Section 7: バンクロールシミュレーション
    # ========================================
    print(f'\n{"=" * 80}')
    print(f'  Section 7: バンクロールシミュレーション')
    print(f'{"=" * 80}')

    # Time-ordered bets
    def time_ordered_bets(filter_fn) -> list:
        """returns [(race_id, odds, is_win), ...] sorted by race_id"""
        result = []
        for d in rw1_data:
            if filter_fn(d):
                result.append((d['race_id'], d['odds'], d['is_win']))
        return sorted(result, key=lambda x: x[0])

    sim_strategies = {
        '単勝 全買い': lambda d: True,
        '単勝 EV>=1.0': lambda d: d['win_ev'] >= 1.0,
        '単勝 EV>=1.3': lambda d: d['win_ev'] >= 1.3,
        '単勝 EV>=1.0 ARd>=55': lambda d: d['win_ev'] >= 1.0 and d['ar_dev'] >= 55,
        '単勝 gap>=2 EV>=1.0': lambda d: d['win_gap'] >= 2 and d['win_ev'] >= 1.0,
    }

    for s_name, s_fn in sim_strategies.items():
        bets = time_ordered_bets(s_fn)
        if not bets:
            continue

        print(f'\n  --- {s_name} ---')

        for initial, pct in [(50000, 2), (50000, 3), (100000, 2), (100000, 3)]:
            balance = initial
            max_balance = initial
            min_balance = initial
            max_dd = 0

            for race_id, odds, is_win in bets:
                bet_amt = max(100, int(balance * pct / 100 / 100) * 100)  # round to 100
                bet_amt = min(bet_amt, balance)  # can't bet more than balance
                if bet_amt <= 0:
                    break
                balance -= bet_amt
                if is_win:
                    balance += int(odds * bet_amt)
                max_balance = max(max_balance, balance)
                min_balance = min(min_balance, balance)
                dd = (max_balance - balance) / max_balance * 100 if max_balance > 0 else 0
                max_dd = max(max_dd, dd)

            pnl = balance - initial
            gain = (balance / initial - 1) * 100
            print(f'    初期{initial//1000}K {pct}%: '
                  f'最終 ¥{balance:>10,} ({gain:>+6.1f}%) '
                  f'MaxDD {max_dd:>5.1f}% '
                  f'最低 ¥{min_balance:>8,} '
                  f'P&L ¥{pnl:>+10,}')

    # ========================================
    # Section 8: 芝/ダート・グレード別分析
    # ========================================
    print(f'\n{"=" * 80}')
    print(f'  Section 8: 芝/ダート・グレード別 (rank_w=1 EV>=1.0)')
    print(f'{"=" * 80}')

    for track in ['芝', 'ダ']:
        filtered = [d for d in rw1_data if d['track_type'] == track and d['win_ev'] >= 1.0]
        r = calc_roi([(100, int(d['odds'] * 100) if d['is_win'] else 0, d['is_win']) for d in filtered])
        print(f'  {track}: {fmt_roi(r)}')

    grade_groups = defaultdict(list)
    for d in rw1_data:
        if d['win_ev'] >= 1.0:
            g = d.get('grade', '') or '不明'
            grade_groups[g].append(d)

    print(f'\n  {"グレード":>10} {"Bets":>5} {"TotalBet":>10} {"TotalRet":>10} '
          f'{"ROI":>7}  {"Hits":>5} {"HitRate":>7} {"P&L":>9}')
    print(f'  {"-" * 80}')

    for grade in sorted(grade_groups.keys()):
        group = grade_groups[grade]
        r = calc_roi([(100, int(d['odds'] * 100) if d['is_win'] else 0, d['is_win']) for d in group])
        print(f'  {grade:>10} {fmt_roi(r)}')

    print(f'\n{"=" * 80}')
    print(f'  分析完了')
    print(f'{"=" * 80}')


if __name__ == '__main__':
    main()
