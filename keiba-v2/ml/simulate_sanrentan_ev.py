#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
三連単 Synthetic EV バックテスト

Harville公式でモデル勝率から全組み合わせの確率を合成し、
実配当と比較してEV(期待値)ベースの購入戦略をバックテストする。

核心アイデア:
  - モデル勝率 P_win(A) から Harville公式で P(A1着,B2着,C3着) を計算
  - P_model × 配当 / 100 = Synthetic EV
  - EV > 閾値 の組み合わせのみ購入 → 「隠れたオッズの歪み」を発見

Usage:
    python -m ml.simulate_sanrentan_ev
    python -m ml.simulate_sanrentan_ev --top-n 20       # 上位N点買い
    python -m ml.simulate_sanrentan_ev --ev-threshold 2  # EV閾値
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from core.db import get_connection


# ===========================================================================
# Data loading
# ===========================================================================

def load_backtest_cache() -> list:
    path = config.ml_dir() / "backtest_cache.json"
    with open(path, encoding="utf-8") as f:
        cache = json.load(f)
    print(f"[Load] backtest_cache: {len(cache):,} races")
    return cache


def load_sanrentan_payouts(race_codes: List[str]) -> Dict[str, list]:
    """haraimodoshiから三連単実配当を取得"""
    cols = ["RACE_CODE", "FUSEIRITSU_FLAG_SANRENTAN"]
    for i in range(1, 7):
        cols.extend([
            f"SANRENTAN{i}_KUMIBAN1",
            f"SANRENTAN{i}_KUMIBAN2",
            f"SANRENTAN{i}_KUMIBAN3",
            f"SANRENTAN{i}_HARAIMODOSHIKIN",
        ])

    result = {}
    batch_size = 500

    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        for start in range(0, len(race_codes), batch_size):
            batch = race_codes[start:start + batch_size]
            placeholders = ",".join(["%s"] * len(batch))
            sql = (f"SELECT {', '.join(cols)} FROM haraimodoshi "
                   f"WHERE RACE_CODE IN ({placeholders})")
            cur.execute(sql, batch)
            for row in cur.fetchall():
                rc = row["RACE_CODE"].strip()
                if (row.get("FUSEIRITSU_FLAG_SANRENTAN", "0") or "0") == "1":
                    continue
                payouts = []
                for i in range(1, 7):
                    k1 = _pi(row.get(f"SANRENTAN{i}_KUMIBAN1", ""))
                    k2 = _pi(row.get(f"SANRENTAN{i}_KUMIBAN2", ""))
                    k3 = _pi(row.get(f"SANRENTAN{i}_KUMIBAN3", ""))
                    pay = _pi(row.get(f"SANRENTAN{i}_HARAIMODOSHIKIN", ""))
                    if k1 and k2 and k3 and pay:
                        payouts.append(((k1, k2, k3), pay))
                if payouts:
                    result[rc] = payouts
        cur.close()

    return result


def _pi(s) -> int:
    if not s:
        return 0
    try:
        return int(str(s).strip())
    except (ValueError, TypeError):
        return 0


# ===========================================================================
# Harville formula
# ===========================================================================

def extract_win_probs(entries: list) -> Dict[int, float]:
    """各馬の正規化された勝率を算出

    win_ev / odds で calibrated win prob を逆算し、sum=1.0 に正規化。
    """
    probs = {}
    for e in entries:
        odds = e.get("odds") or 0
        win_ev = e.get("win_ev") or 0
        if odds > 0 and win_ev > 0:
            probs[e["umaban"]] = win_ev / odds
        elif odds > 0:
            # win_evがない場合はoddsから逆算（フォールバック）
            probs[e["umaban"]] = 1.0 / odds

    # 正規化
    total = sum(probs.values())
    if total > 0:
        probs = {k: v / total for k, v in probs.items()}

    return probs


def extract_market_probs(entries: list) -> Dict[int, float]:
    """オッズから市場の暗黙確率を算出（正規化）"""
    probs = {}
    for e in entries:
        odds = e.get("odds") or 0
        if odds > 0:
            probs[e["umaban"]] = 1.0 / odds

    total = sum(probs.values())
    if total > 0:
        probs = {k: v / total for k, v in probs.items()}

    return probs


