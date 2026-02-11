#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JRA-VAN SE_DATA（馬毎レース成績）パーサー

SU*.DAT: 555バイト固定長レコード（Shift-JIS）

既存se_reader.pyからの移植・拡張版:
  - 全フィールド抽出（wakuban, umaban, futan, horse_weight, time, corners, last4f等）
  - 16桁race_id対応
"""

from pathlib import Path
from typing import Dict, Generator, List, Optional

from ..config import jv_se_data_path
from ..constants import SE_RECORD_LEN, SEX_CODES
from . import race_id as rid


def _decode(data: bytes, start: int, length: int) -> str:
    """Shift-JISデコード"""
    try:
        return data[start:start + length].decode('shift_jis', errors='replace').strip().replace('\u3000', '')
    except Exception:
        return ''


def _int(data: bytes, start: int, length: int, default: int = 0) -> int:
    """整数フィールドをパース"""
    try:
        v = _decode(data, start, length)
        return int(v) if v else default
    except (ValueError, TypeError):
        return default


def parse_record(record: bytes) -> Optional[Dict]:
    """
    SE_DATA 555バイトレコードをパース（全フィールド版）

    バイトオフセット:
      0-1:     RecordType ("SE")
      11-14:   Year (4)
      15-18:   MonthDay MMDD (4)
      19-20:   VenueCode (2)
      21-22:   Kai (2)
      23-24:   Nichi (2)
      25-26:   RaceNumber (2)
      27:      Wakuban (1)
      28-29:   Umaban (2)
      30-39:   KettoNum (10)
      40-75:   HorseName (36, Shift-JIS)
      78:      SexCD (1)
      82-83:   Age (2)
      84:      TozaiCD (1) - 1=美浦, 2=栗東
      85-89:   TrainerCode (5)
      90-97:   TrainerName略称 (8, Shift-JIS)
      288-290: Futan/斤量 x10 (3)
      296-300: JockeyCode (5)
      306-313: JockeyName略称 (8, Shift-JIS)
      324-326: HorseWeight (3)
      327:     ZogenFugo (+/-)
      328-330: ZogenSa (3)
      334-335: FinishPosition (2)
      338-341: Time MSST (4)
      351-358: Corners c1-c4 各2桁 (8)
      359-362: Odds x10 (4)
      363-364: Popularity (2)
      387-389: Last4F SST (3)
      390-392: Last3F SST (3)
    """
    if len(record) < SE_RECORD_LEN:
        return None

    if _decode(record, 0, 2) != 'SE':
        return None

    year = _decode(record, 11, 4)
    month_day = _decode(record, 15, 4)
    if not year or not month_day or len(month_day) < 4:
        return None

    venue_code = _decode(record, 19, 2)
    kai = _int(record, 21, 2)
    nichi = _int(record, 23, 2)
    race_number = _int(record, 25, 2)

    race_id = rid.build_from_se(year, month_day, venue_code, kai, nichi, race_number)

    ketto_num = _decode(record, 30, 10)
    if not ketto_num:
        return None

    # 斤量（x10で格納）
    futan_raw = _int(record, 288, 3)
    futan = futan_raw / 10.0 if futan_raw > 0 else 0.0

    # タイム（MSST: 分・秒十・秒一・1/10秒）
    time_raw = _decode(record, 338, 4)
    time_str = _format_time(time_raw)

    # コーナー通過順（各2桁x4 = 8桁）
    corners = []
    for ci in range(4):
        c = _int(record, 351 + ci * 2, 2)
        if c > 0:
            corners.append(c)

    # オッズ（x10で格納）
    odds_raw = _int(record, 359, 4)
    odds = odds_raw / 10.0 if odds_raw > 0 else 0.0

    # 上がり3F/4F（SST: 秒十・秒一・1/10秒）
    last_3f_raw = _int(record, 390, 3)
    last_3f = last_3f_raw / 10.0 if last_3f_raw > 0 else 0.0
    last_4f_raw = _int(record, 387, 3)
    last_4f = last_4f_raw / 10.0 if last_4f_raw > 0 else 0.0

    # 馬体重増減
    zogen_fugo = _decode(record, 327, 1)
    zogen_sa = _int(record, 328, 3)
    weight_diff = zogen_sa if zogen_fugo != '-' else -zogen_sa

    sex_cd = _decode(record, 78, 1)

    # 調教師コード: offset 85-89 (5桁), offset 84 = tozai_cd
    trainer_code = _decode(record, 85, 5)
    # 騎手コード: offset 296-300 (5桁)
    jockey_code = _decode(record, 296, 5)

    return {
        'race_id': race_id,
        'race_date': f"{year}-{month_day[:2]}-{month_day[2:]}",
        'venue_code': venue_code,
        'kai': kai,
        'nichi': nichi,
        'race_number': race_number,
        'wakuban': _int(record, 27, 1),
        'umaban': _int(record, 28, 2),
        'ketto_num': ketto_num,
        'horse_name': _decode(record, 40, 36),
        'sex_cd': sex_cd,
        'sex_name': SEX_CODES.get(sex_cd, ''),
        'age': _int(record, 82, 2),
        'trainer_code': trainer_code,
        'trainer_name': _decode(record, 90, 8),
        'jockey_code': jockey_code,
        'jockey_name': _decode(record, 306, 8),
        'futan': futan,
        'horse_weight': _int(record, 324, 3),
        'horse_weight_diff': weight_diff,
        'finish_position': _int(record, 334, 2),
        'time': time_str,
        'last_3f': last_3f,
        'last_4f': last_4f,
        'odds': odds,
        'popularity': _int(record, 363, 2),
        'corners': corners,
    }


def _format_time(raw: str) -> str:
    """MSST形式のタイムを読みやすい形式に変換"""
    if not raw or len(raw) < 4:
        return ''
    try:
        m = int(raw[0])
        s = int(raw[1:3])
        t = int(raw[3])
        if m == 0:
            return f"{s}.{t}"
        return f"{m}:{s:02d}.{t}"
    except (ValueError, IndexError):
        return raw


# === スキャン関数 ===

def get_su_files(years: List[int]) -> List[Path]:
    """指定年のSU*.DATファイル一覧"""
    root = jv_se_data_path()
    files = []
    for year in years:
        year_dir = root / str(year)
        if year_dir.exists():
            files.extend(sorted(year_dir.glob('SU*.DAT')))
    return files


def scan(
    years: List[int],
    min_finish: int = 0,
) -> Generator[Dict, None, None]:
    """SE_DATAを全スキャン"""
    for filepath in get_su_files(years):
        try:
            data = filepath.read_bytes()
        except Exception:
            continue

        num_records = len(data) // SE_RECORD_LEN
        for i in range(num_records):
            offset = i * SE_RECORD_LEN
            record = parse_record(data[offset:offset + SE_RECORD_LEN])
            if record is None:
                continue
            if min_finish > 0 and record['finish_position'] != min_finish:
                continue
            yield record


def count_records(years: List[int]) -> int:
    """レコード総数を概算"""
    total = 0
    for filepath in get_su_files(years):
        try:
            total += filepath.stat().st_size // SE_RECORD_LEN
        except Exception:
            pass
    return total
