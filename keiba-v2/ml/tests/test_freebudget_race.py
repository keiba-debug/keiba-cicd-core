# -*- coding: utf-8 -*-
"""freebudget_race.py のテスト (Session 135)

検証:
  - race_timing: 締切=発走-2分 / 投票推奨=発走-6分 / 状態遷移
  - parse_post_dt / load_post_times: race_info.json パース
  - filter_result_by_race: 1レース切り出し + total 再計算
"""
import json
from datetime import datetime

import pytest

from ml.strategies.freebudget import FreebudgetBet, FreebudgetResult
from ml.strategies import freebudget_race as fr


def _bet(race_id, umaban, amount, win_ev=2.0, odds=5.0):
    return FreebudgetBet(
        race_id=race_id, race_number=9, venue_name="京都", grade="",
        track_type="芝", distance=1600, num_runners=12, umaban=umaban,
        horse_name=f"テスト馬{umaban}", odds=odds, rank_p=1, rank_w=1,
        odds_rank=1, vb_gap=0, win_ev=win_ev, confidence=0.5,
        amount=amount,
    )


def _result(bets):
    return FreebudgetResult(
        bets=bets, bankroll=10000, kelly_fraction=0.25,
        per_bet_cap_pct=0.10, preset="standard",
        total_yen=sum(b.amount for b in bets), n_eligible=len(bets),
        n_funded=len(bets), n_truncated=0,
    )


# --- parse_post_dt ---

def test_parse_post_dt_valid():
    dt = fr.parse_post_dt("2026-05-30", "9:50")
    assert dt == datetime(2026, 5, 30, 9, 50)


def test_parse_post_dt_two_digit_hour():
    dt = fr.parse_post_dt("2026-05-30", "15:05")
    assert dt == datetime(2026, 5, 30, 15, 5)


@pytest.mark.parametrize("bad", ["", "なし", "25", None])
def test_parse_post_dt_invalid(bad):
    assert fr.parse_post_dt("2026-05-30", bad) is None


# --- race_timing: 締切=発走-2分 / 投票=発走-6分 ---

def test_race_timing_deadline_and_vote_offsets():
    t = fr.race_timing("2026-05-30", "14:30", now=datetime(2026, 5, 30, 10, 0))
    assert t["post"] == datetime(2026, 5, 30, 14, 30)
    assert t["deadline"] == datetime(2026, 5, 30, 14, 28)   # -2分
    assert t["vote_at"] == datetime(2026, 5, 30, 14, 24)    # -6分


def test_race_timing_status_waiting():
    # 投票時刻 14:24 より前 → 待機
    t = fr.race_timing("2026-05-30", "14:30", now=datetime(2026, 5, 30, 14, 0))
    assert "待機" in t["status"]


def test_race_timing_status_vote_window():
    # 14:24〜14:28 = 投票WINDOW
    t = fr.race_timing("2026-05-30", "14:30", now=datetime(2026, 5, 30, 14, 25))
    assert "投票WINDOW" in t["status"]


def test_race_timing_status_deadline_passed():
    # 14:28〜14:30 = 締切済(発走前)
    t = fr.race_timing("2026-05-30", "14:30", now=datetime(2026, 5, 30, 14, 29))
    assert "締切済" in t["status"]


def test_race_timing_status_started():
    t = fr.race_timing("2026-05-30", "14:30", now=datetime(2026, 5, 30, 14, 31))
    assert t["status"] == "発走済"


def test_race_timing_unknown_when_no_time():
    t = fr.race_timing("2026-05-30", "", now=datetime(2026, 5, 30, 10, 0))
    assert t["status"] == "時刻不明"
    assert t["deadline"] is None


# --- load_post_times ---

def test_load_post_times(tmp_path):
    info = {
        "date": "2026-05-30",
        "kaisai_data": {
            "東京": [
                {"race_id_16": "2026053005021101", "start_time": "9:50"},
                {"race_id_16": "2026053005021103", "start_time": "10:50"},
            ],
            "京都": [
                {"race_id_16": "2026053008031109", "start_time": "14:30"},
            ],
        },
    }
    (tmp_path / "race_info.json").write_text(
        json.dumps(info, ensure_ascii=False), encoding="utf-8")
    m = fr.load_post_times(tmp_path)
    assert m["2026053005021101"] == "9:50"
    assert m["2026053005021103"] == "10:50"
    assert m["2026053008031109"] == "14:30"


def test_load_post_times_missing_file(tmp_path):
    assert fr.load_post_times(tmp_path) == {}


