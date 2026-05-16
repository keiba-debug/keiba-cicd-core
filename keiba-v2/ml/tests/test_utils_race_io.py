#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ml/utils/race_io.py ユニットテスト

races/YYYY/MM/DD/race_*.json と predictions.json の fixture を tmp_path に作って検証する。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pytest

from ml.utils.race_io import (
    iter_date_dirs, date_dir_for,
    iter_race_files, load_race, load_race_results,
    load_predictions, iter_predictions,
    fetch_race_meta, enrich_with_race_meta,
)


@pytest.fixture
def fake_races_root(tmp_path):
    """races/2026/01/24/race_xxx.json + predictions.json を 2日分作る"""
    base = tmp_path / "races"
    for day in ("24", "25"):
        day_dir = base / "2026" / "01" / day
        day_dir.mkdir(parents=True)
        for race_no in range(1, 3):
            rid = f"20260124060102{race_no:02d}" if day == "24" else f"20260125060102{race_no:02d}"
            data = {
                "race_id": rid,
                "venue_code": "06",
                "distance": 1800,
                "race_name": f"Test Race {race_no}",
                "track_type": "turf" if race_no == 1 else "dirt",
                "entries": [
                    {"umaban": 1, "finish_position": 1, "odds": 2.5,
                     "jockey_code": "01091", "trainer_code": "01001"},
                    {"umaban": 2, "finish_position": 5, "odds": 12.0,
                     "jockey_code": "01100", "trainer_code": "01002"},
                ],
            }
            (day_dir / f"race_{rid}.json").write_text(
                json.dumps(data), encoding="utf-8")
        # predictions.json
        (day_dir / "predictions.json").write_text(
            json.dumps({"races": [{"race_id": f"2026012{day[1]}06010201", "entries": []}]}),
            encoding="utf-8")
    # ノイズ用に YYYY 以外の dir も置く
    (base / "tmp_garbage").mkdir(parents=True)
    return base


class TestIterDateDirs:
    def test_all(self, fake_races_root):
        dirs = list(iter_date_dirs(root=fake_races_root))
        names = [d.name for d in dirs]
        assert names == ["24", "25"]

    def test_filter_after(self, fake_races_root):
        dirs = list(iter_date_dirs("2026-02", None, root=fake_races_root))
        assert dirs == []

    def test_filter_before(self, fake_races_root):
        dirs = list(iter_date_dirs(None, "2025-12", root=fake_races_root))
        assert dirs == []

    def test_in_range(self, fake_races_root):
        dirs = list(iter_date_dirs("2026-01", "2026-01", root=fake_races_root))
        assert len(dirs) == 2

    def test_ignore_non_year_dir(self, fake_races_root):
        # tmp_garbage はスキップされる ─ year_dir.name.isdigit() が偽
        dirs = list(iter_date_dirs(root=fake_races_root))
        # 全 dir の祖父 (year_dir) が "2026" であること
        assert all(d.parent.parent.name == "2026" for d in dirs)


class TestDateDirFor:
    def test_dash_format(self, fake_races_root):
        d = date_dir_for("2026-01-24", root=fake_races_root)
        assert d.exists()
        assert d.name == "24"

    def test_compact_format(self, fake_races_root):
        d = date_dir_for("20260124", root=fake_races_root)
        assert d.name == "24"

    def test_slash_format(self, fake_races_root):
        d = date_dir_for("2026/01/24", root=fake_races_root)
        assert d.name == "24"

    def test_invalid(self):
        with pytest.raises(ValueError):
            date_dir_for("invalid")


class TestRaceLoaders:
    def test_iter_race_files(self, fake_races_root):
        d24 = fake_races_root / "2026" / "01" / "24"
        files = list(iter_race_files(d24))
        assert len(files) == 2
        assert all(f.name.startswith("race_") for f in files)

    def test_load_race(self, fake_races_root):
        d24 = fake_races_root / "2026" / "01" / "24"
        race = load_race(d24, "2026012406010201")
        assert race is not None
        assert race["race_id"] == "2026012406010201"

    def test_load_race_missing(self, fake_races_root):
        d24 = fake_races_root / "2026" / "01" / "24"
        assert load_race(d24, "9999999999999999") is None

    def test_load_race_results(self, fake_races_root):
        d24 = fake_races_root / "2026" / "01" / "24"
        out = load_race_results(d24)
        assert len(out) == 2  # 2 races
        first_rid = next(iter(out))
        assert 1 in out[first_rid]
        assert out[first_rid][1]["finish_position"] == 1
        assert out[first_rid][1]["odds"] == 2.5
        # 後方互換キー
        assert out[first_rid][1]["finish"] == 1


class TestPredictions:
    def test_load_predictions(self, fake_races_root):
        d = fake_races_root / "2026" / "01" / "24"
        data = load_predictions(d)
        assert data is not None
        assert "races" in data

    def test_load_predictions_missing(self, tmp_path):
        assert load_predictions(tmp_path) is None

    def test_iter_predictions(self, fake_races_root):
        out = list(iter_predictions(root=fake_races_root))
        assert len(out) == 2
        for d, data in out:
            assert isinstance(d, Path)
            assert "races" in data

    def test_iter_predictions_with_results(self, fake_races_root):
        out = list(iter_predictions(root=fake_races_root, with_results=True))
        assert len(out) == 2
        for tup in out:
            assert len(tup) == 3
            _, _, results = tup
            assert isinstance(results, dict)


class TestFetchRaceMeta:
    def test_basic(self, fake_races_root):
        rids = ["2026012406010201", "2026012406010202"]
        meta = fetch_race_meta(rids, root=fake_races_root)
        assert len(meta) == 2
        assert meta["2026012406010201"]["race"]["venue_code"] == "06"
        assert meta["2026012406010201"]["race"]["distance"] == 1800
        assert meta["2026012406010201"]["race"]["track_type"] == "turf"
        assert meta["2026012406010201"]["entries"][1]["jockey_code"] == "01091"

    def test_missing_race_skip(self, fake_races_root):
        rids = ["2026012406010201", "9999999999999999"]
        meta = fetch_race_meta(rids, root=fake_races_root)
        assert len(meta) == 1
        assert "9999999999999999" not in meta


class TestEnrichWithRaceMeta:
    @pytest.fixture
    def base_df(self, fake_races_root):
        pd = pytest.importorskip("pandas")
        return pd.DataFrame({
            "race_id": ["2026012406010201", "2026012406010201", "2026012406010202"],
            "umaban":  [1, 2, 1],
            "track_type": ["", "", ""],     # 空文字 → meta から fillna
        })

    def test_enrich_adds_columns(self, fake_races_root, base_df):
        out = enrich_with_race_meta(base_df, root=fake_races_root)
        for col in ("venue_code", "distance", "race_name", "jockey_code", "trainer_code"):
            assert col in out.columns

    def test_enrich_fillna_blank(self, fake_races_root, base_df):
        # 元の track_type が空文字 → meta の値で上書きされる
        out = enrich_with_race_meta(base_df, root=fake_races_root)
        assert out.loc[0, "track_type"] == "turf"   # race 01
        assert out.loc[2, "track_type"] == "dirt"   # race 02

    def test_enrich_per_entry(self, fake_races_root, base_df):
        out = enrich_with_race_meta(base_df, root=fake_races_root)
        # race 01 の馬1 は jockey_code "01091"、馬2 は "01100"
        r01 = out[out["race_id"] == "2026012406010201"]
        assert set(r01["jockey_code"].tolist()) == {"01091", "01100"}
