#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""ROI / リスク指標 共通ユーティリティ

ml/ 配下で 15+ ファイルに分散していた calc_roi 系を集約。
レース単位リサンプリングの Bootstrap CI を一級市民に。

提供:
    Bet (dataclass)               — 1ベット = (race_id, cost, payout)
    RoiResult (dataclass)         — 集計結果
    calc_roi(bets)                — リスト/DataFrame両対応、bootstrap_n>0 で CI 付き
    bootstrap_roi_ci(...)         — レース単位リサンプリングの Bootstrap CI
    sharpe_ratio / sortino_ratio  — 月次/週次系列向け
    max_drawdown                  — 累積 P&L 系列の MaxDD
    losing_streaks                — 連敗ストリーク (max/avg/n_10plus/max_loss)
    consecutive_loss_months       — 連続マイナス月数
    calc_brier_score / calc_ece   — 確率予測評価
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Sequence, Union

import numpy as np

try:
    import pandas as pd
except ImportError:
    pd = None


# ===========================================================================
# Dataclasses
# ===========================================================================

@dataclass
class Bet:
    """単一ベット"""
    race_id: str
    cost: float          # 投資額
    payout: float        # 払戻 (外れ時 0)
    is_hit: bool = False  # cost>0 かつ payout>0
    odds: float = 0.0
    bet_type: str = ""    # 'win'/'place'/'umaren' 等
    horse_key: str = ""   # umaban や (a,b,c)


@dataclass
class RoiResult:
    """ROI 集計結果"""
    n: int = 0
    cost: float = 0.0
    payout: float = 0.0
    pnl: float = 0.0
    roi: float = 0.0           # (payout / cost) * 100, %
    hit_rate: float = 0.0      # %
    hits: int = 0
    mean_hit_odds: float = 0.0
    ci_low: float = 0.0
    ci_high: float = 0.0
    ci_width: float = 0.0
    bootstrap_n: int = 0

    def __bool__(self) -> bool:
        return self.n > 0

    def as_dict(self) -> dict:
        return {
            "n": self.n,
            "cost": round(self.cost, 1),
            "payout": round(self.payout, 1),
            "pnl": round(self.pnl, 1),
            "roi": round(self.roi, 1),
            "hit_rate": round(self.hit_rate, 1),
            "hits": self.hits,
            "mean_hit_odds": round(self.mean_hit_odds, 2),
            "ci_low": round(self.ci_low, 1),
            "ci_high": round(self.ci_high, 1),
            "ci_width": round(self.ci_width, 1),
            "bootstrap_n": self.bootstrap_n,
        }


# ===========================================================================
# Internal helpers
# ===========================================================================

def _bets_from_df(df, cost_col="cost", payout_col="payout", race_id_col="race_id",
                  odds_col=None, hit_col=None) -> List[Bet]:
    """DataFrame → List[Bet] 変換"""
    bets: List[Bet] = []
    for _, row in df.iterrows():
        cost = float(row[cost_col]) if cost_col in row else 100.0
        payout = float(row[payout_col]) if payout_col in row else 0.0
        odds = float(row[odds_col]) if odds_col and odds_col in row else 0.0
        if hit_col and hit_col in row:
            is_hit = bool(row[hit_col])
        else:
            is_hit = payout > 0
        bets.append(Bet(
            race_id=str(row[race_id_col]),
            cost=cost,
            payout=payout,
            is_hit=is_hit,
            odds=odds,
        ))
    return bets


def _df_from_win_bets(df, race_id_col="race_id", odds_col="odds",
                     is_win_col="is_win", bet_unit: float = 100.0) -> List[Bet]:
    """単勝ベット DataFrame → List[Bet]"""
    bets: List[Bet] = []
    for _, row in df.iterrows():
        odds = float(row[odds_col]) if odds_col in row else 0.0
        is_win = int(row[is_win_col]) == 1
        bets.append(Bet(
            race_id=str(row[race_id_col]),
            cost=bet_unit,
            payout=odds * bet_unit if is_win else 0.0,
            is_hit=is_win,
            odds=odds,
            bet_type="win",
        ))
    return bets


# ===========================================================================
# ROI core
# ===========================================================================

