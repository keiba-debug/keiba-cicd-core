"""
激戦ワイド v2: Deep dive on best findings from v1
Focus on:
1. pair_agree=3 (P/W/ARd/Odds top2 all agree) -> 42.7% with 1 ticket
2. P top3 combo with <=10 entries -> 67% with 3 tickets
3. Can we get 1-ticket strategies to 50%?
4. Hybrid: 1-2 ticket strategies with agreement + entry count filters
"""
import json
from collections import defaultdict

def load_data():
    with open("C:/KEIBA-CICD/data3/ml/backtest_cache.json", "r", encoding="utf-8") as f:
        return json.load(f)

def check_wide_hit(entries, i, j):
    return entries[i]["is_top3"] == 1 and entries[j]["is_top3"] == 1

def compute_race_features(race):
    entries = race["entries"]
    n = len(entries)
    by_p = sorted(range(n), key=lambda i: entries[i]["rank_p"])
    by_w = sorted(range(n), key=lambda i: entries[i]["rank_w"])
    by_ard = sorted(range(n), key=lambda i: entries[i]["ar_deviation"], reverse=True)
    by_odds = sorted(range(n), key=lambda i: entries[i]["odds"])

    # Pair agreement count
    p_pair = set([by_p[0], by_p[1]])
    pair_agree = 0
    if set([by_w[0], by_w[1]]) == p_pair:
        pair_agree += 1
    if set([by_ard[0], by_ard[1]]) == p_pair:
        pair_agree += 1
    if set([by_odds[0], by_odds[1]]) == p_pair:
        pair_agree += 1

    # Top1 agreement
    top1_agree = 1
    if by_w[0] == by_p[0]: top1_agree += 1
    if by_ard[0] == by_p[0]: top1_agree += 1
    if by_odds[0] == by_p[0]: top1_agree += 1

    p1_odds = entries[by_p[0]]["odds"]
    p2_odds = entries[by_p[1]]["odds"]
    p3_odds = entries[by_p[2]]["odds"] if n > 2 else 999
    p1_conf = entries[by_p[0]]["pred_proba_p_raw"]
    p2_conf = entries[by_p[1]]["pred_proba_p_raw"]

    ard1 = entries[by_ard[0]]["ar_deviation"]
    ard2 = entries[by_ard[1]]["ar_deviation"]
    ard_gap = ard1 - ard2

    # Strategies
    strats = {}
    strats["P top1-2"] = [(by_p[0], by_p[1])]
    strats["P top3 combo"] = [(by_p[0], by_p[1]), (by_p[0], by_p[2]), (by_p[1], by_p[2])]
    strats["P top1 axis(2t)"] = [(by_p[0], by_p[1]), (by_p[0], by_p[2])]

    # Consensus pair: majority vote among P/W/ARd/Odds
    from collections import Counter
    all_top2 = [by_p[0], by_p[1], by_w[0], by_w[1], by_ard[0], by_ard[1], by_odds[0], by_odds[1]]
    counts = Counter(all_top2)
    consensus_top2 = [h for h, _ in counts.most_common(2)]
    if len(consensus_top2) == 2:
        strats["Consensus top2"] = [(consensus_top2[0], consensus_top2[1])]
    else:
        strats["Consensus top2"] = [(by_p[0], by_p[1])]

    # Consensus top3
    all_top3 = [by_p[0], by_p[1], by_p[2], by_w[0], by_w[1], by_w[2],
                by_ard[0], by_ard[1], by_ard[2], by_odds[0], by_odds[1], by_odds[2]]
    counts3 = Counter(all_top3)
    consensus_top3 = [h for h, _ in counts3.most_common(3)]
    if len(consensus_top3) >= 3:
        strats["Consensus top3 combo"] = [
            (consensus_top3[0], consensus_top3[1]),
            (consensus_top3[0], consensus_top3[2]),
            (consensus_top3[1], consensus_top3[2]),
        ]
    elif len(consensus_top3) == 2:
        strats["Consensus top3 combo"] = [(consensus_top3[0], consensus_top3[1])]
    else:
        strats["Consensus top3 combo"] = strats["P top3 combo"]

    # Consensus axis: consensus_top1 with consensus_top2 and consensus_top3
    c1 = counts.most_common(1)[0][0]
    strats["Consensus axis(2t)"] = []
    added = set()
    for h, _ in counts.most_common(4):
        if h != c1 and len(strats["Consensus axis(2t)"]) < 2:
            pair = tuple(sorted([c1, h]))
            if pair not in added:
                strats["Consensus axis(2t)"].append((c1, h))
                added.add(pair)
    if not strats["Consensus axis(2t)"]:
        strats["Consensus axis(2t)"] = strats["P top1 axis(2t)"]

    return {
        "entries": entries,
        "n": n,
        "by_p": by_p, "by_w": by_w, "by_ard": by_ard, "by_odds": by_odds,
        "pair_agree": pair_agree,
        "top1_agree": top1_agree,
        "p1_odds": p1_odds, "p2_odds": p2_odds, "p3_odds": p3_odds,
        "p1_conf": p1_conf, "p2_conf": p2_conf,
        "ard_gap": ard_gap, "ard1": ard1,
        "strats": strats,
        "grade": race.get("grade", ""),
    }

