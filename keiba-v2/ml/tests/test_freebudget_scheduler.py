# -*- coding: utf-8 -*-
"""freebudget_scheduler の安全機構テスト (Session 135 / シズネ🔴対応)

検証:
  - acquire_lock: 多重起動防止 (🔴-1)
  - load_state: 破損時 halt / 正常時 consecutive_failures 既定 (🔴-4b)
  - vote_one_race: live で --max-yen/--max-bets を期待値ちょうど渡す (🔴-2/🟡-1)
  - filter→vote の dry-run
"""
import json
import os
import time

from ml.strategies import freebudget_scheduler as sch
from ml.strategies.freebudget import FreebudgetBet, FreebudgetResult


# --- acquire_lock (🔴-1) ---

def test_acquire_lock_fresh(tmp_path):
    lp = sch.lock_path(tmp_path)
    assert sch.acquire_lock(lp) is True
    assert lp.exists()
    sch.release_lock(lp)
    assert not lp.exists()


def test_acquire_lock_blocked_when_fresh_lock_exists(tmp_path):
    lp = sch.lock_path(tmp_path)
    assert sch.acquire_lock(lp) is True
    # 2 回目 (別パス相当) は取得できない
    assert sch.acquire_lock(lp) is False
    sch.release_lock(lp)


def test_acquire_lock_overrides_stale(tmp_path):
    lp = sch.lock_path(tmp_path)
    lp.write_text("123 old", encoding="utf-8")
    # mtime を stale 閾値より古く偽装
    old = time.time() - (sch.LOCK_STALE_SEC + 60)
    os.utime(lp, (old, old))
    assert sch.acquire_lock(lp) is True   # stale なので上書き取得できる
    sch.release_lock(lp)


# --- load_state (🔴-4b) ---

def test_load_state_missing_is_fresh(tmp_path):
    st = sch.load_state(tmp_path / "none.json", "2026-05-30", "dry-run")
    assert st["halted"] is False
    assert st["votes"] == {}
    assert st["consecutive_failures"] == 0


def test_load_state_corruption_halts(tmp_path):
    p = tmp_path / "state.json"
    p.write_text("{ broken !!", encoding="utf-8")
    st = sch.load_state(p, "2026-05-30", "live")
    assert st["halted"] is True
    assert "破損" in st["halt_reason"]


def test_load_state_valid_adds_consecutive_failures_default(tmp_path):
    p = tmp_path / "state.json"
    p.write_text(json.dumps({"date": "2026-05-30", "mode": "live",
                             "halted": False, "votes": {}}), encoding="utf-8")
    st = sch.load_state(p, "2026-05-30", "live")
    assert st["consecutive_failures"] == 0   # 旧形式でも既定補完


# --- vote_one_race (🔴-2 / 🟡-1) ---

def _sub(race_id="2026053008031108", n=1, amount_each=300):
    bets = [FreebudgetBet(
        race_id=race_id, race_number=8, venue_name="京都", grade="",
        track_type="芝", distance=1600, num_runners=12, umaban=10 + i,
        horse_name=f"馬{i}", odds=6.0, rank_p=1, rank_w=1, odds_rank=1,
        vb_gap=0, win_ev=1.9, confidence=0.5, amount=amount_each) for i in range(n)]
    return FreebudgetResult(
        bets=bets, bankroll=10000, kelly_fraction=0.25, per_bet_cap_pct=0.10,
        preset="standard", total_yen=amount_each * n, n_eligible=n,
        n_funded=n, n_truncated=0)