def calc_roi(
    bets: Union[List[Bet], "pd.DataFrame"],
    bootstrap_n: int = 0,
    ci_level: float = 0.95,
    seed: int = 42,
    *,
    cost_col: str = "cost",
    payout_col: str = "payout",
    race_id_col: str = "race_id",
    odds_col: Optional[str] = None,
    hit_col: Optional[str] = None,
) -> RoiResult:
    """ROI を計算する統一エントリポイント

    入力:
        bets        — List[Bet] か DataFrame (cost/payout 列必須)
        bootstrap_n — 0 なら CI 計算なし、>0 ならレース単位リサンプリングで CI 計算
        ci_level    — 信頼水準 (デフォルト 0.95)

    DataFrame の場合は cost_col/payout_col/race_id_col を指定 (デフォルトはそのまま)。
    odds_col を指定すれば mean_hit_odds が算出される。
    """
    if pd is not None and isinstance(bets, pd.DataFrame):
        bet_list = _bets_from_df(
            bets,
            cost_col=cost_col,
            payout_col=payout_col,
            race_id_col=race_id_col,
            odds_col=odds_col,
            hit_col=hit_col,
        )
    else:
        bet_list = list(bets)

    if not bet_list:
        return RoiResult()

    total_cost = sum(b.cost for b in bet_list)
    total_payout = sum(b.payout for b in bet_list)
    n = len(bet_list)
    hits = sum(1 for b in bet_list if b.is_hit)
    pnl = total_payout - total_cost
    roi = (total_payout / total_cost * 100) if total_cost > 0 else 0.0
    hit_rate = (hits / n * 100) if n > 0 else 0.0
    mean_hit_odds = 0.0
    if hits > 0:
        odds_vals = [b.odds for b in bet_list if b.is_hit and b.odds > 0]
        if odds_vals:
            mean_hit_odds = float(np.mean(odds_vals))

    result = RoiResult(
        n=n,
        cost=total_cost,
        payout=total_payout,
        pnl=pnl,
        roi=roi,
        hit_rate=hit_rate,
        hits=hits,
        mean_hit_odds=mean_hit_odds,
    )

    if bootstrap_n > 0:
        ci_low, ci_high = bootstrap_roi_ci(bet_list, n_bootstrap=bootstrap_n,
                                           ci_level=ci_level, seed=seed)
        result.ci_low = ci_low
        result.ci_high = ci_high
        result.ci_width = ci_high - ci_low
        result.bootstrap_n = bootstrap_n

    return result


def calc_win_roi(
    df,
    odds_col: str = "odds",
    is_win_col: str = "is_win",
    race_id_col: str = "race_id",
    bet_unit: float = 100.0,
    bootstrap_n: int = 0,
    ci_level: float = 0.95,
    seed: int = 42,
) -> RoiResult:
    """単勝ベット DataFrame (race_id, odds, is_win) を直接 RoiResult に"""
    if pd is None or not isinstance(df, pd.DataFrame):
        raise TypeError("calc_win_roi requires a pandas DataFrame")
    bet_list = _df_from_win_bets(
        df,
        race_id_col=race_id_col,
        odds_col=odds_col,
        is_win_col=is_win_col,
        bet_unit=bet_unit,
    )
    return calc_roi(bet_list, bootstrap_n=bootstrap_n, ci_level=ci_level, seed=seed)


# ===========================================================================
# Bootstrap CI (race-grouped)
# ===========================================================================

def bootstrap_roi_ci(
    bets: List[Bet],
    n_bootstrap: int = 2000,
    ci_level: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]:
    """レース単位リサンプリングで ROI の Bootstrap CI を計算

    同一レース内の馬は独立でない (1頭勝つと他が負ける) ため、
    レース ID をリサンプリングして該当する全ベットをまとめて取る。

    Returns: (ci_low, ci_high) — %
    """
    if not bets:
        return (0.0, 0.0)
    rng = np.random.default_rng(seed)
    alpha = (1 - ci_level) / 2

    # race_id -> [bet,...]
    by_race: dict[str, List[Bet]] = {}
    for b in bets:
        by_race.setdefault(b.race_id, []).append(b)

    race_ids = list(by_race.keys())
    n_races = len(race_ids)
    if n_races == 0:
        return (0.0, 0.0)

    rois: List[float] = []
    for _ in range(n_bootstrap):
        sampled = rng.choice(race_ids, size=n_races, replace=True)
        total_cost = 0.0
        total_payout = 0.0
        for rid in sampled:
            for b in by_race[rid]:
                total_cost += b.cost
                total_payout += b.payout
        if total_cost > 0:
            rois.append(total_payout / total_cost * 100)

    if not rois:
        return (0.0, 0.0)
    arr = np.array(rois)
    return (float(np.percentile(arr, alpha * 100)),
            float(np.percentile(arr, (1 - alpha) * 100)))


# ===========================================================================
# Risk metrics
# ===========================================================================

def sharpe_ratio(returns: Sequence[float], rf: float = 0.0, periods_per_year: int = 12) -> float:
    """Sharpe 比 — 月次/週次 ROI 系列の (μ - rf) / σ × √periods_per_year

    returns: 各期間の単純リターン (%) でも (P&L/cost) でも可。 単位を統一すること。
    rf: 無リスク利率 (同じ単位)
    """
    arr = np.asarray(returns, dtype=float)
    if arr.size < 2:
        return 0.0
    std = arr.std(ddof=1)
    if std == 0:
        return 0.0
    return float((arr.mean() - rf) / std * np.sqrt(periods_per_year))


