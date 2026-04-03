#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WIN5 推奨馬ピッカー

指定日のWIN5対象レースに対して4プラン(A/B/C/D)で推奨馬を出力する。
combo_sim と同一の戦略を使用。

Plan A: WPs2固定         — WP合算rank top2 (32点, ¥3,200/週)
Plan B: WPs2+kb1+idm1   — WP合算top2 ∪ KB印◎ ∪ IDM1位 (~71点, ¥7,100/週)
Plan C: field_adaptive   — 頭数適応 (12以下→1頭, 14以上→3頭, 他→2頭, ~94点 ¥9,400/週)
Plan D: WPs3固定         — WP合算rank top3 (243点, ¥24,300/週) [参考]

Usage:
    python -m ml.win5_pick --date 2026-01-25
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from core import config, db


# ============================================================
# 共通ソートユーティリティ
# ============================================================

KB_MARK_ORDER = {'\u25ce': 1, '\u25cb': 2, '\u25b2': 3, '\u25b3': 4, '\u25bd': 5, '\u00d7': 6, '': 99}


def wps_sorted(entries: list) -> list:
    """WP合算rank (rank_w + rank_p) でソート"""
    valid = [e for e in entries
             if (e.get('rank_w') or 0) > 0 and (e.get('rank_p') or 0) > 0]
    return sorted(valid, key=lambda e: e['rank_w'] + e['rank_p'])


def kb_mark_top(entries: list, n: int) -> list:
    """競馬ブック印順で上位N頭の馬番リスト"""
    s = sorted(entries, key=lambda e: (
        KB_MARK_ORDER.get(e.get('kb_mark', ''), 99),
        -float(e.get('kb_rating', 0) or 0)
    ))
    return [int(e['umaban']) for e in s[:n]]


def idm_top(entries: list, n: int) -> list:
    """JRDB IDM順で上位N頭の馬番リスト"""
    s = sorted(entries, key=lambda e: -float(e.get('jrdb_idm', 0) or 0))
    return [int(e['umaban']) for e in s[:n]]


def wps_top(entries: list, n: int) -> list:
    """WP合算rank上位N頭の馬番リスト"""
    return [int(e['umaban']) for e in wps_sorted(entries)[:n]]


def union(*lists) -> list:
    """複数リストの和集合"""
    s = set()
    for l in lists:
        s.update(l)
    return list(s)


# ============================================================
# 戦略定義 (combo_sim と完全同一)
# ============================================================

def plan_a_select(entries: list, race_info: dict = None) -> list:
    """Plan A: WPs2固定 — WP合算rank top2"""
    return wps_top(entries, 2)


def plan_b_select(entries: list, race_info: dict = None) -> list:
    """Plan B: WPs2+kb1+idm1 — WP合算top2 ∪ KB印◎ ∪ IDM1位"""
    return union(wps_top(entries, 2), kb_mark_top(entries, 1), idm_top(entries, 1))


def plan_c_select(entries: list, race_info: dict = None) -> list:
    """Plan C: field_adaptive — 頭数12以下→1頭, 14以上→3頭, 他→2頭"""
    num_runners = len(entries)
    if race_info:
        num_runners = race_info.get('num_runners', num_runners)
    if num_runners <= 12:
        n = 1
    elif num_runners >= 14:
        n = 3
    else:
        n = 2
    return wps_top(entries, n)


def plan_d_select(entries: list, race_info: dict = None) -> list:
    """Plan D: WPs3固定 — WP合算rank top3 [参考]"""
    return wps_top(entries, 3)


PLANS = {
    'A': {
        'label': 'Plan A: WP合算 Top2 (32点/週)',
        'select': plan_a_select,
        'reference': False,
    },
    'B': {
        'label': 'Plan B: WP合算2+KB印◎+IDM1位 (~71点/週)',
        'select': plan_b_select,
        'reference': False,
    },
    'C': {
        'label': 'Plan C: 頭数適応 WP合算 (~94点/週)',
        'select': plan_c_select,
        'reference': False,
    },
    'D': {
        'label': 'Plan D: WP合算 Top3 (243点/週)',
        'select': plan_d_select,
        'reference': True,
    },
}


# ============================================================
# WIN5対象レース取得
# ============================================================

