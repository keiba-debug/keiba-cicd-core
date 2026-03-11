"""
WIN5 Backtest Analysis: When does the winner fall within top N of rank_w?
Analyzes race-level features that predict winner's rank_w position.
"""
import json
import sys
from collections import defaultdict

def main():
    # Load backtest cache
    with open("C:/KEIBA-CICD/data3/ml/backtest_cache.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Total races in backtest cache: {len(data)}")

    # Process each race
    rows = []
    for race in data:
        race_id = race["race_id"]
        entries = race["entries"]
        entry_count = len(entries)

        # Find winner
        winner = None
        for e in entries:
            if e.get("finish_position") == 1:
                winner = e
                break
        if winner is None:
            continue

        # Sort by rank_w to get top entries
        sorted_by_rw = sorted(entries, key=lambda x: x.get("rank_w", 999))
        # Sort by rank_p
        sorted_by_rp = sorted(entries, key=lambda x: x.get("rank_p", 999))
        # Sort by ar_deviation descending (higher = better)
        sorted_by_ard = sorted(entries, key=lambda x: x.get("ar_deviation", 0), reverse=True)
        # Sort by pred_proba_p_raw descending
        sorted_by_pp = sorted(entries, key=lambda x: x.get("pred_proba_p_raw", 0), reverse=True)

        # Top1/Top2 pred_proba_p_raw
        top1_pp = sorted_by_pp[0]["pred_proba_p_raw"] if len(sorted_by_pp) > 0 else 0
        top2_pp = sorted_by_pp[1]["pred_proba_p_raw"] if len(sorted_by_pp) > 1 else 0
        pp_gap = top1_pp - top2_pp  # confidence gap

        # Top1/Top2 ar_deviation
        top1_ard = sorted_by_ard[0]["ar_deviation"] if len(sorted_by_ard) > 0 else 50
        top2_ard = sorted_by_ard[1]["ar_deviation"] if len(sorted_by_ard) > 1 else 50
        ard_gap = top1_ard - top2_ard

        # Winner's rank_w and rank_p
        winner_rank_w = winner.get("rank_w", 999)
        winner_rank_p = winner.get("rank_p", 999)
        winner_ard = winner.get("ar_deviation", 50)
        winner_odds = winner.get("odds", 99)

        # Grade info
        grade = race.get("grade", "")

        rows.append({
            "race_id": race_id,
            "entry_count": entry_count,
            "grade": grade,
            "top1_pp": top1_pp,
            "pp_gap": pp_gap,
            "top1_ard": top1_ard,
            "ard_gap": ard_gap,
            "winner_rank_w": winner_rank_w,
            "winner_rank_p": winner_rank_p,
            "winner_ard": winner_ard,
            "winner_odds": winner_odds,
        })

    print(f"Races with winner identified: {len(rows)}")
    print()

    # ===== Overall baseline =====
    print("=" * 80)
    print("OVERALL: Winner's rank_w distribution")
    print("=" * 80)
    total = len(rows)
    for n in [1, 2, 3, 4, 5, 6, 8, 10]:
        count = sum(1 for r in rows if r["winner_rank_w"] <= n)
        print(f"  Winner in top{n:>2} of rank_w: {count:>5} / {total} = {count/total*100:5.1f}%")

    print()
    print("  Winner rank_w distribution:")
    rank_dist = defaultdict(int)
    for r in rows:
        rw = r["winner_rank_w"]
        if rw <= 10:
            rank_dist[rw] += 1
        else:
            rank_dist[99] += 1
    for rw in range(1, 11):
        cnt = rank_dist.get(rw, 0)
        print(f"    rank_w={rw:>2}: {cnt:>5} ({cnt/total*100:5.1f}%)")
    cnt = rank_dist.get(99, 0)
    print(f"    rank_w>10: {cnt:>5} ({cnt/total*100:5.1f}%)")

    # ===== Analysis functions =====
    def analyze_bins(rows, feature_name, bins, labels):
        """Analyze top-N hit rates for different bins of a feature."""
        print()
        print("=" * 80)
        print(f"Feature: {feature_name}")
        print("=" * 80)
        header = f"{'Bin':<25} {'N':>5} {'Top1':>7} {'Top2':>7} {'Top3':>7} {'Top5':>7} {'Top8':>7} {'AvgRkW':>7}"
        print(header)
        print("-" * 80)

        for i, label in enumerate(labels):
            lo = bins[i]
            hi = bins[i + 1]
            subset = [r for r in rows if lo <= r[feature_name] < hi]
            n = len(subset)
            if n == 0:
                continue

            top1 = sum(1 for r in subset if r["winner_rank_w"] <= 1) / n * 100
            top2 = sum(1 for r in subset if r["winner_rank_w"] <= 2) / n * 100
            top3 = sum(1 for r in subset if r["winner_rank_w"] <= 3) / n * 100
            top5 = sum(1 for r in subset if r["winner_rank_w"] <= 5) / n * 100
            top8 = sum(1 for r in subset if r["winner_rank_w"] <= 8) / n * 100
            avg_rw = sum(r["winner_rank_w"] for r in subset) / n
            print(f"{label:<25} {n:>5} {top1:>6.1f}% {top2:>6.1f}% {top3:>6.1f}% {top5:>6.1f}% {top8:>6.1f}% {avg_rw:>7.1f}")

    # ----- 1. ARD Gap -----
    analyze_bins(rows, "ard_gap",
                 [-999, 0, 3, 5, 8, 10, 15, 999],
                 ["< 0", "0-3", "3-5", "5-8", "8-10", "10-15", ">= 15"])

    # ----- 2. Entry Count -----
    analyze_bins(rows, "entry_count",
                 [0, 8, 10, 12, 14, 16, 99],
                 ["<= 7", "8-9", "10-11", "12-13", "14-15", "16+"])

    # ----- 3. Top1 ARD (absolute strength) -----
    analyze_bins(rows, "top1_ard",
                 [0, 50, 55, 60, 65, 70, 999],
                 ["< 50", "50-55", "55-60", "60-65", "65-70", ">= 70"])

    # ----- 4. PP Gap (pred_proba_p_raw gap) -----
    analyze_bins(rows, "pp_gap",
                 [-999, 0.01, 0.03, 0.05, 0.08, 0.12, 999],
                 ["< 0.01", "0.01-0.03", "0.03-0.05", "0.05-0.08", "0.08-0.12", ">= 0.12"])

    # ----- 5. Top1 PP (absolute) -----
    analyze_bins(rows, "top1_pp",
                 [0, 0.15, 0.20, 0.25, 0.30, 0.40, 999],
                 ["< 0.15", "0.15-0.20", "0.20-0.25", "0.25-0.30", "0.30-0.40", ">= 0.40"])

    # ===== Combined rules analysis =====
    print()
    print("=" * 80)
    print("COMBINED RULES: ARD Gap x Entry Count")
    print("=" * 80)
    header = f"{'Rule':<40} {'N':>5} {'Top1':>7} {'Top2':>7} {'Top3':>7} {'Top5':>7}"
    print(header)
    print("-" * 80)

    rules = [
        ("ard_gap>=10 & entries<=12", lambda r: r["ard_gap"] >= 10 and r["entry_count"] <= 12),
        ("ard_gap>=10 & entries<=14", lambda r: r["ard_gap"] >= 10 and r["entry_count"] <= 14),
        ("ard_gap>=10 & entries<=16", lambda r: r["ard_gap"] >= 10 and r["entry_count"] <= 16),
        ("ard_gap>=8  & entries<=12", lambda r: r["ard_gap"] >= 8 and r["entry_count"] <= 12),
        ("ard_gap>=8  & entries<=14", lambda r: r["ard_gap"] >= 8 and r["entry_count"] <= 14),
        ("ard_gap>=5  & entries<=12", lambda r: r["ard_gap"] >= 5 and r["entry_count"] <= 12),
        ("ard_gap>=5  & entries<=14", lambda r: r["ard_gap"] >= 5 and r["entry_count"] <= 14),
        ("ard_gap>=5  & entries<=16", lambda r: r["ard_gap"] >= 5 and r["entry_count"] <= 16),
        ("ard_gap<3   & entries>=14",  lambda r: r["ard_gap"] < 3 and r["entry_count"] >= 14),
        ("ard_gap<3   & entries>=16",  lambda r: r["ard_gap"] < 3 and r["entry_count"] >= 16),
        ("ard_gap<5   & entries>=16",  lambda r: r["ard_gap"] < 5 and r["entry_count"] >= 16),
        ("top1_ard>=65 & ard_gap>=8",  lambda r: r["top1_ard"] >= 65 and r["ard_gap"] >= 8),
        ("top1_ard>=65 & ard_gap>=5",  lambda r: r["top1_ard"] >= 65 and r["ard_gap"] >= 5),
        ("top1_ard>=60 & ard_gap>=8",  lambda r: r["top1_ard"] >= 60 and r["ard_gap"] >= 8),
        ("pp_gap>=0.08 & ard_gap>=5",  lambda r: r["pp_gap"] >= 0.08 and r["ard_gap"] >= 5),
        ("pp_gap>=0.08 & ard_gap>=8",  lambda r: r["pp_gap"] >= 0.08 and r["ard_gap"] >= 8),
        ("pp_gap>=0.05 & ard_gap>=5 & ent<=14", lambda r: r["pp_gap"] >= 0.05 and r["ard_gap"] >= 5 and r["entry_count"] <= 14),
    ]

    for name, fn in rules:
        subset = [r for r in rows if fn(r)]
        n = len(subset)
        if n == 0:
            print(f"{name:<40} {0:>5}  (no data)")
            continue
        top1 = sum(1 for r in subset if r["winner_rank_w"] <= 1) / n * 100
        top2 = sum(1 for r in subset if r["winner_rank_w"] <= 2) / n * 100
        top3 = sum(1 for r in subset if r["winner_rank_w"] <= 3) / n * 100
        top5 = sum(1 for r in subset if r["winner_rank_w"] <= 5) / n * 100
        print(f"{name:<40} {n:>5} {top1:>6.1f}% {top2:>6.1f}% {top3:>6.1f}% {top5:>6.1f}%")

    # ===== Proposed pick strategy =====
    print()
    print("=" * 80)
    print("PROPOSED PICK STRATEGY (rule -> N picks)")
    print("=" * 80)

    def evaluate_strategy(rows, strategy_fn):
        """strategy_fn(row) -> n_picks. Returns hit rate."""
        hits = 0
        total = 0
        pick_counts = defaultdict(int)
        for r in rows:
            n_picks = strategy_fn(r)
            pick_counts[n_picks] += 1
            total += 1
            if r["winner_rank_w"] <= n_picks:
                hits += 1
        return hits, total, pick_counts

    strategies = {
        "Baseline: always 3 picks": lambda r: 3,
        "Baseline: always 5 picks": lambda r: 5,
        "S1: ard_gap>=10→2, >=5→3, else→5": lambda r: 2 if r["ard_gap"] >= 10 else (3 if r["ard_gap"] >= 5 else 5),
        "S2: ard_gap>=10→2, >=5→3, >=3→4, else→5": lambda r: 2 if r["ard_gap"] >= 10 else (3 if r["ard_gap"] >= 5 else (4 if r["ard_gap"] >= 3 else 5)),
        "S3: ard_gap>=8&ent<=12→2, ard>=5→3, else→5": lambda r: 2 if (r["ard_gap"] >= 8 and r["entry_count"] <= 12) else (3 if r["ard_gap"] >= 5 else 5),
        "S4: ard_gap>=10→1, >=5→2, >=3→3, else→5": lambda r: 1 if r["ard_gap"] >= 10 else (2 if r["ard_gap"] >= 5 else (3 if r["ard_gap"] >= 3 else 5)),
        "S5: pp_gap>=0.08→2, ard>=5→3, else→5": lambda r: 2 if r["pp_gap"] >= 0.08 else (3 if r["ard_gap"] >= 5 else 5),
    }

    print(f"{'Strategy':<50} {'Hits':>5} {'Total':>5} {'Hit%':>7} {'AvgPick':>8} {'Combos':>12}")
    print("-" * 95)

    for name, fn in strategies.items():
        hits, total, pick_counts = evaluate_strategy(rows, fn)
        avg_picks = sum(n * c for n, c in pick_counts.items()) / total
        # Estimate total combos for 5-race WIN5 (geometric mean approach)
        # Just show average picks per race
        print(f"{name:<50} {hits:>5} {total:>5} {hits/total*100:>6.1f}% {avg_picks:>7.1f}  dist={dict(sorted(pick_counts.items()))}")

    # ===== WIN5 simulation =====
    print()
    print("=" * 80)
    print("WIN5 SIMULATION: 5-race combination analysis")
    print("=" * 80)

    # Group races by date
    from collections import OrderedDict
    date_races = defaultdict(list)
    for r in rows:
        date = r["race_id"][:8]  # YYYYMMDD
        date_races[date].append(r)

    # WIN5 is typically last 5 races of the day on Sundays
    # We'll simulate with all groups of 5+ races per date
    print(f"\nDates with races: {len(date_races)}")
    print(f"Dates with >= 5 races: {sum(1 for d, rs in date_races.items() if len(rs) >= 5)}")

    # Simple analysis: for each strategy, compute expected combos and hit rate across 5-race sets
    # Take last 5 races per date as proxy
    win5_sets = []
    for date, races in sorted(date_races.items()):
        if len(races) >= 5:
            # Take last 5 races (highest race numbers)
            sorted_races = sorted(races, key=lambda r: r["race_id"])
            last5 = sorted_races[-5:]
            win5_sets.append((date, last5))

    print(f"WIN5 sets (last 5 races/date): {len(win5_sets)}")

    def simulate_win5(win5_sets, strategy_fn):
        total_sets = len(win5_sets)
        all_hit = 0
        total_combos_list = []
        for date, races in win5_sets:
            combo = 1
            all_correct = True
            for r in races:
                n_picks = strategy_fn(r)
                combo *= n_picks
                if r["winner_rank_w"] > n_picks:
                    all_correct = False
            if all_correct:
                all_hit += 1
            total_combos_list.append(combo)
        avg_combos = sum(total_combos_list) / len(total_combos_list) if total_combos_list else 0
        median_combos = sorted(total_combos_list)[len(total_combos_list)//2] if total_combos_list else 0
        return all_hit, total_sets, avg_combos, median_combos

    print(f"\n{'Strategy':<50} {'5/5Hit':>6} {'Sets':>5} {'Hit%':>7} {'AvgCombo':>9} {'MedCombo':>9} {'Cost@100':>10}")
    print("-" * 100)

    for name, fn in strategies.items():
        hits, total_sets, avg_combos, med_combos = simulate_win5(win5_sets, fn)
        cost = med_combos * 100
        print(f"{name:<50} {hits:>6} {total_sets:>5} {hits/total_sets*100 if total_sets else 0:>6.1f}% {avg_combos:>9.0f} {med_combos:>9} {cost:>9}円")

    # ===== Per-race hit rate by strategy =====
    print()
    print("=" * 80)
    print("PER-RACE HIT RATE by strategy (winner in top N_picks of rank_w)")
    print("=" * 80)
    for name, fn in strategies.items():
        hits = sum(1 for r in rows if r["winner_rank_w"] <= fn(r))
        print(f"  {name:<50} {hits}/{len(rows)} = {hits/len(rows)*100:.1f}%")


if __name__ == "__main__":
    main()
