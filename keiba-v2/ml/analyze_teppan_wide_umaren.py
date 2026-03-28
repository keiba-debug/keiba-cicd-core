"""
螺旋丸の鉄板複勝推奨馬を軸にしたワイド・馬連バックテスト分析

predictions.jsonからmarket_signal="鉄板"の馬を抽出し、
同レースのPモデル/Wモデル上位馬との組み合わせで
ワイド・馬連の成績をバックテストする。
"""

import json
import glob
import os
import sys
import mysql.connector
from collections import defaultdict
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

DATA_DIR = "c:/KEIBA-CICD/data3"
RACE_DIR = f"{DATA_DIR}/races"


def load_haraimodoshi(conn, race_ids):
    """haraimodoshiテーブルからワイド・馬連の払戻データを取得"""
    if not race_ids:
        return {}

    cur = conn.cursor(dictionary=True)
    result = {}

    # バッチで取得（1000件ずつ）
    race_id_list = list(race_ids)
    for i in range(0, len(race_id_list), 500):
        batch = race_id_list[i:i+500]
        placeholders = ','.join(['%s'] * len(batch))
        query = f"SELECT * FROM haraimodoshi WHERE RACE_CODE IN ({placeholders})"
        cur.execute(query, batch)
        for row in cur.fetchall():
            result[row['RACE_CODE']] = row

    return result


def parse_wide_payouts(row):
    """haraimodoshi行からワイドの払戻を解析"""
    payouts = []
    for i in range(1, 8):
        k1 = f'WIDE{i}_KUMIBAN1'
        k2 = f'WIDE{i}_KUMIBAN2'
        kp = f'WIDE{i}_HARAIMODOSHIKIN'
        if row.get(k1) and row.get(k2) and row.get(kp):
            uma1 = row[k1].strip()
            uma2 = row[k2].strip()
            payout = row[kp].strip()
            if uma1 and uma2 and payout and int(payout) > 0:
                payouts.append({
                    'uma1': int(uma1),
                    'uma2': int(uma2),
                    'payout': int(payout)
                })
    return payouts


def parse_umaren_payouts(row):
    """haraimodoshi行から馬連の払戻を解析"""
    payouts = []
    for i in range(1, 4):
        k1 = f'UMAREN{i}_KUMIBAN1'
        k2 = f'UMAREN{i}_KUMIBAN2'
        kp = f'UMAREN{i}_HARAIMODOSHIKIN'
        if row.get(k1) and row.get(k2) and row.get(kp):
            uma1 = row[k1].strip()
            uma2 = row[k2].strip()
            payout = row[kp].strip()
            if uma1 and uma2 and payout and int(payout) > 0:
                payouts.append({
                    'uma1': int(uma1),
                    'uma2': int(uma2),
                    'payout': int(payout)
                })
    return payouts


def load_finish_positions(date_dir, race_id):
    """レースJSONから着順を読み込み"""
    race_files = glob.glob(f"{date_dir}/race_{race_id}.json")
    if not race_files:
        return {}

    with open(race_files[0], encoding='utf-8') as f:
        race_data = json.load(f)

    positions = {}
    for entry in race_data.get('entries', []):
        umaban = entry.get('umaban')
        fp = entry.get('finish_position')
        if umaban and fp and fp > 0:
            positions[umaban] = fp
    return positions


