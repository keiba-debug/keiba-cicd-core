#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JRA-VAN SR_DATA（レース成績サマリ）パーサー

SR*.DAT: 1272バイト固定長レコード（Shift-JIS）
レコードタイプ "RA"、DataKubun "7"（確定データ）

既存 calculate_race_type_standards_jv.py の parse_sr_record() を独立モジュールとして抽出。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from ..config import jv_se_data_path  # SR_DATAもSE_DATA配下にある
from ..constants import SR_RECORD_LEN, VENUE_CODES, TRACK_TYPES, BABA_CODES
from . import race_id as rid


@dataclass
class SrRecord:
    """SR_DATAレコード"""
    race_id: str            # 16桁
    date: str               # YYYY-MM-DD
    venue_code: str
    venue_name: str
    kai: int
    nichi: int
    race_number: int
    distance: int
    track_type: str         # "turf" or "dirt"
    track_cd: str           # 生のトラックコード
    baba_cd: str            # 馬場状態コード
    baba_name: str          # 良/稍重/重/不良
    num_runners: int
    first_3f: Optional[float]
    first_4f: Optional[float]
    last_3f: Optional[float]
    last_4f: Optional[float]
    rpci: Optional[float]

    def to_pace_dict(self) -> Dict:
        """pace情報を辞書で返す"""
        return {
            's3': self.first_3f,
            's4': self.first_4f,
            'l3': self.last_3f,
            'l4': self.last_4f,
            'rpci': self.rpci,
            'race_trend': self.classify_trend(),
        }

    def classify_trend(self) -> Optional[str]:
        """レース傾向5段階分類"""
        if self.rpci is None or self.last_3f is None:
            return None
        rpci = self.rpci
        l3 = self.last_3f
        l4 = self.last_4f

        if rpci >= 50 and l4 is not None:
            f4 = self.first_4f
            if f4 is not None and l4 < f4 and (l4 - l3 * 4 / 3) < -0.5:
                return 'long_sprint'
        if rpci >= 51:
            return 'sprint_finish'
        if rpci > 48:
            return 'even_pace'
        # rpci <= 48
        if l3 < 35.5:
            return 'front_loaded_strong'
        return 'front_loaded'


def _decode(data: bytes, start: int, length: int) -> str:
    try:
        return data[start:start + length].decode('shift_jis', errors='replace').strip().replace('\u3000', '')
    except Exception:
        return ''


def _parse_pace_time(raw: str) -> Optional[float]:
    """3桁のペースタイム（SST形式）を秒に変換"""
    if not raw or not raw.isdigit() or len(raw) < 3:
        return None
    try:
        val = int(raw[0]) * 10 + int(raw[1]) + int(raw[2]) / 10.0
        return val
    except (ValueError, IndexError):
        return None


def _calculate_rpci(first_3f: float, last_3f: float) -> Optional[float]:
    """RPCI = last_3f / (first_3f + last_3f) * 100"""
    total = first_3f + last_3f
    if total <= 0:
        return None
    return round(last_3f / total * 100, 1)


