"""§14.1 馬個別特徴量テスト

データ辞書 (analysis/niigata1000/data_dictionary.md) を単一の真実とする。
"""
from __future__ import annotations

import math

import pytest

from analysis.niigata1000.features import compute_horse_features


# ----------------------------------------------------------------------------
# (a) Reference cutoff: 全フィールドが定義通り算出される
# ----------------------------------------------------------------------------

def test_veteran_reference_cutoff_returns_all_fields(history_cache, pin_veteran):
    """Pin 2018106612, cutoff='2024-08-12' で §14.1 全フィールドを期待値検証

    手計算済み期待値 (実データ依存):
      - 過去走 36 件 (2024-08-04 と 2024-08-11 含む)
      - 千直 12 戦 / top3=3 / rate=0.25 / finish_avg=5.25 / l3f_avg≈32.8833
      - last5 = [2024-02-24, 2024-05-04, 2024-05-18, 2024-08-04, 2024-08-11]
        - corners 有効値は 2024-02-24 のみ (corners=[10,10]) → cf5=[10]
        - last_3f は 5件すべて有効
      - 短距離 (1000-1200m turf) 25 戦, l3f 平均 34.056
      - 前走 = 2024-08-11, 1000m, finish=5
    """
    feat = compute_horse_features(pin_veteran, "2024-08-12", history_cache)

    assert feat["total_career_races_at_cutoff"] == 36
    assert feat["niigata_1000m_count"] == 12
    assert feat["niigata_1000m_top3_count"] == 3
    assert feat["past_choku_top3_rate"] == pytest.approx(0.25)
    assert feat["past_choku_finish_avg"] == pytest.approx(5.25)
    assert feat["past_choku_last_3f_avg"] == pytest.approx(32.8833, abs=1e-3)

    assert feat["past_corner_first_avg_5"] == pytest.approx(10.0)
    assert feat["past_corner_first_min_5"] == 10
    assert feat["past_last_3f_avg_5"] == pytest.approx(32.92)
    assert feat["past_last_3f_min_5"] == pytest.approx(32.1)

    assert feat["past_short_count"] == 25
    assert feat["past_short_avg_l3f"] == pytest.approx(34.056, abs=1e-3)

    assert feat["prev_distance"] == 1000
    assert feat["prev_finish"] == 5
    assert feat["days_since_prev"] == 1

    assert feat["is_first_choku"] is False


# ----------------------------------------------------------------------------
# (b) cutoff_date 当日は含めない (strict less than)
# ----------------------------------------------------------------------------

def test_cutoff_excludes_same_day_race(history_cache, pin_veteran):
    """cutoff='2024-08-04' なら 2024-08-04 のレースは含まれない

    cutoff='2024-08-05' なら含まれる。差分が +1 になる。
    """
    feat_at = compute_horse_features(pin_veteran, "2024-08-04", history_cache)
    feat_next = compute_horse_features(pin_veteran, "2024-08-05", history_cache)

    # cutoff 当日除外: 2024-08-04 当日は past に含まれない
    assert feat_at["total_career_races_at_cutoff"] == 34
    # 翌日は含まれる
    assert feat_next["total_career_races_at_cutoff"] == 35

    # 千直カウントも同様 (2024-08-04 は千直)
    assert feat_at["niigata_1000m_count"] == 10
    assert feat_next["niigata_1000m_count"] == 11


# ----------------------------------------------------------------------------
# (c) cutoff_date 変動: 結果が変わる (リーク防止)
# ----------------------------------------------------------------------------

def test_cutoff_variation_changes_top3_rate(history_cache, pin_veteran):
    """cutoff='2024-08-04' (10戦/3着内3) → 0.30
    cutoff='2024-08-12' (12戦/3着内3) → 0.25
    """
    feat_early = compute_horse_features(pin_veteran, "2024-08-04", history_cache)
    feat_late = compute_horse_features(pin_veteran, "2024-08-12", history_cache)

    assert feat_early["past_choku_top3_rate"] == pytest.approx(0.30)
    assert feat_late["past_choku_top3_rate"] == pytest.approx(0.25)
    assert feat_early["past_choku_top3_rate"] != feat_late["past_choku_top3_rate"]


def test_cutoff_variation_changes_prev_run(history_cache, pin_veteran):
    """cutoff が変わると前走情報も変わる"""
    # cutoff='2024-08-12': prev = 2024-08-11 (1000m, finish=5)
    feat_late = compute_horse_features(pin_veteran, "2024-08-12", history_cache)
    assert feat_late["prev_distance"] == 1000
    assert feat_late["prev_finish"] == 5

    # cutoff='2024-08-04': prev = 2024-05-18 (1000m, finish=1)
    feat_early = compute_horse_features(pin_veteran, "2024-08-04", history_cache)
    assert feat_early["prev_distance"] == 1000
    assert feat_early["prev_finish"] == 1


