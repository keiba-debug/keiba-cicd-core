#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ml/utils/backtest_cache.py ユニットテスト

実 backtest_cache.json は使わず、tmp_path に小さな fixture を作って検証する。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from ml.utils.backtest_cache import (
    load_backtest_cache, build_lookup,
    cache_to_predictions, flatten_to_df,
)


@pytest.fixture
def sample_races():
    return [
        {
            "race_id": "2026012406010208",
            "track_type": "芝",
            "grade": "G1",
            "age_class": "3+",
            "entries": [
                {
                    "umaban": 1, "horse_name": "A", "odds": 2.5, "odds_rank": 1,
                    "rank_p": 1, "rank_w": 1, "vb_gap": 4, "win_vb_gap": 4,
                    "win_ev": 1.3, "place_ev": 1.1, "ar_deviation": 1.5,
                    "dev_gap": 0.2, "closing_strength": 1.8,
                    "pred_proba_p_raw": 0.45, "predicted_margin": 0.5,
                    "is_win": 1, "is_top3": 1, "finish_position": 1,
                    "place_odds_min": 1.2,
                },
                {
                    "umaban": 2, "horse_name": "B", "odds": 12.0, "odds_rank": 5,
                    "rank_p": 3, "rank_w": 4, "vb_gap": 2,
                    "win_ev": 0.8, "place_ev": 1.0, "ar_deviation": -0.5,
                    "is_win": 0, "is_top3": 0, "finish_position": 8,
                    "place_odds_min": 2.5,
                },
            ],
        },
        {
            "race_id": "2026012406010209",
            "track_type": "ダ",
            "grade": "未勝利",
            "entries": [
                {
                    "umaban": 1, "horse_name": "C", "odds": 3.0, "odds_rank": 1,
                    "rank_p": 1, "rank_w": 1, "vb_gap": 5,
                    "win_ev": 1.5, "ar_deviation": 2.0,
                    "is_win": 0, "is_top3": 1, "finish_position": 3,
                    "place_odds_min": 1.5,
                },
            ],
        },
    ]


@pytest.fixture
def cache_file(tmp_path, sample_races):
    p = tmp_path / "backtest_cache_test.json"
    p.write_text(json.dumps(sample_races), encoding="utf-8")
    return p


class TestLoad:
    def test_load_from_path(self, cache_file):
        races = load_backtest_cache(path=cache_file, quiet=True)
        assert len(races) == 2
        assert races[0]["race_id"] == "2026012406010208"

    def test_load_missing(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_backtest_cache(path=tmp_path / "missing.json", quiet=True)


class TestLookup:
    def test_build(self, sample_races):
        lk = build_lookup(sample_races)
        assert ("2026012406010208", 1) in lk
        assert ("2026012406010208", 2) in lk
        assert ("2026012406010209", 1) in lk
        assert lk[("2026012406010208", 1)]["horse_name"] == "A"

    def test_missing_race_id_skip(self):
        races = [{"entries": [{"umaban": 1}]}, {"race_id": "X", "entries": [{"umaban": 1}]}]
        lk = build_lookup(races)
        assert ("X", 1) in lk
        assert len(lk) == 1


class TestCacheToPredictions:
    def test_passthrough(self, sample_races):
        preds = cache_to_predictions(sample_races)
        assert len(preds) == 2
        assert preds[0]["race_id"] == "2026012406010208"
        assert preds[0]["track_type"] == "芝"
        assert preds[0]["grade"] == "G1"
        assert len(preds[0]["entries"]) == 2
        e0 = preds[0]["entries"][0]
        assert e0["umaban"] == 1
        assert e0["odds"] == 2.5
        assert e0["win_vb_gap"] == 4

    def test_default_win_vb_gap(self, sample_races):
        # vb_gap=2 で win_vb_gap 未定義 → vb_gap で fallback
        preds = cache_to_predictions(sample_races)
        e1 = preds[0]["entries"][1]
        assert e1["win_vb_gap"] == 2


class TestFlattenToDf:
    def test_columns(self, sample_races):
        pd = pytest.importorskip("pandas")
        df = flatten_to_df(sample_races)
        assert len(df) == 3  # 2 + 1 entries
        for col in ("race_id", "date", "track_type", "grade", "odds_band",
                    "is_top3", "is_win", "is_upset", "is_big_upset"):
            assert col in df.columns

    def test_date_parse(self, sample_races):
        df = flatten_to_df(sample_races)
        assert df["date"].iloc[0] == "2026-01-24"

    def test_bool_cast(self, sample_races):
        df = flatten_to_df(sample_races)
        assert df["is_win"].dtype == bool
        assert df["is_top3"].dtype == bool

    def test_upset_flag(self, sample_races):
        df = flatten_to_df(sample_races)
        # umaban=2 odds=12 is_top3=False → is_upset=False
        # umaban=1 (race1) odds=2.5 is_top3=True → is_upset=False
        # umaban=1 (race2) odds=3.0 is_top3=True → is_upset=False
        assert not df["is_upset"].any()

    def test_empty(self):
        df = flatten_to_df([])
        assert df.empty
