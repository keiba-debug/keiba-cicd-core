#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""D: 単勝多点買いゲート検証 → 三連単頭複数への発展 (Session 148)

ふくだ構想:
  「1番人気が飛びそう (AI評価低) なとき、勝ちそうな馬を複数買っても合成オッズが
   X% を超えるなら単勝多点買いはあり。光が見えたら同じゲートで三連単の頭を
   複数にする戦略 (◎▲→…) につながる」

ゲート (L3 = 買うか降りるか。オッズは合成の絶対水準のみ・配分には使わない):
  - fav_weak : 1番人気 (最小単勝オッズ馬) の composite rank >= 4 = AI は評価していない
  - G floor  : 買う単勝群の合成オッズ G = 1/Σ(1/oₖ) が閾値以上 (トリガミ回避の絶対水準)

構成 (AI = composite 序列):
  - tansho_ai1   : AI 1位の単勝 (対照 = ◎単勝)
  - tansho_ai2   : AI 1-2位の単勝 2点
  - tansho_ai3   : AI 1-3位の単勝 3点
  - srt_box3     : 三連単 AI 1-3位 BOX 6点 (対照)
  - srt_2head    : 三連単 頭2頭 [AI1,AI2] → [AI1-3] → [AI1-4] 8点 (頭複数の発展形)

CLI:
    python -m ml.analyze.backtest_tansho_multi
    python -m ml.analyze.backtest_tansho_multi --g-floors 2.0,2.5,3.0
