"""追加分析: 鉄板馬のオッズ帯・人気・複合フィルター別成績"""

import json
import glob
import os
import sys
import mysql.connector
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = "c:/KEIBA-CICD/data3/races"


def get_wide_map(harai):
    wide_map = {}
    for i in range(1, 8):
        k1, k2, kp = f'WIDE{i}_KUMIBAN1', f'WIDE{i}_KUMIBAN2', f'WIDE{i}_HARAIMODOSHIKIN'
        u1 = (harai.get(k1) or '').strip()
        u2 = (harai.get(k2) or '').strip()
        pay = (harai.get(kp) or '').strip()
        if u1 and u2 and pay and int(pay) > 0:
            wide_map[(min(int(u1), int(u2)), max(int(u1), int(u2)))] = int(pay)
    return wide_map


def get_umaren_map(harai):
    umaren_map = {}
    for i in range(1, 4):
        k1, k2, kp = f'UMAREN{i}_KUMIBAN1', f'UMAREN{i}_KUMIBAN2', f'UMAREN{i}_HARAIMODOSHIKIN'
        u1 = (harai.get(k1) or '').strip()
        u2 = (harai.get(k2) or '').strip()
        pay = (harai.get(kp) or '').strip()
        if u1 and u2 and pay and int(pay) > 0:
            umaren_map[(min(int(u1), int(u2)), max(int(u1), int(u2)))] = int(pay)
    return umaren_map


