"""Bankroll simulation v7.3 — Intersection Filter + Simple Strategies

Presets:
  ev_strategy  — Intersection Filter (gap × EV × margin)
    intersection: rank_w=1, win_gap>=4, win_ev>=1.3, margin<=60
    relaxed:      rank_w=1, win_gap>=3, win_ev>=1.0, margin<=60
    ev_focus:     rank_w=1, win_gap>=1, win_ev>=1.3, margin<=60
  simple       — シンプル戦略 (rank_w=1 + 単条件)
    simple:       rank_w=1, win_gap>=4
    simple_ev2:   rank_w=1, win_ev>=2.0
    simple_wide:  rank_w=1, win_gap>=3

Win-only (Place ROI < 100% for all conditions).
Confirmed odds used for gap/EV recalculation.
"""
import json
import math
import shutil
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.odds_db import batch_get_pre_race_odds


# ── Config ──────────────────────────────────────────────
INITIAL_BANKROLL = 50_000

BUDGET_CONFIGS = [
    {"label": "1%",      "pct": 0.01, "min": 500},
    {"label": "2%",      "pct": 0.02, "min": 1_000},
    {"label": "3%",      "pct": 0.03, "min": 1_500},
    {"label": "5%",      "pct": 0.05, "min": 2_000},
    {"label": "flat100", "pct": 0,    "min": 0},
]

# Intersection Filter strategies (matching bet-engine.ts)
PRESET_STRATEGIES = {
    "ev_strategy": [
        {
            "mode": "intersection",
            "label": "Intersection (gap>=4 EV>=1.3 m<=60)",
            "max_rank_w": 1,
            "min_win_gap": 4,
            "min_win_ev": 1.3,
            "max_margin": 60,
            "max_win_per_race": 1,
        },
        {
            "mode": "relaxed",
            "label": "Relaxed (gap>=3 EV>=1.0 m<=60)",
            "max_rank_w": 1,
            "min_win_gap": 3,
            "min_win_ev": 1.0,
            "max_margin": 60,
            "max_win_per_race": 1,
        },
        {
            "mode": "ev_focus",
            "label": "EV Focus (gap>=1 EV>=1.3 m<=60)",
            "max_rank_w": 1,
            "min_win_gap": 1,
            "min_win_ev": 1.3,
            "max_margin": 60,
            "max_win_per_race": 1,
        },
    ],
    "simple": [
        {
            "mode": "simple",
            "label": "Simple (1位 gap>=4)",
            "max_rank_w": 1,
            "min_win_gap": 4,
            "min_win_ev": 0,
            "max_margin": 999,
            "max_win_per_race": 1,
        },
        {
            "mode": "simple_ev2",
            "label": "Simple EV2 (1位 EV>=2.0)",
            "max_rank_w": 1,
            "min_win_gap": 0,
            "min_win_ev": 2.0,
            "max_margin": 999,
            "max_win_per_race": 1,
        },
        {
            "mode": "simple_wide",
            "label": "Simple Wide (1位 gap>=3)",
            "max_rank_w": 1,
            "min_win_gap": 3,
            "min_win_ev": 0,
            "max_margin": 999,
            "max_win_per_race": 1,
        },
    ],
}


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


def prepare_race_entries(race, confirmed_odds_map):
    """backtest_cache race → entries with confirmed odds recalculated."""
    race_id = race["race_id"]
    race_confirmed = confirmed_odds_map.get(race_id, {})

    # Recalculate odds rank with confirmed odds
    odds_for_rank = []
    for e in race["entries"]:
        uma = e["umaban"]
        if uma in race_confirmed:
            odds_for_rank.append((uma, race_confirmed[uma]["odds"]))
        else:
            odds_for_rank.append((uma, e.get("odds", 9999)))
    odds_for_rank.sort(key=lambda x: x[1])
    rank_map = {uma: rank + 1 for rank, (uma, _) in enumerate(odds_for_rank)}

    entries = []
    for e in race["entries"]:
        uma = e["umaban"]
        old_odds = e.get("odds", 0) or 0
        new_odds = race_confirmed[uma]["odds"] if uma in race_confirmed else old_odds
        new_rank = rank_map.get(uma, 99)
        rank_w = e.get("rank_w", 99)

        # Win gap recalc
        win_gap = new_rank - rank_w

        # Win EV recalc: prob = old_ev / old_odds → new_ev = prob * new_odds
        old_win_ev = e.get("win_ev") or 0
        if old_odds > 0 and new_odds > 0:
            win_prob = old_win_ev / old_odds
            win_ev = win_prob * new_odds
        else:
            win_ev = old_win_ev

        entries.append({
            "umaban": uma,
            "odds": new_odds,
            "rank_w": rank_w,
            "win_gap": win_gap,
            "win_ev": win_ev,
            "predicted_margin": e.get("predicted_margin"),
        })
    return race_id, entries


