#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""settle_ledger.py + writer.record_settlement() ユニットテスト (Session 136)

money 計算の正確性 + ledger 状態遷移 + 冪等性 + provenance(payout_source/reconciled) +
🔴-2 (元返し廃止 → 配当未取得は PENDING 据え置き) を守る。

Usage:
    cd keiba-v2
    python -m pytest ml/tests/test_settle_ledger.py -v
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from ml import settle_ledger
from ml.purchase_ledger import writer


# =====================================================================
# ledger ビルダ
# =====================================================================

def _ticket(tid: str, bet_type: str, horses: list, amount: int,
            formation_type: str = "single") -> dict:
    return {
        "ticket_id": tid,
        "strategy_name": "test_strategy",
        "formation_type": formation_type,
        "pattern_label": "その他",
        "raw_legs": {"horses": horses},
        "notes": "",
        "bet_type": bet_type,
        "total_amount": amount,
        "idempotency_key": f"tk-{tid}",
        "created_at": "2026-05-30T12:00:00",
        "submitted_at": "2026-05-30T12:00:00",
    }


def _portfolio(pid: str, tickets: list) -> dict:
    return {
        "portfolio_id": pid,
        "portfolio_strategy": "test_strategy",
        "created_at": "2026-05-30T12:00:00",
        "tickets": tickets,
        "portfolio_total": sum(t["total_amount"] for t in tickets),
        "idempotency_key": f"pf-{pid}",
    }


def _ledger(date: str, races: list) -> dict:
    return {"version": 2, "date": date, "races": races, "events": []}


def _write_ledger(ledger_dir: Path, ledger: dict) -> Path:
    ledger_dir.mkdir(parents=True, exist_ok=True)
    path = ledger_dir / f"{ledger['date']}.json"
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _result(tid, payout, won, source="db"):
    return {"ticket_id": tid, "payout": payout, "won": won, "payout_source": source}


@pytest.fixture
def ledger_dir(tmp_path, monkeypatch):
    """writer / settle_ledger 両方の LEDGER_DIR を tmp に向ける"""
    d = tmp_path / "purchase_ledger"
    monkeypatch.setattr(writer, "LEDGER_DIR", d)
    monkeypatch.setattr(settle_ledger, "LEDGER_DIR", d)
    return d


# =====================================================================
# compute_payout — 券種別 払戻計算 (戻り値 = (result, status))
# =====================================================================

