#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WIN5 A/B/C/D 併用 精密週次シミュレーション

win5_pick.py と同一の戦略:
- Plan A: WPs2固定         — WP合算rank top2 (32点, ¥3,200/週)
- Plan B: WPs2+kb1+idm1   — WP合算top2 ∪ KB印◎ ∪ IDM1位 (~71点, ¥7,100/週)
- Plan C: field_adaptive   — 頭数適応 WP合算 (~94点, ¥9,400/週)
- Plan D: WPs3固定         — WP合算rank top3 (243点, ¥24,300/週) [参考]
- 併用: A+B / A+C / A+B+C / A+B+C+D
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.config import data_root, ml_dir, races_dir
from core import db


# ============================================================
# Data Load
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
            WIN5_KUMIBAN1, WIN5_KUMIBAN2, WIN5_KUMIBAN3, WIN5_KUMIBAN4, WIN5_KUMIBAN5,
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
        no_hit = (row.get('TEKICHU_NASHI_FLAG') or '').strip() == '1'
        weeks.append({
            'date': date_str, 'races': races,
            'payout': payout, 'no_hit': no_hit
        })
    return weeks


def load_predictions_all(weeks):
    """全WIN5日のpredictions.jsonを読み込み"""
    pc = {}
    for w in weeks:
        ds = w['date']
        if ds in pc:
            continue
        y, m, d = ds[:4], ds[4:6], ds[6:8]
        p = races_dir() / y / m / d / 'predictions.json'
        if not p.exists():
            continue
        with open(p, encoding='utf-8') as f:
            data = json.load(f)
        rd = {}
        for r in data.get('races', []):
            rid = r.get('race_id', '')
            rd[rid] = {
                'entries': r.get('entries', []),
                'num_runners': r.get('num_runners', len(r.get('entries', []))),
                'is_handicap': r.get('is_handicap', False),
            }
        pc[ds] = rd
    return pc


# ============================================================
# Strategy implementations (win5_pick.py と完全同一)
# ============================================================
KB_MARK_ORDER = {'\u25ce': 1, '\u25cb': 2, '\u25b2': 3, '\u25b3': 4, '\u25bd': 5, '\u00d7': 6, '': 99}


def wps_sorted(entries):
    valid = [e for e in entries if (e.get('rank_w') or 0) > 0 and (e.get('rank_p') or 0) > 0]
    return sorted(valid, key=lambda e: e['rank_w'] + e['rank_p'])


def wps_top(entries, n):
    return [int(e['umaban']) for e in wps_sorted(entries)[:n]]


def kb_mark_top(entries, n):
    s = sorted(entries, key=lambda e: (
        KB_MARK_ORDER.get(e.get('kb_mark', ''), 99),
        -float(e.get('kb_rating', 0) or 0)
    ))
    return [int(e['umaban']) for e in s[:n]]


def idm_top(entries, n):
    s = sorted(entries, key=lambda e: -float(e.get('jrdb_idm', 0) or 0))
    return [int(e['umaban']) for e in s[:n]]


def union(*lists):
    s = set()
    for l in lists:
        s.update(l)
    return list(s)


def plan_a_select(race_info):
    """Plan A: WPs2固定"""
    return wps_top(race_info['entries'], 2)


def plan_b_select(race_info):
    """Plan B: WPs2+kb1+idm1"""
    e = race_info['entries']
    return union(wps_top(e, 2), kb_mark_top(e, 1), idm_top(e, 1))


def plan_c_select(race_info):
    """Plan C: field_adaptive — 頭数12以下→1頭, 14以上→3頭, 他→2頭"""
    f = race_info['num_runners']
    if f <= 12:
        n = 1
    elif f >= 14:
        n = 3
    else:
        n = 2
    return wps_top(race_info['entries'], n)


def plan_d_select(race_info):
    """Plan D: WPs3固定 [参考]"""
    return wps_top(race_info['entries'], 3)


