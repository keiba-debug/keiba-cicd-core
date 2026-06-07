# -*- coding: utf-8 -*-
"""AI購入軸印 (markSet=3) の抽出 + DAT writer + 施錠/凍結ガード テスト。

設計: docs/auto-purchase/23_AI_MARK_VOTE_SYNC_DESIGN.md (案C) / 26_MARK_SLOT_MAP.md
カバレッジ:
  - ledger (raw_legs 積集合) → 軸(★)+相手(☆) 抽出 (アンカー/単票/box/superseded)
  - ★☆ の CP932 byte が TS target-mark-reader と対称 (819a/8199)
  - write_buy_marks_to_dat round-trip (write → read_marks_from_dat)
  - 施錠: 買い writer は markSet=1/2 拒否 (markSet=2 凍結ガード)、AI writer は markSet=3 拒否
  - markSet=3 へ書いても markSet=2 (AI評価) は不変
"""

import importlib

import pytest

from ml.ai_marks import buy_marks, dat_writer


# ---------------------------------------------------------------------------
# ledger → 軸+相手 抽出
# ---------------------------------------------------------------------------

def _pf(tickets):
    """portfolio dict ヘルパ。tickets=[(bet_type, [horses]), ...]"""
    return {
        "portfolio_id": "pf-x",
        "tickets": [
            {"bet_type": bt, "raw_legs": {"horses": hs}, "total_amount": 100}
            for bt, hs in tickets
        ],
    }


def test_extract_anchor_umaren():
    """アンカー型 (◎-相手 馬連2点): 積集合=軸、残り=相手。 5/31 東京4R 実データ相当。"""
    race = {"race_id": "2026053105021204",
            "portfolios": [_pf([("umaren", [5, 12]), ("umaren", [5, 7])])]}
    r = buy_marks.extract_race_buy_marks(race)
    assert r.axes == [5]
    assert r.partners == [7, 12]
    assert r.marks == {5: "★", 7: "☆", 12: "☆"}
    assert r.n_portfolios == 1


def test_extract_anchor_mixed_bettypes():
    """複数券種ミックス (複/馬連/ワイド/馬単/三連単) でも積集合=軸。 5/31 京都6R 相当。"""
    race = {"race_id": "2026053108031206", "portfolios": [_pf([
        ("fukusho", [6]), ("umaren", [6, 8]), ("umaren", [6, 9]),
        ("wide", [6, 8]), ("wide", [6, 3]), ("umatan", [6, 8]), ("umatan", [6, 3]),
        ("sanrentan", [6, 8, 11]), ("sanrentan", [6, 8, 3]),
        ("sanrentan", [6, 11, 8]), ("sanrentan", [6, 3, 8]),
    ])]}
    r = buy_marks.extract_race_buy_marks(race)
    assert r.axes == [6]
    assert r.partners == [3, 8, 9, 11]


def test_extract_single_tansho_is_axis():
    """単勝1点 = その馬が軸 (相手なし)。"""
    race = {"race_id": "2026053105021208", "portfolios": [_pf([("tansho", [13])])]}
    r = buy_marks.extract_race_buy_marks(race)
    assert r.axes == [13]
    assert r.partners == []
    assert r.marks == {13: "★"}


def test_extract_box_no_common_axis():
    """共通馬のない box (3点) → 軸なし、全馬を相手 (honest fallback)。"""
    race = {"race_id": "2026053105021209",
            "portfolios": [_pf([("umaren", [3, 5]), ("umaren", [5, 7]), ("umaren", [3, 7])])]}
    r = buy_marks.extract_race_buy_marks(race)
    assert r.axes == []
    assert r.partners == [3, 5, 7]
    assert all(m == "☆" for m in r.marks.values())
    assert any("軸なし" in n for n in r.notes)


def test_extract_superseded_excluded():
    """superseded_by_repair の旧 portfolio は集計対象外。"""
    old = _pf([("tansho", [13])])
    old["superseded_by_repair"] = True
    new = _pf([("umaren", [5, 12]), ("umaren", [5, 7])])
    race = {"race_id": "2026053105021204", "portfolios": [old, new]}
    r = buy_marks.extract_race_buy_marks(race)
    assert r.axes == [5]                 # 旧 portfolio の 13 は出ない
    assert 13 not in r.marks
    assert r.n_portfolios == 1


def test_extract_multi_portfolio_axis_priority():
    """同一レースに2 portfolio: 一方で軸の馬は★ (他方で相手でも軸優先)。"""
    race = {"race_id": "2026053105021204", "portfolios": [
        _pf([("umaren", [5, 7])]),       # 軸=5,7 (2点なら積=なし→box扱い) ... 単票化
        _pf([("tansho", [7])]),          # 軸=7
    ]}
    r = buy_marks.extract_race_buy_marks(race)
    assert 7 in r.axes                   # portfolio2 で軸
    assert r.marks[7] == "★"


def test_extract_from_ledger_filters_empty():
    """extract_buy_marks_from_ledger は買い目のあるレースだけ返す。"""
    ledger = {"races": [
        {"race_id": "2026053105021204",
         "portfolios": [_pf([("tansho", [5])])]},
        {"race_id": "2026053105021205", "portfolios": []},   # 空 → 除外
    ]}
    out = buy_marks.extract_buy_marks_from_ledger(ledger)
    assert len(out) == 1
    assert out[0].race_id == "2026053105021204"


