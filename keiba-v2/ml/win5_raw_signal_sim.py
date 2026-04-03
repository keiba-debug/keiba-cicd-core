#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WIN5 生データ指標シミュレーション

MLモデルに依存せず、競馬ブック印・JRDB IDM・オッズ等の
「生データ」でWIN5を検証する。

Usage:
    python -m ml.win5_raw_signal_sim
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.config import data_root, races_dir
from core import db


# ============================================================
# Data Load
# ============================================================
def load_win5_schedule():
    schedule_rows = db.query("""
        SELECT w.KAISAI_NEN, w.KAISAI_GAPPI,
            w.RACE_CODE1, w.RACE_CODE2, w.RACE_CODE3, w.RACE_CODE4, w.RACE_CODE5
        FROM win5 w ORDER BY w.KAISAI_NEN, w.KAISAI_GAPPI
    """)
    payout_rows = db.query("""
        SELECT KAISAI_NEN, KAISAI_GAPPI,
            WIN5_KUMIBAN1, WIN5_KUMIBAN2, WIN5_KUMIBAN3, WIN5_KUMIBAN4, WIN5_KUMIBAN5,
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


def load_predictions_for_date(date_str: str) -> dict:
    """predictions.json から race_id -> entries の辞書を返す"""
    y, m, d = date_str[:4], date_str[4:6], date_str[6:8]
    pred_path = races_dir() / y / m / d / "predictions.json"
    if not pred_path.exists():
        return {}
    with open(pred_path, encoding='utf-8') as f:
        data = json.load(f)
    return {r['race_id']: r.get('entries', []) for r in data.get('races', [])}


def load_race_results(date_str: str, race_id: str) -> dict:
    """race_{id}.json から馬番→着順マップを返す"""
    y, m, d = date_str[:4], date_str[4:6], date_str[6:8]
    race_path = races_dir() / y / m / d / f"race_{race_id}.json"
    if not race_path.exists():
        return {}
    with open(race_path, encoding='utf-8') as f:
        rj = json.load(f)
    return {e.get('umaban'): e.get('finish_position', 0)
            for e in rj.get('entries', []) if e.get('finish_position')}


# ============================================================
# Selection Strategies (raw signal based)
# ============================================================

KB_MARK_ORDER = {'◎': 1, '○': 2, '▲': 3, '△': 4, '▽': 5, '×': 6, '': 99}


def rank_by_kb_mark(entries, n):
    """競馬ブック印順でtop-N"""
    sorted_e = sorted(entries, key=lambda e: (
        KB_MARK_ORDER.get(e.get('kb_mark', ''), 99),
        -float(e.get('kb_rating', 0) or 0)
    ))
    return [int(e['umaban']) for e in sorted_e[:n]]


def rank_by_kb_rating(entries, n):
    """競馬ブック総合評価順でtop-N"""
    sorted_e = sorted(entries, key=lambda e: -float(e.get('kb_rating', 0) or 0))
    return [int(e['umaban']) for e in sorted_e[:n]]


def rank_by_kb_mark_point(entries, n):
    """競馬ブック印ポイント順でtop-N"""
    sorted_e = sorted(entries, key=lambda e: -float(e.get('kb_mark_point', 0) or 0))
    return [int(e['umaban']) for e in sorted_e[:n]]


def rank_by_jrdb_idm(entries, n):
    """JRDB IDM順でtop-N"""
    sorted_e = sorted(entries, key=lambda e: -float(e.get('jrdb_idm', 0) or 0))
    return [int(e['umaban']) for e in sorted_e[:n]]


def rank_by_odds(entries, n):
    """単勝オッズ順(人気順)でtop-N"""
    sorted_e = sorted(entries, key=lambda e: float(e.get('odds', 999) or 999))
    return [int(e['umaban']) for e in sorted_e[:n]]


def rank_by_kb_ai(entries, n):
    """競馬ブックAI指数順でtop-N"""
    sorted_e = sorted(entries, key=lambda e: -float(e.get('kb_ai_index', 0) or 0))
    return [int(e['umaban']) for e in sorted_e[:n]]


def union_kb_jrdb(entries, kb_n, jrdb_n):
    """競馬ブック印top-N ∪ JRDB IDM top-M"""
    kb_set = set(rank_by_kb_mark(entries, kb_n))
    jrdb_set = set(rank_by_jrdb_idm(entries, jrdb_n))
    return list(kb_set | jrdb_set)


def union_odds_kb(entries, odds_n, kb_n):
    """オッズ人気top-N ∪ 競馬ブック印top-M"""
    odds_set = set(rank_by_odds(entries, odds_n))
    kb_set = set(rank_by_kb_mark(entries, kb_n))
    return list(odds_set | kb_set)


def consensus_kb_odds(entries, kb_top, odds_top, fallback_n=2):
    """競馬ブック印top-N ∩ オッズ人気top-M (一致なければfallback)"""
    kb_set = set(rank_by_kb_mark(entries, kb_top))
    odds_set = set(rank_by_odds(entries, odds_top))
    consensus = kb_set & odds_set
    if len(consensus) < 1:
        return rank_by_odds(entries, fallback_n)
    return list(consensus)


def union_all3(entries, kb_n, jrdb_n, odds_n):
    """KB印 ∪ JRDB IDM ∪ オッズ top-N の和集合"""
    s = set()
    s.update(rank_by_kb_mark(entries, kb_n))
    s.update(rank_by_jrdb_idm(entries, jrdb_n))
    s.update(rank_by_odds(entries, odds_n))
    return list(s)


# Also test model-based for comparison
def rank_by_model_w(entries, n):
    """rank_w top-N (ML model, for comparison)"""
    sorted_e = sorted(
        [e for e in entries if (e.get('rank_w') or 0) > 0],
        key=lambda e: e['rank_w']
    )
    return [int(e['umaban']) for e in sorted_e[:n]]


def rank_by_model_p(entries, n):
    """rank_p top-N (ML model, for comparison)"""
    sorted_e = sorted(
        [e for e in entries if (e.get('rank_p') or 0) > 0],
        key=lambda e: e['rank_p']
    )
    return [int(e['umaban']) for e in sorted_e[:n]]


# ============================================================
# Build strategy list
# ============================================================
def build_strategies():
    strategies = {}

    # --- 単独指標 fixed top-N ---
    for n in [1, 2, 3, 4, 5]:
        strategies[f'kb_mark_top{n}'] = lambda e, n=n: rank_by_kb_mark(e, n)
        strategies[f'kb_rating_top{n}'] = lambda e, n=n: rank_by_kb_rating(e, n)
        strategies[f'kb_mp_top{n}'] = lambda e, n=n: rank_by_kb_mark_point(e, n)
        strategies[f'jrdb_idm_top{n}'] = lambda e, n=n: rank_by_jrdb_idm(e, n)
        strategies[f'odds_top{n}'] = lambda e, n=n: rank_by_odds(e, n)
        strategies[f'kb_ai_top{n}'] = lambda e, n=n: rank_by_kb_ai(e, n)
        # ML comparison
        strategies[f'model_w_top{n}'] = lambda e, n=n: rank_by_model_w(e, n)
        strategies[f'model_p_top{n}'] = lambda e, n=n: rank_by_model_p(e, n)

    # --- Union: KB印 ∪ JRDB IDM ---
    for kb_n in [1, 2]:
        for jrdb_n in [1, 2]:
            strategies[f'union_kb{kb_n}_jrdb{jrdb_n}'] = \
                lambda e, kn=kb_n, jn=jrdb_n: union_kb_jrdb(e, kn, jn)

    # --- Union: オッズ ∪ KB印 ---
    for on in [1, 2]:
        for kn in [1, 2]:
            strategies[f'union_odds{on}_kb{kn}'] = \
                lambda e, on=on, kn=kn: union_odds_kb(e, on, kn)

    # --- Union: 3指標 ---
    for n in [1, 2]:
        strategies[f'union3_kb{n}_jrdb{n}_odds{n}'] = \
            lambda e, n=n: union_all3(e, n, n, n)

    # --- Consensus: KB印 ∩ オッズ ---
    for kt in [3, 4, 5]:
        for ot in [3, 4, 5]:
            strategies[f'consensus_kb{kt}_odds{ot}'] = \
                lambda e, kt=kt, ot=ot: consensus_kb_odds(e, kt, ot)

    return strategies


# ============================================================
# Simulation
# ============================================================
def simulate(weeks, strategies):
    results = {}

    # Pre-load all predictions
    print("[Load] predictions.json for all WIN5 dates...")
    pred_cache = {}
    loaded = 0
    for week in weeks:
        date = week['date']
        if date not in pred_cache:
            preds = load_predictions_for_date(date)
            if preds:
                pred_cache[date] = preds
                loaded += 1
    print(f"  Loaded {loaded} dates")

    for sname, select_fn in strategies.items():
        week_results = []
        for week in weeks:
            preds = pred_cache.get(week['date'], {})
            if not preds:
                continue

            race_sels = []
            valid = True
            for race in week['races']:
                entries = preds.get(race['race_id'], [])
                if not entries:
                    valid = False
                    break
                sel = select_fn(entries)
                if not sel:
                    valid = False
                    break
                race_sels.append(set(sel))

            if not valid or len(race_sels) < 5:
                continue
            if not all(r['winner'] > 0 for r in week['races']):
                continue

            tickets = 1
            for s in race_sels:
                tickets *= len(s)

            hit = all(
                race['winner'] in race_sels[i]
                for i, race in enumerate(week['races'])
            )

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
            'total_cost': total_cost,
            'total_payout': total_payout,
            'roi': total_payout / total_cost if total_cost > 0 else 0,
            'hit_dates': [r['date'] for r in hits],
            'hit_payouts': [r['payout'] for r in hits],
            'hit_tickets': [r['tickets'] for r in hits],
            'avg_covered': np.mean([sum(r['covered']) for r in week_results]),
        }

    return results


# ============================================================
# Report
# ============================================================
def print_report(results):
    sorted_r = sorted(results.items(), key=lambda x: -x[1]['roi'])

    # Group by signal type
    groups = {
        'KB印': [(n, s) for n, s in sorted_r if n.startswith('kb_mark_top')],
        'KB総合': [(n, s) for n, s in sorted_r if n.startswith('kb_rating_top')],
        'KB印pt': [(n, s) for n, s in sorted_r if n.startswith('kb_mp_top')],
        'KB AI': [(n, s) for n, s in sorted_r if n.startswith('kb_ai_top')],
        'JRDB IDM': [(n, s) for n, s in sorted_r if n.startswith('jrdb_idm_top')],
        'オッズ人気': [(n, s) for n, s in sorted_r if n.startswith('odds_top')],
        'ML W': [(n, s) for n, s in sorted_r if n.startswith('model_w_top')],
        'ML P': [(n, s) for n, s in sorted_r if n.startswith('model_p_top')],
    }

    print(f"\n{'='*90}")
    print(f"  指標別 TOP-N 比較 (同一条件)")
    print(f"{'='*90}")

    header = f"{'strategy':<25} {'play':>4} {'hit':>3} {'rate':>5} {'avg':>6} {'cost':>10} {'payout':>10} {'ROI':>6} {'avg5':>4}"
    print(header)
    print('-' * 80)

    for group_name, items in groups.items():
        if not items:
            continue
        print(f"\n  --- {group_name} ---")
        for n, s in sorted(items, key=lambda x: x[1]['avg_tickets']):
            print(f"  {n:<23} {s['played']:>4} {s['hits']:>3} {s['hit_rate']:>4.1%} "
                  f"{s['avg_tickets']:>6.0f} {s['total_cost']:>10,} {s['total_payout']:>10,} "
                  f"{s['roi']:>5.1%} {s['avg_covered']:>4.1f}")

    # Union/consensus strategies
    print(f"\n{'='*90}")
    print(f"  Union/Consensus 戦略 (avg<=200点)")
    print(f"{'='*90}")
    union_strats = [(n, s) for n, s in sorted_r
                    if ('union' in n or 'consensus' in n) and s['avg_tickets'] <= 200 and s['hits'] >= 1]
    print(header)
    print('-' * 80)
    for n, s in union_strats[:20]:
        print(f"  {n:<23} {s['played']:>4} {s['hits']:>3} {s['hit_rate']:>4.1%} "
              f"{s['avg_tickets']:>6.0f} {s['total_cost']:>10,} {s['total_payout']:>10,} "
              f"{s['roi']:>5.1%} {s['avg_covered']:>4.1f}")

    # Overall top 20 (avg <= 200)
    budget_200 = [(n, s) for n, s in sorted_r if s['avg_tickets'] <= 200 and s['hits'] >= 1]
    print(f"\n{'='*90}")
    print(f"  全戦略 ROI上位20 (avg<=200点)")
    print(f"{'='*90}")
    print(header)
    print('-' * 80)
    for n, s in budget_200[:20]:
        print(f"  {n:<23} {s['played']:>4} {s['hits']:>3} {s['hit_rate']:>4.1%} "
              f"{s['avg_tickets']:>6.0f} {s['total_cost']:>10,} {s['total_payout']:>10,} "
              f"{s['roi']:>5.1%} {s['avg_covered']:>4.1f}")

    # Hit details for top 5
    print(f"\n{'='*90}")
    print(f"  的中詳細 (上位5)")
    print(f"{'='*90}")
    for n, s in budget_200[:5]:
        print(f"\n  [{n}] ROI={s['roi']:.1%}  avg={s['avg_tickets']:.0f}pt")
        for i in range(s['hits']):
            print(f"    {s['hit_dates'][i]}: {s['hit_tickets'][i]:>6}pt -> {s['hit_payouts'][i]:>10,}")

    # Overall top 20 (no budget limit)
    all_hit = [(n, s) for n, s in sorted_r if s['hits'] >= 1]
    print(f"\n{'='*90}")
    print(f"  全戦略 ROI上位20 (予算無制限)")
    print(f"{'='*90}")
    print(header)
    print('-' * 80)
    for n, s in all_hit[:20]:
        print(f"  {n:<23} {s['played']:>4} {s['hits']:>3} {s['hit_rate']:>4.1%} "
              f"{s['avg_tickets']:>6.0f} {s['total_cost']:>10,} {s['total_payout']:>10,} "
              f"{s['roi']:>5.1%} {s['avg_covered']:>4.1f}")


def main():
    print("=" * 80)
    print("  WIN5 Raw Signal Simulation")
    print("  (KB印 / KB Rating / JRDB IDM / オッズ / ML比較)")
    print("=" * 80)

    print("\n[Load] WIN5 schedule...")
    weeks = load_win5_schedule()
    print(f"  {len(weeks)} weeks")

    strategies = build_strategies()
    print(f"\n[Strategies] {len(strategies)}")

    results = simulate(weeks, strategies)
    print(f"[Results] {len(results)} strategies with data")

    print_report(results)


if __name__ == '__main__':
    main()
