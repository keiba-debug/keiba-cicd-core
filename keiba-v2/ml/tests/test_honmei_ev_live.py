# -*- coding: utf-8 -*-
"""本命EV単 本投票化 (honmei_ev_live) の単体テスト (Session 177)。

カバレッジ:
  - read_honmei_ev_config: 既定(無効)/欠損/サニティクランプ/有効化
  - select_honmei_ev: rank_w=1 / win_vb_gap≥3 / win_ev≥1.3 / margin≤60 / 1点 / ev降順
  - ★parity: DEFAULT_PARAMS が bet_engine PRESETS['tansho_ippon'] と一致 (条件ドリフト検知)
  - account_balance / realized_pnl
  - size_honmei_ev_race: 選定→残高×比率・なし=None・極小残高=None・per_race_cap
  - settle_honmei_ev_day: 台帳記録・冪等 (compute_recovery は monkeypatch)
"""
from __future__ import annotations

import json

import pytest

from ml.strategies import honmei_ev_live as hl


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------

def _entry(umaban, rank_w, win_vb_gap, win_ev, margin=30.0, odds=4.0, name="h"):
    return {"umaban": umaban, "horse_name": name, "rank_w": rank_w,
            "win_vb_gap": win_vb_gap, "win_ev": win_ev,
            "predicted_margin": margin, "odds": odds}


def _race(rid="2026062805030611", venue="東京", rno=11, entries=None):
    return {"race_id": rid, "venue_name": venue, "race_number": rno,
            "entries": entries if entries is not None else [
                _entry(2, 1, 4, 1.5),     # rank_w1 gap4 ev1.5 margin30 → 該当
                _entry(1, 2, 6, 2.0),     # rank_w2 → 非該当 (本命でない)
                _entry(5, 1, 1, 1.4),     # gap1 → 非該当
            ]}


