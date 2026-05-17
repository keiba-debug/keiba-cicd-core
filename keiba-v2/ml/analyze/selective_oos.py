#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Selective 戦略 OOS 集計 (Session 122 Phase 4 の後継)

実戦投入後の selective_bets.json を全日走査し、 race_*.json の着順と join して
戦略タグ別 (baseline / not_fav1 / not_top2 / gap>=3 / gap>=4) の ROI / P&L /
MaxDD / 連敗ストリークを集計する。

BT 集計は ml/analyze/polaris_hybrid.py、 OOS 集計が本スクリプト。

Usage:
    python -m ml.analyze.selective_oos
    python -m ml.analyze.selective_oos --start 2026-04-01
    python -m ml.analyze.selective_oos --start 2026-04-01 --end 2026-05-16
    python -m ml.analyze.selective_oos --json out.json --csv daily_pnl.csv
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.utils.race_io import iter_date_dirs, load_race_results
from ml.utils.roi import Bet, calc_roi, max_drawdown, losing_streaks


BET_UNIT = 100.0

# 戦略タグ判定 (selective-bets WebUI 側ロジックと同期、 page.tsx:40-57)
STRATEGY_TAGS = ["baseline", "not_fav1", "not_top2", "gap3", "gap4"]


def matches_tag(bet: dict, tag: str) -> bool:
    odds_rank = bet.get("odds_rank")
    vb_gap = bet.get("vb_gap")
    if tag == "baseline":
        return True
    if tag == "not_fav1":
        return odds_rank is not None and odds_rank != 1
    if tag == "not_top2":
        return odds_rank is not None and odds_rank > 2
    if tag == "gap3":
        return vb_gap is not None and vb_gap >= 3
    if tag == "gap4":
        return vb_gap is not None and vb_gap >= 4
    return False


@dataclass
class ResolvedBet:
    """1ベット + 着順情報"""
    date: str
    race_id: str
    venue_name: Optional[str]
    grade: str
    umaban: int
    horse_name: str
    odds: float
    odds_rank: Optional[int]
    vb_gap: Optional[int]
    finish: Optional[int]
    is_win: bool


def load_selective_bets(day_dir: Path) -> Optional[dict]:
    p = day_dir / "selective_bets.json"
    if not p.exists():
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def resolve_bets(start: Optional[str], end: Optional[str]) -> List[ResolvedBet]:
    """期間内の selective_bets.json を全部集めて、着順と join"""
    out: List[ResolvedBet] = []
    for day_dir in iter_date_dirs(start, end):
        sb = load_selective_bets(day_dir)
        if not sb:
            continue
        results = load_race_results(day_dir)
        date_str = f"{day_dir.parts[-3]}-{day_dir.parts[-2]}-{day_dir.parts[-1]}"
        for bet in sb.get("bets", []):
            rid = str(bet.get("race_id", ""))
            umaban = int(bet.get("umaban") or 0)
            race_result = results.get(rid, {})
            finish = race_result.get(umaban, {}).get("finish_position")
            is_win = (finish == 1)
            out.append(ResolvedBet(
                date=date_str,
                race_id=rid,
                venue_name=bet.get("venue_name"),
                grade=bet.get("grade", ""),
                umaban=umaban,
                horse_name=str(bet.get("horse_name") or ""),
                odds=float(bet.get("odds") or 0),
                odds_rank=bet.get("odds_rank"),
                vb_gap=bet.get("vb_gap"),
                finish=finish if isinstance(finish, int) else None,
                is_win=is_win,
            ))
    return out


