#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""harville.py 性質テスト (Session 137 Phase 1)

ハーヴィル確率の数学的性質 + 既知の手計算ケースで正しさをロックする。

Usage:
    cd keiba-v2
    python -m pytest ml/tests/test_harville.py -v
"""

import sys
from itertools import permutations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from ml.strategies import harville as H


def _approx(a, b, tol=1e-9):
    return abs(a - b) < tol


# =====================================================================
# normalize
# =====================================================================

def test_normalize_sums_to_one():
    p = H.normalize({1: 0.5, 2: 0.3, 3: 0.2})
    assert _approx(sum(p.values()), 1.0)

def test_normalize_rescales_uncalibrated():
    # ML pred_proba は合計≠1 のことがある
    p = H.normalize({1: 0.4, 2: 0.3, 3: 0.1})  # 合計 0.8
    assert _approx(sum(p.values()), 1.0)
    assert _approx(p[1], 0.5)  # 0.4/0.8

def test_normalize_drops_nonpositive():
    p = H.normalize({1: 0.6, 2: 0.4, 3: 0.0, 4: -0.1})
    assert set(p.keys()) == {1, 2}


# =====================================================================
# 手計算ケース (2頭 / 3頭)
# =====================================================================

class TestKnownCases:
    def test_two_horse_umatan(self):
        p = {1: 0.6, 2: 0.4}
        assert _approx(H.umatan_prob(p, 1, 2), 0.6)   # 0.6*0.4/0.4
        assert _approx(H.umatan_prob(p, 2, 1), 0.4)   # 0.4*0.6/0.6
        assert _approx(H.umaren_prob(p, 1, 2), 1.0)   # 2頭の馬連は確実

    def test_three_horse_sanrentan(self):
        p = {1: 0.5, 2: 0.3, 3: 0.2}
        # 0.5 * 0.3/0.5 * 0.2/0.2 = 0.3
        assert _approx(H.sanrentan_prob(p, 1, 2, 3), 0.3)
        # 3頭の三連複は確実
        assert _approx(H.sanrenpuku_prob(p, 1, 2, 3), 1.0)

    def test_tansho_equals_input(self):
        p = {1: 0.5, 2: 0.3, 3: 0.2}
        assert _approx(H.tansho_prob(p, 1), 0.5)


# =====================================================================
# 数学的性質 (確率分布の整合)
# =====================================================================

class TestProperties:
    P = {1: 0.4, 2: 0.25, 3: 0.15, 4: 0.1, 5: 0.06, 6: 0.04}

    def test_tansho_sums_to_one(self):
        s = sum(H.tansho_prob(self.P, i) for i in self.P)
        assert _approx(s, 1.0)

    def test_umatan_all_pairs_sum_to_one(self):
        # 全ての (1着,2着) 順列の確率合計 = 1 (どれか1つは必ず起きる)
        s = sum(H.umatan_prob(self.P, i, j)
                for i, j in permutations(self.P, 2))
        assert _approx(s, 1.0)

    def test_sanrentan_all_triples_sum_to_one(self):
        s = sum(H.sanrentan_prob(self.P, i, j, k)
                for i, j, k in permutations(self.P, 3))
        assert _approx(s, 1.0)

    def test_fukusho_sums_to_places(self):
        # 全馬の複勝(top3)確率の合計 = 3 (top3 の枠が3つ)
        s = sum(H.fukusho_prob(self.P, i, places=3) for i in self.P)
        assert _approx(s, 3.0)

    def test_umaren_symmetric(self):
        assert _approx(H.umaren_prob(self.P, 2, 5), H.umaren_prob(self.P, 5, 2))

    def test_sanrenpuku_order_insensitive(self):
        base = H.sanrenpuku_prob(self.P, 1, 3, 5)
        for i, j, k in permutations((1, 3, 5), 3):
            assert _approx(H.sanrenpuku_prob(self.P, i, j, k), base)

    def test_umaren_equals_two_umatan(self):
        # 馬連 = 両順の馬単の和
        a = H.umaren_prob(self.P, 1, 4)
        b = H.umatan_prob(self.P, 1, 4) + H.umatan_prob(self.P, 4, 1)
        assert _approx(a, b)

    def test_wide_geq_umaren(self):
        # ワイド(3着内2頭) は 馬連(1-2着) より緩い → 確率は常に >=
        for i, j in [(1, 2), (1, 6), (3, 5)]:
            assert H.wide_prob(self.P, i, j, places=3) >= H.umaren_prob(self.P, i, j) - 1e-12

    def test_sanrenpuku_equals_six_sanrentan(self):
        s = sum(H.sanrentan_prob(self.P, *o) for o in permutations((2, 4, 6), 3))
        assert _approx(H.sanrenpuku_prob(self.P, 2, 4, 6), s)


# =====================================================================
# エッジケース
# =====================================================================

class TestEdge:
    def test_same_horse_returns_zero(self):
        p = {1: 0.6, 2: 0.4}
        assert H.umaren_prob(p, 1, 1) == 0.0
        assert H.sanrentan_prob(p, 1, 1, 2) == 0.0

    def test_missing_horse_zero(self):
        p = {1: 0.6, 2: 0.4}
        assert H.tansho_prob(p, 99) == 0.0
        assert H.umatan_prob(p, 1, 99) == 0.0

    def test_fukusho_full_field_is_certain(self):
        # places == 頭数 なら複勝は確実
        p = {1: 0.5, 2: 0.3, 3: 0.2}
        assert _approx(H.fukusho_prob(p, 2, places=3), 1.0)
