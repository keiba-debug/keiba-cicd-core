#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""W9: multi-bettype 経路の 2層バンクロールシミュレーション (Session 146)

bettype_selection → bettype_sizing の実際の買い目で、 過去開催日を複利で回し、
「資金配分ルール」ごとに 総資金成長 / maxDD / 日次テールリスク / Sharpe / 破産確率 を
比較する。 ふくだ W9 = 「評価は信じる・配分で勝つ」を実測で正当化するための道具。

★2層バンクロール構造 (ふくだ要望 Session 146):
  - 総資金レイヤー W_total (例 30万)
  - 日次スタート額 = W_total × day_fraction (例 10% → 3万)
  - 日次 PnL を W_total にフィードバック → 翌開催日のスタート額を再計算
    (+10万で終えたら次は 40万×10%=4万)。 「連勝でその場で増額」ではなく
    「総資金の固定% を開催日境界で再適用」= 規律的な比例ベット (破産確率を下げる)。

★比較する資金配分ルール (日内サイジング):
  - B (frozen) : 当日スタート額で Kelly bankroll を凍結 (live 第一候補・§3 哲学整合)
  - C (follow) : 日内の現残高 (= スタート額 + その日の確定 PnL) に Kelly bankroll を追従
  - D (reserve): Kelly は B と同じだが per_race_cap を「残予算 ÷ 残レース数」で本命に確保

選定ロジック (どの馬・どの券種) は触らない。 strategy/sizing は固定で、 資金配分だけ比較する。

効率化: 選定 + RaceEfficiency (DB オッズ) は bankroll 非依存なので 1 レース 1 回キャッシュし、
  ルール sweep は安い re-sizing のみ。 破産確率は乗法的複利 (W_{t+1}=W_t(1+frac·rₜ)) を
  利用し、 日次リターン rₜ 列を Monte Carlo シャッフルして算出。

CLI:
    python -m ml.analyze.simulate_bankroll_bettype
    python -m ml.analyze.simulate_bankroll_bettype --w0 300000 \
        --day-fractions 0.05,0.10,0.20 --rules B,C,D --mc 3000
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.analyze.backtest_bettype_fund import (  # noqa: E402
    cache_race_to_pred, simulate_legs,
)
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.strategies import bettype_selection as bs  # noqa: E402
from ml.strategies import bettype_sizing as sz  # noqa: E402
from ml.utils.backtest_cache import load_backtest_cache  # noqa: E402

DEFAULT_W0 = 300_000           # 総資金 (全体資金)
DEFAULT_DAY_FRACTIONS = (0.05, 0.10, 0.20)
DEFAULT_KELLY_FRACTION = 0.25
DEFAULT_PER_RACE_CAP_PCT = 0.10   # 1レース上限 = 日次スタート額 × この割合 (30000→3000=現行 live 相当)
DEFAULT_RULES = ("B", "C", "D")
DEFAULT_TAIL_THRESHOLD = 0.50     # 日次でスタート額の 50%+ を溶かした日 = テール
DEFAULT_RUIN_FRAC = 0.50          # 総資金が初期の 50% を割ったら「破産」
DEFAULT_MC = 3000                 # 破産確率 Monte Carlo 試行数
MIN_DAY_START = 1000              # スタート額の下限 (これ未満なら実質ベット不能)


# ---------------------------------------------------------------------------
# Phase A: レースごとに選定 + RaceEfficiency をキャッシュ (DB は 1 回だけ)
# ---------------------------------------------------------------------------

@dataclass
class RaceCtx:
    """1 レースの bankroll 非依存コンテキスト (re-sizing で使い回す)。"""
    pred_race: dict
    selection: object          # bs.BetSelection
    race_eff: object           # be.RaceEfficiency


def build_race_contexts(
    races: List[dict], *, strategy: str, ev_floor: float = bs.DEFAULT_EV_FLOOR,
) -> Dict[str, List[RaceCtx]]:
    """日付 -> [RaceCtx] (選定成立 & 1着確定のレースのみ)。"""
    by_date: Dict[str, List[RaceCtx]] = {}
    n_total = n_kept = 0
    for raw in races:
        pred = cache_race_to_pred(raw)
        if pred is None:
            continue
        n_total += 1
        # 結果未確定 (1着なし) は精算不能 → 除外 (backtest_bettype_fund と同基準)
        if not any(int(e.get("finish_position") or 99) == 1
                   for e in pred.get("entries", [])):
            continue
        sel = bs.evaluate_and_select(pred, strategy=strategy, ev_floor=ev_floor)
        if sel is None:
            continue
        race_eff = be.process_race(pred, axis=sel.axis_umaban)
        if race_eff is None:
            continue
        date = str(pred["race_id"])[:8]
        by_date.setdefault(date, []).append(
            RaceCtx(pred_race=pred, selection=sel, race_eff=race_eff))
        n_kept += 1
    print(f"  race contexts: {n_kept}/{n_total} races kept, {len(by_date)} days")
    return dict(sorted(by_date.items()))


