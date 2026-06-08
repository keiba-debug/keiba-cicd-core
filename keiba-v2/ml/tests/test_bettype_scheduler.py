# -*- coding: utf-8 -*-
"""bettype_scheduler の単体/統合テスト (Session 140 / multi-bettype 自動投票)

検証:
  - build_bet_specs が parse_bet_spec と往復一致 (馬単/三連単の順序保持)
  - vote_one_race_multi: dry で subprocess 不発 / live で --bet×n + max-yen/max-bets/confirm
  - state/lock が bettype_scheduler* (freebudget state を汚さない)
  - halt_day が bettype state のみ halt
  - _run_pass_inner dry 統合: 窓判定 / 冪等 / per_day skip / fund0 skip
"""
from datetime import datetime, timedelta

from ml.strategies import bettype_scheduler as sch
from ml.strategies.bettype_sizing import SizedLeg, RaceSizing
from ml.target_clicker.ff_writer import parse_bet_spec, BET_TYPE_CODE

RID = "2026053108031109"


def _rs(total=600, legs=None):
    if legs is None:
        legs = [
            SizedLeg(RID, "tansho", [3], 300, "単", 5.0, None, 0.3, ""),
            SizedLeg(RID, "umatan", [3, 7], 200, "馬単", 18.0, 1.3, 0.1, ""),
            SizedLeg(RID, "sanrentan", [3, 7, 11], 100, "三連単", 40.0, 1.5, 0.05, ""),
        ]
    return RaceSizing(RID, legs, total, 300, total - 300, 3000, 0, [])


# --- build_bet_specs 往復 ---

def test_build_bet_specs_roundtrip_preserves_order():
    specs = sch.build_bet_specs(RID, _rs())
    assert specs == [f"{RID}:tansho:3:300", f"{RID}:umatan:3/7:200",
                     f"{RID}:sanrentan:3/7/11:100"]
    # parse_bet_spec で往復: 順序保持
    umatan = parse_bet_spec(specs[1])
    assert umatan.bet_type == BET_TYPE_CODE["umatan"]
    assert umatan.umaban == 3 and umatan.umaban2 == 7 and umatan.amount == 200
    sanren = parse_bet_spec(specs[2])
    assert sanren.bet_type == BET_TYPE_CODE["sanrentan"]
    assert (sanren.umaban, sanren.umaban2, sanren.umaban3) == (3, 7, 11)


# --- vote_one_race_multi ---

