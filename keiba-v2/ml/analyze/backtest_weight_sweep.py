#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""A+F3+B: 本命フォーメーション weight sweep + 的中時リターン分布 + 買い足し検証 (Session 148)

honmei_formation (三連複1頭軸保険 + ◎○▲三連単BOX) の配分 weight を sweep し、
「当たった時にでかく勝つ」(hit時リターン分布 中央値/p90/max) と
全体ROI・月別中央値・maxDD のトレードオフ (フロンティア) を定量化する。

仕組み: コンポーネント別に flat100円 精算を 1 回だけ行い、 weight は線形再構成
  (cost(w)=Σ wᵢ·costᵢ, payout(w)=Σ wᵢ·payoutᵢ) → sweep は集計のみで安い。

買い足し (B案): 単勝◎ / 馬単◎→○▲ を weight 0 (なし) 〜 で同時に sweep し
「本命セットに足す価値」を測る。 コンポーネント間レースPnL相関も出力
(松風知見9 ポートフォリオ理論: 相関が高い券種の併用は同じ賭けを2回するだけ)。

哲学整合: 配分は評価ベース (feedback_betting_philosophy §5)。 sweep は
「テンプレ定数の選定」であって、レース毎にオッズで動的に変える話ではない。

CLI:
    python -m ml.analyze.backtest_weight_sweep              # composite(理論)モード
    python -m ml.analyze.backtest_weight_sweep --mode ai    # 実AI印 (崖カット) モード
    python -m ml.analyze.backtest_weight_sweep --top 30
