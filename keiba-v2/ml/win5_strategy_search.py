#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WIN5 戦略探索 — P系・Union系・ハイブリッド系を200点以内で網羅

Usage:
    python -m ml.win5_strategy_search
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.config import data_root, ml_dir
from core import db


# ============================================================
# Data Load (reuse from win5_variable)
# ============================================================
def load_win5_schedule():
    schedule_rows = db.query("""
        SELECT w.KAISAI_NEN, w.KAISAI_GAPPI,
            w.RACE_CODE1, w.RACE_CODE2, w.RACE_CODE3, w.RACE_CODE4, w.RACE_CODE5,
            w.TEKICHU_NASHI_FLAG
        FROM win5 w ORDER BY w.KAISAI_NEN, w.KAISAI_GAPPI
    """)
    payout_rows = db.query("""
        SELECT KAISAI_NEN, KAISAI_GAPPI,
            WIN5_KUMIBAN1, WIN5_KUMIBAN2, WIN5_KUMIBAN3,
            WIN5_KUMIBAN4, WIN5_KUMIBAN5,
            WIN5_HARAIMODOSHIKIN
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
            pr = payout_index.get(date_str)
            winner = 0
            if pr:
                kb = (pr.get(f'WIN5_KUMIBAN{i}') or '').strip()
                winner = int(kb) if kb and kb.isdigit() else 0
            races.append({'race_id': rc, 'winner': winner})
        pr = payout_index.get(date_str)
        payout = 0
        if pr:
            raw = (pr.get('WIN5_HARAIMODOSHIKIN') or '').strip()
            payout = int(raw) if raw and raw.isdigit() else 0
        weeks.append({'date': date_str, 'races': races, 'payout': payout})
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
                'rank_w': int(e.get('rank_w', 0) or 0),
                'rank_p': int(e.get('rank_p', 0) or 0),
                'ar_deviation': ard,
                'is_win': bool(e.get('is_win', False)),
                'odds': float(e.get('odds', 0) or 0),
                'pred_proba_p_raw': float(e.get('pred_proba_p_raw', 0) or 0),
                'pred_proba_w_cal': float(e.get('pred_proba_w_cal', 0) or 0),
                'win_ev': float(e.get('win_ev', 0) or 0),
            })
        idx[rid] = {'entries': entries}
    return idx


# ============================================================
# Strategy Selection Functions
# ============================================================
def get_sorted(entries, rank_key):
    if rank_key == 'wp_sum':
        valid = [e for e in entries if e['rank_w'] > 0 and e['rank_p'] > 0]
        return sorted(valid, key=lambda e: e['rank_w'] + e['rank_p'])
    if rank_key == 'wp_min':
        valid = [e for e in entries if e['rank_w'] > 0 and e['rank_p'] > 0]
        return sorted(valid, key=lambda e: min(e['rank_w'], e['rank_p']))
    return sorted(
        [e for e in entries if e.get(rank_key, 0) > 0],
        key=lambda e: e[rank_key]
    )


def select_fixed(pred, rank_key, n):
    top = get_sorted(pred['entries'], rank_key)
    return [e['umaban'] for e in top[:n]] if top else []


def select_union(pred, keys_and_ns):
    """Union of multiple rank_key top-N picks"""
    uma_set = set()
    for rank_key, n in keys_and_ns:
        top = get_sorted(pred['entries'], rank_key)
        for e in top[:n]:
            uma_set.add(e['umaban'])
    return list(uma_set)


def select_variable(pred, rank_key, gap_rules, default_n, ard_floor=0, min_ard_1st=0):
    """Variable selection based on ARd gap"""
    top = get_sorted(pred['entries'], rank_key)
    if not top:
        return None

    ard_1st = top[0]['ar_deviation']
    if min_ard_1st > 0 and ard_1st < min_ard_1st:
        return None

    ard_2nd = top[1]['ar_deviation'] if len(top) > 1 else 0
    gap_12 = ard_1st - ard_2nd

    n = default_n
    for gap_thresh, target_n in gap_rules:
        if gap_12 >= gap_thresh:
            n = target_n
            break

    selected = top[:n]
    if ard_floor > 0:
        selected = [e for e in selected if e['ar_deviation'] >= ard_floor]
        if not selected:
            return None

    return [e['umaban'] for e in selected]


def select_p_proba_topn(pred, n, min_proba=0):
    """Select by raw P probability (not rank)"""
    entries = sorted(pred['entries'], key=lambda e: -e['pred_proba_p_raw'])
    if min_proba > 0:
        entries = [e for e in entries if e['pred_proba_p_raw'] >= min_proba]
    return [e['umaban'] for e in entries[:n]]


def select_ev_topn(pred, n, min_ev=0):
    """Select by win_ev"""
    entries = sorted(pred['entries'], key=lambda e: -e['win_ev'])
    if min_ev > 0:
        entries = [e for e in entries if e['win_ev'] >= min_ev]
    return [e['umaban'] for e in entries[:n]]


def select_consensus(pred, max_rank_w, max_rank_p, fallback_n=2):
    """Select horses that are top-N in BOTH W and P models, with fallback"""
    w_set = set(e['umaban'] for e in pred['entries']
                if 0 < e['rank_w'] <= max_rank_w)
    p_set = set(e['umaban'] for e in pred['entries']
                if 0 < e['rank_p'] <= max_rank_p)
    consensus = w_set & p_set
    if len(consensus) < 1:
        # Fallback to W top-N
        top_w = get_sorted(pred['entries'], 'rank_w')
        return [e['umaban'] for e in top_w[:fallback_n]]
    return list(consensus)


# ============================================================
# Strategy Definitions
# ============================================================
def build_strategies():
    strategies = {}

    # --- P-model fixed ---
    for n in [2, 3, 4]:
        strategies[f'p_fixed_{n}'] = lambda pred, n=n: select_fixed(pred, 'rank_p', n)

    # --- P-model variable (gap-based) ---
    for min_ard in [0, 50, 55]:
        for gap_1h in [12, 10, 8]:
            for gap_2h in [6, 5]:
                for default in [3, 4]:
                    name = f'p_gap_{min_ard}_{gap_1h}_{gap_2h}_d{default}'
                    strategies[name] = lambda pred, ma=min_ard, g1=gap_1h, g2=gap_2h, dn=default: \
                        select_variable(pred, 'rank_p', [(g1, 1), (g2, 2)], dn, min_ard_1st=ma)

    # --- P-model with ARd floor ---
    for floor in [45, 48, 50]:
        for default in [3, 4]:
            name = f'p_floor{floor}_d{default}'
            strategies[name] = lambda pred, f=floor, d=default: \
                select_variable(pred, 'rank_p', [(12, 1), (6, 2), (3, 3)], d, ard_floor=f)

    # --- Union strategies ---
    # W top-N + P top-M
    for wn in [1, 2]:
        for pn in [1, 2, 3]:
            name = f'union_w{wn}_p{pn}'
            strategies[name] = lambda pred, wn=wn, pn=pn: \
                select_union(pred, [('rank_w', wn), ('rank_p', pn)])

    # W top-2 + P top-2 + AR top-1
    strategies['union_w2_p2_ar1'] = lambda pred: \
        select_union(pred, [('rank_w', 2), ('rank_p', 2)]) + \
        [sorted(pred['entries'], key=lambda e: -e['ar_deviation'])[0]['umaban']]

    # --- WP sum/min rank ---
    for n in [2, 3, 4]:
        strategies[f'wp_sum_top{n}'] = lambda pred, n=n: select_fixed(pred, 'wp_sum', n)
        strategies[f'wp_min_top{n}'] = lambda pred, n=n: select_fixed(pred, 'wp_min', n)

    # --- Consensus (both models agree) ---
    for max_w in [3, 4, 5]:
        for max_p in [3, 4, 5]:
            name = f'consensus_w{max_w}_p{max_p}'
            strategies[name] = lambda pred, mw=max_w, mp=max_p: \
                select_consensus(pred, mw, mp, fallback_n=2)

    # --- P probability-based ---
    for n in [2, 3, 4]:
        strategies[f'p_proba_top{n}'] = lambda pred, n=n: select_p_proba_topn(pred, n)
    for min_p in [0.15, 0.20]:
        name = f'p_proba_min{int(min_p*100)}'
        strategies[name] = lambda pred, mp=min_p: select_p_proba_topn(pred, 5, min_proba=mp)

    # --- Win EV-based ---
    for n in [2, 3]:
        strategies[f'win_ev_top{n}'] = lambda pred, n=n: select_ev_topn(pred, n)
    strategies['win_ev_above1'] = lambda pred: select_ev_topn(pred, 5, min_ev=1.0)

    # --- W variable (for comparison, key ones) ---
    for default in [3, 4]:
        strategies[f'w_gap_0_10_5_d{default}'] = lambda pred, d=default: \
            select_variable(pred, 'rank_w', [(10, 1), (5, 2)], d)
        strategies[f'w_gap_55_10_5_d{default}'] = lambda pred, d=default: \
            select_variable(pred, 'rank_w', [(10, 1), (5, 2)], d, min_ard_1st=55)

    # --- Hybrid: P-variable + W-top1 union ---
    for default in [2, 3]:
        name = f'hybrid_p{default}_w1'
        strategies[name] = lambda pred, d=default: list(set(
            select_fixed(pred, 'rank_p', d) + select_fixed(pred, 'rank_w', 1)
        ))

    # --- Hybrid: P-variable + AR-top1 ---
    for default in [2, 3]:
        name = f'hybrid_p{default}_ar1'
        strategies[name] = lambda pred, d=default: list(set(
            select_fixed(pred, 'rank_p', d) +
            [sorted(pred['entries'], key=lambda e: -e['ar_deviation'])[0]['umaban']]
        ))

    return strategies


# ============================================================
# Simulation
# ============================================================
def simulate(weeks, pred_index, strategies):
    results = {}

    for sname, select_fn in strategies.items():
        week_results = []
        for week in weeks:
            race_sels = []
            skip = False
            for race in week['races']:
                pred = pred_index.get(race['race_id'])
                if not pred:
                    race_sels.append([])
                    continue
                sel = select_fn(pred)
                if sel is None:
                    skip = True
                    break
                # Deduplicate
                sel = list(set(sel))
                race_sels.append(sel)

            if skip or len(race_sels) < 5 or any(len(s) == 0 for s in race_sels):
                continue

            tickets = 1
            for s in race_sels:
                tickets *= len(s)

            hit = all(
                race['winner'] in race_sels[i]
                for i, race in enumerate(week['races'])
                if race['winner'] > 0
            ) and all(r['winner'] > 0 for r in week['races'])

            week_results.append({
                'date': week['date'],
                'tickets': tickets,
                'cost': tickets * 100,
                'hit': hit,
                'payout': week['payout'] if hit else 0,
                'covered': [race['winner'] in race_sels[i] for i, race in enumerate(week['races'])],
            })

        if not week_results:
            continue

        played = len(week_results)
        hits = [r for r in week_results if r['hit']]
        total_cost = sum(r['cost'] for r in week_results)
        total_payout = sum(r['payout'] for r in hits)
        ticket_counts = [r['tickets'] for r in week_results]

        results[sname] = {
            'played': played,
            'hits': len(hits),
            'hit_rate': len(hits) / played if played else 0,
            'avg_tickets': np.mean(ticket_counts),
            'median_tickets': np.median(ticket_counts),
            'total_cost': total_cost,
            'total_payout': total_payout,
            'roi': total_payout / total_cost if total_cost > 0 else 0,
            'hit_dates': [r['date'] for r in hits],
            'hit_payouts': [r['payout'] for r in hits],
            'hit_tickets': [r['tickets'] for r in hits],
            'avg_covered': np.mean([sum(r['covered']) for r in week_results]),
            'weekly': week_results,
        }

    return results


# ============================================================
# Report
# ============================================================
def print_report(results):
    sorted_r = sorted(results.items(), key=lambda x: -x[1]['roi'])

    # All results, avg <= 200 tickets
    budget_200 = [(n, s) for n, s in sorted_r if s['avg_tickets'] <= 200 and s['hits'] >= 1]

    print(f"\n{'='*90}")
    print(f"  週2万以内 (avg<=200点) + 的中1+ : {len(budget_200)}戦略")
    print(f"{'='*90}")
    print(f"{'strategy':<35} {'play':>4} {'hit':>3} {'rate':>5} {'avg':>6} {'med':>6} "
          f"{'cost':>10} {'payout':>10} {'ROI':>6} {'avg5/5':>5}")
    print('-'*95)
    for n, s in budget_200[:40]:
        print(f"{n:<35} {s['played']:>4} {s['hits']:>3} {s['hit_rate']:>4.1%} "
              f"{s['avg_tickets']:>6.0f} {s['median_tickets']:>6.0f} "
              f"{s['total_cost']:>10,} {s['total_payout']:>10,} "
              f"{s['roi']:>5.1%} {s['avg_covered']:>5.1f}")

    # Hit details for top 10
    print(f"\n{'='*90}")
    print(f"  的中詳細 (上位10)")
    print(f"{'='*90}")
    for n, s in budget_200[:10]:
        print(f"\n  [{n}] ROI={s['roi']:.1%}  avg={s['avg_tickets']:.0f}pt")
        for i in range(s['hits']):
            print(f"    {s['hit_dates'][i]}: {s['hit_tickets'][i]:>6}pt -> {s['hit_payouts'][i]:>10,}")

    # Per-leg coverage analysis for top strategies
    print(f"\n{'='*90}")
    print(f"  レッグ別カバー率 (上位10)")
    print(f"{'='*90}")
    for n, s in budget_200[:10]:
        coverages = [0] * 5
        total_weeks = 0
        for w in s['weekly']:
            total_weeks += 1
            for i, c in enumerate(w['covered']):
                if c:
                    coverages[i] += 1
        rates = [c / total_weeks * 100 for c in coverages]
        print(f"  {n:<35}  "
              f"R1={rates[0]:>4.0f}%  R2={rates[1]:>4.0f}%  R3={rates[2]:>4.0f}%  "
              f"R4={rates[3]:>4.0f}%  R5={rates[4]:>4.0f}%  "
              f"avg={sum(rates)/5:.0f}%")

    # All results summary (no budget filter)
    print(f"\n{'='*90}")
    print(f"  全戦略 ROI上位20 (予算無制限)")
    print(f"{'='*90}")
    all_hit = [(n, s) for n, s in sorted_r if s['hits'] >= 1]
    print(f"{'strategy':<35} {'play':>4} {'hit':>3} {'rate':>5} {'avg':>6} "
          f"{'cost':>10} {'payout':>10} {'ROI':>6}")
    print('-'*85)
    for n, s in all_hit[:20]:
        print(f"{n:<35} {s['played']:>4} {s['hits']:>3} {s['hit_rate']:>4.1%} "
              f"{s['avg_tickets']:>6.0f} "
              f"{s['total_cost']:>10,} {s['total_payout']:>10,} "
              f"{s['roi']:>5.1%}")


def main():
    print("=" * 80)
    print("  WIN5 Strategy Search (P-model / Union / Hybrid)")
    print("=" * 80)

    print("\n[Load]...")
    all_weeks = load_win5_schedule()
    pred_index = load_cache()
    print(f"  WIN5: {len(all_weeks)}w, pred: {len(pred_index)}r")

    matched = [w for w in all_weeks
               if all(r['race_id'] in pred_index for r in w['races'])
               and all(r['winner'] > 0 for r in w['races'])]
    print(f"  Matched: {len(matched)}w ({matched[0]['date']}~{matched[-1]['date']})")

    print("\n[Build] strategies...")
    strategies = build_strategies()
    print(f"  {len(strategies)} strategies")

    print("\n[Sim]...")
    results = simulate(matched, pred_index, strategies)
    print(f"  {len(results)} results")

    print_report(results)

    # Save
    out = {}
    for n, s in results.items():
        out[n] = {k: (float(v) if isinstance(v, (np.floating, np.integer)) else v)
                  for k, v in s.items() if k != 'weekly'}
    save_path = ml_dir() / "win5_strategy_search_results.json"
    with open(str(save_path), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n[Save] {save_path}")


if __name__ == '__main__':
    main()
