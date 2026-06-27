# -*- coding: utf-8 -*-
"""スリーブ・オーケストレーション (sleeves + sleeve_orchestrator) の単体テスト (Session 176 / §8-1)。

カバレッジ:
  - registry / GapSleeve: enabled フィルタ・freeze・size_race のスリーブタグ・settle委譲
  - filter_votes_for_sleeve / sleeve_voted_yen: B別建ての帰属 (脚をスリーブkeyでフィルタ)
  - orchestrator: 無効=no-op / gap単独で投票 / 冪等 / スリーブ別cap / 全体cap / settle分離
振舞い不変(差分0)は ml/analyze/verify_sleeve_parity.py が実データで担保。
"""
from __future__ import annotations

import json
from datetime import datetime

import pytest

from ml.strategies import gap_tansho_live as gl
from ml.strategies import honmei_ev_live as hl
from ml.strategies import sleeve_orchestrator as ORCH
from ml.strategies.sleeves import enabled_sleeves, get_sleeve, SLEEVES
from ml.strategies.sleeves.gap_sleeve import GapSleeve
from ml.strategies.sleeves.honmei_ev_sleeve import HonmeiEvSleeve


def _entry(umaban, rank_w, odds_rank, odds, win_ev):
    return {"umaban": umaban, "horse_name": "h", "rank_w": rank_w,
            "odds_rank": odds_rank, "odds": odds, "win_ev": win_ev}


def _gap_race(rid="2026062805030611"):
    return {"race_id": rid, "grade": "未勝利", "venue_name": "東京", "race_number": 11,
            "entries": [_entry(1, 1, 1, 2.0, 0.9), _entry(11, 2, 7, 15.0, 1.1),
                        _entry(5, 3, 4, 6.0, 1.2)]}


def _no_gap_race(rid="2026062805030601"):
    return {"race_id": rid, "grade": "未勝利", "venue_name": "東京", "race_number": 1,
            "entries": [_entry(1, 1, 1, 2.0, 0.9), _entry(2, 2, 3, 4.0, 0.8)]}


@pytest.fixture(autouse=True)
def _sleeves_off_by_default(monkeypatch):
    """★テストを実 config から隔離★: 既定で両スリーブ無効 (gap_on/honmei_on で個別に有効化)。

    autouse は明示 fixture より先に走るので、 gap_on/honmei_on の setattr が後勝ちで上書きする。
    これが無いと「実 config で honmei を有効化した日」に単一スリーブ前提のテストが壊れる (非密閉)。
    """
    monkeypatch.setattr(gl, "read_gap_config",
                        lambda *a, **k: gl.GapConfig(False, 300000, 1.0, 5.0))
    monkeypatch.setattr(gl, "account_balance", lambda *a, **k: 300000)
    monkeypatch.setattr(hl, "read_honmei_ev_config",
                        lambda *a, **k: hl.HonmeiEvConfig(False, 300000, 2.0, 10.0))
    monkeypatch.setattr(hl, "account_balance", lambda *a, **k: 300000)


@pytest.fixture
def gap_on(monkeypatch):
    cfg = gl.GapConfig(True, 300000, 1.0, 5.0, source="TEST")
    monkeypatch.setattr(gl, "read_gap_config", lambda *a, **k: cfg)
    monkeypatch.setattr(gl, "account_balance", lambda *a, **k: cfg.initial_bankroll_yen)
    return cfg


@pytest.fixture
def honmei_on(monkeypatch):
    cfg = hl.HonmeiEvConfig(True, 300000, 2.0, 10.0, source="TEST")
    monkeypatch.setattr(hl, "read_honmei_ev_config", lambda *a, **k: cfg)
    monkeypatch.setattr(hl, "account_balance", lambda *a, **k: cfg.initial_bankroll_yen)
    return cfg


