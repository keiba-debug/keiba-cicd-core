"""§14.4 race-level 環境変数テスト"""
from __future__ import annotations

import pytest

from analysis.niigata1000.features import (
    classify_track_condition_grp,
    classify_era,
    is_full_field,
    classify_race_type,
    compute_race_env,
)


# ----------------------------------------------------------------------------
# track_condition_grp: 良 / 稍重以上
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("cond,expected", [
    ("良", "良"),
    ("稍重", "稍重以上"),
    ("重", "稍重以上"),
    ("不良", "稍重以上"),
])
def test_track_condition_grp(cond, expected):
    assert classify_track_condition_grp(cond) == expected


def test_track_condition_grp_unknown_treats_as_heavy():
    """想定外の値は安全側 (稍重以上) に倒す"""
    assert classify_track_condition_grp("") == "稍重以上"
    assert classify_track_condition_grp(None) == "稍重以上"


# ----------------------------------------------------------------------------
# era: 2020-2022 / 2023-2026 (境界 = 2023-01-01)
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("date_str,expected", [
    ("2020-01-01", "2020-2022"),
    ("2021-06-15", "2020-2022"),
    ("2022-12-31", "2020-2022"),
    ("2023-01-01", "2023-2026"),
    ("2024-08-04", "2023-2026"),
    ("2026-04-01", "2023-2026"),
])
def test_era_boundary(date_str, expected):
    assert classify_era(date_str) == expected


# ----------------------------------------------------------------------------
# is_full_field: num_runners >= 16
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("n,expected", [
    (10, False),
    (15, False),
    (16, True),
    (17, True),
    (18, True),
])
def test_is_full_field(n, expected):
    assert is_full_field(n) is expected


# ----------------------------------------------------------------------------
# race_type: アイビスSD / OP / 条件戦
# ----------------------------------------------------------------------------

def test_race_type_ibis_summer_dash():
    assert classify_race_type(grade="G3", race_name="アイビスサマーダッシュ") == "G3アイビスSD"
    # grade が None でも race_name から判定できる
    assert classify_race_type(grade=None, race_name="第24回アイビスサマーダッシュ") == "G3アイビスSD"


def test_race_type_open_class():
    assert classify_race_type(grade="OP", race_name="ルミエールオータムダッシュ") == "OP"
    assert classify_race_type(grade="L", race_name="韋駄天ステークス") == "OP"


def test_race_type_conditioned_race():
    """3勝/2勝/1勝/未勝利 → 条件戦"""
    assert classify_race_type(grade="3勝", race_name="信濃川特別") == "条件戦"
    assert classify_race_type(grade="2勝", race_name="ある条件戦") == "条件戦"
    assert classify_race_type(grade="1勝", race_name="ある条件戦") == "条件戦"
    assert classify_race_type(grade="未勝利", race_name="未勝利戦") == "条件戦"
    assert classify_race_type(grade=None, race_name="ある条件戦") == "条件戦"


# ----------------------------------------------------------------------------
# compute_race_env: 統合 API
# ----------------------------------------------------------------------------

def test_compute_race_env_aibis_full_field():
    race = {
        "race_date": "2025-08-04",
        "track_condition": "良",
        "num_runners": 18,
        "grade": "G3",
        "race_name": "アイビスサマーダッシュ",
    }
    env = compute_race_env(race)
    assert env == {
        "track_condition_grp": "良",
        "era": "2023-2026",
        "is_full_field": True,
        "race_type": "G3アイビスSD",
    }


def test_compute_race_env_early_era_heavy_track():
    race = {
        "race_date": "2021-05-22",
        "track_condition": "稍重",
        "num_runners": 14,
        "grade": "3勝",
        "race_name": "信濃川特別",
    }
    env = compute_race_env(race)
    assert env == {
        "track_condition_grp": "稍重以上",
        "era": "2020-2022",
        "is_full_field": False,
        "race_type": "条件戦",
    }


def test_compute_race_env_missing_fields_defaults():
    """欠損フィールドは安全側にフォールバック"""
    race = {
        "race_date": "2024-05-04",
        # track_condition, num_runners, grade, race_name 欠損
    }
    env = compute_race_env(race)
    assert env["era"] == "2023-2026"
    assert env["is_full_field"] is False  # num_runners 欠損 → False
    assert env["track_condition_grp"] == "稍重以上"  # 不明は安全側
    assert env["race_type"] == "条件戦"  # 不明は条件戦扱い