class TestComputePayout:
    def _caches_win(self, monkeypatch, odds_map):
        monkeypatch.setattr(settle_ledger, "get_final_win_odds",
                            lambda rid: {u: {"odds": o} for u, o in odds_map.items()})

    def _caches_place(self, monkeypatch, odds_map):
        monkeypatch.setattr(settle_ledger, "get_final_place_odds",
                            lambda rid: {u: {"odds_low": o} for u, o in odds_map.items()})

    def test_tansho_win(self, monkeypatch):
        self._caches_win(monkeypatch, {13: 3.2})
        tk = _ticket("t1", "tansho", [13], 100)
        r, st = settle_ledger.compute_payout(tk, {13: 1, 8: 2}, 16, "R", {})
        assert st == settle_ledger.ST_OK
        assert r == {"ticket_id": "t1", "payout": 320, "won": True, "payout_source": "db"}

    def test_tansho_win_500yen(self, monkeypatch):
        self._caches_win(monkeypatch, {4: 1.5})
        tk = _ticket("t1", "tansho", [4], 500)
        r, st = settle_ledger.compute_payout(tk, {4: 1}, 16, "R", {})
        assert st == settle_ledger.ST_OK and r["payout"] == 750 and r["won"] is True

    def test_tansho_lose(self, monkeypatch):
        self._caches_win(monkeypatch, {13: 3.2})
        tk = _ticket("t1", "tansho", [13], 100)
        r, st = settle_ledger.compute_payout(tk, {13: 5}, 16, "R", {})
        assert st == settle_ledger.ST_OK
        assert r == {"ticket_id": "t1", "payout": 0, "won": False, "payout_source": "db"}

    def test_tansho_pending_no_finish(self, monkeypatch):
        self._caches_win(monkeypatch, {13: 3.2})
        tk = _ticket("t1", "tansho", [13], 100)
        r, st = settle_ledger.compute_payout(tk, {13: 0}, 16, "R", {})
        assert r is None and st == settle_ledger.ST_PENDING

    def test_tansho_win_odds_missing_defers_not_motokaeshi(self, monkeypatch):
        # 🔴-2: 1着なのにオッズ取れない → 元返しせず PAYOUT_UNAVAILABLE (settle 見送り)
        self._caches_win(monkeypatch, {})
        tk = _ticket("t1", "tansho", [13], 100)
        r, st = settle_ledger.compute_payout(tk, {13: 1}, 16, "R", {})
        assert r is None and st == settle_ledger.ST_PAYOUT_UNAVAILABLE

    def test_fukusho_win(self, monkeypatch):
        self._caches_place(monkeypatch, {7: 1.5})
        tk = _ticket("t1", "fukusho", [7], 100)
        r, st = settle_ledger.compute_payout(tk, {7: 3}, 16, "R", {})
        assert st == settle_ledger.ST_OK and r["payout"] == 150 and r["won"] is True

    def test_fukusho_lose_out_of_place(self, monkeypatch):
        self._caches_place(monkeypatch, {7: 1.5})
        tk = _ticket("t1", "fukusho", [7], 100)
        r, st = settle_ledger.compute_payout(tk, {7: 4}, 16, "R", {})
        assert st == settle_ledger.ST_OK and r["payout"] == 0 and r["won"] is False

    def test_fukusho_place_limit_small_field(self, monkeypatch):
        self._caches_place(monkeypatch, {7: 1.5})
        tk = _ticket("t1", "fukusho", [7], 100)
        r, st = settle_ledger.compute_payout(tk, {7: 3}, 7, "R", {})  # 7頭=2着まで
        assert r["payout"] == 0 and r["won"] is False

    def test_fukusho_win_odds_missing_defers(self, monkeypatch):
        self._caches_place(monkeypatch, {})
        tk = _ticket("t1", "fukusho", [7], 100)
        r, st = settle_ledger.compute_payout(tk, {7: 2}, 16, "R", {})
        assert r is None and st == settle_ledger.ST_PAYOUT_UNAVAILABLE

    def test_umaren_hit(self, monkeypatch):
        monkeypatch.setattr(settle_ledger, "get_umaren_payouts", lambda rid: {(8, 13): 1230})
        tk = _ticket("t1", "umaren", [13, 8], 100)
        r, st = settle_ledger.compute_payout(tk, {13: 1, 8: 2}, 16, "R", {})
        assert st == settle_ledger.ST_OK and r["payout"] == 1230 and r["won"] is True

    def test_umaren_miss(self, monkeypatch):
        # 辞書正本: 払戻辞書は非空 (別の当たり) だが買い目キーが無い → 確定はずれ
        monkeypatch.setattr(settle_ledger, "get_umaren_payouts", lambda rid: {(1, 2): 500})
        tk = _ticket("t1", "umaren", [13, 8], 100)
        r, st = settle_ledger.compute_payout(tk, {13: 1, 8: 3}, 16, "R", {})
        assert st == settle_ledger.ST_OK and r["payout"] == 0 and r["won"] is False

    def test_umaren_empty_table_defers(self, monkeypatch):
        # 辞書が空 (DB 払戻未取得/結果未確定) → settle 見送り
        monkeypatch.setattr(settle_ledger, "get_umaren_payouts", lambda rid: {})
        tk = _ticket("t1", "umaren", [13, 8], 100)
        r, st = settle_ledger.compute_payout(tk, {13: 1, 8: 2}, 16, "R", {})
        assert r is None and st == settle_ledger.ST_PAYOUT_UNAVAILABLE

    def test_wide_hit_both_in_place(self, monkeypatch):
        monkeypatch.setattr(settle_ledger, "get_wide_payouts", lambda rid: {(8, 13): 450})
        tk = _ticket("t1", "wide", [13, 8], 200)
        r, st = settle_ledger.compute_payout(tk, {13: 1, 8: 3}, 16, "R", {})
        assert r["payout"] == 900 and r["won"] is True  # 200/100*450

    def test_wide_miss(self, monkeypatch):
        # 辞書非空だが買い目キー無し → はずれ (ワイドは複数当たりだが買い目はそのどれでもない)
        monkeypatch.setattr(settle_ledger, "get_wide_payouts",
                            lambda rid: {(1, 2): 300, (1, 3): 400, (2, 3): 350})
        tk = _ticket("t1", "wide", [13, 8], 200)
        r, st = settle_ledger.compute_payout(tk, {13: 1, 8: 4}, 16, "R", {})
        assert r["payout"] == 0 and r["won"] is False

    def test_umatan_hit_exact_order(self, monkeypatch):
        monkeypatch.setattr(settle_ledger, "get_umatan_payouts", lambda rid: {(17, 11): 2500})
        tk = _ticket("t1", "umatan", [17, 11], 100)  # 17→1着, 11→2着
        r, st = settle_ledger.compute_payout(tk, {17: 1, 11: 2}, 16, "R", {})
        assert r["payout"] == 2500 and r["won"] is True

    def test_umatan_miss_wrong_order(self, monkeypatch):
        # 実際の決着は 11→17 (辞書キー (11,17))。 買い目 [17,11]=(17,11) は順序違いで辞書に無い → はずれ
        monkeypatch.setattr(settle_ledger, "get_umatan_payouts", lambda rid: {(11, 17): 2500})
        tk = _ticket("t1", "umatan", [17, 11], 100)
        r, st = settle_ledger.compute_payout(tk, {17: 2, 11: 1}, 16, "R", {})
        assert r["payout"] == 0 and r["won"] is False

    def test_sanrenpuku_hit(self, monkeypatch):
        monkeypatch.setattr(settle_ledger, "get_sanrenpuku_payouts",
                            lambda rid: {(3, 8, 13): 4500})
        tk = _ticket("t1", "sanrenpuku", [13, 3, 8], 100)
        # 13,3,8 が1,2,3着 (順不同)
        r, st = settle_ledger.compute_payout(tk, {13: 1, 3: 2, 8: 3}, 16, "R", {})
        assert st == settle_ledger.ST_OK and r["payout"] == 4500 and r["won"] is True

    def test_sanrenpuku_miss(self, monkeypatch):
        # 辞書非空だが買い目キー (3,8,13) が無い → はずれ
        monkeypatch.setattr(settle_ledger, "get_sanrenpuku_payouts",
                            lambda rid: {(1, 2, 3): 9000})
        tk = _ticket("t1", "sanrenpuku", [13, 3, 8], 100)
        r, st = settle_ledger.compute_payout(tk, {13: 1, 3: 2, 8: 4}, 16, "R", {})
        assert r["payout"] == 0 and r["won"] is False

    def test_sanrentan_hit_exact_order(self, monkeypatch):
        monkeypatch.setattr(settle_ledger, "get_sanrentan_payouts",
                            lambda rid: {(13, 3, 8): 28900})
        tk = _ticket("t1", "sanrentan", [13, 3, 8], 100)  # 13→3→8 の順
        r, st = settle_ledger.compute_payout(tk, {13: 1, 3: 2, 8: 3}, 16, "R", {})
        assert st == settle_ledger.ST_OK and r["payout"] == 28900 and r["won"] is True

    def test_sanrentan_miss_wrong_order(self, monkeypatch):
        # 決着は 3→13→8 (辞書キー (3,13,8))。 買い目 [13,3,8]=(13,3,8) は辞書に無い → はずれ
        monkeypatch.setattr(settle_ledger, "get_sanrentan_payouts",
                            lambda rid: {(3, 13, 8): 28900})
        tk = _ticket("t1", "sanrentan", [13, 3, 8], 100)
        r, st = settle_ledger.compute_payout(tk, {13: 2, 3: 1, 8: 3}, 16, "R", {})
        assert r["payout"] == 0 and r["won"] is False

    def test_sanrentan_empty_table_defers(self, monkeypatch):
        monkeypatch.setattr(settle_ledger, "get_sanrentan_payouts", lambda rid: {})
        tk = _ticket("t1", "sanrentan", [13, 3, 8], 100)
        r, st = settle_ledger.compute_payout(tk, {13: 1, 3: 2, 8: 3}, 16, "R", {})
        assert r is None and st == settle_ledger.ST_PAYOUT_UNAVAILABLE

    def test_sanrentan_dead_heat_hit(self, monkeypatch):
        # 🔴修正の核心: 2-3着同着。 JRA は 13→8→3 と 13→3→8 を両方的中扱いし haraimodoshi に両組載る。
        # 旧実装 (f1==1&f2==2&f3==3 厳密一致) は f3=2 (同着) で両方取りこぼした。
        # 辞書正本なら買い目が辞書に載っていれば的中 = 同着を正しく拾う。
        monkeypatch.setattr(settle_ledger, "get_sanrentan_payouts",
                            lambda rid: {(13, 8, 3): 15000, (13, 3, 8): 15000})
        tk = _ticket("t1", "sanrentan", [13, 8, 3], 100)
        # 着順は 13=1着, 8=2着(同着), 3=2着(同着) — f3 が 3 でなくても的中
        r, st = settle_ledger.compute_payout(tk, {13: 1, 8: 2, 3: 2}, 16, "R", {})
        assert st == settle_ledger.ST_OK and r["payout"] == 15000 and r["won"] is True

    def test_umaren_dead_heat_hit(self, monkeypatch):
        # 1着同着で馬連が2組当たるケースも辞書正本で拾える
        monkeypatch.setattr(settle_ledger, "get_umaren_payouts",
                            lambda rid: {(5, 8): 1200, (5, 13): 1300, (8, 13): 1400})
        tk = _ticket("t1", "umaren", [5, 8], 100)
        # 5,8 が1着同着 (set判定なら {1,1}!={1,2} で旧実装は取りこぼし)
        r, st = settle_ledger.compute_payout(tk, {5: 1, 8: 1}, 16, "R", {})
        assert st == settle_ledger.ST_OK and r["payout"] == 1200 and r["won"] is True

    def test_unsupported_bet_type(self, monkeypatch):
        # sanrentan でも formation_type が single でなければ未対応
        tk = _ticket("t1", "sanrentan", [1, 2, 3], 100, formation_type="formation")
        r, st = settle_ledger.compute_payout(tk, {1: 1, 2: 2, 3: 3}, 16, "R", {})
        assert r is None and st == settle_ledger.ST_UNSUPPORTED

    def test_non_single_formation(self):
        tk = _ticket("t1", "umaren", [8, 13], 100, formation_type="box")
        r, st = settle_ledger.compute_payout(tk, {8: 1, 13: 2}, 16, "R", {})
        assert r is None and st == settle_ledger.ST_UNSUPPORTED

    def test_raw_legs_without_horses(self):
        tk = _ticket("t1", "tansho", [], 100)
        tk["raw_legs"] = {"box": [1, 2]}
        r, st = settle_ledger.compute_payout(tk, {1: 1}, 16, "R", {})
        assert r is None and st == settle_ledger.ST_INVALID

    def test_two_horse_type_needs_two_legs(self, monkeypatch):
        monkeypatch.setattr(settle_ledger, "get_umaren_payouts", lambda rid: {})
        tk = _ticket("t1", "umaren", [8], 100)
        r, st = settle_ledger.compute_payout(tk, {8: 1}, 16, "R", {})
        assert r is None and st == settle_ledger.ST_INVALID


