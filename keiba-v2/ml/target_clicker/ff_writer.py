#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""TARGET 買い目取り込み FF CSV ライター (Python 版)

既存 TS 実装 `keiba-v2/web/src/lib/data/target-pd-writer.ts` の完全互換ポート。
公式仕様: https://targetfaq.jra-van.jp/faq/detail?site=SVKNEGBV&category=48&id=693

FF CSV 構造 (1行 = 1買い目, 12フィールド):
  [0]  レースID (16桁)
  [1]  返還フラグ (0=有効)
  [2]  券種 (0=単勝, 1=複勝, 2=枠連, 3=馬連, 4=ワイド, 5=馬単, 6=三連複, 7=三連単)
  [3]  目１ (馬番) ※必須
  [4]  目２ (0 = なし)
  [5]  目３ (0 = なし)
  [6]  購入金額 (円)
  [7]  オッズ (0 = 未確定)
  [8]  的中時配当 (0 = 未確定)
  [9-11] エリア/マーク/一括購入目 (省略)

ファイル: {JV_DATA_ROOT}/TXT/FFyyyymmdd_HHmmss.CSV
エンコ:   Shift-JIS (cp932), CRLF
"""

from __future__ import annotations

import os
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional


# 券種コード (TS BET_TYPE_CODE と完全一致)
BET_TYPE_CODE = {
    "tansho": 0,       # 単勝
    "fukusho": 1,      # 複勝
    "wakuren": 2,      # 枠連
    "umaren": 3,       # 馬連
    "wide": 4,         # ワイド
    "umatan": 5,       # 馬単
    "sanrenpuku": 6,   # 三連複
    "sanrentan": 7,    # 三連単
}
BET_TYPE_NAME = {v: k for k, v in BET_TYPE_CODE.items()}

VALID_BET_TYPES = set(BET_TYPE_CODE.values())
TWO_HORSE_TYPES = {2, 3, 4, 5}   # 枠連/馬連/ワイド/馬単
THREE_HORSE_TYPES = {6, 7}        # 三連複/三連単


def _jv_root() -> Path:
    return Path(os.getenv("JV_DATA_ROOT", "C:/TFJV"))


def ff_csv_dir() -> Path:
    return _jv_root() / "TXT"


@dataclass
class FfBet:
    """1 件の買い目"""
    race_id: str           # 16桁
    bet_type: int          # 0=単勝, 1=複勝, 3=馬連, 4=ワイド, 5=馬単, 6=三連複, 7=三連単
    umaban: int            # 目１ (馬番)
    amount: int            # 円
    umaban2: Optional[int] = None
    umaban3: Optional[int] = None

    def validate(self) -> None:
        if not self.race_id or len(self.race_id) != 16 or not self.race_id.isdigit():
            raise ValueError(f"invalid race_id: {self.race_id!r}")
        if self.bet_type not in VALID_BET_TYPES:
            raise ValueError(f"invalid bet_type: {self.bet_type}")
        if not (1 <= self.umaban <= 18):
            raise ValueError(f"invalid umaban: {self.umaban}")
        if self.bet_type in TWO_HORSE_TYPES:
            if not self.umaban2 or not (1 <= self.umaban2 <= 18):
                raise ValueError(f"bet_type={self.bet_type} requires umaban2")
        if self.bet_type in THREE_HORSE_TYPES:
            if not self.umaban2 or not (1 <= self.umaban2 <= 18):
                raise ValueError(f"bet_type={self.bet_type} requires umaban2")
            if not self.umaban3 or not (1 <= self.umaban3 <= 18):
                raise ValueError(f"bet_type={self.bet_type} requires umaban3")
        if self.amount < 100 or self.amount % 100 != 0:
            raise ValueError(f"amount must be >=100 and multiple of 100: {self.amount}")


def _build_row(b: FfBet) -> str:
    fields = [
        b.race_id,                            # [0]
        "0",                                  # [1] 返還フラグ
        str(b.bet_type),                      # [2]
        str(b.umaban),                        # [3]
        str(b.umaban2 or 0),                  # [4]
        str(b.umaban3 or 0),                  # [5]
        str(b.amount),                        # [6]
        "0",                                  # [7] オッズ
        "0",                                  # [8] 的中時配当
        "",                                   # [9] エリア
        "",                                   # [10] マーク
        "",                                   # [11] 一括購入目
    ]
    return ",".join(fields)


def write_ff_csv(bets: list[FfBet]) -> Path:
    """FF CSV ファイルを書き出す。 戻り値は最後に書いたファイルパス。

    複数日が混在する場合は日付ごとに別ファイル (現状ユースケースは単日想定)。
    """
    if not bets:
        raise ValueError("bets is empty")

    for b in bets:
        b.validate()

    by_date: dict[str, list[FfBet]] = defaultdict(list)
    for b in bets:
        by_date[b.race_id[:8]].append(b)

    out_dir = ff_csv_dir()
    out_dir.mkdir(parents=True, exist_ok=True)

    last_path: Optional[Path] = None
    for date_str, day_bets in by_date.items():
        now = datetime.now()
        fname = f"FF{date_str}_{now.strftime('%H%M%S')}.CSV"
        path = out_dir / fname
        lines = [_build_row(b) for b in day_bets]
        content = "\r\n".join(lines) + "\r\n"
        path.write_bytes(content.encode("cp932"))
        last_path = path

    assert last_path is not None
    return last_path


def parse_bet_spec(spec: str) -> FfBet:
    """CLI 用の簡易パーサ

    形式:
      race_id:bet_type:umaban[/umaban2[/umaban3]]:amount

    例:
      '2026052404010301:tansho:5:100'              → 新潟3R 単勝5 100円
      '2026052405021103:umaren:3/7:200'             → 馬連 3-7 200円
      '2026052408031103:sanrentan:5/3/9:100'        → 三連単 5→3→9 100円
    """
    parts = spec.split(":")
    if len(parts) != 4:
        raise ValueError(f"bet spec must be race_id:bet_type:horses:amount, got: {spec!r}")
    race_id, bt_name, horses_str, amount_str = parts
    if bt_name not in BET_TYPE_CODE:
        raise ValueError(f"unknown bet_type: {bt_name} (valid: {list(BET_TYPE_CODE)})")
    horses = [int(h) for h in horses_str.split("/")]
    bt = BET_TYPE_CODE[bt_name]

    if bt in (0, 1):  # tansho / fukusho
        if len(horses) != 1:
            raise ValueError(f"{bt_name} expects 1 horse, got {len(horses)}")
        return FfBet(race_id=race_id, bet_type=bt, umaban=horses[0],
                     amount=int(amount_str))
    if bt in TWO_HORSE_TYPES:
        if len(horses) != 2:
            raise ValueError(f"{bt_name} expects 2 horses, got {len(horses)}")
        return FfBet(race_id=race_id, bet_type=bt, umaban=horses[0],
                     umaban2=horses[1], amount=int(amount_str))
    if bt in THREE_HORSE_TYPES:
        if len(horses) != 3:
            raise ValueError(f"{bt_name} expects 3 horses, got {len(horses)}")
        return FfBet(race_id=race_id, bet_type=bt, umaban=horses[0],
                     umaban2=horses[1], umaban3=horses[2], amount=int(amount_str))
    raise ValueError(f"unhandled bet_type: {bt}")
