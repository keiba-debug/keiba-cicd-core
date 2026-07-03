# -*- coding: utf-8 -*-
"""スリーブ・レジストリ (Session 176 / §2.3)。

新スリーブ追加 = ここに1行 + Sleeve実装 + config の <key>_enabled + display。
★順序 = 優先度の初期既定★ (全体cap執行の第1キー候補・§11-3)。
S177: 2本目 = 本命EV単 (honmei_ev)。優先順は ★本命EV単 > 逆張り単★ (ふくだ確定 S177)。
"""
from __future__ import annotations

from typing import Dict, List

from ml.strategies.sleeves.base import Sleeve
from ml.strategies.sleeves.comment_a_sleeve import CommentASleeve
from ml.strategies.sleeves.gap_sleeve import GapSleeve
from ml.strategies.sleeves.honmei_ev_sleeve import HonmeiEvSleeve

# ★登録順 = 優先度 (全体cap執行の第1キー)★。dict は挿入順を保持する。
# S177 ふくだ確定: 本命EV単 (honmei_ev) > 逆張り単 (gap_tansho)。
# S189: 3本目 = コメＡ3点セット (comment_a・新参は最後尾 = cap 競合時に先に見送り)。
SLEEVES: Dict[str, Sleeve] = {
    HonmeiEvSleeve.key: HonmeiEvSleeve(),
    GapSleeve.key: GapSleeve(),
    CommentASleeve.key: CommentASleeve(),
}


def get_sleeve(key: str) -> Sleeve:
    if key not in SLEEVES:
        raise KeyError(f"unknown sleeve: {key!r} (registered: {tuple(SLEEVES)})")
    return SLEEVES[key]


def enabled_sleeves() -> List[Sleeve]:
    """is_enabled()=True のスリーブを ★登録順 (=優先度順)★ で返す。"""
    return [s for s in SLEEVES.values() if s.is_enabled()]
