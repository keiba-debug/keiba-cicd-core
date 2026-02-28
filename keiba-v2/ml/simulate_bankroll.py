"""Bankroll simulation with compounding (v5.35b)

Initial: 100K, daily budget = bankroll * X%, settle daily.
Compare allocation strategies: final balance, max DD, Sharpe, Calmar, max losing streak.
Output JSON for web visualization.

v5.35b: 確定オッズでGap/EV再計算（予測時オッズとのズレ修正）
"""
import json
import math
import sys
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ml.bet_engine import PRESETS, generate_recommendations
from core.odds_db import batch_get_pre_race_odds


# ── Config ──────────────────────────────────────────────
INITIAL_BANKROLL = 100_000
MIN_DAILY_BUDGET = 2_000

BUDGET_CONFIGS = [
    {"label": "2%",  "pct": 0.02, "min": 2_000},
    {"label": "3%",  "pct": 0.03, "min": 2_000},
    {"label": "5%",  "pct": 0.05, "min": 2_000},
    {"label": "7%",  "pct": 0.07, "min": 2_000},
    {"label": "10%", "pct": 0.10, "min": 2_000},
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


def cache_to_preds(races, confirmed_odds_map=None):
    """backtest_cache → bet_engine入力形式に変換。

    confirmed_odds_map が指定されていれば、確定オッズで以下を再計算:
      - odds_rank: 確定オッズ昇順ランク
      - vb_gap:    confirmed_odds_rank - rank_v
      - win_vb_gap: confirmed_odds_rank - rank_wv
      - win_ev:    (old_win_ev / old_odds) * confirmed_odds
      - odds:      確定オッズ値
    """
    preds = []
    for race in races:
        race_id = race["race_id"]
        race_confirmed = confirmed_odds_map.get(race_id, {}) if confirmed_odds_map else {}

        # 確定オッズでランキング再計算
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

            if uma in race_confirmed:
                new_odds = race_confirmed[uma]["odds"]
            else:
                new_odds = old_odds

            new_rank = rank_map.get(uma, 99)
            rank_v = e.get("rank_v", 99)
            rank_wv = e.get("rank_wv", 99)

            # Gap再計算
            new_vb_gap = new_rank - rank_v
            new_win_vb_gap = new_rank - rank_wv

            # EV再計算: prob = old_ev / old_odds → new_ev = prob * new_odds
            old_win_ev = e.get("win_ev") or 0
            if old_odds > 0 and new_odds > 0:
                win_prob = old_win_ev / old_odds
                new_win_ev = win_prob * new_odds
            else:
                new_win_ev = old_win_ev

            entries.append({
                "umaban": uma,
                "horse_name": e.get("horse_name", ""),
                "odds": new_odds,
                "odds_rank": new_rank,
                "vb_gap": new_vb_gap,
                "win_vb_gap": new_win_vb_gap,
                "rank_v": rank_v,
                "rank_wv": rank_wv,
                "place_odds_min": e.get("place_odds_min"),
                "pred_proba_v_raw": e.get("pred_proba_v_raw"),
                "predicted_margin": e.get("predicted_margin"),
                "win_ev": new_win_ev,
                "place_ev": e.get("place_ev"),
                "comment_memo_trouble_score": e.get("comment_memo_trouble_score", 0),
                "ar_deviation": e.get("ar_deviation"),
            })
        preds.append({
            "race_id": race_id,
            "track_type": race.get("track_type", ""),
            "grade": race.get("grade", ""),
            "grade_offset": race.get("grade_offset", 0),
            "entries": entries,
        })
    return preds


def build_lookup(cache_races, confirmed_odds_map=None):
    """(race_id, umaban) → entry のルックアップ。

    confirmed_odds_map があれば確定オッズで entry["odds"] を上書き（払戻計算用）。
    """
    lookup = {}
    for race in cache_races:
        race_id = race["race_id"]
        race_confirmed = confirmed_odds_map.get(race_id, {}) if confirmed_odds_map else {}
        for e in race["entries"]:
            uma = e["umaban"]
            entry = dict(e)  # copy
            if uma in race_confirmed:
                entry["odds"] = race_confirmed[uma]["odds"]
            lookup[(race_id, uma)] = entry
    return lookup


# ── Allocation strategies ───────────────────────────────
def apply_strategy(recs, daily_budget, mode):
    """Apply allocation strategy to bet_engine recommendations.

    Modes:
      passthrough - scale bet_engine's exact output to daily_budget (tilt preserved)
      win_only    - tilt + 100% win (v5.35 default)
      equal_win   - equal per-bet + 100% win
      s90_n50     - tilt + strong=90/10, normal=50/50
      s80_n50     - tilt + strong=80/20, normal=50/50
      equal_50    - equal per-bet + 50/50 split
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
            # v5.35: WinOnly → all to win
            b["win_amount"] = scaled
            b["place_amount"] = 0
        return bets

    # Determine weights
    if mode in ("equal_win", "equal_50"):
        weights = [1.0] * n
    else:
        # tilt: use orig_total as weight (preserves bet_engine's gap-based tilt)
        weights = [b["orig_total"] for b in bets]

    total_w = sum(weights)
    if total_w == 0:
        return []

    # Determine win/place ratio
    for b in bets:
        if mode == "win_only":
            b["win_pct"] = 1.0
        elif mode == "equal_win":
            b["win_pct"] = 1.0
        elif mode == "s90_n50":
            b["win_pct"] = 0.9 if b["strength"] == "strong" else 0.5
        elif mode == "s80_n50":
            b["win_pct"] = 0.8 if b["strength"] == "strong" else 0.5
        elif mode == "equal_50":
            b["win_pct"] = 0.5
        else:
            b["win_pct"] = 1.0

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
    """Settle one day: returns (total_bet, total_return, any_hit)"""
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


def run_simulation(dates_races, lookup, params, mode, label, budget_pct, min_budget,
                    confirmed_odds_map=None):
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

    history = [{"date": None, "bankroll": bankroll}]

    for date, races in sorted(dates_races.items()):
        daily_budget = max(min_budget, int(bankroll * budget_pct / 100) * 100)

        if daily_budget > bankroll:
            daily_budget = int(bankroll / 100) * 100

        if daily_budget < 200:
            history.append({"date": date, "bankroll": round(bankroll)})
            continue

        preds = cache_to_preds(races, confirmed_odds_map)
        recs = generate_recommendations(preds, params, budget=daily_budget)

        if not recs:
            history.append({"date": date, "bankroll": round(bankroll)})
            continue

        if mode == "exact":
            # Use bet_engine's amounts directly (no compounding)
            bets = [{"race_id": r.race_id, "umaban": r.umaban,
                      "win_amount": r.win_amount, "place_amount": r.place_amount}
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
                current_loss_streak = 0
                if current_win_streak > max_win_streak:
                    max_win_streak = current_win_streak
            else:
                current_loss_streak += 1
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

    # Calmar ratio (ROI / MaxDD)
    roi_pct = (bankroll / INITIAL_BANKROLL - 1) * 100
    calmar = roi_pct / (max_dd * 100) if max_dd > 0 else 0

    return {
        "label": label,
        "mode": mode,
        "budget_pct": budget_pct,
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
        "avg_daily_return": round(avg_r * 100, 2),
        "win_days": win_days,
        "lose_days": lose_days,
        "max_loss_streak": max_loss_streak,
        "max_win_streak": max_win_streak,
        "history": history,
    }


STRATEGIES = [
    ("exact",         "Exact (fixed amount)"),
    ("win_only",      "WinOnly + Tilt (default)"),
    ("passthrough",   "Passthrough + Tilt"),
    ("equal_win",     "WinOnly + Equal"),
    ("s90_n50",       "S90/N50 + Tilt"),
    ("s80_n50",       "S80/N50 + Tilt"),
    ("equal_50",      "Equal 50/50"),
]


def main():
    print("=" * 80)
    print(f"  Bankroll Simulation v5.35b (Initial: {INITIAL_BANKROLL:,})")
    print("  確定オッズでGap/EV再計算")
    print("=" * 80)

    cache = load_cache()
    print(f"  Cache: {len(cache)} races")

    dates_races = group_by_date(cache)
    print(f"  Dates: {len(dates_races)} days ({min(dates_races)}~{max(dates_races)})")

    # 確定オッズ取得
    race_codes = [r["race_id"] for r in cache]
    print(f"  Loading confirmed odds from mykeibadb ({len(race_codes)} races)...")
    confirmed_odds_map = batch_get_pre_race_odds(race_codes)
    hit = sum(1 for rc in race_codes if rc in confirmed_odds_map)
    print(f"  Confirmed odds: {hit}/{len(race_codes)} races ({hit/len(race_codes)*100:.0f}%)")

    lookup = build_lookup(cache, confirmed_odds_map)

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
                    confirmed_odds_map=confirmed_odds_map,
                )
                r["preset"] = preset_name
                r["budget_label"] = bcfg["label"]
                results.append(r)

            # Display
            print(f"\n  {'Strategy':<24} {'Final':>9} {'ROI':>7} {'FlatROI':>8} {'MaxDD':>6} {'Calmar':>7} {'Sharpe':>7} {'W/L':>7} {'MaxLS':>5}")
            print(f"  {'-'*24} {'-'*9} {'-'*7} {'-'*8} {'-'*6} {'-'*7} {'-'*7} {'-'*7} {'-'*5}")
            for r in results:
                marker = " ***" if r["final_bankroll"] > INITIAL_BANKROLL else ""
                wl = f"{r['win_days']}/{r['lose_days']}"
                print(f"  {r['label']:<24} {r['final_bankroll']:>8,} {r['roi_pct']:>+6.1f}% {r['flat_roi']:>7.1f}% {r['max_dd']:>5.1f}% {r['calmar']:>6.2f} {r['sharpe']:>7.3f} {wl:>7} {r['max_loss_streak']:>5}{marker}")

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


if __name__ == "__main__":
    main()
