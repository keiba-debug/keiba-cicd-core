"""Bankroll simulation v5 — bet_engine.generate_recommendations() 統合

backtest_cache.json の全レースデータに bet_engine の各プリセットを適用し、
複利バンクロールシミュレーションを実行。

★ v5: ワイド・馬連を haraimodoshi 実配当で精算（近似値廃止）。
  bet_engine.generate_recommendations() を直接呼び出す。
  馬券画面(ExecuteTab)と完全に同一の買い目で検証。

対応券種: 単勝, 複勝, 単複, ワイド(激戦/障害), 馬連(激戦/障害), 馬単(障害)
精算: 単勝=is_win*odds, 複勝=is_top3*place_odds_min, ワイド/馬連/馬単=haraimodoshi実配当

Usage:
    python -m ml.simulate_bankroll
"""
import json
import math
import shutil
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ml.bet_engine import (
    PRESETS, BetRecommendation, generate_recommendations,
    generate_adaptive_recommendations, ADAPTIVE_RULES, apply_adaptive_kelly,
)
from core.db import get_connection

# ── Config ──────────────────────────────────────────────
INITIAL_BANKROLL = 100_000

# Sizing modes:
#   pct > 0: equal sizing (daily budget = bankroll * pct, divided equally)
#   pct = 0, kelly = 0: flat 100yen per unit
#   kelly > 0: Kelly criterion (fractional kelly, per-bet sizing)
#   ev_weight = True: EV-proportional sizing within daily budget
BUDGET_CONFIGS = [
    {"label": "1%",      "pct": 0.01, "min": 500},
    {"label": "2%",      "pct": 0.02, "min": 1_000},
    {"label": "3%",      "pct": 0.03, "min": 1_500},
    {"label": "5%",      "pct": 0.05, "min": 2_000},
    {"label": "flat100", "pct": 0,    "min": 0},
    # Kelly sizing: bet = bankroll * kelly_frac * f*, capped per bet
    {"label": "K1/4",    "pct": 0, "min": 0, "kelly": 0.25, "kelly_cap": 0.05},
    {"label": "K1/8",    "pct": 0, "min": 0, "kelly": 0.125, "kelly_cap": 0.03},
    # EV-weighted: 3% budget distributed proportionally to EV
    {"label": "3%EV",    "pct": 0.03, "min": 1_500, "ev_weight": True},
]


def load_cache():
    path = Path("C:/KEIBA-CICD/data3/ml/backtest_cache.json")
    with open(path, encoding="utf-8") as f:
        cache = json.load(f)
    # 障害レースをpredictions.jsonアーカイブから追加
    obstacle_races = _load_obstacle_races(cache)
    if obstacle_races:
        cache.extend(obstacle_races)
        print(f"  + {len(obstacle_races)} obstacle races from predictions archives")
    return cache


