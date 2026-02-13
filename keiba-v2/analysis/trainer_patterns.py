#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
調教師パターン分析スクリプト (v2)

data3/keibabook（cyokyo_detail）と data3/races（着順）を結合し、
調教師別の好走パターンを統計的に分析します。

v1の collect_trainer_training_history.py + analyze_trainer_patterns.py を統合。
cyokyo_detailのリッチデータ（タイム＋脚色＋併せ馬等）を活用。

Usage:
    python -m analysis.trainer_patterns
    python -m analysis.trainer_patterns --since 2023
"""

import argparse
import json
import math
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config


# ========================================================================
# 調教特徴量抽出
# ========================================================================

def extract_oikiri_session(sessions: list) -> Optional[dict]:
    """追い切りセッション（最終追切）を抽出"""
    # is_oikiri=trueを探す。なければ最後のセッションで times が有効なもの
    for s in sessions:
        if s.get('is_oikiri'):
            return s
    # フォールバック: 最後のセッションでtimesがあるもの
    for s in reversed(sessions):
        times = s.get('times', {})
        if times and any(v for v in times.values() if v):
            return s
    return None


def extract_weekend_session(sessions: list) -> Optional[dict]:
    """土日追切セッションを抽出（■ or ◇マーク）"""
    for s in sessions:
        date_str = s.get('date', '')
        if date_str in ('■', '◇'):
            return s
    return None


def classify_course(course: str) -> str:
    """コース名を分類"""
    if not course:
        return ''
    if '坂' in course:
        return '坂'
    if 'Ｗ' in course or 'ウ' in course or 'W' in course:
        return 'コ'
    if '芝' in course:
        return '芝'
    if 'ダ' in course or 'Ｄ' in course:
        return 'ダ'
    if 'Ｃ' in course or 'Ｂ' in course or 'ポ' in course:
        return 'コ'
    return ''


def classify_acceleration(times: dict) -> str:
    """ラップの加速/減速を判定"""
    t3f = times.get('3f')
    t1f = times.get('1f')
    if t3f is None or t1f is None:
        return ''
    # 3Fの平均1Fと最終1Fを比較
    avg_1f_in_3f = t3f / 3
    if t1f < avg_1f_in_3f * 0.97:
        return '+'  # 加速
    elif t1f > avg_1f_in_3f * 1.03:
        return '-'  # 減速
    return '='  # イーブン


def classify_lap_grade(times: dict) -> str:
    """タイムからラップグレードを分類（A+/A=/A-/B+等）"""
    t4f = times.get('half_mile')  # 4F = half_mile
    t1f = times.get('1f')
    if t4f is None:
        return ''

    # 4F基準で大まかな分類
    if t4f <= 50.0:
        base = 'S'
    elif t4f <= 52.0:
        base = 'A'
    elif t4f <= 54.0:
        base = 'B'
    elif t4f <= 56.0:
        base = 'C'
    else:
        base = 'D'

    # 加速度で+/=/- を付与
    acc = classify_acceleration(times)
    if acc == '+':
        return f'{base}+'
    elif acc == '-':
        return f'{base}-'
    return f'{base}='


def has_good_time(times: dict, course: str) -> bool:
    """好タイム判定（コース別基準）"""
    t4f = times.get('half_mile')
    if t4f is None:
        return False
    loc = classify_course(course)
    if loc == '坂':
        return t4f <= 53.0
    elif loc == 'コ':
        return t4f <= 52.0
    return t4f <= 53.0


def extract_training_features(cyokyo_detail: dict) -> Optional[dict]:
    """cyokyo_detailから調教特徴量を抽出"""
    sessions = cyokyo_detail.get('sessions', [])
    if not sessions:
        return None

    oikiri = extract_oikiri_session(sessions)
    weekend = extract_weekend_session(sessions)

    if not oikiri:
        return None

    oikiri_times = oikiri.get('times', {})
    oikiri_course = oikiri.get('course', '')

    features = {
        'final_lap': classify_lap_grade(oikiri_times),
        'final_location': classify_course(oikiri_course),
        'final_time_4f': oikiri_times.get('half_mile'),
        'final_1f': oikiri_times.get('1f'),
        'final_acceleration': classify_acceleration(oikiri_times),
        'final_has_good_time': has_good_time(oikiri_times, oikiri_course),
        'final_intensity': oikiri.get('intensity', ''),
        'final_awase': oikiri.get('awase') is not None,
        'session_count': len(sessions),
    }

    if weekend:
        wk_times = weekend.get('times', {})
        wk_course = weekend.get('course', '')
        features['weekend_lap'] = classify_lap_grade(wk_times)
        features['weekend_location'] = classify_course(wk_course)
        features['weekend_has_good_time'] = has_good_time(wk_times, wk_course)
    else:
        features['weekend_lap'] = ''
        features['weekend_location'] = ''
        features['weekend_has_good_time'] = False

    return features


# ========================================================================
# パターン定義（v1の15パターンを移植 + v2拡張）
# ========================================================================

PATTERNS = [
    {
        'name': '好タイム+加速ラップ',
        'check': lambda f: f['final_has_good_time'] and f['final_acceleration'] == '+',
    },
    {
        'name': 'S評価以上',
        'check': lambda f: f['final_lap'].startswith('S'),
    },
    {
        'name': '坂路+加速',
        'check': lambda f: f['final_location'] == '坂' and f['final_acceleration'] == '+',
    },
    {
        'name': 'コース+好タイム',
        'check': lambda f: f['final_location'] == 'コ' and f['final_has_good_time'],
    },
    {
        'name': '坂路+好タイム',
        'check': lambda f: f['final_location'] == '坂' and f['final_has_good_time'],
    },
    {
        'name': '坂路+S評価',
        'check': lambda f: f['final_location'] == '坂' and f['final_lap'].startswith('S'),
    },
    {
        'name': 'コース+加速',
        'check': lambda f: f['final_location'] == 'コ' and f['final_acceleration'] == '+',
    },
    {
        'name': '土日好タイム→最終追切',
        'check': lambda f: f['weekend_has_good_time'],
    },
    {
        'name': '土日坂路+加速',
        'check': lambda f: f['weekend_location'] == '坂' and f['weekend_lap'].endswith('+'),
    },
    {
        'name': '土日S評価→最終追切',
        'check': lambda f: f['weekend_lap'].startswith('S'),
    },
    # v2拡張: cyokyo_detail固有のデータ
    {
        'name': '併せ馬追切',
        'check': lambda f: f['final_awase'],
    },
    {
        'name': '強め追い+加速',
        'check': lambda f: '強め' in f.get('final_intensity', '') and f['final_acceleration'] == '+',
    },
]


# ========================================================================
# データ収集
# ========================================================================

def collect_history(since_year: int) -> dict:
    """data3/races + data3/keibabook から調教師別の調教×着順履歴を収集"""
    races_dir = config.races_dir()
    kb_dir = config.keibabook_dir()

    trainer_history = defaultdict(lambda: {'records': [], 'name': '', 'total': 0})
    matched = 0
    no_training = 0

    print(f"  Races: {races_dir}")
    print(f"  Keibabook: {kb_dir}")

    for year_dir in sorted(races_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        try:
            year = int(year_dir.name)
            if year < since_year:
                continue
        except ValueError:
            continue

        year_matched = 0
        for race_file in year_dir.rglob("race_[0-9]*.json"):
            try:
                with open(race_file, 'r', encoding='utf-8') as f:
                    race = json.load(f)

                race_id = race['race_id']
                race_date = race.get('date', '')

                # 対応するkb_extを探す
                date_parts = race_date.split('-')
                if len(date_parts) != 3:
                    continue
                kb_path = kb_dir / date_parts[0] / date_parts[1] / date_parts[2] / f"kb_ext_{race_id}.json"
                if not kb_path.exists():
                    continue

                with open(kb_path, 'r', encoding='utf-8') as f:
                    kb_ext = json.load(f)

                for entry in race.get('entries', []):
                    finish = entry.get('finish_position', 0)
                    if finish <= 0:
                        continue

                    trainer_code = entry.get('trainer_code', '')
                    trainer_name = entry.get('trainer_name', '')
                    ketto_num = entry.get('ketto_num', '')
                    umaban = str(entry.get('umaban', ''))

                    if not trainer_code or not umaban:
                        continue

                    # kb_extからこの馬のデータを取得
                    kb_entry = kb_ext.get('entries', {}).get(umaban, {})
                    cyokyo_detail = kb_entry.get('cyokyo_detail')

                    if not cyokyo_detail:
                        no_training += 1
                        continue

                    features = extract_training_features(cyokyo_detail)
                    if not features:
                        no_training += 1
                        continue

                    record = {
                        'race_date': race_date,
                        'race_id': race_id,
                        'ketto_num': ketto_num,
                        'horse_name': entry.get('horse_name', ''),
                        'finish': finish,
                        'odds': entry.get('odds', 0),
                        'popularity': entry.get('popularity', 0),
                        'training': features,
                    }

                    trainer_history[trainer_code]['records'].append(record)
                    trainer_history[trainer_code]['name'] = trainer_name
                    matched += 1
                    year_matched += 1

            except (json.JSONDecodeError, KeyError, TypeError):
                continue

        print(f"  [{year}] {year_matched:,} records matched")

    print(f"\n  Total matched: {matched:,}")
    print(f"  No training data: {no_training:,}")
    print(f"  Trainers: {len(trainer_history)}")

    return dict(trainer_history)


# ========================================================================
# パターン分析
# ========================================================================

def analyze_patterns(trainer_history: dict) -> dict:
    """調教師別のパターン分析"""
    results = {}
    total_patterns = 0

    for trainer_code, data in trainer_history.items():
        records = data['records']
        if len(records) < 20:
            continue

        # 全体統計
        finishes = [r['finish'] for r in records]
        wins = sum(1 for f in finishes if f == 1)
        top3 = sum(1 for f in finishes if f <= 3)
        n = len(finishes)

        overall_win_rate = wins / n
        overall_top3_rate = top3 / n

        # 各パターンの検出
        best_patterns = []

        for pattern in PATTERNS:
            matching = [r for r in records if pattern['check'](r['training'])]
            if len(matching) < 8:
                continue

            p_finishes = [r['finish'] for r in matching]
            p_wins = sum(1 for f in p_finishes if f == 1)
            p_top3 = sum(1 for f in p_finishes if f <= 3)
            p_n = len(matching)

            p_win_rate = p_wins / p_n
            p_top3_rate = p_top3 / p_n
            lift = p_top3_rate - overall_top3_rate

            if p_top3_rate < 0.25 or lift < 0.05:
                continue

            score = p_top3_rate * math.sqrt(p_n) * max(lift, 0.01)

            best_patterns.append({
                'name': pattern['name'],
                'win_rate': round(p_win_rate, 4),
                'top3_rate': round(p_top3_rate, 4),
                'sample_size': p_n,
                'lift': round(lift, 4),
                'score': round(score, 4),
            })

        # スコア順でtop5
        best_patterns.sort(key=lambda x: x['score'], reverse=True)
        best_patterns = best_patterns[:5]

        if not best_patterns:
            continue

        total_patterns += len(best_patterns)

        results[trainer_code] = {
            'name': data['name'],
            'total_runners': n,
            'overall_stats': {
                'win_rate': round(overall_win_rate, 4),
                'top3_rate': round(overall_top3_rate, 4),
                'avg_finish': round(statistics.mean(finishes), 1),
            },
            'best_patterns': best_patterns,
        }

    print(f"\n  Trainers with patterns: {len(results)}")
    print(f"  Total patterns found: {total_patterns}")
    return results


def main():
    parser = argparse.ArgumentParser(description="Trainer Pattern Analyzer (v2)")
    parser.add_argument("--since", type=int, default=2023, help="Start year (default: 2023)")
    output_default = str(config.data_root() / "analysis" / "trainer_patterns.json")
    parser.add_argument("--output", type=str, default=output_default)
    args = parser.parse_args()

    print("=" * 70)
    print("Trainer Pattern Analyzer (v2)")
    print("=" * 70)
    print(f"Since: {args.since}")
    print(f"Output: {args.output}")
    print()

    # Collect
    print("[STEP 1] Collecting trainer training history...")
    history = collect_history(args.since)

    if not history:
        print("[ERROR] No data collected")
        return 1

    # Analyze
    print("\n[STEP 2] Analyzing patterns...")
    results = analyze_patterns(history)

    # Save
    output_data = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "source": "data3/races + data3/keibabook (cyokyo_detail)",
            "since": args.since,
            "total_trainers": len(results),
            "version": "2.0",
        },
        "trainers": results,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 70}")
    print(f"[OK] Patterns saved: {output_path}")

    # Top trainers by pattern score
    if results:
        print("\nTop 5 trainers by best pattern score:")
        top = sorted(results.items(),
                     key=lambda x: x[1]['best_patterns'][0]['score'] if x[1]['best_patterns'] else 0,
                     reverse=True)[:5]
        for code, data in top:
            bp = data['best_patterns'][0]
            print(f"  {data['name']} ({code}): {bp['name']} "
                  f"top3={bp['top3_rate']:.1%} lift=+{bp['lift']:.1%} n={bp['sample_size']}")

    return 0


if __name__ == "__main__":
    exit(main())
