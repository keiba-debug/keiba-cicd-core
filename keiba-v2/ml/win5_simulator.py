#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WIN5 シミュレーター

過去のWIN5対象レースに対して各種カバレッジ戦略を適用し、
「何点あれば的中できたか」をシミュレーションする。

データソース:
  - mykeibadb win5/win5_haraimodoshi テーブル（対象レース・払戻金）
  - backtest_cache.json（予測データ・着順）

Usage:
    python -m ml.win5_simulator
"""

import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.config import data_root, ml_dir
from core import db


# ============================================================
# データ構造
# ============================================================

@dataclass
class Win5Race:
    """WIN5対象の1レース"""
    race_id: str          # 16桁 race_id
    venue_code: str       # 場コード(2桁)
    race_number: str      # R番号(2桁)
    winner_umaban: int    # 勝ち馬番号


@dataclass
class Win5Week:
    """1週分のWIN5データ"""
    date: str             # YYYYMMDD
    races: list           # Win5Race × 5
    payout: int           # 払戻金（円）。0=的中なし
    payout_count: int     # 的中票数
    ticket_count: int     # 発売票数
    carry_over_before: int  # 開始時キャリーオーバー
    carry_over_after: int   # 終了時キャリーオーバー
    no_hit: bool          # 的中なしフラグ


@dataclass
class RaceEntry:
    """1頭の予測データ"""
    umaban: int
    horse_name: str
    odds: float
    odds_rank: int
    is_win: bool
    finish_position: int
    rank_v: int
    rank_wv: int
    ar_deviation: float
    pred_proba_v_raw: float
    vb_gap: float
    win_vb_gap: float
    win_ev: float
    place_ev: float
    kb_mark: str = ''         # 競馬ブック印（後から連携）
    kb_mark_point: int = 0


@dataclass
class RacePrediction:
    """1レースの予測データ"""
    race_id: str
    track_type: str
    grade: str
    age_class: str
    entry_count: int
    entries: list  # List[RaceEntry]


@dataclass
class WeekResult:
    """1週分のシミュレーション結果"""
    date: str
    strategy_name: str
    tickets_per_race: list     # 各レースの点数
    total_tickets: int         # 合計点数（5レースの積）
    cost: int                  # 投資額（total_tickets × 100）
    is_hit: bool               # 的中したか
    payout: int                # 払戻金（的中時のみ）
    race_types: list           # 各レースのタイプ(A/B/C/D)
    target_score: int          # 狙い目スコア
    covered_races: int         # 勝ち馬をカバーできたレース数(/5)


# ============================================================
# Step 1: WIN5データ取得（mykeibadb）
# ============================================================

def load_win5_schedule() -> list:
    """
    mykeibadbからWIN5開催データを取得。
    Returns: List[Win5Week]
    """
    # win5テーブル: 対象レースと票数
    schedule_rows = db.query("""
        SELECT
            w.KAISAI_NEN, w.KAISAI_GAPPI,
            w.RACE_CODE1, w.KEIBAJO_CODE1, w.RACE_BANGO1,
            w.RACE_CODE2, w.KEIBAJO_CODE2, w.RACE_BANGO2,
            w.RACE_CODE3, w.KEIBAJO_CODE3, w.RACE_BANGO3,
            w.RACE_CODE4, w.KEIBAJO_CODE4, w.RACE_BANGO4,
            w.RACE_CODE5, w.KEIBAJO_CODE5, w.RACE_BANGO5,
            w.WIN5_HATSUBAI_HYOSU,
            w.TEKICHU_NASHI_FLAG,
            w.CARRY_OVER_SHOKI,
            w.CARRY_OVER_ZANDAKA
        FROM win5 w
        ORDER BY w.KAISAI_NEN, w.KAISAI_GAPPI
    """)

    # win5_haraimodoshi: 的中馬番と払戻金
    payout_rows = db.query("""
        SELECT
            KAISAI_NEN, KAISAI_GAPPI,
            WIN5_KUMIBAN1, WIN5_KUMIBAN2, WIN5_KUMIBAN3,
            WIN5_KUMIBAN4, WIN5_KUMIBAN5,
            WIN5_HARAIMODOSHIKIN, TEKICHU_HYOSU
        FROM win5_haraimodoshi
        ORDER BY KAISAI_NEN, KAISAI_GAPPI
    """)

    # 払戻をdate keyでインデックス化（複数的中組がある場合は最初のみ）
    payout_index = {}
    for row in payout_rows:
        key = row['KAISAI_NEN'].strip() + row['KAISAI_GAPPI'].strip()
        if key not in payout_index:
            payout_index[key] = row

    weeks = []
    for row in schedule_rows:
        year = row['KAISAI_NEN'].strip()
        gappi = row['KAISAI_GAPPI'].strip()
        date_str = year + gappi  # YYYYMMDD

        # 対象5レースを取得
        races = []
        for i in range(1, 6):
            race_code = (row.get(f'RACE_CODE{i}') or '').strip()
            venue = (row.get(f'KEIBAJO_CODE{i}') or '').strip()
            race_num = (row.get(f'RACE_BANGO{i}') or '').strip()

            # 勝ち馬番号は払戻データから取得
            payout_row = payout_index.get(date_str)
            winner = 0
            if payout_row:
                kumiban = (payout_row.get(f'WIN5_KUMIBAN{i}') or '').strip()
                winner = int(kumiban) if kumiban and kumiban.isdigit() else 0

            races.append(Win5Race(
                race_id=race_code,
                venue_code=venue,
                race_number=race_num,
                winner_umaban=winner,
            ))

        # 払戻情報
        payout_row = payout_index.get(date_str)
        payout = 0
        payout_count = 0
        if payout_row:
            raw = (payout_row.get('WIN5_HARAIMODOSHIKIN') or '').strip()
            payout = int(raw) if raw and raw.isdigit() else 0
            raw_cnt = (payout_row.get('TEKICHU_HYOSU') or '').strip()
            payout_count = int(raw_cnt) if raw_cnt and raw_cnt.isdigit() else 0

        ticket_count_raw = (row.get('WIN5_HATSUBAI_HYOSU') or '').strip()
        ticket_count = int(ticket_count_raw) if ticket_count_raw and ticket_count_raw.isdigit() else 0

        co_before_raw = (row.get('CARRY_OVER_SHOKI') or '').strip()
        co_before = int(co_before_raw) if co_before_raw and co_before_raw.isdigit() else 0
        co_after_raw = (row.get('CARRY_OVER_ZANDAKA') or '').strip()
        co_after = int(co_after_raw) if co_after_raw and co_after_raw.isdigit() else 0

        no_hit_flag = (row.get('TEKICHU_NASHI_FLAG') or '').strip()

        weeks.append(Win5Week(
            date=date_str,
            races=races,
            payout=payout,
            payout_count=payout_count,
            ticket_count=ticket_count,
            carry_over_before=co_before,
            carry_over_after=co_after,
            no_hit=(no_hit_flag == '1'),
        ))

    return weeks


# ============================================================
# Step 1b: backtest_cache からの予測データロード
# ============================================================

def load_backtest_predictions() -> dict:
    """
    backtest_cache.json を読み込み、race_id → RacePrediction の辞書を返す。
    """
    cache_path = ml_dir() / 'backtest_cache.json'
    with open(cache_path, encoding='utf-8') as f:
        data = json.load(f)

    index = {}
    for race in data:
        rid = race['race_id']
        entries = []
        for e in race.get('entries', []):
            entries.append(RaceEntry(
                umaban=int(e.get('umaban', 0)),
                horse_name=e.get('horse_name', ''),
                odds=float(e.get('odds', 0) or 0),
                odds_rank=int(e.get('odds_rank', 0) or 0),
                is_win=bool(e.get('is_win', False)),
                finish_position=int(e.get('finish_position', 0) or 0),
                rank_v=int(e.get('rank_v', 0) or 0),
                rank_wv=int(e.get('rank_wv', 0) or 0),
                ar_deviation=float(e.get('ar_deviation', 0) or 0),
                pred_proba_v_raw=float(e.get('pred_proba_v_raw', 0) or 0),
                vb_gap=float(e.get('vb_gap', 0) or 0),
                win_vb_gap=float(e.get('win_vb_gap', 0) or 0),
                win_ev=float(e.get('win_ev', 0) or 0),
                place_ev=float(e.get('place_ev', 0) or 0),
            ))
        index[rid] = RacePrediction(
            race_id=rid,
            track_type=race.get('track_type', ''),
            grade=race.get('grade', ''),
            age_class=race.get('age_class', ''),
            entry_count=len(entries),
            entries=entries,
        )

    return index


# ============================================================
# Step 2: レースタイプ分類
# ============================================================

def classify_race_type(pred: RacePrediction) -> str:
    """
    レースをタイプ A/B/C/D に分類。

    A: 一点突破（ARd1位>=65, 2位との差>=10, 勝利確率高い）
    B: 信頼軸（ARd1位>=60, 2位との差>=6）
    C: 混戦（それ以外）
    D: 危険人気馬消し（1-3番人気にodds<=8 & ARd<50 & V%<15%）

    D は他のタイプと併存する（D+A, D+C等）。
    返り値は 'A', 'B', 'C', 'DA', 'DB', 'DC' 等。
    """
    entries = sorted(pred.entries, key=lambda e: -e.ar_deviation)

    # ARd上位
    ard_1st = entries[0].ar_deviation if len(entries) > 0 else 0
    ard_2nd = entries[1].ar_deviation if len(entries) > 1 else 0
    ard_gap = ard_1st - ard_2nd

    # 危険人気馬チェック（odds<=8 & ARd<50 & V%<15%）
    has_danger = False
    for e in pred.entries:
        if e.odds <= 8 and e.ar_deviation < 50 and e.pred_proba_v_raw < 0.15:
            has_danger = True
            break

    # タイプ判定
    if ard_1st >= 65 and ard_gap >= 10:
        base_type = 'A'
    elif ard_1st >= 60 and ard_gap >= 6:
        base_type = 'B'
    else:
        base_type = 'C'

    return f'D{base_type}' if has_danger else base_type


def calc_target_score(race_types: list) -> int:
    """
    5レースのタイプから週の狙い目スコアを計算。
    """
    score = 0
    for rt in race_types:
        base = rt.replace('D', '')
        if base == 'A':
            score += 25
        elif base == 'B':
            score += 15
        else:
            score += 5
        if 'D' in rt:
            score += 10
    return score


# ============================================================
# Step 3: カバレッジ戦略
# ============================================================

def strategy_top_n(pred: RacePrediction, n: int, use_rank_v: bool = False) -> list:
    """rank_wv or rank_v 上位N頭を選択。"""
    rank_key = 'rank_v' if use_rank_v else 'rank_wv'
    return sorted(
        [e for e in pred.entries if getattr(e, rank_key, 0) > 0],
        key=lambda e: getattr(e, rank_key)
    )[:n]


def strategy_best_union(pred: RacePrediction, n: int) -> list:
    """rank_v と rank_wv の上位N頭の和集合。カバレッジ最大化。"""
    top_v = {e.umaban for e in sorted(
        [e for e in pred.entries if e.rank_v > 0], key=lambda e: e.rank_v)[:n]}
    top_wv = {e.umaban for e in sorted(
        [e for e in pred.entries if e.rank_wv > 0], key=lambda e: e.rank_wv)[:n]}
    union = top_v | top_wv
    return [e for e in pred.entries if e.umaban in union]


def strategy_ard_threshold(pred: RacePrediction, threshold: float) -> list:
    """AR偏差値が閾値以上の馬を全選択。"""
    selected = [e for e in pred.entries if e.ar_deviation >= threshold]
    return selected if selected else [max(pred.entries, key=lambda e: e.ar_deviation)]


def strategy_danger_exclude_top_n(pred: RacePrediction, n: int) -> list:
    """危険人気馬を除外した上でrank_wv上位N頭。"""
    safe = [
        e for e in pred.entries
        if not (e.odds <= 8 and e.ar_deviation < 50 and e.pred_proba_v_raw < 0.15)
    ]
    if not safe:
        safe = pred.entries
    return sorted(safe, key=lambda e: e.rank_wv)[:n]


def strategy_type_adaptive(pred: RacePrediction, race_type: str) -> list:
    """レースタイプに応じた適応的選択。"""
    base = race_type.replace('D', '')
    has_danger = 'D' in race_type

    # 危険馬を除外した候補
    if has_danger:
        pool = [
            e for e in pred.entries
            if not (e.odds <= 8 and e.ar_deviation < 50 and e.pred_proba_v_raw < 0.15)
        ]
        if not pool:
            pool = pred.entries
    else:
        pool = pred.entries

    if base == 'A':
        # 1頭のみ
        return [max(pool, key=lambda e: e.ar_deviation)]
    elif base == 'B':
        # Top2
        return sorted(pool, key=lambda e: e.rank_wv)[:2]
    else:
        # ARd>=50 or Top4
        selected = [e for e in pool if e.ar_deviation >= 50]
        if len(selected) < 2:
            selected = sorted(pool, key=lambda e: e.rank_wv)[:4]
        return selected


def strategy_budget(pred: RacePrediction, race_type: str, budget_tier: str) -> list:
    """
    非均等配分戦略: 自信レースで点数を節約し、混戦レースで広くカバーする。

    budget_tier:
      'tight':  総点数100点以内を目指す（各R: A=1, B=2, C=3-4）
      'normal': 総点数300点以内を目指す（各R: A=1, B=2, C=5-7）
      'wide':   カバレッジ最大化（各R: A=1, B=3, C=ARd>=45全買い）
    """
    base = race_type.replace('D', '')
    has_danger = 'D' in race_type

    if has_danger:
        pool = [
            e for e in pred.entries
            if not (e.odds <= 8 and e.ar_deviation < 50 and e.pred_proba_v_raw < 0.15)
        ]
        if not pool:
            pool = pred.entries
    else:
        pool = pred.entries

    if budget_tier == 'tight':
        if base == 'A':
            return [max(pool, key=lambda e: e.ar_deviation)]
        elif base == 'B':
            return sorted(pool, key=lambda e: e.rank_v)[:2]
        else:
            # 混戦: rank_v ∪ rank_wv Top2の和集合（最大4頭）
            top_v = set(e.umaban for e in sorted(pool, key=lambda e: e.rank_v)[:2])
            top_wv = set(e.umaban for e in sorted(pool, key=lambda e: e.rank_wv)[:2])
            union = top_v | top_wv
            return [e for e in pool if e.umaban in union]

    elif budget_tier == 'normal':
        if base == 'A':
            return [max(pool, key=lambda e: e.ar_deviation)]
        elif base == 'B':
            return sorted(pool, key=lambda e: e.rank_v)[:2]
        else:
            # 混戦: ARd>=50全買い（最低rank_v Top3）
            selected = [e for e in pool if e.ar_deviation >= 50]
            if len(selected) < 3:
                selected = sorted(pool, key=lambda e: e.rank_v)[:3]
            return selected

    else:  # wide
        if base == 'A':
            return [max(pool, key=lambda e: e.ar_deviation)]
        elif base == 'B':
            return sorted(pool, key=lambda e: e.rank_v)[:3]
        else:
            # 混戦: ARd>=45全買い
            selected = [e for e in pool if e.ar_deviation >= 45]
            if len(selected) < 3:
                selected = sorted(pool, key=lambda e: e.rank_v)[:5]
            return selected


# 全戦略の定義
STRATEGIES = {
    # rank_wv（勝利独自）ベース
    'wv_top1': lambda pred, rt: strategy_top_n(pred, 1),
    'wv_top2': lambda pred, rt: strategy_top_n(pred, 2),
    'wv_top3': lambda pred, rt: strategy_top_n(pred, 3),
    'wv_top5': lambda pred, rt: strategy_top_n(pred, 5),
    # rank_v（好走独自）ベース
    'v_top1': lambda pred, rt: strategy_top_n(pred, 1, use_rank_v=True),
    'v_top2': lambda pred, rt: strategy_top_n(pred, 2, use_rank_v=True),
    'v_top3': lambda pred, rt: strategy_top_n(pred, 3, use_rank_v=True),
    'v_top5': lambda pred, rt: strategy_top_n(pred, 5, use_rank_v=True),
    # 和集合（rank_v ∪ rank_wv で最大カバレッジ）
    'union_top2': lambda pred, rt: strategy_best_union(pred, 2),
    'union_top3': lambda pred, rt: strategy_best_union(pred, 3),
    # ARd閾値
    'ard_50': lambda pred, rt: strategy_ard_threshold(pred, 50),
    'ard_45': lambda pred, rt: strategy_ard_threshold(pred, 45),
    # 危険馬除外
    'danger_ex_top3': lambda pred, rt: strategy_danger_exclude_top_n(pred, 3),
    # タイプ適応
    'type_adaptive': lambda pred, rt: strategy_type_adaptive(pred, rt),
    # 非均等配分（自信レース節約 × 混戦広くカバー）
    'budget_tight': lambda pred, rt: strategy_budget(pred, rt, 'tight'),
    'budget_normal': lambda pred, rt: strategy_budget(pred, rt, 'normal'),
    'budget_wide': lambda pred, rt: strategy_budget(pred, rt, 'wide'),
}


# ============================================================
# Step 4: シミュレーション実行
# ============================================================

def simulate_week(
    week: Win5Week,
    pred_index: dict,
    strategy_name: str,
) -> Optional[WeekResult]:
    """
    1週分のWIN5シミュレーション。
    """
    strategy_fn = STRATEGIES.get(strategy_name)
    if not strategy_fn:
        return None

    tickets_per_race = []
    race_types = []
    all_covered = True

    for race in week.races:
        pred = pred_index.get(race.race_id)
        if not pred:
            return None  # 予測データなし → スキップ

        # レースタイプ分類
        rt = classify_race_type(pred)
        race_types.append(rt)

        # 戦略適用
        selected = strategy_fn(pred, rt)
        tickets_per_race.append(len(selected))

        # 勝ち馬がカバーされているか
        selected_umaban = {e.umaban for e in selected}
        if race.winner_umaban not in selected_umaban:
            all_covered = False

    total_tickets = 1
    for t in tickets_per_race:
        total_tickets *= t

    target_score = calc_target_score(race_types)

    return WeekResult(
        date=week.date,
        strategy_name=strategy_name,
        tickets_per_race=tickets_per_race,
        total_tickets=total_tickets,
        cost=total_tickets * 100,
        is_hit=all_covered,
        payout=week.payout if all_covered else 0,
        race_types=race_types,
        target_score=target_score,
        covered_races=sum(
            1 for i, race in enumerate(week.races)
            if pred_index.get(race.race_id) and
            race.winner_umaban in {
                e.umaban for e in strategy_fn(
                    pred_index[race.race_id],
                    race_types[i] if i < len(race_types) else 'C'
                )
            }
        ),
    )


# ============================================================
# Step 5: 集計・レポート
# ============================================================

def aggregate_results(results: list) -> dict:
    """戦略ごとの集計。"""
    by_strategy = defaultdict(list)
    for r in results:
        by_strategy[r.strategy_name].append(r)

    summary = {}
    for name, week_results in by_strategy.items():
        total_weeks = len(week_results)
        hits = [r for r in week_results if r.is_hit]
        ticket_counts = [r.total_tickets for r in week_results]

        # 的中に必要だった最小点数の分布
        min_tickets_needed = []
        for r in week_results:
            min_tickets_needed.append(r.total_tickets)

        # 点数帯別の的中数
        ticket_bins = [10, 50, 100, 300, 500, 1000]
        hit_by_bin = {}
        for threshold in ticket_bins:
            hit_count = sum(1 for r in hits if r.total_tickets <= threshold)
            hit_by_bin[f'<={threshold}'] = hit_count

        # 狙い目スコア別
        score_bins = [(80, 100), (60, 79), (0, 59)]
        hit_by_score = {}
        for lo, hi in score_bins:
            filtered = [r for r in week_results if lo <= r.target_score <= hi]
            filtered_hits = [r for r in filtered if r.is_hit]
            hit_by_score[f'{lo}-{hi}'] = {
                'weeks': len(filtered),
                'hits': len(filtered_hits),
                'avg_tickets': np.mean([r.total_tickets for r in filtered]) if filtered else 0,
            }

        summary[name] = {
            'total_weeks': total_weeks,
            'hit_count': len(hits),
            'hit_rate': len(hits) / total_weeks if total_weeks > 0 else 0,
            'avg_tickets': np.mean(ticket_counts),
            'median_tickets': np.median(ticket_counts),
            'min_tickets': min(ticket_counts) if ticket_counts else 0,
            'max_tickets': max(ticket_counts) if ticket_counts else 0,
            'avg_covered_races': np.mean([r.covered_races for r in week_results]),
            'total_cost': sum(r.cost for r in week_results),
            'total_payout': sum(r.payout for r in hits),
            'roi': (sum(r.payout for r in hits) / sum(r.cost for r in week_results)
                    if sum(r.cost for r in week_results) > 0 else 0),
            'hit_by_ticket_bin': hit_by_bin,
            'hit_by_score': hit_by_score,
            'max_payout': max((r.payout for r in hits), default=0),
            'min_payout': min((r.payout for r in hits), default=0),
        }

    return summary


def print_coverage_analysis(results: list):
    """カバレッジ分析: 各戦略でレースごとの勝ち馬カバー率。"""
    by_strategy = defaultdict(list)
    for r in results:
        by_strategy[r.strategy_name].append(r)

    print('\n' + '=' * 70)
    print('  レース別カバー率（各戦略）')
    print('=' * 70)

    for name in sorted(by_strategy.keys()):
        week_results = by_strategy[name]
        n = len(week_results)
        avg_covered = np.mean([r.covered_races for r in week_results])
        full_cover = sum(1 for r in week_results if r.covered_races == 5)
        race_cover_rates = []
        for i in range(5):
            covered = sum(1 for r in week_results if r.covered_races > i)
            # This is not per-race, just total covered count
        print(f'  {name:20s}: avg={avg_covered:.2f}/5  full_cover={full_cover}/{n}')


def print_summary(summary: dict):
    """結果サマリーの表示。"""
    print('\n' + '=' * 70)
    print('  WIN5 バックテスト結果サマリー')
    print('=' * 70)

    for name, s in sorted(summary.items()):
        print(f'\n--- {name} ---')
        print(f'  対象週数: {s["total_weeks"]}')
        print(f'  的中回数: {s["hit_count"]} ({s["hit_rate"]*100:.1f}%)')
        print(f'  平均点数: {s["avg_tickets"]:.0f}点 (中央値: {s["median_tickets"]:.0f})')
        print(f'  点数範囲: {s["min_tickets"]}〜{s["max_tickets"]}')
        print(f'  平均カバーR: {s["avg_covered_races"]:.2f}/5')
        print(f'  累計投資: {s["total_cost"]:,}円')
        print(f'  累計払戻: {s["total_payout"]:,}円')
        print(f'  ROI: {s["roi"]*100:.1f}%')
        if s["hit_count"] > 0:
            print(f'  払戻: {s["min_payout"]:,}〜{s["max_payout"]:,}円')

        print(f'  --- 点数帯別的中 ---')
        for bin_label, count in s['hit_by_ticket_bin'].items():
            print(f'    {bin_label}点: {count}回的中')

        print(f'  --- 狙い目スコア別 ---')
        for score_range, info in s['hit_by_score'].items():
            print(f'    スコア{score_range}: {info["weeks"]}週 '
                  f'(的中{info["hits"]}回, 平均{info["avg_tickets"]:.0f}点)')


def print_hit_details(results: list):
    """的中事例の詳細表示。"""
    hits = [r for r in results if r.is_hit]
    if not hits:
        return

    print('\n' + '=' * 70)
    print(f'  的中事例一覧（{len(hits)}件）')
    print('=' * 70)

    for r in sorted(hits, key=lambda x: x.date):
        print(f'\n  日付: {r.date}  戦略: {r.strategy_name}')
        print(f'  点数: {r.total_tickets}点 ({" × ".join(str(t) for t in r.tickets_per_race)})')
        print(f'  投資: {r.cost:,}円  払戻: {r.payout:,}円')
        print(f'  タイプ: {" / ".join(r.race_types)}')
        print(f'  スコア: {r.target_score}')


# ============================================================
# 集計テーブル（追加依頼分）
# ============================================================

def build_aggregation_tables(
    weeks: list,
    pred_index: dict,
) -> dict:
    """
    集計テーブル①〜④を構築する汎用関数。
    追加の集計軸はここに関数を追加するだけで対応可能。
    """
    tables = {}

    # WIN5対象レースの全データを収集
    all_race_data = []  # (week, race_idx, pred, winner_entry)
    for week in weeks:
        for i, race in enumerate(week.races):
            pred = pred_index.get(race.race_id)
            if not pred:
                continue
            winner = None
            for e in pred.entries:
                if e.umaban == race.winner_umaban:
                    winner = e
                    break
            all_race_data.append({
                'week': week,
                'race_idx': i,
                'race_id': race.race_id,
                'pred': pred,
                'winner': winner,
                'winner_umaban': race.winner_umaban,
            })

    # ---- 集計①: ARdランク別勝利数 ----
    ard_bins = [
        ('>=65', lambda ard: ard >= 65),
        ('55-64', lambda ard: 55 <= ard < 65),
        ('45-54', lambda ard: 45 <= ard < 55),
        ('35-44', lambda ard: 35 <= ard < 45),
        ('<35', lambda ard: ard < 35),
    ]
    table1 = {label: {'R1': 0, 'R2': 0, 'R3': 0, 'R4': 0, 'R5': 0, 'total': 0}
              for label, _ in ard_bins}

    for rd in all_race_data:
        if not rd['winner']:
            continue
        ard = rd['winner'].ar_deviation
        race_key = f'R{rd["race_idx"] + 1}'
        for label, fn in ard_bins:
            if fn(ard):
                table1[label][race_key] += 1
                table1[label]['total'] += 1
                break

    tables['ard_rank_wins'] = table1

    # ---- 集計②: 競馬ブック◎印別勝利数 ----
    # kb_markが未連携の場合は空テーブルを返す
    mark_labels = ['◎', '○', '▲', '△', '無印']
    table2 = {m: {'R1': 0, 'R2': 0, 'R3': 0, 'R4': 0, 'R5': 0, 'total': 0}
              for m in mark_labels}

    for rd in all_race_data:
        if not rd['winner']:
            continue
        mark = rd['winner'].kb_mark or '無印'
        if mark not in table2:
            mark = '無印'
        race_key = f'R{rd["race_idx"] + 1}'
        table2[mark][race_key] += 1
        table2[mark]['total'] += 1

    tables['kb_mark_wins'] = table2

    # ---- 集計③: ARd×ブック印の複合勝率 ----
    combos = [
        ('ARd>=65 & ◎', lambda e: e.ar_deviation >= 65 and e.kb_mark == '◎'),
        ('ARd>=65 & ○以下', lambda e: e.ar_deviation >= 65 and e.kb_mark != '◎'),
        ('ARd55-64 & ◎', lambda e: 55 <= e.ar_deviation < 65 and e.kb_mark == '◎'),
        ('ARd<45 & 無印', lambda e: e.ar_deviation < 45 and (not e.kb_mark or e.kb_mark == '無印')),
    ]
    table3 = {}
    for label, fn in combos:
        matches = 0
        wins = 0
        for rd in all_race_data:
            for e in rd['pred'].entries:
                if fn(e):
                    matches += 1
                    if e.is_win:
                        wins += 1
        table3[label] = {
            'count': matches,
            'wins': wins,
            'win_rate': wins / matches if matches > 0 else 0,
        }

    tables['ard_mark_combo'] = table3

    # ---- 集計④: 払戻金額帯別の人気・ARd構成 ----
    payout_bins = [
        ('~100万', lambda p: p <= 1_000_000),
        ('100~500万', lambda p: 1_000_000 < p <= 5_000_000),
        ('500~1000万', lambda p: 5_000_000 < p <= 10_000_000),
        ('1000万~', lambda p: p > 10_000_000),
    ]
    table4 = {}
    for label, fn in payout_bins:
        matching_weeks = [w for w in weeks if w.payout > 0 and fn(w.payout)]
        pop1_wins = 0
        ard65_wins = 0
        for w in matching_weeks:
            for race in w.races:
                pred = pred_index.get(race.race_id)
                if not pred:
                    continue
                for e in pred.entries:
                    if e.umaban == race.winner_umaban:
                        if e.odds_rank == 1:
                            pop1_wins += 1
                        if e.ar_deviation >= 65:
                            ard65_wins += 1
                        break
        table4[label] = {
            'weeks': len(matching_weeks),
            'pop1_wins': pop1_wins,
            'ard65_wins': ard65_wins,
        }

    tables['payout_composition'] = table4

    return tables


def print_aggregation_tables(tables: dict):
    """集計テーブルの表示。"""
    # 集計①
    print('\n' + '=' * 70)
    print('  集計①: ARdランク別勝利数')
    print('=' * 70)
    print(f'  {"ARd帯":10s} {"R1":>4s} {"R2":>4s} {"R3":>4s} {"R4":>4s} {"R5":>4s} {"合計":>5s}')
    for label, row in tables['ard_rank_wins'].items():
        print(f'  {label:10s} {row["R1"]:4d} {row["R2"]:4d} {row["R3"]:4d} '
              f'{row["R4"]:4d} {row["R5"]:4d} {row["total"]:5d}')

    # 集計②
    print('\n' + '=' * 70)
    print('  集計②: 競馬ブック印別勝利数')
    print('=' * 70)
    total_all = sum(row['total'] for row in tables['kb_mark_wins'].values())
    if total_all == tables['kb_mark_wins'].get('無印', {}).get('total', 0):
        print('  ※ kb_mark未連携のため全て「無印」に分類されています')
    print(f'  {"印":10s} {"R1":>4s} {"R2":>4s} {"R3":>4s} {"R4":>4s} {"R5":>4s} {"合計":>5s}')
    for label, row in tables['kb_mark_wins'].items():
        print(f'  {label:10s} {row["R1"]:4d} {row["R2"]:4d} {row["R3"]:4d} '
              f'{row["R4"]:4d} {row["R5"]:4d} {row["total"]:5d}')

    # 集計③
    print('\n' + '=' * 70)
    print('  集計③: ARd×印 複合勝率')
    print('=' * 70)
    print(f'  {"条件":25s} {"勝率":>7s} {"件数":>6s}')
    for label, row in tables['ard_mark_combo'].items():
        print(f'  {label:25s} {row["win_rate"]*100:6.1f}% {row["count"]:5d}')

    # 集計④
    print('\n' + '=' * 70)
    print('  集計④: 払戻金額帯別の構成')
    print('=' * 70)
    print(f'  {"払戻帯":15s} {"週数":>5s} {"1番人気勝利":>10s} {"ARd>=65勝利":>10s}')
    for label, row in tables['payout_composition'].items():
        print(f'  {label:15s} {row["weeks"]:5d} {row["pop1_wins"]:10d} {row["ard65_wins"]:10d}')


# ============================================================
# 勝ち馬ランク分析 + 理論的最小点数
# ============================================================

def analyze_winner_ranks(weeks: list, pred_index: dict):
    """
    各週の勝ち馬が各ランキングで何位だったかを分析。
    理論的最小必要点数を計算。
    """
    print('\n' + '=' * 70)
    print('  勝ち馬ランク分析（理論的最小必要点数）')
    print('=' * 70)

    print(f'\n  {"日付":10s} {"R1":>12s} {"R2":>12s} {"R3":>12s} {"R4":>12s} '
          f'{"R5":>12s} {"最小点数(v)":>12s} {"最小点数(wv)":>14s}')
    print('  ' + '-' * 98)

    all_min_v = []
    all_min_wv = []
    rank_v_dist = defaultdict(int)
    rank_wv_dist = defaultdict(int)

    for week in weeks:
        ranks_v = []
        ranks_wv = []
        for race in week.races:
            pred = pred_index.get(race.race_id)
            if not pred:
                ranks_v.append(999)
                ranks_wv.append(999)
                continue
            winner = None
            for e in pred.entries:
                if e.umaban == race.winner_umaban:
                    winner = e
                    break
            if winner:
                rv = winner.rank_v if winner.rank_v > 0 else len(pred.entries)
                rwv = winner.rank_wv if winner.rank_wv > 0 else len(pred.entries)
                ranks_v.append(rv)
                ranks_wv.append(rwv)
                rank_v_dist[rv] += 1
                rank_wv_dist[rwv] += 1
            else:
                ranks_v.append(999)
                ranks_wv.append(999)

        # 理論的最小点数 = 各レースの勝ち馬ランクの積
        min_tickets_v = 1
        min_tickets_wv = 1
        for rv, rwv in zip(ranks_v, ranks_wv):
            min_tickets_v *= rv
            min_tickets_wv *= rwv

        all_min_v.append(min_tickets_v)
        all_min_wv.append(min_tickets_wv)

        r_strs = []
        for rv, rwv in zip(ranks_v, ranks_wv):
            r_strs.append(f'v{rv}/wv{rwv}')

        print(f'  {week.date:10s} {r_strs[0]:>12s} {r_strs[1]:>12s} {r_strs[2]:>12s} '
              f'{r_strs[3]:>12s} {r_strs[4]:>12s} {min_tickets_v:>12,d} {min_tickets_wv:>14,d}')

    print()
    print(f'  理論的最小点数(rank_v):  '
          f'平均={np.mean(all_min_v):,.0f}  中央値={np.median(all_min_v):,.0f}  '
          f'最小={min(all_min_v):,d}  最大={max(all_min_v):,d}')
    print(f'  理論的最小点数(rank_wv): '
          f'平均={np.mean(all_min_wv):,.0f}  中央値={np.median(all_min_wv):,.0f}  '
          f'最小={min(all_min_wv):,d}  最大={max(all_min_wv):,d}')

    # 最小点数の分布
    for label, values in [('rank_v', all_min_v), ('rank_wv', all_min_wv)]:
        print(f'\n  {label}ベース最小点数の分布:')
        for threshold in [10, 50, 100, 243, 500, 1000, 3000, 10000]:
            count = sum(1 for v in values if v <= threshold)
            print(f'    <= {threshold:>6,d}点: {count}/{len(values)}週 ({count/len(values)*100:.1f}%)')

    # 勝ち馬のランク分布
    print(f'\n  勝ち馬のrank_v分布:')
    for rank in sorted(rank_v_dist.keys()):
        cnt = rank_v_dist[rank]
        total = sum(rank_v_dist.values())
        print(f'    rank_v={rank:2d}: {cnt:3d}回 ({cnt/total*100:.1f}%)')

    print(f'\n  勝ち馬のrank_wv分布:')
    for rank in sorted(rank_wv_dist.keys()):
        cnt = rank_wv_dist[rank]
        total = sum(rank_wv_dist.values())
        print(f'    rank_wv={rank:2d}: {cnt:3d}回 ({cnt/total*100:.1f}%)')


# ============================================================
# メイン実行
# ============================================================

def main():
    print('=' * 70)
    print('  WIN5 シミュレーター')
    print('=' * 70)

    # データロード
    print('\n[Load] WIN5スケジュール...')
    weeks = load_win5_schedule()
    print(f'  {len(weeks)}週のWIN5データ')

    print('[Load] 予測データ (backtest_cache)...')
    pred_index = load_backtest_predictions()
    print(f'  {len(pred_index)}レースの予測データ')

    # 予測データとマッチする週を抽出
    matched_weeks = []
    for week in weeks:
        race_ids = [r.race_id for r in week.races]
        if all(rid in pred_index for rid in race_ids):
            matched_weeks.append(week)

    print(f'\n[Match] 予測データとマッチ: {len(matched_weeks)}/{len(weeks)}週')

    if not matched_weeks:
        print('\n⚠ マッチする週がありません。')
        print('  考えられる原因:')
        print('  - mykeibadb WFデータの取り込みがまだ途中')
        print('  - backtest_cache.jsonの期間とWIN5データの期間が重複していない')
        return

    # 期間表示
    dates = sorted(w.date for w in matched_weeks)
    print(f'  期間: {dates[0]} 〜 {dates[-1]}')

    # 全戦略でシミュレーション
    print('\n[Simulate] 各戦略でシミュレーション中...')
    all_results = []
    for strategy_name in STRATEGIES:
        for week in matched_weeks:
            result = simulate_week(week, pred_index, strategy_name)
            if result:
                all_results.append(result)

    # 結果集計
    summary = aggregate_results(all_results)
    print_summary(summary)

    # 的中事例
    print_hit_details(all_results)

    # カバレッジ分析
    print_coverage_analysis(all_results)

    # 勝ち馬ランク分析
    analyze_winner_ranks(matched_weeks, pred_index)

    # 集計テーブル①〜④
    print('\n[Aggregate] 集計テーブル作成中...')
    tables = build_aggregation_tables(matched_weeks, pred_index)
    print_aggregation_tables(tables)

    # あきらめ基準の判定
    print('\n' + '=' * 70)
    print('  あきらめ基準の判定')
    print('=' * 70)

    adaptive = summary.get('type_adaptive', {})
    if adaptive:
        avg = adaptive.get('avg_tickets', 0)
        print(f'\n  基準A（平均500点以上→断念）: 平均{avg:.0f}点')
        print(f'    → {"⚠ 断念基準に該当" if avg >= 500 else "✓ 基準内"}')

        hits_under_100 = adaptive.get('hit_by_ticket_bin', {}).get('<=100', 0)
        total = adaptive.get('total_weeks', 1)
        print(f'\n  基準B（100点以下での的中が0-1回→断念）: {hits_under_100}回/{total}週')
        print(f'    → {"⚠ 断念基準に該当" if hits_under_100 <= 1 else "✓ 基準内"}')

        score_high = adaptive.get('hit_by_score', {}).get('80-100', {})
        score_low = adaptive.get('hit_by_score', {}).get('0-59', {})
        avg_high = score_high.get('avg_tickets', 0)
        avg_low = score_low.get('avg_tickets', 0)
        if avg_high > 0 and avg_low > 0:
            diff = avg_low - avg_high
            print(f'\n  基準C（スコア別点数差なし→断念）:')
            print(f'    スコア80+: 平均{avg_high:.0f}点')
            print(f'    スコア<60: 平均{avg_low:.0f}点')
            print(f'    差分: {diff:.0f}点')
            print(f'    → {"⚠ 断念基準に該当（差が小さい）" if diff < 50 else "✓ 有意差あり"}')

    # JSON出力
    output_path = ml_dir() / 'win5_simulation_results.json'
    output_data = {
        'period': {'start': dates[0], 'end': dates[-1]},
        'matched_weeks': len(matched_weeks),
        'strategies': {},
    }
    for name, s in summary.items():
        output_data['strategies'][name] = {
            k: (v if not isinstance(v, (np.floating, np.integer)) else float(v))
            for k, v in s.items()
        }

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2, default=str)
    print(f'\n[Save] {output_path}')


if __name__ == '__main__':
    main()
