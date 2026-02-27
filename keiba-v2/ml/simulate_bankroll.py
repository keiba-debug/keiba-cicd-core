"""Bankroll simulation with compounding

Initial: 100K, daily budget = bankroll * X%, settle daily.
Compare allocation strategies: final balance, max DD, Sharpe, max losing streak.
Output JSON for web visualization.
"""
import json
import math
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ml.bet_engine import PRESETS, generate_recommendations


# ── Config ──────────────────────────────────────────────
INITIAL_BANKROLL = 100_000
DAILY_BUDGET_PCT = 0.15
MIN_DAILY_BUDGET = 2_000

BUDGET_CONFIGS = [
    {"label": "15%", "pct": 0.15, "min": 2_000},
    {"label": "10%", "pct": 0.10, "min": 2_000},
    {"label": "5%",  "pct": 0.05, "min": 2_000},
    {"label": "20%", "pct": 0.20, "min": 2_000},
]


def load_cache():
    path = Path("C:/KEIBA-CICD/data3/ml/backtest_cache.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def group_by_date(cache_races):
    by_date = defaultdict(list)
    for race in cache_races:
        date = race["race_id"][:8]
        by_date[date].append(race)
    return dict(sorted(by_date.items()))


def cache_to_preds(races):
    preds = []
    for race in races:
        entries = []
        for e in race["entries"]:
            entries.append({
                "umaban": e["umaban"],
                "horse_name": e.get("horse_name", ""),
                "odds": e.get("odds", 0),
                "odds_rank": e.get("odds_rank", 99),
                "vb_gap": e.get("vb_gap", 0),
                "win_vb_gap": e.get("win_vb_gap", e.get("vb_gap", 0)),
                "rank_v": e.get("rank_v", 99),
                "rank_wv": e.get("rank_wv", 99),
                "place_odds_min": e.get("place_odds_min"),
                "pred_proba_v_raw": e.get("pred_proba_v_raw"),
                "predicted_margin": e.get("predicted_margin"),
                "win_ev": e.get("win_ev"),
                "place_ev": e.get("place_ev"),
                "comment_memo_trouble_score": e.get("comment_memo_trouble_score", 0),
                "ar_deviation": e.get("ar_deviation"),
            })
        preds.append({
            "race_id": race["race_id"],
            "track_type": race.get("track_type", ""),
            "grade": race.get("grade", ""),
            "grade_offset": race.get("grade_offset", 0),
            "entries": entries,
        })
    return preds


def build_lookup(cache_races):
    lookup = {}
    for race in cache_races:
        for e in race["entries"]:
            lookup[(race["race_id"], e["umaban"])] = e
    return lookup


# ── Allocation strategies ───────────────────────────────
def apply_strategy(recs, daily_budget, mode):
    """Apply allocation strategy to bet_engine recommendations.

    Modes:
      passthrough  - scale bet_engine's exact output to daily_budget (tilt + cross ratio preserved)
      equal_cross  - equal per-bet with bet_engine's cross ratio
      win80        - tilt + strong=80/20, normal=50/50
      cross_strong - tilt + strong=80/20, normal=20/80
      win_only     - tilt + 100% win
      equal_50     - equal per-bet + 50/50 split
    """
    if not recs:
        return []

    bets = []
    for r in recs:
        bets.append({
            "race_id": r.race_id,
            "umaban": r.umaban,
            "strength": r.strength,
            "orig_win": r.win_amount,
            "orig_place": r.place_amount,
            "orig_total": r.win_amount + r.place_amount,
        })

    n = len(bets)
    if n == 0:
        return []

    orig_total_all = sum(b["orig_total"] for b in bets)
    if orig_total_all == 0:
        return []

    if mode == "passthrough":
        # Scale bet_engine output proportionally to daily_budget
        scale = daily_budget / orig_total_all
        for b in bets:
            scaled = max(200, round(b["orig_total"] * scale / 100) * 100)
            if b["orig_total"] > 0:
                win_ratio = b["orig_win"] / b["orig_total"]
            else:
                win_ratio = 0.5
            if win_ratio >= 1.0:
                b["win_amount"] = scaled
                b["place_amount"] = 0
            elif win_ratio <= 0.0:
                b["win_amount"] = 0
                b["place_amount"] = scaled
            else:
                b["win_amount"] = max(100, round(scaled * win_ratio / 100) * 100)
                b["place_amount"] = max(100, scaled - b["win_amount"])
        return bets

    # Determine weights
    if mode in ("equal_cross", "equal_50"):
        weights = [1.0] * n
    else:
        # tilt: use orig_total as weight (preserves bet_engine's gap-based tilt)
        weights = [b["orig_total"] for b in bets]

    total_w = sum(weights)
    if total_w == 0:
        return []

    # Determine win/place ratio
    for b in bets:
        if mode in ("passthrough", "equal_cross"):
            # preserve bet_engine cross ratio
            if b["orig_total"] > 0:
                b["win_pct"] = b["orig_win"] / b["orig_total"]
            else:
                b["win_pct"] = 0.5
        elif mode == "win80":
            b["win_pct"] = 0.8 if b["strength"] == "strong" else 0.5
        elif mode == "cross_strong":
            b["win_pct"] = 0.8 if b["strength"] == "strong" else 0.2
        elif mode == "win_only":
            b["win_pct"] = 1.0
        elif mode == "equal_50":
            b["win_pct"] = 0.5
        else:
            b["win_pct"] = 0.5

    # Allocate amounts
    for i, b in enumerate(bets):
        per_bet = max(200, round(daily_budget * weights[i] / total_w / 100) * 100)
        wp = b["win_pct"]

        if wp >= 1.0:
            b["win_amount"] = per_bet
            b["place_amount"] = 0
        elif wp <= 0.0:
            b["win_amount"] = 0
            b["place_amount"] = per_bet
        else:
            b["win_amount"] = max(100, round(per_bet * wp / 100) * 100)
            b["place_amount"] = max(100, per_bet - b["win_amount"])

    return bets


def simulate_day(bets, lookup):
    """Settle one day: returns (total_bet, total_return, n_hits, n_miss)"""
    total_bet = 0
    total_return = 0
    any_hit = False

    for b in bets:
        key = (b["race_id"], b["umaban"])
        entry = lookup.get(key)
        if not entry:
            continue

        w = b["win_amount"]
        p = b["place_amount"]
        hit = False

        if w > 0:
            total_bet += w
            if entry.get("is_win"):
                total_return += w * (entry["odds"] or 0)
                hit = True

        if p > 0:
            total_bet += p
            if entry.get("is_top3"):
                po = entry.get("place_odds_min") or 0
                total_return += p * po
                hit = True

        if hit:
            any_hit = True

    return total_bet, round(total_return), any_hit


def run_simulation(dates_races, lookup, params, mode, label, budget_pct, min_budget):
    """Full compounding simulation over all dates."""
    bankroll = INITIAL_BANKROLL
    peak = bankroll
    max_dd = 0
    total_bet = 0
    total_return = 0
    daily_returns = []
    bet_days = 0
    total_bets = 0

    # Streak tracking
    current_loss_streak = 0
    max_loss_streak = 0
    current_win_streak = 0
    max_win_streak = 0
    daily_loss_streaks = []  # all loss streaks

    history = [{"date": None, "bankroll": bankroll}]

    for date, races in sorted(dates_races.items()):
        daily_budget = max(min_budget, int(bankroll * budget_pct / 100) * 100)

        if daily_budget > bankroll:
            daily_budget = int(bankroll / 100) * 100

        if daily_budget < 200:
            history.append({"date": date, "bankroll": round(bankroll)})
            continue

        preds = cache_to_preds(races)
        recs = generate_recommendations(preds, params, budget=daily_budget)

        if not recs:
            history.append({"date": date, "bankroll": round(bankroll)})
            continue

        if mode == "exact":
            # Use bet_engine's Kelly-based amounts directly
            bets = [{"race_id": r.race_id, "umaban": r.umaban,
                      "win_amount": r.win_amount, "place_amount": r.place_amount}
                    for r in recs]
        elif mode == "exact_winonly":
            # Use bet_engine's amounts but redirect all to win
            bets = [{"race_id": r.race_id, "umaban": r.umaban,
                      "win_amount": r.win_amount + r.place_amount, "place_amount": 0}
                    for r in recs]
        else:
            bets = apply_strategy(recs, daily_budget, mode)

        if not bets:
            history.append({"date": date, "bankroll": round(bankroll)})
            continue

        day_bet, day_return, any_hit = simulate_day(bets, lookup)

        if day_bet > 0:
            daily_pnl = day_return - day_bet
            bankroll = bankroll + daily_pnl
            total_bet += day_bet
            total_return += day_return
            daily_returns.append(daily_pnl / day_bet)
            bet_days += 1
            total_bets += len(bets)

            # Streak
            if daily_pnl >= 0:
                current_win_streak += 1
                if current_loss_streak > 0:
                    daily_loss_streaks.append(current_loss_streak)
                current_loss_streak = 0
                if current_win_streak > max_win_streak:
                    max_win_streak = current_win_streak
            else:
                current_loss_streak += 1
                if current_win_streak > 0:
                    pass
                current_win_streak = 0
                if current_loss_streak > max_loss_streak:
                    max_loss_streak = current_loss_streak

        # Drawdown tracking
        if bankroll > peak:
            peak = bankroll
        dd = (peak - bankroll) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd

        history.append({"date": date, "bankroll": round(bankroll)})

    # Final loss streak
    if current_loss_streak > 0:
        daily_loss_streaks.append(current_loss_streak)

    # Sharpe-like ratio
    if daily_returns:
        avg_r = sum(daily_returns) / len(daily_returns)
        if len(daily_returns) > 1:
            var = sum((r - avg_r) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
            std_r = math.sqrt(var)
        else:
            std_r = 0
        sharpe = avg_r / std_r if std_r > 0 else 0
    else:
        avg_r = 0
        sharpe = 0

    # Win/loss day counts
    win_days = sum(1 for r in daily_returns if r >= 0)
    lose_days = sum(1 for r in daily_returns if r < 0)

    return {
        "label": label,
        "mode": mode,
        "budget_pct": budget_pct,
        "final_bankroll": round(bankroll),
        "roi_pct": round((bankroll / INITIAL_BANKROLL - 1) * 100, 1),
        "total_bet": total_bet,
        "total_return": total_return,
        "flat_roi": round(total_return / total_bet * 100, 1) if total_bet > 0 else 0,
        "max_dd": round(max_dd * 100, 1),
        "sharpe": round(sharpe, 3),
        "bet_days": bet_days,
        "total_bets": total_bets,
        "avg_daily_return": round(avg_r * 100, 2),
        "win_days": win_days,
        "lose_days": lose_days,
        "max_loss_streak": max_loss_streak,
        "max_win_streak": max_win_streak,
        "history": history,
    }


STRATEGIES = [
    ("exact",         "Exact (Kelly fraction)"),
    ("exact_winonly", "Exact + WinOnly"),
    ("passthrough",   "Full budget (tilt+cross)"),
    ("win80",         "Full budget + Win80/50"),
    ("win_only",      "Full budget + WinOnly"),
    ("equal_50",      "Full budget + Equal 50/50"),
]


def main():
    print("=" * 80)
    print(f"  Bankroll Simulation (Initial: {INITIAL_BANKROLL:,})")
    print("=" * 80)

    cache = load_cache()
    print(f"  Cache: {len(cache)} races")

    dates_races = group_by_date(cache)
    print(f"  Dates: {len(dates_races)} days ({min(dates_races)}~{max(dates_races)})")

    lookup = build_lookup(cache)

    all_results = []

    for preset_name in ["standard", "aggressive"]:
        params = PRESETS[preset_name]

        for bcfg in BUDGET_CONFIGS:
            print(f"\n{'=' * 80}")
            print(f"  Preset: {preset_name} | Budget: {bcfg['label']}")
            print(f"{'=' * 80}")

            results = []
            for mode, label in STRATEGIES:
                r = run_simulation(
                    dates_races, lookup, params, mode,
                    f"{label}",
                    bcfg["pct"], bcfg["min"],
                )
                r["preset"] = preset_name
                r["budget_label"] = bcfg["label"]
                results.append(r)

            # Display
            print(f"\n  {'Strategy':<28} {'Final':>9} {'ROI':>7} {'FlatROI':>8} {'MaxDD':>6} {'Sharpe':>7} {'W/L':>7} {'MaxLS':>5} {'MaxWS':>5}")
            print(f"  {'-'*28} {'-'*9} {'-'*7} {'-'*8} {'-'*6} {'-'*7} {'-'*7} {'-'*5} {'-'*5}")
            for r in results:
                marker = " ***" if r["final_bankroll"] > INITIAL_BANKROLL else ""
                print(f"  {r['label']:<28} {r['final_bankroll']:>8,} {r['roi_pct']:>+6.1f}% {r['flat_roi']:>7.1f}% {r['max_dd']:>5.1f}% {r['sharpe']:>7.3f} {r['win_days']:>3}/{r['lose_days']:<3} {r['max_loss_streak']:>5} {r['max_win_streak']:>5}{marker}")

            all_results.extend(results)

    # Save JSON for web visualization
    output = {
        "initial_bankroll": INITIAL_BANKROLL,
        "budget_configs": [{"label": b["label"], "pct": b["pct"]} for b in BUDGET_CONFIGS],
        "strategies": [{"mode": m, "label": l} for m, l in STRATEGIES],
        "presets": ["standard", "aggressive"],
        "results": [],
    }

    for r in all_results:
        output["results"].append({
            "preset": r["preset"],
            "budget_label": r["budget_label"],
            "mode": r["mode"],
            "label": r["label"],
            "final_bankroll": r["final_bankroll"],
            "roi_pct": r["roi_pct"],
            "flat_roi": r["flat_roi"],
            "max_dd": r["max_dd"],
            "sharpe": r["sharpe"],
            "bet_days": r["bet_days"],
            "total_bets": r["total_bets"],
            "win_days": r["win_days"],
            "lose_days": r["lose_days"],
            "max_loss_streak": r["max_loss_streak"],
            "max_win_streak": r["max_win_streak"],
            "history": r["history"],
        })

    out_path = Path("C:/KEIBA-CICD/data3/ml/bankroll_simulation.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n  Saved: {out_path} ({out_path.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
