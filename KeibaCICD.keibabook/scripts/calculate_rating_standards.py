#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
レイティング基準値算出スクリプト

競馬ブックのデータからクラス別レイティング統計を算出し、
レースレベル・混戦度の判定基準を生成します。

JRA-VANのグレードマスター（race_grades.json）が存在する場合は、
それを使用して正確なグレード分類を行います。

Usage:
    python calculate_rating_standards.py
    python calculate_rating_standards.py --since 2023
    python calculate_rating_standards.py --output data/rating_standards.json
"""

import argparse
import json
import os
import statistics
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 環境変数読み込み
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# グレードマスターのパス（DATA_ROOT/target配下）
GRADE_MASTER_PATH = Path(os.getenv('KEIBA_DATA_ROOT_DIR', 'C:/KEIBA-CICD/data2')) / "target" / "grade_master.json"


class GradeMatcher:
    """重賞レース名からグレードを判定"""
    
    def __init__(self):
        self.g1_keywords = []
        self.g2_keywords = []
        self.g3_keywords = []
        self._load_master()
    
    def _load_master(self):
        if not GRADE_MASTER_PATH.exists():
            print(f"  [WARN] Grade master not found: {GRADE_MASTER_PATH}")
            return
        
        try:
            with open(GRADE_MASTER_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            self.g1_keywords = [k.upper() for k in data.get('g1_races', [])]
            self.g2_keywords = [k.upper() for k in data.get('g2_races', [])]
            self.g3_keywords = [k.upper() for k in data.get('g3_races', [])]
            
            print(f"  [OK] Loaded grade master: G1={len(self.g1_keywords)}, G2={len(self.g2_keywords)}, G3={len(self.g3_keywords)} keywords")
        except Exception as e:
            print(f"  [ERROR] Failed to load grade master: {e}")
    
    def match(self, race_name: str, race_condition: str = "") -> str:
        """レース名・条件からグレードを判定"""
        # 検索対象を大文字に統一
        text = (race_name + " " + race_condition).upper()
        
        # G1チェック
        for keyword in self.g1_keywords:
            if keyword in text:
                return "G1"
        
        # G2チェック
        for keyword in self.g2_keywords:
            if keyword in text:
                return "G2"
        
        # G3チェック
        for keyword in self.g3_keywords:
            if keyword in text:
                return "G3"
        
        return ""


def load_grade_master() -> GradeMatcher:
    """グレードマスターを読み込む"""
    return GradeMatcher()


@dataclass
class RaceRatingInfo:
    """レースのレイティング情報"""
    race_id: str
    date: str
    grade: str
    race_name: str
    ratings: List[float]
    track: str = ""      # 芝/ダ
    month: int = 0       # 月（1-12）
    age_class: str = ""  # 2歳/3歳
    
    @property
    def mean(self) -> float:
        return statistics.mean(self.ratings) if self.ratings else 0
    
    @property
    def stdev(self) -> float:
        return statistics.stdev(self.ratings) if len(self.ratings) > 1 else 0
    
    @property
    def top3_diff(self) -> float:
        """上位3頭と4位の差（混戦度指標）"""
        if len(self.ratings) < 4:
            return 0
        sorted_ratings = sorted(self.ratings, reverse=True)
        return sorted_ratings[0] - sorted_ratings[3]


def extract_age_class(race_condition: str) -> str:
    """race_conditionから年齢クラスを抽出"""
    if not race_condition:
        return ""
    if '2歳' in race_condition:
        return '2歳'
    if '3歳' in race_condition:
        return '3歳'
    return ""


def extract_month_from_date(date_str: str) -> int:
    """日付から月を抽出"""
    if not date_str:
        return 0
    try:
        # "2024/06/01" or "2024-06-01" 形式
        parts = date_str.replace('-', '/').split('/')
        if len(parts) >= 2:
            return int(parts[1])
    except (ValueError, IndexError):
        pass
    return 0


def get_maiden_season(age_class: str, month: int) -> str:
    """未勝利戦のシーズン区分を取得"""
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


def extract_grade_from_condition(race_condition: str) -> str:
    """race_conditionからグレードを抽出"""
    if not race_condition:
        return ""
    
    cond = race_condition.strip()
    
    # G1/G2/G3
    if 'GI' in cond or 'G1' in cond or 'Ｇ１' in cond:
        return 'G1'
    elif 'GII' in cond or 'G2' in cond or 'Ｇ２' in cond:
        return 'G2'
    elif 'GIII' in cond or 'G3' in cond or 'Ｇ３' in cond:
        return 'G3'
    
    # クラス条件
    if '未勝利' in cond:
        return '未勝利'
    elif '新馬' in cond:
        return '新馬'
    elif '1勝クラス' in cond or '１勝クラス' in cond or '500万' in cond:
        return '1勝クラス'
    elif '2勝クラス' in cond or '２勝クラス' in cond or '1000万' in cond:
        return '2勝クラス'
    elif '3勝クラス' in cond or '３勝クラス' in cond or '1600万' in cond:
        return '3勝クラス'
    elif 'オープン' in cond or 'OP' in cond:
        return 'OP'
    elif 'リステッド' in cond:
        return 'OP'  # リステッドはオープン扱い
    
    return ""


def normalize_grade(grade: str, race_condition: str = "") -> str:
    """グレード名を正規化（race_conditionも参照）"""
    # まずrace_conditionから抽出を試みる
    extracted = extract_grade_from_condition(race_condition)
    if extracted:
        return extracted
    
    if not grade:
        return "未分類"
    
    grade = grade.strip()
    
    # G1/G2/G3
    if grade in ['G1', 'GI']:
        return 'G1'
    elif grade in ['G2', 'GII']:
        return 'G2'
    elif grade in ['G3', 'GIII']:
        return 'G3'
    elif grade in ['OP', 'オープン', 'L', 'リステッド']:
        return 'OP'
    elif grade in ['3勝', '3勝クラス', '1600万']:
        return '3勝クラス'
    elif grade in ['2勝', '2勝クラス', '1000万']:
        return '2勝クラス'
    elif grade in ['1勝', '1勝クラス', '500万']:
        return '1勝クラス'
    elif '新馬' in grade:
        return '新馬'
    elif '未勝利' in grade:
        return '未勝利'
    else:
        return grade


def parse_rating(rating_str) -> Optional[float]:
    """レイティング文字列を数値に変換"""
    if rating_str is None:
        return None
    
    # 文字列に変換
    s = str(rating_str).strip()
    if not s or s == '-' or s == '---':
        return None
    
    # 全角→半角
    z2h = str.maketrans('０１２３４５６７８９．', '0123456789.')
    s = s.translate(z2h)
    
    try:
        value = float(s)
        # 妥当な範囲チェック (30-150程度)
        if 30 <= value <= 150:
            return value
        return None
    except (ValueError, TypeError):
        return None


def scan_integrated_files(data_root: Path, since_year: int, grade_matcher: GradeMatcher = None) -> List[RaceRatingInfo]:
    """integrated JSONファイルをスキャン"""
    results = []
    grade_matcher = grade_matcher or GradeMatcher()
    
    # integrated/ または races/ ディレクトリを探索
    search_dirs = [
        data_root / "integrated",
        data_root / "races",
    ]
    
    for base_dir in search_dirs:
        if not base_dir.exists():
            continue
        
        print(f"  Scanning: {base_dir}")
        
        # 年別ディレクトリを探索
        for year_dir in base_dir.iterdir():
            if not year_dir.is_dir():
                continue
            
            year_name = year_dir.name
            try:
                # 年ディレクトリの形式チェック (2024, 202401, 2024-01 など)
                year_num = int(year_name[:4])
                if year_num < since_year:
                    continue
            except (ValueError, IndexError):
                continue
            
            # JSONファイルを探索
            json_files = list(year_dir.rglob("integrated_*.json"))
            if not json_files:
                json_files = list(year_dir.rglob("*.json"))
            
            for json_file in json_files:
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    
                    race_info = data.get('race_info', {})
                    entries = data.get('entries', [])
                    
                    if not entries:
                        continue
                    
                    # レイティング収集
                    ratings = []
                    for entry in entries:
                        # entry_dataの中にratingがある場合と、直接ratingがある場合に対応
                        entry_data = entry.get('entry_data', {})
                        rating_value = entry_data.get('rating') or entry.get('rating')
                        rating = parse_rating(rating_value)
                        if rating is not None:
                            ratings.append(rating)
                    
                    if len(ratings) < 3:  # 最低3頭必要
                        continue
                    
                    race_id = data.get('metadata', {}).get('race_id', '') or race_info.get('race_id', '')
                    date = race_info.get('date', '')
                    race_condition = race_info.get('race_condition', '')
                    race_name = race_info.get('race_name', '')
                    track = race_info.get('track', '')  # 芝/ダ
                    
                    # 月と年齢クラスを抽出
                    month = extract_month_from_date(date)
                    age_class = extract_age_class(race_condition)
                    
                    # グレード判定: 1. グレードマスター → 2. race_condition → 3. grade フィールド
                    matched_grade = grade_matcher.match(race_name, race_condition)
                    if matched_grade:
                        grade = matched_grade
                    else:
                        grade = normalize_grade(race_info.get('grade', ''), race_condition)
                    
                    results.append(RaceRatingInfo(
                        race_id=race_id,
                        date=date,
                        grade=grade,
                        race_name=race_name,
                        ratings=ratings,
                        track=track,
                        month=month,
                        age_class=age_class,
                    ))
                    
                except (json.JSONDecodeError, KeyError, TypeError) as e:
                    continue
    
    return results


def calculate_grade_stats(races: List[RaceRatingInfo]) -> Dict:
    """クラス別の統計を算出"""
    by_grade = defaultdict(list)
    
    for race in races:
        by_grade[race.grade].append(race)
    
    stats = {}
    for grade, grade_races in sorted(by_grade.items(), key=lambda x: grade_sort_key(x[0])):
        all_ratings = []
        all_means = []
        all_stdevs = []
        all_top3_diffs = []
        
        for race in grade_races:
            all_ratings.extend(race.ratings)
            all_means.append(race.mean)
            all_stdevs.append(race.stdev)
            all_top3_diffs.append(race.top3_diff)
        
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


def grade_sort_key(grade: str) -> int:
    """グレードのソート順"""
    order = {
        'G1': 0, 'G2': 1, 'G3': 2, 'OP': 3,
        '3勝クラス': 4, '2勝クラス': 5, '1勝クラス': 6,
        '新馬': 7, '未勝利': 8, '未分類': 99,
    }
    return order.get(grade, 50)


def interpret_competitiveness(stdev: float) -> str:
    """混戦度の解釈"""
    if stdev < 4:
        return "非常に混戦"
    elif stdev < 6:
        return "やや混戦"
    elif stdev < 8:
        return "標準的"
    else:
        return "力差明確"


def calculate_competitiveness_thresholds(races: List[RaceRatingInfo]) -> Dict:
    """混戦度の閾値を算出"""
    all_stdevs = [race.stdev for race in races if race.stdev > 0]
    all_top3_diffs = [race.top3_diff for race in races if race.top3_diff > 0]
    
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
        "top3_diff": {
            "mean": round(statistics.mean(all_top3_diffs), 2) if all_top3_diffs else 0,
            "description": "上位3頭と4位のレイティング差",
        },
    }


def analyze_maiden_by_season(races: List[RaceRatingInfo]) -> Dict:
    """未勝利戦のシーズン別・コース別分析"""
    # 未勝利戦のみ抽出（trackが有効なもののみ）
    maiden_races = [r for r in races if r.grade == '未勝利' and r.track in ['芝', 'ダ']]
    
    if not maiden_races:
        return {}
    
    # シーズン×コース別に分類
    categories = defaultdict(list)
    
    for race in maiden_races:
        season = get_maiden_season(race.age_class, race.month)
        if not season:
            continue
        
        # コース別（芝/ダート）- ここでは有効なもののみ
        track = race.track
        
        # カテゴリキー
        key = f"{season}_{track}"
        categories[key].append(race)
    
    # 各カテゴリの統計を算出
    result = {}
    
    for key, cat_races in categories.items():
        all_ratings = []
        for race in cat_races:
            all_ratings.extend(race.ratings)
        
        if len(all_ratings) < 10:
            continue
        
        mean_rating = statistics.mean(all_ratings)
        stdev_rating = statistics.stdev(all_ratings) if len(all_ratings) > 1 else 0
        
        result[key] = {
            "sample_count": len(cat_races),
            "horse_count": len(all_ratings),
            "rating": {
                "mean": round(mean_rating, 2),
                "stdev": round(stdev_rating, 2),
                "median": round(statistics.median(all_ratings), 2),
                "min": round(min(all_ratings), 2),
                "max": round(max(all_ratings), 2),
            },
        }
    
    # シーズン順にソート（芝→ダの順で交互に）
    season_order = [
        '2歳未勝利_6-8月_芝', '2歳未勝利_6-8月_ダ',
        '2歳未勝利_9-12月_芝', '2歳未勝利_9-12月_ダ',
        '3歳未勝利_1-3月_芝', '3歳未勝利_1-3月_ダ',
        '3歳未勝利_4-6月_芝', '3歳未勝利_4-6月_ダ',
        '3歳未勝利_7-9月_芝', '3歳未勝利_7-9月_ダ',
    ]
    
    sorted_result = {}
    for key in season_order:
        if key in result:
            sorted_result[key] = result[key]
    
    # 統計情報を追加
    total_races = sum(v['sample_count'] for v in result.values())
    print(f"  [OK] 有効なデータ: {total_races} races (track不明は除外)")
    
    return sorted_result


def main():
    parser = argparse.ArgumentParser(
        description="Calculate rating standards from keibabook data"
    )
    parser.add_argument(
        "--since",
        type=int,
        default=2024,
        help="Start year (default: 2024)"
    )
    default_output = str(
        Path(os.getenv('KEIBA_DATA_ROOT_DIR', 'C:/KEIBA-CICD/data2')) / "keibabook" / "rating_standards.json"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=default_output,
        help="Output file path"
    )
    parser.add_argument(
        "--data-root",
        type=str,
        default=None,
        help="Data root directory (default: DATA_ROOTenv var)"
    )
    
    args = parser.parse_args()
    
    # データルート決定
    if args.data_root:
        data_root = Path(args.data_root)
    else:
        data_root = Path(os.getenv('KEIBA_DATA_ROOT_DIR', './data'))
    
    print("=" * 70)
    print("Rating Standards Calculator")
    print("=" * 70)
    print(f"Data root: {data_root}")
    print(f"Since: {args.since}")
    print(f"Output: {args.output}")
    print()
    
    if not data_root.exists():
        print(f"[ERROR] Data root not found: {data_root}")
        return 1
    
    # グレードマスター読み込み
    print("[STEP 0] Loading grade master...")
    grade_matcher = load_grade_master()
    
    # データスキャン
    print("\n[STEP 1] Scanning integrated files...")
    races = scan_integrated_files(data_root, args.since, grade_matcher)
    print(f"  Found {len(races)} races with rating data")
    
    if not races:
        print("[ERROR] No valid data found")
        return 1
    
    # クラス別統計
    print("\n[STEP 2] Calculating grade statistics...")
    grade_stats = calculate_grade_stats(races)
    
    for grade, stats in grade_stats.items():
        print(f"  [{grade}] {stats['sample_count']} races, "
              f"mean={stats['rating']['mean']:.1f}, "
              f"stdev={stats['rating']['stdev']:.1f}")
    
    # 混戦度閾値
    print("\n[STEP 3] Calculating competitiveness thresholds...")
    comp_thresholds = calculate_competitiveness_thresholds(races)
    
    # 未勝利戦シーズン別分析
    print("\n[STEP 4] Analyzing maiden races by season...")
    maiden_season_stats = analyze_maiden_by_season(races)
    
    if maiden_season_stats:
        print("  未勝利戦シーズン別レイティング:")
        for key, stats in maiden_season_stats.items():
            print(f"    [{key}] {stats['sample_count']} races, "
                  f"mean={stats['rating']['mean']:.1f}")
    else:
        print("  [INFO] No maiden race data found")
    
    # 出力
    current_year = datetime.now().year
    standards = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "source": "keibabook integrated data",
            "years": f"{args.since}-{current_year}",
            "total_races": len(races),
            "description": "Rating standards by grade class",
        },
        "by_grade": grade_stats,
        "competitiveness_thresholds": comp_thresholds,
        "maiden_by_season": maiden_season_stats,
    }
    
    # 出力ディレクトリ作成
    output_path = Path(args.output)
    if not output_path.is_absolute():
        # 相対パスの場合、スクリプトの親ディレクトリを基準にする
        output_path = Path(__file__).parent.parent / args.output
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(standards, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 70)
    print(f"[OK] Standards saved: {output_path}")
    print(f"  Grades: {len(grade_stats)}")
    print(f"  Total races: {len(races)}")
    
    return 0


if __name__ == "__main__":
    exit(main())
