#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
調教分析スクリプト v1.0

training_summary.json (CK_DATA由来) + kb_ext (cyokyo_detail) + race結果を統合し、
調教指標別の好走率・勝率を統計分析します。

出力:
  1. overall: 全体の調教指標別パフォーマンス (Tab1: 調教分析)
  2. trainers: 調教師別パターン分析 (Tab2: 調教×調教師分析)

Usage:
    python -m analysis.training_analysis
    python -m analysis.training_analysis --since 2023
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
# 定数
# ========================================================================

# lapRankの順序 (好成績→悪成績)
LAP_RANK_ORDER = ['SS', 'S+', 'S=', 'S-', 'A+', 'A=', 'A-', 'B+', 'B=', 'B-', 'C+', 'C=', 'C-', 'D+', 'D=', 'D-']

# 脚色分類マッピング
INTENSITY_MAP = {
    '一杯に追う': '一杯',
    '叩き一杯': '一杯',
    '末強め追う': '末強め',
    '末強めに追う': '末強め',
    '強めに追う': '強め',
    '強め追う': '強め',
    'G前仕掛け': '強め',
    '馬なり余力': '馬なり',
    '馬なり': '馬なり',
    'ゲートなり': 'ゲートなり',
}

# 人気帯
POPULARITY_BUCKETS = {
    '1-3': (1, 3),
    '4-6': (4, 6),
    '7-9': (7, 9),
    '10+': (10, 99),
}

# パターン定義 (調教師分析用)
PATTERNS = [
    {
        'name': '好タイム+加速ラップ',
        'conditions': {'hasGoodTime': True, 'acceleration': '+'},
        'check': lambda r: r.get('has_good_time') and r.get('acceleration') == '+',
    },
    {
        'name': 'S評価以上',
        'conditions': {'finalLapClassGroup': ['SS', 'S+', 'S=', 'S-']},
        'check': lambda r: r.get('lapRank', '').startswith('S'),
    },
    {
        'name': '坂路+加速',
        'conditions': {'finalLocation': '坂', 'acceleration': '+'},
        'check': lambda r: r.get('finalLocation') == '坂' and r.get('acceleration') == '+',
    },
    {
        'name': 'コース+好タイム',
        'conditions': {'finalLocation': 'コ', 'hasGoodTime': True},
        'check': lambda r: r.get('finalLocation') == 'コ' and r.get('has_good_time'),
    },
    {
        'name': '坂路+好タイム',
        'conditions': {'finalLocation': '坂', 'hasGoodTime': True},
        'check': lambda r: r.get('finalLocation') == '坂' and r.get('has_good_time'),
    },
    {
        'name': '坂路+S評価',
        'conditions': {'finalLocation': '坂', 'finalLapClassGroup': ['SS', 'S+', 'S=', 'S-']},
        'check': lambda r: r.get('finalLocation') == '坂' and r.get('lapRank', '').startswith('S'),
    },
    {
        'name': 'コース+加速',
        'conditions': {'finalLocation': 'コ', 'acceleration': '+'},
        'check': lambda r: r.get('finalLocation') == 'コ' and r.get('acceleration') == '+',
    },
    {
        'name': '土日好タイム',
        'conditions': {'weekendHasGoodTime': True},
        'check': lambda r: r.get('weekend_has_good_time'),
    },
    {
        'name': '土日坂路+加速',
        'conditions': {'weekendLocation': '坂', 'weekendAcceleration': '+'},
        'check': lambda r: r.get('weekendLocation') == '坂' and r.get('weekend_acceleration') == '+',
    },
    {
        'name': '併せ馬追切',
        'conditions': {'hasAwase': True},
        'check': lambda r: r.get('has_awase'),
    },
    {
        'name': '強め追い+加速',
        'conditions': {'intensity': '強め', 'acceleration': '+'},
        'check': lambda r: r.get('intensity') == '強め' and r.get('acceleration') == '+',
    },
    # CK_DATA新パターン
    {
        'name': 'タイムLv5+加速',
        'conditions': {'timeClass': 5, 'acceleration': '+'},
        'check': lambda r: r.get('timeLevel') == '5' and r.get('acceleration') == '+',
    },
    {
        'name': 'lapRank SS/S+',
        'conditions': {'finalLapClassGroup': ['SS', 'S+']},
        'check': lambda r: r.get('lapRank', '') in ('SS', 'S+'),
    },
]


# ========================================================================
# ヘルパー関数
# ========================================================================

