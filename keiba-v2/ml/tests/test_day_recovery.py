# -*- coding: utf-8 -*-
"""day_recovery の単体テスト (2026-06-13 / 収支ベース日次ゲート)

検証:
  - _legs_from_vote: 有効 leg 抽出 / 不正・欠損は除外
  - compute_recovery: 投票なし→DB非接触0 / 失敗投票除外 / 着順確定で払戻合算 /
    着順未確定→pending0 / 払戻None(配当未取得)→0 (安全側)
"""
import ml.settle_ledger as SL
from ml.strategies import day_recovery as DR


# --- _legs_from_vote ---

def test_legs_from_vote_extracts_valid():
    v = {"exit_code": 0,
         "legs": [{"bet_type": "tansho", "horses": [3], "amount": 300},
                  {"bet_type": "umaren", "horses": [1, 5], "amount": 600}]}
    assert DR._legs_from_vote(v) == [
        {"bet_type": "tansho", "horses": [3], "amount": 300},
        {"bet_type": "umaren", "horses": [1, 5], "amount": 600}]


def test_legs_from_vote_skips_missing_or_bad():
    assert DR._legs_from_vote({"exit_code": 0}) == []                       # legs 無し
    assert DR._legs_from_vote({"legs": [{"bet_type": "tansho",
                                         "horses": [], "amount": 300}]}) == []  # horses 空
    assert DR._legs_from_vote({"legs": [{"bet_type": "tansho",
                                         "horses": [3], "amount": 0}]}) == []   # amount 0
    assert DR._legs_from_vote({"legs": [{"horses": [3], "amount": 300}]}) == []  # bet_type 無し


# --- compute_recovery ---

def test_compute_recovery_empty_no_db(monkeypatch):
    # 投票なし → DB に一切触れず 0 (遅延 import すら走らない)
    called = {"n": 0}
    monkeypatch.setattr(SL, "get_finish_positions",
                        lambda *a, **k: called.__setitem__("n", 1))
    out = DR.compute_recovery("2026-05-31", {})
    assert out["recovered_yen"] == 0
    assert called["n"] == 0


def test_compute_recovery_skips_unsuccessful_votes(monkeypatch, tmp_path):
    votes = {"R1": {"exit_code": 1,  # 投票失敗 → 対象外
                    "legs": [{"bet_type": "tansho", "horses": [3], "amount": 300}]}}
    out = DR.compute_recovery("2026-05-31", votes, races_dir=tmp_path)
    assert out["recovered_yen"] == 0


def test_compute_recovery_sums_settled_payout(monkeypatch, tmp_path):
    votes = {"R1": {"exit_code": 0,
                    "legs": [{"bet_type": "tansho", "horses": [3], "amount": 300}]}}
    monkeypatch.setattr(SL, "get_finish_positions", lambda rid, rd: ({3: 1, 1: 2}, 10))
    monkeypatch.setattr(SL, "compute_payout",
                        lambda ticket, fps, nr, rid, caches: (
                            {"ticket_id": ticket["ticket_id"], "payout": 1500,
                             "won": True, "payout_source": "db"}, "ok"))
    out = DR.compute_recovery("2026-05-31", votes, races_dir=tmp_path)
    assert out["recovered_yen"] == 1500
    assert out["settled_races"] == 1
    assert out["detail"]["R1"]["status"] == "settled"


def test_compute_recovery_pending_when_no_finish(monkeypatch, tmp_path):
    votes = {"R1": {"exit_code": 0,
                    "legs": [{"bet_type": "tansho", "horses": [3], "amount": 300}]}}
    monkeypatch.setattr(SL, "get_finish_positions", lambda rid, rd: ({}, 18))
    out = DR.compute_recovery("2026-05-31", votes, races_dir=tmp_path)
    assert out["recovered_yen"] == 0
    assert out["pending_races"] == 1
    assert out["detail"]["R1"]["status"] == "pending"


def test_compute_recovery_payout_none_is_zero(monkeypatch, tmp_path):
    # 的中だが配当未取得 (compute_payout が None) → 回収0 (安全側・settled 扱い)
    votes = {"R1": {"exit_code": 0,
                    "legs": [{"bet_type": "tansho", "horses": [3], "amount": 300}]}}
    monkeypatch.setattr(SL, "get_finish_positions", lambda rid, rd: ({3: 1}, 10))
    monkeypatch.setattr(SL, "compute_payout", lambda *a, **k: (None, "payout_unavailable"))
    out = DR.compute_recovery("2026-05-31", votes, races_dir=tmp_path)
    assert out["recovered_yen"] == 0
    assert out["settled_races"] == 1


def test_compute_recovery_multi_race_partial(monkeypatch, tmp_path):
    # 確定済みR1(払戻800) + 未確定R2 → 回収=800・pending=1
    votes = {"R1": {"exit_code": 0,
                    "legs": [{"bet_type": "tansho", "horses": [3], "amount": 400}]},
             "R2": {"exit_code": 0,
                    "legs": [{"bet_type": "tansho", "horses": [5], "amount": 400}]}}

    def _fps(rid, rd):
        return ({3: 1}, 10) if rid == "R1" else ({}, 10)
    monkeypatch.setattr(SL, "get_finish_positions", _fps)
    monkeypatch.setattr(SL, "compute_payout",
                        lambda ticket, fps, nr, rid, caches: (
                            {"ticket_id": ticket["ticket_id"], "payout": 800,
                             "won": True, "payout_source": "db"}, "ok"))
    out = DR.compute_recovery("2026-05-31", votes, races_dir=tmp_path)
    assert out["recovered_yen"] == 800
    assert out["settled_races"] == 1
    assert out["pending_races"] == 1
