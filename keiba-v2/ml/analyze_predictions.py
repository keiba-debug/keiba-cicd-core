#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
predictions.json 集計スクリプト（確定払い戻しベース）

predictions.json + race_*.json + mykeibadb確定複勝オッズ を突合し、
ValueBet馬・購入プランの実成績を集計する。

Usage:
    python -m ml.analyze_predictions
    python -m ml.analyze_predictions --start 2025-06 --end 2025-12
"""

import argparse
import json
import sys
import io
from collections import defaultdict
from pathlib import Path

# Windows cp932対策
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

DATA_DIR = Path(r"C:\KEIBA-CICD\data3\races")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def load_race_results(date_dir: Path) -> dict:
    """日付ディレクトリからレース結果を読み込む。
    Returns: {race_id: {umaban: {finish_position, odds}}}
    """
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
    """mykeibadbから確定複勝オッズをバッチ取得。
    Returns: {race_code: {umaban: odds_low}}
    """
    try:
        from core.odds_db import batch_get_place_odds
        raw = batch_get_place_odds(race_codes)
        result = {}
        for rc, horses in raw.items():
            result[rc] = {um: d["odds_low"] for um, d in horses.items() if d.get("odds_low")}
        return result
    except Exception as e:
        print(f"  [WARN] 複勝DB取得失敗: {e}")
        return {}


def fmt_yen(amount: int) -> str:
    """金額表示"""
    return f"Y{amount:,}"


def analyze_predictions(start_month: str = "2025-01", end_month: str = "2026-02"):
    """全predictions.jsonを集計する。"""

    # --- 集計用変数 ---
    vb_stats = {
        "total": 0, "win": 0, "place": 0,
        "wagered": 0, "returned_win": 0, "returned_place": 0,
    }
    non_vb_stats = {"total": 0, "win": 0, "place": 0}

    plan_stats = {}
    for preset in ["standard", "wide", "aggressive"]:
        plan_stats[preset] = {
            "win_bets": 0, "win_hits": 0, "win_wagered": 0, "win_returned": 0,
            "place_bets": 0, "place_hits": 0, "place_wagered": 0, "place_returned": 0,
            "strong_bets": 0, "strong_hits": 0,
            # 選定馬ベース（単勝選定馬の複勝成績も追跡）
            "sel_total": 0, "sel_win": 0, "sel_place": 0,
            "sel_win_returned": 0, "sel_place_returned": 0,
            "sel_strong_total": 0, "sel_strong_win": 0, "sel_strong_place": 0,
            "sel_strong_win_ret": 0, "sel_strong_place_ret": 0,
        }

    ev_bands = {"<1.0": [0, 0, 0], "1.0-1.5": [0, 0, 0], "1.5-2.0": [0, 0, 0],
                "2.0-3.0": [0, 0, 0], "3.0+": [0, 0, 0]}
    ar_bands = {"<50": [0, 0, 0], "50-55": [0, 0, 0], "55-60": [0, 0, 0],
                "60-65": [0, 0, 0], "65+": [0, 0, 0]}
    gap_bands = {"3-4": [0, 0, 0], "5-6": [0, 0, 0], "7-8": [0, 0, 0], "9+": [0, 0, 0]}

    monthly_stats = defaultdict(lambda: {
        "vb_total": 0, "vb_win": 0, "vb_place": 0,
        "vb_wagered": 0, "vb_returned_win": 0, "vb_returned_place": 0,
        "std_bets": 0, "std_win": 0, "std_wagered": 0, "std_returned": 0,
    })
    venue_stats = defaultdict(lambda: {
        "vb_total": 0, "vb_win": 0, "vb_wagered": 0, "vb_returned": 0,
    })

    vb_big_hits = []
    files_processed = 0
    files_skipped = 0
    place_db_hits = 0
    place_db_misses = 0

    # === Phase 1: predictions.jsonとrace_idsを収集 ===
    print("Phase 1: predictions.json ファイル収集...")
    pred_entries = []  # [(pred_path, date_str, month_str)]
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

        # race_idを収集
        for race in pred_data.get("races", []):
            all_race_ids.append(race["race_id"])

        pred_entries.append((pred_path, date_str, month_str, pred_data))

    print(f"  {len(pred_entries)}日分, {len(all_race_ids)}レース")

    # === Phase 2: mykeibadbから確定複勝オッズをバッチ取得 ===
    print("Phase 2: mykeibadb確定複勝オッズ取得...")
    confirmed_place = load_confirmed_place_odds(all_race_ids)
    place_coverage = sum(len(v) for v in confirmed_place.values())
    print(f"  {len(confirmed_place)}レース, {place_coverage}頭分の確定複勝オッズ取得")

    # === Phase 3: 集計 ===
    print("Phase 3: 集計中...")

    for pred_path, date_str, month_str, pred_data in pred_entries:
        date_dir = pred_path.parent
        results = load_race_results(date_dir)

        if not results:
            files_skipped += 1
            continue

        files_processed += 1

        # --- エントリレベル分析 ---
        for race in pred_data.get("races", []):
            race_id = race["race_id"]
            venue = race.get("venue_name", "?")
            race_results = results.get(race_id, {})
            race_place_odds = confirmed_place.get(race_id, {})

            if not race_results:
                continue

            for entry in race.get("entries", []):
                umaban = entry["umaban"]
                result = race_results.get(umaban)
                if not result or result["finish_position"] is None:
                    continue

                pos = result["finish_position"]
                is_win = pos == 1
                is_place = pos <= 3
                actual_win_odds = result.get("odds") or entry.get("odds", 0)

                # 確定複勝オッズ: DB > predictions.json fallback
                actual_place_odds = race_place_odds.get(umaban, 0)
                if actual_place_odds:
                    place_db_hits += 1
                elif is_place:
                    actual_place_odds = entry.get("place_odds_min", 0)
                    place_db_misses += 1

                if entry.get("is_value_bet"):
                    vb_stats["total"] += 1
                    vb_stats["wagered"] += 100
                    if is_win:
                        vb_stats["win"] += 1
                        vb_stats["returned_win"] += int(actual_win_odds * 100)
                    if is_place:
                        vb_stats["place"] += 1
                        vb_stats["returned_place"] += int(actual_place_odds * 100)

                    # 月別
                    ms = monthly_stats[month_str]
                    ms["vb_total"] += 1
                    ms["vb_wagered"] += 100
                    if is_win:
                        ms["vb_win"] += 1
                        ms["vb_returned_win"] += int(actual_win_odds * 100)
                    if is_place:
                        ms["vb_place"] += 1
                        ms["vb_returned_place"] += int(actual_place_odds * 100)

                    # 会場別
                    vs = venue_stats[venue]
                    vs["vb_total"] += 1
                    vs["vb_wagered"] += 100
                    if is_win:
                        vs["vb_win"] += 1
                        vs["vb_returned"] += int(actual_win_odds * 100)

                    # 高配当ヒット
                    if is_win and actual_win_odds >= 10:
                        vb_big_hits.append({
                            "date": date_str, "venue": venue,
                            "race": race.get("race_number"),
                            "horse": entry.get("horse_name", "?"),
                            "odds": actual_win_odds,
                            "gap": entry.get("vb_gap", 0),
                            "win_ev": entry.get("win_ev", 0),
                            "ar_d": entry.get("ar_deviation", 0),
                        })

                    # EV帯別
                    ev = entry.get("win_ev", 0)
                    band = "<1.0" if ev < 1.0 else "1.0-1.5" if ev < 1.5 else \
                           "1.5-2.0" if ev < 2.0 else "2.0-3.0" if ev < 3.0 else "3.0+"
                    ev_bands[band][0] += 1
                    if is_win:
                        ev_bands[band][1] += 1
                        ev_bands[band][2] += int(actual_win_odds * 100)

                    # AR偏差値帯別
                    ar = entry.get("ar_deviation", 0)
                    band = "<50" if ar < 50 else "50-55" if ar < 55 else \
                           "55-60" if ar < 60 else "60-65" if ar < 65 else "65+"
                    ar_bands[band][0] += 1
                    if is_win:
                        ar_bands[band][1] += 1
                        ar_bands[band][2] += int(actual_win_odds * 100)

                    # Gap帯別
                    gap = entry.get("vb_gap", 0)
                    band = "3-4" if gap <= 4 else "5-6" if gap <= 6 else \
                           "7-8" if gap <= 8 else "9+"
                    gap_bands[band][0] += 1
                    if is_win:
                        gap_bands[band][1] += 1
                        gap_bands[band][2] += int(actual_win_odds * 100)
                else:
                    non_vb_stats["total"] += 1
                    if is_win:
                        non_vb_stats["win"] += 1
                    if is_place:
                        non_vb_stats["place"] += 1

        # --- 購入プラン分析 ---
        recs = pred_data.get("recommendations", {})
        for preset_name, preset_data in recs.items():
            if preset_name not in plan_stats:
                continue
            ps = plan_stats[preset_name]

            for bet in preset_data.get("bets", []):
                bet_race_id = bet["race_id"]
                umaban = bet["umaban"]
                race_results_map = results.get(bet_race_id, {})
                result = race_results_map.get(umaban)
                race_place_odds = confirmed_place.get(bet_race_id, {})

                if not result or result["finish_position"] is None:
                    continue

                pos = result["finish_position"]
                is_win = pos == 1
                is_place = pos <= 3
                actual_odds = result.get("odds") or bet.get("odds", 0) or 0
                actual_place = race_place_odds.get(umaban, 0) or bet.get("place_odds_min", 0) or 0

                win_amount = bet.get("win_amount", 0)
                place_amount = bet.get("place_amount", 0)
                is_strong = bet.get("strength") == "strong"

                if win_amount > 0:
                    ps["win_bets"] += 1
                    ps["win_wagered"] += win_amount
                    if is_win:
                        ps["win_hits"] += 1
                        ps["win_returned"] += int(actual_odds * win_amount)
                    if is_strong:
                        ps["strong_bets"] += 1
                        if is_win:
                            ps["strong_hits"] += 1

                if place_amount > 0:
                    ps["place_bets"] += 1
                    ps["place_wagered"] += place_amount
                    if is_place:
                        ps["place_hits"] += 1
                        ps["place_returned"] += int(actual_place * place_amount)

                # 選定馬ベース分析（単勝/複勝を¥100均等で集計）
                if win_amount > 0 or place_amount > 0:
                    ps["sel_total"] += 1
                    if is_win:
                        ps["sel_win"] += 1
                        ps["sel_win_returned"] += int(actual_odds * 100)
                    if is_place:
                        ps["sel_place"] += 1
                        ps["sel_place_returned"] += int(actual_place * 100)
                    if is_strong:
                        ps["sel_strong_total"] += 1
                        if is_win:
                            ps["sel_strong_win"] += 1
                            ps["sel_strong_win_ret"] += int(actual_odds * 100)
                        if is_place:
                            ps["sel_strong_place"] += 1
                            ps["sel_strong_place_ret"] += int(actual_place * 100)

                # 月別(standardのみ)
                if preset_name == "standard" and win_amount > 0:
                    ms = monthly_stats[month_str]
                    ms["std_bets"] += 1
                    ms["std_wagered"] += win_amount
                    if is_win:
                        ms["std_win"] += 1
                        ms["std_returned"] += int(actual_odds * win_amount)

    # ================================================================
    # レポート出力
    # ================================================================
    print()
    print("=" * 72)
    print(f"  predictions.json 確定成績レポート ({start_month} ~ {end_month})")
    print(f"  処理: {files_processed}日 / スキップ: {files_skipped}日")
    print(f"  複勝配当: DB={place_db_hits}, fallback={place_db_misses}")
    print("=" * 72)

    # --- VB馬全体 ---
    print("\n" + "=" * 72)
    print("  1. ValueBet馬 全体成績")
    print("=" * 72)
    if vb_stats["total"] > 0:
        t = vb_stats
        win_rate = t["win"] / t["total"] * 100
        place_rate = t["place"] / t["total"] * 100
        win_roi = t["returned_win"] / t["wagered"] * 100
        place_roi = t["returned_place"] / t["wagered"] * 100
        print(f"  VB馬数:     {t['total']}")
        print(f"  勝率:       {t['win']}/{t['total']} = {win_rate:.1f}%")
        print(f"  複勝率:     {t['place']}/{t['total']} = {place_rate:.1f}%")
        print(f"  単勝投資:   {fmt_yen(t['wagered'])}")
        print(f"  単勝回収:   {fmt_yen(t['returned_win'])} (ROI {win_roi:.1f}%)")
        print(f"  単勝収支:   {t['returned_win'] - t['wagered']:+,}")
        print(f"  複勝回収:   {fmt_yen(t['returned_place'])} (ROI {place_roi:.1f}%)")
        print(f"  複勝収支:   {t['returned_place'] - t['wagered']:+,}")

    if non_vb_stats["total"] > 0:
        nv = non_vb_stats
        nv_wr = nv["win"] / nv["total"] * 100
        nv_pr = nv["place"] / nv["total"] * 100
        print(f"\n  [参考] 非VB馬: 勝率={nv_wr:.1f}%, 複勝率={nv_pr:.1f}% (N={nv['total']})")

    # --- 購入プラン(実際の配分ベース) ---
    print("\n" + "=" * 72)
    print("  2. 購入プラン別成績（実配分ベース）")
    print("=" * 72)
    header = f"  {'Plan':<12} {'Bets':>5} {'Hits':>4} {'Rate':>6} {'Wagered':>10} {'Return':>10} {'ROI':>7} {'P&L':>10}"
    print(header)
    print("  " + "-" * 68)
    for preset in ["standard", "wide", "aggressive"]:
        ps = plan_stats[preset]
        if ps["win_bets"] > 0:
            hr = ps["win_hits"] / ps["win_bets"] * 100
            roi = ps["win_returned"] / ps["win_wagered"] * 100 if ps["win_wagered"] > 0 else 0
            pnl = ps["win_returned"] - ps["win_wagered"]
            print(f"  {preset:<12} {ps['win_bets']:>5} {ps['win_hits']:>4} {hr:>5.1f}% {fmt_yen(ps['win_wagered']):>10} {fmt_yen(ps['win_returned']):>10} {roi:>6.1f}% {pnl:>+9,}")

        if ps["place_bets"] > 0:
            hr = ps["place_hits"] / ps["place_bets"] * 100
            roi = ps["place_returned"] / ps["place_wagered"] * 100 if ps["place_wagered"] > 0 else 0
            pnl = ps["place_returned"] - ps["place_wagered"]
            label = f"{preset}(Place)"
            print(f"  {label:<12} {ps['place_bets']:>5} {ps['place_hits']:>4} {hr:>5.1f}% {fmt_yen(ps['place_wagered']):>10} {fmt_yen(ps['place_returned']):>10} {roi:>6.1f}% {pnl:>+9,}")

        if ps["strong_bets"] > 0:
            shr = ps["strong_hits"] / ps["strong_bets"] * 100
            print(f"    -> strong: {ps['strong_hits']}/{ps['strong_bets']} = {shr:.1f}%")

    # --- 購入プラン選定馬の単勝/複勝（¥100均等ベース） ---
    print("\n" + "=" * 72)
    print("  2b. 購入プラン選定馬 単勝/複勝成績 (Y100均等)")
    print("=" * 72)
    print(f"  {'Plan':<12} {'N':>5}  {'Win':>4} {'WinRate':>7} {'WinROI':>7}  {'Place':>5} {'PlRate':>7} {'PlROI':>7}")
    print("  " + "-" * 68)
    for preset in ["standard", "wide", "aggressive"]:
        ps = plan_stats[preset]
        n = ps["sel_total"]
        if n > 0:
            wagered = n * 100
            wr = ps["sel_win"] / n * 100
            pr = ps["sel_place"] / n * 100
            w_roi = ps["sel_win_returned"] / wagered * 100
            p_roi = ps["sel_place_returned"] / wagered * 100
            print(f"  {preset:<12} {n:>5}  {ps['sel_win']:>4} {wr:>6.1f}% {w_roi:>6.1f}%  {ps['sel_place']:>5} {pr:>6.1f}% {p_roi:>6.1f}%")
        # strong
        sn = ps["sel_strong_total"]
        if sn > 0:
            sw = sn * 100
            swr = ps["sel_strong_win"] / sn * 100
            spr = ps["sel_strong_place"] / sn * 100
            sw_roi = ps["sel_strong_win_ret"] / sw * 100
            sp_roi = ps["sel_strong_place_ret"] / sw * 100
            print(f"    strong     {sn:>5}  {ps['sel_strong_win']:>4} {swr:>6.1f}% {sw_roi:>6.1f}%  {ps['sel_strong_place']:>5} {spr:>6.1f}% {sp_roi:>6.1f}%")

    # 収支サマリー
    print()
    print(f"  {'Plan':<12} {'単勝収支':>12} {'複勝収支':>12} {'単複合算':>12}")
    print("  " + "-" * 44)
    for preset in ["standard", "wide", "aggressive"]:
        ps = plan_stats[preset]
        n = ps["sel_total"]
        if n > 0:
            wagered = n * 100
            w_pnl = ps["sel_win_returned"] - wagered
            p_pnl = ps["sel_place_returned"] - wagered
            # 単複各¥100で両方買った場合
            both_wagered = n * 200
            both_ret = ps["sel_win_returned"] + ps["sel_place_returned"]
            both_pnl = both_ret - both_wagered
            print(f"  {preset:<12} {w_pnl:>+11,} {p_pnl:>+11,} {both_pnl:>+11,}")

    # --- EV帯別 ---
    print("\n" + "=" * 72)
    print("  3. VB馬 帯別分析（単勝）")
    print("=" * 72)

    print("\n  [EV帯別]")
    print(f"  {'EV':>10} {'N':>6} {'Win':>4} {'Rate':>6} {'ROI':>7}")
    for band, (n, w, ret) in ev_bands.items():
        if n > 0:
            wr = w / n * 100
            roi = ret / (n * 100) * 100
            print(f"  {band:>10} {n:>6} {w:>4} {wr:>5.1f}% {roi:>6.1f}%")

    print("\n  [AR偏差値帯別]")
    print(f"  {'ARd':>10} {'N':>6} {'Win':>4} {'Rate':>6} {'ROI':>7}")
    for band, (n, w, ret) in ar_bands.items():
        if n > 0:
            wr = w / n * 100
            roi = ret / (n * 100) * 100
            print(f"  {band:>10} {n:>6} {w:>4} {wr:>5.1f}% {roi:>6.1f}%")

    print("\n  [Gap帯別]")
    print(f"  {'Gap':>10} {'N':>6} {'Win':>4} {'Rate':>6} {'ROI':>7}")
    for band, (n, w, ret) in gap_bands.items():
        if n > 0:
            wr = w / n * 100
            roi = ret / (n * 100) * 100
            print(f"  {band:>10} {n:>6} {w:>4} {wr:>5.1f}% {roi:>6.1f}%")

    # --- 月別推移 ---
    print("\n" + "=" * 72)
    print("  4. 月別推移")
    print("=" * 72)
    print(f"  {'Month':<8} {'VB_N':>5} {'VBwin':>5} {'VBrate':>6} {'VB_ROI':>7} {'VBpl':>5} {'VBplROI':>7}  {'STD_N':>5} {'STDwin':>5} {'STD_ROI':>7}")
    for month in sorted(monthly_stats.keys()):
        ms = monthly_stats[month]
        vb_wr = ms["vb_win"] / ms["vb_total"] * 100 if ms["vb_total"] > 0 else 0
        vb_roi = ms["vb_returned_win"] / ms["vb_wagered"] * 100 if ms["vb_wagered"] > 0 else 0
        vb_pr = ms["vb_place"] / ms["vb_total"] * 100 if ms["vb_total"] > 0 else 0
        vb_pl_roi = ms["vb_returned_place"] / ms["vb_wagered"] * 100 if ms["vb_wagered"] > 0 else 0
        std_roi = ms["std_returned"] / ms["std_wagered"] * 100 if ms["std_wagered"] > 0 else 0
        print(f"  {month:<8} {ms['vb_total']:>5} {ms['vb_win']:>5} {vb_wr:>5.1f}% {vb_roi:>6.1f}% {ms['vb_place']:>5} {vb_pl_roi:>6.1f}%  {ms['std_bets']:>5} {ms['std_win']:>5} {std_roi:>6.1f}%")

    # --- 会場別 ---
    print("\n" + "=" * 72)
    print("  5. VB馬 会場別成績（単勝）")
    print("=" * 72)
    print(f"  {'Venue':<8} {'N':>5} {'Win':>4} {'Rate':>6} {'ROI':>7}")
    for venue in sorted(venue_stats.keys()):
        vs = venue_stats[venue]
        if vs["vb_total"] > 0:
            wr = vs["vb_win"] / vs["vb_total"] * 100
            roi = vs["vb_returned"] / vs["vb_wagered"] * 100
            print(f"  {venue:<8} {vs['vb_total']:>5} {vs['vb_win']:>4} {wr:>5.1f}% {roi:>6.1f}%")

    # --- 高配当ヒット ---
    if vb_big_hits:
        vb_big_hits.sort(key=lambda x: x["odds"], reverse=True)
        print(f"\n{'=' * 72}")
        print(f"  6. VB馬 高配当的中 TOP15 (odds>=10)")
        print("=" * 72)
        for i, h in enumerate(vb_big_hits[:15]):
            print(f"  {i+1:>2}. {h['date']} {h['venue']} R{h['race']:>2}  "
                  f"{h['horse']:<16} odds={h['odds']:>6.1f}  gap={h['gap']:>2}  "
                  f"EV={h['win_ev']:.2f}  ARd={h['ar_d']:.1f}")
        print(f"\n  (高配当的中 合計: {len(vb_big_hits)}件)")

    print("\n" + "=" * 72)
    print("  *** 注意: オッズは確定最終オッズ（レース後）を使用 ***")
    print("  *** 複勝配当: mykeibadb確定値 > predictions.json place_odds_min ***")
    print("=" * 72)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="predictions.json確定成績集計")
    parser.add_argument("--start", default="2025-01", help="開始月 (YYYY-MM)")
    parser.add_argument("--end", default="2026-02", help="終了月 (YYYY-MM)")
    args = parser.parse_args()
    analyze_predictions(args.start, args.end)