def get_win5_race_ids(date: str) -> Optional[list]:
    """mykeibadbからWIN5対象レースIDを取得"""
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
    """predictions.json からレース予測を読み込み (race_id -> race dict)"""
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
# レース情報
# ============================================================

VENUE_MAP = {
    '01': '札幌', '02': '函館', '03': '福島', '04': '新潟',
    '05': '東京', '06': '中山', '07': '中京', '08': '京都',
    '09': '阪神', '10': '小倉',
}


def race_id_to_venue_race(race_id: str) -> tuple:
    venue_code = race_id[8:10]
    race_num = int(race_id[14:16])
    venue_name = VENUE_MAP.get(venue_code, f'場{venue_code}')
    return venue_name, race_num


def get_race_info(race_id: str, date: str) -> dict:
    parts = date.split('-')
    race_path = config.races_dir() / parts[0] / parts[1] / parts[2] / f"race_{race_id}.json"
    if not race_path.exists():
        return {}
    with open(race_path, encoding='utf-8') as f:
        return json.load(f)


def extract_pick_info(entry: dict) -> dict:
    return {
        'umaban': int(entry.get('umaban', 0)),
        'horse_name': entry.get('horse_name', ''),
        'odds': float(entry.get('odds', 0) or 0),
        'odds_rank': int(entry.get('odds_rank', 0) or 0),
        'rank_w': int(entry.get('rank_w', 0) or 0),
        'rank_p': int(entry.get('rank_p', 0) or 0),
        'ar_deviation': round(float(entry.get('ar_deviation', 0) or 0), 1),
        'win_ev': round(float(entry.get('win_ev', 0) or 0), 2),
        'place_ev': round(float(entry.get('place_ev', 0) or 0), 2),
        'pred_proba_w_cal': float(entry.get('pred_proba_w_cal', 0) or 0),
        'pred_proba_p_raw': float(entry.get('pred_proba_p_raw', 0) or 0),
        'kb_mark': entry.get('kb_mark', ''),
        'kb_rating': float(entry.get('kb_rating', 0) or 0),
        'jrdb_idm': float(entry.get('jrdb_idm', 0) or 0),
    }


# ============================================================
# 出力
# ============================================================

def print_picks(date: str, win5_races: list, pred_index: dict, race_infos: dict):
    print(f"\n{'='*70}")
    print(f"  WIN5 推奨馬  {date}")
    print(f"{'='*70}")

    for plan_key, plan in PLANS.items():
        ref_tag = " [参考]" if plan['reference'] else ""
        print(f"\n{'─'*70}")
        print(f"  {plan['label']}{ref_tag}")
        print(f"{'─'*70}")

        total_tickets = 1
        for i, race_id in enumerate(win5_races):
            race_data = pred_index.get(race_id)
            venue, race_num = race_id_to_venue_race(race_id)
            info = race_infos.get(race_id, {})
            race_name = info.get('race_name', '')

            if not race_data:
                print(f"\n  R{i+1}: {venue}{race_num}R {race_name}")
                print(f"       予測データなし")
                total_tickets = 0
                continue

            entries = race_data.get('entries', [])
            race_info = {
                'num_runners': race_data.get('num_runners', len(entries)),
                'is_handicap': race_data.get('is_handicap', False),
            }
            selected_umaban = plan['select'](entries, race_info)

            if not selected_umaban:
                print(f"\n  R{i+1}: {venue}{race_num}R {race_name} → 選択なし")
                total_tickets = 0
                continue

            n = len(selected_umaban)
            total_tickets *= n

            top = wps_sorted(entries)
            ard_1st = float(top[0].get('ar_deviation', 0)) if top else 0
            num_r = race_info['num_runners']

            print(f"\n  R{i+1}: {venue}{race_num}R {race_name}  "
                  f"({num_r}頭, ARd1位={ard_1st:.1f}) → {n}頭")

            picks = [e for e in entries if int(e.get('umaban', 0)) in selected_umaban]
            picks.sort(key=lambda e: (e.get('rank_w', 99) + e.get('rank_p', 99)))

            for e in picks:
                mark = f" {e.get('kb_mark','')}" if e.get('kb_mark') else ""
                idm_v = float(e.get('jrdb_idm', 0) or 0)
                idm_s = f" IDM={idm_v:.0f}" if idm_v else ""
                print(f"       {int(e.get('umaban',0)):>2}番 {e.get('horse_name',''):<10} "
                      f"Rw={int(e.get('rank_w',0))} Rp={int(e.get('rank_p',0))} "
                      f"ARd={float(e.get('ar_deviation',0)):>5.1f} "
                      f"odds={float(e.get('odds',0)):>5.1f}({e.get('odds_rank',0)}人) "
                      f"WEV={float(e.get('win_ev',0)):.2f}{mark}{idm_s}")

        print(f"\n  → 合計 {total_tickets}点 (¥{total_tickets * 100:,})")

    # 参考一覧
    print(f"\n{'='*70}")
    print(f"  参考: WP合算 / rank_w / rank_p 上位3頭")
    print(f"{'='*70}")

    for i, race_id in enumerate(win5_races):
        race_data = pred_index.get(race_id)
        venue, race_num = race_id_to_venue_race(race_id)
        info = race_infos.get(race_id, {})
        race_name = info.get('race_name', '')
        if not race_data:
            continue
        entries = race_data.get('entries', [])
        top_wps = wps_sorted(entries)[:5]

        print(f"\n  R{i+1}: {venue}{race_num}R {race_name}")
        print(f"    WP合算:")
        for e in top_wps:
            mark = f" {e.get('kb_mark','')}" if e.get('kb_mark') else ""
            print(f"      Rw+Rp={e['rank_w']+e['rank_p']:>2} {int(e.get('umaban',0)):>2}番 "
                  f"{e.get('horse_name',''):<10} "
                  f"ARd={float(e.get('ar_deviation',0)):>5.1f} "
                  f"odds={float(e.get('odds',0)):>5.1f}({e.get('odds_rank',0)}人){mark}")