def summarize_tag(bets_for_tag: List[ResolvedBet]) -> dict:
    """1戦略タグの集計"""
    # 未確定 (finish None) は集計から除外
    resolved = [b for b in bets_for_tag if b.finish is not None]
    pending = len(bets_for_tag) - len(resolved)

    if not resolved:
        return {
            "bets": 0,
            "pending": pending,
            "hits": 0,
            "hit_rate": 0.0,
            "cost": 0.0,
            "payout": 0.0,
            "pnl": 0.0,
            "roi": 0.0,
            "mean_hit_odds": 0.0,
            "max_dd": 0.0,
            "max_streak": 0,
        }

    bet_objs = [
        Bet(
            race_id=b.race_id,
            cost=BET_UNIT,
            payout=b.odds * BET_UNIT if b.is_win else 0.0,
            is_hit=b.is_win,
            odds=b.odds,
            bet_type="win",
        )
        for b in resolved
    ]
    roi = calc_roi(bet_objs)

    # 累計 P&L 系列 (日付順) → MaxDD
    sorted_bets = sorted(resolved, key=lambda b: (b.date, b.race_id))
    cum = 0.0
    cum_series: List[float] = []
    hit_series: List[int] = []
    for b in sorted_bets:
        cum += (b.odds * BET_UNIT - BET_UNIT) if b.is_win else -BET_UNIT
        cum_series.append(cum)
        hit_series.append(1 if b.is_win else 0)
    max_dd_amount, _ = max_drawdown(cum_series)
    streak = losing_streaks(hit_series, bet_unit=BET_UNIT)

    return {
        "bets": roi.n,
        "pending": pending,
        "hits": roi.hits,
        "hit_rate": round(roi.hit_rate, 1),
        "cost": round(roi.cost, 0),
        "payout": round(roi.payout, 0),
        "pnl": round(roi.pnl, 0),
        "roi": round(roi.roi, 1),
        "mean_hit_odds": round(roi.mean_hit_odds, 2),
        "max_dd": round(max_dd_amount, 0),
        "max_streak": int(streak["max_streak"]),
    }


def build_daily_pnl(bets: List[ResolvedBet]) -> List[dict]:
    """日別 × 戦略タグ × 累計 P&L 系列"""
    by_date: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    by_date_count: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for b in bets:
        if b.finish is None:
            continue
        pnl_daily = (b.odds * BET_UNIT - BET_UNIT) if b.is_win else -BET_UNIT
        for tag in STRATEGY_TAGS:
            if matches_tag(asdict(b), tag):
                by_date[b.date][tag] += pnl_daily
                by_date_count[b.date][tag] += 1

    rows: List[dict] = []
    cum: dict[str, float] = defaultdict(float)
    cum_n: dict[str, int] = defaultdict(int)
    for d in sorted(by_date.keys()):
        for tag in STRATEGY_TAGS:
            cum[tag] += by_date[d][tag]
            cum_n[tag] += by_date_count[d][tag]
        rows.append({
            "date": d,
            **{f"pnl_{tag}": round(by_date[d][tag], 0) for tag in STRATEGY_TAGS},
            **{f"cum_pnl_{tag}": round(cum[tag], 0) for tag in STRATEGY_TAGS},
            **{f"n_{tag}": cum_n[tag] for tag in STRATEGY_TAGS},
        })
    return rows


