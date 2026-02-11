#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
レースマスターJSON構築

SE_DATA（出走馬成績）+ SR_DATA（レースサマリ）を結合して
data3/races/YYYY/MM/DD/race_{race_id}.json を生成。

Usage:
    python -m builders.build_race_master [--years 2020-2026] [--dry-run]
    python -m builders.build_race_master --date 2026-02-08 [--dry-run]
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from core.constants import VENUE_CODES, SEX_CODES, BABA_CODES
from core.jravan import se_parser, sr_parser, race_id as rid
from core.models.race import RaceMaster, RaceEntry, RacePace


def build_sr_index(years: List[int]) -> Dict[str, 'sr_parser.SrRecord']:
    """SR_DATAをスキャンしてrace_id→SrRecordの辞書を構築"""
    print(f"[SR] Scanning SR_DATA for years {years[0]}-{years[-1]}...")
    sr_records = sr_parser.scan(years)
    index = {}
    for sr in sr_records:
        index[sr.race_id] = sr
    print(f"[SR] {len(index):,} races indexed")
    return index


def build_se_groups(years: List[int]) -> Dict[str, List[Dict]]:
    """SE_DATAをスキャンしてrace_id→出走馬リストにグループ化"""
    print(f"[SE] Scanning SE_DATA for years {years[0]}-{years[-1]}...")
    groups = defaultdict(list)
    count = 0
    for record in se_parser.scan(years):
        groups[record['race_id']].append(record)
        count += 1
        if count % 100_000 == 0:
            print(f"  ... {count:,} records processed")
    print(f"[SE] {count:,} records -> {len(groups):,} races")
    return groups


def build_sr_index_for_date(years: List[int], target_date: str) -> Dict[str, 'sr_parser.SrRecord']:
    """指定日のみのSR_DATAインデックスを構築"""
    print(f"[SR] Scanning SR_DATA for date {target_date}...")
    sr_records = sr_parser.scan(years)
    index = {}
    for sr in sr_records:
        if sr.date == target_date:
            index[sr.race_id] = sr
    print(f"[SR] {len(index):,} races found for {target_date}")
    return index


def build_se_groups_for_date(years: List[int], target_date: str) -> Dict[str, List[Dict]]:
    """指定日のみのSE_DATAグループを構築"""
    print(f"[SE] Scanning SE_DATA for date {target_date}...")
    groups = defaultdict(list)
    count = 0
    for record in se_parser.scan(years):
        # race_idからdateを導出してフィルタ
        info = rid.parse(record['race_id'])
        if info and info['date'] == target_date:
            groups[record['race_id']].append(record)
            count += 1
    print(f"[SE] {count:,} records -> {len(groups):,} races for {target_date}")
    return groups


def create_race_master(
    race_id: str,
    entries_raw: List[Dict],
    sr: Optional['sr_parser.SrRecord'] = None,
) -> RaceMaster:
    """SE_DATAエントリとSR_DATAサマリからRaceMasterを構築

    sr=None の場合（レース前、結果未確定）は race_id からメタ情報を導出し、
    pace=None でレースJSONを生成する。
    """
    # エントリを馬番順にソート
    entries_raw.sort(key=lambda e: e['umaban'])

    entries = []
    for e in entries_raw:
        entry = RaceEntry(
            umaban=e['umaban'],
            wakuban=e['wakuban'],
            ketto_num=e['ketto_num'],
            horse_name=e['horse_name'],
            sex_cd=e['sex_cd'],
            age=e['age'],
            jockey_name=e['jockey_name'],
            trainer_name=e['trainer_name'],
            futan=e['futan'],
            horse_weight=e['horse_weight'],
            horse_weight_diff=e['horse_weight_diff'],
            finish_position=e['finish_position'],
            time=e['time'],
            last_3f=e['last_3f'],
            last_4f=e['last_4f'],
            odds=e['odds'],
            popularity=e['popularity'],
            corners=e['corners'],
            jockey_code=e.get('jockey_code', ''),
            trainer_code=e.get('trainer_code', ''),
        )
        entries.append(entry)

    if sr is not None:
        # SR_DATAあり: フルデータで構築
        pace = RacePace(
            s3=sr.first_3f,
            s4=sr.first_4f,
            l3=sr.last_3f,
            l4=sr.last_4f,
            rpci=sr.rpci,
            race_trend=sr.classify_trend(),
        )
        race = RaceMaster(
            race_id=race_id,
            date=sr.date,
            venue_code=sr.venue_code,
            venue_name=sr.venue_name,
            kai=sr.kai,
            nichi=sr.nichi,
            race_number=sr.race_number,
            distance=sr.distance,
            track_type=sr.track_type,
            track_condition=sr.baba_name,
            num_runners=len(entries),
            pace=pace,
            entries=entries,
            meta={
                'data_version': '4.0',
                'source': 'jravan',
                'created_at': datetime.now().isoformat(timespec='seconds'),
                'has_keibabook_ext': False,
            },
        )
    else:
        # SR_DATAなし: race_idからメタ情報を導出
        info = rid.parse(race_id)
        race = RaceMaster(
            race_id=race_id,
            date=info['date'] if info else '',
            venue_code=info['venue_code'] if info else '',
            venue_name=info['venue_name'] if info else '',
            kai=int(info['kai']) if info else 0,
            nichi=int(info['nichi']) if info else 0,
            race_number=int(info['race_num']) if info else 0,
            num_runners=len(entries),
            pace=None,
            entries=entries,
            meta={
                'data_version': '4.0',
                'source': 'jravan',
                'created_at': datetime.now().isoformat(timespec='seconds'),
                'has_keibabook_ext': False,
                'pre_race': True,
            },
        )
    return race


