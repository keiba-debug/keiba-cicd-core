#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""runner._resolve_from_date の freebudget 優先解決テスト (Session 137 衝突解消)

--from-date は本番 freebudget_bets.json を優先し、 無ければ表示専用 selective_bets.json に
fallback する。 selective は amount 無しのため vote-mode (require_funded) で弾かれる。

Usage:
    cd keiba-v2
    python -m pytest ml/tests/test_runner_from_date.py -v
"""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from ml.target_clicker import runner


def _mkfile(root: Path, d: date, name: str) -> Path:
    p = root / "races" / f"{d.year:04d}" / f"{d.month:02d}" / f"{d.day:02d}" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{}", encoding="utf-8")
    return p


class TestFromDateResolution:
    def test_freebudget_preferred_over_selective(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KEIBA_DATA_ROOT", str(tmp_path))
        d = date(2026, 5, 30)
        _mkfile(tmp_path, d, "selective_bets.json")
        fb = _mkfile(tmp_path, d, "freebudget_bets.json")
        assert runner._resolve_from_date("2026-05-30") == fb

    def test_selective_fallback_when_no_freebudget(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KEIBA_DATA_ROOT", str(tmp_path))
        d = date(2026, 5, 30)
        sel = _mkfile(tmp_path, d, "selective_bets.json")
        assert runner._resolve_from_date("2026-05-30") == sel

    def test_neither_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("KEIBA_DATA_ROOT", str(tmp_path))
        with pytest.raises(FileNotFoundError):
            runner._resolve_from_date("2026-05-30")
