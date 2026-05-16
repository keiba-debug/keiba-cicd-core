#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ml/utils/segments.py ユニットテスト"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

pd = pytest.importorskip("pandas")

from ml.utils.segments import (
    bin_odds, bin_runners, bin_gap, bin_ev, bin_closing_strength,
    bin_distance, bin_ard, bin_novelty, bin_confidence,
    race_id_to_date, race_id_to_month, bin_month,
    is_handicap,
    ODDS_LABELS, RUNNER_LABELS, GAP_LABELS, EV_LABELS,
)


class TestBinOdds:
    def test_low(self):
        s = pd.Series([1.5, 2.9, 3.0])
        out = bin_odds(s)
        assert all(str(x) == "~3.0" for x in out)

    def test_mid(self):
        s = pd.Series([3.5, 5.0])
        out = bin_odds(s)
        assert all(str(x) == "3.1~5.0" for x in out)

    def test_high(self):
        s = pd.Series([100.0, 50.5])
        out = bin_odds(s)
        assert all(str(x) == "50+" for x in out)

    def test_labels_match(self):
        s = pd.Series([2.0, 4.0, 7.5, 15.0, 35.0, 80.0])
        out = bin_odds(s).astype(str).tolist()
        assert out == ODDS_LABELS


class TestBinRunners:
    def test_each_band(self):
        s = pd.Series([5, 10, 14, 18])
        out = bin_runners(s).astype(str).tolist()
        assert out == RUNNER_LABELS


class TestBinGap:
    def test_each_band(self):
        s = pd.Series([1, 3, 5, 7, 10])
        out = bin_gap(s).astype(str).tolist()
        assert out == GAP_LABELS


class TestBinEV:
    def test_each_band(self):
        s = pd.Series([0.3, 0.7, 0.9, 1.1, 1.4, 1.7, 3.0])
        out = bin_ev(s).astype(str).tolist()
        assert out == EV_LABELS


class TestRaceIdHelpers:
    def test_to_date(self):
        assert race_id_to_date("2026012406010208") == "2026-01-24"

    def test_to_month(self):
        assert race_id_to_month("2026012406010208") == "2026-01"

    def test_short_input(self):
        assert race_id_to_date("123") == ""
        assert race_id_to_month("12") == ""

    def test_bin_month(self):
        s = ["2026-01-24", "2026-02-01"]
        out = bin_month(s).tolist()
        assert out == ["2026-01", "2026-02"]


class TestIsHandicap:
    def test_weight_type(self):
        assert is_handicap({"weight_type": "ハンデ"})
        assert is_handicap({"weight_type": "Handicap"})

    def test_race_name(self):
        assert is_handicap({"race_name": "中山金杯(ハンデ)"})
        assert is_handicap({"race_name": "Spring HC"})

    def test_not_handicap(self):
        assert not is_handicap({"race_name": "ジャパンカップ", "weight_type": "別定"})
        assert not is_handicap({})

    def test_non_dict(self):
        assert not is_handicap(None)


class TestOtherBins:
    def test_distance(self):
        s = pd.Series([1000, 1500, 2400, 3000])
        out = bin_distance(s).astype(str).tolist()
        assert out[0] == "~1200"
        assert out[-1] == "2500+"

    def test_closing_strength(self):
        s = pd.Series([0.3, 1.2, 2.5])
        out = bin_closing_strength(s).astype(str).tolist()
        assert out == ["~0.5", "1.0-1.5", "2.0+"]

    def test_ard(self):
        s = pd.Series([-3.0, -0.5, 1.5])
        out = bin_ard(s).astype(str).tolist()
        assert "~-2" in out

    def test_novelty(self):
        s = pd.Series([0, 3, 6, 10])
        out = bin_novelty(s).astype(str).tolist()
        assert out[-1] == "6+"

    def test_confidence(self):
        s = pd.Series([-0.05, 0.03, 0.25])
        out = bin_confidence(s).astype(str).tolist()
        assert out[-1] == "0.20+"
