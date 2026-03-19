#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
購入結果自動反映スクリプト

mykeibadb の確定配当データ（odds1_tansho, odds1_fukusho, haraimodoshi）を使い、
purchases/{date}.json の購入レコードを正確に精算する。

Usage:
    python -m ml.settle_purchases --date 2026-03-08
    python -m ml.settle_purchases --date 2026-03-08 --force   # 確定済みも再計算
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from core.db import query
from core.odds_db import get_final_win_odds, get_final_place_odds


def get_umaren_payouts(race_code: str) -> Dict[Tuple[int, int], int]:
    """haraimodoshi テーブルから馬連払い戻し金を取得

    Returns:
        {(umaban1, umaban2): payout_per_100yen}  ※100円あたりの払い戻し（順不同）
    """
    rows = query(
        "SELECT * FROM haraimodoshi WHERE RACE_CODE = %s", (race_code,)
    )
    if not rows:
        return {}

    row = rows[0]
    result = {}
    for i in range(1, 4):  # UMAREN1 ~ UMAREN3
        k1_key = f"UMAREN{i}_KUMIBAN1"
        k2_key = f"UMAREN{i}_KUMIBAN2"
        pay_key = f"UMAREN{i}_HARAIMODOSHIKIN"
        k1 = (row.get(k1_key) or '').strip()
        k2 = (row.get(k2_key) or '').strip()
        pay_raw = (row.get(pay_key) or '').strip()
        if not k1 or not k2 or not pay_raw:
            continue
        try:
            u1 = int(k1)
            u2 = int(k2)
            payout = int(pay_raw)
            if payout > 0:
                result[(min(u1, u2), max(u1, u2))] = payout
        except (ValueError, IndexError):
            continue
    return result


def get_umatan_payouts(race_code: str) -> Dict[Tuple[int, int], int]:
    """haraimodoshi テーブルから馬単払い戻し金を取得

    Returns:
        {(1着馬番, 2着馬番): payout_per_100yen}  ※順序あり
    """
    rows = query(
        "SELECT * FROM haraimodoshi WHERE RACE_CODE = %s", (race_code,)
    )
    if not rows:
        return {}

    row = rows[0]
    result = {}
    for i in range(1, 7):  # UMATAN1 ~ UMATAN6
        k1_key = f"UMATAN{i}_KUMIBAN1"
        k2_key = f"UMATAN{i}_KUMIBAN2"
        pay_key = f"UMATAN{i}_HARAIMODOSHIKIN"
        k1 = (row.get(k1_key) or '').strip()
        k2 = (row.get(k2_key) or '').strip()
        pay_raw = (row.get(pay_key) or '').strip()
        if not k1 or not k2 or not pay_raw:
            continue
        try:
            u1 = int(k1)
            u2 = int(k2)
            payout = int(pay_raw)
            if payout > 0:
                result[(u1, u2)] = payout  # 順序あり: (1着, 2着)
        except (ValueError, IndexError):
            continue
    return result


def get_wide_payouts(race_code: str) -> Dict[Tuple[int, int], int]:
    """haraimodoshi テーブルからワイド払い戻し金を取得

    Returns:
        {(umaban1, umaban2): payout_per_100yen}  ※100円あたりの払い戻し
    """
    rows = query(
        "SELECT * FROM haraimodoshi WHERE RACE_CODE = %s", (race_code,)
    )
    if not rows:
        return {}

    row = rows[0]
    result = {}
    for i in range(1, 8):  # WIDE1 ~ WIDE7
        k1_key = f"WIDE{i}_KUMIBAN1"
        k2_key = f"WIDE{i}_KUMIBAN2"
        pay_key = f"WIDE{i}_HARAIMODOSHIKIN"
        k1 = (row.get(k1_key) or '').strip()
        k2 = (row.get(k2_key) or '').strip()
        pay_raw = (row.get(pay_key) or '').strip()
        if not k1 or not k2 or not pay_raw:
            continue
        try:
            u1 = int(k1)
            u2 = int(k2)
            payout = int(pay_raw)
            if payout > 0:
                result[(min(u1, u2), max(u1, u2))] = payout
        except (ValueError, IndexError):
            continue
    return result


def get_db_finish_positions(race_code: str) -> Dict[int, int]:
    """umagoto_race_joho (SE) からDB直接で着順を取得（race JSONのフォールバック）"""
    rows = query(
        "SELECT UMABAN, KAKUTEI_CHAKUJUN FROM umagoto_race_joho "
        "WHERE RACE_CODE = %s AND KAKUTEI_CHAKUJUN IS NOT NULL AND KAKUTEI_CHAKUJUN != ''",
        (race_code,)
    )
    result = {}
    for r in rows:
        try:
            uma = int(r['UMABAN'])
            fp = int(r['KAKUTEI_CHAKUJUN'])
            result[uma] = fp
        except (ValueError, TypeError):
            continue
    return result


