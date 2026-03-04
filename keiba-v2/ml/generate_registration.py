#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
特別登録データ生成

MyKeibaDB の tokubetsu_torokuba / tokubetsu_torokubagoto_joho テーブルから
特別登録馬のデータを取得し、races/YYYY/MM/DD/registration.json に出力する。

Usage:
    python -m ml.generate_registration --date 2026-03-07
    python -m ml.generate_registration --latest
"""

import argparse
import json
import sys
import time
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.db import query, get_connection
from core.constants import VENUE_CODES, SEX_CODES, GRADE_CODES, TRACK_TYPES

DATA3 = Path('C:/KEIBA-CICD/data3')
MASTERS_DIR = DATA3 / 'masters' / 'horses'


def get_registration_dates() -> List[str]:
    """特別登録データが存在する日付一覧を取得"""
    rows = query(
        "SELECT DISTINCT CONCAT(KAISAI_NEN, KAISAI_GAPPI) as dt "
        "FROM tokubetsu_torokuba ORDER BY dt DESC LIMIT 30"
    )
    dates = []
    for r in rows:
        dt = r['dt']
        if len(dt) == 8:
            dates.append(f"{dt[:4]}-{dt[4:6]}-{dt[6:8]}")
    return dates


def get_latest_registration_date() -> Optional[str]:
    """最新の特別登録日付を取得"""
    dates = get_registration_dates()
    if not dates:
        return None
    # 今日以降の日付を優先
    today = date.today().isoformat()
    future = [d for d in dates if d >= today]
    return future[-1] if future else dates[0]


def get_races_for_date(target_date: str) -> List[dict]:
    """指定日の特別登録レースを取得"""
    gappi = target_date[5:7] + target_date[8:10]  # "0307"
    nen = target_date[:4]  # "2026"

    rows = query(
        "SELECT RACE_CODE, KAISAI_NEN, KAISAI_GAPPI, KEIBAJO_CODE, "
        "KAISAI_KAI, KAISAI_NICHIME, RACE_BANGO, "
        "KYOSOMEI_HONDAI, KYOSOMEI_FUKUDAI, KYORI, TRACK_CODE, "
        "GRADE_CODE, TOROKU_TOSU, KYOSO_SHUBETSU_CODE, JURYO_SHUBETSU_CODE "
        "FROM tokubetsu_torokuba "
        "WHERE KAISAI_NEN = %s AND KAISAI_GAPPI = %s "
        "ORDER BY RACE_CODE",
        (nen, gappi)
    )
    return rows


def get_entries_for_race(race_code: str) -> List[dict]:
    """特別登録馬を取得"""
    return query(
        "SELECT RENBAN, KETTO_TOROKU_BANGO, BAMEI, SEIBETSU_CODE, "
        "CHOKYOSHI_CODE, CHOKYOSHIMEI_RYAKUSHO, FUTAN_JURYO, KORYU_KUBUN "
        "FROM tokubetsu_torokubagoto_joho "
        "WHERE RACE_CODE = %s ORDER BY RENBAN",
        (race_code,)
    )


def get_past_results_batch(ketto_nums: List[str]) -> Dict[str, List[dict]]:
    """複数馬の近走成績を一括取得"""
    if not ketto_nums:
        return {}

    results = {}
    batch_size = 200
    for i in range(0, len(ketto_nums), batch_size):
        batch = ketto_nums[i:i + batch_size]
        placeholders = ','.join(['%s'] * len(batch))

        rows = query(
            f"SELECT u.KETTO_TOROKU_BANGO, u.RACE_CODE, u.UMABAN, "
            f"u.KAKUTEI_CHAKUJUN, u.TANSHO_ODDS, u.FUTAN_JURYO, "
            f"r.KYORI, r.TRACK_CODE, r.KEIBAJO_CODE, r.GRADE_CODE, "
            f"r.KYOSOMEI_HONDAI "
            f"FROM umagoto_race_joho u "
            f"JOIN race_shosai r ON u.RACE_CODE = r.RACE_CODE "
            f"WHERE u.KETTO_TOROKU_BANGO IN ({placeholders}) "
            f"ORDER BY u.KETTO_TOROKU_BANGO, u.RACE_CODE DESC",
            tuple(batch)
        )

        for r in rows:
            kn = r['KETTO_TOROKU_BANGO'].strip()
            if kn not in results:
                results[kn] = []
            if len(results[kn]) >= 5:
                continue

            track_code = r['TRACK_CODE'].strip()
            track_type = '芝' if track_code.startswith('1') else ('ダ' if track_code.startswith('2') else '障')
            venue_code = r['KEIBAJO_CODE'].strip()
            venue_name = VENUE_CODES.get(venue_code, venue_code)
            grade_code = r['GRADE_CODE'].strip() if r['GRADE_CODE'] else ''
            grade = GRADE_CODES.get(grade_code, '')

            # Parse odds
            odds_raw = r.get('TANSHO_ODDS', '')
            odds = None
            if odds_raw and odds_raw.strip() not in ('', '----', '****', '0000'):
                try:
                    odds = int(odds_raw) / 10.0
                except (ValueError, TypeError):
                    pass

            # Parse finish position
            finish = None
            chaku = r.get('KAKUTEI_CHAKUJUN', '')
            if chaku and chaku.strip():
                try:
                    finish = int(chaku)
                except ValueError:
                    pass

            race_code = r['RACE_CODE']
            race_date = f"{race_code[:4]}-{race_code[4:6]}-{race_code[6:8]}"

            results[kn].append({
                'race_code': race_code.strip(),
                'date': race_date,
                'venue': venue_name,
                'distance': int(r['KYORI']) if r['KYORI'] and r['KYORI'].strip() else 0,
                'track_type': track_type,
                'finish': finish,
                'odds': odds,
                'grade': grade,
                'race_name': (r.get('KYOSOMEI_HONDAI') or '').strip()[:20],
            })

    return results


def load_horse_master(ketto_num: str) -> Optional[dict]:
    """馬マスタJSONを読み込み"""
    fp = MASTERS_DIR / f'{ketto_num}.json'
    if fp.exists():
        try:
            return json.loads(fp.read_text(encoding='utf-8'))
        except Exception:
            pass
    return None


def calc_age(birth_date: str, race_date: str) -> Optional[int]:
    """誕生日とレース日から年齢を計算（競馬年齢: 1/1基準）"""
    if not birth_date or len(birth_date) < 8:
        return None
    try:
        by = int(birth_date[:4])
        ry = int(race_date[:4])
        return ry - by
    except ValueError:
        return None


def generate_registration(target_date: str) -> dict:
    """特別登録データを生成"""
    print(f"[Registration] Generating for {target_date}")

    races_raw = get_races_for_date(target_date)
    if not races_raw:
        print(f"  No registration data found for {target_date}")
        return {}

    print(f"  Found {len(races_raw)} races")

    # 全レースの登録馬を取得
    all_ketto_nums = []
    race_entries_map = {}
    for race in races_raw:
        rc = race['RACE_CODE']
        entries = get_entries_for_race(rc)
        race_entries_map[rc] = entries
        for e in entries:
            kn = e['KETTO_TOROKU_BANGO'].strip()
            if kn:
                all_ketto_nums.append(kn)

    unique_ketto_nums = list(set(all_ketto_nums))
    print(f"  Total registered horses: {len(all_ketto_nums)} ({len(unique_ketto_nums)} unique)")

    # 過去成績を一括取得
    print("  Fetching past results...")
    past_results = get_past_results_batch(unique_ketto_nums)
    print(f"  Past results: {sum(len(v) for v in past_results.values())} total runs")

    # レースごとにデータを組み立て
    output_races = []
    for race in races_raw:
        rc = race['RACE_CODE']
        venue_code = race['KEIBAJO_CODE'].strip()
        venue_name = VENUE_CODES.get(venue_code, venue_code)
        track_code = race['TRACK_CODE'].strip()
        track_type = '芝' if track_code.startswith('1') else ('ダ' if track_code.startswith('2') else '障')
        grade_code = race['GRADE_CODE'].strip() if race['GRADE_CODE'] else ''
        grade = GRADE_CODES.get(grade_code, grade_code)
        distance = int(race['KYORI']) if race['KYORI'] and race['KYORI'].strip() else 0

        entries = race_entries_map.get(rc, [])
        output_entries = []

        for e in entries:
            kn = e['KETTO_TOROKU_BANGO'].strip()
            sex_code = e['SEIBETSU_CODE'].strip() if e['SEIBETSU_CODE'] else ''
            sex = SEX_CODES.get(sex_code, '')

            # 斤量 (3桁、0.1kg単位)
            weight_raw = e['FUTAN_JURYO'].strip() if e['FUTAN_JURYO'] else '0'
            try:
                weight = int(weight_raw) / 10.0
            except ValueError:
                weight = 0

            # 馬マスタから補完
            master = load_horse_master(kn)
            birth_date = master.get('birth_date', '') if master else ''
            age = calc_age(birth_date, target_date)
            tozai = master.get('tozai_name', '') if master else ''

            # 調教師名
            trainer = (e.get('CHOKYOSHIMEI_RYAKUSHO') or '').strip()

            # 過去成績
            recent = past_results.get(kn, [])

            entry_data = {
                'renban': int(e['RENBAN']),
                'ketto_num': kn,
                'horse_name': (e.get('BAMEI') or '').strip(),
                'sex': sex,
                'age': age,
                'trainer_name': trainer,
                'weight_carried': weight,
                'tozai': tozai,
                'recent_results': recent,
            }
            output_entries.append(entry_data)

        race_name = (race.get('KYOSOMEI_HONDAI') or '').strip()
        race_sub = (race.get('KYOSOMEI_FUKUDAI') or '').strip()
        if race_sub:
            race_name = f"{race_name}（{race_sub}）"

        output_races.append({
            'race_code': rc,
            'venue_name': venue_name,
            'venue_code': venue_code,
            'race_number': int(race['RACE_BANGO']),
            'race_name': race_name,
            'grade': grade,
            'distance': distance,
            'track_type': track_type,
            'registered_count': int(race['TOROKU_TOSU']) if race['TOROKU_TOSU'] and race['TOROKU_TOSU'].strip() else len(entries),
            'entries': output_entries,
        })

    return {
        'date': target_date,
        'created_at': datetime.now().isoformat(),
        'source': 'mykeibadb',
        'total_races': len(output_races),
        'total_entries': sum(len(r['entries']) for r in output_races),
        'races': output_races,
    }


def main():
    parser = argparse.ArgumentParser(description='Generate registration data')
    parser.add_argument('--date', type=str, help='Target date (YYYY-MM-DD)')
    parser.add_argument('--latest', action='store_true', help='Use latest registration date')
    parser.add_argument('--all-upcoming', action='store_true',
                        help='Generate for all upcoming dates')
    args = parser.parse_args()

    if args.all_upcoming:
        dates = get_registration_dates()
        today = date.today().isoformat()
        targets = sorted(set(d for d in dates if d >= today))
    elif args.latest:
        d = get_latest_registration_date()
        if not d:
            print("ERROR: No registration data found")
            sys.exit(1)
        targets = [d]
    elif args.date:
        targets = [args.date]
    else:
        print("ERROR: Specify --date, --latest, or --all-upcoming")
        sys.exit(1)

    for target_date in targets:
        t0 = time.time()
        result = generate_registration(target_date)
        if not result:
            continue

        # 出力先ディレクトリ
        y, m, d = target_date.split('-')
        out_dir = DATA3 / 'races' / y / m / d
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / 'registration.json'

        out_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

        elapsed = time.time() - t0
        print(f"  Output: {out_path} ({result['total_races']} races, "
              f"{result['total_entries']} entries, {elapsed:.1f}s)")


if __name__ == '__main__':
    main()
