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


def _empty_close_bucket():
    return {'close_wins': 0, 'close_seconds': 0}


def _distance_bucket(distance: int) -> str:
    """距離をバケット化: sprint/mile/intermediate/long/extended"""
    if distance <= 1400:
        return 'sprint'
    elif distance <= 1800:
        return 'mile'
    elif distance <= 2200:
        return 'intermediate'
    elif distance <= 2800:
        return 'long'
    else:
        return 'extended'


def build_close_finish_stats(years: List[int]) -> Dict[str, Dict]:
    """レースJSONから騎手別の接戦成績を集計

    接戦の定義: 1着と2着のタイム差 <= 0.1秒

    返却値: {jockey_code: {
        close_wins, close_seconds,
        by_year: {YYYY: {close_wins, close_seconds}},
        by_track: {turf/dirt: {close_wins, close_seconds}},
        by_distance: {sprint/mile/..: {close_wins, close_seconds}},
    }}
    """
    print(f"[Close] Scanning race JSONs for close finish stats...")

    close_stats = defaultdict(lambda: {
        'close_wins': 0, 'close_seconds': 0,
        'by_year': defaultdict(_empty_close_bucket),
        'by_track': defaultdict(_empty_close_bucket),
        'by_distance': defaultdict(_empty_close_bucket),
    })
    race_count = 0
    close_count = 0

    for year in years:
        year_dir = config.races_dir() / str(year)
        if not year_dir.exists():
            continue
        for json_file in year_dir.rglob("race_[0-9]*.json"):
            try:
                data = json.loads(json_file.read_text(encoding='utf-8'))
            except Exception:
                continue
            race_count += 1

            entries = data.get('entries', [])
            # 1着と2着を探す
            first = None
            second = None
            for e in entries:
                fp = e.get('finish_position', 0)
                if fp == 1:
                    first = e
                elif fp == 2:
                    second = e
            if not first or not second:
                continue

            # タイム差を計算
            t1 = _parse_time(first.get('time', ''))
            t2 = _parse_time(second.get('time', ''))
            if t1 is None or t2 is None:
                continue

            diff = abs(t2 - t1)
            if diff <= 0.1:
                close_count += 1

                # レース条件を取得
                race_year = data.get('race_date', '')[:4] or str(year)
                track_type = data.get('track_type', '')  # turf / dirt
                distance = data.get('distance', 0) or 0
                dist_bucket = _distance_bucket(distance)

                jc1 = first.get('jockey_code', '')
                jc2 = second.get('jockey_code', '')
                for jc, key in [(jc1, 'close_wins'), (jc2, 'close_seconds')]:
                    if not jc:
                        continue
                    cs = close_stats[jc]
                    cs[key] += 1
                    cs['by_year'][race_year][key] += 1
                    if track_type:
                        cs['by_track'][track_type][key] += 1
                    if distance > 0:
                        cs['by_distance'][dist_bucket][key] += 1

    print(f"  Scanned {race_count:,} races, "
          f"found {close_count:,} close finishes (<=0.1s), "
          f"{len(close_stats):,} jockeys with close data")
    return close_stats


def _parse_time(time_str: str):
    """走破タイム文字列を秒に変換 (例: '1:14.1' -> 74.1)"""
    if not time_str:
        return None
    try:
        if ':' in time_str:
            parts = time_str.split(':')
            return float(parts[0]) * 60 + float(parts[1])
        return float(time_str)
    except (ValueError, IndexError):
        return None


def _close_rate(bucket: dict) -> float:
    """接戦バケットから勝率を計算"""
    total = bucket.get('close_wins', 0) + bucket.get('close_seconds', 0)
    if total <= 0:
        return 0
    return round(bucket['close_wins'] / total, 4)


def _format_close_bucket(bucket: dict) -> dict:
    """接戦バケットをJSON出力用に整形"""
    cw = bucket.get('close_wins', 0)
    cs = bucket.get('close_seconds', 0)
    ct = cw + cs
    return {
        'close_wins': cw,
        'close_seconds': cs,
        'close_total': ct,
        'close_win_rate': round(cw / ct, 4) if ct > 0 else 0,
    }


def finalize_stats(jockeys: Dict[str, Dict],
                   close_stats: Dict[str, Dict] = None) -> List[Dict]:
    """勝率・連対率・複勝率を計算して最終形式に変換"""
    result = []
    for code, j in jockeys.items():
        runs = j['total_runs']

        # 接戦統計をマージ
        cs = (close_stats or {}).get(code, {})
        close_wins = cs.get('close_wins', 0)
        close_seconds = cs.get('close_seconds', 0)
        close_total = close_wins + close_seconds

        # 年度別接戦統計
        cs_by_year = cs.get('by_year', {})

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
            # v5.6: 接戦統計
            'close_wins': close_wins,
            'close_seconds': close_seconds,
            'close_total': close_total,
            'close_win_rate': round(close_wins / close_total, 4) if close_total > 0 else 0,
            # v5.7: 条件別接戦統計
            'close_by_track': {
                t: _format_close_bucket(b)
                for t, b in cs.get('by_track', {}).items()
            },
            'close_by_distance': {
                d: _format_close_bucket(b)
                for d, b in cs.get('by_distance', {}).items()
            },
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
                    # 年度別接戦統計をマージ
                    **_format_close_bucket(cs_by_year.get(y, {})),
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
    close_stats = build_close_finish_stats(years)
    result = finalize_stats(jockeys, close_stats)

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
              f"win={j['win_rate']:.1%}, top3={j['top3_rate']:.1%}, "
              f"close={j['close_wins']}/{j['close_total']}={j['close_win_rate']:.1%}")
    # 接戦統計サマリ
    has_close = [j for j in result if j['close_total'] >= 10]
    if has_close:
        avg_rate = sum(j['close_win_rate'] for j in has_close) / len(has_close)
        print(f"\n  Close finish stats (>= 10 samples): {len(has_close)} jockeys, "
              f"avg close_win_rate={avg_rate:.1%}")
        top3_close = sorted(has_close, key=lambda x: x['close_win_rate'], reverse=True)[:3]
        for j in top3_close:
            print(f"    {j['name']:>8}: {j['close_win_rate']:.1%} "
                  f"({j['close_wins']}/{j['close_total']})")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
