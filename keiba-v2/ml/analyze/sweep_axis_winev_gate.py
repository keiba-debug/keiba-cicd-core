#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""◎過剰人気 見送りゲート (min_axis_win_ev) の sweep — S172。

explore_axis_confidence で「◎の win_ev (単勝EV) が低い (過剰人気) レースはフォメで大負け
(win_ev<0.78 の50R が ROI49%・PnL-44,740 = 大負けの主犯)」と発見。 ◎win_ev 下限ゲートを
足すと -31k→+13k の見込み。 本検証は ★ゲート適用後の全体★ (層別でなく1母集団) の
月中央/天井/maxDD/ROI/PnL を実払戻で測り、 壁72.5%維持 & 現行 (ゲート無し・月中央90%) 比で
改善するかを判定する。

精算=haraimodoshi 実払戻 (リークなし)。 trim 用三連単 OD はバッチ確定値注入 (接続枯渇回避)。
win_ev は predictions 直前オッズ (leak-free) = ★後知恵でない★ ([[feedback_odds_gate_hindsight]])。

CLI:
    python -m ml.analyze.sweep_axis_winev_gate
    python -m ml.analyze.sweep_axis_winev_gate --start 2026-01 --end 2026-05-31
"""
from __future__ import annotations

import argparse
import io
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.analyze.analyze_paddock_signal import load_paddock_marks  # noqa: E402
from ml.analyze.backtest_bet_templates import load_haraimodoshi  # noqa: E402
from ml.analyze.explore_axis_confidence import _load_all_trifecta_odds  # noqa: E402
from ml.analyze.validate_sanrentan_formation import RaceAgg, _legs_to_bets  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.strategies import bettype_selection as bs  # noqa: E402
from ml.strategies import bettype_sizing as sz  # noqa: E402
from ml.strategies.anaba_picks import load_anaba_backtest  # noqa: E402

DEFAULT_PER_RACE_CAP = 5200

# (ラベル, kwargs to size_race_sanrentan_formation)。 本番値 (ev1.5/gap0.4/wp0.15) は既定で固定、
#   ◎win_ev 下限ゲートだけ振る。 0=現行 (ゲート無し)。
CONFIGS = [
    ("現行 ev_gate=0",  dict(min_axis_win_ev=0.0)),   # デフォルト0.6(本番化済)に引かれないよう明示
    ("ev_gate=0.6",     dict(min_axis_win_ev=0.6)),
    ("ev_gate=0.7",     dict(min_axis_win_ev=0.7)),
    ("ev_gate=0.78",    dict(min_axis_win_ev=0.78)),
    ("ev_gate=0.9",     dict(min_axis_win_ev=0.9)),
    ("ev_gate=1.0",     dict(min_axis_win_ev=1.0)),
]


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--start", default="2026-01")
    ap.add_argument("--end", default="2026-05-31")
    ap.add_argument("--strategy", default="concentrate")
    ap.add_argument("--per-race-cap", type=int, default=DEFAULT_PER_RACE_CAP)
    args = ap.parse_args()

    from ml.export_formation_backtest import load_predictions_races
    races = load_predictions_races(start_date=args.start, end_date=args.end)
    print(f"predictions: {len(races)} races ({args.start}~{args.end}, 直前オッズ leak-free)")
    codes = [str(r.get("race_id") or "") for r in races if r.get("race_id")]
    haraimodoshi = load_haraimodoshi(codes)
    anaba = load_anaba_backtest(codes)
    paddock = load_paddock_marks(codes)
    trifecta = _load_all_trifecta_odds(codes)
    print(f"  haraimodoshi={len(haraimodoshi)}  印4={len(anaba)}  パドック={len(paddock)}"
          f"  三連単OD={len(trifecta)}R")

    arms: Dict[str, RaceAgg] = {lbl: RaceAgg() for lbl, _ in CONFIGS}
    n_eval = 0
    for r in races:
        rid = str(r.get("race_id") or "")
        race_pay = haraimodoshi.get(rid)
        if not race_pay or not race_pay.get("sanrentan"):
            continue
        sel = bs.evaluate_and_select(r, strategy=args.strategy, ev_floor=bs.DEFAULT_EV_FLOOR)
        if sel is None:
            continue
        race_eff = be.process_race(r, axis=sel.axis_umaban)
        if race_eff is None or not race_eff.strengths:
            continue
        n_eval += 1
        if n_eval % 200 == 0:
            print(f"   ... {n_eval} races", file=sys.stderr)
        st_odds = trifecta.get(rid, {})
        anaba_u = anaba.get(rid, [])
        pad = paddock.get(rid, {})
        for lbl, kw in CONFIGS:
            rs = sz.size_race_sanrentan_formation(
                race_eff, sel, bankroll=10000, per_race_cap=args.per_race_cap,
                sanrentan_odds=st_odds, anaba_umabans=anaba_u, paddock_marks=pad, **kw)
            arms[lbl].add_race(rid, _legs_to_bets(rid, rs.legs, race_pay))

    print(f"  評価レース={n_eval}\n")
    hdr = (f"  {'config':18}{'発動R':>7}{'点/R':>6}{'ROI':>7}{'月中央':>7}"
           f"{'的中R%':>7}{'≥1000':>7}{'最高配当':>11}{'maxDD':>11}{'PnL':>11}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for lbl, _ in CONFIGS:
        s = arms[lbl].summary()
        if not s:
            print(f"  {lbl:18}{'(発動なし)':>7}")
            continue
        star = " ★" if s["med_roi"] >= 72.5 else ""
        print(f"  {lbl:18}{s['n_races']:>7}{s['avg_pts']:>6.1f}{s['roi']:>6.0f}%"
              f"{s['med_roi']:>6.0f}%{s['hit_race_pct']:>6.0f}%{s['big1000']:>7}"
              f"{s['max_pay']:>11,.0f}{s['maxDD']:>11,.0f}{s['pnl']:>+11,.0f}{star}")
    print("  " + "-" * (len(hdr) - 2))
    print("  ★=月中央≥72.5% (三連系控除率の壁)。 精算=haraimodoshi実払戻 (リークなし)")
    print("  win_ev=◎の単勝EV (pred_w×直前OD・後知恵でない)。 ゲート↑=過剰人気◎を多く見送る (発動↓)")

    # 月別ROI内訳 (月中央が非単調なので、 ノイズか実力かを生データで確認する)
    print("\n■ 月別ROI内訳  月:ROI%(発動R)")
    for lbl, _ in CONFIGS:
        bymon: Dict[str, list] = defaultdict(lambda: [0.0, 0.0])
        for b in arms[lbl].bets:
            ym = b.race_id[:6]
            bymon[ym][0] += b.cost
            bymon[ym][1] += b.payout
        parts = []
        for m in sorted(bymon):
            c, p = bymon[m]
            roi = p / c * 100 if c > 0 else 0.0
            nr = sum(1 for rid in arms[lbl].fired if rid[:6] == m)
            parts.append(f"{m[4:]}:{roi:4.0f}%({nr})")
        print(f"  {lbl:16} " + "  ".join(parts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
