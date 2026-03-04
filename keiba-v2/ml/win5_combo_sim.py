#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WIN5 A+B+C+D 併用 精密週次シミュレーション
- Plan A: w_top2 (rank_w top2, 32pts, 毎週)
- Plan B: w_ard1st_55_tiered (条件付き)
- Plan C: union_top2 (rank_w∪rank_p top2)
- Plan D: w2_ar1_p1 (rank_w top2 ∪ AR偏差値1位 ∪ rank_p 1位)
- A+B / A+B+C / A+D / A+B+D 併用
重複的中の考慮あり
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.config import data_root, ml_dir
from core import db


# ============================================================
# Data Load
# ============================================================
def load_win5_schedule():
    schedule_rows = db.query("""
        SELECT w.KAISAI_NEN, w.KAISAI_GAPPI,
            w.RACE_CODE1, w.KEIBAJO_CODE1, w.RACE_BANGO1,
            w.RACE_CODE2, w.KEIBAJO_CODE2, w.RACE_BANGO2,
            w.RACE_CODE3, w.KEIBAJO_CODE3, w.RACE_BANGO3,
            w.RACE_CODE4, w.KEIBAJO_CODE4, w.RACE_BANGO4,
            w.RACE_CODE5, w.KEIBAJO_CODE5, w.RACE_BANGO5,
            w.TEKICHU_NASHI_FLAG
        FROM win5 w ORDER BY w.KAISAI_NEN, w.KAISAI_GAPPI
    """)
    payout_rows = db.query("""
        SELECT KAISAI_NEN, KAISAI_GAPPI,
            WIN5_KUMIBAN1, WIN5_KUMIBAN2, WIN5_KUMIBAN3,
            WIN5_KUMIBAN4, WIN5_KUMIBAN5,
            WIN5_HARAIMODOSHIKIN, TEKICHU_HYOSU
        FROM win5_haraimodoshi ORDER BY KAISAI_NEN, KAISAI_GAPPI
    """)
    payout_index = {}
    for row in payout_rows:
        key = row['KAISAI_NEN'].strip() + row['KAISAI_GAPPI'].strip()
        if key not in payout_index:
            payout_index[key] = row

    weeks = []
    for row in schedule_rows:
        year = row['KAISAI_NEN'].strip()
        gappi = row['KAISAI_GAPPI'].strip()
        date_str = year + gappi
        races = []
        for i in range(1, 6):
            rc = (row.get(f'RACE_CODE{i}') or '').strip()
            vc = (row.get(f'KEIBAJO_CODE{i}') or '').strip()
            rn = (row.get(f'RACE_BANGO{i}') or '').strip()
            pr = payout_index.get(date_str)
            winner = 0
            if pr:
                kb = (pr.get(f'WIN5_KUMIBAN{i}') or '').strip()
                winner = int(kb) if kb and kb.isdigit() else 0
            races.append({
                'race_id': rc, 'venue': vc,
                'race_num': rn, 'winner': winner
            })
        pr = payout_index.get(date_str)
        payout = 0
        if pr:
            raw = (pr.get('WIN5_HARAIMODOSHIKIN') or '').strip()
            payout = int(raw) if raw and raw.isdigit() else 0
        no_hit = (row.get('TEKICHU_NASHI_FLAG') or '').strip() == '1'
        weeks.append({
            'date': date_str, 'races': races,
            'payout': payout, 'no_hit': no_hit
        })
    return weeks


def load_cache():
    with open(str(ml_dir() / "backtest_cache.json"), encoding='utf-8') as f:
        cache = json.load(f)
    idx = {}
    race_list = cache if isinstance(cache, list) else list(cache.values())
    for rd in race_list:
        rid = rd.get('race_id', '')
        if not rid:
            continue
        entries = []
        for e in rd.get('entries', []):
            ard = float(e.get('ar_deviation', 0) or 0)
            if ard == 0:
                pm = float(e.get('predicted_margin', 0) or 0)
                ard = 50 + pm * 20
            entries.append({
                'umaban': int(e.get('umaban', 0)),
                'horse_name': e.get('horse_name', ''),
                'rank_w': int(e.get('rank_w', 0) or 0),
                'rank_p': int(e.get('rank_p', 0) or 0),
                'ar_deviation': ard,
                'is_win': bool(e.get('is_win', False)),
            })
        idx[rid] = {'entries': entries, 'count': len(entries)}
    return idx


