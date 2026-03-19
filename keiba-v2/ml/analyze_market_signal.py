#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""market_signal別 詳細パフォーマンス分析

ValueBet再設計Phase2のためのデータ分析。
market_signal × VB状態/rank_p/ARd/月別 のクロス集計。
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core import config


def collect_data():
    races_dir = config.races_dir()
    entries_data = []

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
            if not isinstance(race, dict) or race.get("track_type") == "obstacle":
                continue
            entries = race.get("entries", [])
            rid = race.get("race_id", "")
            date = race.get("date", "")
            if not date:
                continue
            parts = date.split("-")
            if len(parts) != 3:
                continue
            race_path = (
                races_dir / parts[0] / parts[1] / parts[2] / f"race_{rid}.json"
            )
            try:
                with open(race_path, encoding="utf-8") as f:
                    rd = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                continue
            actual = {}
            for e in rd.get("entries", []):
                u = e.get("umaban", 0)
                fp = e.get("finish_position", 0)
                if u > 0 and fp > 0:
                    actual[u] = fp
            if not actual:
                continue
            for e in entries:
                ms = e.get("market_signal")
                if not ms:
                    continue
                uma = e.get("umaban", 0)
                fp = actual.get(uma, 99)
                odds = float(e.get("odds", 0) or 0)
                place_odds = float(e.get("place_odds_min", 0) or 0)
                rank_p = e.get("rank_p") or 99
                rank_w = e.get("rank_w") or 99
                ard = float(e.get("ar_deviation", 0) or 0)
                win_ev = float(e.get("win_ev", 0) or 0)
                place_ev = float(e.get("place_ev", 0) or 0)
                vb_win = bool(e.get("value_bet_win"))
                vb_place = bool(e.get("value_bet_place"))
                month = date[:7]

                entries_data.append({
                    "ms": ms, "fp": fp, "odds": odds, "place_odds": place_odds,
                    "rank_p": rank_p, "rank_w": rank_w, "ard": ard,
                    "win_ev": win_ev, "place_ev": place_ev,
                    "vb_win": vb_win, "vb_place": vb_place, "month": month,
                    "date": date, "race_id": rid,
                })
    return entries_data


def calc_stats(subset):
    n = len(subset)
    if n == 0:
        return None
    wins = sum(1 for d in subset if d["fp"] == 1)
    top3 = sum(1 for d in subset if d["fp"] <= 3)
    win_bet = sum(100 for d in subset if d["odds"] > 0)
    win_ret = sum(int(d["odds"] * 100) for d in subset if d["fp"] == 1 and d["odds"] > 0)
    pl_bet = sum(100 for d in subset if d["place_odds"] > 0)
    pl_ret = sum(int(d["place_odds"] * 100) for d in subset if d["fp"] <= 3 and d["place_odds"] > 0)
    return {
        "n": n, "wins": wins, "top3": top3,
        "wr": wins / n * 100,
        "pr": top3 / n * 100,
        "w_roi": win_ret / win_bet * 100 if win_bet else 0,
        "p_roi": pl_ret / pl_bet * 100 if pl_bet else 0,
    }


