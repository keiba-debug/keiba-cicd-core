#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
レイティング基準値算出スクリプト (v3 - data3ネイティブ)

data3/races（grade/race_class）+ data3/keibabook（kb_ext ratings）から
クラス別レイティング統計を算出し、レースレベル・混戦度の判定基準を生成します。

Usage:
    python -m analysis.rating_standards
    python -m analysis.rating_standards --since 2023
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


def parse_rating(rating_str) -> Optional[float]:
    if rating_str is None:
        return None
    s = str(rating_str).strip()
    if not s or s in ('-', '---'):
        return None
    z2h = str.maketrans('０１２３４５６７８９．', '0123456789.')
    s = s.translate(z2h)
    try:
        value = float(s)
        if 30 <= value <= 150:
            return value
        return None
    except (ValueError, TypeError):
        return None


def get_maiden_season(age_class: str, month: int) -> str:
    if age_class == '2歳':
        if 6 <= month <= 8:
            return '2歳未勝利_6-8月'
        elif 9 <= month <= 12:
            return '2歳未勝利_9-12月'
    elif age_class == '3歳':
        if 1 <= month <= 3:
            return '3歳未勝利_1-3月'
        elif 4 <= month <= 6:
            return '3歳未勝利_4-6月'
        elif 7 <= month <= 9:
            return '3歳未勝利_7-9月'
    return ""


def extract_age_class(race_class: str) -> str:
    """race_classから年齢クラスを抽出: '古馬G1' → '古馬', '3歳未勝利' → '3歳'"""
    if not race_class:
        return ""
    if race_class.startswith('2歳'):
        return '2歳'
    if race_class.startswith('3歳'):
        return '3歳'
    if race_class.startswith('古馬'):
        return '古馬'
    return ""


def extract_track_type(track_type: str) -> str:
    """track_typeをWebViewer互換形式に変換"""
    if track_type == 'turf':
        return '芝'
    if track_type == 'dirt':
        return 'ダ'
    return ''


GRADE_SORT_ORDER = {
    'G1_古馬': 0, 'G1_3歳': 1, 'G1_2歳': 2,
    'G2_古馬': 3, 'G2_3歳': 4, 'G2_2歳': 5,
    'G3_古馬': 6, 'G3_3歳': 7, 'G3_2歳': 8,
    'G1': 2, 'G2': 5, 'G3': 8,
    'OP': 9, 'Listed': 9,
    '3勝クラス': 10, '2勝クラス': 11, '1勝クラス': 12,
    '新馬': 13, '未勝利': 14, '未分類': 99,
}


def interpret_competitiveness(stdev: float) -> str:
    if stdev < 4:
        return "非常に混戦"
    elif stdev < 6:
        return "やや混戦"
    elif stdev < 8:
        return "標準的"
    return "力差明確"


def scan_data(since_year: int) -> list:
    """data3/races + data3/keibabook からレイティングデータを収集"""
    results = []
    races_dir = config.races_dir()
    kb_dir = config.keibabook_dir()

    if not races_dir.exists():
        print(f"  [ERROR] races dir not found: {races_dir}")
        return results

    print(f"  Races: {races_dir}")
    print(f"  Keibabook: {kb_dir}")

    no_kb = 0
    no_ratings = 0

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
                race_class = race.get('race_name', '')  # for display
                track_type = extract_track_type(race.get('track_type', ''))

                # gradeが空のレースはスキップ（障害競走等）
                if not grade:
                    continue

                # 対応するkb_extを探してレイティング取得
                date_parts = race_date.split('-')
                if len(date_parts) != 3:
                    continue
                kb_path = kb_dir / date_parts[0] / date_parts[1] / date_parts[2] / f"kb_ext_{race_id}.json"
                if not kb_path.exists():
                    no_kb += 1
                    continue

                with open(kb_path, 'r', encoding='utf-8') as f:
                    kb_ext = json.load(f)

                # 各馬のレイティングを収集
                ratings = []
                for umaban, entry_data in kb_ext.get('entries', {}).items():
                    rating_value = entry_data.get('rating')
                    r = parse_rating(rating_value)
                    if r is not None:
                        ratings.append(r)

                if len(ratings) < 3:
                    no_ratings += 1
                    continue

                # 月を取得
                month = int(date_parts[1])

                # race JSONのgradeフィールドからage_classを導出
                # sr_parserがrace_classを生成するが、race JSONにはgradeだけ入る
                # → race JSONのgradeとrace_classを両方読む
                # 現時点ではgradeフィールドのみ (G1/OP/未勝利等)
                # 年齢はkb_extまたはrace entries から推定
                # → race_class は build_race_master で保存されていないので
                #   race entries の age から判定する
                age_class = _detect_age_class(race)

                results.append({
                    'grade': grade,
                    'ratings': ratings,
                    'track': track_type,
                    'month': month,
                    'age_class': age_class,
                })
                year_count += 1

            except (json.JSONDecodeError, KeyError, TypeError):
                continue

        if year_count:
            print(f"  [{year_dir.name}] {year_count:,} races with ratings")

    print(f"\n  Total: {len(results):,} races")
    print(f"  No keibabook: {no_kb:,}, No ratings: {no_ratings:,}")

    return results


