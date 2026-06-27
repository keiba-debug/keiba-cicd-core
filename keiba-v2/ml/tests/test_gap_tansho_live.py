# -*- coding: utf-8 -*-
"""gap単勝 本投票化 (gap_tansho_live + gap_tansho_scheduler) の単体テスト (Session 176)。

カバレッジ:
  - read_gap_config: 既定/欠損/サニティクランプ/有効化
  - stake_for: 100円丸め・最低・極小残高=0・比例
  - realized_pnl / account_balance: 初期 + 実現PnL
  - size_gap_race: gap選定→残高×比率・買い目なし=None・per_race_cap trim・極小残高=None
  - settle_gap_day: 台帳記録 (compute_recovery は monkeypatch)
  - scheduler: master switch(無効=no-op) / bankroll凍結 / 日次cap skip / 冪等(二重投票なし)
"""
from __future__ import annotations

import json
from datetime import datetime

import pytest

from ml.strategies import gap_tansho_live as gl
from ml.strategies import gap_tansho_scheduler as S


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------

def _entry(umaban, rank_w, odds_rank, odds, win_ev, name="h"):
    return {"umaban": umaban, "horse_name": name, "rank_w": rank_w,
            "odds_rank": odds_rank, "odds": odds, "win_ev": win_ev}


def _gap_race(rid="2026062805030611", grade="未勝利", venue="東京", rno=11):
    """gap単勝該当 1頭 (uma11: rank_w2 odds_rank7 gap5 odds15 ev1.1) を含むレース。"""
    return {"race_id": rid, "grade": grade, "venue_name": venue, "race_number": rno,
            "entries": [
                _entry(1, 1, 1, 2.0, 0.9),     # ◎本命 gap0 → 非該当
                _entry(11, 2, 7, 15.0, 1.1),   # gap5 該当
                _entry(5, 3, 4, 6.0, 1.2),     # gap1 → 非該当
            ]}


def _no_gap_race(rid="2026062805030601"):
    return {"race_id": rid, "grade": "未勝利", "venue_name": "東京", "race_number": 1,
            "entries": [_entry(1, 1, 1, 2.0, 0.9), _entry(2, 2, 3, 4.0, 0.8)]}


