#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
三連単フォーメーション バックテストシミュレーション

backtest_cache.json × haraimodoshiテーブル（三連単実配当）で
複数のフォーメーション戦略をバックテスト検証する。

Usage:
    python -m ml.simulate_sanrentan              # 全パターン
    python -m ml.simulate_sanrentan --pattern B   # 特定パターンのみ
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set

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
    print(f"[Load] backtest_cache: {path}")
    with open(path, encoding="utf-8") as f:
        cache = json.load(f)
    print(f"  {len(cache):,} races")
    return cache


def load_sanrentan_payouts(race_codes: List[str]) -> Dict[str, list]:
    """haraimodoshiテーブルから三連単払戻データを取得

    Returns: {race_code: [((1着, 2着, 3着), 払戻金), ...]}
    """
    cols = ["RACE_CODE", "FUSEIRITSU_FLAG_SANRENTAN"]
    for i in range(1, 7):
        cols.extend([
            f"SANRENTAN{i}_KUMIBAN1",
            f"SANRENTAN{i}_KUMIBAN2",
            f"SANRENTAN{i}_KUMIBAN3",
            f"SANRENTAN{i}_HARAIMODOSHIKIN",
        ])

    col_str = ", ".join(cols)
    result = {}
    batch_size = 500

    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        for start in range(0, len(race_codes), batch_size):
            batch = race_codes[start:start + batch_size]
            placeholders = ",".join(["%s"] * len(batch))
            sql = f"SELECT {col_str} FROM haraimodoshi WHERE RACE_CODE IN ({placeholders})"
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
    """Parse int safely"""
    if not s:
        return 0
    try:
        return int(str(s).strip())
    except (ValueError, TypeError):
        return 0


# ===========================================================================
# Race-level metrics (computed from entries)
# ===========================================================================

def compute_race_confidence(entries: list) -> float:
    """P%のTop1-Top2 gapから自信度を計算 (0-100)"""
    p_vals = sorted([e.get("pred_proba_p_raw", 0) for e in entries], reverse=True)
    if len(p_vals) < 2:
        return 0
    gap = p_vals[0] - p_vals[1]
    # gap 0.05 = 50, gap 0.10 = 100, linear scale
    return min(100, gap * 1000)


def has_danger_horse(entries: list) -> bool:
    """危険馬（人気だがARd低い）がいるか"""
    for e in entries:
        odds = e.get("odds", 999)
        ard = e.get("ar_deviation", 99)
        if 0 < odds <= 8 and ard < 53:
            return True
    return False


def get_top1_ard(entries: list) -> float:
    """ARd 1位の値"""
    ards = [e.get("ar_deviation", 0) for e in entries if e.get("odds", 0) > 0]
    return max(ards) if ards else 0


def count_runners(entries: list) -> int:
    """有効出走頭数"""
    return sum(1 for e in entries if e.get("odds", 0) > 0)


# ===========================================================================
# Horse selection helpers
# ===========================================================================

def by_rank_w(entries: list, top_n: int) -> List[int]:
    """Wモデル順位 top N の馬番"""
    valid = [e for e in entries if e.get("odds", 0) > 0]
    ranked = sorted(valid, key=lambda e: e.get("rank_w", 99))
    return [e["umaban"] for e in ranked[:top_n]]


def by_rank_p(entries: list, top_n: int) -> List[int]:
    """Pモデル順位 top N の馬番"""
    valid = [e for e in entries if e.get("odds", 0) > 0]
    ranked = sorted(valid, key=lambda e: e.get("rank_p", 99))
    return [e["umaban"] for e in ranked[:top_n]]


def by_ard(entries: list, min_ard: float = 0, top_n: int = 99) -> List[int]:
    """ARd閾値以上の馬番（ARd降順）"""
    valid = [e for e in entries
             if e.get("odds", 0) > 0 and e.get("ar_deviation", 0) >= min_ard]
    ranked = sorted(valid, key=lambda e: -e.get("ar_deviation", 0))
    return [e["umaban"] for e in ranked[:top_n]]