def filter_bets(races_data, strategy):
    """Apply Intersection Filter to get bet candidates for a day."""
    bets = []
    for race_id, entries in races_data:
        race_bets = []
        for e in entries:
            if e["rank_w"] > strategy["max_rank_w"]:
                continue
            if e["win_gap"] < strategy["min_win_gap"]:
                continue
            if (e["win_ev"] or 0) < strategy["min_win_ev"]:
                continue
            margin = e["predicted_margin"]
            if (margin if margin is not None else 100) > strategy["max_margin"]:
                continue
            race_bets.append({
                "race_id": race_id,
                "umaban": e["umaban"],
                "win_ev": e["win_ev"] or 0,
            })

        # Max per race constraint (sort by win_ev desc)
        max_per = strategy["max_win_per_race"]
        if max_per > 0 and len(race_bets) > max_per:
            race_bets.sort(key=lambda x: x["win_ev"], reverse=True)
            race_bets = race_bets[:max_per]

        bets.extend(race_bets)
    return bets


def build_lookup(cache_races, confirmed_odds_map):
    """(race_id, umaban) → entry lookup with confirmed odds."""
    lookup = {}
    for race in cache_races:
        race_id = race["race_id"]
        race_confirmed = confirmed_odds_map.get(race_id, {})
        for e in race["entries"]:
            uma = e["umaban"]
            entry = dict(e)
            if uma in race_confirmed:
                entry["odds"] = race_confirmed[uma]["odds"]
            lookup[(race_id, uma)] = entry
    return lookup


def simulate_day_bets(bets, lookup):
    """Settle one day: returns (total_bet, total_return)"""
    total_bet = 0
    total_return = 0
    for b in bets:
        key = (b["race_id"], b["umaban"])
        entry = lookup.get(key)
        if not entry:
            continue
        w = b["win_amount"]
        total_bet += w
        if entry.get("is_win"):
            total_return += w * (entry["odds"] or 0)
    return total_bet, round(total_return)


def run_simulation(dates_races_prepared, lookup, strategy, budget_pct, min_budget):
    """Full compounding simulation."""
    bankroll = INITIAL_BANKROLL
    peak = bankroll
    max_dd = 0
    total_bet = 0
    total_return = 0
    daily_returns = []
    bet_days = 0
    total_bets = 0
    is_flat = budget_pct == 0  # flat100 mode

    # Streak tracking
    current_loss_streak = 0
    max_loss_streak = 0
    current_win_streak = 0
    max_win_streak = 0

    history = [{"date": None, "bankroll": bankroll}]

    for date, races_data in sorted(dates_races_prepared.items()):
        bets = filter_bets(races_data, strategy)
        if not bets:
            continue

        if is_flat:
            # Fixed ¥100 per bet
            for b in bets:
                b["win_amount"] = 100
        else:
            daily_budget = max(min_budget, int(bankroll * budget_pct / 100) * 100)
            if daily_budget > bankroll:
                daily_budget = int(bankroll / 100) * 100
            if daily_budget < 100:
                history.append({"date": date, "bankroll": round(bankroll)})
                continue
            per_bet = max(100, int(daily_budget / len(bets) / 100) * 100)
            for b in bets:
                b["win_amount"] = per_bet

        day_bet, day_return = simulate_day_bets(bets, lookup)

        if day_bet > 0:
            daily_pnl = day_return - day_bet
            bankroll += daily_pnl
            total_bet += day_bet
            total_return += day_return
            daily_returns.append(daily_pnl / day_bet)
            bet_days += 1
            total_bets += len(bets)

            if daily_pnl >= 0:
                current_win_streak += 1
                current_loss_streak = 0
                max_win_streak = max(max_win_streak, current_win_streak)
            else:
                current_loss_streak += 1
                current_win_streak = 0
                max_loss_streak = max(max_loss_streak, current_loss_streak)

        if bankroll > peak:
            peak = bankroll
        dd = (peak - bankroll) / peak if peak > 0 else 0
        max_dd = max(max_dd, dd)

        history.append({"date": date, "bankroll": round(bankroll)})

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

    win_days = sum(1 for r in daily_returns if r >= 0)
    lose_days = sum(1 for r in daily_returns if r < 0)
    roi_pct = (bankroll / INITIAL_BANKROLL - 1) * 100
    calmar = roi_pct / (max_dd * 100) if max_dd > 0 else 0

    return {
        "mode": strategy["mode"],
        "label": strategy["label"],
        "final_bankroll": round(bankroll),
        "roi_pct": round(roi_pct, 1),
        "total_bet": total_bet,
        "total_return": total_return,
        "flat_roi": round(total_return / total_bet * 100, 1) if total_bet > 0 else 0,
        "max_dd": round(max_dd * 100, 1),
        "sharpe": round(sharpe, 3),
        "calmar": round(calmar, 2),
        "bet_days": bet_days,
        "total_bets": total_bets,
        "win_days": win_days,
        "lose_days": lose_days,
        "max_loss_streak": max_loss_streak,
        "max_win_streak": max_win_streak,
        "history": history,
    }


