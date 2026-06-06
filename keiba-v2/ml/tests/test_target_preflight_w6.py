#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""W6: 投票前プリフライト + 一過性 GUI 失敗リトライ + scheduler の skip(haltでなく) 処理。

背景 (2026-06-06 ライブ): ふくだが TARGET で「本日集計画面」 を前面に開いていたため
step1 の click_input が "There is no active desktop ..." で失敗 → exit 4 → 2 連続で
誤 halt し、 8R を取りこぼした (安全装置自体は正常)。

対策:
  1. menu_runner.preflight_target_ready(): 主ウィンドウを前面化、 不可なら False。
  2. runner: preflight NG → exit 9 (EXIT_TARGET_NOT_READY) / step1 一過性失敗を 1 回リトライ。
  3. scheduler: exit 9 を SKIP_EXIT_CODES として halt/失敗カウントせず skip → 次パス再試行。

Usage:
    cd keiba-v2
    python -m pytest ml/tests/test_target_preflight_w6.py -v
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import ml.target_clicker.menu_runner as mr
import ml.target_clicker.runner as runner
import ml.strategies.bettype_scheduler as bsch
import ml.strategies.freebudget_scheduler as fsch


# ======================================================================
# 1. menu_runner.preflight_target_ready — 投票可否判定ロジック
# ======================================================================

class _FakeWin:
    def __init__(self, handle=0x1234):
        self.handle = handle
        self.focus_calls = 0

    def set_focus(self):
        self.focus_calls += 1


def _patch_preflight(monkeypatch, *, window, has_menu, fg_seq):
    """preflight の win32 プリミティブを差し替え。 fg_seq は GetForegroundWindow の連続返り値。"""
    monkeypatch.setattr(mr, "find_target_window", lambda *a, **k: window)
    monkeypatch.setattr(mr, "_window_has_menu", lambda w: has_menu)
    monkeypatch.setattr(mr, "_restore_and_foreground", lambda hwnd: None)
    seq = list(fg_seq)
    monkeypatch.setattr(mr, "_get_foreground_hwnd", lambda: seq.pop(0) if seq else None)
    monkeypatch.setattr(mr.time, "sleep", lambda s: None)


def test_preflight_no_window_is_not_ready(monkeypatch):
    _patch_preflight(monkeypatch, window=None, has_menu=False, fg_seq=[])
    assert mr.preflight_target_ready(verbose=False) is False


def test_preflight_no_menu_window_is_not_ready(monkeypatch):
    # find_target_window が menu 無し窓 (集計画面等) を最終手段で返したケース
    w = _FakeWin()
    _patch_preflight(monkeypatch, window=w, has_menu=False, fg_seq=[w.handle])
    assert mr.preflight_target_ready(verbose=False) is False


def test_preflight_foreground_match_is_ready(monkeypatch):
    w = _FakeWin(handle=0xABCD)
    _patch_preflight(monkeypatch, window=w, has_menu=True, fg_seq=[0xABCD])
    assert mr.preflight_target_ready(verbose=False) is True
    assert w.focus_calls == 1


def test_preflight_foreground_unknown_is_optimistic_ready(monkeypatch):
    # GetForegroundWindow が None (取得不能) なら blocking 判定不能 → 楽観的に投票可
    w = _FakeWin()
    _patch_preflight(monkeypatch, window=w, has_menu=True, fg_seq=[None])
    assert mr.preflight_target_ready(verbose=False) is True


def test_preflight_blocked_foreground_is_not_ready(monkeypatch):
    # 別窓 (集計画面 hwnd=0x9999) が前面を握り続ける → リトライ尽きて投票不可
    w = _FakeWin(handle=0x1111)
    _patch_preflight(monkeypatch, window=w, has_menu=True,
                     fg_seq=[0x9999, 0x9999, 0x9999, 0x9999])
    assert mr.preflight_target_ready(foreground_retries=3, verbose=False) is False
    assert w.focus_calls == 3                       # 各 attempt で前面化を試みた


def test_preflight_recovers_on_retry(monkeypatch):
    # 1 回目は別窓が前面、 2 回目で主ウィンドウが前面に出れば投票可
    w = _FakeWin(handle=0x2222)
    _patch_preflight(monkeypatch, window=w, has_menu=True, fg_seq=[0x9999, 0x2222])
    assert mr.preflight_target_ready(foreground_retries=3, verbose=False) is True


# ======================================================================
# 2. runner._is_transient_gui_error / _step1_with_retry
# ======================================================================