def harville_prob(win_probs: Dict[int, float], a: int, b: int, c: int) -> float:
    """Harville公式: P(A=1着, B=2着, C=3着)

    P(A,B,C) = P(A) × P(B)/(1-P(A)) × P(C)/(1-P(A)-P(B))
    """
    pa = win_probs.get(a, 0)
    pb = win_probs.get(b, 0)
    pc = win_probs.get(c, 0)

    if pa <= 0 or pb <= 0 or pc <= 0:
        return 0

    denom1 = 1.0 - pa
    if denom1 <= 0:
        return 0

    denom2 = 1.0 - pa - pb
    if denom2 <= 0:
        return 0

    return pa * (pb / denom1) * (pc / denom2)


def compute_all_trifecta_probs(
    win_probs: Dict[int, float],
    top_n_horses: int = 0,
) -> List[Tuple[Tuple[int, int, int], float]]:
    """全三連単組み合わせの確率を計算

    top_n_horses > 0 の場合、勝率上位N頭のみで組み合わせを生成（計算量削減）。
    """
    horses = sorted(win_probs.keys(), key=lambda h: -win_probs[h])
    if top_n_horses > 0:
        horses = horses[:top_n_horses]

    results = []
    for a in horses:
        for b in horses:
            if b == a:
                continue
            for c in horses:
                if c == a or c == b:
                    continue
                p = harville_prob(win_probs, a, b, c)
                if p > 0:
                    results.append(((a, b, c), p))

    results.sort(key=lambda x: -x[1])
    return results


# ===========================================================================
# Distortion detection (model vs market)
# ===========================================================================

def compute_distortions(
    model_probs: Dict[int, float],
    market_probs: Dict[int, float],
    top_n_horses: int = 10,
) -> List[Tuple[Tuple[int, int, int], float, float, float]]:
    """モデル確率 vs 市場確率の歪み度を計算

    Returns: [(ticket, model_prob, market_prob, distortion_ratio), ...]
    distortion_ratio = model_prob / market_prob (>1.0 = モデルが市場より高く評価)
    """
    horses_model = sorted(model_probs.keys(), key=lambda h: -model_probs[h])
    horses_market = sorted(market_probs.keys(), key=lambda h: -market_probs[h])

    # 両方に存在する馬のみ
    common = set(horses_model) & set(horses_market)
    horses = sorted(common, key=lambda h: -model_probs.get(h, 0))
    if top_n_horses > 0:
        horses = horses[:top_n_horses]

    results = []
    for a in horses:
        for b in horses:
            if b == a:
                continue
            for c in horses:
                if c == a or c == b:
                    continue
                p_model = harville_prob(model_probs, a, b, c)
                p_market = harville_prob(market_probs, a, b, c)
                if p_model > 0 and p_market > 0:
                    ratio = p_model / p_market
                    results.append(((a, b, c), p_model, p_market, ratio))

    results.sort(key=lambda x: -x[3])  # distortion高い順
    return results


# ===========================================================================
# Backtest
# ===========================================================================

@dataclass
class StrategyResult:
    name: str
    total_races: int = 0
    total_tickets: int = 0
    total_invested: int = 0
    total_return: int = 0
    total_hits: int = 0
    monthly: dict = field(default_factory=dict)
    hit_details: list = field(default_factory=list)
    # EV分析用
    ev_at_hit: list = field(default_factory=list)  # 的中時のEV値

    @property
    def roi(self) -> float:
        return self.total_return / self.total_invested * 100 if self.total_invested else 0

    @property
    def hit_rate_race(self) -> float:
        return self.total_hits / self.total_races * 100 if self.total_races else 0

    @property
    def avg_tickets(self) -> float:
        return self.total_tickets / self.total_races if self.total_races else 0

    @property
    def avg_payout(self) -> int:
        return self.total_return // self.total_hits if self.total_hits else 0


