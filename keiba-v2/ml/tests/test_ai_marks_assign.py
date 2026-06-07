# -*- coding: utf-8 -*-
"""assign_ai_marks 純関数のユニットテスト (設計 SC-2)。

docs/auto-purchase/22_AI_MARKS_DESIGN.md §5 SC-2 の完了条件を網羅。
"""

import pytest

from ml.ai_marks.assign import (
    assign_ai_marks,
    MARK_LADDER,
    ANA_MIN_ODDS,
    ANA_BREAK,
)


def _horse(umaban, w, p, ard, rank_w=None, win_ev=None, odds=None):
    return {
        "umaban": umaban,
        "pred_proba_w_cal": w,
        "pred_proba_p": p,
        "ar_deviation": ard,
        "rank_w": rank_w if rank_w is not None else umaban,
        "win_ev": win_ev,
        "odds": odds,
    }


def test_strongest_horse_gets_honmei():
    """W/P/ADR が一致して最強の馬が ◎ になる (符号バグ無し)。"""
    entries = [
        _horse(1, 0.10, 0.20, 50.0),
        _horse(2, 0.40, 0.55, 65.0),  # 全指標で最強
        _horse(3, 0.08, 0.15, 45.0),
        _horse(4, 0.05, 0.10, 40.0),
    ]
    r = assign_ai_marks(entries)
    assert not r.skipped
    assert r.marks == {2: "◎"}
    # composite も 2番が最大
    assert r.composite[2] == max(r.composite.values())


def test_too_few_runners_skips():
    """出走 2頭 → 撃ちなし。"""
    entries = [_horse(1, 0.5, 0.6, 60.0), _horse(2, 0.3, 0.4, 55.0)]
    r = assign_ai_marks(entries)
    assert r.skipped
    assert r.skip_reason == "too_few_runners"
    assert r.marks == {}


def test_adr_all_null_degrades_to_wp():
    """ADR 全頭 null (京都4R型) → ADR成分除外 + notes記録、W/Pで◎決定。"""
    entries = [
        _horse(1, 0.10, 0.20, None),
        _horse(2, 0.45, 0.50, None),  # W/P最強
        _horse(3, 0.08, 0.12, None),
        _horse(4, 0.05, 0.08, None),
    ]
    r = assign_ai_marks(entries)
    assert not r.skipped
    assert r.adr_used is False
    assert any("ADR全欠損" in n for n in r.notes)
    assert r.marks == {2: "◎"}


def test_flat_distribution_skips():
    """全頭同スコア → 撃ちなし (無作為◎を出さない)。"""
    entries = [_horse(i, 0.10, 0.10, 50.0) for i in range(1, 9)]
    r = assign_ai_marks(entries)
    assert r.skipped
    assert r.skip_reason == "flat_distribution"
    assert r.marks == {}


def test_weights_change_composite():
    """weights=(0.5,2,0.5) と (1,1,1) で composite が変わる。"""
    entries = [
        _horse(1, 0.40, 0.10, 50.0),  # W強・P弱
        _horse(2, 0.10, 0.50, 55.0),  # W弱・P強
        _horse(3, 0.08, 0.12, 45.0),
        _horse(4, 0.05, 0.08, 40.0),
    ]
    r_equal = assign_ai_marks(entries, weights=(1.0, 1.0, 1.0))
    r_pheavy = assign_ai_marks(entries, weights=(0.5, 2.0, 0.5))
    # P寄せにすると 2番(P強)の composite が等重みより相対的に上がる
    assert r_pheavy.composite[2] != r_equal.composite[2]
    # P寄せでは P強の2番が◎になる
    assert r_pheavy.marks == {2: "◎"}


def test_adr_partial_missing_median_fill():
    """ADR 一部欠損 → median 補完 + notes、ADR は活用。"""
    entries = [
        _horse(1, 0.10, 0.20, 50.0),
        _horse(2, 0.40, 0.50, None),  # ADR欠損だが W/P最強
        _horse(3, 0.08, 0.12, 48.0),
        _horse(4, 0.05, 0.08, 46.0),
    ]
    r = assign_ai_marks(entries)
    assert not r.skipped
    assert r.adr_used is True
    assert any("ADR一部欠損" in n for n in r.notes)