# ============================================================
# Strategy implementations
# ============================================================
def get_sorted(entries, rank_key):
    if rank_key == 'wp_sum':
        valid = [e for e in entries if e['rank_w'] > 0 and e['rank_p'] > 0]
        return sorted(valid, key=lambda e: e['rank_w'] + e['rank_p'])
    return sorted(
        [e for e in entries if e.get(rank_key, 0) > 0],
        key=lambda e: e[rank_key]
    )


def plan_a_select(pred):
    """w_top2: rank_w上位2頭"""
    top = get_sorted(pred['entries'], 'rank_w')
    return [e['umaban'] for e in top[:2]] if top else []


def plan_b_select(pred):
    """w_ard1st_55_tiered: ARd1位>=55でtiered"""
    top = get_sorted(pred['entries'], 'rank_w')
    if not top:
        return None
    ard_1st = top[0]['ar_deviation']
    if ard_1st < 55:
        return None
    if ard_1st >= 70:
        n = 1
    elif ard_1st >= 65:
        n = 2
    elif ard_1st >= 60:
        n = 3
    elif ard_1st >= 55:
        n = 4
    else:
        n = 5
    return [e['umaban'] for e in top[:n]]


def plan_c_select(pred):
    """union_top2: rank_w top2 ∪ rank_p top2 の和集合"""
    w_top = get_sorted(pred['entries'], 'rank_w')[:2]
    p_top = get_sorted(pred['entries'], 'rank_p')[:2]
    selected = set()
    for e in w_top + p_top:
        selected.add(e['umaban'])
    return list(selected)


def plan_d_select(pred):
    """w2_ar1_p1: rank_w top2 ∪ AR偏差値1位 ∪ rank_p 1位 の和集合"""
    uma_set = set()
    w_top = get_sorted(pred['entries'], 'rank_w')[:2]
    for e in w_top:
        uma_set.add(e['umaban'])
    # AR deviation top1
    ar_top = sorted(pred['entries'], key=lambda e: -e['ar_deviation'])[:1]
    for e in ar_top:
        uma_set.add(e['umaban'])
    # rank_p top1
    p_top = get_sorted(pred['entries'], 'rank_p')[:1]
    for e in p_top:
        uma_set.add(e['umaban'])
    return list(uma_set)


def simulate_plan(weeks, pred_index, plan_name, select_fn):
    """1つのプランを週次シミュレーション"""
    results = []
    for week in weeks:
        date = week['date']
        races = week['races']
        payout = week['payout']

        race_selections = []
        skip_week = False
        for race in races:
            rid = race['race_id']
            pred = pred_index.get(rid)
            if not pred:
                race_selections.append([])
                continue
            sel = select_fn(pred)
            if sel is None:
                skip_week = True
                break
            race_selections.append(sel)

        if skip_week or len(race_selections) < 5:
            results.append({
                'date': date, 'skip': True, 'cost': 0, 'payout': 0,
                'tickets': 0, 'hit': False, 'selections': [],
            })
            continue

        ticket_counts = [max(len(s), 1) for s in race_selections]
        total_tickets = 1
        for tc in ticket_counts:
            total_tickets *= tc
        cost = total_tickets * 100

        hit = True
        for i, race in enumerate(races):
            winner = race['winner']
            if winner == 0:
                hit = False
                break
            if winner not in race_selections[i]:
                hit = False
                break

        actual_payout = payout if hit else 0
        results.append({
            'date': date, 'skip': False, 'cost': cost, 'payout': actual_payout,
            'tickets': total_tickets, 'hit': hit,
            'selections': [len(s) for s in race_selections],
        })
    return results


def simulate_combined(plan_results_list, plan_names):
    """複数プランの併用シミュレーション"""
    combined = []
    for i in range(len(plan_results_list[0])):
        total_cost = 0
        total_payout = 0
        any_hit = False
        details = {}
        for j, plan in enumerate(plan_results_list):
            r = plan[i]
            details[plan_names[j]] = r
            if not r['skip']:
                total_cost += r['cost']
                if r['hit']:
                    total_payout += r['payout']
                    any_hit = True
        combined.append({
            'date': plan_results_list[0][i]['date'],
            'cost': total_cost, 'payout': total_payout,
            'hit': any_hit, 'details': details,
        })
    return combined


