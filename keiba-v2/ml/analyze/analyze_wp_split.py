#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""W/P乖離 = 「勝ち切る馬」vs「好走止まりの馬」分離の予備分析 (Session 148 / 捨て馬券の土台)

ふくだの買い方知恵: 「経験的に、勝ち切る可能性が明らかにある馬と、好走する
(2-3着止まり) 馬を分けられるときがある」→ 例: 三連複◎○▲が合成2.0倍で
「○の頭はない」と読めるとき、三連複を捨て 三連単 ◎▲→◎○▲→◎○▲ だけ買う。

これを W(勝率) と P(複勝率) の乖離で機械再現できるかを検証する:
  win_share = pred_w / pred_p  (来たとき勝ち切る度。低い = 2-3着止まり型)

検証1: win_share 分位 × P(1着|3着内) — 分離が実在するか (ベースライン≈1/3)
検証2: ○(composite 2位) を win_share で P型/W型に2分 → 1着率の差
検証3: テンプレ対決 (haraimodoshi 実配当・flat100):
  - base   : 三連単 ◎○▲ BOX 6点 (常時)
  - smart  : ○が P型 (win_share がレース内で突出して低い) なら
             ◎▲→◎○▲→◎○▲ (○の頭を捨てる 4点)、それ以外は BOX 6点

CLI:
    python -m ml.analyze.analyze_wp_split
    python -m ml.analyze.analyze_wp_split --p-type-ratio 0.6
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
from ml.analyze.backtest_bet_templates import (  # noqa: E402
    load_haraimodoshi, ticket_payout,
)
from ml.strategies import bet_templates as bt  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.utils.backtest_cache import load_backtest_cache  # noqa: E402


def build_horse_rows(races) -> List[dict]:
    """全馬 1 行: composite順位 / pred_w / pred_p / win_share / finish。"""
    rows: List[dict] = []
    for raw in races:
        pred = cache_race_to_pred(raw)
        if pred is None:
            continue
        entries = pred.get("entries", [])
        if not any(int(e.get("finish_position") or 99) == 1 for e in entries):
            continue
        re_ = be.process_race(pred)
        if re_ is None or not re_.strengths:
            continue
        fin = {int(e.get("umaban") or 0): int(e.get("finish_position") or 99)
               for e in entries}
        rid = str(pred["race_id"])
        for i, s in enumerate(re_.strengths):
            if s.pred_w is None or s.pred_p is None or s.pred_p <= 0:
                continue
            # specialist レースは pred_p が display_score (確率でない) → 除外
            if s.p_source != "model":
                continue
            rows.append({
                "rid": rid, "date": rid[:8], "comp_rank": i + 1,
                "umaban": s.umaban, "w": s.pred_w, "p": s.pred_p,
                "share": s.pred_w / s.pred_p,
                "fin": fin.get(s.umaban, 99),
            })
    return rows


def quantile_table(rows: List[dict], *, label: str, n_q: int = 5):
    """win_share 分位 × {3着内率, 1着率, P(1着|3着内)}。"""
    if not rows:
        print(f"  ({label}: データなし)")
        return
    shares = sorted(r["share"] for r in rows)
    bounds = [shares[int(len(shares) * k / n_q)] for k in range(1, n_q)]

    def _q(v: float) -> int:
        for qi, b in enumerate(bounds):
            if v < b:
                return qi
        return n_q - 1

    agg = defaultdict(lambda: {"n": 0, "top3": 0, "win": 0, "second3": 0})
    for r in rows:
        a = agg[_q(r["share"])]
        a["n"] += 1
        if r["fin"] <= 3:
            a["top3"] += 1
            if r["fin"] == 1:
                a["win"] += 1
            else:
                a["second3"] += 1
        elif r["fin"] == 1:
            a["win"] += 1
    print(f"\n  ◆ {label}: win_share(=W/P) 分位 → 勝ち切り度 (n={len(rows):,})")
    print(f"  {'分位':<14}{'share範囲':>16}{'n':>8}{'3着内率':>9}{'1着率':>8}"
          f"{'P(1着|3着内)':>13}")
    print("  " + "-" * 70)
    for qi in range(n_q):
        a = agg[qi]
        if a["n"] == 0:
            continue
        lo = shares[0] if qi == 0 else bounds[qi - 1]
        hi = bounds[qi] if qi < n_q - 1 else shares[-1]
        t3 = a["top3"] / a["n"] * 100
        w1 = a["win"] / a["n"] * 100
        cw = a["win"] / a["top3"] * 100 if a["top3"] else 0.0
        print(f"  Q{qi + 1:<13}{f'{lo:.2f}-{hi:.2f}':>16}{a['n']:>8,}{t3:>8.1f}%"
              f"{w1:>7.1f}%{cw:>12.1f}%")
    print("  → P(1着|3着内) が分位で単調に変われば「来ても勝ち切れない馬」を事前に分離できている")