# ---------------------------------------------------------------------------
# ★☆ byte が TS と対称 (decode 対称、条件⑤)
# ---------------------------------------------------------------------------

def test_buy_mark_bytes_match_ts():
    """★=0x819a / ☆=0x8199 (target-mark-reader.ts の MARK_BYTES_TO_SYMBOL と一致)。"""
    assert dat_writer._SYMBOL_TO_MARK_BYTES["★"] == b"\x81\x9a"
    assert dat_writer._SYMBOL_TO_MARK_BYTES["☆"] == b"\x81\x99"
    # CP932 round-trip でも一致 (記号が壊れていない保証)
    assert "★".encode("cp932") == b"\x81\x9a"
    assert "☆".encode("cp932") == b"\x81\x99"


def test_buy_marks_no_byte_collision_with_eval():
    """★☆ は評価印 ◎○▲△Ⅲ穴 のどの byte とも衝突しない。"""
    eval_bytes = {dat_writer._SYMBOL_TO_MARK_BYTES[s]
                  for s in ("◎", "○", "▲", "△", "Ⅲ", "穴")}
    assert dat_writer._SYMBOL_TO_MARK_BYTES["★"] not in eval_bytes
    assert dat_writer._SYMBOL_TO_MARK_BYTES["☆"] not in eval_bytes


# ---------------------------------------------------------------------------
# DAT writer round-trip + 施錠 + 凍結ガード
# ---------------------------------------------------------------------------

@pytest.fixture
def jv_root(tmp_path, monkeypatch):
    """一時 JV_DATA_ROOT を差し、my_marks / dat_writer を読み直す。"""
    monkeypatch.setenv("JV_DATA_ROOT", str(tmp_path))
    import ml.features.my_marks as mm
    importlib.reload(mm)
    importlib.reload(dat_writer)
    return tmp_path, mm


def test_buy_roundtrip(jv_root):
    """markSet=8 に ★☆ を書き → read_marks_from_dat で読み戻せる。"""
    tmp, _ = jv_root
    rid = "2026053105021204"
    n = dat_writer.write_buy_marks_to_dat(rid, {5: "★", 7: "☆", 12: "☆"}, mark_set=3)
    assert n == 3
    got = dat_writer.read_marks_from_dat(rid, mark_set=3)
    assert got == {5: "★", 7: "☆", 12: "☆"}
    assert (tmp / "MY_DATA" / "UmaMark3").exists()


def test_buy_clear_first(jv_root):
    """clear_race_first=True で前回の買い軸が残らない。"""
    _, _ = jv_root
    rid = "2026053105021204"
    dat_writer.write_buy_marks_to_dat(rid, {5: "★", 7: "☆"}, mark_set=3)
    dat_writer.write_buy_marks_to_dat(rid, {3: "★"}, mark_set=3)
    got = dat_writer.read_marks_from_dat(rid, mark_set=3)
    assert got == {3: "★"}


def test_buy_writer_rejects_markset_1(jv_root):
    """買い軸 writer は markSet=1 (ふくだ手動) を拒否。"""
    _, _ = jv_root
    with pytest.raises(ValueError, match="手動印専用"):
        dat_writer.write_buy_marks_to_dat("2026053105021204", {5: "★"}, mark_set=1)


def test_buy_writer_rejects_markset_2_frozen(jv_root):
    """買い軸 writer は markSet=2 (AI評価) を拒否 = 凍結ガード (条件①)。"""
    _, _ = jv_root
    with pytest.raises(ValueError, match="凍結"):
        dat_writer.write_buy_marks_to_dat("2026053105021204", {5: "★"}, mark_set=2)


def test_ai_writer_rejects_markset_3(jv_root):
    """AI評価 writer は markSet=3 (買い軸) を拒否 = 相互施錠。"""
    _, _ = jv_root
    with pytest.raises(ValueError, match="購入軸専用"):
        dat_writer.write_ai_marks_to_dat("2026053105021204", {5: "◎"}, mark_set=3)


def test_buy_writer_rejects_eval_marks(jv_root):
    """買い軸 writer は ◎○▲△Ⅲ穴 (評価印) を拒否 (★☆ のみ)。"""
    _, _ = jv_root
    with pytest.raises(ValueError, match="許可されない印"):
        dat_writer.write_buy_marks_to_dat("2026053105021204", {5: "◎"}, mark_set=3)


def test_buy_write_does_not_touch_markset6(jv_root):
    """markSet=3 への書込みは markSet=2 (AI評価) を一切変えない (物理スロット分離)。"""
    _, mm = jv_root
    rid = "2026053105021204"
    # markSet=2 に AI評価◎を書く
    dat_writer.write_ai_marks_to_dat(rid, {9: "◎"}, mark_set=2)
    # markSet=3 に買い軸を書く
    dat_writer.write_buy_marks_to_dat(rid, {5: "★", 7: "☆"}, mark_set=3)
    # markSet=2 は不変
    m2 = mm.load_my_marks(rid, mark_set=2)
    assert m2[9].mark_symbol == "◎"
    assert set(m2.keys()) == {9}
    # markSet=3 は買い軸のみ
    m3 = dat_writer.read_marks_from_dat(rid, mark_set=3)
    assert m3 == {5: "★", 7: "☆"}
