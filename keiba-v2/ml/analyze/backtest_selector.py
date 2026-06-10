#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Phase3: 勝負レース・セレクタ backtest (Session 146)

「レース特性で買う/降りるを選別 → そのレースだけ買う」と ROI がどう変わるか、
train/valid で検証する。 ふくだの「本気でレース選択すればプラスの望み」を実証し、
「勝負レース購入します！」の発火条件を定量化する。

★ふくだ重視の "対象レース出現数" を主要メトリクスに:
  - fire        : 条件に合致して買ったレース数
  - R/日        : fire / 全開催日数 (平均何レース/日 発火するか)
  - 月投資      : cost / 月数 (1ヶ月の投資額)
  - 的中間隔    : fire / 的中レース数 (何レース買って1的中か)

精算は haraimodoshi 実配当 (Phase2 と同じ)。 flat 100円/点。

CLI:
    python -m ml.analyze.backtest_selector
    python -m ml.analyze.backtest_selector --split-date 2026-01-01 --max-rest 4
"""

from __future__ import annotations

import argparse
import io
import sys
from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, List, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.analyze.backtest_bettype_fund import cache_race_to_pred  # noqa: E402
from ml.analyze.backtest_bet_templates import (  # noqa: E402
    load_haraimodoshi, ticket_payout,
)
from ml.strategies import bet_templates as bt  # noqa: E402
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.utils.backtest_cache import load_backtest_cache  # noqa: E402


# ---------------------------------------------------------------------------
# 勝負レース条件 (データ駆動・race record -> bool)
# record: {fav_odds, axis_ev, n, top2, rid, date}
# ---------------------------------------------------------------------------

CONDITIONS: Dict[str, Callable[[dict], bool]] = {
    "ALL (全レース)": lambda r: True,
    "荒れ 1人気>=4": lambda r: r["fav_odds"] >= 4.0,
    "軸強 EV>=1.1": lambda r: r["axis_ev"] >= 1.1,
    "荒れ | 軸強": lambda r: r["fav_odds"] >= 4.0 or r["axis_ev"] >= 1.1,
    "荒れ & 多頭16+": lambda r: r["fav_odds"] >= 4.0 and r["n"] >= 16,
    "軸強 & 中頭数": lambda r: r["axis_ev"] >= 1.1 and r["n"] <= 15,
    "堅い2強": lambda r: r["top2"] >= 0.50,
}


# ---------------------------------------------------------------------------
# キャッシュ構築 (process_race + 各テンプレ精算を 1 回だけ)
# ---------------------------------------------------------------------------

def build_records(races, *, template_names, max_rest, haraimodoshi) -> List[dict]:
    recs: List[dict] = []
    for raw in races:
        pred = cache_race_to_pred(raw)
        if pred is None:
            continue
        if not any(int(e.get("finish_position") or 99) == 1 for e in pred.get("entries", [])):
            continue
        re_ = be.process_race(pred)
        if re_ is None or not re_.strengths:
            continue
        s = re_.strengths
        n = len(s)
        axis = s[0]
        fav_odds = min((x.odds for x in s if x.odds and x.odds > 0), default=0.0)
        axis_ev = (axis.win_prob * axis.odds) if (axis and axis.odds) else 0.0
        top2 = (s[0].win_prob + s[1].win_prob) if n >= 2 else axis.win_prob
        marks = bt.marks_from_ranking([x.umaban for x in s], max_rest=max_rest)
        rid = str(pred["race_id"])
        rpay = haraimodoshi.get(rid, {})
        tpl_cp: Dict[str, Tuple[float, float]] = {}
        for name in template_names:
            tickets = bt.apply_template(bt.get_template(name), marks)
            cost = 100.0 * len(tickets)
            payout = float(sum(ticket_payout(tk, rpay) for tk in tickets))
            tpl_cp[name] = (cost, payout)
        recs.append({
            "rid": rid, "date": rid[:8], "n": n, "fav_odds": fav_odds,
            "axis_ev": axis_ev, "top2": top2, "tpl": tpl_cp,
        })
    return recs


# ---------------------------------------------------------------------------
# 集計
# ---------------------------------------------------------------------------

def _months(dates) -> int:
    return len({d[:6] for d in dates}) or 1


def aggregate(recs: List[dict], *, template_names, cond) -> Dict[str, dict]:
    fired = [r for r in recs if cond(r)]
    all_days = {r["date"] for r in recs}
    n_days = len(all_days) or 1
    n_months = _months(all_days)
    out = {}
    for name in template_names:
        cost = payout = 0.0
        n_races = hits = 0
        for r in fired:
            c, p = r["tpl"][name]
            if c <= 0:
                continue
            cost += c
            payout += p
            n_races += 1
            if p > 0:
                hits += 1
        roi = payout / cost * 100 if cost > 0 else 0.0
        out[name] = {
            "fire": n_races, "hits": hits, "roi": roi, "cost": cost, "payout": payout,
            "per_day": n_races / n_days, "month_inv": cost / n_months,
            "interval": (n_races / hits) if hits else float("inf"),
            "hit_rate": hits / n_races * 100 if n_races else 0.0,
        }
    return out


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--cache-path", default=None)
    p.add_argument("--split-date", default="2026-01-01", help="train/valid 分割")
    p.add_argument("--max-rest", type=int, default=4)
    p.add_argument("--templates", default=None)
    return p.parse_args()


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    args = parse_args()
    races = load_backtest_cache(path=Path(args.cache_path) if args.cache_path else None)
    split = args.split_date.replace("-", "")
    names = ([x.strip() for x in args.templates.split(",")] if args.templates
             else bt.list_templates())

    codes = [str(r.get("race_id")) for r in races if r.get("race_id")]
    print(f"backtest_cache: {len(races)} races  split={args.split_date}  max_rest={args.max_rest}")
    print("  loading haraimodoshi...")
    haraimodoshi = load_haraimodoshi(codes)
    print(f"  haraimodoshi: {len(haraimodoshi)}  building records (process_race)...")
    recs = build_records(races, template_names=names, max_rest=args.max_rest,
                         haraimodoshi=haraimodoshi)
    train = [r for r in recs if r["date"] < split]
    valid = [r for r in recs if r["date"] >= split]
    print(f"  records: {len(recs)} (train={len(train)} valid={len(valid)})")

    for cond_name, cond in CONDITIONS.items():
        ag_t = aggregate(train, template_names=names, cond=cond)
        ag_v = aggregate(valid, template_names=names, cond=cond)
        fire_t = max((ag_t[n]["fire"] for n in names), default=0)
        fire_v = max((ag_v[n]["fire"] for n in names), default=0)
        print(f"\n{'='*100}")
        print(f"  ◆ 条件: {cond_name}   (train発火={fire_t}R / valid発火={fire_v}R)")
        print(f"  {'template':<20}{'train ROI':>10}{'valid ROI':>10}{'valid的中率':>11}"
              f"{'R/日':>7}{'月投資':>10}{'的中間隔':>9}")
        print(f"  {'-'*94}")
        for name in names:
            t = ag_t[name]
            v = ag_v[name]
            iv = v["interval"]
            iv_s = f"{iv:.0f}R" if iv != float("inf") else "—"
            star = " ★" if v["roi"] >= 100.0 and v["fire"] >= 20 else ""
            print(f"  {name:<20}{t['roi']:>9.0f}%{v['roi']:>9.0f}%{v['hit_rate']:>10.0f}%"
                  f"{v['per_day']:>7.2f}{v['month_inv']:>10,.0f}{iv_s:>9}{star}")
    print(f"\n  ★ = valid ROI>=100% かつ valid発火>=20R (OOSで黒字の現実味)")
    print(f"  R/日=valid期間の平均発火レース/日 / 月投資=valid月あたり投資額 / 的中間隔=何R買って1的中")
    return 0


if __name__ == "__main__":
    sys.exit(main())