def analyze_plan(results, name):
    played = [r for r in results if not r['skip']]
    skipped = [r for r in results if r['skip']]
    hits = [r for r in played if r['hit']]
    total_cost = sum(r['cost'] for r in played)
    total_payout = sum(r['payout'] for r in played)
    roi = total_payout / total_cost * 100 if total_cost > 0 else 0

    cum_pl = 0
    peak = 0
    max_dd = 0
    max_dd_from = ''
    max_dd_to = ''
    peak_date = ''
    cum_pls = []
    losing_streak = 0
    max_losing_streak = 0

    for r in results:
        if r['skip']:
            cum_pls.append(cum_pl)
            continue
        weekly_pl = r['payout'] - r['cost']
        cum_pl += weekly_pl
        cum_pls.append(cum_pl)

        if cum_pl > peak:
            peak = cum_pl
            peak_date = r['date']
        dd = peak - cum_pl
        if dd > max_dd:
            max_dd = dd
            max_dd_from = peak_date
            max_dd_to = r['date']

        if r['hit']:
            losing_streak = 0
        else:
            losing_streak += 1
            max_losing_streak = max(max_losing_streak, losing_streak)

    return {
        'name': name,
        'played': len(played), 'skipped': len(skipped),
        'hits': len(hits),
        'hit_rate': len(hits) / len(played) * 100 if played else 0,
        'avg_tickets': sum(r['tickets'] for r in played) / len(played) if played else 0,
        'total_cost': total_cost, 'total_payout': total_payout, 'roi': roi,
        'final_pl': cum_pl, 'peak': peak, 'max_dd': max_dd,
        'max_dd_from': max_dd_from, 'max_dd_to': max_dd_to,
        'max_losing_streak': max_losing_streak,
        'cum_pls': cum_pls, 'results': results,
    }


