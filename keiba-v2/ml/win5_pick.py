#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WIN5 推奨馬ピッカー

指定日のWIN5対象レースに対して上位戦略で推奨馬を出力する。

Usage:
    python -m ml.win5_pick --date 2026-01-25
    python -m ml.win5_pick --date 2026-01-25 --json
"""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core import config, db


# ============================================================
# データ構造
# ============================================================

@dataclass
class PickEntry:
    umaban: int
    horse_name: str
    odds: float
    odds_rank: int
    rank_w: int
    rank_p: int
    ar_deviation: float
    win_ev: float
    place_ev: float
    pred_proba_w_cal: float
    pred_proba_p_raw: float
    kb_mark: str
    kb_rating: float


# ============================================================
# WIN5対象レース取得
# ============================================================

def get_win5_race_ids(date: str) -> Optional[list]:
    """
    mykeibadbからWIN5対象レースIDを取得。
    date: YYYY-MM-DD
    Returns: [race_id1, ..., race_id5] or None
    """
    parts = date.split('-')
    year = parts[0]
    gappi = parts[1] + parts[2]

    rows = db.query("""
        SELECT RACE_CODE1, RACE_CODE2, RACE_CODE3, RACE_CODE4, RACE_CODE5
        FROM win5
        WHERE KAISAI_NEN = %s AND KAISAI_GAPPI = %s
    """, (year, gappi))

    if not rows:
        return None

    row = rows[0]
    race_ids = []
    for i in range(1, 6):
        code = (row.get(f'RACE_CODE{i}') or '').strip()
        if code:
            race_ids.append(code)
    return race_ids if len(race_ids) == 5 else None


# ============================================================
# predictions.json から予測データ取得
# ============================================================

def load_predictions(date: str) -> dict:
    """predictions.json からレース予測を読み込み"""
    parts = date.split('-')
    pred_path = config.races_dir() / parts[0] / parts[1] / parts[2] / "predictions.json"
    if not pred_path.exists():
        return {}

    with open(pred_path, encoding='utf-8') as f:
        data = json.load(f)

    index = {}
    for race in data.get('races', []):
        rid = race.get('race_id', '')
        if rid:
            index[rid] = race
    return index


# ============================================================
# 可変戦略ロジック（w_floor50_gap ベース）
# ============================================================

STRATEGIES = {
    'w_floor50_gap': {
        'label': '★1 ARd>=50 + Gap制御 (ROI 224%)',
        'rank_key': 'rank_w',
        'ard_floor': 50,
        'gap_rules': [(12, 1), (6, 2), (3, 3)],
        'default_n': 5,
    },
    'wp_gap_f48': {
        'label': 'WP合算 ARd>=48 + Gap制御 (ROI 110%, 的中8回)',
        'rank_key': 'wp_sum',
        'ard_floor': 48,
        'gap_rules': [(12, 1), (6, 2), (3, 3)],
        'default_n': 5,
    },
    'wp_gap_f50': {
        'label': 'WP合算 ARd>=50 + Gap制御 (ROI 106%, 的中8回)',
        'rank_key': 'wp_sum',
        'ard_floor': 50,
        'gap_rules': [(12, 1), (6, 2), (3, 3)],
        'default_n': 5,
    },
    'w_floor48_gap': {
        'label': '★2 ARd>=48 + Gap制御 (ROI 200%)',
        'rank_key': 'rank_w',
        'ard_floor': 48,
        'gap_rules': [(12, 1), (6, 2), (3, 3)],
        'default_n': 5,
    },
    'w_floor45_gap': {
        'label': '★3 ARd>=45 + Gap制御 (ROI 182%)',
        'rank_key': 'rank_w',
        'ard_floor': 45,
        'gap_rules': [(12, 1), (6, 2), (3, 3)],
        'default_n': 5,
    },
    'p_fixed_2': {
        'label': '低予算 P-Top2固定 32点 (ROI 113%)',
        'rank_key': 'rank_p',
        'ard_floor': 0,
        'gap_rules': [],
        'default_n': 2,
    },
}


def apply_strategy(race_data: dict, strategy: dict) -> list:
    """
    レースに戦略を適用して推奨馬を返す。
    Returns: list of PickEntry (推奨馬)
    """
    rank_key = strategy['rank_key']
    ard_floor = strategy['ard_floor']
    gap_rules = strategy['gap_rules']
    default_n = strategy['default_n']

    entries = race_data.get('entries', [])
    if not entries:
        return []

    # rank順にソート（wp_sum の場合は rank_w + rank_p の合計でソート）
    if rank_key == 'wp_sum':
        valid = [e for e in entries
                 if (e.get('rank_w') or 0) > 0 and (e.get('rank_p') or 0) > 0]
        sorted_entries = sorted(valid, key=lambda e: e['rank_w'] + e['rank_p'])
    else:
        sorted_entries = sorted(
            [e for e in entries if (e.get(rank_key) or 0) > 0],
            key=lambda e: e[rank_key]
        )
    if not sorted_entries:
        return []

    # gap計算
    ard_1st = float(sorted_entries[0].get('ar_deviation', 50) or 50)
    ard_2nd = float(sorted_entries[1].get('ar_deviation', 50) or 50) if len(sorted_entries) > 1 else 0

    gap_12 = ard_1st - ard_2nd

    # 頭数決定
    n = default_n
    for gap_threshold, target_n in gap_rules:
        if gap_12 >= gap_threshold:
            n = target_n
            break

    selected = sorted_entries[:n]

    # ARdフロアでフィルタ
    if ard_floor > 0:
        selected = [e for e in selected if float(e.get('ar_deviation', 0) or 0) >= ard_floor]

    # PickEntryに変換
    picks = []
    for e in selected:
        picks.append(PickEntry(
            umaban=int(e.get('umaban', 0)),
            horse_name=e.get('horse_name', ''),
            odds=float(e.get('odds', 0) or 0),
            odds_rank=int(e.get('odds_rank', 0) or 0),
            rank_w=int(e.get('rank_w', 0) or 0),
            rank_p=int(e.get('rank_p', 0) or 0),
            ar_deviation=float(e.get('ar_deviation', 0) or 0),
            win_ev=float(e.get('win_ev', 0) or 0),
            place_ev=float(e.get('place_ev', 0) or 0),
            pred_proba_w_cal=float(e.get('pred_proba_w_cal', 0) or 0),
            pred_proba_p_raw=float(e.get('pred_proba_p_raw', 0) or 0),
            kb_mark=e.get('kb_mark', ''),
            kb_rating=float(e.get('kb_rating', 0) or 0),
        ))
    return picks


# ============================================================
# レース情報取得
# ============================================================

def get_race_info(race_id: str, date: str) -> dict:
    """race_*.json からレース名等を取得"""
    parts = date.split('-')
    race_path = config.races_dir() / parts[0] / parts[1] / parts[2] / f"race_{race_id}.json"
    if not race_path.exists():
        return {}
    with open(race_path, encoding='utf-8') as f:
        return json.load(f)


VENUE_MAP = {
    '01': '札幌', '02': '函館', '03': '福島', '04': '新潟',
    '05': '東京', '06': '中山', '07': '中京', '08': '京都',
    '09': '阪神', '10': '小倉',
}


def race_id_to_venue_race(race_id: str) -> tuple:
    """race_idから場名とR番号を取得"""
    venue_code = race_id[12:14]
    race_num = int(race_id[14:16])
    venue_name = VENUE_MAP.get(venue_code, f'場{venue_code}')
    return venue_name, race_num


# ============================================================
# 出力
# ============================================================

def print_picks(date: str, win5_races: list, pred_index: dict, race_infos: dict):
    """コンソール出力"""
    print(f"\n{'='*70}")
    print(f"  WIN5 推奨馬  {date}")
    print(f"{'='*70}")

    for strat_name, strat in STRATEGIES.items():
        print(f"\n{'─'*70}")
        print(f"  {strat['label']}")
        print(f"{'─'*70}")

        total_tickets = 1
        race_picks = []

        for i, race_id in enumerate(win5_races):
            race_data = pred_index.get(race_id)
            venue, race_num = race_id_to_venue_race(race_id)

            # レース名取得
            info = race_infos.get(race_id, {})
            race_name = info.get('race_name', '')

            if not race_data:
                print(f"\n  R{i+1}: {venue}{race_num}R {race_name}")
                print(f"       予測データなし")
                race_picks.append([])
                total_tickets = 0
                continue

            picks = apply_strategy(race_data, strat)
            race_picks.append(picks)
            n = len(picks) if picks else 0
            total_tickets *= max(n, 1)

            # ヘッダ
            entries = race_data.get('entries', [])
            sorted_by_w = sorted(
                [e for e in entries if (e.get('rank_w') or 0) > 0],
                key=lambda e: e['rank_w']
            )
            ard_1st = float(sorted_by_w[0]['ar_deviation']) if sorted_by_w else 0
            ard_2nd = float(sorted_by_w[1]['ar_deviation']) if len(sorted_by_w) > 1 else 0
            gap = ard_1st - ard_2nd

            print(f"\n  R{i+1}: {venue}{race_num}R {race_name}  "
                  f"({len(entries)}頭, ARd1位={ard_1st:.1f}, gap={gap:.1f}) → {n}頭")

            if not picks:
                print(f"       → 条件外（推奨なし）")
                continue

            for p in picks:
                mark = f" {p.kb_mark}" if p.kb_mark else ""
                print(f"       {p.umaban:>2}番 {p.horse_name:<10} "
                      f"Rw={p.rank_w} Rp={p.rank_p} ARd={p.ar_deviation:>5.1f} "
                      f"odds={p.odds:>5.1f}({p.odds_rank}人) "
                      f"WEV={p.win_ev:.2f} PEV={p.place_ev:.2f}{mark}")

        print(f"\n  → 合計 {total_tickets}点 (¥{total_tickets * 100:,})")

    # 参考: 各レースの1位-3位一覧
    print(f"\n{'='*70}")
    print(f"  参考: rank_w / rank_p 上位3頭")
    print(f"{'='*70}")

    for i, race_id in enumerate(win5_races):
        race_data = pred_index.get(race_id)
        venue, race_num = race_id_to_venue_race(race_id)
        info = race_infos.get(race_id, {})
        race_name = info.get('race_name', '')

        if not race_data:
            continue

        entries = race_data.get('entries', [])
        by_w = sorted([e for e in entries if (e.get('rank_w') or 0) > 0], key=lambda e: e['rank_w'])[:5]
        by_p = sorted([e for e in entries if (e.get('rank_p') or 0) > 0], key=lambda e: e['rank_p'])[:5]

        print(f"\n  R{i+1}: {venue}{race_num}R {race_name}")
        print(f"    rank_w:")
        for e in by_w:
            mark = f" {e.get('kb_mark','')}" if e.get('kb_mark') else ""
            print(f"      {e['rank_w']:>2}位 {e['umaban']:>2}番 {e.get('horse_name',''):<10} "
                  f"ARd={float(e.get('ar_deviation',0)):>5.1f} "
                  f"odds={float(e.get('odds',0)):>5.1f}({e.get('odds_rank',0)}人) "
                  f"WEV={float(e.get('win_ev',0)):.2f}{mark}")
        print(f"    rank_p:")
        for e in by_p:
            mark = f" {e.get('kb_mark','')}" if e.get('kb_mark') else ""
            print(f"      {e['rank_p']:>2}位 {e['umaban']:>2}番 {e.get('horse_name',''):<10} "
                  f"ARd={float(e.get('ar_deviation',0)):>5.1f} "
                  f"odds={float(e.get('odds',0)):>5.1f}({e.get('odds_rank',0)}人) "
                  f"PEV={float(e.get('place_ev',0)):.2f}{mark}")


def save_json(date: str, win5_races: list, pred_index: dict, race_infos: dict):
    """JSON出力"""
    output = {
        'date': date,
        'strategies': {},
    }

    races_info = []
    for i, race_id in enumerate(win5_races):
        venue, race_num = race_id_to_venue_race(race_id)
        info = race_infos.get(race_id, {})
        races_info.append({
            'leg': i + 1,
            'race_id': race_id,
            'venue': venue,
            'race_number': race_num,
            'race_name': info.get('race_name', ''),
            'num_runners': info.get('num_runners', 0),
        })
    output['races'] = races_info

    for strat_name, strat in STRATEGIES.items():
        strat_result = {
            'label': strat['label'],
            'legs': [],
            'total_tickets': 1,
        }
        for i, race_id in enumerate(win5_races):
            race_data = pred_index.get(race_id)
            if not race_data:
                strat_result['legs'].append({'leg': i + 1, 'picks': [], 'count': 0})
                strat_result['total_tickets'] = 0
                continue

            picks = apply_strategy(race_data, strat)
            n = len(picks) if picks else 0
            strat_result['total_tickets'] *= max(n, 1)

            leg_data = {
                'leg': i + 1,
                'count': n,
                'picks': [{
                    'umaban': p.umaban,
                    'horse_name': p.horse_name,
                    'odds': p.odds,
                    'odds_rank': p.odds_rank,
                    'rank_w': p.rank_w,
                    'rank_p': p.rank_p,
                    'ar_deviation': round(p.ar_deviation, 1),
                    'win_ev': round(p.win_ev, 2),
                    'place_ev': round(p.place_ev, 2),
                    'kb_mark': p.kb_mark,
                } for p in picks],
            }
            strat_result['legs'].append(leg_data)

        strat_result['cost'] = strat_result['total_tickets'] * 100
        output['strategies'][strat_name] = strat_result

    # 保存
    parts = date.split('-')
    out_dir = config.races_dir() / parts[0] / parts[1] / parts[2]
    out_path = out_dir / "win5_picks.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n[Save] {out_path}")
    return out_path


# ============================================================
# メイン
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='WIN5推奨馬ピッカー')
    parser.add_argument('--date', required=True, help='対象日 (YYYY-MM-DD)')
    parser.add_argument('--json', action='store_true', help='JSON出力も保存')
    args = parser.parse_args()

    date = args.date

    # WIN5対象レース取得
    print(f"[WIN5] {date} の対象レースを取得...")
    win5_races = get_win5_race_ids(date)
    if not win5_races:
        print(f"  WIN5データが見つかりません（{date}）")
        print(f"  → mykeibadbにWIN5スケジュールが登録されていない可能性があります")
        return

    for i, rid in enumerate(win5_races):
        venue, race_num = race_id_to_venue_race(rid)
        print(f"  R{i+1}: {venue}{race_num}R ({rid})")

    # predictions.json ロード
    print(f"\n[Load] predictions.json...")
    pred_index = load_predictions(date)
    if not pred_index:
        print(f"  predictions.json が見つかりません")
        print(f"  → 先に python -m ml.predict --date {date} を実行してください")
        return

    matched = sum(1 for r in win5_races if r in pred_index)
    print(f"  {matched}/{len(win5_races)} レースの予測データあり")

    # レース情報ロード
    race_infos = {}
    for rid in win5_races:
        info = get_race_info(rid, date)
        if info:
            race_infos[rid] = info

    # 推奨馬出力
    print_picks(date, win5_races, pred_index, race_infos)

    # JSON保存
    if args.json or True:  # 常に保存
        save_json(date, win5_races, pred_index, race_infos)


if __name__ == '__main__':
    main()