def by_ard_ev(entries: list, min_ard: float, min_ev: float, top_n: int = 99) -> List[int]:
    """ARd + EV フィルタ"""
    valid = [e for e in entries
             if e.get("odds", 0) > 0
             and (e.get("ar_deviation") or 0) >= min_ard
             and (e.get("win_ev") or 0) >= min_ev]
    ranked = sorted(valid, key=lambda e: -e.get("ar_deviation", 0))
    return [e["umaban"] for e in ranked[:top_n]]


def by_vb(entries: list, min_gap: int = 3, min_ev: float = 1.0) -> List[int]:
    """VB候補（gap & EV）"""
    valid = [e for e in entries
             if e.get("odds", 0) > 0
             and e.get("vb_gap", 0) >= min_gap
             and e.get("win_ev", 0) >= min_ev]
    return [e["umaban"] for e in sorted(valid, key=lambda e: -e.get("ar_deviation", 0))]


def exclude_danger(entries: list, umabans: List[int]) -> List[int]:
    """危険馬を除外"""
    danger = set()
    for e in entries:
        odds = e.get("odds", 999)
        ard = e.get("ar_deviation", 99)
        if 0 < odds <= 8 and ard < 53:
            danger.add(e["umaban"])
    return [u for u in umabans if u not in danger]


# ===========================================================================
# Formation ticket generation
# ===========================================================================

def generate_formation_tickets(leg1: List[int], leg2: List[int], leg3: List[int]) -> List[Tuple[int, int, int]]:
    """フォーメーション買い目生成（1着-2着-3着、同一馬は除外）"""
    tickets = []
    seen = set()
    for a in leg1:
        for b in leg2:
            if b == a:
                continue
            for c in leg3:
                if c == a or c == b:
                    continue
                key = (a, b, c)
                if key not in seen:
                    seen.add(key)
                    tickets.append(key)
    return tickets


# ===========================================================================
# Strategy definitions
# ===========================================================================

@dataclass
class SanrentanStrategy:
    name: str
    description: str

    # レースフィルタ
    min_confidence: float = 0       # 自信度下限
    min_runners: int = 0            # 最小出走頭数
    max_runners: int = 99           # 最大出走頭数
    require_danger: bool = False    # 危険馬レースのみ
    min_top1_ard: float = 0         # ARd1位の最低値
    max_tickets: int = 30           # 点数上限（超えたらスキップ）

    # 各脚の選択ルール
    # leg_spec: (method, kwargs)
    # method: "rank_w", "rank_p", "ard", "ard_ev", "vb", "union"
    leg1_specs: list = field(default_factory=list)
    leg2_specs: list = field(default_factory=list)
    leg3_specs: list = field(default_factory=list)

    def select_horses(self, entries: list) -> Tuple[List[int], List[int], List[int]]:
        """各脚の馬番リストを返す"""
        leg1 = self._resolve_specs(self.leg1_specs, entries)
        leg2 = self._resolve_specs(self.leg2_specs, entries)
        leg3 = self._resolve_specs(self.leg3_specs, entries)
        return leg1, leg2, leg3

    def _resolve_specs(self, specs: list, entries: list) -> List[int]:
        result = []
        seen = set()
        for method, kwargs in specs:
            if method == "rank_w":
                horses = by_rank_w(entries, **kwargs)
            elif method == "rank_p":
                horses = by_rank_p(entries, **kwargs)
            elif method == "ard":
                horses = by_ard(entries, **kwargs)
            elif method == "ard_ev":
                horses = by_ard_ev(entries, **kwargs)
            elif method == "vb":
                horses = by_vb(entries, **kwargs)
            else:
                horses = []
            for h in horses:
                if h not in seen:
                    seen.add(h)
                    result.append(h)
        return result

    def passes_race_filter(self, race: dict, entries: list) -> bool:
        if self.min_confidence > 0:
            conf = compute_race_confidence(entries)
            if conf < self.min_confidence:
                return False
        if self.require_danger and not has_danger_horse(entries):
            return False
        if self.min_top1_ard > 0:
            if get_top1_ard(entries) < self.min_top1_ard:
                return False
        runners = count_runners(entries)
        if runners < self.min_runners or runners > self.max_runners:
            return False
        return True


# ---------------------------------------------------------------------------
# Define patterns
# ---------------------------------------------------------------------------

STRATEGIES: Dict[str, SanrentanStrategy] = {}


def _register(s: SanrentanStrategy):
    STRATEGIES[s.name] = s


