#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
馬場（Baba）特徴量: クッション値 + 含水率

CSVデータソース: data3/analysis/baba/
  - cushion{YYYY}.csv: 芝クッション値 (prefix 00/03/04/0B = turf)
  - moistureG_{YYYY}.csv: ゴール前含水率 (00=turf, 0D=dirt)

特徴量:
  - cushion_value: 芝クッション値（9.5=硬い高速馬場, 7.0=柔らかい重馬場級）
    ダートレースではNaN
  - moisture_rate: レースの走路面に対応する含水率
    芝レース→turf moistureG, ダートレース→dirt moistureG

v5.41: 馬場分析特徴量
"""

import csv
from pathlib import Path
from typing import Dict, Optional

import numpy as np

from core import config

# track prefix → surface type
TURF_PREFIXES = {'00', '03', '04', '0B'}
DIRT_PREFIXES = {'0D'}


def _read_csv(path: Path) -> list:
    """エンコーディング自動判定でCSV読み込み"""
    for enc in ('cp932', 'utf-8-sig', 'utf-8'):
        try:
            with open(path, encoding=enc) as f:
                return list(csv.reader(f))
        except Exception:
            continue
    return []


def _parse_csv_id(csv_id: str) -> Optional[dict]:
    """RX{JJ}{YY}{K}{N}{RR} → dict"""
    if len(csv_id) < 10:
        return None
    return {
        'place': csv_id[2:4],
        'year': f"20{csv_id[4:6]}",
        'kai': csv_id[6],
        'nichi': csv_id[7],
        'race_num': csv_id[8:10],
    }


def load_baba_index(years=None) -> Dict[str, dict]:
    """全馬場データをロード → {key: {cushion, moisture_turf, moisture_dirt}}

    Args:
        years: ロード対象年のリスト。Noneなら2020-2027。

    Returns:
        dict: key → {cushion: float, moisture_turf: float, moisture_dirt: float}
              各値は存在しない場合キーなし。
    """
    if years is None:
        years = range(2020, 2028)

    baba_dir = config.analysis_dir() / "baba"
    data: Dict[str, dict] = {}

    for year in years:
        # Cushion (芝のみ)
        path = baba_dir / f"cushion{year}.csv"
        if path.exists():
            for row in _read_csv(path):
                if len(row) < 3:
                    continue
                parsed = _parse_csv_id(row[1])
                if not parsed:
                    continue
                prefix = row[2][:2]
                if prefix not in TURF_PREFIXES:
                    continue
                val_str = row[2][2:].strip()
                try:
                    val = float(val_str)
                except (ValueError, TypeError):
                    continue
                key = f"{parsed['year']}_{parsed['place']}_{parsed['kai']}_{parsed['nichi']}_{parsed['race_num']}"
                data.setdefault(key, {})
                data[key]['cushion'] = val

        # Moisture (ゴール前 = moistureG)
        path = baba_dir / f"moistureG_{year}.csv"
        if path.exists():
            for row in _read_csv(path):
                if len(row) < 3:
                    continue
                parsed = _parse_csv_id(row[1])
                if not parsed:
                    continue
                prefix = row[2][:2]
                val_str = row[2][2:].strip()
                try:
                    val = float(val_str)
                except (ValueError, TypeError):
                    continue
                key = f"{parsed['year']}_{parsed['place']}_{parsed['kai']}_{parsed['nichi']}_{parsed['race_num']}"
                data.setdefault(key, {})
                if prefix in TURF_PREFIXES:
                    data[key]['moisture_turf'] = val
                elif prefix in DIRT_PREFIXES:
                    data[key]['moisture_dirt'] = val

    return data


def race_id_to_baba_key(race_id: str) -> str:
    """race_id (16桁) → baba lookup key"""
    place = race_id[8:10]
    kai = str(int(race_id[10:12]))
    nichi = str(int(race_id[12:14]))
    race_num = race_id[14:16]
    year_str = race_id[:4]
    return f"{year_str}_{place}_{kai}_{nichi}_{race_num}"


def get_baba_features(race_id: str, track_type: str, baba_index: dict) -> dict:
    """レースIDと走路タイプからbaba特徴量を返す。

    Args:
        race_id: 16桁レースID
        track_type: 'turf' or 'dirt'
        baba_index: load_baba_index() の戻り値

    Returns:
        dict: {cushion_value: float|NaN, moisture_rate: float|NaN}
    """
    result = {
        'cushion_value': np.nan,
        'moisture_rate': np.nan,
    }

    if not race_id or len(race_id) < 16 or not baba_index:
        return result

    key = race_id_to_baba_key(race_id)
    baba = baba_index.get(key)
    if not baba:
        return result

    # cushion_value: 芝レースのみ（ダートには意味がない）
    if track_type == 'turf' and 'cushion' in baba:
        result['cushion_value'] = baba['cushion']

    # moisture_rate: レースの走路面に対応する含水率
    if track_type == 'turf' and 'moisture_turf' in baba:
        result['moisture_rate'] = baba['moisture_turf']
    elif track_type == 'dirt' and 'moisture_dirt' in baba:
        result['moisture_rate'] = baba['moisture_dirt']

    return result
