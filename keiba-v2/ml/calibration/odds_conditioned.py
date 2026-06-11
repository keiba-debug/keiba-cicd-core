#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""オッズ条件付き複勝較正 (Session 150)

P複勝モデルの生スコア raw を、単勝オッズを条件に入れて較正する。

背景: Isotonic(cal_p) は raw の単調変換ゆえ、オッズ軸の系統誤差
(人気馬の複勝を実測比 -0.44 過小評価) を分離できない (raw が同値でも人気馬と大穴で
実複勝率が違うため)。 そこで logit(p)=a*logit(raw)+b*log(odds)+c の2入力ロジスティックで
較正する。 原理確認(案X)で <2.9帯の乖離 -0.458 → -0.085 を確認済
(ml/analyze/fit_place_odds_calibration.py)。

設計原則: 「モデル本体は触らない」後処理層。 cal_p の置換でなく並走 (place_ev_oc)。
sklearn LogisticRegression を内包し pickle 可 → calibrators.pkl に同梱できる。
"""

from __future__ import annotations

import numpy as np

_RAW_EPS = 1e-4
_ODDS_FLOOR = 1.0
_FEATURE_NAMES = ("logit_raw", "log_odds")


class OddsConditionedCalibrator:
    """raw(複勝生スコア) + 単勝オッズ → 較正済み複勝確率 P(3着内)。

    fit(raw, odds, y): logit(p)=a*logit(raw)+b*log(odds)+c をロジスティック回帰で学習。
    predict(raw, odds): 較正確率 (0..1) の np.ndarray。
    coef_['log_odds'] が負 = 人気(低オッズ)ほど複勝率高い(常識と一致)。
    coef_['logit_raw'] が正で残る = raw がオッズを超える情報を持つ(=妙味の源)。
    """

    def __init__(self, C: float = 1e6, max_iter: int = 2000):
        self.C = C
        self.max_iter = max_iter
        self._clf = None
        self.coef_ = None
        self.intercept_ = None
        self.n_fit_ = 0

    @staticmethod
    def _design(raw, odds):
        raw = np.clip(np.asarray(raw, dtype=float), _RAW_EPS, 1 - _RAW_EPS)
        odds = np.clip(np.asarray(odds, dtype=float), _ODDS_FLOOR, None)
        return np.column_stack([np.log(raw / (1.0 - raw)), np.log(odds)])

    def fit(self, raw, odds, y) -> "OddsConditionedCalibrator":
        from sklearn.linear_model import LogisticRegression
        X = self._design(raw, odds)
        y = np.asarray(y, dtype=int)
        if len(np.unique(y)) < 2:
            raise ValueError("fit には y に 0/1 両方が必要")
        self._clf = LogisticRegression(C=self.C, max_iter=self.max_iter).fit(X, y)
        self.coef_ = dict(zip(_FEATURE_NAMES, (float(c) for c in self._clf.coef_[0])))
        self.intercept_ = float(self._clf.intercept_[0])
        self.n_fit_ = int(len(y))
        return self

    def predict(self, raw, odds) -> np.ndarray:
        if self._clf is None:
            raise RuntimeError("OddsConditionedCalibrator.predict() before fit()")
        raw_arr = np.atleast_1d(np.asarray(raw, dtype=float))
        odds_arr = np.atleast_1d(np.asarray(odds, dtype=float))
        if raw_arr.shape != odds_arr.shape:
            raise ValueError(f"raw と odds の長さ不一致: {raw_arr.shape} vs {odds_arr.shape}")
        return self._clf.predict_proba(self._design(raw_arr, odds_arr))[:, 1]

    def predict_one(self, raw: float, odds: float) -> float:
        return float(self.predict([raw], [odds])[0])

    def __repr__(self) -> str:
        if self._clf is None:
            return "OddsConditionedCalibrator(unfit)"
        return (f"OddsConditionedCalibrator(intercept={self.intercept_:+.3f}, "
                f"logit_raw={self.coef_['logit_raw']:+.3f}, "
                f"log_odds={self.coef_['log_odds']:+.3f}, n={self.n_fit_})")