# ============================================================
# Main
# ============================================================
def main():
    print("=" * 80)
    print("  WIN5 A+B+C 併用 精密シミュレーション")
    print("=" * 80)

    print("\n[Load] データ読み込み中...")
    all_weeks = load_win5_schedule()
    pred_index = load_cache()
    print(f"  WIN5: {len(all_weeks)}週, 予測: {len(pred_index)}レース")

    # Filter matched weeks
    matched_weeks = []
    for w in all_weeks:
        all_found = all(r['race_id'] in pred_index for r in w['races'])
        all_winners = all(r['winner'] > 0 for r in w['races'])
        if all_found and all_winners:
            matched_weeks.append(w)

    print(f"  マッチ: {len(matched_weeks)}週"
          f" ({matched_weeks[0]['date']} 〜 {matched_weeks[-1]['date']})")

    # Run each plan
    print("\n[Sim] プラン別シミュレーション...")
    res_a = simulate_plan(matched_weeks, pred_index, 'A', plan_a_select)
    res_b = simulate_plan(matched_weeks, pred_index, 'B', plan_b_select)
    res_c = simulate_plan(matched_weeks, pred_index, 'C', plan_c_select)
    res_d = simulate_plan(matched_weeks, pred_index, 'D', plan_d_select)

    # ============================================================
    # Individual Plan Analysis
    # ============================================================
    plans = {
        'A': analyze_plan(res_a, 'A: w_top2 (32点/週)'),
        'B': analyze_plan(res_b, 'B: w_ard1st_55_tiered'),
        'C': analyze_plan(res_c, 'C: union_top2'),
        'D': analyze_plan(res_d, 'D: w2_ar1_p1'),
    }

    for key in ['A', 'B', 'C', 'D']:
        p = plans[key]
        print(f"\n{'=' * 60}")
        print(f"  {p['name']}")
        print(f"{'=' * 60}")
        print(f"  参加: {p['played']}週  スキップ: {p['skipped']}週")
        print(f"  的中: {p['hits']}回 ({p['hit_rate']:.1f}%)")
        print(f"  平均点数: {p['avg_tickets']:.0f}点")
        print(f"  累計投資: {p['total_cost']:>12,}円")
        print(f"  累計払戻: {p['total_payout']:>12,}円")
        print(f"  ROI: {p['roi']:.1f}%")
        print(f"  最終損益: {p['final_pl']:>+12,}円")
        print(f"  最高到達点: {p['peak']:>+12,}円")
        print(f"  最大DD: {p['max_dd']:>12,}円"
              f" ({p['max_dd_from']}〜{p['max_dd_to']})")
        print(f"  最大連敗: {p['max_losing_streak']}週")

    # ============================================================
    # Combined Plans
    # ============================================================
    combos = [
        ('A+B', [res_a, res_b], ['A', 'B']),
        ('A+B+C', [res_a, res_b, res_c], ['A', 'B', 'C']),
        ('A+D', [res_a, res_d], ['A', 'D']),
        ('A+B+D', [res_a, res_b, res_d], ['A', 'B', 'D']),
    ]

    combo_analyses = {}
    for combo_name, combo_res, combo_keys in combos:
        combined = simulate_combined(combo_res, combo_keys)
        cum_pl = 0
        peak = 0
        max_dd = 0
        max_dd_from = ''
        max_dd_to = ''
        peak_date = ''
        cum_pls = []
        losing_streak = 0
        max_losing_streak = 0
        total_cost = 0
        total_payout = 0
        hit_count = 0

        for r in combined:
            total_cost += r['cost']
            total_payout += r['payout']
            weekly_pl = r['payout'] - r['cost']
            cum_pl += weekly_pl
            cum_pls.append(cum_pl)
            if r['hit']:
                hit_count += 1
                losing_streak = 0
            else:
                losing_streak += 1
                max_losing_streak = max(max_losing_streak, losing_streak)
            if cum_pl > peak:
                peak = cum_pl
                peak_date = r['date']
            dd = peak - cum_pl
            if dd > max_dd:
                max_dd = dd
                max_dd_from = peak_date
                max_dd_to = r['date']

        roi = total_payout / total_cost * 100 if total_cost > 0 else 0
        combo_analyses[combo_name] = {
            'total_cost': total_cost, 'total_payout': total_payout,
            'roi': roi, 'final_pl': cum_pl, 'peak': peak,
            'max_dd': max_dd, 'max_dd_from': max_dd_from,
            'max_dd_to': max_dd_to,
            'max_losing_streak': max_losing_streak,
            'hit_count': hit_count,
            'cum_pls': cum_pls, 'combined': combined,
        }

        print(f"\n{'=' * 60}")
        print(f"  併用プラン: {combo_name}")
        print(f"{'=' * 60}")
        print(f"  的中: {hit_count}回")
        print(f"  累計投資: {total_cost:>12,}円")
        print(f"  累計払戻: {total_payout:>12,}円")
        print(f"  ROI: {roi:.1f}%")
        print(f"  最終損益: {cum_pl:>+12,}円")
        print(f"  最高到達点: {peak:>+12,}円")
        print(f"  最大DD: {max_dd:>12,}円"
              f" ({max_dd_from}〜{max_dd_to})")
        print(f"  最大連敗: {max_losing_streak}週")

    # ============================================================
    # Weekly cashflow (A+B combo, detailed)
    # ============================================================
    print(f"\n{'=' * 80}")
    print(f"  A+B 併用 週次収支推移")
    print(f"{'=' * 80}")

    ab = combo_analyses['A+B']
    cum_pl = 0
    peak_so_far = 0
    print(f"\n{'日付':>10} {'A投資':>8} {'A払戻':>10} {'B投資':>8}"
          f" {'B払戻':>10} {'週損益':>10} {'累計損益':>12} {'DD':>10}")
    print("-" * 92)

    for i, r in enumerate(ab['combined']):
        da = r['details'].get('A', {})
        db_r = r['details'].get('B', {})
        a_cost = da.get('cost', 0) if not da.get('skip') else 0
        a_pay = da.get('payout', 0)
        b_cost = db_r.get('cost', 0) if not db_r.get('skip') else 0
        b_pay = db_r.get('payout', 0)
        b_skip = db_r.get('skip', False)
        wpl = r['payout'] - r['cost']
        cum_pl += wpl

        if cum_pl > peak_so_far:
            peak_so_far = cum_pl
        dd = peak_so_far - cum_pl if peak_so_far > cum_pl else 0

        b_cost_str = "   SKIP" if b_skip else f"{b_cost:>7,}円"
        marker = ""
        if da.get('hit') and db_r.get('hit') and not b_skip:
            marker = " ★★"
        elif da.get('hit') or (db_r.get('hit') and not b_skip):
            marker = " ★"

        print(f"{r['date']:>10} {a_cost:>7,}円 {a_pay:>9,}円"
              f" {b_cost_str:>8} {b_pay:>9,}円"
              f" {wpl:>+9,}円 {cum_pl:>+11,}円 {dd:>9,}円{marker}")

    # ============================================================
    # A+B+C Weekly cashflow
    # ============================================================
    print(f"\n{'=' * 80}")
    print(f"  A+B+C 併用 週次収支推移")
    print(f"{'=' * 80}")

    abc = combo_analyses['A+B+C']
    cum_pl = 0
    peak_so_far = 0
    print(f"\n{'日付':>10} {'コスト':>10} {'払戻':>10}"
          f" {'週損益':>10} {'累計損益':>12} {'DD':>10}")
    print("-" * 70)

    for i, r in enumerate(abc['combined']):
        wpl = r['payout'] - r['cost']
        cum_pl += wpl
        if cum_pl > peak_so_far:
            peak_so_far = cum_pl
        dd = peak_so_far - cum_pl if peak_so_far > cum_pl else 0
        marker = " ★" if r['hit'] else ""
        print(f"{r['date']:>10} {r['cost']:>9,}円 {r['payout']:>9,}円"
              f" {wpl:>+9,}円 {cum_pl:>+11,}円 {dd:>9,}円{marker}")

    # ============================================================
    # Summary comparison
    # ============================================================
    print(f"\n{'=' * 80}")
    print(f"  全プラン比較サマリー")
    print(f"{'=' * 80}")

    print(f"\n{'プラン':<22} {'投資':>12} {'払戻':>12} {'ROI':>7}"
          f" {'最終損益':>12} {'最大DD':>12} {'DD率':>6} {'連敗':>4} {'的中':>4}")
    print("-" * 105)

    for key in ['A', 'B', 'C', 'D']:
        p = plans[key]
        dd_pct = (p['max_dd'] / p['total_cost'] * 100
                  if p['total_cost'] > 0 else 0)
        print(f"{p['name']:<22} {p['total_cost']:>11,}円"
              f" {p['total_payout']:>11,}円 {p['roi']:>6.1f}%"
              f" {p['final_pl']:>+11,}円 {p['max_dd']:>11,}円"
              f" {dd_pct:>5.1f}% {p['max_losing_streak']:>3}週"
              f" {p['hits']:>3}回")

    for combo_name in ['A+B', 'A+B+C', 'A+D', 'A+B+D']:
        ca = combo_analyses[combo_name]
        dd_pct = (ca['max_dd'] / ca['total_cost'] * 100
                  if ca['total_cost'] > 0 else 0)
        print(f"{combo_name:<22} {ca['total_cost']:>11,}円"
              f" {ca['total_payout']:>11,}円 {ca['roi']:>6.1f}%"
              f" {ca['final_pl']:>+11,}円 {ca['max_dd']:>11,}円"
              f" {dd_pct:>5.1f}% {ca['max_losing_streak']:>3}週"
              f" {ca['hit_count']:>3}回")

    # ============================================================
    # 重複的中分析
    # ============================================================
    print(f"\n{'=' * 80}")
    print(f"  重複的中分析 (A+B)")
    print(f"{'=' * 80}")

    both_hit = 0
    for r in ab['combined']:
        da = r['details'].get('A', {})
        db_r = r['details'].get('B', {})
        a_hit = da.get('hit', False) if not da.get('skip') else False
        b_hit = db_r.get('hit', False) if not db_r.get('skip') else False
        if a_hit or b_hit:
            print(f"\n  {r['date']}:")
            if a_hit:
                print(f"    Plan A 的中: {da['tickets']}点"
                      f" → ¥{da['payout']:,}")
            if b_hit:
                print(f"    Plan B 的中: {db_r['tickets']}点"
                      f" → ¥{db_r['payout']:,}")
            if a_hit and b_hit:
                both_hit += 1
                combined_payout = da['payout'] + db_r['payout']
                print(f"    → ★★ 両方的中！合計払戻: ¥{combined_payout:,}")
            cost = r['cost']
            profit = r['payout'] - cost
            print(f"    週コスト: ¥{cost:,}"
                  f"  週損益: ¥{profit:+,}")

    total_unique_hit_weeks = sum(
        1 for r in ab['combined']
        if r['details'].get('A', {}).get('hit') or
        (r['details'].get('B', {}).get('hit') and
         not r['details'].get('B', {}).get('skip'))
    )
    print(f"\n  的中週数: {total_unique_hit_weeks}週"
          f"  (A only: {ab['hit_count'] - both_hit - (total_unique_hit_weeks - ab['hit_count'])}週,"
          f" B only: ?, 両方: {both_hit}週)")

    # ============================================================
    # ASCII Art Cumulative P&L Chart (A+B)
    # ============================================================
    print(f"\n{'=' * 80}")
    print(f"  A+B 累計損益チャート")
    print(f"{'=' * 80}")

    pls = ab['cum_pls']
    min_pl = min(pls)
    max_pl = max(pls)
    chart_width = 60
    chart_height = 20

    if max_pl == min_pl:
        max_pl = min_pl + 1

    def scale(val):
        return int((val - min_pl) / (max_pl - min_pl) * (chart_height - 1))

    # Sample points (take every nth point to fit)
    n_points = len(pls)
    step = max(1, n_points // chart_width)
    sampled = [(i, pls[i]) for i in range(0, n_points, step)]

    # Build chart
    chart = [[' ' for _ in range(len(sampled))] for _ in range(chart_height)]
    zero_row = scale(0)

    for col, (idx, val) in enumerate(sampled):
        row = scale(val)
        chart[row][col] = '*'

    # Print chart (top to bottom)
    for row_idx in range(chart_height - 1, -1, -1):
        val = min_pl + (max_pl - min_pl) * row_idx / (chart_height - 1)
        label = f"{val:>+10,.0f}円"
        line = ''.join(chart[row_idx])
        marker = '-' if row_idx == zero_row else ' '
        print(f"  {label} |{line.replace(' ', marker if row_idx == zero_row else ' ')}")

    # X axis labels
    print(f"  {'':>11}+{''.join(['-' for _ in sampled])}")
    first_date = matched_weeks[0]['date']
    last_date = matched_weeks[-1]['date']
    print(f"  {'':>11} {first_date}{'':>{len(sampled)-16}}{last_date}")

    # ============================================================
    # 年間換算
    # ============================================================
    print(f"\n{'=' * 80}")
    print(f"  年間換算（67週 → 52週）")
    print(f"{'=' * 80}")

    ratio = 52 / 67
    for combo_name in ['A+B', 'A+B+C', 'A+D', 'A+B+D']:
        ca = combo_analyses[combo_name]
        annual_cost = ca['total_cost'] * ratio
        annual_payout = ca['total_payout'] * ratio
        annual_pl = ca['final_pl'] * ratio
        print(f"\n  {combo_name}:")
        print(f"    年間投資: ¥{annual_cost:>12,.0f}")
        print(f"    年間払戻: ¥{annual_payout:>12,.0f}")
        print(f"    年間損益: ¥{annual_pl:>+12,.0f}")
        print(f"    月平均損益: ¥{annual_pl / 12:>+12,.0f}")

    # ============================================================
    # バンクロール要件
    # ============================================================
    print(f"\n{'=' * 80}")
    print(f"  バンクロール要件")
    print(f"{'=' * 80}")

    for combo_name in ['A+B', 'A+B+C', 'A+D', 'A+B+D']:
        ca = combo_analyses[combo_name]
        # 最大DDの1.5倍をバンクロール要件とする
        bankroll_req = int(ca['max_dd'] * 1.5)
        weekly_avg_cost = ca['total_cost'] / len(matched_weeks)
        months_to_max_dd = ca['max_dd'] / weekly_avg_cost / 4.3 if weekly_avg_cost > 0 else 0
        print(f"\n  {combo_name}:")
        print(f"    最大DD: ¥{ca['max_dd']:,}")
        print(f"    推奨バンクロール (DD×1.5): ¥{bankroll_req:,}")
        print(f"    週平均コスト: ¥{weekly_avg_cost:,.0f}")
        print(f"    DD到達までの平均期間: {months_to_max_dd:.1f}ヶ月")
        print(f"    DD/バンクロール比: {ca['max_dd']/bankroll_req*100:.0f}%")


    # ============================================================
    # JSON保存（Web表示用）
    # ============================================================
    save_path = ml_dir() / "win5_combo_results.json"

    def plan_to_dict(p):
        return {
            'name': p['name'],
            'played': p['played'], 'skipped': p['skipped'],
            'hits': p['hits'], 'hit_rate': round(p['hit_rate'], 1),
            'avg_tickets': round(p['avg_tickets']),
            'total_cost': p['total_cost'], 'total_payout': p['total_payout'],
            'roi': round(p['roi'], 1),
            'final_pl': p['final_pl'], 'peak': p['peak'],
            'max_dd': p['max_dd'],
            'max_dd_from': p['max_dd_from'], 'max_dd_to': p['max_dd_to'],
            'max_losing_streak': p['max_losing_streak'],
            'cum_pls': p['cum_pls'],
        }

    def combo_to_dict(ca):
        ratio = 52 / len(matched_weeks)
        weekly = []
        cum = 0
        for r in ca['combined']:
            da = r['details'].get('A', {})
            db_r = r['details'].get('B', {})
            dc_r = r['details'].get('C', {})
            dd_r = r['details'].get('D', {})
            cum += r['payout'] - r['cost']
            weekly.append({
                'date': r['date'],
                'cost': r['cost'], 'payout': r['payout'],
                'pl': r['payout'] - r['cost'], 'cum_pl': cum,
                'hit': r['hit'],
                'a_hit': da.get('hit', False) if not da.get('skip') else False,
                'b_hit': db_r.get('hit', False) if not db_r.get('skip') else False,
                'c_hit': dc_r.get('hit', False) if not dc_r.get('skip') else False,
                'd_hit': dd_r.get('hit', False) if not dd_r.get('skip') else False,
                'b_skip': db_r.get('skip', False),
                'a_cost': da.get('cost', 0) if not da.get('skip') else 0,
                'b_cost': db_r.get('cost', 0) if not db_r.get('skip') else 0,
                'c_cost': dc_r.get('cost', 0) if not dc_r.get('skip') else 0,
                'd_cost': dd_r.get('cost', 0) if not dd_r.get('skip') else 0,
                'a_payout': da.get('payout', 0),
                'b_payout': db_r.get('payout', 0),
                'c_payout': dc_r.get('payout', 0),
                'd_payout': dd_r.get('payout', 0),
            })
        return {
            'total_cost': ca['total_cost'],
            'total_payout': ca['total_payout'],
            'roi': round(ca['roi'], 1),
            'final_pl': ca['final_pl'], 'peak': ca['peak'],
            'max_dd': ca['max_dd'],
            'max_dd_from': ca['max_dd_from'],
            'max_dd_to': ca['max_dd_to'],
            'max_losing_streak': ca['max_losing_streak'],
            'hit_count': ca['hit_count'],
            'cum_pls': ca['cum_pls'],
            'weekly': weekly,
            'annual_cost': round(ca['total_cost'] * ratio),
            'annual_payout': round(ca['total_payout'] * ratio),
            'annual_pl': round(ca['final_pl'] * ratio),
            'bankroll_req': int(ca['max_dd'] * 1.5),
        }

    save_data = {
        'period': {
            'start': matched_weeks[0]['date'],
            'end': matched_weeks[-1]['date'],
        },
        'matched_weeks': len(matched_weeks),
        'plans': {k: plan_to_dict(v) for k, v in plans.items()},
        'combos': {k: combo_to_dict(v) for k, v in combo_analyses.items()},
    }

    with open(str(save_path), 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    print(f"\n[Save] {save_path}")


if __name__ == '__main__':
    main()
