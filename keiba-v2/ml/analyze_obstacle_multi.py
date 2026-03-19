#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""障害レース 馬単/馬連/ワイド戦略分析

predictions.jsonベースで障害レースの多馬券戦略をバックテスト。
W Top1が45%あるなら馬単(1着固定)も射程圏内。
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

DATA_ROOT = Path("C:/KEIBA-CICD/data3")


def load_obstacle_predictions():
    """障害レースのpredictions.json + race JSONから実着順を読み込み"""
    results = []
    races_dir = DATA_ROOT / "races"

    for pred_path in sorted(races_dir.glob("**/predictions.json")):
        try:
            with open(pred_path, encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            continue

        races_list = data.get('races', []) if isinstance(data, dict) else data

        for race in races_list:
            if race.get('track_type') != 'obstacle':
                continue
            entries = race.get('entries', [])
            if not entries:
                continue

            race_id = race.get('race_id', '')
            date_str = race.get('date', '')

            # race JSONから実着順を取得
            if date_str:
                parts = date_str.split('-')
                if len(parts) == 3:
                    race_json_path = (races_dir / parts[0] / parts[1] / parts[2]
                                      / f"race_{race_id}.json")
                    try:
                        with open(race_json_path, encoding='utf-8') as f:
                            race_data = json.load(f)
                        # 実着順をumaban→finish_positionでマップ
                        actual_map = {}
                        for e in race_data.get('entries', []):
                            uma = e.get('umaban', 0)
                            fp = e.get('finish_position', 0)
                            if uma > 0 and fp > 0:
                                actual_map[uma] = fp

                        if not actual_map:
                            continue

                        # entriesに実着順を付与
                        for e in entries:
                            e['actual_finish'] = actual_map.get(e.get('umaban', 0), 0)

                    except (FileNotFoundError, json.JSONDecodeError):
                        continue

            has_result = any(e.get('actual_finish', 0) > 0 for e in entries)
            if not has_result:
                continue

            results.append(race)

    return results


def analyze():
    races = load_obstacle_predictions()
    print(f"障害レース数: {len(races)}")

    if not races:
        print("No obstacle races found in predictions.")
        return

    # 各戦略のバックテスト
    strategies = {
        # ワイド系
        'wide_p12': {'desc': 'ワイド P1-2', 'wins': 0, 'bets': 0, 'payout': 0.0},
        'wide_w12': {'desc': 'ワイド W1-2', 'wins': 0, 'bets': 0, 'payout': 0.0},
        'wide_w1p2': {'desc': 'ワイド W1+P2(W1≠P2)', 'wins': 0, 'bets': 0, 'payout': 0.0},
        # 馬連系
        'umaren_p12': {'desc': '馬連 P1-2', 'wins': 0, 'bets': 0, 'payout': 0.0},
        'umaren_w12': {'desc': '馬連 W1-2', 'wins': 0, 'bets': 0, 'payout': 0.0},
        # 馬単系 (1着固定)
        'umatan_w1_p2': {'desc': '馬単 W1→P2', 'wins': 0, 'bets': 0, 'payout': 0.0},
        'umatan_w1_w2': {'desc': '馬単 W1→W2', 'wins': 0, 'bets': 0, 'payout': 0.0},
        'umatan_w1_p23': {'desc': '馬単 W1→P2,3', 'wins': 0, 'bets': 0, 'payout': 0.0},
        'umatan_w1_w23': {'desc': '馬単 W1→W2,3', 'wins': 0, 'bets': 0, 'payout': 0.0},
        # 単勝
        'win_w1': {'desc': '単勝 W1', 'wins': 0, 'bets': 0, 'payout': 0.0},
        'win_p1': {'desc': '単勝 P1', 'wins': 0, 'bets': 0, 'payout': 0.0},
    }

    # 条件別集計
    cond_stats = {
        'all': defaultdict(lambda: {'wins': 0, 'bets': 0, 'payout': 0.0}),
        'ge9': defaultdict(lambda: {'wins': 0, 'bets': 0, 'payout': 0.0}),  # 9頭以上
    }

    for race in races:
        entries = race.get('entries', [])
        num_runners = race.get('num_runners', len(entries))

        # rank_p, rank_wでソート
        by_rank_p = sorted(entries, key=lambda e: e.get('rank_p') or 99)
        by_rank_w = sorted(entries, key=lambda e: e.get('rank_w') or 99)

        # 実着順マップ
        actual = {}
        for e in entries:
            af = e.get('actual_finish')
            if af and af > 0:
                actual[e['umaban']] = af

        if not actual:
            continue

        # 各モデルのTop N
        p1 = by_rank_p[0] if len(by_rank_p) >= 1 else None
        p2 = by_rank_p[1] if len(by_rank_p) >= 2 else None
        p3 = by_rank_p[2] if len(by_rank_p) >= 3 else None
        w1 = by_rank_w[0] if len(by_rank_w) >= 1 else None
        w2 = by_rank_w[1] if len(by_rank_w) >= 2 else None
        w3 = by_rank_w[2] if len(by_rank_w) >= 3 else None

        def _af(e):
            return actual.get(e['umaban'], 99) if e else 99

        conditions = ['all']
        if num_runners >= 9:
            conditions.append('ge9')

        for cond in conditions:
            stats = cond_stats[cond]

            # --- 単勝 ---
            if w1:
                stats['win_w1']['bets'] += 1
                if _af(w1) == 1:
                    stats['win_w1']['wins'] += 1
                    stats['win_w1']['payout'] += w1.get('odds', 0) or 0
            if p1:
                stats['win_p1']['bets'] += 1
                if _af(p1) == 1:
                    stats['win_p1']['wins'] += 1
                    stats['win_p1']['payout'] += p1.get('odds', 0) or 0

            # --- ワイド (3着内同士) ---
            if p1 and p2:
                stats['wide_p12']['bets'] += 1
                if _af(p1) <= 3 and _af(p2) <= 3:
                    stats['wide_p12']['wins'] += 1
                    # ワイドオッズは推定: 単勝オッズの平均の0.3倍程度
                    # 実際はDB必要だが、ここでは的中率のみ

            if w1 and w2:
                stats['wide_w12']['bets'] += 1
                if _af(w1) <= 3 and _af(w2) <= 3:
                    stats['wide_w12']['wins'] += 1

            if w1 and p2 and w1['umaban'] != p2['umaban']:
                stats['wide_w1p2']['bets'] += 1
                if _af(w1) <= 3 and _af(p2) <= 3:
                    stats['wide_w1p2']['wins'] += 1

            # --- 馬連 (1着-2着の組み合わせ、順不同) ---
            if p1 and p2:
                stats['umaren_p12']['bets'] += 1
                fp1, fp2 = _af(p1), _af(p2)
                if {fp1, fp2} == {1, 2}:
                    stats['umaren_p12']['wins'] += 1

            if w1 and w2:
                stats['umaren_w12']['bets'] += 1
                fw1, fw2 = _af(w1), _af(w2)
                if {fw1, fw2} == {1, 2}:
                    stats['umaren_w12']['wins'] += 1

            # --- 馬単 (1着固定→2着固定) ---
            if w1 and p2:
                stats['umatan_w1_p2']['bets'] += 1
                if _af(w1) == 1 and _af(p2) == 2:
                    stats['umatan_w1_p2']['wins'] += 1

            if w1 and w2:
                stats['umatan_w1_w2']['bets'] += 1
                if _af(w1) == 1 and _af(w2) == 2:
                    stats['umatan_w1_w2']['wins'] += 1

            # 馬単 W1→P2 or P3 (2点買い)
            if w1 and p2 and p3:
                stats['umatan_w1_p23']['bets'] += 2  # 2点
                if _af(w1) == 1:
                    if _af(p2) == 2:
                        stats['umatan_w1_p23']['wins'] += 1
                    if _af(p3) == 2:
                        stats['umatan_w1_p23']['wins'] += 1

            # 馬単 W1→W2 or W3 (2点買い)
            if w1 and w2 and w3:
                stats['umatan_w1_w23']['bets'] += 2
                if _af(w1) == 1:
                    if _af(w2) == 2:
                        stats['umatan_w1_w23']['wins'] += 1
                    if _af(w3) == 2:
                        stats['umatan_w1_w23']['wins'] += 1

    # 結果表示
    for cond_name, stats in cond_stats.items():
        nr_label = '全レース' if cond_name == 'all' else '9頭以上'
        print(f"\n{'='*60}")
        print(f"  {nr_label}")
        print(f"{'='*60}")
        print(f"{'戦略':>25} {'買い点':>6} {'的中':>5} {'的中率':>7}")
        print(f"{'-'*55}")

        for key in ['win_w1', 'win_p1', '',
                     'wide_p12', 'wide_w12', 'wide_w1p2', '',
                     'umaren_p12', 'umaren_w12', '',
                     'umatan_w1_p2', 'umatan_w1_w2',
                     'umatan_w1_p23', 'umatan_w1_w23']:
            if key == '':
                print()
                continue
            s = stats[key]
            if s['bets'] == 0:
                continue
            rate = s['wins'] / s['bets'] * 100
            print(f"{key:>25} {s['bets']:>6} {s['wins']:>5} {rate:>6.1f}%")

    # W1が1着の場合、2着は何番目の馬が多い?
    print(f"\n{'='*60}")
    print(f"  W1が1着の時、2着馬のrank_p/rank_w分布")
    print(f"{'='*60}")

    w1_wins = 0
    second_rank_p = defaultdict(int)
    second_rank_w = defaultdict(int)

    for race in races:
        entries = race.get('entries', [])
        by_rank_w = sorted(entries, key=lambda e: e.get('rank_w') or 99)
        if not by_rank_w:
            continue

        w1 = by_rank_w[0]
        actual = {}
        for e in entries:
            af = e.get('actual_finish')
            if af and af > 0:
                actual[e['umaban']] = af

        if actual.get(w1['umaban']) != 1:
            continue

        w1_wins += 1

        # 2着馬を特定
        second_uma = None
        for e in entries:
            if actual.get(e['umaban']) == 2:
                second_uma = e
                break

        if second_uma:
            rp = second_uma.get('rank_p') or 99
            rw = second_uma.get('rank_w') or 99
            second_rank_p[rp] += 1
            second_rank_w[rw] += 1

    print(f"W1が1着: {w1_wins}回")
    print(f"\n  2着馬のrank_p分布:")
    for rp in sorted(second_rank_p.keys()):
        cnt = second_rank_p[rp]
        pct = cnt / w1_wins * 100
        bar = '#' * int(pct / 2)
        print(f"    rank_p={rp:>2}: {cnt:>3}回 ({pct:>5.1f}%) {bar}")

    print(f"\n  2着馬のrank_w分布:")
    for rw in sorted(second_rank_w.keys()):
        cnt = second_rank_w[rw]
        pct = cnt / w1_wins * 100
        bar = '#' * int(pct / 2)
        print(f"    rank_w={rw:>2}: {cnt:>3}回 ({pct:>5.1f}%) {bar}")


if __name__ == '__main__':
    analyze()