def extract_acceleration(lap_str: str) -> str:
    """lapRank/finalLapから加速度を抽出: 'B+' -> '+', 'SS' -> '='"""
    if not lap_str:
        return ''
    if lap_str == 'SS':
        return '+'  # SSは加速を含むので+
    if lap_str.endswith('+'):
        return '+'
    if lap_str.endswith('-'):
        return '-'
    if lap_str.endswith('='):
        return '='
    return ''


def classify_intensity(raw: str) -> str:
    """脚色を5カテゴリに正規化"""
    if not raw:
        return ''
    for key, value in INTENSITY_MAP.items():
        if key in raw:
            return value
    return ''


def has_good_time(time4f: Optional[float], location: str) -> bool:
    """好タイム判定"""
    if time4f is None:
        return False
    if location == '坂':
        return time4f <= 53.0
    elif location == 'コ':
        return time4f <= 52.0
    return time4f <= 53.0


def popularity_bucket(pop: int) -> str:
    """人気帯を返す"""
    if pop <= 0:
        return ''
    for label, (lo, hi) in POPULARITY_BUCKETS.items():
        if lo <= pop <= hi:
            return label
    return '10+'


def compute_stats(records: list) -> dict:
    """レコード群から統計を計算"""
    n = len(records)
    if n == 0:
        return {'sample_size': 0, 'win_rate': 0, 'top3_rate': 0, 'top5_rate': 0, 'avg_finish': 0, 'avg_odds': 0}

    wins = sum(1 for r in records if r['finish'] == 1)
    top3 = sum(1 for r in records if r['finish'] <= 3)
    top5 = sum(1 for r in records if r['finish'] <= 5)
    finishes = [r['finish'] for r in records]
    odds_vals = [r['odds'] for r in records if r['odds'] and r['odds'] > 0]

    return {
        'sample_size': n,
        'win_rate': round(wins / n, 4),
        'top3_rate': round(top3 / n, 4),
        'top5_rate': round(top5 / n, 4),
        'avg_finish': round(statistics.mean(finishes), 1),
        'avg_odds': round(statistics.mean(odds_vals), 1) if odds_vals else 0,
    }


def compute_confidence(sample_size: int, lift: float) -> str:
    """信頼度判定"""
    if sample_size >= 50 and lift >= 0.05:
        return 'high'
    elif sample_size >= 20:
        return 'medium'
    return 'low'


def derive_tozai(records: list) -> str:
    """oikiri_courseから栗東/美浦を推定"""
    ritto = 0
    miho = 0
    for r in records:
        course = r.get('oikiri_course', '')
        if course.startswith('栗'):
            ritto += 1
        elif course.startswith('美'):
            miho += 1
    if ritto > miho:
        return '栗東'
    elif miho > ritto:
        return '美浦'
    return ''


# ========================================================================
# データ収集
# ========================================================================

