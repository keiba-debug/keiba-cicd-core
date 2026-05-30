# -*- coding: utf-8 -*-
"""build_vote_starting_text のテスト (Session 135 / 投票開始 音声予告)"""
from ml.target_clicker.notify import build_vote_starting_text


def test_single_tansho():
    t = build_vote_starting_text(
        [{"bet_type": "tansho", "umaban": "4", "amount": 500, "race_number": 4}], 500)
    assert "自動投票を開始します" in t
    assert "単勝" in t and "4" in t and "500円" in t
    assert "4レース" in t


def test_single_umatan_combo():
    t = build_vote_starting_text(
        [{"bet_type": "umatan", "umaban": "13/17", "amount": 100, "race_number": 4}], 100)
    assert "馬単" in t and "13/17" in t and "100円" in t


def test_multiple_summarized():
    t = build_vote_starting_text([
        {"bet_type": "tansho", "umaban": "4", "amount": 500},
        {"bet_type": "tansho", "umaban": "7", "amount": 300},
    ], 800)
    assert "2 件" in t
    assert "800円" in t


def test_unknown_bet_type_falls_back():
    # 未知 bet_type はそのまま表示 (落ちない)
    t = build_vote_starting_text(
        [{"bet_type": "xyz", "umaban": "1", "amount": 100, "race_number": 1}], 100)
    assert "自動投票を開始します" in t
    assert "xyz" in t


def test_no_race_number_ok():
    t = build_vote_starting_text(
        [{"bet_type": "tansho", "umaban": "4", "amount": 500}], 500)
    assert "単勝" in t  # race_number 無くても落ちない
    assert "レース" not in t.split("。")[1]  # 冒頭にレース番号を入れない
