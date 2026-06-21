# -*- coding: utf-8 -*-
"""AIコメント印 (markSet=4) writer + report パーサのテスト。

- write_comment_marks_to_dat: Ａ/Ｂ/Ｃ round-trip、施錠 (1/2/3 拒否)、不正印拒否。
- parse_report: 本体 (## 場 / **NR** / ［確信］馬番) と 抜粋 (- 場NR 馬番) を拾う。
"""

import importlib

import pytest

from ml.ai_marks import dat_writer
from ml.ai_marks.write_comment_marks import parse_report


@pytest.fixture
def jv_root(tmp_path, monkeypatch):
    monkeypatch.setenv("JV_DATA_ROOT", str(tmp_path))
    import ml.features.my_marks as mm
    importlib.reload(mm)
    importlib.reload(dat_writer)
    return tmp_path, mm


def test_roundtrip_abc(jv_root):
    """Ａ/Ｂ/Ｃ を markSet=4 に書き → read_marks_from_dat で読み戻せる。"""
    tmp, _ = jv_root
    rid = "2026062105030611"  # 東京 第3回6日目 11R
    marks = {11: "Ａ", 10: "Ｂ", 14: "Ｃ"}
    n = dat_writer.write_comment_marks_to_dat(rid, marks)
    assert n == 3
    got = dat_writer.read_marks_from_dat(rid, mark_set=4)
    assert got == marks
    assert (tmp / "MY_DATA" / "UmaMark4").exists()


def test_markset_123_rejected(jv_root):
    """mark_set=1/2/3 (手動/AI評価/AI購入軸) への書込みは例外。"""
    _, _ = jv_root
    for ms in (1, 2, 3):
        with pytest.raises(ValueError, match="施錠ガード"):
            dat_writer.write_comment_marks_to_dat(
                "2026062105030611", {11: "Ａ"}, mark_set=ms)


def test_invalid_mark_rejected(jv_root):
    """Ａ/Ｂ/Ｃ 以外 (◎ 等) は markSet=4 で拒否。"""
    _, _ = jv_root
    with pytest.raises(ValueError, match="許可されない印"):
        dat_writer.write_comment_marks_to_dat("2026062105030611", {11: "◎"})


def test_clear_first_removes_stale(jv_root):
    """clear_race_first=True で前回の別馬印が残らない。"""
    _, _ = jv_root
    rid = "2026062105030611"
    dat_writer.write_comment_marks_to_dat(rid, {11: "Ａ"})
    dat_writer.write_comment_marks_to_dat(rid, {3: "Ｂ"})
    got = dat_writer.read_marks_from_dat(rid, mark_set=4)
    assert got == {3: "Ｂ"}


def test_parse_report_body_and_excerpt():
    """本体の 高/中/低 → Ａ/Ｂ/Ｃ、抜粋セクションの 高 を拾い、重複は強い印を残す。"""
    text = (
        "# タイトル\n"
        "## 函館\n"
        "**2R**\n"
        "  - ［低］馬番10 トーセンアミューズ（想定48.6倍）— x\n"
        "**3R**\n"
        "  - ［中］馬番3 エコロデュラン — y\n"
        "  - ［低］馬番7 カッサンドラ — z\n"
        "## 東京\n"
        "**11R**\n"
        "  - ［高］馬番11 テレサ — a\n"
        "  - ［中］馬番10 ホールネス — b\n"
        "## ★確信「高」だけ抜粋\n"
        "  - 東京6R 馬番12 スカイリッチ（想定9.4倍）— c\n"
        "  - 東京11R 馬番11 テレサ（想定21.9倍）— d\n"
    )
    out = parse_report(text)
    assert out[("函館", 2)] == {10: "Ｃ"}
    assert out[("函館", 3)] == {3: "Ｂ", 7: "Ｃ"}
    assert out[("東京", 11)] == {11: "Ａ", 10: "Ｂ"}  # テレサは本体高=抜粋高で Ａ のまま
    assert out[("東京", 6)] == {12: "Ａ"}             # 抜粋のみの馬も拾う


def test_parse_report_no_marks_outside_race():
    """場見出し前の馬番表記は拾わない (race 未確定)。"""
    text = "## 函館\n  - ［中］馬番5 — まだ R 見出しなし\n"
    out = parse_report(text)
    assert out == {}