# =====================================================================
# record_settlement — ledger 書き込み・状態遷移・冪等性・provenance
# =====================================================================

class TestRecordSettlement:
    def test_settles_ticket_and_writes_payout(self, ledger_dir):
        led = _ledger("2026-05-30", [
            {"race_id": "2026053005020111", "state": "SUBMITTED",
             "portfolios": [_portfolio("pf-A", [_ticket("pf-A#t1", "tansho", [13], 100)])]},
        ])
        _write_ledger(ledger_dir, led)

        res = writer.record_settlement(date="2026-05-30", results=[_result("pf-A#t1", 320, True)])
        assert res.success and res.settled_tickets == 1 and res.won_tickets == 1
        assert res.total_payout == 320 and res.races_settled == 1

        saved = json.loads((ledger_dir / "2026-05-30.json").read_text(encoding="utf-8"))
        tk = saved["races"][0]["portfolios"][0]["tickets"][0]
        assert tk["payout"] == 320 and tk["settled_at"]
        assert tk["payout_source"] == "db" and tk["reconciled"] is False  # 🔴-1 provenance
        pf = saved["races"][0]["portfolios"][0]
        assert pf["portfolio_pnl"] == 220 and pf["portfolio_roi"] == 3.2
        assert saved["races"][0]["state"] == "SETTLED"
        settled_events = [e for e in saved["events"] if e["type"] == "SETTLED"]
        assert len(settled_events) == 1
        assert settled_events[0]["payload"]["payout"] == 320
        assert settled_events[0]["payload"]["portfolio_pnl"] == 220
        assert settled_events[0]["payload"]["reconciled"] is False
        assert settled_events[0]["payload"]["source"] == "db_payout_pre_reconcile"

    def test_reconciled_true_writes_confirmed_provenance(self, ledger_dir):
        led = _ledger("2026-05-30", [
            {"race_id": "2026053005020111", "state": "SUBMITTED",
             "portfolios": [_portfolio("pf-A", [_ticket("pf-A#t1", "tansho", [13], 100)])]},
        ])
        _write_ledger(ledger_dir, led)
        writer.record_settlement(date="2026-05-30", results=[_result("pf-A#t1", 320, True)],
                                 reconciled=True)
        saved = json.loads((ledger_dir / "2026-05-30.json").read_text(encoding="utf-8"))
        tk = saved["races"][0]["portfolios"][0]["tickets"][0]
        assert tk["reconciled"] is True
        ev = [e for e in saved["events"] if e["type"] == "SETTLED"][0]
        assert ev["payload"]["source"] == "db_payout_reconciled"

    def test_lose_ticket_pnl_negative(self, ledger_dir):
        led = _ledger("2026-05-30", [
            {"race_id": "2026053005020111", "state": "SUBMITTED",
             "portfolios": [_portfolio("pf-A", [_ticket("pf-A#t1", "tansho", [13], 500)])]},
        ])
        _write_ledger(ledger_dir, led)
        res = writer.record_settlement(date="2026-05-30", results=[_result("pf-A#t1", 0, False)])
        assert res.success and res.won_tickets == 0
        saved = json.loads((ledger_dir / "2026-05-30.json").read_text(encoding="utf-8"))
        pf = saved["races"][0]["portfolios"][0]
        assert pf["portfolio_pnl"] == -500 and pf["portfolio_roi"] == 0.0

    def test_partial_race_stays_submitted(self, ledger_dir):
        led = _ledger("2026-05-30", [
            {"race_id": "2026053005020111", "state": "SUBMITTED",
             "portfolios": [
                 _portfolio("pf-A", [_ticket("pf-A#t1", "tansho", [13], 100)]),
                 _portfolio("pf-B", [_ticket("pf-B#t1", "tansho", [4], 100)]),
             ]},
        ])
        _write_ledger(ledger_dir, led)
        res = writer.record_settlement(date="2026-05-30", results=[_result("pf-A#t1", 320, True)])
        assert res.settled_tickets == 1 and res.races_settled == 0
        saved = json.loads((ledger_dir / "2026-05-30.json").read_text(encoding="utf-8"))
        assert saved["races"][0]["state"] == "SUBMITTED"

    def test_idempotent_no_force(self, ledger_dir):
        led = _ledger("2026-05-30", [
            {"race_id": "2026053005020111", "state": "SUBMITTED",
             "portfolios": [_portfolio("pf-A", [_ticket("pf-A#t1", "tansho", [13], 100)])]},
        ])
        _write_ledger(ledger_dir, led)
        r1 = writer.record_settlement(date="2026-05-30", results=[_result("pf-A#t1", 320, True)])
        r2 = writer.record_settlement(date="2026-05-30", results=[_result("pf-A#t1", 320, True)])
        assert r1.settled_tickets == 1 and r2.settled_tickets == 0
        saved = json.loads((ledger_dir / "2026-05-30.json").read_text(encoding="utf-8"))
        assert len([e for e in saved["events"] if e["type"] == "SETTLED"]) == 1

    def test_force_resettle_updates(self, ledger_dir):
        led = _ledger("2026-05-30", [
            {"race_id": "2026053005020111", "state": "SUBMITTED",
             "portfolios": [_portfolio("pf-A", [_ticket("pf-A#t1", "tansho", [13], 100)])]},
        ])
        _write_ledger(ledger_dir, led)
        writer.record_settlement(date="2026-05-30", results=[_result("pf-A#t1", 320, True)])
        r = writer.record_settlement(date="2026-05-30", results=[_result("pf-A#t1", 360, True)],
                                     force=True)
        assert r.settled_tickets == 1
        saved = json.loads((ledger_dir / "2026-05-30.json").read_text(encoding="utf-8"))
        tk = saved["races"][0]["portfolios"][0]["tickets"][0]
        assert tk["payout"] == 360
        assert saved["races"][0]["portfolios"][0]["portfolio_pnl"] == 260

    def test_force_resettle_reconciled_upgrade(self, ledger_dir):
        # 暫定 settle → 後で reconciled=True で確定 settle (force)
        led = _ledger("2026-05-30", [
            {"race_id": "2026053005020111", "state": "SUBMITTED",
             "portfolios": [_portfolio("pf-A", [_ticket("pf-A#t1", "tansho", [13], 100)])]},
        ])
        _write_ledger(ledger_dir, led)
        writer.record_settlement(date="2026-05-30", results=[_result("pf-A#t1", 320, True)],
                                 reconciled=False)
        writer.record_settlement(date="2026-05-30", results=[_result("pf-A#t1", 320, True)],
                                 force=True, reconciled=True)
        saved = json.loads((ledger_dir / "2026-05-30.json").read_text(encoding="utf-8"))
        assert saved["races"][0]["portfolios"][0]["tickets"][0]["reconciled"] is True

    def test_ledger_not_found(self, ledger_dir):
        res = writer.record_settlement(date="2026-01-01", results=[])
        assert res.success is False and "not found" in res.reason

    def test_multi_ticket_portfolio_pnl(self, ledger_dir):
        led = _ledger("2026-05-30", [
            {"race_id": "2026053005020111", "state": "SUBMITTED",
             "portfolios": [_portfolio("pf-A", [
                 _ticket("pf-A#t1", "tansho", [13], 100),
                 _ticket("pf-A#t2", "fukusho", [13], 100),
             ])]},
        ])
        _write_ledger(ledger_dir, led)
        res = writer.record_settlement(date="2026-05-30",
                                       results=[_result("pf-A#t1", 320, True),
                                                _result("pf-A#t2", 150, True)])
        assert res.settled_tickets == 2
        saved = json.loads((ledger_dir / "2026-05-30.json").read_text(encoding="utf-8"))
        pf = saved["races"][0]["portfolios"][0]
        assert pf["portfolio_pnl"] == 470 - 200
        assert pf["portfolio_roi"] == round(470 / 200, 4)

    def test_superseded_portfolio_excluded(self, ledger_dir):
        # シズネ 🟡-2 恒久ガード: 修復で superseded にした旧 portfolio は精算・集計対象外。
        # この除外が壊れると二重計上 (税務 SoT 過大計上) になるため回帰でロックする。
        led = _ledger("2026-05-30", [
            {"race_id": "2026053008031104", "state": "SUBMITTED", "portfolios": [
                {**_portfolio("pf-A", [_ticket("pf-A#t1", "tansho", [13], 100)]),
                 "superseded_by_repair": True},
                _portfolio("pf-B", [_ticket("pf-B#t1", "umatan", [13, 17], 100)]),
            ]},
        ])
        _write_ledger(ledger_dir, led)
        res = writer.record_settlement(
            date="2026-05-30", results=[_result("pf-B#t1", 1090, True)])
        assert res.settled_tickets == 1 and res.total_payout == 1090
        saved = json.loads((ledger_dir / "2026-05-30.json").read_text(encoding="utf-8"))
        pfs = {p["portfolio_id"]: p for p in saved["races"][0]["portfolios"]}
        # superseded は一切触られない (settled_at なし、 pnl 再計算なし)
        assert pfs["pf-A"]["tickets"][0].get("settled_at") is None
        assert "portfolio_pnl" not in pfs["pf-A"]
        # active のみ精算され race は SETTLED (superseded を残 ticket と数えない)
        assert pfs["pf-B"]["portfolio_pnl"] == 990
        assert saved["races"][0]["state"] == "SETTLED"
        # SETTLED イベントは active portfolio の 1 件のみ
        assert len([e for e in saved["events"] if e["type"] == "SETTLED"]) == 1