def _both_race(rid="2026062805030611"):
    """本命EV単(uma1) と 逆張り単(uma11) が ★別々の馬★ を推すレース (B別建てマージ検証)。"""
    return {"race_id": rid, "grade": "未勝利", "venue_name": "東京", "race_number": 11,
            "entries": [
                # uma1: rank_w1 gap(odds_rank-rank_w)=3<5 → gap非該当 / 本命EV単該当(win_vb_gap3 ev1.5 margin30)
                {"umaban": 1, "horse_name": "h", "rank_w": 1, "odds_rank": 4, "odds": 3.0,
                 "win_ev": 1.5, "win_vb_gap": 3, "predicted_margin": 30.0},
                # uma11: rank_w2 → 本命EV単非該当 / gap該当(odds_rank7 gap5 ev1.1)
                {"umaban": 11, "horse_name": "h", "rank_w": 2, "odds_rank": 7, "odds": 15.0,
                 "win_ev": 1.1, "win_vb_gap": 1, "predicted_margin": 30.0},
            ]}


# ---------------------------------------------------------------------------
# registry / GapSleeve
# ---------------------------------------------------------------------------

def test_registry_has_gap():
    assert "gap_tansho" in SLEEVES
    assert isinstance(get_sleeve("gap_tansho"), GapSleeve)


def test_enabled_filters_by_switch(monkeypatch):
    monkeypatch.setattr(gl, "read_gap_config",
                        lambda *a, **k: gl.GapConfig(False, 300000, 1.0, 5.0))
    assert enabled_sleeves() == []
    monkeypatch.setattr(gl, "read_gap_config",
                        lambda *a, **k: gl.GapConfig(True, 300000, 1.0, 5.0))
    assert [s.key for s in enabled_sleeves()] == ["gap_tansho"]


def test_gap_sleeve_freeze_and_size(gap_on):
    s = GapSleeve()
    snap = s.freeze(per_race_cap=5200)
    assert snap["bankroll"] == 300000 and snap["bet_pct"] == 1.0
    assert snap["day_cap"] == 15000 and snap["per_race_cap"] == 5200
    rs = s.size_race(_gap_race(), snap)
    assert rs is not None and len(rs.legs) == 1
    assert rs.legs[0].amount == 3000 and rs.legs[0].sleeve == "gap_tansho"  # ★スリーブタグ★
    assert s.size_race(_no_gap_race(), snap) is None


# ---------------------------------------------------------------------------
# 帰属ヘルパ (B別建て)
# ---------------------------------------------------------------------------

def _vote(legs, exit_code=0):
    return {"exit_code": exit_code, "amount": sum(l["amount"] for l in legs), "legs": legs}


def test_filter_votes_for_sleeve():
    votes = {
        "r1": _vote([{"bet_type": "tansho", "horses": [11], "amount": 3000, "sleeve": "gap_tansho"},
                     {"bet_type": "tansho", "horses": [7], "amount": 2000, "sleeve": "ana_tansho"}]),
        "r2": _vote([{"bet_type": "tansho", "horses": [4], "amount": 2500, "sleeve": "ana_tansho"}]),
        "r3": _vote([{"bet_type": "tansho", "horses": [1], "amount": 100, "sleeve": "gap_tansho"}],
                    exit_code=2),  # 失敗vote→除外
    }
    g = ORCH.filter_votes_for_sleeve(votes, "gap_tansho")
    assert set(g) == {"r1"} and g["r1"]["amount"] == 3000 and len(g["r1"]["legs"]) == 1
    a = ORCH.filter_votes_for_sleeve(votes, "ana_tansho")
    assert set(a) == {"r1", "r2"} and a["r1"]["amount"] == 2000
    assert ORCH.sleeve_voted_yen(votes, "gap_tansho") == 3000
    assert ORCH.sleeve_voted_yen(votes, "ana_tansho") == 4500


# ---------------------------------------------------------------------------
# orchestrator run_pass
# ---------------------------------------------------------------------------