def _cfg(path, **settings):
    base = {"settings": settings}
    path.write_text(json.dumps(base, ensure_ascii=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# read_gap_config
# ---------------------------------------------------------------------------

def test_config_missing_defaults_disabled(tmp_path):
    c = gl.read_gap_config(tmp_path / "nope.json")
    assert c.enabled is False
    assert c.initial_bankroll_yen == gl.DEFAULT_GAP_INITIAL_BANKROLL == 300_000
    assert c.bet_pct == gl.DEFAULT_GAP_BET_PCT == 1.0


def test_config_reads_enabled_values(tmp_path):
    p = _cfg(tmp_path / "c.json", gap_enabled=True, gap_initial_bankroll_yen=500000,
             gap_bet_pct=2.0, gap_day_pct=8.0)
    c = gl.read_gap_config(p)
    assert c.enabled is True and c.initial_bankroll_yen == 500000
    assert c.bet_pct == 2.0 and c.day_pct == 8.0


def test_config_sanity_clamps_bad_values(tmp_path):
    # 比率0/負/100超・初期残高0 → 既定にフォールバック
    p = _cfg(tmp_path / "c.json", gap_enabled=True, gap_bet_pct=0,
             gap_day_pct=200, gap_initial_bankroll_yen=0)
    c = gl.read_gap_config(p)
    assert c.bet_pct == gl.DEFAULT_GAP_BET_PCT
    assert c.day_pct == gl.DEFAULT_GAP_DAY_PCT
    assert c.initial_bankroll_yen == gl.DEFAULT_GAP_INITIAL_BANKROLL


# ---------------------------------------------------------------------------
# stake_for
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("bal,pct,want", [
    (300000, 1.0, 3000),     # 30万 × 1% = 3000
    (300000, 0.5, 1500),     # 0.5% = 1500
    (123456, 1.0, 1200),     # 1234.56 → 100円丸め切り捨て = 1200
    (300000, 2.0, 6000),
    (9000, 1.0, 0),          # 90円 < 100円 → 0 (張らない)
    (0, 1.0, 0),
    (-5000, 1.0, 0),
])
def test_stake_for_rounding_and_floor(bal, pct, want):
    assert gl.stake_for(bal, pct) == want


def test_stake_proportional_grows_with_balance():
    # 比例: 残高が増えれば1点も自動で厚く
    assert gl.stake_for(300000, 1.0) < gl.stake_for(600000, 1.0)


# ---------------------------------------------------------------------------
# realized_pnl / account_balance
# ---------------------------------------------------------------------------

def test_realized_pnl_and_balance():
    led = {"days": {"2026-06-28": {"pnl": -6000}, "2026-07-05": {"pnl": 25000}}}
    assert gl.realized_pnl(led) == 19000
    cfg = gl.GapConfig(True, 300000, 1.0, 5.0)
    assert gl.account_balance(cfg, led) == 319000


def test_balance_empty_ledger_is_initial():
    cfg = gl.GapConfig(True, 300000, 1.0, 5.0)
    assert gl.account_balance(cfg, {"days": {}}) == 300000


# ---------------------------------------------------------------------------
# size_gap_race
# ---------------------------------------------------------------------------

def test_size_gap_race_picks_and_sizes():
    rs = gl.size_gap_race(_gap_race(), balance=300000, bet_pct=1.0, per_race_cap=0)
    assert rs is not None and len(rs.legs) == 1
    leg = rs.legs[0]
    assert leg.bet_type == "tansho" and leg.horses == [11] and leg.amount == 3000
    assert rs.total_yen == 3000 and rs.anchor_yen == 3000 and rs.combo_yen == 0


def test_size_gap_race_no_pick_returns_none():
    assert gl.size_gap_race(_no_gap_race(), balance=300000, bet_pct=1.0) is None


def test_size_gap_race_tiny_balance_returns_none():
    # 残高×比率 < 100円 → 張らない
    assert gl.size_gap_race(_gap_race(), balance=5000, bet_pct=1.0) is None


def test_size_gap_race_per_race_cap_trims_multi_pick():
    # 2頭該当 (uma11 gap5, uma9 gap6) を作り per_race_cap=5200 で 2×3000=6000 → 按分
    r = _gap_race()
    r["entries"].append(_entry(9, 3, 9, 22.0, 1.05))  # gap6 該当
    rs = gl.size_gap_race(r, balance=300000, bet_pct=1.0, per_race_cap=5200)
    assert rs is not None
    assert sum(l.amount for l in rs.legs) <= 5200  # cap 内に収まる


# ---------------------------------------------------------------------------
# settle_gap_day (compute_recovery を monkeypatch)
# ---------------------------------------------------------------------------

def test_settle_gap_day_writes_ledger(tmp_path, monkeypatch):
    ledpath = tmp_path / "ledger.json"
    monkeypatch.setattr(gl, "_ledger_path", lambda: ledpath)
    # 当日 state.votes: 1点3000円・exit0、払戻9000 (3倍的中) を模す
    monkeypatch.setattr("ml.strategies.day_recovery.compute_recovery",
                        lambda d, v: {"recovered_yen": 9000, "settled_races": 1,
                                      "pending_races": 0, "detail": {"r1": {"payout": 9000}}})
    votes = {"r1": {"exit_code": 0, "amount": 3000,
                    "legs": [{"bet_type": "tansho", "horses": [11], "amount": 3000}]}}
    day = gl.settle_gap_day("2026-06-28", votes)
    assert day["cost"] == 3000 and day["payout"] == 9000 and day["pnl"] == 6000
    assert day["n"] == 1 and day["hit"] == 1
    saved = json.loads(ledpath.read_text(encoding="utf-8"))
    assert saved["days"]["2026-06-28"]["pnl"] == 6000


def test_settle_gap_day_idempotent_overwrite(tmp_path, monkeypatch):
    ledpath = tmp_path / "ledger.json"
    monkeypatch.setattr(gl, "_ledger_path", lambda: ledpath)
    # 1回目: 未確定(回収0) → 2回目: 確定(回収9000)。 上書きされる。
    seq = iter([{"recovered_yen": 0, "detail": {}},
                {"recovered_yen": 9000, "detail": {"r1": {"payout": 9000}}}])
    monkeypatch.setattr("ml.strategies.day_recovery.compute_recovery",
                        lambda d, v: next(seq))
    votes = {"r1": {"exit_code": 0, "amount": 3000,
                    "legs": [{"bet_type": "tansho", "horses": [11], "amount": 3000}]}}
    gl.settle_gap_day("2026-06-28", votes)
    day2 = gl.settle_gap_day("2026-06-28", votes)
    assert day2["payout"] == 9000
    saved = json.loads(ledpath.read_text(encoding="utf-8"))
    assert len(saved["days"]) == 1 and saved["days"]["2026-06-28"]["pnl"] == 6000


# ---------------------------------------------------------------------------
# scheduler: master switch / freeze / day-cap / idempotency
# ---------------------------------------------------------------------------

def _wire_scheduler(monkeypatch, tmp_path, *, cfg, predictions, post="15:45"):
    """scheduler の I/O 依存を tmp + fake に差し替え (DB/実ファイル非依存)。"""
    monkeypatch.setattr(S, "date_dir_for", lambda d: tmp_path)
    monkeypatch.setattr(S, "load_predictions", lambda dd: predictions)
    rids = [str(r["race_id"]) for r in predictions.get("races", [])]
    monkeypatch.setattr(S, "load_post_times",
                        lambda dd, date_str=None: {rid: post for rid in rids})
    monkeypatch.setattr(S, "read_per_race_cap", lambda: 5200)
    monkeypatch.setattr(S, "compute_recovery",
                        lambda d, v: {"recovered_yen": 0, "detail": {},
                                      "settled_races": 0, "pending_races": 0})
    monkeypatch.setattr(gl, "read_gap_config", lambda *a, **k: cfg)
    monkeypatch.setattr(gl, "account_balance", lambda *a, **k: cfg.initial_bankroll_yen)


def test_scheduler_disabled_is_noop(monkeypatch, tmp_path):
    cfg = gl.GapConfig(False, 300000, 1.0, 5.0, source="TEST disabled")
    _wire_scheduler(monkeypatch, tmp_path, cfg=cfg,
                    predictions={"races": [_gap_race()]})
    out = S.run_pass("2026-06-28", now=datetime(2026, 6, 28, 15, 40), live=False,
                     verbose=False)
    assert out.get("disabled") is True and out["voted"] == []


def test_scheduler_votes_gap_and_freezes_bankroll(monkeypatch, tmp_path):
    cfg = gl.GapConfig(True, 300000, 1.0, 5.0, source="TEST")
    _wire_scheduler(monkeypatch, tmp_path, cfg=cfg,
                    predictions={"races": [_gap_race(), _no_gap_race()]})
    out = S.run_pass("2026-06-28", now=datetime(2026, 6, 28, 15, 40), live=False,
                     verbose=False)
    assert len(out["voted"]) == 1
    rid, res = out["voted"][0]
    assert res["amount"] == 3000 and res["bet_specs"] == [f"{rid}:tansho:11:3000"]
    # bankroll/day_cap が state に凍結
    st = json.loads((tmp_path / "gap_tansho_scheduler_state_dryrun.json").read_text(encoding="utf-8"))
    assert st["gap_bankroll_yen"] == 300000 and st["gap_day_cap_yen"] == 15000


def test_scheduler_idempotent_no_double_vote(monkeypatch, tmp_path):
    cfg = gl.GapConfig(True, 300000, 1.0, 5.0, source="TEST")
    _wire_scheduler(monkeypatch, tmp_path, cfg=cfg, predictions={"races": [_gap_race()]})
    now = datetime(2026, 6, 28, 15, 40)
    o1 = S.run_pass("2026-06-28", now=now, live=False, verbose=False)
    o2 = S.run_pass("2026-06-28", now=now, live=False, verbose=False)
    assert len(o1["voted"]) == 1 and len(o2["voted"]) == 0


def test_scheduler_day_cap_blocks(monkeypatch, tmp_path):
    # day_pct=0.3% → day_cap = 300000×0.3% = 900 < 3000 stake → cap で skip
    cfg = gl.GapConfig(True, 300000, 1.0, 0.3, source="TEST tiny daycap")
    _wire_scheduler(monkeypatch, tmp_path, cfg=cfg, predictions={"races": [_gap_race()]})
    out = S.run_pass("2026-06-28", now=datetime(2026, 6, 28, 15, 40), live=False,
                     verbose=False)
    assert out["voted"] == []
    assert any("日次cap" in reason for _, reason in out["skipped"])
