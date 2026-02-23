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
from core.constants import GRADE_CODES, JOKEN_CLASS_MAP, GRADE_NORMALIZE


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
    'Listed_古馬': 9, 'Listed_3歳': 10, 'Listed_2歳': 11,
    'OP_古馬': 12, 'OP_3歳': 13, 'OP_2歳': 14,
    'Listed': 9, 'OP': 12,
    '3勝クラス': 15, '2勝クラス': 16, '1勝クラス': 17,
    '新馬': 18, '未勝利': 19, '未分類': 99,
}

# 年齢分離を行うグレード
AGE_SEPARATED_GRADES = {'G1', 'G2', 'G3', 'OP', 'Listed'}


def interpret_competitiveness(stdev: float) -> str:
    if stdev < 4:
        return "非常に混戦"
    elif stdev < 6:
        return "やや混戦"
    elif stdev < 8:
        return "標準的"
    return "力差明確"


def _fetch_grade_from_db(race_id: str) -> dict:
    """DBのRACE_SHOSAIからgrade/age_classを取得"""
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
                race_class = race.get('race_name', '')  # for display
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

                # gradeが依然空ならスキップ（障害競走等）
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

                # 年齢クラス: DB fallback優先、なければentries.ageから推定
                age_class = db_age_class if db_age_class else _detect_age_class(race)

                results.append({
                    'race_id': race_id,
                    'grade': grade,
                    'ratings': ratings,
                    'track': track_type,
                    'month': month,
                    'age_class': age_class,
                    'venue_name': race.get('venue_name', ''),
                })
                year_count += 1

            except (json.JSONDecodeError, KeyError, TypeError):
                continue

        if year_count:
            print(f"  [{year_dir.name}] {year_count:,} races with ratings")

    print(f"\n  Total: {len(results):,} races")
    print(f"  No keibabook: {no_kb:,}, No ratings: {no_ratings:,}")
    if db_补完 > 0:
        print(f"  DB grade fallback: {db_补完:,} races")

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
        if grade in AGE_SEPARATED_GRADES and age_class:
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


def build_race_level_index(races: list, grade_stats: dict) -> dict:
    """各レースのレベル指標を算出

    grade_statsのクラス別平均をベースラインとして、
    各レースの出走馬平均レイティングとの差でH/M/Lを判定。
    """
    # グレードキー→ベースライン(mean, stdev)のマッピング
    baselines = {}
    for key, stats in grade_stats.items():
        baselines[key] = (stats['rating']['mean'], stats['rating']['stdev'])

    def _get_baseline(grade: str, age_class: str):
        # 年齢分離グレードはage_class付きキーで引く
        if grade in AGE_SEPARATED_GRADES and age_class:
            key = f"{grade}_{age_class}"
            if key in baselines:
                return baselines[key]
        if grade in baselines:
            return baselines[grade]
        return None

    index = {}
    h_count = m_count = l_count = 0

    for race in races:
        race_id = race.get('race_id', '')
        if not race_id:
            continue

        ratings = race['ratings']
        avg_rating = statistics.mean(ratings)
        max_rating = max(ratings)

        baseline = _get_baseline(race['grade'], race['age_class'])
        if baseline is None:
            continue

        class_mean, class_stdev = baseline
        level_vs_class = avg_rating - class_mean

        # H/M/L判定: ±0.5σ
        if class_stdev > 0:
            if level_vs_class > class_stdev * 0.5:
                level_rank = 'H'
                h_count += 1
            elif level_vs_class < -class_stdev * 0.5:
                level_rank = 'L'
                l_count += 1
            else:
                level_rank = 'M'
                m_count += 1
        else:
            level_rank = 'M'
            m_count += 1

        index[race_id] = {
            'avg_rating': round(avg_rating, 1),
            'max_rating': round(max_rating, 1),
            'num_rated': len(ratings),
            'class_baseline': round(class_mean, 1),
            'level_vs_class': round(level_vs_class, 1),
            'level_rank': level_rank,
        }

    total = h_count + m_count + l_count
    if total > 0:
        print(f"  H: {h_count:,} ({h_count/total*100:.1f}%)")
        print(f"  M: {m_count:,} ({m_count/total*100:.1f}%)")
        print(f"  L: {l_count:,} ({l_count/total*100:.1f}%)")

    return index


def analyze_venue_stats(races: list) -> dict:
    """会場別レイティング統計（芝/ダート別）"""
    by_venue = defaultdict(list)
    for race in races:
        venue = race.get('venue_name', '')
        track = race.get('track', '')
        if not venue or not track:
            continue
        key = f"{venue}_{track}"
        by_venue[key].extend(race['ratings'])

    result = {}
    for key in sorted(by_venue.keys()):
        ratings = by_venue[key]
        if len(ratings) < 20:
            continue
        result[key] = {
            'horse_count': len(ratings),
            'mean': round(statistics.mean(ratings), 2),
            'stdev': round(statistics.stdev(ratings), 2) if len(ratings) > 1 else 0,
            'median': round(statistics.median(ratings), 2),
        }
    return result


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

    # レースレベルインデックス
    print("\n[STEP 5] Building race level index...")
    race_level_index = build_race_level_index(races, grade_stats)
    print(f"  Total: {len(race_level_index):,} races indexed")

    # 会場別統計
    print("\n[STEP 6] Analyzing venue statistics...")
    venue_stats = analyze_venue_stats(races)
    for key, vs in venue_stats.items():
        print(f"    [{key}] mean={vs['mean']:.1f}, n={vs['horse_count']:,}")

    # 出力
    standards = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "source": "data3/races + data3/keibabook (v3 native)",
            "years": f"{args.since}-{datetime.now().year}",
            "total_races": len(races),
            "version": "4.0",
        },
        "by_grade": grade_stats,
        "competitiveness_thresholds": comp_thresholds,
        "maiden_by_season": maiden_season_stats,
        "venue_stats": venue_stats,
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

    # race_level_index.json を indexes/ に保存
    index_path = config.data_root() / "indexes" / "race_level_index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(
        json.dumps(race_level_index, ensure_ascii=False, separators=(',', ':')),
        encoding='utf-8',
    )
    index_size = index_path.stat().st_size / 1024 / 1024

    print(f"\n{'=' * 70}")
    print(f"[OK] Standards saved: {output_path}")
    print(f"  Grades: {len(grade_stats)}, Total races: {len(races)}")
    print(f"[OK] Race level index: {index_path} ({index_size:.1f} MB)")
    print(f"  Indexed: {len(race_level_index):,} races")
    return 0


if __name__ == "__main__":
    exit(main())
