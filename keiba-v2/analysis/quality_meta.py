#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
E-001 品質メタ標準化 — 共通ヘルパ (Session 153 / 仕様 v1.2)

各分析JSONの統計エントリに信頼性メタ
  quality:{metric, ci95, effective_n, stability_flag, algo, ...}
を付与するための純関数。JSON walk（どのエントリに付けるか）は各 builder の
責務で、本モジュールは「1エントリ分の計算」のみを担う（仕様 §4 / S-7）。

仕様: docs/ml-experiments/202606_analysis_reuse/E001_quality_meta_spec.md
- ci95 algo: wilson_binomial / bayesian_beta_binomial / mean_se / none
- prior は指標別・必須引数（一律デフォルト禁止 B-4）。PRIORS で公開。
- stability は CI ベース判定（恣意閾値廃止 S-2）。
- effective_n は率系=raw n / 連続量weighted=(Σw)²/Σw²（§3）。
- 「率×n で hits 復元」は呼び出し側でも全面禁止（B-2）。生カウントを渡すこと。
"""

import math
from typing import Optional, Sequence

from scipy.stats import beta as _beta, t as _t

Z95 = 1.96

# 指標別 prior Beta(α,β): prior mean ≒ 指標の全体ベース率、strength ≒ 10〜13走分（§3 / B-4）。
# 「踏襲」すべきは定数でなくこの設計哲学。一律デフォルト禁止のため、
# 呼び出し側が metric に対応するものを明示的に渡す（自動 fallback はしない）。
PRIORS = {
    "win_rate":        (1.0, 12.0),   # base≈0.077（build_sire_stats.py 既存踏襲）
    "top3_rate":       (2.5, 7.5),    # base=0.25 （build_sire_stats.py 既存踏襲）
    "close_win_rate":  (5.0, 5.0),    # base=0.50 （接戦=2頭の競り合い構造上）
    "slow_start_rate": (2.6, 9.4),    # base≈0.216（=33,749/156,038）
}

# pedigree_features.py:19-22 の複製を一元化（E-010。あちらは import に置換予定）。
PRIOR_TOP3_ALPHA, PRIOR_TOP3_BETA = PRIORS["top3_rate"]
MIN_RUNS_CONDITIONAL = 10

_VALID_ALGOS = {"wilson_binomial", "bayesian_beta_binomial", "mean_se", "none"}


# ----------------------------------------------------------------------------
# ci95 算出（algo 別）
# ----------------------------------------------------------------------------

def wilson_ci(hits: int, n: int, z: float = Z95) -> Optional[dict]:
    """Wilson score 区間（率・非選抜・n大）。"""
    if n is None or n <= 0:
        return None
    p = hits / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return {"lower": round(center - half, 4), "upper": round(center + half, 4)}


def bayesian_ci(hits: int, n: int, prior) -> Optional[dict]:
    """事後 Beta(α+hits, β+n−hits) の 2.5/97.5%ile。prior は必須（B-4）。"""
    if prior is None:
        raise ValueError("bayesian_beta_binomial requires explicit prior=(alpha,beta)")
    if n is None or n < 0 or hits is None or hits < 0:
        return None
    a, b = prior
    post_a = a + hits
    post_b = b + (n - hits)
    return {
        "lower": round(float(_beta.ppf(0.025, post_a, post_b)), 4),
        "upper": round(float(_beta.ppf(0.975, post_a, post_b)), 4),
    }


def mean_se_ci(mean: float, stdev: float, n: Optional[int],
               weights: Optional[Sequence[float]] = None):
    """連続量（RPCI / IDM）の mean ± crit·SE。

    戻り値: (ci95 dict|None, effective_n float|None)
    - 非weighted: SE = stdev/√n、effective_n = n
    - weighted  : SE = √(Σw²)·stdev/Σw、effective_n = (Σw)²/Σw²（§3 RPCI 規定）
    - effective_n ≥ 30 は z=1.96、それ未満は t 分布（df = effective_n−1, N-1）
    """
    if mean is None or stdev is None:
        return None, None
    if weights:
        sw = sum(weights)
        sw2 = sum(w * w for w in weights)
        if sw <= 0 or sw2 <= 0:
            return None, None
        eff_n = (sw * sw) / sw2
        se = math.sqrt(sw2) * stdev / sw
    else:
        if not n or n <= 0:
            return None, None
        eff_n = float(n)
        se = stdev / math.sqrt(n)
    if eff_n >= 30:
        crit = Z95
    elif eff_n > 1:
        crit = float(_t.ppf(0.975, eff_n - 1))
    else:
        return None, eff_n
    return {"lower": round(mean - crit * se, 4), "upper": round(mean + crit * se, 4)}, eff_n


# ----------------------------------------------------------------------------
# stability（CI ベース判定 S-2）
# ----------------------------------------------------------------------------

def _point_value(rec: dict, is_rate: bool):
    """年レコードから (代表値, n) を取り出す。算出不能なら (None, n)。"""
    if not isinstance(rec, dict):
        return None, 0
    n = rec.get("n")
    if not n or n <= 0:
        return None, n or 0
    if is_rate:
        h = rec.get("hits")
        if h is None:
            return None, n
        return h / n, n
    m = rec.get("mean")
    if m is None:
        return None, n
    return m, n


def stability_flag(year_data: Optional[dict], ci95: Optional[dict],
                   is_rate: bool = True, min_latest_n: int = 20) -> str:
    """drift ⇔ 最新年の値が全期間 ci95 の外 ∧ 最新年 n ≥ min_latest_n。

    year_data 無し / 全年欠損 / 最新年 n<min_latest_n → insufficient（「安定」と誤読させない）。
    None年・欠損年はスキップ（接戦の close_win_rate:None 年等）。率/連続量で同一ロジック。
    注意: 最新年は部分年（季節偏り）。鮮度(coverage)は運用配線が担保し stability と混同しない。
    """
    if not year_data or ci95 is None:
        return "insufficient"
    valid = []
    for y in sorted(year_data.keys()):
        rec = year_data[y]
        if rec is None:
            continue
        val, n = _point_value(rec, is_rate)
        if val is None:
            continue
        valid.append((y, val, n))
    if not valid:
        return "insufficient"
    _, latest_val, latest_n = valid[-1]
    if latest_n < min_latest_n:
        return "insufficient"
    if latest_val < ci95["lower"] or latest_val > ci95["upper"]:
        return "drift"
    return "stable"


# ----------------------------------------------------------------------------
# メイン: 1エントリ分の quality を組み立てる
# ----------------------------------------------------------------------------

def quality_meta(*, metric: str, algo: str,
                 hits: Optional[int] = None, n: Optional[int] = None, prior=None,
                 mean: Optional[float] = None, stdev: Optional[float] = None,
                 weights: Optional[Sequence[float]] = None,
                 year_data: Optional[dict] = None, min_n: Optional[int] = None,
                 selected: bool = False, source: Optional[str] = None,
                 original_n: Optional[int] = None) -> dict:
    """1エントリ分の quality dict を返す（仕様 §2 スキーマ）。

    - bayesian は prior 必須（B-4）。prior=None で ValueError。
    - effective_n は率系=raw n、連続量weighted=(Σw)²/Σw²（§3。二重補正防止のため
      ベイズでも raw n を返す — n+α+β にはしない S-5）。
    - n（連続量は effective_n）< min_n → stability_flag="insufficient"（ci95 自体は出してよい）。
    """
    if algo not in _VALID_ALGOS:
        raise ValueError(f"unknown algo: {algo}")

    ci95 = None
    effective_n = n
    is_rate = True

    if algo == "wilson_binomial":
        if hits is None or n is None:
            raise ValueError("wilson_binomial requires hits and n")
        ci95 = wilson_ci(hits, n)
        effective_n = n
    elif algo == "bayesian_beta_binomial":
        if hits is None or n is None:
            raise ValueError("bayesian_beta_binomial requires hits and n")
        ci95 = bayesian_ci(hits, n, prior)   # prior=None → ValueError
        effective_n = n                       # 常に raw n（S-5 二重補正防止）
    elif algo == "mean_se":
        is_rate = False
        ci95, eff = mean_se_ci(mean, stdev, n, weights)
        effective_n = int(round(eff)) if eff is not None else n
    # algo == "none": ci95=None のまま

    # stability / min_n（min_n 判定は effective_n ベース＝率も連続量も整合）
    eff_for_minn = effective_n
    if min_n is not None and (eff_for_minn is None or eff_for_minn < min_n):
        flag = "insufficient"
    else:
        flag = stability_flag(year_data, ci95, is_rate=is_rate)

    out = {
        "metric": metric,
        "ci95": ci95,
        "effective_n": effective_n,
        "stability_flag": flag,
        "algo": algo,
    }
    if selected:
        out["selected"] = True
    if source is not None:
        out["source"] = source
    if original_n is not None:
        out["original_n"] = original_n
    return out