def main():
    print("=" * 80)
    total_strategies = sum(len(s) for s in PRESET_STRATEGIES.values())
    print(f"  Bankroll Simulation v7.3 - Intersection Filter + Simple")
    print(f"  Initial: {INITIAL_BANKROLL:,} | Presets: {len(PRESET_STRATEGIES)} | Strategies: {total_strategies}")
    print("=" * 80)

    cache = load_cache()
    print(f"  Cache: {len(cache)} races")

    dates_races = group_by_date(cache)
    print(f"  Dates: {len(dates_races)} days ({min(dates_races)}~{max(dates_races)})")

    # Confirmed odds
    race_codes = [r["race_id"] for r in cache]
    print(f"  Loading confirmed odds ({len(race_codes)} races)...")
    confirmed_odds_map = batch_get_pre_race_odds(race_codes)
    hit = sum(1 for rc in race_codes if rc in confirmed_odds_map)
    print(f"  Confirmed odds: {hit}/{len(race_codes)} ({hit/len(race_codes)*100:.0f}%)")

    lookup = build_lookup(cache, confirmed_odds_map)

    # Pre-calculate race entries with confirmed odds for all dates
    dates_prepared = {}
    for date, races in dates_races.items():
        prepared = []
        for race in races:
            race_id, entries = prepare_race_entries(race, confirmed_odds_map)
            prepared.append((race_id, entries))
        dates_prepared[date] = prepared

    all_results = []

    for preset_name, strategies in PRESET_STRATEGIES.items():
        print(f"\n{'=' * 60}")
        print(f"  Preset: {preset_name}")
        print(f"{'=' * 60}")

        for strategy in strategies:
            print(f"\n{'─' * 60}")
            print(f"  Strategy: {strategy['label']}")
            print(f"{'─' * 60}")

            for bcfg in BUDGET_CONFIGS:
                r = run_simulation(
                    dates_prepared, lookup, strategy,
                    bcfg["pct"], bcfg["min"],
                )
                r["preset"] = preset_name
                r["budget_label"] = bcfg["label"]

                marker = " ***" if r["final_bankroll"] > INITIAL_BANKROLL else ""
                wl = f"{r['win_days']}/{r['lose_days']}"
                print(f"  {bcfg['label']:>7} | Final {r['final_bankroll']:>8,} | ROI {r['roi_pct']:>+7.1f}% | "
                      f"Flat {r['flat_roi']:>6.1f}% | DD {r['max_dd']:>5.1f}% | "
                      f"Calmar {r['calmar']:>6.2f} | {wl:>5} | Bets {r['total_bets']:>3}{marker}")

                all_results.append(r)

    # Model version
    meta_path = Path("C:/KEIBA-CICD/data3/ml/model_meta.json")
    model_version = "unknown"
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        model_version = meta.get("version", "unknown")

    # Save JSON
    output = {
        "model_version": model_version,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "initial_bankroll": INITIAL_BANKROLL,
        "budget_configs": [{"label": b["label"], "pct": b["pct"]} for b in BUDGET_CONFIGS],
        "strategies": [
            {"mode": s["mode"], "label": s["label"]}
            for strategies in PRESET_STRATEGIES.values()
            for s in strategies
        ],
        "presets": list(PRESET_STRATEGIES.keys()),
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
            "calmar": r["calmar"],
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

    archive_dir = Path(f"C:/KEIBA-CICD/data3/ml/versions/v{model_version}")
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / "bankroll_simulation.json"
    shutil.copy2(out_path, archive_path)
    print(f"  Archive: {archive_path}")
    print(f"  Model: v{model_version}")


if __name__ == "__main__":
    main()
