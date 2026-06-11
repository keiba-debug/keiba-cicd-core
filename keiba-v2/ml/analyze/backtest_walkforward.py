#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Phase3b: 勝負レース条件 × テンプレ の月別ROI推移 (walk-forward / Session 146)

valid 24日の単一区間だと「高配当1本でROIが跳ねる」偶然に騙される (Phase3で発覚)。
→ 全期間を月別に切り、各月を OOS 的に見て **月別ROIの推移** で安定性を判定する。

判定指標 (1本の万馬券で歪む平均でなく、 ロバストな中央値を重視):
  - +月数/全月数 : ROI>=100% の月の割合 (安定して勝てるか)
  - 中央値ROI    : 月別ROIの中央値 (半分の月でこれ以上)
  - 平均ROI      : 参考 (高配当で上振れする)
  - 月平均fire   : 1ヶ月の発火レース数 (薄い条件の注意)

精算は haraimodoshi 実配当。 flat 100円/点。

CLI:
    python -m ml.analyze.backtest_walkforward
    python -m ml.analyze.backtest_walkforward --max-rest 4
"""

from __future__ import annotations

import argparse
import io
import statistics
import sys
from pathlib import Path
from typing import Callable, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.analyze.backtest_bet_templates import load_haraimodoshi  # noqa: E402
from ml.analyze.backtest_selector import CONDITIONS, build_records  # noqa: E402
from ml.strategies import bet_templates as bt  # noqa: E402
from ml.utils.backtest_cache import load_backtest_cache  # noqa: E402

# 月別推移を見る対象 (絞って可読性確保)
FOCUS_CONDITIONS = ["ALL (全レース)", "堅い2強", "軸強 EV>=1.1", "荒れ | 軸強", "荒れ 1人気>=4"]
FOCUS_TEMPLATES = ["fukusho_korogashi", "wide_anchor", "honmei_hoken",
                   "sanrenpuku_1jiku", "sanrentan_roman"]


def monthly_roi(recs, *, cond: Callable, template: str, months: List[str]):
    """月別 (roi, fire) のリスト。"""
    out = []
    for m in months:
        cost = payout = 0.0
        fire = 0
        for r in recs:
            if r["date"][:6] != m or not cond(r):
                continue
            c, p = r["tpl"][template]
            if c <= 0:
                continue
            cost += c
            payout += p
            fire += 1
        roi = payout / cost * 100 if cost > 0 else None
        out.append((m, roi, fire))
    return out


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--cache-path", default=None)
    p.add_argument("--max-rest", type=int, default=4)
    p.add_argument("--conditions", default=None,
                   help="カンマ区切りの条件名 (既定=FOCUS_CONDITIONS)")
    p.add_argument("--templates", default=None,
                   help="カンマ区切りのテンプレ名 (既定=FOCUS_TEMPLATES)")
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
    names = bt.list_templates()
    print(f"backtest_cache: {len(races)} races  max_rest={args.max_rest}")
    print("  loading haraimodoshi...")
    haraimodoshi = load_haraimodoshi(codes)
    print(f"  haraimodoshi: {len(haraimodoshi)}  building records...")
    recs = build_records(races, template_names=names, max_rest=args.max_rest,
                         haraimodoshi=haraimodoshi)
    months = sorted({r["date"][:6] for r in recs})
    print(f"  records={len(recs)}  months={len(months)} ({months[0]}~{months[-1]})\n")

    focus_conds = ([x.strip() for x in args.conditions.split(",")] if args.conditions
                   else FOCUS_CONDITIONS)
    focus_tpls = ([x.strip() for x in args.templates.split(",")] if args.templates
                  else FOCUS_TEMPLATES)
    for cond_name in focus_conds:
        cond = CONDITIONS[cond_name]
        print(f"{'='*112}")
        print(f"  ◆ 条件: {cond_name}")
        print(f"  {'template':<18}" + "".join(f"{m[2:]:>6}" for m in months)
              + f"{'│+月':>6}{'中央値':>7}{'平均':>6}{'月fire':>7}")
        print(f"  {'-'*108}")
        for tpl in focus_tpls:
            series = monthly_roi(recs, cond=cond, template=tpl, months=months)
            roi_vals = [roi for _, roi, _ in series if roi is not None]
            fires = [f for _, _, f in series]
            if not roi_vals:
                continue
            plus = sum(1 for v in roi_vals if v >= 100)
            med = statistics.median(roi_vals)
            avg = statistics.mean(roi_vals)
            avg_fire = statistics.mean(fires)
            cells = ""
            for _, roi, f in series:
                if roi is None:
                    cells += f"{'-':>6}"
                else:
                    cells += f"{roi:>5.0f}"
                    cells += "*" if roi >= 100 else " "
            star = " ★" if med >= 100 else ""
            print(f"  {tpl:<18}{cells}│{plus:>2}/{len(roi_vals):<2}{med:>6.0f}%{avg:>5.0f}%"
                  f"{avg_fire:>7.1f}{star}")
        print()
    print("  数字=その月のROI%% (*=100%%超), +月=ROI>=100%%の月数/有効月数, "
          "中央値=月別ROIの中央値 (★=中央値>=100%%)")
    print("  → 安定して勝てる = 全月コンスタントに*が付き中央値>=100%%。"
          "1-2月だけ跳ねるのは高配当の偶然 (信用しない)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
