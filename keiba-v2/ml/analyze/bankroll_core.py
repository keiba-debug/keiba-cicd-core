#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""2層バンクロール複利エンジンの共通コア (Session 149 / T12)

simulate_bankroll_bettype (bettype 選定経路) と simulate_bankroll_character
(買い方テンプレ経路) が共有する、 **買い目生成に非依存** な複利・破産確率・
メトリクス層。 「日次の買い目生成 (simulate_day_fn) を注入し、 総資金 W を
day_fraction で2層化して複利で回す」 骨格だけを持つ。

★2層バンクロール構造 (ふくだ Session 146):
  - 総資金レイヤー W (例 30万)
  - 日次スタート額 = W × day_fraction (例 10% → 3万)
  - 日次 PnL を W にフィードバック → 翌開催日のスタート額を再計算。
    「連勝でその場で増額」ではなく「総資金の固定% を開催日境界で再適用」=
    規律的な比例ベット (破産確率を下げる)。

simulate_day_fn の契約:
    simulate_day_fn(ctxs, *, day_start, w_total, **day_kwargs) -> (cost, payout)
  - ctxs    : その開催日の bankroll 非依存コンテキスト列 (型は呼び出し側が決める)
  - day_start: その日の予算 = W × day_fraction (100円丸め済)
  - w_total : その時点の総資金。 テンプレ版は base_unit = W × unit_fraction の
              総資金比例ベットに使う。 bettype 版は day_start ベースの Kelly なので
              受け取るだけで無視してよい。
  - 戻り    : (その日の総コスト, 総払戻)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple

import numpy as np

# --- 既定値 (両経路で共有) ---
MIN_DAY_START = 1000              # スタート額の下限 (これ未満なら実質ベット不能)
DEFAULT_TAIL_THRESHOLD = 0.50     # 日次でスタート額の 50%+ を溶かした日 = テール
DEFAULT_RUIN_FRAC = 0.50          # 総資金が初期の 50% を割ったら「破産」
DEFAULT_MC = 3000                 # 破産確率 Monte Carlo 試行数

SimulateDayFn = Callable[..., Tuple[float, float]]


# ---------------------------------------------------------------------------
# 複利トラジェクトリ
# ---------------------------------------------------------------------------

def run_trajectory(
    by_date: Dict[str, list], *, w0: int, day_fraction: float,
    simulate_day_fn: SimulateDayFn, day_kwargs: Dict = None,
) -> Tuple[List[float], List[float], float, float, List[str]]:
    """決定論的に時系列複利。 戻り: (equity, day_returns, total_cost, total_payout, dates)。

    day_returns[t] = day_pnl / day_start (bankroll 非依存・破産 MC 用)。
    dates[t] = その日の日付キー (history 出力用。 破産後の穴埋めは "")。
    """
    day_kwargs = day_kwargs or {}
    w = float(w0)
    equity = [w]
    day_returns: List[float] = []
    dates: List[str] = []
    total_cost = total_payout = 0.0
    for date, ctxs in by_date.items():
        day_start = int(w * day_fraction) // 100 * 100
        if day_start < MIN_DAY_START:
            equity.append(w)
            day_returns.append(0.0)
            dates.append(date)
            continue
        cost, payout = simulate_day_fn(ctxs, day_start=day_start, w_total=w, **day_kwargs)
        pnl = payout - cost
        w += pnl
        total_cost += cost
        total_payout += payout
        r = (pnl / day_start) if day_start > 0 else 0.0
        day_returns.append(r)
        dates.append(date)
        equity.append(w)
        if w <= 0:
            # 破産 (理論上は frac<1 で 0 にならないが安全弁)。 残り日を穴埋め。
            for _ in range(len(by_date) - len(dates)):
                equity.append(max(0.0, w))
                day_returns.append(0.0)
                dates.append("")
            break
    return equity, day_returns, total_cost, total_payout, dates


def _max_dd(equity: List[float]) -> float:
    """equity curve の最大ドローダウン (%・peak 比)。"""
    peak = equity[0]
    mdd = 0.0
    for v in equity:
        peak = max(peak, v)
        if peak > 0:
            mdd = max(mdd, (peak - v) / peak)
    return mdd * 100.0


