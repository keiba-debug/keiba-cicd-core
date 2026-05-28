#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""selective_loader.py の amount 検証拡張テスト (Session 134)

Session 134 で追加した:
  - ALLOWED_SOURCES に "freebudget_kelly_1q" 追加
  - SelectiveBetEntry.amount: Optional[int]
  - freebudget 系では amount 必須 + 100..1000 範囲 + 100円単位検証
  - 他 source で amount があると abort

Usage:
    cd keiba-v2
    python -m pytest ml/tests/test_selective_loader_amount.py -v
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from ml.target_clicker.selective_loader import (
    SchemaError,
    load_selective_bets,
)


def _write_json(tmp_path: Path, bets: list[dict], *,
                strategy: str = "selective",
                version: str = "2.0") -> Path:
    payload = {
        "strategy": strategy,
        "version": version,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "bets": bets,
    }
    p = tmp_path / "selective_bets.json"
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return p


def _base_freebudget_bet(**overrides) -> dict:
    bet = {
        "race_id": "2026053108010101",
        "umaban": 6,
        "horse_name": "テスト馬",
        "odds": 12.0,
        "source": "freebudget_kelly_1q",
        "amount": 300,
    }
    bet.update(overrides)
    return bet


def _base_grade_bet(**overrides) -> dict:
    bet = {
        "race_id": "2026053108010101",
        "umaban": 6,
        "horse_name": "テスト馬",
        "odds": 12.0,
        "source": "grade_top_p",
    }
    bet.update(overrides)
    return bet


class TestFreebudgetSource:

    def test_freebudget_source_accepted(self, tmp_path):
        p = _write_json(tmp_path, [_base_freebudget_bet()])
        loaded = load_selective_bets(p)
        assert len(loaded.bets) == 1
        assert loaded.bets[0].source == "freebudget_kelly_1q"
        assert loaded.bets[0].amount == 300
        assert loaded.n_freebudget_kelly_1q == 1

    def test_freebudget_missing_amount_aborts(self, tmp_path):
        bet = _base_freebudget_bet()
        del bet["amount"]
        p = _write_json(tmp_path, [bet])
        with pytest.raises(SchemaError, match="amount は int 必須"):
            load_selective_bets(p)

    def test_freebudget_amount_below_min_aborts(self, tmp_path):
        p = _write_json(tmp_path, [_base_freebudget_bet(amount=50)])
        with pytest.raises(SchemaError, match="amount 範囲外"):
            load_selective_bets(p)

    def test_freebudget_amount_above_max_aborts(self, tmp_path):
        p = _write_json(tmp_path, [_base_freebudget_bet(amount=1500)])
        with pytest.raises(SchemaError, match="amount 範囲外"):
            load_selective_bets(p)

    def test_freebudget_amount_not_100_unit_aborts(self, tmp_path):
        p = _write_json(tmp_path, [_base_freebudget_bet(amount=350)])
        with pytest.raises(SchemaError, match="100 円単位必須"):
            load_selective_bets(p)

    def test_freebudget_amount_str_aborts(self, tmp_path):
        p = _write_json(tmp_path, [_base_freebudget_bet(amount="300")])
        with pytest.raises(SchemaError, match="amount は int 必須"):
            load_selective_bets(p)


class TestNonFreebudgetSource:

    def test_grade_top_p_without_amount_accepted(self, tmp_path):
        """grade_top_p は amount なし = OK (既存 v2.0 互換)"""
        p = _write_json(tmp_path, [_base_grade_bet()])
        loaded = load_selective_bets(p)
        assert len(loaded.bets) == 1
        assert loaded.bets[0].amount is None
        assert loaded.n_grade_top_p == 1

    def test_grade_top_p_with_amount_aborts(self, tmp_path):
        """grade_top_p に amount がある = schema 違反 (誤混入防止)"""
        bet = _base_grade_bet(amount=300)
        p = _write_json(tmp_path, [bet])
        with pytest.raises(SchemaError, match="amount は source="):
            load_selective_bets(p)