"""

from __future__ import annotations

import argparse
import io
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.analyze.backtest_bettype_fund import cache_race_to_pred  # noqa: E402
from ml.analyze.backtest_bet_templates import load_haraimodoshi  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.utils.backtest_cache import load_backtest_cache  # noqa: E402
from ml.utils.filters import is_obstacle  # noqa: E402

FAV_WEAK_RANK = 4   # 1番人気の composite rank がこれ以上 = AI は推していない


def synth_g(odds: List[Optional[float]]) -> Optional[float]:
    inv = sum(1.0 / o for o in odds if o and o > 0)
    return (1.0 / inv) if inv > 0 else None


def build_records(races, haraimodoshi, *, from_predictions: bool = False) -> List[dict]:
    """from_predictions=True: predictions.json の race をそのまま使う (spot check 用)。

    predictions には finish_position が無いので結果確定は haraimodoshi (tansho) の
    有無で判定。 オッズは予想時点 (vb_refresh 直前オッズ) = 本番ゲート判定と同条件。
    """
    recs: List[dict] = []
    for raw in races:
        if from_predictions:
            pred = raw
            if is_obstacle(raw):
                continue
        else:
            pred = cache_race_to_pred(raw)
        if pred is None:
            continue
        entries = pred.get("entries", [])
        rid_chk = str(pred.get("race_id") or "")
        if from_predictions:
            if not (haraimodoshi.get(rid_chk) or {}).get("tansho"):
                continue  # 結果未確定 / 中止
        elif not any(int(e.get("finish_position") or 99) == 1 for e in entries):
            continue
        re_ = be.process_race(pred)
        if re_ is None or len(re_.strengths) < 4:
            continue
        s = re_.strengths
        with_odds = [x for x in s if x.odds and x.odds > 0]
        if not with_odds:
            continue
        fav = min(with_odds, key=lambda x: x.odds)
        fav_rank = next((i + 1 for i, x in enumerate(s) if x.umaban == fav.umaban), 99)
        rid = str(pred["race_id"])
        rpay = haraimodoshi.get(rid, {})
        top = s[:4]
        recs.append({
            "rid": rid, "date": rid[:8],
            "fav_odds": fav.odds, "fav_rank": fav_rank,
            "uma": [x.umaban for x in top],
            "odds": [x.odds for x in top],
            "tan_pay": rpay.get("tansho", {}),
            "srt_pay": rpay.get("sanrentan", {}),
        })
    return recs


# ---------------------------------------------------------------------------
# 構成の精算 (flat 100円/点)
# ---------------------------------------------------------------------------

def settle(rec: dict, kind: str) -> Optional[tuple]:
    """(cost, payout, g) — g は単勝系のみ (三連系は odds_db なしのため None)。"""
    uma = rec["uma"]
    odds = rec["odds"]
    tan = rec["tan_pay"]
    if kind == "tansho_ai1":
        legs = [0]
    elif kind == "tansho_ai2":
        legs = [0, 1]
    elif kind == "tansho_ai3":
        legs = [0, 1, 2]
    elif kind == "srt_box3":
        from itertools import permutations
        pts = list(permutations(uma[:3], 3))
        cost = 100.0 * len(pts)
        pay = sum(rec["srt_pay"].get(t, 0) for t in pts)
        return cost, float(pay), None
    elif kind == "srt_2head":
        pts = []
        for h1 in uma[:2]:
            for h2 in uma[:3]:
                if h2 == h1:
                    continue
                for h3 in uma[:4]:
                    if h3 in (h1, h2):
                        continue
                    pts.append((h1, h2, h3))
        cost = 100.0 * len(pts)
        pay = sum(rec["srt_pay"].get(t, 0) for t in pts)
        return cost, float(pay), None
    else:
        raise ValueError(kind)
    cost = 100.0 * len(legs)
    pay = sum(tan.get(uma[i], 0) for i in legs)
    g = synth_g([odds[i] for i in legs])
    return cost, float(pay), g


KINDS = ["tansho_ai1", "tansho_ai2", "tansho_ai3", "srt_box3", "srt_2head"]


def aggregate(recs: List[dict], kind: str, *, gate, g_floor: Optional[float]) -> dict:
    monthly: Dict[str, List[float]] = defaultdict(lambda: [0.0, 0.0])
    cost_all = pay_all = 0.0
    fire = hits = 0
    for r in recs:
        if not gate(r):
            continue
        st = settle(r, kind)
        if st is None:
            continue
        c, p, g = st
        if g_floor is not None and kind.startswith("tansho"):
            if g is None or g < g_floor:
                continue
        cost_all += c
        pay_all += p
        fire += 1
        if p > 0:
            hits += 1
        m = monthly[r["date"][:6]]
        m[0] += c
        m[1] += p
    rois = [v[1] / v[0] * 100 for v in monthly.values() if v[0] > 0]
    return {
        "fire": fire, "roi": pay_all / cost_all * 100 if cost_all else 0.0,
        "med": statistics.median(rois) if rois else 0.0,
        "plus": sum(1 for v in rois if v >= 100), "n_m": len(rois),
        "hit": hits / fire * 100 if fire else 0.0,
    }


GATES = {
    "ALL": lambda r: True,
    "1人気弱 (AIrank>=4)": lambda r: r["fav_rank"] >= FAV_WEAK_RANK,
    "1人気弱 & 1人気<3.5倍": lambda r: r["fav_rank"] >= FAV_WEAK_RANK and r["fav_odds"] < 3.5,
}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--cache-path", default=None)
    p.add_argument("--g-floors", default="2.0,2.5,3.0")
    p.add_argument("--source", default="cache", choices=["cache", "predictions"],
                   help="predictions = 本番 predictions.json で spot check (リークなし・"
                        "直前オッズ判定。 2026-01 split で旧モデル期/現行モデル期が分かれる)")
    p.add_argument("--start", default="2025-03")
    p.add_argument("--end", default="2026-12")
    return p.parse_args()


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = parse_args()
    floors = [float(x) for x in args.g_floors.split(",")]
    from_predictions = args.source == "predictions"
    if from_predictions:
        from ml.export_formation_backtest import load_predictions_races
        races = load_predictions_races(start_date=args.start, end_date=args.end)
        print(f"predictions.json: {len(races)} races ({args.start}~{args.end}, leak-free)")
    else:
        races = load_backtest_cache(path=Path(args.cache_path) if args.cache_path else None)
        print(f"backtest_cache: {len(races)} races")
    codes = [str(r.get("race_id")) for r in races if r.get("race_id")]
    print("  loading haraimodoshi...")
    haraimodoshi = load_haraimodoshi(codes)
    print("  building records...")
    recs = build_records(races, haraimodoshi, from_predictions=from_predictions)
    print(f"  records={len(recs)}")
    n_weak = sum(1 for r in recs if r["fav_rank"] >= FAV_WEAK_RANK)
    print(f"  1人気弱 (AIrank>={FAV_WEAK_RANK}): {n_weak}R ({n_weak / len(recs) * 100:.1f}%)\n")

    hdr = (f"  {'構成':<14}{'fire':>7}{'ROI':>8}{'月中央':>8}{'+月':>7}{'的中率':>8}")
    for gname, gate in GATES.items():
        print("=" * 64)
        print(f"  ◆ ゲート: {gname}")
        print(hdr)
        print("  " + "-" * 60)
        for kind in KINDS:
            a = aggregate(recs, kind, gate=gate, g_floor=None)
            print(f"  {kind:<14}{a['fire']:>7,}{a['roi']:>7.1f}%{a['med']:>7.1f}%"
                  f"{a['plus']:>3}/{a['n_m']:<3}{a['hit']:>7.1f}%")
        print()

    # G floor を単勝多点に重ねる (1人気弱ゲート上で)
    print("=" * 64)
    print("  ◆ 1人気弱ゲート × 合成オッズ G フロア (単勝多点のみ)")
    print(f"  {'構成':<14}{'Gfloor':>7}{'fire':>7}{'ROI':>8}{'月中央':>8}{'+月':>7}{'的中率':>8}")
    print("  " + "-" * 60)
    gate = GATES["1人気弱 (AIrank>=4)"]
    for kind in ("tansho_ai2", "tansho_ai3"):
        for fl in floors:
            a = aggregate(recs, kind, gate=gate, g_floor=fl)
            print(f"  {kind:<14}{fl:>7.1f}{a['fire']:>7,}{a['roi']:>7.1f}%{a['med']:>7.1f}%"
                  f"{a['plus']:>3}/{a['n_m']:<3}{a['hit']:>7.1f}%")
    print("\n  → tansho_ai2/3 が ALL より 1人気弱ゲートで改善し、Gフロアで更に締まるなら"
          "「単勝多点に光」。srt_2head が srt_box3 を同ゲートで上回るなら頭複数化も成立。")

    # --- 月別推移 + train/valid (頑健性チェック / スヌーピング監査) ---
    print("\n" + "=" * 64)
    print("  ◆ 月別推移 (1人気弱ゲート)")
    for kind, fl in (("tansho_ai2", None), ("tansho_ai2", 2.5), ("tansho_ai1", None)):
        monthly: Dict[str, List[float]] = defaultdict(lambda: [0.0, 0.0, 0])
        tr = [0.0, 0.0]
        va = [0.0, 0.0]
        for r in recs:
            if r["fav_rank"] < FAV_WEAK_RANK:
                continue
            st = settle(r, kind)
            if st is None:
                continue
            c, p, g = st
            if fl is not None and (g is None or g < fl):
                continue
            m = monthly[r["date"][:6]]
            m[0] += c
            m[1] += p
            m[2] += 1
            t = tr if r["date"] < "20260101" else va
            t[0] += c
            t[1] += p
        label = f"{kind}" + (f" G>={fl}" if fl else "")
        cells = "".join(
            f"  {ym[2:]}:{v[1] / v[0] * 100:>4.0f}%({v[2]:>2})" if v[0] > 0 else f"  {ym[2:]}:  -"
            for ym, v in sorted(monthly.items()))
        print(f"  {label:<20}{cells}")
        print(f"  {'':<20}  train(=~25/12): {tr[1] / tr[0] * 100 if tr[0] else 0:.1f}%"
              f"   valid(26/01~): {va[1] / va[0] * 100 if va[0] else 0:.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