def _detect_age_class(race: dict) -> str:
    """race JSONのentries内ageから年齢クラスを推定"""
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
    # 3歳以上 or 4歳以上
    return '古馬'


def calculate_stats(races: list) -> dict:
    """クラス別統計を算出"""
    by_grade = defaultdict(list)
    for race in races:
        grade = race['grade']
        age_class = race['age_class']
        if grade in ('G1', 'G2', 'G3') and age_class:
            key = f"{grade}_{age_class}"
        else:
            key = grade
        by_grade[key].append(race)

    stats = {}
    for grade in sorted(by_grade.keys(), key=lambda g: GRADE_SORT_ORDER.get(g, 50)):
        grade_races = by_grade[grade]
        all_ratings = []
        all_stdevs = []
        all_top3_diffs = []

        for race in grade_races:
            r = race['ratings']
            all_ratings.extend(r)
            if len(r) > 1:
                all_stdevs.append(statistics.stdev(r))
            if len(r) >= 4:
                sr = sorted(r, reverse=True)
                all_top3_diffs.append(sr[0] - sr[3])

        if len(all_ratings) < 10:
            continue

        mean_rating = statistics.mean(all_ratings)
        stdev_rating = statistics.stdev(all_ratings)
        mean_race_stdev = statistics.mean(all_stdevs) if all_stdevs else 0
        mean_top3_diff = statistics.mean(all_top3_diffs) if all_top3_diffs else 0

        stats[grade] = {
            "sample_count": len(grade_races),
            "horse_count": len(all_ratings),
            "rating": {
                "mean": round(mean_rating, 2),
                "stdev": round(stdev_rating, 2),
                "median": round(statistics.median(all_ratings), 2),
                "min": round(min(all_ratings), 2),
                "max": round(max(all_ratings), 2),
            },
            "competitiveness": {
                "mean_race_stdev": round(mean_race_stdev, 2),
                "mean_top3_diff": round(mean_top3_diff, 2),
                "description": interpret_competitiveness(mean_race_stdev),
            },
            "thresholds": {
                "high_level": round(mean_rating + stdev_rating * 0.5, 2),
                "low_level": round(mean_rating - stdev_rating * 0.5, 2),
            },
        }

    return stats


def calculate_competitiveness_thresholds(races: list) -> dict:
    all_stdevs = []
    for race in races:
        r = race['ratings']
        if len(r) > 1:
            all_stdevs.append(statistics.stdev(r))
    if not all_stdevs:
        return {}
    stdev_mean = statistics.mean(all_stdevs)
    stdev_stdev = statistics.stdev(all_stdevs) if len(all_stdevs) > 1 else 0
    return {
        "stdev": {
            "mean": round(stdev_mean, 2),
            "thresholds": {
                "very_competitive": round(stdev_mean - stdev_stdev, 2),
                "competitive": round(stdev_mean - stdev_stdev * 0.5, 2),
                "normal": round(stdev_mean, 2),
                "clear_difference": round(stdev_mean + stdev_stdev * 0.5, 2),
            },
        },
    }