def test_vote_dry_no_subprocess(monkeypatch, tmp_path):
    called = {"n": 0}
    monkeypatch.setattr(sch.subprocess, "run",
                        lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    res = sch.vote_one_race_multi(tmp_path, RID, _rs(), live=False)
    assert res["mode"] == "dry-run" and res["exit_code"] == 0
    assert called["n"] == 0
    assert res["bet_count"] == 3 and len(res["bet_specs"]) == 3


def test_vote_live_builds_bet_args(monkeypatch, tmp_path):
    captured = {}

    class _Proc:
        returncode = 0

    monkeypatch.setattr(sch.subprocess, "run",
                        lambda cmd, **k: (captured.__setitem__("cmd", cmd), _Proc())[1])
    res = sch.vote_one_race_multi(tmp_path, RID, _rs(), live=True, per_race_cap=3000)
    cmd = captured["cmd"]
    assert cmd.count("--bet") == 3
    assert f"{RID}:umatan:3/7:200" in cmd
    assert "--confirm" in cmd
    # --max-yen = min(total=600, cap=3000) = 600, --max-bets = 3
    assert cmd[cmd.index("--max-yen") + 1] == "600"
    assert cmd[cmd.index("--max-bets") + 1] == "3"
    assert res["exit_code"] == 0


def test_vote_live_max_yen_capped_at_per_race(monkeypatch, tmp_path):
    captured = {}

    class _Proc:
        returncode = 0

    monkeypatch.setattr(sch.subprocess, "run",
                        lambda cmd, **k: (captured.__setitem__("cmd", cmd), _Proc())[1])
    sch.vote_one_race_multi(tmp_path, RID, _rs(total=4000), live=True, per_race_cap=3000)
    cmd = captured["cmd"]
    assert cmd[cmd.index("--max-yen") + 1] == "3000"   # min(4000, 3000)


def test_vote_live_max_yen_capped_at_per_day_remaining(monkeypatch, tmp_path):
    # 🔴-1: 日次残予算 < per_race のとき --max-yen は残予算で抑える (累積上限の per-call 番人)
    captured = {}

    class _Proc:
        returncode = 0

    monkeypatch.setattr(sch.subprocess, "run",
                        lambda cmd, **k: (captured.__setitem__("cmd", cmd), _Proc())[1])
    sch.vote_one_race_multi(tmp_path, RID, _rs(total=600), live=True,
                            per_race_cap=3000, per_day_remaining=400)
    cmd = captured["cmd"]
    assert cmd[cmd.index("--max-yen") + 1] == "400"   # min(600, 3000, 400)


# --- state / lock 分離 ---

def test_state_lock_paths_are_bettype(tmp_path):
    assert sch.state_path(tmp_path, live=True).name == "bettype_scheduler_state.json"
    assert sch.state_path(tmp_path, live=False).name == "bettype_scheduler_state_dryrun.json"
    assert sch.lock_path(tmp_path).name == "bettype_scheduler.lock"


def test_halt_day_writes_bettype_state_only(tmp_path, monkeypatch):
    monkeypatch.setattr(sch, "date_dir_for", lambda d: tmp_path)
    out = sch.halt_day("2026-05-31", live=True, reason="test_halt")
    assert out["halted"] is True
    assert (tmp_path / "bettype_scheduler_state.json").exists()
    # freebudget state は作られない
    assert not (tmp_path / "freebudget_scheduler_state.json").exists()


# --- _run_pass_inner dry 統合 ---

def _setup_inner(monkeypatch, tmp_path, *, rs_total=600, now_in_window=True,
                 already_voted=False, per_day=30000):
    pr = {"race_id": RID, "venue_name": "東京", "race_number": 11}
    monkeypatch.setattr(sch, "load_predictions",
                        lambda dd: {"races": [pr], "vb_refreshed_at": None})
    monkeypatch.setattr(sch, "load_post_times", lambda dd, date_str=None: {RID: "15:00"})
    monkeypatch.setattr(sch, "read_per_race_cap", lambda: 3000)
    # 既定では config「本日のスタート額」未設定扱い → CLI per_day_max_yen にフォールバック。
    #   実 config.json に依存させない (テスト隔離)。 凍結検証テストは個別に上書きする。
    monkeypatch.setattr(sch, "read_day_budget", lambda: (0, ""))
    now = datetime(2026, 5, 31, 14, 55)
    if now_in_window:
        timing = {"deadline": now + timedelta(minutes=3), "vote_at": now - timedelta(minutes=1)}
    else:
        timing = {"deadline": now + timedelta(hours=3), "vote_at": now + timedelta(hours=2)}
    monkeypatch.setattr(sch, "race_timing", lambda d, st, n: timing)
    monkeypatch.setattr(sch, "size_one_race",
                        lambda pr, **k: _rs(total=rs_total) if rs_total else None)
    votes = {}
    if already_voted:
        votes[RID] = {"exit_code": 0, "amount": rs_total}
    monkeypatch.setattr(sch, "load_state",
                        lambda sp, ds, mode: {"date": ds, "mode": mode, "halted": False,
                                              "halt_reason": None, "consecutive_failures": 0,
                                              "votes": votes})
    monkeypatch.setattr(sch, "save_state", lambda sp, st: None)
    return now, per_day


def test_inner_window_dry_would_vote(monkeypatch, tmp_path):
    now, per_day = _setup_inner(monkeypatch, tmp_path)
    out = sch._run_pass_inner("2026-05-31", tmp_path, now=now, live=False,
                              bankroll=10000, strategy="concentrate", ev_floor=1.0,
                              sizing="anchor_kelly_combo_ev", per_day_max_yen=per_day,
                              login_timeout=180, verbose=False)
    assert out["halted"] is False
    assert len(out["voted"]) == 1
    rid, res = out["voted"][0]
    assert res["mode"] == "dry-run" and res["bet_count"] == 3


def test_inner_before_window_waits(monkeypatch, tmp_path):
    now, per_day = _setup_inner(monkeypatch, tmp_path, now_in_window=False)
    out = sch._run_pass_inner("2026-05-31", tmp_path, now=now, live=False,
                              bankroll=10000, strategy="concentrate", ev_floor=1.0,
                              sizing="anchor_kelly_combo_ev", per_day_max_yen=per_day,
                              login_timeout=180, verbose=False)
    assert out["voted"] == []          # 窓前は静かに待機


def test_inner_idempotent_skips_voted(monkeypatch, tmp_path):
    now, per_day = _setup_inner(monkeypatch, tmp_path, already_voted=True)
    out = sch._run_pass_inner("2026-05-31", tmp_path, now=now, live=False,
                              bankroll=10000, strategy="concentrate", ev_floor=1.0,
                              sizing="anchor_kelly_combo_ev", per_day_max_yen=per_day,
                              login_timeout=180, verbose=False)
    assert out["voted"] == []          # 既投票は再投票しない


def test_inner_per_day_cap_skips(monkeypatch, tmp_path):
    now, _ = _setup_inner(monkeypatch, tmp_path, rs_total=600)
    out = sch._run_pass_inner("2026-05-31", tmp_path, now=now, live=False,
                              bankroll=10000, strategy="concentrate", ev_floor=1.0,
                              sizing="anchor_kelly_combo_ev", per_day_max_yen=500,
                              login_timeout=180, verbose=False)
    assert out["voted"] == []          # 600 > per_day 500 → skip
    assert any("日次キャップ" in r for _, r in out["skipped"])


def test_inner_skip_notify_live_once_dry_silent(monkeypatch, tmp_path):
    # 見送り通知 (ふくだ要望): live で fund0 を1回だけ音声通知、 2パス目は再通知しない。 dry は無音。
    pr = {"race_id": RID, "venue_name": "東京", "race_number": 11}
    monkeypatch.setattr(sch, "load_predictions",
                        lambda dd: {"races": [pr], "vb_refreshed_at": None})
    monkeypatch.setattr(sch, "load_post_times", lambda dd, date_str=None: {RID: "15:00"})
    monkeypatch.setattr(sch, "read_per_race_cap", lambda: 3000)
    now = datetime(2026, 5, 31, 14, 55)
    monkeypatch.setattr(sch, "race_timing",
                        lambda d, st, n: {"deadline": now + timedelta(minutes=3),
                                          "vote_at": now - timedelta(minutes=1)})
    monkeypatch.setattr(sch, "size_one_race", lambda pr, **k: None)   # fund0 → 見送り
    shared = {"date": "2026-05-31", "mode": "live", "halted": False,
              "halt_reason": None, "consecutive_failures": 0, "votes": {}}
    monkeypatch.setattr(sch, "load_state", lambda sp, ds, mode: shared)
    monkeypatch.setattr(sch, "save_state", lambda sp, st: None)
    calls = {"n": 0}
    monkeypatch.setattr(sch, "notify_skip",
                        lambda label, reason: calls.__setitem__("n", calls["n"] + 1))
    common = dict(bankroll=10000, strategy="concentrate", ev_floor=1.0,
                  sizing="anchor_kelly_combo_ev", per_day_max_yen=30000,
                  login_timeout=180, verbose=False)
    sch._run_pass_inner("2026-05-31", tmp_path, now=now, live=True, **common)
    sch._run_pass_inner("2026-05-31", tmp_path, now=now, live=True, **common)
    assert calls["n"] == 1                               # 2パスでも1回だけ (notified_skips)
    # dry は無音
    calls["n"] = 0
    shared["notified_skips"] = []
    sch._run_pass_inner("2026-05-31", tmp_path, now=now, live=False, **common)
    assert calls["n"] == 0


def test_inner_fund0_skips(monkeypatch, tmp_path):
    now, per_day = _setup_inner(monkeypatch, tmp_path, rs_total=0)  # size_one_race→None
    out = sch._run_pass_inner("2026-05-31", tmp_path, now=now, live=False,
                              bankroll=10000, strategy="concentrate", ev_floor=1.0,
                              sizing="anchor_kelly_combo_ev", per_day_max_yen=per_day,
                              login_timeout=180, verbose=False)
    assert out["voted"] == []
    assert any("fund 対象なし" in r for _, r in out["skipped"])


# --- Session145: 当日予算の残高ベース凍結 + スキップ理由永続化 ---

def _setup_inner_capture(monkeypatch, tmp_path, **kw):
    """_setup_inner と同じ配線だが、 load_state が返す state dict を呼び出し側へ渡す
    (in-place 変異後の day_budget_yen / skips を検証できるように)。"""
    now, per_day = _setup_inner(monkeypatch, tmp_path, **kw)
    state = {"date": "2026-05-31", "mode": "dry-run", "halted": False,
             "halt_reason": None, "consecutive_failures": 0, "votes": {}}
    if kw.get("already_voted"):
        state["votes"][RID] = {"exit_code": 0, "amount": kw.get("rs_total", 600)}
    monkeypatch.setattr(sch, "load_state", lambda sp, ds, mode: state)
    return now, per_day, state


_COMMON = dict(bankroll=10000, strategy="concentrate", ev_floor=1.0,
               sizing="anchor_kelly_combo_ev", login_timeout=180, verbose=False)


def test_inner_freezes_day_budget_from_config(monkeypatch, tmp_path):
    # config「本日のスタート額」があれば CLI --per-day-max-yen を無視して凍結する。
    now, per_day, state = _setup_inner_capture(monkeypatch, tmp_path)
    monkeypatch.setattr(sch, "read_day_budget", lambda: (50000, "本日のスタート額 50,000円"))
    sch._run_pass_inner("2026-05-31", tmp_path, now=now, live=False,
                        per_day_max_yen=30000, **_COMMON)
    assert state["day_budget_yen"] == 50000
    assert "50,000" in state["day_budget_source"]


def test_inner_day_budget_fallback_to_cli(monkeypatch, tmp_path):
    # config 未設定なら従来の per_day_max_yen (CLI/既定) にフォールバック (後方互換)。
    now, per_day, state = _setup_inner_capture(monkeypatch, tmp_path)
    monkeypatch.setattr(sch, "read_day_budget", lambda: (0, ""))
    sch._run_pass_inner("2026-05-31", tmp_path, now=now, live=False,
                        per_day_max_yen=12345, **_COMMON)
    assert state["day_budget_yen"] == 12345


def test_inner_day_budget_frozen_not_reread(monkeypatch, tmp_path):
    # 既に凍結済みなら read_day_budget を再読しない (午前の払戻で増えても上限は不変)。
    now, per_day, state = _setup_inner_capture(monkeypatch, tmp_path)
    state["day_budget_yen"] = 7000
    state["day_budget_source"] = "frozen earlier"
    monkeypatch.setattr(sch, "read_day_budget", lambda: (99999, "ignored"))
    sch._run_pass_inner("2026-05-31", tmp_path, now=now, live=False,
                        per_day_max_yen=30000, **_COMMON)
    assert state["day_budget_yen"] == 7000


def test_inner_skip_reason_persisted_to_state(monkeypatch, tmp_path):
    # 穴B: per-race スキップ理由が state["skips"] に永続化される (halted=False でも残る)。
    now, per_day, state = _setup_inner_capture(monkeypatch, tmp_path, rs_total=600)
    monkeypatch.setattr(sch, "read_day_budget", lambda: (500, "tiny"))  # 600>500 → 日次キャップ
    sch._run_pass_inner("2026-05-31", tmp_path, now=now, live=False,
                        per_day_max_yen=30000, **_COMMON)
    assert state["halted"] is False
    assert RID in state["skips"]
    assert "日次キャップ" in state["skips"][RID]
