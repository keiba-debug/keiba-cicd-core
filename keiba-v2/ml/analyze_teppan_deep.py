"""深掘り分析: 最有望パターンの詳細"""

import json
import glob
import os
import sys
import mysql.connector
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = "c:/KEIBA-CICD/data3/races"


def get_wide_map(harai):
    m = {}
    for i in range(1, 8):
        u1 = (harai.get(f'WIDE{i}_KUMIBAN1') or '').strip()
        u2 = (harai.get(f'WIDE{i}_KUMIBAN2') or '').strip()
        pay = (harai.get(f'WIDE{i}_HARAIMODOSHIKIN') or '').strip()
        if u1 and u2 and pay and int(pay) > 0:
            m[(min(int(u1), int(u2)), max(int(u1), int(u2)))] = int(pay)
    return m


def get_umaren_map(harai):
    m = {}
    for i in range(1, 4):
        u1 = (harai.get(f'UMAREN{i}_KUMIBAN1') or '').strip()
        u2 = (harai.get(f'UMAREN{i}_KUMIBAN2') or '').strip()
        pay = (harai.get(f'UMAREN{i}_HARAIMODOSHIKIN') or '').strip()
        if u1 and u2 and pay and int(pay) > 0:
            m[(min(int(u1), int(u2)), max(int(u1), int(u2)))] = int(pay)
    return m