# ----------------------------------------------------------------------------
# (d) 欠損時挙動: デビュー馬 / 経験ゼロ
# ----------------------------------------------------------------------------

def test_debut_horse_returns_zeros_and_nones(history_cache, pin_debut):
    """2023104705 は 2025-06-29 デビュー → cutoff='2025-06-29' で過去走ゼロ"""
    feat = compute_horse_features(pin_debut, "2025-06-29", history_cache)

    assert feat["total_career_races_at_cutoff"] == 0
    assert feat["niigata_1000m_count"] == 0
    assert feat["niigata_1000m_top3_count"] == 0
    assert feat["past_choku_top3_rate"] is None
    assert feat["past_choku_finish_avg"] is None
    assert feat["past_choku_last_3f_avg"] is None
    assert feat["past_corner_first_avg_5"] is None
    assert feat["past_corner_first_min_5"] is None
    assert feat["past_last_3f_avg_5"] is None
    assert feat["past_last_3f_min_5"] is None
    assert feat["past_short_count"] == 0
    assert feat["past_short_avg_l3f"] is None
    assert feat["prev_distance"] is None
    assert feat["prev_finish"] is None
    assert feat["days_since_prev"] is None
    assert feat["is_first_choku"] is True


def test_unknown_horse_returns_default_dict(history_cache):
    """history_cache に存在しない ketto_num でも例外を出さず欠損 dict を返す"""
    feat = compute_horse_features("9999999999", "2024-08-12", history_cache)
    assert feat["total_career_races_at_cutoff"] == 0
    assert feat["niigata_1000m_count"] == 0
    assert feat["past_choku_top3_rate"] is None
    assert feat["is_first_choku"] is True


# ----------------------------------------------------------------------------
# (a-2) 千直経験ありで corners が空配列だけの場合の corners 系 None
# ----------------------------------------------------------------------------

def test_corners_filtered_when_all_zero_or_empty(history_cache, pin_veteran):
    """cutoff='2024-09-01': last5 = 全部 千直 (corners=[]) → past_corner_first_avg_5 is None

    2018106612 の 2024-08-12 以降の流れ:
      - 2024-08-04 finish=7 (千直, corners=[])
      - 2024-08-11 finish=5 (千直, corners=[])
    cutoff='2024-09-01' とすると、past 末尾5件は:
      [2024-05-04 千直, 2024-05-18 千直, 2024-08-04 千直, 2024-08-11 千直, ?]

    実データ確認: 2024-02-24 (1200m, corners=[10,10]) は 5件目にギリギリ含まれる
    なので、より厳密な検証は別途行う。

    ここではデビュー馬で corners 系が None であることのみ検証 (test_debut_horse でカバー済み)。
    本テストは将来 corners-only-empty な fixture が見つかれば追加する。
    """
    pytest.skip("将来 corners 空のみ fixture が見つかれば実装")


# ----------------------------------------------------------------------------
# (return shape) 全キーが存在する
# ----------------------------------------------------------------------------

EXPECTED_KEYS = {
    "total_career_races_at_cutoff",
    "niigata_1000m_count",
    "niigata_1000m_top3_count",
    "past_choku_top3_rate",
    "past_choku_finish_avg",
    "past_choku_last_3f_avg",
    "past_corner_first_avg_5",
    "past_corner_first_min_5",
    "past_last_3f_avg_5",
    "past_last_3f_min_5",
    "past_short_count",
    "past_short_avg_l3f",
    "prev_distance",
    "prev_finish",
    "days_since_prev",
    "is_first_choku",
}


def test_return_dict_has_all_expected_keys(history_cache, pin_veteran):
    feat = compute_horse_features(pin_veteran, "2024-08-12", history_cache)
    assert set(feat.keys()) == EXPECTED_KEYS


def test_return_dict_keys_stable_for_debut(history_cache, pin_debut):
    feat = compute_horse_features(pin_debut, "2025-06-29", history_cache)
    assert set(feat.keys()) == EXPECTED_KEYS


# ----------------------------------------------------------------------------
# (cutoff format) ISO YYYY-MM-DD 必須
# ----------------------------------------------------------------------------

def test_invalid_cutoff_format_raises(history_cache, pin_veteran):
    """cutoff_date が ISO 形式でない場合は ValueError"""
    with pytest.raises(ValueError):
        compute_horse_features(pin_veteran, "2024/08/12", history_cache)
