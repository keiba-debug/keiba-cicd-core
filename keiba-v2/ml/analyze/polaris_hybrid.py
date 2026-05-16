#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""polaris 2.0 P×W ハイブリッド戦略 Pilot (Session 122 Phase 4)

P (rank_p==1) と W (rank_w==1) の Top1 馬を組み合わせて、複数のハイブリッド戦略を
評価し ROI/Sharpe/MaxDD を比較する。

戦略:
    1. P_only          — rank_p==1 を毎レース単勝買い (baseline P)
    2. W_only          — rank_w==1 を毎レース単勝買い (baseline W)
    3. Hybrid-Grade    — 重賞(G1-G3+Listed) → P / 他 → W
    4. Hybrid-Odds     — W top1 odds が 10-20倍 → W / 他 → P
    5. Hybrid-Concur   — P top1 == W top1 のレースのみ買う (両モデル一致)
    6. Concur+Grade    — Hybrid-Concur AND 重賞 → 確信度最大
    7. Selective       — 重賞のみ P (新馬・1勝・3勝は完全スキップ)

Usage:
    python -m ml.analyze.polaris_hybrid
    python -m ml.analyze.polaris_hybrid --run-id v1_2026-05

Output:
    data3/analysis/polaris_hybrid/{run_id}/
        summary.md
        strategies.json