def save_json(date: str, win5_races: list, pred_index: dict, race_infos: dict):
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

    for plan_key, plan in PLANS.items():
        strat_result = {
            'label': plan['label'],
            'reference': plan['reference'],
            'legs': [],
            'total_tickets': 1,
        }
        for i, race_id in enumerate(win5_races):
            race_data = pred_index.get(race_id)
            if not race_data:
                strat_result['legs'].append({'leg': i + 1, 'picks': [], 'count': 0})
                strat_result['total_tickets'] = 0
                continue

            entries = race_data.get('entries', [])
            race_info = {
                'num_runners': race_data.get('num_runners', len(entries)),
                'is_handicap': race_data.get('is_handicap', False),
            }
            selected_umaban = plan['select'](entries, race_info)

            if not selected_umaban:
                strat_result['legs'].append({'leg': i + 1, 'picks': [], 'count': 0})
                strat_result['total_tickets'] = 0
                continue

            n = len(selected_umaban)
            strat_result['total_tickets'] *= n

            picks = [e for e in entries if int(e.get('umaban', 0)) in selected_umaban]
            picks.sort(key=lambda e: (e.get('rank_w', 99) + e.get('rank_p', 99)))

            strat_result['legs'].append({
                'leg': i + 1,
                'count': n,
                'picks': [extract_pick_info(e) for e in picks],
            })

        strat_result['cost'] = strat_result['total_tickets'] * 100
        output['strategies'][plan_key] = strat_result

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

    print(f"[WIN5] {date} の対象レースを取得...")
    win5_races = get_win5_race_ids(date)
    if not win5_races:
        print(f"  WIN5データが見つかりません（{date}）")
        return

    for i, rid in enumerate(win5_races):
        venue, race_num = race_id_to_venue_race(rid)
        print(f"  R{i+1}: {venue}{race_num}R ({rid})")

    print(f"\n[Load] predictions.json...")
    pred_index = load_predictions(date)
    if not pred_index:
        print(f"  predictions.json が見つかりません")
        print(f"  → 先に python -m ml.predict --date {date} を実行してください")
        return

    matched = sum(1 for r in win5_races if r in pred_index)
    print(f"  {matched}/{len(win5_races)} レースの予測データあり")

    race_infos = {}
    for rid in win5_races:
        info = get_race_info(rid, date)
        if info:
            race_infos[rid] = info

    print_picks(date, win5_races, pred_index, race_infos)

    if args.json or True:
        save_json(date, win5_races, pred_index, race_infos)


if __name__ == '__main__':
    main()