def _wire(monkeypatch, tmp_path, predictions, post="15:45", recovered=0, per_race_cap=5200):
    monkeypatch.setattr(ORCH, "date_dir_for", lambda d: tmp_path)
    monkeypatch.setattr(ORCH, "load_predictions", lambda dd: predictions)
    rids = [str(r["race_id"]) for r in predictions.get("races", [])]
    monkeypatch.setattr(ORCH, "load_post_times", lambda dd, date_str=None: {r: post for r in rids})
    # 案A: orchestrator は resolve_per_race_cap() で (合算cap, ok, source) を取る。 ok=True で一致前提。
    monkeypatch.setattr(ORCH, "resolve_per_race_cap", lambda: (per_race_cap, True, "test"))
    monkeypatch.setattr(ORCH, "compute_recovery",
                        lambda d, v: {"recovered_yen": recovered, "detail": {}})
    monkeypatch.setattr(ORCH, "read_total_day_cap", lambda: 0)  # 専用キーなし → Σ にフォールバック


def test_orch_disabled_noop(monkeypatch, tmp_path):
    monkeypatch.setattr(gl, "read_gap_config",
                        lambda *a, **k: gl.GapConfig(False, 300000, 1.0, 5.0))
    _wire(monkeypatch, tmp_path, {"races": [_gap_race()]})
    out = ORCH.run_pass("2026-06-28", now=datetime(2026, 6, 28, 15, 40), live=False, verbose=False)
    assert out.get("disabled") is True and out["voted"] == []


def test_orch_votes_gap_single_sleeve(gap_on, monkeypatch, tmp_path):
    _wire(monkeypatch, tmp_path, {"races": [_gap_race(), _no_gap_race()]})
    out = ORCH.run_pass("2026-06-28", now=datetime(2026, 6, 28, 15, 40), live=False, verbose=False)
    assert len(out["voted"]) == 1
    rid, res = out["voted"][0]
    assert res["amount"] == 3000 and res["bet_specs"] == [f"{rid}:tansho:11:3000"]
    assert res["sleeves"] == ["gap_tansho"]
    st = json.loads((tmp_path / "sleeve_orchestrator_state_dryrun.json").read_text(encoding="utf-8"))
    assert st["sleeves"]["gap_tansho"]["snapshot"]["bankroll"] == 300000
    assert st["total_day_cap_yen"] == 15000  # Σ = gap day_cap (単一スリーブ)
    # 脚にスリーブタグが記録されている (settle 帰属用)
    assert res["legs"][0]["sleeve"] == "gap_tansho"


def test_orch_idempotent(gap_on, monkeypatch, tmp_path):
    _wire(monkeypatch, tmp_path, {"races": [_gap_race()]})
    now = datetime(2026, 6, 28, 15, 40)
    o1 = ORCH.run_pass("2026-06-28", now=now, live=False, verbose=False)
    o2 = ORCH.run_pass("2026-06-28", now=now, live=False, verbose=False)
    assert len(o1["voted"]) == 1 and len(o2["voted"]) == 0


def test_orch_overall_cap_blocks(gap_on, monkeypatch, tmp_path):
    # day_pct=0.3% → day_cap=900 < 3000 → スリーブ別cap で弾かれ全体も0 → 投票なし
    monkeypatch.setattr(gl, "read_gap_config",
                        lambda *a, **k: gl.GapConfig(True, 300000, 1.0, 0.3, source="tiny"))
    monkeypatch.setattr(gl, "account_balance", lambda *a, **k: 300000)
    _wire(monkeypatch, tmp_path, {"races": [_gap_race()]})
    out = ORCH.run_pass("2026-06-28", now=datetime(2026, 6, 28, 15, 40), live=False, verbose=False)
    assert out["voted"] == []


# ---------------------------------------------------------------------------
# マルチスリーブ (本命EV単 + 逆張り単 並行・Session 177 §8-2/8-3)
# ---------------------------------------------------------------------------

def test_registry_priority_order_honmei_first():
    # ★優先順 = 本命EV単 > 逆張り単 (登録順)★
    assert list(SLEEVES.keys()) == ["honmei_ev", "gap_tansho"]


def test_two_sleeves_enabled_order(gap_on, honmei_on):
    assert [s.key for s in enabled_sleeves()] == ["honmei_ev", "gap_tansho"]