# ---------------------------------------------------------------------------
# Phase B: 1 開催日を 1 ルールで回す (安い re-sizing)
# ---------------------------------------------------------------------------

def _size_race(ctx: RaceCtx, *, sizing: str, bankroll: int, per_race_cap: int,
               kelly_fraction: float) -> object:
    """RaceCtx を与えられた bankroll/cap で re-size (DB 非依存)。"""
    return sz.get_sizer(sizing)(
        ctx.race_eff, ctx.selection, bankroll=bankroll, per_race_cap=per_race_cap,
        kelly_fraction=kelly_fraction)


def simulate_day(
    ctxs: List[RaceCtx], *, day_start: int, rule: str, sizing: str,
    kelly_fraction: float, per_race_cap_pct: float,
    exclude_bet_types: Tuple[str, ...] = (),
) -> Tuple[int, int]:
    """1 開催日を時系列順に回す。 戻り: (day_cost, day_payout)。

    先着順 (race_id 昇順 = 時系列) で per_day=day_start を enforce (live 再現)。
    rule で Kelly bankroll / per_race_cap の決め方を変える。
    """
    voted = 0
    payout_sum = 0
    cost_sum = 0
    day_pnl = 0
    base_cap = max(sz.MIN_BET_YEN, int(day_start * per_race_cap_pct) // 100 * 100)
    n = len(ctxs)
    for i, ctx in enumerate(sorted(ctxs, key=lambda c: str(c.pred_race["race_id"]))):
        remaining_budget = max(0, day_start - voted)
        if remaining_budget < sz.MIN_BET_YEN:
            break
        # --- ルール別 Kelly bankroll / per_race_cap ---
        if rule == "C":
            # 日内の現残高 (スタート + その日の確定 PnL) に追従
            kelly_bankroll = max(MIN_DAY_START, day_start + day_pnl)
            per_race_cap = min(base_cap, remaining_budget)
        elif rule == "D":
            # Kelly は凍結、 per_race_cap = 残予算 ÷ 残レース数 (本命に確保)
            kelly_bankroll = day_start
            remaining_races = n - i
            reserve_cap = remaining_budget // max(1, remaining_races) // 100 * 100
            per_race_cap = min(base_cap, max(sz.MIN_BET_YEN, reserve_cap), remaining_budget)
        else:  # B (frozen) = live 第一候補
            kelly_bankroll = day_start
            per_race_cap = min(base_cap, remaining_budget)

        rs = _size_race(ctx, sizing=sizing, bankroll=kelly_bankroll,
                        per_race_cap=per_race_cap, kelly_fraction=kelly_fraction)
        if rs is None or not rs.legs:
            continue
        if exclude_bet_types:
            rs.legs = [l for l in rs.legs if l.bet_type not in exclude_bet_types]
            rs.total_yen = sum(l.amount for l in rs.legs)
            if not rs.legs:
                continue
        if voted + rs.total_yen > day_start:
            continue  # 日次キャップ超過 → 先着順で見送り (live 再現)
        bets = simulate_legs(ctx.pred_race, rs)
        c = int(sum(b.cost for b in bets))
        p = int(sum(b.payout for b in bets))
        if c <= 0:
            continue
        voted += c
        cost_sum += c
        payout_sum += p
        day_pnl += p - c
    return cost_sum, payout_sum


# ---------------------------------------------------------------------------
# 複利トラジェクトリ + メトリクス
# ---------------------------------------------------------------------------

@dataclass
class SimResult:
    rule: str
    day_fraction: float
    kelly_fraction: float
    w0: int
    final_w: float
    growth_pct: float
    max_dd_pct: float
    sharpe: float
    tail_day_rate: float       # スタート額の tail_threshold 以上を溶かした日の割合
    bet_days: int
    flat_roi_pct: float        # Σpayout/Σcost (非複利・参考)
    ruin_prob_pct: float       # Monte Carlo: 総資金が初期 ruin_frac を割った試行割合
    day_returns: List[float] = field(default_factory=list)  # rₜ = day_pnl/day_start


def run_trajectory(
    by_date: Dict[str, List[RaceCtx]], *, w0: int, day_fraction: float, rule: str,
    sizing: str, kelly_fraction: float, per_race_cap_pct: float,
    tail_threshold: float, exclude_bet_types: Tuple[str, ...] = (),
) -> Tuple[List[float], List[float], float, float]:
    """決定論的に時系列複利。 戻り: (equity_curve, day_returns, total_cost, total_payout)。"""
    w = float(w0)
    equity = [w]
    day_returns: List[float] = []
    total_cost = total_payout = 0.0
    for date, ctxs in by_date.items():
        day_start = int(w * day_fraction) // 100 * 100
        if day_start < MIN_DAY_START:
            equity.append(w)
            day_returns.append(0.0)
            continue
        cost, payout = simulate_day(
            ctxs, day_start=day_start, rule=rule, sizing=sizing,
            kelly_fraction=kelly_fraction, per_race_cap_pct=per_race_cap_pct,
            exclude_bet_types=exclude_bet_types)
        pnl = payout - cost
        w += pnl
        total_cost += cost
        total_payout += payout
        # 日次リターン rₜ = PnL / スタート額 (bankroll 非依存・MC 用)
        r = (pnl / day_start) if day_start > 0 else 0.0
        day_returns.append(r)
        equity.append(w)
        if w <= 0:
            # 破産 (理論上は frac<1 で 0 にならないが安全弁)
            for _ in range(len(by_date) - len(equity) + 1):
                equity.append(max(0.0, w))
                day_returns.append(0.0)
            break
    return equity, day_returns, total_cost, total_payout


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
    (100円丸め・per_race_cap 固定割合のため厳密ではない旨を docstring 明記)。
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


def run_config(
    by_date: Dict[str, List[RaceCtx]], *, w0: int, day_fraction: float, rule: str,
    sizing: str, kelly_fraction: float, per_race_cap_pct: float,
    tail_threshold: float, ruin_frac: float, mc: int,
    exclude_bet_types: Tuple[str, ...] = (),
) -> SimResult:
    equity, day_returns, total_cost, total_payout = run_trajectory(
        by_date, w0=w0, day_fraction=day_fraction, rule=rule, sizing=sizing,
        kelly_fraction=kelly_fraction, per_race_cap_pct=per_race_cap_pct,
        tail_threshold=tail_threshold, exclude_bet_types=exclude_bet_types)
    final_w = equity[-1]
    growth = (final_w / w0 - 1.0) * 100.0
    bet_days = sum(1 for r in day_returns if r != 0.0)
    tail_days = sum(1 for r in day_returns if r <= -tail_threshold)
    tail_rate = (tail_days / bet_days * 100.0) if bet_days > 0 else 0.0
    flat_roi = (total_payout / total_cost * 100.0) if total_cost > 0 else 0.0
    ruin = ruin_probability(
        day_returns, w0=w0, day_fraction=day_fraction, ruin_frac=ruin_frac, mc=mc)
    return SimResult(
        rule=rule, day_fraction=day_fraction, kelly_fraction=kelly_fraction, w0=w0,
        final_w=final_w, growth_pct=growth, max_dd_pct=_max_dd(equity),
        sharpe=_sharpe(day_returns), tail_day_rate=tail_rate, bet_days=bet_days,
        flat_roi_pct=flat_roi, ruin_prob_pct=ruin, day_returns=day_returns)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_floats(s: str) -> Tuple[float, ...]:
    return tuple(float(x) for x in s.split(",") if x.strip())


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--cache-path", default=None)
    p.add_argument("--split-date", default=None,
                   help="指定すると valid (>=日付) のみシミュ (walk-forward)")
    p.add_argument("--w0", type=int, default=DEFAULT_W0, help="初期総資金")
    p.add_argument("--day-fractions", default=",".join(str(f) for f in DEFAULT_DAY_FRACTIONS))
    p.add_argument("--kelly-fractions", default=str(DEFAULT_KELLY_FRACTION))
    p.add_argument("--rules", default=",".join(DEFAULT_RULES))
    p.add_argument("--per-race-cap-pct", type=float, default=DEFAULT_PER_RACE_CAP_PCT)
    p.add_argument("--tail-threshold", type=float, default=DEFAULT_TAIL_THRESHOLD)
    p.add_argument("--ruin-frac", type=float, default=DEFAULT_RUIN_FRAC)
    p.add_argument("--mc", type=int, default=DEFAULT_MC)
    p.add_argument("--strategy", default="adaptive", help="選定戦略 (固定・配分のみ比較)")
    p.add_argument("--sizing", default=sz.ADAPTIVE_SIZER, help="サイザー名")
    p.add_argument("--ev-floor", type=float, default=bs.DEFAULT_EV_FLOOR,
                   help="複合券種を fund する EV 下限 (W9: 既定1.0 は緩い・1.5 で黒字圏)")
    p.add_argument("--exclude-bet-types", default="",
                   help="買わない券種 (カンマ区切り、 例 sanrentan,umatan)")
    p.add_argument("--json-out", default=None, help="結果 JSON 出力先")
    return p.parse_args()


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                          errors="replace")
        except (AttributeError, ValueError):
            pass
    args = parse_args()
    cache_path = Path(args.cache_path) if args.cache_path else None
    races_raw = load_backtest_cache(path=cache_path)
    if args.split_date:
        split = args.split_date.replace("-", "")
        races_raw = [r for r in races_raw if str(r.get("race_id", ""))[:8] >= split]

    print(f"backtest_cache: {len(races_raw)} races"
          + (f" (valid >= {args.split_date})" if args.split_date else ""))
    exclude = tuple(x.strip() for x in args.exclude_bet_types.split(",") if x.strip())
    print(f"W0={args.w0:,}  strategy={args.strategy}  sizing={args.sizing}  "
          f"ev_floor={args.ev_floor}  exclude={exclude or '-'}  "
          f"per_race_cap_pct={args.per_race_cap_pct}  ruin_frac={args.ruin_frac}  mc={args.mc}")

    by_date = build_race_contexts(races_raw, strategy=args.strategy, ev_floor=args.ev_floor)

    day_fractions = _parse_floats(args.day_fractions)
    kelly_fractions = _parse_floats(args.kelly_fractions)
    rules = tuple(r.strip().upper() for r in args.rules.split(",") if r.strip())

    results: List[SimResult] = []
    for kf in kelly_fractions:
        for df in day_fractions:
            for rule in rules:
                results.append(run_config(
                    by_date, w0=args.w0, day_fraction=df, rule=rule,
                    sizing=args.sizing, kelly_fraction=kf,
                    per_race_cap_pct=args.per_race_cap_pct,
                    tail_threshold=args.tail_threshold, ruin_frac=args.ruin_frac,
                    mc=args.mc, exclude_bet_types=exclude))

    # 表示 (growth 降順)
    print(f"\n{'='*108}")
    print(f"  {'rule':<5}{'day%':>6}{'kelly':>7}{'finalW':>13}{'growth':>9}"
          f"{'maxDD':>8}{'sharpe':>8}{'tail%':>7}{'ruin%':>7}{'flatROI':>9}{'days':>6}")
    print(f"  {'-'*104}")
    tail_lbl = int(args.tail_threshold * 100)
    for r in sorted(results, key=lambda x: -x.growth_pct):
        print(f"  {r.rule:<5}{r.day_fraction*100:>5.0f}%{r.kelly_fraction:>7.2f}"
              f"{r.final_w:>13,.0f}{r.growth_pct:>+8.0f}%{r.max_dd_pct:>7.1f}%"
              f"{r.sharpe:>8.3f}{r.tail_day_rate:>6.1f}%{r.ruin_prob_pct:>6.1f}%"
              f"{r.flat_roi_pct:>8.1f}%{r.bet_days:>6}")
    print(f"  {'-'*104}")
    print(f"  tail% = スタート額の {tail_lbl}%+ を溶かした開催日の割合 / "
          f"ruin% = 総資金が初期 {int(args.ruin_frac*100)}% を割る確率 (日順MC {args.mc}回)")

    if args.json_out:
        out = {
            "w0": args.w0, "strategy": args.strategy, "sizing": args.sizing,
            "per_race_cap_pct": args.per_race_cap_pct,
            "tail_threshold": args.tail_threshold, "ruin_frac": args.ruin_frac,
            "mc": args.mc, "split_date": args.split_date,
            "results": [
                {k: v for k, v in r.__dict__.items() if k != "day_returns"}
                for r in results
            ],
        }
        Path(args.json_out).write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  Saved: {args.json_out}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