def test_composite_tiebreak_rank_w():
    """composite 同点は rank_w 昇順で決定的。"""
    # 1番と2番が同スコアだが rank_w が 1番=1, 2番=2
    entries = [
        _horse(1, 0.30, 0.40, 55.0, rank_w=1),
        _horse(2, 0.30, 0.40, 55.0, rank_w=2),
        _horse(3, 0.05, 0.08, 40.0),
        _horse(4, 0.04, 0.06, 38.0),
    ]
    r = assign_ai_marks(entries)
    assert not r.skipped
    # 同点なら rank_w=1 の 1番が◎
    assert r.marks == {1: "◎"}


def test_only_one_mark_in_step1():
    """Step1 では ◎ 1頭のみ (○▲△ を書かない)。"""
    entries = [_horse(i, 0.5 - i * 0.05, 0.6 - i * 0.05, 60.0 - i) for i in range(1, 11)]
    r = assign_ai_marks(entries)
    assert not r.skipped
    assert len(r.marks) == 1
    assert set(r.marks.values()) == {"◎"}


# ---------------------------------------------------------------------------
# Step2: 序列=composite総合 / 頭数=複勝率(P)の崖 + 穴 (別系統)
# ---------------------------------------------------------------------------

def test_step2_smooth_no_cliff_fills_to_cap():
    """なだらかに続く分布 (崖なし) → cap (頭数-1, 上限5) まで ◎○▲△Ⅲ。"""
    # 複勝率(P)が僅差で続く = 崖が来ない。6頭立て → cap=min(5,5)=5。
    entries = [
        _horse(1, 0.30, 0.24, 60.0),
        _horse(2, 0.28, 0.22, 59.0),
        _horse(3, 0.26, 0.20, 58.0),
        _horse(4, 0.24, 0.18, 57.0),
        _horse(5, 0.22, 0.16, 56.0),
        _horse(6, 0.20, 0.14, 55.0),
    ]
    r = assign_ai_marks(entries, step=2)
    assert not r.skipped
    assert r.marks[1] == "◎"
    ordered = sorted(r.marks.items(), key=lambda kv: -r.composite[kv[0]])
    syms = [sym for _u, sym in ordered]
    assert syms == list(MARK_LADDER)  # 崖なし → 上限5頭フル
    assert len(r.marks) == 5


def test_step2_cliff_truncates_at_gap():
    """複勝率に崖 (比 >= CLIFF_RATIO) があれば、その手前で打ち切り。"""
    # ◎が複勝率でも抜けてる: P 0.50 → 0.10 (比 5.0) で崖 → ◎単独。
    entries = [
        _horse(1, 0.70, 0.50, 75.0),  # 圧倒的 (P0.50)
        _horse(2, 0.10, 0.10, 50.0),  # 0.50/0.10 = 5.0 で崖
        _horse(3, 0.09, 0.09, 49.0),
        _horse(4, 0.08, 0.08, 48.0),
        _horse(5, 0.07, 0.07, 47.0),
    ]
    r = assign_ai_marks(entries, step=2)
    assert not r.skipped
    assert r.marks[1] == "◎"
    assert len(r.marks) == 1  # 崖で◎単独
    assert any("崖" in n for n in r.notes)


def test_step2_fukuda_case_smooth():
    """ふくだ例1: なだらか (20,20,10,8,8,8,8,1,1) → 8%まで続き上限5頭。"""
    ps = [0.20, 0.20, 0.10, 0.08, 0.08, 0.08, 0.08, 0.01, 0.01]
    entries = [_horse(i + 1, ps[i], ps[i], 60.0 - i, rank_w=i + 1) for i in range(len(ps))]
    r = assign_ai_marks(entries, step=2)
    assert len(r.marks) == 5  # 8%が続く → 崖(8→1)より先に上限5で止まる


def test_step2_fukuda_case_cliff():
    """ふくだ例2: 崖 (30,30,30,1,1,1,1,1) → 30%の3頭で打ち切り。"""
    ps = [0.30, 0.30, 0.30, 0.01, 0.01, 0.01, 0.01, 0.01]
    entries = [_horse(i + 1, ps[i], ps[i], 60.0 - i, rank_w=i + 1) for i in range(len(ps))]
    r = assign_ai_marks(entries, step=2)
    assert len(r.marks) == 3  # 0.30/0.01 = 30 で崖
    assert set(r.marks.keys()) == {1, 2, 3}


