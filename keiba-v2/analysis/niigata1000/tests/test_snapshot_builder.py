"""§14.2 関係者snapshot builder テスト

合成 history_cache (analysis/niigata1000/tests/_synthetic_fixture.py) を使い、
月末スナップショットの集計とリーク防止を厳密に検証する。
"""
from __future__ import annotations

import pytest

from analysis.niigata1000 import snapshot_builder as sb
from analysis.niigata1000.tests._synthetic_fixture import build_synthetic_history


@pytest.fixture(scope="module")
def synthetic_cache() -> dict:
    return build_synthetic_history()


# ----------------------------------------------------------------------------
# 月末判定 / window 計算
# ----------------------------------------------------------------------------

def test_last_day_of_month():
    assert sb._last_day_of_month("2024-07") == "2024-07-31"
    assert sb._last_day_of_month("2024-02") == "2024-02-29"  # leap
    assert sb._last_day_of_month("2025-02") == "2025-02-28"
    assert sb._last_day_of_month("2024-12") == "2024-12-31"


def test_window_start_inclusive():
    """window_start = snapshot_date - 730 days (inclusive)"""
    assert sb._window_start("2024-07-31") == "2022-08-01"
    assert sb._window_start("2024-08-31") == "2022-09-01"
    assert sb._window_start("2024-02-29") == "2022-03-01"


# ----------------------------------------------------------------------------
# build_relation_snapshot: 月末スナップショット生成
# ----------------------------------------------------------------------------

def test_snapshot_july_includes_a_b_d_excludes_c_e(synthetic_cache):
    """snapshot_ym='2024-07' は Race A(2022-08-21), B(2024-05-04), D(2022-08-10) を含み、
    Race C(2024-08-04), E(2024-08-25) を除外する"""
    snap = sb.build_relation_snapshot("2024-07", synthetic_cache)

    assert snap["snapshot_ym"] == "2024-07"
    assert snap["snapshot_date"] == "2024-07-31"

    # J_A: Race A (n=2 top3=2 strong=1) + Race B (n=2 top3=1 strong=0)
    #      + Race D (n=1 top3=1 strong=0) = n=5 top3=4 strong=1
    j_a = snap["jockeys"]["J_A"]
    assert j_a["n"] == 5
    assert j_a["top3"] == 4
    assert j_a["strong"] == 1

    # T_A: Race A (n=2 top3=1 strong=1) + Race B (n=2 top3=2 strong=0)
    #      + Race D (n=1 top3=1 strong=0) = n=5 top3=4 strong=1
    t_a = snap["trainers"]["T_A"]
    assert t_a["n"] == 5
    assert t_a["top3"] == 4
    assert t_a["strong"] == 1

    # J_B: Race A (n=2 top3=1) + Race D (n=1 top3=1) = n=3 top3=2 strong=0
    j_b = snap["jockeys"]["J_B"]
    assert j_b == {"n": 3, "top3": 2, "strong": 0}

    # J_C: Race B (n=2 top3=2) = n=2 top3=2 strong=0
    assert snap["jockeys"]["J_C"] == {"n": 2, "top3": 2, "strong": 0}


def test_snapshot_august_excludes_a_d(synthetic_cache):
    """snapshot_ym='2024-08' (window ~2022-09-01 ~ 2024-08-31) は Race A(2022-08-21) と
    Race D(2022-08-10) を除外し、B + C + E を含む"""
    snap = sb.build_relation_snapshot("2024-08", synthetic_cache)

    # J_A: Race B (n=2 top3=1 strong=0) + Race C (n=2 top3=2 strong=0)
    #      + Race E (n=1 top3=1 strong=0) = n=5 top3=4 strong=0
    j_a = snap["jockeys"]["J_A"]
    assert j_a == {"n": 5, "top3": 4, "strong": 0}


# ----------------------------------------------------------------------------
# 強馬判定の厳密検証 (Race A の H_A1 のみが strong)
# ----------------------------------------------------------------------------

def test_strong_horse_only_in_race_a(synthetic_cache):
    """Race A の H_A1 (J_A, T_A, finish=1, time=54.5, last_3f=32.5) のみが strong horse

    他は dev 条件を満たさないか top3 外。
    """
    # snapshot 2022-09 (window includes Race A and D)
    snap = sb.build_relation_snapshot("2022-09", synthetic_cache)
    # Race A の strong=1 (J_A, T_A) + Race D の strong=0 = 合計 strong=1
    assert snap["jockeys"]["J_A"]["strong"] == 1
    assert snap["trainers"]["T_A"]["strong"] == 1
    # 他は全部 strong=0
    assert snap["jockeys"]["J_B"]["strong"] == 0


# ----------------------------------------------------------------------------
# write/load round-trip
# ----------------------------------------------------------------------------

def test_write_and_load_snapshot(synthetic_cache, tmp_path):
    snap = sb.build_relation_snapshot("2024-07", synthetic_cache)
    path = sb.write_snapshot(snap, root=tmp_path)
    assert path.exists()
    assert path.name == "2024-07.json"

    loaded = sb.load_snapshot("2024-07", root=tmp_path)
    assert loaded == snap


def test_load_snapshot_returns_none_when_missing(tmp_path):
    assert sb.load_snapshot("9999-99", root=tmp_path) is None


# ----------------------------------------------------------------------------
# build_all_snapshots: range build
# ----------------------------------------------------------------------------

def test_build_all_snapshots_writes_each_month(synthetic_cache, tmp_path):
    paths = sb.build_all_snapshots("2024-06", "2024-08", synthetic_cache, root=tmp_path)
    assert len(paths) == 3
    names = sorted(p.name for p in paths)
    assert names == ["2024-06.json", "2024-07.json", "2024-08.json"]