def _sharpe(day_returns: List[float]) -> float:
    arr = np.array([r for r in day_returns if r != 0.0], dtype=float)
    if arr.size < 2:
        return 0.0
    sd = arr.std(ddof=1)
    return float(arr.mean() / sd) if sd > 0 else 0.0


def ruin_probability(
    day_returns: List[float], *, w0: int, day_fraction: float, ruin_frac: float,
    mc: int, seed: int = 12345,
) -> float:
    """日次リターン rₜ 列を MC シャッフルし、 複利で総資金が w0·ruin_frac を割る試行割合。

    乗法的複利: W_{t+1} = W_t + (W_t·day_fraction)·rₜ = W_t·(1 + day_fraction·rₜ)。
    rₜ は bankroll 非依存 (金額が day_start に線形) という近似に基づく
    (100円丸め・base_unit 固定割合のため厳密ではない旨を明記)。
    """
    rs = np.array([r for r in day_returns], dtype=float)
    rs = rs[rs != 0.0]
    if rs.size == 0:
        return 0.0
    rng = np.random.default_rng(seed)
    threshold = ruin_frac
    ruined = 0
    n_days = rs.size
    for _ in range(mc):
        order = rng.permutation(n_days)
        mult = 1.0
        hit = False
        for idx in order:
            mult *= (1.0 + day_fraction * rs[idx])
            if mult <= threshold:
                hit = True
                break
        if hit:
            ruined += 1
    return ruined / mc * 100.0


# ---------------------------------------------------------------------------
# 集約メトリクス
# ---------------------------------------------------------------------------

@dataclass
class TrajectoryStats:
    """1 軌道 (1 設定) のメトリクス。 ラベル (rule / character 等) は呼び出し側で付与。"""
    w0: int
    day_fraction: float
    final_w: float
    growth_pct: float
    max_dd_pct: float
    sharpe: float
    tail_day_rate: float       # スタート額の tail_threshold 以上を溶かした日の割合
    bet_days: int
    flat_roi_pct: float        # Σpayout/Σcost (非複利・参考)
    ruin_prob_pct: float       # Monte Carlo: 総資金が初期 ruin_frac を割った試行割合
    equity: List[float] = field(default_factory=list)
    dates: List[str] = field(default_factory=list)
    day_returns: List[float] = field(default_factory=list)


def compute_trajectory_stats(
    by_date: Dict[str, list], *, w0: int, day_fraction: float,
    simulate_day_fn: SimulateDayFn, day_kwargs: Dict = None,
    tail_threshold: float = DEFAULT_TAIL_THRESHOLD,
    ruin_frac: float = DEFAULT_RUIN_FRAC, mc: int = DEFAULT_MC,
) -> TrajectoryStats:
    """1 設定を複利で回し、 成長率・maxDD・Sharpe・破産確率まで一括算出。"""
    equity, day_returns, total_cost, total_payout, dates = run_trajectory(
        by_date, w0=w0, day_fraction=day_fraction,
        simulate_day_fn=simulate_day_fn, day_kwargs=day_kwargs)
    final_w = equity[-1]
    growth = (final_w / w0 - 1.0) * 100.0
    bet_days = sum(1 for r in day_returns if r != 0.0)
    tail_days = sum(1 for r in day_returns if r <= -tail_threshold)
    tail_rate = (tail_days / bet_days * 100.0) if bet_days > 0 else 0.0
    flat_roi = (total_payout / total_cost * 100.0) if total_cost > 0 else 0.0
    ruin = ruin_probability(
        day_returns, w0=w0, day_fraction=day_fraction, ruin_frac=ruin_frac, mc=mc)
    return TrajectoryStats(
        w0=w0, day_fraction=day_fraction, final_w=final_w, growth_pct=growth,
        max_dd_pct=_max_dd(equity), sharpe=_sharpe(day_returns),
        tail_day_rate=tail_rate, bet_days=bet_days, flat_roi_pct=flat_roi,
        ruin_prob_pct=ruin, equity=equity, dates=dates, day_returns=day_returns)
