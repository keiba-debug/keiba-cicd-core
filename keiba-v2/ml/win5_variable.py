#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WIN5 可変点数シミュレーター

各レースの rank_w 1位/2位/3位 の数値（ARd, gap, WinEV等）を見て
1〜5頭を可変で選ぶ。条件外のレースがあればその週は購入しない。

Usage:
    python -m ml.win5_variable
"""

import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core.config import data_root, ml_dir
from core import db


# ============================================================
# データ構造（win5_simulator.py と同じ）
# ============================================================

@dataclass
class Win5Race:
    race_id: str
    venue_code: str
    race_number: str
    winner_umaban: int

@dataclass
class Win5Week:
    date: str
    races: list
    payout: int
    no_hit: bool

@dataclass
class RaceEntry:
    umaban: int
    horse_name: str
    odds: float
    odds_rank: int
    is_win: bool
    finish_position: int
    rank_p: int
    rank_w: int
    ar_deviation: float
    pred_proba_p_raw: float
    vb_gap: float
    win_vb_gap: float
    win_ev: float
    place_ev: float

@dataclass
class RacePrediction:
    race_id: str
    entry_count: int
    entries: list  # List[RaceEntry]


# ============================================================
# データロード
# ============================================================

def load_win5_schedule() -> list:
    schedule_rows = db.query("""
        SELECT w.KAISAI_NEN, w.KAISAI_GAPPI,
            w.RACE_CODE1, w.KEIBAJO_CODE1, w.RACE_BANGO1,
            w.RACE_CODE2, w.KEIBAJO_CODE2, w.RACE_BANGO2,
            w.RACE_CODE3, w.KEIBAJO_CODE3, w.RACE_BANGO3,
            w.RACE_CODE4, w.KEIBAJO_CODE4, w.RACE_BANGO4,
            w.RACE_CODE5, w.KEIBAJO_CODE5, w.RACE_BANGO5,
            w.TEKICHU_NASHI_FLAG
        FROM win5 w ORDER BY w.KAISAI_NEN, w.KAISAI_GAPPI
    """)
    payout_rows = db.query("""
        SELECT KAISAI_NEN, KAISAI_GAPPI,
            WIN5_KUMIBAN1, WIN5_KUMIBAN2, WIN5_KUMIBAN3,
            WIN5_KUMIBAN4, WIN5_KUMIBAN5,
            WIN5_HARAIMODOSHIKIN, TEKICHU_HYOSU
        FROM win5_haraimodoshi ORDER BY KAISAI_NEN, KAISAI_GAPPI
    """)
    payout_index = {}
    for row in payout_rows:
        key = row['KAISAI_NEN'].strip() + row['KAISAI_GAPPI'].strip()
        if key not in payout_index:
            payout_index[key] = row

    weeks = []
    for row in schedule_rows:
        year = row['KAISAI_NEN'].strip()
        gappi = row['KAISAI_GAPPI'].strip()
        date_str = year + gappi

        races = []
        for i in range(1, 6):
            race_code = (row.get(f'RACE_CODE{i}') or '').strip()
            venue = (row.get(f'KEIBAJO_CODE{i}') or '').strip()
            race_num = (row.get(f'RACE_BANGO{i}') or '').strip()
            payout_row = payout_index.get(date_str)
            winner = 0
            if payout_row:
                kumiban = (payout_row.get(f'WIN5_KUMIBAN{i}') or '').strip()
                winner = int(kumiban) if kumiban and kumiban.isdigit() else 0
            races.append(Win5Race(race_id=race_code, venue_code=venue,
                                  race_number=race_num, winner_umaban=winner))

        payout_row = payout_index.get(date_str)
        payout = 0
        if payout_row:
            raw = (payout_row.get('WIN5_HARAIMODOSHIKIN') or '').strip()
            payout = int(raw) if raw and raw.isdigit() else 0

        no_hit = (row.get('TEKICHU_NASHI_FLAG') or '').strip() == '1'

        weeks.append(Win5Week(date=date_str, races=races, payout=payout, no_hit=no_hit))
    return weeks


def load_backtest_cache() -> dict:
    cache_path = ml_dir() / "backtest_cache.json"
    with open(cache_path, encoding='utf-8') as f:
        cache = json.load(f)

    pred_index = {}
    race_list = cache if isinstance(cache, list) else cache.values()
    for race_data in race_list:
        race_id = race_data.get('race_id', '')
        if not race_id:
            continue
        entries = []
        for e in race_data.get('entries', []):
            # ar_deviation: predicted_margin→偏差値変換（backtest_cacheにない場合は推定）
            ard = float(e.get('ar_deviation', 0) or 0)
            if ard == 0:
                # predicted_marginから偏差値を推定（mean=0, std≈0.5 → deviation = 50 + margin/0.5*10）
                pm = float(e.get('predicted_margin', 0) or 0)
                ard = 50 + pm * 20  # 粗い推定
            entries.append(RaceEntry(
                umaban=int(e.get('umaban', 0)),
                horse_name=e.get('horse_name', ''),
                odds=float(e.get('odds', 0) or 0),
                odds_rank=int(e.get('odds_rank', 0) or 0),
                is_win=bool(e.get('is_win', False)),
                finish_position=int(e.get('finish_position', 0) or 0),
                rank_p=int(e.get('rank_p', 0) or 0),
                rank_w=int(e.get('rank_w', 0) or 0),
                ar_deviation=ard,
                pred_proba_p_raw=float(e.get('pred_proba_p_raw', 0) or 0),
                vb_gap=float(e.get('vb_gap', 0) or 0),
                win_vb_gap=float(e.get('win_vb_gap', 0) or 0),
                win_ev=float(e.get('win_ev', 0) or 0),
                place_ev=float(e.get('place_ev', 0) or 0),
            ))
        pred_index[race_id] = RacePrediction(
            race_id=race_id,
            entry_count=len(entries),
            entries=entries,
        )
    return pred_index


# ============================================================
# 可変戦略ルール
# ============================================================

def get_top_entries(pred: RacePrediction, rank_key: str = 'rank_w') -> list:
    """rank_w or rank_p or wp_sum でソートした上位を返す"""
    if rank_key == 'wp_sum':
        valid = [e for e in pred.entries if e.rank_w > 0 and e.rank_p > 0]
        return sorted(valid, key=lambda e: e.rank_w + e.rank_p)
    return sorted(
        [e for e in pred.entries if getattr(e, rank_key, 0) > 0],
        key=lambda e: getattr(e, rank_key)
    )


def variable_select(pred: RacePrediction, rule: dict) -> Optional[list]:
    """
    ルールに基づいて可変頭数を選択。
    返り値:
      - list: 選択された馬リスト（1〜5頭）
      - None: このレースは条件外（=その週は購入しない）

    rule の keys:
      rank_key: 'rank_w' or 'rank_p'
      min_ard_1st: 1位の最低ARd（これ未満は条件外）
      thresholds: [(ard_gap_12, n_horses), ...] 降順でマッチ
        ard_gap_12: 1位-2位のARd差がこれ以上なら n_horses 頭
      default_n: どの閾値にもマッチしなかった場合のデフォルト頭数
      max_n: 最大頭数
      ard_floor: 選択馬のARd最低ライン（これ未満はカット）
    """
    rank_key = rule.get('rank_key', 'rank_w')
    top = get_top_entries(pred, rank_key)
    if not top:
        return None

    ard_1st = top[0].ar_deviation
    ard_2nd = top[1].ar_deviation if len(top) > 1 else 0
    ard_3rd = top[2].ar_deviation if len(top) > 2 else 0

    # 最低条件チェック
    min_ard_1st = rule.get('min_ard_1st', 0)
    if min_ard_1st > 0 and ard_1st < min_ard_1st:
        return None

    gap_12 = ard_1st - ard_2nd
    gap_23 = ard_2nd - ard_3rd

    # 閾値マッチング
    n = rule.get('default_n', 3)
    for threshold in rule.get('thresholds', []):
        cond_type = threshold.get('cond', 'gap_12')
        cond_val = threshold.get('val', 0)
        target_n = threshold.get('n', 3)

        if cond_type == 'gap_12' and gap_12 >= cond_val:
            n = target_n
            break
        elif cond_type == 'gap_23' and gap_23 >= cond_val:
            n = target_n
            break
        elif cond_type == 'ard_1st' and ard_1st >= cond_val:
            n = target_n
            break
        elif cond_type == 'ard_3rd_low' and ard_3rd < cond_val:
            n = target_n
            break

    max_n = rule.get('max_n', 5)
    n = min(n, max_n)
    selected = top[:n]

    # ARdフロア
    ard_floor = rule.get('ard_floor', 0)
    if ard_floor > 0:
        selected = [e for e in selected if e.ar_deviation >= ard_floor]
        if not selected:
            return None

    return selected


# ============================================================
# ルール定義: 網羅的に試すバリエーション
# ============================================================

def build_rules() -> dict:
    """テストする全ルールを生成"""
    rules = {}

    # --- グループ1: gap_12ベース (1位-2位差で頭数決定) ---
    # W-model版
    for min_ard in [0, 50, 55]:
        for gap_1h in [15, 12, 10, 8]:  # 1頭にする閾値
            for gap_2h in [8, 6, 5]:      # 2頭にする閾値
                for gap_3h in [3, 0]:       # 3頭にする閾値
                    for default in [3, 4, 5]:
                        name = f"w_gap_{min_ard}_{gap_1h}_{gap_2h}_{gap_3h}_d{default}"
                        thresholds = []
                        thresholds.append({'cond': 'gap_12', 'val': gap_1h, 'n': 1})
                        thresholds.append({'cond': 'gap_12', 'val': gap_2h, 'n': 2})
                        if gap_3h > 0:
                            thresholds.append({'cond': 'gap_12', 'val': gap_3h, 'n': 3})
                        rules[name] = {
                            'rank_key': 'rank_w',
                            'min_ard_1st': min_ard,
                            'thresholds': thresholds,
                            'default_n': default,
                            'max_n': 5,
                        }

    # --- グループ2: ARd1位の値ベース ---
    for min_ard in [0, 50, 55]:
        rules[f"w_ard1st_{min_ard}_tiered"] = {
            'rank_key': 'rank_w',
            'min_ard_1st': min_ard,
            'thresholds': [
                {'cond': 'ard_1st', 'val': 70, 'n': 1},
                {'cond': 'ard_1st', 'val': 65, 'n': 2},
                {'cond': 'ard_1st', 'val': 60, 'n': 3},
                {'cond': 'ard_1st', 'val': 55, 'n': 4},
            ],
            'default_n': 5,
            'max_n': 5,
        }

    # --- グループ3: gap_12 + gap_23 複合 ---
    for min_ard in [0, 50]:
        rules[f"w_dualgap_{min_ard}"] = {
            'rank_key': 'rank_w',
            'min_ard_1st': min_ard,
            'thresholds': [
                {'cond': 'gap_12', 'val': 12, 'n': 1},
                {'cond': 'gap_12', 'val': 6, 'n': 2},
                {'cond': 'gap_23', 'val': 5, 'n': 3},  # 2位-3位差が大きい→3頭で十分
            ],
            'default_n': 4,
            'max_n': 5,
        }

    # --- グループ4: P-model版 ---
    for min_ard in [0, 50]:
        for gap_1h in [12, 10]:
            for gap_2h in [6, 5]:
                name = f"p_gap_{min_ard}_{gap_1h}_{gap_2h}_d3"
                rules[name] = {
                    'rank_key': 'rank_p',
                    'min_ard_1st': min_ard,
                    'thresholds': [
                        {'cond': 'gap_12', 'val': gap_1h, 'n': 1},
                        {'cond': 'gap_12', 'val': gap_2h, 'n': 2},
                    ],
                    'default_n': 3,
                    'max_n': 5,
                }

    # --- グループ5: ARdフロア付き ---
    for floor in [45, 48, 50]:
        rules[f"w_floor{floor}_gap"] = {
            'rank_key': 'rank_w',
            'min_ard_1st': 0,
            'thresholds': [
                {'cond': 'gap_12', 'val': 12, 'n': 1},
                {'cond': 'gap_12', 'val': 6, 'n': 2},
                {'cond': 'gap_12', 'val': 3, 'n': 3},
            ],
            'default_n': 5,
            'max_n': 5,
            'ard_floor': floor,
        }

    # --- グループ7: WP合算 + ARd gap制御 (ハイブリッド) ---
    for floor in [45, 48, 50]:
        rules[f"wp_gap_f{floor}"] = {
            'rank_key': 'wp_sum',
            'min_ard_1st': 0,
            'thresholds': [
                {'cond': 'gap_12', 'val': 12, 'n': 1},
                {'cond': 'gap_12', 'val': 6, 'n': 2},
                {'cond': 'gap_12', 'val': 3, 'n': 3},
            ],
            'default_n': 5,
            'max_n': 5,
            'ard_floor': floor,
        }

    # --- グループ6: シンプル固定 (ベースライン比較用) ---
    for n in [1, 2, 3, 4, 5]:
        rules[f"w_fixed_{n}"] = {
            'rank_key': 'rank_w',
            'min_ard_1st': 0,
            'thresholds': [],
            'default_n': n,
            'max_n': n,
        }
        rules[f"p_fixed_{n}"] = {
            'rank_key': 'rank_p',
            'min_ard_1st': 0,
            'thresholds': [],
            'default_n': n,
            'max_n': n,
        }

    return rules


# ============================================================
# シミュレーション実行
# ============================================================

def simulate_week(week: Win5Week, pred_index: dict, rule: dict) -> Optional[dict]:
    """
    1週分のシミュレーション。
    Returns None if any race has no prediction data or rule returns None (skip week).
    """
    selections = []  # per-race: list of selected entries
    for race in week.races:
        pred = pred_index.get(race.race_id)
        if not pred:
            return None

        selected = variable_select(pred, rule)
        if selected is None:
            # 条件外 → この週は購入しない
            return {'skipped': True, 'date': week.date}

        selections.append(selected)

    # 点数計算
    tickets_per_race = [len(s) for s in selections]
    total_tickets = 1
    for t in tickets_per_race:
        total_tickets *= t

    # 的中判定
    covered = []
    for i, race in enumerate(week.races):
        selected_umaban = {e.umaban for e in selections[i]}
        covered.append(race.winner_umaban in selected_umaban)

    is_hit = all(covered)

    return {
        'skipped': False,
        'date': week.date,
        'tickets_per_race': tickets_per_race,
        'total_tickets': total_tickets,
        'cost': total_tickets * 100,
        'is_hit': is_hit,
        'payout': week.payout if is_hit else 0,
        'covered_count': sum(covered),
        'covered_detail': covered,
    }


def run_simulation(weeks: list, pred_index: dict, rules: dict) -> dict:
    """全ルールでシミュレーション実行"""
    results = {}

    for rule_name, rule in rules.items():
        week_results = []
        skipped = 0
        for week in weeks:
            res = simulate_week(week, pred_index, rule)
            if res is None:
                continue  # 予測データなし
            if res.get('skipped'):
                skipped += 1
                continue
            week_results.append(res)

        if not week_results:
            continue

        hits = [r for r in week_results if r['is_hit']]
        total_cost = sum(r['cost'] for r in week_results)
        total_payout = sum(r['payout'] for r in hits)

        ticket_counts = [r['total_tickets'] for r in week_results]
        avg_covered = np.mean([r['covered_count'] for r in week_results])

        results[rule_name] = {
            'total_weeks_available': len(week_results) + skipped,
            'played_weeks': len(week_results),
            'skipped_weeks': skipped,
            'hit_count': len(hits),
            'hit_rate': len(hits) / len(week_results) if week_results else 0,
            'avg_tickets': np.mean(ticket_counts),
            'median_tickets': np.median(ticket_counts),
            'min_tickets': min(ticket_counts),
            'max_tickets': max(ticket_counts),
            'total_cost': total_cost,
            'total_payout': total_payout,
            'roi': total_payout / total_cost if total_cost > 0 else 0,
            'avg_covered': avg_covered,
            'hit_payouts': [r['payout'] for r in hits],
            'hit_dates': [r['date'] for r in hits],
            'hit_tickets': [r['total_tickets'] for r in hits],
        }

    return results


# ============================================================
# レポート
# ============================================================

def print_report(results: dict):
    """結果レポート"""
    print(f"\n{'='*70}")
    print(f"  WIN5 可変点数シミュレーション結果")
    print(f"{'='*70}")

    # ROI順にソート
    sorted_rules = sorted(results.items(), key=lambda x: -x[1]['roi'])

    # --- Top 30 サマリー ---
    print(f"\n{'='*70}")
    print(f"  ROI上位30戦略")
    print(f"{'='*70}")
    print(f"{'戦略名':<40} {'参加':>4} {'skip':>4} {'的中':>4} {'率':>6} "
          f"{'平均点':>8} {'中央点':>8} {'投資':>12} {'払戻':>12} {'ROI':>7}")
    print(f"{'-'*120}")

    for name, s in sorted_rules[:30]:
        print(f"{name:<40} {s['played_weeks']:>4} {s['skipped_weeks']:>4} "
              f"{s['hit_count']:>4} {s['hit_rate']:>5.1%} "
              f"{s['avg_tickets']:>8.0f} {s['median_tickets']:>8.0f} "
              f"{s['total_cost']:>12,} {s['total_payout']:>12,} "
              f"{s['roi']:>6.1%}")

    # --- 的中1回以上 & 投資1000万以下で ROI上位 ---
    print(f"\n{'='*70}")
    print(f"  実用的戦略（的中1+, 投資1000万以下, ROI順）")
    print(f"{'='*70}")
    practical = [(n, s) for n, s in sorted_rules
                 if s['hit_count'] >= 1 and s['total_cost'] <= 10_000_000]
    print(f"{'戦略名':<40} {'参加':>4} {'skip':>4} {'的中':>4} {'率':>6} "
          f"{'平均点':>8} {'中央点':>8} {'投資':>12} {'払戻':>12} {'ROI':>7}")
    print(f"{'-'*120}")
    for name, s in practical[:20]:
        print(f"{name:<40} {s['played_weeks']:>4} {s['skipped_weeks']:>4} "
              f"{s['hit_count']:>4} {s['hit_rate']:>5.1%} "
              f"{s['avg_tickets']:>8.0f} {s['median_tickets']:>8.0f} "
              f"{s['total_cost']:>12,} {s['total_payout']:>12,} "
              f"{s['roi']:>6.1%}")

    # --- 低予算帯（週平均5000円以下）---
    print(f"\n{'='*70}")
    print(f"  低予算帯（平均点数50以下 = 週5000円以下, ROI順）")
    print(f"{'='*70}")
    low_budget = [(n, s) for n, s in sorted_rules
                  if s['avg_tickets'] <= 50]
    print(f"{'戦略名':<40} {'参加':>4} {'skip':>4} {'的中':>4} {'率':>6} "
          f"{'平均点':>8} {'中央点':>8} {'投資':>12} {'払戻':>12} {'ROI':>7}")
    print(f"{'-'*120}")
    for name, s in low_budget[:20]:
        print(f"{name:<40} {s['played_weeks']:>4} {s['skipped_weeks']:>4} "
              f"{s['hit_count']:>4} {s['hit_rate']:>5.1%} "
              f"{s['avg_tickets']:>8.0f} {s['median_tickets']:>8.0f} "
              f"{s['total_cost']:>12,} {s['total_payout']:>12,} "
              f"{s['roi']:>6.1%}")

    # --- 中予算帯（週平均5万円以下）---
    print(f"\n{'='*70}")
    print(f"  中予算帯（平均点数500以下 = 週5万円以下, ROI順）")
    print(f"{'='*70}")
    mid_budget = [(n, s) for n, s in sorted_rules
                  if 50 < s['avg_tickets'] <= 500]
    print(f"{'戦略名':<40} {'参加':>4} {'skip':>4} {'的中':>4} {'率':>6} "
          f"{'平均点':>8} {'中央点':>8} {'投資':>12} {'払戻':>12} {'ROI':>7}")
    print(f"{'-'*120}")
    for name, s in mid_budget[:20]:
        print(f"{name:<40} {s['played_weeks']:>4} {s['skipped_weeks']:>4} "
              f"{s['hit_count']:>4} {s['hit_rate']:>5.1%} "
              f"{s['avg_tickets']:>8.0f} {s['median_tickets']:>8.0f} "
              f"{s['total_cost']:>12,} {s['total_payout']:>12,} "
              f"{s['roi']:>6.1%}")

    # --- 的中詳細（ROI上位10戦略）---
    print(f"\n{'='*70}")
    print(f"  的中詳細（ROI上位10戦略の的中内訳）")
    print(f"{'='*70}")
    for name, s in sorted_rules[:10]:
        if s['hit_count'] == 0:
            continue
        print(f"\n  [{name}] ROI={s['roi']:.1%} 的中{s['hit_count']}回")
        for i in range(s['hit_count']):
            print(f"    {s['hit_dates'][i]} : {s['hit_tickets'][i]:>6}点 → ¥{s['hit_payouts'][i]:>12,}")

    # --- skip率分析 ---
    print(f"\n{'='*70}")
    print(f"  Skip率分析（min_ard > 0 のルール）")
    print(f"{'='*70}")
    skip_rules = [(n, s) for n, s in sorted_rules
                  if s['skipped_weeks'] > 0]
    print(f"{'戦略名':<40} {'全週':>4} {'参加':>4} {'skip':>4} {'skip率':>6} {'的中':>4} {'ROI':>7}")
    print(f"{'-'*80}")
    for name, s in sorted(skip_rules, key=lambda x: -x[1]['skipped_weeks'])[:20]:
        skip_rate = s['skipped_weeks'] / s['total_weeks_available'] if s['total_weeks_available'] > 0 else 0
        print(f"{name:<40} {s['total_weeks_available']:>4} {s['played_weeks']:>4} "
              f"{s['skipped_weeks']:>4} {skip_rate:>5.1%} "
              f"{s['hit_count']:>4} {s['roi']:>6.1%}")


def main():
    print(f"{'='*70}")
    print(f"  WIN5 可変点数シミュレーター")
    print(f"{'='*70}")

    # データロード
    print("\n[Load] WIN5スケジュール...")
    weeks = load_win5_schedule()
    print(f"  {len(weeks)}週")

    print("[Load] 予測データ...")
    pred_index = load_backtest_cache()
    print(f"  {len(pred_index)}レース")

    # マッチング
    matched_weeks = []
    for week in weeks:
        race_ids = [r.race_id for r in week.races]
        if all(rid in pred_index for rid in race_ids):
            matched_weeks.append(week)
    print(f"[Match] {len(matched_weeks)}/{len(weeks)}週")

    if not matched_weeks:
        print("マッチする週がありません")
        return

    print(f"  期間: {matched_weeks[0].date} 〜 {matched_weeks[-1].date}")

    # ルール生成
    rules = build_rules()
    print(f"\n[Rules] {len(rules)}ルールを生成")

    # シミュレーション
    print("[Simulate] シミュレーション中...")
    results = run_simulation(matched_weeks, pred_index, rules)
    print(f"  {len(results)}ルールの結果を取得")

    # レポート
    print_report(results)

    # JSON保存
    out_path = ml_dir() / "win5_variable_results.json"
    serializable = {}
    for name, s in results.items():
        serializable[name] = {
            k: (float(v) if isinstance(v, (np.floating, np.integer)) else v)
            for k, v in s.items()
        }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)
    print(f"\n[Save] {out_path}")


if __name__ == '__main__':
    main()
