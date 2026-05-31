# -*- coding: utf-8 -*-
"""AI印 DAT writer の round-trip テスト (設計 SC-3)。

一時 JV_DATA_ROOT に markSet=6 で書込み → load_my_marks(mark_set=6) で読み戻す。
mark_set=1 への書込みは拒否されること、byte offset が TS と等価なことを検証。
"""

import importlib

import pytest

from ml.ai_marks import dat_writer


@pytest.fixture
def jv_root(tmp_path, monkeypatch):
    """一時 JV_DATA_ROOT を差し、my_marks を読み直す。"""
    monkeypatch.setenv("JV_DATA_ROOT", str(tmp_path))
    import ml.features.my_marks as mm
    importlib.reload(mm)
    importlib.reload(dat_writer)
    return tmp_path, mm


def test_roundtrip_honmei(jv_root):
    """markSet=6 に◎を書き → load_my_marks(mark_set=6) で読める。"""
    tmp, mm = jv_root
    rid = "2026053108031208"  # 京都 第3回8日目 8R
    n = dat_writer.write_ai_marks_to_dat(rid, {8: "◎"}, mark_set=6)
    assert n == 1
    marks = mm.load_my_marks(rid, mark_set=6)
    assert 8 in marks
    assert marks[8].mark_symbol == "◎"
    # ファイルは UmaMark6 サブフォルダに作られる
    assert (tmp / "MY_DATA" / "UmaMark6").exists()


def test_clear_first_removes_stale(jv_root):
    """clear_race_first=True で前回の別馬◎が残らない。"""
    _, mm = jv_root
    rid = "2026053108031208"
    dat_writer.write_ai_marks_to_dat(rid, {8: "◎"}, mark_set=6)
    dat_writer.write_ai_marks_to_dat(rid, {3: "◎"}, mark_set=6)  # 別馬に上書き
    marks = mm.load_my_marks(rid, mark_set=6)
    assert 3 in marks and marks[3].mark_symbol == "◎"
    assert 8 not in marks  # 前回の◎は消えている


def test_other_race_untouched(jv_root):
    """同一DAT内の別レースは書込みで壊れない。"""
    _, mm = jv_root
    rid8 = "2026053108031208"   # 8R
    rid7 = "2026053108031207"   # 7R 同一ファイル(京都 第3回8日目)
    dat_writer.write_ai_marks_to_dat(rid8, {8: "◎"}, mark_set=6)
    dat_writer.write_ai_marks_to_dat(rid7, {1: "◎"}, mark_set=6)
    m8 = mm.load_my_marks(rid8, mark_set=6)
    m7 = mm.load_my_marks(rid7, mark_set=6)
    assert m8[8].mark_symbol == "◎"
    assert m7[1].mark_symbol == "◎"


def test_markset_1_rejected(jv_root):
    """mark_set=1 (ふくだ手動印) への書込みは例外。"""
    _, _ = jv_root
    with pytest.raises(ValueError, match="手動印専用"):
        dat_writer.write_ai_marks_to_dat("2026053108031208", {8: "◎"}, mark_set=1)


def test_step2_marks_roundtrip(jv_root):
    """Step2: ◎○▲△Ⅲ穴 を markSet=6 に書き → load_my_marks で全て読み戻せる。"""
    tmp, mm = jv_root
    rid = "2026053108031208"
    marks = {8: "◎", 3: "○", 5: "▲", 1: "△", 9: "Ⅲ", 12: "穴"}
    n = dat_writer.write_ai_marks_to_dat(rid, marks, mark_set=6)
    assert n == 6
    got = mm.load_my_marks(rid, mark_set=6)
    for uma, sym in marks.items():
        assert got[uma].mark_symbol == sym


def test_unknown_mark_rejected(jv_root):
    """未知の印 (○▲△Ⅲ穴 以外、例: 消) は書込み拒否。"""
    _, _ = jv_root
    with pytest.raises(ValueError, match="未知の印"):
        dat_writer.write_ai_marks_to_dat("2026053108031208", {8: "消"}, mark_set=6)


def test_empty_marks_noop(jv_root):
    """空 dict は何もしない。"""
    _, _ = jv_root
    n = dat_writer.write_ai_marks_to_dat("2026053108031208", {}, mark_set=6)
    assert n == 0


def test_byte_offset_matches_ts(jv_root):
    """byte offset が TS batchWriteHorseMarks と等価。

    race_id=2026053108031208 → day_in_meet=12, race=8 (桁: YYYYMMDD VV KK NN RR)。
    record_index=(day-1)*12+(race-1)=(12-1)*12+(8-1)=139、offset=139*44+6+(8-1)*2。
    """
    tmp, _ = jv_root
    rid = "2026053108031208"
    dat_writer.write_ai_marks_to_dat(rid, {8: "◎"}, mark_set=6)
    path = tmp / "MY_DATA" / "UmaMark6"
    dat = next(path.glob("UM*.DAT"))
    raw = dat.read_bytes()
    record_index = (12 - 1) * 12 + (8 - 1)  # =139 (day_in_meet=12)
    offset = record_index * 44 + 6 + (8 - 1) * 2
    assert raw[offset:offset + 2] == b"\x81\x9d"  # ◎