def main():
    print("=" * 70)
    print("  market_signal 詳細パフォーマンス分析")
    print("=" * 70)

    data = collect_data()
    print(f"\n  Total: {len(data)} entries with market_signal")

    SIGNALS = ["鉄板", "軸向き", "想定通り", "やや妙味", "妙味", "人気しすぎ", "穴注目"]

    # =================================================================
    # 0. Overview
    # =================================================================
    print("\n" + "=" * 70)
    print("  0. Overview")
    print("=" * 70)
    print(f"\n  {'signal':>12} {'N':>5} {'勝率':>6} {'複勝率':>6} {'単ROI':>7} {'複ROI':>7}")
    print("  " + "-" * 50)
    for ms in SIGNALS:
        s = calc_stats([d for d in data if d["ms"] == ms])
        if not s:
            continue
        m = " ★" if s["w_roi"] > 110 or s["p_roi"] > 90 else ""
        print(f"  {ms:>12} {s['n']:>5} {s['wr']:>5.1f}% {s['pr']:>5.1f}% "
              f"{s['w_roi']:>6.1f}% {s['p_roi']:>6.1f}%{m}")

    # =================================================================
    # 1. Signal × VB状態
    # =================================================================
    print("\n" + "=" * 70)
    print("  1. Signal × VB状態（VB付きは成績が上がるか？）")
    print("=" * 70)

    for ms in SIGNALS:
        subset = [d for d in data if d["ms"] == ms]
        if not subset:
            continue
        results = []
        for vb_label, filt in [
            ("VB_win", lambda d: d["vb_win"]),
            ("VB_place", lambda d: d["vb_place"]),
            ("VB_any", lambda d: d["vb_win"] or d["vb_place"]),
            ("no_VB", lambda d: not d["vb_win"] and not d["vb_place"]),
        ]:
            sub = [d for d in subset if filt(d)]
            if not sub:
                continue
            s = calc_stats(sub)
            m = " ★" if s["w_roi"] > 120 or s["p_roi"] > 95 else ""
            results.append(f"    {vb_label:<10} N={s['n']:>4} W={s['wr']:>5.1f}% "
                           f"P={s['pr']:>5.1f}% 単={s['w_roi']:>6.1f}% 複={s['p_roi']:>6.1f}%{m}")
        if results:
            print(f"\n  [{ms}]")
            for r in results:
                print(r)

    # =================================================================
    # 2. Signal × rank_p帯
    # =================================================================
    print("\n" + "=" * 70)
    print("  2. Signal × rank_p帯")
    print("=" * 70)

    for ms in SIGNALS:
        subset = [d for d in data if d["ms"] == ms]
        if not subset:
            continue
        results = []
        for rp_label, filt in [
            ("rp=1", lambda d: d["rank_p"] == 1),
            ("rp=2-3", lambda d: 2 <= d["rank_p"] <= 3),
            ("rp=4+", lambda d: d["rank_p"] >= 4),
        ]:
            sub = [d for d in subset if filt(d)]
            if not sub:
                continue
            s = calc_stats(sub)
            m = " ★" if s["w_roi"] > 120 or s["p_roi"] > 95 else ""
            results.append(f"    {rp_label:<10} N={s['n']:>4} W={s['wr']:>5.1f}% "
                           f"P={s['pr']:>5.1f}% 単={s['w_roi']:>6.1f}% 複={s['p_roi']:>6.1f}%{m}")
        if results:
            print(f"\n  [{ms}]")
            for r in results:
                print(r)

    # =================================================================
    # 3. Signal × ARd帯
    # =================================================================
    print("\n" + "=" * 70)
    print("  3. Signal × ARd帯")
    print("=" * 70)

    for ms in ["鉄板", "軸向き", "やや妙味", "人気しすぎ"]:
        subset = [d for d in data if d["ms"] == ms]
        if not subset:
            continue
        results = []
        for label, filt in [
            ("ARd 55-65", lambda d: 55 <= d["ard"] < 65),
            ("ARd 65-75", lambda d: 65 <= d["ard"] < 75),
            ("ARd 75+", lambda d: d["ard"] >= 75),
        ]:
            sub = [d for d in subset if filt(d)]
            if not sub:
                continue
            s = calc_stats(sub)
            m = " ★" if s["w_roi"] > 120 or s["p_roi"] > 95 else ""
            results.append(f"    {label:<12} N={s['n']:>4} W={s['wr']:>5.1f}% "
                           f"P={s['pr']:>5.1f}% 単={s['w_roi']:>6.1f}% 複={s['p_roi']:>6.1f}%{m}")
        if results:
            print(f"\n  [{ms}]")
            for r in results:
                print(r)

    # =================================================================
    # 4. Signal × WinEV帯（EV高い方が成績良いか？）
    # =================================================================
    print("\n" + "=" * 70)
    print("  4. Signal × WinEV帯")
    print("=" * 70)

    for ms in ["やや妙味", "妙味", "人気しすぎ", "想定通り"]:
        subset = [d for d in data if d["ms"] == ms]
        if not subset:
            continue
        results = []
        for label, filt in [
            ("EV<1.0", lambda d: d["win_ev"] < 1.0),
            ("EV 1.0-1.5", lambda d: 1.0 <= d["win_ev"] < 1.5),
            ("EV 1.5-2.0", lambda d: 1.5 <= d["win_ev"] < 2.0),
            ("EV 2.0+", lambda d: d["win_ev"] >= 2.0),
        ]:
            sub = [d for d in subset if filt(d)]
            if not sub:
                continue
            s = calc_stats(sub)
            m = " ★" if s["w_roi"] > 120 or s["p_roi"] > 95 else ""
            results.append(f"    {label:<12} N={s['n']:>4} W={s['wr']:>5.1f}% "
                           f"P={s['pr']:>5.1f}% 単={s['w_roi']:>6.1f}% 複={s['p_roi']:>6.1f}%{m}")
        if results:
            print(f"\n  [{ms}]")
            for r in results:
                print(r)

    # =================================================================
    # 5. 月別安定性
    # =================================================================
    print("\n" + "=" * 70)
    print("  5. 月別安定性")
    print("=" * 70)

    for ms in ["鉄板", "やや妙味", "人気しすぎ"]:
        subset = [d for d in data if d["ms"] == ms]
        if not subset:
            continue
        months = sorted(set(d["month"] for d in subset))
        print(f"\n  [{ms}] {len(months)}ヶ月")
        win_months_w = 0
        win_months_p = 0
        for m in months:
            sub = [d for d in subset if d["month"] == m]
            s = calc_stats(sub)
            mw = "+" if s["w_roi"] >= 100 else "-"
            mp = "+" if s["p_roi"] >= 100 else "-"
            if s["w_roi"] >= 100:
                win_months_w += 1
            if s["p_roi"] >= 100:
                win_months_p += 1
            print(f"    {m}: N={s['n']:>3} W={s['wins']:>2}/{s['n']} "
                  f"単={s['w_roi']:>6.1f}%{mw} 複={s['p_roi']:>6.1f}%{mp}")
        print(f"    単勝ち月: {win_months_w}/{len(months)} ({win_months_w / len(months) * 100:.0f}%)"
              f" | 複勝ち月: {win_months_p}/{len(months)} ({win_months_p / len(months) * 100:.0f}%)")

    # =================================================================
    # 6. 複合シグナル（鉄板+VB / やや妙味+VB 等の最強組み合わせ）
    # =================================================================
    print("\n" + "=" * 70)
    print("  6. 最強組み合わせ候補")
    print("=" * 70)

    combos = [
        ("鉄板 (ALL)", lambda d: d["ms"] == "鉄板"),
        ("鉄板+VB_any", lambda d: d["ms"] == "鉄板" and (d["vb_win"] or d["vb_place"])),
        ("鉄板+ARd65+", lambda d: d["ms"] == "鉄板" and d["ard"] >= 65),
        ("やや妙味 (ALL)", lambda d: d["ms"] == "やや妙味"),
        ("やや妙味+VB_win", lambda d: d["ms"] == "やや妙味" and d["vb_win"]),
        ("やや妙味+EV1.5+", lambda d: d["ms"] == "やや妙味" and d["win_ev"] >= 1.5),
        ("人気しすぎ (ALL)", lambda d: d["ms"] == "人気しすぎ"),
        ("人気しすぎ+VB_any", lambda d: d["ms"] == "人気しすぎ" and (d["vb_win"] or d["vb_place"])),
        ("穴注目+VB_place", lambda d: d["ms"] == "穴注目" and d["vb_place"]),
        ("both候補", lambda d: (d["ms"] in ("妙味", "やや妙味", "穴注目")) and (d["vb_win"] or d["vb_place"])),
    ]

    print(f"\n  {'組み合わせ':>22} {'N':>5} {'勝率':>6} {'複勝率':>6} {'単ROI':>7} {'複ROI':>7}")
    print("  " + "-" * 55)
    for label, filt in combos:
        sub = [d for d in data if filt(d)]
        if not sub:
            continue
        s = calc_stats(sub)
        m = " ★" if s["w_roi"] > 120 or s["p_roi"] > 95 else ""
        print(f"  {label:>22} {s['n']:>5} {s['wr']:>5.1f}% {s['pr']:>5.1f}% "
              f"{s['w_roi']:>6.1f}% {s['p_roi']:>6.1f}%{m}")

    print("\n  Done.")


if __name__ == "__main__":
    main()