def parse_record(data: bytes, offset: int = 0) -> Optional[SrRecord]:
    """
    SR_DATA 1272バイトレコードをパース

    バイトオフセット:
      0-1:     RecordType ("RA")
      2:       DataKubun ("7" = 確定)
      11-14:   Year (4)
      15-18:   MonthDay (4)
      19-20:   VenueCode (2)
      21-22:   Kai (2)
      23-24:   Nichi (2)
      25-26:   RaceNumber (2)
      697-700: Distance (4)
      705-706: TrackCode (2)
      883-884: NumRunners (2)
      888:     SibaBabaCD (1)
      889:     DirtBabaCD (1)
      969-971: First3F (3)
      972-974: First4F (3)
      975-977: Last3F (3)
      978-980: Last4F (3)
    """
    record = data[offset:offset + SR_RECORD_LEN]
    if len(record) < SR_RECORD_LEN:
        return None

    record_type = _decode(record, 0, 2)
    if record_type != 'RA':
        return None

    data_kubun = _decode(record, 2, 1)
    if data_kubun != '7':
        return None

    year_str = _decode(record, 11, 4)
    month_day = _decode(record, 15, 4)
    venue_code = _decode(record, 19, 2)

    if not year_str.isdigit():
        return None

    kai_str = _decode(record, 21, 2)
    nichi_str = _decode(record, 23, 2)
    race_num_str = _decode(record, 25, 2)
    kai = int(kai_str) if kai_str.isdigit() else 0
    nichi = int(nichi_str) if nichi_str.isdigit() else 0
    race_number = int(race_num_str) if race_num_str.isdigit() else 0

    race_id_16 = rid.build_from_se(year_str, month_day, venue_code, kai, nichi, race_number)

    # Distance
    kyori_str = _decode(record, 697, 4)
    if not kyori_str.isdigit():
        return None
    distance = int(kyori_str)
    if distance < 800 or distance > 4000:
        return None

    # Track type
    track_cd = _decode(record, 705, 2)
    track_type = TRACK_TYPES.get(track_cd[0:1], None) if track_cd else None
    if track_type is None:
        return None

    # Runners
    syusso_str = _decode(record, 883, 2)
    num_runners = int(syusso_str) if syusso_str.isdigit() else 0

    # Baba
    siba_baba_cd = _decode(record, 888, 1)
    dirt_baba_cd = _decode(record, 889, 1)
    baba_cd = siba_baba_cd if track_type == 'turf' else dirt_baba_cd
    baba_name = BABA_CODES.get(baba_cd, '不明')

    # Pace times
    first_3f = _parse_pace_time(_decode(record, 969, 3))
    first_4f = _parse_pace_time(_decode(record, 972, 3))
    last_3f = _parse_pace_time(_decode(record, 975, 3))
    last_4f = _parse_pace_time(_decode(record, 978, 3))

    if first_3f is None or last_3f is None:
        return None
    if first_3f < 30 or first_3f > 50 or last_3f < 30 or last_3f > 50:
        return None
    if first_4f is not None and (first_4f < 40 or first_4f > 70):
        first_4f = None
    if last_4f is not None and (last_4f < 40 or last_4f > 70):
        last_4f = None

    rpci = _calculate_rpci(first_3f, last_3f)

    date_str = f"{year_str}-{month_day[:2]}-{month_day[2:]}"
    venue_name = VENUE_CODES.get(venue_code, f"?({venue_code})")

    return SrRecord(
        race_id=race_id_16,
        date=date_str,
        venue_code=venue_code,
        venue_name=venue_name,
        kai=kai,
        nichi=nichi,
        race_number=race_number,
        distance=distance,
        track_type=track_type,
        track_cd=track_cd,
        baba_cd=baba_cd,
        baba_name=baba_name,
        num_runners=num_runners,
        first_3f=first_3f,
        first_4f=first_4f,
        last_3f=last_3f,
        last_4f=last_4f,
        rpci=rpci,
    )


# === スキャン関数 ===

def get_sr_files(years: List[int]) -> List[Path]:
    """指定年のSR*.DATファイル一覧"""
    root = jv_se_data_path()  # SR_DATAもSE_DATAと同じディレクトリ
    files = []
    for year in years:
        year_dir = root / str(year)
        if year_dir.exists():
            files.extend(sorted(year_dir.glob('SR*.DAT')))
    return files


def scan(years: List[int]) -> List[SrRecord]:
    """SR_DATAをスキャンして全有効レコードを返す"""
    records = []
    for filepath in get_sr_files(years):
        try:
            data = filepath.read_bytes()
        except Exception:
            continue

        file_size = len(data)
        i = 0
        while True:
            offset = i * SR_RECORD_LEN
            if offset + SR_RECORD_LEN > file_size:
                break
            result = parse_record(data, offset)
            if result:
                records.append(result)
            i += 1

    return records
