# -*- coding: utf-8 -*-
"""bet_templates 展開エンジンの単体テスト (Phase1 / Session 146)"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.strategies.bet_templates import (
    BetComponent, Template, Ticket, apply_template, count_points,
    expand_component, marks_from_ranking, get_template, TEMPLATES,
)

MARKS = {"◎": [1], "○": [2], "▲": [3], "△": [4], "Ⅲ": [5]}


def _bt(tickets):
    return sorted((tk.bet_type, tk.horses) for tk in tickets)


def test_tansho_single():
    c = BetComponent("tansho", [["◎"]])
    assert _bt(expand_component(c, MARKS)) == [("tansho", (1,))]


def test_umaren_nagashi_2points():
    # 馬連 ◎-○▲ = 1-2, 1-3 の2点 (昇順・順不同)
    c = BetComponent("umaren", [["◎"], ["○", "▲"]])
    assert _bt(expand_component(c, MARKS)) == [("umaren", (1, 2)), ("umaren", (1, 3))]


def test_umatan_ordered_atama_fixed():
    # 馬単 ◎→○▲ = 1→2, 1→3 (順序保持・アタマ固定)
    c = BetComponent("umatan", [["◎"], ["○", "▲"]])
    res = _bt(expand_component(c, MARKS))
    assert res == [("umatan", (1, 2)), ("umatan", (1, 3))]
    # 逆順 (2→1) は含まれない
    assert ("umatan", (2, 1)) not in res


def test_sanrenpuku_formation_dedup():
    # 三連複 ◎-○▲-○▲△  (△=[4] 単独・◎○▲△Ⅲ 語彙)
    # ◎=1固定, col2={2,3}, col3={2,3,4} → 3頭全異・集合重複排除
    c = BetComponent("sanrenpuku", [["◎"], ["○", "▲"], ["○", "▲", "△"]])
    res = set(tk.horses for tk in expand_component(c, MARKS))
    assert res == {(1, 2, 3), (1, 2, 4), (1, 3, 4)}


def test_sanrentan_atama_fixed_ordered():
    # 三連単 ◎→○▲→○▲△ アタマ固定、順序保持、同一馬除外
    c = BetComponent("sanrentan", [["◎"], ["○", "▲"], ["○", "▲", "△"]])
    res = set(tk.horses for tk in expand_component(c, MARKS))
    # 1→2→{3,4}, 1→3→{2,4}
    assert res == {(1, 2, 3), (1, 2, 4), (1, 3, 2), (1, 3, 4)}
    assert len(res) == 4


def test_empty_when_mark_missing():
    # markset に無い印を含む列は買えない (空)
    c = BetComponent("umaren", [["◎"], ["XX"]])
    assert expand_component(c, MARKS) == []


def test_no_same_horse_in_combo():
    # ◎と○が同じ馬番なら同一馬の組は生成されない
    marks = {"◎": [1], "○": [1, 2]}
    c = BetComponent("umaren", [["◎"], ["○"]])
    res = set(tk.horses for tk in expand_component(c, marks))
    assert res == {(1, 2)}  # 1-1 は除外


def test_marks_from_ranking():
    # 上位5頭に ◎○▲△Ⅲ を1頭ずつ (AI印 markSet=2 と同語彙)
    m = marks_from_ranking([7, 3, 9, 4, 1, 6])
    assert m["◎"] == [7] and m["○"] == [3] and m["▲"] == [9]
    assert m["△"] == [4] and m["Ⅲ"] == [1]


def test_marks_from_ranking_top5_only():
    # 6位以降は無印 (印の付いた馬しか買わない)
    m = marks_from_ranking([7, 3, 9, 4, 1, 6, 8])
    assert set(m.keys()) == {"◎", "○", "▲", "△", "Ⅲ"}
    assert 6 not in sum(m.values(), []) and 8 not in sum(m.values(), [])


def test_template_honmei_hoken_points():
    # 単◎(1) + 馬連◎-○▲(2) = 3点、役割が保険/本線
    tickets = apply_template(get_template("honmei_hoken"), MARKS)
    assert count_points(get_template("honmei_hoken"), MARKS) == 3
    roles = {tk.bet_type: tk.role for tk in tickets}
    assert roles["tansho"] == "保険" and roles["umaren"] == "本線"
    assert all(tk.template == "honmei_hoken" for tk in tickets)


def test_all_templates_expand_nonempty():
    # 代表テンプレが全て買い目を生成できる (印が揃っていれば)
    for name in TEMPLATES:
        n = count_points(get_template(name), MARKS)
        assert n > 0, f"{name} produced 0 tickets"


def test_ringfenced_flag():
    assert get_template("sanrentan_roman").ringfenced is True
    assert get_template("honmei_hoken").ringfenced is False