def print_summary(summary: dict, daily: List[dict],
                  bet_details: List[ResolvedBet], start: str, end: str) -> None:
    print()
    print("=" * 78)
    print(f"  Selective OOS Summary  ({start} 〜 {end})")
    print("=" * 78)

    n_total = len(bet_details)
    n_resolved = sum(1 for b in bet_details if b.finish is not None)
    n_pending = n_total - n_resolved
    print(f"  Total bets: {n_total}  (resolved: {n_resolved}, pending: {n_pending})")
    print()

    # 戦略タグ別テーブル
    print(f"  {'Strategy':<14} {'bets':>5} {'hits':>5} {'hit%':>6} "
          f"{'ROI%':>7} {'P&L':>9} {'MaxDD':>8} {'streak':>7} {'hitOdds':>8}")
    print("  " + "-" * 76)
    for tag in STRATEGY_TAGS:
        s = summary[tag]
        if s["bets"] == 0:
            print(f"  {tag:<14} {'-':>5}")
            continue
        print(f"  {tag:<14} {s['bets']:>5} {s['hits']:>5} {s['hit_rate']:>5.1f}% "
              f"{s['roi']:>6.1f}% {s['pnl']:>+9,.0f} {s['max_dd']:>+8,.0f} "
              f"{s['max_streak']:>7} {s['mean_hit_odds']:>8.2f}")
    print()

    # BT 比較 (Session 122 時点の数値)
    print("  -- BT 比較 (v8.4 polaris_hybrid 2025-05〜2026-03 / 166 bets baseline) --")
    bt_table = {
        "baseline": (203.1, 22.9),
        "not_fav1": (246.8, 19.3),
        "not_top2": (262.6, 18.9),
        "gap3":     (319.6, 13.7),
        "gap4":     (381.3, 13.0),
    }
    print(f"  {'Strategy':<14} {'OOS ROI':>8} {'BT ROI':>8} {'差':>8}")
    print("  " + "-" * 40)
    for tag in STRATEGY_TAGS:
        s = summary[tag]
        if s["bets"] == 0:
            continue
        bt_roi, _ = bt_table[tag]
        diff = s["roi"] - bt_roi
        print(f"  {tag:<14} {s['roi']:>7.1f}% {bt_roi:>7.1f}% {diff:>+7.1f}pt")
    print()

    # 直近のヒット例 (最新5件)
    hits = [b for b in bet_details if b.is_win]
    hits_recent = sorted(hits, key=lambda b: b.date, reverse=True)[:5]
    if hits_recent:
        print("  -- 直近的中5件 --")
        for b in hits_recent:
            tags = [t for t in STRATEGY_TAGS if matches_tag(asdict(b), t)]
            tag_str = ",".join(tags)
            print(f"    {b.date} {b.venue_name or '?'} {b.grade} "
                  f"{b.umaban}番 {b.horse_name} odds={b.odds:.1f} → "
                  f"+¥{int(b.odds * BET_UNIT - BET_UNIT):,}  [{tag_str}]")
        print()

    # 最新の未確定ベット
    pending_bets = [b for b in bet_details if b.finish is None]
    if pending_bets:
        print(f"  -- 未確定 {len(pending_bets)} 件 (最新3件) --")
        for b in sorted(pending_bets, key=lambda b: b.date, reverse=True)[:3]:
            print(f"    {b.date} {b.venue_name or '?'} {b.grade} "
                  f"{b.umaban}番 {b.horse_name} odds={b.odds:.1f}")
        print()


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--start", default="2026-04-01",
                   help="OOS 開始日 (default: 2026-04-01)")
    p.add_argument("--end", default=None,
                   help="OOS 終了日 (default: yesterday)")
    p.add_argument("--json", default=None, help="JSON サマリー出力先")
    p.add_argument("--csv", default=None, help="日別 P&L CSV 出力先")
    p.add_argument("--quiet", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    end = args.end or (date.today() - timedelta(days=1)).isoformat()
    start = args.start

    bets = resolve_bets(start, end)
    if not bets:
        print(f"selective_bets.json が見つかりません ({start} 〜 {end})", file=sys.stderr)
        return 1

    summary: dict = {}
    for tag in STRATEGY_TAGS:
        filt = [b for b in bets if matches_tag(asdict(b), tag)]
        summary[tag] = summarize_tag(filt)

    daily = build_daily_pnl(bets)

    if not args.quiet:
        print_summary(summary, daily, bets, start, end)

    if args.json:
        out = {
            "period": {"start": start, "end": end},
            "n_total": len(bets),
            "n_resolved": sum(1 for b in bets if b.finish is not None),
            "summary": summary,
            "daily_pnl": daily,
            "bets": [asdict(b) for b in bets],
        }
        Path(args.json).write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[Saved] {args.json}")

    if args.csv:
        import csv
        if daily:
            with open(args.csv, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(daily[0].keys()))
                w.writeheader()
                w.writerows(daily)
            print(f"[Saved] {args.csv}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
