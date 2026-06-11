#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""キャラ別バンクロールsim 結果を JSON 出力 (Session 149 / web /analysis/character-sim 用)

simulate_bankroll_character のキャラ別複利軌道 + flat OOS 検証を **SoT** として
JSON 化する。 web は読むだけ (bet-lab / simulation で確立した
「Python artifact → web 表示」 パターン)。

出力 (キャラ毎):
  - 複利 (全期間・後知恵込み表示用): final_w / growth / max_dd / sharpe / ruin / flat_roi
  - 検証規律 (flat 100円集計): roi_valid (OOS) / median_roi / plus_months / 前後半
  - 軌道: history[] = {date, bankroll} (equity curve)
  - 系列: monthly[] / warnings[] (odds_dependent・ringfenced)

Output: data3/ml/character_simulation.json  (+ versions/v{version}/ にアーカイブ)

Usage:
    python -m ml.export_character_simulation
    python -m ml.export_character_simulation --split-date 2026-01-01 --mc 3000
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import config  # noqa: E402
from ml.analyze.backtest_bet_templates import load_haraimodoshi  # noqa: E402
from ml.analyze.bankroll_core import DEFAULT_MC  # noqa: E402
from ml.analyze.simulate_bankroll_character import (  # noqa: E402
    DEFAULT_SPLIT, DEFAULT_W0, build_tmpl_contexts, run_character,
)
from ml.strategies import bet_templates as bt  # noqa: E402
from ml.strategies import characters as ch  # noqa: E402
from ml.utils.backtest_cache import load_backtest_cache  # noqa: E402

# sim 版 (キャラ定義/比例ベットの版。 モデル version とは別軸)。
SIM_VERSION = "1.0"


def _build_history(stats, eff_w0) -> list:
    """equity curve → history[{date, bankroll}]。 先頭は初期資金 (date=None)。"""
    hist = [{"date": None, "bankroll": round(eff_w0)}]
    for i, d in enumerate(stats.dates):
        if d:  # 破産後の穴埋め ("") は除外
            hist.append({"date": d, "bankroll": round(stats.equity[i + 1])})
    return hist


def parse_args():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("--cache-path", default=None)
    p.add_argument("--w0", type=int, default=DEFAULT_W0)
    p.add_argument("--split-date", default=DEFAULT_SPLIT)
    p.add_argument("--characters", default=None, help="カンマ区切り key (既定=全キャラ)")
    p.add_argument("--mc", type=int, default=DEFAULT_MC)
    return p.parse_args()