def test_orch_merges_both_sleeves_b_betsuda(gap_on, honmei_on, monkeypatch, tmp_path):
    # 同一レースで本命EV単(uma1=6000) と逆張り単(uma11=3000) が別馬を推す → 2脚マージ・各タグ
    # per_race_cap=20000 は本テストで非干渉に (B別建てマージ自体を確認)。 本番値は別テストで検証。
    _wire(monkeypatch, tmp_path, {"races": [_both_race()]}, per_race_cap=20000)
    out = ORCH.run_pass("2026-06-28", now=datetime(2026, 6, 28, 15, 40), live=False, verbose=False)
    assert len(out["voted"]) == 1
    rid, res = out["voted"][0]
    assert res["sleeves"] == ["honmei_ev", "gap_tansho"]   # 優先順
    assert res["amount"] == 9000
    legs = {l["sleeve"]: l for l in res["legs"]}
    assert legs["honmei_ev"]["horses"] == [1] and legs["honmei_ev"]["amount"] == 6000
    assert legs["gap_tansho"]["horses"] == [11] and legs["gap_tansho"]["amount"] == 3000


def test_orch_total_cap_keeps_priority_sleeve_deterministic(gap_on, honmei_on, monkeypatch, tmp_path):
    # 全体cap=6000 → 優先の本命EV単(6000)だけ残り、逆張り単(3000)は決定的にdrop (先着順でなく固定順)
    _wire(monkeypatch, tmp_path, {"races": [_both_race()]}, per_race_cap=20000)
    monkeypatch.setattr(ORCH, "read_total_day_cap", lambda: 6000)
    out = ORCH.run_pass("2026-06-28", now=datetime(2026, 6, 28, 15, 40), live=False, verbose=False)
    rid, res = out["voted"][0]
    assert res["sleeves"] == ["honmei_ev"]   # 本命EV単のみ残存
    assert res["amount"] == 6000
    assert [l["horses"] for l in res["legs"]] == [[1]]


def test_orch_total_cap_boundary_exact_fits_both(gap_on, honmei_on, monkeypatch, tmp_path):
    # 境界: 全体cap=9000 ちょうど → 両方 fit (6000+3000=9000≤9000)
    _wire(monkeypatch, tmp_path, {"races": [_both_race()]}, per_race_cap=20000)
    monkeypatch.setattr(ORCH, "read_total_day_cap", lambda: 9000)
    out = ORCH.run_pass("2026-06-28", now=datetime(2026, 6, 28, 15, 40), live=False, verbose=False)
    _, res = out["voted"][0]
    assert res["amount"] == 9000 and res["sleeves"] == ["honmei_ev", "gap_tansho"]


def test_orch_settle_separates_by_sleeve(gap_on, monkeypatch, tmp_path):
    # settle_day が当該スリーブ分の votes だけを sleeve.settle_day に渡すか
    monkeypatch.setattr(ORCH, "date_dir_for", lambda d: tmp_path)
    captured = {}
    monkeypatch.setattr(GapSleeve, "settle_day",
                        lambda self, date, votes: captured.update({"votes": votes}) or {"pnl": 0})
    sp = ORCH.state_path(tmp_path, live=True)
    sp.write_text(json.dumps({"date": "2026-06-28", "votes": {
        "r1": _vote([{"bet_type": "tansho", "horses": [11], "amount": 3000, "sleeve": "gap_tansho"},
                     {"bet_type": "tansho", "horses": [7], "amount": 2000, "sleeve": "ana_tansho"}]),
    }}), encoding="utf-8")
    out = ORCH.settle_day("2026-06-28", live=True)
    assert "gap_tansho" in out["sleeves"]
    # gap には gap脚だけ (ana脚は除外) が渡る
    assert captured["votes"]["r1"]["amount"] == 3000
    assert all(l["sleeve"] == "gap_tansho" for l in captured["votes"]["r1"]["legs"])


