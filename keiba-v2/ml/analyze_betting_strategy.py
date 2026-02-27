#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
購入戦略シミュレーション

連敗ストリーク分析 + 単複配分比較 + 自信度別配分効果検証

Usage:
    python -m ml.analyze_betting_strategy
    python -m ml.analyze_betting_strategy --preset standard
"""

import argparse
import json
import sys
import io
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Tuple

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
DATA_DIR = Path(r"C:\KEIBA-CICD\data3\races")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def load_race_results(date_dir: Path) -> dict:
    results = {}
    for rf in sorted(date_dir.glob("race_[0-9]*.json")):
        with open(rf, encoding="utf-8") as f:
            rd = json.load(f)
        race_id = rd["race_id"]
        entry_map = {}
        for e in rd.get("entries", []):
            entry_map[e["umaban"]] = {
                "finish_position": e.get("finish_position"),
                "odds": e.get("odds"),
            }
        results[race_id] = entry_map
    return results


def load_confirmed_place_odds(race_codes: list) -> dict:
    try:
        from core.odds_db import batch_get_place_odds
        raw = batch_get_place_odds(race_codes)
        result = {}
        for rc, horses in raw.items():
            result[rc] = {um: d["odds_low"] for um, d in horses.items() if d.get("odds_low")}
        return result
    except Exception as e:
        print(f"  [WARN] place odds failed: {e}")
        return {}


def collect_bet_timeline(
    start_month: str, end_month: str
) -> Tuple[Dict[str, List[dict]], Dict[str, dict]]:
    """全プランのベット時系列を収集。
    Returns:
        plan_bets: {preset_name: [bet_record, ...]}  時系列順
        summary: {preset_name: {params, ...}}
    """
    print("Phase 1: predictions.json収集...")
    pred_entries = []
    all_race_ids = []

    for pred_path in sorted(DATA_DIR.glob("**/predictions.json")):
        parts = pred_path.parts
        try:
            idx = list(parts).index("races")
            year, month, day = parts[idx+1], parts[idx+2], parts[idx+3]
            date_str = f"{year}-{month}-{day}"
            month_str = f"{year}-{month}"
        except (ValueError, IndexError):
            continue
        if month_str < start_month or month_str > end_month:
            continue

        with open(pred_path, encoding="utf-8") as f:
            pred_data = json.load(f)
        for race in pred_data.get("races", []):
            all_race_ids.append(race["race_id"])
        pred_entries.append((pred_path, date_str, month_str, pred_data))

    print(f"  {len(pred_entries)}日分, {len(all_race_ids)}レース")

    print("Phase 2: 確定複勝オッズ取得...")
    confirmed_place = load_confirmed_place_odds(all_race_ids)
    print(f"  {len(confirmed_place)}レース分取得")

    print("Phase 3: ベット時系列構築...")
    plan_bets = {"standard": [], "wide": [], "aggressive": []}
    plan_params = {}

    for pred_path, date_str, month_str, pred_data in pred_entries:
        date_dir = pred_path.parent
        results = load_race_results(date_dir)
        if not results:
            continue

        # predictions.jsonのentryからar_deviationをlookup用に構築
        entry_lookup = {}  # {(race_id, umaban): entry_dict}
        for race in pred_data.get("races", []):
            for entry in race.get("entries", []):
                entry_lookup[(race["race_id"], entry["umaban"])] = entry

        recs = pred_data.get("recommendations", {})
        for preset_name, preset_data in recs.items():
            if preset_name not in plan_bets:
                continue

            if preset_name not in plan_params and "params" in preset_data:
                plan_params[preset_name] = preset_data["params"]

            for bet in preset_data.get("bets", []):
                bet_race_id = bet["race_id"]
                umaban = bet["umaban"]
                race_results_map = results.get(bet_race_id, {})
                result = race_results_map.get(umaban)
                race_place_odds = confirmed_place.get(bet_race_id, {})
                pred_entry = entry_lookup.get((bet_race_id, umaban), {})

                if not result or result["finish_position"] is None:
                    continue

                pos = result["finish_position"]
                actual_odds = result.get("odds") or bet.get("odds", 0) or 0
                actual_place = race_place_odds.get(umaban, 0) or bet.get("place_odds_min", 0) or 0

                # ar_deviation: predictions.json entry > bet.predicted_margin fallback
                ar_deviation = pred_entry.get("ar_deviation") or bet.get("predicted_margin", 0) or 0

                plan_bets[preset_name].append({
                    "date": date_str,
                    "race_id": bet_race_id,
                    "umaban": umaban,
                    "horse": bet.get("horse_name", "?"),
                    "strength": bet.get("strength", "normal"),
                    "win_amount": bet.get("win_amount", 0),
                    "pos": pos,
                    "is_win": pos == 1,
                    "is_place": pos <= 3,
                    "win_odds": actual_odds,
                    "place_odds": actual_place,
                    "gap": bet.get("gap", 0),
                    "win_ev": bet.get("win_ev", 0),
                    "ar_d": ar_deviation,
                })

    return plan_bets, plan_params


def analyze_streaks(bets: List[dict], label: str = "単勝"):
    """連敗/連勝ストリーク分析。"""
    if not bets:
        return

    # 的中判定関数
    if label == "単勝":
        hit_fn = lambda b: b["is_win"]
    elif label == "複勝":
        hit_fn = lambda b: b["is_place"]
    else:  # 単複どちらか
        hit_fn = lambda b: b["is_win"] or b["is_place"]

    # ストリーク計算
    lose_streaks = []
    win_streaks = []
    current_lose = 0
    current_win = 0

    for b in bets:
        if hit_fn(b):
            current_win += 1
            if current_lose > 0:
                lose_streaks.append(current_lose)
                current_lose = 0
        else:
            current_lose += 1
            if current_win > 0:
                win_streaks.append(current_win)
                current_win = 0

    if current_lose > 0:
        lose_streaks.append(current_lose)
    if current_win > 0:
        win_streaks.append(current_win)

    max_lose = max(lose_streaks) if lose_streaks else 0
    avg_lose = sum(lose_streaks) / len(lose_streaks) if lose_streaks else 0
    max_win = max(win_streaks) if win_streaks else 0

    # 連敗分布
    lose_dist = defaultdict(int)
    for s in lose_streaks:
        if s <= 5:
            lose_dist["1-5"] += 1
        elif s <= 10:
            lose_dist["6-10"] += 1
        elif s <= 15:
            lose_dist["11-15"] += 1
        elif s <= 20:
            lose_dist["16-20"] += 1
        elif s <= 30:
            lose_dist["21-30"] += 1
        else:
            lose_dist["31+"] += 1

    total_hits = sum(1 for b in bets if hit_fn(b))
    hit_rate = total_hits / len(bets) * 100

    print(f"\n  [{label}] N={len(bets)}, 的中={total_hits} ({hit_rate:.1f}%)")
    print(f"    最大連敗: {max_lose}  平均連敗: {avg_lose:.1f}  最大連勝: {max_win}")
    print(f"    連敗分布: ", end="")
    for band in ["1-5", "6-10", "11-15", "16-20", "21-30", "31+"]:
        if lose_dist[band] > 0:
            print(f"{band}={lose_dist[band]}  ", end="")
    print()

    return {"max_lose": max_lose, "avg_lose": avg_lose, "hit_rate": hit_rate}


def simulate_allocation(bets: List[dict], win_pct: int, place_pct: int,
                        base_unit: int = 100, label: str = "") -> dict:
    """単複配分シミュレーション。

    Args:
        win_pct: 単勝に割り当てる割合 (0-100)
        place_pct: 複勝に割り当てる割合 (0-100)
        base_unit: 1ベットの基本金額
    """
    win_bet = int(base_unit * win_pct / 100)
    place_bet = int(base_unit * place_pct / 100)
    total_per_bet = win_bet + place_bet

    if total_per_bet == 0:
        return {}

    cumulative = 0
    max_balance = 0
    min_balance = 0
    balance_history = []

    total_wagered = 0
    total_returned = 0
    wins = 0
    places = 0

    for b in bets:
        wagered = total_per_bet
        returned = 0

        if win_bet > 0 and b["is_win"]:
            returned += int(b["win_odds"] * win_bet)
            wins += 1
        if place_bet > 0 and b["is_place"]:
            returned += int(b["place_odds"] * place_bet)
            places += 1

        total_wagered += wagered
        total_returned += returned
        cumulative += (returned - wagered)
        balance_history.append(cumulative)

        max_balance = max(max_balance, cumulative)
        min_balance = min(min_balance, cumulative)

    roi = total_returned / total_wagered * 100 if total_wagered > 0 else 0
    pnl = total_returned - total_wagered

    # 最大ドローダウン（ピークからの最大下落）
    peak = 0
    max_dd = 0
    for bal in balance_history:
        peak = max(peak, bal)
        dd = peak - bal
        max_dd = max(max_dd, dd)

    return {
        "label": label,
        "win_pct": win_pct,
        "place_pct": place_pct,
        "n": len(bets),
        "wagered": total_wagered,
        "returned": total_returned,
        "roi": roi,
        "pnl": pnl,
        "max_dd": max_dd,
        "min_balance": min_balance,
        "max_balance": max_balance,
        "wins": wins,
        "places": places,
    }


def simulate_strength_allocation(bets: List[dict],
                                 strong_unit: int, normal_unit: int,
                                 win_pct: int = 100, place_pct: int = 0,
                                 label: str = "") -> dict:
    """自信度別配分シミュレーション。"""
    win_frac = win_pct / 100
    place_frac = place_pct / 100

    cumulative = 0
    peak = 0
    max_dd = 0
    total_wagered = 0
    total_returned = 0

    strong_n = 0
    strong_win = 0
    strong_ret = 0
    strong_wag = 0
    normal_n = 0
    normal_win = 0
    normal_ret = 0
    normal_wag = 0

    for b in bets:
        unit = strong_unit if b["strength"] == "strong" else normal_unit
        win_bet = int(unit * win_frac)
        place_bet = int(unit * place_frac)
        wagered = win_bet + place_bet
        returned = 0

        if win_bet > 0 and b["is_win"]:
            returned += int(b["win_odds"] * win_bet)
        if place_bet > 0 and b["is_place"]:
            returned += int(b["place_odds"] * place_bet)

        total_wagered += wagered
        total_returned += returned
        cumulative += (returned - wagered)
        peak = max(peak, cumulative)
        max_dd = max(max_dd, peak - cumulative)

        if b["strength"] == "strong":
            strong_n += 1
            strong_wag += wagered
            strong_ret += returned
            if b["is_win"]:
                strong_win += 1
        else:
            normal_n += 1
            normal_wag += wagered
            normal_ret += returned
            if b["is_win"]:
                normal_win += 1

    roi = total_returned / total_wagered * 100 if total_wagered > 0 else 0
    pnl = total_returned - total_wagered

    return {
        "label": label,
        "strong_unit": strong_unit,
        "normal_unit": normal_unit,
        "n": len(bets),
        "wagered": total_wagered,
        "returned": total_returned,
        "roi": roi,
        "pnl": pnl,
        "max_dd": max_dd,
        "strong_n": strong_n,
        "strong_roi": strong_ret / strong_wag * 100 if strong_wag > 0 else 0,
        "normal_n": normal_n,
        "normal_roi": normal_ret / normal_wag * 100 if normal_wag > 0 else 0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2025-01")
    parser.add_argument("--end", default="2026-02")
    parser.add_argument("--preset", default=None, help="single preset to analyze")
    args = parser.parse_args()

    plan_bets, plan_params = collect_bet_timeline(args.start, args.end)

    presets = [args.preset] if args.preset else ["standard", "wide", "aggressive"]

    for preset in presets:
        bets = plan_bets.get(preset, [])
        if not bets:
            continue

        print("\n" + "=" * 72)
        print(f"  {preset.upper()} プラン分析 (N={len(bets)})")
        print("=" * 72)

        # ============================================================
        # 1. 連敗ストリーク分析
        # ============================================================
        print("\n" + "-" * 72)
        print("  1. 連敗ストリーク分析")
        print("-" * 72)

        s_win = analyze_streaks(bets, "単勝")
        s_place = analyze_streaks(bets, "複勝")
        s_either = analyze_streaks(bets, "単複どちらか")

        # 日別連敗（同日に複数ベットがある場合、日単位で見る）
        daily_results = defaultdict(lambda: {"bets": 0, "wins": 0, "places": 0})
        for b in bets:
            d = daily_results[b["date"]]
            d["bets"] += 1
            if b["is_win"]:
                d["wins"] += 1
            if b["is_place"]:
                d["places"] += 1

        # 日単位の連続ノーヒット（単勝）
        day_lose_streak = 0
        max_day_lose = 0
        day_lose_streaks = []
        for date in sorted(daily_results.keys()):
            d = daily_results[date]
            if d["wins"] == 0:
                day_lose_streak += 1
            else:
                if day_lose_streak > 0:
                    day_lose_streaks.append(day_lose_streak)
                day_lose_streak = 0
        if day_lose_streak > 0:
            day_lose_streaks.append(day_lose_streak)
        max_day_lose = max(day_lose_streaks) if day_lose_streaks else 0

        print(f"\n  [日単位] 開催日数={len(daily_results)}")
        print(f"    単勝ノーヒット最大連続: {max_day_lose}日")

        # 複勝日単位
        day_place_lose = 0
        max_day_place_lose = 0
        day_place_streaks = []
        for date in sorted(daily_results.keys()):
            d = daily_results[date]
            if d["places"] == 0:
                day_place_lose += 1
            else:
                if day_place_lose > 0:
                    day_place_streaks.append(day_place_lose)
                day_place_lose = 0
        if day_place_lose > 0:
            day_place_streaks.append(day_place_lose)
        max_day_place_lose = max(day_place_streaks) if day_place_streaks else 0
        print(f"    複勝ノーヒット最大連続: {max_day_place_lose}日")

        # ============================================================
        # 2. 単複配分シミュレーション
        # ============================================================
        print("\n" + "-" * 72)
        print("  2. 単複配分シミュレーション (1ベット=Y100)")
        print("-" * 72)

        allocations = [
            (100, 0, "単勝のみ"),
            (0, 100, "複勝のみ"),
            (70, 30, "単7:複3"),
            (50, 50, "単5:複5"),
            (30, 70, "単3:複7"),
            (100, 100, "単複各100"),
        ]

        print(f"\n  {'配分':<12} {'投資':>10} {'回収':>10} {'ROI':>7} {'収支':>10} {'MaxDD':>8} {'底値':>8}")
        print("  " + "-" * 68)

        for wp, pp, lbl in allocations:
            r = simulate_allocation(bets, wp, pp, base_unit=100, label=lbl)
            print(f"  {lbl:<12} {r['wagered']:>9,} {r['returned']:>9,} "
                  f"{r['roi']:>6.1f}% {r['pnl']:>+9,} {r['max_dd']:>7,} {r['min_balance']:>+7,}")

        # ============================================================
        # 3. 自信度別配分シミュレーション
        # ============================================================
        print("\n" + "-" * 72)
        print("  3. 自信度別配分 (strong/normal)")
        print("-" * 72)

        # まずstrong/normalの基本成績
        strong_bets = [b for b in bets if b["strength"] == "strong"]
        normal_bets = [b for b in bets if b["strength"] != "strong"]
        print(f"\n  strong: {len(strong_bets)}件, normal: {len(normal_bets)}件")

        if strong_bets:
            sw = sum(1 for b in strong_bets if b["is_win"])
            sp = sum(1 for b in strong_bets if b["is_place"])
            sw_ret = sum(int(b["win_odds"] * 100) for b in strong_bets if b["is_win"])
            sp_ret = sum(int(b["place_odds"] * 100) for b in strong_bets if b["is_place"])
            sn = len(strong_bets)
            print(f"    strong: 勝率{sw/sn*100:.1f}% ROI(単){sw_ret/(sn*100)*100:.1f}%  "
                  f"複勝率{sp/sn*100:.1f}% ROI(複){sp_ret/(sn*100)*100:.1f}%")
        if normal_bets:
            nw = sum(1 for b in normal_bets if b["is_win"])
            np_ = sum(1 for b in normal_bets if b["is_place"])
            nw_ret = sum(int(b["win_odds"] * 100) for b in normal_bets if b["is_win"])
            np_ret = sum(int(b["place_odds"] * 100) for b in normal_bets if b["is_place"])
            nn = len(normal_bets)
            print(f"    normal: 勝率{nw/nn*100:.1f}% ROI(単){nw_ret/(nn*100)*100:.1f}%  "
                  f"複勝率{np_/nn*100:.1f}% ROI(複){np_ret/(nn*100)*100:.1f}%")

        # 配分パターン
        strength_patterns = [
            (100, 100, "均等Y100"),
            (200, 100, "strong倍額"),
            (100, 200, "normal倍額"),
            (300, 100, "strong3倍"),
            (50, 100, "strong半額"),
        ]

        # 単勝のみ
        print(f"\n  [単勝のみ]")
        print(f"  {'配分':<16} {'投資':>9} {'回収':>9} {'ROI':>7} {'収支':>10} {'MaxDD':>8}")
        print("  " + "-" * 60)
        for su, nu, lbl in strength_patterns:
            r = simulate_strength_allocation(bets, su, nu, win_pct=100, place_pct=0, label=lbl)
            print(f"  {lbl:<16} {r['wagered']:>8,} {r['returned']:>8,} "
                  f"{r['roi']:>6.1f}% {r['pnl']:>+9,} {r['max_dd']:>7,}")

        # 単複各ベース
        print(f"\n  [単複各Y100ベース (strong/normalで金額変動)]")
        print(f"  {'配分':<16} {'投資':>9} {'回収':>9} {'ROI':>7} {'収支':>10} {'MaxDD':>8}")
        print("  " + "-" * 60)

        strength_patterns_wp = [
            (100, 100, 50, 50, "均等 単5:複5"),
            (200, 100, 50, 50, "strong倍 5:5"),
            (100, 100, 70, 30, "均等 単7:複3"),
            (200, 100, 70, 30, "strong倍 7:3"),
            (100, 100, 100, 100, "均等 各100"),
            (200, 100, 100, 100, "strong倍 各100"),
        ]

        for su, nu, wp, pp, lbl in strength_patterns_wp:
            # Custom simulation for strength + win/place split
            cumulative = 0
            peak = 0
            max_dd = 0
            total_wag = 0
            total_ret = 0

            for b in bets:
                unit = su if b["strength"] == "strong" else nu
                w_bet = int(unit * wp / 100)
                p_bet = int(unit * pp / 100)
                wagered = w_bet + p_bet
                returned = 0
                if w_bet > 0 and b["is_win"]:
                    returned += int(b["win_odds"] * w_bet)
                if p_bet > 0 and b["is_place"]:
                    returned += int(b["place_odds"] * p_bet)
                total_wag += wagered
                total_ret += returned
                cumulative += (returned - wagered)
                peak = max(peak, cumulative)
                max_dd = max(max_dd, peak - cumulative)

            roi = total_ret / total_wag * 100 if total_wag > 0 else 0
            pnl = total_ret - total_wag
            print(f"  {lbl:<16} {total_wag:>8,} {total_ret:>8,} "
                  f"{roi:>6.1f}% {pnl:>+9,} {max_dd:>7,}")

        # ============================================================
        # 4. 資金推移サマリー（単複各100の場合）
        # ============================================================
        print("\n" + "-" * 72)
        print("  4. 月別資金推移 (単複各Y100)")
        print("-" * 72)

        monthly = defaultdict(lambda: {"wag": 0, "ret": 0, "n": 0})
        for b in bets:
            m = b["date"][:7]
            w_ret = int(b["win_odds"] * 100) if b["is_win"] else 0
            p_ret = int(b["place_odds"] * 100) if b["is_place"] else 0
            monthly[m]["wag"] += 200
            monthly[m]["ret"] += w_ret + p_ret
            monthly[m]["n"] += 1

        cumul = 0
        print(f"\n  {'Month':<8} {'N':>4} {'投資':>8} {'回収':>8} {'月収支':>8} {'累計':>9}")
        for m in sorted(monthly.keys()):
            d = monthly[m]
            pnl = d["ret"] - d["wag"]
            cumul += pnl
            roi = d["ret"] / d["wag"] * 100 if d["wag"] > 0 else 0
            print(f"  {m:<8} {d['n']:>4} {d['wag']:>7,} {d['ret']:>7,} {pnl:>+7,} {cumul:>+8,}")

    # ================================================================
    # 5. 複利シミュレーション（残高比例ベット）
    # ================================================================
    print("\n" + "=" * 72)
    print("  5. 複利シミュレーション（残高の一定割合をベット）")
    print("=" * 72)

    for preset in presets:
        bets = plan_bets.get(preset, [])
        if not bets:
            continue

        print(f"\n  [{preset.upper()}] 初期資金=Y100,000")

        configs = [
            # (bet_pct, win_split, place_split, label)
            (1.0, 100, 0,  "1%単勝のみ"),
            (1.0, 0,  100, "1%複勝のみ"),
            (1.0, 50,  50, "1%単5:複5"),
            (1.0, 30,  70, "1%単3:複7"),
            (2.0, 50,  50, "2%単5:複5"),
            (2.0, 30,  70, "2%単3:複7"),
            (3.0, 30,  70, "3%単3:複7"),
            (1.0, 100, 100,"1%単複各1%"),
            (2.0, 100, 100,"2%単複各2%"),
        ]

        print(f"  {'戦略':<16} {'最終残高':>10} {'成長率':>7} {'MaxDD%':>7} {'底値':>10} {'破産':>4}")
        print("  " + "-" * 60)

        for bet_pct, w_split, p_split, lbl in configs:
            balance = 100000
            peak_bal = balance
            max_dd_pct = 0
            min_balance = balance

            for b in bets:
                if w_split == 100 and p_split == 100:
                    # 単複各bet_pct
                    w_bet = max(100, int(balance * bet_pct / 100 / 100) * 100)
                    p_bet = max(100, int(balance * bet_pct / 100 / 100) * 100)
                else:
                    total_bet = max(100, int(balance * bet_pct / 100 / 100) * 100)
                    w_bet = int(total_bet * w_split / 100)
                    p_bet = int(total_bet * p_split / 100)

                wagered = w_bet + p_bet
                returned = 0
                if w_bet > 0 and b["is_win"]:
                    returned += int(b["win_odds"] * w_bet)
                if p_bet > 0 and b["is_place"]:
                    returned += int(b["place_odds"] * p_bet)

                balance = balance - wagered + returned
                peak_bal = max(peak_bal, balance)
                dd_pct = (peak_bal - balance) / peak_bal * 100 if peak_bal > 0 else 0
                max_dd_pct = max(max_dd_pct, dd_pct)
                min_balance = min(min_balance, balance)

            growth = (balance / 100000 - 1) * 100
            bust = "YES" if min_balance <= 0 else ""
            print(f"  {lbl:<16} {balance:>9,} {growth:>+6.1f}% {max_dd_pct:>6.1f}% {min_balance:>9,} {bust:>4}")

    # ================================================================
    # 6. 自信度×単複クロス配分
    # ================================================================
    print("\n" + "=" * 72)
    print("  6. 自信度×単複クロス配分")
    print("    strong=穴狙い→単勝重視, normal=堅実→複勝重視")
    print("=" * 72)

    for preset in presets:
        bets = plan_bets.get(preset, [])
        if not bets:
            continue

        print(f"\n  [{preset.upper()}]")

        cross_configs = [
            # (s_win%, s_place%, n_win%, n_place%, label)
            (50, 50, 50, 50, "均等 5:5 / 5:5"),
            (70, 30, 30, 70, "S単7:複3 / N単3:複7"),
            (80, 20, 20, 80, "S単8:複2 / N単2:複8"),
            (100, 0, 0, 100, "S単勝のみ / N複勝のみ"),
            (70, 30, 50, 50, "S単7:複3 / N単5:複5"),
            (50, 50, 30, 70, "S単5:複5 / N単3:複7"),
            (100, 100, 100, 100, "全員 単複各100"),
            (100, 100, 50, 50,  "S各100 / N単5:複5"),
        ]

        print(f"  {'配分':<24} {'投資':>9} {'回収':>9} {'ROI':>7} {'収支':>10} {'MaxDD':>7}")
        print("  " + "-" * 68)

        for s_wp, s_pp, n_wp, n_pp, lbl in cross_configs:
            cumulative = 0
            peak = 0
            max_dd = 0
            total_wag = 0
            total_ret = 0

            for b in bets:
                if b["strength"] == "strong":
                    w_bet = int(100 * s_wp / 100)
                    p_bet = int(100 * s_pp / 100)
                else:
                    w_bet = int(100 * n_wp / 100)
                    p_bet = int(100 * n_pp / 100)

                wagered = w_bet + p_bet
                returned = 0
                if w_bet > 0 and b["is_win"]:
                    returned += int(b["win_odds"] * w_bet)
                if p_bet > 0 and b["is_place"]:
                    returned += int(b["place_odds"] * p_bet)

                total_wag += wagered
                total_ret += returned
                cumulative += (returned - wagered)
                peak = max(peak, cumulative)
                max_dd = max(max_dd, peak - cumulative)

            roi = total_ret / total_wag * 100 if total_wag > 0 else 0
            pnl = total_ret - total_wag
            print(f"  {lbl:<24} {total_wag:>8,} {total_ret:>8,} "
                  f"{roi:>6.1f}% {pnl:>+9,} {max_dd:>6,}")

    # ================================================================
    # 7. 複利 × 自信度クロス配分（ベスト戦略）
    # ================================================================
    print("\n" + "=" * 72)
    print("  7. 複利 × クロス配分 (初期Y100,000)")
    print("=" * 72)

    for preset in presets:
        bets = plan_bets.get(preset, [])
        if not bets:
            continue

        print(f"\n  [{preset.upper()}]")

        compound_cross = [
            # (pct, s_w, s_p, n_w, n_p, label)
            (2.0, 50, 50, 50, 50, "2% 均等5:5"),
            (2.0, 70, 30, 30, 70, "2% S単7複3/N単3複7"),
            (2.0, 80, 20, 20, 80, "2% S単8複2/N単2複8"),
            (2.0, 100, 0, 0, 100, "2% S単のみ/N複のみ"),
            (3.0, 50, 50, 50, 50, "3% 均等5:5"),
            (3.0, 70, 30, 30, 70, "3% S単7複3/N単3複7"),
            (3.0, 80, 20, 20, 80, "3% S単8複2/N単2複8"),
            (1.5, 70, 30, 30, 70, "1.5% S単7複3/N単3複7"),
        ]

        print(f"  {'戦略':<26} {'最終残高':>10} {'成長':>7} {'MaxDD%':>7} {'底値':>10}")
        print("  " + "-" * 62)

        for pct, s_w, s_p, n_w, n_p, lbl in compound_cross:
            balance = 100000
            peak_bal = balance
            max_dd_pct = 0
            min_bal = balance

            for b in bets:
                total_bet = max(100, int(balance * pct / 100 / 100) * 100)

                if b["strength"] == "strong":
                    w_bet = int(total_bet * s_w / 100)
                    p_bet = int(total_bet * s_p / 100)
                else:
                    w_bet = int(total_bet * n_w / 100)
                    p_bet = int(total_bet * n_p / 100)

                wagered = w_bet + p_bet
                returned = 0
                if w_bet > 0 and b["is_win"]:
                    returned += int(b["win_odds"] * w_bet)
                if p_bet > 0 and b["is_place"]:
                    returned += int(b["place_odds"] * p_bet)

                balance = balance - wagered + returned
                peak_bal = max(peak_bal, balance)
                dd = (peak_bal - balance) / peak_bal * 100 if peak_bal > 0 else 0
                max_dd_pct = max(max_dd_pct, dd)
                min_bal = min(min_bal, balance)

            growth = (balance / 100000 - 1) * 100
            print(f"  {lbl:<26} {balance:>9,} {growth:>+6.1f}% {max_dd_pct:>6.1f}% {min_bal:>9,}")

    # ================================================================
    # 8. tier相対strength判定の検証
    # ================================================================
    print("\n" + "=" * 72)
    print("  8. tier相対strength判定 vs 現行 (gap>=7)")
    print("    現行: strong = gap >= 7 (固定)")
    print("    提案: strong = gap >= tier_gap + 2 (ARd帯別)")
    print("       ARd>=65: gap>=5, ARd>=55: gap>=6, ARd<55: gap>=7")
    print("=" * 72)

    ARD_TIERS = [(65, 3), (55, 4), (45, 5)]  # bet_engine.py PRESETS と同じ

    def get_tier_gap(ar_d: float) -> int:
        """ARd段階フィルターの該当tier gapを返す"""
        for tier_ard, tier_gap in ARD_TIERS:
            if ar_d >= tier_ard:
                return tier_gap
        return 5  # default (ARd<45)

    def classify_strength_tier(b: dict) -> str:
        """tier相対でstrong判定"""
        tier_gap = get_tier_gap(b["ar_d"])
        return "strong" if b["gap"] >= tier_gap + 2 else "normal"

    def classify_strength_current(b: dict) -> str:
        """現行判定 (gap>=7)"""
        return "strong" if b["gap"] >= 7 else "normal"

    for preset in presets:
        bets = plan_bets.get(preset, [])
        if not bets:
            continue

        print(f"\n  [{preset.upper()}] N={len(bets)}")

        # 両方の判定を付与
        for b in bets:
            b["str_current"] = classify_strength_current(b)
            b["str_tier"] = classify_strength_tier(b)

        # 分類の比較
        same = sum(1 for b in bets if b["str_current"] == b["str_tier"])
        upgrade = [b for b in bets if b["str_current"] == "normal" and b["str_tier"] == "strong"]
        downgrade = [b for b in bets if b["str_current"] == "strong" and b["str_tier"] == "normal"]

        print(f"  一致: {same}/{len(bets)} ({same/len(bets)*100:.1f}%)")
        print(f"  normal->strong昇格: {len(upgrade)}件, strong->normal降格: {len(downgrade)}件")

        # 昇格馬の詳細
        if upgrade:
            up_wins = sum(1 for b in upgrade if b["is_win"])
            up_places = sum(1 for b in upgrade if b["is_place"])
            up_w_ret = sum(int(b["win_odds"] * 100) for b in upgrade if b["is_win"])
            up_p_ret = sum(int(b["place_odds"] * 100) for b in upgrade if b["is_place"])
            un = len(upgrade)
            print(f"\n  [昇格馬 (normal->strong)] N={un}")
            print(f"    勝率: {up_wins/un*100:.1f}%  単ROI: {up_w_ret/(un*100)*100:.1f}%")
            print(f"    複勝率: {up_places/un*100:.1f}%  複ROI: {up_p_ret/(un*100)*100:.1f}%")
            # ARd/Gap分布
            ard_bins = {"65+": 0, "55-64": 0, "45-54": 0, "<45": 0}
            for b in upgrade:
                if b["ar_d"] >= 65:
                    ard_bins["65+"] += 1
                elif b["ar_d"] >= 55:
                    ard_bins["55-64"] += 1
                elif b["ar_d"] >= 45:
                    ard_bins["45-54"] += 1
                else:
                    ard_bins["<45"] += 1
            print(f"    ARd分布: ", end="")
            for k, v in ard_bins.items():
                if v > 0:
                    print(f"{k}={v} ", end="")
            print()

        # 各判定での成績比較
        for method_name, key in [("現行(gap>=7)", "str_current"), ("tier相対", "str_tier")]:
            strong = [b for b in bets if b[key] == "strong"]
            normal = [b for b in bets if b[key] != "strong"]

            s_n = len(strong)
            n_n = len(normal)
            if s_n == 0 or n_n == 0:
                continue

            s_wins = sum(1 for b in strong if b["is_win"])
            s_places = sum(1 for b in strong if b["is_place"])
            s_w_ret = sum(int(b["win_odds"] * 100) for b in strong if b["is_win"])
            s_p_ret = sum(int(b["place_odds"] * 100) for b in strong if b["is_place"])

            n_wins = sum(1 for b in normal if b["is_win"])
            n_places = sum(1 for b in normal if b["is_place"])
            n_w_ret = sum(int(b["win_odds"] * 100) for b in normal if b["is_win"])
            n_p_ret = sum(int(b["place_odds"] * 100) for b in normal if b["is_place"])

            print(f"\n  === {method_name} ===")
            print(f"  strong({s_n}件): 勝率{s_wins/s_n*100:.1f}% 単ROI {s_w_ret/(s_n*100)*100:.1f}%"
                  f"  複勝率{s_places/s_n*100:.1f}% 複ROI {s_p_ret/(s_n*100)*100:.1f}%")
            print(f"  normal({n_n}件): 勝率{n_wins/n_n*100:.1f}% 単ROI {n_w_ret/(n_n*100)*100:.1f}%"
                  f"  複勝率{n_places/n_n*100:.1f}% 複ROI {n_p_ret/(n_n*100)*100:.1f}%")

        # クロス配分シミュレーション比較
        print(f"\n  --- クロス配分効果比較 (S単7複3/N単3複7, Y100/bet) ---")
        print(f"  {'判定方法':<16} {'投資':>9} {'回収':>9} {'ROI':>7} {'収支':>10} {'MaxDD':>7}")
        print("  " + "-" * 60)

        for method_name, key in [("現行(gap>=7)", "str_current"), ("tier相対", "str_tier"),
                                 ("ベースライン(5:5)", None)]:
            cumulative = 0
            peak = 0
            max_dd = 0
            total_wag = 0
            total_ret = 0

            for b in bets:
                if key is None:
                    # baseline: 均等配分
                    w_bet, p_bet = 50, 50
                elif b[key] == "strong":
                    w_bet, p_bet = 70, 30
                else:
                    w_bet, p_bet = 30, 70

                wagered = w_bet + p_bet
                returned = 0
                if w_bet > 0 and b["is_win"]:
                    returned += int(b["win_odds"] * w_bet)
                if p_bet > 0 and b["is_place"]:
                    returned += int(b["place_odds"] * p_bet)

                total_wag += wagered
                total_ret += returned
                cumulative += (returned - wagered)
                peak = max(peak, cumulative)
                max_dd = max(max_dd, peak - cumulative)

            roi = total_ret / total_wag * 100 if total_wag > 0 else 0
            pnl = total_ret - total_wag
            print(f"  {method_name:<16} {total_wag:>8,} {total_ret:>8,} "
                  f"{roi:>6.1f}% {pnl:>+9,} {max_dd:>6,}")

        # 複利×クロス比較
        print(f"\n  --- 複利×クロス比較 (2% S単7複3/N単3複7, 初期Y100,000) ---")
        print(f"  {'判定方法':<16} {'最終残高':>10} {'成長':>7} {'MaxDD%':>7} {'底値':>10}")
        print("  " + "-" * 52)

        for method_name, key in [("現行(gap>=7)", "str_current"), ("tier相対", "str_tier"),
                                 ("ベースライン(5:5)", None)]:
            balance = 100000
            peak_bal = balance
            max_dd_pct = 0
            min_bal = balance

            for b in bets:
                total_bet = max(100, int(balance * 2.0 / 100 / 100) * 100)

                if key is None:
                    w_bet = int(total_bet * 50 / 100)
                    p_bet = int(total_bet * 50 / 100)
                elif b[key] == "strong":
                    w_bet = int(total_bet * 70 / 100)
                    p_bet = int(total_bet * 30 / 100)
                else:
                    w_bet = int(total_bet * 30 / 100)
                    p_bet = int(total_bet * 70 / 100)

                wagered = w_bet + p_bet
                returned = 0
                if w_bet > 0 and b["is_win"]:
                    returned += int(b["win_odds"] * w_bet)
                if p_bet > 0 and b["is_place"]:
                    returned += int(b["place_odds"] * p_bet)

                balance = balance - wagered + returned
                peak_bal = max(peak_bal, balance)
                dd = (peak_bal - balance) / peak_bal * 100 if peak_bal > 0 else 0
                max_dd_pct = max(max_dd_pct, dd)
                min_bal = min(min_bal, balance)

            growth = (balance / 100000 - 1) * 100
            print(f"  {method_name:<16} {balance:>9,} {growth:>+6.1f}% {max_dd_pct:>6.1f}% {min_bal:>9,}")

    print("\n" + "=" * 72)
    print("  *** 注意: 確定最終オッズ使用 ***")
    print("=" * 72)


if __name__ == "__main__":
    main()
