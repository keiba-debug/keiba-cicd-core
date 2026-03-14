#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""フィルター付きDistortion戦略バックテスト"""
import json
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from ml.simulate_sanrentan_ev import (
    load_backtest_cache, load_sanrentan_payouts,
    extract_win_probs, extract_market_probs,
    compute_distortions,
)

FILTERS = {
    "Base_D3_T10":        {"min_dist": 3.0, "max_tickets": 10, "horses": 10,
                           "min_avg_dist": 0, "max_conf": 999, "min_runners": 0},
    "AvgD8+_D3_T10":      {"min_dist": 3.0, "max_tickets": 10, "horses": 10,
                           "min_avg_dist": 8, "max_conf": 999, "min_runners": 0},
    "AvgD15+_D3_T10":     {"min_dist": 3.0, "max_tickets": 10, "horses": 10,
                           "min_avg_dist": 15, "max_conf": 999, "min_runners": 0},
    "LowConf_D3_T10":     {"min_dist": 3.0, "max_tickets": 10, "horses": 10,
                           "min_avg_dist": 0, "max_conf": 0.03, "min_runners": 0},
    "LowConf+AvgD8_T10":  {"min_dist": 3.0, "max_tickets": 10, "horses": 10,
                           "min_avg_dist": 8, "max_conf": 0.03, "min_runners": 0},
    "13+頭_D3_T10":       {"min_dist": 3.0, "max_tickets": 10, "horses": 10,
                           "min_avg_dist": 0, "max_conf": 999, "min_runners": 13},
    "13+頭+AvgD8_T10":    {"min_dist": 3.0, "max_tickets": 10, "horses": 10,
                           "min_avg_dist": 8, "max_conf": 999, "min_runners": 13},
    "LowConf+13頭_T10":   {"min_dist": 3.0, "max_tickets": 10, "horses": 10,
                           "min_avg_dist": 0, "max_conf": 0.03, "min_runners": 13},
    "AvgD8+_D3_T5":       {"min_dist": 3.0, "max_tickets": 5, "horses": 10,
                           "min_avg_dist": 8, "max_conf": 999, "min_runners": 0},
    "AvgD15+_D3_T5":      {"min_dist": 3.0, "max_tickets": 5, "horses": 10,
                           "min_avg_dist": 15, "max_conf": 999, "min_runners": 0},
    "AllFilter_T10":       {"min_dist": 3.0, "max_tickets": 10, "horses": 10,
                           "min_avg_dist": 8, "max_conf": 0.03, "min_runners": 13},
    "AvgD8+_D5_T10":      {"min_dist": 5.0, "max_tickets": 10, "horses": 10,
                           "min_avg_dist": 8, "max_conf": 999, "min_runners": 0},
    "AvgD8+_D3_T10_H12":  {"min_dist": 3.0, "max_tickets": 10, "horses": 12,
                           "min_avg_dist": 8, "max_conf": 999, "min_runners": 0},
}


