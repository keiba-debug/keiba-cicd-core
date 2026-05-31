# -*- coding: utf-8 -*-
"""assign_ai_marks 純関数のユニットテスト (設計 SC-2)。

docs/auto-purchase/22_AI_MARKS_DESIGN.md §5 SC-2 の完了条件を網羅。
"""

import pytest

from ml.ai_marks.assign import (
    assign_ai_marks,
    FLAT_EPS,
    BREAK_GAP,
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
# Step2: 段差ベース ○▲△Ⅲ 割当 + 穴 (別系統)
# ---------------------------------------------------------------------------

def test_step2_smooth_distribution_assigns_ladder():
    """僅差で連続する分布 → ◎○▲△Ⅲ が順に付く (打ち切られない)。"""
    # composite が滑らかに下がる = 隣接段差が BREAK_GAP 未満で続く想定。
    # W/P/ADR を僅差で並べる (median/MAD で z 化されても段差は小さく保たれる)。
    entries = [
        _horse(1, 0.30, 0.50, 60.0),
        _horse(2, 0.28, 0.48, 59.0),
        _horse(3, 0.26, 0.46, 58.0),
        _horse(4, 0.24, 0.44, 57.0),
        _horse(5, 0.22, 0.42, 56.0),
        _horse(6, 0.20, 0.40, 55.0),
    ]
    r = assign_ai_marks(entries, step=2)
    assert not r.skipped
    # ◎ は composite 最高 (= 1番)
    assert r.marks[1] == "◎"
    # 序列は composite 降順に MARK_LADDER 順
    ordered = sorted(r.marks.items(), key=lambda kv: -r.composite[kv[0]])
    syms = [sym for _u, sym in ordered]
    assert syms == list(MARK_LADDER[: len(syms)])
    # 序列印は最大 5 (◎○▲△Ⅲ)
    assert len(r.marks) <= len(MARK_LADDER)


def test_step2_break_gap_truncates():
    """1強 (◎が突出) → 段差で打ち切られ ◎単独 (or 少数) に絞られる。"""
    # 1番だけ圧倒的、残りは団子。1番→2番の段差が BREAK_GAP 以上開く想定。
    entries = [
        _horse(1, 0.70, 0.80, 75.0),  # 圧倒的
        _horse(2, 0.08, 0.15, 50.0),
        _horse(3, 0.07, 0.14, 49.0),
        _horse(4, 0.06, 0.13, 48.0),
        _horse(5, 0.05, 0.12, 47.0),
    ]
    r = assign_ai_marks(entries, step=2)
    assert not r.skipped
    assert r.marks[1] == "◎"
    # ◎の次との段差が大きいので打ち切られ、◎単独になる
    assert len(r.marks) == 1
    assert any("打ち切り" in n for n in r.notes)


def test_step2_break_gap_value_threshold():
    """BREAK_GAP の閾値が割当頭数を支配することの確認 (回帰防止)。"""
    entries = [
        _horse(1, 0.40, 0.55, 65.0),
        _horse(2, 0.20, 0.40, 58.0),
        _horse(3, 0.10, 0.20, 52.0),
    ]
    r = assign_ai_marks(entries, step=2)
    ordered = sorted(r.marks.items(), key=lambda kv: -r.composite[kv[0]])
    # 隣接段差が BREAK_GAP 未満の区間だけ印が続いていること
    prev = None
    for u, _sym in ordered:
        if prev is not None:
            assert r.composite[prev] - r.composite[u] < BREAK_GAP
        prev = u


def test_step2_ana_disabled_by_default():
    """enable_ana=False (既定) では穴を付けない。"""
    entries = [
        _horse(1, 0.40, 0.55, 65.0, win_ev=0.8, odds=2.0),
        _horse(2, 0.30, 0.45, 60.0, win_ev=0.9, odds=3.0),
        _horse(3, 0.05, 0.10, 48.0, win_ev=8.0, odds=20.0),  # 妙味だが穴OFF
        _horse(4, 0.04, 0.08, 46.0, win_ev=0.5, odds=50.0),
    ]
    r = assign_ai_marks(entries, step=2, enable_ana=False)
    assert "穴" not in r.marks.values()


def test_step2_ana_marks_standout_value_horse():
    """enable_ana=True: 序列印外で win_ev が突出した高オッズ馬に穴が付く。"""
    entries = [
        _horse(1, 0.45, 0.55, 70.0, win_ev=0.9, odds=2.0),   # ◎ (序列印)
        _horse(2, 0.30, 0.45, 60.0, win_ev=0.8, odds=3.0),
        _horse(3, 0.10, 0.15, 50.0, win_ev=8.0, odds=ANA_MIN_ODDS + 10),  # 妙味が突出
        _horse(4, 0.04, 0.08, 46.0, win_ev=0.5, odds=ANA_MIN_ODDS + 40),  # 高オッズだが win_ev 小
    ]
    r = assign_ai_marks(entries, step=2, enable_ana=True)
    # 3番が穴 (序列印外 & win_ev が他の高オッズ馬より突出 = 妙味が1頭に集中)
    assert r.marks.get(3) == "穴"
    # ◎は実力馬 (確率で序列を決め、穴は別系統 = Themis 整合)
    assert r.marks[1] == "◎"


def test_step2_ana_skips_when_not_standout():
    """高オッズ妙味馬が団子 (突出しない) なら穴を付けない (乱発防止)。"""
    entries = [
        _horse(1, 0.45, 0.55, 70.0, win_ev=0.9, odds=2.0),  # ◎
        _horse(2, 0.30, 0.45, 60.0, win_ev=0.8, odds=3.0),
        # 高オッズ馬が2頭、win_ev が僅差 (突出していない) → 穴なし
        _horse(3, 0.08, 0.12, 48.0, win_ev=3.0, odds=ANA_MIN_ODDS + 10),
        _horse(4, 0.07, 0.11, 47.0, win_ev=3.0 - (ANA_BREAK * 0.5), odds=ANA_MIN_ODDS + 20),
    ]
    r = assign_ai_marks(entries, step=2, enable_ana=True)
    assert "穴" not in r.marks.values()
    assert any("突出せず" in n for n in r.notes)


def test_step2_ana_skips_popular_horse():
    """odds が低い (人気) 馬は win_ev が高くても穴にしない (低人気=妙味の前提)。"""
    entries = [
        _horse(1, 0.45, 0.55, 70.0, win_ev=0.9, odds=2.0),
        _horse(2, 0.30, 0.45, 60.0, win_ev=0.8, odds=3.0),
        # win_ev は高いが odds < ANA_MIN_ODDS = 人気馬 → 穴候補にしない
        _horse(3, 0.10, 0.15, 50.0, win_ev=8.0, odds=ANA_MIN_ODDS - 2.0),
    ]
    r = assign_ai_marks(entries, step=2, enable_ana=True)
    assert "穴" not in r.marks.values()


def test_step2_ana_not_on_ranked_horse():
    """既に序列印が付いた馬には穴を二重付与しない。"""
    # 全馬が僅差 → ◎○▲△ が並ぶ。win_ev が高い馬も既に序列印なので穴対象外。
    entries = [
        _horse(1, 0.26, 0.46, 58.0, win_ev=1.0, odds=4.0),
        _horse(2, 0.25, 0.45, 57.5, win_ev=1.1, odds=5.0),
        _horse(3, 0.24, 0.44, 57.0, win_ev=8.0, odds=ANA_MIN_ODDS + 5),
        _horse(4, 0.23, 0.43, 56.5, win_ev=0.9, odds=4.0),
    ]
    r = assign_ai_marks(entries, step=2, enable_ana=True)
    # 各馬は ◎○▲△ のいずれか (穴で上書きされていない)
    for u, sym in r.marks.items():
        assert sym in MARK_LADDER  # 穴ではない