# ---------------------------------------------------------------------------
# 案A per_race 二段化 (Session 178 / §11-7-7・§11-8) — ★本番値★ 回帰テスト
# ---------------------------------------------------------------------------

@pytest.fixture
def gap_on_15(monkeypatch):
    """本番比率の逆張り単 (1点=残高×1.5%=4500・config 実値)。"""
    cfg = gl.GapConfig(True, 300000, 1.5, 10.0, source="TEST15")
    monkeypatch.setattr(gl, "read_gap_config", lambda *a, **k: cfg)
    monkeypatch.setattr(gl, "account_balance", lambda *a, **k: cfg.initial_bankroll_yen)
    return cfg


def test_orch_prod_both_full_fit_at_12000(gap_on_15, honmei_on, monkeypatch, tmp_path):
    # ★本番値★: 合算上限12000・本命EV単6000(2%)+逆張り単4500(1.5%)=10500≤12000 → 両方満額で投票。
    _wire(monkeypatch, tmp_path, {"races": [_both_race()]}, per_race_cap=12000)
    out = ORCH.run_pass("2026-06-28", now=datetime(2026, 6, 28, 15, 40), live=False, verbose=False)
    _, res = out["voted"][0]
    assert res["sleeves"] == ["honmei_ev", "gap_tansho"]   # 固定順 (本命EV単 > 逆張り単)
    assert res["amount"] == 10500
    assert res["amount"] <= 12000                          # merged ≤ 合算上限 (runner番人を通る)
    legs = {l["sleeve"]: l for l in res["legs"]}
    assert legs["honmei_ev"]["amount"] == 6000 and legs["honmei_ev"]["horses"] == [1]
    assert legs["gap_tansho"]["amount"] == 4500 and legs["gap_tansho"]["horses"] == [11]


def test_orch_prod_old_5200_drops_low_priority_no_overflow(gap_on_15, honmei_on, monkeypatch, tmp_path):
    # ★§11-8 実害バグの回帰★: 旧5200のまま2スリーブ被りだと本命EV単6000+逆張り単4500=10500>5200。
    #   案A: ① 本命EV単をスリーブ別上限(=per_race_cap)で 6000→5200 に fit、 ② 逆張り単は合算超過で
    #   ★固定順に丸ごと見送り★ → merged=5200≤5200 で runner exit5(day-halt)を構造的に起こさない。
    _wire(monkeypatch, tmp_path, {"races": [_both_race()]}, per_race_cap=5200)
    out = ORCH.run_pass("2026-06-28", now=datetime(2026, 6, 28, 15, 40), live=False, verbose=False)
    _, res = out["voted"][0]
    assert res["sleeves"] == ["honmei_ev"]                 # 優先=本命EV単のみ残存 (逆張り単は見送り)
    assert res["amount"] == 5200 and res["amount"] <= 5200  # per_race_cap に fit (溢れない)
    assert [l["horses"] for l in res["legs"]] == [[1]]


def test_orch_prod_per_race_cap_boundary_exact_both(gap_on_15, honmei_on, monkeypatch, tmp_path):
    # 境界: 合算上限=10500 ちょうど → 両方 fit (6000+4500=10500≤10500)。
    _wire(monkeypatch, tmp_path, {"races": [_both_race()]}, per_race_cap=10500)
    out = ORCH.run_pass("2026-06-28", now=datetime(2026, 6, 28, 15, 40), live=False, verbose=False)
    _, res = out["voted"][0]
    assert res["amount"] == 10500 and res["sleeves"] == ["honmei_ev", "gap_tansho"]


def test_orch_prod_per_race_cap_boundary_minus_one_drops_gap(gap_on_15, honmei_on, monkeypatch, tmp_path):
    # 境界-: 合算上限=10400 (=10500-100) → 逆張り単(4500)を足すと 6000+4500=10500>10400 → 逆張り単のみ
    #   固定順で丸ごと見送り、 本命EV単(6000)だけ残る。
    _wire(monkeypatch, tmp_path, {"races": [_both_race()]}, per_race_cap=10400)
    out = ORCH.run_pass("2026-06-28", now=datetime(2026, 6, 28, 15, 40), live=False, verbose=False)
    _, res = out["voted"][0]
    assert res["sleeves"] == ["honmei_ev"] and res["amount"] == 6000