def test_transient_gui_error_classification():
    assert runner._is_transient_gui_error(
        RuntimeError("There is no active desktop required for moving mouse cursor!"))
    assert runner._is_transient_gui_error(Exception("menu operation failed"))
    assert runner._is_transient_gui_error(Exception("SetForegroundWindow foreground lost"))
    # 一過性でない (本物のバグ) はリトライ対象外
    assert not runner._is_transient_gui_error(ValueError("FF CSV not found"))
    assert not runner._is_transient_gui_error(KeyError("race_id"))


class _FakeMenuRunner:
    """step1_open_csv_select / preflight_target_ready をスクリプト化した fake。"""
    def __init__(self, step1_results):
        # step1_results: 各呼び出しの結果。 True/False or 送出する Exception。
        self._results = list(step1_results)
        self.step1_calls = 0
        self.preflight_calls = 0

    def step1_open_csv_select(self, ff_path, *, verbose=True):
        self.step1_calls += 1
        r = self._results.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def preflight_target_ready(self, *, verbose=True):
        self.preflight_calls += 1
        return True


def test_step1_success_first_try(monkeypatch):
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    m = _FakeMenuRunner([True])
    assert runner._step1_with_retry(m, Path("x.csv"), verbose=False) is True
    assert m.step1_calls == 1 and m.preflight_calls == 0


def test_step1_transient_then_success(monkeypatch):
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    m = _FakeMenuRunner([RuntimeError("no active desktop"), True])
    assert runner._step1_with_retry(m, Path("x.csv"), verbose=False) is True
    assert m.step1_calls == 2
    assert m.preflight_calls == 1            # リトライ前に再前面化した


def test_step1_transient_persists_reraises(monkeypatch):
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    m = _FakeMenuRunner([RuntimeError("no active desktop"),
                         RuntimeError("no active desktop")])
    # リトライ後も一過性失敗が続けば送出 → 上位で exit 4 (halt 安全弁を維持)
    try:
        runner._step1_with_retry(m, Path("x.csv"), verbose=False)
        assert False, "should have raised"
    except RuntimeError:
        pass
    assert m.step1_calls == 2


def test_step1_nontransient_reraises_immediately(monkeypatch):
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    m = _FakeMenuRunner([ValueError("real bug")])
    try:
        runner._step1_with_retry(m, Path("x.csv"), verbose=False)
        assert False, "should have raised"
    except ValueError:
        pass
    assert m.step1_calls == 1 and m.preflight_calls == 0    # 即送出・リトライしない


def test_step1_returns_false_after_retries(monkeypatch):
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    m = _FakeMenuRunner([False, False])
    assert runner._step1_with_retry(m, Path("x.csv"), verbose=False) is False
    assert m.step1_calls == 2 and m.preflight_calls == 1


# ======================================================================
# 3. scheduler の exit 9 (SKIP) 処理 — halt/失敗カウントせず skip
# ======================================================================

RID = "2026053108010101"


def _rs(total=2800):
    """size_one_race の返り値 (RaceSizing) を模した最小スタブ。"""
    class _Leg:
        bet_type = "tansho"; horses = [1]; amount = total
        leg_odds = 2.0; ev = 1.2; plan_label = "x"
    class _RS:
        legs = [_Leg()]; total_yen = total; anchor_yen = total; combo_yen = 0
        warnings = []
    return _RS()


def _setup_bettype(monkeypatch, *, exit_code, shared_state):
    pr = {"race_id": RID, "venue_name": "東京", "race_number": 11}
    now = datetime(2026, 5, 31, 14, 55)
    monkeypatch.setattr(bsch, "load_predictions",
                        lambda dd: {"races": [pr], "vb_refreshed_at": None})
    monkeypatch.setattr(bsch, "load_post_times", lambda dd, date_str=None: {RID: "15:00"})
    monkeypatch.setattr(bsch, "read_per_race_cap", lambda: 3000)
    monkeypatch.setattr(bsch, "race_timing",
                        lambda d, st, n: {"deadline": now + timedelta(minutes=3),
                                          "vote_at": now - timedelta(minutes=1)})
    monkeypatch.setattr(bsch, "size_one_race", lambda pr, **k: _rs())
    monkeypatch.setattr(bsch, "load_state", lambda sp, ds, mode: shared_state)
    monkeypatch.setattr(bsch, "save_state", lambda sp, st: None)
    # vote_one_race_multi は subprocess を立てるので exit_code 固定の dict を返す stub に
    monkeypatch.setattr(bsch, "vote_one_race_multi",
                        lambda dd, rid, rs, **k: {"amount": rs.total_yen, "bet_count": 1,
                                                  "mode": "live", "exit_code": exit_code,
                                                  "note": "stub"})
    return now