def collect_records(since_year: int) -> List[dict]:
    """training_summary + race JSON + kb_ext を統合してレコード収集"""
    races_dir = config.races_dir()
    kb_dir = config.keibabook_dir()

    records = []
    no_summary = 0
    no_match = 0
    matched = 0

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

        # 日付ディレクトリを走査
        for month_dir in sorted(year_dir.iterdir()):
            if not month_dir.is_dir():
                continue
            for day_dir in sorted(month_dir.iterdir()):
                if not day_dir.is_dir():
                    continue

                # training_summary.json読み込み
                summary_path = day_dir / 'temp' / 'training_summary.json'
                if not summary_path.exists():
                    no_summary += 1
                    continue

                try:
                    with open(summary_path, 'r', encoding='utf-8') as f:
                        summary_data = json.load(f)
                except (json.JSONDecodeError, OSError):
                    continue

                summaries = summary_data.get('summaries', {})
                race_date = f"{year_dir.name}-{month_dir.name}-{day_dir.name}"

                # 同日のrace JSONを走査
                for race_file in sorted(day_dir.glob("race_[0-9]*.json")):
                    try:
                        with open(race_file, 'r', encoding='utf-8') as f:
                            race = json.load(f)
                    except (json.JSONDecodeError, OSError):
                        continue

                    race_id = race.get('race_id', '')

                    # kb_ext読み込み (oikiri_summary用)
                    kb_ext = None
                    date_parts = race_date.split('-')
                    if len(date_parts) == 3:
                        kb_path = kb_dir / date_parts[0] / date_parts[1] / date_parts[2] / f"kb_ext_{race_id}.json"
                        if kb_path.exists():
                            try:
                                with open(kb_path, 'r', encoding='utf-8') as f:
                                    kb_ext = json.load(f)
                            except (json.JSONDecodeError, OSError):
                                pass

                    for entry in race.get('entries', []):
                        finish = entry.get('finish_position', 0)
                        if finish <= 0:
                            continue

                        horse_name = entry.get('horse_name', '')
                        trainer_code = entry.get('trainer_code', '')
                        trainer_name = entry.get('trainer_name', '')
                        umaban = str(entry.get('umaban', ''))

                        if not horse_name or not trainer_code:
                            continue

                        # training_summaryからマッチ
                        ts = summaries.get(horse_name)
                        if not ts:
                            no_match += 1
                            continue

                        # CK_DATAの指標
                        lap_rank = ts.get('lapRank', '')
                        time_level = ts.get('timeRank', '')
                        final_location = ts.get('finalLocation', '')
                        final_lap = ts.get('finalLap', '')
                        final_time4f = ts.get('finalTime4F')
                        final_lap1 = ts.get('finalLap1')
                        weekend_location = ts.get('weekendLocation', '')
                        weekend_lap = ts.get('weekendLap', '')
                        weekend_time4f = ts.get('weekendTime4F')
                        week_ago_location = ts.get('weekAgoLocation', '')
                        week_ago_lap = ts.get('weekAgoLap', '')

                        # 加速度
                        acceleration = extract_acceleration(final_lap) if final_lap else extract_acceleration(lap_rank)
                        weekend_acc = extract_acceleration(weekend_lap)

                        # kb_extからoikiri_summary
                        oikiri_intensity_raw = ''
                        oikiri_has_awase = False
                        oikiri_course = ''
                        session_count = -1

                        if kb_ext:
                            kb_entry = kb_ext.get('entries', {}).get(umaban, {})
                            cyokyo = kb_entry.get('cyokyo_detail', {})
                            if cyokyo:
                                oikiri = cyokyo.get('oikiri_summary', {})
                                oikiri_intensity_raw = oikiri.get('oikiri_intensity', '')
                                oikiri_has_awase = oikiri.get('oikiri_has_awase', False)
                                oikiri_course = oikiri.get('oikiri_course', '')
                                session_count = oikiri.get('session_count', -1)

                        record = {
                            'race_date': race_date,
                            'race_id': race_id,
                            'horse_name': horse_name,
                            'ketto_num': entry.get('ketto_num', ''),
                            'trainer_code': trainer_code,
                            'trainer_name': trainer_name,
                            'finish': finish,
                            'odds': entry.get('odds', 0),
                            'popularity': entry.get('popularity', 0),
                            # CK_DATA指標
                            'lapRank': lap_rank,
                            'timeLevel': time_level,
                            'finalLocation': final_location,
                            'finalLap': final_lap,
                            'finalTime4F': final_time4f,
                            'finalLap1': final_lap1,
                            'acceleration': acceleration,
                            'weekendLocation': weekend_location,
                            'weekendLap': weekend_lap,
                            'weekendTime4F': weekend_time4f,
                            'weekend_acceleration': weekend_acc,
                            'weekAgoLocation': week_ago_location,
                            'weekAgoLap': week_ago_lap,
                            # keibabook指標
                            'oikiri_course': oikiri_course,
                            'intensity': classify_intensity(oikiri_intensity_raw),
                            'has_awase': oikiri_has_awase,
                            'session_count': session_count,
                            'has_good_time': has_good_time(final_time4f, final_location),
                            'weekend_has_good_time': has_good_time(weekend_time4f, weekend_location),
                        }

                        records.append(record)
                        matched += 1
                        year_matched += 1

        print(f"  [{year}] {year_matched:,} records")

    print(f"\n  Total records: {matched:,}")
    print(f"  No training_summary: {no_summary} dates skipped")
    print(f"  No horse match: {no_match:,}")
    return records


# ========================================================================
# 全体分析 (Tab1)
# ========================================================================

def group_and_compute(records: list, key_fn, filter_fn=None) -> dict:
    """レコードをグループ化して統計計算"""
    groups = defaultdict(list)
    for r in records:
        if filter_fn and not filter_fn(r):
            continue
        key = key_fn(r)
        if key:
            groups[key].append(r)
    return {k: compute_stats(v) for k, v in groups.items()}