def test_step2_cap_prevents_all_marked_small_field():
    """少頭数で崖が来なくても全頭印にしない (cap = 頭数-1)。"""
    # 4頭が僅差 (崖なし) → cap=min(5,3)=3。4頭目に印が付かない。
    entries = [
        _horse(1, 0.28, 0.27, 60.0),
        _horse(2, 0.26, 0.25, 59.0),
        _horse(3, 0.24, 0.23, 58.0),
        _horse(4, 0.22, 0.21, 57.0),
    ]
    r = assign_ai_marks(entries, step=2)
    assert len(r.marks) == 3  # 全頭(4)にはしない
    assert 4 not in r.marks


def test_step2_ana_disabled_by_default():
    """enable_ana=False (既定) では穴を付けない。"""
    entries = [
        _horse(1, 0.45, 0.30, 65.0, win_ev=0.8, odds=2.0),
        _horse(2, 0.35, 0.25, 60.0, win_ev=0.9, odds=3.0),
        _horse(3, 0.06, 0.08, 48.0, win_ev=8.0, odds=20.0),  # 妙味だが穴OFF
        _horse(4, 0.05, 0.07, 46.0, win_ev=0.5, odds=50.0),
        _horse(5, 0.04, 0.06, 44.0, win_ev=0.4, odds=40.0),
        _horse(6, 0.03, 0.05, 42.0, win_ev=0.3, odds=30.0),
    ]
    r = assign_ai_marks(entries, step=2, enable_ana=False)
    assert "穴" not in r.marks.values()


def test_step2_ana_marks_standout_value_horse():
    """enable_ana=True: 崖の外で win_ev が突出した高オッズ馬に穴。"""
    entries = [
        _horse(1, 0.45, 0.30, 70.0, win_ev=0.9, odds=2.0),    # ◎
        _horse(2, 0.35, 0.25, 62.0, win_ev=0.8, odds=3.0),    # ○ (崖の内側)
        _horse(3, 0.06, 0.08, 48.0, win_ev=8.0, odds=ANA_MIN_ODDS + 10),  # 崖の外・妙味突出
        _horse(4, 0.05, 0.07, 46.0, win_ev=0.5, odds=ANA_MIN_ODDS + 40),  # 崖の外・win_ev小
        _horse(5, 0.04, 0.06, 44.0, win_ev=0.4, odds=ANA_MIN_ODDS + 30),
        _horse(6, 0.03, 0.05, 42.0, win_ev=0.3, odds=ANA_MIN_ODDS + 20),
    ]
    r = assign_ai_marks(entries, step=2, enable_ana=True)
    assert r.marks.get(3) == "穴"   # 崖の外 & win_ev 突出
    assert r.marks[1] == "◎"
    assert r.marks.get(1) != "穴" and r.marks.get(2) != "穴"  # 序列印は穴で上書きしない


def test_step2_ana_skips_when_not_standout():
    """崖の外の妙味馬が団子 (突出しない) なら穴なし (乱発防止)。"""
    entries = [
        _horse(1, 0.45, 0.30, 70.0, win_ev=0.9, odds=2.0),  # ◎
        _horse(2, 0.35, 0.25, 60.0, win_ev=0.8, odds=3.0),  # ○
        _horse(3, 0.06, 0.08, 48.0, win_ev=3.0, odds=ANA_MIN_ODDS + 10),
        _horse(4, 0.05, 0.07, 47.0, win_ev=3.0 - (ANA_BREAK * 0.5), odds=ANA_MIN_ODDS + 20),
        _horse(5, 0.04, 0.06, 44.0, win_ev=0.4, odds=ANA_MIN_ODDS + 5),
    ]
    r = assign_ai_marks(entries, step=2, enable_ana=True)
    assert "穴" not in r.marks.values()
    assert any("突出せず" in n for n in r.notes)


def test_step2_ana_skips_popular_horse():
    """odds が低い (人気) 馬は win_ev が高くても穴にしない (低人気=妙味の前提)。"""
    entries = [
        _horse(1, 0.45, 0.30, 70.0, win_ev=0.9, odds=2.0),
        _horse(2, 0.35, 0.25, 60.0, win_ev=0.8, odds=3.0),
        _horse(3, 0.06, 0.08, 50.0, win_ev=8.0, odds=ANA_MIN_ODDS - 2.0),  # win_ev高だが人気
        _horse(4, 0.05, 0.07, 46.0, win_ev=0.5, odds=ANA_MIN_ODDS + 10),
        _horse(5, 0.04, 0.06, 44.0, win_ev=0.4, odds=ANA_MIN_ODDS + 5),
    ]
    r = assign_ai_marks(entries, step=2, enable_ana=True)
    assert "穴" not in r.marks.values()
