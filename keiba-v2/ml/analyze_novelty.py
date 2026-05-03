#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
novelty_score 帯別の予測精度・ROI 分析。

enrich_novelty.py で predictions.json を補完した後に実行する。
各 entry の確定 finish_position と単勝オッズを race_*.json から突合し、
novelty 帯ごとの:
  - 単勝的中率 / 単勝ROI (win_ev >= 1.3 で買った場合)
  - 複勝率 / pred_proba_p の Brier-like 指標
  - VB候補馬の novelty 分布
を出力する。

Usage:
    python -m ml.analyze_novelty
    python -m ml.analyze_novelty --start 2025-05 --end 2026-04
    python -m ml.analyze_novelty --vb-min-ev 1.3
"""

import argparse
import io
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config


def iter_date_dirs(start: str, end: str):
    root = Path(config.races_dir())
    for year_dir in sorted(root.iterdir()):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        for month_dir in sorted(year_dir.iterdir()):
            if not month_dir.is_dir():
                continue
            ym = f"{year_dir.name}-{month_dir.name}"
            if start and ym < start:
                continue
            if end and ym > end:
                continue
            for day_dir in sorted(month_dir.iterdir()):
                if day_dir.is_dir():
                    yield day_dir


def build_results(date_dir: Path) -> dict:
    """{race_id: {umaban: {finish_position, odds}}}"""
    out = {}
    for rf in date_dir.glob("race_[0-9]*.json"):
        try:
            with open(rf, encoding="utf-8") as f:
                rd = json.load(f)
        except Exception:
            continue
        rid = rd.get("race_id")
        if not rid:
            continue
        emap = {}
        for e in rd.get("entries", []):
            um = e.get("umaban")
            if um is None:
                continue
            emap[um] = {
                "finish": e.get("finish_position"),
                "odds": e.get("odds") or 0,
            }
        out[rid] = emap
    return out


def fmt_pct(num, den):
    return f"{100*num/max(1,den):5.1f}%"


def fmt_roi(returned, wagered):
    if wagered == 0:
        return "  -  "
    return f"{100*returned/wagered:6.1f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2025-05")
    ap.add_argument("--end", default="2026-04")
    ap.add_argument("--vb-min-ev", type=float, default=1.3,
                    help="単勝EV閾値 (この値以上をVB扱い)")
    ap.add_argument("--bet-unit", type=int, default=100)
    ap.add_argument("--use-is-vb", action="store_true",
                    help="is_value_bet フラグを VB判定に使用 (フィルタ適用後の効果検証用)")
    args = ap.parse_args()

    # novelty 帯別の集計
    by_score = defaultdict(lambda: {
        "total": 0, "win": 0, "place": 0,
        "vb_total": 0, "vb_win": 0, "vb_wagered": 0, "vb_returned": 0,
        "ard_sum": 0.0, "ard_n": 0,
        "ard_adj_sum": 0.0, "ard_adj_n": 0,
    })

    # 個別フラグ別の集計 (single-flag isolation)
    by_flag = {f: {"total": 0, "win": 0, "place": 0,
                   "vb_total": 0, "vb_win": 0, "vb_wagered": 0, "vb_returned": 0}
               for f in ["career_short", "first_surface", "first_distance",
                         "first_venue", "long_layoff", "jockey_change"]}

    # ARd vs ARd_adj 比較 (VB判定が変わる馬)
    ard_change = defaultdict(int)

    files_done = 0
    races_done = 0

    for day_dir in iter_date_dirs(args.start, args.end):
        pred_path = day_dir / "predictions.json"
        if not pred_path.exists():
            continue
        try:
            with open(pred_path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue

        results = build_results(day_dir)
        files_done += 1

        for race in data.get("races", []):
            rid = race.get("race_id")
            rmap = results.get(rid, {})
            if not rmap:
                continue
            races_done += 1

            for e in race.get("entries", []):
                um = e.get("umaban")
                r = rmap.get(um)
                if not r:
                    continue

                fin = r["finish"]
                odds = r["odds"] or e.get("odds") or 0
                if fin is None:
                    continue

                score = int(e.get("novelty_score", 0) or 0)
                won = (fin == 1)
                placed = (fin in (1, 2, 3))

                bucket = by_score[score]
                bucket["total"] += 1
                bucket["win"] += int(won)
                bucket["place"] += int(placed)

                ard = e.get("ar_deviation")
                ard_adj = e.get("ar_deviation_adj")
                if ard is not None:
                    bucket["ard_sum"] += ard
                    bucket["ard_n"] += 1
                if ard_adj is not None:
                    bucket["ard_adj_sum"] += ard_adj
                    bucket["ard_adj_n"] += 1

                # VB判定: --use-is-vb なら is_value_bet 使用、否なら EV閾値
                ev = e.get("win_ev") or 0
                if args.use_is_vb:
                    is_vb = bool(e.get("is_value_bet"))
                else:
                    is_vb = ev >= args.vb_min_ev
                if is_vb:
                    bucket["vb_total"] += 1
                    bucket["vb_wagered"] += args.bet_unit
                    if won and odds > 0:
                        bucket["vb_win"] += 1
                        bucket["vb_returned"] += int(args.bet_unit * odds)

                # 個別フラグ寄与 (排他評価ではなく重複OK)
                for fname in by_flag:
                    if int(e.get(f"novelty_{fname}", 0) or 0) == 1:
                        fb = by_flag[fname]
                        fb["total"] += 1
                        fb["win"] += int(won)
                        fb["place"] += int(placed)
                        if ev >= args.vb_min_ev:
                            fb["vb_total"] += 1
                            fb["vb_wagered"] += args.bet_unit
                            if won and odds > 0:
                                fb["vb_win"] += 1
                                fb["vb_returned"] += int(args.bet_unit * odds)

                # ARd補正の効果 (VB判定が変わる馬)
                if ard is not None and ard_adj is not None:
                    if ard >= 65 and ard_adj < 65:
                        ard_change["downgraded_from_65"] += 1
                    if ard >= 50 and ard_adj < 50:
                        ard_change["downgraded_below_50"] += 1

    # === レポート出力 ===
    print(f"\n{'='*78}")
    print(f"Novelty Backtest  ({args.start} ~ {args.end})  files={files_done} races={races_done}")
    print(f"VB判定: win_ev >= {args.vb_min_ev}  bet_unit={args.bet_unit}")
    print(f"{'='*78}\n")

    print(f"{'score':>5} {'N':>7} {'win%':>7} {'place%':>7}  "
          f"{'ARd':>5} {'ARd_adj':>7}  "
          f"{'VB_N':>5} {'VB_win%':>7} {'VB_ROI':>7} {'P&L':>10}")
    print("-" * 92)
    grand_vb_total = 0
    grand_vb_won = 0
    grand_vb_wager = 0
    grand_vb_ret = 0
    for s in sorted(by_score.keys()):
        b = by_score[s]
        if b["total"] == 0:
            continue
        ard_avg = b["ard_sum"] / max(1, b["ard_n"])
        ard_adj_avg = b["ard_adj_sum"] / max(1, b["ard_adj_n"])
        pnl = b["vb_returned"] - b["vb_wagered"]
        print(f"{s:>5} {b['total']:>7,} {fmt_pct(b['win'], b['total']):>7} "
              f"{fmt_pct(b['place'], b['total']):>7}  "
              f"{ard_avg:>5.1f} {ard_adj_avg:>7.1f}  "
              f"{b['vb_total']:>5,} {fmt_pct(b['vb_win'], b['vb_total']):>7} "
              f"{fmt_roi(b['vb_returned'], b['vb_wagered']):>7} {pnl:>+10,}")
        grand_vb_total += b["vb_total"]
        grand_vb_won += b["vb_win"]
        grand_vb_wager += b["vb_wagered"]
        grand_vb_ret += b["vb_returned"]
    print("-" * 92)
    print(f"{'ALL':>5} {sum(b['total'] for b in by_score.values()):>7,} "
          f"{'':>16}{'':>14}  "
          f"{grand_vb_total:>5,} {fmt_pct(grand_vb_won, grand_vb_total):>7} "
          f"{fmt_roi(grand_vb_ret, grand_vb_wager):>7} "
          f"{grand_vb_ret - grand_vb_wager:>+10,}")

    print(f"\n--- 個別フラグ (単一フラグ立った馬の集計, 重複あり) ---")
    print(f"{'flag':>16} {'N':>7} {'win%':>7} {'place%':>7}  "
          f"{'VB_N':>5} {'VB_win%':>7} {'VB_ROI':>7} {'P&L':>10}")
    print("-" * 78)
    for fname, fb in by_flag.items():
        if fb["total"] == 0:
            continue
        pnl = fb["vb_returned"] - fb["vb_wagered"]
        print(f"{fname:>16} {fb['total']:>7,} {fmt_pct(fb['win'], fb['total']):>7} "
              f"{fmt_pct(fb['place'], fb['total']):>7}  "
              f"{fb['vb_total']:>5,} {fmt_pct(fb['vb_win'], fb['vb_total']):>7} "
              f"{fmt_roi(fb['vb_returned'], fb['vb_wagered']):>7} {pnl:>+10,}")

    print(f"\n--- ARd 補正で評価が変わる馬 ---")
    print(f"  ARd>=65 → ARd_adj<65 (鉄板格下げ): {ard_change['downgraded_from_65']:,}")
    print(f"  ARd>=50 → ARd_adj<50 (中位以上→以下): {ard_change['downgraded_below_50']:,}")


if __name__ == "__main__":
    main()
