#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""WIN5 Hybrid combo simulation — raw data + model combos"""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from core.config import races_dir
from core import db

def load_win5_schedule():
    sr = db.query("SELECT w.KAISAI_NEN, w.KAISAI_GAPPI, w.RACE_CODE1, w.RACE_CODE2, w.RACE_CODE3, w.RACE_CODE4, w.RACE_CODE5 FROM win5 w ORDER BY w.KAISAI_NEN, w.KAISAI_GAPPI")
    pr = db.query("SELECT KAISAI_NEN, KAISAI_GAPPI, WIN5_KUMIBAN1, WIN5_KUMIBAN2, WIN5_KUMIBAN3, WIN5_KUMIBAN4, WIN5_KUMIBAN5, WIN5_HARAIMODOSHIKIN FROM win5_haraimodoshi ORDER BY KAISAI_NEN, KAISAI_GAPPI")
    pi = {}
    for r in pr:
        k = r['KAISAI_NEN'].strip() + r['KAISAI_GAPPI'].strip()
        if k not in pi: pi[k] = r
    weeks = []
    for r in sr:
        y = r['KAISAI_NEN'].strip(); g = r['KAISAI_GAPPI'].strip(); ds = y+g
        races = []
        for i in range(1,6):
            rc = (r.get(f'RACE_CODE{i}') or '').strip()
            p = pi.get(ds)
            w = 0
            if p:
                kb = (p.get(f'WIN5_KUMIBAN{i}') or '').strip()
                w = int(kb) if kb.isdigit() else 0
            races.append({'race_id': rc, 'winner': w})
        p = pi.get(ds)
        po = int((p.get('WIN5_HARAIMODOSHIKIN') or '0').strip()) if p else 0
        weeks.append({'date': ds, 'races': races, 'payout': po})
    return weeks

def load_preds(ds):
    y,m,d = ds[:4],ds[4:6],ds[6:8]
    p = races_dir()/y/m/d/'predictions.json'
    if not p.exists(): return {}
    with open(p, encoding='utf-8') as f: data = json.load(f)
    return {r['race_id']: r.get('entries',[]) for r in data.get('races',[])}

KBO = {'\u25ce':1,'\u25cb':2,'\u25b2':3,'\u25b3':4,'\u25bd':5,'\u00d7':6,'':99}
def kb_top(e,n): return [int(x['umaban']) for x in sorted(e, key=lambda x:(KBO.get(x.get('kb_mark',''),99),-float(x.get('kb_rating',0) or 0)))[:n]]
def idm_top(e,n): return [int(x['umaban']) for x in sorted(e, key=lambda x:-float(x.get('jrdb_idm',0) or 0))[:n]]
def w_top(e,n):
    v=[x for x in e if (x.get('rank_w') or 0)>0]
    return [int(x['umaban']) for x in sorted(v, key=lambda x:x['rank_w'])[:n]]
def p_top(e,n):
    v=[x for x in e if (x.get('rank_p') or 0)>0]
    return [int(x['umaban']) for x in sorted(v, key=lambda x:x['rank_p'])[:n]]
def wps_top(e,n):
    v=[x for x in e if (x.get('rank_w') or 0)>0 and (x.get('rank_p') or 0)>0]
    return [int(x['umaban']) for x in sorted(v, key=lambda x:x['rank_w']+x['rank_p'])[:n]]
def U(*ls): return list(set().union(*[set(l) for l in ls]))

PLANS = {
    'A': ('kb1+P2', lambda e: U(kb_top(e,1), p_top(e,2))),
    'B': ('idm1+W2', lambda e: U(idm_top(e,1), w_top(e,2))),
    'C': ('kb1+WPs2', lambda e: U(kb_top(e,1), wps_top(e,2))),
    'D': ('idm2+kb1+W1', lambda e: U(idm_top(e,2), kb_top(e,1), w_top(e,1))),
}

def sim_plan(weeks, pc, select_fn):
    results = []
    for wk in weeks:
        pd = pc.get(wk['date'],{})
        if not pd: results.append(None); continue
        ss = []; ok=True
        for rc in wk['races']:
            en = pd.get(rc['race_id'],[])
            if not en: ok=False; break
            sl = select_fn(en)
            if not sl: ok=False; break
            ss.append(set(sl))
        if not ok or len(ss)<5 or not all(r['winner']>0 for r in wk['races']):
            results.append(None); continue
        tx=1
        for s in ss: tx*=len(s)
        h = all(wk['races'][i]['winner'] in ss[i] for i in range(5))
        results.append({'tx':tx,'c':tx*100,'h':h,'p':wk['payout'] if h else 0,'d':wk['date']})
    return results

