# -*- coding: utf-8 -*-
"""役割分化 (role_split + bet_templates no_head) のテスト (Session 148)

ふくだの捨て馬券例「○の頭はない → 三連単 ◎▲→◎○▲→◎○▲」がそのまま代表ケース。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.strategies.bet_templates import (
    BetComponent, apply_template, expand_component, get_template,
)
from ml.strategies.role_split import detect_no_head, win_share

MARKS = {"◎": [5], "○": [3], "▲": [8], "△": [1], "Ⅲ": [2]}


# ---------------------------------------------------------------------------
# detect_no_head / win_share
# ---------------------------------------------------------------------------

def test_win_share():
    assert win_share(0.2, 0.4) == 0.5
    assert win_share(None, 0.4) is None
    assert win_share(0.2, None) is None
    assert win_share(0.2, 0.0) is None


def test_detect_no_head_basic():
    # share: ◎=1.0, ○=0.3, ▲=0.9 → median 0.9, 閾値 0.54 → ○だけ P型
    horses = [(5, 0.30, 0.30), (3, 0.06, 0.20), (8, 0.18, 0.20)]
    assert detect_no_head(horses) == [3]


def test_detect_no_head_none_when_all_similar():
    horses = [(5, 0.30, 0.30), (3, 0.25, 0.28), (8, 0.18, 0.20)]
    assert detect_no_head(horses) == []


def test_detect_no_head_missing_data():
    # 欠損馬は P型にしない / 有効2頭未満は判定しない
    horses = [(5, 0.30, 0.30), (3, None, 0.20), (8, 0.18, 0.20)]
    assert 3 not in detect_no_head(horses)
    assert detect_no_head([(5, 0.3, 0.3), (3, None, None)]) == []


# ---------------------------------------------------------------------------
# bet_templates no_head (1列目除外)
# ---------------------------------------------------------------------------

def test_sanrentan_box_no_head_fukuda_example():
    # 三連単 ◎○▲ BOX 6点 → ○(3) を頭から外すと ◎▲→◎○▲→◎○▲ の4点
    box = BetComponent("sanrentan", [["◎", "○", "▲"]] * 3)
    base = expand_component(box, MARKS)
    assert len(base) == 6
    split = expand_component(box, MARKS, no_head=[3])
    assert len(split) == 4
    assert all(tk.horses[0] != 3 for tk in split)          # ○は1着に置かない
    assert any(3 in tk.horses for tk in split)             # 2-3着には残る


def test_umatan_no_head():
    c = BetComponent("umatan", [["◎", "○"], ["◎", "○", "▲"]])
    base = expand_component(c, MARKS)
    split = expand_component(c, MARKS, no_head=[3])
    assert all(tk.horses[0] != 3 for tk in split)
    assert len(split) < len(base)


def test_unordered_not_affected():
    # 順不同系 (三連複/馬連/ワイド) と単複は no_head の影響を受けない
    puku = BetComponent("sanrenpuku", [["◎"], ["○", "▲", "△", "Ⅲ"], ["○", "▲", "△", "Ⅲ"]])
    assert len(expand_component(puku, MARKS, no_head=[3])) == \
        len(expand_component(puku, MARKS))
    tan = BetComponent("tansho", [["◎"]])
    assert len(expand_component(tan, MARKS, no_head=[5])) == 1


def test_no_head_empties_first_column():
    # 1列目が空になれば component 不成立
    c = BetComponent("sanrentan", [["◎"], ["○", "▲"], ["○", "▲", "△"]])
    assert expand_component(c, MARKS, no_head=[5]) == []


def test_apply_template_no_head_honmei_formation():
    # honmei_formation: 三連複6点は不変 + 三連単BOX 6→4点 = 計10点
    t = get_template("honmei_formation")
    base = apply_template(t, MARKS)
    split = apply_template(t, MARKS, no_head=[3])
    assert len(base) == 12
    assert len(split) == 10
    srt_first = {tk.horses[0] for tk in split if tk.bet_type == "sanrentan"}
    assert 3 not in srt_first
    n_puku = sum(1 for tk in split if tk.bet_type == "sanrenpuku")
    assert n_puku == 6
