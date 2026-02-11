#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
距離別RPCI分析スクリプト

距離グループ別にRPCIが異なるか検証する
"""

import os
import statistics
from collections import defaultdict
from pathlib import Path


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
        env_candidates = [
            Path(__file__).resolve().parents[2] / "KeibaCICD.keibabook" / ".env",
            Path(__file__).resolve().parents[1] / ".env",
        ]
        for env_path in env_candidates:
            if env_path.exists():
                load_dotenv(env_path)
                break
    except ImportError:
        pass


_load_dotenv_if_available()

JV_DATA_ROOT = Path(os.getenv('JV_DATA_ROOT_DIR', 'C:/TFJV'))
SE_DATA_PATH = JV_DATA_ROOT / 'SE_DATA'

TRACK_CODES = {
    '01': 'Sapporo', '02': 'Hakodate', '03': 'Fukushima', '04': 'Niigata', 
    '05': 'Tokyo', '06': 'Nakayama', '07': 'Chukyo', '08': 'Kyoto', 
    '09': 'Hanshin', '10': 'Kokura'
}

SR_RECORD_LEN = 1272


def decode_sjis(d):
    return d.decode('shift_jis', errors='replace').strip()


def parse_time(s):
    if not s or not s.isdigit() or len(s) != 3:
        return None
    return int(s[:2]) + int(s[2]) / 10


def classify_distance(d):
    if d <= 1200:
        return 'D1: 1200m or less'
    elif d <= 1600:
        return 'D2: 1400-1600m'
    elif d <= 2200:
        return 'D3: 1800-2200m'
    else:
        return 'D4: 2400m+'


def main():
    results = defaultdict(list)
    results_by_track_dist = defaultdict(list)
    
    for year in [2024, 2025]:
        year_dir = SE_DATA_PATH / str(year)
        if not year_dir.exists():
            print(f"  [SKIP] {year}")
            continue
        
        sr_files = list(year_dir.glob('SR*.DAT'))
        print(f"  [{year}] {len(sr_files)} files")
        
        for sr_file in sr_files:
            with open(sr_file, 'rb') as f:
                data = f.read()
            
            for i in range(len(data) // SR_RECORD_LEN):
                offset = i * SR_RECORD_LEN
                record = data[offset:offset + SR_RECORD_LEN]
                if len(record) < SR_RECORD_LEN:
                    break
                if decode_sjis(record[0:2]) != 'RA':
                    continue
                if decode_sjis(record[2:3]) != '7':
                    continue
                
                # Distance (offset 698, 4bytes -> Python: 697:701)
                kyori_str = decode_sjis(record[697:701])
                if not kyori_str.isdigit():
                    continue
                distance = int(kyori_str)
                if distance < 800 or distance > 4000:
                    continue
                
                # Track type (offset 706, 2bytes -> Python: 705:707)
                track_cd = decode_sjis(record[705:707])
                if track_cd.startswith('1'):
                    track_type = 'Turf'
                elif track_cd.startswith('2'):
                    track_type = 'Dirt'
                else:
                    continue
                
                # Venue
                jyo_cd = decode_sjis(record[19:21])
                track_name = TRACK_CODES.get(jyo_cd, '')
                if not track_name:
                    continue
                
                # First 3F / Last 3F
                first_3f = parse_time(decode_sjis(record[969:972]))
                last_3f = parse_time(decode_sjis(record[975:978]))
                
                if first_3f and last_3f and 30 < first_3f < 50 and 30 < last_3f < 50:
                    rpci = (first_3f / last_3f) * 50
                    dist_group = classify_distance(distance)
                    
                    # By distance group only
                    results[dist_group].append(rpci)
                    
                    # By track x distance
                    key = f'{track_name}_{track_type}_{dist_group}'
                    results_by_track_dist[key].append(rpci)
    
    print()
    print('=' * 70)
    print('RPCI Analysis by Distance Group (2024-2025)')
    print('=' * 70)
    print()
    print('Overall by Distance:')
    print('-' * 70)
    print(f"{'Distance Group':<25} {'Count':>8} {'Mean':>8} {'StDev':>8} {'Min':>8} {'Max':>8}")
    print('-' * 70)
    
    for dist_group in ['D1: 1200m or less', 'D2: 1400-1600m', 'D3: 1800-2200m', 'D4: 2400m+']:
        if dist_group in results and len(results[dist_group]) >= 20:
            vals = results[dist_group]
            mean = statistics.mean(vals)
            stdev = statistics.stdev(vals)
            print(f'{dist_group:<25} {len(vals):>8} {mean:>8.2f} {stdev:>8.2f} {min(vals):>8.2f} {max(vals):>8.2f}')
    
    print()
    print('By Track Type x Distance:')
    print('-' * 70)
    
    # Group by track type and distance
    turf_by_dist = defaultdict(list)
    dirt_by_dist = defaultdict(list)
    
    for key, vals in results_by_track_dist.items():
        parts = key.split('_')
        if len(parts) == 3:
            track_type = parts[1]
            dist_group = parts[2]
            if track_type == 'Turf':
                turf_by_dist[dist_group].extend(vals)
            else:
                dirt_by_dist[dist_group].extend(vals)
    
    print(f"{'Category':<25} {'Count':>8} {'Mean':>8} {'StDev':>8}")
    print('-' * 70)
    
    for dist_group in ['D1: 1200m or less', 'D2: 1400-1600m', 'D3: 1800-2200m', 'D4: 2400m+']:
        if dist_group in turf_by_dist and len(turf_by_dist[dist_group]) >= 20:
            vals = turf_by_dist[dist_group]
            mean = statistics.mean(vals)
            stdev = statistics.stdev(vals)
            print(f'Turf {dist_group:<20} {len(vals):>8} {mean:>8.2f} {stdev:>8.2f}')
    
    print()
    for dist_group in ['D1: 1200m or less', 'D2: 1400-1600m', 'D3: 1800-2200m', 'D4: 2400m+']:
        if dist_group in dirt_by_dist and len(dirt_by_dist[dist_group]) >= 20:
            vals = dirt_by_dist[dist_group]
            mean = statistics.mean(vals)
            stdev = statistics.stdev(vals)
            print(f'Dirt {dist_group:<20} {len(vals):>8} {mean:>8.2f} {stdev:>8.2f}')
    
    print()
    print('Top 20 Course x Distance combinations:')
    print('-' * 70)
    print(f"{'Course':<35} {'Count':>6} {'Mean':>8} {'StDev':>8}")
    print('-' * 70)
    
    sorted_results = sorted(results_by_track_dist.items(), key=lambda x: -len(x[1]))
    for key, vals in sorted_results[:20]:
        if len(vals) >= 30:
            mean = statistics.mean(vals)
            stdev = statistics.stdev(vals)
            print(f'{key:<35} {len(vals):>6} {mean:>8.2f} {stdev:>8.2f}')
    
    print()
    print('=' * 70)
    print('Conclusion:')
    print('=' * 70)
    
    # Compare distance groups
    all_means = {}
    for dist_group in ['D1: 1200m or less', 'D2: 1400-1600m', 'D3: 1800-2200m', 'D4: 2400m+']:
        if dist_group in results and len(results[dist_group]) >= 20:
            all_means[dist_group] = statistics.mean(results[dist_group])
    
    if all_means:
        max_diff = max(all_means.values()) - min(all_means.values())
        print(f'Max difference between distance groups: {max_diff:.2f}')
        print(f'Recommendation: {"YES - separate by distance" if max_diff > 2 else "NO - distance grouping not critical"}')


if __name__ == '__main__':
    print('=' * 70)
    print('RPCI Analysis by Distance')
    print('=' * 70)
    print(f'Data path: {JV_DATA_ROOT}')
    print()
    main()