def compute_overall_analysis(records: list) -> dict:
    """Tab1: 全体の調教指標別統計"""
    print("  Computing overall analysis...")

    overall = {}

    # 単一軸
    overall['by_lapRank'] = group_and_compute(records, lambda r: r.get('lapRank', '') or None)
    overall['by_timeLevel'] = group_and_compute(records, lambda r: r.get('timeLevel', '') or None)
    overall['by_location'] = group_and_compute(records, lambda r: r.get('finalLocation', '') or None)
    overall['by_acceleration'] = group_and_compute(records, lambda r: r.get('acceleration', '') or None)
    overall['by_intensity'] = group_and_compute(records, lambda r: r.get('intensity', '') or None)
    overall['by_awase'] = group_and_compute(
        records,
        lambda r: 'あり' if r.get('has_awase') else 'なし',
        filter_fn=lambda r: r.get('intensity') != ''  # kb_extあり限定
    )

    # 交差分析
    overall['by_lapRank_x_location'] = group_and_compute(
        records,
        lambda r: f"{r.get('lapRank', '')}_{r.get('finalLocation', '')}" if r.get('lapRank') and r.get('finalLocation') else None
    )
    overall['by_timeLevel_x_acceleration'] = group_and_compute(
        records,
        lambda r: f"{r.get('timeLevel', '')}_{r.get('acceleration', '')}" if r.get('timeLevel') and r.get('acceleration') else None
    )

    # 人気帯別
    pop_buckets = {}
    for label, (lo, hi) in POPULARITY_BUCKETS.items():
        bucket_records = [r for r in records if lo <= r.get('popularity', 0) <= hi]
        if not bucket_records:
            continue
        pop_buckets[label] = {
            'by_lapRank': group_and_compute(bucket_records, lambda r: r.get('lapRank', '') or None),
            'by_timeLevel': group_and_compute(bucket_records, lambda r: r.get('timeLevel', '') or None),
            'by_location': group_and_compute(bucket_records, lambda r: r.get('finalLocation', '') or None),
            'by_acceleration': group_and_compute(bucket_records, lambda r: r.get('acceleration', '') or None),
        }
    overall['by_popularity_bucket'] = pop_buckets

    # 全体統計
    overall['total'] = compute_stats(records)

    return overall


# ========================================================================
# 調教師分析 (Tab2)
# ========================================================================

def compute_trainer_analysis(records: list) -> dict:
    """Tab2: 調教師別パターン分析"""
    print("  Computing trainer analysis...")

    # 調教師別にグループ化
    trainer_groups = defaultdict(list)
    for r in records:
        code = r.get('trainer_code', '')
        if code:
            trainer_groups[code].append(r)

    # コメント読み込み
    comments_path = config.userdata_dir() / 'trainer_comments.json'
    comments = {}
    if comments_path.exists():
        try:
            with open(comments_path, 'r', encoding='utf-8') as f:
                comments = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    results = {}
    total_patterns = 0

    for trainer_code, t_records in trainer_groups.items():
        if len(t_records) < 20:
            continue

        trainer_name = t_records[0].get('trainer_name', '')
        tozai = derive_tozai(t_records)

        # 全体統計
        overall = compute_stats(t_records)

        # all_patterns: 分類別統計
        all_patterns = {}

        # by_final_lap (lapRank別)
        by_lap = group_and_compute(t_records, lambda r: r.get('lapRank', '') or None)
        # サンプル数5以上のみ
        by_lap = {k: v for k, v in by_lap.items() if v['sample_size'] >= 5}
        if by_lap:
            all_patterns['by_final_lap'] = by_lap

        # by_location
        by_loc = group_and_compute(t_records, lambda r: r.get('finalLocation', '') or None)
        by_loc = {k: v for k, v in by_loc.items() if v['sample_size'] >= 5}
        if by_loc:
            all_patterns['by_location'] = by_loc

        # by_time_class
        by_time = group_and_compute(t_records, lambda r: r.get('timeLevel', '') or None)
        by_time = {k: v for k, v in by_time.items() if v['sample_size'] >= 5}
        if by_time:
            all_patterns['by_time_class'] = by_time

        # by_acceleration
        by_acc = group_and_compute(t_records, lambda r: r.get('acceleration', '') or None)
        by_acc = {k: v for k, v in by_acc.items() if v['sample_size'] >= 5}
        if by_acc:
            all_patterns['by_acceleration'] = by_acc

        # by_volume (セッション数)
        def volume_label(r):
            sc = r.get('session_count', -1)
            if sc < 0:
                return None
            if sc <= 3:
                return '少なめ(1-3本)'
            elif sc <= 5:
                return '普通(4-5本)'
            else:
                return '多め(6本+)'

        by_vol = group_and_compute(t_records, volume_label)
        by_vol = {k: v for k, v in by_vol.items() if v['sample_size'] >= 5}
        if by_vol:
            all_patterns['by_volume'] = by_vol

        # best_patterns: パターン検出
        best_patterns = []
        overall_top3 = overall['top3_rate']

        for pattern in PATTERNS:
            matching = [r for r in t_records if pattern['check'](r)]
            if len(matching) < 8:
                continue

            p_stats = compute_stats(matching)
            lift = round(p_stats['top3_rate'] - overall_top3, 4)

            # パターン条件: top3_rate >= 25% or lift >= 5%
            if p_stats['top3_rate'] < 0.25 and lift < 0.05:
                continue

            confidence = compute_confidence(p_stats['sample_size'], lift)
            score = p_stats['top3_rate'] * math.sqrt(p_stats['sample_size']) * max(lift, 0.01)

            best_patterns.append({
                'description': pattern['name'],
                'human_label': None,
                'conditions': pattern['conditions'],
                'stats': {
                    **p_stats,
                    'confidence': confidence,
                    'lift': lift,
                },
                '_score': score,
            })

        # スコア順でtop5
        best_patterns.sort(key=lambda x: x['_score'], reverse=True)
        best_patterns = best_patterns[:5]
        # _scoreはJSON出力に不要なので除去
        for bp in best_patterns:
            del bp['_score']

        total_patterns += len(best_patterns)

        results[trainer_code] = {
            'name': trainer_name,
            'jvn_code': trainer_code,
            'tozai': tozai,
            'total_runners': overall['sample_size'],
            'overall_stats': overall,
            'best_patterns': best_patterns,
            'all_patterns': all_patterns,
            'comment': comments.get(trainer_code, ''),
        }

    print(f"  Trainers analyzed: {len(results)}")
    print(f"  Total patterns found: {total_patterns}")
    return results