def test_vote_one_race_dry_run_no_subprocess(monkeypatch, tmp_path):
    called = {"n": 0}
    monkeypatch.setattr(sch.subprocess, "run", lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    res = sch.vote_one_race(tmp_path, "2026053008031108", _sub(), live=False)
    assert res["mode"] == "dry-run"
    assert called["n"] == 0          # dry-run は subprocess 起動しない


def test_vote_one_race_live_passes_exact_max(monkeypatch, tmp_path):
    captured = {}

    class _Proc:
        returncode = 0

    def _fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return _Proc()

    monkeypatch.setattr(sch.subprocess, "run", _fake_run)
    monkeypatch.setattr(sch, "write_freebudget_bets",
                        lambda dd, r, filename=None: tmp_path / (filename or "x.json"))
    res = sch.vote_one_race(tmp_path, "2026053008031108",
                            _sub(n=2, amount_each=300), live=True)
    cmd = captured["cmd"]
    assert "--max-yen" in cmd and "600" in cmd      # 期待合計ちょうど
    assert "--max-bets" in cmd and "2" in cmd       # 期待件数ちょうど
    assert "--confirm" in cmd
    assert res["exit_code"] == 0


# --- halt_day (Session 139 / web「停止」= 当日 halt) ---

def test_halt_day_creates_halted_state(tmp_path, monkeypatch):
    monkeypatch.setattr(sch, "date_dir_for", lambda d: tmp_path)
    out = sch.halt_day("2026-05-30", live=True, reason="manual_stop_via_web")
    assert out["halted"] is True
    assert out["already_halted"] is False
    st = json.loads(sch.state_path(tmp_path, live=True).read_text(encoding="utf-8"))
    assert st["halted"] is True
    assert st["halt_reason"] == "manual_stop_via_web"
    assert "halted_at" in st


def test_halt_day_idempotent_keeps_first_reason(tmp_path, monkeypatch):
    # 既に halted のとき reason を上書きしない (最初の停止理由を保つ)
    monkeypatch.setattr(sch, "date_dir_for", lambda d: tmp_path)
    sch.halt_day("2026-05-30", live=True, reason="first_reason")
    out2 = sch.halt_day("2026-05-30", live=True, reason="second_reason")
    assert out2["already_halted"] is True
    st = json.loads(sch.state_path(tmp_path, live=True).read_text(encoding="utf-8"))
    assert st["halt_reason"] == "first_reason"


def test_halt_day_preserves_existing_votes(tmp_path, monkeypatch):
    # 停止しても既に投票成立した記録は消さない
    monkeypatch.setattr(sch, "date_dir_for", lambda d: tmp_path)
    sp = sch.state_path(tmp_path, live=False)
    sp.write_text(json.dumps({
        "date": "2026-05-30", "mode": "dry-run", "halted": False,
        "votes": {"2026053005021101": {"amount": 500, "exit_code": 0}},
        "consecutive_failures": 0,
    }), encoding="utf-8")
    sch.halt_day("2026-05-30", live=False, reason="manual_stop_via_web")
    st = json.loads(sp.read_text(encoding="utf-8"))
    assert st["halted"] is True
    assert st["votes"]["2026053005021101"]["amount"] == 500


def test_halt_day_corrupted_state_keeps_corruption_reason(tmp_path, monkeypatch):
    # 破損 state は load_state が halted=True(破損理由) を返す → halt_day は理由を上書きせず
    # 破損シグナルを隠さない (already_halted=True 扱い)
    monkeypatch.setattr(sch, "date_dir_for", lambda d: tmp_path)
    sp = sch.state_path(tmp_path, live=True)
    sp.write_text("{ broken", encoding="utf-8")
    out = sch.halt_day("2026-05-30", live=True, reason="manual_stop_via_web")
    assert out["already_halted"] is True
    st = json.loads(sp.read_text(encoding="utf-8"))
    assert "破損" in st["halt_reason"]


def test_halt_day_works_when_day_dir_missing(tmp_path, monkeypatch):
    # 安全ブレーキは未準備の日付でも効く (親 dir を作って halt を確実に永続化)
    missing = tmp_path / "races" / "2099" / "01" / "01"   # 未作成
    monkeypatch.setattr(sch, "date_dir_for", lambda d: missing)
    out = sch.halt_day("2099-01-01", live=True, reason="manual_stop_via_web")
    assert out["halted"] is True
    assert sch.state_path(missing, live=True).exists()
