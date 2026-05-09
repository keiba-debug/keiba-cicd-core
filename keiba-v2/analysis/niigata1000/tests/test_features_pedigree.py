"""§14.3 血統特徴量テスト"""
from __future__ import annotations

import pytest

from analysis.niigata1000.features import (
    classify_sire_line,
    compute_horse_pedigree,
)


# ----------------------------------------------------------------------------
# classify_sire_line: 系統判定
# ----------------------------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    # サンデー系
    ("ディープインパクト", "サンデー系"),
    ("キズナ", "サンデー系"),
    ("ハーツクライ", "サンデー系"),
    ("ダイワメジャー", "サンデー系"),
    ("スペシャルウィーク", "サンデー系"),
    # キングカメハメハ系
    ("キングカメハメハ", "キングカメハメハ系"),
    ("ロードカナロア", "キングカメハメハ系"),
    ("ドゥラメンテ", "キングカメハメハ系"),
    # ノーザンダンサー系 (ハービンジャーは特例ハードコード)
    ("ハービンジャー", "ノーザンダンサー系"),
    # その他
    ("ジョーカプチーノ", "その他"),
    ("ゼンノエルシド", "その他"),
    ("サンダースノー", "その他"),
    ("ビッグアーサー", "その他"),  # TOP_SIRE だが系統分類は「その他」
    # 不明
    ("", "不明"),
    ("?", "不明"),
])
def test_classify_sire_line(name, expected):
    assert classify_sire_line(name) == expected


def test_classify_sire_line_none():
    """None は不明扱い"""
    assert classify_sire_line(None) == "不明"


# ----------------------------------------------------------------------------
# compute_horse_pedigree: Pin 馬で実データ検証
# ----------------------------------------------------------------------------

EXPECTED_PEDIGREE_KEYS = {
    "sire_id", "sire_name", "sire_line",
    "bms_id", "bms_name", "bms_line",
}


def test_veteran_pedigree(pin_veteran, pedigree_index, sire_stats):
    """2018106612: sire=ジョーカプチーノ(その他), bms=ゼンノエルシド(その他)"""
    p = compute_horse_pedigree(pin_veteran, pedigree_index, sire_stats)
    assert p["sire_id"] == "1120002283"
    assert p["sire_name"] == "ジョーカプチーノ"
    assert p["sire_line"] == "その他"
    assert p["bms_id"] == "1120001942"
    assert p["bms_name"] == "ゼンノエルシド"
    assert p["bms_line"] == "その他"


def test_debut_pedigree(pin_debut, pedigree_index, sire_stats):
    """2023104705: sire=サンダースノー(その他), bms=スペシャルウィーク(サンデー系)"""
    p = compute_horse_pedigree(pin_debut, pedigree_index, sire_stats)
    assert p["sire_id"] == "1120002505"
    assert p["sire_name"] == "サンダースノー"
    assert p["sire_line"] == "その他"
    assert p["bms_id"] == "1120001743"
    assert p["bms_name"] == "スペシャルウィーク"
    assert p["bms_line"] == "サンデー系"


# ----------------------------------------------------------------------------
# 欠損挙動: 馬不在 / sire_id だけありで stats 未登録
# ----------------------------------------------------------------------------

def test_unknown_horse_returns_default_pedigree(pedigree_index, sire_stats):
    """pedigree_index に存在しない ketto_num はデフォルト dict"""
    p = compute_horse_pedigree("9999999999", pedigree_index, sire_stats)
    assert p["sire_id"] == ""
    assert p["sire_name"] == "?"
    assert p["sire_line"] == "不明"
    assert p["bms_id"] == ""
    assert p["bms_name"] == "?"
    assert p["bms_line"] == "不明"


def test_pedigree_id_present_but_stats_missing():
    """pedigree に id はあるが sire_stats に登録なし → name='?' line='不明'"""
    fake_pedigree = {"7777777777": {"sire": "9999999999", "bms": "8888888888", "dam": "0"}}
    fake_stats = {"sire": {}, "bms": {}, "dam": {}}
    p = compute_horse_pedigree("7777777777", fake_pedigree, fake_stats)
    assert p["sire_id"] == "9999999999"
    assert p["sire_name"] == "?"
    assert p["sire_line"] == "不明"
    assert p["bms_id"] == "8888888888"
    assert p["bms_name"] == "?"
    assert p["bms_line"] == "不明"


# ----------------------------------------------------------------------------
# return shape
# ----------------------------------------------------------------------------

def test_pedigree_return_keys_stable(pin_veteran, pedigree_index, sire_stats):
    p = compute_horse_pedigree(pin_veteran, pedigree_index, sire_stats)
    assert set(p.keys()) == EXPECTED_PEDIGREE_KEYS


def test_pedigree_return_keys_stable_for_unknown(pedigree_index, sire_stats):
    p = compute_horse_pedigree("9999999999", pedigree_index, sire_stats)
    assert set(p.keys()) == EXPECTED_PEDIGREE_KEYS
