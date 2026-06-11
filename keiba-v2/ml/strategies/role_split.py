#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""W/P 乖離による役割分化 — 「○の頭はない」の機械化 (Session 148 / 捨て馬券の土台)

ふくだの買い方知恵: 「経験的に、勝ち切る可能性が明らかにある馬と、好走する
(2-3着止まり) の馬を分けられるときがある」→ 例: 三連複◎○▲が合成2.0倍で安く、
「○の頭はない」と読めるとき三連単 ◎▲→◎○▲→◎○▲ だけ買う (○を1列目から外す)。

機械化: win_share = pred_w / pred_p (来たとき勝ち切る度)。
頭候補群 (◎○▲) の中で share が群中央値 × ratio 未満の馬 = P型 (2-3着要員) と判定し、
bet_templates.apply_template(no_head=...) で順序系券種の 1 列目から外す。

検証実績 (analyze_wp_split / 2934R / Session 148):
  - 印対象馬の P(1着|3着内): win_share 五分位で Q1 22.3% → Q5 45.2% (単調)
  - ○P型 (ratio=0.6) 発火 336R: 三連単BOX ROI 128.2% → ○頭捨て4点 172.8%
    (コスト 2/3 で払戻ほぼ維持)

純関数・DB/モデル非依存。判定材料 (pred_w/pred_p) は呼び出し側が渡す。
"""

from __future__ import annotations

from statistics import median
from typing import List, Optional, Sequence, Tuple

# P型判定の既定比率 (share < head群中央値 × ratio)。Session 148 検証値。
P_TYPE_RATIO = 0.6

# (umaban, pred_w, pred_p)
HorseWP = Tuple[int, Optional[float], Optional[float]]


def win_share(pred_w: Optional[float], pred_p: Optional[float]) -> Optional[float]:
    """勝ち切り度 = pred_w / pred_p。判定不能 (欠損・P<=0) は None。"""
    if pred_w is None or pred_p is None or pred_p <= 0:
        return None
    return pred_w / pred_p


def detect_no_head(head_horses: Sequence[HorseWP], *,
                   ratio: float = P_TYPE_RATIO) -> List[int]:
    """頭候補群から「1着に来ない (P型)」馬番を検出する。

    head_horses: 頭候補 (例: ◎○▲ の3頭) の (umaban, pred_w, pred_p)。
    判定: win_share が群中央値 × ratio 未満 → P型。
    share が判定不能の馬は P型にしない (情報なしで頭から外さない)。
    群の有効 share が 2 頭未満なら判定しない (中央値が意味を持たない)。
    """
    shares = [(int(u), win_share(w, p)) for u, w, p in head_horses]
    valid = [s for _, s in shares if s is not None]
    if len(valid) < 2:
        return []
    med = median(valid)
    threshold = med * ratio
    return [u for u, s in shares if s is not None and s < threshold]
