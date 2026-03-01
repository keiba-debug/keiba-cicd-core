"""配分戦略の比較分析: 傾斜 vs 均等 × クロス vs 均等単複

backtest_cacheを使って、配分戦略によるROI差を分析。
bet_engineで馬を選定後、金額配分を変えてROIを比較する。
"""
import json
import sys
from pathlib import Path
from copy import deepcopy

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ml.bet_engine import PRESETS, generate_recommendations


def load_cache():
    cache_path = Path("C:/KEIBA-CICD/data3/ml/backtest_cache.json")
    with open(cache_path, encoding="utf-8") as f:
        return json.load(f)


def cache_to_predictions(cache_races):
    """backtest_cache -> generate_recommendations用List[dict]"""
    preds = []
    for race in cache_races:
        entries = []
        for e in race["entries"]:
            entries.append({
                "umaban": e["umaban"],
                "horse_name": e.get("horse_name", ""),
                "odds": e.get("odds", 0),
                "odds_rank": e.get("odds_rank", 99),
                "vb_gap": e.get("vb_gap", 0),
                "win_vb_gap": e.get("win_vb_gap", e.get("vb_gap", 0)),
                "rank_p": e.get("rank_p", 99),
                "rank_w": e.get("rank_w", 99),
                "place_odds_min": e.get("place_odds_min"),
                "pred_proba_p_raw": e.get("pred_proba_p_raw"),
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


def calc_roi(recs, cache_lookup):
    """ROI計算"""
    total_bet = 0
    total_return = 0
    win_bet = 0
    win_return = 0
    place_bet = 0
    place_return = 0
    wins = 0
    places = 0

    for r in recs:
        key = (r["race_id"], r["umaban"])
        entry = cache_lookup.get(key)
        if not entry:
            continue

        w = r["win_amount"]
        p = r["place_amount"]

        if w > 0:
            win_bet += w
            total_bet += w
            if entry.get("is_win"):
                payout = w * (entry["odds"] or 0)
                win_return += payout
                total_return += payout
                wins += 1

        if p > 0:
            place_bet += p
            total_bet += p
            if entry.get("is_top3"):
                po = entry.get("place_odds_min") or 0
                payout = p * po
                place_return += payout
                total_return += payout
                places += 1

    return {
        "total_bet": total_bet,
        "total_return": round(total_return),
        "total_roi": round(total_return / total_bet * 100, 1) if total_bet > 0 else 0,
        "win_bet": win_bet,
        "win_roi": round(win_return / win_bet * 100, 1) if win_bet > 0 else 0,
        "place_bet": place_bet,
        "place_roi": round(place_return / place_bet * 100, 1) if place_bet > 0 else 0,
        "num_bets": len(recs),
        "wins": wins,
        "places": places,
    }


def apply_allocation(base_recs, budget, mode="current"):
    """配分戦略を適用してrec dictリストを返す

    modes:
      current     = 現行 (units傾斜 + cross配分)
      equal_cross = 均等総額 + cross配分 (S/N比率維持)
      tilt_equal  = units傾斜 + 50/50 split
      equal_equal = 均等総額 + 50/50 split
      win_only    = units傾斜 + 単勝100%
      place_only  = units傾斜 + 複勝100%
      heavy_tilt  = より傾斜(1:2:4) + cross配分
    """
    recs = []
    for r in base_recs:
        recs.append({
            "race_id": r.race_id,
            "umaban": r.umaban,
            "strength": r.strength,
            "gap": r.gap,
            "odds": r.odds,
            # 元のbet_engine出力(cross_alloc後)
            "orig_win": r.win_amount,
            "orig_place": r.place_amount,
            "orig_total": r.win_amount + r.place_amount,
            "win_amount": 0,
            "place_amount": 0,
        })

    if not recs:
        return recs

    # bet_engine出力の合計
    orig_total_all = sum(r["orig_total"] for r in recs)
    if orig_total_all == 0:
        return recs

    # 各ベットの「重み」を設定
    for r in recs:
        if mode in ("equal_cross", "equal_equal"):
            r["weight"] = 1.0
        elif mode == "heavy_tilt":
            # orig_totalから推定units: 300=3unit, 200=1-2unit
            if r["orig_total"] >= 280:
                r["weight"] = 4.0  # 3 units -> 4x weight
            elif r["orig_total"] >= 180:
                r["weight"] = 2.0  # 2 units -> 2x weight
            else:
                r["weight"] = 1.0
        else:
            # current, tilt_equal, win_only, place_only: 元の金額比率を維持
            r["weight"] = r["orig_total"]

    total_weight = sum(r["weight"] for r in recs)

    # 予算配分 (weight按分) - 丸め誤差を最小化するため1000倍スケール
    scale_budget = budget * 10  # 丸め影響を排除 (300K effective)
    for r in recs:
        per_bet = max(1000, round(scale_budget * r["weight"] / total_weight / 100) * 100)

        # 単複比率
        if mode in ("tilt_equal", "equal_equal"):
            win_pct = 0.5
        elif mode == "win_only":
            win_pct = 1.0
        elif mode == "place_only":
            win_pct = 0.0
        elif mode == "cross_strong":
            # strong=80/20, normal=20/80 (より極端なcross)
            win_pct = 0.8 if r["strength"] == "strong" else 0.2
        else:
            # current, equal_cross, heavy_tilt: 元のcross比率を維持
            if r["orig_total"] > 0:
                win_pct = r["orig_win"] / r["orig_total"]
            else:
                win_pct = 0.5

        r["win_amount"] = max(100, round(per_bet * win_pct / 100) * 100) if win_pct > 0 else 0
        r["place_amount"] = max(100, per_bet - r["win_amount"]) if win_pct < 1.0 else 0

        if win_pct >= 1.0:
            r["win_amount"] = per_bet
            r["place_amount"] = 0
        elif win_pct <= 0.0:
            r["win_amount"] = 0
            r["place_amount"] = per_bet

    return recs


def main():
    print("=" * 70)
    print("  Allocation Strategy Comparison")
    print("=" * 70)

    cache = load_cache()
    print(f"  Cache: {len(cache)} races")

    preds = cache_to_predictions(cache)

    cache_lookup = {}
    for race in cache:
        for e in race["entries"]:
            cache_lookup[(race["race_id"], e["umaban"])] = e

    budget = 30000

    strategies = [
        ("current",      "A) Tilt+Cross (current)"),
        ("equal_cross",  "B) Equal+Cross"),
        ("tilt_equal",   "C) Tilt+50/50"),
        ("equal_equal",  "D) Equal+50/50"),
        ("win_only",     "E) Tilt+WinOnly"),
        ("place_only",   "F) Tilt+PlaceOnly"),
        ("heavy_tilt",   "G) HeavyTilt+Cross"),
        ("cross_strong", "H) Tilt+Cross80/20"),
    ]

    for preset_name in ["standard", "wide", "aggressive"]:
        params = PRESETS[preset_name]
        print(f"\n{'=' * 60}")
        print(f"  Preset: {preset_name}")
        print(f"{'=' * 60}")

        # bet_engineで馬を選定 (cross_alloc含む)
        base_recs = generate_recommendations(preds, params, budget=budget)

        if not base_recs:
            print("  No bets")
            continue

        # ベット詳細
        totals = [r.win_amount + r.place_amount for r in base_recs]
        strengths = [r.strength for r in base_recs]
        n_strong = strengths.count("strong")
        n_normal = strengths.count("normal")
        n_3unit = sum(1 for t in totals if t >= 280)
        n_12unit = sum(1 for t in totals if t < 280)
        print(f"  Bets: {len(base_recs)} (strong={n_strong}, normal={n_normal})")
        print(f"  Units: 3-unit={n_3unit} ({n_3unit*100//len(base_recs)}%), 1-2unit={n_12unit} ({n_12unit*100//len(base_recs)}%)")

        results = []
        for mode, label in strategies:
            recs = apply_allocation(base_recs, budget, mode=mode)
            r = calc_roi(recs, cache_lookup)
            r["label"] = label

            total_win_amt = sum(x["win_amount"] for x in recs)
            total_place_amt = sum(x["place_amount"] for x in recs)
            r["win_pct"] = round(total_win_amt / (total_win_amt + total_place_amt) * 100) if (total_win_amt + total_place_amt) > 0 else 0

            results.append(r)

        print(f"\n  {'Strategy':<26} {'Bets':>4} {'W%':>4} {'Total ROI':>10} {'Win ROI':>10} {'PlcROI':>10} {'Bet':>9} {'Return':>9}")
        print(f"  {'-'*26} {'-'*4} {'-'*4} {'-'*10} {'-'*10} {'-'*10} {'-'*9} {'-'*9}")
        for r in results:
            marker = " ***" if r["total_roi"] > 100 else ""
            print(f"  {r['label']:<26} {r['num_bets']:>4} {r['win_pct']:>3}% {r['total_roi']:>9.1f}% {r['win_roi']:>9.1f}% {r['place_roi']:>9.1f}% {r['total_bet']:>9,} {r['total_return']:>9,}{marker}")

        # 効果分離
        a_roi = results[0]["total_roi"]
        b_roi = results[1]["total_roi"]
        c_roi = results[2]["total_roi"]
        d_roi = results[3]["total_roi"]
        e_roi = results[4]["total_roi"]
        f_roi = results[5]["total_roi"]

        print(f"\n  Effect decomposition:")
        print(f"    Cross alloc effect  (A vs C): {a_roi - c_roi:+.1f}pt  (S/N split vs 50/50)")
        print(f"    Tilt alloc effect   (A vs B): {a_roi - b_roi:+.1f}pt  (units-weight vs equal)")
        print(f"    Win vs Place        (E vs F): {e_roi - f_roi:+.1f}pt  (win-only vs place-only)")
        print(f"    Heavy tilt uplift   (G vs A): {results[6]['total_roi'] - a_roi:+.1f}pt  (1:2:4 vs 1:1:1.5)")


if __name__ == "__main__":
    main()
