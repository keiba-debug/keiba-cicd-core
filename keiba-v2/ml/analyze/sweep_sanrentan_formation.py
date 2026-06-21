#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""三連単フォーメーション 購入/見送りゲートの sweep (S171・ふくだ「判定をシビアに」)。

複数の (head_ev_floor, min_axis_gap, win_prob_floor, max_points, n_head_max) を ★1回のDBパス★
で比較する (三連単確定オッズ取得 = レースあたり1クエリが重いので、 全config を同じ race ループ内で
評価して DB コストを1回に抑える)。 精算は haraimodoshi 実払戻 (リークなし)。

「シビアにする」= 発動レースを絞って月中央ROI/天井を改善できる設定を探す。 控除率の壁=72.5%を
月中央で超える config があれば本番候補。

CLI:
    python -m ml.analyze.sweep_sanrentan_formation
    python -m ml.analyze.sweep_sanrentan_formation --start 2026-01 --end 2026-05-31
"""
from __future__ import annotations

import argparse
import io
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from core.odds_db import get_final_trifecta_odds  # noqa: E402
from ml.analyze.analyze_paddock_signal import load_paddock_marks  # noqa: E402
from ml.analyze.backtest_bet_templates import load_haraimodoshi  # noqa: E402
from ml.analyze.validate_sanrentan_formation import RaceAgg, _legs_to_bets  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.strategies import bettype_selection as bs  # noqa: E402
from ml.strategies import bettype_sizing as sz  # noqa: E402
from ml.strategies.anaba_picks import load_anaba_backtest  # noqa: E402

DEFAULT_PER_RACE_CAP = 5200

# (ラベル, kwargs to size_race_sanrentan_formation)
# S171後半: ふくだ「3連単なので点数増やしてOK」(阪神7R 頭ばっちりも2-3着カバー狭で取りこぼし)。
#   strict ゲート(ev1.5/gap0.4/wp0.15)を固定し、 ★3着候補幅(n_third)・連軸(n_renjiku)・点数上限★ を
#   広げて「頭が当たったレースを取りこぼさない」+ 天井捕捉を増やす設定を探す。 月中央が壁(72.5%)を
#   保つ範囲で広げる。
_G = dict(head_ev_floor=1.5, min_axis_gap=0.4, win_prob_floor=0.15)  # strict ゲート (本番値・固定)
CONFIGS = [
    ("本番 n3=4 rj2 mp36",   dict(**_G, n_third_composite=4, n_renjiku=2)),   # 現行 (~5-6点)
    ("広 n3=6 rj2",          dict(**_G, n_third_composite=6, n_renjiku=2)),
    ("広 n3=8 rj2",          dict(**_G, n_third_composite=8, n_renjiku=2)),
    ("広 n3=6 rj3",          dict(**_G, n_third_composite=6, n_renjiku=3)),
    ("広 n3=8 rj3",          dict(**_G, n_third_composite=8, n_renjiku=3)),
    ("広 n3=10 rj3",         dict(**_G, n_third_composite=10, n_renjiku=3)),
    ("広 n3=8 rj3 hd4",      dict(**_G, n_third_composite=8, n_renjiku=3, n_head_max=4)),
    # ゲート少し緩め+広げ (発動増やしつつ天井) — 壁を割らないか確認
    ("緩 ev1.3 gap0.4 n3=8 rj3", dict(head_ev_floor=1.3, min_axis_gap=0.4,
                                      win_prob_floor=0.15, n_third_composite=8, n_renjiku=3)),
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
    print(f"  haraimodoshi={len(haraimodoshi)}  印4={len(anaba)}  パドック={len(paddock)}")

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
        st_odds = get_final_trifecta_odds(rid)
        anaba_u = anaba.get(rid, [])
        pad = paddock.get(rid, {})
        for lbl, kw in CONFIGS:
            rs = sz.size_race_sanrentan_formation(
                race_eff, sel, bankroll=10000, per_race_cap=args.per_race_cap,
                sanrentan_odds=st_odds, anaba_umabans=anaba_u, paddock_marks=pad, **kw)
            arms[lbl].add_race(rid, _legs_to_bets(rid, rs.legs, race_pay))

    print(f"  評価レース={n_eval}\n")
    hdr = (f"  {'config':22}{'発動R':>7}{'点/R':>6}{'ROI':>7}{'月中央':>7}"
           f"{'的中R%':>7}{'≥1000':>7}{'最高配当':>11}{'maxDD':>11}{'PnL':>11}")
    print(hdr)
    print("  " + "-" * (len(hdr) - 2))
    for lbl, _ in CONFIGS:
        s = arms[lbl].summary()
        if not s:
            print(f"  {lbl:22}{'(発動なし)':>7}")
            continue
        star = " ★" if s["med_roi"] >= 72.5 else ""
        print(f"  {lbl:22}{s['n_races']:>7}{s['avg_pts']:>6.1f}{s['roi']:>6.0f}%"
              f"{s['med_roi']:>6.0f}%{s['hit_race_pct']:>6.0f}%{s['big1000']:>7}"
              f"{s['max_pay']:>11,.0f}{s['maxDD']:>11,.0f}{s['pnl']:>+11,.0f}{star}")
    print("  " + "-" * (len(hdr) - 2))
    print("  ★=月中央ROIが三連系控除率の壁72.5%以上。 精算=haraimodoshi実払戻(リークなし)")
    print("  gap=◎の格(composite gap)見送りゲート / ev=頭のwin_ev閾値 / wp=頭のpred_w閾値 / mp=最大点数")
    return 0


if __name__ == "__main__":
    sys.exit(main())
