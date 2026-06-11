# -*- coding: utf-8 -*-
"""OddsConditionedCalibrator のテスト (Session 150)"""
import pickle

import numpy as np
import pytest

from ml.calibration.odds_conditioned import OddsConditionedCalibrator


def _toy(n=6000, seed=0):
    """raw と odds が独立に複勝率へ効く toy データ。

    真の複勝率 p = clip(1.3/odds + 0.5*raw, ...) ＝ 人気(低オッズ)ほど高く、
    raw もオッズと独立に押し上げる。 → log_odds<0, logit_raw>0 が出るべき。
    """
    rng = np.random.default_rng(seed)
    odds = rng.uniform(1.2, 80.0, n)
    raw = rng.uniform(0.02, 0.60, n)  # odds と独立
    p = np.clip(1.3 / odds + 0.5 * raw, 0.02, 0.97)
    y = (rng.uniform(0, 1, n) < p).astype(int)
    return raw, odds, y


def test_fit_predict_range():
    raw, odds, y = _toy()
    c = OddsConditionedCalibrator().fit(raw, odds, y)
    p = c.predict(raw, odds)
    assert p.shape == (len(raw),)
    assert np.all((p >= 0) & (p <= 1))
    assert c.n_fit_ == len(raw)


def test_monotonic_in_odds():
    raw, odds, y = _toy()
    c = OddsConditionedCalibrator().fit(raw, odds, y)
    assert c.coef_["log_odds"] < 0  # 人気ほど複勝率高い
    assert c.predict_one(0.3, 2.0) > c.predict_one(0.3, 20.0)


def test_monotonic_in_raw():
    raw, odds, y = _toy()
    c = OddsConditionedCalibrator().fit(raw, odds, y)
    assert c.coef_["logit_raw"] > 0  # raw がオッズを超える情報を持つ
    assert c.predict_one(0.5, 10.0) > c.predict_one(0.1, 10.0)


def test_pickle_roundtrip():
    raw, odds, y = _toy()
    c = OddsConditionedCalibrator().fit(raw, odds, y)
    c2 = pickle.loads(pickle.dumps(c))
    np.testing.assert_allclose(c.predict(raw, odds), c2.predict(raw, odds))


def test_predict_before_fit_raises():
    with pytest.raises(RuntimeError):
        OddsConditionedCalibrator().predict([0.3], [3.0])


def test_length_mismatch_raises():
    raw, odds, y = _toy(n=500)
    c = OddsConditionedCalibrator().fit(raw, odds, y)
    with pytest.raises(ValueError):
        c.predict([0.3, 0.4], [3.0])


def test_single_class_raises():
    with pytest.raises(ValueError):
        OddsConditionedCalibrator().fit([0.3, 0.4], [3.0, 5.0], [0, 0])
