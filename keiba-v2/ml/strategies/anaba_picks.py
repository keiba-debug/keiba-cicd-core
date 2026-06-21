#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""印4 (競馬ブックコメント × ローカルLLM 穴馬ピックアップ) の読み込み (Session 170)

印4 = AI指数 (composite/rank_w) で拾えない穴馬を Ollama (qwen2.5:14b) がコメントから
抽出したもの。 自動投票の「印4ワイド」(◎ → 印4馬 最大2頭 流し) で使う。

  - live     : data3/comment_llm/live/picks_{date}.json (confidence 高/中/低 = A/B/C 付き)
  - backtest : data3/comment_llm/backtest/flags_bt_{rid}.json (value_picks・confidence なし)

race_id × umaban で結合。 ★max 2頭★ (ふくだ確定 / S170)。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

_BT_DIR = Path("C:/KEIBA-CICD/data3/comment_llm/backtest")
_LIVE_DIR = Path("C:/KEIBA-CICD/data3/comment_llm/live")
MAX_ANABA = 2  # 印4馬は最大2頭 (ふくだ確定)


def _umabans_from_picks(picks: list, max_n: int) -> List[int]:
    out: List[int] = []
    for p in picks or []:
        if not isinstance(p, dict):
            continue  # 稀に LLM 出力JSON破損で str が混入 (flags_bt の1件で観測)
        u = p.get("umaban")
        if u is None:
            continue
        try:
            iu = int(u)
        except (TypeError, ValueError):
            continue
        if iu not in out:
            out.append(iu)
    return out[:max_n]


def load_anaba_backtest(race_ids, *, max_n: int = MAX_ANABA) -> Dict[str, List[int]]:
    """flags_bt_{rid}.json の value_picks → {rid: [umaban]} (最大 max_n 頭)。"""
    out: Dict[str, List[int]] = {}
    for rid in race_ids:
        f = _BT_DIR / f"flags_bt_{rid}.json"
        if not f.exists():
            continue
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        umas = _umabans_from_picks(d.get("value_picks"), max_n)
        if umas:
            out[rid] = umas
    return out


def load_anaba_live(date_str: str, *, max_n: int = MAX_ANABA) -> Dict[str, List[int]]:
    """live picks_{date}.json → {rid: [umaban]}。 confidence A(高)>B(中)>C(低) 順に最大 max_n 頭。

    picks_{date}.json は 1 ファイルに複数レース (list または {races:[...]})。
    """
    f = _LIVE_DIR / f"picks_{date_str}.json"
    if not f.exists():
        return {}
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if isinstance(data, list):
        races = data
    elif isinstance(data, dict):
        races = data.get("races") or [data]
    else:
        return {}
    conf_rank = {"高": 0, "中": 1, "低": 2}
    out: Dict[str, List[int]] = {}
    for r in races:
        rid = str((r or {}).get("race_id") or "")
        picks = (r or {}).get("picks") or []
        picks_sorted = sorted(picks, key=lambda p: conf_rank.get((p or {}).get("confidence", ""), 3))
        umas = _umabans_from_picks(picks_sorted, max_n)
        if rid and umas:
            out[rid] = umas
    return out
