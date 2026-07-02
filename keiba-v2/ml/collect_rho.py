#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""隊列一致度 ρ (Spearman) の蓄積 (Session 187 Phase 3-c)

レースごとに「事前予想の着順」vs「実着順」の Spearman ρ を計算して
data3/ml/rho_history.json に蓄積する（race_id キーで冪等・再実行上書き）。

  - JRDB展開予想ゴール: leg_profiles.json の jrdb.goal.order
  - ML(AR着差回帰):     predictions.json の ar_deviation（高い=上位想定 → 符号反転）

Web の ResultTenkaiReplay に表示している答え合わせρと同じ定義。
蓄積の用途: 予想品質ベンチ / A-4 荒れ度モデルの目的変数・特徴量候補。

実行:
  python -m ml.collect_rho --date 2026-06-21
  python -m ml.collect_rho --from 2026-01-01 --to 2026-06-30
"""

import argparse
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from core import config

RHO_HISTORY_PATH = config.ml_dir() / 'rho_history.json'


def _rank(vals: List[float]) -> List[float]:
    """平均ランク（同順位対応）"""
    n = len(vals)
    idx = sorted(range(n), key=lambda i: vals[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and vals[idx[j + 1]] == vals[idx[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[idx[k]] = avg
        i = j + 1
    return ranks


def spearman(pairs: List[Tuple[float, float]]) -> Optional[float]:
    """Spearman ρ。n<3 または分散0は None"""
    n = len(pairs)
    if n < 3:
        return None
    ra = _rank([p[0] for p in pairs])
    rb = _rank([p[1] for p in pairs])
    ma = sum(ra) / n
    mb = sum(rb) / n
    num = da = db = 0.0
    for a, b in zip(ra, rb):
        xa, xb = a - ma, b - mb
        num += xa * xb
        da += xa * xa
        db += xb * xb
    if da <= 0 or db <= 0:
        return None
    return num / (da * db) ** 0.5


def collect_for_date(target: str) -> Dict[str, Dict]:
    """1開催日分の ρ を計算して {race_id: record} を返す"""
    y, m, d = target.split('-')
    day_dir = config.races_dir() / y / m / d
    if not day_dir.exists():
        return {}

    # leg_profiles.json (JRDB展開予想ゴール)
    leg_profiles: Dict = {}
    lp_path = day_dir / 'leg_profiles.json'
    if lp_path.exists():
        try:
            leg_profiles = json.loads(lp_path.read_text(encoding='utf-8'))
        except Exception:
            pass

    # predictions.json (ML ar_deviation)
    ml_by_race: Dict[str, Dict[int, float]] = {}
    pred_path = day_dir / 'predictions.json'
    if pred_path.exists():
        try:
            pred = json.loads(pred_path.read_text(encoding='utf-8'))
            for r in pred.get('races', []):
                devs = {}
                for e in r.get('entries', []):
                    dev = e.get('ar_deviation')
                    if dev is not None:
                        devs[int(e['umaban'])] = float(dev)
                if devs:
                    ml_by_race[str(r.get('race_id', ''))] = devs
        except Exception:
            pass

    records: Dict[str, Dict] = {}
    for f in sorted(day_dir.glob('race_*.json')):
        try:
            race = json.loads(f.read_text(encoding='utf-8'))
        except Exception:
            continue
        entries = race.get('entries')
        race_id = race.get('race_id')
        if not entries or not race_id:
            continue

        # 実着順（完走馬のみ）
        finishers = [
            (int(e['umaban']), int(e['finish_position']))
            for e in entries
            if e.get('finish_position') and int(e['finish_position']) > 0
        ]
        if len(finishers) < 3:
            continue

        # JRDB予想ゴール vs 実着順
        lp_race = leg_profiles.get(race_id, {})
        jrdb_pairs = []
        for umaban, finish in finishers:
            goal = (lp_race.get(str(umaban)) or {}).get('jrdb', {}).get('goal')
            if goal and goal.get('order'):
                jrdb_pairs.append((float(goal['order']), float(finish)))
        rho_jrdb = spearman(jrdb_pairs)

        # ML(ARd) vs 実着順（偏差値高い=上位着順 → 符号反転で順位化）
        ml_devs = ml_by_race.get(race_id, {})
        ml_pairs = [
            (-ml_devs[umaban], float(finish))
            for umaban, finish in finishers
            if umaban in ml_devs
        ]
        rho_ml = spearman(ml_pairs)

        if rho_jrdb is None and rho_ml is None:
            continue

        records[race_id] = {
            'date': target,
            'venue_code': race.get('venue_code'),
            'race_number': race.get('race_number'),
            'grade': race.get('grade') or '',
            'distance': race.get('distance'),
            'track_type': race.get('track_type'),
            'num_finishers': len(finishers),
            'rho_jrdb': round(rho_jrdb, 4) if rho_jrdb is not None else None,
            'n_jrdb': len(jrdb_pairs),
            'rho_ml': round(rho_ml, 4) if rho_ml is not None else None,
            'n_ml': len(ml_pairs),
        }

    return records


def main():
    parser = argparse.ArgumentParser(description='隊列一致度ρの蓄積')
    parser.add_argument('--date', help='単日 (YYYY-MM-DD)')
    parser.add_argument('--from', dest='date_from', help='範囲開始 (YYYY-MM-DD)')
    parser.add_argument('--to', dest='date_to', help='範囲終了 (YYYY-MM-DD)')
    args = parser.parse_args()

    if args.date:
        targets = [args.date]
    elif args.date_from and args.date_to:
        d0 = date.fromisoformat(args.date_from)
        d1 = date.fromisoformat(args.date_to)
        targets = []
        while d0 <= d1:
            targets.append(d0.isoformat())
            d0 += timedelta(days=1)
    else:
        parser.error('--date か --from/--to を指定')
        return

    # 既存履歴を読み込み（race_id キーで冪等マージ）
    history: Dict[str, Dict] = {}
    if RHO_HISTORY_PATH.exists():
        try:
            history = json.loads(RHO_HISTORY_PATH.read_text(encoding='utf-8'))
        except Exception:
            print(f'WARN: {RHO_HISTORY_PATH} の読み込みに失敗。新規作成します')

    total_new = 0
    for target in targets:
        recs = collect_for_date(target)
        if not recs:
            continue
        history.update(recs)
        total_new += len(recs)
        jr = [r['rho_jrdb'] for r in recs.values() if r['rho_jrdb'] is not None]
        ml = [r['rho_ml'] for r in recs.values() if r['rho_ml'] is not None]
        msg = f'[{target}] {len(recs)} races'
        if jr:
            msg += f' | JRDB mean rho={sum(jr) / len(jr):.3f} (n={len(jr)})'
        if ml:
            msg += f' | ML mean rho={sum(ml) / len(ml):.3f} (n={len(ml)})'
        print(msg)

    if total_new == 0:
        print('対象レースなし（結果未登録 or leg_profiles/predictions 無し）')
        return

    RHO_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    RHO_HISTORY_PATH.write_text(
        json.dumps(history, ensure_ascii=False, indent=1), encoding='utf-8'
    )
    print(f'Saved: {RHO_HISTORY_PATH} (total {len(history):,} races, +{total_new} this run)')


if __name__ == '__main__':
    main()
