#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""My印 (ふくだ手動入力) を Python 戦略エンジンから読む共通リーダー

責務:
  1. TARGET MY_DATA/UM{yy}{kai}{venue_kanji}.DAT から ◎○▲△Ⅲ穴 を抽出
  2. data3/my_marks_v2/{race_id}.json から explicit_erase ('消') を取得
  3. 両者をマージして race_id → {umaban: MyMark} を返す

設計背景: docs/auto-purchase/09_MY_MARKS_AND_STRATEGY.md §6.4 / §9.4
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

# 印バイト (Shift-JIS) → 記号
# 0x2020 (= 半角スペース2文字) は「未入力」と「明示消」が物理層で区別不能のため空文字で返す。
# 明示消は my_marks_v2/{race_id}.json から別途取得して merge する。
_MARK_BYTES_TO_SYMBOL: Dict[bytes, str] = {
    b"\x81\x9d": "◎",
    b"\x81\x9b": "○",
    b"\x81\xa3": "▲",
    b"\x81\xa2": "△",
    b"\x87\x56": "Ⅲ",
    b"\x8c\x8a": "穴",
    b"\x20\x20": "",
}

# 印 → 優先度 (大きいほど強い印)。「消」は -1 で「明示的に切られた」を表現
MARK_PRIORITY: Dict[str, int] = {
    "◎": 6,
    "○": 5,
    "▲": 4,
    "△": 3,
    "Ⅲ": 2,
    "穴": 1,
    "消": -1,
}

_VENUE_CODE_TO_KANJI: Dict[str, str] = {
    "01": "札",
    "02": "函",
    "03": "福",
    "04": "新",
    "05": "東",
    "06": "中",
    "07": "名",
    "08": "京",
    "09": "阪",
    "10": "小",
}

_MARK_SET_FOLDERS: Dict[int, str] = {
    1: "",
    2: "UmaMark2",
    3: "UmaMark3",
    4: "UmaMark4",
    5: "UmaMark5",
    6: "UmaMark6",
    7: "UmaMark7",
    8: "UmaMark8",
}


@dataclass
class MyMark:
    """1 頭分の My印 情報"""
    umaban: int
    mark_symbol: str          # ◎○▲△Ⅲ穴消 / '' (未入力)
    is_marked: bool           # mark_symbol != '' and != '消'
    is_erased: bool           # mark_symbol == '消'
    mark_priority: int        # MARK_PRIORITY の値 (未入力は 0)
    source: str               # 'dat' / 'my_marks_v2' / 'merged'


@dataclass
class RaceCoord:
    """race_id (16桁) から逆引きされる TARGET DAT 座標"""
    year: int
    month: int
    day_of_month: int
    venue_code: str           # '01'〜'10'
    venue_kanji: str          # '札'〜'小'
    kai: int                  # 1回目=1, 2回目=2 ...
    day_in_meet: int          # 開催日次 (1-12)
    race_number: int          # レース番号 (1-12)


def parse_race_id(race_id: str) -> RaceCoord:
    """race_id (YYYYMMDDJJKKNNRR) → RaceCoord

    Raises:
        ValueError: 16桁数字以外、または venue_code 未知
    """
    s = str(race_id).strip()
    if len(s) != 16 or not s.isdigit():
        raise ValueError(f"invalid race_id (expected 16-digit): {race_id!r}")

    year = int(s[0:4])
    month = int(s[4:6])
    dom = int(s[6:8])
    venue_code = s[8:10]
    kai = int(s[10:12])
    day_in_meet = int(s[12:14])
    race_number = int(s[14:16])

    kanji = _VENUE_CODE_TO_KANJI.get(venue_code)
    if kanji is None:
        raise ValueError(f"unknown venue_code {venue_code!r} in race_id {race_id}")

    return RaceCoord(
        year=year,
        month=month,
        day_of_month=dom,
        venue_code=venue_code,
        venue_kanji=kanji,
        kai=kai,
        day_in_meet=day_in_meet,
        race_number=race_number,
    )


def _jv_root() -> Path:
    return Path(os.getenv("JV_DATA_ROOT", "C:/TFJV"))


def _my_data_dir(mark_set: int = 1) -> Path:
    base = _jv_root() / "MY_DATA"
    sub = _MARK_SET_FOLDERS.get(mark_set, "")
    return base / sub if sub else base


