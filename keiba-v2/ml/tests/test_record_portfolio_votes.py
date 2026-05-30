#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""record_portfolio_votes / record_vote / record_tansho_vote ユニットテスト (Session 136)

本治療の検証: 全券種を実 bet_type + 全馬番で記録し、 idempotency 衝突による
過少記録 (Session 135 recorded=3/11) が起きないこと。

Usage:
    cd keiba-v2
    python -m pytest ml/tests/test_record_portfolio_votes.py -v
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from ml.purchase_ledger import writer


RACE = "2026053008031111"  # 京都11R


@pytest.fixture
def ledger_dir(tmp_path, monkeypatch):
    d = tmp_path / "purchase_ledger"
    monkeypatch.setattr(writer, "LEDGER_DIR", d)
    return d


def _load(ledger_dir):
    return json.loads((ledger_dir / "2026-05-30.json").read_text(encoding="utf-8"))


def _all_tickets(ledger):
    return [t for r in ledger["races"] for pf in r["portfolios"] for t in pf["tickets"]]


# =====================================================================
# record_portfolio_votes — 多券種を 1 portfolio に N 枚
# =====================================================================

class TestRecordPortfolioVotes:
    def test_all_seven_bet_types_recorded_no_collision(self, ledger_dir):
        """全7券種 11 点を投票 → 11 枚すべて記録される (過少記録 3/11 の再発防止)"""
        tickets = [
            {"bet_type": "tansho", "horses": [5], "amount": 100},
            {"bet_type": "fukusho", "horses": [5], "amount": 100},
            {"bet_type": "umaren", "horses": [5, 2], "amount": 100},
            {"bet_type": "umaren", "horses": [5, 3], "amount": 100},   # 同じ 5 始まりでも別買い目
            {"bet_type": "wide", "horses": [5, 2], "amount": 100},
            {"bet_type": "wide", "horses": [5, 3], "amount": 100},
            {"bet_type": "umatan", "horses": [5, 2], "amount": 100},
            {"bet_type": "umatan", "horses": [2, 5], "amount": 100},   # 順序違いも別
            {"bet_type": "sanrenpuku", "horses": [5, 2, 3], "amount": 100},
            {"bet_type": "sanrentan", "horses": [5, 2, 3], "amount": 100},
            {"bet_type": "sanrentan", "horses": [5, 3, 2], "amount": 100},  # 順序違いも別
        ]
        res = writer.record_portfolio_votes(
            race_id=RACE, portfolio_strategy="manual_cli", tickets=tickets,
            receipt_number="0010", clicked_at="2026-05-30T15:00:00")
        assert res.success and res.action == "recorded"

        ledger = _load(ledger_dir)
        all_tk = _all_tickets(ledger)
        assert len(all_tk) == 11, f"11点全記録のはずが {len(all_tk)}"
        # idempotency_key が全部ユニーク (衝突なし)
        keys = {t["idempotency_key"] for t in all_tk}
        assert len(keys) == 11, "idempotency_key が衝突している"
        # bet_type が正しく保持されている
        bt = sorted(t["bet_type"] for t in all_tk)
        assert bt.count("umaren") == 2 and bt.count("sanrentan") == 2
        # 2頭/3頭の馬番が保持されている
        umatan = [t for t in all_tk if t["bet_type"] == "umatan"]
        assert {tuple(t["raw_legs"]["horses"]) for t in umatan} == {(5, 2), (2, 5)}
        sant = [t for t in all_tk if t["bet_type"] == "sanrentan"]
        assert {tuple(t["raw_legs"]["horses"]) for t in sant} == {(5, 2, 3), (5, 3, 2)}

    def test_single_portfolio_with_n_tickets(self, ledger_dir):
        """1 意思決定 = 1 portfolio に N 枚 (バラバラの portfolio にしない)"""
        tickets = [
            {"bet_type": "tansho", "horses": [5], "amount": 100},
            {"bet_type": "wide", "horses": [5, 8], "amount": 200},
        ]
        writer.record_portfolio_votes(race_id=RACE, portfolio_strategy="manual_cli",
                                      tickets=tickets, receipt_number="0010")
        ledger = _load(ledger_dir)
        assert len(ledger["races"]) == 1
        assert len(ledger["races"][0]["portfolios"]) == 1
        pf = ledger["races"][0]["portfolios"][0]
        assert len(pf["tickets"]) == 2
        assert pf["portfolio_total"] == 300
        assert pf["tickets"][0]["ticket_id"].endswith("#t1")
        assert pf["tickets"][1]["ticket_id"].endswith("#t2")

    def test_ipat_confirmed_event_once_per_portfolio(self, ledger_dir):
        tickets = [
            {"bet_type": "tansho", "horses": [5], "amount": 100},
            {"bet_type": "tansho", "horses": [8], "amount": 100},
        ]
        writer.record_portfolio_votes(race_id=RACE, portfolio_strategy="manual_cli",
                                      tickets=tickets, receipt_number="0010")
        ledger = _load(ledger_dir)
        ipat = [e for e in ledger["events"] if e["type"] == "IPAT_CONFIRMED"]
        assert len(ipat) == 1  # portfolio 単位で 1 回
        ff = [e for e in ledger["events"] if e["type"] == "FF_WRITTEN"]
        assert ff[0]["payload"]["count"] == 2 and ff[0]["payload"]["amount"] == 200

    def test_duplicate_portfolio_skipped(self, ledger_dir):
        tickets = [{"bet_type": "umaren", "horses": [5, 8], "amount": 100}]
        r1 = writer.record_portfolio_votes(race_id=RACE, portfolio_strategy="manual_cli",
                                           tickets=tickets)
        r2 = writer.record_portfolio_votes(race_id=RACE, portfolio_strategy="manual_cli",
                                           tickets=tickets)
        assert r1.action == "recorded" and r2.action == "duplicate"
        assert len(_all_tickets(_load(ledger_dir))) == 1

    def test_umaren_order_insensitive_dedup(self, ledger_dir):
        """馬連 5-8 と 8-5 は同一買い目 → 2回目は duplicate"""
        r1 = writer.record_portfolio_votes(
            race_id=RACE, portfolio_strategy="manual_cli",
            tickets=[{"bet_type": "umaren", "horses": [5, 8], "amount": 100}])
        r2 = writer.record_portfolio_votes(
            race_id=RACE, portfolio_strategy="manual_cli",
            tickets=[{"bet_type": "umaren", "horses": [8, 5], "amount": 100}])
        assert r1.action == "recorded" and r2.action == "duplicate"

    def test_different_strategy_separate_portfolio(self, ledger_dir):
        """同一レースでも strategy が違えば別 portfolio (14 §3.1.3)"""
        writer.record_portfolio_votes(
            race_id=RACE, portfolio_strategy="selective_v3_freebudget_kelly_1q",
            tickets=[{"bet_type": "tansho", "horses": [5], "amount": 100}])
        writer.record_portfolio_votes(
            race_id=RACE, portfolio_strategy="manual_cli",
            tickets=[{"bet_type": "tansho", "horses": [5], "amount": 100}])
        ledger = _load(ledger_dir)
        assert len(ledger["races"][0]["portfolios"]) == 2

    # --- バリデーション ---
    def test_wrong_horse_count_rejected(self, ledger_dir):
        r = writer.record_portfolio_votes(
            race_id=RACE, portfolio_strategy="manual_cli",
            tickets=[{"bet_type": "umaren", "horses": [5], "amount": 100}])  # 馬連は2頭
        assert r.success is False and "expects 2" in r.reason

    def test_sanrentan_needs_three(self, ledger_dir):
        r = writer.record_portfolio_votes(
            race_id=RACE, portfolio_strategy="manual_cli",
            tickets=[{"bet_type": "sanrentan", "horses": [5, 8], "amount": 100}])
        assert r.success is False and "expects 3" in r.reason

    def test_unknown_bet_type_rejected(self, ledger_dir):
        r = writer.record_portfolio_votes(
            race_id=RACE, portfolio_strategy="manual_cli",
            tickets=[{"bet_type": "exotic", "horses": [5], "amount": 100}])
        assert r.success is False and "invalid bet_type" in r.reason

    def test_empty_tickets_rejected(self, ledger_dir):
        r = writer.record_portfolio_votes(race_id=RACE, portfolio_strategy="m", tickets=[])
        assert r.success is False and "empty" in r.reason

    def test_invalid_amount_rejected(self, ledger_dir):
        r = writer.record_portfolio_votes(
            race_id=RACE, portfolio_strategy="manual_cli",
            tickets=[{"bet_type": "tansho", "horses": [5], "amount": 0}])
        assert r.success is False and "invalid amount" in r.reason


