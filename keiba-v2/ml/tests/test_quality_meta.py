#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""E-001 quality_meta ヘルパの境界テスト（仕様 v1.2 §4）。"""

import math

import pytest

from analysis.quality_meta import (
    PRIORS,
    bayesian_ci,
    mean_se_ci,
    quality_meta,
    stability_flag,
    wilson_ci,
)


# --- Wilson（既知値ピン留め） ------------------------------------------------

def test_wilson_known_value():
    ci = wilson_ci(20, 80)  # p=0.25
    assert ci["lower"] == pytest.approx(0.1680, abs=0.001)
    assert ci["upper"] == pytest.approx(0.3548, abs=0.001)


def test_wilson_zero_n():
    assert wilson_ci(0, 0) is None


# --- Beta-Binomial（prior 必須 B-4） ----------------------------------------

def test_bayesian_requires_prior():
    with pytest.raises(ValueError):
        bayesian_ci(10, 13, None)


def test_bayesian_close_win_shrinkage():
    # rank1 10/13=0.769 を close prior(5,5) で → 事後 Beta(15,8), mean=0.652
    ci = bayesian_ci(10, 13, PRIORS["close_win_rate"])
    assert ci["lower"] < 0.652 < ci["upper"]
    assert ci["lower"] > 0.40   # ベース0.5 近傍に踏みとどまる（破壊的反転しない）


def test_quality_meta_bayesian_missing_prior_raises():
    with pytest.raises(ValueError):
        quality_meta(metric="close_win_rate", algo="bayesian_beta_binomial",
                     hits=10, n=13, prior=None)


# --- mean_se（z / t / weighted） --------------------------------------------

def test_mean_se_large_n_uses_z():
    ci, eff = mean_se_ci(51.89, 1.06, 2789)   # RPCI 実物近傍
    assert eff == 2789
    half = 1.96 * 1.06 / math.sqrt(2789)
    assert ci["lower"] == pytest.approx(51.89 - half, abs=0.001)
    assert ci["upper"] == pytest.approx(51.89 + half, abs=0.001)


def test_mean_se_small_n_uses_t():
    ci, eff = mean_se_ci(75.0, 3.0, 10)
    assert eff == 10
    half_z = 1.96 * 3.0 / math.sqrt(10)
    # t(9)=2.262 > z なので幅は z より広い
    assert (ci["upper"] - ci["lower"]) / 2 > half_z


def test_mean_se_weighted_effective_n():
    ci, eff = mean_se_ci(50.0, 1.0, None, weights=[2, 2, 1, 1])
    assert eff == pytest.approx(3.6, abs=1e-9)   # (6^2)/10
    assert ci is not None


def test_mean_se_missing_inputs():
    assert mean_se_ci(None, 1.0, 10) == (None, None)


# --- stability（CI ベース S-2） ---------------------------------------------

CI = {"lower": 0.2, "upper": 0.4}


def test_stability_stable():
    yd = {2024: {"hits": 30, "n": 100}, 2025: {"hits": 32, "n": 100}}
    assert stability_flag(yd, CI) == "stable"


def test_stability_drift():
    yd = {2024: {"hits": 30, "n": 100}, 2025: {"hits": 60, "n": 100}}  # 0.6 > 0.4
    assert stability_flag(yd, CI) == "drift"


def test_stability_latest_n_too_small():
    yd = {2025: {"hits": 5, "n": 10}}   # n<20
    assert stability_flag(yd, CI) == "insufficient"


def test_stability_no_year_data():
    assert stability_flag(None, CI) == "insufficient"


def test_stability_skips_none_year():
    yd = {2024: {"hits": 30, "n": 100}, 2025: None}  # 最新有効年=2024
    assert stability_flag(yd, CI) == "stable"


def test_stability_all_years_invalid():
    yd = {2024: None, 2025: {"hits": None, "n": 50}}
    assert stability_flag(yd, CI) == "insufficient"


def test_stability_continuous_mean():
    yd = {2024: {"mean": 0.3, "n": 100}, 2025: {"mean": 0.5, "n": 100}}  # 0.5 > 0.4
    assert stability_flag(yd, CI, is_rate=False) == "drift"


# --- quality_meta 統合 ------------------------------------------------------

def test_quality_meta_wilson_basic():
    q = quality_meta(metric="top3_rate", algo="wilson_binomial", hits=20, n=80)
    assert q["metric"] == "top3_rate"
    assert q["algo"] == "wilson_binomial"
    assert q["effective_n"] == 80
    assert q["ci95"]["lower"] == pytest.approx(0.1680, abs=0.001)


def test_quality_meta_bayesian_effective_n_is_raw():
    # effective_n は n+α+β でなく raw n（S-5 二重補正防止）
    q = quality_meta(metric="top3_rate", algo="bayesian_beta_binomial",
                     hits=5, n=20, prior=PRIORS["top3_rate"])
    assert q["effective_n"] == 20


def test_quality_meta_min_n_insufficient():
    q = quality_meta(metric="top3_rate", algo="wilson_binomial", hits=2, n=5, min_n=10)
    assert q["stability_flag"] == "insufficient"
    assert q["ci95"] is not None   # ci95 自体は出す


def test_quality_meta_flags():
    q = quality_meta(metric="top3_rate", algo="bayesian_beta_binomial",
                     hits=10, n=30, prior=PRIORS["top3_rate"],
                     selected=True, source="fallback:G1", original_n=9)
    assert q["selected"] is True
    assert q["source"] == "fallback:G1"
    assert q["original_n"] == 9


def test_quality_meta_none_algo():
    q = quality_meta(metric="rpci_weighted_mean", algo="none")
    assert q["ci95"] is None
    assert q["stability_flag"] == "insufficient"


def test_quality_meta_unknown_algo():
    with pytest.raises(ValueError):
        quality_meta(metric="x", algo="bogus")


def test_quality_meta_wilson_requires_hits_n():
    with pytest.raises(ValueError):
        quality_meta(metric="top3_rate", algo="wilson_binomial", hits=None, n=80)