def maru_split_analysis(rows_by_race: Dict[str, List[dict]], *, p_type_ratio: float):
    """○(composite 2位) を P型/W型に分けて 1着率・P(1着|3着内) を比較。

    P型判定: ○の win_share が ◎○▲ 3頭の中央値 × p_type_ratio 未満
    (レース内相対で「この馬だけ勝ち切り度が低い」を拾う)。
    """
    p_rows, w_rows = [], []
    for rid, rs in rows_by_race.items():
        top3 = [r for r in rs if r["comp_rank"] <= 3]
        if len(top3) < 3:
            continue
        maru = next((r for r in top3 if r["comp_rank"] == 2), None)
        if maru is None:
            continue
        med = statistics.median(r["share"] for r in top3)
        (p_rows if maru["share"] < med * p_type_ratio else w_rows).append(maru)
    print(f"\n  ◆ ○(composite 2位) の P型/W型 比較 (P型 = share < 印3頭中央値×{p_type_ratio})")
    print(f"  {'型':<18}{'n':>7}{'3着内率':>9}{'1着率':>8}{'P(1着|3着内)':>13}")
    print("  " + "-" * 58)
    for label, rs in (("P型 (頭なし候補)", p_rows), ("W型 (頭あり)", w_rows)):
        if not rs:
            continue
        n = len(rs)
        t3 = sum(1 for r in rs if r["fin"] <= 3)
        w1 = sum(1 for r in rs if r["fin"] == 1)
        print(f"  {label:<18}{n:>7,}{t3 / n * 100:>8.1f}%{w1 / n * 100:>7.1f}%"
              f"{(w1 / t3 * 100 if t3 else 0):>12.1f}%")