def get_db_num_runners(race_code: str) -> int:
    """race_shosai から出走頭数を取得"""
    rows = query(
        "SELECT SHUSSO_TOSU FROM race_shosai WHERE RACE_CODE = %s", (race_code,)
    )
    if rows:
        try:
            return int(rows[0].get('SHUSSO_TOSU', 18))
        except (ValueError, TypeError):
            pass
    return 18


def get_db_horse_names(race_code: str) -> Dict[str, int]:
    """umagoto_race_joho から horse_name -> umaban マッピング"""
    rows = query(
        "SELECT UMABAN, BAMEI FROM umagoto_race_joho WHERE RACE_CODE = %s",
        (race_code,)
    )
    result = {}
    for r in rows:
        name = (r.get('BAMEI') or '').strip()
        try:
            uma = int(r['UMABAN'])
            if name:
                result[name] = uma
        except (ValueError, TypeError):
            continue
    return result


def load_race_data(race_code: str, races_dir: Path) -> Optional[dict]:
    """race JSON を読み込み"""
    race_file = races_dir / f"race_{race_code}.json"
    if not race_file.exists():
        return None
    try:
        return json.loads(race_file.read_text(encoding='utf-8'))
    except Exception:
        return None


def get_name_to_umaban(race_data: dict) -> Dict[str, int]:
    """horse_name -> umaban マッピング"""
    result = {}
    for e in race_data.get('entries', []):
        name = e.get('horse_name', '')
        uma = e.get('umaban')
        if name and uma is not None:
            result[name] = uma
    return result


def resolve_wide_pair(item: dict, race_data: Optional[dict]) -> Optional[Tuple[int, int]]:
    """ワイドのペア馬番を解決

    wide_pair があればそれを使う。
    なければ selection "1-馬名A-馬名B" から馬名を抽出し、race JSONで馬番を逆引き。
    """
    wp = item.get('wide_pair')
    if wp and len(wp) == 2:
        return (min(wp), max(wp))

    # selection: "6-ワザオギ-アメリカンイズム" → horse_name で逆引き
    selection = item.get('selection', '')
    parts = selection.split('-')
    if len(parts) < 3:
        return None

    # horse_name フィールドが "馬名A-馬名B" 形式
    horse_name = item.get('horse_name', '')
    names = horse_name.split('-') if horse_name else parts[1:]

    # race JSONから馬名マッピング、なければDBから
    name_map = get_name_to_umaban(race_data) if race_data else {}
    if not name_map:
        race_id = item.get('race_id', '')
        name_map = get_db_horse_names(race_id)

    umabans = []
    for name in names:
        name = name.strip()
        if name in name_map:
            umabans.append(name_map[name])

    if len(umabans) >= 2:
        return (min(umabans[0], umabans[1]), max(umabans[0], umabans[1]))
    return None


