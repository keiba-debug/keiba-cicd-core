#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E-004 分析先行: 出遅れシグナルに「切るべき負け組」のエッジがあるか測る。

背景: bet_engine の horse_slow_start_rate ペナルティは過去バックテストで **逆効果**
（除外馬の的中率 8.4% > 平均 5% — 出遅れ常習馬を切ると勝ち馬を切る）。
E-004 を素朴な「出遅れ率高い馬を減点」で実装すると同じ轍を踏むため、実装の前に
**VB 買い目の中で**出遅れシグナル（馬 ss率 / 騎手 ss率 / 逃げ馬×ss / 騎手 top3 崩壊）が
ROI を落とす負け組を識別できるかを bootstrap CI 付きで検証する。

読み取り専用。backtest_cache.json（df_to_race_predictions 出力＝結果付き・jockey_code 付き）と
slow_start_analysis.json を消費。判定: gap>=k ROI/CI ゲート（負け組の ROI 上限 CI が
ベースライン下限を下回れば「切るエッジあり」）。

Usage:
    python -m ml.analyze.analyze_slow_start_edge
    python -m ml.analyze.analyze_slow_start_edge --preset wide
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core import config
from ml.bet_engine import PRESETS, generate_recommendations
from ml.strategies.quality_gate import reliable_value


def _boot_roi_ci(bets, n_boot=2000, seed=0):
    """bet単位ブートストラップで ROI の95%CIを返す。bets=[(stake, ret)]。"""
    if not bets:
        return (0.0, 0.0, 0.0)
    arr = np.array(bets, dtype=float)  # [:,0]=stake, [:,1]=ret
    rng = np.random.default_rng(seed)
    n = len(arr)
    rois = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        s = arr[idx, 0].sum()
        r = arr[idx, 1].sum()
        rois.append(r / s * 100 if s > 0 else 0.0)
    point = arr[:, 1].sum() / arr[:, 0].sum() * 100 if arr[:, 0].sum() > 0 else 0.0
    return (point, float(np.percentile(rois, 2.5)), float(np.percentile(rois, 97.5)))


def load_jockey_ss_map(path=None):
    """slow_start_analysis.json jockey_ranking → {code: entry}。"""
    if path is None:
        path = config.analysis_dir() / "slow_start_analysis.json"
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    out = {}
    for r in d.get("jockey_ranking", []):
        c = r.get("jockey_code")
        if c:
            out[str(c)] = r
    return out


