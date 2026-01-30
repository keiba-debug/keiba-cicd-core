#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JRA-VANデータからレース特性基準値を算出するスクリプト

SR_DATA（レース毎成績）から前3F/後3FでRPCIを計算し、
コース別（競馬場×芝/ダート×距離）の瞬発戦/持続戦の基準値を統計的に算出します。

Usage:
    python calculate_race_type_standards_jv.py
    python calculate_race_type_standards_jv.py --years 2024,2025
    python calculate_race_type_standards_jv.py --output data/race_type_standards.json
"""

import argparse
import json
import os
import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


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


def _get_env_path(key: str, default: str) -> Path:
    value = os.getenv(key)
    if value:
        return Path(value)
    return Path(default)


_load_dotenv_if_available()

# JRA-VAN data path
JV_DATA_ROOT = _get_env_path("JV_DATA_ROOT_DIR", "Y:/")
SE_DATA_PATH = JV_DATA_ROOT / "SE_DATA"

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
    track_code: str
    track_name: str
    distance: int
    track_type: str  # Turf/Dirt
    first_3f_seconds: float
    last_3f_seconds: float
    rpci: float


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
        year = decode_sjis(record[11:15])
        month_day = decode_sjis(record[15:19])
        jyo_cd = decode_sjis(record[19:21])
        kaiji = decode_sjis(record[21:23])
        nichiji = decode_sjis(record[23:25])
        race_num = decode_sjis(record[25:27])
        
        race_id = f"{year}{jyo_cd}{kaiji}{nichiji}{race_num}"
        
        # Distance (offset 698, 4bytes -> Python: 697:701)
        kyori_str = decode_sjis(record[697:701])
        if not kyori_str.isdigit():
            return None
        distance = int(kyori_str)
        if distance < 800 or distance > 4000:
            return None
        
        # Track type (offset 706, 2bytes -> Python: 705:707)
        track_cd = decode_sjis(record[705:707])
        if track_cd.startswith("1"):
            track_type = "Turf"
        elif track_cd.startswith("2"):
            track_type = "Dirt"
        else:
            return None
        
        # First 3F (offset 970 -> Python: 969:972)
        first_3f_str = decode_sjis(record[969:972])
        first_3f_seconds = parse_time_to_seconds(first_3f_str)
        
        # Last 3F (offset 976 -> Python: 975:978)
        last_3f_str = decode_sjis(record[975:978])
        last_3f_seconds = parse_time_to_seconds(last_3f_str)
        
        if first_3f_seconds is None or last_3f_seconds is None:
            return None
        
        # Validation (3F time should be 30-50 seconds)
        if first_3f_seconds < 30 or first_3f_seconds > 50:
            return None
        if last_3f_seconds < 30 or last_3f_seconds > 50:
            return None
        
        rpci = calculate_rpci(first_3f_seconds, last_3f_seconds)
        if rpci is None:
            return None
        
        track_name = TRACK_CODES.get(jyo_cd, "Unknown")
        date_str = f"{year}-{month_day[:2]}-{month_day[2:]}"
        
        return RaceInfo(
            race_id=race_id,
            date=date_str,
            track_code=jyo_cd,
            track_name=track_name,
            distance=distance,
            track_type=track_type,
            first_3f_seconds=first_3f_seconds,
            last_3f_seconds=last_3f_seconds,
            rpci=rpci,
        )
    except Exception:
        return None


def scan_sr_files(years: List[int]) -> Tuple[Dict[str, List[RaceInfo]], Dict[str, List[RaceInfo]]]:
    """Scan SR_DATA files and return results by course and by distance group"""
    results_by_course: Dict[str, List[RaceInfo]] = defaultdict(list)
    results_by_distance: Dict[str, List[RaceInfo]] = defaultdict(list)
    total_records = 0
    valid_records = 0
    
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
                        valid_records += 1
                        
                        # Course key: Track_Surface_Distance
                        course_key = f"{result.track_name}_{result.track_type}_{result.distance}m"
                        results_by_course[course_key].append(result)
                        
                        # Distance group key: Surface_DistanceGroup
                        dist_group = classify_distance(result.distance)
                        dist_key = f"{result.track_type}_{dist_group}"
                        results_by_distance[dist_key].append(result)
                        
            except Exception as e:
                print(f"  [ERROR] {sr_file}: {e}")
    
    print(f"\n  Total records: {total_records:,}")
    print(f"  Valid records: {valid_records:,}")
    
    return results_by_course, results_by_distance


def calculate_course_stats(rpci_values: List[float]) -> Dict:
    """Calculate statistics for a course"""
    if len(rpci_values) < 10:
        return None
    
    mean = statistics.mean(rpci_values)
    stdev = statistics.stdev(rpci_values) if len(rpci_values) > 1 else 0
    median = statistics.median(rpci_values)
    
    # Thresholds
    instantaneous = mean + stdev * 0.5
    sustained = mean - stdev * 0.5
    
    return {
        "sample_count": len(rpci_values),
        "rpci": {
            "mean": round(mean, 2),
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


def calculate_standards(results_by_course: Dict[str, List[RaceInfo]], 
                        results_by_distance: Dict[str, List[RaceInfo]],
                        years: List[int]) -> Dict:
    """Calculate standards for all courses"""
    years_str = f"{min(years)}-{max(years)}" if len(years) > 1 else str(years[0])
    standards = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "source": "JRA-VAN SR_DATA",
            "years": years_str,
            "years_list": years,
            "description": f"RPCI standards by course (Track x Surface x Distance) [{years_str}]",
            "calculation": "RPCI = (First 3F / Last 3F) x 50",
        },
        "by_distance_group": {},
        "courses": {},
        "similar_courses": {},
    }
    
    # Distance group stats
    print("\n[STEP 2a] Distance group statistics...")
    for dist_key in sorted(results_by_distance.keys()):
        infos = results_by_distance[dist_key]
        rpci_values = [r.rpci for r in infos if r.rpci is not None]
        stats = calculate_course_stats(rpci_values)
        if stats:
            standards["by_distance_group"][dist_key] = stats
            print(f"  [OK] {dist_key}: {len(rpci_values)} races, RPCI={stats['rpci']['mean']:.2f}")
    
    # Course stats
    print("\n[STEP 2b] Course statistics...")
    course_stats = {}
    for course_key in sorted(results_by_course.keys()):
        infos = results_by_course[course_key]
        rpci_values = [r.rpci for r in infos if r.rpci is not None]
        stats = calculate_course_stats(rpci_values)
        if stats:
            course_stats[course_key] = stats
            standards["courses"][course_key] = stats
    
    print(f"  Total courses: {len(course_stats)}")
    
    # Find similar courses
    print("\n[STEP 2c] Finding similar courses...")
    similar = find_similar_courses(course_stats, threshold=0.8)
    
    # Format similar courses for output
    for course, similar_list in similar.items():
        if len(similar_list) >= 1:
            standards["similar_courses"][course] = similar_list
    
    return standards


def print_similar_courses_report(standards: Dict):
    """Print a report of similar courses"""
    similar = standards.get("similar_courses", {})
    courses = standards.get("courses", {})
    
    if not similar:
        print("\n  No similar courses found (threshold 0.8)")
        return
    
    print("\n" + "=" * 70)
    print("Similar Courses Report (RPCI diff <= 0.8)")
    print("=" * 70)
    
    # Group by surface type
    turf_pairs = []
    dirt_pairs = []
    cross_surface = []
    
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
            else:
                cross_surface.append((course1, course2, mean1, mean2, diff))
    
    def format_course_jp(course: str) -> str:
        parts = course.split("_")
        if len(parts) >= 3:
            track = TRACK_NAMES_JP.get(parts[0], parts[0])
            surface = "Turf" if parts[1] == "Turf" else "Dirt"
            dist = parts[2]
            return f"{track}{surface}{dist}"
        return course
    
    if turf_pairs:
        print("\n[Turf] Similar courses:")
        for c1, c2, m1, m2, diff in sorted(turf_pairs, key=lambda x: x[4])[:15]:
            print(f"  {c1} (RPCI={m1:.1f}) ~ {c2} (RPCI={m2:.1f}) [diff={diff:.2f}]")
    
    if dirt_pairs:
        print("\n[Dirt] Similar courses:")
        for c1, c2, m1, m2, diff in sorted(dirt_pairs, key=lambda x: x[4])[:15]:
            print(f"  {c1} (RPCI={m1:.1f}) ~ {c2} (RPCI={m2:.1f}) [diff={diff:.2f}]")


def print_course_comparison(standards: Dict):
    """Print course comparison for specific examples"""
    courses = standards.get("courses", {})
    
    print("\n" + "=" * 70)
    print("Course Comparison Examples")
    print("=" * 70)
    
    # Example comparisons
    comparisons = [
        ("Fukushima_Dirt_1700m", "Kokura_Dirt_1700m"),
        ("Nakayama_Turf_1600m", "Tokyo_Turf_1600m"),
        ("Nakayama_Turf_2000m", "Tokyo_Turf_2000m"),
        ("Hanshin_Turf_1600m", "Kyoto_Turf_1600m"),
        ("Chukyo_Dirt_1800m", "Kyoto_Dirt_1800m"),
    ]
    
    print(f"\n{'Course A':<25} {'RPCI':>6} | {'Course B':<25} {'RPCI':>6} | {'Diff':>6}")
    print("-" * 80)
    
    for c1, c2 in comparisons:
        s1 = courses.get(c1, {})
        s2 = courses.get(c2, {})
        
        if s1 and s2:
            m1 = s1["rpci"]["mean"]
            m2 = s2["rpci"]["mean"]
            diff = m2 - m1
            sign = "+" if diff > 0 else ""
            print(f"{c1:<25} {m1:>6.2f} | {c2:<25} {m2:>6.2f} | {sign}{diff:>5.2f}")
        else:
            missing = []
            if not s1:
                missing.append(c1)
            if not s2:
                missing.append(c2)
            print(f"  [SKIP] Missing data: {', '.join(missing)}")


def main():
    parser = argparse.ArgumentParser(
        description="Calculate race type standards from JRA-VAN data"
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
        default="data/race_type_standards.json",
        help="Output file path"
    )
    
    args = parser.parse_args()
    
    # 年の決定: --years が指定されていればそれを使用、なければ --since から現在年まで
    current_year = datetime.now().year
    if args.years:
        years = [int(y.strip()) for y in args.years.split(",")]
    else:
        years = list(range(args.since, current_year + 1))
    
    print("=" * 70)
    print("JRA-VAN RPCI Standards Calculator")
    print("=" * 70)
    print(f"Data path: {JV_DATA_ROOT}")
    print(f"SE_DATA: {SE_DATA_PATH}")
    print(f"Years: {years}")
    print(f"Output: {args.output}")
    print()
    
    if not SE_DATA_PATH.exists():
        print(f"[ERROR] SE_DATA not found: {SE_DATA_PATH}")
        print("Set JV_DATA_ROOT_DIR environment variable")
        return 1
    
    # Scan SR_DATA
    print("[STEP 1] Scanning SR_DATA...")
    results_by_course, results_by_distance = scan_sr_files(years)
    
    if not results_by_course:
        print("[ERROR] No valid data found")
        return 1
    
    # Calculate standards
    print("\n[STEP 2] Calculating standards...")
    standards = calculate_standards(results_by_course, results_by_distance, years)
    
    # Print similar courses report
    print_similar_courses_report(standards)
    
    # Print course comparison examples
    print_course_comparison(standards)
    
    # Output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(standards, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 70)
    print(f"[OK] Standards saved: {output_path}")
    print(f"  Distance groups: {len(standards['by_distance_group'])}")
    print(f"  Courses: {len(standards['courses'])}")
    print(f"  Similar course pairs: {sum(len(v) for v in standards['similar_courses'].values()) // 2}")
    
    return 0


if __name__ == "__main__":
    exit(main())
