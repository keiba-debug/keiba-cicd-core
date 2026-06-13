#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E-003 接戦タイブレーク — 騎手の接戦勝率(close_win_rate)を買い目の同点解消に使う。

`analysis/jockey_close_finish.json`（E-010 で quality メタ付与済み）の ranking から
騎手コード → close_win_rate / quality を引き、quality_gate.reliable_value で
「信頼性を織り込んだ採用値」(ci95.lower 一本) を返す。

設計（[[analysis-reuse-project]] E-003）:
- composite vb_score が **同点** のときだけ効く純粋なタイブレーク信号。買う/買わないの
  判定そのものは変えない（既定 OFF / params.enable_close_tiebreak で明示 ON）。
- 生率 0.769（10/13）でなく ci95.lower 0.451 を採用＝小標本の上振れ騎手に軸を奪われない
  （[[feedback_betting_philosophy]] の「妙味は下振れ側で測る」と同じ向き）。
- ranking に居ない騎手（接戦試行<閾値で集計対象外）は 0.0 ＝ 実績のある騎手に控えめに劣後。

このモジュールは読み込み＋純関数のみ。bet_engine 側は map を受け取って消費する。
"""

import json
from pathlib import Path
from typing import Dict, Optional

from ml.strategies.quality_gate import reliable_value


def load_jockey_close_map(path: Optional[Path] = None) -> Dict[str, dict]:
    """jockey_close_finish.json の ranking を {騎手code: entry} に変換して返す。

    Args:
        path: JSON パス。未指定なら config.analysis_dir()/jockey_close_finish.json。

    Returns:
        {jockey_code: {"close_win_rate": float, "quality": dict, ...}}。
        ファイル不在・壊れている場合は空 dict（呼び出し側はタイブレーク無効として扱える）。
    """
    if path is None:
        from core import config
        path = config.analysis_dir() / "jockey_close_finish.json"
    path = Path(path)
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    ranking = data.get("ranking")
    if not isinstance(ranking, list):
        return {}
    out: Dict[str, dict] = {}
    for r in ranking:
        code = r.get("code")
        if code:
            out[str(code)] = r
    return out


def jockey_close_reliable(jmap: Dict[str, dict], jockey_code: Optional[str]) -> float:
    """騎手コードから接戦勝率の信頼性採用値(ci95.lower 採用)を返す。

    map に居ない / コード欠損なら 0.0（タイブレークで実績騎手に劣後）。
    """
    if not jockey_code:
        return 0.0
    entry = jmap.get(str(jockey_code))
    if not entry:
        return 0.0
    point = entry.get("close_win_rate", 0.0) or 0.0
    return reliable_value(entry.get("quality"), float(point))
