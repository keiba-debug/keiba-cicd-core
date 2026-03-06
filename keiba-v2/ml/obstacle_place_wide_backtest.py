#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""障害レース 単勝・ワイド・複勝 バックテスト分析

Pモデル予測 × 実払戻(haraimodoshi) で券種別ROIを横断比較。
"""
import json, glob, sys, pickle, time
from pathlib import Path
from itertools import combinations
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import config
from core.odds_db import batch_get_place_odds
from ml.simulate_multi_leg import load_haraimodoshi

ml_dir = config.ml_dir()
import lightgbm as lgb

# モデル
with open(ml_dir / 'model_obstacle_meta.json', encoding='utf-8') as f:
    meta = json.load(f)

features_p = meta.get('features_p') or meta.get('features', [])
features_w = meta.get('features_w') or features_p
model_p = lgb.Booster(model_file=str(ml_dir / 'model_obstacle_p.txt'))
model_w = lgb.Booster(model_file=str(ml_dir / 'model_obstacle_w.txt'))

cal_path = ml_dir / 'calibrators_obstacle.pkl'
cal_p, cal_w = None, None
if cal_path.exists():
    with open(cal_path, 'rb') as f:
        cals = pickle.load(f)
    if isinstance(cals, dict):
        cal_p = cals.get('cal_p')
        cal_w = cals.get('cal_w')

from ml.experiment import load_data, build_pit_personnel_timeline
from ml.experiment_obstacle import build_obstacle_dataset
from ml.features.obstacle_features import build_obstacle_personnel_timelines

t0 = time.time()

(history_cache, trainer_index, jockey_index,
 date_index, pace_index, kb_ext_index, training_summary_index,
 race_level_index, pedigree_index, sire_stats_index,
 jrdb_sed_index, *_extra) = load_data()

pit_trainer_tl, pit_jockey_tl = build_pit_personnel_timeline(years=list(range(2019, 2027)))
jockey_obstacle_tl, trainer_obstacle_tl = build_obstacle_personnel_timelines(history_cache)

build_kwargs = dict(
    date_index=date_index, history_cache=history_cache,
    trainer_index=trainer_index, jockey_index=jockey_index,
    pace_index=pace_index, kb_ext_index=kb_ext_index,
    use_db_odds=True, race_level_index=race_level_index,
    pedigree_index=pedigree_index, sire_stats_index=sire_stats_index,
    pit_trainer_tl=pit_trainer_tl, pit_jockey_tl=pit_jockey_tl,
    jockey_obstacle_tl=jockey_obstacle_tl,
    trainer_obstacle_tl=trainer_obstacle_tl,
    jrdb_sed_index=jrdb_sed_index,
)

df = build_obstacle_dataset(**build_kwargs, min_year=2025, max_year=2025, min_month=1, max_month=12)
if 'is_win' not in df.columns:
    df['is_win'] = (df['finish_position'] == 1).astype(int)

print(f'2025 obstacle: {len(df)} entries, {df["race_id"].nunique()} races')

# P/W 予測
avail_p = [f for f in features_p if f in df.columns]
avail_w = [f for f in features_w if f in df.columns]
X_p = df[avail_p].values.astype(np.float64)
X_w = df[avail_w].values.astype(np.float64)

pred_p_raw = model_p.predict(X_p)
pred_w_raw = model_w.predict(X_w)
pred_w_cal = cal_w.predict(pred_w_raw) if cal_w else pred_w_raw

df['pred_p_raw'] = pred_p_raw
df['pred_w_cal'] = pred_w_cal

df['rank_p'] = df.groupby('race_id')['pred_p_raw'].rank(ascending=False, method='first').astype(int)
df['rank_w'] = df.groupby('race_id')['pred_w_cal'].rank(ascending=False, method='first').astype(int)
df['is_top3'] = ((df['finish_position'] >= 1) & (df['finish_position'] <= 3)).astype(int)

# DBオッズ
race_ids = df['race_id'].unique().tolist()
place_odds_all = batch_get_place_odds(race_ids)

def get_place_low(row):
    return (place_odds_all.get(row['race_id'], {}).get(int(row['umaban']), {})).get('odds_low', 0) or 0

df['place_odds_min'] = df.apply(get_place_low, axis=1)
df['win_ev'] = df['pred_w_cal'] * df['odds']
df['place_ev'] = df['pred_p_raw'] * df['place_odds_min']

# 払戻データ
haraimodoshi = load_haraimodoshi(race_ids)
print(f'Haraimodoshi: {len(haraimodoshi)}/{len(race_ids)} races')
print(f'Elapsed: {time.time()-t0:.0f}s')

# =================================================
# 1) 単勝 バックテスト
# =================================================
print(f'\n{"="*60}')
print(f'  1) 単勝 (Win) バックテスト')
print(f'{"="*60}')

print('\n=== rank_w別 単勝ROI ===')
for rw_min, rw_max, label in [
    (1, 1, 'rank_w=1'), (2, 2, 'rank_w=2'), (3, 3, 'rank_w=3'),
    (1, 3, 'rank_w 1-3'),
]:
    mask = (df['rank_w'] >= rw_min) & (df['rank_w'] <= rw_max) & (df['odds'] > 0)
    sub = df[mask]
    wins = sub['is_win'].sum()
    payout = (sub[sub['is_win'] == 1]['odds']).sum()
    roi = payout / len(sub) * 100 if len(sub) > 0 else 0
    rate = wins / len(sub) * 100 if len(sub) > 0 else 0
    print(f'  {label:>10}: {len(sub):>4}頭  勝ち{int(wins):>3}({rate:>5.1f}%)  ROI={roi:>5.1f}%')

print('\n=== 単勝EV帯別 ROI ===')
for ev_min, ev_max, label in [
    (0, 0.5, '<0.5'), (0.5, 1.0, '0.5-1.0'), (1.0, 1.5, '1.0-1.5'),
    (1.5, 2.0, '1.5-2.0'), (2.0, 3.0, '2.0-3.0'), (3.0, 999, '3.0+'),
]:
    mask = (df['win_ev'] >= ev_min) & (df['win_ev'] < ev_max) & (df['odds'] > 0)
    sub = df[mask]
    if len(sub) == 0:
        continue
    wins = sub['is_win'].sum()
    payout = (sub[sub['is_win'] == 1]['odds']).sum()
    roi = payout / len(sub) * 100
    rate = wins / len(sub) * 100
    print(f'  {label:>7}: {len(sub):>4}頭  勝ち{int(wins):>3}({rate:>5.1f}%)  ROI={roi:>6.1f}%')

# =================================================
# 2) ワイド バックテスト
# =================================================
print(f'\n{"="*60}')
print(f'  2) ワイド (Wide) バックテスト')
print(f'{"="*60}')

wide_results = []

for race_id, group in df.groupby('race_id'):
    if race_id not in haraimodoshi:
        continue

    payouts = haraimodoshi[race_id]
    wide_payouts = payouts.get('wide', [])
    if payouts['flags'].get('WIDE'):
        continue

    wide_map = {pair: pay for pair, pay in wide_payouts}

    group_sorted = group.sort_values('rank_p')
    umabans = group_sorted['umaban'].values
    rank_ps = group_sorted['rank_p'].values
    pred_ps = group_sorted['pred_p_raw'].values

    for i in range(min(6, len(umabans))):
        for j in range(i + 1, min(6, len(umabans))):
            u1, u2 = int(umabans[i]), int(umabans[j])
            rp1, rp2 = int(rank_ps[i]), int(rank_ps[j])
            pp1, pp2 = float(pred_ps[i]), float(pred_ps[j])

            pair = frozenset({u1, u2})
            payout = wide_map.get(pair, 0)
            hit = 1 if payout > 0 else 0

            wide_results.append({
                'race_id': race_id,
                'u1': u1, 'u2': u2,
                'rp1': rp1, 'rp2': rp2,
                'max_rp': max(rp1, rp2),
                'pp1': pp1, 'pp2': pp2,
                'pair_prob': pp1 * pp2,
                'payout': payout / 100 if payout > 0 else 0,
                'hit': hit,
            })

wdf = pd.DataFrame(wide_results)
print(f'\nTotal wide pairs analyzed: {len(wdf)}')
print(f'Hit rate: {wdf["hit"].mean()*100:.1f}%')

print('\n=== Pモデル rank_p 上位ペア別 ワイドROI ===')
for max_rp, label in [
    (2, 'Top1-2 (1点)'),
    (3, 'Top1-3 (3点)'),
    (4, 'Top1-4 (6点)'),
    (5, 'Top1-5 (10点)'),
]:
    sub = wdf[wdf['max_rp'] <= max_rp]
    if len(sub) == 0:
        continue
    hits = sub['hit'].sum()
    total_payout = sub['payout'].sum()
    n_races = sub['race_id'].nunique()
    cost = len(sub)
    roi = total_payout / cost * 100
    pts_per_race = len(sub) / n_races
    print(f'  {label:>15}: {len(sub):>4}点  的中{int(hits):>3}({hits/len(sub)*100:>5.1f}%)  '
          f'ROI={roi:>6.1f}%  ({pts_per_race:.1f}点/R, {n_races}R)')

print('\n=== ワイド 個別ペア詳細 ===')
for rp1, rp2, label in [
    (1, 2, 'Top1 x Top2'),
    (1, 3, 'Top1 x Top3'),
    (2, 3, 'Top2 x Top3'),
    (1, 4, 'Top1 x Top4'),
    (1, 5, 'Top1 x Top5'),
]:
    sub = wdf[(wdf['rp1'] == rp1) & (wdf['rp2'] == rp2)]
    if len(sub) == 0:
        continue
    hits = sub['hit'].sum()
    total_payout = sub['payout'].sum()
    roi = total_payout / len(sub) * 100
    avg_pay = sub[sub['hit'] == 1]['payout'].mean() if hits > 0 else 0
    rate = hits / len(sub) * 100
    print(f'  {label:>13}: {len(sub):>4}R  的中{int(hits):>3}({rate:>5.1f}%)  '
          f'ROI={roi:>6.1f}%  平均配当{avg_pay:>5.1f}倍')

# =================================================
# 3) 券種別 ROI まとめ
# =================================================
print(f'\n{"="*60}')
print(f'  3) 券種別 ROI まとめ (障害2025, {df["race_id"].nunique()}R)')
print(f'{"="*60}')

# 複勝 rank_p top3
pt3 = df[(df['rank_p'] <= 3) & (df['place_odds_min'] > 0)]
pt3_roi = pt3[pt3['is_top3'] == 1]['place_odds_min'].sum() / len(pt3) * 100 if len(pt3) > 0 else 0
pt3_hit = pt3['is_top3'].mean() * 100

# 単勝 rank_w top1
wt1 = df[(df['rank_w'] == 1) & (df['odds'] > 0)]
wt1_roi = wt1[wt1['is_win'] == 1]['odds'].sum() / len(wt1) * 100 if len(wt1) > 0 else 0
wt1_hit = wt1['is_win'].mean() * 100

# ワイド Top1×2
w12 = wdf[(wdf['rp1'] == 1) & (wdf['rp2'] == 2)]
w12_roi = w12['payout'].sum() / len(w12) * 100 if len(w12) > 0 else 0
w12_hit = w12['hit'].mean() * 100

# ワイド Top1-3 BOX (3点)
w3box = wdf[wdf['max_rp'] <= 3]
w3box_roi = w3box['payout'].sum() / len(w3box) * 100 if len(w3box) > 0 else 0
w3box_hit = w3box['hit'].mean() * 100

# 複勝EV>=2.0
pev2 = df[(df['place_ev'] >= 2.0) & (df['place_odds_min'] > 0)]
pev2_roi = pev2[pev2['is_top3'] == 1]['place_odds_min'].sum() / len(pev2) * 100 if len(pev2) > 0 else 0
pev2_hit = pev2['is_top3'].mean() * 100

print(f'  {"券種":<20}  {"点/R":>5}  {"的中率":>6}  {"ROI":>7}')
print(f'  {"-"*50}')
print(f'  {"複勝 rank_p 1-3":<20}  {"3":>5}  {pt3_hit:>5.1f}%  {pt3_roi:>6.1f}%')
print(f'  {"複勝 EV>=2.0":<20}  {"var":>5}  {pev2_hit:>5.1f}%  {pev2_roi:>6.1f}%')
print(f'  {"単勝 rank_w=1":<20}  {"1":>5}  {wt1_hit:>5.1f}%  {wt1_roi:>6.1f}%')
print(f'  {"ワイド Top1x2":<20}  {"1":>5}  {w12_hit:>5.1f}%  {w12_roi:>6.1f}%')
print(f'  {"ワイド Top1-3 BOX":<20}  {"3":>5}  {w3box_hit:>5.1f}%  {w3box_roi:>6.1f}%')
