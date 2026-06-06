# -*- coding: utf-8 -*-
"""AI印 書込みの監査ログ (JSONL 追記)。

data3/ai_marks/audit/{date}.jsonl に 1 レース 1 行。
「いつ・どのレースに・何を・どの weights で書いたか / 撃ちなし理由」を残す。
AI印は markSet=6 物理分離なので手動印上書きは構造上起きないが、証跡は残す
(設計 §4.Y / 09_MY_MARKS_AND_STRATEGY.md §9.5)。

時刻は呼び出し側が渡す (workflow/CLI 由来。ライブラリ内で now() を呼ばない)。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


def _audit_dir(subdir: str = "audit") -> Path:
    root = Path(os.getenv("KEIBA_DATA_ROOT", "C:/KEIBA-CICD/data3"))
    return root / "ai_marks" / subdir


def append_audit(date: str, record: dict, ts: Optional[str] = None,
                 subdir: str = "audit") -> None:
    """1 レース分の監査レコードを {date}.jsonl に追記する。

    Args:
        date: YYYY-MM-DD (ファイル名)。
        record: {race_id, weights, marks, skipped, skip_reason, adr_used, composite_top3, notes}
        ts: ISO タイムスタンプ (呼び出し側が渡す)。
        subdir: ai_marks 配下のサブディレクトリ (既定 'audit'=AI評価印、'buy_audit'=買い軸印)。
    """
    d = _audit_dir(subdir)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{date}.jsonl"
    line = {"ts": ts, **record}
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
