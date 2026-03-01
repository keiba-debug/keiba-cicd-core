#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
馬連・ワイド・馬単・三連複バックテストシミュレーション + 当日推奨

backtest_cache.json（ML予測+着順）× haraimodoshiテーブル（実配当）で
複数の券種戦略をバックテスト検証する。
--today で当日predictions.jsonから買い目推奨を出力。

Usage:
    python -m ml.simulate_multi_leg           # バックテスト
    python -m ml.simulate_multi_leg --today   # 当日推奨
"""

import json
import sys
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Dict, List, Optional, Tuple

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config
from core.db import get_connection


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_backtest_cache() -> list:
    path = config.ml_dir() / "backtest_cache.json"
    print(f"[Load] backtest_cache: {path}")
    with open(path, encoding="utf-8") as f:
        cache = json.load(f)
    print(f"  {len(cache):,} races")
    return cache


def load_haraimodoshi(race_codes: List[str]) -> Dict[str, dict]:
    """haraimodoshiテーブルから払戻データを一括取得"""

    # 必要カラム
    cols = ["RACE_CODE"]
    # 不成立フラグ
    for bt in ("UMAREN", "WIDE", "UMATAN", "SANRENPUKU"):
        cols.append(f"FUSEIRITSU_FLAG_{bt}")
    # 馬連 1-3
    for i in range(1, 4):
        cols.extend([f"UMAREN{i}_KUMIBAN1", f"UMAREN{i}_KUMIBAN2",
                     f"UMAREN{i}_HARAIMODOSHIKIN"])
    # ワイド 1-7
    for i in range(1, 8):
        cols.extend([f"WIDE{i}_KUMIBAN1", f"WIDE{i}_KUMIBAN2",
                     f"WIDE{i}_HARAIMODOSHIKIN"])
    # 馬単 1-6
    for i in range(1, 7):
        cols.extend([f"UMATAN{i}_KUMIBAN1", f"UMATAN{i}_KUMIBAN2",
                     f"UMATAN{i}_HARAIMODOSHIKIN"])
    # 三連複 1-3
    for i in range(1, 4):
        cols.extend([f"SANRENPUKU{i}_KUMIBAN1", f"SANRENPUKU{i}_KUMIBAN2",
                     f"SANRENPUKU{i}_KUMIBAN3", f"SANRENPUKU{i}_HARAIMODOSHIKIN"])

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
                result[rc] = _parse_haraimodoshi_row(row)
        cur.close()

    return result


def _parse_int(s: str) -> int:
    if not s or not s.strip():
        return 0
    try:
        return int(s)
    except (ValueError, TypeError):
        return 0


def _parse_haraimodoshi_row(row: dict) -> dict:
    """haraimodoshi行を構造化payoutデータに変換"""
    payouts = {
        "umaren": [],       # [(frozenset({a,b}), yen), ...]
        "wide": [],         # [(frozenset({a,b}), yen), ...]
        "umatan": [],       # [((1st, 2nd), yen), ...]
        "sanrenpuku": [],   # [(frozenset({a,b,c}), yen), ...]
        "flags": {},
    }

    for bt in ("UMAREN", "WIDE", "UMATAN", "SANRENPUKU"):
        payouts["flags"][bt] = (row.get(f"FUSEIRITSU_FLAG_{bt}", "0") == "1")

    # 馬連 (順不同)
    for i in range(1, 4):
        k1 = _parse_int(row.get(f"UMAREN{i}_KUMIBAN1", ""))
        k2 = _parse_int(row.get(f"UMAREN{i}_KUMIBAN2", ""))
        pay = _parse_int(row.get(f"UMAREN{i}_HARAIMODOSHIKIN", ""))
        if k1 and k2 and pay:
            payouts["umaren"].append((frozenset({k1, k2}), pay))

    # ワイド (順不同)
    for i in range(1, 8):
        k1 = _parse_int(row.get(f"WIDE{i}_KUMIBAN1", ""))
        k2 = _parse_int(row.get(f"WIDE{i}_KUMIBAN2", ""))
        pay = _parse_int(row.get(f"WIDE{i}_HARAIMODOSHIKIN", ""))
        if k1 and k2 and pay:
            payouts["wide"].append((frozenset({k1, k2}), pay))

    # 馬単 (順序あり: KUMIBAN1=1着, KUMIBAN2=2着)
    for i in range(1, 7):
        k1 = _parse_int(row.get(f"UMATAN{i}_KUMIBAN1", ""))
        k2 = _parse_int(row.get(f"UMATAN{i}_KUMIBAN2", ""))
        pay = _parse_int(row.get(f"UMATAN{i}_HARAIMODOSHIKIN", ""))
        if k1 and k2 and pay:
            payouts["umatan"].append(((k1, k2), pay))

    # 三連複 (順不同)
    for i in range(1, 4):
        k1 = _parse_int(row.get(f"SANRENPUKU{i}_KUMIBAN1", ""))
        k2 = _parse_int(row.get(f"SANRENPUKU{i}_KUMIBAN2", ""))
        k3 = _parse_int(row.get(f"SANRENPUKU{i}_KUMIBAN3", ""))
        pay = _parse_int(row.get(f"SANRENPUKU{i}_HARAIMODOSHIKIN", ""))
        if k1 and k2 and k3 and pay:
            payouts["sanrenpuku"].append((frozenset({k1, k2, k3}), pay))

    return payouts


# ---------------------------------------------------------------------------
# Horse selection helpers
# ---------------------------------------------------------------------------

def get_ard_top_n(entries: list, n: int) -> list:
    """ARd降順でtop N（odds=0の出走取消馬は除外）"""
    valid = [e for e in entries if e.get("ar_deviation", 0) > 0
             and e.get("odds", 0) > 0]
    return sorted(valid, key=lambda e: -e.get("ar_deviation", 0))[:n]


def get_danger_horses(entries: list) -> set:
    """危険馬のumaban集合（odds<=8 & ARd<53 & V%<15%）"""
    danger = set()
    for e in entries:
        odds = e.get("odds", 999)
        ard = e.get("ar_deviation", 99)
        v_pct = e.get("pred_proba_p_raw", 1.0)
        if 0 < odds <= 8 and ard < 53 and v_pct < 0.15:
            danger.add(e["umaban"])
    return danger


def get_vb_candidates(entries: list) -> list:
    """aggressiveプリセット相当のVB候補判定（簡易インライン版）"""
    v_pcts = [e.get("pred_proba_p_raw", 0) for e in entries]
    race_max_v = max(v_pcts) if v_pcts else 0

    candidates = []
    for e in entries:
        ard = e.get("ar_deviation", 0)
        gap = e.get("vb_gap", 0)
        win_ev = e.get("win_ev", 0)
        odds = e.get("odds", 0)
        v_pct = e.get("pred_proba_p_raw", 0)

        # ARd VBルート（独立バイパス）
        if ard >= 65 and odds >= 10:
            candidates.append(e)
            continue

        # V%比率チェック
        v_ratio = v_pct / race_max_v if race_max_v > 0 else 0
        if v_ratio < 0.75:
            if not (gap >= 7 and win_ev >= 3.0):
                continue

        # ARd gap tiers
        if ard >= 65 and gap >= 3:
            pass
        elif ard >= 55 and gap >= 4:
            pass
        elif ard >= 45 and gap >= 5:
            pass
        else:
            continue

        # EV >= 1.8 (aggressive)
        if win_ev < 1.8:
            continue

        candidates.append(e)

    return candidates


# ---------------------------------------------------------------------------
# Payout matching helpers
# ---------------------------------------------------------------------------

def _match_umaren(payouts: dict, pair: frozenset) -> int:
    for combo, pay in payouts.get("umaren", []):
        if combo == pair:
            return pay
    return 0


def _match_wide(payouts: dict, pair: frozenset) -> int:
    for combo, pay in payouts.get("wide", []):
        if combo == pair:
            return pay
    return 0


def _match_umatan(payouts: dict, ticket: tuple) -> int:
    for (first, second), pay in payouts.get("umatan", []):
        if first == ticket[0] and second == ticket[1]:
            return pay
    return 0


def _match_sanrenpuku(payouts: dict, trio: frozenset) -> int:
    for combo, pay in payouts.get("sanrenpuku", []):
        if combo == trio:
            return pay
    return 0


# ---------------------------------------------------------------------------
# Strategy evaluation
# ---------------------------------------------------------------------------

@dataclass
class BetResult:
    race_id: str
    ticket_type: str
    horses: tuple
    cost: int
    payout: int
    hit: bool


def evaluate_A(race: dict, payouts: dict) -> list:
    """A: 馬単流し ARd Top1 → Top2-5"""
    if payouts["flags"].get("UMATAN"):
        return []
    top5 = get_ard_top_n(race["entries"], 5)
    if len(top5) < 2:
        return []
    axis = top5[0]["umaban"]
    results = []
    for t in top5[1:]:
        ticket = (axis, t["umaban"])
        pay = _match_umatan(payouts, ticket)
        results.append(BetResult(race["race_id"], "umatan", ticket, 100, pay, pay > 0))
    return results


def evaluate_B(race: dict, payouts: dict) -> list:
    """B: 馬連BOX ARd Top2"""
    if payouts["flags"].get("UMAREN"):
        return []
    top2 = get_ard_top_n(race["entries"], 2)
    if len(top2) < 2:
        return []
    pair = frozenset({top2[0]["umaban"], top2[1]["umaban"]})
    pay = _match_umaren(payouts, pair)
    return [BetResult(race["race_id"], "umaren", tuple(sorted(pair)), 100, pay, pay > 0)]


def evaluate_C(race: dict, payouts: dict) -> list:
    """C: ワイドBOX VB候補+ARd Top3"""
    if payouts["flags"].get("WIDE"):
        return []
    ard_top3 = get_ard_top_n(race["entries"], 3)
    vb_cands = get_vb_candidates(race["entries"])
    horse_set = set()
    for e in ard_top3 + vb_cands:
        horse_set.add(e["umaban"])
    horses = sorted(horse_set)
    if len(horses) < 2:
        return []
    results = []
    for a, b in combinations(horses, 2):
        pair = frozenset({a, b})
        pay = _match_wide(payouts, pair)
        results.append(BetResult(race["race_id"], "wide", (a, b), 100, pay, pay > 0))
    return results


def evaluate_D(race: dict, payouts: dict) -> list:
    """D: 馬連流し ARd Top1 → 危険馬消し残りTop4"""
    if payouts["flags"].get("UMAREN"):
        return []
    entries = race["entries"]
    danger = get_danger_horses(entries)
    ard_sorted = get_ard_top_n(entries, 99)
    if not ard_sorted:
        return []
    axis = ard_sorted[0]
    targets = [e for e in ard_sorted[1:] if e["umaban"] not in danger][:4]
    results = []
    for t in targets:
        pair = frozenset({axis["umaban"], t["umaban"]})
        pay = _match_umaren(payouts, pair)
        results.append(BetResult(race["race_id"], "umaren", tuple(sorted(pair)), 100, pay, pay > 0))
    return results


def evaluate_E(race: dict, payouts: dict) -> list:
    """E: 一点勝負 馬単 ARd Top1→Top2"""
    if payouts["flags"].get("UMATAN"):
        return []
    top2 = get_ard_top_n(race["entries"], 2)
    if len(top2) < 2:
        return []
    ticket = (top2[0]["umaban"], top2[1]["umaban"])
    pay = _match_umatan(payouts, ticket)
    return [BetResult(race["race_id"], "umatan", ticket, 100, pay, pay > 0)]


def evaluate_F(race: dict, payouts: dict) -> list:
    """F: 三連複 ARd Top3 BOX"""
    if payouts["flags"].get("SANRENPUKU"):
        return []
    top3 = get_ard_top_n(race["entries"], 3)
    if len(top3) < 3:
        return []
    trio = frozenset({e["umaban"] for e in top3})
    pay = _match_sanrenpuku(payouts, trio)
    return [BetResult(race["race_id"], "sanrenpuku", tuple(sorted(trio)), 100, pay, pay > 0)]


# ---------------------------------------------------------------------------
# VBレース限定戦略（単勝VBの補完・保険）
# ---------------------------------------------------------------------------

def evaluate_G(race: dict, payouts: dict) -> list:
    """G: VBレース馬単ボーナス — VB馬→ARd Top2-3 馬単流し

    単勝VBが勝てば単勝+馬単ダブル回収。
    VBが出ているレースのみ発動。軸=VB馬、相手=ARd上位。
    """
    if payouts["flags"].get("UMATAN"):
        return []
    vb = get_vb_candidates(race["entries"])
    if not vb:
        return []
    ard_sorted = get_ard_top_n(race["entries"], 5)
    vb_umabans = {e["umaban"] for e in vb}

    results = []
    for v in vb:
        # 相手 = ARd上位からVB馬自身を除いた2-3頭
        targets = [e for e in ard_sorted if e["umaban"] != v["umaban"]][:3]
        for t in targets:
            ticket = (v["umaban"], t["umaban"])
            pay = _match_umatan(payouts, ticket)
            results.append(BetResult(race["race_id"], "umatan", ticket, 100, pay, pay > 0))
    return results


def evaluate_H(race: dict, payouts: dict) -> list:
    """H: VBレース馬連保険 — VB馬×ARd Top2-3 馬連

    VB馬が2着でも回収。VBレースのみ発動。
    """
    if payouts["flags"].get("UMAREN"):
        return []
    vb = get_vb_candidates(race["entries"])
    if not vb:
        return []
    ard_sorted = get_ard_top_n(race["entries"], 5)

    results = []
    seen_pairs = set()
    for v in vb:
        targets = [e for e in ard_sorted if e["umaban"] != v["umaban"]][:3]
        for t in targets:
            pair = frozenset({v["umaban"], t["umaban"]})
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            pay = _match_umaren(payouts, pair)
            results.append(BetResult(race["race_id"], "umaren", tuple(sorted(pair)), 100, pay, pay > 0))
    return results


def evaluate_I(race: dict, payouts: dict) -> list:
    """I: VBレース馬単一点 — VB馬(最強)→ARd Top1 馬単

    VB馬のうち最もARdが高い1頭→ARd全体Top1（VB馬除く）に一点。
    """
    if payouts["flags"].get("UMATAN"):
        return []
    vb = get_vb_candidates(race["entries"])
    if not vb:
        return []
    # VB馬のうちARd最高
    axis = max(vb, key=lambda e: e.get("ar_deviation", 0))
    # ARd Top1でVB馬以外
    ard_sorted = get_ard_top_n(race["entries"], 5)
    target = None
    for e in ard_sorted:
        if e["umaban"] != axis["umaban"]:
            target = e
            break
    if not target:
        return []
    ticket = (axis["umaban"], target["umaban"])
    pay = _match_umatan(payouts, ticket)
    return [BetResult(race["race_id"], "umatan", ticket, 100, pay, pay > 0)]


def evaluate_J(race: dict, payouts: dict) -> list:
    """J: VBレース馬連一点 — VB馬(最強)×ARd Top1 馬連

    Iの馬連版。2着でも救済。
    """
    if payouts["flags"].get("UMAREN"):
        return []
    vb = get_vb_candidates(race["entries"])
    if not vb:
        return []
    axis = max(vb, key=lambda e: e.get("ar_deviation", 0))
    ard_sorted = get_ard_top_n(race["entries"], 5)
    target = None
    for e in ard_sorted:
        if e["umaban"] != axis["umaban"]:
            target = e
            break
    if not target:
        return []
    pair = frozenset({axis["umaban"], target["umaban"]})
    pay = _match_umaren(payouts, pair)
    return [BetResult(race["race_id"], "umaren", tuple(sorted(pair)), 100, pay, pay > 0)]


def evaluate_K(race: dict, payouts: dict) -> list:
    """K: 危険馬裏目ワイド — 危険馬レースでARd Top2のワイド

    危険馬がいるレース = 人気馬が危ない = 配当が跳ねやすい。
    危険馬を無視してARd上位2頭のワイドで拾う。
    """
    if payouts["flags"].get("WIDE"):
        return []
    danger = get_danger_horses(race["entries"])
    if not danger:
        return []
    # 危険馬を除外したARd Top2
    ard_sorted = get_ard_top_n(race["entries"], 99)
    non_danger = [e for e in ard_sorted if e["umaban"] not in danger][:3]
    if len(non_danger) < 2:
        return []
    results = []
    for a, b in combinations([e["umaban"] for e in non_danger], 2):
        pair = frozenset({a, b})
        pay = _match_wide(payouts, pair)
        results.append(BetResult(race["race_id"], "wide", (a, b), 100, pay, pay > 0))
    return results


STRATEGIES = {
    # --- 全レース戦略 ---
    "A.馬単流し":     evaluate_A,
    "B.馬連Top2":     evaluate_B,
    "C.ワイドVB":     evaluate_C,
    "D.馬連-危険消":  evaluate_D,
    "E.一点馬単":     evaluate_E,
    "F.三連複Top3":   evaluate_F,
    # --- VBレース限定戦略 ---
    "G.VB馬単流":     evaluate_G,
    "H.VB馬連保険":   evaluate_H,
    "I.VB馬単1点":    evaluate_I,
    "J.VB馬連1点":    evaluate_J,
    "K.危険裏ワイド":  evaluate_K,
}


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

@dataclass
class StrategyStats:
    name: str
    total_races: int = 0
    total_bets: int = 0
    total_hits: int = 0
    total_invested: int = 0
    total_return: int = 0
    monthly: dict = field(default_factory=dict)
    top_hits: list = field(default_factory=list)

    @property
    def hit_rate(self) -> float:
        return self.total_hits / self.total_bets * 100 if self.total_bets else 0

    @property
    def roi(self) -> float:
        return self.total_return / self.total_invested * 100 if self.total_invested else 0

    @property
    def avg_payout(self) -> int:
        return self.total_return // self.total_hits if self.total_hits else 0


def run_all_strategies(cache: list, payouts: dict) -> Dict[str, StrategyStats]:
    stats = {name: StrategyStats(name=name) for name in STRATEGIES}

    for race in cache:
        race_id = race["race_id"]
        race_payouts = payouts.get(race_id)
        if not race_payouts:
            continue

        # 障害レースをスキップ
        if race.get("track_type") in ("obstacle", "steeplechase"):
            continue

        # race_idからYYYY-MM抽出 (race_id[:8] = "20250105")
        rid = race["race_id"]
        month = f"{rid[:4]}-{rid[4:6]}"

        for name, eval_func in STRATEGIES.items():
            results = eval_func(race, race_payouts)
            if not results:
                continue

            st = stats[name]
            st.total_races += 1

            if month not in st.monthly:
                st.monthly[month] = {"bets": 0, "hits": 0, "invested": 0, "returned": 0}
            m = st.monthly[month]

            for r in results:
                st.total_bets += 1
                st.total_invested += r.cost
                st.total_return += r.payout
                m["bets"] += 1
                m["invested"] += r.cost
                m["returned"] += r.payout
                if r.hit:
                    st.total_hits += 1
                    m["hits"] += 1
                    # 高配当記録
                    if r.payout >= 5000:
                        st.top_hits.append(r)

    return stats


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_summary(stats: Dict[str, StrategyStats]):
    print(f"\n{'='*85}")
    print(f"  Multi-leg Betting Strategy Backtest Results")
    print(f"{'='*85}")
    print(f"{'Strategy':<16} {'Races':>6} {'Bets':>6} {'Hits':>5} "
          f"{'HitRate':>8} {'Invested':>10} {'Return':>10} {'ROI%':>7} {'AvgPay':>8}")
    print(f"{'-'*85}")

    for name, st in stats.items():
        marker = " **" if st.roi >= 100 else ""
        print(f"{name:<16} {st.total_races:>6} {st.total_bets:>6} {st.total_hits:>5} "
              f"{st.hit_rate:>7.1f}% {st.total_invested:>9,} {st.total_return:>9,} "
              f"{st.roi:>6.1f}%{marker} {st.avg_payout:>7,}")

    # 単勝参考値
    print(f"{'-'*85}")
    print(f"  (**) = ROI >= 100%")


def print_monthly(stats: Dict[str, StrategyStats]):
    for name, st in stats.items():
        if st.roi < 70 or st.total_bets < 50:
            continue

        print(f"\n{'='*72}")
        print(f"  {name} Monthly Breakdown (ROI {st.roi:.1f}%)")
        print(f"{'='*72}")
        print(f"{'Month':>8} {'Bets':>6} {'Hits':>5} {'HitRate':>8} "
              f"{'Invested':>10} {'Return':>10} {'ROI%':>7} {'P&L':>10}")
        print(f"{'-'*72}")

        cum_pnl = 0
        for month in sorted(st.monthly.keys()):
            m = st.monthly[month]
            hr = m["hits"] / m["bets"] * 100 if m["bets"] else 0
            roi = m["returned"] / m["invested"] * 100 if m["invested"] else 0
            pnl = m["returned"] - m["invested"]
            cum_pnl += pnl
            print(f"{month:>8} {m['bets']:>6} {m['hits']:>5} {hr:>7.1f}% "
                  f"{m['invested']:>9,} {m['returned']:>9,} {roi:>6.1f}% {pnl:>+9,}")
        print(f"{'-'*72}")
        print(f"{'TOTAL':>8} {st.total_bets:>6} {st.total_hits:>5} {st.hit_rate:>7.1f}% "
              f"{st.total_invested:>9,} {st.total_return:>9,} {st.roi:>6.1f}% {cum_pnl:>+9,}")


def print_top_hits(stats: Dict[str, StrategyStats]):
    all_hits = []
    for name, st in stats.items():
        for r in st.top_hits:
            all_hits.append((name, r))

    if not all_hits:
        return

    all_hits.sort(key=lambda x: -x[1].payout)
    print(f"\n{'='*72}")
    print(f"  Top 15 Payouts")
    print(f"{'='*72}")
    for name, r in all_hits[:15]:
        print(f"  {name:<16} {r.race_id}  {r.ticket_type:<10} "
              f"{str(r.horses):<16} ¥{r.payout:>8,}")


# ---------------------------------------------------------------------------
# Today's recommendation (--today mode)
# ---------------------------------------------------------------------------

# 収益性検証済み戦略のみ推奨に使用
RECOMMEND_STRATEGIES = {
    "I.VB馬単1点":    evaluate_I,
    "G.VB馬単流":     evaluate_G,
    "K.危険裏ワイド":  evaluate_K,
}


def load_predictions_today(date_str: Optional[str] = None) -> list:
    """当日のpredictions.jsonを読み込む

    date_str: "YYYY-MM-DD" 形式。Noneなら今日。
    """
    from datetime import date as dt_date

    if date_str:
        parts = date_str.split("-")
        y, m, d = parts[0], parts[1], parts[2]
    else:
        today = dt_date.today()
        y, m, d = str(today.year), f"{today.month:02d}", f"{today.day:02d}"

    pred_path = Path(config.data_root()) / "races" / y / m / d / "predictions.json"
    if not pred_path.exists():
        print(f"[Error] predictions.json not found: {pred_path}")
        return []

    with open(pred_path, encoding="utf-8") as f:
        data = json.load(f)

    races = data.get("races", [])
    print(f"[Load] predictions: {pred_path}")
    print(f"  date: {data.get('date')}  created_at: {data.get('created_at')}")
    print(f"  {len(races)} races")
    return races


@dataclass
class Recommendation:
    race_id: str
    venue: str
    race_num: int
    strategy: str
    ticket_type: str
    horses: tuple
    horse_names: tuple
    cost: int
    note: str = ""


def generate_recommendations(races: list) -> List[Recommendation]:
    """収益性検証済みの戦略で買い目推奨を生成"""
    recs = []

    # 馬番→馬名のマッピング作成用ヘルパー
    def name_map(entries):
        return {e["umaban"]: e.get("horse_name", f"#{e['umaban']}") for e in entries}

    for race in races:
        # 障害レーススキップ
        if race.get("track_type") in ("obstacle", "steeplechase"):
            continue

        venue = race.get("venue_name", "?")
        race_num = race.get("race_number", 0)
        entries = race.get("entries", [])
        nm = name_map(entries)

        for strat_name, eval_func in RECOMMEND_STRATEGIES.items():
            # evaluate_*はpayoutsが必要だが推奨モードではpayout判定不要
            # → payoutsなしで呼べるようにダミーpayoutsで買い目だけ抽出
            bets = _generate_bets_no_payout(eval_func, race)
            for ticket_type, horses in bets:
                horse_names = tuple(nm.get(h, f"#{h}") for h in horses)
                # 戦略固有の補足情報
                note = _make_note(strat_name, race, horses)
                recs.append(Recommendation(
                    race_id=race["race_id"],
                    venue=venue,
                    race_num=race_num,
                    strategy=strat_name,
                    ticket_type=ticket_type,
                    horses=horses,
                    horse_names=horse_names,
                    cost=100,
                    note=note,
                ))

    return recs


def _generate_bets_no_payout(eval_func, race: dict) -> List[Tuple[str, tuple]]:
    """payout判定なしで買い目（券種, 馬番タプル）を生成

    evaluate_*関数のロジックを再利用するが、payoutsのflag/マッチングは不要。
    ダミーpayoutsを渡してBetResultのhorses部分だけ抽出。
    """
    dummy_payouts = {
        "umaren": [], "wide": [], "umatan": [], "sanrenpuku": [],
        "flags": {},  # 全て不成立なし
    }
    results = eval_func(race, dummy_payouts)
    return [(r.ticket_type, r.horses) for r in results]


def _make_note(strat_name: str, race: dict, horses: tuple) -> str:
    """推奨の補足情報"""
    entries = race.get("entries", [])
    ard_map = {e["umaban"]: e.get("ar_deviation", 0) for e in entries}
    odds_map = {e["umaban"]: e.get("odds", 0) for e in entries}

    parts = []
    for h in horses:
        ard = ard_map.get(h, 0)
        odds = odds_map.get(h, 0)
        parts.append(f"#{h}(ARd{ard:.0f}/odds{odds:.0f})")
    return " ".join(parts)


def print_recommendations(recs: List[Recommendation]):
    """推奨買い目を整形出力"""
    if not recs:
        print("\n  推奨なし（VB候補・危険馬のいるレースが見つかりません）")
        return

    # レース単位でグループ化
    from collections import OrderedDict
    by_race: Dict[str, list] = OrderedDict()
    for r in recs:
        key = f"{r.venue}{r.race_num}R"
        if key not in by_race:
            by_race[key] = []
        by_race[key].append(r)

    total_cost = sum(r.cost for r in recs)
    total_tickets = len(recs)

    print(f"\n{'='*75}")
    print(f"  Multi-leg Recommendations  ({len(by_race)} races, "
          f"{total_tickets} tickets, total cost: {total_cost:,})")
    print(f"{'='*75}")

    ticket_type_jp = {
        "umatan": "馬単", "umaren": "馬連", "wide": "ワイド", "sanrenpuku": "三連複",
    }

    for race_label, race_recs in by_race.items():
        print(f"\n  [{race_label}] {race_recs[0].race_id}")

        # 戦略ごとにまとめて表示
        current_strat = None
        for r in race_recs:
            if r.strategy != current_strat:
                current_strat = r.strategy
                print(f"    {r.strategy}")

            tt = ticket_type_jp.get(r.ticket_type, r.ticket_type)
            horses_str = "-".join(str(h) for h in r.horses)
            names_str = " x ".join(r.horse_names)
            print(f"      {tt} {horses_str:>8}  ({names_str})  {r.cost:,}")

    # VB単勝との組み合わせサマリー
    print(f"\n{'='*75}")
    print(f"  Summary")
    print(f"{'='*75}")

    # 戦略別集計
    by_strat: Dict[str, int] = {}
    for r in recs:
        by_strat.setdefault(r.strategy, 0)
        by_strat[r.strategy] += 1

    for strat, count in by_strat.items():
        cost = count * 100
        print(f"    {strat:<16}  {count:>3} tickets  {cost:>6,}")
    print(f"    {'合計':<16}  {total_tickets:>3} tickets  {total_cost:>6,}")

    print(f"\n  Backtest ROI Reference:")
    print(f"    I.VB馬単1点:   ROI 189% (単勝VBの補完、ダブル回収狙い)")
    print(f"    G.VB馬単流:    ROI 130% (VB馬→ARd上位への馬単流し)")
    print(f"    K.危険裏ワイド: ROI 117% (危険馬レースでARd上位ワイドBOX)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import sys as _sys
    args = _sys.argv[1:]

    if "--today" in args:
        # --today YYYY-MM-DD or --today (defaults to today)
        date_str = None
        idx = args.index("--today")
        if idx + 1 < len(args) and not args[idx + 1].startswith("-"):
            date_str = args[idx + 1]

        print("=" * 70)
        print("  KeibaCICD Multi-leg Recommendations")
        print("=" * 70)

        races = load_predictions_today(date_str)
        if not races:
            return
        recs = generate_recommendations(races)
        print_recommendations(recs)
        return

    # --- バックテストモード ---
    print("=" * 70)
    print("  KeibaCICD Multi-leg Betting Strategy Backtest")
    print("=" * 70)

    # 1. Load cache
    cache = load_backtest_cache()

    # 2. Load payouts
    race_codes = [r["race_id"] for r in cache]
    print(f"\n[Load] haraimodoshi from MySQL...")
    payouts = load_haraimodoshi(race_codes)
    matched = sum(1 for rc in race_codes if rc in payouts)
    print(f"  Payouts matched: {matched:,}/{len(race_codes):,} races")

    # 3. Run strategies
    print(f"\n[Simulate] Running {len(STRATEGIES)} strategies...")
    stats = run_all_strategies(cache, payouts)

    # 4. Output
    print_summary(stats)
    print_monthly(stats)
    print_top_hits(stats)


if __name__ == "__main__":
    main()