def main():
    conn = mysql.connector.connect(
        host='localhost', port=3306,
        user='root', password='test123!',
        database='mykeibadb'
    )

    # Step 1: 全日程のpredictions.jsonを読み込み、鉄板馬を集める
    print("=" * 70)
    print("螺旋丸 鉄板複勝推奨馬 × ワイド・馬連 バックテスト分析")
    print("=" * 70)
    print()

    teppan_races = []  # (race_id, date_dir, teppan_entry, all_entries, race_info)
    all_race_ids = set()
    dates_scanned = 0
    no_predictions = 0

    # 2025-01 〜 2026-03
    for year in [2025, 2026]:
        year_dir = f"{RACE_DIR}/{year}"
        if not os.path.isdir(year_dir):
            continue
        for month in range(1, 13):
            if year == 2026 and month > 3:
                break
            month_dir = f"{year_dir}/{month:02d}"
            if not os.path.isdir(month_dir):
                continue
            for day_name in sorted(os.listdir(month_dir)):
                date_dir = f"{month_dir}/{day_name}"
                pred_file = f"{date_dir}/predictions.json"
                if not os.path.isfile(pred_file):
                    continue

                dates_scanned += 1
                try:
                    with open(pred_file, encoding='utf-8') as f:
                        pred_data = json.load(f)
                except:
                    continue

                races = pred_data.get('races', [])
                if not races:
                    no_predictions += 1
                    continue

                for race in races:
                    race_id = race.get('race_id', '')
                    entries = race.get('entries', [])
                    if not entries:
                        continue

                    all_race_ids.add(race_id)

                    # 鉄板馬を探す
                    for entry in entries:
                        if entry.get('market_signal') == '鉄板':
                            teppan_races.append({
                                'race_id': race_id,
                                'date_dir': date_dir,
                                'teppan': entry,
                                'entries': entries,
                                'race_info': {
                                    'num_runners': race.get('num_runners', 0),
                                    'track_type': race.get('track_type', ''),
                                    'distance': race.get('distance', 0),
                                    'grade': race.get('grade', ''),
                                    'venue_name': race.get('venue_name', ''),
                                }
                            })

    print(f"スキャン日数: {dates_scanned}")
    print(f"鉄板馬出現レース数: {len(teppan_races)}")
    print()

    # Step 2: 払戻データを取得
    teppan_race_ids = set(r['race_id'] for r in teppan_races)
    print(f"払戻データ取得中... ({len(teppan_race_ids)} races)")
    haraimodoshi = load_haraimodoshi(conn, teppan_race_ids)
    print(f"払戻データ取得完了: {len(haraimodoshi)} races")
    print()

    # Step 3: 着順データを取得して分析
    # 基本成績
    total = 0
    win = 0
    place2 = 0
    place3 = 0
    no_result = 0

    # ワイド・馬連の結果を格納
    wide_results = defaultdict(list)  # key: strategy_name, value: list of (bet, payout_or_0)
    umaren_results = defaultdict(list)

    for item in teppan_races:
        race_id = item['race_id']
        date_dir = item['date_dir']
        teppan = item['teppan']
        entries = item['entries']
        race_info = item['race_info']

        teppan_umaban = teppan['umaban']
        teppan_ard = teppan.get('ar_deviation', 0)
        teppan_rank_p = teppan.get('rank_p', 99)
        teppan_rank_w = teppan.get('rank_w', 99)
        num_runners = race_info.get('num_runners', 0)

        # 着順を取得
        positions = load_finish_positions(date_dir, race_id)
        if not positions:
            no_result += 1
            continue

        teppan_finish = positions.get(teppan_umaban, 99)

        total += 1
        if teppan_finish == 1:
            win += 1
        if teppan_finish <= 2:
            place2 += 1
        if teppan_finish <= 3:
            place3 += 1

        # 払戻データ
        harai = haraimodoshi.get(race_id)
        if not harai:
            continue

        wide_payouts = parse_wide_payouts(harai)
        umaren_payouts = parse_umaren_payouts(harai)

        # ワイド的中判定用のdict: (小さい番号, 大きい番号) -> payout
        wide_map = {}
        for wp in wide_payouts:
            key = (min(wp['uma1'], wp['uma2']), max(wp['uma1'], wp['uma2']))
            wide_map[key] = wp['payout']

        umaren_map = {}
        for up in umaren_payouts:
            key = (min(up['uma1'], up['uma2']), max(up['uma1'], up['uma2']))
            umaren_map[key] = up['payout']

        # エントリーをソート（Pモデル、Wモデル）
        entries_by_p = sorted(entries, key=lambda e: e.get('pred_proba_p', 0), reverse=True)
        entries_by_w = sorted(entries, key=lambda e: e.get('pred_proba_w', 0), reverse=True)

        # 鉄板馬を除いた上位馬
        p_others = [e for e in entries_by_p if e['umaban'] != teppan_umaban]
        w_others = [e for e in entries_by_w if e['umaban'] != teppan_umaban]

        # === ワイド戦略 ===
        # Pモデル上位2頭とのワイド (2点)
        for n_targets, label in [(2, 'P_top2'), (3, 'P_top3'), (4, 'P_top4')]:
            targets = p_others[:n_targets]
            bet_amount = 100 * n_targets
            total_payout = 0
            for t in targets:
                pair = (min(teppan_umaban, t['umaban']), max(teppan_umaban, t['umaban']))
                if pair in wide_map:
                    total_payout += wide_map[pair]
            wide_results[f'wide_{label}'].append({
                'race_id': race_id,
                'bet': bet_amount,
                'payout': total_payout,
                'teppan_ard': teppan_ard,
                'teppan_rank_p': teppan_rank_p,
                'num_runners': num_runners,
                'teppan_finish': teppan_finish,
            })

        # Wモデル上位とのワイド
        for n_targets, label in [(2, 'W_top2'), (3, 'W_top3')]:
            targets = w_others[:n_targets]
            bet_amount = 100 * n_targets
            total_payout = 0
            for t in targets:
                pair = (min(teppan_umaban, t['umaban']), max(teppan_umaban, t['umaban']))
                if pair in wide_map:
                    total_payout += wide_map[pair]
            wide_results[f'wide_{label}'].append({
                'race_id': race_id,
                'bet': bet_amount,
                'payout': total_payout,
                'teppan_ard': teppan_ard,
                'teppan_rank_p': teppan_rank_p,
                'num_runners': num_runners,
                'teppan_finish': teppan_finish,
            })

        # === 馬連戦略 ===
        # Pモデル上位とのの馬連
        for n_targets, label in [(2, 'P_top2'), (3, 'P_top3')]:
            targets = p_others[:n_targets]
            bet_amount = 100 * n_targets
            total_payout = 0
            for t in targets:
                pair = (min(teppan_umaban, t['umaban']), max(teppan_umaban, t['umaban']))
                if pair in umaren_map:
                    total_payout += umaren_map[pair]
            umaren_results[f'umaren_{label}'].append({
                'race_id': race_id,
                'bet': bet_amount,
                'payout': total_payout,
                'teppan_ard': teppan_ard,
                'teppan_rank_p': teppan_rank_p,
                'num_runners': num_runners,
                'teppan_finish': teppan_finish,
            })

        # Wモデル上位との馬連
        for n_targets, label in [(2, 'W_top2'), (3, 'W_top3')]:
            targets = w_others[:n_targets]
            bet_amount = 100 * n_targets
            total_payout = 0
            for t in targets:
                pair = (min(teppan_umaban, t['umaban']), max(teppan_umaban, t['umaban']))
                if pair in umaren_map:
                    total_payout += umaren_map[pair]
            umaren_results[f'umaren_{label}'].append({
                'race_id': race_id,
                'bet': bet_amount,
                'payout': total_payout,
                'teppan_ard': teppan_ard,
                'teppan_rank_p': teppan_rank_p,
                'num_runners': num_runners,
                'teppan_finish': teppan_finish,
            })

    conn.close()

    # === 結果出力 ===
    print("=" * 70)
    print("【1】鉄板複勝推奨馬の基本成績")
    print("=" * 70)
    print(f"  対象レース数: {total} (着順不明: {no_result})")
    print(f"  1着率: {win}/{total} = {win/total*100:.1f}%")
    print(f"  2着内率: {place2}/{total} = {place2/total*100:.1f}%")
    print(f"  3着内率(複勝): {place3}/{total} = {place3/total*100:.1f}%")
    print()

    # ワイド成績
    print("=" * 70)
    print("【2】鉄板馬軸ワイド成績")
    print("=" * 70)
    print(f"{'戦略':<20} {'件数':>5} {'的中':>5} {'的中率':>7} {'投資':>10} {'回収':>10} {'ROI':>7} {'平均配当':>8}")
    print("-" * 70)
    for name in sorted(wide_results.keys()):
        results = wide_results[name]
        n = len(results)
        hits = sum(1 for r in results if r['payout'] > 0)
        total_bet = sum(r['bet'] for r in results)
        total_payout = sum(r['payout'] for r in results)
        avg_payout = total_payout / hits if hits > 0 else 0
        roi = total_payout / total_bet * 100 if total_bet > 0 else 0
        print(f"{name:<20} {n:>5} {hits:>5} {hits/n*100:>6.1f}% {total_bet:>10,} {total_payout:>10,} {roi:>6.1f}% {avg_payout:>8.0f}")
    print()

    # 馬連成績
    print("=" * 70)
    print("【3】鉄板馬軸馬連成績")
    print("=" * 70)
    print(f"{'戦略':<20} {'件数':>5} {'的中':>5} {'的中率':>7} {'投資':>10} {'回収':>10} {'ROI':>7} {'平均配当':>8}")
    print("-" * 70)
    for name in sorted(umaren_results.keys()):
        results = umaren_results[name]
        n = len(results)
        hits = sum(1 for r in results if r['payout'] > 0)
        total_bet = sum(r['bet'] for r in results)
        total_payout = sum(r['payout'] for r in results)
        avg_payout = total_payout / hits if hits > 0 else 0
        roi = total_payout / total_bet * 100 if total_bet > 0 else 0
        print(f"{name:<20} {n:>5} {hits:>5} {hits/n*100:>6.1f}% {total_bet:>10,} {total_payout:>10,} {roi:>6.1f}% {avg_payout:>8.0f}")
    print()

    # === フィルター別分析 ===
    print("=" * 70)
    print("【4】フィルター別成績（ワイド P_top3 基準）")
    print("=" * 70)

    base_key = 'wide_P_top3'
    if base_key in wide_results:
        base_results = wide_results[base_key]

        # ARd帯別
        print("\n--- ARd帯別 ---")
        print(f"{'フィルター':<25} {'件数':>5} {'的中':>5} {'的中率':>7} {'ROI':>7}")
        print("-" * 55)
        for ard_min, label in [(0, 'ARd全体'), (60, 'ARd≥60'), (65, 'ARd≥65'), (70, 'ARd≥70')]:
            filtered = [r for r in base_results if r['teppan_ard'] >= ard_min]
            if not filtered:
                continue
            n = len(filtered)
            hits = sum(1 for r in filtered if r['payout'] > 0)
            total_bet = sum(r['bet'] for r in filtered)
            total_payout = sum(r['payout'] for r in filtered)
            roi = total_payout / total_bet * 100 if total_bet > 0 else 0
            print(f"{label:<25} {n:>5} {hits:>5} {hits/n*100:>6.1f}% {roi:>6.1f}%")

        # 頭数別
        print("\n--- 頭数別 ---")
        print(f"{'フィルター':<25} {'件数':>5} {'的中':>5} {'的中率':>7} {'ROI':>7}")
        print("-" * 55)
        for cond, label in [
            (lambda r: r['num_runners'] <= 14, '14頭以下'),
            (lambda r: r['num_runners'] >= 15, '15頭以上'),
        ]:
            filtered = [r for r in base_results if cond(r)]
            if not filtered:
                continue
            n = len(filtered)
            hits = sum(1 for r in filtered if r['payout'] > 0)
            total_bet = sum(r['bet'] for r in filtered)
            total_payout = sum(r['payout'] for r in filtered)
            roi = total_payout / total_bet * 100 if total_bet > 0 else 0
            print(f"{label:<25} {n:>5} {hits:>5} {hits/n*100:>6.1f}% {roi:>6.1f}%")

        # rank_p別
        print("\n--- 鉄板馬のrank_p別 ---")
        print(f"{'フィルター':<25} {'件数':>5} {'的中':>5} {'的中率':>7} {'ROI':>7}")
        print("-" * 55)
        for cond, label in [
            (lambda r: r['teppan_rank_p'] == 1, 'rank_p=1'),
            (lambda r: r['teppan_rank_p'] >= 2, 'rank_p≥2'),
        ]:
            filtered = [r for r in base_results if cond(r)]
            if not filtered:
                continue
            n = len(filtered)
            hits = sum(1 for r in filtered if r['payout'] > 0)
            total_bet = sum(r['bet'] for r in filtered)
            total_payout = sum(r['payout'] for r in filtered)
            roi = total_payout / total_bet * 100 if total_bet > 0 else 0
            print(f"{label:<25} {n:>5} {hits:>5} {hits/n*100:>6.1f}% {roi:>6.1f}%")

        # 鉄板馬の着順別（3着内 vs 4着以下）
        print("\n--- 鉄板馬の着順別 ---")
        print(f"{'フィルター':<25} {'件数':>5} {'的中':>5} {'的中率':>7} {'ROI':>7}")
        print("-" * 55)
        for cond, label in [
            (lambda r: r['teppan_finish'] <= 3, '鉄板馬3着内'),
            (lambda r: r['teppan_finish'] >= 4, '鉄板馬4着以下'),
        ]:
            filtered = [r for r in base_results if cond(r)]
            if not filtered:
                continue
            n = len(filtered)
            hits = sum(1 for r in filtered if r['payout'] > 0)
            total_bet = sum(r['bet'] for r in filtered)
            total_payout = sum(r['payout'] for r in filtered)
            roi = total_payout / total_bet * 100 if total_bet > 0 else 0
            print(f"{label:<25} {n:>5} {hits:>5} {hits/n*100:>6.1f}% {roi:>6.1f}%")

    # フィルター別（馬連 P_top2 基準）
    print()
    print("=" * 70)
    print("【5】フィルター別成績（馬連 P_top2 基準）")
    print("=" * 70)

    base_key = 'umaren_P_top2'
    if base_key in umaren_results:
        base_results = umaren_results[base_key]

        # ARd帯別
        print("\n--- ARd帯別 ---")
        print(f"{'フィルター':<25} {'件数':>5} {'的中':>5} {'的中率':>7} {'ROI':>7}")
        print("-" * 55)
        for ard_min, label in [(0, 'ARd全体'), (60, 'ARd≥60'), (65, 'ARd≥65'), (70, 'ARd≥70')]:
            filtered = [r for r in base_results if r['teppan_ard'] >= ard_min]
            if not filtered:
                continue
            n = len(filtered)
            hits = sum(1 for r in filtered if r['payout'] > 0)
            total_bet = sum(r['bet'] for r in filtered)
            total_payout = sum(r['payout'] for r in filtered)
            roi = total_payout / total_bet * 100 if total_bet > 0 else 0
            print(f"{label:<25} {n:>5} {hits:>5} {hits/n*100:>6.1f}% {roi:>6.1f}%")

        # 頭数別
        print("\n--- 頭数別 ---")
        print(f"{'フィルター':<25} {'件数':>5} {'的中':>5} {'的中率':>7} {'ROI':>7}")
        print("-" * 55)
        for cond, label in [
            (lambda r: r['num_runners'] <= 14, '14頭以下'),
            (lambda r: r['num_runners'] >= 15, '15頭以上'),
        ]:
            filtered = [r for r in base_results if cond(r)]
            if not filtered:
                continue
            n = len(filtered)
            hits = sum(1 for r in filtered if r['payout'] > 0)
            total_bet = sum(r['bet'] for r in filtered)
            total_payout = sum(r['payout'] for r in filtered)
            roi = total_payout / total_bet * 100 if total_bet > 0 else 0
            print(f"{label:<25} {n:>5} {hits:>5} {hits/n*100:>6.1f}% {roi:>6.1f}%")

        # rank_p別
        print("\n--- 鉄板馬のrank_p別 ---")
        print(f"{'フィルター':<25} {'件数':>5} {'的中':>5} {'的中率':>7} {'ROI':>7}")
        print("-" * 55)
        for cond, label in [
            (lambda r: r['teppan_rank_p'] == 1, 'rank_p=1'),
            (lambda r: r['teppan_rank_p'] >= 2, 'rank_p≥2'),
        ]:
            filtered = [r for r in base_results if cond(r)]
            if not filtered:
                continue
            n = len(filtered)
            hits = sum(1 for r in filtered if r['payout'] > 0)
            total_bet = sum(r['bet'] for r in filtered)
            total_payout = sum(r['payout'] for r in filtered)
            roi = total_payout / total_bet * 100 if total_bet > 0 else 0
            print(f"{label:<25} {n:>5} {hits:>5} {hits/n*100:>6.1f}% {roi:>6.1f}%")

    # === 高配当分析 ===
    print()
    print("=" * 70)
    print("【6】高配当ヒット例（ワイド P_top3、配当上位10件）")
    print("=" * 70)

    if 'wide_P_top3' in wide_results:
        hits_with_payout = [(r, r['payout']) for r in wide_results['wide_P_top3'] if r['payout'] > 0]
        hits_with_payout.sort(key=lambda x: x[1], reverse=True)
        print(f"{'race_id':<20} {'配当':>8} {'ARd':>6} {'rank_p':>7} {'着順':>5} {'頭数':>5}")
        print("-" * 55)
        for r, p in hits_with_payout[:10]:
            print(f"{r['race_id']:<20} {p:>8,} {r['teppan_ard']:>6.1f} {r['teppan_rank_p']:>7} {r['teppan_finish']:>5} {r['num_runners']:>5}")

    # === 月別推移 ===
    print()
    print("=" * 70)
    print("【7】月別推移（ワイド P_top3）")
    print("=" * 70)

    if 'wide_P_top3' in wide_results:
        monthly = defaultdict(lambda: {'n': 0, 'bet': 0, 'payout': 0, 'hits': 0})
        for r in wide_results['wide_P_top3']:
            rid = r['race_id']
            ym = rid[:4] + '-' + rid[4:6]
            monthly[ym]['n'] += 1
            monthly[ym]['bet'] += r['bet']
            monthly[ym]['payout'] += r['payout']
            if r['payout'] > 0:
                monthly[ym]['hits'] += 1

        print(f"{'月':<10} {'件数':>5} {'的中':>5} {'的中率':>7} {'投資':>10} {'回収':>10} {'ROI':>7}")
        print("-" * 60)
        for ym in sorted(monthly.keys()):
            m = monthly[ym]
            roi = m['payout'] / m['bet'] * 100 if m['bet'] > 0 else 0
            hit_rate = m['hits'] / m['n'] * 100 if m['n'] > 0 else 0
            print(f"{ym:<10} {m['n']:>5} {m['hits']:>5} {hit_rate:>6.1f}% {m['bet']:>10,} {m['payout']:>10,} {roi:>6.1f}%")


if __name__ == '__main__':
    main()
