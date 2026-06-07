# -*- coding: utf-8 -*-
"""AI評価印 / AI購入軸印 を TARGET DAT に書く Python writer。

印スロット再編 (docs/auto-purchase/26_MARK_SLOT_MAP.md / ふくだ確定 2026-06-06):
  1=My手動 / 2=AI評価 / 3=AI購入軸 / 4-8=将来拡張。

web/src/lib/data/target-mark-reader.ts の batchWriteHorseMarks と
**バイト互換** (record_index=(day-1)*12+(race-1)、offset=record*44+6+(uma-1)*2、
新規ファイルは 0x20 初期化 + 各レコード末尾 CR/LF、8日以下=96 / 9日以上=144 records)。

スロット (markSet) と用途:
  - markSet=1 : ふくだ手動印 (◎○▲△Ⅲ穴消)。**writer から書込み禁止** (施錠)。
  - markSet=2 : AI評価印 (◎○▲△Ⅲ穴)。`write_ai_marks_to_dat` 専用。
                購入軸 writer からは **凍結・書換禁止** (将来のML特徴量化/監査)。
  - markSet=3 : AI購入軸印 (実際に買った 軸=★ / 相手=☆)。`write_buy_marks_to_dat` 専用。
                中立記号で「評価(◎) と 買い目(★☆) を意味分離」する (設計書 23 案C)。

設計: docs/auto-purchase/22_AI_MARKS_DESIGN.md §2 / §3.5,
      docs/auto-purchase/23_AI_MARK_VOTE_SYNC_DESIGN.md (案C),
      docs/auto-purchase/26_MARK_SLOT_MAP.md
安全機構 (シズネ施錠ガード):
  - 各 writer は自分のスロットのみ書込み可。markSet=1/2/3 を相互に侵さない。
  - markSet=2 (AI評価) は購入軸 writer から書換不可 = 凍結ガード (条件①)。
  - 書込み印は VALID_*_MARKS のみ (typo 無検証書込み防止)。

座標逆引き・パス解決は ml.features.my_marks を再利用 (再発明しない)。
購入軸印 (★☆) の symbol↔byte 表はこのモジュールに self-contained で持つ
(my_marks.py は live 戦略から import されるため触らない)。
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable

from ml.features.my_marks import RaceCoord, get_mark_file_path, parse_race_id

# 記号 → Shift-JIS(CP932) 2バイト。
# ◎○▲△Ⅲ穴 は my_marks._MARK_BYTES_TO_SYMBOL と同一バイト。
# ★☆ は購入軸印 (target-mark-reader.ts の MARK_BYTES_TO_SYMBOL と対称: 819a/8199)。
_SYMBOL_TO_MARK_BYTES: Dict[str, bytes] = {
    "◎": b"\x81\x9d",
    "○": b"\x81\x9b",
    "▲": b"\x81\xa3",
    "△": b"\x81\xa2",
    "Ⅲ": b"\x87\x56",
    "穴": b"\x8c\x8a",
    "★": b"\x81\x9a",  # 購入軸 (axis) — 中立記号
    "☆": b"\x81\x99",  # 購入相手 (partner) — 中立記号
    "": b"\x20\x20",   # 無印 (クリア)
}

# byte → symbol 逆引き (round-trip / decode 対称テスト用)。
_MARK_BYTES_TO_SYMBOL: Dict[bytes, str] = {
    b: s for s, b in _SYMBOL_TO_MARK_BYTES.items() if s
}

# AI評価印で書込みを許可する印 (Step2 で ◎○▲△Ⅲ穴 を解禁)。
# 「消」は持ち込まない (explicit_erase は手動印 my_marks_v2 専用、設計 §4-E)。
VALID_AI_MARKS = ("◎", "○", "▲", "△", "Ⅲ", "穴")

# AI購入軸印で書込みを許可する印 (★=軸 / ☆=相手 のみ)。
VALID_BUY_MARKS = ("★", "☆")

_RECORD_BYTES = 44
_MARK_AREA_OFFSET = 6  # レコード先頭からの馬印領域開始
_MARK_SLOT_AI = 2      # AI評価スロット (印スロット再編 2026-06-06: 旧 6 → 2)
_MARK_SLOT_BUY = 3     # AI購入軸スロット (印スロット再編 2026-06-06: 旧 8 → 3)


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


def _write_marks_core(
    race_id: str,
    marks: Dict[int, str],
    *,
    mark_set: int,
    valid_marks: Iterable[str],
    clear_race_first: bool,
) -> int:
    """1 レース分の印を任意スロットに書く共通コア。書いた頭数を返す。

    呼び出し側 (write_ai_marks_to_dat / write_buy_marks_to_dat) が施錠ガードと
    valid_marks を渡す。 ここでは印のバイト変換と byte offset 書込みのみ行う。
    """
    if not marks:
        return 0
    valid_set = set(valid_marks)
    for u, sym in marks.items():
        if sym not in _SYMBOL_TO_MARK_BYTES:
            raise ValueError(f"未知の印: {sym!r} (umaban={u})")
        if sym and sym not in valid_set:
            raise ValueError(
                f"markSet={mark_set} で許可されない印: {sym!r} "
                f"(許可={tuple(valid_set)})"
            )
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


def write_ai_marks_to_dat(
    race_id: str,
    marks: Dict[int, str],
    mark_set: int = _MARK_SLOT_AI,
    clear_race_first: bool = True,
) -> int:
    """1 レース分の AI評価印 を markSet=2 に書く。書いた頭数を返す。

    Args:
        race_id: 16桁 race_id。
        marks: {umaban: '◎'}。空 dict なら何もしない (0 を返す)。
        mark_set: 既定 2 (AI評価)。1/3 を渡すと例外 (施錠ガード)。
        clear_race_first: True なら当該レコードの18頭分を 0x2020 でクリアしてから書く
            (AI評価スロットは AI 専用なので安全。前回の◎が別馬に残るのを防ぐ)。

    Raises:
        ValueError: mark_set∈{1,3} / 未知の印 / 不正 umaban。
    """
    if mark_set == 1:
        raise ValueError("mark_set=1 はふくだ手動印専用。AI評価は mark_set=2 を使うこと")
    if mark_set == _MARK_SLOT_BUY:
        raise ValueError("mark_set=3 はAI購入軸専用。AI評価 writer は mark_set=2 のみ書込み可")
    return _write_marks_core(
        race_id, marks, mark_set=mark_set,
        valid_marks=VALID_AI_MARKS, clear_race_first=clear_race_first,
    )


def write_buy_marks_to_dat(
    race_id: str,
    marks: Dict[int, str],
    mark_set: int = _MARK_SLOT_BUY,
    clear_race_first: bool = True,
) -> int:
    """1 レース分の AI購入軸印 (軸=★ / 相手=☆) を markSet=3 に書く。書いた頭数を返す。

    購入軸印は「実際に購入した 軸+相手」を表示するための **中立記号** で、
    評価印 (markSet=2 ◎○▲△Ⅲ穴) とは意味も物理スロットも分離する (設計書 23 案C)。
    購入の正本は purchase_ledger であり、この印は表示用 (条件⑥)。

    Args:
        race_id: 16桁 race_id。
        marks: {umaban: '★'|'☆'}。空 dict なら何もしない (0 を返す)。
        mark_set: 既定 3 (AI購入軸)。1/2 を渡すと例外 (施錠 + markSet=2 凍結ガード)。
        clear_race_first: True なら当該レコードの18頭分を 0x2020 でクリアしてから書く。

    Raises:
        ValueError: mark_set∈{1,2} / ★☆ 以外の印 / 不正 umaban。
    """
    if mark_set == 1:
        raise ValueError("mark_set=1 はふくだ手動印専用。AI購入軸は mark_set=3 を使うこと")
    if mark_set == _MARK_SLOT_AI:
        raise ValueError(
            "mark_set=2 は AI評価印専用・凍結。AI購入軸は mark_set=3 を使うこと "
            "(markSet=2 凍結ガード)"
        )
    return _write_marks_core(
        race_id, marks, mark_set=mark_set,
        valid_marks=VALID_BUY_MARKS, clear_race_first=clear_race_first,
    )


def read_marks_from_dat(race_id: str, mark_set: int) -> Dict[int, str]:
    """DAT から 1 レース分の印を読み戻す (round-trip / decode 対称テスト用)。

    my_marks._decode_dat_marks と同じ byte 解釈だが、★☆ を含む
    _MARK_BYTES_TO_SYMBOL で decode する (my_marks 側は★☆を持たないため
    購入軸スロットの検証にはこちらを使う)。ファイル無し / 範囲外は空 dict。
    """
    coord = parse_race_id(race_id)
    path = get_mark_file_path(coord, mark_set=mark_set)
    if not path.exists():
        return {}
    raw = path.read_bytes()
    rec_start = _record_index(coord.day_in_meet, coord.race_number) * _RECORD_BYTES
    if rec_start + _RECORD_BYTES > len(raw):
        return {}
    out: Dict[int, str] = {}
    for uma in range(1, 19):
        off = rec_start + _MARK_AREA_OFFSET + (uma - 1) * 2
        sym = _MARK_BYTES_TO_SYMBOL.get(bytes(raw[off:off + 2]))
        if sym:
            out[uma] = sym
    return out