PLAN_FNS = {
    'A': ('A: WP合算 Top2 (32点)', plan_a_select),
    'B': ('B: WP2+KB印+IDM (~71点)', plan_b_select),
    'C': ('C: 頭数適応 WP合算 (~94点)', plan_c_select),
    'D': ('D: WP合算 Top3 (243点) [参考]', plan_d_select),
}


# ============================================================
# Simulation
# ============================================================
def simulate_plan(weeks, pred_cache, plan_key, select_fn):
    results = []
    for week in weeks:
        preds = pred_cache.get(week['date'], {})
        race_selections = []
        skip_week = False
        for race in week['races']:
            ri = preds.get(race['race_id'])
            if not ri or not ri['entries']:
                race_selections.append([])
                continue
            sel = select_fn(ri)
            if not sel:
                skip_week = True
                break
            race_selections.append(sel)

        if skip_week or len(race_selections) < 5:
            results.append({
                'date': week['date'], 'skip': True, 'cost': 0, 'payout': 0,
                'tickets': 0, 'hit': False, 'selections': [],
            })
            continue

        ticket_counts = [max(len(s), 1) for s in race_selections]
        total_tickets = 1
        for tc in ticket_counts:
            total_tickets *= tc
        cost = total_tickets * 100

        hit = True
        for i, race in enumerate(week['races']):
            winner = race['winner']
            if winner == 0:
                hit = False
                break
            if winner not in race_selections[i]:
                hit = False
                break

        results.append({
            'date': week['date'], 'skip': False, 'cost': cost,
            'payout': week['payout'] if hit else 0,
            'tickets': total_tickets, 'hit': hit,
            'selections': [len(s) for s in race_selections],
        })
    return results