def main():
    cache = load_backtest_cache()
    race_codes = [r["race_id"] for r in cache]
    payouts = load_sanrentan_payouts(race_codes)

    results = {f: {"races": 0, "tickets": 0, "invested": 0, "returned": 0,
                   "hits": 0, "monthly": {}, "hit_details": []}
               for f in FILTERS}

    for race in cache:
        race_id = race["race_id"]
        entries = race.get("entries", [])
        if race.get("track_type") in ("obstacle", "steeplechase"):
            continue
        race_payouts = payouts.get(race_id)
        if not race_payouts:
            continue
        valid = [e for e in entries if (e.get("odds") or 0) > 0]
        if len(valid) < 5:
            continue

        model_probs = extract_win_probs(entries)
        market_probs = extract_market_probs(entries)
        if len(model_probs) < 5:
            continue

        n_runners = len(valid)
        p_vals = sorted([e.get("pred_proba_p_raw", 0) for e in entries], reverse=True)
        conf_gap = p_vals[0] - p_vals[1] if len(p_vals) >= 2 else 0
        month = f"{race_id[:4]}-{race_id[4:6]}"
        payout_map = {t: p for t, p in race_payouts}

        for fname, cfg in FILTERS.items():
            # レースフィルター
            if n_runners < cfg["min_runners"]:
                continue
            if conf_gap > cfg["max_conf"]:
                continue

            # Distortion計算
            dists = compute_distortions(model_probs, market_probs, cfg["horses"])
            selected = [(t, mp, mkp, r) for t, mp, mkp, r in dists
                        if r >= cfg["min_dist"]][:cfg["max_tickets"]]
            if not selected:
                continue

            # AvgDist フィルター
            avg_d = sum(r for _, _, _, r in selected) / len(selected)
            if avg_d < cfg["min_avg_dist"]:
                continue

            sr = results[fname]
            sr["races"] += 1
            sr["tickets"] += len(selected)
            sr["invested"] += len(selected) * 100

            if month not in sr["monthly"]:
                sr["monthly"][month] = {"races": 0, "tickets": 0,
                                        "inv": 0, "ret": 0, "hits": 0}
            m = sr["monthly"][month]
            m["races"] += 1
            m["tickets"] += len(selected)
            m["inv"] += len(selected) * 100

            for t, _, _, ratio in selected:
                if t in payout_map:
                    pay = payout_map[t]
                    sr["hits"] += 1
                    sr["returned"] += pay
                    m["hits"] += 1
                    m["ret"] += pay
                    sr["hit_details"].append((race_id, t, pay, ratio))

    # ===== 出力 =====
    print(f"\n{'='*120}")
    print(f"  フィルター付き Distortion戦略 バックテスト")
    print(f"{'='*120}")
    print(f"{'Strategy':<22} {'Races':>6} {'Tkts':>7} {'Avg':>5} {'Hits':>4} "
          f"{'HitR%':>6} {'Invested':>11} {'Return':>11} {'ROI%':>7} {'AvgPay':>9} "
          f"{'月投資':>8} {'月R数':>5}")
    print(f"{'-'*120}")

    for fname in FILTERS:
        sr = results[fname]
        if sr["races"] == 0:
            continue
        roi = sr["returned"] / sr["invested"] * 100 if sr["invested"] else 0
        hr = sr["hits"] / sr["races"] * 100 if sr["races"] else 0
        avg_t = sr["tickets"] / sr["races"] if sr["races"] else 0
        avg_pay = sr["returned"] // sr["hits"] if sr["hits"] else 0
        n_months = len(sr["monthly"])
        monthly_inv = sr["invested"] / n_months if n_months else 0
        monthly_races = sr["races"] / n_months if n_months else 0
        marker = " **" if roi >= 100 else ""
        print(f"{fname:<22} {sr['races']:>6} {sr['tickets']:>7} {avg_t:>5.1f} "
              f"{sr['hits']:>4} {hr:>5.1f}% {sr['invested']:>10,} {sr['returned']:>10,} "
              f"{roi:>6.1f}%{marker} {avg_pay:>8,} {monthly_inv:>8,.0f} {monthly_races:>5.0f}")

    print(f"{'-'*120}")
    print(f"  月投資 = 総投資/月数, 月R数 = レース数/月数")

    # 有望戦略の月次
    promising = ["AvgD8+_D3_T10", "AvgD15+_D3_T10", "LowConf_D3_T10",
                 "13+頭+AvgD8_T10", "AvgD15+_D3_T5", "LowConf+AvgD8_T10",
                 "AllFilter_T10"]
    for fname in promising:
        sr = results[fname]
        if sr["races"] < 10:
            continue
        roi = sr["returned"] / sr["invested"] * 100 if sr["invested"] else 0
        print(f"\n--- {fname} (ROI {roi:.1f}%) ---")
        cum = 0
        for month in sorted(sr["monthly"]):
            m = sr["monthly"][month]
            m_roi = m["ret"] / m["inv"] * 100 if m["inv"] else 0
            pnl = m["ret"] - m["inv"]
            cum += pnl
            print(f"  {month} {m['races']:>4}R {m['tickets']:>5}点 {m['hits']}的中 "
                  f"Inv={m['inv']:>8,} Ret={m['ret']:>8,} "
                  f"ROI={m_roi:>6.1f}% PnL={pnl:>+9,} Cum={cum:>+10,}")

    # 的中詳細
    print(f"\n{'='*90}")
    print(f"  的中詳細（全フィルター横断）")
    print(f"{'='*90}")
    all_hits = set()
    for fname, sr in results.items():
        for race_id, ticket, pay, ratio in sr["hit_details"]:
            all_hits.add((race_id, ticket, pay, ratio, fname))

    for race_id, ticket, pay, ratio, fname in sorted(all_hits, key=lambda x: -x[2]):
        t = ticket
        print(f"  {race_id} {t[0]:>2}-{t[1]:>2}-{t[2]:>2} "
              f"Pay={pay:>10,} Dist={ratio:>6.1f} [{fname}]")


if __name__ == "__main__":
    main()