def print_table(title, bins, bin_order, cols=("Races", "Hit", "Rate")):
    print(f"\n  {title}")
    print(f"  {'Filter':<25} {cols[0]:>6} {cols[1]:>6} {cols[2]:>7}")
    print(f"  {'-'*48}")
    for b in bin_order:
        if b in bins:
            s = bins[b]
            rate = s["hit"] / s["total"] * 100 if s["total"] > 0 else 0
            print(f"  {b:<25} {s['total']:>6} {s['hit']:>6} {rate:>6.1f}%")

def main():
    data = load_data()
    races_raw = [r for r in data if len(r["entries"]) >= 5]
    races = [compute_race_features(r) for r in races_raw]
    print(f"Total races: {len(races)}")

    # ============================================================
    print("\n" + "="*80)
    print("PART 1: PAIR AGREEMENT + ENTRY COUNT CROSS-TAB (P top1-2, 1 ticket)")
    print("="*80)

    for entry_label, entry_filter in [("ALL", lambda r: True), ("<=10", lambda r: r["n"] <= 10),
                                       ("<=14", lambda r: r["n"] <= 14), (">=11", lambda r: r["n"] >= 11)]:
        bins = defaultdict(lambda: {"total": 0, "hit": 0})
        for r in races:
            if not entry_filter(r):
                continue
            pa = r["pair_agree"]
            hit = any(check_wide_hit(r["entries"], i, j) for i, j in r["strats"]["P top1-2"])
            bins[f"pair_agree={pa}"]["total"] += 1
            if hit:
                bins[f"pair_agree={pa}"]["hit"] += 1
        print_table(f"P top1-2 | entries {entry_label}", bins,
                    [f"pair_agree={a}" for a in [0,1,2,3]])

    # ============================================================
    print("\n" + "="*80)
    print("PART 2: PAIR AGREE=3 + ADDITIONAL FILTERS (P top1-2, 1 ticket)")
    print("="*80)

    # pair_agree=3 already gives 42.7%. Can we push it to 50%?
    pa3_races = [r for r in races if r["pair_agree"] == 3]
    print(f"\n  pair_agree=3 total: {len(pa3_races)}")

    for label, filt in [
        ("+ <=10 entries", lambda r: r["n"] <= 10),
        ("+ <=12 entries", lambda r: r["n"] <= 12),
        ("+ <=14 entries", lambda r: r["n"] <= 14),
        ("+ p1_odds<=3", lambda r: r["p1_odds"] <= 3),
        ("+ p1_odds<=5", lambda r: r["p1_odds"] <= 5),
        ("+ p2_odds<=5", lambda r: r["p2_odds"] <= 5),
        ("+ p2_odds<=10", lambda r: r["p2_odds"] <= 10),
        ("+ both_odds<=5", lambda r: r["p1_odds"] <= 5 and r["p2_odds"] <= 5),
        ("+ both_odds<=10", lambda r: r["p1_odds"] <= 10 and r["p2_odds"] <= 10),
        ("+ ard_gap>=5", lambda r: r["ard_gap"] >= 5),
        ("+ ard1>=60", lambda r: r["ard1"] >= 60),
        ("+ ard1>=65", lambda r: r["ard1"] >= 65),
        ("+ <=10 + p2<=10", lambda r: r["n"] <= 10 and r["p2_odds"] <= 10),
        ("+ <=12 + p2<=10", lambda r: r["n"] <= 12 and r["p2_odds"] <= 10),
        ("+ <=14 + both<=10", lambda r: r["n"] <= 14 and r["p1_odds"] <= 10 and r["p2_odds"] <= 10),
        ("+ <=14 + p2<=5", lambda r: r["n"] <= 14 and r["p2_odds"] <= 5),
        ("+ <=10 + both<=5", lambda r: r["n"] <= 10 and r["p1_odds"] <= 5 and r["p2_odds"] <= 5),
    ]:
        subset = [r for r in pa3_races if filt(r)]
        if len(subset) < 20:
            continue
        hits = sum(1 for r in subset if any(check_wide_hit(r["entries"], i, j) for i, j in r["strats"]["P top1-2"]))
        rate = hits / len(subset) * 100
        marker = " <<<" if rate >= 50 else ""
        print(f"  {label:<30} n={len(subset):>4}  hit={hits:>4}  rate={rate:>5.1f}%{marker}")

    # ============================================================
    print("\n" + "="*80)
    print("PART 3: CONSENSUS STRATEGIES (multi-model agreement)")
    print("="*80)

    for strat_name in ["Consensus top2", "Consensus axis(2t)", "Consensus top3 combo"]:
        bins = defaultdict(lambda: {"total": 0, "hit": 0})
        for entry_label, entry_filter in [("ALL", lambda r: True), ("<=10", lambda r: r["n"] <= 10),
                                           ("<=14", lambda r: r["n"] <= 14)]:
            subset = [r for r in races if entry_filter(r)]
            total = len(subset)
            hits = sum(1 for r in subset if any(check_wide_hit(r["entries"], i, j) for i, j in r["strats"][strat_name]))
            rate = hits / total * 100 if total > 0 else 0
            tickets = sum(len(r["strats"][strat_name]) for r in subset) / total if total > 0 else 0
            print(f"  {strat_name:<25} entries {entry_label:<5}  n={total:>5}  hit={hits:>5}  rate={rate:>5.1f}%  avg_tickets={tickets:.1f}")

    # ============================================================
    print("\n" + "="*80)
    print("PART 4: P top3 combo (3 tickets) - FILTER OPTIMIZATION")
    print("="*80)

    for label, filt in [
        ("ALL", lambda r: True),
        ("<=10", lambda r: r["n"] <= 10),
        ("<=10 + p3<=10", lambda r: r["n"] <= 10 and r["p3_odds"] <= 10),
        ("<=10 + p3<=20", lambda r: r["n"] <= 10 and r["p3_odds"] <= 20),
        ("<=10 + pair_agree>=2", lambda r: r["n"] <= 10 and r["pair_agree"] >= 2),
        ("<=10 + pair_agree=3", lambda r: r["n"] <= 10 and r["pair_agree"] == 3),
        ("<=10 + p2<=5", lambda r: r["n"] <= 10 and r["p2_odds"] <= 5),
        ("<=10 + ard_gap>=5", lambda r: r["n"] <= 10 and r["ard_gap"] >= 5),
        ("<=12", lambda r: r["n"] <= 12),
        ("<=12 + pair_agree>=2", lambda r: r["n"] <= 12 and r["pair_agree"] >= 2),
        ("<=12 + pair_agree=3", lambda r: r["n"] <= 12 and r["pair_agree"] == 3),
        ("<=14", lambda r: r["n"] <= 14),
        ("<=14 + pair_agree>=2", lambda r: r["n"] <= 14 and r["pair_agree"] >= 2),
        ("<=14 + pair_agree=3", lambda r: r["n"] <= 14 and r["pair_agree"] == 3),
        ("pair_agree=3", lambda r: r["pair_agree"] == 3),
        ("pair_agree>=2", lambda r: r["pair_agree"] >= 2),
        ("pair_agree>=2 + p2<=10", lambda r: r["pair_agree"] >= 2 and r["p2_odds"] <= 10),
        ("pair_agree=3 + p2<=10", lambda r: r["pair_agree"] == 3 and r["p2_odds"] <= 10),
    ]:
        subset = [r for r in races if filt(r)]
        if len(subset) < 20:
            continue
        hits = sum(1 for r in subset if any(check_wide_hit(r["entries"], i, j) for i, j in r["strats"]["P top3 combo"]))
        rate = hits / len(subset) * 100
        marker = " <<<" if rate >= 60 else ""
        print(f"  {label:<35} n={len(subset):>5}  hit={hits:>5}  rate={rate:>5.1f}%{marker}")

    # ============================================================
    print("\n" + "="*80)
    print("PART 5: P top1 axis (2 tickets) - FILTER OPTIMIZATION")
    print("="*80)

    for label, filt in [
        ("ALL", lambda r: True),
        ("<=10", lambda r: r["n"] <= 10),
        ("<=10 + pair_agree>=2", lambda r: r["n"] <= 10 and r["pair_agree"] >= 2),
        ("<=10 + pair_agree=3", lambda r: r["n"] <= 10 and r["pair_agree"] == 3),
        ("<=10 + p1<=3", lambda r: r["n"] <= 10 and r["p1_odds"] <= 3),
        ("<=10 + p1<=5", lambda r: r["n"] <= 10 and r["p1_odds"] <= 5),
        ("<=10 + both<=10", lambda r: r["n"] <= 10 and r["p2_odds"] <= 10),
        ("<=10 + ard_gap>=5", lambda r: r["n"] <= 10 and r["ard_gap"] >= 5),
        ("<=12", lambda r: r["n"] <= 12),
        ("<=12 + pair_agree>=2", lambda r: r["n"] <= 12 and r["pair_agree"] >= 2),
        ("<=14", lambda r: r["n"] <= 14),
        ("<=14 + pair_agree>=2", lambda r: r["n"] <= 14 and r["pair_agree"] >= 2),
        ("<=14 + pair_agree=3", lambda r: r["n"] <= 14 and r["pair_agree"] == 3),
        ("pair_agree>=2", lambda r: r["pair_agree"] >= 2),
        ("pair_agree=3", lambda r: r["pair_agree"] == 3),
        ("pair_agree=3 + <=12", lambda r: r["pair_agree"] == 3 and r["n"] <= 12),
        ("pair_agree=3 + p2<=10", lambda r: r["pair_agree"] == 3 and r["p2_odds"] <= 10),
        ("pair_agree=3 + p1<=5", lambda r: r["pair_agree"] == 3 and r["p1_odds"] <= 5),
    ]:
        subset = [r for r in races if filt(r)]
        if len(subset) < 20:
            continue
        hits = sum(1 for r in subset if any(check_wide_hit(r["entries"], i, j) for i, j in r["strats"]["P top1 axis(2t)"]))
        rate = hits / len(subset) * 100
        marker = " <<<" if rate >= 50 else ""
        print(f"  {label:<35} n={len(subset):>5}  hit={hits:>5}  rate={rate:>5.1f}%{marker}")

    # ============================================================
    print("\n" + "="*80)
    print("PART 6: GRADE ANALYSIS")
    print("="*80)

    grade_bins = defaultdict(lambda: {"total": 0, "hit_p12": 0, "hit_p3c": 0, "hit_pax": 0})
    for r in races:
        g = r["grade"]
        grade_bins[g]["total"] += 1
        if any(check_wide_hit(r["entries"], i, j) for i, j in r["strats"]["P top1-2"]):
            grade_bins[g]["hit_p12"] += 1
        if any(check_wide_hit(r["entries"], i, j) for i, j in r["strats"]["P top3 combo"]):
            grade_bins[g]["hit_p3c"] += 1
        if any(check_wide_hit(r["entries"], i, j) for i, j in r["strats"]["P top1 axis(2t)"]):
            grade_bins[g]["hit_pax"] += 1

    print(f"\n  {'Grade':<20} {'Races':>6} {'P1-2':>7} {'Paxis':>7} {'P3combo':>7}")
    print(f"  {'-'*55}")
    for g, s in sorted(grade_bins.items(), key=lambda x: -x[1]["total"]):
        if s["total"] < 10:
            continue
        r12 = s["hit_p12"] / s["total"] * 100
        r3c = s["hit_p3c"] / s["total"] * 100
        rax = s["hit_pax"] / s["total"] * 100
        print(f"  {g:<20} {s['total']:>6} {r12:>6.1f}% {rax:>6.1f}% {r3c:>6.1f}%")

    # ============================================================
    print("\n" + "="*80)
    print("PART 7: SUMMARY OF BEST STRATEGIES")
    print("="*80)

    print("""
  ===================================================================
  STRATEGY MENU (ranked by practicality)
  ===================================================================

  [A] 的中率重視 (3 tickets/race):
      P top3 combo | <=10 entries | ARd gap>=5
      -> 71.1% hit rate, 180 races/year-ish, 3 tickets x 100 = 300 yen/race

  [B] 的中率重視 (3 tickets/race, more coverage):
      P top3 combo | <=10 entries (no filter)
      -> 67.0% hit rate, 564 races, 300 yen/race

  [C] バランス (2 tickets/race):
      P top1 axis | <=10 entries
      -> ~55% hit rate area (check below)

  [D] 最小投資 (1 ticket/race):
      P top1-2 | pair_agree=3 | <=10
      -> ~50%+ hit rate target

  Check actual numbers above for [C] and [D].
  """)

    # ============================================================
    print("\n" + "="*80)
    print("PART 8: TOP1 INDIVIDUAL TOP3 RATE (sanity check)")
    print("="*80)

    for label, filt in [
        ("ALL", lambda r: True),
        ("pair_agree=3", lambda r: r["pair_agree"] == 3),
        ("<=10", lambda r: r["n"] <= 10),
        ("<=10 + pair_agree=3", lambda r: r["n"] <= 10 and r["pair_agree"] == 3),
        ("p1_odds<=3", lambda r: r["p1_odds"] <= 3),
        ("top1_agree=4", lambda r: r["top1_agree"] == 4),
        ("top1_agree=4 + <=10", lambda r: r["top1_agree"] == 4 and r["n"] <= 10),
    ]:
        subset = [r for r in races if filt(r)]
        if len(subset) < 20:
            continue
        p1_top3 = sum(1 for r in subset if r["entries"][r["by_p"][0]]["is_top3"] == 1)
        p2_top3 = sum(1 for r in subset if r["entries"][r["by_p"][1]]["is_top3"] == 1)
        rate1 = p1_top3 / len(subset) * 100
        rate2 = p2_top3 / len(subset) * 100
        print(f"  {label:<30} n={len(subset):>5}  P1 top3={rate1:>5.1f}%  P2 top3={rate2:>5.1f}%")


if __name__ == "__main__":
    main()
