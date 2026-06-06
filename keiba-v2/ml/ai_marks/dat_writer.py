# -*- coding: utf-8 -*-
"""AI予想印 (AI評価) を TARGET DAT に書く Python writer。

印スロット再編 (docs/auto-purchase/26_MARK_SLOT_MAP.md / ふくだ確定 2026-06-06):
  AI評価 = markSet=2 (旧 6 から移動)。1=My手動 / 2=AI評価 / 3=AI購入軸 / 4-8=将来拡張。

web/src/lib/data/target-mark-reader.ts の batchWriteHorseMarks と
**バイト互換** (record_index=(day-1)*12+(race-1)、offset=record*44+6+(uma-1)*2、
新規ファイルは 0x20 初期化 + 各レコード末尾 CR/LF、8日以下=96 / 9日以上=144 records)。

設計: docs/auto-purchase/22_AI_MARKS_DESIGN.md §2 / §3.5 / 26_MARK_SLOT_MAP.md
安全機構 (シズネ施錠ガード):
  - mark_set=1 への書込みは例外 (ふくだ手動印専用)。AI評価は markSet=2。
  - 書込み印は VALID_AI_MARKS のみ (typo 無検証書込み防止)。

座標逆引き・パス解決は ml.features.my_marks を再利用 (再発明しない)。
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Tuple

from ml.features.my_marks import RaceCoord, get_mark_file_path, parse_race_id

# 記号 → Shift-JIS 2バイト (my_marks._MARK_BYTES_TO_SYMBOL の逆 + encode 規則)
_SYMBOL_TO_MARK_BYTES: Dict[str, bytes] = {
    "◎": b"\x81\x9d",
    "○": b"\x81\x9b",
    "▲": b"\x81\xa3",
    "△": b"\x81\xa2",
    "Ⅲ": b"\x87\x56",
    "穴": b"\x8c\x8a",
    "": b"\x20\x20",  # 無印 (クリア)
}

# AI印で書込みを許可する印 (Step2 で ◎○▲△Ⅲ穴 を解禁)。
# 「消」は持ち込まない (explicit_erase は手動印 my_marks_v2 専用、設計 §4-E)。
VALID_AI_MARKS = ("◎", "○", "▲", "△", "Ⅲ", "穴")

_RECORD_BYTES = 44
_MARK_AREA_OFFSET = 6  # レコード先頭からの馬印領域開始
_MARK_SLOT_AI = 2      # AI評価スロット (印スロット再編 2026-06-06: 旧 6 → 2)


def _required_records(day: int) -> int:
    return 144 if day > 8 else 96


def _record_index(day: int, race_number: int) -> int:
    return (day - 1) * 12 + (race_number - 1)


def _init_buffer(n_records: int) -> bytearray:
    buf = bytearray(b"\x20" * (n_records * _RECORD_BYTES))
    for i in range(n_records):
        base = i * _RECORD_BYTES
        buf[base + 42] = 0x0D  # CR
        buf[base + 43] = 0x0A  # LF
    return buf


def write_ai_marks_to_dat(
    race_id: str,
    marks: Dict[int, str],
    mark_set: int = _MARK_SLOT_AI,
    clear_race_first: bool = True,
) -> int:
    """1 レース分の AI印を DAT に書く。書いた頭数を返す。

    Args:
        race_id: 16桁 race_id。
        marks: {umaban: '◎'}。空 dict なら何もしない (0 を返す)。
        mark_set: 既定 2 (AI評価)。1 を渡すと例外 (施錠ガード=手動印保護)。
        clear_race_first: True なら当該レコードの18頭分を 0x2020 でクリアしてから書く
            (AI印スロットは AI 専用なので安全。前回の◎が別馬に残るのを防ぐ)。

    Raises:
        ValueError: mark_set==1 / 未知の印 / 不正 umaban。
    """
    if mark_set == 1:
        raise ValueError("mark_set=1 はふくだ手動印専用。AI評価は mark_set=2 を使うこと")
    if not marks:
        return 0
    for u, sym in marks.items():
        if sym not in _SYMBOL_TO_MARK_BYTES:
            raise ValueError(f"未知の印: {sym!r} (umaban={u})")
        if sym not in VALID_AI_MARKS and sym != "":
            raise ValueError(f"AI印で許可されない印: {sym!r} (Step1 は ◎ のみ)")
        if not (1 <= int(u) <= 18):
            raise ValueError(f"umaban 範囲外: {u}")

    coord: RaceCoord = parse_race_id(race_id)
    path: Path = get_mark_file_path(coord, mark_set=mark_set)
    n_records = _required_records(coord.day_in_meet)
    required_size = n_records * _RECORD_BYTES

    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        buf = _init_buffer(n_records)
    else:
        raw = bytearray(path.read_bytes())
        if len(raw) < required_size:
            expanded = _init_buffer(n_records)
            expanded[: len(raw)] = raw  # 既存データ保持
            buf = expanded
        else:
            buf = raw

    rec_start = _record_index(coord.day_in_meet, coord.race_number) * _RECORD_BYTES

    if clear_race_first:
        for uma in range(1, 19):
            off = rec_start + _MARK_AREA_OFFSET + (uma - 1) * 2
            buf[off:off + 2] = b"\x20\x20"

    written = 0
    for u, sym in marks.items():
        off = rec_start + _MARK_AREA_OFFSET + (int(u) - 1) * 2
        buf[off:off + 2] = _SYMBOL_TO_MARK_BYTES[sym]
        if sym:
            written += 1

    path.write_bytes(bytes(buf))
    return written