def _bucket_report(title, groups):
    """groups: {label: [(stake,ret,is_win)]} を ROI/CI/win% で表示。"""
    print(f"\n  --- {title} ---")
    print(f'  {"bucket":>22} {"N":>6} {"win%":>7} {"ROI%":>7} {"CI_low":>7} {"CI_hi":>7}')
    print(f'  {"-"*64}')
    for label, rows in groups.items():
        if not rows:
            print(f'  {label:>22} {0:>6}')
            continue
        n = len(rows)
        wins = sum(1 for _, _, w in rows if w)
        bets = [(s, r) for s, r, _ in rows]
        point, lo, hi = _boot_roi_ci(bets)
        print(f'  {label:>22} {n:>6} {wins/n*100:>6.1f}% {point:>6.1f}% {lo:>6.1f}% {hi:>6.1f}%')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--preset', default='standard')
    ap.add_argument('--cache', default=None)
    args = ap.parse_args()

    cache_path = Path(args.cache) if args.cache else (Path(config.data_root()) / 'ml' / 'backtest_cache.json')
    with open(cache_path, encoding='utf-8') as f:
        race_preds = json.load(f)
    print(f'[Load] {len(race_preds)} races from {cache_path}')

    jmap = load_jockey_ss_map()
    print(f'[Load] jockey ss map: {len(jmap)} 騎手')

    params = PRESETS[args.preset]
    recs = generate_recommendations(race_preds, params, budget=30000)
    win_recs = [r for r in recs if r.bet_type in ('単勝', '単複')]
    print(f'[Bets] preset={args.preset}: {len(win_recs)} 単勝/単複 bets')

    # entry lookup
    elut = {}
    for race in race_preds:
        for e in race['entries']:
            elut[(race['race_id'], e['umaban'])] = e

    # baseline rows = (stake, ret, is_win) for win bets (100円均一で ROI 評価)
    base_rows = []
    rows_h = {'ss_missing': [], 'ss_0-20': [], 'ss_20-35': [], 'ss_35+': []}
    rows_fr = {'front_runner_ss20+': [], 'other': []}
    rows_j = {'jss_lo(<25%)': [], 'jss_mid(25-40%)': [], 'jss_hi(40%+)': [], 'jss_missing': []}
    rows_jt = {'jt3_drop_hi(>=8pt)': [], 'jt3_drop_lo(<8pt)': [], 'jt3_missing': []}

    for r in win_recs:
        e = elut.get((r.race_id, r.umaban))
        if e is None:
            continue
        odds = e.get('odds', 0) or 0
        is_win = bool(e.get('is_win', 0))
        stake, ret = 100.0, (odds * 100.0 if is_win else 0.0)
        base_rows.append((stake, ret, is_win))

        # --- 馬 ss率 ---
        ss = e.get('horse_slow_start_rate', -1)
        if ss is None or ss < 0:
            rows_h['ss_missing'].append((stake, ret, is_win))
        elif ss < 0.20:
            rows_h['ss_0-20'].append((stake, ret, is_win))
        elif ss < 0.35:
            rows_h['ss_20-35'].append((stake, ret, is_win))
        else:
            rows_h['ss_35+'].append((stake, ret, is_win))

        # --- 逃げ馬 × ss20+ (理論: 逃げ馬は出遅れでプラン崩壊) ---
        c1 = e.get('last_race_corner1_ratio', -1)
        is_fr = (c1 is not None and 0 <= c1 <= 0.25)
        if is_fr and ss is not None and ss >= 0.20:
            rows_fr['front_runner_ss20+'].append((stake, ret, is_win))
        else:
            rows_fr['other'].append((stake, ret, is_win))

        # --- 騎手 ss率 (reliable_value=ci95.lower で上振れ抑制) ---
        jc = e.get('jockey_code')
        jentry = jmap.get(str(jc)) if jc else None
        if jentry is None:
            rows_j['jss_missing'].append((stake, ret, is_win))
            rows_jt['jt3_missing'].append((stake, ret, is_win))
        else:
            jss = reliable_value(jentry.get('quality'), jentry.get('slow_start_rate', 0.0) or 0.0)
            if jss < 0.25:
                rows_j['jss_lo(<25%)'].append((stake, ret, is_win))
            elif jss < 0.40:
                rows_j['jss_mid(25-40%)'].append((stake, ret, is_win))
            else:
                rows_j['jss_hi(40%+)'].append((stake, ret, is_win))
            # top3 崩壊度 = top3_normal - top3_when_slow（大きいほど出遅れに弱い騎手）
            drop = (jentry.get('top3_rate_normal', 0) or 0) - (jentry.get('top3_rate_when_slow', 0) or 0)
            if drop >= 0.08:
                rows_jt['jt3_drop_hi(>=8pt)'].append((stake, ret, is_win))
            else:
                rows_jt['jt3_drop_lo(<8pt)'].append((stake, ret, is_win))

    # baseline
    bp, blo, bhi = _boot_roi_ci([(s, r) for s, r, _ in base_rows])
    bw = sum(1 for _, _, w in base_rows if w)
    print(f'\n{"="*66}')
    print(f'  E-004 出遅れエッジ分析 (preset={args.preset})')
    print(f'{"="*66}')
    print(f'  baseline: N={len(base_rows)} win%={bw/len(base_rows)*100:.1f}% '
          f'ROI={bp:.1f}% CI[{blo:.1f}, {bhi:.1f}]')

    _bucket_report('馬 slow_start_rate 別', rows_h)
    _bucket_report('逃げ馬×ss20+ (プラン崩壊仮説)', rows_fr)
    _bucket_report('騎手 slow_start_rate 別 (ci95.lower)', rows_j)
    _bucket_report('騎手 top3崩壊度 別 (normal-when_slow)', rows_jt)

    print('\n  判定基準: ある負け組の ROI CI上限 < baseline ROI CI下限 なら「切るエッジ」候補。')
    print('  逆に負け組の of win% が baseline 以上なら除外は逆効果（line338の轍）。')
    print('\nDone.')


if __name__ == '__main__':
    main()
