#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""1番人気（odds_rank=1）の「裏切り」実態分析 — danger-model P0。

目的:
  - 1番人気が3着外（betrayal）になる率のベースラインを測る
  - 脚質・ARd・odds_move・頭数・距離帯など要因別の裏切り率を見る
  - 現行「危」ロジックとの比較材料を出す

使用例:
  python -m ml.analyze.analyze_favorite_betrayal
  python -m ml.analyze.analyze_favorite_betrayal --since 2025-01-01
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from core import config
from ml.utils.race_io import load_race, date_dir_for
from ml.utils.filters import is_obstacle

DANGER_ODDS_MAX = 8.0
DANGER_ARD_MAX = 53.0
DANGER_P_MAX = 0.15


def _place_limit(num_runners: int) -> int:
    if num_runners >= 8:
        return 3
    if num_runners >= 5:
        return 2
    return 1


def _is_danger(odds, ard, p_proba):
    if odds is None or odds <= 0 or ard is None or p_proba is None:
        return False
    return odds <= DANGER_ODDS_MAX and ard < DANGER_ARD_MAX and p_proba < DANGER_P_MAX


def _style_bucket(first_corner_ratio):
    if not isinstance(first_corner_ratio, (int, float)) or first_corner_ratio < 0:
        return "unknown"
    if first_corner_ratio <= 0.25:
        return "front(<=0.25)"
    if first_corner_ratio <= 0.45:
        return "mid(0.26-0.45)"
    return "back(>0.45)"


def _dist_bucket(distance):
    if not isinstance(distance, (int, float)) or distance <= 0:
        return "unknown"
    if distance <= 1400:
        return "sprint(<=1400)"
    if distance <= 2000:
        return "mile(1401-2000)"
    return "long(>2000)"


def _runners_bucket(n):
    if not isinstance(n, int) or n <= 0:
        return "unknown"
    if n <= 12:
        return "small(<=12)"
    if n <= 15:
        return "mid(13-15)"
    return "large(>=16)"


def _ard_bucket(ard):
    if not isinstance(ard, (int, float)):
        return "unknown"
    if ard < 45:
        return "ard<45"
    if ard < 53:
        return "ard45-52"
    if ard < 60:
        return "ard53-59"
    return "ard>=60"


def _odds_move_bucket(move):
    if not isinstance(move, (int, float)):
        return "unknown"
    if move <= 0.95:
        return "down(<=0.95)"
    if move <= 1.05:
        return "flat(0.96-1.05)"
    return "up(>1.05)"


