#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
IDM基準値算出スクリプト — クラス別 JRDB IDM 統計

data3/races の race JSON（jrdb_idm付き）から、
クラス別に「全馬IDM」「勝ち馬IDM」の統計を算出します。

Usage:
    python -m analysis.idm_standards
    python -m analysis.idm_standards --since 2023
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
from core.constants import GRADE_CODES, JOKEN_CLASS_MAP, GRADE_NORMALIZE


# ── 定数 ──

GRADE_SORT_ORDER = {
    'G1_古馬': 0, 'G1_3歳': 1, 'G1_2歳': 2,
    'G2_古馬': 3, 'G2_3歳': 4, 'G2_2歳': 5,
    'G3_古馬': 6, 'G3_3歳': 7, 'G3_2歳': 8,
    'G1': 2, 'G2': 5, 'G3': 8,
    'Listed_古馬': 9, 'Listed_3歳': 10, 'Listed_2歳': 11,
    'OP_古馬': 12, 'OP_3歳': 13, 'OP_2歳': 14,
    'Listed': 9, 'OP': 12,
    '3勝クラス': 15, '2勝クラス': 16, '1勝クラス': 17,
    '新馬': 18, '未勝利': 19, '未分類': 99,
}

AGE_SEPARATED_GRADES = {'G1', 'G2', 'G3', 'OP', 'Listed'}
MIN_SAMPLE_COUNT = 30


# ── ヘルパー ──

def extract_track_type(track_type: str) -> str:
    if track_type == 'turf':
        return '芝'
    if track_type == 'dirt':
        return 'ダ'
    return ''


def _detect_age_class(race: dict) -> str:
    entries = race.get('entries', [])
    if not entries:
        return ''
    ages = [e.get('age', 0) for e in entries if e.get('age', 0) > 0]
    if not ages:
        return ''
    min_age = min(ages)
    max_age = max(ages)
    if max_age == 2:
        return '2歳'
    if min_age <= 3 and max_age == 3:
        return '3歳'
    return '古馬'


def _fetch_grade_from_db(race_id: str) -> dict:
    try:
        from core.db import get_connection
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                'SELECT GRADE_CODE, '
                'KYOSO_JOKEN_CODE_2SAI, KYOSO_JOKEN_CODE_3SAI, '
                'KYOSO_JOKEN_CODE_4SAI, KYOSO_JOKEN_CODE_5SAI_IJO, '
                'KYOSO_JOKEN_CODE_SAIJAKUNEN '
                'FROM RACE_SHOSAI WHERE RACE_CODE = %s',
                (race_id,)
            )
            row = cur.fetchone()
            if not row:
                return {}
            grade_code = (row[0] or '').strip()
            j2sai = (row[1] or '').strip()
            j3sai = (row[2] or '').strip()
            j4sai = (row[3] or '').strip()
            j5sai = (row[4] or '').strip()
            j_min = (row[5] or '').strip()

            grade = GRADE_CODES.get(grade_code, '')
            if not grade and j_min:
                grade = JOKEN_CLASS_MAP.get(j_min, '')

            age_class = ''
            if j2sai != '000' and j3sai == '000':
                age_class = '2歳'
            elif j3sai != '000' and j4sai == '000':
                age_class = '3歳'
            elif j4sai != '000' or j5sai != '000':
                age_class = '古馬'

            return {'grade': grade, 'age_class': age_class}
    except Exception:
        return {}


# ── データスキャン ──

