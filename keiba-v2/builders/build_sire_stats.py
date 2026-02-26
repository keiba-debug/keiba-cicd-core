#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
種牡馬(sire)・母父(bms)統計インデックス構築

race JSONsとpedigree_index.jsonから、sire/bms別の集計統計を構築。
ベースライン(勝率/複勝率) + 条件別(休み明け/間隔詰め)の統計を算出。

Usage:
    python -m builders.build_sire_stats             # ビルドのみ
    python -m builders.build_sire_stats --analyze    # ビルド + H3/H4分析
"""

import json
import sys
import time
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config


# ============================================================
# ベイズ平滑化パラメータ (past_features.pyと同じ)
# ============================================================
PRIOR_WIN_ALPHA = 1.0
PRIOR_WIN_BETA = 12.0      # prior mean ≈ 0.077

PRIOR_TOP3_ALPHA = 2.5
PRIOR_TOP3_BETA = 7.5      # prior mean = 0.25


def bayesian_rate(successes: int, total: int, alpha: float, beta: float) -> float:
    """ベイズ平滑化レート (Beta-Binomial posterior mean)"""
    return round((successes + alpha) / (total + alpha + beta), 4)


# ============================================================
# 条件閾値
# ============================================================
FRESH_DAYS = 56     # 8週以上 = 休み明け
TIGHT_DAYS = 21     # 3週以内 = 間隔詰め
MIN_RUNS_CONDITIONAL = 10  # 条件付きrateの最小サンプル数


def load_race_jsons() -> List[dict]:
    """全レースJSONを日付順にロード"""
    races_dir = config.races_dir()
    files = sorted(races_dir.glob("**/race_[0-9]*.json"))
    print(f"  Found {len(files):,} race files")

    races = []
    for f in files:
        try:
            with open(f, encoding='utf-8') as fp:
                race = json.load(fp)
            races.append(race)
        except Exception:
            continue

    # 日付順ソート
    races.sort(key=lambda r: r.get('date', ''))
    return races


def load_pedigree_index() -> Dict[str, dict]:
    """pedigree_index.jsonをロード"""
    path = config.indexes_dir() / "pedigree_index.json"
    if not path.exists():
        print(f"  [ERROR] pedigree_index.json not found: {path}")
        return {}
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def build_sire_stats(races: List[dict], pedigree_index: Dict[str, dict]) -> dict:
    """sire/bms別統計を構築

    各馬の前走日を追跡してdays_since_last_raceを計算し、
    sire/bms別にベースライン+条件別の成績を集計。
    """

    # 馬ごとの最終出走日を追跡
    horse_last_date: Dict[str, str] = {}  # ketto_num → date string

    # sire/bms別集計
    sire_stats = defaultdict(lambda: {
        'total_runs': 0, 'wins': 0, 'top3': 0,
        'fresh_runs': 0, 'fresh_wins': 0, 'fresh_top3': 0,
        'tight_runs': 0, 'tight_wins': 0, 'tight_top3': 0,
        'normal_runs': 0, 'normal_wins': 0, 'normal_top3': 0,
    })
    bms_stats = defaultdict(lambda: {
        'total_runs': 0, 'wins': 0, 'top3': 0,
        'fresh_runs': 0, 'fresh_wins': 0, 'fresh_top3': 0,
        'tight_runs': 0, 'tight_wins': 0, 'tight_top3': 0,
        'normal_runs': 0, 'normal_wins': 0, 'normal_top3': 0,
    })

    total_entries = 0
    matched_entries = 0
    no_prev_race = 0

    for race in races:
        race_date = race.get('date', '')
        if not race_date:
            continue

        entries = race.get('entries', [])
        for entry in entries:
            ketto_num = entry.get('ketto_num', '')
            if not ketto_num:
                continue

            finish = entry.get('finish_position')
            if finish is None or finish == 0:
                continue  # 出走取消・競走中止

            total_entries += 1

            # 血統ルックアップ
            ped = pedigree_index.get(ketto_num)
            if not ped:
                continue

            sire_id = ped.get('sire')
            bms_id = ped.get('bms')
            if not sire_id and not bms_id:
                continue

            matched_entries += 1

            is_win = (finish == 1)
            is_top3 = (finish <= 3)

            # days_since_last_race 計算
            prev_date = horse_last_date.get(ketto_num)
            days = None
            if prev_date:
                try:
                    d1 = datetime.strptime(prev_date, '%Y-%m-%d')
                    d2 = datetime.strptime(race_date, '%Y-%m-%d')
                    days = (d2 - d1).days
                except ValueError:
                    pass
            else:
                no_prev_race += 1

            # 馬の最終出走日を更新
            horse_last_date[ketto_num] = race_date

            # 条件分類
            cond = _classify_rest(days)

            # sire集計
            if sire_id:
                _accumulate(sire_stats[sire_id], is_win, is_top3, cond)

            # bms集計
            if bms_id:
                _accumulate(bms_stats[bms_id], is_win, is_top3, cond)

    print(f"  Total entries: {total_entries:,}")
    print(f"  Matched (pedigree): {matched_entries:,} ({matched_entries/max(total_entries,1)*100:.1f}%)")
    print(f"  No prev race (debut): {no_prev_race:,}")
    print(f"  Unique sires: {len(sire_stats):,}")
    print(f"  Unique BMS: {len(bms_stats):,}")

    # 統計量を計算
    sire_result = _finalize_stats(sire_stats)
    bms_result = _finalize_stats(bms_stats)

    return {
        'sire': sire_result,
        'bms': bms_result,
        'meta': {
            'total_races': len(races),
            'total_entries': total_entries,
            'matched_entries': matched_entries,
            'unique_sires': len(sire_stats),
            'unique_bms': len(bms_stats),
            'fresh_days_threshold': FRESH_DAYS,
            'tight_days_threshold': TIGHT_DAYS,
            'min_runs_conditional': MIN_RUNS_CONDITIONAL,
            'built_at': datetime.now().isoformat(timespec='seconds'),
        }
    }


def _classify_rest(days: Optional[int]) -> str:
    """休養日数を分類"""
    if days is None:
        return 'debut'  # 初出走
    if days >= FRESH_DAYS:
        return 'fresh'
    if days <= TIGHT_DAYS:
        return 'tight'
    return 'normal'


def _accumulate(stats: dict, is_win: bool, is_top3: bool, cond: str):
    """成績を加算"""
    stats['total_runs'] += 1
    if is_win:
        stats['wins'] += 1
    if is_top3:
        stats['top3'] += 1

    if cond == 'debut':
        return  # デビュー戦は条件別集計に含めない

    stats[f'{cond}_runs'] += 1
    if is_win:
        stats[f'{cond}_wins'] += 1
    if is_top3:
        stats[f'{cond}_top3'] += 1


def _finalize_stats(raw_stats: dict) -> dict:
    """生カウントからレート・差分を計算"""
    result = {}

    for sid, s in raw_stats.items():
        total = s['total_runs']
        if total == 0:
            continue

        entry = {
            'total_runs': total,
            'wins': s['wins'],
            'top3': s['top3'],
            'win_rate': bayesian_rate(s['wins'], total, PRIOR_WIN_ALPHA, PRIOR_WIN_BETA),
            'top3_rate': bayesian_rate(s['top3'], total, PRIOR_TOP3_ALPHA, PRIOR_TOP3_BETA),
        }

        # 条件別レート（runs >= MIN_RUNS_CONDITIONAL で有効）
        normal_top3_rate = None
        if s['normal_runs'] >= MIN_RUNS_CONDITIONAL:
            normal_top3_rate = bayesian_rate(
                s['normal_top3'], s['normal_runs'],
                PRIOR_TOP3_ALPHA, PRIOR_TOP3_BETA)
            entry['normal_runs'] = s['normal_runs']
            entry['normal_top3_rate'] = normal_top3_rate

        if s['fresh_runs'] >= MIN_RUNS_CONDITIONAL:
            fresh_rate = bayesian_rate(
                s['fresh_top3'], s['fresh_runs'],
                PRIOR_TOP3_ALPHA, PRIOR_TOP3_BETA)
            entry['fresh_runs'] = s['fresh_runs']
            entry['fresh_top3_rate'] = fresh_rate
            if normal_top3_rate is not None:
                entry['fresh_advantage'] = round(fresh_rate - normal_top3_rate, 4)

        if s['tight_runs'] >= MIN_RUNS_CONDITIONAL:
            tight_rate = bayesian_rate(
                s['tight_top3'], s['tight_runs'],
                PRIOR_TOP3_ALPHA, PRIOR_TOP3_BETA)
            entry['tight_runs'] = s['tight_runs']
            entry['tight_top3_rate'] = tight_rate
            if normal_top3_rate is not None:
                entry['tight_penalty'] = round(tight_rate - normal_top3_rate, 4)

        result[sid] = entry

    return result


# ============================================================
# 分析モード
# ============================================================

def analyze_h3_h4(stats: dict):
    """H3(休み明け上昇)・H4(間隔詰め疲労)の統計的検証"""

    print(f"\n{'='*60}")
    print(f"  H3/H4 血統仮説検証")
    print(f"{'='*60}")

    for label, data in [('Sire (父)', stats['sire']), ('BMS (母父)', stats['bms'])]:
        print(f"\n--- {label} ---")
        print(f"  Total entries: {len(data):,}")

        # 有効なサンプルのフィルタ
        has_fresh = [(sid, s) for sid, s in data.items() if 'fresh_advantage' in s]
        has_tight = [(sid, s) for sid, s in data.items() if 'tight_penalty' in s]

        print(f"  Has fresh_advantage (fresh>=10 & normal>=10): {len(has_fresh):,}")
        print(f"  Has tight_penalty  (tight>=10 & normal>=10): {len(has_tight):,}")

        # H3: 休み明け上昇分析
        if has_fresh:
            advantages = [s['fresh_advantage'] for _, s in has_fresh]
            _print_distribution("H3 fresh_advantage", advantages)

            # 上位5（休み明け得意）
            top5 = sorted(has_fresh, key=lambda x: x[1]['fresh_advantage'], reverse=True)[:10]
            print(f"\n  Top 10 休み明け得意 sire/bms:")
            for sid, s in top5:
                print(f"    {sid}: advantage={s['fresh_advantage']:+.4f} "
                      f"(fresh={s['fresh_runs']}走 rate={s['fresh_top3_rate']:.3f}, "
                      f"normal={s['normal_runs']}走 rate={s['normal_top3_rate']:.3f})")

            # 下位5（休み明け苦手）
            bot5 = sorted(has_fresh, key=lambda x: x[1]['fresh_advantage'])[:10]
            print(f"\n  Top 10 休み明け苦手 sire/bms:")
            for sid, s in bot5:
                print(f"    {sid}: advantage={s['fresh_advantage']:+.4f} "
                      f"(fresh={s['fresh_runs']}走 rate={s['fresh_top3_rate']:.3f}, "
                      f"normal={s['normal_runs']}走 rate={s['normal_top3_rate']:.3f})")

        # H4: 間隔詰め疲労分析
        if has_tight:
            penalties = [s['tight_penalty'] for _, s in has_tight]
            _print_distribution("H4 tight_penalty", penalties)

            # 上位5（詰め使い得意）
            top5 = sorted(has_tight, key=lambda x: x[1]['tight_penalty'], reverse=True)[:10]
            print(f"\n  Top 10 間隔詰め得意 sire/bms:")
            for sid, s in top5:
                print(f"    {sid}: penalty={s['tight_penalty']:+.4f} "
                      f"(tight={s['tight_runs']}走 rate={s['tight_top3_rate']:.3f}, "
                      f"normal={s['normal_runs']}走 rate={s['normal_top3_rate']:.3f})")

            # 下位5（詰め使い苦手）
            bot5 = sorted(has_tight, key=lambda x: x[1]['tight_penalty'])[:10]
            print(f"\n  Top 10 間隔詰め苦手 sire/bms:")
            for sid, s in bot5:
                print(f"    {sid}: penalty={s['tight_penalty']:+.4f} "
                      f"(tight={s['tight_runs']}走 rate={s['tight_top3_rate']:.3f}, "
                      f"normal={s['normal_runs']}走 rate={s['normal_top3_rate']:.3f})")

    # ベースライン統計
    print(f"\n--- ベースライン統計 ---")
    for label, data in [('Sire', stats['sire']), ('BMS', stats['bms'])]:
        if not data:
            print(f"  {label}: no data")
            continue
        total_runs_list = [s['total_runs'] for s in data.values()]
        top3_rates = [s['top3_rate'] for s in data.values()]
        has_30_plus = sum(1 for r in total_runs_list if r >= 30)
        has_100_plus = sum(1 for r in total_runs_list if r >= 100)
        print(f"  {label}: {len(data):,} entries, "
              f">=30runs={has_30_plus:,}, >=100runs={has_100_plus:,}, "
              f"top3_rate median={statistics.median(top3_rates):.4f}")


def _print_distribution(name: str, values: List[float]):
    """分布の要約統計量を表示"""
    if not values:
        print(f"  {name}: no data")
        return

    mean = statistics.mean(values)
    median = statistics.median(values)
    stdev = statistics.stdev(values) if len(values) > 1 else 0.0
    pct_positive = sum(1 for v in values if v > 0) / len(values) * 100
    pct_strong = sum(1 for v in values if abs(v) > 0.05) / len(values) * 100

    print(f"\n  {name} 分布 (n={len(values):,}):")
    print(f"    Mean:     {mean:+.4f}")
    print(f"    Median:   {median:+.4f}")
    print(f"    Stdev:    {stdev:.4f}")
    print(f"    Min/Max:  {min(values):+.4f} / {max(values):+.4f}")
    print(f"    正の割合: {pct_positive:.1f}%")
    print(f"    |val|>0.05: {pct_strong:.1f}% (信号強度)")


# ============================================================
# メイン
# ============================================================

def main():
    print(f"\n{'='*60}")
    print(f"  KeibaCICD v4 - Sire/BMS Stats Builder")
    print(f"{'='*60}\n")

    t0 = time.time()
    do_analyze = '--analyze' in sys.argv

    # データロード
    print("[1/3] Loading pedigree index...")
    pedigree_index = load_pedigree_index()
    if not pedigree_index:
        print("  Cannot proceed without pedigree_index.json")
        return

    print(f"  Loaded {len(pedigree_index):,} horses")

    print("\n[2/3] Loading race JSONs...")
    races = load_race_jsons()

    print(f"\n[3/3] Building sire/bms stats...")
    stats = build_sire_stats(races, pedigree_index)

    # 保存
    out_path = config.indexes_dir() / "sire_stats_index.json"
    config.ensure_dir(config.indexes_dir())

    print(f"\n[Save] Writing {out_path}...")
    out_path.write_text(
        json.dumps(stats, ensure_ascii=False, separators=(',', ':')),
        encoding='utf-8',
    )

    file_size = out_path.stat().st_size / 1024 / 1024
    elapsed = time.time() - t0

    print(f"\n{'='*60}")
    print(f"  Results")
    print(f"{'='*60}")
    print(f"  Sires:     {len(stats['sire']):,}")
    print(f"  BMS:       {len(stats['bms']):,}")
    print(f"  File size: {file_size:.1f} MB")
    print(f"  Output:    {out_path}")
    print(f"  Elapsed:   {elapsed:.1f}s")
    print(f"{'='*60}")

    # 分析モード
    if do_analyze:
        analyze_h3_h4(stats)

    print()


if __name__ == '__main__':
    main()