def main():
    conn = mysql.connector.connect(
        host='localhost', port=3306,
        user='root', password='test123!',
        database='mykeibadb'
    )

    # Collect all teppan records
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

                        teppan_finish = positions.get(teppan['umaban'], 99)
                        records.append({
                            'race_id': race_id,
                            'teppan_umaban': teppan['umaban'],
                            'teppan_ard': teppan.get('ar_deviation', 0),
                            'teppan_rank_p': teppan.get('rank_p', 99),
                            'teppan_rank_w': teppan.get('rank_w', 99),
                            'teppan_odds': teppan.get('odds', 0),
                            'teppan_popularity': teppan.get('popularity', 99),
                            'teppan_finish': teppan_finish,
                            'num_runners': race.get('num_runners', 0),
                            'entries': entries,
                        })

    print(f'Total teppan records: {len(records)}')

    # Get haraimodoshi
    race_ids = list(set(r['race_id'] for r in records))
    cur = conn.cursor(dictionary=True)
    haraimodoshi = {}
    for i in range(0, len(race_ids), 500):
        batch = race_ids[i:i + 500]
        ph = ','.join(['%s'] * len(batch))
        cur.execute(f'SELECT * FROM haraimodoshi WHERE RACE_CODE IN ({ph})', batch)
        for row in cur.fetchall():
            haraimodoshi[row['RACE_CODE']] = row

    def compute_results(filtered_records, n_wide_targets=3, n_umaren_targets=2):
        w_bet = w_pay = w_hits = 0
        u_bet = u_pay = u_hits = 0
        for r in filtered_records:
            harai = haraimodoshi.get(r['race_id'])
            if not harai:
                continue
            entries_by_p = sorted(r['entries'], key=lambda e: e.get('pred_proba_p', 0), reverse=True)
            p_others = [e for e in entries_by_p if e['umaban'] != r['teppan_umaban']]

            wide_map = get_wide_map(harai)
            umaren_map = get_umaren_map(harai)

            # wide
            wp = 0
            for t in p_others[:n_wide_targets]:
                pair = (min(r['teppan_umaban'], t['umaban']), max(r['teppan_umaban'], t['umaban']))
                if pair in wide_map:
                    wp += wide_map[pair]
            w_bet += 100 * n_wide_targets
            w_pay += wp
            if wp > 0:
                w_hits += 1

            # umaren
            up = 0
            for t in p_others[:n_umaren_targets]:
                pair = (min(r['teppan_umaban'], t['umaban']), max(r['teppan_umaban'], t['umaban']))
                if pair in umaren_map:
                    up += umaren_map[pair]
            u_bet += 100 * n_umaren_targets
            u_pay += up
            if up > 0:
                u_hits += 1

        n = len(filtered_records)
        w_roi = w_pay / w_bet * 100 if w_bet > 0 else 0
        u_roi = u_pay / u_bet * 100 if u_bet > 0 else 0
        w_hr = w_hits / n * 100 if n > 0 else 0
        u_hr = u_hits / n * 100 if n > 0 else 0
        return n, w_hr, w_roi, u_hr, u_roi

    # === 分析A: オッズ帯別 ===
    print()
    print("=" * 70)
    print("【追加A】鉄板馬のオッズ帯別")
    print("=" * 70)
    print(f"{'オッズ帯':<15} {'件数':>5} | {'W的中率':>7} {'W_ROI':>7} | {'U的中率':>7} {'U_ROI':>7}")
    print("-" * 60)
    for lo, hi, label in [(0, 1.5, '~1.5'), (1.5, 2.0, '1.5-2.0'), (2.0, 3.0, '2.0-3.0'), (3.0, 99, '3.0+')]:
        filtered = [r for r in records if lo <= r['teppan_odds'] < hi]
        if len(filtered) < 5:
            continue
        n, w_hr, w_roi, u_hr, u_roi = compute_results(filtered)
        print(f"{label:<15} {n:>5} | {w_hr:>6.1f}% {w_roi:>6.1f}% | {u_hr:>6.1f}% {u_roi:>6.1f}%")

    # === 分析B: 人気別 ===
    print()
    print("=" * 70)
    print("【追加B】鉄板馬の人気別")
    print("=" * 70)
    print(f"{'人気':<15} {'件数':>5} | {'W的中率':>7} {'W_ROI':>7} | {'U的中率':>7} {'U_ROI':>7}")
    print("-" * 60)
    for lo, hi, label in [(1, 2, '1番人気'), (2, 3, '2番人気'), (3, 99, '3番人気+')]:
        filtered = [r for r in records if lo <= r['teppan_popularity'] < hi]
        if len(filtered) < 5:
            continue
        n, w_hr, w_roi, u_hr, u_roi = compute_results(filtered)
        print(f"{label:<15} {n:>5} | {w_hr:>6.1f}% {w_roi:>6.1f}% | {u_hr:>6.1f}% {u_roi:>6.1f}%")

    # === 分析C: ARd帯別(鉄板馬のARd最低65なので細分化) ===
    print()
    print("=" * 70)
    print("【追加C】鉄板馬のARd帯別(細分化)")
    print("=" * 70)
    print(f"{'ARd帯':<15} {'件数':>5} | {'W的中率':>7} {'W_ROI':>7} | {'U的中率':>7} {'U_ROI':>7}")
    print("-" * 60)
    for lo, hi, label in [(65, 67, '65-67'), (67, 69, '67-69'), (69, 71, '69-71'), (71, 76, '71+')]:
        filtered = [r for r in records if lo <= r['teppan_ard'] < hi]
        if len(filtered) < 5:
            continue
        n, w_hr, w_roi, u_hr, u_roi = compute_results(filtered)
        print(f"{label:<15} {n:>5} | {w_hr:>6.1f}% {w_roi:>6.1f}% | {u_hr:>6.1f}% {u_roi:>6.1f}%")

    # === 分析D: 複合フィルター ===
    print()
    print("=" * 70)
    print("【追加D】有望な複合フィルター")
    print("=" * 70)
    print(f"{'フィルター':<35} {'n':>4} | {'W的中':>6} {'W_ROI':>7} | {'U的中':>6} {'U_ROI':>7}")
    print("-" * 70)

    combos = [
        ('全体', lambda r: True),
        ('rank_p>=2', lambda r: r['teppan_rank_p'] >= 2),
        ('ARd>=70', lambda r: r['teppan_ard'] >= 70),
        ('odds>=2.0', lambda r: r['teppan_odds'] >= 2.0),
        ('1番人気 & ARd>=68', lambda r: r['teppan_popularity'] == 1 and r['teppan_ard'] >= 68),
        ('odds>=2.0 & rank_p>=2', lambda r: r['teppan_odds'] >= 2.0 and r['teppan_rank_p'] >= 2),
        ('14頭以下', lambda r: r['num_runners'] <= 14),
        ('14頭以下 & ARd>=68', lambda r: r['num_runners'] <= 14 and r['teppan_ard'] >= 68),
        ('15頭以上 & 1番人気', lambda r: r['num_runners'] >= 15 and r['teppan_popularity'] == 1),
        ('rank_w<=2', lambda r: r['teppan_rank_w'] <= 2),
        ('rank_p=1 & rank_w=1', lambda r: r['teppan_rank_p'] == 1 and r['teppan_rank_w'] == 1),
        ('rank_p>=2 & odds>=2.0', lambda r: r['teppan_rank_p'] >= 2 and r['teppan_odds'] >= 2.0),
    ]

    for label, filt in combos:
        filtered = [r for r in records if filt(r)]
        if len(filtered) < 10:
            continue
        n, w_hr, w_roi, u_hr, u_roi = compute_results(filtered)
        marker = " ***" if w_roi > 105 or u_roi > 110 else ""
        print(f"{label:<35} {n:>4} | {w_hr:>5.1f}% {w_roi:>6.1f}% | {u_hr:>5.1f}% {u_roi:>6.1f}%{marker}")

    # === 分析E: Wモデルベースで相手を選ぶ場合の成績 ===
    print()
    print("=" * 70)
    print("【追加E】相手馬選択: Pモデル vs Wモデル vs P+W混合")
    print("=" * 70)

    # mixed: P_top1 + W_top1 (重複除去して2頭)
    for label, strategy in [
        ('P_top3 wide', 'p3_wide'),
        ('W_top3 wide', 'w3_wide'),
        ('P1+W1 wide (2点)', 'pw_wide'),
        ('P_top2 umaren', 'p2_umaren'),
        ('W_top2 umaren', 'w2_umaren'),
        ('P1+W1 umaren (2点)', 'pw_umaren'),
    ]:
        total_bet = total_pay = hits = 0
        for r in records:
            harai = haraimodoshi.get(r['race_id'])
            if not harai:
                continue

            entries_by_p = sorted(r['entries'], key=lambda e: e.get('pred_proba_p', 0), reverse=True)
            entries_by_w = sorted(r['entries'], key=lambda e: e.get('pred_proba_w', 0), reverse=True)
            p_others = [e for e in entries_by_p if e['umaban'] != r['teppan_umaban']]
            w_others = [e for e in entries_by_w if e['umaban'] != r['teppan_umaban']]

            wide_map = get_wide_map(harai)
            umaren_map = get_umaren_map(harai)

            if strategy == 'p3_wide':
                targets = p_others[:3]
                payout_map = wide_map
                bet = 300
            elif strategy == 'w3_wide':
                targets = w_others[:3]
                payout_map = wide_map
                bet = 300
            elif strategy == 'pw_wide':
                # P1 + W1, deduplicated
                target_set = set()
                tgts = []
                for e in [p_others[0], w_others[0]] if p_others and w_others else []:
                    if e['umaban'] not in target_set:
                        target_set.add(e['umaban'])
                        tgts.append(e)
                targets = tgts
                payout_map = wide_map
                bet = 100 * len(targets)
            elif strategy == 'p2_umaren':
                targets = p_others[:2]
                payout_map = umaren_map
                bet = 200
            elif strategy == 'w2_umaren':
                targets = w_others[:2]
                payout_map = umaren_map
                bet = 200
            elif strategy == 'pw_umaren':
                target_set = set()
                tgts = []
                for e in [p_others[0], w_others[0]] if p_others and w_others else []:
                    if e['umaban'] not in target_set:
                        target_set.add(e['umaban'])
                        tgts.append(e)
                targets = tgts
                payout_map = umaren_map
                bet = 100 * len(targets)
            else:
                continue

            pay = 0
            for t in targets:
                pair = (min(r['teppan_umaban'], t['umaban']), max(r['teppan_umaban'], t['umaban']))
                if pair in payout_map:
                    pay += payout_map[pair]

            total_bet += bet
            total_pay += pay
            if pay > 0:
                hits += 1

        n = len(records)
        hr = hits / n * 100
        roi = total_pay / total_bet * 100 if total_bet > 0 else 0
        print(f"  {label:<30} 的中 {hits:>4}/{n} ({hr:.1f}%)  投資 {total_bet:>10,}  回収 {total_pay:>10,}  ROI {roi:.1f}%")

    conn.close()


if __name__ == '__main__':
    main()