def scan_data(since_year: int) -> list:
    """data3/races から IDM データを収集（勝ち馬IDM含む）"""
    results = []
    races_dir = config.races_dir()

    if not races_dir.exists():
        print(f"  [ERROR] races dir not found: {races_dir}")
        return results

    print(f"  Races: {races_dir}")

    no_idm = 0
    db_补完 = 0

    for year_dir in sorted(races_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        try:
            year_num = int(year_dir.name)
            if year_num < since_year:
                continue
        except ValueError:
            continue

        year_count = 0
        for race_file in year_dir.rglob("race_[0-9]*.json"):
            try:
                with open(race_file, 'r', encoding='utf-8') as f:
                    race = json.load(f)

                race_id = race['race_id']
                race_date = race.get('date', '')
                grade = race.get('grade', '')
                track_type = extract_track_type(race.get('track_type', ''))
                db_age_class = ''

                # gradeが空の場合、DBからfallback取得
                if not grade:
                    db_info = _fetch_grade_from_db(race_id)
                    grade = db_info.get('grade', '')
                    db_age_class = db_info.get('age_class', '')
                    if grade:
                        db_补完 += 1

                # grade正規化
                grade = GRADE_NORMALIZE.get(grade, grade)

                if not grade:
                    continue

                # entries から IDM 収集
                all_idms = []
                winner_idms = []
                for entry in race.get('entries', []):
                    idm = entry.get('jrdb_idm')
                    if idm is None or idm == 0:
                        continue
                    all_idms.append(idm)
                    fp = entry.get('finish_position')
                    if fp == 1:
                        winner_idms.append(idm)

                if len(all_idms) < 3:
                    no_idm += 1
                    continue

                # 月・年齢クラス
                date_parts = race_date.split('-')
                if len(date_parts) != 3:
                    continue
                month = int(date_parts[1])
                age_class = db_age_class if db_age_class else _detect_age_class(race)

                results.append({
                    'race_id': race_id,
                    'grade': grade,
                    'all_idms': all_idms,
                    'winner_idms': winner_idms,
                    'track': track_type,
                    'month': month,
                    'age_class': age_class,
                    'race_name': race.get('race_name', ''),
                    'race_date': race_date,
                })
                year_count += 1

            except (json.JSONDecodeError, KeyError, TypeError):
                continue

        if year_count:
            print(f"  [{year_dir.name}] {year_count:,} races with IDM")

    print(f"\n  Total: {len(results):,} races")
    print(f"  No IDM: {no_idm:,}")
    if db_补完 > 0:
        print(f"  DB grade fallback: {db_补完:,} races")

    return results


# ── 統計計算 ──

def _compute_grade_stats(grade_races: list) -> Optional[dict]:
    """グレードの IDM 統計を算出"""
    all_idms = []
    winner_idms = []

    for race in grade_races:
        all_idms.extend(race['all_idms'])
        winner_idms.extend(race['winner_idms'])

    if len(all_idms) < 10:
        return None

    mean_all = statistics.mean(all_idms)
    stdev_all = statistics.stdev(all_idms) if len(all_idms) > 1 else 0

    result = {
        "sample_count": len(grade_races),
        "horse_count": len(all_idms),
        "winner_count": len(winner_idms),
        "all": {
            "mean": round(mean_all, 2),
            "stdev": round(stdev_all, 2),
            "median": round(statistics.median(all_idms), 2),
            "min": round(min(all_idms), 2),
            "max": round(max(all_idms), 2),
        },
    }

    if winner_idms:
        mean_win = statistics.mean(winner_idms)
        stdev_win = statistics.stdev(winner_idms) if len(winner_idms) > 1 else 0
        result["winner"] = {
            "mean": round(mean_win, 2),
            "stdev": round(stdev_win, 2),
            "median": round(statistics.median(winner_idms), 2),
            "min": round(min(winner_idms), 2),
            "max": round(max(winner_idms), 2),
        }
    else:
        result["winner"] = None

    return result


def calculate_stats(races: list) -> dict:
    """クラス別統計を算出（小サンプルは全年齢プールにフォールバック）"""
    by_grade = defaultdict(list)
    by_grade_pooled = defaultdict(list)

    for race in races:
        grade = race['grade']
        age_class = race['age_class']
        if grade in AGE_SEPARATED_GRADES and age_class:
            by_grade[f"{grade}_{age_class}"].append(race)
            by_grade_pooled[grade].append(race)
        else:
            by_grade[grade].append(race)

    # 全年齢プールの統計
    pooled_stats = {}
    for base_grade in AGE_SEPARATED_GRADES:
        if base_grade in by_grade_pooled:
            s = _compute_grade_stats(by_grade_pooled[base_grade])
            if s:
                pooled_stats[base_grade] = s

    # 年齢分離の統計
    stats = {}
    fallback_count = 0
    for grade in sorted(by_grade.keys(), key=lambda g: GRADE_SORT_ORDER.get(g, 50)):
        s = _compute_grade_stats(by_grade[grade])
        if s is None:
            continue

        base_grade = grade.rsplit('_', 1)[0] if '_' in grade else ''
        if s['sample_count'] < MIN_SAMPLE_COUNT and base_grade in pooled_stats:
            fallback = dict(pooled_stats[base_grade])
            fallback['fallback_from'] = grade
            fallback['fallback_to'] = base_grade
            fallback['original_sample_count'] = s['sample_count']
            stats[grade] = fallback
            fallback_count += 1
        else:
            stats[grade] = s

    if fallback_count:
        print(f"  Small-sample fallback: {fallback_count} categories")

    return stats


def calculate_by_race_name(races: list) -> dict:
    """重賞（G1/G2/G3）を同一レース名でグループ化して統計算出"""
    by_name = defaultdict(list)
    for race in races:
        if race['grade'] in ('G1', 'G2', 'G3') and race['race_name']:
            by_name[race['race_name']].append(race)

    result = {}
    for name in sorted(by_name.keys()):
        races_group = by_name[name]
        if len(races_group) < 2:
            continue

        all_idms = []
        winner_idms = []
        years = []
        for race in races_group:
            all_idms.extend(race['all_idms'])
            winner_idms.extend(race['winner_idms'])
            years.append(race['race_date'][:4])

        if not all_idms:
            continue

        entry = {
            "grade": races_group[0]['grade'],
            "count": len(races_group),
            "years": sorted(set(years)),
            "all_mean": round(statistics.mean(all_idms), 2),
        }
        if winner_idms:
            entry["winner_mean"] = round(statistics.mean(winner_idms), 2)
            entry["winner_min"] = round(min(winner_idms), 2)
            entry["winner_max"] = round(max(winner_idms), 2)
            # 各年の勝ち馬IDMリスト
            yearly = []
            for race in sorted(races_group, key=lambda r: r['race_date']):
                if race['winner_idms']:
                    yearly.append({
                        "year": race['race_date'][:4],
                        "winner_idm": race['winner_idms'][0],
                    })
            entry["yearly_winners"] = yearly

        result[name] = entry

    return result


# ── メイン ──

def main():
    parser = argparse.ArgumentParser(description="IDM Standards Calculator")
    parser.add_argument("--since", type=int, default=2023, help="Start year (default: 2023)")
    output_default = str(config.data_root() / "analysis" / "idm_standards.json")
    parser.add_argument("--output", type=str, default=output_default, help="Output file path")
    args = parser.parse_args()

    print("=" * 70)
    print("IDM Standards Calculator (JRDB IDM)")
    print("=" * 70)
    print(f"Data source: {config.races_dir()}")
    print(f"Since: {args.since}")
    print(f"Output: {args.output}")
    print()

    # データスキャン
    print("[STEP 1] Scanning data3/races for IDM data...")
    races = scan_data(args.since)
    print(f"  Found {len(races)} races with IDM data")

    if not races:
        print("[ERROR] No valid data found")
        return 1

    # クラス別統計
    print("\n[STEP 2] Calculating grade statistics...")
    grade_stats = calculate_stats(races)
    for grade, stats in grade_stats.items():
        winner_info = ""
        if stats.get('winner'):
            winner_info = f", winner_mean={stats['winner']['mean']:.1f}"
        print(f"  [{grade}] {stats['sample_count']} races, "
              f"all_mean={stats['all']['mean']:.1f}"
              f"{winner_info}")

    # 重賞同一レース名統計
    print("\n[STEP 3] Calculating by-race-name statistics (graded)...")
    by_race_name = calculate_by_race_name(races)
    for name, info in list(by_race_name.items())[:10]:
        wm = info.get('winner_mean', '-')
        print(f"  [{info['grade']}] {name}: {info['count']}回, winner_mean={wm}")
    if len(by_race_name) > 10:
        print(f"  ... and {len(by_race_name) - 10} more")
    print(f"  Total: {len(by_race_name)} unique race names")

    # グローバル平均
    all_global_idms = []
    all_winner_idms = []
    for race in races:
        all_global_idms.extend(race['all_idms'])
        all_winner_idms.extend(race['winner_idms'])
    global_mean = round(statistics.mean(all_global_idms), 2) if all_global_idms else 0
    global_winner_mean = round(statistics.mean(all_winner_idms), 2) if all_winner_idms else 0
    print(f"\n  Global mean IDM: {global_mean}")
    print(f"  Global winner mean IDM: {global_winner_mean}")

    # 出力
    standards = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "source": "data3/races (JRDB IDM)",
            "years": f"{args.since}-{datetime.now().year}",
            "total_races": len(races),
            "version": "1.0",
            "global_mean_idm": global_mean,
            "global_winner_mean_idm": global_winner_mean,
        },
        "by_grade": grade_stats,
        "by_race_name": by_race_name,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(standards, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 70}")
    print(f"[OK] IDM Standards saved: {output_path}")
    print(f"  Grades: {len(grade_stats)}, Total races: {len(races)}")
    return 0


if __name__ == "__main__":
    exit(main())
