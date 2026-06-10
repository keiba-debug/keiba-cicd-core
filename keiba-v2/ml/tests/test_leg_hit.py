# -*- coding: utf-8 -*-
"""backtest_bettype_fund.leg_hit の回帰テスト (Session 146 / W9)

★発見した精算バグの再発防止:
  - sanrenpuku / sanrentan が leg_hit で未処理 → 常に False (0 ヒット) だった。
  - umaren が着順でなく馬番でソートしていた → ほぼ的中しなかった。
finish = {umaban: 着順}。 top3 = {1,2,3 着}, top2 = {1,2 着}。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.analyze.backtest_bettype_fund import leg_hit

# 着順: 馬5=1着, 馬3=2着, 馬8=3着, 馬1=4着
FINISH = {5: 1, 3: 2, 8: 3, 1: 4, 2: 5}


def test_tansho():
    assert leg_hit("tansho", [5], FINISH) is True
    assert leg_hit("tansho", [3], FINISH) is False


def test_fukusho():
    assert leg_hit("fukusho", [8], FINISH) is True   # 3着
    assert leg_hit("fukusho", [1], FINISH) is False  # 4着


def test_umaren_order_independent():
    # 1-2着の組 = {5,3}。 馬番順でなく着順で判定されること。
    assert leg_hit("umaren", [3, 5], FINISH) is True
    assert leg_hit("umaren", [5, 3], FINISH) is True
    assert leg_hit("umaren", [5, 8], FINISH) is False  # 8 は3着


def test_wide():
    assert leg_hit("wide", [5, 8], FINISH) is True   # 1着・3着とも top3
    assert leg_hit("wide", [5, 1], FINISH) is False  # 1 は4着
    assert leg_hit("wide", [5, 5], FINISH) is False  # 同一馬は不成立


def test_umatan_ordered():
    assert leg_hit("umatan", [5, 3], FINISH) is True   # 1着→2着
    assert leg_hit("umatan", [3, 5], FINISH) is False  # 順序違い


def test_sanrenpuku_set():
    assert leg_hit("sanrenpuku", [8, 5, 3], FINISH) is True   # {1,2,3着}
    assert leg_hit("sanrenpuku", [5, 3, 1], FINISH) is False  # 1 は4着


def test_sanrentan_ordered():
    assert leg_hit("sanrentan", [5, 3, 8], FINISH) is True    # 1→2→3着
    assert leg_hit("sanrentan", [5, 8, 3], FINISH) is False   # 2,3着が逆
    assert leg_hit("sanrentan", [3, 5, 8], FINISH) is False


def test_dead_heat_1st_two_horses_umaren_ok():
    # 1着同着2頭 → fp<=2 の集合 = {5,3} の2頭 = 通常の 1-2着と同じ扱いで成立。
    finish = {5: 1, 3: 1, 8: 3}
    assert leg_hit("umaren", [5, 3], finish) is True


def test_dead_heat_1st_three_horses_breaks_umaren():
    # 1着同着3頭 → fp<=2 の集合が3頭 (len!=2) → どの2頭 umaren も不成立 (保守)。
    finish = {5: 1, 3: 1, 8: 1, 1: 4}
    assert leg_hit("umaren", [5, 3], finish) is False
    assert leg_hit("umaren", [3, 8], finish) is False
    # 同じく sanrenpuku は top3 が3頭ちょうどなら成立しうる ({5,3,8} = fp<=3)
    assert leg_hit("sanrenpuku", [5, 3, 8], finish) is True