# =====================================================================
# settle() — DB をモックした end-to-end
# =====================================================================

class TestSettleEndToEnd:
    def test_settle_full_flow(self, ledger_dir, monkeypatch):
        led = _ledger("2026-05-30", [
            {"race_id": "2026053005020111", "state": "SUBMITTED",
             "portfolios": [
                 _portfolio("pf-A", [_ticket("pf-A#t1", "tansho", [13], 100)]),
                 _portfolio("pf-B", [_ticket("pf-B#t1", "tansho", [4], 200)]),
             ]},
        ])
        _write_ledger(ledger_dir, led)
        monkeypatch.setattr(settle_ledger, "get_finish_positions",
                            lambda rid, rd: ({13: 1, 4: 5}, 16))
        monkeypatch.setattr(settle_ledger, "get_final_win_odds",
                            lambda rid: {13: {"odds": 3.2}, 4: {"odds": 8.0}})

        out = settle_ledger.settle("2026-05-30")
        assert out["success"] and out["settled"] == 2 and out["won"] == 1
        assert out["total_payout"] == 320 and out["races_settled"] == 1
        assert out["reconciled"] is False and out["payout_unavailable"] == 0
        saved = json.loads((ledger_dir / "2026-05-30.json").read_text(encoding="utf-8"))
        assert saved["races"][0]["state"] == "SETTLED"
        assert saved["races"][0]["portfolios"][0]["tickets"][0]["payout_source"] == "db"

    def test_settle_pending_race_not_settled(self, ledger_dir, monkeypatch):
        led = _ledger("2026-05-30", [
            {"race_id": "2026053005020112", "state": "SUBMITTED",
             "portfolios": [_portfolio("pf-A", [_ticket("pf-A#t1", "tansho", [9], 100)])]},
        ])
        _write_ledger(ledger_dir, led)
        monkeypatch.setattr(settle_ledger, "get_finish_positions", lambda rid, rd: ({}, 18))
        out = settle_ledger.settle("2026-05-30")
        assert out["settled"] == 0 and out["pending"] == 1
        saved = json.loads((ledger_dir / "2026-05-30.json").read_text(encoding="utf-8"))
        assert saved["races"][0]["state"] == "SUBMITTED"
        assert saved["races"][0]["portfolios"][0]["tickets"][0].get("settled_at") is None

    def test_settle_payout_unavailable_defers(self, ledger_dir, monkeypatch):
        # 🔴-2: 着順は確定(13番1着)だがオッズDBが空 → settle されず PENDING 据え置き
        led = _ledger("2026-05-30", [
            {"race_id": "2026053005020111", "state": "SUBMITTED",
             "portfolios": [_portfolio("pf-A", [_ticket("pf-A#t1", "tansho", [13], 100)])]},
        ])
        _write_ledger(ledger_dir, led)
        monkeypatch.setattr(settle_ledger, "get_finish_positions",
                            lambda rid, rd: ({13: 1}, 16))
        monkeypatch.setattr(settle_ledger, "get_final_win_odds", lambda rid: {})  # 配当取れない
        out = settle_ledger.settle("2026-05-30")
        assert out["settled"] == 0 and out["payout_unavailable"] == 1
        saved = json.loads((ledger_dir / "2026-05-30.json").read_text(encoding="utf-8"))
        assert saved["races"][0]["state"] == "SUBMITTED"  # 据え置き
        assert saved["races"][0]["portfolios"][0]["tickets"][0].get("settled_at") is None
        # 元返し(payout=100)が書かれていないことを確認 (税務SoTに暫定値を入れない)
        assert "payout" not in saved["races"][0]["portfolios"][0]["tickets"][0]

    def test_settle_dry_run_no_write(self, ledger_dir, monkeypatch):
        led = _ledger("2026-05-30", [
            {"race_id": "2026053005020111", "state": "SUBMITTED",
             "portfolios": [_portfolio("pf-A", [_ticket("pf-A#t1", "tansho", [13], 100)])]},
        ])
        _write_ledger(ledger_dir, led)
        monkeypatch.setattr(settle_ledger, "get_finish_positions",
                            lambda rid, rd: ({13: 1}, 16))
        monkeypatch.setattr(settle_ledger, "get_final_win_odds", lambda rid: {13: {"odds": 3.2}})
        out = settle_ledger.settle("2026-05-30", dry_run=True)
        assert out["dry_run"] and out["computed"] == 1 and out["total_payout"] == 320
        saved = json.loads((ledger_dir / "2026-05-30.json").read_text(encoding="utf-8"))
        assert saved["races"][0]["state"] == "SUBMITTED"
        assert saved["races"][0]["portfolios"][0]["tickets"][0].get("settled_at") is None

    def test_settle_skips_superseded(self, ledger_dir, monkeypatch):
        # シズネ 🟡-2: settle_ledger.settle が superseded portfolio を再精算しない
        led = _ledger("2026-05-30", [
            {"race_id": "2026053008031104", "state": "SUBMITTED", "portfolios": [
                {**_portfolio("pf-A", [_ticket("pf-A#t1", "tansho", [13], 100)]),
                 "superseded_by_repair": True},
                _portfolio("pf-B", [_ticket("pf-B#t1", "tansho", [9], 200)]),
            ]},
        ])
        _write_ledger(ledger_dir, led)
        monkeypatch.setattr(settle_ledger, "get_finish_positions",
                            lambda rid, rd: ({13: 1, 9: 5}, 16))
        monkeypatch.setattr(settle_ledger, "get_final_win_odds",
                            lambda rid: {13: {"odds": 3.2}, 9: {"odds": 8.0}})
        out = settle_ledger.settle("2026-05-30")
        # superseded の pf-A (馬番13) は settle されず、 active の pf-B (馬番9) のみ精算
        assert out["settled"] == 1
        saved = json.loads((ledger_dir / "2026-05-30.json").read_text(encoding="utf-8"))
        pfs = {p["portfolio_id"]: p for p in saved["races"][0]["portfolios"]}
        assert pfs["pf-A"]["tickets"][0].get("settled_at") is None
        assert pfs["pf-B"]["tickets"][0].get("settled_at") is not None

    def test_settle_reconciled_flag_propagates(self, ledger_dir, monkeypatch):
        led = _ledger("2026-05-30", [
            {"race_id": "2026053005020111", "state": "SUBMITTED",
             "portfolios": [_portfolio("pf-A", [_ticket("pf-A#t1", "tansho", [13], 100)])]},
        ])
        _write_ledger(ledger_dir, led)
        monkeypatch.setattr(settle_ledger, "get_finish_positions",
                            lambda rid, rd: ({13: 1}, 16))
        monkeypatch.setattr(settle_ledger, "get_final_win_odds", lambda rid: {13: {"odds": 3.2}})
        out = settle_ledger.settle("2026-05-30", reconciled=True)
        assert out["reconciled"] is True
        saved = json.loads((ledger_dir / "2026-05-30.json").read_text(encoding="utf-8"))
        assert saved["races"][0]["portfolios"][0]["tickets"][0]["reconciled"] is True

    def test_settle_missing_ledger_returns_error(self, ledger_dir):
        # 非開催日/未投票日 = ledger 無し → settle() は error("not found")。
        # 自動化バッチ (main) はこれを no-op skip 扱いにする (exit 0)。
        out = settle_ledger.settle("2026-01-01")
        assert "error" in out and "not found" in out["error"]


# =====================================================================
# _resolve_dates — 自動化バッチ用の対象日解決 (--today / --catchup-days)
# =====================================================================

class TestResolveDates:
    def test_base_only_no_catchup(self):
        assert settle_ledger._resolve_dates("2026-05-30", 0) == ["2026-05-30"]

    def test_catchup_descending(self):
        # 基準日を含み新しい順 (catch-up は前日確定の遅延払戻を翌日 run で拾う)
        assert settle_ledger._resolve_dates("2026-05-30", 2) == [
            "2026-05-30", "2026-05-29", "2026-05-28",
        ]

    def test_catchup_crosses_month_year_boundary(self):
        assert settle_ledger._resolve_dates("2026-01-01", 1) == [
            "2026-01-01", "2025-12-31",
        ]

    def test_negative_catchup_treated_as_zero(self):
        assert settle_ledger._resolve_dates("2026-05-30", -3) == ["2026-05-30"]