def get_mark_file_path(coord: RaceCoord, mark_set: int = 1) -> Path:
    """TARGET DAT ファイルパス: MY_DATA/UM{yy}{kai}{venue_kanji}.DAT"""
    yy = f"{coord.year % 100:02d}"
    filename = f"UM{yy}{coord.kai}{coord.venue_kanji}.DAT"
    return _my_data_dir(mark_set) / filename


def _decode_dat_marks(coord: RaceCoord, mark_set: int = 1) -> Dict[int, str]:
    """DAT ファイルから 1 レース分の馬印を読む。 ファイル無し / レコード範囲外は空 dict

    TARGET MY_DATA/UM*.DAT のレコード構造 (1 race = 44 bytes):
        bytes [0:2]    レース色コード (Step1 未使用)
        bytes [2:6]    レース印 (4 bytes Shift-JIS、Step1 未使用)
        bytes [6:42]   馬印 18 頭 × 2 bytes Shift-JIS
        bytes [42:44]  改行 (CR LF) パディング

    record_index = (day_in_meet - 1) * 12 + (race_number - 1)
        全体は 96 records (8 日 × 12 race) または 144 records (9-12 日開催)

    本実装の根拠: keiba-v2/web/src/lib/data/target-mark-reader.ts L156-217
    (TS 側 reader と byte 解釈・record_index 計算が等価であることを検証済)
    """
    path = get_mark_file_path(coord, mark_set)
    if not path.exists():
        return {}

    raw = path.read_bytes()
    record_index = (coord.day_in_meet - 1) * 12 + (coord.race_number - 1)
    record_start = record_index * 44
    if record_start + 44 > len(raw):
        return {}

    out: Dict[int, str] = {}
    for uma in range(1, 19):
        offset = record_start + 6 + (uma - 1) * 2
        b = raw[offset:offset + 2]
        sym = _MARK_BYTES_TO_SYMBOL.get(b)
        if sym is None:
            # ASCII 2文字 (たとえば数字印 "+5" 等) は無視。Step1 では使わない
            continue
        if sym:
            out[uma] = sym
    return out


def _data_root() -> Path:
    return Path(os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3"))


def _my_marks_v2_path(race_id: str) -> Path:
    return _data_root() / "my_marks_v2" / f"{race_id}.json"


def _read_explicit_erase(race_id: str) -> list[int]:
    path = _my_marks_v2_path(race_id)
    if not path.exists():
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return []
    arr = data.get("explicit_erase")
    if not isinstance(arr, list):
        return []
    out: list[int] = []
    for n in arr:
        try:
            v = int(n)
        except (TypeError, ValueError):
            continue
        if 1 <= v <= 18:
            out.append(v)
    return sorted(set(out))


def load_my_marks(race_id: str, mark_set: int = 1) -> Dict[int, MyMark]:
    """race_id 1 件分の My印を返す。

    マージ順位 (上位ほど勝つ):
      1. my_marks_v2 explicit_erase   → '消'
      2. TARGET DAT mark_set          → '◎○▲△Ⅲ穴'

    Returns:
        {umaban: MyMark}。印が無い馬は dict に入らない。
    """
    coord = parse_race_id(race_id)
    dat_marks = _decode_dat_marks(coord, mark_set=mark_set)
    erased = set(_read_explicit_erase(race_id))

    out: Dict[int, MyMark] = {}
    for uma, sym in dat_marks.items():
        if uma in erased:
            continue  # 明示消が DAT 印を上書き
        out[uma] = MyMark(
            umaban=uma,
            mark_symbol=sym,
            is_marked=True,
            is_erased=False,
            mark_priority=MARK_PRIORITY.get(sym, 0),
            source="dat",
        )
    for uma in erased:
        out[uma] = MyMark(
            umaban=uma,
            mark_symbol="消",
            is_marked=False,
            is_erased=True,
            mark_priority=MARK_PRIORITY["消"],
            source="my_marks_v2",
        )
    return out


def find_horse_by_mark(marks: Dict[int, MyMark], symbol: str) -> Optional[MyMark]:
    """指定印が打たれた馬を返す。 複数いる場合は最若馬番を返す (Step1 では◎は1頭前提)"""
    candidates = [m for m in marks.values() if m.mark_symbol == symbol]
    if not candidates:
        return None
    return min(candidates, key=lambda m: m.umaban)