def settle(date: str, force: bool = False) -> dict:
    """購入レコードを精算"""
    purchases_path = config.userdata_dir() / 'purchases' / f'{date}.json'
    if not purchases_path.exists():
        return {'error': 'No purchase data found'}

    purchases = json.loads(purchases_path.read_text(encoding='utf-8'))
    items = purchases.get('items', [])
    if not items:
        return {'message': 'Empty items', 'settled': 0}

    y, m, d = date.split('-')
    races_dir = config.races_dir() / y / m / d

    # キャッシュ
    win_odds_cache: Dict[str, Dict[int, dict]] = {}
    place_odds_cache: Dict[str, Dict[int, dict]] = {}
    wide_payout_cache: Dict[str, Dict[Tuple[int, int], int]] = {}
    umaren_payout_cache: Dict[str, Dict[Tuple[int, int], int]] = {}
    umatan_payout_cache: Dict[str, Dict[Tuple[int, int], int]] = {}
    race_data_cache: Dict[str, Optional[dict]] = {}

    settled_count = 0
    win_count = 0
    total_payout = 0

    for item in items:
        status = item.get('status', '')
        if not force and status in ('result_win', 'result_lose'):
            continue
        if status == 'planned':
            continue

        race_id = item['race_id']
        bet_type = item.get('bet_type', '')
        selection = item.get('selection', '')
        amount = item.get('amount', 0)

        # race data 取得
        if race_id not in race_data_cache:
            race_data_cache[race_id] = load_race_data(race_id, races_dir)
        race_data = race_data_cache[race_id]

        # 着順取得: race JSON → DBフォールバック
        fps: Dict[int, int] = {}
        num_runners = 18
        if race_data:
            entries = race_data.get('entries', [])
            fps = {e['umaban']: e.get('finish_position', 0)
                   for e in entries if e.get('umaban') is not None}
            num_runners = race_data.get('num_runners', len(entries))

        # race JSONの着順が全て0 or race JSONなし → DBから取得
        if not fps or all(fp == 0 for fp in fps.values()):
            db_fps = get_db_finish_positions(race_id)
            if db_fps:
                fps = db_fps
                num_runners = get_db_num_runners(race_id) or len(db_fps)

        if not fps or all(fp == 0 for fp in fps.values()):
            continue

        now = datetime.now().isoformat()

        if bet_type in ('単勝',):
            umaban = int(selection.split('-')[0])
            fp = fps.get(umaban, 0)
            if fp == 0:
                continue

            if fp == 1:
                if race_id not in win_odds_cache:
                    win_odds_cache[race_id] = get_final_win_odds(race_id)
                odds_data = win_odds_cache[race_id].get(umaban, {})
                odds = odds_data.get('odds', item.get('odds') or 1)
                payout = int(amount / 100 * odds * 100)
                item['status'] = 'result_win'
                item['payout'] = payout
                item['odds'] = odds
                win_count += 1
                total_payout += payout
            else:
                item['status'] = 'result_lose'
                item['payout'] = 0
            item['updated_at'] = now
            settled_count += 1

        elif bet_type in ('複勝',):
            umaban = int(selection.split('-')[0])
            fp = fps.get(umaban, 0)
            if fp == 0:
                continue

            place_limit = 3 if num_runners >= 8 else (2 if num_runners >= 5 else 1)
            if fp <= place_limit:
                if race_id not in place_odds_cache:
                    place_odds_cache[race_id] = get_final_place_odds(race_id)
                odds_data = place_odds_cache[race_id].get(umaban, {})
                odds_low = odds_data.get('odds_low')
                if odds_low:
                    payout = int(amount / 100 * odds_low * 100)
                    item['odds'] = odds_low
                else:
                    payout = amount
                    print(f"  [WARN] Place odds not found: {race_id} uma={umaban}")
                item['status'] = 'result_win'
                item['payout'] = payout
                win_count += 1
                total_payout += payout
            else:
                item['status'] = 'result_lose'
                item['payout'] = 0
            item['updated_at'] = now
            settled_count += 1

        elif bet_type in ('単複',):
            umaban = int(selection.split('-')[0])
            fp = fps.get(umaban, 0)
            if fp == 0:
                continue

            win_amount = item.get('win_amount', amount // 2)
            place_amount = item.get('place_amount', amount - win_amount)
            place_limit = 3 if num_runners >= 8 else (2 if num_runners >= 5 else 1)

            payout = 0
            is_win = False

            if fp == 1:
                if race_id not in win_odds_cache:
                    win_odds_cache[race_id] = get_final_win_odds(race_id)
                odds_data = win_odds_cache[race_id].get(umaban, {})
                odds = odds_data.get('odds', item.get('odds') or 1)
                payout += int(win_amount / 100 * odds * 100)
                is_win = True

            if fp <= place_limit:
                if race_id not in place_odds_cache:
                    place_odds_cache[race_id] = get_final_place_odds(race_id)
                odds_data = place_odds_cache[race_id].get(umaban, {})
                odds_low = odds_data.get('odds_low')
                if odds_low:
                    payout += int(place_amount / 100 * odds_low * 100)
                else:
                    payout += place_amount
                    print(f"  [WARN] Place odds not found: {race_id} uma={umaban}")
                is_win = True

            if is_win:
                item['status'] = 'result_win'
                item['payout'] = payout
                win_count += 1
                total_payout += payout
            else:
                item['status'] = 'result_lose'
                item['payout'] = 0
            item['updated_at'] = now
            settled_count += 1

        elif bet_type in ('ワイド',):
            pair = resolve_wide_pair(item, race_data)
            if not pair:
                print(f"  [WARN] Cannot resolve wide pair: {race_id} sel={selection}")
                continue

            u1, u2 = pair
            fp1 = fps.get(u1, 0)
            fp2 = fps.get(u2, 0)
            if fp1 == 0 or fp2 == 0:
                continue

            place_limit = 3 if num_runners >= 8 else (2 if num_runners >= 5 else 1)
            if fp1 <= place_limit and fp2 <= place_limit:
                if race_id not in wide_payout_cache:
                    wide_payout_cache[race_id] = get_wide_payouts(race_id)
                pair_key = (min(u1, u2), max(u1, u2))
                wide_pay = wide_payout_cache[race_id].get(pair_key)
                if wide_pay:
                    payout = int(amount / 100 * wide_pay)
                    item['odds'] = wide_pay / 100
                else:
                    payout = amount
                    print(f"  [WARN] Wide payout not found: {race_id} pair={pair_key}")
                item['status'] = 'result_win'
                item['payout'] = payout
                win_count += 1
                total_payout += payout
            else:
                item['status'] = 'result_lose'
                item['payout'] = 0
            item['updated_at'] = now
            settled_count += 1

        elif bet_type in ('馬連',):
            pair = resolve_wide_pair(item, race_data)
            if not pair:
                print(f"  [WARN] Cannot resolve umaren pair: {race_id} sel={selection}")
                continue

            u1, u2 = pair
            fp1 = fps.get(u1, 0)
            fp2 = fps.get(u2, 0)
            if fp1 == 0 or fp2 == 0:
                continue

            # 馬連的中: 1着-2着の組み合わせ（順不同）
            if set([fp1, fp2]) == {1, 2}:
                if race_id not in umaren_payout_cache:
                    umaren_payout_cache[race_id] = get_umaren_payouts(race_id)
                pair_key = (min(u1, u2), max(u1, u2))
                umaren_pay = umaren_payout_cache[race_id].get(pair_key)
                if umaren_pay:
                    payout = int(amount / 100 * umaren_pay)
                    item['odds'] = umaren_pay / 100
                else:
                    payout = amount
                    print(f"  [WARN] Umaren payout not found: {race_id} pair={pair_key}")
                item['status'] = 'result_win'
                item['payout'] = payout
                win_count += 1
                total_payout += payout
            else:
                item['status'] = 'result_lose'
                item['payout'] = 0
            item['updated_at'] = now
            settled_count += 1

        elif bet_type in ('馬単',):
            pair = resolve_wide_pair(item, race_data)
            if not pair:
                print(f"  [WARN] Cannot resolve umatan pair: {race_id} sel={selection}")
                continue

            u1, u2 = pair  # [1着候補, 2着候補] の順
            fp1 = fps.get(u1, 0)
            fp2 = fps.get(u2, 0)
            if fp1 == 0 or fp2 == 0:
                continue

            # 馬単的中: pair[0]が1着 かつ pair[1]が2着
            if fp1 == 1 and fp2 == 2:
                if race_id not in umatan_payout_cache:
                    umatan_payout_cache[race_id] = get_umatan_payouts(race_id)
                pair_key = (u1, u2)  # 順序あり
                umatan_pay = umatan_payout_cache[race_id].get(pair_key)
                if umatan_pay:
                    payout = int(amount / 100 * umatan_pay)
                    item['odds'] = umatan_pay / 100
                else:
                    payout = amount
                    print(f"  [WARN] Umatan payout not found: {race_id} pair={pair_key}")
                item['status'] = 'result_win'
                item['payout'] = payout
                win_count += 1
                total_payout += payout
            else:
                item['status'] = 'result_lose'
                item['payout'] = 0
            item['updated_at'] = now
            settled_count += 1

    # 合計再計算
    purchases['total_purchased'] = sum(
        i['amount'] for i in items
        if i.get('status') in ('purchased', 'result_win', 'result_lose')
    )
    purchases['total_payout'] = sum(
        i['payout'] for i in items if i.get('status') == 'result_win'
    )
    purchases['total_planned'] = sum(
        i['amount'] for i in items if i.get('status') == 'planned'
    )
    purchases['updated_at'] = datetime.now().isoformat()

    # 保存
    purchases_path.write_text(
        json.dumps(purchases, ensure_ascii=False, indent=2),
        encoding='utf-8'
    )

    profit = purchases['total_payout'] - purchases['total_purchased']
    print(f"\n[Settle] {date}")
    print(f"  Settled: {settled_count}, Wins: {win_count}")
    print(f"  Invested: {purchases['total_purchased']:,}")
    print(f"  Payout:   {purchases['total_payout']:,}")
    print(f"  Profit:   {profit:+,}")

    return {
        'success': True,
        'settled': settled_count,
        'wins': win_count,
        'totalPayout': total_payout,
        'totalInvested': purchases['total_purchased'],
        'profit': profit,
    }


def main():
    parser = argparse.ArgumentParser(description='Settle purchases with confirmed payouts')
    parser.add_argument('--date', required=True, help='Date (YYYY-MM-DD)')
    parser.add_argument('--force', action='store_true',
                        help='Re-settle already confirmed items')
    args = parser.parse_args()

    result = settle(args.date, force=args.force)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
