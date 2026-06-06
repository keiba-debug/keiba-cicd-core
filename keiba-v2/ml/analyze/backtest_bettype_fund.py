#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""P2b 配分・券種出し分け backtest (RELEASE_0606_0607 / Session 141)

baseline (concentrate + anchor_kelly_combo_ev) vs adaptive (adaptive + adaptive_fund) の
full-selection ROI を backtest_cache で比較。 Bootstrap CI 下限で改善判定。

おまけ (P2a 🟡-3): hole_seeker 軸 support_cut (top-3 / top-quarter / top-5) を
ROI proxy で比較 (find_taste_axis 本体は触らない)。

CLI:
    python -m ml.analyze.backtest_bettype_fund
    python -m ml.analyze.backtest_bettype_fund --split-date 2026-01-01 --bootstrap 1000
"""

from __future__ import annotations

import argparse
import io
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.strategies import bettype_fund as bf  # noqa: E402
from ml.strategies import bettype_selection as bs  # noqa: E402
from ml.strategies import bettype_sizing as sz  # noqa: E402
from ml.utils.backtest_cache import load_backtest_cache  # noqa: E402
from ml.utils.roi import Bet, calc_roi  # noqa: E402

DEFAULT_BANKROLL = 10000
DEFAULT_PER_RACE_CAP = 3000
DEFAULT_BOOTSTRAP = 1000


def _W(e: dict) -> Optional[float]:
    o = e.get("odds") or 0
    we = e.get("win_ev")
    if o > 0 and we is not None:
        return we / o
    return None


def cache_race_to_pred(race: dict) -> Optional[dict]:
    """backtest_cache 1 race → predictions.json race 互換。"""
    ents = []
    for e in race.get("entries", []) or []:
        if e.get("umaban") is None:
            continue
        w = _W(e)
        ents.append({
            "umaban": int(e["umaban"]),
            "horse_name": str(e.get("horse_name") or ""),
            "odds": float(e.get("odds") or 0),
            "place_odds_min": e.get("place_odds_min"),
            "pred_proba_w_cal": w,
            "pred_proba_p": e.get("pred_proba_p_raw"),
            "ar_deviation": e.get("ar_deviation"),
            "finish_position": e.get("finish_position"),
        })
    if len(ents) < 3:
        return None
    rid = str(race.get("race_id") or "")
    return {
        "race_id": rid,
        "date": f"{rid[:4]}-{rid[4:6]}-{rid[6:8]}" if len(rid) >= 8 else None,
        "venue_name": race.get("venue_name"),
        "race_number": race.get("race_number"),
        "grade": str(race.get("grade") or ""),
        "track_type": race.get("track_type"),
        "num_runners": len(ents),
        "entries": ents,
    }


def _finish_map(pred_race: dict) -> Dict[int, int]:
    out = {}
    for e in pred_race.get("entries", []) or []:
        fp = e.get("finish_position")
        try:
            out[int(e["umaban"])] = int(fp)
        except (TypeError, ValueError):
            out[int(e["umaban"])] = 99
    return out


def _place_odds(entry_map: dict, umaban: int) -> float:
    e = entry_map.get(umaban) or {}
    po = e.get("place_odds_min")
    try:
        return float(po) if po and float(po) > 0 else 0.0
    except (TypeError, ValueError):
        return 0.0


def leg_hit(bet_type: str, horses: List[int], finish: Dict[int, int]) -> bool:
    if bet_type == "tansho":
        return finish.get(horses[0], 99) == 1
    if bet_type == "fukusho":
        return 1 <= finish.get(horses[0], 99) <= 3
    if bet_type == "umaren" and len(horses) >= 2:
        top2 = sorted((u, finish.get(u, 99)) for u in finish)[:2]
        top2_set = {u for u, _ in top2 if _ <= 2}
        return set(horses[:2]) == top2_set and len(top2_set) == 2
    if bet_type == "wide" and len(horses) >= 2:
        top3 = {u for u, fp in finish.items() if fp <= 3}
        return horses[0] in top3 and horses[1] in top3
    if bet_type == "umatan" and len(horses) >= 2:
        return finish.get(horses[0], 99) == 1 and finish.get(horses[1], 99) == 2
    return False


def simulate_legs(pred_race: dict, rs: sz.RaceSizing) -> List[Bet]:
    """RaceSizing の各 leg を結果で決済 (combo は plan odds 近似)。"""
    if not rs or not rs.legs:
        return []
    finish = _finish_map(pred_race)
    entry_map = {int(e["umaban"]): e for e in pred_race.get("entries", []) or []}
    bets: List[Bet] = []
    rid = str(pred_race.get("race_id"))
    for leg in rs.legs:
        hit = leg_hit(leg.bet_type, leg.horses, finish)
        payout = 0.0
        if hit:
            if leg.bet_type == "fukusho":
                po = _place_odds(entry_map, leg.horses[0])
                payout = leg.amount * po if po > 0 else 0.0
            elif leg.leg_odds and leg.leg_odds > 0:
                payout = leg.amount * leg.leg_odds
        bets.append(Bet(
            race_id=rid, cost=float(leg.amount), payout=float(payout),
            is_hit=hit and payout > 0, odds=float(leg.leg_odds or 0),
            bet_type=leg.bet_type,
        ))
    return bets


def evaluate_race(
    pred_race: dict,
    *,
    strategy: str,
    sizing: str,
    bankroll: int = DEFAULT_BANKROLL,
    per_race_cap: int = DEFAULT_PER_RACE_CAP,
) -> Tuple[List[Bet], Optional[str]]:
    sel = bs.evaluate_and_select(pred_race, strategy=strategy, ev_floor=bs.DEFAULT_EV_FLOOR)
    if sel is None:
        return [], None
    race_eff = be.process_race(pred_race, axis=sel.axis_umaban)
    if race_eff is None:
        return [], sel.fund_mode
    rs = sz.get_sizer(sizing)(
        race_eff, sel, bankroll=bankroll, per_race_cap=per_race_cap)
    return simulate_legs(pred_race, rs), sel.fund_mode


@dataclass
class BacktestSummary:
    label: str
    n_races: int
    n_bets: int
    roi: float
    ci_low: float
    ci_high: float
    cost: float
    payout: float
    mode_counts: Dict[str, int]


def run_backtest(
    races: List[dict],
    *,
    strategy: str,
    sizing: str,
    bootstrap_n: int,
) -> BacktestSummary:
    all_bets: List[Bet] = []
    mode_counts: Counter = Counter()
    n_races = 0
    for raw in races:
        pred = cache_race_to_pred(raw)
        if pred is None:
            continue
        if not any(int(e.get("finish_position") or 99) == 1
                   for e in pred.get("entries", [])):
            continue
        bets, mode = evaluate_race(
            pred, strategy=strategy, sizing=sizing)
        if mode:
            mode_counts[mode] += 1
        n_races += 1
        all_bets.extend(bets)
    roi_res = calc_roi(all_bets, bootstrap_n=bootstrap_n)
    return BacktestSummary(
        label=f"{strategy}+{sizing}",
        n_races=n_races,
        n_bets=roi_res.n,
        roi=roi_res.roi,
        ci_low=roi_res.ci_low,
        ci_high=roi_res.ci_high,
        cost=roi_res.cost,
        payout=roi_res.payout,
        mode_counts=dict(mode_counts),
    )


# ---------------------------------------------------------------------------
# P2a おまけ: support_cut 比較 (find_taste_axis は触らない)
# ---------------------------------------------------------------------------

def _taste_axis_with_cut(race_eff, support_cut: int) -> Optional[int]:
    """find_taste_axis と同型だが support_cut だけ差し替え (backtest 専用)。"""
    present = [s for s in race_eff.strengths
               if s.odds is not None and s.odds > 0 and s.win_prob > 0]
    if not present:
        return None
    n = len(present)
    pop_rank = {s.umaban: i for i, s in
                enumerate(sorted(present, key=lambda s: (s.odds, s.umaban)), start=1)}
    comp_rank = {s.umaban: i for i, s in
                 enumerate(sorted(present, key=lambda s: (-s.composite, -s.win_prob, s.umaban)),
                           start=1)}
    cut = min(n, support_cut) if support_cut > 0 else max(1, (n + 2) // 3)
    prob_floor = 1.0 / n
    cands = [s for s in present
             if comp_rank[s.umaban] <= cut and s.win_prob >= prob_floor]
    if not cands:
        return None
    best = max(cands, key=lambda s: (pop_rank[s.umaban] - comp_rank[s.umaban],
                                     -comp_rank[s.umaban], -s.umaban))
    if pop_rank[best.umaban] - comp_rank[best.umaban] <= 0:
        return None
    return best.umaban


def run_taste_axis_backtest(races: List[dict], *, bootstrap_n: int) -> None:
    """popularity_gap_max 軸の support_cut 比較 (軸単勝フラット ROI proxy)。"""
    cuts = {
        "top-3 (P2a prod)": 3,
        "top-quarter": 0,   # 0 → ceil(n/3) 相当の旧 top-third 近似用に別処理
        "top-5": 5,
    }
    print("\n=== P2a おまけ: hole_seeker support_cut 比較 (軸単勝フラット ROI) ===")
    for label, cut in cuts.items():
        bets: List[Bet] = []
        n = 0
        for raw in races:
            pred = cache_race_to_pred(raw)
            if pred is None:
                continue
            re0 = be.process_race(pred)
            if re0 is None:
                continue
            if cut == 0:
                n_run = len([s for s in re0.strengths if s.odds and s.odds > 0])
                sc = max(1, (n_run + 2) // 3)
            else:
                sc = cut
            axis = _taste_axis_with_cut(re0, sc)
            if axis is None:
                axis = re0.axis_umaban
            finish = _finish_map(pred)
            entry_map = {int(e["umaban"]): e for e in pred.get("entries", []) or []}
            e = entry_map.get(axis)
            if not e:
                continue
            odds = float(e.get("odds") or 0)
            if odds <= 0:
                continue
            n += 1
            hit = finish.get(axis, 99) == 1
            bets.append(Bet(
                race_id=str(pred["race_id"]), cost=100.0,
                payout=odds * 100.0 if hit else 0.0, is_hit=hit, odds=odds,
                bet_type="tansho",
            ))
        roi_res = calc_roi(bets, bootstrap_n=bootstrap_n)
        print(f"  {label:<22} n={n:>4}  ROI={roi_res.roi:6.1f}%  "
              f"CI=[{roi_res.ci_low:.1f}, {roi_res.ci_high:.1f}]%")


def _fmt_summary(s: BacktestSummary) -> str:
    modes = ", ".join(f"{k}:{v}" for k, v in sorted(s.mode_counts.items()))
    return (f"  {s.label:<35} races={s.n_races:>4} bets={s.n_bets:>5}  "
            f"ROI={s.roi:6.1f}% CI=[{s.ci_low:.1f}, {s.ci_high:.1f}]%  "
            f"cost={s.cost:,.0f} payout={s.payout:,.0f}"
            + (f"  modes=({modes})" if modes else ""))


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--split-date", default="2026-01-01",
                   help="walk-forward valid 開始 (YYYY-MM-DD)")
    p.add_argument("--bootstrap", type=int, default=DEFAULT_BOOTSTRAP)
    p.add_argument("--cache-path", default=None)
    p.add_argument("--taste-axis", action="store_true",
                   help="P2a support_cut 比較も実行")
    return p.parse_args()


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                          errors="replace")
        except (AttributeError, ValueError):
            pass
    args = parse_args()
    cache_path = Path(args.cache_path) if args.cache_path else None
    races_raw = load_backtest_cache(path=cache_path)
    split = args.split_date.replace("-", "")

    train = [r for r in races_raw if str(r.get("race_id", ""))[:8] < split]
    valid = [r for r in races_raw if str(r.get("race_id", ""))[:8] >= split]

    print(f"backtest_cache: {len(races_raw)} races")
    print(f"walk-forward split={args.split_date}  train={len(train)} valid={len(valid)}")

    baseline = run_backtest(
        valid, strategy="concentrate", sizing=sz.DEFAULT_SIZER,
        bootstrap_n=args.bootstrap)
    adaptive = run_backtest(
        valid, strategy="adaptive", sizing=sz.ADAPTIVE_SIZER,
        bootstrap_n=args.bootstrap)

    print("\n=== valid 期間 ROI (full-selection legs) ===")
    print(_fmt_summary(baseline))
    print(_fmt_summary(adaptive))
    delta = adaptive.roi - baseline.roi
    ci_ok = adaptive.ci_low > baseline.roi
    print(f"\n  ΔROI (adaptive - baseline) = {delta:+.1f}pt")
    print(f"  改善判定 (adaptive CI下限 > baseline ROI): {'✅ PASS' if ci_ok else '❌ FAIL'}")
    if not ci_ok:
        print("  ※ live 反映不可 (シズネ + ふくだ判断待ち)。 dry-run/shadow 観察のみ。")

    if args.taste_axis:
        run_taste_axis_backtest(valid, bootstrap_n=args.bootstrap)

    return 0 if ci_ok else 1


if __name__ == "__main__":
    sys.exit(main())