def save_race_json(race: RaceMaster, dry_run: bool = False) -> Path:
    """RaceMasterをJSONファイルとして保存"""
    # パス: data3/races/YYYY/MM/DD/race_{race_id}.json
    date_parts = race.date.split('-')
    if len(date_parts) != 3:
        raise ValueError(f"Invalid date format: {race.date}")

    year, month, day = date_parts
    race_dir = config.races_dir() / year / month / day
    filepath = race_dir / f"race_{race.race_id}.json"

    if dry_run:
        return filepath

    config.ensure_dir(race_dir)
    filepath.write_text(race.to_json(), encoding='utf-8')
    return filepath


def parse_year_range(s: str) -> List[int]:
    """'2020-2026' → [2020, 2021, ..., 2026]"""
    if '-' in s:
        start, end = s.split('-', 1)
        return list(range(int(start), int(end) + 1))
    return [int(s)]


def main():
    parser = argparse.ArgumentParser(description='Build race master JSONs from JRA-VAN data')
    parser.add_argument('--years', default=None, help='Year range (e.g. 2020-2026)')
    parser.add_argument('--date', default=None, help='Single date (YYYY-MM-DD) for incremental build')
    parser.add_argument('--dry-run', action='store_true', help='Count only, do not write files')
    args = parser.parse_args()

    if args.date and args.years:
        print("ERROR: --date and --years are mutually exclusive")
        sys.exit(1)

    t0 = time.time()

    if args.date:
        # インクリメンタルモード: 指定日のみ
        year = int(args.date[:4])
        years = [year]
        print(f"\n{'='*60}")
        print(f"  KeibaCICD v4 - Race Master Builder (incremental)")
        print(f"  Date: {args.date}")
        print(f"  Output: {config.races_dir()}")
        print(f"  Dry run: {args.dry_run}")
        print(f"{'='*60}\n")

        sr_index = build_sr_index_for_date(years, args.date)
        se_groups = build_se_groups_for_date(years, args.date)
        allow_no_sr = True
    else:
        # 全年モード（デフォルト: 2020-2026）
        years = parse_year_range(args.years or '2020-2026')
        print(f"\n{'='*60}")
        print(f"  KeibaCICD v4 - Race Master Builder")
        print(f"  Years: {years[0]}-{years[-1]}")
        print(f"  Output: {config.races_dir()}")
        print(f"  Dry run: {args.dry_run}")
        print(f"{'='*60}\n")

        sr_index = build_sr_index(years)
        se_groups = build_se_groups(years)
        allow_no_sr = False

    # SR + SE を結合してレースJSON生成
    print(f"\n[Build] Merging SE + SR data...")
    created = 0
    created_no_sr = 0
    skipped_no_sr = 0
    skipped_no_entries = 0
    errors = 0

    for race_id, entries_raw in se_groups.items():
        sr = sr_index.get(race_id)
        if sr is None and not allow_no_sr:
            skipped_no_sr += 1
            continue

        if len(entries_raw) == 0:
            skipped_no_entries += 1
            continue

        try:
            race = create_race_master(race_id, entries_raw, sr)
            save_race_json(race, dry_run=args.dry_run)
            created += 1
            if sr is None:
                created_no_sr += 1
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  ERROR: {race_id}: {e}")

    elapsed = time.time() - t0

    print(f"\n{'='*60}")
    print(f"  Results")
    print(f"{'='*60}")
    print(f"  Created:          {created:,} race JSONs")
    if created_no_sr:
        print(f"    (pre-race):     {created_no_sr:,}")
    if skipped_no_sr:
        print(f"  Skipped (no SR):  {skipped_no_sr:,}")
    print(f"  Skipped (empty):  {skipped_no_entries:,}")
    print(f"  Errors:           {errors:,}")
    print(f"  Elapsed:          {elapsed:.1f}s")
    print(f"{'='*60}\n")


if __name__ == '__main__':
    main()