def simulate_combined(plan_results_list, plan_names):
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
        'played': len(played), 'skipped': len(results) - len(played),
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
    print("  WIN5 A/B/C/D 併用 精密シミュレーション")
    print("=" * 80)

    print("\n[Load] データ読み込み中...")
    all_weeks = load_win5_schedule()
    pred_cache = load_predictions_all(all_weeks)
    print(f"  WIN5: {len(all_weeks)}週, 予測: {len(pred_cache)}日")

    matched_weeks = []
    for w in all_weeks:
        preds = pred_cache.get(w['date'], {})
        all_found = all(r['race_id'] in preds for r in w['races'])
        all_winners = all(r['winner'] > 0 for r in w['races'])
        if all_found and all_winners:
            matched_weeks.append(w)

    print(f"  マッチ: {len(matched_weeks)}週"
          f" ({matched_weeks[0]['date']} 〜 {matched_weeks[-1]['date']})")

    print("\n[Sim] プラン別シミュレーション...")
    for pk, (pname, _) in PLAN_FNS.items():
        print(f"  Plan {pk}: {pname}")

    plan_results = {}
    for pk, (pname, pfn) in PLAN_FNS.items():
        plan_results[pk] = simulate_plan(matched_weeks, pred_cache, pk, pfn)

    plans = {}
    for pk, (pname, _) in PLAN_FNS.items():
        plans[pk] = analyze_plan(plan_results[pk], pname)

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
        print(f"  最大DD: {p['max_dd']:>12,}円"
              f" ({p['max_dd_from']}〜{p['max_dd_to']})")
        print(f"  最大連敗: {p['max_losing_streak']}週")

    combos = [
        ('A+B', ['A', 'B']),
        ('A+C', ['A', 'C']),
        ('A+B+C', ['A', 'B', 'C']),
        ('A+B+C+D', ['A', 'B', 'C', 'D']),
    ]

    combo_analyses = {}
    for combo_name, combo_keys in combos:
        res_list = [plan_results[k] for k in combo_keys]
        combined = simulate_combined(res_list, combo_keys)
        cum_pl = 0; peak = 0; max_dd = 0
        max_dd_from = ''; max_dd_to = ''; peak_date = ''
        cum_pls = []; losing_streak = 0; max_losing_streak = 0
        total_cost = 0; total_payout = 0; hit_count = 0

        for r in combined:
            total_cost += r['cost']
            total_payout += r['payout']
            weekly_pl = r['payout'] - r['cost']
            cum_pl += weekly_pl
            cum_pls.append(cum_pl)
            if r['hit']:
                hit_count += 1; losing_streak = 0
            else:
                losing_streak += 1
                max_losing_streak = max(max_losing_streak, losing_streak)
            if cum_pl > peak:
                peak = cum_pl; peak_date = r['date']
            dd = peak - cum_pl
            if dd > max_dd:
                max_dd = dd; max_dd_from = peak_date; max_dd_to = r['date']

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
        print(f"  最大DD: {max_dd:>12,}円"
              f" ({max_dd_from}〜{max_dd_to})")
        print(f"  最大連敗: {max_losing_streak}週")

    # Summary
    print(f"\n{'=' * 80}")
    print(f"  全プラン比較サマリー")
    print(f"{'=' * 80}")
    print(f"\n{'プラン':<30} {'投資':>12} {'払戻':>12} {'ROI':>7}"
          f" {'最終損益':>12} {'最大DD':>12} {'連敗':>4} {'的中':>4}")
    print("-" * 105)
    for key in ['A', 'B', 'C', 'D']:
        p = plans[key]
        print(f"{p['name']:<30} {p['total_cost']:>11,}円"
              f" {p['total_payout']:>11,}円 {p['roi']:>6.1f}%"
              f" {p['final_pl']:>+11,}円 {p['max_dd']:>11,}円"
              f" {p['max_losing_streak']:>3}週 {p['hits']:>3}回")
    for combo_name in ['A+B', 'A+C', 'A+B+C', 'A+B+C+D']:
        ca = combo_analyses[combo_name]
        print(f"{combo_name:<30} {ca['total_cost']:>11,}円"
              f" {ca['total_payout']:>11,}円 {ca['roi']:>6.1f}%"
              f" {ca['final_pl']:>+11,}円 {ca['max_dd']:>11,}円"
              f" {ca['max_losing_streak']:>3}週 {ca['hit_count']:>3}回")

    # ============================================================
    # JSON保存
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

    def combo_to_dict(ca, combo_keys):
        ratio = 52 / len(matched_weeks) if matched_weeks else 1
        weekly = []
        cum = 0
        for r in ca['combined']:
            cum += r['payout'] - r['cost']
            entry = {
                'date': r['date'],
                'cost': r['cost'], 'payout': r['payout'],
                'pl': r['payout'] - r['cost'], 'cum_pl': cum,
                'hit': r['hit'],
            }
            for k in ['A', 'B', 'C', 'D']:
                dk = r['details'].get(k, {})
                entry[f'{k.lower()}_hit'] = dk.get('hit', False) if not dk.get('skip') else False
                entry[f'{k.lower()}_cost'] = dk.get('cost', 0) if not dk.get('skip') else 0
                entry[f'{k.lower()}_payout'] = dk.get('payout', 0)
                entry[f'{k.lower()}_skip'] = dk.get('skip', False)
            weekly.append(entry)
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
        'combos': {k: combo_to_dict(combo_analyses[k], ck)
                   for k, ck in [c for c in combos]},
    }

    save_json = json.dumps(save_data, ensure_ascii=False, indent=2)
    with open(str(save_path), 'w', encoding='utf-8') as f:
        f.write(save_json)
    print(f"\n[Save] {save_path}")

    meta_path = ml_dir() / "model_meta.json"
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        version = meta.get("version", "")
        if version:
            archive_dir = ml_dir() / "versions" / f"v{version}"
            archive_dir.mkdir(parents=True, exist_ok=True)
            archive_path = archive_dir / "win5_combo_results.json"
            with open(str(archive_path), 'w', encoding='utf-8') as f:
                f.write(save_json)
            print(f"  Archive: {archive_path}")


if __name__ == '__main__':
    main()