def main():
    conn = mysql.connector.connect(
        host='localhost', port=3306,
        user='root', password='test123!',
        database='mykeibadb'
    )

    records = []
    for year in [2025, 2026]:
        year_dir = f'{DATA_DIR}/{year}'
        if not os.path.isdir(year_dir):
            continue
        for month in range(1, 13):
            if year == 2026 and month > 3:
                break
            month_dir = f'{year_dir}/{month:02d}'
            if not os.path.isdir(month_dir):
                continue
            for day_name in sorted(os.listdir(month_dir)):
                date_dir = f'{month_dir}/{day_name}'
                pred_file = f'{date_dir}/predictions.json'
                if not os.path.isfile(pred_file):
                    continue
                with open(pred_file, encoding='utf-8') as f:
                    pred_data = json.load(f)
                for race in pred_data.get('races', []):
                    race_id = race.get('race_id', '')
                    entries = race.get('entries', [])
                    if not entries:
                        continue
                    teppan_list = [e for e in entries if e.get('market_signal') == '鉄板']
                    if not teppan_list:
                        continue
                    for teppan in teppan_list:
                        race_files = glob.glob(f'{date_dir}/race_{race_id}.json')
                        if not race_files:
                            continue
                        with open(race_files[0], encoding='utf-8') as f:
                            rd = json.load(f)
                        positions = {}
                        for ent in rd.get('entries', []):
                            u = ent.get('umaban')
                            fp = ent.get('finish_position')
                            if u and fp and fp > 0:
                                positions[u] = fp
                        if not positions:
                            continue

                        records.append({
                            'race_id': race_id,
                            'date_dir': date_dir,
                            'teppan_umaban': teppan['umaban'],
                            'teppan_name': teppan.get('horse_name', '?'),
                            'teppan_ard': teppan.get('ar_deviation', 0),
                            'teppan_rank_p': teppan.get('rank_p', 99),
                            'teppan_rank_w': teppan.get('rank_w', 99),
                            'teppan_odds': teppan.get('odds', 0),
                            'teppan_popularity': teppan.get('popularity', 99),
                            'teppan_finish': positions.get(teppan['umaban'], 99),
                            'num_runners': race.get('num_runners', 0),
                            'entries': entries,
                            'positions': positions,
                        })

    race_ids = list(set(r['race_id'] for r in records))
    cur = conn.cursor(dictionary=True)
    haraimodoshi = {}
    for i in range(0, len(race_ids), 500):
        batch = race_ids[i:i + 500]
        ph = ','.join(['%s'] * len(batch))
        cur.execute(f'SELECT * FROM haraimodoshi WHERE RACE_CODE IN ({ph})', batch)
        for row in cur.fetchall():
            haraimodoshi[row['RACE_CODE']] = row

    # === 1. P1+W1馬連の詳細分析 ===
    print("=" * 80)
    print("【深掘り1】P1+W1 馬連 (2点) の詳細 - ROI 114.3%の中身")
    print("=" * 80)

    pw_umaren_detail = []
    for r in records:
        harai = haraimodoshi.get(r['race_id'])
        if not harai:
            continue
        entries_by_p = sorted(r['entries'], key=lambda e: e.get('pred_proba_p', 0), reverse=True)
        entries_by_w = sorted(r['entries'], key=lambda e: e.get('pred_proba_w', 0), reverse=True)
        p_others = [e for e in entries_by_p if e['umaban'] != r['teppan_umaban']]
        w_others = [e for e in entries_by_w if e['umaban'] != r['teppan_umaban']]

        if not p_others or not w_others:
            continue

        targets = []
        seen = set()
        for e in [p_others[0], w_others[0]]:
            if e['umaban'] not in seen:
                seen.add(e['umaban'])
                targets.append(e)

        umaren_map = get_umaren_map(harai)
        bet = 100 * len(targets)
        pay = 0
        for t in targets:
            pair = (min(r['teppan_umaban'], t['umaban']), max(r['teppan_umaban'], t['umaban']))
            if pair in umaren_map:
                pay += umaren_map[pair]

        pw_umaren_detail.append({
            'race_id': r['race_id'],
            'teppan_name': r['teppan_name'],
            'teppan_odds': r['teppan_odds'],
            'teppan_pop': r['teppan_popularity'],
            'teppan_finish': r['teppan_finish'],
            'teppan_ard': r['teppan_ard'],
            'teppan_rank_p': r['teppan_rank_p'],
            'n_targets': len(targets),
            'is_same': len(targets) == 1,
            'bet': bet,
            'pay': pay,
            'num_runners': r['num_runners'],
        })

    # P1==W1の場合 vs 異なる場合
    same = [d for d in pw_umaren_detail if d['is_same']]
    diff = [d for d in pw_umaren_detail if not d['is_same']]

    print(f"\nP1==W1 (1点): n={len(same)}, "
          f"的中={sum(1 for d in same if d['pay']>0)}/{len(same)} "
          f"({sum(1 for d in same if d['pay']>0)/len(same)*100:.1f}%), "
          f"ROI={sum(d['pay'] for d in same)/sum(d['bet'] for d in same)*100:.1f}%")
    print(f"P1!=W1 (2点): n={len(diff)}, "
          f"的中={sum(1 for d in diff if d['pay']>0)}/{len(diff)} "
          f"({sum(1 for d in diff if d['pay']>0)/len(diff)*100:.1f}%), "
          f"ROI={sum(d['pay'] for d in diff)/sum(d['bet'] for d in diff)*100:.1f}%")

    # P1+W1 馬連 高配当Top10
    print("\n--- P1+W1 馬連 高配当Top10 ---")
    hits = [(d, d['pay']) for d in pw_umaren_detail if d['pay'] > 0]
    hits.sort(key=lambda x: x[1], reverse=True)
    print(f"{'race_id':<20} {'馬名':<15} {'着順':>4} {'odds':>6} {'人気':>4} {'配当':>8} {'P1=W1':>6}")
    for d, p in hits[:10]:
        print(f"{d['race_id']:<20} {d['teppan_name']:<15} {d['teppan_finish']:>4} {d['teppan_odds']:>6.1f} {d['teppan_pop']:>4} {p:>8,} {'Y' if d['is_same'] else 'N':>6}")

    # === 2. 2番人気鉄板のワイド詳細 (ROI 131.1%) ===
    print()
    print("=" * 80)
    print("【深掘り2】2番人気鉄板 ワイドP_top3 (ROI 131.1%) の中身")
    print("=" * 80)

    nini2 = [r for r in records if r['teppan_popularity'] == 2]
    print(f"\n2番人気鉄板: n={len(nini2)}")
    print(f"  1着率: {sum(1 for r in nini2 if r['teppan_finish']==1)/len(nini2)*100:.1f}%")
    print(f"  3着内率: {sum(1 for r in nini2 if r['teppan_finish']<=3)/len(nini2)*100:.1f}%")
    print(f"  オッズ平均: {sum(r['teppan_odds'] for r in nini2)/len(nini2):.1f}")
    print(f"  ARd平均: {sum(r['teppan_ard'] for r in nini2)/len(nini2):.1f}")

    # 月別
    monthly = defaultdict(lambda: {'n': 0, 'bet': 0, 'pay': 0, 'hits': 0})
    for r in nini2:
        harai = haraimodoshi.get(r['race_id'])
        if not harai:
            continue
        entries_by_p = sorted(r['entries'], key=lambda e: e.get('pred_proba_p', 0), reverse=True)
        p_others = [e for e in entries_by_p if e['umaban'] != r['teppan_umaban']][:3]
        wide_map = get_wide_map(harai)

        pay = 0
        for t in p_others:
            pair = (min(r['teppan_umaban'], t['umaban']), max(r['teppan_umaban'], t['umaban']))
            if pair in wide_map:
                pay += wide_map[pair]

        ym = r['race_id'][:4] + '-' + r['race_id'][4:6]
        monthly[ym]['n'] += 1
        monthly[ym]['bet'] += 300
        monthly[ym]['pay'] += pay
        if pay > 0:
            monthly[ym]['hits'] += 1

    print(f"\n{'月':<10} {'件数':>5} {'的中':>5} {'投資':>8} {'回収':>8} {'ROI':>7}")
    print("-" * 50)
    for ym in sorted(monthly.keys()):
        m = monthly[ym]
        roi = m['pay'] / m['bet'] * 100 if m['bet'] > 0 else 0
        print(f"{ym:<10} {m['n']:>5} {m['hits']:>5} {m['bet']:>8,} {m['pay']:>8,} {roi:>6.1f}%")

    # === 3. ~1.5倍鉄板 馬連P_top2 (ROI 121.7%) ===
    print()
    print("=" * 80)
    print("【深掘り3】~1.5倍鉄板 馬連P_top2 (ROI 121.7%) の中身")
    print("=" * 80)

    low_odds = [r for r in records if r['teppan_odds'] < 1.5]
    print(f"\n~1.5倍鉄板: n={len(low_odds)}")
    print(f"  1着率: {sum(1 for r in low_odds if r['teppan_finish']==1)/len(low_odds)*100:.1f}%")
    print(f"  2着内率: {sum(1 for r in low_odds if r['teppan_finish']<=2)/len(low_odds)*100:.1f}%")
    print(f"  3着内率: {sum(1 for r in low_odds if r['teppan_finish']<=3)/len(low_odds)*100:.1f}%")

    for r in low_odds:
        harai = haraimodoshi.get(r['race_id'])
        if not harai:
            continue
        entries_by_p = sorted(r['entries'], key=lambda e: e.get('pred_proba_p', 0), reverse=True)
        p_others = [e for e in entries_by_p if e['umaban'] != r['teppan_umaban']][:2]
        umaren_map = get_umaren_map(harai)

        pay = 0
        for t in p_others:
            pair = (min(r['teppan_umaban'], t['umaban']), max(r['teppan_umaban'], t['umaban']))
            if pair in umaren_map:
                pay += umaren_map[pair]

    # 配当分布
    payouts = []
    for r in low_odds:
        harai = haraimodoshi.get(r['race_id'])
        if not harai:
            continue
        entries_by_p = sorted(r['entries'], key=lambda e: e.get('pred_proba_p', 0), reverse=True)
        p_others = [e for e in entries_by_p if e['umaban'] != r['teppan_umaban']][:2]
        umaren_map = get_umaren_map(harai)

        pay = 0
        for t in p_others:
            pair = (min(r['teppan_umaban'], t['umaban']), max(r['teppan_umaban'], t['umaban']))
            if pair in umaren_map:
                pay += umaren_map[pair]
        payouts.append(pay)

    hit_payouts = [p for p in payouts if p > 0]
    print(f"\n  的中時配当: min={min(hit_payouts) if hit_payouts else 0}, max={max(hit_payouts) if hit_payouts else 0}, "
          f"avg={sum(hit_payouts)/len(hit_payouts):.0f}" if hit_payouts else "")

    # === 4. 最終推奨戦略まとめ ===
    print()
    print("=" * 80)
    print("【まとめ】推奨戦略候補")
    print("=" * 80)

    strategies = [
        ("A: 鉄板全体 + P1+W1馬連", lambda r: True, 'pw_umaren'),
        ("B: 2番人気鉄板 + ワイドP_top3", lambda r: r['teppan_popularity'] == 2, 'p3_wide'),
        ("C: ~1.5倍鉄板 + 馬連P_top2", lambda r: r['teppan_odds'] < 1.5, 'p2_umaren'),
        ("D: ARd>=71 + 馬連P_top2", lambda r: r['teppan_ard'] >= 71, 'p2_umaren'),
        ("E: 1番人気&ARd>=68 + 馬連P_top2", lambda r: r['teppan_popularity'] == 1 and r['teppan_ard'] >= 68, 'p2_umaren'),
        ("F: 1番人気&ARd>=68 + ワイドP_top3", lambda r: r['teppan_popularity'] == 1 and r['teppan_ard'] >= 68, 'p3_wide'),
        ("G: ~1.5倍鉄板 + ワイドP_top3", lambda r: r['teppan_odds'] < 1.5, 'p3_wide'),
        ("H: 2番人気 + P1+W1馬連", lambda r: r['teppan_popularity'] == 2, 'pw_umaren'),
    ]

    print(f"\n{'戦略':<40} {'n':>4} {'的中率':>7} {'ROI':>7} {'月平均件数':>8}")
    print("-" * 70)

    for label, filt, strat_type in strategies:
        filtered = [r for r in records if filt(r)]
        if not filtered:
            continue

        total_bet = total_pay = hits = 0
        for r in filtered:
            harai = haraimodoshi.get(r['race_id'])
            if not harai:
                continue

            entries_by_p = sorted(r['entries'], key=lambda e: e.get('pred_proba_p', 0), reverse=True)
            entries_by_w = sorted(r['entries'], key=lambda e: e.get('pred_proba_w', 0), reverse=True)
            p_others = [e for e in entries_by_p if e['umaban'] != r['teppan_umaban']]
            w_others = [e for e in entries_by_w if e['umaban'] != r['teppan_umaban']]
            wide_map = get_wide_map(harai)
            umaren_map = get_umaren_map(harai)

            if strat_type == 'pw_umaren':
                targets = []
                seen = set()
                for e in [p_others[0], w_others[0]] if p_others and w_others else []:
                    if e['umaban'] not in seen:
                        seen.add(e['umaban'])
                        targets.append(e)
                bet = 100 * len(targets)
                pay = 0
                for t in targets:
                    pair = (min(r['teppan_umaban'], t['umaban']), max(r['teppan_umaban'], t['umaban']))
                    if pair in umaren_map:
                        pay += umaren_map[pair]
            elif strat_type == 'p3_wide':
                targets = p_others[:3]
                bet = 300
                pay = 0
                for t in targets:
                    pair = (min(r['teppan_umaban'], t['umaban']), max(r['teppan_umaban'], t['umaban']))
                    if pair in wide_map:
                        pay += wide_map[pair]
            elif strat_type == 'p2_umaren':
                targets = p_others[:2]
                bet = 200
                pay = 0
                for t in targets:
                    pair = (min(r['teppan_umaban'], t['umaban']), max(r['teppan_umaban'], t['umaban']))
                    if pair in umaren_map:
                        pay += umaren_map[pair]
            else:
                continue

            total_bet += bet
            total_pay += pay
            if pay > 0:
                hits += 1

        n = len(filtered)
        hr = hits / n * 100
        roi = total_pay / total_bet * 100 if total_bet > 0 else 0
        # 期間: 2025-01 to 2026-03 = 15ヶ月
        months = 15
        avg_per_month = n / months
        print(f"{label:<40} {n:>4} {hr:>6.1f}% {roi:>6.1f}% {avg_per_month:>7.1f}")

    conn.close()


if __name__ == '__main__':
    main()
