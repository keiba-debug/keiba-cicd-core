#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WIN5 Adaptive WPsum — レース特性でtop1-4を可変制御

条件:
  - WPs1位の勝率 (pred_proba_p_raw)
  - 出走頭数 (num_runners)
  - ハンデ戦フラグ (is_handicap)
"""
import json, sys, itertools
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from core.config import races_dir
from core import db


def load_win5():
    sr = db.query("SELECT w.KAISAI_NEN, w.KAISAI_GAPPI, w.RACE_CODE1, w.RACE_CODE2, w.RACE_CODE3, w.RACE_CODE4, w.RACE_CODE5 FROM win5 w ORDER BY w.KAISAI_NEN, w.KAISAI_GAPPI")
    pr = db.query("SELECT KAISAI_NEN, KAISAI_GAPPI, WIN5_KUMIBAN1, WIN5_KUMIBAN2, WIN5_KUMIBAN3, WIN5_KUMIBAN4, WIN5_KUMIBAN5, WIN5_HARAIMODOSHIKIN FROM win5_haraimodoshi ORDER BY KAISAI_NEN, KAISAI_GAPPI")
    pi = {r['KAISAI_NEN'].strip()+r['KAISAI_GAPPI'].strip(): r for r in pr}
    weeks = []
    for r in sr:
        ds = r['KAISAI_NEN'].strip()+r['KAISAI_GAPPI'].strip()
        races = []
        for i in range(1,6):
            rc = (r.get(f'RACE_CODE{i}') or '').strip()
            p = pi.get(ds); w = 0
            if p:
                kb = (p.get(f'WIN5_KUMIBAN{i}') or '').strip()
                w = int(kb) if kb.isdigit() else 0
            races.append({'race_id':rc,'winner':w})
        p = pi.get(ds)
        po = int((p.get('WIN5_HARAIMODOSHIKIN') or '0').strip()) if p else 0
        weeks.append({'date':ds,'races':races,'payout':po})
    return weeks


def load_preds_all(weeks):
    pc = {}
    for w in weeks:
        ds = w['date']
        if ds in pc: continue
        y,m,d = ds[:4],ds[4:6],ds[6:8]
        p = races_dir()/y/m/d/'predictions.json'
        if not p.exists(): continue
        with open(p, encoding='utf-8') as f: data = json.load(f)
        rd = {}
        for r in data.get('races', []):
            rid = r.get('race_id','')
            rd[rid] = {
                'entries': r.get('entries',[]),
                'is_handicap': r.get('is_handicap', False),
                'num_runners': r.get('num_runners', len(r.get('entries',[]))),
            }
        pc[ds] = rd
    return pc


def wps_sorted(entries):
    v = [e for e in entries if (e.get('rank_w') or 0)>0 and (e.get('rank_p') or 0)>0]
    return sorted(v, key=lambda x: x['rank_w']+x['rank_p'])


def sim_adaptive(weeks, pc, rule_fn):
    """rule_fn(top_sorted, race_info) -> n (1-4)"""
    wr = []
    for wk in weeks:
        pd = pc.get(wk['date'],{})
        if not pd: continue
        ss = []; ok = True
        for rc in wk['races']:
            ri = pd.get(rc['race_id'])
            if not ri or not ri['entries']: ok=False; break
            top = wps_sorted(ri['entries'])
            if not top: ok=False; break
            n = rule_fn(top, ri)
            picked = set(int(e['umaban']) for e in top[:n])
            ss.append(picked)
        if not ok or len(ss)<5 or not all(r['winner']>0 for r in wk['races']): continue
        tx = 1
        for s in ss: tx *= len(s)
        h = all(wk['races'][i]['winner'] in ss[i] for i in range(5))
        wr.append({'tx':tx,'c':tx*100,'h':h,'p':wk['payout'] if h else 0,'d':wk['date']})
    return wr


def analyze(wr, name):
    if not wr: return None
    hs = [r for r in wr if r['h']]
    tc = sum(r['c'] for r in wr); tp = sum(r['p'] for r in hs)
    # 2025-05+ (test period)
    r25 = [r for r in wr if r['d']>='20250501']
    h25 = [r for r in r25 if r['h']]
    tc25 = sum(r['c'] for r in r25); tp25 = sum(r['p'] for r in h25)
    return {
        'name': name, 'pl': len(wr), 'ht': len(hs),
        'at': np.mean([r['tx'] for r in wr]),
        'tc': tc, 'tp': tp, 'roi': tp/tc if tc>0 else 0,
        'pl25': len(r25), 'ht25': len(h25),
        'tc25': tc25, 'tp25': tp25, 'roi25': tp25/tc25 if tc25>0 else 0,
        'hd': [r['d'] for r in hs], 'hp': [r['p'] for r in hs],
    }


def main():
    print("="*90)
    print("  WIN5 Adaptive WPsum Strategy Search")
    print("="*90)

    weeks = load_win5()
    pc = load_preds_all(weeks)
    print(f"  {len(weeks)} weeks, {len(pc)} dates with predictions")

    # First: analyze the distribution of WPs1 top horse's p_raw and field sizes
    print("\n--- WPs1 top horse characteristics ---")
    p_raws = []; fields = []; handicaps = 0; total_races = 0
    for ds, preds in pc.items():
        for rid, ri in preds.items():
            top = wps_sorted(ri['entries'])
            if not top: continue
            total_races += 1
            p_raws.append(float(top[0].get('pred_proba_p_raw', 0) or 0))
            fields.append(ri['num_runners'])
            if ri['is_handicap']: handicaps += 1

    print(f"  Races: {total_races}, Handicap: {handicaps} ({handicaps/total_races*100:.1f}%)")
    print(f"  p_raw: median={np.median(p_raws):.3f}, mean={np.mean(p_raws):.3f}, "
          f"P25={np.percentile(p_raws,25):.3f}, P75={np.percentile(p_raws,75):.3f}")
    print(f"  field: median={np.median(fields):.0f}, mean={np.mean(fields):.1f}, "
          f"min={min(fields)}, max={max(fields)}")

    # Fixed baselines
    results = []
    for n in [1,2,3,4]:
        wr = sim_adaptive(weeks, pc, lambda top, ri, n=n: n)
        r = analyze(wr, f'WPs_fixed_{n}')
        if r: results.append(r)

    # Adaptive rules: vary N based on conditions
    # Parameters to search:
    #  - p_raw threshold for "strong" (top horse p_raw >= X -> fewer picks)
    #  - field size threshold for "big field" (field >= Y -> more picks)
    #  - handicap bonus (is_handicap -> +1 pick)

    rules = {}

    # Rule type 1: p_raw based (strong top -> fewer picks)
    for p_strong in [0.25, 0.30, 0.35]:
        for p_weak in [0.15, 0.18, 0.20]:
            for base in [2, 3]:
                name = f'proba_{p_strong}_{p_weak}_b{base}'
                def make_fn(ps, pw, b):
                    def fn(top, ri):
                        p = float(top[0].get('pred_proba_p_raw', 0) or 0)
                        if p >= ps: return max(b-1, 1)
                        if p <= pw: return min(b+1, 4)
                        return b
                    return fn
                rules[name] = make_fn(p_strong, p_weak, base)

    # Rule type 2: field size based
    for small in [10, 12]:
        for big in [16, 14]:
            for base in [2, 3]:
                name = f'field_{small}_{big}_b{base}'
                def make_fn(s, b2, b):
                    def fn(top, ri):
                        f = ri['num_runners']
                        if f <= s: return max(b-1, 1)
                        if f >= b2: return min(b+1, 4)
                        return b
                    return fn
                rules[name] = make_fn(small, big, base)

    # Rule type 3: combined p_raw + field + handicap
    for p_strong in [0.28, 0.32]:
        for p_weak in [0.17, 0.20]:
            for big_field in [14, 16]:
                for handi_plus in [0, 1]:
                    for base in [2, 3]:
                        name = f'combo_ps{p_strong}_pw{p_weak}_f{big_field}_h{handi_plus}_b{base}'
                        def make_fn(ps, pw, bf, hp, b):
                            def fn(top, ri):
                                p = float(top[0].get('pred_proba_p_raw', 0) or 0)
                                f = ri['num_runners']
                                n = b
                                if p >= ps: n -= 1
                                if p <= pw: n += 1
                                if f >= bf: n += 1
                                if ri['is_handicap'] and hp: n += 1
                                return max(1, min(4, n))
                            return fn
                        rules[name] = make_fn(p_strong, p_weak, big_field, handi_plus, base)

    print(f"\n  Testing {len(rules)} adaptive rules + {len(results)} baselines...")

    for name, fn in rules.items():
        wr = sim_adaptive(weeks, pc, fn)
        r = analyze(wr, name)
        if r: results.append(r)

    # Sort by ROI
    results.sort(key=lambda x: -x['roi'])

    # Budget filter: avg <= 200pt
    budget = [r for r in results if r['at'] <= 200 and r['ht'] >= 1]

    print(f"\n{'='*105}")
    print(f"  Results (avg<=200pt, {len(budget)} strategies)")
    print(f"{'='*105}")
    print('{:<45} {:>4} {:>3} {:>5} {:>5} {:>10} {:>10} {:>6} | {:>3} {:>3} {:>6}'.format(
        'strategy','pl','ht','rate','avg','cost','pay','ROI','p25','h25','R25'))
    print('-'*110)
    for s in budget[:40]:
        print('{:<45} {:>4} {:>3} {:>4.1%} {:>5.0f} {:>10,} {:>10,} {:>5.1%} | {:>3} {:>3} {:>5.1%}'.format(
            s['name'],s['pl'],s['ht'],s['ht']/s['pl'],s['at'],s['tc'],s['tp'],s['roi'],
            s['pl25'],s['ht25'],s['roi25']))

    # Show the best adaptive vs fixed comparison
    print(f"\n{'='*105}")
    print(f"  Fixed vs Adaptive (top picks)")
    print(f"{'='*105}")
    for s in results:
        if s['name'].startswith('WPs_fixed') or s['roi'] > 1500 or (s['at'] <= 100 and s['ht'] >= 25):
            if s['at'] <= 300:
                print('{:<45} {:>4} {:>3} {:>4.1%} {:>5.0f} {:>10,} {:>10,} {:>5.1%} | {:>3} {:>3} {:>5.1%}'.format(
                    s['name'],s['pl'],s['ht'],s['ht']/s['pl'],s['at'],s['tc'],s['tp'],s['roi'],
                    s['pl25'],s['ht25'],s['roi25']))

    # Hit details for top 3
    print(f"\n{'='*105}")
    print(f"  Hit details (top 3 adaptive strategies in budget)")
    print(f"{'='*105}")
    adaptive_budget = [r for r in budget if not r['name'].startswith('WPs_fixed')]
    for s in adaptive_budget[:3]:
        print(f"\n  [{s['name']}] hits={s['ht']} avg={s['at']:.0f}pt ROI={s['roi']:.1%}")
        for i in range(s['ht']):
            print(f"    {s['hd'][i]}: {s['hp'][i]:>10,}")


if __name__ == '__main__':
    main()
