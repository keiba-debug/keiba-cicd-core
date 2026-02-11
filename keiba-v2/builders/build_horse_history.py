#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ML用馬過去走キャッシュ構築

SE_DATAから馬ごとの過去走成績をキャッシュとして
data3/ml/horse_history_cache.json を生成。

MLの特徴量計算時に全レースJSONをスキャンする代わりに、
このキャッシュから高速に過去走データを取得できる。

構造:
{
    "ketto_num": [
        {
            "race_id": "...",
            "race_date": "YYYY-MM-DD",
            "venue_code": "06",
            "finish_position": 1,
            "time": "1:12.6",
            "last_3f": 38.5,
            "odds": 4.2,
            "popularity": 3,
            "futan": 55.0,
            "num_runners": 16,
            "distance": 1200,
            "track_type": "dirt"
        },
        ...
    ]
}

Usage:
    python -m builders.build_horse_history [--years 2020-2026]
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from core.jravan import se_parser, sr_parser


def build_horse_history(years: List[int]) -> Dict[str, List[Dict]]:
    """SE_DATAから馬ごとの過去走をキャッシュ"""
    print(f"[SE] Scanning SE_DATA for years {years[0]}-{years[-1]}...")

    # SR_DATAインデックス（distance, track_type, num_runners取得用）
    print(f"[SR] Building SR index for race metadata...")
    sr_index = {}
    for sr in sr_parser.scan(years):
        sr_index[sr.race_id] = sr

    print(f"[SR] {len(sr_index):,} races indexed")

    histories = defaultdict(list)
    count = 0
    skipped = 0

    for rec in se_parser.scan(years):
        fp = rec['finish_position']
        if fp <= 0:
            skipped += 1
            continue

        ketto = rec['ketto_num']
        race_id = rec['race_id']

        # SR_DATAからレースメタデータを取得
        sr = sr_index.get(race_id)
        if sr is None:
            skipped += 1
            continue

        entry = {
            'race_id': race_id,
            'race_date': rec['race_date'],
            'venue_code': rec['venue_code'],
            'finish_position': fp,
            'time': rec['time'],
            'last_3f': rec['last_3f'],
            'odds': rec['odds'],
            'popularity': rec['popularity'],
            'futan': rec['futan'],
            'horse_weight': rec['horse_weight'],
            'jockey_code': rec.get('jockey_code', ''),
            'trainer_code': rec.get('trainer_code', ''),
            'corners': rec['corners'],
            'num_runners': sr.num_runners,
            'distance': sr.distance,
            'track_type': sr.track_type,
        }
        histories[ketto].append(entry)

        count += 1
        if count % 100_000 == 0:
            print(f"  ... {count:,} records processed, {len(histories):,} horses")

    # 各馬の走歴を日付順にソート
    for ketto in histories:
        histories[ketto].sort(key=lambda x: x['race_date'])

    print(f"[SE] {count:,} records -> {len(histories):,} horses (skipped: {skipped:,})")
    return histories


def parse_year_range(s: str) -> List[int]:
    if '-' in s:
        start, end = s.split('-', 1)
        return list(range(int(start), int(end) + 1))
    return [int(s)]


def main():
    parser = argparse.ArgumentParser(description='Build horse history cache for ML')
    parser.add_argument('--years', default='2020-2026', help='Year range')
    args = parser.parse_args()

    years = parse_year_range(args.years)
    print(f"\n{'='*60}")
    print(f"  KeibaCICD v4 - Horse History Cache Builder")
    print(f"  Years: {years[0]}-{years[-1]}")
    print(f"{'='*60}\n")

    t0 = time.time()

    histories = build_horse_history(years)

    # 保存
    out_path = config.ml_dir() / "horse_history_cache.json"
    config.ensure_dir(config.ml_dir())

    print(f"[Save] Writing {out_path}...")
    out_path.write_text(
        json.dumps(histories, ensure_ascii=False, separators=(',', ':')),
        encoding='utf-8',
    )

    file_size = out_path.stat().st_size / 1024 / 1024
    elapsed = time.time() - t0

    # 統計
    total_runs = sum(len(v) for v in histories.values())
    avg_runs = total_runs / len(histories) if histories else 0

    print(f"\n{'='*60}")
    print(f"  Results")
    print(f"{'='*60}")
    print(f"  Horses:        {len(histories):,}")
    print(f"  Total runs:    {total_runs:,}")
    print(f"  Avg runs/horse: {avg_runs:.1f}")
    print(f"  File size:     {file_size:.1f} MB")
    print(f"  Output:        {out_path}")
    print(f"  Elapsed:       {elapsed:.1f}s")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
