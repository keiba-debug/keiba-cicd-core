#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ml/utils/filters.py ユニットテスト

Usage:
    cd keiba-v2
    python -m pytest ml/tests/test_utils_filters.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from ml.utils.filters import (
    is_obstacle,
    exclude_obstacle,
    split_by_obstacle,
    has_min_samples,
    sample_size_marker,
    MIN_SAMPLE_DEFAULT,
)


class TestIsObstacle:
    def test_track_type_obstacle(self):
        assert is_obstacle({"track_type": "obstacle"})

    def test_track_type_japanese(self):
        assert is_obstacle({"track_type": "障害"})

    def test_track_type_steeplechase(self):
        # legacy value
        assert is_obstacle({"track_type": "steeplechase"})

    def test_race_name_contains_obstacle(self):
        assert is_obstacle({"track_type": "芝", "race_name": "障害4歳以上未勝利"})

    def test_flat_race(self):
        assert not is_obstacle({"track_type": "芝", "race_name": "ジャパンカップ"})

    def test_dirt_race(self):
        assert not is_obstacle({"track_type": "ダ", "race_name": "ユニコーンS"})

    def test_empty_dict(self):
        assert not is_obstacle({})

    def test_non_dict(self):
        assert not is_obstacle(None)
        assert not is_obstacle("foo")

    def test_missing_race_name(self):
        assert not is_obstacle({"track_type": "芝"})


class TestExcludeObstacle:
    def test_mixed(self):
        races = [
            {"race_id": "1", "track_type": "芝"},
            {"race_id": "2", "track_type": "obstacle"},
            {"race_id": "3", "track_type": "ダ"},
            {"race_id": "4", "track_type": "芝", "race_name": "障害特別"},
        ]
        out = exclude_obstacle(races)
        assert len(out) == 2
        assert {r["race_id"] for r in out} == {"1", "3"}

    def test_empty(self):
        assert exclude_obstacle([]) == []


class TestSplitByObstacle:
    def test_split(self):
        races = [
            {"race_id": "1", "track_type": "芝"},
            {"race_id": "2", "track_type": "obstacle"},
        ]
        flat, obs = split_by_obstacle(races)
        assert [r["race_id"] for r in flat] == ["1"]
        assert [r["race_id"] for r in obs] == ["2"]


class TestSampleSize:
    def test_has_min_default(self):
        assert has_min_samples(MIN_SAMPLE_DEFAULT)
        assert has_min_samples(MIN_SAMPLE_DEFAULT + 1)
        assert not has_min_samples(MIN_SAMPLE_DEFAULT - 1)

    def test_has_min_custom(self):
        assert has_min_samples(10, threshold=10)
        assert not has_min_samples(9, threshold=10)

    def test_marker_high(self):
        assert sample_size_marker(MIN_SAMPLE_DEFAULT) == ""
        assert sample_size_marker(100) == ""

    def test_marker_low(self):
        # 30/3 = 10, so 10 is low-sample
        assert "低サンプル" in sample_size_marker(10)
        # 9 < 10 → 要警戒
        assert "要警戒" in sample_size_marker(9)
        assert "要警戒" in sample_size_marker(0)


class TestFilters:
    """pandas 必須テスト — skipif で fallback"""

    @pytest.fixture
    def df(self):
        pd = pytest.importorskip("pandas")
        return pd.DataFrame({
            "pred_rank_w": [1, 2, 4, 1, 3],
            "win_gap":     [6, 7, 8, 4, 6],
            "win_ev":      [1.5, 1.3, 1.1, 1.4, 1.0],
            "margin":      [0.5, 0.8, -0.5, -1.5, 1.0],
            "odds":        [5.0, 6.0, 10.0, 4.0, 0.0],
        })

    def test_filter_win_only(self, df):
        from ml.utils.filters import filter_win_only
        out = filter_win_only(df, min_gap=5, min_ability=-1.2)
        # rank_w<=3 + win_gap>=5 + margin>=-1.2 + odds>0
        # row0(rank1,gap6,margin0.5,odds5) ok
        # row1(rank2,gap7,margin0.8,odds6) ok
        # row2(rank4) ng (rank_w>3)
        # row3(rank1,gap4) ng (gap<5)
        # row4(rank3,gap6,margin1.0,odds0) ng (odds=0)
        assert len(out) == 2

    def test_filter_selective(self, df):
        from ml.utils.filters import filter_selective
        out = filter_selective(df, min_gap=6, min_ev=1.2, min_ability=-0.8)
        # rank_w<=3 + gap>=6 + ev>=1.2 + margin>=-0.8 + odds>0
        # row0(gap6,ev1.5,margin0.5,odds5) ok
        # row1(gap7,ev1.3,margin0.8,odds6) ok
        # row2(rank4) ng
        # row3(gap4) ng
        # row4(gap6,ev1.0) ng (ev<1.2)
        assert len(out) == 2