def run_ev_backtest(cache: list, payouts: Dict[str, list]) -> Dict[str, StrategyResult]:
    """複数のEV戦略をバックテスト"""

    strategies = {
        # --- Harville確率 Top-N 戦略 ---
        "Top5":  {"mode": "top_n", "n": 5, "horses": 10},
        "Top10": {"mode": "top_n", "n": 10, "horses": 10},
        "Top20": {"mode": "top_n", "n": 20, "horses": 12},
        "Top30": {"mode": "top_n", "n": 30, "horses": 12},
        # --- Distortion戦略（モデル vs 市場の歪み） ---
        "Dist>1.5_T10": {"mode": "distortion", "min_ratio": 1.5,
                         "max_tickets": 10, "horses": 10},
        "Dist>2.0_T10": {"mode": "distortion", "min_ratio": 2.0,
                         "max_tickets": 10, "horses": 10},
        "Dist>2.0_T20": {"mode": "distortion", "min_ratio": 2.0,
                         "max_tickets": 20, "horses": 10},
        "Dist>3.0_T10": {"mode": "distortion", "min_ratio": 3.0,
                         "max_tickets": 10, "horses": 10},
        "Dist>3.0_T20": {"mode": "distortion", "min_ratio": 3.0,
                         "max_tickets": 20, "horses": 10},
        "Dist>5.0_T10": {"mode": "distortion", "min_ratio": 5.0,
                         "max_tickets": 10, "horses": 12},
        "Dist>5.0_T20": {"mode": "distortion", "min_ratio": 5.0,
                         "max_tickets": 20, "horses": 12},
        # --- ハイブリッド（Distortion + 最低確率フィルタ） ---
        "Hybrid_D2_P0.5": {"mode": "hybrid", "min_ratio": 2.0,
                           "min_prob_pct": 0.5, "max_tickets": 15, "horses": 10},
        "Hybrid_D3_P0.3": {"mode": "hybrid", "min_ratio": 3.0,
                           "min_prob_pct": 0.3, "max_tickets": 15, "horses": 10},
        "Hybrid_D2_P1.0": {"mode": "hybrid", "min_ratio": 2.0,
                           "min_prob_pct": 1.0, "max_tickets": 10, "horses": 10},
    }

    results = {name: StrategyResult(name=name) for name in strategies}

    for race in cache:
        race_id = race["race_id"]
        entries = race.get("entries", [])

        # 障害レーススキップ
        if race.get("track_type") in ("obstacle", "steeplechase"):
            continue

        race_payouts = payouts.get(race_id)
        if not race_payouts:
            continue

        # 有効出走馬が少ないレースをスキップ
        valid_entries = [e for e in entries if (e.get("odds") or 0) > 0]
        if len(valid_entries) < 5:
            continue

        month = f"{race_id[:4]}-{race_id[4:6]}"

        # 確率計算
        model_probs = extract_win_probs(entries)
        market_probs = extract_market_probs(entries)

        if len(model_probs) < 5:
            continue

        # 的中組み合わせをセットに
        payout_map = {ticket: pay for ticket, pay in race_payouts}

        for strat_name, cfg in strategies.items():
            mode = cfg["mode"]
            n_horses = cfg.get("horses", 10)

            if mode == "top_n":
                # Harville確率が高い順にTop N
                all_probs = compute_all_trifecta_probs(model_probs, n_horses)
                n = cfg["n"]
                selected = all_probs[:n]
                tickets = [t for t, _ in selected]

            elif mode == "distortion":
                # Model/Market 歪み度が高い順
                distortions = compute_distortions(
                    model_probs, market_probs, n_horses)
                min_ratio = cfg["min_ratio"]
                max_tickets = cfg["max_tickets"]
                selected = [(t, mp, mkp, r) for t, mp, mkp, r in distortions
                            if r >= min_ratio][:max_tickets]
                tickets = [t for t, _, _, _ in selected]

            elif mode == "hybrid":
                # 歪み度 + 最低確率
                distortions = compute_distortions(
                    model_probs, market_probs, n_horses)
                min_ratio = cfg["min_ratio"]
                min_prob = cfg["min_prob_pct"] / 100.0
                max_tickets = cfg["max_tickets"]
                selected = [(t, mp, mkp, r) for t, mp, mkp, r in distortions
                            if r >= min_ratio and mp >= min_prob][:max_tickets]
                tickets = [t for t, _, _, _ in selected]
            else:
                continue

            if not tickets:
                continue

            sr = results[strat_name]
            sr.total_races += 1
            sr.total_tickets += len(tickets)
            sr.total_invested += len(tickets) * 100

            if month not in sr.monthly:
                sr.monthly[month] = {"races": 0, "tickets": 0, "invested": 0,
                                     "returned": 0, "hits": 0}
            m = sr.monthly[month]
            m["races"] += 1
            m["tickets"] += len(tickets)
            m["invested"] += len(tickets) * 100

            # 的中チェック
            for ticket in tickets:
                if ticket in payout_map:
                    pay = payout_map[ticket]
                    sr.total_hits += 1
                    sr.total_return += pay
                    m["hits"] += 1
                    m["returned"] += pay
                    sr.hit_details.append((race_id, ticket, pay))

    return results