# =====================================================================
# record_vote / record_tansho_vote — 後方互換ラッパ
# =====================================================================

class TestWrappers:
    def test_record_vote_single(self, ledger_dir):
        r = writer.record_vote(race_id=RACE, bet_type="umatan", horses=[5, 8],
                               amount=200, strategy_name="manual_cli")
        assert r.success and r.action == "recorded"
        tk = _all_tickets(_load(ledger_dir))[0]
        assert tk["bet_type"] == "umatan" and tk["raw_legs"]["horses"] == [5, 8]
        assert tk["total_amount"] == 200

    def test_record_tansho_vote_backward_compat(self, ledger_dir):
        r = writer.record_tansho_vote(race_id=RACE, umaban=7, amount=300,
                                      strategy_name="selective_v3_freebudget_kelly_1q",
                                      ev_at_decision=1.97, receipt_number="0004")
        assert r.success and r.action == "recorded"
        tk = _all_tickets(_load(ledger_dir))[0]
        assert tk["bet_type"] == "tansho" and tk["raw_legs"]["horses"] == [7]
        assert tk["ev_at_decision"] == 1.97 and tk["ipat_receipt_number"] == "0004"

    def test_record_tansho_vote_invalid_umaban(self, ledger_dir):
        r = writer.record_tansho_vote(race_id=RACE, umaban=0, amount=100,
                                      strategy_name="m")
        assert r.success is False and "invalid umaban" in r.reason
