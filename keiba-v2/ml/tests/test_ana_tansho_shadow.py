# -*- coding: utf-8 -*-
"""ana_tansho_shadow.select_ana_tansho の単体テスト (Session 169)

検証:
  - 高ARDクラスタ(max-ARD<=gap) ∩ 単勝[lo,hi] ∩ 非1人気(odds_rank>=2) を ARD降順 top_k
  - 1人気(odds_rank=1)は除外 / オッズ帯外は除外 / ARDクラスタ外は除外
  - 5頭未満は空
"""
from ml.strategies.ana_tansho_shadow import select_ana_tansho


def _e(umaban, ard, odds, odds_rank, name="H"):
    return {"umaban": umaban, "ar_deviation": ard, "odds": odds,
            "odds_rank": odds_rank, "horse_name": f"{name}{umaban}"}


def _race(entries):
    return {"entries": entries}


def test_picks_high_ard_longshot_non_favorite():
    # max ARD=59。 2番: ARD55(gap4)・54倍・人気5 → 妙味穴。 1番: ARD59 だが3倍/1人気 → 除外
    ents = [
        _e(1, 59, 3.0, 1),    # 本命(1人気) 除外
        _e(2, 55, 54.0, 5),   # ★妙味穴★
        _e(3, 50, 8.0, 3),    # オッズ低 (<20) 除外
        _e(4, 40, 80.0, 8),   # ARDクラスタ外(59-40=19>5) 除外
        _e(5, 56, 120.0, 9),  # オッズ高 (>100) 除外
        _e(6, 30, 5.0, 2),
    ]
    picks = select_ana_tansho(_race(ents), ard_gap=5, lo=20, hi=100, top_k=1)
    assert len(picks) == 1
    assert picks[0]["umaban"] == 2
    assert picks[0]["odds"] == 54.0
    assert picks[0]["ard_max"] == 59


def test_top_k_limits():
    ents = [
        _e(1, 60, 3.0, 1),    # 1人気 除外
        _e(2, 58, 25.0, 4),   # 穴1 (ARD高)
        _e(3, 57, 40.0, 6),   # 穴2
        _e(4, 56, 30.0, 5),   # 穴3
        _e(5, 30, 2.0, 2),
    ]
    picks = select_ana_tansho(_race(ents), ard_gap=5, lo=20, hi=100, top_k=2)
    assert [p["umaban"] for p in picks] == [2, 3]   # ARD降順 top2


def test_no_candidate_returns_empty():
    # 高ARD馬が全部 低オッズ (人気) → 妙味穴なし
    ents = [_e(i, 60 - i, 2.0 + i, i) for i in range(1, 8)]
    picks = select_ana_tansho(_race(ents), ard_gap=5, lo=20, hi=100, top_k=1)
    assert picks == []


def test_under_5_horses_empty():
    ents = [_e(1, 60, 30.0, 2), _e(2, 58, 40.0, 3)]
    assert select_ana_tansho(_race(ents)) == []


def test_favorite_excluded_even_if_high_ard_longshot_odds():
    # odds_rank=1 は除外 (オッズが偶然高くても1人気なら穴ではない)
    ents = [_e(1, 60, 30.0, 1)] + [_e(i, 40, 5.0, i) for i in range(2, 7)]
    assert select_ana_tansho(_race(ents), ard_gap=5, lo=20, hi=100, top_k=1) == []