def test_load_post_times_skips_blank(tmp_path):
    info = {"kaisai_data": {"東京": [
        {"race_id_16": "2026053005021101", "start_time": ""},
        {"race_id_16": "", "start_time": "9:50"},
    ]}}
    (tmp_path / "race_info.json").write_text(
        json.dumps(info, ensure_ascii=False), encoding="utf-8")
    assert fr.load_post_times(tmp_path) == {}


# --- 🔴-3 mykeibadb 発走時刻 正本 (DB優先) ---

class _FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, *a, **k):
        pass

    def fetchall(self):
        return self._rows


class _FakeConn:
    def __init__(self, rows):
        self._rows = rows

    def cursor(self):
        return _FakeCursor(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _patch_db(monkeypatch, rows):
    import core.db
    monkeypatch.setattr(core.db, "get_connection", lambda: _FakeConn(rows))


def test_load_post_times_from_db_hhmm_to_colon(monkeypatch):
    _patch_db(monkeypatch, [("2026053005021101", "0950"),
                            ("2026053008031109", "1431")])
    m = fr.load_post_times_from_db("2026-05-30")
    assert m["2026053005021101"] == "09:50"
    assert m["2026053008031109"] == "14:31"


def test_load_post_times_from_db_skips_bad_hhmm(monkeypatch):
    _patch_db(monkeypatch, [("2026053005021101", ""),       # 空
                            ("2026053005021102", "99"),      # 桁不足
                            ("2026053005021103", "1050")])   # OK
    m = fr.load_post_times_from_db("2026-05-30")
    assert m == {"2026053005021103": "10:50"}


def test_load_post_times_db_overrides_file(monkeypatch, tmp_path):
    # file は 14:30、 DB(正本) は 14:31 → DB 優先
    info = {"kaisai_data": {"京都": [
        {"race_id_16": "2026053008031109", "start_time": "14:30"}]}}
    (tmp_path / "race_info.json").write_text(
        json.dumps(info, ensure_ascii=False), encoding="utf-8")
    _patch_db(monkeypatch, [("2026053008031109", "1431")])
    m = fr.load_post_times(tmp_path, date_str="2026-05-30")
    assert m["2026053008031109"] == "14:31"   # DB が上書き


def test_load_post_times_db_down_falls_back_to_file(monkeypatch, tmp_path):
    info = {"kaisai_data": {"京都": [
        {"race_id_16": "2026053008031109", "start_time": "14:30"}]}}
    (tmp_path / "race_info.json").write_text(
        json.dumps(info, ensure_ascii=False), encoding="utf-8")

    def _boom():
        raise RuntimeError("db down")
    import core.db
    monkeypatch.setattr(core.db, "get_connection", _boom)
    m = fr.load_post_times(tmp_path, date_str="2026-05-30")
    assert m["2026053008031109"] == "14:30"   # DB 不通 → file フォールバック


def test_load_post_times_no_date_str_file_only(monkeypatch, tmp_path):
    info = {"kaisai_data": {"京都": [
        {"race_id_16": "2026053008031109", "start_time": "14:30"}]}}
    (tmp_path / "race_info.json").write_text(
        json.dumps(info, ensure_ascii=False), encoding="utf-8")
    # date_str 無し → DB を引かない (file のみ)。 get_connection が呼ばれたら失敗させる
    import core.db
    monkeypatch.setattr(core.db, "get_connection",
                        lambda: (_ for _ in ()).throw(AssertionError("DB called")))
    m = fr.load_post_times(tmp_path)
    assert m["2026053008031109"] == "14:30"


# --- filter_result_by_race ---

def test_filter_result_by_race_keeps_only_target():
    res = _result([
        _bet("2026053008031109", 4, 600),
        _bet("2026053008031108", 10, 300),
        _bet("2026053008031109", 7, 200),
    ])
    sub = fr.filter_result_by_race(res, "2026053008031109")
    assert len(sub.bets) == 2
    assert {b.umaban for b in sub.bets} == {4, 7}
    assert sub.total_yen == 800
    assert sub.n_funded == 2


def test_filter_result_by_race_no_match():
    res = _result([_bet("2026053008031108", 10, 300)])
    sub = fr.filter_result_by_race(res, "9999999999999999")
    assert sub.bets == []
    assert sub.total_yen == 0


def test_filter_does_not_mutate_original():
    res = _result([
        _bet("2026053008031109", 4, 600),
        _bet("2026053008031108", 10, 300),
    ])
    fr.filter_result_by_race(res, "2026053008031109")
    assert len(res.bets) == 2          # 元は不変
    assert res.total_yen == 900
