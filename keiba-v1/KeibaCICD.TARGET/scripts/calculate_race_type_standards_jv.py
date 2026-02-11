#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JRA-VANデータからレース特性基準値を算出するスクリプト（v3）

SR_DATA（レース毎成績）から前3F/後3F/前4F/後4FでRPCIを計算し、
コース別（競馬場×芝/ダート×距離）の瞬発戦/持続戦の基準値を統計的に算出します。

v3改善点:
  - S4(前4F)/L4(後4F)パース追加
  - 5段階レース傾向分類（瞬発/ロンスパ/平均/H前傾/H後傾）
  - コース別L3平均・傾向分布を出力

v2改善点:
  A. 馬場状態別分離（良 vs 稍重以上）
  D. 頭数別補正（少/中/多頭数でRPCI偏差を算出）
  B. 年度重み付け（直近2年は×2倍）

Usage:
    python calculate_race_type_standards_jv.py
    python calculate_race_type_standards_jv.py --years 2024,2025
    python calculate_race_type_standards_jv.py --output data/race_type_standards.json
"""

import argparse
import json
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# UTF-8出力
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# 共通設定モジュールをインポート
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.config import get_jv_data_root, get_jv_se_data_path, get_target_data_dir

# JRA-VAN data path
JV_DATA_ROOT = get_jv_data_root()
SE_DATA_PATH = get_jv_se_data_path()

# Track codes
TRACK_CODES = {
    "01": "Sapporo",
    "02": "Hakodate",
    "03": "Fukushima",
    "04": "Niigata",
    "05": "Tokyo",
    "06": "Nakayama",
    "07": "Chukyo",
    "08": "Kyoto",
    "09": "Hanshin",
    "10": "Kokura",
}

TRACK_NAMES_JP = {
    "Sapporo": "札幌",
    "Hakodate": "函館",
    "Fukushima": "福島",
    "Niigata": "新潟",
    "Tokyo": "東京",
    "Nakayama": "中山",
    "Chukyo": "中京",
    "Kyoto": "京都",
    "Hanshin": "阪神",
    "Kokura": "小倉",
}

SR_RECORD_LEN = 1272


@dataclass
class RaceInfo:
    """Race information data"""
    race_id: str
    date: str
    year: int
    track_code: str
    track_name: str
    distance: int
    track_type: str       # Turf/Dirt
    baba_condition: str   # "良" / "稍重以上"
    num_runners: int      # 出走頭数
    first_3f_seconds: float
    last_3f_seconds: float
    rpci: float
    first_4f_seconds: Optional[float] = None  # S4
    last_4f_seconds: Optional[float] = None   # L4
    race_trend: str = ''                        # 5段階分類結果


# レース傾向分類の定義
RACE_TREND_TYPES = ['sprint_finish', 'long_sprint', 'even_pace', 'front_loaded', 'front_loaded_strong']

RACE_TREND_LABELS = {
    'sprint_finish': '瞬発戦',
    'long_sprint': 'ロンスパ戦',
    'even_pace': '平均ペース',
    'front_loaded': 'H前傾',
    'front_loaded_strong': 'H後傾',
}


def classify_race_trend(
    rpci: float,
    s3: float,
    l3: float,
    s4: Optional[float],
    l4: Optional[float],
    course_avg_l3: Optional[float] = None,
) -> str:
    """
    レースを5段階に分類する。

    瞬発戦: RPCI>=51, 最後3Fで一気加速
    ロンスパ戦: RPCI>=50, 残り4F目も速い
    平均ペース: 48 < RPCI < 51
    H前傾: RPCI<=48, L3遅め (前半消耗)
    H後傾: RPCI<=48, L3速い (ハイペースでも脚を使える)
    """
    # ロンスパ判定: L4-L3 (=残り4F目の単独ハロン) が L3平均ハロンの1.05倍以内
    is_long_sprint = False
    if l4 is not None and l3 is not None and l4 > l3:
        fourth_furlong_time = l4 - l3  # 残り4F目の単独タイム
        avg_l3_per_furlong = l3 / 3    # L3の平均ハロンタイム
        if fourth_furlong_time <= avg_l3_per_furlong * 1.05:
            is_long_sprint = True

    if rpci >= 50 and is_long_sprint:
        return 'long_sprint'

    if rpci >= 51:
        return 'sprint_finish'

    if rpci > 48:
        return 'even_pace'

    # Hペース領域 (RPCI <= 48)
    # L3がコース平均以下(速い)なら後傾
    if course_avg_l3 is not None and l3 is not None:
        if l3 <= course_avg_l3 * 1.03:
            return 'front_loaded_strong'

    return 'front_loaded'


def decode_sjis(data: bytes) -> str:
    """Decode Shift-JIS and trim"""
    return data.decode('shift_jis', errors='replace').strip().replace('\u3000', '').replace('@', '')


def parse_time_to_seconds(time_str: str) -> Optional[float]:
    """Parse time string to seconds"""
    if not time_str or not time_str.strip():
        return None

    time_str = time_str.strip()
    if not time_str.isdigit():
        return None

    try:
        if len(time_str) == 3:
            # SST format (e.g., "334" = 33.4 seconds)
            seconds = int(time_str[:2])
            tenths = int(time_str[2])
            return seconds + tenths / 10
        elif len(time_str) == 4:
            # MMST format (e.g., "1234" = 1:23.4)
            minutes = int(time_str[0])
            seconds = int(time_str[1:3])
            tenths = int(time_str[3])
            return minutes * 60 + seconds + tenths / 10
        else:
            return None
    except (ValueError, IndexError):
        return None


def calculate_rpci(first_3f: float, last_3f: float) -> Optional[float]:
    """Calculate RPCI = (First 3F / Last 3F) x 50"""
    if first_3f is None or last_3f is None:
        return None
    if last_3f <= 0 or first_3f <= 0:
        return None

    rpci = (first_3f / last_3f) * 50
    return round(rpci, 2)


def classify_distance(d: int) -> str:
    """Classify distance into groups"""
    if d <= 1200:
        return "1200m-"
    elif d <= 1600:
        return "1400-1600m"
    elif d <= 2200:
        return "1800-2200m"
    else:
        return "2400m+"


def classify_runners(n: int) -> str:
    """Classify number of runners into groups"""
    if n <= 8:
        return "少頭数(~8)"
    elif n <= 13:
        return "中頭数(9-13)"
    else:
        return "多頭数(14~)"


def parse_sr_record(data: bytes, offset: int = 0) -> Optional[RaceInfo]:
    """Parse SR (race results) record"""
    try:
        record = data[offset:offset + SR_RECORD_LEN]

        if len(record) < SR_RECORD_LEN:
            return None

        # Record type check
        record_type = decode_sjis(record[0:2])
        if record_type != "RA":
            return None

        # Data type ("7" = confirmed data)
        data_kubun = decode_sjis(record[2:3])
        if data_kubun != "7":
            return None

        # RACE_ID
        year_str = decode_sjis(record[11:15])
        month_day = decode_sjis(record[15:19])
        jyo_cd = decode_sjis(record[19:21])
        kaiji = decode_sjis(record[21:23])
        nichiji = decode_sjis(record[23:25])
        race_num = decode_sjis(record[25:27])

        if not year_str.isdigit():
            return None
        year = int(year_str)

        # race_idはTypeScript側(SE_DATA reader)と同じ形式: year+kai+venue+nichi+raceNum
        race_id = f"{year_str}{kaiji}{jyo_cd}{nichiji}{race_num}"

        # Distance (C# offset 698, 4bytes -> Python: 697:701)
        kyori_str = decode_sjis(record[697:701])
        if not kyori_str.isdigit():
            return None
        distance = int(kyori_str)
        if distance < 800 or distance > 4000:
            return None

        # Track type (C# offset 706, 2bytes -> Python: 705:707)
        track_cd = decode_sjis(record[705:707])
        if track_cd.startswith("1"):
            track_type = "Turf"
        elif track_cd.startswith("2"):
            track_type = "Dirt"
        else:
            return None

        # 出走頭数 (C# offset 884, 2bytes -> Python: 883:885)
        syusso_str = decode_sjis(record[883:885])
        num_runners = int(syusso_str) if syusso_str.isdigit() else 0

        # 馬場状態 (C# TenkoBaba = MidB2B(888, 3) -> Python: 887:890)
        # sub[1]=TenkoCD(887), sub[2]=SibaBabaCD(888), sub[3]=DirtBabaCD(889)
        siba_baba_cd = decode_sjis(record[888:889])  # 1=良,2=稍,3=重,4=不
        dirt_baba_cd = decode_sjis(record[889:890])  # 1=良,2=稍,3=重,4=不

        baba_cd = siba_baba_cd if track_type == "Turf" else dirt_baba_cd
        baba_condition = "良" if baba_cd == "1" else "稍重以上"

        # First 3F (C# offset 970, 3bytes -> Python: 969:972)
        first_3f_str = decode_sjis(record[969:972])
        first_3f_seconds = parse_time_to_seconds(first_3f_str)

        # First 4F (C# offset 973, 3bytes -> Python: 972:975)
        first_4f_str = decode_sjis(record[972:975])
        first_4f_seconds = parse_time_to_seconds(first_4f_str)

        # Last 3F (C# offset 976, 3bytes -> Python: 975:978)
        last_3f_str = decode_sjis(record[975:978])
        last_3f_seconds = parse_time_to_seconds(last_3f_str)

        # Last 4F (C# offset 979, 3bytes -> Python: 978:981)
        last_4f_str = decode_sjis(record[978:981])
        last_4f_seconds = parse_time_to_seconds(last_4f_str)

        if first_3f_seconds is None or last_3f_seconds is None:
            return None

        # Validation (3F time should be 30-50 seconds)
        if first_3f_seconds < 30 or first_3f_seconds > 50:
            return None
        if last_3f_seconds < 30 or last_3f_seconds > 50:
            return None

        # 4F validation (4F time should be 40-70 seconds)
        if first_4f_seconds is not None and (first_4f_seconds < 40 or first_4f_seconds > 70):
            first_4f_seconds = None
        if last_4f_seconds is not None and (last_4f_seconds < 40 or last_4f_seconds > 70):
            last_4f_seconds = None

        rpci = calculate_rpci(first_3f_seconds, last_3f_seconds)
        if rpci is None:
            return None

        track_name = TRACK_CODES.get(jyo_cd, "Unknown")
        date_str = f"{year_str}-{month_day[:2]}-{month_day[2:]}"

        return RaceInfo(
            race_id=race_id,
            date=date_str,
            year=year,
            track_code=jyo_cd,
            track_name=track_name,
            distance=distance,
            track_type=track_type,
            baba_condition=baba_condition,
            num_runners=num_runners,
            first_3f_seconds=first_3f_seconds,
            last_3f_seconds=last_3f_seconds,
            rpci=rpci,
            first_4f_seconds=first_4f_seconds,
            last_4f_seconds=last_4f_seconds,
        )
    except Exception:
        return None


def scan_sr_files(years: List[int]) -> List[RaceInfo]:
    """Scan SR_DATA files and return all valid race records"""
    all_records: List[RaceInfo] = []
    total_records = 0

    for year in years:
        year_dir = SE_DATA_PATH / str(year)
        if not year_dir.exists():
            print(f"  [SKIP] {year}")
            continue

        sr_files = list(year_dir.glob("SR*.DAT"))
        print(f"  [{year}] {len(sr_files)} files")

        for sr_file in sr_files:
            try:
                with open(sr_file, "rb") as f:
                    data = f.read()

                file_size = len(data)
                estimated_records = file_size // SR_RECORD_LEN

                for i in range(estimated_records + 1):
                    offset = i * SR_RECORD_LEN
                    if offset + SR_RECORD_LEN > file_size:
                        break

                    result = parse_sr_record(data, offset)
                    total_records += 1

                    if result:
                        all_records.append(result)

            except Exception as e:
                print(f"  [ERROR] {sr_file}: {e}")

    print(f"\n  Total records: {total_records:,}")
    print(f"  Valid records: {len(all_records):,}")

    return all_records


def calculate_course_stats(race_infos: List[RaceInfo], current_year: int) -> Optional[Dict]:
    """Calculate statistics for a course with weighted mean"""
    if len(race_infos) < 10:
        return None

    rpci_values = [r.rpci for r in race_infos]

    mean = statistics.mean(rpci_values)
    stdev = statistics.stdev(rpci_values) if len(rpci_values) > 1 else 0
    median = statistics.median(rpci_values)

    # 年度重み付け平均（直近2年は×2倍）
    weighted_sum = 0.0
    weight_total = 0.0
    for r in race_infos:
        w = 2.0 if r.year >= current_year - 1 else 1.0
        weighted_sum += r.rpci * w
        weight_total += w
    w_mean = weighted_sum / weight_total if weight_total > 0 else mean

    # Thresholds（weighted_meanベース）
    instantaneous = w_mean + stdev * 0.5
    sustained = w_mean - stdev * 0.5

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
            "instantaneous": round(instantaneous, 2),
            "sustained": round(sustained, 2),
        },
    }


def find_similar_courses(course_stats: Dict, threshold: float = 1.0) -> Dict[str, List[str]]:
    """Find similar courses based on RPCI mean"""
    similar = defaultdict(list)

    courses = list(course_stats.keys())
    for i, course1 in enumerate(courses):
        stats1 = course_stats[course1]
        if not stats1:
            continue
        mean1 = stats1["rpci"]["mean"]

        for course2 in courses[i+1:]:
            stats2 = course_stats[course2]
            if not stats2:
                continue
            mean2 = stats2["rpci"]["mean"]

            if abs(mean1 - mean2) <= threshold:
                similar[course1].append(course2)
                similar[course2].append(course1)

    return dict(similar)


def calculate_runner_adjustments(
    all_records: List[RaceInfo],
    dist_group_stats: Dict[str, Dict],
) -> Dict[str, Dict]:
    """
    頭数帯別のRPCIオフセットを距離グループごとに算出

    Returns:
        {
            "Turf_1800-2200m": {
                "少頭数(~8)":  {"rpci_offset": +1.2, "sample_count": 450},
                ...
            }
        }
    """
    # 距離グループ×頭数帯でグルーピング
    groups: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))

    for r in all_records:
        dist_group = classify_distance(r.distance)
        dist_key = f"{r.track_type}_{dist_group}"
        runner_group = classify_runners(r.num_runners)
        groups[dist_key][runner_group].append(r.rpci)

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


def calculate_standards(all_records: List[RaceInfo], years: List[int]) -> Dict:
    """Calculate standards for all courses"""
    current_year = max(years)
    years_str = f"{min(years)}-{max(years)}" if len(years) > 1 else str(years[0])

    standards = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "source": "JRA-VAN SR_DATA",
            "years": years_str,
            "years_list": years,
            "description": f"RPCI standards by course [{years_str}] (v3: 5段階傾向分類/馬場別/頭数補正/年度重み)",
            "calculation": "RPCI = (First 3F / Last 3F) x 50",
            "version": "3.0",
        },
        "by_distance_group": {},
        "courses": {},
        "by_baba": {},
        "by_distance_group_baba": {},
        "runner_adjustments": {},
        "similar_courses": {},
        "course_l3_average": {},
        "race_trend_distribution": {},
    }

    # --- グルーピング ---
    by_course: Dict[str, List[RaceInfo]] = defaultdict(list)
    by_distance: Dict[str, List[RaceInfo]] = defaultdict(list)
    by_baba: Dict[str, List[RaceInfo]] = defaultdict(list)
    by_dist_baba: Dict[str, List[RaceInfo]] = defaultdict(list)

    for r in all_records:
        course_key = f"{r.track_name}_{r.track_type}_{r.distance}m"
        by_course[course_key].append(r)

        dist_group = classify_distance(r.distance)
        dist_key = f"{r.track_type}_{dist_group}"
        by_distance[dist_key].append(r)

        # 馬場別
        baba_key = f"{course_key}_{r.baba_condition}"
        by_baba[baba_key].append(r)

        dist_baba_key = f"{dist_key}_{r.baba_condition}"
        by_dist_baba[dist_baba_key].append(r)

    # --- [STEP 2a] Distance group stats ---
    print("\n[STEP 2a] Distance group statistics...")
    for dist_key in sorted(by_distance.keys()):
        infos = by_distance[dist_key]
        stats = calculate_course_stats(infos, current_year)
        if stats:
            standards["by_distance_group"][dist_key] = stats
            m = stats['rpci']['mean']
            wm = stats['rpci']['weighted_mean']
            print(f"  [OK] {dist_key}: {stats['sample_count']} races, RPCI={m:.2f} (weighted={wm:.2f})")

    # --- [STEP 2b] Course stats ---
    print("\n[STEP 2b] Course statistics...")
    course_stats = {}
    for course_key in sorted(by_course.keys()):
        infos = by_course[course_key]
        stats = calculate_course_stats(infos, current_year)
        if stats:
            course_stats[course_key] = stats
            standards["courses"][course_key] = stats
    print(f"  Total courses: {len(course_stats)}")

    # --- [STEP 2c] 馬場状態別コース統計 ---
    print("\n[STEP 2c] Baba condition statistics...")
    baba_count = 0
    for baba_key in sorted(by_baba.keys()):
        infos = by_baba[baba_key]
        stats = calculate_course_stats(infos, current_year)
        if stats:
            standards["by_baba"][baba_key] = stats
            baba_count += 1
    print(f"  Total baba entries: {baba_count}")

    # --- [STEP 2d] 馬場状態別距離グループ統計 ---
    print("\n[STEP 2d] Distance group x baba statistics...")
    for dist_baba_key in sorted(by_dist_baba.keys()):
        infos = by_dist_baba[dist_baba_key]
        stats = calculate_course_stats(infos, current_year)
        if stats:
            standards["by_distance_group_baba"][dist_baba_key] = stats
            m = stats['rpci']['mean']
            print(f"  [OK] {dist_baba_key}: {stats['sample_count']} races, RPCI={m:.2f}")

    # --- [STEP 2e] 頭数別補正 ---
    print("\n[STEP 2e] Runner count adjustments...")
    runner_adj = calculate_runner_adjustments(all_records, standards["by_distance_group"])
    standards["runner_adjustments"] = runner_adj
    for dist_key, groups in sorted(runner_adj.items()):
        parts = [f"{g}: offset={d['rpci_offset']:+.2f} (n={d['sample_count']})" for g, d in groups.items()]
        print(f"  {dist_key}: {' / '.join(parts)}")

    # --- [STEP 2f] Similar courses ---
    print("\n[STEP 2f] Finding similar courses...")
    similar = find_similar_courses(course_stats, threshold=0.5)
    for course, similar_list in similar.items():
        if len(similar_list) >= 1:
            standards["similar_courses"][course] = similar_list

    # --- [STEP 2g] コース別L3平均 ---
    print("\n[STEP 2g] Course L3 averages...")
    course_l3_avg: Dict[str, float] = {}
    for course_key, infos in by_course.items():
        l3_values = [r.last_3f_seconds for r in infos if r.last_3f_seconds]
        if l3_values:
            avg_l3 = statistics.mean(l3_values)
            course_l3_avg[course_key] = round(avg_l3, 2)
    standards["course_l3_average"] = course_l3_avg
    print(f"  Courses with L3 average: {len(course_l3_avg)}")

    # --- [STEP 2h] レース傾向5段階分類 ---
    print("\n[STEP 2h] Race trend classification (5 types)...")
    for r in all_records:
        course_key = f"{r.track_name}_{r.track_type}_{r.distance}m"
        avg_l3 = course_l3_avg.get(course_key)
        r.race_trend = classify_race_trend(
            r.rpci, r.first_3f_seconds, r.last_3f_seconds,
            r.first_4f_seconds, r.last_4f_seconds,
            course_avg_l3=avg_l3,
        )

    # コース別傾向分布
    trend_dist: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in all_records:
        course_key = f"{r.track_name}_{r.track_type}_{r.distance}m"
        trend_dist[course_key][r.race_trend] += 1

    for course_key in sorted(trend_dist.keys()):
        counts = trend_dist[course_key]
        total = sum(counts.values())
        dist_entry = {}
        for t in RACE_TREND_TYPES:
            c = counts.get(t, 0)
            dist_entry[t] = {"count": c, "pct": round(c / total * 100, 1) if total > 0 else 0}
        standards["race_trend_distribution"][course_key] = dist_entry

    # サマリ表示
    global_counts = defaultdict(int)
    for r in all_records:
        global_counts[r.race_trend] += 1
    total_all = len(all_records)
    for t in RACE_TREND_TYPES:
        c = global_counts.get(t, 0)
        pct = c / total_all * 100 if total_all > 0 else 0
        print(f"  {RACE_TREND_LABELS.get(t, t)}: {c:,} ({pct:.1f}%)")

    return standards


def print_baba_comparison(standards: Dict):
    """Print baba condition comparison"""
    by_dist_baba = standards.get("by_distance_group_baba", {})
    if not by_dist_baba:
        return

    print("\n" + "=" * 70)
    print("Baba Condition Comparison (良 vs 稍重以上)")
    print("=" * 70)

    # 距離グループごとに良 vs 稍重以上を比較
    base_keys = set()
    for k in by_dist_baba.keys():
        # "Turf_1200m-_良" -> "Turf_1200m-"
        parts = k.rsplit("_", 1)
        if len(parts) == 2:
            base_keys.add(parts[0])

    print(f"\n{'Group':<25} {'良 RPCI':>8} {'稍重+ RPCI':>10} {'Diff':>8} {'良 n':>6} {'稍+ n':>6}")
    print("-" * 70)
    for base in sorted(base_keys):
        good = by_dist_baba.get(f"{base}_良", {})
        heavy = by_dist_baba.get(f"{base}_稍重以上", {})
        if good and heavy:
            gm = good["rpci"]["mean"]
            hm = heavy["rpci"]["mean"]
            diff = hm - gm
            sign = "+" if diff > 0 else ""
            print(f"{base:<25} {gm:>8.2f} {hm:>10.2f} {sign}{diff:>7.2f} {good['sample_count']:>6} {heavy['sample_count']:>6}")


def print_similar_courses_report(standards: Dict):
    """Print a report of similar courses"""
    similar = standards.get("similar_courses", {})
    courses = standards.get("courses", {})

    if not similar:
        print("\n  No similar courses found (threshold 0.5)")
        return

    print("\n" + "=" * 70)
    print("Similar Courses Report (RPCI diff <= 0.5)")
    print("=" * 70)

    turf_pairs = []
    dirt_pairs = []

    reported = set()
    for course1, similar_list in similar.items():
        for course2 in similar_list:
            pair = tuple(sorted([course1, course2]))
            if pair in reported:
                continue
            reported.add(pair)

            stats1 = courses.get(course1, {})
            stats2 = courses.get(course2, {})
            if not stats1 or not stats2:
                continue

            mean1 = stats1["rpci"]["mean"]
            mean2 = stats2["rpci"]["mean"]
            diff = abs(mean1 - mean2)

            is_turf1 = "Turf" in course1
            is_turf2 = "Turf" in course2

            if is_turf1 and is_turf2:
                turf_pairs.append((course1, course2, mean1, mean2, diff))
            elif not is_turf1 and not is_turf2:
                dirt_pairs.append((course1, course2, mean1, mean2, diff))

    if turf_pairs:
        print("\n[Turf] Similar courses:")
        for c1, c2, m1, m2, diff in sorted(turf_pairs, key=lambda x: x[4])[:15]:
            print(f"  {c1} (RPCI={m1:.1f}) ~ {c2} (RPCI={m2:.1f}) [diff={diff:.2f}]")

    if dirt_pairs:
        print("\n[Dirt] Similar courses:")
        for c1, c2, m1, m2, diff in sorted(dirt_pairs, key=lambda x: x[4])[:15]:
            print(f"  {c1} (RPCI={m1:.1f}) ~ {c2} (RPCI={m2:.1f}) [diff={diff:.2f}]")


def main():
    parser = argparse.ArgumentParser(
        description="Calculate race type standards from JRA-VAN data (v2)"
    )
    parser.add_argument(
        "--years",
        type=str,
        default=None,
        help="Target years (comma separated, e.g., 2024,2025)"
    )
    parser.add_argument(
        "--since",
        type=int,
        default=2020,
        help="Start year (calculates from this year to current year)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(get_target_data_dir() / "race_type_standards.json"),
        help="Output file path"
    )

    args = parser.parse_args()

    current_year = datetime.now().year
    if args.years:
        years = [int(y.strip()) for y in args.years.split(",")]
    else:
        years = list(range(args.since, current_year + 1))

    print("=" * 70)
    print("JRA-VAN RPCI Standards Calculator (v3)")
    print("=" * 70)
    print(f"Data path: {JV_DATA_ROOT}")
    print(f"SE_DATA: {SE_DATA_PATH}")
    print(f"Years: {years}")
    print(f"Output: {args.output}")
    print(f"Features: 5段階傾向分類 / 馬場別分離 / 頭数別補正 / 年度重み付け")
    print()

    if not SE_DATA_PATH.exists():
        print(f"[ERROR] SE_DATA not found: {SE_DATA_PATH}")
        print("Set JV_DATA_ROOT_DIR environment variable")
        return 1

    # Scan SR_DATA
    print("[STEP 1] Scanning SR_DATA...")
    all_records = scan_sr_files(years)

    if not all_records:
        print("[ERROR] No valid data found")
        return 1

    # 馬場状態の分布を表示
    baba_good = sum(1 for r in all_records if r.baba_condition == "良")
    baba_heavy = len(all_records) - baba_good
    runners_avg = statistics.mean([r.num_runners for r in all_records if r.num_runners > 0]) if all_records else 0
    print(f"\n  馬場分布: 良={baba_good:,} / 稍重以上={baba_heavy:,}")
    print(f"  平均出走頭数: {runners_avg:.1f}")

    # Calculate standards
    print("\n[STEP 2] Calculating standards...")
    standards = calculate_standards(all_records, years)

    # Reports
    print_baba_comparison(standards)
    print_similar_courses_report(standards)

    # Output: race_type_standards.json
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(standards, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print(f"[OK] Standards saved: {output_path}")
    print(f"  Distance groups: {len(standards['by_distance_group'])}")
    print(f"  Courses: {len(standards['courses'])}")
    print(f"  Baba entries: {len(standards['by_baba'])}")
    print(f"  Dist x Baba: {len(standards['by_distance_group_baba'])}")
    print(f"  Runner adj groups: {len(standards['runner_adjustments'])}")
    print(f"  Similar course pairs: {sum(len(v) for v in standards['similar_courses'].values()) // 2}")
    print(f"  Course L3 averages: {len(standards['course_l3_average'])}")
    print(f"  Trend distributions: {len(standards['race_trend_distribution'])}")

    # Output: race_trend_index.json（レースごとの傾向分類インデックス）
    trend_index = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "version": "1.0",
            "source": "JRA-VAN SR_DATA",
            "years": standards["metadata"]["years"],
            "description": "Race trend classification index (per race)",
        },
        "races": {},
    }
    for r in all_records:
        entry: Dict = {
            "trend": r.race_trend,
            "rpci": r.rpci,
            "s3": r.first_3f_seconds,
            "l3": r.last_3f_seconds,
        }
        if r.first_4f_seconds is not None:
            entry["s4"] = r.first_4f_seconds
        if r.last_4f_seconds is not None:
            entry["l4"] = r.last_4f_seconds
        trend_index["races"][r.race_id] = entry

    trend_index_path = output_path.parent / "race_trend_index.json"
    with open(trend_index_path, "w", encoding="utf-8") as f:
        json.dump(trend_index, f, ensure_ascii=False, indent=2)

    print(f"\n[OK] Trend index saved: {trend_index_path}")
    print(f"  Total races: {len(trend_index['races']):,}")

    return 0


if __name__ == "__main__":
    exit(main())