def analyze_maiden_by_season(races: list) -> dict:
    maiden_races = [r for r in races if r['grade'] == '未勝利' and r['track'] in ('芝', 'ダ')]
    if not maiden_races:
        return {}

    categories = defaultdict(list)
    for race in maiden_races:
        season = get_maiden_season(race['age_class'], race['month'])
        if not season:
            continue
        key = f"{season}_{race['track']}"
        categories[key].append(race)

    result = {}
    for key, cat_races in categories.items():
        all_ratings = []
        for race in cat_races:
            all_ratings.extend(race['ratings'])
        if len(all_ratings) < 10:
            continue
        result[key] = {
            "sample_count": len(cat_races),
            "horse_count": len(all_ratings),
            "rating": {
                "mean": round(statistics.mean(all_ratings), 2),
                "stdev": round(statistics.stdev(all_ratings), 2) if len(all_ratings) > 1 else 0,
                "median": round(statistics.median(all_ratings), 2),
                "min": round(min(all_ratings), 2),
                "max": round(max(all_ratings), 2),
            },
        }

    season_order = [
        '2歳未勝利_6-8月_芝', '2歳未勝利_6-8月_ダ',
        '2歳未勝利_9-12月_芝', '2歳未勝利_9-12月_ダ',
        '3歳未勝利_1-3月_芝', '3歳未勝利_1-3月_ダ',
        '3歳未勝利_4-6月_芝', '3歳未勝利_4-6月_ダ',
        '3歳未勝利_7-9月_芝', '3歳未勝利_7-9月_ダ',
    ]
    return {k: result[k] for k in season_order if k in result}


def main():
    parser = argparse.ArgumentParser(description="Rating Standards Calculator (v3 - data3 native)")
    parser.add_argument("--since", type=int, default=2023, help="Start year (default: 2023)")
    output_default = str(config.data_root() / "analysis" / "rating_standards.json")
    parser.add_argument("--output", type=str, default=output_default, help="Output file path")
    args = parser.parse_args()

    print("=" * 70)
    print("Rating Standards Calculator (v3 - data3 native)")
    print("=" * 70)
    print(f"Data source: {config.races_dir()}")
    print(f"Keibabook: {config.keibabook_dir()}")
    print(f"Since: {args.since}")
    print(f"Output: {args.output}")
    print()

    # データスキャン
    print("[STEP 1] Scanning data3/races + keibabook...")
    races = scan_data(args.since)
    print(f"  Found {len(races)} races with rating data")

    if not races:
        print("[ERROR] No valid data found")
        return 1

    # クラス別統計
    print("\n[STEP 2] Calculating grade statistics...")
    grade_stats = calculate_stats(races)
    for grade, stats in grade_stats.items():
        print(f"  [{grade}] {stats['sample_count']} races, "
              f"mean={stats['rating']['mean']:.1f}, "
              f"stdev={stats['rating']['stdev']:.1f}")

    # 混戦度閾値
    print("\n[STEP 3] Calculating competitiveness thresholds...")
    comp_thresholds = calculate_competitiveness_thresholds(races)

    # 未勝利戦シーズン別
    print("\n[STEP 4] Analyzing maiden races by season...")
    maiden_season_stats = analyze_maiden_by_season(races)
    if maiden_season_stats:
        for key, stats in maiden_season_stats.items():
            print(f"    [{key}] {stats['sample_count']} races, mean={stats['rating']['mean']:.1f}")

    # 出力
    standards = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "source": "data3/races + data3/keibabook (v3 native)",
            "years": f"{args.since}-{datetime.now().year}",
            "total_races": len(races),
            "version": "3.0",
        },
        "by_grade": grade_stats,
        "competitiveness_thresholds": comp_thresholds,
        "maiden_by_season": maiden_season_stats,
    }

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
    print(f"  Grades: {len(grade_stats)}, Total races: {len(races)}")
    return 0


if __name__ == "__main__":
    exit(main())
