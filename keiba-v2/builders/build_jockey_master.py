#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
騎手マスター構築

SE_DATAから騎手別の成績を集計して data3/masters/jockeys.json を生成。

Usage:
    python -m builders.build_jockey_master [--years 2020-2026]
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


def build_jockey_stats(years: List[int]) -> Dict[str, Dict]:
    """SE_DATAから騎手別成績を集計"""
    print(f"[SE] Scanning SE_DATA for years {years[0]}-{years[-1]}...")

    jockeys = defaultdict(lambda: {
        'code': '',
        'name': '',
        'total_runs': 0,
        'wins': 0,
        'top2': 0,
        'top3': 0,
        'venue_stats': defaultdict(lambda: {'runs': 0, 'wins': 0, 'top3': 0}),
        'track_stats': defaultdict(lambda: {'runs': 0, 'wins': 0, 'top3': 0}),
        'year_stats': defaultdict(lambda: {'runs': 0, 'wins': 0, 'top3': 0}),
    })

    count = 0
    for rec in se_parser.scan(years):
        jc = rec.get('jockey_code', '')
        if not jc or not jc.isdigit():
            continue

        fp = rec['finish_position']
        if fp <= 0:
            continue

        j = jockeys[jc]
        j['code'] = jc
        if not j['name'] or len(rec['jockey_name']) > len(j['name']):
            j['name'] = rec['jockey_name']

        j['total_runs'] += 1
        if fp == 1:
            j['wins'] += 1
        if fp <= 2:
            j['top2'] += 1
        if fp <= 3:
            j['top3'] += 1

        # 場所別
        vc = rec['venue_code']
        vs = j['venue_stats'][vc]
        vs['runs'] += 1
        if fp == 1:
            vs['wins'] += 1
        if fp <= 3:
            vs['top3'] += 1

        # トラック別（turf/dirt）
        # venue_codeからはtrack_typeが分からないので、後でレースJSONと結合する
        # ここでは省略

        # 年別
        year = rec['race_date'][:4]
        ys = j['year_stats'][year]
        ys['runs'] += 1
        if fp == 1:
            ys['wins'] += 1
        if fp <= 3:
            ys['top3'] += 1

        count += 1
        if count % 100_000 == 0:
            print(f"  ... {count:,} records processed")

    print(f"[SE] {count:,} records -> {len(jockeys):,} jockeys")
    return jockeys


def finalize_stats(jockeys: Dict[str, Dict]) -> List[Dict]:
    """勝率・連対率・複勝率を計算して最終形式に変換"""
    result = []
    for code, j in jockeys.items():
        runs = j['total_runs']
        entry = {
            'code': j['code'],
            'name': j['name'],
            'total_runs': runs,
            'wins': j['wins'],
            'top2': j['top2'],
            'top3': j['top3'],
            'win_rate': round(j['wins'] / runs, 4) if runs > 0 else 0,
            'top2_rate': round(j['top2'] / runs, 4) if runs > 0 else 0,
            'top3_rate': round(j['top3'] / runs, 4) if runs > 0 else 0,
            'venue_stats': {
                vc: {
                    'runs': vs['runs'],
                    'wins': vs['wins'],
                    'top3': vs['top3'],
                    'top3_rate': round(vs['top3'] / vs['runs'], 4) if vs['runs'] > 0 else 0,
                }
                for vc, vs in j['venue_stats'].items()
            },
            'year_stats': {
                y: {
                    'runs': ys['runs'],
                    'wins': ys['wins'],
                    'top3': ys['top3'],
                    'top3_rate': round(ys['top3'] / ys['runs'], 4) if ys['runs'] > 0 else 0,
                }
                for y, ys in sorted(j['year_stats'].items())
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
    parser = argparse.ArgumentParser(description='Build jockey master from SE_DATA')
    parser.add_argument('--years', default='2020-2026', help='Year range')
    args = parser.parse_args()

    years = parse_year_range(args.years)
    print(f"\n{'='*60}")
    print(f"  KeibaCICD v4 - Jockey Master Builder")
    print(f"  Years: {years[0]}-{years[-1]}")
    print(f"{'='*60}\n")

    t0 = time.time()

    jockeys = build_jockey_stats(years)
    result = finalize_stats(jockeys)

    # 保存
    out_path = config.masters_dir() / "jockeys.json"
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
    print(f"  Jockeys:   {len(result):,}")
    print(f"  Output:    {out_path}")
    print(f"  Elapsed:   {elapsed:.1f}s")
    print(f"\n  Top 5 by runs:")
    for j in top5:
        print(f"    {j['name']:>8} ({j['code']}): {j['total_runs']:>5} runs, "
              f"win={j['win_rate']:.1%}, top3={j['top3_rate']:.1%}")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