def main() -> int:
    if sys.platform == "win32":
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    print("=" * 80)
    print("  Character Bankroll Simulation → JSON Export (/analysis/character-sim)")
    print("=" * 80)

    args = parse_args()
    split = args.split_date.replace("-", "")
    races = load_backtest_cache(path=Path(args.cache_path) if args.cache_path else None)
    chars = ([ch.get_character(k.strip()) for k in args.characters.split(",")]
             if args.characters else ch.CHARACTERS)
    codes = [str(r.get("race_id")) for r in races if r.get("race_id")]

    print(f"  backtest_cache: {len(races)} races  W0={args.w0:,}  split={args.split_date}")
    print("  loading haraimodoshi...")
    haraimodoshi = load_haraimodoshi(codes)
    print(f"  haraimodoshi: {len(haraimodoshi)}  building contexts (process_race)...")
    by_date = build_tmpl_contexts(races, characters=chars, haraimodoshi=haraimodoshi)
    if not by_date:
        print("  [ERROR] no contexts built")
        return 1

    all_dates = sorted(by_date)
    months = sorted({f"{d[:4]}-{d[4:6]}" for d in all_dates})
    total_races = sum(len(v) for v in by_date.values())
    print(f"  contexts: {total_races} races  {len(all_dates)} days  "
          f"{len(months)} months ({months[0]}~{months[-1]})")

    characters_out = []
    for c in chars:
        r = run_character(c, by_date, w0=args.w0, mc=args.mc, split=split)
        st, fl = r.stats, r.flat
        t_meta = [{"key": n, "label": bt.get_template(n).label} for n in c.templates]
        characters_out.append({
            "key": c.key, "name": c.name,
            "templates": list(c.templates), "template_meta": t_meta,
            "mark_mode": c.mark_mode,
            "ringfenced": c.ringfenced, "odds_dependent": c.odds_dependent,
            "day_fraction": r.day_fraction, "unit_fraction": r.unit_fraction,
            "eff_w0": r.eff_w0,
            # 複利 (全期間・後知恵込み表示用)
            "final_w": round(st.final_w), "growth_pct": round(st.growth_pct, 1),
            "max_dd_pct": round(st.max_dd_pct, 1), "sharpe": round(st.sharpe, 3),
            "ruin_prob_pct": round(st.ruin_prob_pct, 1),
            "flat_roi_pct": round(st.flat_roi_pct, 1),
            "tail_day_rate": round(st.tail_day_rate, 1), "bet_days": st.bet_days,
            # 検証規律 (flat 100円集計)
            "roi": fl["roi"], "roi_train": fl["roi_train"], "roi_valid": fl["roi_valid"],
            "median_roi": fl["median_roi"], "plus_months": fl["plus_months"],
            "roi_first_half": fl["roi_first_half"], "roi_second_half": fl["roi_second_half"],
            "hit_rate": fl["hit_rate"], "fire": fl["fire"], "hits": fl["hits"],
            "monthly": fl["monthly"],
            "history": _build_history(st, r.eff_w0),
            "note": c.note, "warnings": list(c.warnings),
        })

    result = {
        "created_at": datetime.now().isoformat(),
        "sim_version": SIM_VERSION,
        "initial_bankroll": args.w0,
        "split_date": args.split_date,
        "data_source": "backtest_cache + haraimodoshi (実配当)。 複利軌道は全期間="
                       "後知恵込みの表示用 (in-sample を含む)。 正直な OOS は roi_valid "
                       "(split以降)・月別 median_roi。 1点 stake = 総資金 × unit_fraction "
                       "の比例ベット (評価ベース・Kelly/EV/オッズで歪めない)。",
        "period_start": f"{all_dates[0][:4]}-{all_dates[0][4:6]}-{all_dates[0][6:8]}",
        "period_end": f"{all_dates[-1][:4]}-{all_dates[-1][4:6]}-{all_dates[-1][6:8]}",
        "total_races": total_races,
        "months": months,
        "characters": characters_out,
    }

    out_path = config.ml_dir() / "character_simulation.json"
    out_json = json.dumps(result, ensure_ascii=False, indent=2)
    out_path.write_text(out_json, encoding="utf-8")
    print(f"\n  Saved: {out_path}  ({len(out_json) // 1024} KB)")

    # version アーカイブ (bet-lab / formation exporter と同じ作法)
    meta_path = config.ml_dir() / "model_meta.json"
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            version = meta.get("version", "")
            if version:
                archive_dir = config.ml_dir() / "versions" / f"v{version}"
                archive_dir.mkdir(parents=True, exist_ok=True)
                (archive_dir / "character_simulation.json").write_text(out_json, encoding="utf-8")
                print(f"  Archive: {archive_dir / 'character_simulation.json'}")
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [warn] archive skipped: {e}")

    # サマリ
    print(f"\n  {'character':<16}{'finalW':>12}{'growth':>9}{'maxDD':>8}"
          f"{'flatROI':>9}{'median':>8}{'OOSvalid':>9}{'+月':>7}")
    for c in characters_out:
        rf = " [隔離]" if c["ringfenced"] else (" ⚠" if c["odds_dependent"] else "")
        print(f"  {c['name']:<16}{c['final_w']:>12,}{c['growth_pct']:>+8.0f}%"
              f"{c['max_dd_pct']:>7.1f}%{c['flat_roi_pct']:>8.1f}%{c['median_roi']:>7.1f}%"
              f"{c['roi_valid']:>8.1f}%{c['plus_months']:>7}{rf}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