# --- A: 堅め ---
_register(SanrentanStrategy(
    name="A.堅め",
    description="W1位→P1-2位→ARd≥55&EV≥1.5 (自信度60+)",
    min_confidence=60,
    max_tickets=12,
    leg1_specs=[("rank_w", {"top_n": 1})],
    leg2_specs=[("rank_p", {"top_n": 2})],
    leg3_specs=[("ard_ev", {"min_ard": 55, "min_ev": 1.5, "top_n": 5})],
))

# --- B: 標準（ユーザー提案） ---
_register(SanrentanStrategy(
    name="B.標準",
    description="W1位→P1-3位→ARd≥50&EV≥1.3 (自信度60+)",
    min_confidence=60,
    max_tickets=18,
    leg1_specs=[("rank_w", {"top_n": 1})],
    leg2_specs=[("rank_p", {"top_n": 3})],
    leg3_specs=[("ard_ev", {"min_ard": 50, "min_ev": 1.3, "top_n": 6})],
))

# --- C: 広め ---
_register(SanrentanStrategy(
    name="C.広め",
    description="W1-2位→P1-3位→ARd≥45&EV≥1.0",
    min_confidence=40,
    max_tickets=30,
    leg1_specs=[("rank_w", {"top_n": 2})],
    leg2_specs=[("rank_p", {"top_n": 3})],
    leg3_specs=[("ard_ev", {"min_ard": 45, "min_ev": 1.0, "top_n": 8})],
))

# --- D: VB特化 ---
_register(SanrentanStrategy(
    name="D.VB特化",
    description="VB馬→ARd Top3→P1-5位",
    min_confidence=0,
    max_tickets=20,
    leg1_specs=[("vb", {"min_gap": 4, "min_ev": 1.5})],
    leg2_specs=[("ard", {"min_ard": 50, "top_n": 3})],
    leg3_specs=[("rank_p", {"top_n": 5})],
))

# --- E: 危険馬消し ---
_register(SanrentanStrategy(
    name="E.危険消し",
    description="W1位→P Top3(危険馬除外)→ARd≥50 (危険馬レースのみ)",
    require_danger=True,
    min_confidence=40,
    max_tickets=18,
    leg1_specs=[("rank_w", {"top_n": 1})],
    leg2_specs=[("rank_p", {"top_n": 4})],  # 危険馬除外で減る想定
    leg3_specs=[("ard_ev", {"min_ard": 50, "min_ev": 1.0, "top_n": 6})],
))

# --- F: ARd軸 一点集中 ---
_register(SanrentanStrategy(
    name="F.ARd軸",
    description="ARd1位→W1-2位→P1-3位 (ARd65+, 自信度50+)",
    min_confidence=50,
    min_top1_ard=65,
    max_tickets=12,
    leg1_specs=[("ard", {"min_ard": 65, "top_n": 1})],
    leg2_specs=[("rank_w", {"top_n": 2})],
    leg3_specs=[("rank_p", {"top_n": 3})],
))

# --- G: 高自信度のみ ---
_register(SanrentanStrategy(
    name="G.高自信度",
    description="W1位→P1-2位→ARd≥50 (自信度80+, 少数精鋭)",
    min_confidence=80,
    max_tickets=10,
    leg1_specs=[("rank_w", {"top_n": 1})],
    leg2_specs=[("rank_p", {"top_n": 2})],
    leg3_specs=[("ard", {"min_ard": 50, "top_n": 4})],
))

# --- H: W×P一致軸 ---
_register(SanrentanStrategy(
    name="H.WP一致軸",
    description="W1位(=P1位一致時)→P2-3位→ARd≥45 (モデル一致で堅い)",
    min_confidence=50,
    max_tickets=15,
    leg1_specs=[("rank_w", {"top_n": 1})],  # pass_filterでW1=P1チェック
    leg2_specs=[("rank_p", {"top_n": 3})],
    leg3_specs=[("ard_ev", {"min_ard": 45, "min_ev": 1.0, "top_n": 6})],
))


# ===========================================================================
# Backtest engine
# ===========================================================================