"""

from __future__ import annotations

import argparse
import io
import statistics
import sys
from collections import defaultdict
from itertools import product
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.ai_marks.assign import assign_ai_marks  # noqa: E402
from ml.analyze.backtest_bettype_fund import cache_race_to_pred  # noqa: E402
from ml.analyze.backtest_bet_templates import (  # noqa: E402
    load_haraimodoshi, ticket_payout,
)
from ml.export_bet_template_lab import ai_marks_to_markset  # noqa: E402
from ml.strategies import bet_templates as bt  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.utils.backtest_cache import load_backtest_cache  # noqa: E402


# ---------------------------------------------------------------------------
# 買いブロック (コンポーネント)。 weight は sweep 側で掛けるため定義は flat。
# ---------------------------------------------------------------------------

COMPONENTS: Dict[str, bt.BetComponent] = {
    # honmei_formation の保険: 三連複 ◎-相手総流し (6点)
    "puku": bt.BetComponent("sanrenpuku",
                            [["◎"], ["○", "▲", "△", "Ⅲ"], ["○", "▲", "△", "Ⅲ"]]),
    # honmei_formation のボーナス: 三連単 ◎○▲ BOX (6点)
    "tan3": bt.BetComponent("sanrentan",
                            [["◎", "○", "▲"], ["◎", "○", "▲"], ["◎", "○", "▲"]]),
    # 買い足し候補 (B案)
    "tansho": bt.BetComponent("tansho", [["◎"]]),
    "umatan": bt.BetComponent("umatan", [["◎"], ["○", "▲"]]),
}
COMP_ORDER = ["puku", "tan3", "tansho", "umatan"]

# sweep グリッド (0 = そのコンポーネントを買わない)
GRID: Dict[str, Tuple[float, ...]] = {
    "puku": (0.5, 0.75, 1.0),
    "tan3": (0.0, 0.1, 0.25, 0.4, 0.5, 0.75, 1.0),
    "tansho": (0.0, 0.5, 1.0),
    "umatan": (0.0, 0.25, 0.5),
}

# アンカー構成 (表で必ず出す基準点)
ANCHORS: List[Tuple[str, Dict[str, float]]] = [
    ("現行 honmei_formation", {"puku": 1.0, "tan3": 0.25, "tansho": 0.0, "umatan": 0.0}),
    ("三連複のみ (保険单独)", {"puku": 1.0, "tan3": 0.0, "tansho": 0.0, "umatan": 0.0}),
    ("三連単BOXのみ", {"puku": 0.0, "tan3": 1.0, "tansho": 0.0, "umatan": 0.0}),
    ("フル本命セット例", {"puku": 1.0, "tan3": 0.25, "tansho": 1.0, "umatan": 0.25}),
]


# ---------------------------------------------------------------------------
# レコード構築 (コンポーネント別 flat 精算 1回)
# ---------------------------------------------------------------------------

def build_records(races, *, mode: str, haraimodoshi) -> List[dict]:
    recs: List[dict] = []
    skipped_marks = 0
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
        s = re_.strengths
        if mode == "composite":
            marks = bt.marks_from_ranking([x.umaban for x in s])
        else:
            ai_res = assign_ai_marks(entries, step=2)
            marks = ai_marks_to_markset(ai_res.marks) if not ai_res.skipped else {}
        if not marks:
            skipped_marks += 1
            continue
        rid = str(pred["race_id"])
        rpay = haraimodoshi.get(rid, {})

        comp_cp: Dict[str, Tuple[float, float]] = {}
        for cname, comp in COMPONENTS.items():
            tickets = bt.expand_component(comp, marks)
            cost = 100.0 * len(tickets)
            payout = float(sum(ticket_payout(tk, rpay) for tk in tickets))
            comp_cp[cname] = (cost, payout)

        # 本命決着 = 印上位3 (◎○▲) が 1-3着を独占 (順不問)。印<3頭なら判定不能(None)。
        top3_marks = [marks.get(m, [None])[0] for m in ("◎", "○", "▲")]
        honmei: Optional[bool] = None
        if all(u is not None for u in top3_marks):
            fin_top3 = {int(e.get("umaban") or 0) for e in entries
                        if int(e.get("finish_position") or 99) <= 3}
            honmei = fin_top3 == set(top3_marks)

        recs.append({"rid": rid, "date": rid[:8], "comp": comp_cp, "honmei": honmei})
    if skipped_marks:
        print(f"  (marks なしスキップ: {skipped_marks}R)")
    return recs


# ---------------------------------------------------------------------------
# weight 構成の評価 (線形再構成)
# ---------------------------------------------------------------------------

def evaluate(recs: List[dict], w: Dict[str, float]) -> Optional[dict]:
    cost_all = pay_all = 0.0
    fire = hits = 0
    monthly: Dict[str, List[float]] = defaultdict(lambda: [0.0, 0.0])  # ym -> [cost, pay]
    hit_ratios: List[float] = []
    cum = peak = max_dd = 0.0
    hon_cost = hon_pay = 0.0
    n_honmei = 0

    for r in sorted(recs, key=lambda x: x["rid"]):
        c = sum(w[k] * r["comp"][k][0] for k in COMP_ORDER)
        p = sum(w[k] * r["comp"][k][1] for k in COMP_ORDER)
        if c <= 0:
            continue
        cost_all += c
        pay_all += p
        fire += 1
        ym = r["date"][:6]
        monthly[ym][0] += c
        monthly[ym][1] += p
        if p > 0:
            hits += 1
            hit_ratios.append(p / c)
        cum += p - c
        peak = max(peak, cum)
        max_dd = max(max_dd, peak - cum)
        if r["honmei"]:
            hon_cost += c
            hon_pay += p
            n_honmei += 1

    if cost_all <= 0:
        return None
    rois = [v[1] / v[0] * 100 for v in monthly.values() if v[0] > 0]
    hit_sorted = sorted(hit_ratios)

    def _pct(q: float) -> float:
        if not hit_sorted:
            return 0.0
        return hit_sorted[min(len(hit_sorted) - 1, int(q * (len(hit_sorted) - 1)))]

    return {
        "roi": pay_all / cost_all * 100,
        "med": statistics.median(rois) if rois else 0.0,
        "plus": sum(1 for v in rois if v >= 100),
        "n_months": len(rois),
        "max_dd": max_dd,
        "hit_rate": hits / fire * 100 if fire else 0.0,
        "hit_med": statistics.median(hit_sorted) if hit_sorted else 0.0,
        "hit_p90": _pct(0.90),
        "hit_max": hit_sorted[-1] if hit_sorted else 0.0,
        "honmei_roi": hon_pay / hon_cost * 100 if hon_cost > 0 else 0.0,
        "n_honmei": n_honmei,
        "fire": fire,
        "month_inv": cost_all / max(1, len(monthly)),
    }


def pearson(xs: List[float], ys: List[float]) -> Optional[float]:
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    sxx = sum((a - mx) ** 2 for a in xs)
    syy = sum((b - my) ** 2 for b in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / (sxx * syy) ** 0.5


def _wkey(w: Dict[str, float]) -> str:
    return "/".join(f"{w[k]:g}" for k in COMP_ORDER)


def _row(label: str, w: Dict[str, float], m: dict) -> str:
    return (f"  {label:<26}{_wkey(w):>18}{m['roi']:>7.1f}%{m['med']:>7.1f}%"
            f"{m['plus']:>3}/{m['n_months']:<3}{m['max_dd']:>9,.0f}{m['hit_rate']:>6.1f}%"
            f"{m['hit_med']:>6.2f}{m['hit_p90']:>7.2f}{m['hit_max']:>7.1f}"
            f"{m['honmei_roi']:>8.0f}%{m['month_inv']:>9,.0f}")


HEADER = (f"  {'構成':<26}{'w(puku/tan3/単/馬単)':>18}{'ROI':>8}{'月中央':>8}{'+月':>7}"
          f"{'maxDD':>9}{'hit率':>7}{'hit中':>6}{'hitP90':>7}{'hitMax':>7}{'本命ROI':>9}{'月投資':>9}")


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--cache-path", default=None)
    p.add_argument("--mode", default="composite", choices=["composite", "ai"])
    p.add_argument("--top", type=int, default=20, help="月中央値順の表示数")
    return p.parse_args()


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = parse_args()
    races = load_backtest_cache(path=Path(args.cache_path) if args.cache_path else None)
    codes = [str(r.get("race_id")) for r in races if r.get("race_id")]
    print(f"backtest_cache: {len(races)} races  mode={args.mode}")
    print("  loading haraimodoshi...")
    haraimodoshi = load_haraimodoshi(codes)
    print(f"  haraimodoshi: {len(haraimodoshi)}  building records...")
    recs = build_records(races, mode=args.mode, haraimodoshi=haraimodoshi)
    n_honmei = sum(1 for r in recs if r["honmei"])
    print(f"  records={len(recs)}  本命決着(印上位3独占)={n_honmei}R "
          f"({n_honmei / len(recs) * 100:.1f}%)\n")

    # --- 1. コンポーネント単体 (flat 100円) ---
    print("=" * 110)
    print("  ◆ コンポーネント単体 (flat 100円/点)")
    print(HEADER)
    print("  " + "-" * 106)
    for cname in COMP_ORDER:
        w = {k: (1.0 if k == cname else 0.0) for k in COMP_ORDER}
        m = evaluate(recs, w)
        if m:
            print(_row(f"単体 {cname}", w, m))

    # --- 2. コンポーネント間 レースPnL 相関 (flat) ---
    print("\n  ◆ コンポーネント間 レースPnL相関 (松風知見9: 高相関の併用=同じ賭けを2回)")
    pnl: Dict[str, List[float]] = {k: [] for k in COMP_ORDER}
    for r in sorted(recs, key=lambda x: x["rid"]):
        for k in COMP_ORDER:
            c, p = r["comp"][k]
            pnl[k].append(p - c)
    print("  " + " " * 10 + "".join(f"{k:>10}" for k in COMP_ORDER))
    for a in COMP_ORDER:
        row = f"  {a:<10}"
        for b in COMP_ORDER:
            r_ = pearson(pnl[a], pnl[b])
            row += f"{r_:>10.2f}" if r_ is not None else f"{'-':>10}"
        print(row)

    # --- 3. アンカー構成 ---
    print("\n" + "=" * 110)
    print("  ◆ アンカー構成")
    print(HEADER)
    print("  " + "-" * 106)
    for label, w in ANCHORS:
        m = evaluate(recs, w)
        if m:
            print(_row(label, w, m))

    # --- 4. sweep (月中央値順 Top N) ---
    results: List[Tuple[Dict[str, float], dict]] = []
    for vals in product(*(GRID[k] for k in COMP_ORDER)):
        w = dict(zip(COMP_ORDER, vals))
        if all(v == 0 for v in vals):
            continue
        m = evaluate(recs, w)
        if m:
            results.append((w, m))
    results.sort(key=lambda x: (-x[1]["med"], -x[1]["roi"]))
    print("\n" + "=" * 110)
    print(f"  ◆ sweep 全{len(results)}構成 — 月中央値ROI 順 Top {args.top}")
    print(HEADER)
    print("  " + "-" * 106)
    for w, m in results[:args.top]:
        print(_row("", w, m))

    # --- 5. 「でかく勝つ」フロンティア: 月中央値 >= 閾値 で hitP90 最大 ---
    print(f"\n  ◆ フロンティア: 月中央値 >= 95% を守りつつ hitP90 (でかく勝つ) 最大化")
    cand = [x for x in results if x[1]["med"] >= 95.0]
    cand.sort(key=lambda x: -x[1]["hit_p90"])
    print(HEADER)
    print("  " + "-" * 106)
    for w, m in cand[:10]:
        print(_row("", w, m))
    print("\n  hit中/hitP90/hitMax = 的中レースの payout/cost 倍率 (中央値/90%点/最大)。"
          "本命ROI = 印上位3が1-3着独占レースだけのROI")
    return 0


if __name__ == "__main__":
    sys.exit(main())