def main():
    print("="*80)
    print("  WIN5 Hybrid Combo Simulation")
    print("="*80)

    weeks = load_win5_schedule()
    pc = {}
    for w in weeks:
        if w['date'] not in pc:
            p = load_preds(w['date'])
            if p: pc[w['date']] = p
    print(f"  {len(weeks)} weeks, {len(pc)} dates with predictions")

    plan_results = {}
    for pk,(pname,pfn) in PLANS.items():
        plan_results[pk] = sim_plan(weeks, pc, pfn)

    # Individual
    print(f"\n{'='*80}")
    print("  Individual Plans")
    print(f"{'='*80}")
    for pk,(pname,_) in PLANS.items():
        res = [r for r in plan_results[pk] if r is not None]
        hits = [r for r in res if r['h']]
        tc = sum(r['c'] for r in res)
        tp = sum(r['p'] for r in hits)
        at = np.mean([r['tx'] for r in res])
        roi = tp/tc if tc>0 else 0
        rate = len(hits)/len(res) if res else 0
        print(f"  {pk} [{pname}]: {len(res)}w  hit={len(hits)} ({rate:.1%})  avg={at:.0f}pt  "
              f"cost={tc:,}  pay={tp:,}  ROI={roi:.1%}")

    # Combos
    combos = [
        ('A+B', ['A','B']),
        ('A+C', ['A','C']),
        ('B+C', ['B','C']),
        ('A+B+C', ['A','B','C']),
        ('A+D', ['A','D']),
        ('B+D', ['B','D']),
        ('A+B+D', ['A','B','D']),
        ('A+B+C+D', ['A','B','C','D']),
    ]

    print(f"\n{'='*80}")
    print("  Combo Plans (each plan independently purchased, payout per hitting plan)")
    print(f"{'='*80}")
    print(f"  {'combo':<12} {'played':>5} {'hits':>4} {'rate':>6} {'avg_cost':>10} "
          f"{'total_cost':>12} {'total_pay':>12} {'ROI':>7} {'final_PL':>12} {'maxDD':>10} {'streak':>6}")
    print("-"*100)

    for cname, ckeys in combos:
        total_cost = 0; total_payout = 0; hit_weeks = 0
        cum_pl = 0; peak = 0; max_dd = 0; played = 0
        losing = 0; max_losing = 0

        for i in range(len(weeks)):
            plans_active = [(k, plan_results[k][i]) for k in ckeys if plan_results[k][i] is not None]
            if not plans_active: continue
            played += 1
            week_cost = sum(r['c'] for _,r in plans_active)
            week_payout = sum(r['p'] for _,r in plans_active if r['h'])
            total_cost += week_cost
            total_payout += week_payout
            cum_pl += (week_payout - week_cost)
            if any(r['h'] for _,r in plans_active):
                hit_weeks += 1; losing = 0
            else:
                losing += 1; max_losing = max(max_losing, losing)
            if cum_pl > peak: peak = cum_pl
            dd = peak - cum_pl
            if dd > max_dd: max_dd = dd

        roi = total_payout/total_cost if total_cost > 0 else 0
        avg_wc = total_cost / played if played else 0
        desc = '+'.join(PLANS[k][0] for k in ckeys)
        print(f"  {cname:<12} {played:>5} {hit_weeks:>4} {hit_weeks/played if played else 0:>5.1%} "
              f"{avg_wc:>10,.0f} {total_cost:>12,} {total_payout:>12,} {roi:>6.1%} "
              f"{cum_pl:>+12,} {max_dd:>10,} {max_losing:>5}w")

    # Year breakdown for A+B+C+D
    print(f"\n{'='*80}")
    print("  A+B+C+D Year-by-Year")
    print(f"{'='*80}")
    ckeys = ['A','B','C','D']
    yearly = {}
    for i in range(len(weeks)):
        yr = weeks[i]['date'][:4]
        plans_active = [(k, plan_results[k][i]) for k in ckeys if plan_results[k][i] is not None]
        if not plans_active: continue
        if yr not in yearly: yearly[yr] = {'cost':0,'pay':0,'hits':0,'weeks':0}
        yearly[yr]['weeks'] += 1
        yearly[yr]['cost'] += sum(r['c'] for _,r in plans_active)
        pay = sum(r['p'] for _,r in plans_active if r['h'])
        yearly[yr]['pay'] += pay
        if any(r['h'] for _,r in plans_active): yearly[yr]['hits'] += 1

    for yr in sorted(yearly.keys()):
        y = yearly[yr]
        roi = y['pay']/y['cost'] if y['cost']>0 else 0
        pl = y['pay'] - y['cost']
        print(f"  {yr}: {y['weeks']:>3}w  hits={y['hits']:>2}  cost={y['cost']:>10,}  "
              f"pay={y['pay']:>12,}  ROI={roi:>7.1%}  P/L={pl:>+12,}")

    # Hit overlap analysis
    print(f"\n{'='*80}")
    print("  Hit Overlap Analysis (which plans catch which weeks)")
    print(f"{'='*80}")
    hit_dates = set()
    for pk in PLANS:
        for r in plan_results[pk]:
            if r and r['h']: hit_dates.add(r['d'])

    for d in sorted(hit_dates):
        hits_by = []
        for pk in PLANS:
            idx = next((i for i,w in enumerate(weeks) if w['date']==d), None)
            if idx is not None:
                r = plan_results[pk][idx]
                if r and r['h']:
                    hits_by.append(f"{pk}({r['tx']}pt)")
        payout = next((w['payout'] for w in weeks if w['date']==d), 0)
        print(f"  {d}: {' '.join(hits_by):<40} payout={payout:>10,}")

if __name__ == '__main__':
    main()