"""

from __future__ import annotations

import argparse
import io
import json
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

import numpy as np

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core import config
from ml.utils.backtest_cache import load_backtest_cache
from ml.utils.filters import exclude_obstacle
from ml.utils.roi import Bet, calc_roi, sharpe_ratio, max_drawdown, losing_streaks


GRADE_KEISHOU = {"G1", "G2", "G3", "Listed"}  # 重賞 + リステッド


# ===========================================================================
# Per-race candidate extraction
# ===========================================================================

def get_top1(entries: list[dict], rank_key: str) -> Optional[dict]:
    """entries から rank_key == 1 の馬を返す (オッズ>0 のもののみ)"""
    for e in entries:
        if e.get(rank_key) == 1 and (e.get("odds") or 0) > 0:
            return e
    return None


def make_bet(race_id: str, entry: dict) -> Bet:
    odds = float(entry.get("odds") or 0)
    is_win = bool(entry.get("is_win"))
    return Bet(
        race_id=race_id,
        cost=100.0,
        payout=odds * 100.0 if is_win else 0.0,
        is_hit=is_win,
        odds=odds,
        bet_type="win",
    )


# ===========================================================================
# Strategy: each is (name, description, picker_fn)
# picker_fn(race) -> Optional[Bet] (None = skip race)
# ===========================================================================

def strat_p_only(race: dict) -> Optional[Bet]:
    top = get_top1(race["entries"], "rank_p")
    return make_bet(race["race_id"], top) if top else None


def strat_w_only(race: dict) -> Optional[Bet]:
    top = get_top1(race["entries"], "rank_w")
    return make_bet(race["race_id"], top) if top else None


def strat_hybrid_grade(race: dict) -> Optional[Bet]:
    """重賞(G1-G3+Listed) → P / 他 → W"""
    grade = race.get("grade", "")
    use_p = grade in GRADE_KEISHOU
    rank_key = "rank_p" if use_p else "rank_w"
    top = get_top1(race["entries"], rank_key)
    return make_bet(race["race_id"], top) if top else None


def strat_hybrid_odds(race: dict) -> Optional[Bet]:
    """W top1 odds が 10-20倍 → W / 他 → P"""
    w = get_top1(race["entries"], "rank_w")
    if w is not None:
        w_odds = float(w.get("odds") or 0)
        if 10 <= w_odds <= 20:
            return make_bet(race["race_id"], w)
    p = get_top1(race["entries"], "rank_p")
    return make_bet(race["race_id"], p) if p else None


def strat_hybrid_concur(race: dict) -> Optional[Bet]:
    """P top1 == W top1 のレースのみ買う (両モデル一致)"""
    p = get_top1(race["entries"], "rank_p")
    w = get_top1(race["entries"], "rank_w")
    if p is None or w is None:
        return None
    if p.get("umaban") != w.get("umaban"):
        return None
    return make_bet(race["race_id"], p)


def strat_concur_grade(race: dict) -> Optional[Bet]:
    """Hybrid-Concur AND 重賞のみ"""
    grade = race.get("grade", "")
    if grade not in GRADE_KEISHOU:
        return None
    return strat_hybrid_concur(race)


def strat_selective(race: dict) -> Optional[Bet]:
    """重賞のみ P (新馬・1勝・3勝は完全スキップ)"""
    grade = race.get("grade", "")
    if grade not in GRADE_KEISHOU:
        return None
    top = get_top1(race["entries"], "rank_p")
    return make_bet(race["race_id"], top) if top else None


STRATEGIES: list[tuple[str, str, Callable[[dict], Optional[Bet]]]] = [
    ("P_only",          "rank_p==1 全レース",                                 strat_p_only),
    ("W_only",          "rank_w==1 全レース",                                 strat_w_only),
    ("Hybrid-Grade",    "重賞(G1-G3+Listed)→P / 他→W",                       strat_hybrid_grade),
    ("Hybrid-Odds",     "W top1 odds 10-20倍→W / 他→P",                     strat_hybrid_odds),
    ("Hybrid-Concur",   "P top1 == W top1 のみ (両モデル一致)",              strat_hybrid_concur),
    ("Concur+Grade",    "両モデル一致 AND 重賞",                              strat_concur_grade),
    ("Selective",       "重賞のみ P (新馬/1勝/3勝完全スキップ)",              strat_selective),
]


# ===========================================================================
# Evaluation
# ===========================================================================

def evaluate(name: str, description: str, picker: Callable[[dict], Optional[Bet]],
             races: list[dict]) -> dict:
    """1 戦略を全レースに適用して統計を返す"""
    bets: list[Bet] = []
    monthly_bets: dict[str, list[Bet]] = defaultdict(list)
    for r in races:
        bet = picker(r)
        if bet is None:
            continue
        bets.append(bet)
        # race_id 先頭 6桁 = YYYYMM
        rid = str(r.get("race_id", ""))
        if len(rid) >= 6:
            month = f"{rid[:4]}-{rid[4:6]}"
            monthly_bets[month].append(bet)

    roi = calc_roi(bets)

    # Monthly ROI 系列
    months_sorted = sorted(monthly_bets.keys())
    monthly_roi: list[float] = []
    monthly_pnl: list[float] = []
    monthly_hits: list[int] = []
    monthly_count: list[int] = []
    cum_pnl: list[float] = []
    running = 0.0
    for m in months_sorted:
        mbets = monthly_bets[m]
        mr = calc_roi(mbets)
        monthly_roi.append(mr.roi)
        monthly_pnl.append(mr.pnl)
        monthly_hits.append(mr.hits)
        monthly_count.append(mr.n)
        running += mr.pnl
        cum_pnl.append(running)

    # Risk metrics
    sharpe = sharpe_ratio(monthly_roi, periods_per_year=12) if monthly_roi else 0.0
    dd_amt, dd_pct = max_drawdown(cum_pnl) if cum_pnl else (0.0, 0.0)
    hits_chronological = [1 if b.is_hit else 0 for b in bets]
    streaks = losing_streaks(hits_chronological)

    return {
        "name": name,
        "description": description,
        "n_bets": roi.n,
        "n_hits": roi.hits,
        "hit_rate": round(roi.hit_rate, 1),
        "roi": round(roi.roi, 1),
        "pnl": round(roi.pnl, 0),
        "cost": round(roi.cost, 0),
        "payout": round(roi.payout, 0),
        "mean_hit_odds": round(roi.mean_hit_odds, 2),
        "sharpe": round(sharpe, 2),
        "max_dd_amount": round(dd_amt, 0),
        "max_dd_pct": round(dd_pct, 1),
        "max_streak": streaks["max_streak"],
        "avg_streak": streaks["avg_streak"],
        "streak_10plus": streaks["streak_10plus"],
        "max_streak_loss": round(streaks["max_streak_loss"], 0),
        "months_covered": len(months_sorted),
    }


# ===========================================================================
# Output
# ===========================================================================

def _fmt_roi(roi: float) -> str:
    s = f"{roi:+.1f}%"
    if roi >= 130: return f"**{s}** 🟢🟢"
    if roi >= 110: return f"**{s}** 🟢"
    if roi >= 95: return s
    if roi >= 80: return f"{s} 🟡"
    return f"{s} 🔴"


def render_markdown(results: list[dict], n_races: int, run_id: str) -> str:
    lines = [
        f"# polaris 2.0 ハイブリッド戦略比較 — {run_id}\n",
        f"- 対象: {n_races:,} flat races (障害除外)",
        f"- 戦略: {len(STRATEGIES)} 種",
        "- 評価: 100円単勝買い基準",
        "",
        "## 戦略別パフォーマンス",
        "",
        "| 戦略 | bets | 勝率 | ROI | P&L | Sharpe | MaxDD | 最長連敗 | mean odds |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    # ROI 降順
    sorted_results = sorted(results, key=lambda r: -r["roi"])
    for r in sorted_results:
        lines.append(
            f"| **{r['name']}** | {r['n_bets']:,} | {r['hit_rate']}% | "
            f"{_fmt_roi(r['roi'])} | {int(r['pnl']):+,} | {r['sharpe']} | "
            f"¥{int(r['max_dd_amount']):,} ({r['max_dd_pct']}%) | "
            f"{r['max_streak']} (-¥{int(r['max_streak_loss']):,}) | "
            f"{r['mean_hit_odds']} |"
        )
    lines.append("")
    lines.append("## 戦略説明")
    for r in sorted_results:
        lines.append(f"- **{r['name']}**: {r['description']}")
    lines.append("")
    lines.append("## 比較サマリ")
    p = next((r for r in results if r["name"] == "P_only"), None)
    w = next((r for r in results if r["name"] == "W_only"), None)
    best = max(results, key=lambda r: r["roi"])
    if p and w and best:
        lines.append(f"- **P単独**: ROI {p['roi']}%, Sharpe {p['sharpe']}, MaxDD ¥{int(p['max_dd_amount']):,}")
        lines.append(f"- **W単独**: ROI {w['roi']}%, Sharpe {w['sharpe']}, MaxDD ¥{int(w['max_dd_amount']):,}")
        lines.append(f"- **🏆 最高ROI**: {best['name']} → ROI {best['roi']}% (P比 {best['roi'] - p['roi']:+.1f}, W比 {best['roi'] - w['roi']:+.1f})")

    lines.append(f"\n---\n_Generated: {datetime.now().isoformat(timespec='seconds')}_")
    return "\n".join(lines)


# ===========================================================================
# CLI
# ===========================================================================

def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--run-id", default=None, help="出力ディレクトリ名")
    p.add_argument("--output-root", default=None)
    p.add_argument("--quiet", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    verbose = not args.quiet

    if verbose:
        print(f"=== polaris_hybrid run_id={run_id} ===\n")

    t0 = time.time()
    races = exclude_obstacle(load_backtest_cache(quiet=not verbose))
    if verbose:
        print(f"[Load] {len(races):,} flat races ({time.time()-t0:.1f}s)\n")

    results = []
    for name, desc, picker in STRATEGIES:
        ts = time.time()
        r = evaluate(name, desc, picker, races)
        results.append(r)
        if verbose:
            print(f"  [{name:<14s}] bets={r['n_bets']:>5} hit={r['hit_rate']:>5}% "
                  f"ROI={r['roi']:>+7.1f}% P&L={int(r['pnl']):>+8,} "
                  f"Sharpe={r['sharpe']:>6.2f}  ({time.time()-ts:.1f}s)")

    out_root = Path(args.output_root) if args.output_root \
        else config.data_root() / "analysis" / "polaris_hybrid"
    out_dir = out_root / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "summary.md").write_text(
        render_markdown(results, len(races), run_id), encoding="utf-8")
    (out_dir / "strategies.json").write_text(
        json.dumps({
            "run_id": run_id,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "n_races": len(races),
            "strategies": results,
        }, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    if verbose:
        print(f"\n[Done] {time.time()-t0:.1f}s")
        print(f"  summary.md      → {out_dir / 'summary.md'}")
        print(f"  strategies.json → {out_dir / 'strategies.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