def template_duel(rows_by_race: Dict[str, List[dict]], haraimodoshi,
                  *, p_type_ratio: float):
    """三連単 BOX vs ○頭捨てフォーメーション の実配当対決 (月別中央値込み)。"""
    box = bt.BetComponent("sanrentan", [["◎", "○", "▲"]] * 3)
    drop = bt.BetComponent("sanrentan", [["◎", "▲"], ["◎", "○", "▲"], ["◎", "○", "▲"]])

    stats = {k: defaultdict(lambda: [0.0, 0.0]) for k in ("base", "smart")}  # ym->[c,p]
    fire_smart = 0
    n = 0
    for rid, rs in rows_by_race.items():
        top3 = sorted((r for r in rs if r["comp_rank"] <= 3), key=lambda r: r["comp_rank"])
        if len(top3) < 3:
            continue
        marks = {"◎": [top3[0]["umaban"]], "○": [top3[1]["umaban"]], "▲": [top3[2]["umaban"]]}
        med = statistics.median(r["share"] for r in top3)
        maru_is_p = top3[1]["share"] < med * p_type_ratio
        rpay = haraimodoshi.get(rid, {})
        ym = rid[:6]
        n += 1
        for key, comp in (("base", box), ("smart", drop if maru_is_p else box)):
            tickets = bt.expand_component(comp, marks)
            c = 100.0 * len(tickets)
            p = float(sum(ticket_payout(tk, rpay) for tk in tickets))
            stats[key][ym][0] += c
            stats[key][ym][1] += p
        if maru_is_p:
            fire_smart += 1

    print(f"\n  ◆ テンプレ対決: 三連単◎○▲BOX vs ○P型なら頭捨て(◎▲→◎○▲→◎○▲)"
          f"  (n={n:,}R, ○P型発火={fire_smart:,}R)")
    print(f"  {'戦略':<10}{'ROI':>8}{'月中央値':>9}{'+月':>8}")
    print("  " + "-" * 40)
    for key in ("base", "smart"):
        ms = stats[key]
        cost = sum(v[0] for v in ms.values())
        pay = sum(v[1] for v in ms.values())
        rois = [v[1] / v[0] * 100 for v in ms.values() if v[0] > 0]
        med = statistics.median(rois) if rois else 0.0
        plus = sum(1 for v in rois if v >= 100)
        print(f"  {key:<10}{pay / cost * 100 if cost else 0:>7.1f}%{med:>8.1f}%"
              f"{plus:>4}/{len(rois):<3}")
    # 発火レースだけの差分も (smart が効いた瞬間の純効果)
    print("  (発火レース内のみの比較)")
    cost_b = pay_b = cost_s = pay_s = 0.0
    for rid, rs in rows_by_race.items():
        top3 = sorted((r for r in rs if r["comp_rank"] <= 3), key=lambda r: r["comp_rank"])
        if len(top3) < 3:
            continue
        med = statistics.median(r["share"] for r in top3)
        if not (top3[1]["share"] < med * p_type_ratio):
            continue
        marks = {"◎": [top3[0]["umaban"]], "○": [top3[1]["umaban"]], "▲": [top3[2]["umaban"]]}
        rpay = haraimodoshi.get(rid, {})
        for comp, acc in ((box, "b"), (drop, "s")):
            tickets = bt.expand_component(comp, marks)
            c = 100.0 * len(tickets)
            p = float(sum(ticket_payout(tk, rpay) for tk in tickets))
            if acc == "b":
                cost_b += c
                pay_b += p
            else:
                cost_s += c
                pay_s += p
    if cost_b > 0 and cost_s > 0:
        print(f"    BOX6点      : ROI {pay_b / cost_b * 100:>6.1f}%  (cost {cost_b:,.0f})")
        print(f"    ○頭捨て4点  : ROI {pay_s / cost_s * 100:>6.1f}%  (cost {cost_s:,.0f})")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--cache-path", default=None)
    p.add_argument("--p-type-ratio", type=float, default=0.6,
                   help="○P型判定: share < 印3頭中央値×ratio (既定0.6)")
    return p.parse_args()


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = parse_args()
    races = load_backtest_cache(path=Path(args.cache_path) if args.cache_path else None)
    print(f"backtest_cache: {len(races)} races")
    rows = build_horse_rows(races)
    rows_by_race: Dict[str, List[dict]] = defaultdict(list)
    for r in rows:
        rows_by_race[r["rid"]].append(r)

    # 検証1: 全馬 / 印対象 (composite top5)
    quantile_table(rows, label="全馬")
    quantile_table([r for r in rows if r["comp_rank"] <= 5], label="印対象 (composite top5)")
    # 検証2: ○の P型/W型
    maru_split_analysis(rows_by_race, p_type_ratio=args.p_type_ratio)
    # 検証3: テンプレ対決 (実配当)
    print("\n  loading haraimodoshi...")
    haraimodoshi = load_haraimodoshi(list(rows_by_race.keys()))
    template_duel(rows_by_race, haraimodoshi, p_type_ratio=args.p_type_ratio)
    return 0


if __name__ == "__main__":
    sys.exit(main())