def _cfg(path, **settings):
    path.write_text(json.dumps({"settings": settings}, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# read_honmei_ev_config
# ---------------------------------------------------------------------------

def test_config_missing_defaults_disabled(tmp_path):
    c = hl.read_honmei_ev_config(tmp_path / "nope.json")
    assert c.enabled is False
    assert c.initial_bankroll_yen == hl.DEFAULT_INITIAL_BANKROLL == 300_000
    assert c.bet_pct == hl.DEFAULT_BET_PCT == 2.0
    assert c.day_pct == hl.DEFAULT_DAY_PCT == 10.0


def test_config_reads_enabled_values(tmp_path):
    p = _cfg(tmp_path / "c.json", tansho_ev_enabled=True,
             tansho_ev_initial_bankroll_yen=500000, tansho_ev_bet_pct=1.5,
             tansho_ev_day_pct=7.0)
    c = hl.read_honmei_ev_config(p)
    assert c.enabled is True and c.initial_bankroll_yen == 500000
    assert c.bet_pct == 1.5 and c.day_pct == 7.0


def test_config_sanity_clamps_bad_values(tmp_path):
    p = _cfg(tmp_path / "c.json", tansho_ev_enabled=True, tansho_ev_bet_pct=0,
             tansho_ev_day_pct=200, tansho_ev_initial_bankroll_yen=0)
    c = hl.read_honmei_ev_config(p)
    assert c.bet_pct == hl.DEFAULT_BET_PCT
    assert c.day_pct == hl.DEFAULT_DAY_PCT
    assert c.initial_bankroll_yen == hl.DEFAULT_INITIAL_BANKROLL


def test_config_independent_of_gap(tmp_path):
    # gap_enabled だけ True でも 本命EV単は無効 (口座が独立=別キー)
    p = _cfg(tmp_path / "c.json", gap_enabled=True)
    assert hl.read_honmei_ev_config(p).enabled is False


# ---------------------------------------------------------------------------
# select_honmei_ev + bet_engine parity
# ---------------------------------------------------------------------------

def test_select_picks_only_rank1_value_close():
    picks = hl.select_honmei_ev(_race())
    assert [p["umaban"] for p in picks] == [2]


def test_select_rank_gate_rank1_only():
    # rank_w=2 は gap/ev/margin を満たしても非該当
    r = _race(entries=[_entry(1, 2, 9, 3.0, 10.0)])
    assert hl.select_honmei_ev(r) == []


def test_select_gap_floor():
    assert hl.select_honmei_ev(_race(entries=[_entry(1, 1, 2, 1.5)])) == []  # gap2<3
    assert len(hl.select_honmei_ev(_race(entries=[_entry(1, 1, 3, 1.5)]))) == 1  # gap3 OK


def test_select_ev_floor():
    assert hl.select_honmei_ev(_race(entries=[_entry(1, 1, 5, 1.29)])) == []   # ev<1.3
    assert len(hl.select_honmei_ev(_race(entries=[_entry(1, 1, 5, 1.30)]))) == 1


def test_select_margin_gate():
    assert hl.select_honmei_ev(_race(entries=[_entry(1, 1, 5, 1.5, margin=61)])) == []  # margin>60
    assert len(hl.select_honmei_ev(_race(entries=[_entry(1, 1, 5, 1.5, margin=60)]))) == 1


def test_select_top_k_one_per_race():
    # rank_w=1 が2頭(データ異常)でも 1点まで・ev降順で高い方
    r = _race(entries=[_entry(1, 1, 5, 1.4), _entry(2, 1, 5, 1.9)])
    picks = hl.select_honmei_ev(r)
    assert len(picks) == 1 and picks[0]["umaban"] == 2


def test_params_parity_with_bet_engine_tansho_ippon():
    """★条件ドリフト検知★: honmei DEFAULT_PARAMS = bet_engine PRESETS['tansho_ippon'] の実効条件。"""
    from ml.bet_engine import PRESETS
    ti = PRESETS["tansho_ippon"]
    assert hl.DEFAULT_PARAMS["rank_w_max"] == ti.win_max_rank_w == 1
    assert hl.DEFAULT_PARAMS["win_gap_min"] == ti.win_min_win_gap == 3
    assert hl.DEFAULT_PARAMS["win_ev_floor"] == ti.win_min_ev == 1.3
    assert hl.DEFAULT_PARAMS["margin_max"] == ti.win_max_predicted_margin == 60
    assert hl.DEFAULT_PARAMS["top_k"] == ti.max_win_per_race == 1


# ---------------------------------------------------------------------------
# realized_pnl / account_balance
# ---------------------------------------------------------------------------

def test_realized_pnl_and_balance():
    led = {"days": {"2026-06-28": {"pnl": -6000}, "2026-07-05": {"pnl": 25000}}}
    assert hl.realized_pnl(led) == 19000
    cfg = hl.HonmeiEvConfig(True, 300000, 2.0, 10.0)
    assert hl.account_balance(cfg, led) == 319000


def test_balance_empty_ledger_is_initial():
    cfg = hl.HonmeiEvConfig(True, 300000, 2.0, 10.0)
    assert hl.account_balance(cfg, {"days": {}}) == 300000


# ---------------------------------------------------------------------------
# size_honmei_ev_race
# ---------------------------------------------------------------------------

def test_size_picks_and_sizes():
    rs = hl.size_honmei_ev_race(_race(), balance=300000, bet_pct=2.0, per_race_cap=0)
    assert rs is not None and len(rs.legs) == 1
    leg = rs.legs[0]
    assert leg.bet_type == "tansho" and leg.horses == [2] and leg.amount == 6000
    assert rs.total_yen == 6000 and rs.combo_yen == 0


def test_size_no_pick_returns_none():
    r = _race(entries=[_entry(1, 2, 6, 2.0)])  # rank_w2 → 非該当
    assert hl.size_honmei_ev_race(r, balance=300000, bet_pct=2.0) is None


def test_size_tiny_balance_returns_none():
    assert hl.size_honmei_ev_race(_race(), balance=4000, bet_pct=2.0) is None  # 80円<100


# ---------------------------------------------------------------------------
# settle_honmei_ev_day (compute_recovery を monkeypatch)
# ---------------------------------------------------------------------------

def test_settle_writes_ledger(tmp_path, monkeypatch):
    ledpath = tmp_path / "ledger.json"
    monkeypatch.setattr(hl, "_ledger_path", lambda: ledpath)
    monkeypatch.setattr("ml.strategies.day_recovery.compute_recovery",
                        lambda d, v: {"recovered_yen": 18000, "settled_races": 1,
                                      "pending_races": 0, "detail": {"r1": {"payout": 18000}}})
    votes = {"r1": {"exit_code": 0, "amount": 6000,
                    "legs": [{"bet_type": "tansho", "horses": [2], "amount": 6000}]}}
    day = hl.settle_honmei_ev_day("2026-06-28", votes)
    assert day["cost"] == 6000 and day["payout"] == 18000 and day["pnl"] == 12000
    assert day["n"] == 1 and day["hit"] == 1
    saved = json.loads(ledpath.read_text(encoding="utf-8"))
    assert saved["days"]["2026-06-28"]["pnl"] == 12000


def test_settle_idempotent_overwrite(tmp_path, monkeypatch):
    ledpath = tmp_path / "ledger.json"
    monkeypatch.setattr(hl, "_ledger_path", lambda: ledpath)
    seq = iter([{"recovered_yen": 0, "detail": {}},
                {"recovered_yen": 18000, "detail": {"r1": {"payout": 18000}}}])
    monkeypatch.setattr("ml.strategies.day_recovery.compute_recovery",
                        lambda d, v: next(seq))
    votes = {"r1": {"exit_code": 0, "amount": 6000,
                    "legs": [{"bet_type": "tansho", "horses": [2], "amount": 6000}]}}
    hl.settle_honmei_ev_day("2026-06-28", votes)
    day2 = hl.settle_honmei_ev_day("2026-06-28", votes)
    assert day2["payout"] == 18000
    saved = json.loads(ledpath.read_text(encoding="utf-8"))
    assert len(saved["days"]) == 1 and saved["days"]["2026-06-28"]["pnl"] == 12000
