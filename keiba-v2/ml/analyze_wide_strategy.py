"""
激戦ワイド (Intense Wide Bet) Strategy Analysis
Goal: Find conditions where wide (quinella place) hit rate >= 50% with 1-3 tickets
Wide = pick 2 horses, both must finish top 3
"""
import json
import sys
from collections import defaultdict

def load_data():
    with open("C:/KEIBA-CICD/data3/ml/backtest_cache.json", "r", encoding="utf-8") as f:
        return json.load(f)

def get_entry_count_bin(n):
    if n <= 10:
        return "<=10"
    elif n <= 14:
        return "11-14"
    else:
        return "15-18"

def get_confidence_bin(p):
    if p >= 0.30:
        return ">=30%"
    elif p >= 0.25:
        return "25-30%"
    elif p >= 0.20:
        return "20-25%"
    elif p >= 0.15:
        return "15-20%"
    else:
        return "<15%"

def get_ard_gap_bin(gap):
    if gap >= 15:
        return ">=15"
    elif gap >= 10:
        return "10-15"
    elif gap >= 5:
        return "5-10"
    else:
        return "<5"

def check_wide_hit(entries, idx1, idx2):
    """Check if both horses finished top3"""
    return entries[idx1]["is_top3"] == 1 and entries[idx2]["is_top3"] == 1

