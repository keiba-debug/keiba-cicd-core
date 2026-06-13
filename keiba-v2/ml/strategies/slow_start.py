#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""出遅れ(slow start)分析の reader — 馬+騎手の出遅れ率を quality-gate で引く。

`analysis/slow_start_analysis.json`（E-010 で jockey_ranking に quality 付与済・
horse_stats は N過少のため quality なし）から:
- 騎手コード → slow_start_rate / quality(ci95) → `reliable_value`(ci95.lower)
- 馬 ketto_num → slow_start_rate（point のみ・quality なし → 点推定フォールバック）

用途は **表示タグ（E-005 出遅れ注意）** が主。買い目フィルタとしては逆効果
（出遅れ常習馬の ROI が最良＝市場が過剰割引・[[analyze_slow_start_edge]] で実証）と分かっており、
切る/減点には使わない。jockey_close.py と同じ reader→reliable_value パターン。
"""

import json
from pathlib import Path
from typing import Dict, Optional, Tuple

from ml.strategies.quality_gate import reliable_value


def load_slow_start_maps(path: Optional[Path] = None) -> Tuple[Dict[str, dict], Dict[str, dict]]:
    """slow_start_analysis.json → (jockey_map[code], horse_map[ketto_num])。

    ファイル不在・破損時は (空, 空) を返す（呼び出し側はタグ無効として扱える）。
    """
    if path is None:
        from core import config
        path = config.analysis_dir() / "slow_start_analysis.json"
    path = Path(path)
    if not path.exists():
        return {}, {}
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}, {}
    jmap: Dict[str, dict] = {}
    for r in data.get("jockey_ranking", []) or []:
        c = r.get("jockey_code")
        if c:
            jmap[str(c)] = r
    hmap: Dict[str, dict] = {}
    for r in data.get("horse_stats", []) or []:
        k = r.get("ketto_num")
        if k:
            hmap[str(k)] = r
    return jmap, hmap


def jockey_slow_start_reliable(jmap: Dict[str, dict], jockey_code: Optional[str]) -> float:
    """騎手の出遅れ率の信頼性採用値(ci95.lower)。map不在/コード欠損なら 0.0。"""
    if not jockey_code:
        return 0.0
    entry = jmap.get(str(jockey_code))
    if not entry:
        return 0.0
    point = entry.get("slow_start_rate", 0.0) or 0.0
    return reliable_value(entry.get("quality"), float(point))


def horse_slow_start_rate(hmap: Dict[str, dict], ketto_num: Optional[str]) -> float:
    """馬の出遅れ率(point)。quality なし＝点推定。map不在/欠損なら 0.0。

    ※ N過少の馬は上振れしやすい。表示タグでは effective_n を併用して注意喚起する。
    """
    if not ketto_num:
        return 0.0
    entry = hmap.get(str(ketto_num))
    if not entry:
        return 0.0
    return float(entry.get("slow_start_rate", 0.0) or 0.0)
