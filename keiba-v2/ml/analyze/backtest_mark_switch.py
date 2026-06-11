#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""AI印数 → 買い方テンプレ切替の検証 (Session 149 / 自動購入バージョンアップ)

★仮説（事前固定・スヌーピング回避のため1パターンのみ。 総当たりで良い組合せを拾う禁止）:
  assign_ai_marks(step2) の印数 = モデルの確信構造 (複勝率の崖)。 印数帯で買い方を切り替える。
    skip (撃ちなし)      → 見送り (買わない)
    1-2頭 (上位に確信)   → honmei_plus_tansho (◎単勝厚め + 三連複保険)
    3頭   (中間)         → honmei_hoken       (馬連 ◎-○▲)
    4-5頭 (勝負圏が広い)  → wide_anchor        (ワイド◎流し + 三連複)

判定: 選定器の「月別ROI中央値」「OOS(valid)」が、 固定ベンチ
  (同じ対象レース × wide_anchor / × honmei_plus_tansho) を上回るか。
  上回らなければ「切替は固定に勝てない＝不採用、固定でよい」。

オッズ非依存 (印数=複勝率の崖=ML由来) なので後知恵フリー。 精算は haraimodoshi 実配当、
flat 100円/点 (sizing は別問題)。 対象レースは selector/bench とも揃える (skip は両方見送り)。

CLI:
    python -m ml.analyze.backtest_mark_switch --split-date 2026-01-01
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ml.ai_marks.assign import assign_ai_marks  # noqa: E402
from ml.analyze.backtest_bet_templates import load_haraimodoshi  # noqa: E402
from ml.analyze.backtest_bettype_fund import cache_race_to_pred  # noqa: E402
from ml.analyze.simulate_bankroll_character import (  # noqa: E402
    TmplRaceCtx, aggregate_char_flat, ai_marks_to_markset, settle_templates_cp,
)
from ml.strategies import bettype_efficiency as be  # noqa: E402
from ml.utils.backtest_cache import load_backtest_cache  # noqa: E402

# --- 仮説（事前固定）---
SWITCH = {
    1: "honmei_plus_tansho", 2: "honmei_plus_tansho",
    3: "honmei_hoken",
    4: "wide_anchor", 5: "wide_anchor",
}
BENCH = {"bench_wide": "wide_anchor", "bench_hpt": "honmei_plus_tansho"}


def build(races, haraimodoshi):
    by_date = {}
    mark_dist = {}
    n_skip = n_total = 0
    for raw in races:
        pred = cache_race_to_pred(raw)
        if pred is None:
            continue
        if not any(int(e.get("finish_position") or 99) == 1
                   for e in pred.get("entries", [])):
            continue
        re_ = be.process_race(pred)
        if re_ is None or not re_.strengths:
            continue
        n_total += 1
        rid = str(pred["race_id"])
        rpay = haraimodoshi.get(rid, {})
        ai = assign_ai_marks(pred["entries"], step=2)
        if ai.skipped:
            n_skip += 1
            continue  # 見送り (selector も bench も買わない=対象外)
        marks = ai_marks_to_markset(ai.marks)
        n = len(ai.marks)
        mark_dist[n] = mark_dist.get(n, 0) + 1
        tmpl = SWITCH.get(n)
        settle = {"selector": settle_templates_cp((tmpl,), marks, rpay) if tmpl else (0.0, 0.0)}
        for bk, name in BENCH.items():
            settle[bk] = settle_templates_cp((name,), marks, rpay)
        by_date.setdefault(rid[:8], []).append(TmplRaceCtx(rid, rid[:8], settle))
    return dict(sorted(by_date.items())), mark_dist, n_skip, n_total


def _fmt(label, agg):
    return (f"  {label:<22}{agg['fire']:>6}{agg['hit_rate']:>7.1f}%{agg['roi']:>8.1f}%"
            f"{agg['median_roi']:>8.1f}%{agg['roi_valid']:>9.1f}%{agg['plus_months']:>7}"
            f"{agg['roi_first_half']:>8.1f}%{agg['roi_second_half']:>8.1f}%")


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--cache-path", default=None)
    p.add_argument("--split-date", default="2026-01-01")
    args = p.parse_args()
    split = args.split_date.replace("-", "")

    races = load_backtest_cache(path=Path(args.cache_path) if args.cache_path else None)
    codes = [str(r.get("race_id")) for r in races if r.get("race_id")]
    print(f"backtest_cache: {len(races)} races  split={args.split_date}")
    print("  loading haraimodoshi...")
    haraimodoshi = load_haraimodoshi(codes)
    print(f"  haraimodoshi: {len(haraimodoshi)}  building (process_race + assign_ai_marks)...")
    by_date, mark_dist, n_skip, n_total = build(races, haraimodoshi)

    fired = sum(len(v) for v in by_date.values())
    print(f"\n  結果確定 {n_total}R  /  AI skip(見送り) {n_skip}R  /  対象(印あり) {fired}R")
    print("  AI印数分布: " + "  ".join(
        f"{n}印={mark_dist.get(n, 0)}R→{SWITCH.get(n, '-')}" for n in sorted(mark_dist)))

    sel = aggregate_char_flat(by_date, "selector", split=split)
    bw = aggregate_char_flat(by_date, "bench_wide", split=split)
    bh = aggregate_char_flat(by_date, "bench_hpt", split=split)

    print(f"\n{'='*96}")
    print(f"  {'戦略':<22}{'fire':>6}{'的中率':>8}{'ROI':>8}{'中央値':>8}"
          f"{'OOSvalid':>9}{'+月':>7}{'前半':>8}{'後半':>8}")
    print(f"  {'-'*92}")
    print(_fmt("印数切替 selector", sel))
    print(_fmt("固定 wide_anchor", bw))
    print(_fmt("固定 honmei+tansho", bh))
    print(f"  {'-'*92}")

    # 判定 (中央値 と OOSvalid で固定ベンチを上回るか)
    win_med = sel["median_roi"] > max(bw["median_roi"], bh["median_roi"])
    win_oos = sel["roi_valid"] > max(bw["roi_valid"], bh["roi_valid"])
    print(f"\n  判定: 中央値 {'○' if win_med else '×'} "
          f"(切替 {sel['median_roi']:.1f}% vs 固定max {max(bw['median_roi'], bh['median_roi']):.1f}%)  /  "
          f"OOSvalid {'○' if win_oos else '×'} "
          f"(切替 {sel['roi_valid']:.1f}% vs 固定max {max(bw['roi_valid'], bh['roi_valid']):.1f}%)")
    if win_med and win_oos:
        print("  → 切替が固定を中央値・OOS 両方で上回る。 採用検討の価値あり。")
    else:
        print("  → 切替は固定に勝てない。 仮説どおりなら『固定でよい』が結論 (切替の複雑さは不要)。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
