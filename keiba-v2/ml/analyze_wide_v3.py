"""
ワイド戦略 v3 分析: ROI重視の条件探索
激戦ワイド419件がROI 89%で赤字 → 改善条件を探す

Focus:
1. 現状の激戦ワイドのROI内訳（オッズ分布、頭数別）
2. オッズフロア（最低ワイドオッズ）の効果
3. 頭数制限の厳格化
4. ARd/P%条件追加
5. 撤廃 vs 条件絞り込みの比較
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ワイドオッズDB
try:
    from core.odds_db import get_final_wide_odds, get_final_quinella_odds
    HAS_ODDS_DB = True
except Exception:
    HAS_ODDS_DB = False


def load_data():
    with open("C:/KEIBA-CICD/data3/ml/backtest_cache.json", "r", encoding="utf-8") as f:
        return json.load(f)


def check_wide_hit(entries, i, j):
    return entries[i]["is_top3"] == 1 and entries[j]["is_top3"] == 1


def check_umaren_hit(entries, i, j):
    """馬連ヒット: 両方が1-2着"""
    fp1 = entries[i].get("finish_position", 99)
    fp2 = entries[j].get("finish_position", 99)
    return fp1 <= 2 and fp2 <= 2


def get_wide_odds_from_db(race_id, u1, u2):
    """ワイドオッズをDBから取得"""
    if not HAS_ODDS_DB:
        return None
    try:
        odds_map = get_final_wide_odds(race_id)
        kumiban = f"{min(u1,u2):02d}{max(u1,u2):02d}"
        entry = odds_map.get(kumiban)
        if entry:
            return entry.get('odds_low', entry.get('odds', 0))
    except Exception:
        pass
    return None


def get_umaren_odds_from_db(race_id, u1, u2):
    """馬連オッズをDBから取得"""
    if not HAS_ODDS_DB:
        return None
    try:
        odds_map = get_final_quinella_odds(race_id)
        kumiban = f"{min(u1,u2):02d}{max(u1,u2):02d}"
        entry = odds_map.get(kumiban)
        if entry:
            return entry.get('odds', 0)
    except Exception:
        pass
    return None


def estimate_wide_odds(entries, i, j):
    """ワイドオッズの推定（DB無い場合のフォールバック）"""
    o1 = entries[i].get("odds", 10)
    o2 = entries[j].get("odds", 10)
    # 粗い推定: ワイドオッズ ≈ sqrt(単勝1 * 単勝2) * 0.15
    est = (o1 * o2) ** 0.5 * 0.15
    return max(1.1, est)


def compute_race_data(race):
    entries = race["entries"]
    n = len(entries)
    is_obstacle = race.get("track_type") == "obstacle" or "障害" in race.get("race_name", "")

    by_p = sorted(range(n), key=lambda i: entries[i].get("rank_p", 99))
    by_w = sorted(range(n), key=lambda i: entries[i].get("rank_w", 99))
    by_ard = sorted(range(n), key=lambda i: -float(entries[i].get("ar_deviation", 0) or 0))
    by_odds = sorted(range(n), key=lambda i: float(entries[i].get("odds", 999) or 999))

    # pair_agree
    if n < 2:
        return None
    p_pair = frozenset([by_p[0], by_p[1]])
    pair_agree = 0
    for ranking in [by_w, by_ard, by_odds]:
        if len(ranking) >= 2 and frozenset([ranking[0], ranking[1]]) == p_pair:
            pair_agree += 1

    # Top horses data
    e1, e2 = entries[by_p[0]], entries[by_p[1]]
    u1, u2 = e1["umaban"], e2["umaban"]

    # Wide odds
    wide_odds = get_wide_odds_from_db(race["race_id"], u1, u2)
    if wide_odds is None or wide_odds <= 0:
        wide_odds = estimate_wide_odds(entries, by_p[0], by_p[1])

    # Umaren odds
    umaren_odds = get_umaren_odds_from_db(race["race_id"], u1, u2)
    if umaren_odds is None or umaren_odds <= 0:
        umaren_odds = wide_odds * 3.0  # fallback estimate

    # Hit check
    hit = check_wide_hit(entries, by_p[0], by_p[1])
    umaren_hit = check_umaren_hit(entries, by_p[0], by_p[1])

    # P%/W% of top1/2
    p1_pp = e1.get("pred_proba_p_raw", 0)
    p2_pp = e2.get("pred_proba_p_raw", 0)
    p1_ard = float(e1.get("ar_deviation", 0) or 0)
    p2_ard = float(e2.get("ar_deviation", 0) or 0)
    p1_odds = float(e1.get("odds", 999) or 999)

    # Race confidence proxy
    if n >= 3:
        p3_pp = entries[by_p[2]].get("pred_proba_p_raw", 0)
        top_gap = p1_pp - p3_pp
    else:
        top_gap = p1_pp - p2_pp

    return {
        "race_id": race["race_id"],
        "n": n,
        "is_obstacle": is_obstacle,
        "pair_agree": pair_agree,
        "hit": hit,
        "umaren_hit": umaren_hit,
        "wide_odds": wide_odds,
        "umaren_odds": umaren_odds,
        "p1_pp": p1_pp,
        "p2_pp": p2_pp,
        "p1_ard": p1_ard,
        "p2_ard": p2_ard,
        "p1_odds": p1_odds,
        "top_gap": top_gap,
        "grade": race.get("grade", ""),
    }


def calc_roi(bets):
    """bets: list of (bet_amount, return_amount, hit_bool)"""
    if not bets:
        return 0, 0, 0, 0.0
    total_bet = sum(b[0] for b in bets)
    total_ret = sum(b[1] for b in bets)
    hits = sum(1 for b in bets if b[2])
    roi = total_ret / total_bet * 100 if total_bet > 0 else 0
    return len(bets), hits, total_bet, roi


def print_row(label, bets, extra=""):
    n, hits, total_bet, roi = calc_roi(bets)
    hit_rate = hits / n * 100 if n > 0 else 0
    pnl = sum(b[1] for b in bets) - total_bet
    marker = " ***" if roi >= 100 else ""
    print(f"  {label:<35} {n:>5} {hits:>5} {hit_rate:>6.1f}% {roi:>7.1f}%{marker} {pnl:>+8,}{extra}")


def main():
    data = load_data()
    print(f"Total races in cache: {len(data)}")
    print(f"Wide odds DB available: {HAS_ODDS_DB}")

    # Process all races
    all_races = []
    for race in data:
        rd = compute_race_data(race)
        if rd:
            all_races.append(rd)

    # === 1. 現状の激戦ワイド再現 ===
    print("\n" + "=" * 80)
    print("  PART 1: 現状の激戦ワイド再現 (非障害, <=14頭, pair_agree>=3)")
    print("=" * 80)
    print(f"  {'条件':<35} {'件数':>5} {'的中':>5} {'的中率':>7} {'ROI':>8} {'P&L':>9}")
    print(f"  {'-' * 78}")

    current = [(100, int(r["wide_odds"] * 100) if r["hit"] else 0, r["hit"])
               for r in all_races if not r["is_obstacle"] and r["n"] <= 14 and r["pair_agree"] >= 3]
    print_row("現状 (<=14, agree>=3)", current)

    # 障害ワイド（参考）
    obstacle = [(100, int(r["wide_odds"] * 100) if r["hit"] else 0, r["hit"])
                for r in all_races if r["is_obstacle"] and r["n"] >= 9]
    print_row("障害ワイド (>=9頭)", obstacle)

    # === 2. 頭数別分析 ===
    print("\n" + "=" * 80)
    print("  PART 2: 頭数別ROI分析 (激戦ワイド: agree>=3)")
    print("=" * 80)
    print(f"  {'頭数':<35} {'件数':>5} {'的中':>5} {'的中率':>7} {'ROI':>8} {'P&L':>9}")
    print(f"  {'-' * 78}")

    for max_n in range(5, 19):
        subset = [(100, int(r["wide_odds"] * 100) if r["hit"] else 0, r["hit"])
                  for r in all_races if not r["is_obstacle"] and r["n"] == max_n and r["pair_agree"] >= 3]
        if subset:
            print_row(f"  {max_n}頭", subset)

    # 頭数レンジ
    print()
    for lo, hi in [(5, 8), (9, 10), (11, 12), (13, 14), (9, 14), (11, 14), (9, 12)]:
        subset = [(100, int(r["wide_odds"] * 100) if r["hit"] else 0, r["hit"])
                  for r in all_races if not r["is_obstacle"] and lo <= r["n"] <= hi and r["pair_agree"] >= 3]
        if subset:
            print_row(f"  {lo}-{hi}頭", subset)

    # === 3. ワイドオッズフロア ===
    print("\n" + "=" * 80)
    print("  PART 3: ワイドオッズフロア (激戦ワイド: agree>=3, <=14頭)")
    print("=" * 80)
    print(f"  {'オッズフロア':<35} {'件数':>5} {'的中':>5} {'的中率':>7} {'ROI':>8} {'P&L':>9}")
    print(f"  {'-' * 78}")

    gekisen = [r for r in all_races if not r["is_obstacle"] and r["n"] <= 14 and r["pair_agree"] >= 3]

    for min_odds in [1.0, 1.3, 1.5, 1.8, 2.0, 2.5, 3.0, 4.0, 5.0]:
        subset = [(100, int(r["wide_odds"] * 100) if r["hit"] else 0, r["hit"])
                  for r in gekisen if r["wide_odds"] >= min_odds]
        if subset:
            print_row(f"  odds >= {min_odds:.1f}", subset)

    # === 4. 頭数×オッズフロア ===
    print("\n" + "=" * 80)
    print("  PART 4: 頭数レンジ × オッズフロア (agree>=3)")
    print("=" * 80)
    print(f"  {'条件':<35} {'件数':>5} {'的中':>5} {'的中率':>7} {'ROI':>8} {'P&L':>9}")
    print(f"  {'-' * 78}")

    for (lo, hi) in [(9, 14), (11, 14), (9, 12)]:
        for min_odds in [1.0, 1.5, 2.0, 3.0]:
            subset = [(100, int(r["wide_odds"] * 100) if r["hit"] else 0, r["hit"])
                      for r in all_races
                      if not r["is_obstacle"] and lo <= r["n"] <= hi
                      and r["pair_agree"] >= 3 and r["wide_odds"] >= min_odds]
            if subset:
                print_row(f"  {lo}-{hi}頭 odds>={min_odds:.1f}", subset)
        print()

    # === 5. pair_agree不問（Pモデルtop1-2だけ） ===
    print("\n" + "=" * 80)
    print("  PART 5: pair_agree不問 (Pモデル top1-2 のみ)")
    print("=" * 80)
    print(f"  {'条件':<35} {'件数':>5} {'的中':>5} {'的中率':>7} {'ROI':>8} {'P&L':>9}")
    print(f"  {'-' * 78}")

    for agree in [0, 1, 2, 3]:
        for (lo, hi) in [(5, 18), (9, 14), (11, 14)]:
            subset = [(100, int(r["wide_odds"] * 100) if r["hit"] else 0, r["hit"])
                      for r in all_races
                      if not r["is_obstacle"] and lo <= r["n"] <= hi
                      and r["pair_agree"] >= agree]
            if subset:
                print_row(f"  agree>={agree} {lo}-{hi}頭", subset)
        print()

    # === 6. P%/ARd条件 ===
    print("\n" + "=" * 80)
    print("  PART 6: P%/ARd追加フィルタ (agree>=3, <=14頭)")
    print("=" * 80)
    print(f"  {'条件':<35} {'件数':>5} {'的中':>5} {'的中率':>7} {'ROI':>8} {'P&L':>9}")
    print(f"  {'-' * 78}")

    for min_ard in [0, 45, 50, 55, 60]:
        subset = [(100, int(r["wide_odds"] * 100) if r["hit"] else 0, r["hit"])
                  for r in gekisen if r["p1_ard"] >= min_ard and r["p2_ard"] >= min_ard]
        if subset:
            print_row(f"  both ARd >= {min_ard}", subset)

    print()
    for min_ard1 in [50, 55, 60]:
        subset = [(100, int(r["wide_odds"] * 100) if r["hit"] else 0, r["hit"])
                  for r in gekisen if r["p1_ard"] >= min_ard1]
        if subset:
            print_row(f"  top1 ARd >= {min_ard1}", subset)

    # === 7. オッズ分布ヒストグラム ===
    print("\n" + "=" * 80)
    print("  PART 7: ワイドオッズ分布 (激戦ワイド: agree>=3, <=14頭)")
    print("=" * 80)

    bins = [(1.0, 1.5), (1.5, 2.0), (2.0, 2.5), (2.5, 3.0), (3.0, 4.0),
            (4.0, 5.0), (5.0, 7.0), (7.0, 10.0), (10.0, 999)]
    print(f"  {'オッズ帯':<20} {'件数':>5} {'的中':>5} {'的中率':>7} {'ROI':>8} {'avgOdds':>8}")
    print(f"  {'-' * 60}")

    for lo, hi in bins:
        subset = [r for r in gekisen if lo <= r["wide_odds"] < hi]
        if not subset:
            continue
        n = len(subset)
        hits = sum(1 for r in subset if r["hit"])
        total_bet = n * 100
        total_ret = sum(int(r["wide_odds"] * 100) for r in subset if r["hit"])
        roi = total_ret / total_bet * 100
        hit_rate = hits / n * 100
        avg_odds = sum(r["wide_odds"] for r in subset) / n
        label = f"{lo:.1f}-{hi:.1f}" if hi < 999 else f"{lo:.1f}+"
        marker = " ***" if roi >= 100 else ""
        print(f"  {label:<20} {n:>5} {hits:>5} {hit_rate:>6.1f}% {roi:>7.1f}%{marker} {avg_odds:>8.2f}")

    # === 8. 全戦略の全体P/Lインパクト比較 ===
    print("\n" + "=" * 80)
    print("  PART 8: 全体P/Lインパクト（激戦ワイドの選択肢）")
    print("=" * 80)
    print(f"  {'戦略':<35} {'件数':>5} {'的中':>5} {'的中率':>7} {'ROI':>8} {'P&L':>9}")
    print(f"  {'-' * 78}")

    strategies = {
        "A: 現状 (<=14, agree>=3)": lambda r: not r["is_obstacle"] and r["n"] <= 14 and r["pair_agree"] >= 3,
        "B: 撤廃 (激戦ワイドなし)": lambda r: False,
        "C: odds>=2.0 追加": lambda r: not r["is_obstacle"] and r["n"] <= 14 and r["pair_agree"] >= 3 and r["wide_odds"] >= 2.0,
        "D: odds>=2.5 追加": lambda r: not r["is_obstacle"] and r["n"] <= 14 and r["pair_agree"] >= 3 and r["wide_odds"] >= 2.5,
        "E: odds>=3.0 追加": lambda r: not r["is_obstacle"] and r["n"] <= 14 and r["pair_agree"] >= 3 and r["wide_odds"] >= 3.0,
        "F: 9-14頭 + odds>=2.0": lambda r: not r["is_obstacle"] and 9 <= r["n"] <= 14 and r["pair_agree"] >= 3 and r["wide_odds"] >= 2.0,
        "G: 9-14頭 + odds>=2.5": lambda r: not r["is_obstacle"] and 9 <= r["n"] <= 14 and r["pair_agree"] >= 3 and r["wide_odds"] >= 2.5,
        "H: 11-14頭 + odds>=2.0": lambda r: not r["is_obstacle"] and 11 <= r["n"] <= 14 and r["pair_agree"] >= 3 and r["wide_odds"] >= 2.0,
        "I: <=12頭 + odds>=2.0": lambda r: not r["is_obstacle"] and r["n"] <= 12 and r["pair_agree"] >= 3 and r["wide_odds"] >= 2.0,
        "J: agree>=3 + ARd>=50 both": lambda r: not r["is_obstacle"] and r["n"] <= 14 and r["pair_agree"] >= 3 and r["p1_ard"] >= 50 and r["p2_ard"] >= 50,
        "K: odds>=2.0 + ARd>=50 both": lambda r: not r["is_obstacle"] and r["n"] <= 14 and r["pair_agree"] >= 3 and r["wide_odds"] >= 2.0 and r["p1_ard"] >= 50 and r["p2_ard"] >= 50,
    }

    for label, filter_fn in strategies.items():
        bets = [(100, int(r["wide_odds"] * 100) if r["hit"] else 0, r["hit"])
                for r in all_races if filter_fn(r)]
        print_row(label, bets)

    # === 9. ワイドEV (est. hit_rate * odds) ===
    print("\n" + "=" * 80)
    print("  PART 9: ワイドEV推定 (agree>=3, <=14頭)")
    print("  ※ wide_ev = 推定的中率(pair_agree=3→50%) × ワイドオッズ")
    print("=" * 80)

    for ev_min in [0.8, 0.9, 1.0, 1.1, 1.2, 1.5]:
        subset = [(100, int(r["wide_odds"] * 100) if r["hit"] else 0, r["hit"])
                  for r in gekisen if 0.50 * r["wide_odds"] >= ev_min]
        if subset:
            print_row(f"  wide_ev >= {ev_min:.1f}", subset)

    # === 10. ワイド vs 馬連 比較 ===
    print("\n" + "=" * 80)
    print("  PART 10: ワイド vs 馬連 直接比較")
    print("  ワイド = 両方3着内, 馬連 = 両方2着内")
    print("=" * 80)

    print(f"\n  --- 激戦ワイド条件 (agree>=3) × 頭数帯 ---")
    print(f"  {'条件':<30} │{'── ワイド ──':>24} │{'── 馬連 ──':>24}")
    print(f"  {'':30} │{'件数':>5} {'的中':>4} {'率':>6} {'ROI':>7} │{'件数':>5} {'的中':>4} {'率':>6} {'ROI':>7}")
    print(f"  {'-' * 90}")

    def print_wide_vs_umaren(label, subset):
        if not subset:
            return
        n = len(subset)
        # ワイド
        w_hits = sum(1 for r in subset if r["hit"])
        w_bet = n * 100
        w_ret = sum(int(r["wide_odds"] * 100) for r in subset if r["hit"])
        w_roi = w_ret / w_bet * 100
        w_rate = w_hits / n * 100
        # 馬連
        u_hits = sum(1 for r in subset if r["umaren_hit"])
        u_bet = n * 100
        u_ret = sum(int(r["umaren_odds"] * 100) for r in subset if r["umaren_hit"])
        u_roi = u_ret / u_bet * 100
        u_rate = u_hits / n * 100
        w_mark = "***" if w_roi >= 100 else "   "
        u_mark = "***" if u_roi >= 100 else "   "
        print(f"  {label:<30} │{n:>5} {w_hits:>4} {w_rate:>5.1f}% {w_roi:>6.1f}%{w_mark}│"
              f"{n:>5} {u_hits:>4} {u_rate:>5.1f}% {u_roi:>6.1f}%{u_mark}")

    # 全体
    for (lo, hi) in [(5, 14), (5, 18), (9, 14), (11, 14), (13, 18)]:
        subset = [r for r in all_races if not r["is_obstacle"]
                  and lo <= r["n"] <= hi and r["pair_agree"] >= 3]
        print_wide_vs_umaren(f"agree>=3 {lo}-{hi}頭", subset)

    # 頭数別
    print(f"\n  --- 頭数別 (agree>=3) ---")
    print(f"  {'頭数':<30} │{'── ワイド ──':>24} │{'── 馬連 ──':>24}")
    print(f"  {'':30} │{'件数':>5} {'的中':>4} {'率':>6} {'ROI':>7} │{'件数':>5} {'的中':>4} {'率':>6} {'ROI':>7}")
    print(f"  {'-' * 90}")

    for n_entries in range(5, 19):
        subset = [r for r in all_races if not r["is_obstacle"]
                  and r["n"] == n_entries and r["pair_agree"] >= 3]
        if len(subset) >= 5:
            print_wide_vs_umaren(f"  {n_entries}頭", subset)

    # === 11. 馬連のオッズフロア ===
    print(f"\n  --- 馬連 オッズフロア (agree>=3, <=14頭) ---")
    print(f"  {'条件':<35} {'件数':>5} {'的中':>5} {'的中率':>7} {'ROI':>8} {'P&L':>9}")
    print(f"  {'-' * 78}")

    for min_odds in [1.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0]:
        subset = [(100, int(r["umaren_odds"] * 100) if r["umaren_hit"] else 0, r["umaren_hit"])
                  for r in gekisen if r["umaren_odds"] >= min_odds]
        if subset:
            print_row(f"  馬連 odds >= {min_odds:.0f}", subset)

    # === 12. ワイド+馬連コンボ（両方買い） ===
    print(f"\n  --- ワイド+馬連 両方買い (agree>=3) ---")
    print(f"  {'条件':<35} {'件数':>5} {'投資':>8} {'回収':>8} {'ROI':>8} {'P&L':>9}")
    print(f"  {'-' * 78}")

    for (lo, hi) in [(5, 14), (9, 14), (11, 14)]:
        subset = [r for r in all_races if not r["is_obstacle"]
                  and lo <= r["n"] <= hi and r["pair_agree"] >= 3]
        if not subset:
            continue
        # ワイドのみ
        w_bet = len(subset) * 100
        w_ret = sum(int(r["wide_odds"] * 100) for r in subset if r["hit"])
        # 馬連のみ
        u_bet = len(subset) * 100
        u_ret = sum(int(r["umaren_odds"] * 100) for r in subset if r["umaren_hit"])
        # コンボ(ワイド100+馬連100)
        c_bet = len(subset) * 200
        c_ret = w_ret + u_ret

        print(f"  {lo}-{hi}頭 ワイドのみ            {len(subset):>5} {w_bet:>8,} {w_ret:>8,} {w_ret/w_bet*100:>7.1f}% {w_ret-w_bet:>+8,}")
        print(f"  {lo}-{hi}頭 馬連のみ              {len(subset):>5} {u_bet:>8,} {u_ret:>8,} {u_ret/u_bet*100:>7.1f}% {u_ret-u_bet:>+8,}")
        print(f"  {lo}-{hi}頭 ワイド+馬連           {len(subset):>5} {c_bet:>8,} {c_ret:>8,} {c_ret/c_bet*100:>7.1f}% {c_ret-c_bet:>+8,}")
        print()

    # === 13. 馬連単独 vs ワイド単独 戦略サマリー ===
    print("\n" + "=" * 80)
    print("  PART 13: 最終戦略比較（全候補）")
    print("=" * 80)
    print(f"  {'戦略':<40} {'件数':>5} {'投資':>8} {'回収':>8} {'ROI':>8} {'P&L':>9}")
    print(f"  {'-' * 80}")

    final_strategies = [
        ("A: 現状ワイド (<=14, agree>=3)",
         lambda r: [(100, int(r["wide_odds"]*100) if r["hit"] else 0)] if not r["is_obstacle"] and r["n"]<=14 and r["pair_agree"]>=3 else []),
        ("B: ワイド撤廃",
         lambda r: []),
        ("C: ワイド odds>=2.0",
         lambda r: [(100, int(r["wide_odds"]*100) if r["hit"] else 0)] if not r["is_obstacle"] and r["n"]<=14 and r["pair_agree"]>=3 and r["wide_odds"]>=2.0 else []),
        ("D: 馬連のみ (<=14, agree>=3)",
         lambda r: [(100, int(r["umaren_odds"]*100) if r["umaren_hit"] else 0)] if not r["is_obstacle"] and r["n"]<=14 and r["pair_agree"]>=3 else []),
        ("E: 馬連 odds>=5.0",
         lambda r: [(100, int(r["umaren_odds"]*100) if r["umaren_hit"] else 0)] if not r["is_obstacle"] and r["n"]<=14 and r["pair_agree"]>=3 and r["umaren_odds"]>=5.0 else []),
        ("F: 馬連 odds>=10.0",
         lambda r: [(100, int(r["umaren_odds"]*100) if r["umaren_hit"] else 0)] if not r["is_obstacle"] and r["n"]<=14 and r["pair_agree"]>=3 and r["umaren_odds"]>=10.0 else []),
        ("G: ワイドodds>=2.0 + 馬連odds>=10.0",
         lambda r: ([(100, int(r["wide_odds"]*100) if r["hit"] else 0)] if r["wide_odds"]>=2.0 else []) +
                   ([(100, int(r["umaren_odds"]*100) if r["umaren_hit"] else 0)] if r["umaren_odds"]>=10.0 else [])
                   if not r["is_obstacle"] and r["n"]<=14 and r["pair_agree"]>=3 else []),
        ("H: 馬連のみ (9-14頭, agree>=3)",
         lambda r: [(100, int(r["umaren_odds"]*100) if r["umaren_hit"] else 0)] if not r["is_obstacle"] and 9<=r["n"]<=14 and r["pair_agree"]>=3 else []),
        ("I: 馬連 9-14頭 odds>=7.0",
         lambda r: [(100, int(r["umaren_odds"]*100) if r["umaren_hit"] else 0)] if not r["is_obstacle"] and 9<=r["n"]<=14 and r["pair_agree"]>=3 and r["umaren_odds"]>=7.0 else []),
        ("J: ワイドodds>=2.5 + 馬連odds>=7.0",
         lambda r: ([(100, int(r["wide_odds"]*100) if r["hit"] else 0)] if r["wide_odds"]>=2.5 else []) +
                   ([(100, int(r["umaren_odds"]*100) if r["umaren_hit"] else 0)] if r["umaren_odds"]>=7.0 else [])
                   if not r["is_obstacle"] and r["n"]<=14 and r["pair_agree"]>=3 else []),
    ]

    for label, bet_fn in final_strategies:
        all_bets = []
        for r in all_races:
            bets = bet_fn(r)
            all_bets.extend(bets)
        if not all_bets:
            print(f"  {label:<40} {'---':>5}")
            continue
        total_bet = sum(b[0] for b in all_bets)
        total_ret = sum(b[1] for b in all_bets)
        roi = total_ret / total_bet * 100 if total_bet > 0 else 0
        pnl = total_ret - total_bet
        marker = " ***" if roi >= 100 else ""
        print(f"  {label:<40} {len(all_bets):>5} {total_bet:>8,} {total_ret:>8,} {roi:>7.1f}%{marker} {pnl:>+8,}")

    # === 14. ワイド:馬連 配分比率シミュレーション ===
    print("\n" + "=" * 80)
    print("  PART 14: ワイド:馬連 配分比率シミュレーション")
    print("  同じレース・同じペアでワイド+馬連を買う場合の最適比率")
    print("=" * 80)

    # 条件セット × 配分比率
    filter_sets = [
        ("全件 (agree>=3, <=14頭)", gekisen),
        ("odds_w>=2.0のみ", [r for r in gekisen if r["wide_odds"] >= 2.0]),
        ("9-14頭", [r for r in all_races if not r["is_obstacle"] and 9 <= r["n"] <= 14 and r["pair_agree"] >= 3]),
        ("11-14頭", [r for r in all_races if not r["is_obstacle"] and 11 <= r["n"] <= 14 and r["pair_agree"] >= 3]),
    ]

    ratios = [
        ("ワイド300:馬連0", 300, 0),
        ("ワイド200:馬連100", 200, 100),
        ("ワイド150:馬連150", 150, 150),
        ("ワイド100:馬連100", 100, 100),
        ("ワイド100:馬連200", 100, 200),
        ("ワイド0:馬連300", 0, 300),
        ("ワイド100:馬連0", 100, 0),
        ("ワイド0:馬連100", 0, 100),
    ]

    for filter_label, subset in filter_sets:
        if not subset:
            continue
        print(f"\n  --- {filter_label} ({len(subset)}件) ---")
        print(f"  {'配分':<25} {'投資':>8} {'回収':>8} {'ROI':>8} {'P&L':>9} {'的中回数':>8}")
        print(f"  {'-' * 72}")

        for ratio_label, w_amt, u_amt in ratios:
            total_bet = 0
            total_ret = 0
            hit_count = 0
            for r in subset:
                bet = w_amt + u_amt
                total_bet += bet
                ret = 0
                hit = False
                if w_amt > 0 and r["hit"]:
                    ret += int(r["wide_odds"] * w_amt)
                    hit = True
                if u_amt > 0 and r["umaren_hit"]:
                    ret += int(r["umaren_odds"] * u_amt)
                    hit = True
                total_ret += ret
                if hit:
                    hit_count += 1
            roi = total_ret / total_bet * 100 if total_bet > 0 else 0
            pnl = total_ret - total_bet
            marker = " ***" if roi >= 100 else ""
            print(f"  {ratio_label:<25} {total_bet:>8,} {total_ret:>8,} {roi:>7.1f}%{marker} {pnl:>+8,} {hit_count:>6}件")

    # === 14b. 条件分岐戦略（ワイドオッズで切り替え） ===
    print(f"\n  --- 条件分岐: ワイドオッズで買い方を切り替え ---")
    print(f"  {'戦略':<45} {'件数':>5} {'投資':>8} {'回収':>8} {'ROI':>8} {'P&L':>9}")
    print(f"  {'-' * 85}")

    branch_strategies = [
        ("現状: 全部ワイド100",
         lambda r: (100, 0)),
        ("全部馬連100に切替",
         lambda r: (0, 100)),
        ("odds_w<2.0→馬連100, >=2.0→ワイド100",
         lambda r: (0, 100) if r["wide_odds"] < 2.0 else (100, 0)),
        ("odds_w<2.0→馬連100, >=2.0→ワイド+馬連100:100",
         lambda r: (0, 100) if r["wide_odds"] < 2.0 else (100, 100)),
        ("odds_w<2.0→撤退, >=2.0→ワイド100",
         lambda r: (0, 0) if r["wide_odds"] < 2.0 else (100, 0)),
        ("odds_w<2.0→撤退, >=2.0→ワイド+馬連100:100",
         lambda r: (0, 0) if r["wide_odds"] < 2.0 else (100, 100)),
        ("odds_w<1.5→馬連, 1.5-2.5→W+U均等, >=2.5→ワイド",
         lambda r: (0, 100) if r["wide_odds"] < 1.5 else ((100, 100) if r["wide_odds"] < 2.5 else (100, 0))),
        ("odds_w<2.0→馬連100, >=2.0→ワイド200+馬連100",
         lambda r: (0, 100) if r["wide_odds"] < 2.0 else (200, 100)),
    ]

    for label, alloc_fn in branch_strategies:
        total_bet = 0
        total_ret = 0
        n_bets = 0
        for r in gekisen:
            w_amt, u_amt = alloc_fn(r)
            bet = w_amt + u_amt
            if bet <= 0:
                continue
            total_bet += bet
            n_bets += 1
            if w_amt > 0 and r["hit"]:
                total_ret += int(r["wide_odds"] * w_amt)
            if u_amt > 0 and r["umaren_hit"]:
                total_ret += int(r["umaren_odds"] * u_amt)
        if total_bet <= 0:
            print(f"  {label:<45} {'---':>5}")
            continue
        roi = total_ret / total_bet * 100
        pnl = total_ret - total_bet
        marker = " ***" if roi >= 100 else ""
        print(f"  {label:<45} {n_bets:>5} {total_bet:>8,} {total_ret:>8,} {roi:>7.1f}%{marker} {pnl:>+8,}")

    # === 15. 馬連オッズ分布 ===
    print(f"\n\n  --- 馬連オッズ分布 (agree>=3, <=14頭) ---")
    print(f"  {'オッズ帯':<20} {'件数':>5} {'的中':>5} {'的中率':>7} {'ROI':>8} {'avgOdds':>8}")
    print(f"  {'-' * 60}")

    bins = [(1, 3), (3, 5), (5, 7), (7, 10), (10, 15), (15, 20), (20, 30), (30, 50), (50, 999)]
    for lo, hi in bins:
        subset = [r for r in gekisen if lo <= r["umaren_odds"] < hi]
        if not subset:
            continue
        n = len(subset)
        hits = sum(1 for r in subset if r["umaren_hit"])
        total_bet = n * 100
        total_ret = sum(int(r["umaren_odds"] * 100) for r in subset if r["umaren_hit"])
        roi = total_ret / total_bet * 100
        hit_rate = hits / n * 100
        avg_odds = sum(r["umaren_odds"] for r in subset) / n
        label = f"{lo}-{hi}" if hi < 999 else f"{lo}+"
        marker = " ***" if roi >= 100 else ""
        print(f"  {label:<20} {n:>5} {hits:>5} {hit_rate:>6.1f}% {roi:>7.1f}%{marker} {avg_odds:>8.1f}")


if __name__ == "__main__":
    main()