def test_orch_bet_specs_total_within_per_race_cap(gap_on_15, honmei_on, monkeypatch, tmp_path):
    # ★vote_one_race_multi に渡る bet_specs の合計 ≤ 合算上限★ (runner _check_per_race_limits を通る保証)。
    _wire(monkeypatch, tmp_path, {"races": [_both_race()]}, per_race_cap=12000)
    out = ORCH.run_pass("2026-06-28", now=datetime(2026, 6, 28, 15, 40), live=False, verbose=False)
    _, res = out["voted"][0]
    spec_total = sum(int(s.rsplit(":", 1)[1]) for s in res["bet_specs"])
    assert spec_total == res["amount"] and spec_total <= 12000


# --- resolve_per_race_cap: 合算上限=runner一致アサート / fail-safe ---

def test_read_per_race_max_yen_requires_absolute(monkeypatch):
    # runner と同条件: limit_mode != absolute なら 0 (= runner 無制限)、 absolute なら per_race_max_yen。
    monkeypatch.setattr(ORCH, "_settings",
                        lambda: {"limit_mode": "percent", "per_race_max_yen": 5200})
    assert ORCH.read_per_race_max_yen() == 0
    monkeypatch.setattr(ORCH, "_settings",
                        lambda: {"limit_mode": "absolute", "per_race_max_yen": 5200})
    assert ORCH.read_per_race_max_yen() == 5200


def test_resolve_per_race_cap_fallback_to_per_race_max(monkeypatch):
    # 専用キー未設定 → per_race_max_yen をそのまま採用 (ok=True・不一致は起きない)。
    monkeypatch.setattr(ORCH, "read_per_race_max_yen", lambda: 12000)
    monkeypatch.setattr(ORCH, "_settings", lambda: {})
    cap, ok, _src = ORCH.resolve_per_race_cap()
    assert ok is True and cap == 12000


def test_resolve_per_race_cap_match_ok(monkeypatch):
    # 専用キー == per_race_max_yen → ok=True (web は両者を同値で保存する)。
    monkeypatch.setattr(ORCH, "read_per_race_max_yen", lambda: 12000)
    monkeypatch.setattr(ORCH, "_settings", lambda: {"sleeve_per_race_cap_yen": 12000})
    cap, ok, _src = ORCH.resolve_per_race_cap()
    assert ok is True and cap == 12000


def test_resolve_per_race_cap_mismatch_failsafe(monkeypatch):
    # ★不一致 → ok=False (投票しない fail-safe)・cap は保守側(小さい方)★。
    monkeypatch.setattr(ORCH, "read_per_race_max_yen", lambda: 5200)
    monkeypatch.setattr(ORCH, "_settings", lambda: {"sleeve_per_race_cap_yen": 12000})
    cap, ok, _src = ORCH.resolve_per_race_cap()
    assert ok is False and cap == 5200


def test_orch_cap_mismatch_does_not_vote(gap_on, monkeypatch, tmp_path):
    # 合算cap と runner番人が不一致 → run_pass は ★1円も投票せず★ cap_mismatch を返す。
    monkeypatch.setattr(ORCH, "date_dir_for", lambda d: tmp_path)
    monkeypatch.setattr(ORCH, "load_predictions", lambda dd: {"races": [_gap_race()]})
    monkeypatch.setattr(ORCH, "load_post_times",
                        lambda dd, date_str=None: {"2026062805030611": "15:45"})
    monkeypatch.setattr(ORCH, "resolve_per_race_cap", lambda: (5200, False, "不一致 (test)"))
    out = ORCH.run_pass("2026-06-28", now=datetime(2026, 6, 28, 15, 40), live=False, verbose=False)
    assert out.get("cap_mismatch") is True and out["voted"] == []