def _run_bettype(monkeypatch, now, tmp_path):
    monkeypatch.setattr(bsch, "notify_skip", lambda label, reason: None)
    return bsch._run_pass_inner(
        "2026-05-31", tmp_path, now=now, live=True, bankroll=10000,
        strategy="hole_seeker", ev_floor=1.0, sizing="anchor_kelly_combo_ev",
        per_day_max_yen=30000, login_timeout=180, verbose=False)


def test_bettype_exit9_skips_not_halt(monkeypatch, tmp_path):
    state = {"date": "2026-05-31", "mode": "live", "halted": False,
             "halt_reason": None, "consecutive_failures": 0, "votes": {}}
    now = _setup_bettype(monkeypatch, exit_code=9, shared_state=state)
    out = _run_bettype(monkeypatch, now, tmp_path)
    assert out["halted"] is False                 # halt しない
    assert out["voted"] == []                     # 投票扱いにしない
    assert any("TARGET投票不可" in r for _, r in out["skipped"])
    assert state["consecutive_failures"] == 0     # 失敗カウントしない
    assert RID not in state["votes"]              # state に投票記録を残さない (次パス再評価)


def test_bettype_exit9_twice_never_halts(monkeypatch, tmp_path):
    # exit 9 が 2 パス連続でも halt しない (exit 4 なら MAX_CONSECUTIVE_FAILURES=2 で halt)
    state = {"date": "2026-05-31", "mode": "live", "halted": False,
             "halt_reason": None, "consecutive_failures": 0, "votes": {}}
    now = _setup_bettype(monkeypatch, exit_code=9, shared_state=state)
    _run_bettype(monkeypatch, now, tmp_path)
    out2 = _run_bettype(monkeypatch, now, tmp_path)
    assert out2["halted"] is False
    assert state["consecutive_failures"] == 0


def test_bettype_exit9_notifies_skip_once(monkeypatch, tmp_path):
    state = {"date": "2026-05-31", "mode": "live", "halted": False,
             "halt_reason": None, "consecutive_failures": 0, "votes": {}}
    now = _setup_bettype(monkeypatch, exit_code=9, shared_state=state)
    calls = {"n": 0, "reasons": []}

    def fake_notify(label, reason):
        calls["n"] += 1
        calls["reasons"].append(reason)
    monkeypatch.setattr(bsch, "notify_skip", fake_notify)
    common = dict(bankroll=10000, strategy="hole_seeker", ev_floor=1.0,
                  sizing="anchor_kelly_combo_ev", per_day_max_yen=30000,
                  login_timeout=180, verbose=False)
    bsch._run_pass_inner("2026-05-31", tmp_path, now=now, live=True, **common)
    bsch._run_pass_inner("2026-05-31", tmp_path, now=now, live=True, **common)
    assert calls["n"] == 1                          # notified_skips で 1 回だけ
    assert "投票画面" in calls["reasons"][0]


def test_bettype_exit4_still_halts_at_two(monkeypatch, tmp_path):
    # 回帰ガード: 本物の失敗 (exit 4) は従来通り 2 連続で halt する (安全弁を壊していない)
    state = {"date": "2026-05-31", "mode": "live", "halted": False,
             "halt_reason": None, "consecutive_failures": 0, "votes": {}}
    now = _setup_bettype(monkeypatch, exit_code=4, shared_state=state)
    _run_bettype(monkeypatch, now, tmp_path)
    assert state["consecutive_failures"] == 1 and state["halted"] is False
    # 2 パス目 (state["votes"] に exit4 記録が残るが idempotency は exit==0 のみ → 再評価)
    out2 = _run_bettype(monkeypatch, now, tmp_path)
    assert state["consecutive_failures"] == 2 and out2["halted"] is True


def test_freebudget_skip_exit_codes_constant():
    # 定数の契約: runner.EXIT_TARGET_NOT_READY == 9 で両 scheduler が同値を共有
    assert runner.EXIT_TARGET_NOT_READY == 9
    assert fsch.EXIT_TARGET_NOT_READY == 9
    assert 9 in fsch.SKIP_EXIT_CODES
    assert 9 in bsch.SKIP_EXIT_CODES
    assert 9 not in fsch.HALT_EXIT_CODES         # skip と halt は排他
