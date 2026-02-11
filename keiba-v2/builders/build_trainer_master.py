#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
調教師マスター構築

SE_DATAから調教師別の成績を集計して data3/masters/trainers.json を生成。

Usage:
    python -m builders.build_trainer_master [--years 2020-2026]
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
from core.jravan import se_parser


def build_trainer_stats(years: List[int]) -> Dict[str, Dict]:
    """SE_DATAから調教師別成績を集計"""
    print(f"[SE] Scanning SE_DATA for years {years[0]}-{years[-1]}...")

    trainers = defaultdict(lambda: {
        'code': '',
        'name': '',
        'total_runs': 0,
        'wins': 0,
        'top2': 0,
        'top3': 0,
        'venue_stats': defaultdict(lambda: {'runs': 0, 'wins': 0, 'top3': 0}),
        'year_stats': defaultdict(lambda: {'runs': 0, 'wins': 0, 'top3': 0}),
    })

    count = 0
    for rec in se_parser.scan(years):
        tc = rec.get('trainer_code', '')
        if not tc or not tc.isdigit():
            continue

        fp = rec['finish_position']
        if fp <= 0:
            continue

        t = trainers[tc]
        t['code'] = tc
        if not t['name'] or len(rec['trainer_name']) > len(t['name']):
            t['name'] = rec['trainer_name']

        t['total_runs'] += 1
        if fp == 1:
            t['wins'] += 1
        if fp <= 2:
            t['top2'] += 1
        if fp <= 3:
            t['top3'] += 1

        # 場所別
        vc = rec['venue_code']
        vs = t['venue_stats'][vc]
        vs['runs'] += 1
        if fp == 1:
            vs['wins'] += 1
        if fp <= 3:
            vs['top3'] += 1

        # 年別
        year = rec['race_date'][:4]
        ys = t['year_stats'][year]
        ys['runs'] += 1
        if fp == 1:
            ys['wins'] += 1
        if fp <= 3:
            ys['top3'] += 1

        count += 1
        if count % 100_000 == 0:
            print(f"  ... {count:,} records processed")

    print(f"[SE] {count:,} records -> {len(trainers):,} trainers")
    return trainers


def finalize_stats(trainers: Dict[str, Dict]) -> List[Dict]:
    """勝率・連対率・複勝率を計算して最終形式に変換"""
    result = []
    for code, t in trainers.items():
        runs = t['total_runs']
        entry = {
            'code': t['code'],
            'name': t['name'],
            'total_runs': runs,
            'wins': t['wins'],
            'top2': t['top2'],
            'top3': t['top3'],
            'win_rate': round(t['wins'] / runs, 4) if runs > 0 else 0,
            'top2_rate': round(t['top2'] / runs, 4) if runs > 0 else 0,
            'top3_rate': round(t['top3'] / runs, 4) if runs > 0 else 0,
            'venue_stats': {
                vc: {
                    'runs': vs['runs'],
                    'wins': vs['wins'],
                    'top3': vs['top3'],
                    'top3_rate': round(vs['top3'] / vs['runs'], 4) if vs['runs'] > 0 else 0,
                }
                for vc, vs in t['venue_stats'].items()
            },
            'year_stats': {
                y: {
                    'runs': ys['runs'],
                    'wins': ys['wins'],
                    'top3': ys['top3'],
                    'top3_rate': round(ys['top3'] / ys['runs'], 4) if ys['runs'] > 0 else 0,
                }
                for y, ys in sorted(t['year_stats'].items())
            },
        }
        result.append(entry)

    result.sort(key=lambda x: x['total_runs'], reverse=True)
    return result


def parse_year_range(s: str) -> List[int]:
    if '-' in s:
        start, end = s.split('-', 1)
        return list(range(int(start), int(end) + 1))
    return [int(s)]


def main():
    parser = argparse.ArgumentParser(description='Build trainer master from SE_DATA')
    parser.add_argument('--years', default='2020-2026', help='Year range')
    args = parser.parse_args()

    years = parse_year_range(args.years)
    print(f"\n{'='*60}")
    print(f"  KeibaCICD v4 - Trainer Master Builder")
    print(f"  Years: {years[0]}-{years[-1]}")
    print(f"{'='*60}\n")

    t0 = time.time()

    trainers = build_trainer_stats(years)
    result = finalize_stats(trainers)

    # 保存
    out_path = config.masters_dir() / "trainers.json"
    config.ensure_dir(config.masters_dir())
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    elapsed = time.time() - t0

    # サマリ
    top5 = result[:5]
    print(f"\n{'='*60}")
    print(f"  Results")
    print(f"{'='*60}")
    print(f"  Trainers:  {len(result):,}")
    print(f"  Output:    {out_path}")
    print(f"  Elapsed:   {elapsed:.1f}s")
    print(f"\n  Top 5 by runs:")
    for t in top5:
        print(f"    {t['name']:>8} ({t['code']}): {t['total_runs']:>5} runs, "
              f"win={t['win_rate']:.1%}, top3={t['top3_rate']:.1%}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
