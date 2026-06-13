#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E-002 quality_gate（信頼性ゲート純関数）のテスト。"""

from ml.strategies.quality_gate import is_low_confidence, reliable_value


# --- reliable_value: ci95.lower 採用 + フォールバック ---

def test_reliable_value_uses_lower():
    q = {"ci95": {"lower": 0.451, "upper": 0.828}}
    # 生率 0.769 でなく下限 0.451 を採用（小標本上振れに騙されない）
    assert reliable_value(q, 0.769) == 0.451


def test_reliable_value_mode_upper():
    q = {"ci95": {"lower": 0.451, "upper": 0.828}}
    assert reliable_value(q, 0.769, mode="upper") == 0.828


def test_reliable_value_ci_null_falls_back():
    q = {"ci95": None}
    assert reliable_value(q, 0.30) == 0.30


def test_reliable_value_missing_ci_key_falls_back():
    q = {"metric": "top3_rate"}
    assert reliable_value(q, 0.30) == 0.30


def test_reliable_value_quality_none_falls_back():
    assert reliable_value(None, 0.30) == 0.30


def test_reliable_value_quality_not_dict_falls_back():
    assert reliable_value("oops", 0.30) == 0.30


def test_reliable_value_mode_value_none_falls_back():
    q = {"ci95": {"lower": None, "upper": 0.5}}
    assert reliable_value(q, 0.30) == 0.30


# --- is_low_confidence: 表示タグ補助（減点には使わない） ---

def test_low_confidence_insufficient():
    q = {"stability_flag": "insufficient", "effective_n": 1000}
    assert is_low_confidence(q) is True


def test_low_confidence_small_effective_n():
    q = {"stability_flag": "stable", "effective_n": 8}
    assert is_low_confidence(q, min_effective_n=30) is True


def test_high_confidence_stable_large_n():
    q = {"stability_flag": "stable", "effective_n": 500}
    assert is_low_confidence(q, min_effective_n=30) is False


def test_low_confidence_quality_none():
    assert is_low_confidence(None) is True


def test_low_confidence_effective_n_none():
    q = {"stability_flag": "stable"}
    assert is_low_confidence(q, min_effective_n=30) is True
