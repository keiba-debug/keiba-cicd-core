#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JRA-VAN SE_DATA（馬毎レース成績）リーダー

SU*.DAT: 555バイト固定長レコード（Shift-JIS）
TypeScript版 target-race-result-reader.ts のPython移植。

Usage:
    from common.jravan.se_reader import scan_se_data

    for record in scan_se_data(years=[2023, 2024, 2025, 2026]):
        print(record['kettoNum'], record['finishPosition'], record['trainerName'])
"""

import sys
from pathlib import Path
from typing import Dict, Generator, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from common.config import get_jv_se_data_path

SE_DATA_ROOT = get_jv_se_data_path()
SE_RECORD_LEN = 555


def _decode_sjis(data: bytes, start: int, length: int) -> str:
    """Shift-JISデコード"""
    try:
        return data[start:start + length].decode('shift_jis', errors='replace').strip().replace('\u3000', '')
    except Exception:
        return ''


def _parse_int(data: bytes, start: int, length: int, default: int = 0) -> int:
    """整数フィールドをパース"""
    try:
        return int(_decode_sjis(data, start, length)) or default
    except (ValueError, TypeError):
        return default


def parse_se_record(record: bytes) -> Optional[Dict]:
    """
    SE_DATA 555バイトレコードをパース

    バイトオフセット（TypeScript版と同一）:
      0-1:   RecordType ("SE")
      11-14: Year (4)
      15-18: MonthDay MMDD (4)
      19-20: VenueCode (2)
      21-22: Kai (2)
      23-24: Nichi (2)
      25-26: RaceNumber (2)
      27:    Wakuban (1)
      28-29: Umaban (2)
      30-39: KettoNum (10)
      40-75: HorseName (36, Shift-JIS)
      78:    SexCD (1)
      82-83: Age (2)
      90-97: TrainerName略称 (8, Shift-JIS)
      288-290: Weight/Futan (3)
      306-313: JockeyName略称 (8, Shift-JIS)
      324-326: HorseWeight (3)
      334-335: FinishPosition (2)
      338-341: Time MSST (4)
      359-362: Odds x10 (4)
      363-364: Popularity (2)
      390-392: Last3F SST (3)
    """
    if len(record) < SE_RECORD_LEN:
        return None

    record_type = _decode_sjis(record, 0, 2)
    if record_type != 'SE':
        return None

    year = _decode_sjis(record, 11, 4)
    month_day = _decode_sjis(record, 15, 4)
    if not year or not month_day:
        return None

    race_date = year + month_day
    venue_code = _decode_sjis(record, 19, 2)
    kai = _parse_int(record, 21, 2)
    nichi = _parse_int(record, 23, 2)
    race_number = _parse_int(record, 25, 2)

    ketto_num = _decode_sjis(record, 30, 10)
    if not ketto_num:
        return None

    horse_name = _decode_sjis(record, 40, 36)
    trainer_name = _decode_sjis(record, 90, 8)
    jockey_name = _decode_sjis(record, 306, 8)

    finish_position = _parse_int(record, 334, 2)
    odds_raw = _parse_int(record, 359, 4)
    odds = odds_raw / 10.0 if odds_raw > 0 else 0.0
    popularity = _parse_int(record, 363, 2)

    return {
        'raceDate': race_date,
        'venueCode': venue_code,
        'kai': kai,
        'nichi': nichi,
        'raceNumber': race_number,
        'kettoNum': ketto_num,
        'horseName': horse_name,
        'trainerName': trainer_name,
        'jockeyName': jockey_name,
        'finishPosition': finish_position,
        'odds': odds,
        'popularity': popularity,
    }


def get_su_dat_files(years: List[int]) -> List[Path]:
    """指定年のSU*.DATファイル一覧を取得"""
    files = []
    for year in years:
        year_dir = SE_DATA_ROOT / str(year)
        if not year_dir.exists():
            continue
        for f in sorted(year_dir.glob('SU*.DAT')):
            files.append(f)
    return files


def scan_se_data(
    years: List[int],
    min_finish: int = 0,
) -> Generator[Dict, None, None]:
    """
    SE_DATAを全スキャンし、レコードを順次yield

    Args:
        years: 対象年リスト（例: [2023, 2024, 2025, 2026]）
        min_finish: 着順フィルタ（0=フィルタなし、例: 1なら1着のみ）

    Yields:
        パースされたレコード辞書
    """
    files = get_su_dat_files(years)

    for filepath in files:
        try:
            data = filepath.read_bytes()
        except Exception:
            continue

        num_records = len(data) // SE_RECORD_LEN
        for i in range(num_records):
            offset = i * SE_RECORD_LEN
            record = parse_se_record(data[offset:offset + SE_RECORD_LEN])
            if record is None:
                continue
            if min_finish > 0 and record['finishPosition'] != min_finish:
                continue
            yield record


def count_se_records(years: List[int]) -> int:
    """SE_DATAのレコード総数を概算（ファイルサイズベース）"""
    total = 0
    for filepath in get_su_dat_files(years):
        try:
            total += filepath.stat().st_size // SE_RECORD_LEN
        except Exception:
            pass
    return total