def analyze():
    data = load_data()
    print(f"Total races in backtest_cache: {len(data)}")

    # Filter: skip obstacle races and races with too few entries
    races = []
    for r in data:
        entries = r["entries"]
        # Skip if fewer than 5 entries (not meaningful)
        if len(entries) < 5:
            continue
        # Sort entries by various ranks
        races.append(r)

    print(f"Races after filtering: {len(races)}")

    # ============================================================
    # STRATEGY DEFINITIONS
    # ============================================================
    strategies = {}

    def compute_strategies(race):
        entries = race["entries"]
        n = len(entries)

        # Sort by rank_p
        by_p = sorted(range(n), key=lambda i: entries[i]["rank_p"])
        # Sort by rank_w
        by_w = sorted(range(n), key=lambda i: entries[i]["rank_w"])
        # Sort by ar_deviation descending
        by_ard = sorted(range(n), key=lambda i: entries[i]["ar_deviation"], reverse=True)
        # Sort by odds (favorites)
        by_odds = sorted(range(n), key=lambda i: entries[i]["odds"])

        result = {}

        # Strategy 1: rank_p top1-2
        result["P top1-2"] = [(by_p[0], by_p[1])]

        # Strategy 2: rank_w top1-2
        result["W top1-2"] = [(by_w[0], by_w[1])]

        # Strategy 3: rank_p top1 + rank_w top1 (if different)
        if by_p[0] != by_w[0]:
            result["P1+W1"] = [(by_p[0], by_w[0])]
        else:
            result["P1+W1"] = [(by_p[0], by_p[1])]  # fallback to P top1-2

        # Strategy 4: Best 2 of top3 by rank_p (3 tickets)
        result["P top3 combo"] = [
            (by_p[0], by_p[1]),
            (by_p[0], by_p[2]),
            (by_p[1], by_p[2]),
        ]

        # Strategy 5: ARd top1-2
        result["ARd top1-2"] = [(by_ard[0], by_ard[1])]

        # Strategy 6: P1 + ARd1 (if different)
        if by_p[0] != by_ard[0]:
            result["P1+ARd1"] = [(by_p[0], by_ard[0])]
        else:
            result["P1+ARd1"] = [(by_p[0], by_p[1])]

        # Strategy 7: Odds top1-2 (favorites)
        result["Fav top1-2"] = [(by_odds[0], by_odds[1])]

        # Strategy 8: P1 + Fav1 (if different)
        if by_p[0] != by_odds[0]:
            result["P1+Fav1"] = [(by_p[0], by_odds[0])]
        else:
            result["P1+Fav1"] = [(by_p[0], by_p[1])]

        # Strategy 9: P top1-2 + P top1-3 (2 tickets: 1-2 and 1-3)
        result["P top1 axis(2t)"] = [
            (by_p[0], by_p[1]),
            (by_p[0], by_p[2]),
        ]

        # Strategy 10: Union of P1+W1 and P1+ARd1 (unique pairs, max 2 tickets)
        pairs_10 = set()
        p1_w1 = tuple(sorted([by_p[0], by_w[0]])) if by_p[0] != by_w[0] else tuple(sorted([by_p[0], by_p[1]]))
        p1_ard1 = tuple(sorted([by_p[0], by_ard[0]])) if by_p[0] != by_ard[0] else tuple(sorted([by_p[0], by_p[1]]))
        pairs_10.add(p1_w1)
        pairs_10.add(p1_ard1)
        result["P1+W1 | P1+ARd1"] = [tuple(p) for p in pairs_10]

        return result, entries, by_p, by_ard

    # ============================================================
    # OVERALL STRATEGY COMPARISON
    # ============================================================
    print("\n" + "="*80)
    print("PART 1: OVERALL STRATEGY COMPARISON")
    print("="*80)

    strat_stats = defaultdict(lambda: {"total": 0, "hit": 0, "tickets": 0})

    for race in races:
        strats, entries, by_p, by_ard = compute_strategies(race)
        for name, pairs in strats.items():
            strat_stats[name]["total"] += 1
            strat_stats[name]["tickets"] += len(pairs)
            hit = any(check_wide_hit(entries, i, j) for i, j in pairs)
            if hit:
                strat_stats[name]["hit"] += 1

    print(f"\n{'Strategy':<22} {'Races':>6} {'Hit':>6} {'Rate':>7} {'Tickets':>8} {'T/R':>5}")
    print("-" * 60)
    for name in ["P top1-2", "W top1-2", "P1+W1", "ARd top1-2", "P1+ARd1",
                  "Fav top1-2", "P1+Fav1", "P top1 axis(2t)", "P top3 combo", "P1+W1 | P1+ARd1"]:
        s = strat_stats[name]
        rate = s["hit"] / s["total"] * 100 if s["total"] > 0 else 0
        tpr = s["tickets"] / s["total"] if s["total"] > 0 else 0
        print(f"{name:<22} {s['total']:>6} {s['hit']:>6} {rate:>6.1f}% {s['tickets']:>8} {tpr:>5.1f}")

    # ============================================================
    # PART 2: BREAKDOWN BY ENTRY COUNT
    # ============================================================
    print("\n" + "="*80)
    print("PART 2: HIT RATE BY ENTRY COUNT")
    print("="*80)

    key_strategies = ["P top1-2", "W top1-2", "P1+W1", "P top3 combo", "P1+ARd1"]

    for strat_name in key_strategies:
        breakdown = defaultdict(lambda: {"total": 0, "hit": 0})
        for race in races:
            strats, entries, _, _ = compute_strategies(race)
            if strat_name not in strats:
                continue
            pairs = strats[strat_name]
            n = len(entries)
            bin_label = get_entry_count_bin(n)
            breakdown[bin_label]["total"] += 1
            hit = any(check_wide_hit(entries, i, j) for i, j in pairs)
            if hit:
                breakdown[bin_label]["hit"] += 1

        print(f"\n  {strat_name}:")
        print(f"  {'Entries':<10} {'Races':>6} {'Hit':>6} {'Rate':>7}")
        print(f"  {'-'*35}")
        for b in ["<=10", "11-14", "15-18"]:
            if b in breakdown:
                s = breakdown[b]
                rate = s["hit"] / s["total"] * 100 if s["total"] > 0 else 0
                print(f"  {b:<10} {s['total']:>6} {s['hit']:>6} {rate:>6.1f}%")

    # ============================================================
    # PART 3: BREAKDOWN BY ARd GAP (top1 - top2)
    # ============================================================
    print("\n" + "="*80)
    print("PART 3: HIT RATE BY ARd GAP (top1 ARd - top2 ARd)")
    print("="*80)

    for strat_name in key_strategies:
        breakdown = defaultdict(lambda: {"total": 0, "hit": 0})
        for race in races:
            strats, entries, _, by_ard = compute_strategies(race)
            if strat_name not in strats:
                continue
            pairs = strats[strat_name]
            # ARd gap = top1 - top2
            ard1 = entries[by_ard[0]]["ar_deviation"]
            ard2 = entries[by_ard[1]]["ar_deviation"]
            gap = ard1 - ard2
            bin_label = get_ard_gap_bin(gap)
            breakdown[bin_label]["total"] += 1
            hit = any(check_wide_hit(entries, i, j) for i, j in pairs)
            if hit:
                breakdown[bin_label]["hit"] += 1

        print(f"\n  {strat_name}:")
        print(f"  {'ARd Gap':<10} {'Races':>6} {'Hit':>6} {'Rate':>7}")
        print(f"  {'-'*35}")
        for b in ["<5", "5-10", "10-15", ">=15"]:
            if b in breakdown:
                s = breakdown[b]
                rate = s["hit"] / s["total"] * 100 if s["total"] > 0 else 0
                print(f"  {b:<10} {s['total']:>6} {s['hit']:>6} {rate:>6.1f}%")

    # ============================================================
    # PART 4: BREAKDOWN BY TOP1 CONFIDENCE (pred_proba_p_raw)
    # ============================================================
    print("\n" + "="*80)
    print("PART 4: HIT RATE BY TOP1 CONFIDENCE (pred_proba_p_raw of rank_p=1)")
    print("="*80)

    for strat_name in key_strategies:
        breakdown = defaultdict(lambda: {"total": 0, "hit": 0})
        for race in races:
            strats, entries, by_p, _ = compute_strategies(race)
            if strat_name not in strats:
                continue
            pairs = strats[strat_name]
            top1_conf = entries[by_p[0]]["pred_proba_p_raw"]
            bin_label = get_confidence_bin(top1_conf)
            breakdown[bin_label]["total"] += 1
            hit = any(check_wide_hit(entries, i, j) for i, j in pairs)
            if hit:
                breakdown[bin_label]["hit"] += 1

        print(f"\n  {strat_name}:")
        print(f"  {'Confidence':<12} {'Races':>6} {'Hit':>6} {'Rate':>7}")
        print(f"  {'-'*37}")
        for b in [">=30%", "25-30%", "20-25%", "15-20%", "<15%"]:
            if b in breakdown:
                s = breakdown[b]
                rate = s["hit"] / s["total"] * 100 if s["total"] > 0 else 0
                print(f"  {b:<12} {s['total']:>6} {s['hit']:>6} {rate:>6.1f}%")

    # ============================================================
    # PART 5: COMBINED FILTER SEARCH - maximize hit rate
    # ============================================================
    print("\n" + "="*80)
    print("PART 5: COMBINED FILTER SEARCH (target: hit rate >= 50%)")
    print("="*80)

    # Build per-race features for filtering
    race_records = []
    for race in races:
        strats, entries, by_p, by_ard = compute_strategies(race)
        n = len(entries)
        ard1 = entries[by_ard[0]]["ar_deviation"]
        ard2 = entries[by_ard[1]]["ar_deviation"]
        ard_gap = ard1 - ard2
        top1_conf = entries[by_p[0]]["pred_proba_p_raw"]
        top2_conf = entries[by_p[1]]["pred_proba_p_raw"]
        conf_gap = top1_conf - top2_conf

        # Compute P top1-2 gap (rank_p confidence gap)
        p_gap = top1_conf - top2_conf

        # Odds of top picks
        p1_odds = entries[by_p[0]]["odds"]
        p2_odds = entries[by_p[1]]["odds"]

        # Simple race_confidence proxy: top1_conf * (conf_gap / top1_conf) * ard_gap
        # Higher = more separation = more confident

        rec = {
            "entry_count": n,
            "ard_gap": ard_gap,
            "ard_top1": ard1,
            "top1_conf": top1_conf,
            "top2_conf": top2_conf,
            "conf_gap": conf_gap,
            "p1_odds": p1_odds,
            "p2_odds": p2_odds,
            "grade": race.get("grade", ""),
        }

        # Compute hit for each strategy
        for name, pairs in strats.items():
            rec[f"hit_{name}"] = 1 if any(check_wide_hit(entries, i, j) for i, j in pairs) else 0

        race_records.append(rec)

    print(f"\nTotal race records: {len(race_records)}")

    # Try systematic filter combinations
    best_combos = []

    entry_filters = [
        ("all", lambda r: True),
        ("<=10", lambda r: r["entry_count"] <= 10),
        ("<=14", lambda r: r["entry_count"] <= 14),
        (">=11", lambda r: r["entry_count"] >= 11),
    ]

    conf_filters = [
        ("all", lambda r: True),
        ("conf>=20%", lambda r: r["top1_conf"] >= 0.20),
        ("conf>=25%", lambda r: r["top1_conf"] >= 0.25),
        ("conf>=30%", lambda r: r["top1_conf"] >= 0.30),
        ("conf>=35%", lambda r: r["top1_conf"] >= 0.35),
    ]

    ard_filters = [
        ("all", lambda r: True),
        ("ardgap>=5", lambda r: r["ard_gap"] >= 5),
        ("ardgap>=10", lambda r: r["ard_gap"] >= 10),
        ("ardgap>=15", lambda r: r["ard_gap"] >= 15),
        ("ard1>=60", lambda r: r["ard_top1"] >= 60),
        ("ard1>=65", lambda r: r["ard_top1"] >= 65),
    ]

    odds_filters = [
        ("all", lambda r: True),
        ("p1odds<=5", lambda r: r["p1_odds"] <= 5.0),
        ("p1odds<=10", lambda r: r["p1_odds"] <= 10.0),
        ("p2odds<=10", lambda r: r["p2_odds"] <= 10.0),
        ("p2odds<=20", lambda r: r["p2_odds"] <= 20.0),
    ]

    target_strats = ["P top1-2", "P1+W1", "P1+ARd1", "P top1 axis(2t)", "P top3 combo"]

    for strat in target_strats:
        hit_key = f"hit_{strat}"
        for ef_name, ef in entry_filters:
            for cf_name, cf in conf_filters:
                for af_name, af in ard_filters:
                    for of_name, of_ in odds_filters:
                        filtered = [r for r in race_records if ef(r) and cf(r) and af(r) and of_(r)]
                        if len(filtered) < 30:  # need minimum sample
                            continue
                        hits = sum(r[hit_key] for r in filtered)
                        total = len(filtered)
                        rate = hits / total * 100
                        if rate >= 50:
                            # Count active filters
                            active = sum(1 for x in [ef_name, cf_name, af_name, of_name] if x != "all")
                            best_combos.append({
                                "strat": strat,
                                "filters": f"{ef_name} | {cf_name} | {af_name} | {of_name}",
                                "total": total,
                                "hit": hits,
                                "rate": rate,
                                "active_filters": active,
                            })

    # Sort by rate desc, then total desc
    best_combos.sort(key=lambda x: (-x["rate"], -x["total"]))

    print(f"\nFound {len(best_combos)} combos with hit rate >= 50%")
    print(f"\n{'Strategy':<20} {'Filters':<50} {'Races':>6} {'Hit':>5} {'Rate':>7}")
    print("-" * 95)
    for c in best_combos[:40]:
        print(f"{c['strat']:<20} {c['filters']:<50} {c['total']:>6} {c['hit']:>5} {c['rate']:>6.1f}%")

    # ============================================================
    # PART 6: BEST PRACTICAL STRATEGIES (balance hit rate vs coverage)
    # ============================================================
    print("\n" + "="*80)
    print("PART 6: TOP PRACTICAL STRATEGIES (rate >= 50%, races >= 100)")
    print("="*80)

    practical = [c for c in best_combos if c["total"] >= 100]
    practical.sort(key=lambda x: (-x["rate"], -x["total"]))

    print(f"\n{'Strategy':<20} {'Filters':<50} {'Races':>6} {'Hit':>5} {'Rate':>7}")
    print("-" * 95)
    for c in practical[:25]:
        print(f"{c['strat']:<20} {c['filters']:<50} {c['total']:>6} {c['hit']:>5} {c['rate']:>6.1f}%")

    # ============================================================
    # PART 7: Deep dive on best strategies - payout analysis
    # ============================================================
    print("\n" + "="*80)
    print("PART 7: ESTIMATED WIDE PAYOUT RANGE ANALYSIS")
    print("="*80)

    # For P top1-2 strategy, look at odds of the pair to estimate wide payout
    for strat_name in ["P top1-2", "P1+W1"]:
        print(f"\n  {strat_name} - Odds profile of pair:")
        odds_bins = defaultdict(lambda: {"total": 0, "hit": 0})
        for race in races:
            strats, entries, by_p, _ = compute_strategies(race)
            pairs = strats[strat_name]
            i, j = pairs[0]
            max_odds = max(entries[i]["odds"], entries[j]["odds"])
            if max_odds <= 5:
                b = "both<=5x"
            elif max_odds <= 10:
                b = "max<=10x"
            elif max_odds <= 20:
                b = "max<=20x"
            else:
                b = "max>20x"
            odds_bins[b]["total"] += 1
            hit = check_wide_hit(entries, i, j)
            if hit:
                odds_bins[b]["hit"] += 1

        print(f"  {'Odds Profile':<15} {'Races':>6} {'Hit':>6} {'Rate':>7}")
        print(f"  {'-'*40}")
        for b in ["both<=5x", "max<=10x", "max<=20x", "max>20x"]:
            if b in odds_bins:
                s = odds_bins[b]
                rate = s["hit"] / s["total"] * 100 if s["total"] > 0 else 0
                print(f"  {b:<15} {s['total']:>6} {s['hit']:>6} {rate:>6.1f}%")

    # ============================================================
    # PART 8: Rank agreement analysis
    # ============================================================
    print("\n" + "="*80)
    print("PART 8: RANK AGREEMENT BONUS (P, W, ARd, Odds agree)")
    print("="*80)

    agree_bins = defaultdict(lambda: {"total": 0, "hit": 0})
    for race in races:
        strats, entries, by_p, by_ard = compute_strategies(race)
        n = len(entries)
        by_w = sorted(range(n), key=lambda i: entries[i]["rank_w"])
        by_odds = sorted(range(n), key=lambda i: entries[i]["odds"])

        # Count how many systems agree on top1
        top1_p = by_p[0]
        agree_count = 1  # P itself
        if by_w[0] == top1_p:
            agree_count += 1
        if by_ard[0] == top1_p:
            agree_count += 1
        if by_odds[0] == top1_p:
            agree_count += 1

        # Check P top1-2 hit
        hit = check_wide_hit(entries, by_p[0], by_p[1])
        agree_bins[f"top1_agree={agree_count}"]["total"] += 1
        if hit:
            agree_bins[f"top1_agree={agree_count}"]["hit"] += 1

    print(f"\n  P top1-2 strategy, by top1 agreement count:")
    print(f"  {'Agreement':<18} {'Races':>6} {'Hit':>6} {'Rate':>7}")
    print(f"  {'-'*40}")
    for a in [1, 2, 3, 4]:
        b = f"top1_agree={a}"
        if b in agree_bins:
            s = agree_bins[b]
            rate = s["hit"] / s["total"] * 100 if s["total"] > 0 else 0
            print(f"  {b:<18} {s['total']:>6} {s['hit']:>6} {rate:>6.1f}%")

    # Top2 agreement
    print(f"\n  P top1-2 strategy, by top1+top2 pair agreement:")
    pair_agree_bins = defaultdict(lambda: {"total": 0, "hit": 0})
    for race in races:
        strats, entries, by_p, by_ard = compute_strategies(race)
        n = len(entries)
        by_w = sorted(range(n), key=lambda i: entries[i]["rank_w"])
        by_odds = sorted(range(n), key=lambda i: entries[i]["odds"])

        p_pair = set([by_p[0], by_p[1]])
        agree = 0
        if set([by_w[0], by_w[1]]) == p_pair:
            agree += 1
        if set([by_ard[0], by_ard[1]]) == p_pair:
            agree += 1
        if set([by_odds[0], by_odds[1]]) == p_pair:
            agree += 1

        hit = check_wide_hit(entries, by_p[0], by_p[1])
        pair_agree_bins[f"pair_agree={agree}"]["total"] += 1
        if hit:
            pair_agree_bins[f"pair_agree={agree}"]["hit"] += 1

    print(f"  {'Pair Agreement':<18} {'Races':>6} {'Hit':>6} {'Rate':>7}")
    print(f"  {'-'*40}")
    for a in [0, 1, 2, 3]:
        b = f"pair_agree={a}"
        if b in pair_agree_bins:
            s = pair_agree_bins[b]
            rate = s["hit"] / s["total"] * 100 if s["total"] > 0 else 0
            print(f"  {b:<18} {s['total']:>6} {s['hit']:>6} {rate:>6.1f}%")


if __name__ == "__main__":
    analyze()
