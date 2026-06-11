# -*- coding: utf-8 -*-
"""synthetic_odds (合成オッズ・トリガミ検出・点削減) のテスト (Session 148 / F1)

ふくだの捨て馬券例 (三連複合成2.0倍が安い → 三連単だけ残す) がそのまま
トリガミ検出 / prune の代表ケースになっている。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.strategies.bet_templates import ROLE_BONUS, ROLE_INSURANCE, Ticket
from ml.strategies.synthetic_odds import (
    analyze_plan, kumiban, make_odds_lookup, prune_to_floor,
)


def _t(bet_type, horses, role="本線", w=1.0):
    return Ticket(bet_type, tuple(horses), role, "test", w)


def _odds_map(mapping):
    """{(bet_type, horses tuple): odds} -> OddsOf。順不同系はソート済キーで引く。"""
    def of(tk):
        key = tuple(tk.horses) if tk.bet_type in ("umatan", "sanrentan", "tansho", "fukusho") \
            else tuple(sorted(tk.horses))
        return mapping.get((tk.bet_type, key))
    return of


# ---------------------------------------------------------------------------
# kumiban / make_odds_lookup
# ---------------------------------------------------------------------------

def test_kumiban():
    assert kumiban((2, 1), ordered=False) == "0102"      # 順不同 → 昇順
    assert kumiban((2, 1), ordered=True) == "0201"       # 順序あり → 着順保持
    assert kumiban((14, 6, 4), ordered=False) == "040614"
    assert kumiban((6, 14, 4), ordered=True) == "061404"


def test_make_odds_lookup():
    all_odds = {
        "tansho": {5: {"odds": 4.2, "ninki": 2}},
        "fukusho": {5: {"odds_low": 1.5, "odds_high": 1.9}},
        "umaren": {"0305": {"odds": 12.0}},
        "wide": {"0305": {"odds": 5.5, "odds_low": 5.5, "odds_high": 6.8}},
        "umatan": {"0503": {"odds": 21.0}},
        "sanrenpuku": {"030508": {"odds": 45.0}},
        "sanrentan": {"050308": {"odds": 230.0}},
    }
    of = make_odds_lookup(all_odds)
    assert of(_t("tansho", [5])) == 4.2
    assert of(_t("fukusho", [5])) == 1.5                  # odds_low 採用
    assert of(_t("umaren", [5, 3])) == 12.0               # 順不同 → '0305'
    assert of(_t("wide", [3, 5])) == 5.5
    assert of(_t("umatan", [5, 3])) == 21.0               # 順序 → '0503'
    assert of(_t("umatan", [3, 5])) is None               # 逆順は別組番
    assert of(_t("sanrenpuku", [8, 5, 3])) == 45.0        # ソートして '030508'
    assert of(_t("sanrentan", [5, 3, 8])) == 230.0
    assert of(_t("tansho", [9])) is None                  # 欠落
    assert of(_t("umaren", [1, 2])) is None


# ---------------------------------------------------------------------------
# analyze_plan: 合成オッズ G
# ---------------------------------------------------------------------------

def test_g_two_even_points():
    # o=2,2 → G = 1/(0.5+0.5) = 1.0 (全部買うと必ずトントン以下の形)
    tks = [_t("tansho", [1]), _t("tansho", [2])]
    of = _odds_map({("tansho", (1,)): 2.0, ("tansho", (2,)): 2.0})
    pa = analyze_plan(tks, of)
    assert pa.g == pytest.approx(1.0)
    assert pa.coverage == 1.0


def test_g_mixed_odds():
    # o=10,5 → G = 1/(0.1+0.2) = 3.333…
    tks = [_t("tansho", [1]), _t("tansho", [2])]
    of = _odds_map({("tansho", (1,)): 10.0, ("tansho", (2,)): 5.0})
    pa = analyze_plan(tks, of)
    assert pa.g == pytest.approx(10.0 / 3.0)


def test_g_missing_odds_coverage():
    tks = [_t("tansho", [1]), _t("tansho", [2])]
    of = _odds_map({("tansho", (1,)): 4.0})   # 2 はオッズ無し
    pa = analyze_plan(tks, of)
    assert pa.g == pytest.approx(4.0)          # 取れた点のみで計算
    assert pa.coverage == pytest.approx(0.5)
    assert pa.views[1].hit_return is None      # 情報なし点は判定対象外
    of_none = _odds_map({})
    pa2 = analyze_plan(tks, of_none)
    assert pa2.g is None and pa2.coverage == 0.0


# ---------------------------------------------------------------------------
# analyze_plan: weight 配分の hit_return
# ---------------------------------------------------------------------------

def test_hit_return_with_weight():
    # 単勝 w=1.0 o=5.0 (stake100) + 三連単 6点 w=0.25 o=100 (stake各25 → 150)
    # total=250。単勝だけ的中: 5.0*100/250 = 2.0 / 三連単1点的中: 100*25/250 = 10.0
    tks = [_t("tansho", [1], ROLE_INSURANCE, 1.0)]
    m = {("tansho", (1,)): 5.0}
    for i, perm in enumerate([(1, 2, 3), (1, 3, 2), (2, 1, 3), (2, 3, 1), (3, 1, 2), (3, 2, 1)]):
        tks.append(_t("sanrentan", perm, ROLE_BONUS, 0.25))
        m[("sanrentan", perm)] = 100.0
    pa = analyze_plan(tks, _odds_map(m))
    assert pa.total_stake == pytest.approx(250.0)
    assert pa.views[0].hit_return == pytest.approx(2.0)
    assert pa.views[1].hit_return == pytest.approx(10.0)
    assert not pa.has_torigami


def test_torigami_fukuda_example():
    # ふくだの例: 三連複 ◎○▲ 1点が合成2.0倍しかない + 三連単6点(o=30) flat。
    # total=700。三連複だけ的中: 2.0*100/700 = 0.286 → 当たったのに損 = トリガミ。
    tks = [_t("sanrenpuku", (1, 2, 3), ROLE_INSURANCE, 1.0)]
    m = {("sanrenpuku", (1, 2, 3)): 2.0}
    for perm in [(1, 2, 3), (1, 3, 2), (2, 1, 3), (2, 3, 1), (3, 1, 2), (3, 2, 1)]:
        tks.append(_t("sanrentan", perm, ROLE_BONUS, 1.0))
        m[("sanrentan", perm)] = 30.0
    pa = analyze_plan(tks, _odds_map(m))
    assert pa.has_torigami
    assert len(pa.torigami) == 1
    assert pa.torigami[0].ticket.bet_type == "sanrenpuku"
    assert pa.worst_hit_return == pytest.approx(2.0 * 100 / 700)
    # 三連単側は 30*100/700 = 4.29 で生きている
    assert pa.best_hit_return == pytest.approx(30.0 * 100 / 700)


# ---------------------------------------------------------------------------
# prune_to_floor
# ---------------------------------------------------------------------------

def test_prune_drops_low_odds_first():
    # o=[1.5, 10, 20] → G=1/(0.667+0.1+0.05)=1.224。floor=3.0 → 1.5 を削って
    # G=1/(0.15)=6.67 で到達。
    tks = [_t("wide", [1, 2]), _t("umaren", [1, 3]), _t("umaren", [1, 4])]
    of = _odds_map({("wide", (1, 2)): 1.5, ("umaren", (1, 3)): 10.0, ("umaren", (1, 4)): 20.0})
    r = prune_to_floor(tks, of, 3.0)
    assert [tk.bet_type for tk in r.dropped] == ["wide"]
    assert len(r.kept) == 2
    assert r.g_before == pytest.approx(1.0 / (1 / 1.5 + 0.1 + 0.05))
    assert r.g_after == pytest.approx(1.0 / 0.15)
    assert r.reached_floor


def test_prune_respects_protect_roles():
    # 保険 (低オッズ) を protect すると削れず floor 不達 → 「降りる」判断材料。
    tks = [_t("wide", [1, 2], ROLE_INSURANCE), _t("umaren", [1, 3])]
    of = _odds_map({("wide", (1, 2)): 1.5, ("umaren", (1, 3)): 10.0})
    r = prune_to_floor(tks, of, 5.0, protect_roles=(ROLE_INSURANCE,))
    assert r.dropped == []
    assert not r.reached_floor


def test_prune_unreachable_floor():
    # 全部削っても届かない (削り尽くすと G=None) → reached_floor False。
    tks = [_t("tansho", [1]), _t("tansho", [2])]
    of = _odds_map({("tansho", (1,)): 1.2, ("tansho", (2,)): 1.3})
    r = prune_to_floor(tks, of, 100.0)
    assert not r.reached_floor


def test_prune_max_drop():
    # max_drop 内で届けば採用、足りなければロールバック (中途半端に削らない)。
    tks = [_t("tansho", [1]), _t("tansho", [2]), _t("tansho", [3])]
    of = _odds_map({("tansho", (1,)): 1.1, ("tansho", (2,)): 5.0, ("tansho", (3,)): 30.0})
    r = prune_to_floor(tks, of, 4.0, max_drop=1)      # 1.1 を削れば G=4.29 で到達
    assert [tk.horses for tk in r.dropped] == [(1,)]  # 最低オッズから削る
    assert r.reached_floor
    r2 = prune_to_floor(tks, of, 6.0, max_drop=1)     # 2点削らないと届かない
    assert r2.dropped == [] and not r2.reached_floor


def test_prune_keeps_unknown_odds():
    # オッズ None の点は削減対象にしない (情報なしで切らない)。
    tks = [_t("tansho", [1]), _t("umaren", [1, 9])]
    of = _odds_map({("tansho", (1,)): 1.5})
    r = prune_to_floor(tks, of, 2.0)
    assert all(tk.bet_type != "umaren" for tk in r.dropped)
    # tansho を削れば G=None (funded ゼロ) のまま floor 不達
    assert not r.reached_floor