@dataclass
class StratResult:
    name: str
    total_races: int = 0
    total_tickets: int = 0
    total_invested: int = 0
    total_return: int = 0
    total_hits: int = 0
    monthly: dict = field(default_factory=dict)
    hit_payouts: list = field(default_factory=list)

    @property
    def hit_rate(self) -> float:
        return self.total_hits / self.total_races * 100 if self.total_races else 0

    @property
    def ticket_hit_rate(self) -> float:
        return self.total_hits / self.total_tickets * 100 if self.total_tickets else 0

    @property
    def roi(self) -> float:
        return self.total_return / self.total_invested * 100 if self.total_invested else 0

    @property
    def avg_payout(self) -> int:
        return self.total_return // self.total_hits if self.total_hits else 0

    @property
    def avg_tickets_per_race(self) -> float:
        return self.total_tickets / self.total_races if self.total_races else 0


def run_backtest(cache: list, payouts: Dict[str, list],
                 strategies: Dict[str, SanrentanStrategy]) -> Dict[str, StratResult]:
    results = {name: StratResult(name=name) for name in strategies}

    for race in cache:
        race_id = race["race_id"]
        entries = race.get("entries", [])

        # 障害レーススキップ
        if race.get("track_type") in ("obstacle", "steeplechase"):
            continue

        race_payouts = payouts.get(race_id)
        if not race_payouts:
            continue

        month = f"{race_id[:4]}-{race_id[4:6]}"

        for name, strat in strategies.items():
            # レースフィルタ
            if not strat.passes_race_filter(race, entries):
                continue

            # H: WP一致チェック
            if name == "H.WP一致軸":
                w1 = by_rank_w(entries, 1)
                p1 = by_rank_p(entries, 1)
                if not w1 or not p1 or w1[0] != p1[0]:
                    continue

            # E: 危険馬除外をleg2に適用
            leg1, leg2, leg3 = strat.select_horses(entries)
            if name == "E.危険消し":
                leg2 = exclude_danger(entries, leg2)

            if not leg1 or not leg2 or not leg3:
                continue

            tickets = generate_formation_tickets(leg1, leg2, leg3)
            if not tickets or len(tickets) > strat.max_tickets:
                continue

            sr = results[name]
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
                for (k1, k2, k3), pay in race_payouts:
                    if ticket == (k1, k2, k3):
                        sr.total_hits += 1
                        sr.total_return += pay
                        m["hits"] += 1
                        m["returned"] += pay
                        sr.hit_payouts.append((race_id, ticket, pay))
                        break

    return results


# ===========================================================================
# Output
# ===========================================================================

def print_summary(results: Dict[str, StratResult], strategies: Dict[str, SanrentanStrategy]):
    print(f"\n{'='*100}")
    print(f"  三連単フォーメーション バックテスト結果")
    print(f"{'='*100}")
    print(f"{'Strategy':<14} {'Description':<36} {'Races':>6} {'Tkts':>6} {'Avg':>4} "
          f"{'Hits':>4} {'HitR%':>6} {'Invested':>10} {'Return':>10} {'ROI%':>7} {'AvgPay':>8}")
    print(f"{'-'*100}")

    for name, sr in results.items():
        desc = strategies[name].description[:35]
        marker = " **" if sr.roi >= 100 else ""
        print(f"{name:<14} {desc:<36} {sr.total_races:>6} {sr.total_tickets:>6} "
              f"{sr.avg_tickets_per_race:>4.1f} {sr.total_hits:>4} {sr.hit_rate:>5.1f}% "
              f"{sr.total_invested:>9,} {sr.total_return:>9,} {sr.roi:>6.1f}%{marker} "
              f"{sr.avg_payout:>7,}")

    print(f"{'-'*100}")
    print(f"  (**) = ROI >= 100%")
    print(f"  HitR% = レース的中率（少なくとも1点当たったレース/参加レース数）")
    print(f"  Avg = 平均点数/レース")