def sortino_ratio(returns: Sequence[float], rf: float = 0.0, periods_per_year: int = 12) -> float:
    """Sortino 比 — 下方リスクのみで割る"""
    arr = np.asarray(returns, dtype=float)
    if arr.size < 2:
        return 0.0
    downside = arr[arr < rf]
    if downside.size == 0:
        return float("inf")
    dd_std = np.sqrt(np.mean((downside - rf) ** 2))
    if dd_std == 0:
        return 0.0
    return float((arr.mean() - rf) / dd_std * np.sqrt(periods_per_year))


def max_drawdown(cum_pnl: Sequence[float]) -> tuple[float, float]:
    """累積 P&L 系列の最大ドローダウン

    Returns: (max_dd_amount, dd_pct_from_peak)
    """
    arr = np.asarray(cum_pnl, dtype=float)
    if arr.size == 0:
        return (0.0, 0.0)
    peak = np.maximum.accumulate(arr)
    drawdown = arr - peak
    idx = int(np.argmin(drawdown))
    max_dd = float(drawdown[idx])
    peak_val = float(peak[idx])
    dd_pct = (max_dd / peak_val * 100) if peak_val > 0 else 0.0
    return (max_dd, dd_pct)


def losing_streaks(is_hit_series: Sequence[int], bet_unit: float = 100.0) -> dict:
    """連敗ストリーク

    Args:
        is_hit_series: 時系列順の 0/1 (1=的中)
        bet_unit: 1ベット単位 (損失累計用)

    Returns:
        {max_streak, avg_streak, streak_10plus, max_streak_loss}
    """
    streaks: List[tuple[int, float]] = []
    cur_n = 0
    cur_loss = 0.0
    for hit in is_hit_series:
        if int(hit) == 0:
            cur_n += 1
            cur_loss += bet_unit
        else:
            if cur_n > 0:
                streaks.append((cur_n, cur_loss))
            cur_n = 0
            cur_loss = 0.0
    if cur_n > 0:
        streaks.append((cur_n, cur_loss))

    if not streaks:
        return {"max_streak": 0, "avg_streak": 0.0,
                "streak_10plus": 0, "max_streak_loss": 0.0}
    return {
        "max_streak": max(s[0] for s in streaks),
        "avg_streak": round(float(np.mean([s[0] for s in streaks])), 1),
        "streak_10plus": sum(1 for s in streaks if s[0] >= 10),
        "max_streak_loss": max(s[1] for s in streaks),
    }


def consecutive_loss_months(monthly_pnl: Sequence[float]) -> int:
    """最長連続マイナス月数"""
    max_consec = 0
    cur = 0
    for pnl in monthly_pnl:
        if pnl < 0:
            cur += 1
            max_consec = max(max_consec, cur)
        else:
            cur = 0
    return max_consec


# ===========================================================================
# Probabilistic prediction metrics
# ===========================================================================

def calc_brier_score(y_true, y_pred) -> float:
    """Brier Score: 確率予測の精度指標 (低いほど良い)"""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.mean((y_pred - y_true) ** 2))


def calc_ece(y_true, y_pred, n_bins: int = 10) -> float:
    """Expected Calibration Error

    予測確率をビンに分割し、各ビンの「予測平均」と「実際の正例率」の
    加重平均差を計算。低いほどキャリブレーションが良い。
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    if len(y_true) == 0:
        return 0.0
    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for i in range(n_bins):
        mask = (y_pred >= bin_edges[i]) & (y_pred < bin_edges[i + 1])
        if i == n_bins - 1:
            mask = mask | (y_pred == 1.0)  # 1.0 も最終ビンに
        if mask.sum() == 0:
            continue
        bin_acc = y_true[mask].mean()
        bin_conf = y_pred[mask].mean()
        ece += mask.sum() / len(y_true) * abs(bin_acc - bin_conf)
    return float(ece)


def calibration_curve(y_true, y_pred, n_bins: int = 10) -> List[dict]:
    """キャリブレーション曲線データ

    Returns: [{bin_lo, bin_hi, n, mean_pred, actual_rate}]
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    bin_edges = np.linspace(0, 1, n_bins + 1)
    rows: List[dict] = []
    for i in range(n_bins):
        lo, hi = bin_edges[i], bin_edges[i + 1]
        if i == n_bins - 1:
            mask = (y_pred >= lo) & (y_pred <= hi)
        else:
            mask = (y_pred >= lo) & (y_pred < hi)
        n = int(mask.sum())
        if n == 0:
            rows.append({"bin_lo": lo, "bin_hi": hi, "n": 0,
                         "mean_pred": 0.0, "actual_rate": 0.0})
            continue
        rows.append({
            "bin_lo": float(lo), "bin_hi": float(hi), "n": n,
            "mean_pred": float(y_pred[mask].mean()),
            "actual_rate": float(y_true[mask].mean()),
        })
    return rows