# ========================================================================
# メイン
# ========================================================================

def main():
    parser = argparse.ArgumentParser(description="Training Analysis v1.0")
    parser.add_argument("--since", type=int, default=2023, help="Start year (default: 2023)")
    output_default = str(config.data_root() / "analysis" / "training_analysis.json")
    parser.add_argument("--output", type=str, default=output_default)
    args = parser.parse_args()

    print("=" * 70)
    print("Training Analysis v1.0")
    print("=" * 70)
    print(f"Since: {args.since}")
    print(f"Output: {args.output}")
    print()

    # Step 1: Collect records
    print("[STEP 1] Collecting training × race records...")
    records = collect_records(args.since)

    if not records:
        print("[ERROR] No records collected")
        return 1

    # Step 2: Overall analysis
    print("\n[STEP 2] Computing overall training analysis...")
    overall = compute_overall_analysis(records)

    # Step 3: Trainer analysis
    print("\n[STEP 3] Computing trainer-specific analysis...")
    trainers = compute_trainer_analysis(records)

    # Save
    output_data = {
        "metadata": {
            "created_at": datetime.now().isoformat(),
            "source": "data3/races/training_summary + data3/keibabook + data3/races",
            "since": args.since,
            "total_records": len(records),
            "version": "1.0",
        },
        "overall": overall,
        "trainers": trainers,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 70}")
    print(f"[OK] Analysis saved: {output_path}")
    print(f"     Total records: {len(records):,}")
    print(f"     Overall groups: {sum(len(v) for k, v in overall.items() if isinstance(v, dict) and k != 'total')}")
    print(f"     Trainers: {len(trainers)}")

    # Top findings
    if overall.get('by_lapRank'):
        print("\n  lapRank Top 5 by top3_rate:")
        top_lr = sorted(overall['by_lapRank'].items(), key=lambda x: x[1]['top3_rate'], reverse=True)[:5]
        for rank, stats in top_lr:
            print(f"    {rank}: top3={stats['top3_rate']:.1%} win={stats['win_rate']:.1%} n={stats['sample_size']}")

    if trainers:
        print("\n  Top 5 trainers by best pattern score:")
        top_t = sorted(
            trainers.items(),
            key=lambda x: x[1]['best_patterns'][0]['stats']['top3_rate'] if x[1]['best_patterns'] else 0,
            reverse=True
        )[:5]
        for code, data in top_t:
            if data['best_patterns']:
                bp = data['best_patterns'][0]
                print(f"    {data['name']} ({code}): {bp['description']} "
                      f"top3={bp['stats']['top3_rate']:.1%} n={bp['stats']['sample_size']}")

    return 0


if __name__ == "__main__":
    exit(main())