def _load_obstacle_races(cache: list) -> list:
    """predictions.jsonアーカイブから障害レースを読み込み、backtest_cache形式に変換"""
    existing_ids = {r["race_id"] for r in cache}
    # backtest_cacheのdate rangeを取得
    dates = sorted(set(r["race_id"][:8] for r in cache))
    if not dates:
        return []
    date_min, date_max = dates[0], dates[-1]

    races_dir = Path("C:/KEIBA-CICD/data3/races")
    obstacle_races = []

    for year_dir in sorted(races_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        for month_dir in sorted(year_dir.iterdir()):
            if not month_dir.is_dir():
                continue
            for day_dir in sorted(month_dir.iterdir()):
                if not day_dir.is_dir():
                    continue
                date_str = f"{year_dir.name}{month_dir.name}{day_dir.name}"
                if date_str < date_min or date_str > date_max:
                    continue
                pred_path = day_dir / "predictions.json"
                if not pred_path.exists():
                    continue
                try:
                    with open(pred_path, encoding="utf-8") as f:
                        pred_data = json.load(f)
                except Exception:
                    continue

                for race in pred_data.get("races", []):
                    rid = race.get("race_id", "")
                    if rid in existing_ids:
                        continue
                    tt = race.get("track_type", "")
                    if tt != "obstacle":
                        continue
                    # race JSONから結果データを取得
                    race_json_path = day_dir / f"race_{rid}.json"
                    result_entries = {}
                    if race_json_path.exists():
                        try:
                            with open(race_json_path, encoding="utf-8") as f:
                                rj = json.load(f)
                            for e in rj.get("entries", []):
                                result_entries[e.get("umaban")] = e
                        except Exception:
                            pass

                    # backtest_cache形式に変換
                    entries = []
                    for e in race.get("entries", []):
                        uma = e.get("umaban")
                        re_ = result_entries.get(uma, {})
                        fp = re_.get("finish_position") or e.get("finish_position")
                        entries.append({
                            "umaban": uma,
                            "horse_name": e.get("horse_name", ""),
                            "odds": e.get("odds", 0),
                            "rank_p": e.get("rank_p", 99),
                            "rank_w": e.get("rank_w", 99),
                            "odds_rank": e.get("odds_rank", 99),
                            "finish_position": fp,
                            "is_win": fp == 1 if fp else False,
                            "is_top3": fp is not None and fp <= 3,
                            "place_odds_min": re_.get("place_odds_min") or e.get("place_odds_min"),
                            "pred_proba_p_raw": e.get("pred_proba_p_raw") or e.get("pred_proba_p", 0),
                            "predicted_margin": e.get("predicted_margin"),
                            "ar_deviation": e.get("ar_deviation"),
                            "vb_gap": e.get("vb_gap", 0),
                            "win_vb_gap": e.get("win_vb_gap", 0),
                            "win_ev": e.get("win_ev", 0),
                            "place_ev": e.get("place_ev", 0),
                            "dev_gap": e.get("dev_gap", 0),
                            "closing_strength": 0,
                            "comment_memo_trouble_score": e.get("comment_memo_trouble_score", 0),
                            "horse_slow_start_rate": 0,
                            "last_race_corner1_ratio": 0,
                        })
                    if entries:
                        obstacle_races.append({
                            "race_id": rid,
                            "track_type": "obstacle",
                            "grade": race.get("grade", ""),
                            "age_class": race.get("age_class", ""),
                            "grade_offset": 0,
                            "closing_race_proba": 0,
                            "entries": entries,
                        })
                        existing_ids.add(rid)

    return obstacle_races


# ── haraimodoshi 実配当ロード ──
_haraimodoshi_cache: Dict[str, dict] = {}


def _pi(s) -> int:
    if not s:
        return 0
    try:
        return int(str(s).strip())
    except (ValueError, TypeError):
        return 0


def load_haraimodoshi(race_codes: List[str]):
    """haraimodoshiテーブルからワイド・馬連の実配当を一括ロード"""
    global _haraimodoshi_cache

    cols = ["RACE_CODE"]
    # ワイド 1-7
    for i in range(1, 8):
        cols.extend([f"WIDE{i}_KUMIBAN1", f"WIDE{i}_KUMIBAN2",
                     f"WIDE{i}_HARAIMODOSHIKIN"])
    # 馬連 1-3
    for i in range(1, 4):
        cols.extend([f"UMAREN{i}_KUMIBAN1", f"UMAREN{i}_KUMIBAN2",
                     f"UMAREN{i}_HARAIMODOSHIKIN"])
    # 馬単 1-6
    for i in range(1, 7):
        cols.extend([f"UMATAN{i}_KUMIBAN1", f"UMATAN{i}_KUMIBAN2",
                     f"UMATAN{i}_HARAIMODOSHIKIN"])

    col_str = ", ".join(cols)
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
                payouts = {"wide": [], "umaren": [], "umatan": []}

                for i in range(1, 8):
                    k1 = _pi(row.get(f"WIDE{i}_KUMIBAN1", ""))
                    k2 = _pi(row.get(f"WIDE{i}_KUMIBAN2", ""))
                    pay = _pi(row.get(f"WIDE{i}_HARAIMODOSHIKIN", ""))
                    if k1 and k2 and pay:
                        payouts["wide"].append((frozenset({k1, k2}), pay))

                for i in range(1, 4):
                    k1 = _pi(row.get(f"UMAREN{i}_KUMIBAN1", ""))
                    k2 = _pi(row.get(f"UMAREN{i}_KUMIBAN2", ""))
                    pay = _pi(row.get(f"UMAREN{i}_HARAIMODOSHIKIN", ""))
                    if k1 and k2 and pay:
                        payouts["umaren"].append((frozenset({k1, k2}), pay))

                for i in range(1, 7):
                    k1 = _pi(row.get(f"UMATAN{i}_KUMIBAN1", ""))
                    k2 = _pi(row.get(f"UMATAN{i}_KUMIBAN2", ""))
                    pay = _pi(row.get(f"UMATAN{i}_HARAIMODOSHIKIN", ""))
                    if k1 and k2 and pay:
                        # 馬単は順序あり: (1着, 2着) のタプル
                        payouts["umatan"].append(((k1, k2), pay))

                _haraimodoshi_cache[rc] = payouts
        cur.close()

    print(f"  haraimodoshi: {len(_haraimodoshi_cache):,} races loaded")


def _lookup_haraimodoshi(race_id: str, bet_type: str, pair: list) -> int:
    """実配当を検索。Returns 100円あたりの払戻金（0=ハズレ）

    馬単は順序あり: pair=[1着馬番, 2着馬番]
    ワイド/馬連は順序なし: pair=[馬番, 馬番]
    """
    payouts = _haraimodoshi_cache.get(race_id, {})
    entries = payouts.get(bet_type, [])
    if bet_type == "umatan":
        # 馬単: 順序あり (1着, 2着)
        target = (pair[0], pair[1])
        for combo, pay in entries:
            if combo == target:
                return pay
    else:
        # ワイド/馬連: 順序なし
        target = frozenset({pair[0], pair[1]})
        for combo, pay in entries:
            if combo == target:
                return pay
    return 0


def group_by_date(cache_races):
    by_date = defaultdict(list)
    for race in cache_races:
        date = race["race_id"][:8]
        by_date[date].append(race)
    return dict(sorted(by_date.items()))


# ── BetRecommendation → sim内部形式変換 ──
def _rec_to_sim_bet(rec: BetRecommendation, race_entries: dict) -> dict:
    """BetRecommendation を精算可能な内部形式に変換

    race_entries: {umaban: entry_dict} のマップ（finish_position等の参照用）
    """
    bt = rec.bet_type  # '単勝' | '複勝' | '単複' | 'ワイド' | '馬連'
    entry = race_entries.get(rec.umaban, {})

    if bt in ('単勝', '複勝', '単複'):
        return {
            "bet_type": _bet_type_to_sim(bt),
            "umaban": rec.umaban,
            "entry": entry,
            "rec": rec,
        }
    elif bt in ('ワイド', '馬連', '馬単'):
        pair = rec.wide_pair or [rec.umaban, rec.umaban]
        e1 = race_entries.get(pair[0], {})
        e2 = race_entries.get(pair[1], {})
        sim_type = {"ワイド": "wide", "馬連": "umaren", "馬単": "umatan"}[bt]
        return {
            "bet_type": sim_type,
            "pair": pair,  # 馬単: [1着馬番, 2着馬番] の順序
            "entries": [e1, e2],
            "num_runners": len(race_entries),
            "race_id": rec.race_id,
            "rec": rec,
        }
    return {"bet_type": "unknown", "rec": rec}


def _bet_type_to_sim(bt: str) -> str:
    return {"単勝": "win", "複勝": "place", "単複": "win_place",
            "ワイド": "wide", "馬連": "umaren", "馬単": "umatan"}.get(bt, "win")


# ── Settlement ──
def settle_bet(bet: dict) -> Tuple[int, float]:
    """Settle a bet. Returns (bet_amount_units, return_per_unit).
    Units = per 100yen.
    """
    bt = bet["bet_type"]

    if bt == "win":
        e = bet["entry"]
        if e.get("is_win", 0):
            return (1, e.get("odds") or 0)
        return (1, 0)

    elif bt == "place":
        e = bet["entry"]
        if e.get("is_top3", 0):
            return (1, e.get("place_odds_min") or 1.0)
        return (1, 0)

    elif bt == "win_place":
        e = bet["entry"]
        is_win = e.get("is_win", 0)
        is_top3 = e.get("is_top3", 0)
        odds = e.get("odds") or 0
        place_odds = e.get("place_odds_min") or 1.0
        win_ret = odds if is_win else 0
        place_ret = place_odds if is_top3 else 0
        return (2, win_ret + place_ret)

    elif bt == "wide":
        race_id = bet.get("race_id", "")
        pair = bet["pair"]
        pay = _lookup_haraimodoshi(race_id, "wide", pair)
        if pay > 0:
            return (1, pay / 100)  # 100円あたり倍率
        return (1, 0)

    elif bt == "umaren":
        race_id = bet.get("race_id", "")
        pair = bet["pair"]
        pay = _lookup_haraimodoshi(race_id, "umaren", pair)
        if pay > 0:
            return (1, pay / 100)  # 100円あたり倍率
        return (1, 0)

    elif bt == "umatan":
        race_id = bet.get("race_id", "")
        pair = bet["pair"]  # [1着馬番, 2着馬番] 順序あり
        pay = _lookup_haraimodoshi(race_id, "umatan", pair)
        if pay > 0:
            return (1, pay / 100)  # 100円あたり倍率
        return (1, 0)

    return (0, 0)


def calc_kelly(prob: float, odds: float) -> float:
    """Kelly Criterion: f* = (b*p - q) / b"""
    b = odds - 1.0
    if b <= 0 or prob <= 0:
        return 0.0
    q = 1.0 - prob
    f = (b * prob - q) / b
    return max(0.0, f)


def get_bet_ev(bet: dict) -> float:
    """Get EV for a bet (used for Kelly and EV-weighted sizing)"""
    rec: BetRecommendation = bet["rec"]
    bt = bet["bet_type"]
    if bt in ("win", "place", "win_place"):
        return rec.win_ev or (rec.place_ev or 0)
    elif bt == "wide":
        entries = bet["entries"]
        e1, e2 = entries[0], entries[1]
        p1 = e1.get("pred_proba_p_raw") or 0.3
        p2 = e2.get("pred_proba_p_raw") or 0.3
        o1 = e1.get("place_odds_min") or 1.0
        o2 = e2.get("place_odds_min") or 1.0
        p_both = p1 * p2 * 0.8
        payout = (o1 + o2) * 0.8
        return p_both * payout
    elif bt in ("umaren", "umatan"):
        return 0.8  # conservative default
    return 1.0


def calc_bet_kelly_fraction(bet: dict) -> float:
    """Calculate raw Kelly fraction for a bet"""
    rec: BetRecommendation = bet["rec"]
    bt = bet["bet_type"]
    if bt in ("win", "win_place"):
        e = bet["entry"]
        win_ev = e.get("win_ev") or (rec.win_ev or 0)
        odds = e.get("odds") or (rec.odds or 0)
        if odds <= 1:
            return 0.0
        p_win = win_ev / odds
        return calc_kelly(p_win, odds)
    elif bt == "place":
        e = bet["entry"]
        place_ev = e.get("place_ev") or (rec.place_ev or 0)
        place_odds = e.get("place_odds_min") or 1.0
        if place_odds <= 1:
            return 0.0
        p_top3 = place_ev / place_odds if place_odds > 0 else 0
        return calc_kelly(p_top3, place_odds)
    elif bt == "wide":
        entries = bet["entries"]
        e1, e2 = entries[0], entries[1]
        p1 = e1.get("pred_proba_p_raw") or 0.3
        p2 = e2.get("pred_proba_p_raw") or 0.3
        o1 = e1.get("place_odds_min") or 1.0
        o2 = e2.get("place_odds_min") or 1.0
        p_both = p1 * p2 * 0.8
        payout = (o1 + o2) * 0.8
        return calc_kelly(p_both, payout)
    elif bt in ("umaren", "umatan"):
        return 0.01
    return 0.0


def run_simulation(dates_races: dict, preset_name: str, budget_cfg: dict):
    """Full compounding simulation for a preset + budget config.

    Uses bet_engine.generate_recommendations() for bet selection.
    preset_name == 'adaptive' の場合は generate_adaptive_recommendations() を使用。
    """
    is_adaptive = preset_name == 'adaptive'
    params = None if is_adaptive else PRESETS[preset_name]
    budget_pct = budget_cfg["pct"]
    min_budget = budget_cfg["min"]
    kelly_frac = budget_cfg.get("kelly", 0)
    kelly_cap = budget_cfg.get("kelly_cap", 0.05)
    ev_weight = budget_cfg.get("ev_weight", False)

    is_flat = budget_pct == 0 and kelly_frac == 0
    is_kelly = kelly_frac > 0

    bankroll = INITIAL_BANKROLL
    peak = bankroll
    max_dd = 0
    total_bet = 0
    total_return = 0
    daily_returns = []
    bet_days = 0

    # Bet type counters
    win_bets = 0
    place_bets = 0
    wide_bets = 0
    umaren_bets = 0
    umatan_bets = 0
    win_hits = 0
    place_hits = 0
    wide_hits = 0
    umaren_hits = 0
    umatan_hits = 0
    total_bets_count = 0

    # Streak tracking
    current_loss_streak = 0
    max_loss_streak = 0
    current_win_streak = 0
    max_win_streak = 0

    history = [{"date": None, "bankroll": bankroll}]

    for date, races in sorted(dates_races.items()):
        if bankroll <= 0:
            history.append({"date": date, "bankroll": 0})
            continue

        # bet_engine で買い目生成
        if is_adaptive:
            # relaxed ベースで生成 → adaptive Kelly 率上書き
            recs = generate_recommendations(races, PRESETS['relaxed'], budget=30000)
            recs = apply_adaptive_kelly(recs, races, ADAPTIVE_RULES)
        else:
            recs = generate_recommendations(races, params, budget=30000)

        if not recs:
            continue

        # BetRecommendation → sim内部形式に変換
        # race_entries マップを作成 (race_id -> {umaban: entry})
        race_entries_map: Dict[str, Dict[int, dict]] = {}
        for race in races:
            emap = {e["umaban"]: e for e in race.get("entries", [])}
            race_entries_map[race["race_id"]] = emap

        day_bets = []
        for rec in recs:
            entries_for_race = race_entries_map.get(rec.race_id, {})
            sim_bet = _rec_to_sim_bet(rec, entries_for_race)
            day_bets.append(sim_bet)

        if not day_bets:
            continue

        # ── Allocate amounts per bet ──
        bet_amounts = []

        if is_kelly:
            for b in day_bets:
                bt = b["bet_type"]
                # ワイド/馬連は補助券種のため固定比率(bankroll×1%)
                if bt in ("wide", "umaren", "umatan"):
                    amount = max(100, int(bankroll * 0.01 / 100) * 100)
                else:
                    raw_f = calc_bet_kelly_fraction(b)
                    # adaptive: ルール固有のKelly fractionを使用
                    rec_obj: BetRecommendation = b["rec"]
                    if is_adaptive and rec_obj.kelly_capped > 0:
                        rule_kf = rec_obj.kelly_capped  # rule.kelly_fraction
                        f = min(raw_f * rule_kf, kelly_cap)
                    else:
                        f = min(raw_f * kelly_frac, kelly_cap)
                    amount = int(bankroll * f / 100) * 100
                    if bt == "win_place":
                        amount = max(200, amount)
                    else:
                        amount = max(100, amount)
                bet_amounts.append(amount)
            total_exposure = sum(bet_amounts)
            if total_exposure > bankroll * 0.3:
                scale = bankroll * 0.3 / total_exposure
                bet_amounts = [max(100, int(a * scale / 100) * 100) for a in bet_amounts]

        elif is_flat:
            bet_amounts = [
                200 if b["bet_type"] == "win_place" else 100
                for b in day_bets
            ]

        elif ev_weight:
            daily_budget = max(min_budget, int(bankroll * budget_pct / 100) * 100)
            if daily_budget > bankroll:
                daily_budget = int(bankroll / 100) * 100
            if daily_budget < 100:
                history.append({"date": date, "bankroll": round(bankroll)})
                continue
            # ワイド/馬連は固定比率で先に確定、残りをEV配分
            wide_umaren_total = 0
            wide_umaren_indices = set()
            for i, b in enumerate(day_bets):
                if b["bet_type"] in ("wide", "umaren"):
                    wide_umaren_indices.add(i)
                    amt = max(100, int(bankroll * 0.01 / 100) * 100)
                    wide_umaren_total += amt
            remaining_budget = max(0, daily_budget - wide_umaren_total)
            # adaptive: ルール固有Kelly fractionをEVの重みに反映
            evs = []
            for b in day_bets:
                ev = max(get_bet_ev(b), 0.5)
                if is_adaptive:
                    rec_obj_ev: BetRecommendation = b["rec"]
                    kf = rec_obj_ev.kelly_capped if rec_obj_ev.kelly_capped > 0 else 0.125
                    ev *= kf / 0.125  # K1/4ルールはEVウェイト2倍
                evs.append(ev)
            # 単勝/複勝のみEV配分
            win_evs = [evs[i] if i not in wide_umaren_indices else 0 for i in range(len(day_bets))]
            ev_total = sum(win_evs)
            if ev_total <= 0 and not wide_umaren_indices:
                continue
            for i, b in enumerate(day_bets):
                if i in wide_umaren_indices:
                    bet_amounts.append(max(100, int(bankroll * 0.01 / 100) * 100))
                elif ev_total > 0:
                    units = 2 if b["bet_type"] == "win_place" else 1
                    share = win_evs[i] / ev_total
                    amount = max(100 * units, int(remaining_budget * share / 100) * 100)
                    bet_amounts.append(amount)
                else:
                    bet_amounts.append(100)
            total_alloc = sum(bet_amounts)
            if total_alloc > daily_budget:
                scale = daily_budget / total_alloc
                bet_amounts = [max(100, int(a * scale / 100) * 100) for a in bet_amounts]

        else:
            # Equal sizing
            daily_budget = max(min_budget, int(bankroll * budget_pct / 100) * 100)
            if daily_budget > bankroll:
                daily_budget = int(bankroll / 100) * 100
            if daily_budget < 100:
                history.append({"date": date, "bankroll": round(bankroll)})
                continue
            # ワイド/馬連は固定比率
            wide_umaren_indices_eq = set()
            for i, b in enumerate(day_bets):
                if b["bet_type"] in ("wide", "umaren"):
                    wide_umaren_indices_eq.add(i)
            non_wide_bets = [b for i, b in enumerate(day_bets) if i not in wide_umaren_indices_eq]
            total_units = sum(
                2 if b["bet_type"] == "win_place" else 1
                for b in non_wide_bets
            )
            if total_units == 0 and not wide_umaren_indices_eq:
                continue
            remaining_eq = daily_budget - sum(
                max(100, int(bankroll * 0.01 / 100) * 100)
                for i in wide_umaren_indices_eq
            )
            bet_unit = max(100, int(remaining_eq / max(total_units, 1) / 100) * 100) if total_units > 0 else 100
            bet_amounts = [
                max(100, int(bankroll * 0.01 / 100) * 100) if i in wide_umaren_indices_eq
                else bet_unit * (2 if b["bet_type"] == "win_place" else 1)
                for i, b in enumerate(day_bets)
            ]

        # ── Settle ──
        day_bet_amount = 0
        day_return_amount = 0

        for i, b in enumerate(day_bets):
            amount = bet_amounts[i]
            _units, ret_per_unit = settle_bet(b)

            if is_kelly or ev_weight:
                if b["bet_type"] == "win_place":
                    win_amount = amount // 2
                    place_amount = amount - win_amount
                    e = b["entry"]
                    win_ret = round(win_amount * (e.get("odds") or 0)) if e.get("is_win") else 0
                    place_ret = round(place_amount * (e.get("place_odds_min") or 1.0)) if e.get("is_top3") else 0
                    ret = win_ret + place_ret
                else:
                    ret = round(amount * ret_per_unit)
            else:
                ret = round(amount / (2 if b["bet_type"] == "win_place" else 1) * ret_per_unit)

            day_bet_amount += amount
            day_return_amount += ret

            bt = b["bet_type"]
            if bt == "win":
                win_bets += 1
                if ret > 0: win_hits += 1
            elif bt == "place":
                place_bets += 1
                if ret > 0: place_hits += 1
            elif bt == "win_place":
                win_bets += 1
                place_bets += 1
                e = b["entry"]
                if e.get("is_win"): win_hits += 1
                if e.get("is_top3"): place_hits += 1
            elif bt == "wide":
                wide_bets += 1
                if ret > 0: wide_hits += 1
            elif bt == "umaren":
                umaren_bets += 1
                if ret > 0: umaren_hits += 1
            elif bt == "umatan":
                umatan_bets += 1
                if ret > 0: umatan_hits += 1

        total_bets_count += len(day_bets)

        if day_bet_amount > 0:
            daily_pnl = day_return_amount - day_bet_amount
            bankroll += daily_pnl
            total_bet += day_bet_amount
            total_return += day_return_amount
            daily_returns.append(daily_pnl / day_bet_amount)
            bet_days += 1

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

    # Metrics
    if daily_returns:
        avg_r = sum(daily_returns) / len(daily_returns)
        if len(daily_returns) > 1:
            var = sum((r - avg_r) ** 2 for r in daily_returns) / (len(daily_returns) - 1)
            std_r = math.sqrt(var)
        else:
            std_r = 0
        sharpe = avg_r / std_r if std_r > 0 else 0
    else:
        sharpe = 0

    win_days = sum(1 for r in daily_returns if r >= 0)
    lose_days = sum(1 for r in daily_returns if r < 0)
    roi_pct = (bankroll / INITIAL_BANKROLL - 1) * 100
    calmar = roi_pct / (max_dd * 100) if max_dd > 0 else 0

    return {
        "preset": preset_name,
        "label": preset_name,
        "final_bankroll": round(bankroll),
        "roi_pct": round(roi_pct, 1),
        "total_bet": total_bet,
        "total_return": total_return,
        "flat_roi": round(total_return / total_bet * 100, 1) if total_bet > 0 else 0,
        "max_dd": round(max_dd * 100, 1),
        "sharpe": round(sharpe, 3),
        "calmar": round(calmar, 2),
        "bet_days": bet_days,
        "total_bets": total_bets_count,
        "win_days": win_days,
        "lose_days": lose_days,
        "max_loss_streak": max_loss_streak,
        "max_win_streak": max_win_streak,
        "history": history,
        "win_bets": win_bets,
        "place_bets": place_bets,
        "wide_bets": wide_bets,
        "umaren_bets": umaren_bets,
        "umatan_bets": umatan_bets,
        "win_hit_rate": round(win_hits / win_bets * 100, 1) if win_bets > 0 else 0,
        "place_hit_rate": round(place_hits / place_bets * 100, 1) if place_bets > 0 else 0,
        "wide_hit_rate": round(wide_hits / wide_bets * 100, 1) if wide_bets > 0 else 0,
        "umaren_hit_rate": round(umaren_hits / umaren_bets * 100, 1) if umaren_bets > 0 else 0,
        "umatan_hit_rate": round(umatan_hits / umatan_bets * 100, 1) if umatan_bets > 0 else 0,
    }


def main():
    preset_names = list(PRESETS.keys()) + ['adaptive']
    print("=" * 80)
    print(f"  Bankroll Simulation v4 - bet_engine unified")
    print(f"  Initial: {INITIAL_BANKROLL:,} | Presets: {len(preset_names)}")
    print(f"  Presets: {', '.join(preset_names)}")
    print("=" * 80)

    cache = load_cache()
    print(f"  Cache: {len(cache)} races")

    # haraimodoshi実配当ロード
    race_codes = [r["race_id"] for r in cache]
    print(f"\n[Load] haraimodoshi (ワイド・馬連実配当)...")
    load_haraimodoshi(race_codes)

    dates_races = group_by_date(cache)
    print(f"  Dates: {len(dates_races)} days ({min(dates_races)}~{max(dates_races)})")

    all_results = []

    for preset_name in preset_names:
        print(f"\n{'=' * 60}")
        print(f"  Preset: {preset_name}")
        print(f"{'=' * 60}")

        for bcfg in BUDGET_CONFIGS:
            r = run_simulation(dates_races, preset_name, bcfg)
            r["budget_label"] = bcfg["label"]

            marker = " ***" if r["final_bankroll"] > INITIAL_BANKROLL else ""
            wl = f"{r['win_days']}/{r['lose_days']}"
            bt_info = f"W{r['win_bets']}({r['win_hit_rate']}%)"
            if r['place_bets'] > 0:
                bt_info += f" P{r['place_bets']}({r['place_hit_rate']}%)"
            if r['wide_bets'] > 0:
                bt_info += f" Wd{r['wide_bets']}({r['wide_hit_rate']}%)"
            if r['umaren_bets'] > 0:
                bt_info += f" Um{r['umaren_bets']}({r['umaren_hit_rate']}%)"
            if r['umatan_bets'] > 0:
                bt_info += f" Ut{r['umatan_bets']}({r['umatan_hit_rate']}%)"
            print(f"  {bcfg['label']:>7} | Final {r['final_bankroll']:>8,} | ROI {r['roi_pct']:>+7.1f}% | "
                  f"Flat {r['flat_roi']:>6.1f}% | DD {r['max_dd']:>5.1f}% | "
                  f"{wl:>5} | {bt_info}{marker}")

            all_results.append(r)

    # Model version
    meta_path = Path("C:/KEIBA-CICD/data3/ml/model_meta.json")
    model_version = "unknown"
    if meta_path.exists():
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        model_version = meta.get("version", "unknown")

    # Build output
    output = {
        "model_version": model_version,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "initial_bankroll": INITIAL_BANKROLL,
        "budget_configs": [{"label": b["label"], "pct": b["pct"]} for b in BUDGET_CONFIGS],
        "presets": preset_names,
        "strategies": [
            {"mode": k, "label": k + (" (adaptive rules)" if k == "adaptive" else "")}
            for k in preset_names
        ],
        "results": [],
    }

    for r in all_results:
        output["results"].append({
            "preset": r["preset"],
            "budget_label": r["budget_label"],
            "mode": r["preset"],
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
            "win_bets": r["win_bets"],
            "place_bets": r["place_bets"],
            "wide_bets": r["wide_bets"],
            "umaren_bets": r["umaren_bets"],
            "umatan_bets": r["umatan_bets"],
            "win_hit_rate": r["win_hit_rate"],
            "place_hit_rate": r["place_hit_rate"],
            "wide_hit_rate": r["wide_hit_rate"],
            "umaren_hit_rate": r["umaren_hit_rate"],
            "umatan_hit_rate": r["umatan_hit_rate"],
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