# ===========================================================================
# Analysis: 的中レースでの distortion 分析
# ===========================================================================

def analyze_winning_distortions(cache: list, payouts: Dict[str, list]):
    """的中した三連単について、モデル vs 市場の歪み度を分析

    「もし歪み度ベースで選んでいたら当たっていたか？」を検証
    """
    print(f"\n{'='*90}")
    print(f"  的中組み合わせの Distortion 分析")
    print(f"{'='*90}")

    distortion_hits = []

    for race in cache:
        race_id = race["race_id"]
        entries = race.get("entries", [])
        if race.get("track_type") in ("obstacle", "steeplechase"):
            continue

        race_payouts = payouts.get(race_id)
        if not race_payouts:
            continue

        valid = [e for e in entries if (e.get("odds") or 0) > 0]
        if len(valid) < 5:
            continue

        model_probs = extract_win_probs(entries)
        market_probs = extract_market_probs(entries)

        if len(model_probs) < 5:
            continue

        for (k1, k2, k3), pay in race_payouts:
            p_model = harville_prob(model_probs, k1, k2, k3)
            p_market = harville_prob(market_probs, k1, k2, k3)
            if p_model > 0 and p_market > 0:
                ratio = p_model / p_market
                # モデル確率でのランク（上位何番目か）
                all_probs = compute_all_trifecta_probs(model_probs, 12)
                rank = 1
                for (t, _) in all_probs:
                    if t == (k1, k2, k3):
                        break
                    rank += 1
                distortion_hits.append({
                    "race_id": race_id,
                    "ticket": (k1, k2, k3),
                    "payout": pay,
                    "p_model": p_model,
                    "p_market": p_market,
                    "distortion": ratio,
                    "model_rank": rank,
                    "synthetic_ev": p_model * pay / 100,
                })

    if not distortion_hits:
        print("  データなし")
        return

    # 歪み度帯別の分析
    distortion_hits.sort(key=lambda x: -x["distortion"])

    bands = [
        (0, 0.5, "D<0.5 (市場>モデル)"),
        (0.5, 1.0, "D 0.5-1.0"),
        (1.0, 1.5, "D 1.0-1.5"),
        (1.5, 2.0, "D 1.5-2.0"),
        (2.0, 3.0, "D 2.0-3.0"),
        (3.0, 5.0, "D 3.0-5.0"),
        (5.0, 10.0, "D 5.0-10.0"),
        (10.0, float("inf"), "D 10.0+"),
    ]

    print(f"\n{'Band':<22} {'Count':>6} {'AvgPay':>8} {'AvgRank':>8} "
          f"{'AvgEV':>8} {'MedPay':>8}")
    print(f"{'-'*66}")

    for lo, hi, label in bands:
        hits = [h for h in distortion_hits if lo <= h["distortion"] < hi]
        if not hits:
            continue
        avg_pay = sum(h["payout"] for h in hits) / len(hits)
        avg_rank = sum(h["model_rank"] for h in hits) / len(hits)
        avg_ev = sum(h["synthetic_ev"] for h in hits) / len(hits)
        pays = sorted(h["payout"] for h in hits)
        med_pay = pays[len(pays) // 2]
        print(f"{label:<22} {len(hits):>6} {avg_pay:>8,.0f} {avg_rank:>8.1f} "
              f"{avg_ev:>8.2f} {med_pay:>8,}")

    # Model rank帯別
    print(f"\n{'='*90}")
    print(f"  的中組み合わせの Model Rank 分布")
    print(f"{'='*90}")

    rank_bands = [
        (1, 5, "Rank 1-5"),
        (6, 10, "Rank 6-10"),
        (11, 20, "Rank 11-20"),
        (21, 50, "Rank 21-50"),
        (51, 100, "Rank 51-100"),
        (101, 500, "Rank 101-500"),
        (501, 99999, "Rank 500+"),
    ]

    print(f"\n{'Band':<16} {'Count':>6} {'AvgPay':>8} {'AvgDist':>8} {'AvgEV':>8}")
    print(f"{'-'*50}")

    for lo, hi, label in rank_bands:
        hits = [h for h in distortion_hits if lo <= h["model_rank"] <= hi]
        if not hits:
            continue
        avg_pay = sum(h["payout"] for h in hits) / len(hits)
        avg_dist = sum(h["distortion"] for h in hits) / len(hits)
        avg_ev = sum(h["synthetic_ev"] for h in hits) / len(hits)
        print(f"{label:<16} {len(hits):>6} {avg_pay:>8,.0f} {avg_dist:>8.2f} {avg_ev:>8.2f}")

    # Synthetic EV 帯別
    print(f"\n{'='*90}")
    print(f"  的中組み合わせの Synthetic EV 分布")
    print(f"{'='*90}")

    ev_bands = [
        (0, 0.5, "EV<0.5"),
        (0.5, 1.0, "EV 0.5-1.0"),
        (1.0, 2.0, "EV 1.0-2.0"),
        (2.0, 5.0, "EV 2.0-5.0"),
        (5.0, 10.0, "EV 5.0-10.0"),
        (10.0, float("inf"), "EV 10.0+"),
    ]

    print(f"\n{'Band':<16} {'Count':>6} {'AvgPay':>8} {'AvgDist':>8} {'AvgRank':>8}")
    print(f"{'-'*52}")

    for lo, hi, label in ev_bands:
        hits = [h for h in distortion_hits if lo <= h["synthetic_ev"] < hi]
        if not hits:
            continue
        avg_pay = sum(h["payout"] for h in hits) / len(hits)
        avg_dist = sum(h["distortion"] for h in hits) / len(hits)
        avg_rank = sum(h["model_rank"] for h in hits) / len(hits)
        print(f"{label:<16} {len(hits):>6} {avg_pay:>8,.0f} {avg_dist:>8.2f} "
              f"{avg_rank:>8.1f}")

    # Top 20 高歪み的中
    print(f"\n{'='*90}")
    print(f"  Top 20 高歪み的中 (Distortion降順)")
    print(f"{'='*90}")
    for h in distortion_hits[:20]:
        t = h["ticket"]
        print(f"  {h['race_id']}  {t[0]:>2}-{t[1]:>2}-{t[2]:>2}  "
              f"Pay=¥{h['payout']:>8,}  Dist={h['distortion']:>6.2f}  "
              f"Rank={h['model_rank']:>4}  EV={h['synthetic_ev']:>6.2f}")


# ===========================================================================
# Output
# ===========================================================================

def print_summary(results: Dict[str, StrategyResult]):
    print(f"\n{'='*100}")
    print(f"  三連単 Synthetic EV バックテスト結果")
    print(f"{'='*100}")
    print(f"{'Strategy':<18} {'Races':>6} {'Tkts':>7} {'Avg':>5} {'Hits':>5} "
          f"{'HitR%':>6} {'Invested':>11} {'Return':>11} {'ROI%':>7} {'AvgPay':>9}")
    print(f"{'-'*100}")

    for name, sr in sorted(results.items(), key=lambda x: -x[1].roi):
        marker = " **" if sr.roi >= 100 else ""
        print(f"{name:<18} {sr.total_races:>6} {sr.total_tickets:>7} "
              f"{sr.avg_tickets:>5.1f} {sr.total_hits:>5} {sr.hit_rate_race:>5.1f}% "
              f"{sr.total_invested:>10,} {sr.total_return:>10,} "
              f"{sr.roi:>6.1f}%{marker} {sr.avg_payout:>8,}")

    print(f"{'-'*100}")
    print(f"  (**) = ROI >= 100%")


def print_monthly_detail(results: Dict[str, StrategyResult]):
    # ROIが高い上位3戦略のみ月次を表示
    top_strats = sorted(results.items(), key=lambda x: -x[1].roi)[:3]

    for name, sr in top_strats:
        if sr.total_races < 10:
            continue

        print(f"\n{'='*80}")
        print(f"  {name}  ROI {sr.roi:.1f}% (Avg {sr.avg_tickets:.1f}点/R)")
        print(f"{'='*80}")
        print(f"{'Month':>8} {'Races':>6} {'Tkts':>6} {'Hits':>5} "
              f"{'Invested':>10} {'Return':>10} {'ROI%':>7} {'P&L':>10}")
        print(f"{'-'*80}")

        for month in sorted(sr.monthly.keys()):
            m = sr.monthly[month]
            roi = m["returned"] / m["invested"] * 100 if m["invested"] else 0
            pnl = m["returned"] - m["invested"]
            print(f"{month:>8} {m['races']:>6} {m['tickets']:>6} {m['hits']:>5} "
                  f"{m['invested']:>9,} {m['returned']:>9,} {roi:>6.1f}% {pnl:>+9,}")

        print(f"{'-'*80}")
        pnl_total = sr.total_return - sr.total_invested
        print(f"{'TOTAL':>8} {sr.total_races:>6} {sr.total_tickets:>6} "
              f"{sr.total_hits:>5} {sr.total_invested:>9,} {sr.total_return:>9,} "
              f"{sr.roi:>6.1f}% {pnl_total:>+9,}")


def print_top_hits(results: Dict[str, StrategyResult]):
    all_hits = []
    for name, sr in results.items():
        for race_id, ticket, pay in sr.hit_details:
            all_hits.append((name, race_id, ticket, pay))

    if not all_hits:
        print("\n  的中なし")
        return

    # 重複排除（同じ的中が複数戦略にまたがる場合）
    unique = {}
    for name, race_id, ticket, pay in all_hits:
        key = (race_id, ticket)
        if key not in unique:
            unique[key] = []
        unique[key].append(name)

    print(f"\n{'='*90}")
    print(f"  Top 15 高配当的中")
    print(f"{'='*90}")

    sorted_hits = sorted(unique.items(), key=lambda x: -x[1][0] if False else
                         -next(pay for n, r, t, pay in all_hits
                               if (r, t) == x[0]))

    count = 0
    for (race_id, ticket), strat_names in sorted_hits:
        if count >= 15:
            break
        pay = next(p for n, r, t, p in all_hits if (r, t) == (race_id, ticket))
        strats = ", ".join(strat_names[:3])
        t = ticket
        print(f"  {race_id}  {t[0]:>2}-{t[1]:>2}-{t[2]:>2}  "
              f"¥{pay:>10,}  [{strats}]")
        count += 1


# ===========================================================================
# Main
# ===========================================================================

def main():
    print("=" * 90)
    print("  KeibaCICD 三連単 Synthetic EV バックテスト (Harville)")
    print("=" * 90)

    # 1. Load
    cache = load_backtest_cache()

    race_codes = [r["race_id"] for r in cache]
    print(f"[Load] 三連単 haraimodoshi...")
    payouts = load_sanrentan_payouts(race_codes)
    print(f"  三連単データ: {len(payouts):,}/{len(race_codes):,} races")

    # 2. Distortion analysis（的中した組み合わせの歪み度分析）
    analyze_winning_distortions(cache, payouts)

    # 3. Strategy backtest
    print(f"\n[Backtest] Running EV strategies...")
    results = run_ev_backtest(cache, payouts)

    # 4. Output
    print_summary(results)
    print_monthly_detail(results)
    print_top_hits(results)


if __name__ == "__main__":
    main()