def collect(since=None):
    races_dir = config.races_dir()
    rows = []
    for pred_path in sorted(races_dir.glob("**/predictions.json")):
        try:
            with open(pred_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        races_list = data.get("races", []) if isinstance(data, dict) else data
        if isinstance(races_list, str):
            continue
        for race in races_list:
            if not isinstance(race, dict) or is_obstacle(race):
                continue
            rid = race.get("race_id", "")
            date = race.get("date", "")
            if since and date and date < since:
                continue
            if not date:
                continue
            try:
                day_dir = date_dir_for(date, root=races_dir)
            except ValueError:
                continue
            rd = load_race(day_dir, rid)
            if rd is None:
                continue
            actual = {}
            for e in rd.get("entries", []):
                u = e.get("umaban", 0)
                fp = e.get("finish_position", 0)
                if u > 0 and fp > 0:
                    actual[u] = fp
            if not actual:
                continue
            num_runners = int(race.get("num_runners") or len(race.get("entries", [])) or 0)
            pl = _place_limit(num_runners)
            fav = None
            for e in race.get("entries", []):
                if int(e.get("odds_rank") or 0) == 1:
                    fav = e
                    break
            if fav is None:
                continue
            uma = fav.get("umaban", 0)
            fp = actual.get(uma)
            if not fp:
                continue
            odds = float(fav.get("odds", 0) or 0)
            ard = fav.get("ar_deviation")
            ard = float(ard) if isinstance(ard, (int, float)) else None
            p_proba = fav.get("pred_proba_p")
            p_proba = float(p_proba) if isinstance(p_proba, (int, float)) else None
            first_corner = fav.get("avg_first_corner_ratio")
            first_corner = float(first_corner) if isinstance(first_corner, (int, float)) else None
            closing = fav.get("closing_strength")
            closing = float(closing) if isinstance(closing, (int, float)) else None
            odds_move = fav.get("odds_move")
            odds_move = float(odds_move) if isinstance(odds_move, (int, float)) else None
            rows.append({
                "rid": rid,
                "date": date,
                "fp": fp,
                "betrayal": fp > pl,
                "win": fp == 1,
                "top3": fp <= 3,
                "odds": odds,
                "ard": ard,
                "p_proba": p_proba,
                "danger": _is_danger(odds, ard, p_proba),
                "track_type": race.get("track_type") or "unknown",
                "distance": race.get("distance"),
                "num_runners": num_runners,
                "style": _style_bucket(first_corner),
                "dist_bucket": _dist_bucket(race.get("distance")),
                "runners_bucket": _runners_bucket(num_runners),
                "ard_bucket": _ard_bucket(ard),
                "odds_move_bucket": _odds_move_bucket(odds_move),
                "closing": closing,
                "market_signal": fav.get("market_signal"),
            })
    return rows


def _rate(subset, key):
    if not subset:
        return None
    n = len(subset)
    betray = sum(1 for r in subset if r[key])
    return {
        "n": n,
        "rate": betray / n * 100,
        "win_rate": sum(1 for r in subset if r["win"]) / n * 100,
        "top3_rate": sum(1 for r in subset if r["top3"]) / n * 100,
    }


def _print_group(title, rows, field):
    print(f"\n  -- {title} --")
    groups = defaultdict(list)
    for r in rows:
        groups[r.get(field, "unknown")].append(r)
    order = sorted(groups.keys(), key=lambda k: (-len(groups[k]), k))
    for k in order:
        s = _rate(groups[k], "betrayal")
        if s is None:
            continue
        print(f"  {k:<22} n={s['n']:>5}  裏切り率{s['rate']:5.1f}%  "
              f"勝率{s['win_rate']:5.1f}%  3着内{s['top3_rate']:5.1f}%")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=None, help="YYYY-MM-DD 以降のみ")
    args = ap.parse_args()

    rows = collect(since=args.since)
    base = _rate(rows, "betrayal")
    danger_rows = [r for r in rows if r["danger"]]
    danger = _rate(danger_rows, "betrayal")

    print("=" * 78)
    print("  1番人気裏切り分析 (favorite-betrayal P0)")
    if args.since:
        print(f"  期間: {args.since} 以降")
    print(f"  対象: 1番人気 {base['n']:,} レース (結果確定・障害除外)")
    print("=" * 78)

    print("\n[1] ベースライン")
    print(f"  裏切り率(複勝圏外): {base['rate']:.1f}%")
    print(f"  勝率: {base['win_rate']:.1f}%  /  3着内率: {base['top3_rate']:.1f}%")

    print("\n[2] 現行「危」1番人気 vs 非危 1番人気")
    if danger:
        print(f"  危(1番人気):     n={danger['n']:>5}  裏切り率{danger['rate']:5.1f}%")
        non = _rate([r for r in rows if not r["danger"]], "betrayal")
        print(f"  非危(1番人気):   n={non['n']:>5}  裏切り率{non['rate']:5.1f}%")

    _print_group("芝/ダ", rows, "track_type")
    _print_group("距離帯", rows, "dist_bucket")
    _print_group("頭数", rows, "runners_bucket")
    _print_group("脚質(1角比率)", rows, "style")
    _print_group("ARd帯", rows, "ard_bucket")
    _print_group("odds_move", rows, "odds_move_bucket")

    print("\n[3] 示唆メモ")
    print("  - 裏切り率がベースラインより +10pt 以上高いセグメントを P1 ルール候補にする")
    print("  - n<80 のセグメントは観測のみ（採用判断しない）")
    print("  - danger-model の opt_* 登録前に、この表で「何を避けるか」を固定する")


if __name__ == "__main__":
    main()