def print_monthly(results: Dict[str, StratResult]):
    for name, sr in results.items():
        if sr.total_races < 20:
            continue

        print(f"\n{'='*80}")
        print(f"  {name}  ROI {sr.roi:.1f}%  (レース的中率 {sr.hit_rate:.1f}%)")
        print(f"{'='*80}")
        print(f"{'Month':>8} {'Races':>6} {'Tkts':>6} {'Hits':>5} "
              f"{'Invested':>10} {'Return':>10} {'ROI%':>7} {'P&L':>10}")
        print(f"{'-'*80}")

        cum_pnl = 0
        for month in sorted(sr.monthly.keys()):
            m = sr.monthly[month]
            roi = m["returned"] / m["invested"] * 100 if m["invested"] else 0
            pnl = m["returned"] - m["invested"]
            cum_pnl += pnl
            print(f"{month:>8} {m['races']:>6} {m['tickets']:>6} {m['hits']:>5} "
                  f"{m['invested']:>9,} {m['returned']:>9,} {roi:>6.1f}% {pnl:>+9,}")
        print(f"{'-'*80}")
        print(f"{'TOTAL':>8} {sr.total_races:>6} {sr.total_tickets:>6} {sr.total_hits:>5} "
              f"{sr.total_invested:>9,} {sr.total_return:>9,} {sr.roi:>6.1f}% "
              f"{sr.total_return - sr.total_invested:>+9,}")


def print_top_hits(results: Dict[str, StratResult]):
    all_hits = []
    for name, sr in results.items():
        for race_id, ticket, pay in sr.hit_payouts:
            all_hits.append((name, race_id, ticket, pay))

    if not all_hits:
        print("\n  的中なし")
        return

    all_hits.sort(key=lambda x: -x[3])
    print(f"\n{'='*80}")
    print(f"  Top 20 高配当的中")
    print(f"{'='*80}")
    for name, race_id, ticket, pay in all_hits[:20]:
        t_str = f"{ticket[0]}-{ticket[1]}-{ticket[2]}"
        print(f"  {name:<14} {race_id}  {t_str:>8}  ¥{pay:>10,}")

    print(f"\n  的中数合計: {len(all_hits)} / 平均配当: ¥{sum(x[3] for x in all_hits)//len(all_hits):,}")


def print_payout_distribution(results: Dict[str, StratResult]):
    """配当帯別の的中分布"""
    all_pays = []
    for sr in results.values():
        for _, _, pay in sr.hit_payouts:
            all_pays.append(pay)

    if not all_pays:
        return

    bands = [
        (0, 5000, "~5千"),
        (5000, 10000, "5千~1万"),
        (10000, 30000, "1万~3万"),
        (30000, 100000, "3万~10万"),
        (100000, 500000, "10万~50万"),
        (500000, float('inf'), "50万~"),
    ]

    print(f"\n{'='*50}")
    print(f"  三連単配当帯分布（全戦略合計）")
    print(f"{'='*50}")
    for lo, hi, label in bands:
        cnt = sum(1 for p in all_pays if lo <= p < hi)
        total = sum(p for p in all_pays if lo <= p < hi)
        if cnt:
            print(f"  {label:<12} {cnt:>4}件  合計 ¥{total:>10,}")


# ===========================================================================
# Main
# ===========================================================================

def main():
    args = sys.argv[1:]

    # パターン指定
    pattern_filter = None
    if "--pattern" in args:
        idx = args.index("--pattern")
        if idx + 1 < len(args):
            pattern_filter = args[idx + 1].upper()

    print("=" * 80)
    print("  KeibaCICD 三連単フォーメーション バックテスト")
    print("=" * 80)

    # 1. Load cache
    cache = load_backtest_cache()

    # 2. Load sanrentan payouts
    race_codes = [r["race_id"] for r in cache]
    print(f"\n[Load] 三連単 haraimodoshi from MySQL...")
    payouts = load_sanrentan_payouts(race_codes)
    print(f"  三連単データ: {len(payouts):,}/{len(race_codes):,} races")

    # 3. Filter strategies
    strats = STRATEGIES
    if pattern_filter:
        strats = {k: v for k, v in STRATEGIES.items() if k.startswith(pattern_filter)}
        if not strats:
            print(f"  [Error] Pattern '{pattern_filter}' not found. Available: {list(STRATEGIES.keys())}")
            return
    print(f"\n[Simulate] Running {len(strats)} strategies...")

    # 4. Run
    results = run_backtest(cache, payouts, strats)

    # 5. Output
    print_summary(results, strats)
    print_monthly(results)
    print_top_hits(results)
    print_payout_distribution(results)


if __name__ == "__main__":
    main()
