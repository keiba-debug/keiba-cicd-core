#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
レース特性基準値算出スクリプト (v2)

data3/racesのレースJSONからRPCIを集計し、
コース別（競馬場×芝/ダ×距離）の瞬発戦/持続戦の基準値を統計的に算出します。

v1ではSR_DATAバイナリを直接パースしていたが、
v2ではbuild_race_masterが生成したdata3/races JSONを利用する。

Usage:
    python -m analysis.race_type_standards
    python -m analysis.race_type_standards --since 2020
"""

import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from analysis.race_classifier import (
    classify_race_v2, compute_lap33, TREND_V2_TYPES, TREND_V2_LABELS, V2_TO_V1,
)

VENUE_NAMES = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟", "05": "東京",
    "06": "中山", "07": "中京", "08": "京都", "09": "阪神", "10": "小倉",
}

TRACK_TYPE_MAP = {"turf": "Turf", "dirt": "Dirt"}

BABA_MAP = {"良": "良", "稍重": "稍重以上", "稍": "稍重以上", "重": "稍重以上", "不良": "稍重以上"}

# v1分類タイプ（後方互換）
RACE_TREND_TYPES = ['sprint_finish', 'long_sprint', 'even_pace', 'front_loaded', 'front_loaded_strong']
RACE_TREND_LABELS = {
    'sprint_finish': '瞬発戦', 'long_sprint': 'ロンスパ戦',
    'even_pace': '平均ペース', 'front_loaded': 'H前傾', 'front_loaded_strong': 'H後傾',
}


def classify_distance(d: int) -> str:
    if d <= 1200:
        return "1200m-"
    elif d <= 1600:
        return "1400-1600m"
    elif d <= 2200:
        return "1800-2200m"
    return "2400m+"


def classify_runners(n: int) -> str:
    if n <= 8:
        return "少頭数(~8)"
    elif n <= 13:
        return "中頭数(9-13)"
    return "多頭数(14~)"


def scan_races(since_year: int) -> list:
    """data3/racesからペースデータを収集"""
    results = []
    races_dir = config.races_dir()

    if not races_dir.exists():
        print(f"  [ERROR] races dir not found: {races_dir}")
        return results

    print(f"  Scanning: {races_dir}")

    for year_dir in sorted(races_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        try:
            year_num = int(year_dir.name)
            if year_num < since_year:
                continue
        except ValueError:
            continue

        json_files = list(year_dir.rglob("race_[0-9]*.json"))
        year_count = 0

        for json_file in json_files:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                pace = data.get('pace')
                if not pace or not pace.get('rpci'):
                    continue

                rpci = pace['rpci']
                s3 = pace.get('s3')
                l3 = pace.get('l3')
                if s3 is None or l3 is None:
                    continue
                # validation
                if s3 < 30 or s3 > 50 or l3 < 30 or l3 > 50:
                    continue

                distance = data.get('distance', 0)
                if distance < 800 or distance > 4000:
                    continue

                track_type_raw = data.get('track_type', '')
                track_type = TRACK_TYPE_MAP.get(track_type_raw, '')
                if not track_type:
                    continue

                venue_name = data.get('venue_name', '')
                # Map venue_name (Japanese) to English for consistency with v1
                venue_en = None
                for code, name_jp in VENUE_NAMES.items():
                    if name_jp == venue_name:
                        venue_en = {
                            "札幌": "Sapporo", "函館": "Hakodate", "福島": "Fukushima",
                            "新潟": "Niigata", "東京": "Tokyo", "中山": "Nakayama",
                            "中京": "Chukyo", "京都": "Kyoto", "阪神": "Hanshin", "小倉": "Kokura",
                        }.get(name_jp)
                        break
                if not venue_en:
                    continue

                track_condition = data.get('track_condition', '')
                baba_condition = BABA_MAP.get(track_condition, '良')

                num_runners = data.get('num_runners', 0)
                date = data.get('date', '')
                year = int(date[:4]) if date else year_num

                results.append({
                    'race_id': data['race_id'],
                    'date': date,
                    'year': year,
                    'track_name': venue_en,
                    'distance': distance,
                    'track_type': track_type,
                    'track_type_raw': track_type_raw,  # 'turf' or 'dirt'
                    'track_condition': track_condition,  # 良/稍重/重/不良
                    'baba_condition': baba_condition,
                    'num_runners': num_runners,
                    's3': s3,
                    'l3': l3,
                    's4': pace.get('s4'),
                    'l4': pace.get('l4'),
                    'rpci': rpci,
                    'lap_times': pace.get('lap_times'),
                    'race_trend': '',  # v1, will be computed
                    'race_trend_v2': '',  # v2, will be computed
                    'lap33': None,  # will be computed
                })
                year_count += 1

            except (json.JSONDecodeError, KeyError, TypeError):
                continue

        print(f"  [{year_num}] {year_count} races with pace data")

    return results


def calculate_course_stats(records: list, current_year: int) -> Optional[dict]:
    if len(records) < 10:
        return None

    rpci_values = [r['rpci'] for r in records]
    mean = statistics.mean(rpci_values)
    stdev = statistics.stdev(rpci_values) if len(rpci_values) > 1 else 0
    median = statistics.median(rpci_values)

    weighted_sum = 0.0
    weight_total = 0.0
    for r in records:
        w = 2.0 if r['year'] >= current_year - 1 else 1.0
        weighted_sum += r['rpci'] * w
        weight_total += w
    w_mean = weighted_sum / weight_total if weight_total > 0 else mean

    return {
        "sample_count": len(rpci_values),
        "rpci": {
            "mean": round(mean, 2),
            "weighted_mean": round(w_mean, 2),
            "stdev": round(stdev, 2),
            "median": round(median, 2),
            "min": round(min(rpci_values), 2),
            "max": round(max(rpci_values), 2),
        },
        "thresholds": {
            "sustained": round(w_mean + stdev * 0.5, 2),
            "instantaneous": round(w_mean - stdev * 0.5, 2),
        },
    }


def calculate_runner_adjustments(records: list, dist_group_stats: dict) -> dict:
    groups = defaultdict(lambda: defaultdict(list))
    for r in records:
        dist_group = classify_distance(r['distance'])
        dist_key = f"{r['track_type']}_{dist_group}"
        runner_group = classify_runners(r['num_runners'])
        groups[dist_key][runner_group].append(r['rpci'])

    result = {}
    for dist_key, runner_groups in sorted(groups.items()):
        base_stats = dist_group_stats.get(dist_key)
        if not base_stats:
            continue
        base_mean = base_stats["rpci"]["mean"]
        adjustments = {}
        for runner_group in ["少頭数(~8)", "中頭数(9-13)", "多頭数(14~)"]:
            values = runner_groups.get(runner_group, [])
            if len(values) < 10:
                continue
            group_mean = statistics.mean(values)
            adjustments[runner_group] = {
                "rpci_offset": round(group_mean - base_mean, 2),
                "rpci_mean": round(group_mean, 2),
                "sample_count": len(values),
            }
        if adjustments:
            result[dist_key] = adjustments
    return result


def calculate_standards(records: list, since_year: int) -> dict:
    current_year = datetime.now().year
    years = list(range(since_year, current_year + 1))
    years_str = f"{min(years)}-{max(years)}"

    standards = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "source": "data3/races (JRA-VAN SR_DATA via build_race_master)",
            "years": years_str,
            "years_list": years,
            "version": "5.0",
        },
        "by_distance_group": {},
        "courses": {},
        "by_baba": {},
        "by_distance_group_baba": {},
        "runner_adjustments": {},
        "similar_courses": {},
        "course_l3_average": {},
        "course_lap33_average": {},
        "race_trend_distribution": {},
        "race_trend_v2_distribution": {},
    }

    by_course = defaultdict(list)
    by_distance = defaultdict(list)
    by_baba = defaultdict(list)
    by_dist_baba = defaultdict(list)

    for r in records:
        course_key = f"{r['track_name']}_{r['track_type']}_{r['distance']}m"
        by_course[course_key].append(r)
        dist_group = classify_distance(r['distance'])
        dist_key = f"{r['track_type']}_{dist_group}"
        by_distance[dist_key].append(r)
        baba_key = f"{course_key}_{r['baba_condition']}"
        by_baba[baba_key].append(r)
        dist_baba_key = f"{dist_key}_{r['baba_condition']}"
        by_dist_baba[dist_baba_key].append(r)

    # Distance group stats
    print("\n[STEP 2a] Distance group statistics...")
    for dist_key in sorted(by_distance.keys()):
        stats = calculate_course_stats(by_distance[dist_key], current_year)
        if stats:
            standards["by_distance_group"][dist_key] = stats
            print(f"  {dist_key}: {stats['sample_count']} races, RPCI={stats['rpci']['mean']:.2f}")

    # Course stats
    print("\n[STEP 2b] Course statistics...")
    course_stats = {}
    for course_key in sorted(by_course.keys()):
        stats = calculate_course_stats(by_course[course_key], current_year)
        if stats:
            course_stats[course_key] = stats
            standards["courses"][course_key] = stats
    print(f"  Total courses: {len(course_stats)}")

    # Baba condition stats
    print("\n[STEP 2c] Baba condition statistics...")
    baba_count = 0
    for baba_key in sorted(by_baba.keys()):
        stats = calculate_course_stats(by_baba[baba_key], current_year)
        if stats:
            standards["by_baba"][baba_key] = stats
            baba_count += 1
    print(f"  Total: {baba_count}")

    # Distance x baba
    print("\n[STEP 2d] Distance group x baba statistics...")
    for dist_baba_key in sorted(by_dist_baba.keys()):
        stats = calculate_course_stats(by_dist_baba[dist_baba_key], current_year)
        if stats:
            standards["by_distance_group_baba"][dist_baba_key] = stats

    # Runner adjustments
    print("\n[STEP 2e] Runner count adjustments...")
    standards["runner_adjustments"] = calculate_runner_adjustments(records, standards["by_distance_group"])

    # Similar courses
    print("\n[STEP 2f] Similar courses...")
    courses_list = list(course_stats.keys())
    similar = defaultdict(list)
    for i, c1 in enumerate(courses_list):
        m1 = course_stats[c1]["rpci"]["mean"]
        for c2 in courses_list[i+1:]:
            m2 = course_stats[c2]["rpci"]["mean"]
            if abs(m1 - m2) <= 0.5:
                similar[c1].append(c2)
                similar[c2].append(c1)
    standards["similar_courses"] = dict(similar)

    # Course L3 average
    print("\n[STEP 2g] Course L3 averages...")
    course_l3_avg = {}
    for course_key, recs in by_course.items():
        l3_vals = [r['l3'] for r in recs if r['l3']]
        if l3_vals:
            course_l3_avg[course_key] = round(statistics.mean(l3_vals), 2)
    standards["course_l3_average"] = course_l3_avg
    print(f"  Courses: {len(course_l3_avg)}")

    # Course 33ラップ average
    print("\n[STEP 2g2] Course 33ラップ averages...")
    course_lap33_avg = {}
    for course_key, recs in by_course.items():
        lap33_vals = []
        for r in recs:
            if r.get('lap_times'):
                v = compute_lap33(r['lap_times'], r['distance'])
                if v is not None:
                    lap33_vals.append(v)
        if len(lap33_vals) >= 10:
            course_lap33_avg[course_key] = {
                "mean": round(statistics.mean(lap33_vals), 2),
                "stdev": round(statistics.stdev(lap33_vals), 2) if len(lap33_vals) > 1 else 0,
                "median": round(statistics.median(lap33_vals), 2),
                "sample_count": len(lap33_vals),
            }
    standards["course_lap33_average"] = course_lap33_avg
    print(f"  Courses with lap33: {len(course_lap33_avg)}")

    # Race trend classification (v1 + v2)
    print("\n[STEP 2h] Race trend classification (v1 + v2)...")
    for r in records:
        course_key = f"{r['track_name']}_{r['track_type']}_{r['distance']}m"
        avg_l3 = course_l3_avg.get(course_key)
        avg_rpci = None
        if course_key in course_stats:
            avg_rpci = course_stats[course_key]['rpci']['mean']
        avg_lap33 = None
        if course_key in course_lap33_avg:
            avg_lap33 = course_lap33_avg[course_key]['mean']

        # v2分類（race_classifier.py統一ロジック）
        v2_result = classify_race_v2(
            rpci=r['rpci'], l3=r['l3'], l4=r['l4'],
            s3=r['s3'], s4=r['s4'],
            distance=r['distance'], track_type=r['track_type_raw'],
            track_condition=r['track_condition'],
            lap_times=r.get('lap_times'),
            course_avg_l3=avg_l3,
            course_avg_rpci=avg_rpci,
            course_avg_lap33=avg_lap33,
        )
        r['race_trend'] = v2_result['trend_v1']  # v1後方互換
        r['race_trend_v2'] = v2_result['trend_v2']
        r['lap33'] = v2_result['lap33']
        r['trend_detail'] = v2_result.get('trend_detail')

    # v1 trend distribution
    trend_dist = defaultdict(lambda: defaultdict(int))
    for r in records:
        course_key = f"{r['track_name']}_{r['track_type']}_{r['distance']}m"
        trend_dist[course_key][r['race_trend']] += 1

    for course_key in sorted(trend_dist.keys()):
        counts = trend_dist[course_key]
        total = sum(counts.values())
        dist_entry = {}
        for t in RACE_TREND_TYPES:
            c = counts.get(t, 0)
            dist_entry[t] = {"count": c, "pct": round(c / total * 100, 1) if total > 0 else 0}
        standards["race_trend_distribution"][course_key] = dist_entry

    # v2 trend distribution
    trend_v2_dist = defaultdict(lambda: defaultdict(int))
    for r in records:
        course_key = f"{r['track_name']}_{r['track_type']}_{r['distance']}m"
        trend_v2_dist[course_key][r['race_trend_v2']] += 1

    for course_key in sorted(trend_v2_dist.keys()):
        counts = trend_v2_dist[course_key]
        total = sum(counts.values())
        dist_entry = {}
        for t in TREND_V2_TYPES:
            c = counts.get(t, 0)
            dist_entry[t] = {"count": c, "pct": round(c / total * 100, 1) if total > 0 else 0}
        standards["race_trend_v2_distribution"][course_key] = dist_entry

    # Summary
    print("\n  --- v1 distribution ---")
    global_v1 = defaultdict(int)
    for r in records:
        global_v1[r['race_trend']] += 1
    total_all = len(records)
    for t in RACE_TREND_TYPES:
        c = global_v1.get(t, 0)
        pct = c / total_all * 100 if total_all > 0 else 0
        print(f"  {RACE_TREND_LABELS.get(t, t):12s}: {c:,} ({pct:.1f}%)")

    print("\n  --- v2 distribution ---")
    global_v2 = defaultdict(int)
    for r in records:
        global_v2[r['race_trend_v2']] += 1
    for t in TREND_V2_TYPES:
        c = global_v2.get(t, 0)
        pct = c / total_all * 100 if total_all > 0 else 0
        print(f"  {TREND_V2_LABELS.get(t, t):12s}: {c:,} ({pct:.1f}%)")

    return standards


def main():
    parser = argparse.ArgumentParser(description="RPCI Standards Calculator (v2)")
    parser.add_argument("--since", type=int, default=2020, help="Start year (default: 2020)")
    output_default = str(config.data_root() / "analysis" / "race_type_standards.json")
    parser.add_argument("--output", type=str, default=output_default)
    args = parser.parse_args()

    print("=" * 70)
    print("RPCI Standards Calculator (v2)")
    print("=" * 70)
    print(f"Data source: {config.races_dir()}")
    print(f"Since: {args.since}")
    print(f"Output: {args.output}")
    print()

    # Scan
    print("[STEP 1] Scanning race JSONs...")
    records = scan_races(args.since)
    print(f"\n  Total: {len(records):,} races with pace data")

    if not records:
        print("[ERROR] No valid data found")
        return 1

    baba_good = sum(1 for r in records if r['baba_condition'] == '良')
    print(f"  馬場: 良={baba_good:,} / 稍重以上={len(records)-baba_good:,}")

    # Calculate
    standards = calculate_standards(records, args.since)

    # Save standards
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 旧バージョンをアーカイブ
    if output_path.exists():
        from core.versioning import archive_flat
        try:
            old = json.loads(output_path.read_text(encoding='utf-8'))
            old_ver = old.get("metadata", {}).get("version", "unknown")
            archive_flat(output_path.parent, old_ver, output_path.name,
                         metadata={"created_at": old.get("metadata", {}).get("created_at", "")})
        except Exception as e:
            print(f"  [versioning] Warning: {e}")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(standards, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 70}")
    print(f"[OK] Standards saved: {output_path}")
    print(f"  Courses: {len(standards['courses'])}")

    # Save trend index
    trend_index = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "source": "data3/races",
            "years": standards["metadata"]["years"],
            "version": "5.0",
            "description": "レース傾向インデックス（v1+v2分類）",
        },
        "races": {},
    }
    for r in records:
        entry = {
            "trend": r['race_trend'],        # v1後方互換
            "trend_v2": r['race_trend_v2'],   # v2分類
            "rpci": r['rpci'],
            "s3": r['s3'],
            "l3": r['l3'],
        }
        if r.get('s4') is not None:
            entry["s4"] = r['s4']
        if r.get('l4') is not None:
            entry["l4"] = r['l4']
        if r.get('lap33') is not None:
            entry["lap33"] = r['lap33']
        trend_index["races"][r['race_id']] = entry

    trend_path = output_path.parent / "race_trend_index.json"
    with open(trend_path, 'w', encoding='utf-8') as f:
        json.dump(trend_index, f, ensure_ascii=False, indent=2)

    print(f"[OK] Trend index saved: {trend_path}")
    print(f"  Total races: {len(trend_index['races']):,}")
    return 0


if __name__ == "__main__":
    exit(main())
