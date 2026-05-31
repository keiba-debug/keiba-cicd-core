#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""multi-bettype レース単位 dry-run ビュー (Session 140 / ロールアウト Step1-2 検証用)

投票は一切しない。 各レースの「選定券種 + サイジング + runner に渡る --bet 一覧」を表示し、
発走時刻・投票窓も併記する。 bettype_scheduler の候補生成 (size_one_race) をそのまま使う。

CLI:
    python -m ml.strategies.bettype_race --date today                       # 当日全レース一覧
    python -m ml.strategies.bettype_race --date 2026-05-31 --race-id <16桁> # 単一レース詳細
    python -m ml.strategies.bettype_race --date today --strategy hole_seeker --sizing anchor_kelly_combo_ev
"""

from __future__ import annotations

import argparse
import io
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.strategies.bettype_scheduler import (  # noqa: E402
    size_one_race, build_bet_specs, DEFAULT_BANKROLL, DEFAULT_STRATEGY,
    DEFAULT_EV_FLOOR,
)
from ml.strategies.bettype_sizing import DEFAULT_SIZER, SIZERS  # noqa: E402
from ml.strategies.bettype_selection import STRATEGIES  # noqa: E402
from ml.strategies.freebudget_scheduler import read_per_race_cap  # noqa: E402
from ml.strategies.freebudget_race import load_post_times, race_timing  # noqa: E402
from ml.strategies.freebudget import resolve_date  # noqa: E402
from ml.utils.race_io import date_dir_for, load_predictions  # noqa: E402


def _print_race(race_id: str, label: str, rs, timing: dict) -> None:
    win = (f"投票窓[{timing['vote_at'].strftime('%H:%M')}-"
           f"{timing['deadline'].strftime('%H:%M')}]" if timing.get("deadline") else "発走時刻不明")
    print(f"\n=== {race_id} {label} {win} ===")
    print(f"  合計 {rs.total_yen}円 (◎{rs.anchor_yen} + 複合{rs.combo_yen}) "
          f"{len(rs.legs)}点  per_race_cap={rs.per_race_cap}")
    for l in rs.legs:
        o = f"{l.leg_odds:.1f}" if l.leg_odds else "--"
        ev = f"{l.ev:.2f}" if l.ev is not None else "--"
        horses = "/".join(str(h) for h in l.horses)
        print(f"    {l.bet_type:<11} {horses:<10} ¥{l.amount:<5} odds={o:>6} EV={ev:>5}  {l.note}")
    for spec in build_bet_specs(race_id, rs):
        print(f"    --bet {spec}")
    for w in rs.warnings:
        print(f"    ⚠ {w}")


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                          errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--date", default="today")
    p.add_argument("--race-id", default=None)
    p.add_argument("--strategy", default=DEFAULT_STRATEGY, choices=STRATEGIES)
    p.add_argument("--ev-floor", type=float, default=DEFAULT_EV_FLOOR)
    p.add_argument("--sizing", default=DEFAULT_SIZER, choices=tuple(SIZERS))
    p.add_argument("--bankroll", type=int, default=DEFAULT_BANKROLL)
    args = p.parse_args()

    date_str = resolve_date(args.date)
    day_dir = date_dir_for(date_str)
    predictions = load_predictions(day_dir)
    if predictions is None:
        print(f"predictions.json なし ({date_str})")
        return 1
    post_times = load_post_times(day_dir, date_str=date_str)
    per_race_cap = read_per_race_cap()
    now = datetime.now()

    races = predictions.get("races", []) or []
    pred_by_id = {str(r.get("race_id")): r for r in races if r.get("race_id")}
    targets = [args.race_id] if args.race_id else sorted(pred_by_id)

    total_yen = 0
    n_races = 0
    for rid in targets:
        pr = pred_by_id.get(rid)
        if pr is None:
            print(f"race {rid} が predictions に無い")
            continue
        rs = size_one_race(pr, strategy=args.strategy, ev_floor=args.ev_floor,
                           sizing=args.sizing, bankroll=args.bankroll,
                           per_race_cap=per_race_cap)
        if rs is None or not rs.legs:
            continue
        label = f"{pr.get('venue_name') or '?'} {pr.get('race_number') or '?'}R"
        timing = race_timing(date_str, post_times.get(rid, ""), now)
        _print_race(rid, label, rs, timing)
        total_yen += rs.total_yen
        n_races += 1

    print(f"\n[Done] {n_races} races / 合計 {total_yen}円 "
          f"(strategy={args.strategy} sizing={args.sizing} per_race_cap={per_race_cap})")
    print("※ これは dry-run 表示。 投票はしていない。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
