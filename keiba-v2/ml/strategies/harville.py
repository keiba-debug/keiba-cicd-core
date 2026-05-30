#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ハーヴィルの公式 — 単勝勝率から各券種の的中確率を導く純関数 (Session 137 Phase 1)

設計思想: [[bettype-selection-roadmap]] / [[feedback_betting_philosophy]] §4
  買い目の基本は予想 (ML 単勝勝率)。 ハーヴィルで各券種の的中確率を出し、
  合成オッズ判断で「どの券種を買うべきか/絞るか/降りるか」を選ぶための基盤。

ハーヴィルモデル (独立性仮定の着順確率):
  P(着順 = (a,b,c,...)) = p_a · p_b/(1-p_a) · p_c/(1-p_a-p_b) · ...
  既知の限界: 強い馬を過小・人気薄を過大評価するバイアス (特に三連単)。
  → 実運用では必ず backtest で実 ROI を検証してから使う。

純関数のみ (DB/IO なし)。 入力 probs は {horse_id: 単勝勝率}。
既定で合計 1.0 に正規化 (ML の pred_proba は独立校正で合計≠1 のことがあるため)。
"""

from __future__ import annotations

from itertools import permutations
from typing import Dict, Iterable, Hashable

Probs = Dict[Hashable, float]

_EPS = 1e-12


def normalize(probs: Probs) -> Probs:
    """単勝勝率を合計 1.0 に正規化 (0 以下は除外)。"""
    pos = {k: float(v) for k, v in probs.items() if v and float(v) > 0}
    total = sum(pos.values())
    if total <= _EPS:
        return {}
    return {k: v / total for k, v in pos.items()}


def ordered_prob(probs: Probs, order: Iterable[Hashable]) -> float:
    """指定した着順 (order = (1着, 2着, 3着, ...)) で**ちょうど**決まる確率。

    ハーヴィル: P = Π_k p_k / (1 - Σ_{先着} p)。 probs は正規化済を想定。
    """
    result = 1.0
    used = 0.0
    for hid in order:
        denom = 1.0 - used
        if denom <= _EPS:
            return 0.0
        p = probs.get(hid, 0.0)
        if p <= 0:
            return 0.0
        result *= p / denom
        used += p
    return result


def place_prob(probs: Probs, targets: Iterable[Hashable], k: int) -> float:
    """target 馬が**全員** top-k (k 着以内) に入る確率。

    複勝 (1頭が top-k) / ワイド (2頭が top-k) の共通計算。
    全 top-k 順列を走査し、 targets を含むものの ordered_prob を合算。
    """
    ids = list(probs.keys())
    tset = set(targets)
    if not tset or len(tset) > k or k > len(ids):
        # k > 頭数 のときは「全員 top-k」= targets が場にいれば確実 (端数レース)
        if tset and all(t in probs for t in tset) and k >= len(ids):
            return 1.0 if len(tset) <= len(ids) else 0.0
        if len(tset) > k:
            return 0.0
    total = 0.0
    for order in permutations(ids, k):
        if tset.issubset(order):
            total += ordered_prob(probs, order)
    return total


# ---------------------------------------------------------------------------
# 券種別 的中確率 (probs は正規化推奨。 未正規化なら normalize() を先に呼ぶ)
# ---------------------------------------------------------------------------

def tansho_prob(probs: Probs, i: Hashable) -> float:
    """単勝 i = i が 1 着"""
    return probs.get(i, 0.0)


def fukusho_prob(probs: Probs, i: Hashable, places: int = 3) -> float:
    """複勝 i = i が places 着以内 (既定 3、 7頭以下は 2、 4頭以下は 1 を呼び側で指定)"""
    return place_prob(probs, [i], places)


def umaren_prob(probs: Probs, i: Hashable, j: Hashable) -> float:
    """馬連 i-j (順不同) = i,j が 1-2 着 (どちらが上でも可)"""
    if i == j:
        return 0.0
    return ordered_prob(probs, (i, j)) + ordered_prob(probs, (j, i))


def umatan_prob(probs: Probs, i: Hashable, j: Hashable) -> float:
    """馬単 i→j = i が 1 着、 j が 2 着 (順序あり)"""
    if i == j:
        return 0.0
    return ordered_prob(probs, (i, j))


def wide_prob(probs: Probs, i: Hashable, j: Hashable, places: int = 3) -> float:
    """ワイド i-j = i,j が両方 places 着以内 (既定 3)"""
    if i == j:
        return 0.0
    return place_prob(probs, [i, j], places)


def sanrenpuku_prob(probs: Probs, i: Hashable, j: Hashable, k: Hashable) -> float:
    """三連複 {i,j,k} (順不同) = 3 頭が 1-2-3 着 (順序問わず)"""
    if len({i, j, k}) != 3:
        return 0.0
    total = 0.0
    for order in permutations((i, j, k), 3):
        total += ordered_prob(probs, order)
    return total


def sanrentan_prob(probs: Probs, i: Hashable, j: Hashable, k: Hashable) -> float:
    """三連単 i→j→k (順序あり) = i が 1 着、 j が 2 着、 k が 3 着"""
    if len({i, j, k}) != 3:
        return 0.0
    return ordered_prob(probs, (i, j, k))
